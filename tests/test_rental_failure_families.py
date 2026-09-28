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
from againward.domains.rental.entity_contract import (FIELD_SCOPE, PACKAGE_SOURCE_REQUIRED,
    normalize_single_line_document_groups, structural_gaps, unique_pixel_entity_for_required_field)
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
    validate_rental_extraction(extraction, allow_incomplete=True)  # QA input only; still unreviewed.


def test_unapproved_pixel_field_targets_only_one_eligible_missing_entity():
    from types import SimpleNamespace
    candidates = [SimpleNamespace(entity_id="line", location="page:1",
                    semantic_type="entity_kind", value="INVOICE_LINE"),
                  SimpleNamespace(entity_id="line", location="page:1",
                    semantic_type="invoice_id", value="INV-8"),
                  SimpleNamespace(entity_id="support", location="page:1",
                    semantic_type="entity_kind", value="SUPPORTING_DOCUMENT")]
    assert unique_pixel_entity_for_required_field("charge_type", "page:1", candidates) == "line"
    assert unique_pixel_entity_for_required_field("charge_type", "page:2", candidates) is None
    candidates.append(SimpleNamespace(entity_id="second-line", location="page:1",
                      semantic_type="entity_kind", value="INVOICE_LINE"))
    assert unique_pixel_entity_for_required_field("charge_type", "page:1", candidates) is None


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


def test_multirow_accounting_export_uses_source_level_role_and_status(tmp_path):
    candidates = [
        {"entity_id": "invoice-1", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Invoice row 1"},
        {"entity_id": "invoice-1", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "PAYMENT_EXPORT", "quote": "Export ledger"},
        {"entity_id": "invoice-1", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "EXTRACTED", "quote": "Mirror only"},
        {"entity_id": "invoice-1", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "900.00", "quote": "900.00"},
        {"entity_id": "invoice-2", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Invoice row 2"},
        {"entity_id": "invoice-2", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "270.00", "quote": "270.00"},
        {"entity_id": "credit-1", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Credit row"},
        {"entity_id": "credit-1", "semantic_type": "credit_id", "value_type": "IDENTIFIER",
         "value": "CN-41", "quote": "CN-41"},
    ]
    extraction = _proposal(tmp_path,
        "Export ledger. Invoice row 1 Mirror only: 900.00. Invoice row 2: 270.00. Credit row CN-41.",
        candidates)
    validate_rental_extraction(extraction)


def test_canonical_scope_and_review_shape_are_route_independent():
    assert FIELD_SCOPE["entity_kind"] == "ENTITY"
    assert FIELD_SCOPE["document_role"] == FIELD_SCOPE["document_status"] == "SOURCE"
    assert "invoice_line_id" not in PACKAGE_SOURCE_REQUIRED["INVOICE_LINE"]
    assert "charge_key" not in PACKAGE_SOURCE_REQUIRED["INVOICE_LINE"]
    from againward.domains.rental.entity_contract import PACKAGE_RELATIONAL_FIELDS
    assert "charge_type" not in PACKAGE_SOURCE_REQUIRED["INVOICE_LINE"]
    assert "charge_type" in PACKAGE_RELATIONAL_FIELDS["INVOICE_LINE"]
    for source_id in ("native-source", "visual-source"):
        accepted = [(source_id, "row-1", "entity_kind"),
                    (source_id, "row-1", "document_role"),
                    (source_id, "row-1", "document_status"),
                    (source_id, "row-2", "entity_kind")]
        assert structural_gaps(accepted) == []
        assert structural_gaps(accepted[:-1]) == []
        assert structural_gaps(accepted[1:]) == [{
            "source_id": source_id, "entity_id": "row-1", "missing": ["entity_kind"]}]


@pytest.mark.parametrize("visual", [False, True])
def test_unique_invoice_document_envelope_groups_without_changing_evidence(visual):
    group = "entity_hint" if visual else "entity_id"
    rows = [
        {group: "invoice", "semantic_type": "document_role", "value": "INVOICE"},
        {group: "invoice", "semantic_type": "invoice_id", "value": "INV-8"},
        {group: "line", "semantic_type": "entity_kind", "value": "INVOICE_LINE"},
        {group: "line", "semantic_type": "net_amount", "value": "850.00"},
    ]
    for row in rows:
        row["visible_text" if visual else "raw_observed_value"] = str(row["value"])
        if visual:
            row["page"] = 1
    raw = {"observations" if visual else "candidates": rows}
    normalized, moves = normalize_single_line_document_groups(raw, visual=visual)
    assert moves == 2
    assert {row[group] for row in normalized["observations" if visual else "candidates"]} == {"line"}
    assert raw["observations" if visual else "candidates"][0][group] == "invoice"
    assert [row["visible_text" if visual else "raw_observed_value"] for row in rows] == [
        row["visible_text" if visual else "raw_observed_value"]
        for row in normalized["observations" if visual else "candidates"]]


def test_document_envelope_is_not_moved_across_ambiguous_invoice_lines():
    raw = {"observations": [
        {"entity_hint": "invoice", "semantic_type": "document_role", "value": "INVOICE", "page": 1},
        {"entity_hint": "line-1", "semantic_type": "entity_kind", "value": "INVOICE_LINE", "page": 1},
        {"entity_hint": "line-2", "semantic_type": "entity_kind", "value": "INVOICE_LINE", "page": 1},
    ]}
    assert normalize_single_line_document_groups(raw, visual=True)[1] == 0


def test_document_envelope_does_not_override_conflict_or_cross_page_pixels():
    rows = [
        {"entity_hint": "invoice", "semantic_type": "document_status", "value": "ISSUED", "page": 1},
        {"entity_hint": "line", "semantic_type": "entity_kind", "value": "INVOICE_LINE", "page": 1},
        {"entity_hint": "line", "semantic_type": "document_status", "value": "ACCEPTED", "page": 1},
    ]
    normalized, moved = normalize_single_line_document_groups({"observations": rows}, visual=True)
    assert moved == 0
    assert normalized["observations"] == rows
    rows[2]["semantic_type"] = "net_amount"
    rows[2]["page"] = 2
    assert normalize_single_line_document_groups({"observations": rows}, visual=True)[1] == 0


def test_invoice_charge_type_is_deferred_to_package_review_not_invented_in_source(tmp_path):
    rows = _fields() + [
        {"entity_id": "line", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-8", "quote": "INV-8"},
        {"entity_id": "line", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR"},
        {"entity_id": "line", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "850.00", "quote": "850.00"},
    ]
    extraction = _proposal(tmp_path, "Invoice line Issued INV-8 EUR 850.00.", rows)
    validate_rental_extraction(extraction)  # A challenger may still recover the omitted fact.
    validate_rental_extraction(extraction, require_package_facts=True)
    assert not any(c.semantic_type == "charge_type" for c in extraction.candidates)
    from tests.test_rental_document_adapter import packet
    from againward.domains.rental.document_adapter import load_document_case
    source, package = packet(tmp_path / "package", omit_invoice_fields={"charge_type"})
    with pytest.raises(DocumentError) as caught:
        load_document_case(package, source.parent)
    assert caught.value.diagnostic["validation_code"] == "PACKAGE_CLASSIFICATION_REVIEW_REQUIRED"


def test_multrow_accounting_export_still_requires_kind_for_each_row(tmp_path):
    candidates = [
        {"entity_id": "invoice-1", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Invoice row 1"},
        {"entity_id": "invoice-1", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "PAYMENT_EXPORT", "quote": "Export ledger"},
        {"entity_id": "invoice-1", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "EXTRACTED", "quote": "Mirror only"},
        {"entity_id": "invoice-2", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "270.00", "quote": "270.00"},
    ]
    extraction = _proposal(tmp_path, "Export ledger. Invoice row 1 Mirror only. 270.00.", candidates)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(extraction)
    assert caught.value.code == "STRUCTURAL_INCOMPLETE"
    assert caught.value.diagnostic["missing_structural_fields"] == ["entity_kind"]


def test_conflicting_source_level_document_metadata_fails_closed(tmp_path):
    candidates = [
        {"entity_id": "invoice-1", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Rental scope"},
        {"entity_id": "invoice-1", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "INVOICE", "quote": "Invoice document"},
        {"entity_id": "invoice-1", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "Issued status"},
        {"entity_id": "invoice-2", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "SUPPORTING_DOCUMENT", "quote": "Invoice row 2"},
        {"entity_id": "invoice-2", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "PAYMENT_EXPORT", "quote": "Export ledger"},
    ]
    extraction = _proposal(tmp_path,
        "Rental scope. Invoice document. Issued status. Invoice row 2 Export ledger.", candidates)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(extraction)
    assert caught.value.code == "EXTRACTION_CONTRADICTION"
    assert caught.value.diagnostic["validation_code"] == "SOURCE_DOCUMENT_METADATA_CONFLICT"
    assert caught.value.diagnostic["conflicting_semantic_types"] == ["document_role"]


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
    assert "Do not infer a role/status from a filename" in RENTAL_STRUCTURE_RETRY
    assert "validation will stop" in RENTAL_STRUCTURE_RETRY
    assert "entity_kind, not document_role" in RENTAL_STRUCTURE_RETRY
    assert "Do not guess missing fields" in QA_INSTRUCTIONS


def test_terminal_structural_diagnostic_records_one_retry_without_entity_content():
    error = DocumentError("STRUCTURAL_INCOMPLETE", diagnostic={
        "error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[].entity_id",
        "validation_code": "ENTITY_METADATA_REQUIRED", "structural_gap_count": 1,
        "missing_structural_fields": ["entity_kind"], "source_sha256": "a" * 64,
        "extractor_version": "reader-v2", "current_prompt_version_count": 12,
        "entity_id": "private-model-label"})
    _bind_extraction_attempt(error, attempt=2, model="gpt-6-luna", semantic_guidance="rental source task")
    receipt = _safe_failure_diagnostic(error, stage="PRIMARY_EXTRACTION", source_id="src-abc")
    assert receipt["retry_count"] == 1
    assert receipt["model"] == "gpt-6-luna"
    assert receipt["error_category"] == "STRUCTURAL_INCOMPLETE"
    assert receipt["missing_structural_fields"] == ["entity_kind"]
    assert receipt["source_sha256"] == "a" * 64
    assert receipt["extractor_version"] == "reader-v2"
    assert receipt["current_prompt_version_count"] == 12
    assert "entity_id" not in receipt and "private-model-label" not in repr(receipt)
