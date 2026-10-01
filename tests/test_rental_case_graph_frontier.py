"""Material accounting cannot be replaced by convenient persisted flags."""
from copy import deepcopy

from againward.domains.rental.case_graph_frontier import materiality_frontier
from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review
from tests.test_rental_case_graph_relations import occurrences, PAIR


def test_reviewed_evidence_is_accounted_for_but_not_a_readiness_claim(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    result = materiality_frontier(graph)
    assert result["accounted_for"] and not result["blockers"]
    assert set(result["observations"].values()) == {"USED"}
    assert "ready" not in result  # Required financial fields are checked separately.


def test_editing_disposition_or_issue_flags_cannot_hide_unreviewed_facts(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    for observation in graph["observations"].values():
        observation["disposition"] = "IRRELEVANT"
    for issue in graph["issues"].values():
        issue.update(state="RESOLVED", materiality="NON_MATERIAL")
    result = materiality_frontier(graph)
    assert not result["accounted_for"]
    assert set(result["observations"].values()) == {"UNRESOLVED"}


def test_rejected_or_irrelevant_fact_requires_current_independent_review(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [("SUPPORTING_RECORD", {"description": "Office address"})], review=False)
    oid = next(iter(graph["observations"]))
    graph = reduce_claim(graph, bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": oid,
        "value": "IRRELEVANT", "evidence_ids": [oid], "reason": "Address has no financial effect"}))
    claim = next(key for key, issue in graph["issues"].items() if issue["kind"] == "SEMANTIC_CLAIM")
    assert not materiality_frontier(graph)["accounted_for"]
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    assert materiality_frontier(graph)["accounted_for"]


def test_new_reader_rejection_and_limitation_are_never_silently_ignored(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    for kind in ("READING_REJECTION", "READING_LIMITATION", "EMPTY_READING", "FUTURE_ISSUE"):
        changed = deepcopy(graph)
        changed["issues"]["new"] = {"kind": kind, "observation_ids": [], "state": "RESOLVED",
            "source_id": None, "materiality": "NON_MATERIAL", "details": {}}
        result = materiality_frontier(changed)
        assert not result["accounted_for"]
        assert any(blocker["kind"] == kind for blocker in result["blockers"])


def test_two_supported_incompatible_values_still_block(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [
        ("SUPPORTING_RECORD", {"document_status": "ACCEPTED"}),
        ("SUPPORTING_RECORD", {"document_status": "ISSUED"})])
    ids = list(graph["observations"])
    # Exercise a conflict slot independent of source construction helpers.
    graph["issues"]["conflict"] = {"kind": "SEMANTIC_CONFLICT", "observation_ids": ids,
        "state": "RESOLVED", "source_id": None, "details": {}}
    assert any(row["target"] == "conflict" for row in materiality_frontier(graph)["blockers"])


def test_competing_supported_commercial_claims_cannot_both_pass_frontier(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    for value in ("RENTAL", "TRANSPORT"):
        graph = reduce_claim(graph, bind_claim(graph, {"kind": "CHARGE_MEANING", "target": targets[0],
            "value": value, "evidence_ids": list(graph["observations"]), "reason": "Competing interpretations"}))
        claim = next(key for key, issue in graph["issues"].items() if issue["kind"] == "SEMANTIC_CLAIM"
                     and issue["details"]["proposal"]["value"] == value)
        receipt = invoke_occurrence_review(graph, claim, root, model="scripted-reviewer")
        graph = reduce_review(graph, receipt, root)
    result = materiality_frontier(graph)
    assert not result["accounted_for"]
    assert any(row["kind"] == "COMMERCIAL_CLAIM_CONFLICT" for row in result["blockers"])


def test_latest_ambiguous_review_reopens_material_accounting(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    assert materiality_frontier(graph)["accounted_for"]
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Grouping not established"}, 0.1))
    receipt = invoke_occurrence_review(graph, targets[0], root, model="scripted-reviewer")
    graph = reduce_review(graph, receipt, root)
    result = materiality_frontier(graph)
    assert not result["accounted_for"]
    assert "UNRESOLVED" in result["observations"].values()


def test_unread_source_stays_visible_and_view_is_order_invariant(tmp_path, monkeypatch):
    _, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    graph["readings"] = {}
    before = deepcopy(graph)
    result = materiality_frontier(graph)
    assert any(row["kind"] == "SOURCE_UNREAD" for row in result["blockers"])
    reordered = {**graph, "observations": dict(reversed(list(graph["observations"].items()))),
                 "issues": dict(reversed(list(graph["issues"].items())))}
    assert materiality_frontier(reordered) == result
    assert graph == before
