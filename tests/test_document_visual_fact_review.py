"""Scripted protocol checks only; no test attestation is a real human review."""
from __future__ import annotations

from copy import deepcopy

import pytest

from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.core.artifact_store import write_json
from againward.documents.adjudication import validate_adjudication
from againward.documents.contracts import DocumentError
from againward.documents.extraction import promote_facts, validate_proposal
from againward.documents.independent_qa import compare_extractions
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.visual_fact_review import attest_visual_facts, record_model_visual_review
from againward.evidence.hashing import stable_hash
from benchmarking.document_renderers import pdf


def _packet(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    pdf(public / "return.pdf", ["Signed return: one LIFT-5 unit on 2026-09-05."], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    raw = {"status": "NEEDS_REVIEW", "limitations": [], "candidates": [{
        "entity_id": "return-1", "semantic_type": "date", "value_type": "DATE",
        "value": "2026-09-05", "raw_observed_value": "2026-09-05",
        "location": parsed.units[0].location, "normalization_notes": "Exact printed date",
        "ambiguity_flags": [],
    }]}
    prompt_version = prompt_version_for_guidance("")
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
        "synthetic-model", prompt_version=prompt_version,
        visual_bindings=bind_visual_pages(document, parsed, root, model="synthetic-model",
            prompt_version=prompt_version, invocation_id="fixture-visual"),
        invocation_id="fixture-visual"), batch, root)
    candidate = extraction.candidates[0]
    review = {"schema_version": "againward-fact-review-v1",
              "extraction_hashes": [extraction.to_dict()["extraction_sha256"]],
              "reviewer_role": "ANALYST", "reviewed_at": "2026-09-23T12:00:00Z",
              "limitations_acknowledged": True, "decisions": [{
                  "candidate_id": candidate.candidate_id, "decision": "ACCEPT",
                  "reason": "Synthetic analyst candidate pending separate visual inspection",
                  "resolved_flags": list(candidate.ambiguity_flags)}]}
    return root, batch, extraction, review


def test_mixed_review_requires_exact_human_visual_attestation(tmp_path):
    root, batch, extraction, review = _packet(tmp_path)
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        promote_facts((extraction,), review, batch, root)
    legacy_claim = deepcopy(review)
    legacy_claim["reviewer_role"] = "HUMAN"
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        promote_facts((extraction,), legacy_claim, batch, root)
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        attest_visual_facts(batch, (extraction,), review, root, actor_id="test_operator",
                            ask=lambda _: "CONFIRM", interactive=False)

    prompts = []

    def scripted_fixture(prompt):
        prompts.append(prompt)
        if prompt.startswith("Open the preview"):
            return "INSPECTED " + batch.documents[0].sha256[:12]
        if prompt.startswith("Confirm ALL"):
            return "CONFIRM " + prompt.split("CONFIRM ")[1].split(":")[0]
        raise AssertionError(prompt)

    attested = attest_visual_facts(batch, (extraction,), review, root,
                                   actor_id="test_operator", ask=scripted_fixture,
                                   interactive=True)
    assert len(prompts) == 2
    assert attested["reviewer_role"] == "ANALYST"
    assert attested["visual_attestations"][0]["reviewer_role"] == "HUMAN"
    assert len(promote_facts((extraction,), attested, batch, root)) == 1
    assert "visual_attestations" not in review

    stale = deepcopy(attested)
    stale["visual_attestations"][0]["preview_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        promote_facts((extraction,), stale, batch, root)
    stale = deepcopy(attested)
    stale["visual_attestations"][0]["candidate_hashes"] = []
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        promote_facts((extraction,), stale, batch, root)
    stale = deepcopy(attested)
    stale["decisions"][0]["decision"] = "DEFER"
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        promote_facts((extraction,), stale, batch, root)


def test_clear_visual_fact_can_use_model_receipt_without_becoming_human(tmp_path):
    root, batch, extraction, review = _packet(tmp_path)
    visual_review = deepcopy(review)
    visual_review["decisions"][0]["resolved_flags"] = []
    visual = {"batch_id": batch.batch_id, "review": visual_review,
              "status": "WAITING_FOR_VISUAL_ATTESTATION", "model": "scripted-model"}
    visual["receipt_sha256"] = stable_hash(visual)
    write_json(root / "analyst_reviews" / (visual["receipt_sha256"] + ".json"), visual)
    qa = compare_extractions(batch, (extraction,), (extraction,), root)
    write_json(root / "independent_qa" / (qa["qa_sha256"] + ".json"), qa)
    adjudication = validate_adjudication(batch, (extraction,), (extraction,), qa,
                                        {"decisions": []}, root)
    write_json(root / "adjudications" / (adjudication["adjudication_sha256"] + ".json"), adjudication)
    model_review = record_model_visual_review(batch, (extraction,), visual, qa, adjudication,
                                              root, model="scripted-model")
    assert model_review["reviewer_role"] == "ANALYST"
    assert model_review["visual_model_reviews"][0]["reviewer_role"] == "MODEL"
    assert "visual_attestations" not in model_review
    assert len(promote_facts((extraction,), model_review, batch, root)) == 1
    stale = deepcopy(model_review)
    stale["visual_model_reviews"][0]["preview_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        promote_facts((extraction,), stale, batch, root)
    stale = deepcopy(model_review)
    stale["visual_model_reviews"][0]["qa_sha256"] = "0" * 64
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        promote_facts((extraction,), stale, batch, root)
    (root / batch.documents[0].blob_path).write_bytes(b"changed")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        promote_facts((extraction,), model_review, batch, root)
