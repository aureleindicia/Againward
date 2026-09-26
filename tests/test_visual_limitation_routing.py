"""Visual-only extraction limits must reach bound pixel review, not fact promotion."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from againward.core.artifact_store import write_json
from againward.documents.adjudication import validate_adjudication, verify_adjudication_pixels
from againward.documents.analyst_review import build_analyst_review
from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.documents.contracts import DocumentError
from againward.documents.extraction import (append_adjudicator_visual_observations,
    promote_facts, validate_proposal, visual_only_limited_extraction)
from againward.documents.independent_qa import compare_extractions
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.visual_fact_review import _render_hash, record_model_visual_review
from againward.evidence.hashing import stable_hash
from benchmarking.document_renderers import pdf


PRIMARY_LIMIT = (
    "The invoice details are visible in the image but absent from native text; "
    "visual transcriptions require pixel verification."
)
CHALLENGER_LIMIT = (
    "The visible image details are omitted from native text and cannot be cited "
    "with an exact native substring."
)


def _case(tmp_path: Path):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "billing.pdf", ["Invoice attachment follows"], scan=True)
    (public / "agreement.txt").write_text("Accepted agreement is available.", encoding="utf-8")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    visual_doc = next(doc for doc in batch.documents if "billing.pdf" in doc.original_names)
    native_doc = next(doc for doc in batch.documents if "agreement.txt" in doc.original_names)
    visual_source = read_document(visual_doc, root)
    native_source = read_document(native_doc, root)
    visual_location = next(unit.location for unit in visual_source.units if unit.route != "NATIVE")

    rows = [
        ("entity_kind", "ENUM", "INVOICE_LINE", "Line 1 - Rental agreement AG-1"),
        ("document_role", "ENUM", "INVOICE", "ACCEPTED INVOICE"),
        ("document_status", "ENUM", "ISSUED", "ACCEPTED INVOICE"),
        ("net_amount", "DECIMAL", "150.00", "EUR 150.00"),
    ]
    visual_primary = validate_proposal(assemble_proposal({
        "status": "NEEDS_REVIEW", "limitations": [PRIMARY_LIMIT],
        "candidates": [{"entity_id": "line-1", "semantic_type": kind,
                        "value_type": value_type, "value": value,
                        "raw_observed_value": observed, "location": visual_location,
                        "normalization_notes": "Visual reading awaiting pixel review.",
                        "ambiguity_flags": []}
                       for kind, value_type, value, observed in rows]},
        visual_doc, visual_source, batch.batch_id, "scripted-model",
        prompt_version=prompt_version_for_guidance(""),
        visual_bindings=bind_visual_pages(visual_doc, visual_source, root, model="scripted-model",
            prompt_version=prompt_version_for_guidance(""), invocation_id="fixture-primary"),
        invocation_id="fixture-primary"), batch, root)
    visual_challenger = validate_proposal(assemble_proposal({
        "status": "PARTIAL", "limitations": [CHALLENGER_LIMIT], "candidates": []},
        visual_doc, visual_source, batch.batch_id, "scripted-model",
        prompt_version=prompt_version_for_guidance(""),
        visual_bindings=bind_visual_pages(visual_doc, visual_source, root, model="scripted-model",
            prompt_version=prompt_version_for_guidance(""), invocation_id="fixture-challenger"),
        invocation_id="fixture-challenger"), batch, root)
    native = validate_proposal(assemble_proposal({
        "status": "SUCCESS", "limitations": [], "candidates": []},
        native_doc, native_source, batch.batch_id, "scripted-model"), batch, root)
    primary = (visual_primary, native)
    challenger = (visual_challenger, native)
    qa = compare_extractions(batch, primary, challenger, root)
    preview_dir = tmp_path / "preview"
    preview_dir.mkdir()
    preview, _, _ = _render_hash(visual_doc, root, visual_location, preview_dir)
    decision = {"source_id": visual_doc.source_id, "selection": "PRIMARY",
                "rationale": "Original pixels support the visual candidate values.",
                "citations": [{"source_id": visual_doc.source_id,
                               "location": visual_location,
                               "quote": rows[-1][3], "preview_sha256": preview}]}
    return root, batch, visual_doc, primary, challenger, qa, {"decisions": [decision]}


def _pixel_adjudication(tmp_path: Path):
    root, batch, visual_doc, primary, challenger, qa, raw = _case(tmp_path)
    result = validate_adjudication(batch, primary, challenger, qa, raw, root)
    return root, batch, visual_doc, primary, challenger, qa, result


def test_visual_only_disagreement_routes_to_original_pixel_adjudication(tmp_path):
    root, batch, visual_doc, primary, challenger, qa, raw = _case(tmp_path)
    selected = next(item for item in primary if item.source_id == visual_doc.source_id)
    assert visual_only_limited_extraction(selected, batch, root)
    visual_qa = next(row for row in qa["source_results"] if row["source_id"] == visual_doc.source_id)
    assert visual_qa["material_needs_reconciliation"]
    result = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert result["status"] == "RESOLVED_FOR_FACT_REVIEW"
    assert result["material_unresolved_source_ids"] == []
    assert result["selected_extractions"][visual_doc.source_id] == selected.to_dict()["extraction_sha256"]
    assert result["decisions"][0]["citations"][0]["verification_method"] == "MULTIMODAL_ORIGINAL_PIXELS"
    assert result["facts_approved"] == 0 and result["delivery_approved"] is False


def test_resolved_pixels_can_continue_to_visual_review_as_model_evidence(tmp_path):
    root, batch, visual_doc, primary, challenger, qa, adjudication = _pixel_adjudication(tmp_path)
    selected = tuple(next(item for item in (*primary, *challenger)
                          if item.source_id == doc.source_id and
                          item.to_dict()["extraction_sha256"] == adjudication["selected_extractions"][doc.source_id])
                     for doc in batch.documents)
    native = build_analyst_review(batch, selected, {}, root)
    assert native["status"] == "WAITING_FOR_VISUAL_REVIEW"
    visual_review = deepcopy(native["review"])
    for row in visual_review["decisions"]:
        if row["candidate_id"] in {c.candidate_id for e in selected for c in e.candidates}:
            row.update(decision="ACCEPT", reason="Scripted regression pixel decision.")
    visual = {"batch_id": batch.batch_id, "review": visual_review,
              "status": "WAITING_FOR_VISUAL_ATTESTATION", "model": "scripted-model"}
    visual["receipt_sha256"] = stable_hash(visual)
    write_json(root / "analyst_reviews" / (visual["receipt_sha256"] + ".json"), visual)
    write_json(root / "independent_qa" / (qa["qa_sha256"] + ".json"), qa)
    write_json(root / "adjudications" /
               (adjudication["adjudication_sha256"] + ".json"), adjudication)
    model_review = record_model_visual_review(batch, selected, visual, qa, adjudication,
                                              root, model="scripted-model")
    assert model_review["reviewer_role"] == "ANALYST"
    assert {row["reviewer_role"] for row in model_review["visual_model_reviews"]} == {"MODEL"}
    assert all(row["source_sha256"] == visual_doc.sha256
               for row in model_review["visual_model_reviews"])
    assert "visual_attestations" not in model_review


def test_challenger_only_visual_observation_can_be_selected_for_pixel_review(tmp_path):
    root, batch, visual_doc, primary, challenger, qa, raw = _case(tmp_path)
    swapped_primary, swapped_challenger = challenger, primary
    qa = compare_extractions(batch, swapped_primary, swapped_challenger, root)
    raw["decisions"][0]["selection"] = "CHALLENGER"
    result = validate_adjudication(batch, swapped_primary, swapped_challenger, qa, raw, root)
    expected = next(item for item in swapped_challenger if item.source_id == visual_doc.source_id)
    assert result["selected_extractions"][visual_doc.source_id] == expected.to_dict()["extraction_sha256"]
    selected = tuple(next(item for item in (*swapped_primary, *swapped_challenger)
                          if item.source_id == doc.source_id
                          and item.to_dict()["extraction_sha256"] == result["selected_extractions"][doc.source_id])
                     for doc in batch.documents)
    review = build_analyst_review(batch, selected, {}, root)
    assert review["visual_candidates_deferred"] > 0


def test_ambiguous_pixels_keep_existing_human_review_fallback(tmp_path):
    root, batch, _visual_doc, primary, challenger, qa, adjudication = _pixel_adjudication(tmp_path)
    selected = tuple(next(item for item in (*primary, *challenger)
                          if item.source_id == doc.source_id and
                          item.to_dict()["extraction_sha256"] == adjudication["selected_extractions"][doc.source_id])
                     for doc in batch.documents)
    native = build_analyst_review(batch, selected, {}, root)
    visual_review = deepcopy(native["review"])
    visual_review["decisions"][0].update(decision="DEFER", reason="Pixels remain materially ambiguous.")
    visual = {"batch_id": batch.batch_id, "review": visual_review,
              "status": "WAITING_FOR_VISUAL_ATTESTATION", "model": "scripted-model"}
    visual["receipt_sha256"] = stable_hash(visual)
    qa_path = root / "independent_qa" / (qa["qa_sha256"] + ".json")
    adjudication_path = root / "adjudications" / (adjudication["adjudication_sha256"] + ".json")
    write_json(qa_path, qa)
    write_json(adjudication_path, adjudication)
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        record_model_visual_review(batch, selected, visual, qa, adjudication,
                                  root, model="scripted-model")


def test_missing_pixel_binding_and_source_render_mutation_fail_closed(tmp_path, monkeypatch):
    root, batch, _visual_doc, primary, challenger, qa, raw = _case(tmp_path)
    missing = deepcopy(raw)
    missing["decisions"][0]["citations"][0].pop("preview_sha256")
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        validate_adjudication(batch, primary, challenger, qa, missing, root)
    result = validate_adjudication(batch, primary, challenger, qa, raw, root)
    verify_adjudication_pixels(batch, result, root)
    monkeypatch.setattr("againward.documents.visual_fact_review._render_hash",
                        lambda *args: ("0" * 64, None, "0" * 64))
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        verify_adjudication_pixels(batch, result, root)
    monkeypatch.undo()
    visual_doc = next(doc for doc in batch.documents if "billing.pdf" in doc.original_names)
    (root / visual_doc.blob_path).write_bytes(b"changed original source")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        verify_adjudication_pixels(batch, result, root)


def test_nonvisual_extraction_limit_remains_a_hard_stop(tmp_path):
    root, batch, visual_doc, primary, challenger, _qa, raw = _case(tmp_path)
    invoice = next(item for item in primary if item.source_id == visual_doc.source_id)
    invoice = replace(invoice, limitations=("A required source page is missing.",))
    assert not visual_only_limited_extraction(invoice, batch, root)
    primary = tuple(invoice if item.source_id == visual_doc.source_id else item for item in primary)
    qa = compare_extractions(batch, primary, challenger, root)
    with pytest.raises(DocumentError, match="non-visual-limited proposal"):
        validate_adjudication(batch, primary, challenger, qa, raw, root)


def test_page_scoped_visual_field_absence_is_retained_for_pixel_review(tmp_path):
    root, batch, visual_doc, primary, _challenger, _qa, _raw = _case(tmp_path)
    invoice = next(item for item in primary if item.source_id == visual_doc.source_id)
    limitation = "Page 1 states the line quantity and net amount but does not show a separate invoice total."
    invoice = replace(invoice, limitations=(limitation,))

    assert visual_only_limited_extraction(invoice, batch, root)
    selected = tuple(invoice if item.source_id == visual_doc.source_id else item for item in primary)
    review = build_analyst_review(batch, selected, {}, root)
    assert review["visual_candidates_deferred"] == len(invoice.candidates)
    assert review["native_facts_accepted"] == 0
    assert limitation in invoice.limitations


def test_page_scoped_limit_does_not_mask_missing_source_pages(tmp_path):
    root, batch, visual_doc, primary, _challenger, _qa, _raw = _case(tmp_path)
    invoice = next(item for item in primary if item.source_id == visual_doc.source_id)
    invoice = replace(invoice, limitations=("Only page 1 was provided; the return date is unreadable.",))
    assert not visual_only_limited_extraction(invoice, batch, root)


def test_adjudicator_duplicate_structural_observations_keep_the_existing_entity_binding(tmp_path):
    root, batch, visual_doc, primary, _challenger, _qa, _raw = _case(tmp_path)
    extraction = next(item for item in primary if item.source_id == visual_doc.source_id)
    binding = extraction.visual_bindings[0]
    unit = next(unit for unit in read_document(visual_doc, root).units if unit.location == binding["location"])
    existing = {(candidate.semantic_type, candidate.raw_observed_value): candidate.entity_id
                for candidate in extraction.candidates}
    observations = [
        {"source_id": visual_doc.source_id, "source_sha256": visual_doc.sha256,
         "location": binding["location"], "unit_sha256": unit.unit_sha256,
         "render_sha256": binding["render_sha256"], "origin": "ADJUDICATOR_PIXEL_OBSERVATION",
         "semantic_type": semantic, "value_type": value_type, "value": value,
         "visible_text": quote, "ambiguity": [], "entity_hint": hint}
        for semantic, value_type, value, quote, hint in (
            ("entity_kind", "ENUM", "INVOICE_LINE", "Line 1 - Rental agreement AG-1", "invoice-line"),
            ("document_status", "ENUM", "ACCEPTED", "ACCEPTED INVOICE", "invoice-header"),
        )]
    augmented = append_adjudicator_visual_observations(
        extraction, observations, batch, root, "a" * 64)
    pixel_rows = [candidate for candidate in augmented.candidates
                  if "ADJUDICATOR_PIXEL_OBSERVATION" in candidate.ambiguity_flags]
    assert len(pixel_rows) == 2
    for candidate in pixel_rows:
        assert candidate.entity_id == existing[(candidate.semantic_type, candidate.raw_observed_value)]
        assert "ADJUDICATOR_PIXEL_OBSERVATION" in candidate.ambiguity_flags


def test_direct_visual_absence_claim_conflict_fails_before_fact_review(tmp_path):
    root, batch, visual_doc, primary, _challenger, _qa, _raw = _case(tmp_path)
    invoice = next(item for item in primary if item.source_id == visual_doc.source_id)
    contradictory = replace(invoice, limitations=("No net amount is visible on page 1.",))
    with pytest.raises(DocumentError, match="EXTRACTION_CONTRADICTION"):
        visual_only_limited_extraction(contradictory, batch, root)


def test_pixel_adjudicator_recovers_new_unapproved_observation_after_both_readers_miss(tmp_path):
    root, batch, visual_doc, _primary, _challenger, _qa, _raw = _case(tmp_path)
    visual_source = read_document(visual_doc, root)
    prompt_version = "scripted-prompt-version"

    def empty_pass(status: str, limitation: str, invocation_id: str):
        proposal = assemble_proposal({"status": status, "limitations": [limitation], "candidates": []},
            visual_doc, visual_source, batch.batch_id, "scripted-model", prompt_version=prompt_version,
            visual_bindings=bind_visual_pages(visual_doc, visual_source, root, model="scripted-model",
                prompt_version=prompt_version, invocation_id=invocation_id), invocation_id=invocation_id)
        return validate_proposal(proposal, batch, root)

    primary_visual = empty_pass("PARTIAL", PRIMARY_LIMIT, "miss-primary")
    challenger_visual = empty_pass("NEEDS_REVIEW", CHALLENGER_LIMIT, "miss-challenger")
    native_doc = next(doc for doc in batch.documents if doc.source_id != visual_doc.source_id)
    native_source = read_document(native_doc, root)
    native = validate_proposal(assemble_proposal({"status": "SUCCESS", "limitations": [],
        "candidates": []}, native_doc, native_source, batch.batch_id, "scripted-model"), batch, root)
    primary, challenger = (primary_visual, native), (challenger_visual, native)
    qa = compare_extractions(batch, primary, challenger, root)
    with __import__("tempfile").TemporaryDirectory() as directory:
        preview, _, _ = _render_hash(visual_doc, root, "page:1", Path(directory))
    raw = {"decisions": [{"source_id": visual_doc.source_id, "selection": "PRIMARY",
        "rationale": "Both readers omitted the visible total; adjudicator observed it on original pixels.",
        "citations": [{"source_id": visual_doc.source_id, "location": "page:1",
                       "quote": "EUR 150.00", "preview_sha256": preview}],
        "observations": [{"semantic_type": "net_amount", "value_type": "DECIMAL",
            "value": "150.00", "visible_text": "EUR 150.00", "page": 1,
            "ambiguity": [], "entity_hint": "invoice total"}]}]}
    adjudication = validate_adjudication(batch, primary, challenger, qa, raw, root)
    assert adjudication["status"] == "RESOLVED_FOR_FACT_REVIEW"
    observation = adjudication["decisions"][0]["pixel_observations"][0]
    assert observation["origin"] == "ADJUDICATOR_PIXEL_OBSERVATION"
    observation["adjudicator_model"] = "scripted-model"
    observation["adjudication_version"] = adjudication["schema_version"]
    augmented = append_adjudicator_visual_observations(primary_visual, [observation], batch, root,
                                                        adjudication["adjudication_sha256"])
    candidate = next(c for c in augmented.candidates
                     if "ADJUDICATOR_PIXEL_OBSERVATION" in c.ambiguity_flags)
    assert candidate.value == "150.00" and candidate.source_span is None
    review = build_analyst_review(batch, (augmented, native), {}, root)
    decision = next(row for row in review["review"]["decisions"]
                    if row["candidate_id"] == candidate.candidate_id)
    assert decision["decision"] == "DEFER"
    forced = deepcopy(review["review"])
    next(row for row in forced["decisions"] if row["candidate_id"] == candidate.candidate_id).update(
        decision="ACCEPT", resolved_flags=list(candidate.ambiguity_flags))
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        promote_facts((augmented, native), forced, batch, root)
