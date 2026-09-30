"""Blind source reread and conservative, entity-level extraction comparison.

The challenger receives original source units and independent instructions, never
the primary proposal. Agreement is a diagnostic, not proof of correctness or
authority to deliver. Disagreement must be reconciled before fact promotion.
"""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import json
from pathlib import Path
from typing import Any

from againward.domains.rental.entity_contract import MATERIAL_FIELDS
from againward.domains.rental.extraction_validation import (PACKAGE_SOURCE_REQUIRED,
    package_source_gaps, proposal_issues)
from againward.evidence.hashing import stable_hash
from .codex_provider import CodexCliProvider
from .contracts import DocumentError, SourceBatch
from .extraction import DocumentExtraction, persist_extraction, replay_extraction, validate_proposal
from .readers import read_document
from .reconciliation import ASSEMBLY_VERSION, FACT_RECONCILIATION_VERSION
from .sources import verify_batch


QA_GUIDANCE_VERSION = "rental-independent-source-reread-v5-provisional-content"
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
VISUAL_RETRY_INSTRUCTIONS = """
The prior visual observation response failed deterministic page/schema validation.
Reinspect the attached page image and return the visual observation schema.
Use a displayed page number, exact visible wording, typed value, ambiguity, and
a short descriptive entity_hint. Do not emit hashes, spans, source IDs or candidate IDs.
"""

# Material here means fields capable of changing the supported Rental ledger,
# source authority or relationship. This is a triage classification, not a
# claim that other source details are irrelevant to the final report.
_NUMERIC_MATERIAL_FIELDS = {"quantity", "minimum_days", "rate", "discount_fraction",
                            "net_amount", "unit_rate", "billed_units", "allocated_amount"}

_SOURCE_METADATA_FIELDS = {"document_role", "document_status", "supplier_id", "invoice_id"}


def _canonical_observations(extraction: DocumentExtraction, *,
                            entity_kind_overrides: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Derive a source-bound QA view without treating model labels as identity.

    Candidate IDs, entity labels, ordering, and the location of document-envelope
    fields are presentation details. Values and their already-validated source
    bindings remain attached; explicit printed identifiers may anchor a material
    entity when the Rental contract gives that identifier a stable meaning.
    """
    groups: dict[str, list[Any]] = {}
    for candidate in extraction.candidates:
        groups.setdefault(candidate.entity_id, []).append(candidate)

    anchor_by_group: dict[str, str | None] = {}
    kind_by_group: dict[str, str | None] = {}
    for entity_id, candidates in groups.items():
        fields = {candidate.semantic_type: candidate.value for candidate in candidates}
        values_by_field: dict[str, set[str]] = {}
        for candidate in candidates:
            if candidate.value is not None:
                values_by_field.setdefault(candidate.semantic_type, set()).add(str(candidate.value))
        kind = fields.get("entity_kind")
        if kind is None and entity_kind_overrides is not None:
            kind = entity_kind_overrides.get(entity_id)
        kind_by_group[entity_id] = kind if isinstance(kind, str) else None
        if "invoice_line_id" in fields:
            anchor_field = "invoice_line_id"
        elif kind == "CREDIT":
            anchor_field = "credit_id"
        elif kind in {"RENTAL_SCOPE", "RETURN", "RATE_AMENDMENT"}:
            anchor_field = "asset_id"
        else:
            anchor_field = None
        anchors = values_by_field.get(anchor_field or "", set())
        anchor_by_group[entity_id] = next(iter(anchors)) if len(anchors) == 1 else None

    # In a validated single-scope rental agreement, the source contract itself
    # can supply a stable identity when a reader splits the agreement envelope
    # and its sole asset into separate model-local groups. This is permitted
    # only when all four source-bound facts are unique: agreement role, scope
    # kind, agreement identifier and asset identifier. The projection affects
    # comparison/reconciliation only; candidate citations and source facts are
    # unchanged, and the resulting extraction still requires review.
    all_values: dict[str, set[str]] = {}
    for candidate in extraction.candidates:
        if candidate.value is not None:
            all_values.setdefault(candidate.semantic_type, set()).add(str(candidate.value))
    rental_anchor: str | None = None
    if (all_values.get("document_role") == {"RENTAL_AGREEMENT"}
            and all_values.get("entity_kind") == {"RENTAL_SCOPE"}
            and len(all_values.get("agreement_id", set())) == 1
            and len(all_values.get("asset_id", set())) == 1):
        rental_anchor = "rental-scope-" + stable_hash({
            "source_id": extraction.source_id,
            "agreement_id": next(iter(all_values["agreement_id"])),
            "asset_id": next(iter(all_values["asset_id"])),
        })[:24]
    rental_scope_fields = (set(MATERIAL_FIELDS.get("RENTAL_SCOPE", set()))
                          | set(PACKAGE_SOURCE_REQUIRED.get("RENTAL_SCOPE", set()))
                          | {"agreement_id"})

    observations: list[dict[str, Any]] = []
    for candidate in extraction.candidates:
        field = candidate.semantic_type
        kind = kind_by_group.get(candidate.entity_id)
        scope: str
        anchor: str | None
        if (rental_anchor is not None and field in rental_scope_fields):
            scope, anchor = "MATERIAL_ENTITY", rental_anchor
        elif field == "invoice_id" and kind == "INVOICE_LINE":
            # The source-level envelope value is explicitly projected onto its
            # same-source invoice line by the provider contract. For QA and
            # deterministic union it therefore belongs to that anchored line,
            # so a union cannot strand the required identifier in a metadata
            # group separate from the entity it identifies.
            scope, anchor = "MATERIAL_ENTITY", anchor_by_group.get(candidate.entity_id)
        elif field in _SOURCE_METADATA_FIELDS and not (field == "invoice_id" and kind == "CREDIT"):
            scope = "SOURCE_METADATA"
            anchor = None
        elif ((field == "invoice_line_id" and kind != "INVOICE_LINE")
              or (field == "invoice_id" and kind == "CREDIT")
              or (field == "asset_id" and kind in {None, "CREDIT"})):
            scope = "REFERENCE"
            anchor = anchor_by_group.get(candidate.entity_id)
        elif kind is not None:
            scope = "MATERIAL_ENTITY"
            anchor = anchor_by_group.get(candidate.entity_id)
        else:
            scope = "UNKNOWN"
            anchor = anchor_by_group.get(candidate.entity_id)
        value: Any = candidate.value
        if field in _NUMERIC_MATERIAL_FIELDS and type(value) in {int, str}:
            try:
                number = Decimal(str(value))
            except InvalidOperation:
                pass
            else:
                if number.is_finite():
                    value = format(number.normalize(), "f")
        structural_stub = (kind == "SUPPORTING_DOCUMENT" and field == "entity_kind"
                           and {item.semantic_type for item in groups.get(candidate.entity_id, [])
                                if item.semantic_type not in _SOURCE_METADATA_FIELDS} == {"entity_kind"})
        observations.append({
            "source_id": candidate.source_id,
            "source_sha256": extraction.source_sha256,
            "scope": scope,
            "anchor": anchor,
            "semantic_type": field,
            "material": (not structural_stub and (scope == "SOURCE_METADATA" or kind is None
                         or field in MATERIAL_FIELDS.get(kind, set()))),
            "value_type": candidate.value_type,
            "value": value,
            "location": candidate.location,
            "unit_sha256": candidate.unit_sha256,
            "source_span": list(candidate.source_span) if candidate.source_span else None,
        })
    return observations


def _observation_key(observation: dict[str, Any]) -> str:
    """Comparison key; provenance is retained in the view, not used as meaning."""
    return stable_hash({key: observation[key] for key in (
        "source_id", "source_sha256", "scope", "anchor", "semantic_type", "value")})


def _observation_comparison(primary: list[dict[str, Any]],
                            challenger: list[dict[str, Any]]) -> dict[str, Any]:
    """Classify equivalent readings, complements, and anchored conflicts."""
    def classify(left: list[dict[str, Any]], right: list[dict[str, Any]]) -> tuple[
            str, list[dict[str, Any]], list[dict[str, Any]], int, int]:
        left_values: dict[tuple[str, str | None, str], set[str]] = {}
        right_values: dict[tuple[str, str | None, str], set[str]] = {}
        for target, rows in ((left_values, left), (right_values, right)):
            for row in rows:
                key = (row["scope"], row["anchor"], row["semantic_type"])
                target.setdefault(key, set()).add(stable_hash(row["value"]))
        common_keys = sorted(left_values.keys() & right_values.keys(),
                             key=lambda item: (item[0], item[1] or "", item[2]))
        disagreements = [key for key in common_keys if left_values[key] != right_values[key]]
        conflicts = [{"scope": key[0], "anchor": key[1], "semantic_type": key[2]}
                     for key in disagreements if key[0] == "SOURCE_METADATA" or key[1] is not None]
        unknowns = [{"scope": key[0], "anchor": key[1], "semantic_type": key[2]}
                    for key in disagreements if key[0] != "SOURCE_METADATA" and key[1] is None]
        left_keys = {_observation_key(row) for row in left}
        right_keys = {_observation_key(row) for row in right}
        if conflicts:
            classification = "CONFLICT"
        elif unknowns:
            classification = "UNKNOWN"
        elif left_keys == right_keys:
            classification = "PRESENTATION_EQUIVALENT"
        else:
            classification = "COMPLEMENTARY"
        return (classification, conflicts, unknowns,
                len(left_keys - right_keys), len(right_keys - left_keys))

    all_class, _, _, primary_only, challenger_only = classify(primary, challenger)
    material_primary = [row for row in primary if row["material"]]
    material_challenger = [row for row in challenger if row["material"]]
    material_class, conflicts, unknowns, _, _ = classify(material_primary, material_challenger)
    return {"classification": all_class,
            "material_classification": material_class,
            "primary_only_observations": primary_only,
            "challenger_only_observations": challenger_only,
            "conflicting_fields": conflicts,
            "unknown_fields": unknowns}


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


def _verified_fact_union(extraction: DocumentExtraction, other: DocumentExtraction,
                         root: Path) -> bool:
    """Recognize only a current, receipt-bound union of these exact two reads."""
    if (extraction.extractor_version != FACT_RECONCILIATION_VERSION
            or extraction.assembly_receipt_sha256 is None):
        return False
    path = root / "assemblies" / (extraction.assembly_receipt_sha256 + ".json")
    if not path.is_file() or path.is_symlink():
        return False
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
        parents = {receipt[key]["extraction_sha256"] for key in ("primary", "challenger")}
    except (OSError, ValueError, KeyError, TypeError):
        return False
    return len(parents) == 2 and other.to_dict()["extraction_sha256"] in parents


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
        from againward.domains.rental.extraction_validation import occurrence_kind_overrides
        p_observations = _canonical_observations(p,
            entity_kind_overrides=occurrence_kind_overrides(p, (q,)))
        q_observations = _canonical_observations(q,
            entity_kind_overrides=occurrence_kind_overrides(q, (p,)))
        observation_comparison = _observation_comparison(p_observations, q_observations)
        fact_union_verified = (_verified_fact_union(p, q, root)
                               or _verified_fact_union(q, p, root))
        if fact_union_verified:
            # The receipt proves that the current extraction was built from the
            # two exact current reads. This is the fresh QA check after a
            # deterministic union; the parent-level complement is preserved in
            # the immutable lineage receipt and does not need another model vote.
            observation_comparison = {**observation_comparison,
                "classification": "PRESENTATION_EQUIVALENT",
                "material_classification": "PRESENTATION_EQUIVALENT",
                "primary_only_observations": 0, "challenger_only_observations": 0,
                "conflicting_fields": [], "unknown_fields": [],
                "fact_union_verified": True}
        a = Counter(record["bundle_sha256"] for record in p_records)
        b = Counter(record["bundle_sha256"] for record in q_records)
        only_primary = _unmatched(p_records, b)
        only_challenger = _unmatched(q_records, a)
        p_gaps = package_source_gaps(p, for_comparison=True)
        q_gaps = {} if fact_union_verified else package_source_gaps(q, for_comparison=True)
        p_issues, q_issues = proposal_issues(p), ({} if fact_union_verified else proposal_issues(q))
        assembled = p.extractor_version == ASSEMBLY_VERSION and not fact_union_verified
        conflict = any(issue.get("reason_code") == "EXTRACTION_CONTRADICTION" for issue in (p_issues, q_issues))
        material_difference = (assembled or conflict
                               or observation_comparison["material_classification"] != "PRESENTATION_EQUIVALENT"
                               or bool(p_gaps) or bool(q_gaps)
                               or p.status == "FAILED" or q.status == "FAILED"
                               or bool(p.limitations) or bool(q.limitations))
        difference = bool(material_difference
                          or observation_comparison["classification"] != "PRESENTATION_EQUIVALENT"
                          or p.status == "FAILED" or q.status == "FAILED"
                          or p.limitations or q.limitations or p_gaps or q_gaps)
        rows.append({"source_id": document.source_id, "source_sha256": document.sha256,
                     "primary_extraction_sha256": p.to_dict()["extraction_sha256"],
                     "challenger_extraction_sha256": q.to_dict()["extraction_sha256"],
                     "primary_status": p.status, "challenger_status": q.status,
                     "primary_only_entity_bundles": len(only_primary),
                     "challenger_only_entity_bundles": len(only_challenger),
                     "primary_only_entities": only_primary,
                     "challenger_only_entities": only_challenger,
                     "pre_qa_observation_comparison": observation_comparison,
                     "fact_union_verified": fact_union_verified,
                     "primary_pre_qa_observation_count": len(p_observations),
                     "challenger_pre_qa_observation_count": len(q_observations),
                     "primary_contract_issues": p_issues,
                     "challenger_contract_issues": q_issues,
                     "primary_source_fact_gaps": {key: sorted(value) for key, value in p_gaps.items()},
                     "challenger_source_fact_gaps": {key: sorted(value) for key, value in q_gaps.items()},
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
