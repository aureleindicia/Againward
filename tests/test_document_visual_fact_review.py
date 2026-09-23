"""Scripted protocol checks only; no test attestation is a real human review."""
from __future__ import annotations

from copy import deepcopy

import pytest

from againward.documents.codex_provider import assemble_proposal
from againward.documents.contracts import DocumentError
from againward.documents.extraction import promote_facts, validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.visual_fact_review import attest_visual_facts
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
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
                                                     "synthetic-model"), batch, root)
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
