"""Blind source reread and conservative, entity-level extraction comparison.

The challenger receives original source units and independent instructions, never
the primary proposal. Agreement is a diagnostic, not proof of correctness or
authority to deliver. Disagreement must be reconciled before fact promotion.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from againward.evidence.hashing import stable_hash
from .codex_provider import CodexCliProvider
from .contracts import DocumentError, SourceBatch
from .extraction import DocumentExtraction, persist_extraction, replay_extraction, validate_proposal
from .readers import read_document
from .sources import verify_batch


QA_GUIDANCE_VERSION = "rental-independent-source-reread-v1"
QA_INSTRUCTIONS = """
INDEPENDENT ADVERSARIAL SOURCE REREAD. You have not seen the first extraction.
Read every original unit/page before answering. Search for material facts the
first pass might omit: all distinct invoice lines, issued credits and their
allocations, accepted terms versus mere proposals, exact quantities, dates,
rates, units, currencies, physical returns versus off-hire requests, and
duplicate exports that must not become new charges. Inspect internal conflicts.
Output source-local observations only, using the same closed Rental vocabulary.
Do not guess missing fields, compute money, or invent cross-document links.
Do not treat a document's existence as proof of contractual acceptance.
"""
RETRY_INSTRUCTIONS = """
The prior response failed strict source/schema validation. Reinspect this
original source. Every native raw_observed_value MUST be an exact substring
appearing exactly once in its named unit; expand the quote with nearby source
words when a numeric token repeats. Do not reuse or edit an unsupported quote.
If the source cannot support a fact with a unique quote, omit that candidate
and state the limitation. Keep all response-schema field names and types exact.
"""

# Material here means fields capable of changing the supported Rental ledger,
# source authority or relationship. This is a triage classification, not a
# claim that other source details are irrelevant to the final report.
MATERIAL_FIELDS = {
    "RENTAL_SCOPE": {"entity_kind", "document_role", "document_status", "agreement_id",
                     "supplier_id", "client_id", "asset_id", "serial_number", "description", "start", "end",
                     "quantity", "rate", "currency", "charge_key", "charge_type", "billing_unit",
                     "weekends_billable", "minimum_days", "partial_period_policy", "stop_event",
                     "stop_day_billable", "discount_fraction"},
    "INVOICE_LINE": {"entity_kind", "document_role", "document_status", "invoice_id",
                     "invoice_line_id", "supplier_id", "agreement_id", "asset_id", "serial_number",
                     "currency", "net_amount", "charge_key", "charge_type", "start", "end",
                     "quantity", "unit_rate", "billed_units"},
    "CREDIT": {"entity_kind", "document_role", "document_status", "credit_id", "supplier_id",
               "currency", "net_amount", "status", "invoice_id", "invoice_line_id",
               "allocated_amount"},
    "RETURN": {"entity_kind", "document_role", "document_status", "agreement_id", "asset_id",
               "serial_number", "event_type", "date", "quantity", "verification"},
    "RATE_AMENDMENT": {"entity_kind", "document_role", "document_status", "agreement_id",
                       "supplier_id", "asset_id", "serial_number", "rate", "currency",
                       "charge_key", "charge_type", "effective_from", "terms_unchanged"},
    "SUPPORTING_DOCUMENT": {"entity_kind", "document_role", "document_status"},
    "IRRELEVANT": {"entity_kind", "document_role", "document_status"},
}


def _entity_records(extraction: DocumentExtraction) -> list[dict[str, Any]]:
    """Keep comparison independent of model-local entity IDs, but show deltas."""
    by_entity: dict[str, list[tuple[str, str, str]]] = {}
    for candidate in extraction.candidates:
        value = json.dumps(candidate.value, sort_keys=True, ensure_ascii=False)
        by_entity.setdefault(candidate.entity_id, []).append(
            (candidate.semantic_type, candidate.value_type, value))
    return [{"entity_id": entity_id,
             "fields": [{"semantic_type": field, "value_type": kind, "value": json.loads(value)}
                        for field, kind, value in sorted(fields)],
             "bundle_sha256": stable_hash(sorted(fields))}
            for entity_id, fields in sorted(by_entity.items())]


def _unmatched(records: list[dict[str, Any]], other: Counter[str]) -> list[dict[str, Any]]:
    remaining = other.copy()
    result = []
    for record in records:
        key = record["bundle_sha256"]
        if remaining[key]:
            remaining[key] -= 1
        else:
            result.append(record)
    return result


def _material_bundles(records: list[dict[str, Any]]) -> Counter[str]:
    bundles: Counter[str] = Counter()
    for record in records:
        fields = {field["semantic_type"]: field["value"] for field in record["fields"]}
        kind = fields.get("entity_kind")
        # Unknown/unclassified entities are not a licence to ignore fields.
        keep = MATERIAL_FIELDS.get(kind if isinstance(kind, str) else "", set(fields))
        bundles[stable_hash({field: value for field, value in fields.items() if field in keep})] += 1
    return bundles


def compare_extractions(batch: SourceBatch, primary: tuple[DocumentExtraction, ...],
                        challenger: tuple[DocumentExtraction, ...], root: Path) -> dict[str, Any]:
    """Fail closed on omissions, entity-field swaps, unreadable sources or stale bytes."""
    verify_batch(batch, root)
    expected = {document.source_id for document in batch.documents}
    if (len(primary) != len(expected) or len(challenger) != len(expected)
            or {extraction.source_id for extraction in primary} != expected
            or {extraction.source_id for extraction in challenger} != expected):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Both passes must cover every source exactly once")
    first = {extraction.source_id: replay_extraction(extraction.to_dict(), batch, root) for extraction in primary}
    second = {extraction.source_id: replay_extraction(extraction.to_dict(), batch, root) for extraction in challenger}
    rows = []
    for document in batch.documents:
        p, q = first[document.source_id], second[document.source_id]
        p_records, q_records = _entity_records(p), _entity_records(q)
        a = Counter(record["bundle_sha256"] for record in p_records)
        b = Counter(record["bundle_sha256"] for record in q_records)
        only_primary = _unmatched(p_records, b)
        only_challenger = _unmatched(q_records, a)
        material_difference = (_material_bundles(p_records) != _material_bundles(q_records)
                               or p.status == "FAILED" or q.status == "FAILED"
                               or bool(p.limitations) or bool(q.limitations))
        difference = bool(a != b or p.status == "FAILED" or q.status == "FAILED"
                          or p.limitations or q.limitations)
        rows.append({"source_id": document.source_id, "source_sha256": document.sha256,
                     "primary_extraction_sha256": p.to_dict()["extraction_sha256"],
                     "challenger_extraction_sha256": q.to_dict()["extraction_sha256"],
                     "primary_status": p.status, "challenger_status": q.status,
                     "primary_only_entity_bundles": len(only_primary),
                     "challenger_only_entity_bundles": len(only_challenger),
                     "primary_only_entities": only_primary,
                     "challenger_only_entities": only_challenger,
                     "material_needs_reconciliation": material_difference,
                     "primary_limitations": list(p.limitations),
                     "challenger_limitations": list(q.limitations),
                     "needs_reconciliation": difference})
    body = {"schema_version": "againward-independent-source-qa-v1",
            "qa_guidance_version": QA_GUIDANCE_VERSION,
            "batch_id": batch.batch_id,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "status": "RECONCILIATION_REQUIRED" if any(row["needs_reconciliation"] for row in rows) else "AGREEMENT",
            "material_status": "RECONCILIATION_REQUIRED" if any(row["material_needs_reconciliation"] for row in rows) else "MATERIAL_AGREEMENT",
            "source_results": rows,
            "delivery_approved": False,
            "limitations": ["Same model family may share errors; agreement is not a blind accuracy estimate.",
                            "This check compares proposed source-local facts, not entity links, financial calculations or report completeness."]}
    body["qa_sha256"] = stable_hash(body)
    return body


def reread_sources(batch: SourceBatch, primary: tuple[DocumentExtraction, ...],
                   root: Path, *, model: str, timeout_seconds: int = 180) -> tuple[dict[str, Any], tuple[Path, ...]]:
    """Independently request all source units; stop if any challenge fails."""
    provider = CodexCliProvider(root, model=model, timeout_seconds=timeout_seconds)
    challenger = []
    paths = []
    attempts = {}
    # No primary facts, review decisions, oracle or financial result enter this call.
    from againward.domains.rental.semantic_guidance import guidance
    for document in batch.documents:
        parsed = read_document(document, root)
        for number in (1, 2):
            try:
                instructions = guidance() + QA_INSTRUCTIONS + (RETRY_INSTRUCTIONS if number == 2 else "")
                proposal = provider.propose(document, parsed,
                                            {"batch": batch, "semantic_guidance": instructions})
                extraction = validate_proposal(proposal, batch, root)
                attempts[document.source_id] = number
                break
            except DocumentError as exc:
                # Retry only model-format/citation errors. Never retry a source,
                # privacy, resource or provider failure as if it were harmless.
                if number == 2 or exc.code not in {"SOURCE_LOCATION_INVALID", "EXTRACTION_SCHEMA_INVALID"}:
                    raise
        challenger.append(extraction)
        paths.append(persist_extraction(extraction, root))
    body = compare_extractions(batch, primary, tuple(challenger), root)
    body["challenger_attempts_by_source"] = attempts
    body["challenger_model_calls"] = sum(attempts.values())
    body["qa_sha256"] = stable_hash({key: value for key, value in body.items() if key != "qa_sha256"})
    return body, tuple(paths)
