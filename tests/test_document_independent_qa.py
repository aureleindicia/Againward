"""Independent QA must find omissions and swapped entity fields, not bless a pass."""
from __future__ import annotations

from copy import deepcopy
import json

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.cli import main
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal
from againward.documents.independent_qa import (_canonical_observations,
    _observation_comparison, compare_extractions, reread_sources)
from againward.documents.reconciliation import FACT_RECONCILIATION_VERSION, reconcile_complementary_facts
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.domains.rental.extraction_validation import package_source_gaps


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
