from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .evidence_plane import EvidenceDataset, stable_hash
from .evidence_protocol import (
    EvidenceQuery,
    EvidenceQuerySession,
    validate_finding_provenance,
)

from .client_lifecycle import assert_workflow_action_allowed

def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Fichier requis absent: {path}.") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON invalide dans {path}: {exc}.") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{path} doit contenir un objet JSON.")
    return payload


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as handle:
            temporary_name = handle.name
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


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
    root = Path(case_directory)
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


def validate_case_findings(
    case_directory: str | Path, findings_path: str | Path
) -> dict[str, Any]:
    root = Path(case_directory)
    assert_workflow_action_allowed(case_directory, "finding_validation")
    session = EvidenceQuerySession.from_dict(
        _read_json(root / "evidence_query_session.json")
    )
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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interroge l’Evidence Plane local d’un dossier INDICIA."
    )
    parser.add_argument("case_directory")
    parser.add_argument("request_json", nargs="?")
    parser.add_argument(
        "--validate-findings",
        metavar="FINDINGS_JSON",
        help="Valide les références d’un registre de constats agentiques.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.validate_findings:
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
