"""Independent QA must find omissions and swapped entity fields, not bless a pass."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.cli import main
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.extraction import append_adjudicator_native_observations
from againward.documents.independent_qa import (_canonical_observations,
    _observation_comparison, compare_extractions, reread_sources)
from againward.documents.reconciliation import (FACT_RECONCILIATION_VERSION,
    complete_fact_superset, reconcile_complementary_facts)
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.evidence.hashing import stable_hash
from againward.domains.rental.extraction_validation import (package_source_gaps,
    reconstruct_runtime_structure, validate_rental_extraction)
from againward.domains.rental.entity_contract import unique_pixel_entity_for_required_field


def _case(tmp_path, source_text="Invoice I-1 line A net 100; line B net 200."):
    public = tmp_path / "public"
    public.mkdir()
    (public / "invoice.txt").write_text(source_text)
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    raw = {"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": entity, "semantic_type": field, "value_type": kind,
         "value": value, "raw_observed_value": quote, "location": parsed.units[0].location,
         "normalization_notes": "Exact source value", "ambiguity_flags": []}
        for entity, field, kind, value, quote in (
            ("line-A", "invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("line-A", "net_amount", "DECIMAL", "100", "100"),
            ("line-B", "invoice_line_id", "IDENTIFIER", "B", "line B"),
            ("line-B", "net_amount", "DECIMAL", "200", "200"),
        )]}

    def validate(body):
        return validate_proposal(assemble_proposal(body, document, parsed, batch.batch_id,
                                                   "synthetic-model"), batch, root)
    return root, batch, raw, validate


def test_independent_qa_agreement_is_non_authoritative(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    second = validate(deepcopy(raw))
    body = compare_extractions(batch, (first,), (second,), root)
    assert body["status"] == "AGREEMENT"
    assert body["material_status"] == "MATERIAL_AGREEMENT"
    assert body["delivery_approved"] is False
    assert "Same model family" in body["limitations"][0]
    assert body["source_results"][0]["needs_reconciliation"] is False


def test_two_matching_omissions_of_required_invoice_fact_trigger_adjudication(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    raw["candidates"].append({"entity_id": "line-A", "semantic_type": "entity_kind",
        "value_type": "ENUM", "value": "INVOICE_LINE", "raw_observed_value": "line A",
        "location": read_document(batch.documents[0], root).units[0].location,
        "normalization_notes": "Source-bound invoice line", "ambiguity_flags": []})
    first = validate(raw)
    body = compare_extractions(batch, (first,), (validate(deepcopy(raw)),), root)
    row = body["source_results"][0]
    assert body["status"] == "RECONCILIATION_REQUIRED"
    assert row["material_needs_reconciliation"] is True
    assert set(row["primary_source_fact_gaps"]["line-A"]) == {"currency", "invoice_id"}
    # Charge meaning may be proved by reviewed package relations; intrinsic
    # source omissions must still force reconciliation even when readers agree.
    assert "charge_type" not in row["primary_source_fact_gaps"]["line-A"]
    assert row["challenger_source_fact_gaps"] == row["primary_source_fact_gaps"]


def test_independent_qa_finds_omission_and_entity_swap(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    omitted = deepcopy(raw)
    omitted["candidates"].pop()
    missing = compare_extractions(batch, (first,), (validate(omitted),), root)
    assert missing["status"] == "RECONCILIATION_REQUIRED"
    assert missing["material_status"] == "RECONCILIATION_REQUIRED"
    assert missing["source_results"][0]["primary_only_entity_bundles"] == 1

    swapped = deepcopy(raw)
    swapped["candidates"][1]["entity_id"] = "line-B"
    swapped["candidates"][3]["entity_id"] = "line-A"
    mismatch = compare_extractions(batch, (first,), (validate(swapped),), root)
    assert mismatch["status"] == "RECONCILIATION_REQUIRED"
    assert mismatch["material_status"] == "RECONCILIATION_REQUIRED"
    assert mismatch["source_results"][0]["primary_only_entity_bundles"] == 2
    assert {row["entity_id"] for row in mismatch["source_results"][0]["primary_only_entities"]} == {
        "line-A", "line-B"}
    assert any(field["value"] == "100" for row in mismatch["source_results"][0]["challenger_only_entities"]
               for field in row["fields"])
    assert mismatch["source_results"][0]["pre_qa_observation_comparison"]["classification"] == "CONFLICT"


def test_pre_qa_view_ignores_order_and_model_local_entity_labels(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    presentation_variant = deepcopy(raw)
    remap = {"line-A": "arbitrary-left", "line-B": "arbitrary-right"}
    for candidate in presentation_variant["candidates"]:
        candidate["entity_id"] = remap[candidate["entity_id"]]
    presentation_variant["candidates"].reverse()
    body = compare_extractions(batch, (first,), (validate(presentation_variant),), root)
    row = body["source_results"][0]
    assert row["needs_reconciliation"] is False
    assert row["pre_qa_observation_comparison"]["classification"] == "PRESENTATION_EQUIVALENT"


def test_pre_qa_view_places_document_envelope_metadata_at_source_scope(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    source = batch.documents[0]
    location = read_document(source, root).units[0].location
    attached = deepcopy(raw)
    attached["candidates"].extend([
        {"entity_id": "line-A", "semantic_type": "document_role", "value_type": "ENUM",
         "value": "INVOICE", "raw_observed_value": "Invoice", "location": location,
         "normalization_notes": "Source role", "ambiguity_flags": []},
        {"entity_id": "line-A", "semantic_type": "document_status", "value_type": "ENUM",
         "value": "ISSUED", "raw_observed_value": "Invoice", "location": location,
         "normalization_notes": "Source status", "ambiguity_flags": []},
    ])
    separate = deepcopy(attached)
    for candidate in separate["candidates"][-2:]:
        candidate["entity_id"] = "envelope-only"
    first_view = _canonical_observations(validate(attached))
    second_view = _canonical_observations(validate(separate))
    assert _observation_comparison(first_view, second_view)["classification"] == "PRESENTATION_EQUIVALENT"
    assert {row["scope"] for row in second_view if row["semantic_type"] == "document_role"} == {
        "SOURCE_METADATA"}


def test_pre_qa_rate_card_rows_get_stable_occurrence_anchors_and_source_metadata(tmp_path):
    content = ("Accepted rate card for agreement AGR-7 dated 2026-08-28. "
        "Terms unchanged. Asset A / serial S-A: EUR 12 per asset per day. "
        "Asset B / serial S-B: EUR 9 per asset per day.")
    root, batch, _, validate = _case(tmp_path, content)
    location = read_document(batch.documents[0], root).units[0].location
    candidates = []
    for field, kind, value, quote in (
        ("document_role", "ENUM", "RATE_CARD", "rate card"),
        ("document_status", "ENUM", "ACCEPTED", "Accepted"),
        ("agreement_id", "IDENTIFIER", "AGR-7", "agreement AGR-7"),
        ("date", "DATE", "2026-08-28", "2026-08-28"),
        ("terms_unchanged", "BOOLEAN", True, "Terms unchanged"),
    ):
        candidates.append({"entity_id": "header-a", "semantic_type": field, "value_type": kind,
            "value": value, "raw_observed_value": quote, "location": location,
            "normalization_notes": "Exact source observation", "ambiguity_flags": []})
    for label, asset, serial, rate, quote in (
        ("local-group-a", "ASSET-A", "S-A", "12", "Asset A / serial S-A: EUR 12 per asset per day"),
        ("local-group-b", "ASSET-B", "S-B", "9", "Asset B / serial S-B: EUR 9 per asset per day"),
    ):
        for field, kind, value, raw_quote in (
            ("entity_kind", "ENUM", "SUPPORTING_DOCUMENT", quote),
            ("asset_id", "IDENTIFIER", asset, quote),
            ("serial_number", "IDENTIFIER", serial, quote),
            ("rate", "DECIMAL", rate, quote),
            ("currency", "CURRENCY", "EUR", quote),
        ):
            candidates.append({"entity_id": label, "semantic_type": field, "value_type": kind,
                "value": value, "raw_observed_value": raw_quote, "location": location,
                "normalization_notes": "Exact source observation", "ambiguity_flags": []})
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": candidates})
    view = _canonical_observations(extraction)
    rows = [row for row in view if row["semantic_type"] == "rate"]
    assert len(rows) == 2
    assert len({row["anchor"] for row in rows}) == 2
    assert all(row["scope"] == "MATERIAL_ENTITY" for row in rows)
    agreement = next(row for row in view if row["semantic_type"] == "agreement_id")
    assert agreement["scope"] == "REFERENCE" and not agreement["material"]
    assert next(row for row in view if row["semantic_type"] == "terms_unchanged")["scope"] == "SOURCE_METADATA"


def test_pre_qa_view_keeps_invoice_lines_distinct_and_detects_anchored_conflict(tmp_path):
    root, batch, raw, validate = _case(
        tmp_path, "Invoice I-1 line A net 100 or 101; line B net 200.")
    location = read_document(batch.documents[0], root).units[0].location
    raw["candidates"].extend([
        {"entity_id": "line-A", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "INVOICE_LINE", "raw_observed_value": "line A", "location": location,
         "normalization_notes": "Source-bound line kind", "ambiguity_flags": []},
        {"entity_id": "line-B", "semantic_type": "entity_kind", "value_type": "ENUM",
         "value": "INVOICE_LINE", "raw_observed_value": "line B", "location": location,
         "normalization_notes": "Source-bound line kind", "ambiguity_flags": []},
    ])
    first = validate(raw)
    observations = _canonical_observations(first)
    amount_rows = [row for row in observations if row["semantic_type"] == "net_amount"]
    assert {row["anchor"] for row in amount_rows} == {"A", "B"}

    changed = deepcopy(raw)
    changed["candidates"][1]["value"] = "101"
    changed["candidates"][1]["raw_observed_value"] = "101"
    result = _observation_comparison(observations, _canonical_observations(validate(changed)))
    assert result["classification"] == "CONFLICT"
    assert result["conflicting_fields"] == [{"scope": "MATERIAL_ENTITY", "anchor": "A",
                                               "semantic_type": "net_amount"}]


def test_pre_qa_view_retains_visual_and_native_lineage_while_comparing_semantics(tmp_path):
    from dataclasses import replace

    root, batch, raw, validate = _case(tmp_path)
    extraction = validate(raw)
    native = _canonical_observations(extraction)
    visual_candidates = tuple(replace(candidate, location="page:1", unit_sha256="f" * 64,
                                      source_span=None)
                              for candidate in extraction.candidates)
    visual_extraction = replace(extraction, candidates=visual_candidates,
                                visual_bindings=({"page": 1, "render_sha256": "f" * 64},))
    visual = _canonical_observations(visual_extraction)
    assert _observation_comparison(native, visual)["classification"] == "PRESENTATION_EQUIVALENT"
    assert native[0]["location"] != visual[0]["location"]
    assert native[0]["unit_sha256"] != visual[0]["unit_sha256"]


def _anchored_fact_reads(tmp_path, *, challenger_amount="100", include_date=True):
    amount_text = "net 100" if challenger_amount == "100" else "net 100 or 101"
    source_text = f"Invoice I-1, line A, {amount_text}, currency EUR, date 2026-09-01."
    root, batch, _, validate = _case(tmp_path, source_text)
    location = read_document(batch.documents[0], root).units[0].location
    common = [
        ("entity_kind", "ENUM", "INVOICE_LINE", "line A"),
        ("invoice_id", "IDENTIFIER", "I-1", "I-1"),
        ("invoice_line_id", "IDENTIFIER", "A", "line A"),
    ]
    first_rows = common + [("net_amount", "DECIMAL", "100", "100")]
    second_rows = common + [("net_amount", "DECIMAL", challenger_amount, challenger_amount)]
    if include_date:
        second_rows.append(("date", "DATE", "2026-09-01", "2026-09-01"))

    def extraction(rows, label):
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": kind,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for field, kind, value, quote in rows]}
        return validate(raw)

    return root, batch, extraction(first_rows, "first-local-label"), extraction(second_rows, "other-local-label")


def test_fact_reconciliation_unions_anchored_complements_and_binds_both_reads(tmp_path):
    from againward.documents.extraction import replay_extraction

    root, batch, primary, challenger = _anchored_fact_reads(tmp_path)
    merged = reconcile_complementary_facts(primary, challenger, batch, root)
    assert merged is not None
    assert merged.extractor_version == FACT_RECONCILIATION_VERSION
    assert {item.semantic_type for item in merged.candidates} >= {
        "entity_kind", "invoice_id", "invoice_line_id", "net_amount", "date"}
    replayed = replay_extraction(merged.to_dict(), batch, root)
    qa = compare_extractions(batch, (replayed,), (challenger,), root)
    row = qa["source_results"][0]
    assert row["fact_union_verified"] is True
    assert row["pre_qa_observation_comparison"]["classification"] == "PRESENTATION_EQUIVALENT"
    receipt = json.loads((root / "assemblies" / f"{merged.assembly_receipt_sha256}.json").read_text())
    assert {receipt["primary"]["extraction_sha256"], receipt["challenger"]["extraction_sha256"]} == {
        primary.to_dict()["extraction_sha256"], challenger.to_dict()["extraction_sha256"]}


def test_fact_union_preserves_kind_across_a_partial_reader_and_replays_canonically(tmp_path):
    from againward.documents.extraction import replay_extraction

    text = ("Invoice I-9 line A rental charge 100 EUR, dated 2026-09-01. "
            "Document status ISSUED.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location

    def read(label, *, with_kind, with_date=False):
        rows = [
            ("document_role", "ENUM", "INVOICE", "Invoice"),
            ("document_status", "ENUM", "ISSUED", "ISSUED"),
            ("invoice_id", "IDENTIFIER", "I-9", "I-9"),
            ("invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("charge_type", "ENUM", "RENTAL", "rental charge"),
            ("net_amount", "DECIMAL", "100", "100"),
            ("currency", "CURRENCY", "EUR", "EUR"),
        ]
        if with_kind:
            rows.append(("entity_kind", "ENUM", "INVOICE_LINE", "line A"))
        if with_date:
            rows.append(("date", "DATE", "2026-09-01", "2026-09-01"))
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for field, value_type, value, quote in rows]})

    primary = read("first-read-label", with_kind=False)
    challenger = read("reread-label", with_kind=True, with_date=True)
    merged = reconcile_complementary_facts(primary, challenger, batch, root)
    assert merged is not None
    validate_rental_extraction(merged)
    line_fields = {"entity_kind", "invoice_id", "invoice_line_id", "charge_type",
                   "net_amount", "currency", "date"}
    line_candidates = [candidate for candidate in merged.candidates
                       if candidate.semantic_type in line_fields]
    assert {candidate.semantic_type for candidate in line_candidates} == line_fields
    assert len({candidate.entity_id for candidate in line_candidates}) == 1
    assert all(candidate.source_id == batch.documents[0].source_id
               and candidate.source_span is not None for candidate in line_candidates)
    replayed = replay_extraction(merged.to_dict(), batch, root)
    validate_rental_extraction(replayed)
    assert reconstruct_runtime_structure(replayed) == replayed
    assert [(c.semantic_type, c.value, c.entity_id)
            for c in replayed.candidates] == [
                (c.semantic_type, c.value, c.entity_id)
                for c in merged.candidates]
    receipt = json.loads((root / "assemblies" / f"{merged.assembly_receipt_sha256}.json").read_text())
    source_labels = {candidate["entity_id"] for parent in (receipt["primary"], receipt["challenger"])
                     for candidate in parent["candidates"]}
    assert {"first-read-label", "reread-label"} <= source_labels


def test_exact_duplicate_rate_atom_is_assigned_to_one_anchored_occurrence(tmp_path):
    text = ("Accepted rental agreement AG-22. Asset: UNIT-7. "
            "Rental rate EUR 90.00 per asset per calendar day.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    rows = [
        ("scope", "entity_kind", "ENUM", "RENTAL_SCOPE", "Accepted rental agreement AG-22."),
        ("scope", "document_role", "ENUM", "RENTAL_AGREEMENT", "Accepted rental agreement AG-22."),
        ("scope", "document_status", "ENUM", "ACCEPTED", "Accepted rental agreement AG-22."),
        ("scope", "agreement_id", "IDENTIFIER", "AG-22", "AG-22"),
        ("scope", "asset_id", "IDENTIFIER", "UNIT-7", "UNIT-7"),
        ("scope", "rate", "DECIMAL", "90.00", "Rental rate EUR 90.00 per asset per calendar day."),
        ("scope", "currency", "CURRENCY", "EUR", "Rental rate EUR 90.00 per asset per calendar day."),
        ("orphan-rate", "unit_rate", "DECIMAL", "90.00", "Rental rate EUR 90.00 per asset per calendar day."),
    ]
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": group, "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact cited source observation", "ambiguity_flags": []}
        for group, field, value_type, value, quote in rows]})

    normalized = reconstruct_runtime_structure(extraction)
    rate = next(c for c in normalized.candidates if c.semantic_type == "rate")
    atom = next(c for c in normalized.candidates if c.semantic_type == "unit_rate")
    assert atom.entity_id == rate.entity_id
    assert atom.source_span == rate.source_span
    assert atom.source_id == rate.source_id == extraction.source_id
    assert normalized.source_sha256 == extraction.source_sha256
    validate_rental_extraction(normalized)
    assert reconstruct_runtime_structure(normalized) == normalized


def test_rate_atom_is_not_assigned_when_multiple_occurrences_share_the_same_proof(tmp_path):
    text = ("Accepted rental agreement AG-23 lists UNIT-7 and UNIT-8. "
            "Rental rate EUR 90.00 per asset per calendar day.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    quote = "Rental rate EUR 90.00 per asset per calendar day."
    rows = []
    for label, asset in (("scope-left", "UNIT-7"), ("scope-right", "UNIT-8")):
        rows.extend([
            (label, "entity_kind", "ENUM", "RENTAL_SCOPE", "Accepted rental agreement AG-23"),
            (label, "agreement_id", "IDENTIFIER", "AG-23", "AG-23"),
            (label, "asset_id", "IDENTIFIER", asset, asset),
            (label, "rate", "DECIMAL", "90.00", quote),
        ])
    rows.append(("untyped-atom", "unit_rate", "DECIMAL", "90.00", quote))
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": group, "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": observed, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for group, field, value_type, value, observed in rows]})

    normalized = reconstruct_runtime_structure(extraction)
    atom = next(c for c in normalized.candidates if c.semantic_type == "unit_rate")
    typed_occurrences = {c.entity_id for c in normalized.candidates
                         if c.semantic_type == "entity_kind"}
    assert atom.entity_id not in typed_occurrences
    with pytest.raises(DocumentError) as caught:
        validate_rental_extraction(normalized)
    assert caught.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_source_supplier_identifier_alone_does_not_create_a_pseudo_entity(tmp_path):
    text = "Invoice I-8 issued by supplier ACME-4."
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    rows = [
        ("document", "document_role", "ENUM", "INVOICE", "Invoice"),
        ("document", "document_status", "ENUM", "ISSUED", "issued"),
        ("supplier-fragment", "supplier_id", "IDENTIFIER", "ACME-4", "ACME-4"),
    ]
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": group, "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for group, field, value_type, value, quote in rows]})

    validate_rental_extraction(extraction)
    supplier = next(c for c in _canonical_observations(extraction)
                    if c["semantic_type"] == "supplier_id")
    assert supplier["scope"] == "SOURCE_METADATA" and supplier["anchor"] is None
    assert next(c for c in extraction.candidates if c.semantic_type == "supplier_id").entity_id == "supplier-fragment"


def test_adjudication_delta_restores_only_unique_same_source_structure(tmp_path):
    text = "Invoice I-7 line C equipment charge 55 EUR. Status ISSUED."
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location

    def read(label, fields):
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for field, value_type, value, quote in fields]})

    selected = read("selected-local-group", [
        ("invoice_id", "IDENTIFIER", "I-7", "I-7"),
        ("invoice_line_id", "IDENTIFIER", "C", "line C"),
        ("net_amount", "DECIMAL", "55", "55"),
    ])
    sibling = read("sibling-local-group", [
        ("entity_kind", "ENUM", "INVOICE_LINE", "line C"),
        ("document_role", "ENUM", "INVOICE", "Invoice"),
        ("document_status", "ENUM", "ISSUED", "ISSUED"),
        ("invoice_id", "IDENTIFIER", "I-7", "I-7"),
        ("invoice_line_id", "IDENTIFIER", "C", "line C"),
    ])
    restored = reconstruct_runtime_structure(selected, (sibling,))
    validate_rental_extraction(restored)
    by_field = {candidate.semantic_type: candidate for candidate in restored.candidates}
    assert {field: by_field[field].value for field in (
        "entity_kind", "document_role", "document_status")} == {
            "entity_kind": "INVOICE_LINE", "document_role": "INVOICE", "document_status": "ISSUED"}
    assert by_field["entity_kind"].entity_id == by_field["invoice_line_id"].entity_id
    assert by_field["entity_kind"].source_id == batch.documents[0].source_id
    assert by_field["entity_kind"].source_span is not None
    assert by_field["entity_kind"].entity_id.startswith("runtime-entity-")
    assert sibling.candidates[0].entity_id == "sibling-local-group"
    assert by_field["document_role"].entity_id.startswith("runtime-source-")
    assert by_field["document_status"].entity_id == by_field["document_role"].entity_id
    assert by_field["document_role"].entity_id != by_field["entity_kind"].entity_id
    assert reconstruct_runtime_structure(restored, (sibling,)) == restored

    # No explicit occurrence anchor means the sibling kind and source metadata
    # cannot be attached to an unrelated recovered fact.
    unanchored = read("no-identity", [("net_amount", "DECIMAL", "55", "55")])
    untouched = reconstruct_runtime_structure(unanchored, (sibling,))
    assert not any(candidate.semantic_type == "entity_kind" for candidate in untouched.candidates)
    with pytest.raises(DocumentError) as excinfo:
        validate_rental_extraction(untouched)
    assert excinfo.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_runtime_structure_never_imports_metadata_from_another_source(tmp_path):
    from dataclasses import replace

    root, batch, primary, challenger = _anchored_fact_reads(tmp_path)
    foreign = replace(challenger, source_id="src-foreign")
    restored = reconstruct_runtime_structure(primary, (foreign,))
    assert not any(candidate.semantic_type in {"document_role", "document_status"}
                   for candidate in restored.candidates)
    stale = replace(challenger, source_sha256="f" * 64)
    stale_restored = reconstruct_runtime_structure(primary, (stale,))
    assert not any(candidate.semantic_type in {"document_role", "document_status"}
                   for candidate in stale_restored.candidates)


def test_runtime_structure_binds_kind_to_one_line_without_leaking_to_sibling_line(tmp_path):
    text = "Invoice I-4 line A net 100; line B net 200. Invoice issued."
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location

    def read(label, with_kind):
        rows = [
            ("A", "invoice_id", "IDENTIFIER", "I-4", "I-4"),
            ("A", "invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("A", "net_amount", "DECIMAL", "100", "100"),
            ("B", "invoice_id", "IDENTIFIER", "I-4", "I-4"),
            ("B", "invoice_line_id", "IDENTIFIER", "B", "line B"),
            ("B", "net_amount", "DECIMAL", "200", "200"),
        ]
        if with_kind:
            rows.append(("A", "entity_kind", "ENUM", "INVOICE_LINE", "line A"))
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": f"{label}-{line}", "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for line, field, value_type, value, quote in rows]})

    selected = read("selected", False)
    sibling = read("sibling", True)
    restored = reconstruct_runtime_structure(selected, (sibling,))
    kind_candidates = [candidate for candidate in restored.candidates
                       if candidate.semantic_type == "entity_kind"]
    assert len(kind_candidates) == 1
    assert kind_candidates[0].raw_observed_value == "line A"
    assert kind_candidates[0].entity_id == next(candidate.entity_id for candidate in restored.candidates
        if candidate.semantic_type == "invoice_line_id" and candidate.value == "A")
    assert next(candidate.entity_id for candidate in restored.candidates
        if candidate.semantic_type == "invoice_line_id" and candidate.value == "B") != kind_candidates[0].entity_id
    with pytest.raises(DocumentError) as excinfo:
        validate_rental_extraction(restored)
    assert excinfo.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_runtime_structure_does_not_infer_source_role_or_status_from_filename(tmp_path):
    text = "A record I-5 with line A and amount 100."
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    selected = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "local-line", "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for field, value_type, value, quote in (
            ("entity_kind", "ENUM", "INVOICE_LINE", "line A"),
            ("invoice_id", "IDENTIFIER", "I-5", "I-5"),
            ("invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("net_amount", "DECIMAL", "100", "100"),
        )]})
    reconstructed = reconstruct_runtime_structure(selected)
    assert not any(candidate.semantic_type in {"document_role", "document_status"}
                   for candidate in reconstructed.candidates)
    with pytest.raises(DocumentError) as excinfo:
        validate_rental_extraction(reconstructed)
    assert excinfo.value.diagnostic["validation_code"] == "ENTITY_METADATA_REQUIRED"


def test_runtime_structure_keeps_document_status_conflict_fail_closed(tmp_path):
    text = "Invoice I-8 line A status ISSUED or PROPOSED, net 100."
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "local-group", "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for field, value_type, value, quote in (
            ("entity_kind", "ENUM", "INVOICE_LINE", "line A"),
            ("document_role", "ENUM", "INVOICE", "Invoice"),
            ("document_status", "ENUM", "ISSUED", "ISSUED"),
            ("document_status", "ENUM", "PROPOSED", "PROPOSED"),
            ("invoice_id", "IDENTIFIER", "I-8", "I-8"),
            ("invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("net_amount", "DECIMAL", "100", "100"),
        )]})
    reconstructed = reconstruct_runtime_structure(extraction)
    assert {candidate.value for candidate in reconstructed.candidates
            if candidate.semantic_type == "document_status"} == {"ISSUED", "PROPOSED"}
    with pytest.raises(DocumentError) as excinfo:
        validate_rental_extraction(reconstructed)
    assert excinfo.value.diagnostic["validation_code"] == "STRUCTURAL_METADATA_CONFLICT"


def test_runtime_structure_restores_source_metadata_once_for_multiline_export(tmp_path):
    text = ("Payment export mirror: ref R-1 agreement G-1 asset A-1 net 100; "
            "ref R-2 agreement G-1 asset A-2 net 200; "
            "ref R-3 agreement G-2 asset A-3 net 300. Export status EXTRACTED.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location

    def read(label, rows):
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": group, "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for group, field, value_type, value, quote in rows]})

    records = []
    for ref, agreement, asset, amount in (
        ("R-1", "G-1", "A-1", "100"),
        ("R-2", "G-1", "A-2", "200"),
        ("R-3", "G-2", "A-3", "300"),
    ):
        records.extend([
            (ref, "entity_kind", "ENUM", "SUPPORTING_DOCUMENT", "Payment export mirror"),
            (ref, "source_reference", "IDENTIFIER", ref, ref),
            (ref, "agreement_id", "IDENTIFIER", agreement, f"ref {ref} agreement {agreement}"),
            (ref, "asset_id", "IDENTIFIER", asset,
             f"ref {ref} agreement {agreement} asset {asset}"),
            (ref, "net_amount", "DECIMAL", amount, amount),
        ])
    selected = read("selected", records)
    envelope = read("envelope", [
        ("envelope", "document_role", "ENUM", "PAYMENT_EXPORT", "Payment export mirror"),
        ("envelope", "document_status", "ENUM", "EXTRACTED", "EXTRACTED"),
    ])
    restored = reconstruct_runtime_structure(selected, (envelope,))
    validate_rental_extraction(restored)
    row_entities = {candidate.entity_id for candidate in restored.candidates
                    if candidate.semantic_type == "source_reference"}
    source_metadata = [candidate for candidate in restored.candidates
                       if candidate.semantic_type in {"document_role", "document_status"}]
    assert len(row_entities) == 3
    assert len(source_metadata) == 2
    assert len({candidate.entity_id for candidate in source_metadata}) == 1
    assert source_metadata[0].entity_id.startswith("runtime-source-")
    assert source_metadata[0].entity_id not in row_entities


def _native_export_extraction(*, label: str, role: str | None,
                              supporting_rows: frozenset[int] = frozenset(),
                              duplicate_row_group: bool = False):
    from againward.documents.extraction import DocumentExtraction, FactCandidate

    source_id, source_sha = "src-ledger", "a" * 64
    candidates = []
    serial = 0

    def add(group: str, field: str, value_type: str, value: str,
            raw: str, location: str) -> None:
        nonlocal serial
        serial += 1
        candidates.append(FactCandidate(
            candidate_id=f"{label}-{serial}", entity_id=group,
            semantic_type=field, value_type=value_type, value=value,
            raw_observed_value=raw, location=location, source_id=source_id,
            unit_sha256=stable_hash({"source": source_sha, "location": location, "raw": raw}),
            normalization_notes="Source-bound proposal", ambiguity_flags=(),
            source_span=(0, len(raw)), confidence="MEDIUM"))

    if role is not None:
        add(f"{label}-metadata", "document_role", "ENUM", role,
            "Mirror only", "sheet:Ledger/cell:F2")
    add(f"{label}-metadata", "document_status", "ENUM", "EXTRACTED",
        "Mirror only", "sheet:Ledger/cell:F2")
    for row, reference, value, amount in (
        (2, "invoice_id", "INV-44", "125.00"),
        (3, "invoice_id", "INV-45", "80.00"),
        (4, "credit_id", "CN-12", "25.00"),
    ):
        group = f"{label}-row-{row}"
        def cell(column):
            return f"sheet:Ledger/cell:{column}{row}"

        if row in supporting_rows:
            add(group, "entity_kind", "ENUM", "SUPPORTING_DOCUMENT", "Mirror only", cell("F"))
        add(group, reference, "IDENTIFIER", value, value, cell("A"))
        add(group, "agreement_id", "IDENTIFIER", "AG-22", "AG-22", cell("B"))
        add(group, "net_amount", "DECIMAL", amount, amount, cell("C"))
    if duplicate_row_group:
        add(f"{label}-other-group", "invoice_id", "IDENTIFIER", "INV-44",
            "INV-44", "sheet:Ledger/cell:A2")
        add(f"{label}-other-group", "net_amount", "DECIMAL", "125.00",
            "125.00", "sheet:Ledger/cell:C2")
    return DocumentExtraction(source_id=source_id, source_sha256=source_sha,
        batch_id="batch-ledger", reader_version="xlsx-v1", extractor_version="test-v1",
        model="test-model", prompt_version="test-prompt", created_at="2026-09-30T00:00:00Z",
        visual_bindings=(), invocation_id=None, status="NEEDS_REVIEW",
        candidates=tuple(candidates), limitations=())


def test_payment_export_reconstructs_supporting_kind_from_source_role_and_unique_rows():
    selected = _native_export_extraction(label="primary-local", role=None)
    sibling = _native_export_extraction(label="reread-local", role="PAYMENT_EXPORT",
                                         supporting_rows=frozenset({2, 3}))
    restored = reconstruct_runtime_structure(selected, (sibling,))
    kinds = [candidate for candidate in restored.candidates
             if candidate.semantic_type == "entity_kind"]
    assert len(kinds) == 3
    assert {candidate.value for candidate in kinds} == {"SUPPORTING_DOCUMENT"}
    assert len({candidate.entity_id for candidate in kinds}) == 3
    assert all(candidate.entity_id.startswith("runtime-entity-") for candidate in kinds)
    assert all(candidate.source_id == selected.source_id and candidate.unit_sha256
               and candidate.source_span is not None for candidate in kinds)
    assert all("unapproved supporting-record container" in candidate.normalization_notes
               for candidate in kinds)
    assert {candidate.value for candidate in restored.candidates
            if candidate.semantic_type == "document_role"} == {"PAYMENT_EXPORT"}
    assert {candidate.value for candidate in restored.candidates
            if candidate.semantic_type == "document_status"} == {"EXTRACTED"}
    validate_rental_extraction(restored)

    relabeled = reconstruct_runtime_structure(
        _native_export_extraction(label="different-reader-label", role=None), (sibling,))
    def comparable(extraction):
        return sorted((candidate.semantic_type, candidate.value, candidate.location, candidate.entity_id)
                      for candidate in extraction.candidates
                      if candidate.semantic_type in {
                          "entity_kind", "invoice_id", "credit_id", "net_amount"})

    assert comparable(relabeled) == comparable(restored)
    assert reconstruct_runtime_structure(restored, (sibling,)) == restored


@pytest.mark.parametrize(("primary_role", "peer_role", "duplicate_row_group"), [
    ("INVOICE", "INVOICE", False),
    ("PAYMENT_EXPORT", "INVOICE", False),
    (None, None, False),
    ("PAYMENT_EXPORT", "PAYMENT_EXPORT", True),
])
def test_payment_export_projection_requires_unique_source_role_and_row(
        primary_role, peer_role, duplicate_row_group):
    primary = _native_export_extraction(label="primary", role=primary_role,
                                         duplicate_row_group=duplicate_row_group)
    peer = _native_export_extraction(label="peer", role=peer_role)
    result = reconstruct_runtime_structure(primary, (peer,))
    derived = [candidate for candidate in result.candidates
               if candidate.semantic_type == "entity_kind"
               and candidate.candidate_id.startswith("runtime-kind-")]
    if duplicate_row_group:
        assert len(derived) == 2
    else:
        assert not derived


def test_payment_export_reconstruction_does_not_type_reference_only_fragments():
    from dataclasses import replace as dataclass_replace

    extraction = _native_export_extraction(label="reader", role="PAYMENT_EXPORT")
    reference = next(candidate for candidate in extraction.candidates
                     if candidate.semantic_type == "invoice_id")
    fragment = dataclass_replace(reference, candidate_id="orphan-reference",
                                 entity_id="orphan-reference")
    extraction = dataclass_replace(extraction, candidates=extraction.candidates + (fragment,))
    restored = reconstruct_runtime_structure(extraction)
    orphan = [candidate for candidate in restored.candidates
              if candidate.candidate_id == "orphan-reference"]
    assert len(orphan) == 1 and orphan[0].semantic_type == "invoice_id"


def test_selected_challenger_is_runtime_reconstructed_before_completeness():
    from againward.domains.rental.source_job import _reconstruct_selected_runtime_structure

    primary = _native_export_extraction(label="primary", role=None)
    challenger = _native_export_extraction(label="challenger", role="PAYMENT_EXPORT",
                                             supporting_rows=frozenset({2, 3}))
    primary_hash = primary.to_dict()["extraction_sha256"]
    challenger_hash = challenger.to_dict()["extraction_sha256"]
    adjudication = {"selected_extractions": {primary.source_id: challenger_hash},
                    "adjudication_sha256": "old-receipt-hash"}

    receipt, reconstructed = _reconstruct_selected_runtime_structure(
        adjudication, (primary, challenger))

    selected = reconstructed[primary.source_id]
    assert receipt["selected_extractions"][primary.source_id] == selected.to_dict()["extraction_sha256"]
    assert receipt["selected_extractions"][primary.source_id] != challenger_hash
    binding = receipt["runtime_reconstructed_extractions"][primary.source_id]
    assert binding == {"selected_proposal_sha256": challenger_hash,
                       "runtime_extraction_sha256": selected.to_dict()["extraction_sha256"],
                       "source_sha256": primary.source_sha256}
    assert receipt["adjudication_sha256"] == stable_hash({
        key: value for key, value in receipt.items() if key != "adjudication_sha256"})
    assert primary_hash != challenger_hash
    assert len({candidate.entity_id for candidate in selected.candidates
                if candidate.semantic_type == "entity_kind"}) == 3
    assert {candidate.value for candidate in selected.candidates
            if candidate.semantic_type == "entity_kind"} == {"SUPPORTING_DOCUMENT"}
    assert all(candidate.source_id == primary.source_id and candidate.unit_sha256
               and candidate.source_span is not None
               for candidate in selected.candidates if candidate.semantic_type == "entity_kind")
    validate_rental_extraction(selected, require_package_facts=True)


def test_selected_proposal_does_not_invent_kind_without_source_role():
    from againward.domains.rental.source_job import _reconstruct_selected_runtime_structure

    primary = _native_export_extraction(label="primary", role=None)
    challenger = _native_export_extraction(label="challenger", role=None)
    selected_hash = primary.to_dict()["extraction_sha256"]
    adjudication = {"selected_extractions": {primary.source_id: selected_hash},
                    "adjudication_sha256": "unchanged"}

    receipt, reconstructed = _reconstruct_selected_runtime_structure(
        adjudication, (primary, challenger))

    assert primary.source_id in reconstructed
    selected = reconstructed[primary.source_id]
    assert receipt["selected_extractions"][primary.source_id] == selected.to_dict()["extraction_sha256"]
    assert receipt["selected_extractions"][primary.source_id] != selected_hash
    assert not any(candidate.candidate_id.startswith("runtime-kind-")
                   for candidate in selected.candidates)
    assert all(candidate.semantic_type != "entity_kind" for candidate in selected.candidates)
    assert receipt["adjudication_sha256"] == stable_hash({
        key: value for key, value in receipt.items() if key != "adjudication_sha256"})


def test_payment_export_projection_requires_current_same_source_native_binding():
    from dataclasses import replace as dataclass_replace

    selected = _native_export_extraction(label="primary", role=None)
    sibling = _native_export_extraction(label="peer", role="PAYMENT_EXPORT",
                                         supporting_rows=frozenset({2, 3, 4}))
    foreign = dataclass_replace(sibling, source_id="src-other")
    stale = dataclass_replace(sibling, source_sha256="b" * 64)
    for peer in (foreign, stale):
        result = reconstruct_runtime_structure(selected, (peer,))
        assert not any(candidate.semantic_type == "entity_kind"
                       and candidate.candidate_id.startswith("runtime-kind-")
                       for candidate in result.candidates)

    visual_candidates = tuple(dataclass_replace(candidate,
        location="page:1", source_span=None, unit_sha256="") for candidate in sibling.candidates)
    visual_peer = dataclass_replace(sibling, candidates=visual_candidates)
    result = reconstruct_runtime_structure(selected, (visual_peer,))
    assert not any(candidate.semantic_type == "entity_kind"
                   and candidate.candidate_id.startswith("runtime-kind-")
                   for candidate in result.candidates)


def test_adjudication_delta_binds_and_canonicalizes_explicit_offhire_event(tmp_path):
    text = ("Email evidence E-7 for agreement AG-7 and asset UNIT-11. "
            "On 2026-03-04 the supplier requested off-hire and collection of one UNIT-11 unit.")
    root, batch, _, validate = _case(tmp_path, text)
    unit = read_document(batch.documents[0], root).units[0]
    location = unit.location
    event_quote = "On 2026-03-04 the supplier requested off-hire and collection of one UNIT-11 unit."
    source_quote = "Email evidence E-7 for agreement AG-7 and asset UNIT-11."
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "reader-local-a", "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for field, value_type, value, quote in (
            ("agreement_id", "IDENTIFIER", "AG-7", source_quote),
            ("asset_id", "IDENTIFIER", "UNIT-11", source_quote),
            ("event_type", "ENUM", "OFF_HIRE_REQUESTED", event_quote),
            ("quantity", "DECIMAL", "1", event_quote),
            ("status", "ENUM", "DECLARED", event_quote),
            ("document_role", "ENUM", "EMAIL_EVIDENCE", "Email evidence"),
            ("document_status", "ENUM", "EXTRACTED", "Email evidence"),
        )]})
    def observation(field, value_type, value, quote):
        start = unit.text.index(quote)
        return {"candidate_id": "model-local-" + field, "source_id": extraction.source_id,
                "semantic_type": field, "value_type": value_type, "value": value,
                "raw_observed_value": quote, "location": location,
                "unit_sha256": unit.unit_sha256, "source_span": [start, start + len(quote)],
                "normalization_notes": "Source-supported observation", "ambiguity_flags": [],
                "confidence": "0.9", "entity_id": "adjudicator-local-label"}
    observations = [
        observation("date", "DATE", "2026-03-04", "2026-03-04"),
        observation("entity_kind", "ENUM", "RENTAL_SCOPE",
                    "requested off-hire and collection of one UNIT-11 unit"),
    ]
    assert unique_pixel_entity_for_required_field("date", location, list(extraction.candidates)) == "reader-local-a"
    assert unique_pixel_entity_for_required_field("entity_kind", location,
                                                   list(extraction.candidates)) == "reader-local-a"
    augmented = append_adjudicator_native_observations(extraction, observations, batch, root,
        "a" * 64, unique_required_entity=unique_pixel_entity_for_required_field)
    canonical = reconstruct_runtime_structure(augmented)
    validate_rental_extraction(canonical, require_package_facts=True)

    event_rows = [row for row in canonical.candidates if row.semantic_type in {
        "entity_kind", "event_type", "agreement_id", "asset_id", "date", "quantity",
        "status", "verification"}]
    assert {row.entity_id for row in event_rows} == {"runtime-entity-" + stable_hash({
            "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
            "anchor": (extraction.source_id, "RETURN", "AG-7", "UNIT-11",
                       "OFF_HIRE_REQUESTED", "2026-03-04")})[:24]}
    assert {row.value for row in event_rows if row.semantic_type == "entity_kind"} == {"RETURN"}
    assert {row.value for row in event_rows if row.semantic_type == "verification"} == {"DECLARED"}
    assert not any("RENTAL_SCOPE" == row.value and row.semantic_type == "entity_kind"
                   for row in canonical.candidates)
    for row in event_rows:
        assert row.source_id == extraction.source_id
        assert row.source_span is not None
    assert reconstruct_runtime_structure(canonical) == canonical


def test_event_kind_derivation_refuses_ambiguous_or_non_event_occurrences(tmp_path):
    text = ("Agreement AG-8 asset UNIT-21 off-hire requested on 2026-04-01; "
            "agreement AG-8 asset UNIT-22 off-hire requested on 2026-04-02.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": group, "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": quote, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for group, field, value_type, value, quote in (
            ("event-a", "agreement_id", "IDENTIFIER", "AG-8", "Agreement AG-8"),
            ("event-a", "asset_id", "IDENTIFIER", "UNIT-21", "asset UNIT-21"),
            ("event-a", "event_type", "ENUM", "OFF_HIRE_REQUESTED", "UNIT-21 off-hire requested"),
            ("event-b", "agreement_id", "IDENTIFIER", "AG-8", "Agreement AG-8"),
            ("event-b", "asset_id", "IDENTIFIER", "UNIT-22", "asset UNIT-22"),
            ("event-b", "event_type", "ENUM", "OFF_HIRE_REQUESTED", "UNIT-22 off-hire requested"),
        )]})
    assert unique_pixel_entity_for_required_field("date", location,
                                                   list(extraction.candidates)) is None
    unchanged = reconstruct_runtime_structure(extraction)
    assert len([row for row in unchanged.candidates if row.semantic_type == "entity_kind"]) == 2
    assert unique_pixel_entity_for_required_field("date", location,
                                                   list(unchanged.candidates)) is None

    unrelated = deepcopy(extraction)
    candidates = list(unrelated.candidates)
    candidates = [replace(row, value="INVOICED") if row.entity_id == "event-a"
                  and row.semantic_type == "event_type" else row for row in candidates]
    unrelated = replace(unrelated, candidates=tuple(candidates))
    normalized = reconstruct_runtime_structure(unrelated)
    kinds_by_group = {row.entity_id: row.value for row in normalized.candidates
                      if row.semantic_type == "entity_kind"}
    assert kinds_by_group == {"event-b": "RETURN"}


def test_transaction_reference_to_event_does_not_become_return_entity(tmp_path):
    text = ("Credit CN-4 for agreement AG-10 and asset UNIT-41 references an off-hire "
            "request and collection; the credit is issued for 25 EUR.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    quote = "Credit CN-4 for agreement AG-10 and asset UNIT-41 references an off-hire request"
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "credit-record", "semantic_type": field, "value_type": value_type,
         "value": value, "raw_observed_value": observed, "location": location,
         "normalization_notes": "Exact source observation", "ambiguity_flags": []}
        for field, value_type, value, observed in (
            ("credit_id", "IDENTIFIER", "CN-4", "CN-4"),
            ("agreement_id", "IDENTIFIER", "AG-10", "AG-10"),
            ("asset_id", "IDENTIFIER", "UNIT-41", "UNIT-41"),
            ("event_type", "ENUM", "OFF_HIRE_REQUESTED", quote),
        )]})
    reconstructed = reconstruct_runtime_structure(extraction)
    assert not any(row.semantic_type == "entity_kind" for row in reconstructed.candidates)


def test_unique_rental_agreement_scope_gets_runtime_container_but_not_authority(tmp_path):
    text = ("RENTAL AGREEMENT for AG-8. Supplier: SUP-8. Customer: SITE-8. "
            "Asset: UNIT-28. Description: electric platform. Quantity: 2. "
            "Hire starts 2026-04-01 and ends 2026-04-08.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    rows = [
        ("document_role", "ENUM", "RENTAL_AGREEMENT", "RENTAL AGREEMENT"),
        ("agreement_id", "IDENTIFIER", "AG-8", "AG-8"),
        ("asset_id", "IDENTIFIER", "UNIT-28", "UNIT-28"),
        ("description", "TEXT", "electric platform", "electric platform"),
        ("quantity", "DECIMAL", "2", "Quantity: 2"),
        ("start", "DATE", "2026-04-01", "2026-04-01"),
        ("end", "DATE", "2026-04-08", "2026-04-08"),
        ("document_status", "ENUM", "ACCEPTED", "RENTAL AGREEMENT"),
    ]
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "local-document-bucket", "semantic_type": field,
         "value_type": value_type, "value": value, "raw_observed_value": quote,
         "location": location, "normalization_notes": "Exact source observation",
         "ambiguity_flags": []}
        for field, value_type, value, quote in rows]})
    reconstructed = reconstruct_runtime_structure(extraction)
    kind_rows = [row for row in reconstructed.candidates if row.semantic_type == "entity_kind"]
    assert len(kind_rows) == 1
    assert kind_rows[0].value == "RENTAL_SCOPE"
    assert kind_rows[0].source_id == extraction.source_id
    assert kind_rows[0].source_span is not None
    assert "ADJUDICATOR" not in " ".join(kind_rows[0].ambiguity_flags)
    assert not any(row.semantic_type in {"governing_agreement", "commercial_authority"}
                   for row in reconstructed.candidates)
    relabeled = replace(extraction, candidates=tuple(
        replace(row, entity_id="different-reader-label") for row in extraction.candidates))
    relabeled_kind = [row for row in reconstruct_runtime_structure(relabeled).candidates
                      if row.semantic_type == "entity_kind"]
    assert [row.candidate_id for row in relabeled_kind] == [row.candidate_id for row in kind_rows]


@pytest.mark.parametrize("change", ["role", "missing_end", "multiple_assets"])
def test_rental_scope_container_is_not_inferred_from_weak_or_ambiguous_evidence(tmp_path, change):
    text = ("RENTAL AGREEMENT for AG-9, asset UNIT-31, description lift, quantity 1, "
            "starts 2026-05-01, ends 2026-05-04; asset UNIT-32.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    rows = [
        ("document_role", "ENUM", "RENTAL_AGREEMENT", "RENTAL AGREEMENT"),
        ("agreement_id", "IDENTIFIER", "AG-9", "AG-9"),
        ("asset_id", "IDENTIFIER", "UNIT-31", "UNIT-31"),
        ("description", "TEXT", "lift", "description lift"),
        ("quantity", "DECIMAL", "1", "quantity 1"),
        ("start", "DATE", "2026-05-01", "2026-05-01"),
        ("end", "DATE", "2026-05-04", "2026-05-04"),
    ]
    if change == "role":
        rows[0] = ("document_role", "ENUM", "EMAIL_EVIDENCE", "RENTAL AGREEMENT")
    elif change == "missing_end":
        rows = [row for row in rows if row[0] != "end"]
    else:
        rows.append(("asset_id", "IDENTIFIER", "UNIT-32", "UNIT-32"))
    extraction = validate({"status": "SUCCESS", "limitations": [], "candidates": [
        {"entity_id": "local-document-bucket", "semantic_type": field,
         "value_type": value_type, "value": value, "raw_observed_value": quote,
         "location": location, "normalization_notes": "Exact source observation",
         "ambiguity_flags": []}
        for field, value_type, value, quote in rows]})
    reconstructed = reconstruct_runtime_structure(extraction)
    assert not any(row.semantic_type == "entity_kind" for row in reconstructed.candidates)


def test_fact_union_is_checked_as_a_whole_not_as_two_individually_complete_reads(tmp_path):
    text = ("Invoice I-1 line A net 100 currency EUR date 2026-09-01; "
            "invoice status ISSUED.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location
    base = [
        ("entity_kind", "ENUM", "INVOICE_LINE", "line A"),
        ("document_role", "ENUM", "INVOICE", "Invoice"),
        ("invoice_line_id", "IDENTIFIER", "A", "line A"),
        ("net_amount", "DECIMAL", "100", "100"),
        ("currency", "CURRENCY", "EUR", "EUR"),
    ]

    def read(rows):
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": group, "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for group, field, value_type, value, quote in rows]})

    primary_rows = [("line", *row) for row in base]
    challenger_rows = [("envelope", *row) for row in base] + [
        ("envelope", "invoice_id", "IDENTIFIER", "I-1", "I-1"),
        ("envelope", "document_status", "ENUM", "ISSUED", "invoice status ISSUED")]
    primary, challenger = read(primary_rows), read(challenger_rows)
    assert package_source_gaps(primary, for_comparison=True)
    merged = reconcile_complementary_facts(primary, challenger, batch, root)
    assert merged is not None
    assert not package_source_gaps(merged, for_comparison=True)
    qa = compare_extractions(batch, (merged,), (challenger,), root)
    assert qa["status"] == "AGREEMENT"
    assert qa["material_status"] == "MATERIAL_AGREEMENT"


def test_fact_reconciliation_refuses_conflicts_and_unanchored_complements(tmp_path):
    root, batch, primary, challenger = _anchored_fact_reads(tmp_path, challenger_amount="101")
    assert reconcile_complementary_facts(primary, challenger, batch, root) is None
    comparison = _observation_comparison(_canonical_observations(primary),
                                         _canonical_observations(challenger))
    assert comparison["material_classification"] == "CONFLICT"

    unknown_root = tmp_path / "unknown"
    unknown_root.mkdir()
    root2, batch2, _, validate = _case(unknown_root, "A label, another label.")
    parsed = read_document(batch2.documents[0], root2)
    location = parsed.units[0].location

    def read(label, quote):
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": label, "semantic_type": "description", "value_type": "TEXT",
            "value": quote, "raw_observed_value": quote, "location": location,
            "normalization_notes": "", "ambiguity_flags": []}]}
        return validate(raw)

    assert reconcile_complementary_facts(read("left", "A label"), read("right", "another label"),
                                         batch2, root2) is None


def test_agreement_scope_union_ignores_envelope_grouping_only_with_unique_source_anchors(tmp_path):
    content = ("ACCEPTED RENTAL AGREEMENT RA-9; ASSET AX-4; supplier SUP-1; client CL-2; "
               "from 2026-06-01 to 2026-06-08; quantity 1; description lift; "
               "charge RENTAL; rate EUR 12 per asset per calendar day.")
    root, batch, _, validate = _case(tmp_path, content)
    location = read_document(batch.documents[0], root).units[0].location
    observations = [
        ("document_role", "ENUM", "RENTAL_AGREEMENT", "RENTAL AGREEMENT"),
        ("document_status", "ENUM", "ACCEPTED", "ACCEPTED"),
        ("entity_kind", "ENUM", "RENTAL_SCOPE", "RENTAL AGREEMENT"),
        ("agreement_id", "IDENTIFIER", "RA-9", "RA-9"),
        ("asset_id", "IDENTIFIER", "AX-4", "AX-4"),
        ("supplier_id", "IDENTIFIER", "SUP-1", "SUP-1"),
        ("client_id", "IDENTIFIER", "CL-2", "CL-2"),
        ("start", "DATE", "2026-06-01", "2026-06-01"),
        ("end", "DATE", "2026-06-08", "2026-06-08"),
        ("quantity", "DECIMAL", "1", "quantity 1"),
        ("description", "TEXT", "lift", "lift"),
        ("charge_type", "ENUM", "RENTAL", "charge RENTAL"),
        ("rate", "DECIMAL", "12", "12"),
        ("currency", "CURRENCY", "EUR", "EUR"),
        ("billing_unit", "ENUM", "DAY", "per asset per calendar day"),
        ("quantity_basis", "ENUM", "PER_ITEM", "per asset per calendar day"),
        ("weekends_billable", "BOOLEAN", True, "per asset per calendar day"),
    ]

    def read(envelope_group, scope_group, *, omit_end=False, include_anchors=True):
        rows = []
        for field, value_type, value, quote in observations:
            if omit_end and field == "end":
                continue
            if not include_anchors and field in {"agreement_id", "asset_id"}:
                continue
            group = envelope_group if field in {"document_role", "document_status", "agreement_id"} else scope_group
            rows.append({"entity_id": group, "semantic_type": field, "value_type": value_type,
                "value": value, "raw_observed_value": quote, "location": location,
                "normalization_notes": "Source-supported classification", "ambiguity_flags": []})
        return validate({"status": "SUCCESS", "limitations": [], "candidates": rows})

    primary = read("envelope-a", "asset-fragment-a", omit_end=True)
    challenger = read("envelope-b", "scope-b")
    view_a, view_b = _canonical_observations(primary), _canonical_observations(challenger)
    assert _observation_comparison(view_a, view_b)["classification"] == "COMPLEMENTARY"
    merged = reconcile_complementary_facts(primary, challenger, batch, root)
    assert merged is not None
    assert {candidate.semantic_type for candidate in merged.candidates} >= {
        "agreement_id", "asset_id", "start", "end", "charge_type", "billing_unit", "quantity_basis"}

    # If the evidence cannot establish a unique agreement-to-asset anchor,
    # model group labels alone cannot authorize an equivalent union.
    unanchored_primary = read("envelope-c", "fragment-c", include_anchors=False)
    unanchored_challenger = read("envelope-d", "fragment-d", include_anchors=False)
    assert reconcile_complementary_facts(unanchored_primary, unanchored_challenger,
                                        batch, root) is None


def test_source_status_conflict_is_not_hidden_by_fact_union(tmp_path):
    text = ("Invoice I-1, line A, net 100, currency EUR, date 2026-09-01; "
            "document status ACCEPTED; document status ISSUED.")
    root, batch, _, validate = _case(tmp_path, text)
    location = read_document(batch.documents[0], root).units[0].location

    def read(status):
        rows = [
            ("entity_kind", "ENUM", "INVOICE_LINE", "line A"),
            ("invoice_id", "IDENTIFIER", "I-1", "I-1"),
            ("invoice_line_id", "IDENTIFIER", "A", "line A"),
            ("net_amount", "DECIMAL", "100", "100"),
            ("currency", "CURRENCY", "EUR", "EUR"),
            ("date", "DATE", "2026-09-01", "2026-09-01"),
            ("document_status", "ENUM", status, f"document status {status}"),
        ]
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": "arbitrary-model-group", "semantic_type": field,
             "value_type": value_type, "value": value, "raw_observed_value": quote,
             "location": location, "normalization_notes": "Exact source evidence",
             "ambiguity_flags": []} for field, value_type, value, quote in rows]})

    primary, challenger = read("ACCEPTED"), read("ISSUED")
    comparison = _observation_comparison(_canonical_observations(primary),
                                        _canonical_observations(challenger))
    assert comparison["material_classification"] == "CONFLICT"
    assert comparison["conflicting_fields"] == [{"scope": "SOURCE_METADATA", "anchor": None,
                                                    "semantic_type": "document_status"}]
    assert reconcile_complementary_facts(primary, challenger, batch, root) is None


def test_complete_source_bound_superset_auto_resolves_partial_read_without_model(tmp_path, monkeypatch):
    from againward.documents.adjudication import adjudicate_with_codex
    from againward.documents.extraction import replay_extraction
    from againward.documents.readers import read_document

    root, batch, _, validate = _case(tmp_path,
        "INVOICE I-9, document marked ISSUED; status ISSUED, line L7, net EUR 100.00.")
    source = batch.documents[0]
    location = read_document(source, root).units[0].location

    def read(label, *, complete):
        rows = [("document_role", "ENUM", "INVOICE", "INVOICE"),
                ("document_status", "ENUM", "ISSUED", "document marked ISSUED"),
                ("entity_kind", "ENUM", "INVOICE_LINE", "line L7"),
                ("invoice_id", "IDENTIFIER", "I-9", "I-9"),
                ("invoice_line_id", "IDENTIFIER", "L7", "line L7")]
        if complete:
            # A redundant same-value observation with a different exact quote
            # is corroboration, not a second meaning or a reason to STOP.
            rows.append(("document_status", "ENUM", "ISSUED", "status ISSUED"))
        if complete:
            rows.extend([("currency", "CURRENCY", "EUR", "EUR"),
                         ("net_amount", "DECIMAL", "100.00", "100.00")])
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": value_type,
             "value": value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for field, value_type, value, quote in rows]})

    primary, challenger = read("primary-group", complete=True), read("other-group", complete=False)
    qa = compare_extractions(batch, (primary,), (challenger,), root)
    assert qa["source_results"][0]["pre_qa_observation_comparison"]["material_classification"] == "COMPLEMENTARY"
    dominant = complete_fact_superset(primary, challenger, batch, root)
    assert dominant is not None and dominant[1] == "PRIMARY"

    def forbidden_provider(*args, **kwargs):
        raise AssertionError("a complete exact-evidence superset must not need another model choice")

    from againward.documents import codex_provider
    monkeypatch.setattr(codex_provider, "CodexCliProvider", forbidden_provider)
    result = adjudicate_with_codex(batch, (primary,), (challenger,), qa, root,
        model="gpt-6-luna", required_source_facts=None)
    assert result["resolution_method"] == "DETERMINISTIC_COMPLETE_FACT_SUPERSET"
    assert result["selected_extractions"][source.source_id] == primary.to_dict()["extraction_sha256"]
    assert result["material_unresolved_source_ids"] == []
    assert result["facts_approved"] == 0
    assert result["delivery_approved"] is False
    assert result["decisions"][0]["citations"][0]["source_span"]
    selected = replay_extraction(primary.to_dict(), batch, root)
    assert sum(row.semantic_type == "document_status" for row in selected.candidates) == 2


@pytest.mark.parametrize("variant", ["conflict", "unanchored", "both_incomplete"])
def test_complete_superset_requires_unique_nonconflicting_scope_and_complete_candidate(tmp_path, variant):
    content = ("INVOICE I-9, ISSUED, line L7, net EUR 100.00 or EUR 90.00."
               if variant == "conflict" else "INVOICE I-9, ISSUED, line L7, net EUR 100.00.")
    root, batch, _, validate = _case(tmp_path, content)
    location = read_document(batch.documents[0], root).units[0].location

    def read(label, value, *, complete, anchor=True):
        rows = [("document_role", "ENUM", "INVOICE", "INVOICE"),
                ("document_status", "ENUM", "ISSUED", "ISSUED"),
                ("entity_kind", "ENUM", "INVOICE_LINE", "line L7"),
                ("invoice_id", "IDENTIFIER", "I-9", "I-9")]
        if anchor:
            rows.append(("invoice_line_id", "IDENTIFIER", "L7", "line L7"))
        if complete:
            rows.extend([("currency", "CURRENCY", "EUR",
                          "net EUR" if variant == "conflict" else "EUR"),
                         ("net_amount", "DECIMAL", value, value)])
        return validate({"status": "SUCCESS", "limitations": [], "candidates": [
            {"entity_id": label, "semantic_type": field, "value_type": value_type,
             "value": field_value, "raw_observed_value": quote, "location": location,
             "normalization_notes": "Exact source observation", "ambiguity_flags": []}
            for field, value_type, field_value, quote in rows]})

    if variant == "conflict":
        first, second = read("p", "100.00", complete=True), read("q", "90.00", complete=True)
    elif variant == "unanchored":
        first, second = read("p", "100.00", complete=True, anchor=False), read("q", "100.00", complete=False, anchor=False)
    else:
        first, second = read("p", "100.00", complete=False), read("q", "100.00", complete=False)
    assert complete_fact_superset(first, second, batch, root) is None


def test_independent_qa_requires_complete_current_source_set(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        compare_extractions(batch, (first,), (), root)
    source = root / batch.documents[0].blob_path
    source.write_text("tampered")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        compare_extractions(batch, (first,), (first,), root)


def test_challenger_retries_one_invalid_quote_without_weaker_validator(tmp_path, monkeypatch):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    parsed = read_document(batch.documents[0], root)
    attempts = []

    class FakeProvider:
        def __init__(self, *_args, **_kwargs):
            pass

        def propose(self, document, _parsed, context):
            attempts.append(context["semantic_guidance"])
            if len(attempts) == 1:
                raise DocumentError("SOURCE_LOCATION_INVALID", "Model quote not unique")
            return assemble_proposal(raw, document, parsed, batch.batch_id, "synthetic-model")

    monkeypatch.setattr("againward.documents.independent_qa.CodexCliProvider", FakeProvider)
    body, paths = reread_sources(batch, (first,), root, model="synthetic-model")
    assert body["status"] == "AGREEMENT"
    assert body["challenger_model_calls"] == 2
    assert "prior response failed" in attempts[1]
    assert len(paths) == 1 and paths[0].is_file()


def test_saved_challenger_can_be_recompared_without_model_call(tmp_path, capsys, monkeypatch):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    omitted = deepcopy(raw)
    omitted["candidates"].pop()
    second = validate(omitted)
    batch_path = root / "batch.json"
    first_path = root / "first.json"
    second_path = root / "second.json"
    batch_path.write_text(json.dumps(batch.to_dict()))
    first_path.write_text(json.dumps(first.to_dict()))
    second_path.write_text(json.dumps(second.to_dict()))
    monkeypatch.setattr("againward.documents.codex_provider.subprocess.run",
                        lambda *_args, **_kwargs: pytest.fail("No model call allowed"))
    assert main(["compare-independent-qa", str(root), str(batch_path), str(first_path),
                 "--challenger-extractions", str(second_path)]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["status"] == "RECONCILIATION_REQUIRED"
    body = json.loads((root / "independent_qa" / receipt["qa_artifact"].split("/")[-1]).read_text())
    assert body["source_results"][0]["primary_only_entities"]


def test_value_type_disagreement_is_advisory_when_material_value_agrees(tmp_path):
    root, batch, raw, validate = _case(tmp_path)
    first = validate(raw)
    variant = deepcopy(raw)
    variant["candidates"][0]["value_type"] = "TEXT"
    second = validate(variant)
    body = compare_extractions(batch, (first,), (second,), root)
    assert body["status"] == "AGREEMENT"
    assert body["material_status"] == "MATERIAL_AGREEMENT"
    assert body["source_results"][0]["material_needs_reconciliation"] is False


def test_numeric_representation_and_description_label_are_advisory_but_money_is_material():
    def fact(field, value, *, material=True):
        return {"source_id": "source", "source_sha256": "a" * 64,
                "scope": "MATERIAL_ENTITY", "anchor": "line-1",
                "semantic_type": field, "value_type": "DECIMAL", "value": value,
                "material": material}

    invoice_int = [fact("net_amount", "270"), fact("billed_units", "9")]
    invoice_decimal = [fact("net_amount", "270"), fact("billed_units", "9")]
    comparison = _observation_comparison(invoice_int, invoice_decimal)
    assert comparison["classification"] == "PRESENTATION_EQUIVALENT"
    assert comparison["material_classification"] == "PRESENTATION_EQUIVALENT"
    changed_money = [fact("net_amount", "271"), fact("billed_units", "9")]
    assert _observation_comparison(invoice_int, changed_money)["material_classification"] == "CONFLICT"
    described = [fact("description", "electric platform", material=False)]
    categorized = [fact("category", "electric platform", material=False)]
    comparison = _observation_comparison(described, categorized)
    assert comparison["material_classification"] == "PRESENTATION_EQUIVALENT"
    assert comparison["classification"] == "COMPLEMENTARY"


def test_unanchored_value_difference_stays_unknown_and_needs_reconciliation():
    def fact(value, scope="MATERIAL_ENTITY"):
        return {"source_id": "source", "source_sha256": "a" * 64,
                "scope": scope, "anchor": None, "semantic_type": "rate",
                "value_type": "DECIMAL", "value": value, "material": True}

    comparison = _observation_comparison([fact("100")], [fact("200")])
    assert comparison["classification"] == "UNKNOWN"
    assert comparison["material_classification"] == "UNKNOWN"
    assert comparison["conflicting_fields"] == []
    assert comparison["unknown_fields"] == [{"scope": "MATERIAL_ENTITY", "anchor": None,
                                               "semantic_type": "rate"}]

    authority_conflict = _observation_comparison(
        [fact("ACCEPTED", "SOURCE_METADATA")], [fact("PROPOSED", "SOURCE_METADATA")])
    assert authority_conflict["classification"] == "CONFLICT"
