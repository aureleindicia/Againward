"""Generic regression cases for Rental failures previously found in live runs."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from againward.documents.adjudication import _SCHEMA, _schema_diagnostic
from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError, error_category
from againward.documents.extraction import validate_proposal, validate_semantic_value_type
from againward.documents.independent_qa import QA_INSTRUCTIONS
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.extraction_validation import (normalize_source_supported_rate_rows,
    validate_rental_extraction)
from againward.domains.rental.entity_contract import (FIELD_SCOPE, PACKAGE_SOURCE_REQUIRED,
    normalize_document_envelopes, normalize_single_line_document_groups, structural_gaps,
    unique_pixel_entity_for_required_field)
from againward.domains.rental.extraction_validation import package_source_gaps
from againward.domains.rental.source_job import (RENTAL_STRUCTURE_RETRY, _bind_extraction_attempt,
    _safe_failure_diagnostic, _visual_review_stop)


def _proposal(tmp_path: Path, content: str, candidates: list[dict], limitations: list[str] | None = None):
    incoming = tmp_path / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "source.txt").write_text(content)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    normalized = []
    for row in candidates:
        matching_units = [unit for unit in parsed.units if row["quote"] in unit.text]
        location = matching_units[0].location if matching_units else parsed.units[0].location
        normalized.append({"entity_id": row["entity_id"], "semantic_type": row["semantic_type"],
            "value_type": row["value_type"], "value": row["value"],
            "raw_observed_value": row["quote"], "location": location,
            "normalization_notes": "Source-bound test observation", "ambiguity_flags": []})
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


def test_source_metadata_and_reference_groups_do_not_need_an_invented_entity_kind(tmp_path):
    from againward.documents.extraction import CanonicalFact
    from againward.documents.resolution import entities_from_facts, non_entity_reference_groups
    from againward.domains.rental.entity_contract import NON_ENTITY_OBSERVATION_FIELDS

    rows = [
        {"entity_id": "credit-core", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "CREDIT", "quote": "Credit record"},
        {"entity_id": "credit-core", "semantic_type": "credit_id", "value_type": "IDENTIFIER",
         "value": "CN-71", "quote": "credit CN-71"},
        {"entity_id": "credit-core", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR"},
        {"entity_id": "credit-core", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "81.00", "quote": "81.00"},
        {"entity_id": "credit-core", "semantic_type": "status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "Credit state: Issued"},
        {"entity_id": "source-header", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "CREDIT_NOTE", "quote": "Credit note"},
        {"entity_id": "source-header", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "Document status: Issued"},
        {"entity_id": "invoice-reference-positive", "semantic_type": "invoice_id",
         "value_type": "IDENTIFIER", "value": "INV-71", "quote": "Invoice INV-71"},
        {"entity_id": "invoice-reference-positive", "semantic_type": "invoice_line_id",
         "value_type": "IDENTIFIER", "value": "ROW-A", "quote": "line ROW-A"},
        {"entity_id": "invoice-reference-negative", "semantic_type": "invoice_id",
         "value_type": "IDENTIFIER", "value": "INV-72", "quote": "No part applies to INV-72"},
    ]
    content = ("Credit record credit CN-71 EUR 81.00. Credit state: Issued. Credit note. "
               "Document status: Issued. "
               "Invoice INV-71 line ROW-A. No part applies to INV-72.")
    extraction = _proposal(tmp_path, content, rows)
    validate_rental_extraction(extraction, require_package_facts=True)
    candidates = extraction.candidates
    accepted = [(candidate.source_id, candidate.entity_id, candidate.semantic_type)
                for candidate in candidates]
    assert structural_gaps(accepted, offered=accepted) == []

    facts = tuple(CanonicalFact(f"fact-{index}", candidate, "extraction-hash",
                                "review-hash", "source fact review")
                  for index, candidate in enumerate(candidates))
    entities = entities_from_facts(facts, non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS)
    assert [(entity.kind, entity.local_id) for entity in entities] == [("CREDIT", "credit-core")]
    fragments = non_entity_reference_groups(facts, non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS)
    assert {row["local_id"] for row in fragments} == {
        "source-header", "invoice-reference-positive", "invoice-reference-negative"}
    assert all(row["source_id"] == extraction.source_id for row in fragments)
    assert sum(len(row["fact_ids"]) for row in fragments) == 5


def test_credit_target_references_are_not_merged_into_credit_entity(tmp_path):
    from againward.documents.extraction import CanonicalFact
    from againward.documents.resolution import entities_from_facts, non_entity_reference_groups
    from againward.domains.rental.entity_contract import (CREDIT_REFERENCE_FIELDS,
        NON_ENTITY_OBSERVATION_FIELDS)

    content = ("Credit CN-91 EUR 81.00 issued. It references invoice INV-91 line ROW-A "
               "asset ASSET-A and invoice INV-92 line ROW-B asset ASSET-B.")
    rows = [
        {"entity_id": "credit-record", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "CREDIT", "quote": "Credit CN-91"},
        {"entity_id": "credit-record", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "CREDIT_NOTE", "quote": "Credit CN-91"},
        {"entity_id": "credit-record", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "issued"},
        {"entity_id": "credit-record", "semantic_type": "credit_id", "value_type": "IDENTIFIER",
         "value": "CN-91", "quote": "CN-91"},
        {"entity_id": "credit-record", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR"},
        {"entity_id": "credit-record", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "81.00", "quote": "81.00"},
        {"entity_id": "credit-record", "semantic_type": "status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "issued"},
        {"entity_id": "credit-record", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-91", "quote": "INV-91"},
        {"entity_id": "credit-record", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-92", "quote": "INV-92"},
        {"entity_id": "credit-record", "semantic_type": "invoice_line_id", "value_type": "IDENTIFIER",
         "value": "ROW-A", "quote": "ROW-A"},
        {"entity_id": "credit-record", "semantic_type": "invoice_line_id", "value_type": "IDENTIFIER",
         "value": "ROW-B", "quote": "ROW-B"},
        {"entity_id": "credit-record", "semantic_type": "asset_id", "value_type": "IDENTIFIER",
         "value": "ASSET-A", "quote": "ASSET-A"},
        {"entity_id": "credit-record", "semantic_type": "asset_id", "value_type": "IDENTIFIER",
         "value": "ASSET-B", "quote": "ASSET-B"},
    ]
    extraction = _proposal(tmp_path, content, rows)
    validate_rental_extraction(extraction, require_package_facts=True)
    facts = tuple(CanonicalFact(f"fact-{index}", candidate, "extraction-hash",
                                "review-hash", "source fact review")
                  for index, candidate in enumerate(extraction.candidates))
    references = {"CREDIT": CREDIT_REFERENCE_FIELDS}
    entities = entities_from_facts(facts, non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS,
                                   reference_fields_by_kind=references)
    credit, = entities
    assert credit.kind == "CREDIT"
    assert {"invoice_id", "invoice_line_id", "asset_id"}.isdisjoint(credit.values)
    fragments = non_entity_reference_groups(
        facts, non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS,
        reference_fields_by_kind=references)
    target_fragments = [row for row in fragments if row["record_type"] == "SOURCE_REFERENCE_FRAGMENT"]
    assert len(target_fragments) == 6
    assert len({row["local_id"] for row in target_fragments}) == 6
    assert all(row["source_id"] == extraction.source_id and len(row["fact_ids"]) == 1
               for row in target_fragments)

    negative_fact_ids = {fact.fact_id for fact in facts
        if fact.candidate.value in {"INV-92", "ROW-B", "ASSET-B"}}
    excluded = tuple(replace(fact, candidate=replace(fact.candidate,
        ambiguity_flags=("excluded_target",))) if fact.fact_id in negative_fact_ids else fact
        for fact in facts)
    positive_credit, = entities_from_facts(excluded,
        non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS,
        reference_fields_by_kind=references)
    assert {field: positive_credit.values[field] for field in CREDIT_REFERENCE_FIELDS} == {
        "invoice_id": "INV-91", "invoice_line_id": "ROW-A", "asset_id": "ASSET-A"}


def test_same_field_conflict_remains_structural_error_for_invoice_entity(tmp_path):
    content = "Invoice line INV-91 Issued; corrected invoice INV-92."
    rows = _fields("line") + [
        {"entity_id": "line", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-91", "quote": "INV-91"},
        {"entity_id": "line", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-92", "quote": "INV-92"},
    ]
    extraction = _proposal(tmp_path, content, rows)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(extraction)
    assert caught.value.code == "EXTRACTION_CONTRADICTION"
    assert caught.value.diagnostic["validation_code"] == "STRUCTURAL_METADATA_CONFLICT"
    assert caught.value.diagnostic["conflicting_semantic_types"] == ["invoice_id"]


def test_untyped_reference_group_needs_invoice_anchor_but_asset_alone_still_stops(tmp_path):
    content = "Invoice line INV-91 Issued; line ROW-A concerns asset ASSET-91."
    rows = _fields("header") + [
        {"entity_id": "references", "semantic_type": "invoice_id", "value_type": "IDENTIFIER",
         "value": "INV-91", "quote": "INV-91"},
        {"entity_id": "references", "semantic_type": "invoice_line_id", "value_type": "IDENTIFIER",
         "value": "ROW-A", "quote": "ROW-A"},
        {"entity_id": "references", "semantic_type": "asset_id", "value_type": "IDENTIFIER",
         "value": "ASSET-91", "quote": "ASSET-91"},
    ]
    extraction = _proposal(tmp_path, content, rows)
    validate_rental_extraction(extraction)

    other = tmp_path / "asset-only"
    asset_only = _proposal(other, "Invoice line Issued. Asset ASSET-91.", _fields("header") + [
        {"entity_id": "reference", "semantic_type": "asset_id", "value_type": "IDENTIFIER",
         "value": "ASSET-91", "quote": "ASSET-91"},
    ])
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(asset_only)
    assert caught.value.diagnostic["missing_structural_fields"] == ["entity_kind"]


@pytest.mark.parametrize("fields", [
    [("credit_id", "CN-91")],
    [("invoice_id", "INV-91"), ("net_amount", "81.00")],
    [("asset_id", "ASSET-91")],
])
def test_untyped_business_observation_still_requires_entity_kind(tmp_path, fields):
    rows = _fields() + [
        {"entity_id": "untyped", "semantic_type": field,
         "value_type": "IDENTIFIER" if field.endswith("_id") else "DECIMAL",
         "value": value, "quote": value}
        for field, value in fields
    ]
    extraction = _proposal(tmp_path, "Invoice line Issued INV-91 81.00 CN-91 ASSET-91.", rows)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(extraction)
    assert caught.value.code == "STRUCTURAL_INCOMPLETE"
    assert caught.value.diagnostic["missing_structural_fields"] == ["entity_kind"]


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


def _supporting_rate_card(tmp_path: Path, *, support_witness: bool = True, duplicate_anchor: bool = False,
                          terms_unchanged: bool | None = True, include_dimensions: bool = True):
    content = ("Accepted rate card for agreement AGR-7 dated 2026-08-28.\n"
        "This duplicates signed terms and does not amend them.\n"
        "Asset A / serial S-A: net EUR 12.00 per asset per calendar day.\n"
        + ("Asset A / serial S-A: net EUR 13.00 per asset per calendar day.\n" if duplicate_anchor else "")
        + "Asset B / serial S-B: net EUR 9.00 per asset per calendar day.")
    candidates = [
        {"entity_id": "source-envelope", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "RATE_CARD", "quote": "rate card"},
        {"entity_id": "source-envelope", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ACCEPTED", "quote": "Accepted"},
        {"entity_id": "agreement-header", "semantic_type": "agreement_id", "value_type": "IDENTIFIER",
         "value": "AGR-7", "quote": "agreement AGR-7"},
        {"entity_id": "source-envelope", "semantic_type": "date", "value_type": "DATE",
         "value": "2026-08-28", "quote": "2026-08-28"},
    ]
    if terms_unchanged is not None:
        candidates.append({"entity_id": "source-terms", "semantic_type": "terms_unchanged",
            "value_type": "BOOLEAN", "value": terms_unchanged,
            "quote": "This duplicates signed terms and does not amend them."})
    if support_witness:
        candidates.append({"entity_id": "source-note", "semantic_type": "entity_kind", "value_type": "ENUM",
            "value": "SUPPORTING_DOCUMENT", "quote": "This duplicates signed terms and does not amend them."})
    for label, asset, serial, amount, quote in (
        ("row-a", "A", "S-A", "12.00", "Asset A / serial S-A: net EUR 12.00 per asset per calendar day."),
        *(([("row-a-duplicate", "A", "S-A", "13.00",
             "Asset A / serial S-A: net EUR 13.00 per asset per calendar day.")] if duplicate_anchor else [])),
        ("row-b", "B", "S-B", "9.00", "Asset B / serial S-B: net EUR 9.00 per asset per calendar day."),
    ):
        fields = [
            ("asset_id", "ASSET-" + asset, "IDENTIFIER"), ("serial_number", serial, "IDENTIFIER"),
            ("rate", amount, "DECIMAL"), ("currency", "EUR", "CURRENCY"),
        ]
        if include_dimensions:
            fields.extend([("billing_unit", "DAY", "ENUM"), ("quantity_basis", "PER_ITEM", "ENUM")])
        for field, value, value_type in fields:
            candidate_quote = quote
            if field in {"asset_id", "serial_number"}:
                candidate_quote = f"Asset {asset} / serial {serial}"
            elif field == "rate":
                candidate_quote = quote.split(": ", 1)[1]
            elif field == "currency":
                candidate_quote = "net EUR " + amount
            candidates.append({"entity_id": label, "semantic_type": field, "value_type": value_type,
                               "value": value, "quote": candidate_quote})
    return _proposal(tmp_path, content, candidates)


def test_explicit_supporting_rate_card_rows_get_runtime_structure_not_authority(tmp_path):
    from againward.documents.readers import read_document
    # Read the exact source again because the normalizer binds source unit hashes,
    # spans, role, row anchors and the cited supporting statement together.
    extraction = _supporting_rate_card(tmp_path)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    parsed = read_document(batch.documents[0], source_root)
    normalized = normalize_source_supported_rate_rows(extraction, parsed)
    validate_rental_extraction(normalized, require_package_facts=True)
    rows = [candidate for candidate in normalized.candidates if candidate.semantic_type == "entity_kind"
            and candidate.value == "SUPPORTING_DOCUMENT"]
    assert len(rows) == 3
    assert len({candidate.entity_id for candidate in rows}) == 3
    assert all(candidate.source_id == extraction.source_id for candidate in rows)
    assert all("no rate authority granted" in candidate.normalization_notes for candidate in rows[1:])
    assert {candidate.raw_observed_value for candidate in rows[1:]} == {
        "This duplicates signed terms and does not amend them."}


def test_source_supported_non_amendment_rate_rows_get_structure_without_model_kind(tmp_path):
    from againward.documents.readers import read_document
    extraction = _supporting_rate_card(tmp_path, support_witness=False, include_dimensions=False)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    normalized = normalize_source_supported_rate_rows(
        extraction, read_document(batch.documents[0], source_root))
    validate_rental_extraction(normalized, require_package_facts=True)
    by_entity = {}
    for candidate in normalized.candidates:
        by_entity.setdefault(candidate.entity_id, {})[candidate.semantic_type] = candidate
    rows = [fields for fields in by_entity.values() if "rate" in fields]
    assert len(rows) == 2
    for fields in rows:
        assert fields["entity_kind"].value == "SUPPORTING_DOCUMENT"
        assert fields["billing_unit"].value == "DAY"
        assert fields["quantity_basis"].value == "PER_ITEM"
        assert fields["weekends_billable"].value is True
        assert fields["entity_kind"].source_id == fields["rate"].source_id
        assert fields["entity_kind"].unit_sha256 and fields["rate"].unit_sha256
        assert "no rate authority granted" in fields["entity_kind"].normalization_notes
    from againward.documents.extraction import replay_extraction
    replayed = replay_extraction(normalized.to_dict(), batch, source_root)
    assert replayed.to_dict() == normalized.to_dict()


@pytest.mark.parametrize("terms_unchanged", [None, False])
def test_rate_card_rows_without_explicit_non_amendment_proof_stay_incomplete(tmp_path, terms_unchanged):
    from againward.documents.readers import read_document
    extraction = _supporting_rate_card(tmp_path, support_witness=False, terms_unchanged=terms_unchanged)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    normalized = normalize_source_supported_rate_rows(
        extraction, read_document(batch.documents[0], source_root))
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(normalized)
    assert caught.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


@pytest.mark.parametrize("duplicate_anchor", [True])
def test_rate_card_rows_with_nonunique_occurrence_anchors_stay_incomplete(tmp_path, duplicate_anchor):
    from againward.documents.readers import read_document
    extraction = _supporting_rate_card(tmp_path, support_witness=False,
                                      duplicate_anchor=duplicate_anchor)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    normalized = normalize_source_supported_rate_rows(
        extraction, read_document(batch.documents[0], source_root))
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(normalized)
    assert caught.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_rate_card_projection_does_not_overwrite_conflicting_dimension(tmp_path):
    from againward.documents.readers import read_document
    extraction = _supporting_rate_card(tmp_path, support_witness=False)
    contradictory = replace(extraction, candidates=(*extraction.candidates,
        replace(next(row for row in extraction.candidates if row.semantic_type == "billing_unit"),
                candidate_id="model-conflict", value="MONTH")))
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    normalized = normalize_source_supported_rate_rows(
        contradictory, read_document(batch.documents[0], source_root))
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(normalized)
    assert caught.value.diagnostic["validation_code"] == "STRUCTURAL_METADATA_CONFLICT"


def test_rate_card_projection_requires_one_explicit_native_rate_expression(tmp_path):
    from againward.documents.readers import read_document
    content = ("Accepted rate card for agreement AGR-7.\n"
        "This duplicates signed terms and does not amend them.\n"
        "Asset A / serial S-A: EUR 12 per asset per day or EUR 300 per asset per month.")
    candidates = [
        {"entity_id": "envelope", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "RATE_CARD", "quote": "rate card"},
        {"entity_id": "envelope", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ACCEPTED", "quote": "Accepted"},
        {"entity_id": "envelope", "semantic_type": "terms_unchanged", "value_type": "BOOLEAN",
         "value": True, "quote": "This duplicates signed terms and does not amend them."},
        {"entity_id": "row", "semantic_type": "asset_id", "value_type": "IDENTIFIER",
         "value": "ASSET-A", "quote": "Asset A / serial S-A"},
        {"entity_id": "row", "semantic_type": "serial_number", "value_type": "IDENTIFIER",
         "value": "S-A", "quote": "Asset A / serial S-A"},
        {"entity_id": "row", "semantic_type": "rate", "value_type": "DECIMAL",
         "value": "12", "quote": "EUR 12 per asset per day or EUR 300 per asset per month"},
        {"entity_id": "row", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR 12"},
    ]
    extraction = _proposal(tmp_path, content, candidates)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    normalized = normalize_source_supported_rate_rows(
        extraction, read_document(batch.documents[0], source_root))
    assert not any(candidate.semantic_type == "entity_kind"
                   and candidate.value == "SUPPORTING_DOCUMENT" for candidate in normalized.candidates)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(normalized)
    assert caught.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_rate_card_support_projection_refuses_visual_or_split_line_evidence(tmp_path):
    from dataclasses import replace as dataclass_replace
    from againward.documents.readers import read_document
    extraction = _supporting_rate_card(tmp_path)
    source_root = tmp_path / "documents"
    batch = inventory_sources(tmp_path / "incoming", source_root)
    parsed = read_document(batch.documents[0], source_root)
    visual = dataclass_replace(parsed, units=tuple(dataclass_replace(unit, route="VISUAL")
                                                     for unit in parsed.units))
    visual_result = normalize_source_supported_rate_rows(extraction, visual)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(visual_result)
    assert caught.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


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
        assert structural_gaps(accepted[1:]) == []


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


def test_unique_source_invoice_identity_binds_to_line_without_losing_exact_evidence(tmp_path):
    raw = {"candidates": [
        {"entity_id": "document", "semantic_type": "entity_kind", "value": "SUPPORTING_DOCUMENT",
         "value_type": "ENUM", "raw_observed_value": "attachment", "location": "part:1"},
        {"entity_id": "document", "semantic_type": "document_role", "value": "INVOICE",
         "value_type": "ENUM", "raw_observed_value": "invoice document", "location": "part:1"},
        {"entity_id": "document", "semantic_type": "document_status", "value": "ISSUED",
         "value_type": "ENUM", "raw_observed_value": "issued", "location": "part:1"},
        {"entity_id": "document", "semantic_type": "invoice_id", "value": "INV-8",
         "value_type": "IDENTIFIER", "raw_observed_value": "INV-8", "location": "part:1"},
        {"entity_id": "line", "semantic_type": "entity_kind", "value": "INVOICE_LINE",
         "value_type": "ENUM", "raw_observed_value": "line item", "location": "part:1"},
        {"entity_id": "line", "semantic_type": "currency", "value": "EUR",
         "value_type": "CURRENCY", "raw_observed_value": "EUR", "location": "part:1"},
        {"entity_id": "line", "semantic_type": "net_amount", "value": "20.00",
         "value_type": "DECIMAL", "raw_observed_value": "20.00", "location": "part:1"},
    ]}
    normalized = normalize_document_envelopes(raw, visual=False)
    line_id = next(row for row in normalized["candidates"]
                   if row["entity_id"] == "line" and row["semantic_type"] == "invoice_id")
    assert line_id["value"] == "INV-8"
    assert line_id["raw_observed_value"] == "INV-8"
    assert line_id["location"] == "part:1"
    assert raw["candidates"][-1]["semantic_type"] == "net_amount"  # input remains unchanged

    model_candidates = [{"entity_id": row["entity_id"], "semantic_type": row["semantic_type"],
        "value_type": row["value_type"], "value": row["value"], "quote": row["raw_observed_value"]}
        for row in normalized["candidates"]]
    extraction = _proposal(tmp_path, "attachment invoice document issued INV-8 line item EUR 20.00",
                           model_candidates)
    validate_rental_extraction(extraction, require_package_facts=True)
    assert not package_source_gaps(extraction)
    bound = next(row for row in extraction.candidates
                 if row.entity_id == "line" and row.semantic_type == "invoice_id")
    assert bound.source_id == extraction.source_id
    assert bound.raw_observed_value == "INV-8"


def test_document_identity_is_not_borrowed_from_a_different_source(tmp_path):
    left = {"candidates": [
        {"entity_id": "line", "semantic_type": "entity_kind", "value": "INVOICE_LINE"},
        {"entity_id": "line", "semantic_type": "net_amount", "value": "20.00"},
    ]}
    right = {"candidates": [
        {"entity_id": "other", "semantic_type": "document_role", "value": "INVOICE"},
        {"entity_id": "other", "semantic_type": "invoice_id", "value": "INV-8"},
    ]}
    normalized_left = normalize_document_envelopes(left, visual=False)
    normalized_right = normalize_document_envelopes(right, visual=False)
    assert not any(row["semantic_type"] == "invoice_id" for row in normalized_left["candidates"])
    assert any(row["semantic_type"] == "invoice_id" for row in normalized_right["candidates"])


@pytest.mark.parametrize("visual", [False, True])
def test_unique_agreement_envelope_is_projected_to_each_anchored_scope(visual):
    group_key, rows_key = (("entity_hint", "observations") if visual
                           else ("entity_id", "candidates"))
    quote_key = "visible_text" if visual else "raw_observed_value"
    header = {
        "document_role": ("RENTAL_AGREEMENT", "Accepted rental agreement"),
        "document_status": ("ACCEPTED", "Agreement accepted"),
        "agreement_id": ("AG-100", "Agreement AG-100"),
        "supplier_id": ("SUP-20", "Supplier SUP-20"),
        "client_id": ("SITE-4", "Customer SITE-4"),
        "start": ("2026-09-01", "Hire starts 2026-09-01"),
        "end": ("2026-09-30", "Agreement ends 2026-09-30"),
        "currency": ("EUR", "Net EUR"),
    }
    rows = []
    for semantic, (value, quote) in header.items():
        rows.append({group_key: "header", "semantic_type": semantic, "value_type": "TEXT",
                     "value": value, quote_key: quote, "page": 1, "location": "part:1"})
    for group, asset, serial in (("scope-x", "ASSET-X", "SER-X"),
                                 ("scope-y", "ASSET-Y", "SER-Y")):
        for semantic, value, quote in (("entity_kind", "RENTAL_SCOPE", "Rental scope"),
                                       ("asset_id", asset, f"Asset {asset}"),
                                       ("serial_number", serial, f"Serial {serial}"),
                                       ("description", "platform", "platform"),
                                       ("quantity", "1", "quantity 1")):
            rows.append({group_key: group, "semantic_type": semantic, "value_type": "TEXT",
                         "value": value, quote_key: quote, "page": 1, "location": "part:1"})
    if visual:
        for row in rows:
            row.pop("location")
    original = {rows_key: rows}
    normalized = normalize_document_envelopes(original, visual=visual)
    projected_fields = {"agreement_id", "supplier_id", "client_id", "start", "end", "currency"}
    for group in ("scope-x", "scope-y"):
        fields = {row["semantic_type"]: row for row in normalized[rows_key]
                  if row[group_key] == group}
        for semantic in projected_fields:
            value, quote = header[semantic]
            assert fields[semantic]["value"] == value
            assert fields[semantic][quote_key] == quote
            if visual:
                assert fields[semantic]["page"] == 1
            else:
                assert fields[semantic]["location"] == "part:1"
    source_metadata = {row["semantic_type"]: row for row in normalized[rows_key]
                       if row[group_key] == "header"}
    assert source_metadata["document_role"]["value"] == "RENTAL_AGREEMENT"
    assert source_metadata["document_status"]["value"] == "ACCEPTED"
    assert len(original[rows_key]) == len(rows)  # pure transformation, no input mutation


def test_projected_agreement_fields_keep_exact_native_quote_and_source_binding(tmp_path):
    content = ("Accepted rental agreement AG-100 dated 2026-08-28. Agreement status accepted. "
               "Supplier SUP-20. Customer SITE-4. "
               "Hire starts 2026-09-01 and ends 2026-09-30. Net EUR. "
               "Asset ASSET-X serial SER-X electric platform quantity 1.")
    raw = {"status": "SUCCESS", "limitations": [], "candidates": []}
    for group, semantic, value, quote in (
        ("header", "document_role", "RENTAL_AGREEMENT", "Accepted rental agreement"),
        ("header", "date", "2026-08-28", "dated 2026-08-28"),
        ("header", "document_status", "ACCEPTED", "status accepted"),
        ("header", "agreement_id", "AG-100", "AG-100"),
        ("header", "supplier_id", "SUP-20", "Supplier SUP-20"),
        ("header", "client_id", "SITE-4", "Customer SITE-4"),
        ("header", "start", "2026-09-01", "Hire starts 2026-09-01"),
        ("header", "end", "2026-09-30", "ends 2026-09-30"),
        ("header", "currency", "EUR", "Net EUR"),
        ("scope", "entity_kind", "RENTAL_SCOPE", "Asset ASSET-X"),
        ("scope", "asset_id", "ASSET-X", "Asset ASSET-X"),
        ("scope", "serial_number", "SER-X", "serial SER-X"),
        ("scope", "description", "electric platform", "electric platform"),
        ("scope", "quantity", "1", "quantity 1"),
    ):
        raw["candidates"].append({"entity_id": group, "semantic_type": semantic,
            "value_type": "TEXT", "value": value, "raw_observed_value": quote,
            "location": "part:1", "normalization_notes": "Exact source observation",
            "ambiguity_flags": []})
    normalized = normalize_document_envelopes(raw, visual=False)
    value_types = {"entity_kind": "ENUM", "document_role": "ENUM", "document_status": "ENUM",
                   "date": "DATE",
                   "agreement_id": "IDENTIFIER",
                   "supplier_id": "IDENTIFIER", "client_id": "IDENTIFIER", "start": "DATE",
                   "end": "DATE", "currency": "CURRENCY", "asset_id": "IDENTIFIER",
                   "serial_number": "IDENTIFIER", "description": "TEXT", "quantity": "DECIMAL"}
    model_candidates = [{"entity_id": row["entity_id"], "semantic_type": row["semantic_type"],
        "value_type": value_types[row["semantic_type"]], "value": row["value"],
        "quote": row["raw_observed_value"]} for row in normalized["candidates"]]
    extraction = _proposal(tmp_path, content, model_candidates)
    validate_rental_extraction(extraction, require_package_facts=True)
    assert not package_source_gaps(extraction)
    bound = next(candidate for candidate in extraction.candidates
                 if candidate.entity_id == "scope" and candidate.semantic_type == "supplier_id")
    assert bound.source_id == extraction.source_id
    assert bound.raw_observed_value == "Supplier SUP-20"
    assert bound.location == "line:1"


@pytest.mark.parametrize("change", [
    "missing_role", "missing_agreement_id", "multiple_agreements", "missing_anchor",
    "duplicate_anchor", "contradictory_scope_value",
])
def test_agreement_projection_stops_when_identity_or_value_is_not_unique(change):
    rows = [
        {"entity_id": "header", "semantic_type": "document_role", "value": "RENTAL_AGREEMENT"},
        {"entity_id": "header", "semantic_type": "agreement_id", "value": "AG-100"},
        {"entity_id": "header", "semantic_type": "supplier_id", "value": "SUP-20",
         "raw_observed_value": "Supplier SUP-20", "location": "part:1"},
    ]
    for group, asset in (("scope-x", "ASSET-X"), ("scope-y", "ASSET-Y")):
        rows.extend([
            {"entity_id": group, "semantic_type": "entity_kind", "value": "RENTAL_SCOPE"},
            {"entity_id": group, "semantic_type": "asset_id", "value": asset},
            {"entity_id": group, "semantic_type": "description", "value": "platform"},
        ])
    if change == "missing_role":
        rows = [row for row in rows if row["semantic_type"] != "document_role"]
    elif change == "missing_agreement_id":
        rows = [row for row in rows if row["semantic_type"] != "agreement_id"]
    elif change == "multiple_agreements":
        rows.append({"entity_id": "scope-y", "semantic_type": "agreement_id", "value": "AG-200"})
    elif change == "missing_anchor":
        rows = [row for row in rows if not (row["entity_id"] == "scope-y"
                                            and row["semantic_type"] == "asset_id")]
    elif change == "duplicate_anchor":
        next(row for row in rows if row["entity_id"] == "scope-y"
             and row["semantic_type"] == "asset_id")["value"] = "ASSET-X"
    elif change == "contradictory_scope_value":
        rows.append({"entity_id": "scope-y", "semantic_type": "supplier_id", "value": "SUP-99"})
    normalized = normalize_document_envelopes({"candidates": rows}, visual=False)["candidates"]
    if change == "contradictory_scope_value":
        assert not [row for row in normalized if row["entity_id"] == "scope-x"
                    and row["semantic_type"] == "supplier_id"]
        assert [row["value"] for row in normalized if row["entity_id"] == "scope-y"
                and row["semantic_type"] == "supplier_id"] == ["SUP-99"]
        return
    for group in ("scope-x", "scope-y"):
        suppliers = [row["value"] for row in normalized
                     if row["entity_id"] == group and row["semantic_type"] == "supplier_id"]
        assert not suppliers or suppliers == ["SUP-20"]


@pytest.mark.parametrize("visual", [False, True])
def test_issued_credit_status_is_bound_only_from_unambiguous_same_source_metadata(tmp_path, visual):
    group, rows_key = ("entity_hint", "observations") if visual else ("entity_id", "candidates")
    quote_key = "visible_text" if visual else "raw_observed_value"
    rows = [
        {group: "document", "semantic_type": "document_role", "value": "CREDIT_NOTE",
         "value_type": "ENUM", quote_key: "credit note", "page": 1, "location": "part:1",
         "ambiguity": []},
        {group: "document", "semantic_type": "document_status", "value": "ISSUED",
         "value_type": "ENUM", quote_key: "issued", "page": 1, "location": "part:1",
         "ambiguity": []},
        {group: "credit", "semantic_type": "entity_kind", "value": "CREDIT",
         "value_type": "ENUM", quote_key: "credit", "page": 1, "location": "part:1",
         "ambiguity": []},
    ]
    if visual:
        for row in rows:
            row.pop("location")
    normalized = normalize_document_envelopes({rows_key: rows}, visual=visual)
    derived = next(row for row in normalized[rows_key]
                   if row[group] == "credit" and row["semantic_type"] == "status")
    assert derived["value"] == "ISSUED"
    assert derived[quote_key] == "issued"
    if visual:
        assert set(derived) == {group, "semantic_type", "value_type", "value", quote_key,
                                "page", "ambiguity"}
        assert derived["page"] == 1
    else:
        assert derived["location"] == "part:1"
    assert not any(row["semantic_type"] == "status" for row in rows)


@pytest.mark.parametrize("metadata", [
    [("document_role", "CREDIT_NOTE"), ("document_status", "PROMISED")],
    [("document_role", "UNKNOWN"), ("document_status", "ISSUED")],
    [("document_status", "ISSUED")],
    [("document_role", "CREDIT_NOTE"), ("document_status", "ISSUED"),
     ("document_status", "PROMISED")],
])
def test_credit_status_stays_missing_without_unique_source_proof(metadata):
    rows = [{"entity_id": "credit", "semantic_type": field, "value": value}
            for field, value in metadata]
    rows.extend([{"entity_id": "credit", "semantic_type": "entity_kind", "value": "CREDIT"},
                 {"entity_id": "credit", "semantic_type": "credit_id", "value": "CN-8"},
                 {"entity_id": "credit", "semantic_type": "net_amount", "value": "20.00"}])
    normalized = normalize_document_envelopes({"candidates": rows}, visual=False)
    assert not any(row["semantic_type"] == "status" for row in normalized["candidates"])


def test_credit_without_proven_issued_state_remains_package_blocking(tmp_path):
    candidates = [
        {"entity_id": "credit", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "CREDIT", "quote": "credit issued"},
        {"entity_id": "credit", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "CREDIT_NOTE", "quote": "credit note"},
        {"entity_id": "credit", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ACCEPTED", "quote": "accepted"},
        {"entity_id": "credit", "semantic_type": "credit_id", "value_type": "IDENTIFIER",
         "value": "CN-8", "quote": "CN-8"},
        {"entity_id": "credit", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR"},
        {"entity_id": "credit", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "20.00", "quote": "20.00"},
    ]
    extraction = _proposal(tmp_path, "credit note credit issued accepted CN-8 EUR 20.00", candidates)
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(extraction, require_package_facts=True)
    assert caught.value.diagnostic["missing_semantic_fields"] == ["status"]


def test_issued_credit_source_metadata_completes_only_the_same_source_entity(tmp_path):
    raw = {"candidates": [
        {"entity_id": "document", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "CREDIT_NOTE", "quote": "credit note"},
        {"entity_id": "document", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ISSUED", "quote": "status-issued"},
        {"entity_id": "credit", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "CREDIT", "quote": "credit row"},
        {"entity_id": "credit", "semantic_type": "credit_id", "value_type": "IDENTIFIER",
         "value": "CN-8", "quote": "CN-8"},
        {"entity_id": "credit", "semantic_type": "currency", "value_type": "CURRENCY",
         "value": "EUR", "quote": "EUR"},
        {"entity_id": "credit", "semantic_type": "net_amount", "value_type": "DECIMAL",
         "value": "20.00", "quote": "20.00"},
    ]}
    normalized = normalize_document_envelopes(raw, visual=False)
    candidates = [{"entity_id": row["entity_id"], "semantic_type": row["semantic_type"],
        "value_type": row["value_type"], "value": row["value"], "quote": row["quote"]}
        for row in normalized["candidates"]]
    extraction = _proposal(tmp_path, "credit note status-issued credit row CN-8 EUR 20.00", candidates)
    validate_rental_extraction(extraction, require_package_facts=True)
    status = next(row for row in extraction.candidates
                  if row.entity_id == "credit" and row.semantic_type == "status")
    assert status.value == "ISSUED"
    assert status.source_id == extraction.source_id
    assert status.raw_observed_value == "status-issued"


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
