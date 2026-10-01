"""Scripted MODEL review protocol tests; no HUMAN or live quality claims."""
from copy import deepcopy

import pytest

from againward.documents.contracts import DocumentError
from againward.domains.rental.case_graph import replay_evidence, import_reading
from againward.domains.rental.case_graph_actions import apply_action, bind_action
from againward.domains.rental.case_graph_review import (
    commit_review, current_review, invoke_occurrence_review, reduce_review,
)
from tests.test_rental_case_graph_actions import prepared, multiple_amounts


def approve(monkeypatch):
    def scripted(prompt, images, **kwargs):
        assert "ORIGINAL source" in prompt
        assert "No calculations" in prompt
        return {"verdict": "SUPPORTED", "reason": "Scripted protocol check, not live semantic validation"}, 0.1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", scripted)


def reviewed(tmp_path, monkeypatch):
    root, graph, action = prepared(tmp_path)
    graph = apply_action(graph, action, root)
    target = next(iter(graph["occurrences"]))
    approve(monkeypatch)
    receipt = invoke_occurrence_review(graph, target, root, model="synthetic-reviewer")
    return root, reduce_review(graph, receipt, root), target, receipt


def test_local_model_review_replays_without_global_qa_or_human(tmp_path, monkeypatch):
    root, graph, target, receipt = reviewed(tmp_path, monkeypatch)
    assert graph["occurrences"][target]["state"] == "REVIEWED"
    assert graph["occurrences"][target]["authority"] == "NONE"
    assert current_review(graph, target)["reviewer_role"] == "MODEL"
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
                        lambda *a, **k: pytest.fail("Replay must not call the model"))
    assert replay_evidence(graph, root) == graph
    assert reduce_review(graph, receipt, root) == graph


def test_role_flag_without_invocation_evidence_cannot_review(tmp_path):
    root, graph, action = prepared(tmp_path)
    graph = apply_action(graph, action, root)
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        reduce_review(graph, "0" * 64, root)


def test_unrelated_occurrence_does_not_stale_review(tmp_path, monkeypatch):
    root, graph = multiple_amounts(tmp_path, two_sources=True)
    first, second = graph["observations"]
    action = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "INVOICE_LINE",
                                "evidence_ids": [first], "anchor_ids": [first]})
    graph = apply_action(graph, action, root)
    target = next(iter(graph["occurrences"]))
    approve(monkeypatch)
    receipt = invoke_occurrence_review(graph, target, root, model="synthetic-reviewer")
    graph = reduce_review(graph, receipt, root)
    action = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "SUPPORTING_RECORD",
                                "evidence_ids": [second], "anchor_ids": [second]})
    graph = apply_action(graph, action, root)
    assert current_review(graph, target)["verdict"] == "SUPPORTED"
    assert replay_evidence(graph, root) == graph


def test_equivalent_read_does_not_erase_a_local_review(tmp_path, monkeypatch):
    root, graph, target, _ = reviewed(tmp_path, monkeypatch)
    reading = next(iter(graph["readings"].values()))["extraction"]
    graph = import_reading(graph, reading, root, role="INDEPENDENT")
    assert current_review(graph, target)["verdict"] == "SUPPORTED"
    assert all(q["state"] == "REVIEWED" for q in graph["issues"].values() if q["kind"] == "OBSERVATION_REVIEW")
    assert replay_evidence(graph, root) == graph


def test_forged_human_receipt_is_rejected_even_if_rehashed(tmp_path, monkeypatch):
    from againward.core.artifact_store import read_json, write_json
    from againward.evidence.hashing import stable_hash
    root, graph, _, receipt = reviewed(tmp_path, monkeypatch)
    forged = read_json(root / "case_graph_v2" / "review_invocations" / (receipt + ".json"))
    forged["reviewer_role"] = "HUMAN"
    forged.pop("receipt_sha256")
    sha = stable_hash(forged)
    write_json(root / "case_graph_v2" / "review_invocations" / (sha + ".json"),
               {**forged, "receipt_sha256": sha})
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        reduce_review(graph, sha, root)


def test_new_ambiguous_review_cannot_reuse_old_support(tmp_path, monkeypatch):
    root, graph, target, _ = reviewed(tmp_path, monkeypatch)
    before = deepcopy(graph["observations"])
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Source does not settle the ownership"}, 0.1))
    receipt = invoke_occurrence_review(graph, target, root, model="synthetic-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_review(graph, target)["verdict"] == "AMBIGUOUS"
    assert graph["occurrences"][target]["state"] == "NEEDS_REPAIR"
    assert any(q["kind"] == "OCCURRENCE_REVIEW" and q["state"] == "OPEN" for q in graph["issues"].values())
    assert graph["observations"] == before
    assert replay_evidence(graph, root) == graph


def test_attaching_a_new_fact_requires_review_of_the_changed_subject(tmp_path, monkeypatch):
    from againward.documents.contracts import SourceBatch
    from againward.documents.readers import read_document
    from againward.evidence.hashing import stable_hash
    root, graph, target, _ = reviewed(tmp_path, monkeypatch)
    payload = deepcopy(next(iter(graph["readings"].values()))["extraction"])
    batch = SourceBatch.from_dict(graph["batch"])
    unit = read_document(batch.documents[0], root).units[0]
    row = payload["candidates"][0]
    start = unit.text.index("EUR")
    row.update(candidate_id="additional-currency", semantic_type="currency", value_type="CURRENCY",
               value="EUR", raw_observed_value="EUR", source_span=[start, start + 3])
    payload["extraction_sha256"] = stable_hash({k: v for k, v in payload.items() if k != "extraction_sha256"})
    graph = import_reading(graph, payload, root, role="RECOVERY")
    # Merely acquiring a separate fact does not stale the reviewed subject.
    assert current_review(graph, target)["verdict"] == "SUPPORTED"
    new_id = next(oid for oid, o in graph["observations"].items() if o["semantic_type"] == "currency")
    action = bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": target, "evidence_ids": [new_id]})
    graph = apply_action(graph, action, root)
    assert current_review(graph, target) is None
    assert graph["occurrences"][target]["state"] == "PROPOSED"
    assert replay_evidence(graph, root) == graph


def test_actual_source_mutation_invalidates_review_replay(tmp_path, monkeypatch):
    root, graph, _, _ = reviewed(tmp_path, monkeypatch)
    from againward.documents.contracts import SourceBatch
    doc = SourceBatch.from_dict(graph["batch"]).documents[0]
    (root / doc.blob_path).write_text("Different source bytes")
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(graph, root)


def test_visual_review_receipt_requires_actual_rendered_input(tmp_path, monkeypatch):
    from againward.documents.codex_provider import assemble_proposal, bind_visual_pages, prompt_version_for_guidance
    from againward.documents.extraction import validate_proposal
    from againward.documents.readers import read_document
    from againward.documents.sources import inventory_sources
    from againward.domains.rental.case_graph import empty_graph
    from benchmarking.document_renderers import pdf
    incoming = tmp_path / "sources"
    incoming.mkdir()
    pdf(incoming / "record.pdf", ["Record amount 58.00 EUR"], scan=True)
    root = tmp_path / "documents"
    batch = inventory_sources(incoming, root)
    doc = batch.documents[0]
    parsed = read_document(doc, root)
    version = prompt_version_for_guidance("")
    raw = {"status": "NEEDS_REVIEW", "limitations": [], "candidates": [{
        "entity_id": "a-label", "semantic_type": "net_amount", "value_type": "DECIMAL",
        "value": "58.00", "raw_observed_value": "58.00", "location": parsed.units[0].location,
        "normalization_notes": "Printed amount", "ambiguity_flags": []}]}
    proposal = assemble_proposal(raw, doc, parsed, batch.batch_id, "synthetic-reader",
        prompt_version=version, invocation_id="visual-review-test",
        visual_bindings=bind_visual_pages(doc, parsed, root, model="synthetic-reader",
                                         prompt_version=version, invocation_id="visual-review-test"))
    graph = import_reading(empty_graph(batch), validate_proposal(proposal, batch, root).to_dict(),
                           root, role="PRIMARY")
    oid = next(iter(graph["observations"]))
    action = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "SUPPORTING_RECORD",
                                "evidence_ids": [oid], "anchor_ids": [oid]})
    graph = apply_action(graph, action, root)
    target = next(iter(graph["occurrences"]))

    def scripted(prompt, images, **kwargs):
        assert len(images) == 1 and images[0].is_file()
        assert "render_hashes" in prompt
        return {"verdict": "SUPPORTED", "reason": "Synthetic pixel protocol only"}, 0.1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", scripted)
    receipt = invoke_occurrence_review(graph, target, root, model="synthetic-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_review(graph, target)["reviewer_role"] == "MODEL"
    assert replay_evidence(graph, root) == graph


def test_review_uses_the_same_transactional_head_as_actions(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_actions import commit_action
    root, graph, action = prepared(tmp_path)
    graph = commit_action(graph, action, root)
    target = next(iter(graph["occurrences"]))
    approve(monkeypatch)
    receipt = invoke_occurrence_review(graph, target, root, model="synthetic-reviewer")
    result = commit_review(graph, receipt, root)
    assert replay_evidence(result, root) == result
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        commit_review(graph, receipt, root)


def test_transaction_refuses_an_unjournaled_promotion(tmp_path):
    from againward.domains.rental.case_graph import commit_transition
    root, graph, action = prepared(tmp_path)
    graph = apply_action(graph, action, root)

    def invalid_transition(current):
        next(iter(current["occurrences"].values()))["state"] = "REVIEWED"
        return current
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        commit_transition(graph, root, invalid_transition)
    assert not (root / "case_graph_v2" / "head.json").exists()
