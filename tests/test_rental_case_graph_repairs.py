"""Local regrouping repairs retain all evidence and invalidate only their subject."""
from copy import deepcopy

from againward.domains.rental.case_graph import replay_evidence, state_hash
from againward.domains.rental.case_graph_actions import apply_action, bind_action
from againward.domains.rental.case_graph_claims import observation_disposition
from againward.domains.rental.case_graph_review import current_review, invoke_occurrence_review, reduce_review
from tests.test_rental_case_graph_relations import occurrences
from tests.test_rental_case_graph_actions import prepared


def repairable(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [
        ("SUPPORTING_RECORD", {"invoice_id": "DOC-R", "description": "Candidate wording"})], review=False)
    # Build the independent hypothesis with only the exact identity as anchor.
    ids = list(graph["observations"])
    anchor = next(oid for oid in ids if graph["observations"][oid]["semantic_type"] == "invoice_id")
    graph = apply_action(graph, bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "INVOICE_LINE",
        "evidence_ids": ids, "anchor_ids": [anchor]}), root)
    target = next(oid for oid, subject in graph["occurrences"].items() if subject["kind"] == "INVOICE_LINE")
    receipt = invoke_occurrence_review(graph, target, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    return root, graph, target, anchor, next(oid for oid in ids if oid != anchor)


def test_local_replacement_preserves_identity_and_evidence_but_requires_new_review(tmp_path, monkeypatch):
    root, graph, target, anchor, removed = repairable(tmp_path, monkeypatch)
    before = deepcopy(graph["observations"])
    action = bind_action(graph, {"type": "REPLACE_OBSERVATIONS", "target": target, "evidence_ids": [anchor]})
    result = apply_action(graph, action, root)
    assert result["occurrences"][target]["anchor_ids"] == [anchor]
    assert result["occurrences"][target]["fields"] == {"invoice_id": [anchor]}
    assert result["observations"] == before
    assert current_review(result, target) is None
    assert observation_disposition(result, removed) == "UNRESOLVED"
    assert replay_evidence(result, root) == result
    assert apply_action(result, action, root) == result


def test_repair_cannot_replace_runtime_identity_witnesses(tmp_path, monkeypatch):
    root, graph, target, _, removed = repairable(tmp_path, monkeypatch)
    action = bind_action(graph, {"type": "REPLACE_OBSERVATIONS", "target": target, "evidence_ids": [removed]})
    result = apply_action(graph, action, root)
    assert result["actions"][-1]["rejection_code"] == "ENTITY_AMBIGUOUS"
    assert state_hash(result) == state_hash(graph)
    assert replay_evidence(result, root) == result


def test_repair_does_not_borrow_evidence_from_another_source(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [
        ("INVOICE_LINE", {"invoice_id": "DOC-L"}), ("INVOICE_LINE", {"invoice_id": "DOC-M"})])
    foreign = next(iter(graph["occurrences"][targets[1]]["fields"]["invoice_id"]))
    result = apply_action(graph, bind_action(graph, {"type": "REPLACE_OBSERVATIONS", "target": targets[0],
        "evidence_ids": [foreign]}), root)
    assert result["actions"][-1]["result"] == "REJECTED"
    assert state_hash(result) == state_hash(graph)
    assert current_review(result, targets[1]) == current_review(graph, targets[1])


def test_existing_action_journal_replays_with_its_original_validator(tmp_path):
    from againward.domains.rental.case_graph_actions import reduce_action
    root, graph, action = prepared(tmp_path)
    old = reduce_action(graph, action, validator_version="rental-graph-actions-v1")
    assert replay_evidence(old, root) == old
