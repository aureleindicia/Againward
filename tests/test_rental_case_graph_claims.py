"""Commercial decisions require local evidence and independent review, not role flags."""
from copy import deepcopy

import pytest

from againward.documents.contracts import DocumentError
from againward.domains.rental.case_graph import replay_evidence, state_hash
from againward.domains.rental.case_graph_claims import (
    bind_claim, reduce_claim, current_claims, observation_disposition,
)
from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review, current_review
from tests.test_rental_case_graph_relations import occurrences, PAIR


def meaning_claim(graph, targets):
    ids = [oid for target in targets for values in graph["occurrences"][target]["fields"].values() for oid in values]
    return bind_claim(graph, {"kind": "CHARGE_MEANING", "target": targets[0], "value": "RENTAL",
        "evidence_ids": ids, "reason": "Check the exact commercial meaning on the proven relationship"})


def test_related_commercial_meaning_is_a_separate_reviewed_claim(tmp_path, monkeypatch):
    records = deepcopy(PAIR)
    records[1][1]["charge_type"] = "RENTAL"
    root, graph, targets = occurrences(tmp_path, monkeypatch, records)
    facts = deepcopy(graph["observations"])
    graph = reduce_claim(graph, meaning_claim(graph, targets))
    claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM")
    assert graph["issues"][claim]["state"] == "OPEN"
    assert current_claims(graph, "CHARGE_MEANING", targets[0]) == []

    def independent(prompt, images, **kwargs):
        assert "proposed semantic decision" in prompt
        assert all(graph["occurrences"][oid]["source_id"] in prompt for oid in targets)
        assert "original_source" in prompt and "No calculations" in prompt
        return {"verdict": "SUPPORTED", "reason": "Scripted claim protocol"}, 0.1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", independent)
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_claims(graph, "CHARGE_MEANING", targets[0])[0]["proposal"]["value"] == "RENTAL"
    assert graph["observations"] == facts  # No copied fact in the invoice.
    assert all(o["authority"] == "NONE" for o in graph["occurrences"].values())
    assert replay_evidence(graph, root) == graph


def test_unrelated_commercial_source_cannot_supply_charge_meaning(tmp_path, monkeypatch):
    records = deepcopy(PAIR)
    records[1][1].update(agreement_id="OTHER-LEASE", asset_id="OTHER-EQ", charge_type="RENTAL")
    _, graph, targets = occurrences(tmp_path, monkeypatch, records)
    result = reduce_claim(graph, meaning_claim(graph, targets))
    assert result["actions"][-1]["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert state_hash(graph) == state_hash(result)


def test_ambiguous_relation_cannot_expand_claim_evidence(tmp_path, monkeypatch):
    _, graph, targets = occurrences(tmp_path, monkeypatch, [*PAIR, PAIR[1]])
    result = reduce_claim(graph, meaning_claim(graph, targets[:2]))
    assert result["actions"][-1]["rejection_code"] == "SOURCE_LOCATION_INVALID"


def test_rejected_subject_cannot_supply_commercial_claim(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "UNSUPPORTED", "reason": "Wrong grouping"}, 0.1))
    receipt = invoke_occurrence_review(graph, targets[0], root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    result = reduce_claim(graph, meaning_claim(graph, targets))
    assert result["actions"][-1]["rejection_code"] == "REVIEW_STALE"


def test_structural_role_never_proves_governing_authority(tmp_path, monkeypatch):
    records = [("RATE_TERM", {"document_role": "RATE_CARD", "rate": "18.00", "currency": "EUR"})]
    _, graph, targets = occurrences(tmp_path, monkeypatch, records)
    action = bind_claim(graph, {"kind": "GOVERNING_TERM", "target": targets[0], "value": "GOVERNING",
        "evidence_ids": list(graph["observations"]), "reason": "Must not infer acceptance from a rate card"})
    result = reduce_claim(graph, action)
    assert result["actions"][-1]["rejection_code"] == "EXTRACTION_INCOMPLETE"


def test_changed_review_invalidates_a_previously_supported_claim(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    graph = reduce_claim(graph, meaning_claim(graph, targets))
    claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM")
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_review(graph, claim)["verdict"] == "SUPPORTED"
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Identity is uncertain"}, 0.1))
    receipt = invoke_occurrence_review(graph, targets[1], root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_review(graph, claim) is None
    assert current_claims(graph, "CHARGE_MEANING", targets[0]) == []
    assert replay_evidence(graph, root) == graph


def test_disposition_requires_review_and_does_not_erase_evidence(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    oid = next(iter(graph["observations"]))
    before = deepcopy(graph["observations"][oid])
    graph = reduce_claim(graph, bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": oid,
        "value": "REJECTED_WITH_EVIDENCE", "evidence_ids": [oid], "reason": "Wrong interpretation of the source"}))
    claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM")
    assert observation_disposition(graph, oid) == "UNRESOLVED"
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert observation_disposition(graph, oid) == "REJECTED_WITH_EVIDENCE"
    assert graph["observations"][oid] == {**before, "disposition": "REJECTED_WITH_EVIDENCE"}
    assert replay_evidence(graph, root) == graph


def test_conflicting_rejection_and_occurrence_approval_stays_unresolved(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    oid = next(iter(graph["observations"]))
    graph = reduce_claim(graph, bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": oid,
        "value": "REJECTED_WITH_EVIDENCE", "evidence_ids": [oid], "reason": "Challenge earlier interpretation"}))
    claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM")
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert observation_disposition(graph, oid) == "UNRESOLVED"


def test_duplicate_cannot_be_asserted_from_equal_values_alone(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, PAIR)
    ids = [oid for oid, row in graph["observations"].items() if row["semantic_type"] == "asset_id"]
    action = bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": ids[0], "value": "DUPLICATE",
        "evidence_ids": ids, "reason": "Identical text is not duplicate source evidence"})
    result = reduce_claim(graph, action)
    assert result["actions"][-1]["rejection_code"] == "SOURCE_LOCATION_INVALID"


def test_claim_cannot_forge_human_or_prerequisite_hashes(tmp_path, monkeypatch):
    _, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    action = meaning_claim(graph, targets)
    action["prerequisites"] = {}
    result = reduce_claim(graph, action)
    assert result["actions"][-1]["rejection_code"] == "REVIEW_STALE"
    action["reviewer_role"] = "HUMAN"
    with pytest.raises(DocumentError, match="EXTRACTION_SCHEMA_INVALID"):
        reduce_claim(graph, action)


def test_claim_rejection_receipt_replays_and_cannot_be_changed_to_success(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, PAIR)
    action = meaning_claim(graph, targets)
    action["prerequisites"] = {}
    result = reduce_claim(graph, action)
    assert replay_evidence(result, root) == result
    result["actions"][-1]["result"] = "ACCEPTED_PROPOSAL"
    with pytest.raises(DocumentError, match="SOURCE_CHANGED"):
        replay_evidence(result, root)


def test_opposing_supported_dispositions_do_not_choose_latest_convenient_value(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    oid = next(iter(graph["observations"]))
    for disposition in ("REJECTED_WITH_EVIDENCE", "IRRELEVANT"):
        graph = reduce_claim(graph, bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": oid,
            "value": disposition, "evidence_ids": [oid], "reason": "Scripted competing decisions"}))
        claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM"
                     and q["details"]["proposal"]["value"] == disposition)
        receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
        graph = reduce_review(graph, receipt, root)
    assert observation_disposition(graph, oid) == "UNRESOLVED"


def test_governing_claim_with_acceptance_still_needs_its_own_review(tmp_path, monkeypatch):
    records = [("RATE_TERM", {"document_role": "RENTAL_AGREEMENT", "document_status": "ACCEPTED",
                              "rate": "18.00", "currency": "EUR"})]
    root, graph, targets = occurrences(tmp_path, monkeypatch, records)
    graph = reduce_claim(graph, bind_claim(graph, {"kind": "GOVERNING_TERM", "target": targets[0],
        "value": "GOVERNING", "evidence_ids": list(graph["observations"]),
        "reason": "Explicit acceptance must be checked for scope and overrides"}))
    assert graph["actions"][-1]["result"] == "ACCEPTED_PROPOSAL"
    assert current_claims(graph, "GOVERNING_TERM", targets[0]) == []
    claim = next(qid for qid, q in graph["issues"].items() if q["kind"] == "SEMANTIC_CLAIM")
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Possible superseding term"}, 0.1))
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert current_claims(graph, "GOVERNING_TERM", targets[0]) == []
    assert graph["issues"][claim]["state"] == "OPEN"
    assert graph["occurrences"][targets[0]]["authority"] == "NONE"
