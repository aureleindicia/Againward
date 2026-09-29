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
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources


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
