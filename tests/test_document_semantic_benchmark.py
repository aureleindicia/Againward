"""Participant and scorer boundaries are separate from fake human review."""
from hashlib import sha256
import json

import pytest

from againward.documents.codex_provider import assemble_proposal
from benchmarking.semantic_participant import run_semantic_participant
from benchmarking.semantic_scoring import score_semantic_candidates
from benchmarking.semantic_preflight import audit_semantic_preflight


def test_participant_is_real_source_bound_but_never_approves(tmp_path, monkeypatch):
    public = tmp_path / "corpus/public"
    public.mkdir(parents=True)
    case = public / "case-a"
    case.mkdir()
    (case / "invoice.txt").write_text("Invoice INV-9: net EUR 850.00.")
    calls = []

    def model(self, document, parsed, context):
        calls.append((document.source_id, parsed.units[0].text, context["semantic_guidance"]))
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": "line-1", "semantic_type": "net_amount", "value_type": "DECIMAL",
            "value": "850.00", "raw_observed_value": "850.00", "location": parsed.units[0].location,
            "normalization_notes": "", "ambiguity_flags": [],
        }]}
        return assemble_proposal(raw, document, parsed, context["batch"].batch_id, self.model)

    monkeypatch.setattr("benchmarking.semantic_participant.CodexCliProvider.propose", model)
    result = run_semantic_participant(public, tmp_path / "run", split="DEV", model="gpt-6-sol")
    assert len(calls) == 1 and "850.00" in calls[0][1]
    assert result["cases"]["case-a"]["approved_facts"] == 0
    assert result["cases"]["case-a"]["client_facing_financial_claims"] == 0
    assert result["cases"]["case-a"]["documents"][0]["candidates"][0]["value"] == "850.00"
    with pytest.raises(ValueError, match="empty"):
        run_semantic_participant(public, tmp_path / "run", split="DEV", model="gpt-6-sol")


def test_private_semantic_scorer_uses_frozen_observations_and_null_financial_metrics(tmp_path):
    corpus, run = tmp_path / "corpus", tmp_path / "run"
    (corpus / "private").mkdir(parents=True)
    run.mkdir()
    truth = {"split": "DEV", "cases": {"case-a": {
        "source_hashes": {"invoice.txt": "a" * 64},
        "decisive_fields": [{"source_sha256": "a" * 64, "field": "rate", "value": "50.00"}],
    }}}
    raw_truth = json.dumps(truth).encode()
    (corpus / "private/truth.json").write_bytes(raw_truth)
    (corpus / "manifest.json").write_text(json.dumps({"truth_sha256": sha256(raw_truth).hexdigest()}))
    observation = {"split": "DEV", "participant": "CODEX_CLI_REAL_SOURCE_UNITS", "cases": {"case-a": {
        "source_hashes": ["a" * 64], "documents": [{"source_sha256": "a" * 64,
            "status": "SUCCESS", "failure_code": None,
            "candidates": [{"source_id": "src-" + "a" * 64,
                            "entity_id": "line-1", "ambiguity_flags": [],
                            "semantic_type": "rate", "value": "50.0"}]}],
    }}}
    raw_obs = json.dumps(observation).encode()
    (run / "semantic_observations.json").write_bytes(raw_obs)
    (run / "semantic_observations.sha256").write_text(sha256(raw_obs).hexdigest())
    result = score_semantic_candidates(corpus, run)
    assert result["metrics"]["annotated_field_exact_recall"] == 1.0
    assert result["metrics"]["annotated_value_precision"] == 1.0
    assert result["metrics"]["supported_discrepancy_recall"] is None
    with pytest.raises(ValueError, match="overwritten"):
        score_semantic_candidates(corpus, run)
    audit = audit_semantic_preflight(run)
    assert audit["metrics"]["documents"] == 1
    assert audit["metrics"]["candidates"] == 1
    assert audit["metrics"]["unclassified_entities"] == 1
    assert audit["metrics"].get("structurally_complete_entities", 0) == 0
    with pytest.raises(ValueError, match="overwritten"):
        audit_semantic_preflight(run)


def test_supporting_document_is_audited_without_counting_as_material_occurrence(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    observations = {"split": "DEV", "cases": {"case-a": {"documents": [{
        "source_sha256": "a" * 64, "status": "SUCCESS", "candidates": [
            {"entity_id": "duplicate-rate", "semantic_type": "entity_kind",
             "value": "SUPPORTING_DOCUMENT", "ambiguity_flags": []},
            {"entity_id": "duplicate-rate", "semantic_type": "document_role",
             "value": "RATE_CARD", "ambiguity_flags": []},
            {"entity_id": "duplicate-rate", "semantic_type": "document_status",
             "value": "ACCEPTED", "ambiguity_flags": []},
        ],
    }]}}}
    raw = json.dumps(observations).encode()
    (run / "semantic_observations.json").write_bytes(raw)
    (run / "semantic_observations.sha256").write_text(sha256(raw).hexdigest())
    metrics = audit_semantic_preflight(run)["metrics"]
    assert metrics["supporting_entities"] == 1
    assert metrics.get("material_entities", 0) == 0
    assert metrics.get("unclassified_entities", 0) == 0
