"""Codex may review native candidate facts, never manufacture visual approval."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from againward.documents.analyst_review import build_analyst_review, review_visual_with_codex, review_with_codex
from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
from againward.documents.contracts import DocumentError
from againward.documents.extraction import promote_facts, validate_proposal
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources
from againward.documents.visual_fact_review import attest_visual_facts
from tests.test_document_adjudication import _case
from tests.test_document_visual_fact_review import _packet


def _native_decisions(extractions):
    return {extraction.source_id: {"decisions": [
        {"candidate_id": candidate.candidate_id, "decision": "ACCEPT",
         "reason": "Original native phrase supports this source-local classification.",
         "resolved_flags": []}
        for candidate in extraction.candidates]}
        for extraction in extractions}


def _rate_sheet_with_orphan(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    (public / "rates.txt").write_text(
        "ACCEPTED rate card for AG-7 dated 2026-08-28.\n"
        "LIFT-5: EUR 50.00 per day.\nLIFT-50: EUR 30.00 per day.\n")
    root = tmp_path / "documents"
    batch = inventory_sources(public, root)
    document = batch.documents[0]
    parsed = read_document(document, root)
    rows = []

    def add(entity, field, value, quote, line=0, value_type="TEXT"):
        rows.append({"entity_id": entity, "semantic_type": field, "value_type": value_type,
                     "value": value, "raw_observed_value": quote,
                     "location": parsed.units[line].location,
                     "normalization_notes": "Source-local classification", "ambiguity_flags": []})

    for entity, line, asset, rate in (("lift_5", 1, "LIFT-5", "50.00"),
                                      ("lift_50", 2, "LIFT-50", "30.00")):
        add(entity, "entity_kind", "SUPPORTING_DOCUMENT", asset, line, "ENUM")
        add(entity, "document_role", "RATE_CARD", "rate card", 0, "ENUM")
        add(entity, "document_status", "ACCEPTED", "ACCEPTED", 0, "ENUM")
        add(entity, "asset_id", asset, asset, line, "IDENTIFIER")
        add(entity, "rate", rate, rate, line, "DECIMAL")
        add(entity, "date", "2026-08-28", "2026-08-28", 0, "DATE")
    add("rate_sheet", "date", "2026-08-28", "2026-08-28", 0, "DATE")
    extraction = validate_proposal(assemble_proposal(
        {"status": "SUCCESS", "limitations": [], "candidates": rows},
        document, parsed, batch.batch_id, "synthetic-model"), batch, root)
    return root, batch, extraction


def test_orphan_date_requires_rejection_while_complete_rate_rows_keep_dates(tmp_path):
    root, batch, extraction = _rate_sheet_with_orphan(tmp_path)
    all_accepted = _native_decisions((extraction,))
    blocked = build_analyst_review(batch, (extraction,), all_accepted, root)
    assert blocked["status"] == "REPAIR_REQUIRED"
    assert blocked["native_facts_accepted"] == 0
    assert blocked["structural_gaps"][0]["entity_id"] == "rate_sheet"
    assert blocked["structural_gaps"][0]["missing"] == [
        "entity_kind", "document_role", "document_status"]

    orphan = next(c for c in extraction.candidates if c.entity_id == "rate_sheet")
    repaired = _native_decisions((extraction,))
    decision = next(d for d in repaired[extraction.source_id]["decisions"]
                    if d["candidate_id"] == orphan.candidate_id)
    decision.update(decision="REJECT", reason="Printed date has no source-local analytical entity role.")
    ready = build_analyst_review(batch, (extraction,), repaired, root)
    assert ready["status"] == "READY_FOR_PACKAGE"
    assert ready["structural_gaps"] == []
    facts = promote_facts((extraction,), ready["review"], batch, root)
    assert len(facts) == 12
    by_entity = {}
    for fact in facts:
        by_entity.setdefault(fact.candidate.entity_id, {})[fact.candidate.semantic_type] = fact.candidate.value
    assert set(by_entity) == {"lift_5", "lift_50"}
    assert {by_entity[e]["rate"] for e in by_entity} == {"50.00", "30.00"}
    assert all(by_entity[e]["date"] == "2026-08-28" for e in by_entity)


def test_partial_accepted_entity_fails_closed_even_when_other_facts_are_valid(tmp_path):
    root, batch, extraction = _rate_sheet_with_orphan(tmp_path)
    decisions = _native_decisions((extraction,))
    for candidate, decision in zip(extraction.candidates, decisions[extraction.source_id]["decisions"]):
        if candidate.entity_id == "rate_sheet" or (candidate.entity_id == "lift_50"
                                                   and candidate.semantic_type == "document_status"):
            decision.update(decision="REJECT", reason="Reject unsupported structural candidate.")
    receipt = build_analyst_review(batch, (extraction,), decisions, root)
    assert receipt["status"] == "REPAIR_REQUIRED"
    assert receipt["native_facts_accepted"] == 0
    assert receipt["structural_gaps"] == [{"source_id": extraction.source_id,
                                            "entity_id": "lift_50", "missing": ["document_status"]}]


def test_native_repair_rejects_orphan_without_losing_valid_rate_dates(tmp_path, monkeypatch):
    root, batch, extraction = _rate_sheet_with_orphan(tmp_path)
    calls = []

    def model(command, *, input, **_kwargs):
        payload = json.loads(input.split("\n", 1)[1])
        calls.append(payload)
        proposal = _native_decisions((extraction,))[extraction.source_id]
        if "structural_gaps" in payload:
            orphan = next(c for c in extraction.candidates if c.entity_id == "rate_sheet")
            next(d for d in proposal["decisions"] if d["candidate_id"] == orphan.candidate_id).update(
                decision="REJECT", reason="Printed date is detached from an analytical entity.")
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(proposal))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run", model)
    receipt = review_with_codex(batch, (extraction,), root, model="synthetic-model")
    assert len(calls) == 2
    assert receipt["status"] == "READY_FOR_PACKAGE"
    assert receipt["initial_structural_gaps"][0]["entity_id"] == "rate_sheet"
    assert receipt["structural_gaps"] == []
    assert receipt["native_facts_accepted"] == 12
    assert receipt["repair_history"][0]["before"][-1]["decision"] == "ACCEPT"
    assert receipt["repair_history"][0]["after"][-1]["decision"] == "REJECT"


def test_native_analyst_review_promotes_current_facts_without_human_role(tmp_path):
    root, batch, extractions, _challenger, _qa, _raw, _email = _case(tmp_path)
    receipt = build_analyst_review(batch, extractions, _native_decisions(extractions), root)
    assert receipt["status"] == "READY_FOR_PACKAGE"
    assert receipt["native_facts_accepted"] == 6
    assert receipt["structural_gaps"] == []
    assert receipt["review"]["reviewer_role"] == "ANALYST"
    assert receipt["human_approval"] is False and receipt["delivery_approved"] is False
    invalid = _native_decisions(extractions)
    invalid[extractions[0].source_id]["decisions"] = []
    with pytest.raises(DocumentError, match="EXTRACTION_INCOMPLETE"):
        build_analyst_review(batch, extractions, invalid, root)


def test_visual_facts_are_deferred_without_scripted_human_attestation(tmp_path):
    root, batch, extraction, _review = _packet(tmp_path)
    receipt = build_analyst_review(batch, (extraction,), {}, root)
    assert receipt["status"] == "WAITING_FOR_VISUAL_REVIEW"
    assert receipt["visual_candidates_deferred"] == 1
    assert receipt["native_facts_accepted"] == 0
    assert receipt["review"]["decisions"][0]["decision"] == "DEFER"
    assert "visual_attestations" not in receipt["review"]


def test_visual_model_cannot_resolve_flags_without_component_bound_operator(tmp_path, monkeypatch):
    root, batch, _extraction, _review = _packet(tmp_path)
    document = batch.documents[0]
    parsed = read_document(document, root)
    fields = [("entity_kind", "RETURN", "Signed return"),
              ("document_role", "RETURN_NOTE", "Signed return"),
              ("document_status", "ACCEPTED", "Signed return"),
              ("date", "2026-09-05", "2026-09-05")]
    raw = {"status": "NEEDS_REVIEW", "limitations": [], "candidates": [
        {"entity_id": "return-1", "semantic_type": field,
         "value_type": "DATE" if field == "date" else "ENUM", "value": value,
         "raw_observed_value": quote, "location": parsed.units[0].location,
         "normalization_notes": "Pixel proposal", "ambiguity_flags": []}
        for field, value, quote in fields]}
    prompt_version = prompt_version_for_guidance("")
    extraction = validate_proposal(assemble_proposal(raw, document, parsed, batch.batch_id,
        "synthetic-model", prompt_version=prompt_version,
        visual_bindings=bind_visual_pages(document, parsed, root, model="synthetic-model",
            prompt_version=prompt_version, invocation_id="analyst-review-fixture"),
        invocation_id="analyst-review-fixture"), batch, root)
    base = build_analyst_review(batch, (extraction,), {}, root)

    def visual_model(prompt, *, images, **_kwargs):
        assert len(images) == 1 and images[0].is_file()
        assert all(candidate.candidate_id in prompt for candidate in extraction.candidates)
        return {"decisions": [{"candidate_id": candidate.candidate_id, "decision": "ACCEPT",
                               "reason": "The printed field appears in the original page.",
                               "resolved_flags": list(candidate.ambiguity_flags)}
                              for candidate in extraction.candidates]}, 0.1

    monkeypatch.setattr("againward.documents.analyst_review._ask_codex", visual_model)
    result = review_visual_with_codex(batch, (extraction,), base, root, model="synthetic-model")
    assert result["status"] == "WAITING_FOR_VISUAL_ATTESTATION"
    assert result["visual_candidates_pending_attestation"] == 4
    assert all(row["resolved_flags"] == [] for row in result["review"]["decisions"])
    with pytest.raises(DocumentError, match="HUMAN_REVIEW_REQUIRED"):
        promote_facts((extraction,), result["review"], batch, root)

    def scripted_fixture(prompt):
        if prompt.startswith("Open the preview"):
            return "INSPECTED " + batch.documents[0].sha256[:12]
        if prompt.startswith("Confirm ALL"):
            return "CONFIRM " + prompt.split("CONFIRM ")[1].split(":")[0]
        raise AssertionError(prompt)

    # Protocol test only: this callback is NOT a human inspection.
    attested = attest_visual_facts(batch, (extraction,), result["review"], root,
                                   actor_id="TEST_FIXTURE_ONLY", ask=scripted_fixture, interactive=True)
    for decision, candidate in zip(attested["decisions"], extraction.candidates):
        assert set(decision["resolved_flags"]) == set(candidate.ambiguity_flags)
    assert len(promote_facts((extraction,), attested, batch, root)) == 4


def test_codex_analyst_reads_original_native_sources_and_cannot_skip_candidates(tmp_path, monkeypatch):
    root, batch, extractions, _challenger, _qa, _raw, _email = _case(tmp_path)
    seen = []

    def model(command, *, input, **_kwargs):
        assert "invoice's printed net amount is an observed invoice fact" in input
        assert "deterministic code performs that comparison downstream" in input
        prompt = json.loads(input.split("\n", 1)[1])
        seen.append(prompt)
        assert "off-hire request alone" in json.dumps(prompt["original_native_sources"])
        current = next(extraction for extraction in extractions
                       if extraction.source_id == prompt["current_source_id"])
        result = _native_decisions((current,))[current.source_id]
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(result))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run", model)
    receipt = review_with_codex(batch, extractions, root, model="synthetic-model")
    assert len(seen) == 2
    assert receipt["native_facts_accepted"] == 6
    assert receipt["model_calls"] == 2 and receipt["cached_sources"] == 0
    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run",
                        lambda *_args, **_kwargs: pytest.fail("Valid cached source must not call model"))
    resumed = review_with_codex(batch, extractions, root, model="synthetic-model")
    assert resumed["receipt_sha256"] == receipt["receipt_sha256"]
    saved = next((root / "analyst_runs").glob("*.json"))
    saved.write_text(saved.read_text().replace("ACCEPT", "REJECT", 1))
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        review_with_codex(batch, extractions, root, model="synthetic-model")


def test_one_bounded_repair_restores_source_status_without_erasing_first_decision(tmp_path, monkeypatch):
    root, batch, extractions, _challenger, _qa, _raw, _email = _case(tmp_path)
    prompts = []

    def model(command, *, input, **_kwargs):
        payload = json.loads(input.split("\n", 1)[1])
        prompts.append(payload)
        current = next(e for e in extractions if e.source_id == payload["current_source_id"])
        raw = _native_decisions((current,))[current.source_id]
        if "structural_gaps" not in payload and any(c.semantic_type == "document_status"
                                                    and c.value == "EXTRACTED" for c in current.candidates):
            target = next(c.candidate_id for c in current.candidates if c.semantic_type == "document_status")
            next(d for d in raw["decisions"] if d["candidate_id"] == target).update(
                decision="REJECT", reason="Prior pass was too literal about metadata status.")
        Path(command[command.index("--output-last-message") + 1]).write_text(json.dumps(raw))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run", model)
    receipt = review_with_codex(batch, extractions, root, model="synthetic-model")
    assert receipt["status"] == "READY_FOR_PACKAGE"
    assert receipt["model_calls"] == 3
    assert len(receipt["initial_structural_gaps"]) == 1
    assert len(receipt["repair_history"]) == 1
    history = receipt["repair_history"][0]
    assert any(d["decision"] == "REJECT" for d in history["before"])
    assert all(d["decision"] == "ACCEPT" for d in history["after"])
    assert len(list((root / "analyst_repairs").glob("*.json"))) == 1
    resumed = review_with_codex(batch, extractions, root, model="synthetic-model")
    assert resumed["receipt_sha256"] == receipt["receipt_sha256"]
    assert len(prompts) == 3


def test_interrupted_model_call_resumes_from_first_source_receipt(tmp_path, monkeypatch):
    root, batch, extractions, _challenger, _qa, _raw, _email = _case(tmp_path)
    attempted = []

    def interrupted(command, *, input, **_kwargs):
        payload = json.loads(input.split("\n", 1)[1])
        attempted.append(payload["current_source_id"])
        if len(attempted) == 2:
            raise DocumentError("MODEL_TIMEOUT", "Synthetic interruption")
        current = next(e for e in extractions if e.source_id == payload["current_source_id"])
        Path(command[command.index("--output-last-message") + 1]).write_text(
            json.dumps(_native_decisions((current,))[current.source_id]))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run", interrupted)
    with pytest.raises(DocumentError, match="MODEL_TIMEOUT"):
        review_with_codex(batch, extractions, root, model="synthetic-model")
    assert len(list((root / "analyst_proposals").glob("*.json"))) == 1

    def resumed_model(command, *, input, **_kwargs):
        payload = json.loads(input.split("\n", 1)[1])
        assert payload["current_source_id"] == attempted[1]
        current = next(e for e in extractions if e.source_id == payload["current_source_id"])
        Path(command[command.index("--output-last-message") + 1]).write_text(
            json.dumps(_native_decisions((current,))[current.source_id]))
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr("againward.documents.analyst_review.subprocess.run", resumed_model)
    receipt = review_with_codex(batch, extractions, root, model="synthetic-model")
    assert receipt["status"] == "READY_FOR_PACKAGE"
    assert receipt["cached_sources"] == 1 and receipt["model_calls"] == 1
