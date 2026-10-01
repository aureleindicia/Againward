"""A quarantined read is resolved locally only through current source review."""
import json

from againward.domains.rental.case_graph import replay_evidence
from againward.domains.rental.case_graph_actions import apply_action, bind_action
from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim, current_claims
from againward.domains.rental.case_graph_frontier import materiality_frontier
from againward.domains.rental.case_graph_reader import invoke_read, reduce_read
from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review, current_review
from tests.test_rental_case_graph_reader import source, scripted
from tests.test_rental_case_graph_relations import occurrences


def reading_with_gap(tmp_path, monkeypatch, *, review=True):
    root, graph, doc = source(tmp_path)
    scripted(monkeypatch, [{"semantic_type": "invoice_id", "value": "NX-8", "quote": "NX-8"},
                           {"semantic_type": "invoice_id", "value": "NX-8", "quote": "Paraphrased document number"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted", role="PRIMARY")
    graph = reduce_read(graph, receipt, root)
    ids = list(graph["observations"])
    graph = apply_action(graph, bind_action(graph, {"type": "DECLARE_OCCURRENCE", "kind": "SUPPORTING_RECORD",
        "evidence_ids": ids, "anchor_ids": ids}), root)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "SUPPORTED", "reason": "Scripted source review"}, 0.1))
    if review:
        receipt = invoke_occurrence_review(graph, next(iter(graph["occurrences"])), root, model="scripted")
        graph = reduce_review(graph, receipt, root)
    issue = next(key for key, row in graph["issues"].items() if row["kind"] == "READING_REJECTION")
    return root, graph, doc, issue


def propose(graph, issue):
    return reduce_claim(graph, bind_claim(graph, {"kind": "READING_ISSUE_RESOLUTION", "target": issue,
        "value": "RECOVERED", "evidence_ids": list(graph["observations"]),
        "reason": "The same identifier was independently bound to its exact source quotation"}))


def test_recovered_gap_requires_review_of_the_actual_failed_observation(tmp_path, monkeypatch):
    root, graph, _, issue = reading_with_gap(tmp_path, monkeypatch)
    graph = propose(graph, issue)
    claim = next(key for key, row in graph["issues"].items() if row["kind"] == "SEMANTIC_CLAIM")
    assert not materiality_frontier(graph)["accounted_for"]

    def review(prompt, images, **kwargs):
        payload = json.loads(prompt.split("\n", 1)[1])
        raw = payload["original_source"]["reading_issue"]["rejected_model_observation"]
        assert raw["quote"] == "Paraphrased document number"
        assert payload["original_source"]["sources"][0]["units"]
        return {"verdict": "SUPPORTED", "reason": "Exact identifier recovered; invalid quote remains rejected"}, 0.1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", review)
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted")
    graph = reduce_review(graph, receipt, root)
    assert materiality_frontier(graph)["accounted_for"]
    assert len(graph["observations"]) == 1
    assert graph["issues"][issue]["kind"] == "READING_REJECTION"
    assert replay_evidence(graph, root) == graph


def test_recovery_cannot_promote_unreviewed_evidence(tmp_path, monkeypatch):
    root, graph, _, issue = reading_with_gap(tmp_path, monkeypatch, review=False)
    result = propose(graph, issue)
    assert result["actions"][-1]["rejection_code"] == "REVIEW_STALE"
    assert not materiality_frontier(result)["accounted_for"]
    assert replay_evidence(result, root) == result


def test_ambiguous_recovery_verdict_does_not_clear_reading_issue(tmp_path, monkeypatch):
    root, graph, _, issue = reading_with_gap(tmp_path, monkeypatch)
    graph = propose(graph, issue)
    claim = next(key for key, row in graph["issues"].items() if row["kind"] == "SEMANTIC_CLAIM")
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask",
        lambda *a, **k: ({"verdict": "AMBIGUOUS", "reason": "Gap not fully answered"}, 0.1))
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted")
    graph = reduce_review(graph, receipt, root)
    assert not current_claims(graph, "READING_ISSUE_RESOLUTION", issue)
    assert any(row["target"] == issue for row in materiality_frontier(graph)["blockers"])


def test_new_source_evidence_invalidates_a_prior_gap_resolution(tmp_path, monkeypatch):
    root, graph, doc, issue = reading_with_gap(tmp_path, monkeypatch)
    graph = propose(graph, issue)
    claim = next(key for key, row in graph["issues"].items() if row["kind"] == "SEMANTIC_CLAIM")
    receipt = invoke_occurrence_review(graph, claim, root, model="scripted")
    graph = reduce_review(graph, receipt, root)
    assert current_review(graph, claim)
    scripted(monkeypatch, [{"semantic_type": "net_amount", "value": "46.00", "quote": "46.00"}])
    receipt = invoke_read(graph, doc.source_id, root, model="scripted", role="RECOVERY")
    graph = reduce_read(graph, receipt, root)
    assert current_review(graph, claim) is None
    assert not materiality_frontier(graph)["accounted_for"]
    assert replay_evidence(graph, root) == graph


def test_existing_disposition_claim_journal_keeps_its_validator(tmp_path, monkeypatch):
    root, graph, _, _ = reading_with_gap(tmp_path, monkeypatch)
    oid = next(iter(graph["observations"]))
    action = bind_claim(graph, {"kind": "OBSERVATION_DISPOSITION", "target": oid,
        "value": "IRRELEVANT", "evidence_ids": [oid], "reason": "Old proposed disposition"})
    old = reduce_claim(graph, action, validator_version="rental-graph-claims-v1")
    assert replay_evidence(old, root) == old


def test_reading_gap_cannot_be_closed_using_a_foreign_source(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [
        ("SUPPORTING_RECORD", {"invoice_id": "DOC-A"}),
        ("SUPPORTING_RECORD", {"invoice_id": "DOC-B"})])
    sid = graph["occurrences"][targets[0]]["source_id"]
    scripted(monkeypatch, [{"semantic_type": "invoice_id", "value": "DOC-A", "quote": "Not literal"}])
    receipt = invoke_read(graph, sid, root, model="scripted", role="RECOVERY")
    graph = reduce_read(graph, receipt, root)
    issue = next(key for key, row in graph["issues"].items() if row["kind"] == "READING_REJECTION")
    foreign = graph["occurrences"][targets[1]]["fields"]["invoice_id"]
    result = reduce_claim(graph, bind_claim(graph, {"kind": "READING_ISSUE_RESOLUTION", "target": issue,
        "value": "RECOVERED", "evidence_ids": foreign, "reason": "Cannot borrow another document number"}))
    assert result["actions"][-1]["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert replay_evidence(result, root) == result
