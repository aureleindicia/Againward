"""V2 deltas preserve evidence and cannot create reviewed commercial truth."""
from copy import deepcopy

import pytest

from againward.documents.contracts import DocumentError
from againward.domains.rental.case_graph import (
    empty_graph, import_reading, replay_evidence, state_hash,
)
from againward.domains.rental.case_graph_actions import apply_action, bind_action, commit_action
from tests.test_rental_case_graph import evidence


def prepared(tmp_path):
    root, batch, payload = evidence(tmp_path)
    graph = import_reading(empty_graph(batch), payload, root, role="PRIMARY")
    oid = next(iter(graph["observations"]))
    action = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "target": "", "kind": "INVOICE_LINE",
                                "evidence_ids": [oid], "anchor_ids": [oid]})
    return root, graph, action


def test_proposal_is_replayable_idempotent_and_does_not_promote(tmp_path):
    root, graph, action = prepared(tmp_path)
    result = apply_action(graph, action, root)
    occurrence = next(iter(result["occurrences"].values()))
    assert occurrence["state"] == "PROPOSED"
    assert occurrence["authority"] == "NONE"
    assert occurrence["origin"] == "MODEL_STRUCTURE_PROPOSAL"
    assert result["observations"] == graph["observations"]
    assert result["reviews"] == {}
    assert replay_evidence(result, root) == result
    assert apply_action(result, action, root) == result


def test_missing_identity_is_rejected_without_semantic_state_change(tmp_path):
    root, graph, action = prepared(tmp_path)
    action["anchor_ids"] = ["unknown-proof"]
    result = apply_action(graph, action, root)
    receipt = result["actions"][-1]
    assert receipt["result"] == "REJECTED"
    assert receipt["rejection_code"] == "ENTITY_AMBIGUOUS"
    assert receipt["pre_state_hash"] == receipt["post_state_hash"] == state_hash(graph)
    assert len(result["actions"]) == len(graph["actions"]) + 1
    assert replay_evidence(result, root) == result


def test_forged_review_or_changed_occurrence_cannot_enter_replay(tmp_path):
    root, graph, action = prepared(tmp_path)
    result = apply_action(graph, action, root)
    next(iter(result["occurrences"].values()))["state"] = "REVIEWED"
    result["reviews"]["fake"] = {"reviewer_role": "HUMAN"}
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(result, root)


def test_stale_action_is_recorded_and_does_not_mutate_occurrence(tmp_path):
    root, graph, action = prepared(tmp_path)
    action["prerequisites"][next(iter(action["prerequisites"]))] = "0" * 64
    result = apply_action(graph, action, root)
    assert result["actions"][-1]["rejection_code"] == "REVIEW_STALE"
    assert state_hash(result) == state_hash(graph)
    assert replay_evidence(result, root) == result


def test_unknown_evidence_cannot_be_attached(tmp_path):
    root, graph, action = prepared(tmp_path)
    graph = apply_action(graph, action, root)
    oid = next(iter(graph["occurrences"]))
    action = bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": oid, "kind": "",
                                "evidence_ids": ["unbound-observation"], "anchor_ids": []})
    result = apply_action(graph, action, root)
    assert result["actions"][-1]["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert result["occurrences"] == graph["occurrences"]


def test_forged_success_receipt_cannot_hide_rejected_action(tmp_path):
    root, graph, action = prepared(tmp_path)
    action["kind"] = "GOVERNING_AUTHORITY"
    result = apply_action(graph, action, root)
    assert result["actions"][-1]["result"] == "REJECTED"
    result["actions"][-1]["result"] = "ACCEPTED_PROPOSAL"
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(result, root)


@pytest.mark.parametrize("bad", [[], None, {}, 4])
def test_malformed_action_type_is_controlled(tmp_path, bad):
    _, graph, action = prepared(tmp_path)
    proposal = {k: deepcopy(v) for k, v in action.items() if k != "prerequisites"}
    proposal["type"] = bad
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        bind_action(graph, proposal)


def test_transactional_head_rejects_a_stale_writer(tmp_path):
    root, graph, action = prepared(tmp_path)
    current = commit_action(graph, action, root)
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        commit_action(graph, action, root)
    assert commit_action(current, action, root) == current


def test_attachment_of_existing_evidence_does_not_create_a_new_revision(tmp_path):
    root, graph, action = prepared(tmp_path)
    graph = apply_action(graph, action, root)
    target = next(iter(graph["occurrences"]))
    attachment = bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": target, "kind": "",
                                    "anchor_ids": [], "evidence_ids": action["evidence_ids"]})
    result = apply_action(graph, attachment, root)
    assert state_hash(result) == state_hash(graph)
    assert replay_evidence(result, root) == result


def multiple_amounts(tmp_path, *, two_sources):
    from againward.documents.codex_provider import assemble_proposal
    from againward.documents.extraction import validate_proposal
    from againward.documents.readers import read_document
    from againward.documents.sources import inventory_sources
    incoming = tmp_path / "input"
    incoming.mkdir()
    (incoming / "first.txt").write_text("Record Alpha amount 72.00. " +
                                        ("" if two_sources else "Record Beta amount 33.00."))
    if two_sources:
        (incoming / "second.txt").write_text("Record Beta amount 33.00.")
    root = tmp_path / "evidence"
    batch = inventory_sources(incoming, root)
    graph = empty_graph(batch)
    for doc in batch.documents:
        parsed = read_document(doc, root)
        unit = parsed.units[0]
        raw = {"status": "SUCCESS", "limitations": [], "candidates": [{
            "entity_id": "same-untrusted-label", "semantic_type": "net_amount", "value_type": "DECIMAL",
            "value": value, "raw_observed_value": value, "location": unit.location,
            "normalization_notes": "", "ambiguity_flags": []}
            for value in ("72.00", "33.00") if value in unit.text]}
        payload = validate_proposal(assemble_proposal(raw, doc, parsed, batch.batch_id,
                                                      "synthetic-reader"), batch, root).to_dict()
        graph = import_reading(graph, payload, root, role="PRIMARY")
    return root, graph


def test_occurrence_cannot_copy_a_fact_from_another_source(tmp_path):
    root, graph = multiple_amounts(tmp_path, two_sources=True)
    first, second = graph["observations"]
    declaration = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "target": "", "kind": "INVOICE_LINE",
        "anchor_ids": [first], "evidence_ids": [first]})
    graph = apply_action(graph, declaration, root)
    attachment = bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": next(iter(graph["occurrences"])),
        "kind": "", "anchor_ids": [], "evidence_ids": [second]})
    result = apply_action(graph, attachment, root)
    assert result["actions"][-1]["result"] == "REJECTED"
    assert state_hash(graph) == state_hash(result)
    assert replay_evidence(result, root) == result


def test_attachment_cannot_overwrite_a_conflicting_value(tmp_path):
    root, graph = multiple_amounts(tmp_path, two_sources=False)
    first, second = graph["observations"]
    action = bind_action(graph, {"type": "DECLARE_OCCURRENCE", "target": "", "kind": "INVOICE_LINE",
        "anchor_ids": [first], "evidence_ids": [first]})
    graph = apply_action(graph, action, root)
    action = bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": next(iter(graph["occurrences"])),
        "kind": "", "anchor_ids": [], "evidence_ids": [second]})
    result = apply_action(graph, action, root)
    assert result["actions"][-1]["rejection_code"] == "EXTRACTION_CONTRADICTION"
    assert state_hash(result) == state_hash(graph)
    assert result["observations"] == graph["observations"]


def test_unrelated_action_does_not_stale_local_prerequisites(tmp_path):
    root, graph = multiple_amounts(tmp_path, two_sources=True)
    first, second = graph["observations"]
    actions = [bind_action(graph, {"type": "DECLARE_OCCURRENCE", "target": "", "kind": "INVOICE_LINE",
        "anchor_ids": [oid], "evidence_ids": [oid]}) for oid in (first, second)]
    forward = apply_action(apply_action(graph, actions[0], root), actions[1], root)
    reverse = apply_action(apply_action(graph, actions[1], root), actions[0], root)
    assert len(forward["occurrences"]) == 2
    assert forward["actions"][-1]["result"] == "ACCEPTED_PROPOSAL"
    assert reverse["actions"][-1]["result"] == "ACCEPTED_PROPOSAL"
    assert state_hash(forward) == state_hash(reverse)
    assert replay_evidence(forward, root) == forward
    assert replay_evidence(reverse, root) == reverse


def test_model_intent_does_not_need_runtime_hashes_or_empty_protocol_fields(tmp_path):
    root, graph, action = prepared(tmp_path)
    minimal = {k: action[k] for k in ("type", "kind", "evidence_ids", "anchor_ids")}
    assert bind_action(graph, minimal) == action
    graph = apply_action(graph, action, root)
    attachment = bind_action(graph, {"type": "ATTACH_OBSERVATIONS",
        "target": next(iter(graph["occurrences"])), "evidence_ids": action["evidence_ids"]})
    result = apply_action(graph, attachment, root)
    assert result["actions"][-1]["result"] == "ACCEPTED_PROPOSAL"
