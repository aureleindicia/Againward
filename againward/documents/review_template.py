"""Operator worksheet for source-bound fact decisions; never an approval."""
from __future__ import annotations

from .contracts import DocumentError, SourceBatch
from .extraction import DocumentExtraction


def fact_review_template(batch: SourceBatch, extractions: tuple[DocumentExtraction, ...]) -> tuple[dict, str]:
    if len(extractions) != len(batch.documents) or {e.source_id for e in extractions} != {
            d.source_id for d in batch.documents}:
        raise DocumentError("EXTRACTION_INCOMPLETE", "One validated extraction required for every source")
    rows = []
    decisions = []
    for extraction in sorted(extractions, key=lambda item: item.source_id):
        for candidate in extraction.candidates:
            decisions.append({"candidate_id": candidate.candidate_id, "decision": "DEFER",
                              "reason": "UNREVIEWED TEMPLATE — inspect exact source before deciding",
                              "resolved_flags": []})
            rows.append((extraction, candidate))
    template = {"schema_version": "againward-fact-review-v1",
                "extraction_hashes": sorted(e.to_dict()["extraction_sha256"] for e in extractions),
                "reviewer_role": None, "reviewed_at": None,
                "limitations_acknowledged": False, "decisions": decisions}
    worksheet = ["# Unreviewed source-fact worksheet", "",
                 "This is NOT a human approval. Inspect each original source, role, value, unit, date,",
                 "scope and ambiguity before editing the adjacent fact-review JSON.", "",
                 "Record an actual reviewer role and time; acknowledge limitations only after checking",
                 "every page/component. ACCEPT only when the quoted meaning is correct. DEFER otherwise.", ""]
    for extraction, candidate in rows:
        worksheet += [f"## {candidate.candidate_id}", "",
                      f"Source: {candidate.source_id} / {extraction.source_sha256}",
                      f"Location: {candidate.location}; span: {candidate.source_span}",
                      f"Entity: {candidate.entity_id}; field: {candidate.semantic_type}",
                      f"Proposed {candidate.value_type}: {candidate.value!r}",
                      f"Exact observed quote: {candidate.raw_observed_value!r}",
                      f"Ambiguity flags: {', '.join(candidate.ambiguity_flags) or 'none'}", "",
                      "Decision and reason: ______", ""]
    return template, "\n".join(worksheet) + "\n"
