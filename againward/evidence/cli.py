from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .plane import EvidenceDataset, stable_hash
from .protocol import (
    EvidenceQuery,
    EvidenceQuerySession,
    validate_finding_provenance,
)

from againward.core.client_lifecycle import assert_workflow_action_allowed
from againward.core.workflow_paths import resolve_analysis_directory
from againward.core.artifact_store import read_json, write_json, transaction, case_mutation

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


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    write_json(path, payload)


def _append_trace(root: Path, action: str, details: dict[str, Any]) -> None:
    path = root / "trace.json"
    payload = _read_json(path)
    entries = payload.get("entries")
    if not isinstance(entries, list):
        raise ValueError("trace.json: entries doit être une liste.")
    entries.append(
        {"at_utc": datetime.now(timezone.utc).isoformat(), "action": action, **details}
    )
    _atomic_write_json(path, payload)


def execute_case_query(
    case_directory: str | Path, request_path: str | Path
) -> dict[str, Any]:
    root = resolve_analysis_directory(case_directory)
    error = None
    with transaction(root):
        try:
            result = _execute_case_query(root, request_path)
        except ValueError as exc:
            # A rejected attempt is still an atomic audit event.
            error = exc
    if error is not None:
        raise error
    return result


def _execute_case_query(case_directory, request_path):
    root = resolve_analysis_directory(case_directory)
    assert_workflow_action_allowed(case_directory, "evidence_query")
    dataset = EvidenceDataset.from_dict(_read_json(root / "evidence_dataset.json"))
    session_path = root / "evidence_query_session.json"
    session = EvidenceQuerySession.from_dict(_read_json(session_path))
    request = _read_json(Path(request_path))
    calls_before = len(session.calls)
    try:
        parsed = EvidenceQuery.from_dict(request)
        response_path = root / "evidence_queries" / f"{parsed.query_id}.json"
        if response_path.exists():
            existing = _read_json(response_path)
            if (parsed.query_id in session.successful_query_ids
                and existing.get("request_sha256") == stable_hash(parsed.to_dict())):
                if session.transport_replays >= session.budget.maximum_rejected_calls:
                    raise ValueError("Budget de replay épuisé; lire la réponse persistée existante.")
                validate_session_artifacts(root, session, dataset=dataset)
                session.transport_replays += 1
                _atomic_write_json(session_path, session.to_dict())
                _append_trace(root, "evidence_query_replayed", {
                    "query_id":parsed.query_id, "response_sha256":existing["response_sha256"],
                    "new_evidence":False, "additional_resource_charge":False,
                })
                return existing
            session._audit_failure(request, "query_id déjà matérialisé dans evidence_queries.")
            raise ValueError("query_id déjà matérialisé dans evidence_queries.")
        response = session.execute(dataset, request)
    except ValueError as exc:
        if len(session.calls) == calls_before:
            session._audit_failure(request, str(exc))
        _atomic_write_json(session_path, session.to_dict())
        _append_trace(
            root,
            "evidence_query_rejected",
            {
                "request_path": str(request_path),
                "request_sha256": stable_hash(request),
                "reason": str(exc),
                "session_status": session.status,
            },
        )
        raise
    _atomic_write_json(response_path, response)
    _atomic_write_json(session_path, session.to_dict())
    _append_trace(
        root,
        "evidence_query_executed",
        {
            "query_id": response["query_id"],
            "operation": response["operation"],
            "request_sha256": response["request_sha256"],
            "response_sha256": response["response_sha256"],
            "response_path": str(response_path.relative_to(root)),
            "handles": [item["handle"] for item in response["retrieval_handles"]],
        },
    )
    return response


@case_mutation
def validate_case_findings(
    case_directory: str | Path, findings_path: str | Path
) -> dict[str, Any]:
    root = resolve_analysis_directory(case_directory)
    assert_workflow_action_allowed(case_directory, "finding_validation")
    session = EvidenceQuerySession.from_dict(
        _read_json(root / "evidence_query_session.json")
    )
    validate_session_artifacts(root, session)
    findings = _read_json(Path(findings_path))
    if findings.get("ground_truth_used") is not False:
        raise ValueError("Le registre de constats doit déclarer ground_truth_used=false.")
    validate_finding_provenance(findings, session)
    _append_trace(
        root,
        "agent_finding_provenance_validated",
        {
            "findings_path": str(findings_path),
            "findings_sha256": stable_hash(findings),
            "finding_ids": [item["finding_id"] for item in findings["findings"]],
        },
    )
    return {"status": "valid", "findings": len(findings["findings"])}


def validate_session_artifacts(root: Path, session: EvidenceQuerySession, *, dataset=None) -> None:
    """Check materialized evidence, not just references in a self-consistent ledger."""
    dataset = dataset or EvidenceDataset.from_dict(_read_json(root / "evidence_dataset.json"))
    if dataset.dataset_sha256 != session.dataset_sha256 or dataset.dataset_id != session.dataset_id:
        raise ValueError("Evidence session refers to another dataset snapshot.")
    for call in session.calls:
        if call.get("status") != "success":
            continue
        response = _read_json(root / "evidence_queries" / f"{call['query_id']}.json")
        body = {key:value for key,value in response.items() if key != "response_sha256"}
        if stable_hash(body) != call["response_sha256"] or response.get("response_sha256") != call["response_sha256"]:
            raise ValueError("Evidence response content hash mismatch.")
        if any(response.get(key) != expected for key, expected in (
            ("session_id",session.session_id),("dataset_sha256",session.dataset_sha256),
            ("query_id",call["query_id"]),("request_sha256",call["request_sha256"]))):
            raise ValueError("Evidence response provenance mismatch.")
        descriptors = response.get("retrieval_handles", [])
        if [item["handle"] for item in descriptors] != call["handles"] or any(
            session.handles.get(item["handle"]) != item for item in descriptors):
            raise ValueError("Evidence response handles mismatch.")


@case_mutation
def continue_case_evidence(case_directory, assessment):
    root = resolve_analysis_directory(case_directory)
    assert_workflow_action_allowed(case_directory, "evidence_query")
    session = EvidenceQuerySession.from_dict(_read_json(root / "evidence_query_session.json"))
    validate_session_artifacts(root, session)
    record = session.continue_investigation(**assessment)
    _atomic_write_json(root / "evidence_query_session.json", session.to_dict())
    _append_trace(root, "evidence_budget_continued", record)
    return record


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interroge l’Evidence Plane local d’un dossier INDICIA."
    )
    parser.add_argument("case_directory")
    parser.add_argument("request_json", nargs="?")
    parser.add_argument("--continue-investigation", metavar="ASSESSMENT_JSON")
    parser.add_argument(
        "--validate-findings",
        metavar="FINDINGS_JSON",
        help="Valide les références d’un registre de constats agentiques.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.continue_investigation:
            if args.request_json or args.validate_findings:
                raise ValueError("Continuation must be a separate operation.")
            result = continue_case_evidence(args.case_directory, _read_json(Path(args.continue_investigation)))
        elif args.validate_findings:
            if args.request_json:
                raise ValueError("Ne fournissez pas request_json avec --validate-findings.")
            result = validate_case_findings(args.case_directory, args.validate_findings)
        else:
            if not args.request_json:
                raise ValueError("request_json est requis pour exécuter une requête.")
            response = execute_case_query(args.case_directory, args.request_json)
            result = {
                "status": "evidence_returned",
                "query_id": response["query_id"],
                "operation": response["operation"],
                "response_sha256": response["response_sha256"],
                "decision": None,
            }
    except (OSError, ValueError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
