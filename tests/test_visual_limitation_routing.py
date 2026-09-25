"""Visual-only extraction limits must reach bound pixel review, not fact promotion."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import pytest

from againward.core.artifact_store import write_json
from againward.documents.adjudication import validate_adjudication, verify_adjudication_pixels
from againward.documents.analyst_review import build_analyst_review
from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import validate_proposal, visual_only_limited_extraction
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
        visual_doc, visual_source, batch.batch_id, "scripted-model"), batch, root)
    visual_challenger = validate_proposal(assemble_proposal({
        "status": "PARTIAL", "limitations": [CHALLENGER_LIMIT], "candidates": []},
        visual_doc, visual_source, batch.batch_id, "scripted-model"), batch, root)
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
