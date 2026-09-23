"""Post-run structural coverage audit; this is not semantic or financial truth."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path

from againward.domains.rental.models import BILLING_UNITS, CHARGE_TYPES, DOCUMENT_ROLES

REQUIRED = {
    "RENTAL_SCOPE": {"document_role", "document_status", "agreement_id", "supplier_id", "client_id",
                     "description", "start", "end", "quantity", "rate", "currency", "charge_key",
                     "charge_type", "billing_unit", "stop_event"},
    "INVOICE_LINE": {"document_role", "document_status", "invoice_id", "invoice_line_id", "supplier_id",
                     "agreement_id", "net_amount", "currency", "charge_key", "charge_type"},
    "CREDIT": {"document_role", "document_status", "credit_id", "supplier_id", "net_amount",
               "currency", "status"},
    "RETURN": {"document_role", "document_status", "agreement_id", "event_type",
               "date", "quantity", "verification"},
    "RATE_AMENDMENT": {"document_role", "document_status", "agreement_id", "supplier_id",
                       "rate", "currency", "charge_key", "charge_type", "effective_from", "terms_unchanged"},
}
STOP_EVENTS = {"CONTRACT_END", "RETURNED", "COLLECTED", "OFF_HIRE_REQUESTED"}


def audit_semantic_preflight(run: Path) -> dict:
    run = Path(run)
    raw = (run / "semantic_observations.json").read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != (run / "semantic_observations.sha256").read_text().strip():
        raise ValueError("Participant observations changed before preflight audit")
    observations = json.loads(raw)
    summary: Counter[str] = Counter()
    cases = {}
    for case_id, case in observations["cases"].items():
        case_counter: Counter[str] = Counter()
        gaps = []
        for document in case["documents"]:
            case_counter["documents"] += 1
            case_counter["candidates"] += len(document["candidates"])
            if document["status"] in {"ABSTAIN", "FAILED"}:
                case_counter["failed_documents"] += 1
            entities: dict[str, dict[str, list[object]]] = {}
            for candidate in document["candidates"]:
                group = entities.setdefault(candidate["entity_id"], {})
                group.setdefault(candidate["semantic_type"], []).append(candidate["value"])
                case_counter["flagged_candidates"] += bool(candidate["ambiguity_flags"])
            for entity_id, fields in entities.items():
                kinds = fields.get("entity_kind", [])
                kind = kinds[0] if len(kinds) == 1 else None
                if kind == "SUPPORTING_DOCUMENT":
                    case_counter["supporting_entities"] += 1
                    missing_support = [field for field in ("document_role", "document_status")
                                       if len(fields.get(field, [])) != 1]
                    invalid_support = [field for field, allowed in (("document_role", DOCUMENT_ROLES),
                                                                    ("document_status", {"ACCEPTED", "PROPOSED", "VOID", "EXTRACTED"}))
                                       if fields.get(field) and fields[field][0] not in allowed]
                    if missing_support or invalid_support:
                        case_counter["incomplete_supporting_entities"] += 1
                        gaps.append({"source_sha256": document["source_sha256"], "entity_id": entity_id,
                                     "kind": kind, "missing": missing_support, "invalid_enum": invalid_support})
                    continue
                if kind not in REQUIRED:
                    case_counter["unclassified_entities"] += 1
                    continue
                case_counter["material_entities"] += 1
                missing = sorted(field for field in REQUIRED[kind] if len(fields.get(field, [])) != 1)
                if kind in {"INVOICE_LINE", "RETURN", "RATE_AMENDMENT"} and not (
                        len(fields.get("asset_id", [])) == 1 or len(fields.get("serial_number", [])) == 1):
                    missing.append("asset_id_or_serial_number")
                bad = []
                for field, allowed in (("document_role", DOCUMENT_ROLES),
                                       ("document_status", {"ACCEPTED", "PROPOSED", "VOID", "EXTRACTED"}),
                                       ("charge_type", CHARGE_TYPES), ("billing_unit", BILLING_UNITS),
                                       ("stop_event", STOP_EVENTS)):
                    values = fields.get(field, [])
                    if values and (len(values) != 1 or values[0] not in allowed):
                        bad.append(field)
                if missing or bad:
                    case_counter["incomplete_material_entities"] += 1
                    gaps.append({"source_sha256": document["source_sha256"], "entity_id": entity_id,
                                 "kind": kind, "missing": missing, "invalid_enum": bad})
                else:
                    case_counter["structurally_complete_entities"] += 1
        summary.update(case_counter)
        cases[case_id] = {**case_counter, "gaps": gaps}
    result = {"schema_version": "againward-semantic-preflight-v1", "split": observations["split"],
              "observations_sha256": digest, "metrics": dict(summary), "cases": cases,
              "limits": ["Structural field presence and enum shape only; no semantic truth or human approval.",
                         "Completeness does not prove correct terms, links, credits or financial findings.",
                         "Conservative pilot requirements may exceed the adapter's technical minimum."]}
    target = run / "semantic_preflight.json"
    if target.exists():
        raise ValueError("Prior semantic preflight audit cannot be overwritten")
    target.write_text(json.dumps(result, indent=2) + "\n")
    return result
