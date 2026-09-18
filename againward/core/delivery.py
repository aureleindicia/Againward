"""Shared privacy/lifecycle/evidence/human gate with explicit domain review policy."""
from __future__ import annotations
import json
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from .artifact_store import read_json, write_json, artifact_sha256
from .client_lifecycle import lifecycle_directory, validate_client_lifecycle_artifacts
from .privacy import assert_case_privacy_cleared
from againward.evidence.protocol import EvidenceQuerySession, validate_finding_provenance

def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = read_json(path)
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier requis absent: {path}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}: {exc}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} doit contenir un objet JSON.")
    return payload


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _sha256(path: Path) -> str:
    return artifact_sha256(path)


def _append_trace(case_directory: Path, action: str, details: dict[str, Any]) -> None:
    path = case_directory / "trace.json"
    payload = _read_json(path)
    entries = payload.setdefault("entries", [])
    if not isinstance(entries, list):
        raise ValueError("trace.json: entries doit être une liste.")
    entries.append({
        "at_utc": datetime.now(timezone.utc).isoformat(),
        "action": action,
        **details,
    })
    _write_json(path, payload)


def evaluate_delivery_gate(case_directory: str | Path, *, policy) -> dict[str, Any]:
    """Évalue la livrabilité; ne crée jamais une approbation humaine."""

    assert_case_privacy_cleared(case_directory)
    root = lifecycle_directory(case_directory)
    reasons: list[str] = []
    from .contract_policy import assert_contract_permission, contract_policy_digest, POLICY_PATH
    contract = None
    try:
        contract = assert_contract_permission(case_directory, operation="delivery")
    except ValueError as exc:
        reasons.append(str(exc))
    lifecycle_path = root / "investigation_state.json"
    lifecycle_state = None
    if lifecycle_path.exists():
        lifecycle_payload = _read_json(lifecycle_path)
        lifecycle_state = lifecycle_payload.get("client_lifecycle")
        if lifecycle_state is not None:
            try:
                lifecycle_state = validate_client_lifecycle_artifacts(root)
            except ValueError as exc:
                reasons.append(str(exc))
            if isinstance(lifecycle_state, dict) and lifecycle_state.get("state") not in {"FINALIZABLE", "DELIVERABLE"}:
                reasons.append(f"Cycle client non finalisable: état {lifecycle_state.get('state','inconnu')}.")
            if isinstance(lifecycle_state,dict) and lifecycle_state.get("blocking_request_ids"): reasons.append("Des demandes BLOCKING restent ouvertes.")
    required = ("investigation.json", "review.json", "report.md", "human_review.json")
    for name in required:
        if not (root / name).is_file():
            reasons.append(f"Fichier requis absent: {name}.")
    investigation: dict[str, Any] | None = None
    if (root / "investigation.json").is_file():
        try:
            investigation = _read_json(root / "investigation.json")
            policy.validate_investigation(investigation)
        except ValueError as exc:
            reasons.append(str(exc))
    if investigation is not None and (root / "review.json").is_file():
        try:
            policy.validate_review(_read_json(root / "review.json"), investigation)
        except ValueError as exc:
            reasons.append(str(exc))
    if (root / "report.md").is_file() and not (root / "report.md").read_text(
        encoding="utf-8"
    ).strip():
        reasons.append("report.md est vide.")
    if (root / "human_review.json").is_file():
        try:
            human = _read_json(root / "human_review.json")
            if human.get("status") != "approved" or human.get("approved_for_delivery") is not True:
                reasons.append("La revue humaine n'approuve pas encore la livraison.")
            for field in ("reviewer_role", "reviewed_at_utc"):
                if not str(human.get(field, "")).strip():
                    reasons.append(f"Revue humaine incomplète: {field} absent.")
        except ValueError as exc:
            reasons.append(str(exc))
    evidence_artifacts: tuple[str, ...] = ()
    if (root / "evidence_query_session.json").is_file():
        evidence_artifacts = ("evidence_query_session.json", "agent_findings.json")
        if not (root / "agent_findings.json").is_file():
            reasons.append(
                "Fichier requis absent pour le chemin Evidence Plane: agent_findings.json."
            )
        else:
            try:
                session = EvidenceQuerySession.from_dict(
                    _read_json(root / "evidence_query_session.json")
                )
                from againward.evidence.cli import validate_session_artifacts
                validate_session_artifacts(root, session)
                validate_finding_provenance(
                    _read_json(root / "agent_findings.json"), session
                )
            except ValueError as exc:
                reasons.append(str(exc))
    from .workflow_paths import resolve_case_layout
    case_root = Path(resolve_case_layout(case_directory)["case_root"])
    extension = policy.additional_checks(case_directory, root)
    reasons.extend(extension["blocking_reasons"])
    evidence_artifacts += tuple(extension["artifact_names"])
    report_validation = extension["report_validation"]
    payload = {
        "report_validation": report_validation,
        "schema_version": 1,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "contract_policy_ref": POLICY_PATH if contract else None,
        "contract_policy_sha256": contract_policy_digest(contract) if contract else None,
        "status": "ready_for_delivery" if not reasons else "blocked",
        "ready_for_delivery": not reasons,
        "blocking_reasons": reasons,
        "artifact_hashes": {
            name: _sha256(root / name)
            for name in required + evidence_artifacts if (root / name).is_file()
        },
    }
    _write_json(root / "delivery_gate.json", payload)
    policy.update_receipt(case_root, ready=not reasons, report_validation=report_validation)
    if not reasons and lifecycle_state is not None:
        lifecycle_payload=_read_json(lifecycle_path); lifecycle_payload["client_lifecycle"]["state"]="DELIVERABLE"
        lifecycle_payload["client_lifecycle"]["history"].append({"at_utc":payload["evaluated_at_utc"],"action":"marked_deliverable"}); _write_json(lifecycle_path,lifecycle_payload)
    if reasons and isinstance(lifecycle_state, dict) and lifecycle_state.get("state") == "DELIVERABLE":
        lifecycle_payload = _read_json(lifecycle_path)
        lifecycle_payload["client_lifecycle"]["state"] = "FINALIZABLE"
        lifecycle_payload["client_lifecycle"]["history"].append({"at_utc": payload["evaluated_at_utc"], "action": "delivery_approval_invalidated"})
        _write_json(lifecycle_path, lifecycle_payload)
    _append_trace(root, "evaluate_delivery_gate", {
        "status": payload["status"],
        "blocking_reasons": reasons,
    })
    return payload
