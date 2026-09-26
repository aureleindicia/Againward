"""Generic regression cases for Rental failures previously found in live runs."""
from __future__ import annotations

from pathlib import Path

import pytest

from againward.documents.adjudication import _SCHEMA, _schema_diagnostic
from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError, error_category
from againward.documents.extraction import validate_proposal, validate_semantic_value_type
from againward.documents.independent_qa import QA_INSTRUCTIONS
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.extraction_validation import validate_rental_extraction
from againward.domains.rental.source_job import (RENTAL_STRUCTURE_RETRY, _bind_extraction_attempt,
    _safe_failure_diagnostic, _visual_review_stop)


def _proposal(tmp_path: Path, content: str, candidates: list[dict], limitations: list[str] | None = None):
    incoming = tmp_path / "incoming"
    incoming.mkdir()
    (incoming / "source.txt").write_text(content)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    normalized = [{"entity_id": row["entity_id"], "semantic_type": row["semantic_type"],
        "value_type": row["value_type"], "value": row["value"],
        "raw_observed_value": row["quote"], "location": parsed.units[0].location,
        "normalization_notes": "Source-bound test observation", "ambiguity_flags": []}
        for row in candidates]
    raw = {"status": "SUCCESS", "limitations": limitations or [], "candidates": normalized}
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
        "synthetic-model"), batch, root)
    return extraction


def _fields(entity: str = "line", *, omit: set[str] | None = None):
    omit = omit or set()
    return [
        {"entity_id": entity, "semantic_type": field, "value_type": "ENUM", "value": value, "quote": quote}
        for field, value, quote in (
            ("entity_kind", "INVOICE_LINE", "Invoice line"),
            ("document_role", "INVOICE", "Invoice"),
            ("document_status", "ISSUED", "Issued"),
        ) if field not in omit
    ]


def test_failure_family_native_paraphrase_is_not_converted_to_exact_evidence(tmp_path):
    with pytest.raises(DocumentError, match="SOURCE_LOCATION_INVALID"):
        _proposal(tmp_path, "Invoice net amount EUR 2670.00.", [
            {"entity_id": "line", "semantic_type": "net_amount", "value_type": "DECIMAL",
             "value": "2670.00", "quote": "invoice total is 2670 euros"}])


@pytest.mark.parametrize("field", ["net_amount", "rate", "unit_rate", "allocated_amount"])
def test_failure_family_numeric_amount_cannot_be_typed_as_currency(field):
    with pytest.raises(DocumentError, match="requires DECIMAL"):
        validate_semantic_value_type(field, "CURRENCY")


@pytest.mark.parametrize("missing", [
    {"entity_kind"}, {"document_role"}, {"document_status"},
    {"entity_kind", "document_role", "document_status"},
])
def test_failure_family_entity_structure_is_detected_before_fact_review(tmp_path, missing):
    candidates = _fields(omit=missing) + [{"entity_id": "line", "semantic_type": "net_amount",
        "value_type": "DECIMAL", "value": "2670.00", "quote": "2670.00"}]
    extraction = _proposal(tmp_path, "Invoice line Issued net amount 2670.00.", candidates)
    with pytest.raises(DocumentError) as error:
        validate_rental_extraction(extraction)
    assert error.value.code == "STRUCTURAL_INCOMPLETE"
    assert error.value.diagnostic["missing_structural_fields"] == sorted(missing)
    assert error.value.diagnostic["source_id"] == extraction.source_id
    assert error.value.diagnostic["error_category"] == "STRUCTURAL_INCOMPLETE"


def test_failure_family_rate_support_entity_cannot_omit_its_kind(tmp_path):
    candidates = [
        {"entity_id": "support", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "RATE_CARD", "quote": "rate sheet"},
        {"entity_id": "support", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ACCEPTED", "quote": "Accepted"},
        {"entity_id": "support", "semantic_type": "rate", "value_type": "DECIMAL",
         "value": "50.00", "quote": "50.00"},
    ]
    extraction = _proposal(tmp_path, "Accepted rate sheet daily price 50.00.", candidates)
    with pytest.raises(DocumentError, match="metadata is incomplete"):
        validate_rental_extraction(extraction)


def test_failure_family_structural_metadata_value_must_be_canonical_enum(tmp_path):
    candidates = _fields()
    candidates[0]["value"] = "INVOICE-LIKE"
    extraction = _proposal(tmp_path, "Invoice line Issued net amount 2670.00.", candidates)
    with pytest.raises(DocumentError, match="structural enum is invalid"):
        validate_rental_extraction(extraction)


def test_failure_family_observation_and_absence_limitation_is_explicit_contradiction(tmp_path):
    extraction = _proposal(tmp_path, "Invoice line Issued net amount 2670.00.",
        _fields() + [{"entity_id": "line", "semantic_type": "net_amount", "value_type": "DECIMAL",
                      "value": "2670.00", "quote": "2670.00"}],
        ["No invoice total is visible on the supplied page."])
    with pytest.raises(DocumentError) as error:
        validate_rental_extraction(extraction)
    assert error.value.code == "EXTRACTION_CONTRADICTION"
    assert error.value.diagnostic["error_category"] == "SEMANTIC_CONTRADICTION"


def test_failure_family_invalid_adjudication_selection_is_closed_enum():
    diagnostic = _schema_diagnostic({"decisions": [{"source_id": "src-a", "selection": "GUESS",
        "rationale": "test", "citations": [], "observations": []}]}, _SCHEMA)
    assert diagnostic is not None
    assert diagnostic["schema_path"] == "$.decisions[0].selection"


def test_failure_family_visual_handoff_does_not_accept_attestation_state_alias():
    assert _visual_review_stop({"status": "WAITING_FOR_VISUAL_ATTESTATION"}) is None
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        _visual_review_stop({"status": "WAITING_FOR_VISUAL_REVIEW"})


def test_failure_family_visual_group_split_is_incomplete_not_merged_by_guess(tmp_path):
    candidates = _fields("document") + [{"entity_id": "amount-row", "semantic_type": "net_amount",
        "value_type": "DECIMAL", "value": "2670.00", "quote": "2670.00"}]
    extraction = _proposal(tmp_path, "Invoice line Issued net amount 2670.00.", candidates)
    with pytest.raises(DocumentError) as error:
        validate_rental_extraction(extraction)
    assert error.value.diagnostic["structural_gap_count"] == 1


@pytest.mark.parametrize("code,category", [
    ("EXTRACTION_SCHEMA_INVALID", "SCHEMA_ERROR"),
    ("STRUCTURAL_INCOMPLETE", "STRUCTURAL_INCOMPLETE"),
    ("EXTRACTION_CONTRADICTION", "SEMANTIC_CONTRADICTION"),
    ("SOURCE_LOCATION_INVALID", "SOURCE_EVIDENCE_MISSING"),
    ("UNSUPPORTED_PROMOTION", "SOURCE_EVIDENCE_MISSING"),
    ("ENTITY_AMBIGUOUS", "AMBIGUOUS_SOURCE"),
    ("MODEL_UNAVAILABLE", "MODEL_INVOCATION_ERROR"),
    ("REPAIR_REQUIRED", "REVIEW_REQUIRED"),
])
def test_failure_family_taxonomy_is_stable(code, category):
    assert error_category(code) == category


def test_structural_retry_is_one_bounded_source_bound_request():
    assert "Reinspect this source" in RENTAL_STRUCTURE_RETRY
    assert "Do not infer a value from filenames" in RENTAL_STRUCTURE_RETRY
    assert "the proposal will remain incomplete and stop" in RENTAL_STRUCTURE_RETRY
    assert "Do not guess missing fields" in QA_INSTRUCTIONS


def test_terminal_structural_diagnostic_records_one_retry_without_entity_content():
    error = DocumentError("STRUCTURAL_INCOMPLETE", diagnostic={
        "error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[].entity_id",
        "validation_code": "ENTITY_METADATA_REQUIRED", "structural_gap_count": 1,
        "missing_structural_fields": ["entity_kind"], "entity_id": "private-model-label"})
    _bind_extraction_attempt(error, attempt=2, model="gpt-6-luna", semantic_guidance="rental source task")
    receipt = _safe_failure_diagnostic(error, stage="PRIMARY_EXTRACTION", source_id="src-abc")
    assert receipt["retry_count"] == 1
    assert receipt["model"] == "gpt-6-luna"
    assert receipt["error_category"] == "STRUCTURAL_INCOMPLETE"
    assert receipt["missing_structural_fields"] == ["entity_kind"]
    assert "entity_id" not in receipt and "private-model-label" not in repr(receipt)
