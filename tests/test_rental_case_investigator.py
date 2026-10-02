"""Generic issue-driven V2 integration, adversarial stops and deterministic money."""
from copy import deepcopy
import json

import pytest

from againward.core.artifact_store import read_json
from againward.documents.contracts import DocumentError, SourceBatch
from againward.domains.rental.case_graph import empty_graph, replay_evidence, state_hash
from againward.domains.rental.case_graph_actions import bind_action, reduce_action
from againward.domains.rental.case_graph_reader import invoke_read, reduce_read
from againward.domains.rental.case_graph_review import current_review, invoke_occurrence_review, reduce_review
from againward.domains.rental.case_investigator import Budget, investigate
from againward.domains.rental.case_investigator_context import progress_view
from tests.test_rental_case_graph_adapter import complete_graph
from tests.test_rental_case_graph_relations import occurrences, PAIR


def run(graph, root, actions, **kwargs):
    iterator = iter(actions)
    def provider(context):
        action = next(iterator)
        return {"issue_id": context["issue_id"], "action": action(context) if callable(action) else action}
    return investigate(graph, root, model="synthetic", provider=provider, **kwargs)


def review(context):
    return {"type": "REQUEST_REVIEW", "target": next(iter(context["occurrences"]))}


def test_issue_resolved_by_one_review_action_and_replayed(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    result = run(graph, root, [review], budget=Budget(max_turns=1))
    assert current_review(result["graph"], targets[0])["verdict"] == "SUPPORTED"
    assert result["turns"][0]["pre_state_hash"] != result["turns"][0]["post_state_hash"]
    assert replay_evidence(result["graph"], root) == result["graph"]
    assert result["calculation"] is None


def test_rejected_action_machine_feedback_then_successful_correction(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    def correct(context):
        assert context["feedback"]["rejection_code"] == "SOURCE_LOCATION_INVALID"
        return review(context)
    result = run(graph, root, [{"type": "ATTACH_OBSERVATIONS", "target": targets[0], "evidence_ids": ["invented"]}, correct],
                 budget=Budget(max_turns=2))
    assert result["metrics"]["rejected_actions"] == 1
    assert current_review(result["graph"], targets[0])["verdict"] == "SUPPORTED"
    assert result["turns"][0]["pre_state_hash"] == result["turns"][0]["post_state_hash"]


def test_local_repair_preserves_observations_and_stales_only_changed_subject(tmp_path, monkeypatch):
    root, graph, targets = complete_graph(tmp_path, monkeypatch)
    invoice, scope = targets
    original = [oid for group in graph["occurrences"][invoice]["fields"].values() for oid in group]
    sid = graph["occurrences"][invoice]["source_id"]
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"observations": [{"semantic_type": "description", "value": "Record 0", "quote": "Record 0"}], "limitations": []}, .1))
    graph = reduce_read(graph, invoke_read(graph, sid, root, model="synthetic", role="RECOVERY"), root)
    extra = next(oid for oid in graph["observations"] if oid not in original and graph["observations"][oid]["source_id"] == sid)
    graph = reduce_action(graph, bind_action(graph, {"type": "ATTACH_OBSERVATIONS", "target": invoice, "evidence_ids": [extra]}))
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"verdict": "AMBIGUOUS", "reason": "Extra description misassigned"}, .1))
    graph = reduce_review(graph, invoke_occurrence_review(graph, invoice, root, model="synthetic"), root)
    observations = deepcopy(graph["observations"])
    scope_review = current_review(graph, scope)
    result = run(graph, root, [{"type": "REPLACE_OBSERVATIONS", "target": invoice, "evidence_ids": original}],
                 budget=Budget(max_turns=1))
    assert result["turns"][0]["feedback"]["result"] == "ACCEPTED_PROPOSAL"
    assert result["graph"]["observations"] == observations
    assert current_review(result["graph"], scope) == scope_review
    assert current_review(result["graph"], invoice)["verdict"] == "SUPPORTED"
    assert current_review(graph, invoice)["verdict"] == "AMBIGUOUS"
    assert "description" not in result["graph"]["occurrences"][invoice]["fields"]
    assert replay_evidence(result["graph"], root) == result["graph"]


def test_ambiguity_stays_unresolved_without_positive_amount(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    result = run(graph, root, [{"type": "MARK_UNRESOLVED", "reason": "Two accepted amendments cannot be distinguished"}])
    assert result["status"] == "UNRESOLVED" and result["stop_reason"] == "MATERIAL_AMBIGUITY"
    assert result["calculation"] is result["rental_case"] is None
    assert result["graph"] == graph


@pytest.mark.parametrize("where", ["proposal", "review", "reread"])
def test_provider_failure_preserves_graph_and_prior_receipts(tmp_path, monkeypatch, where):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    before = deepcopy(graph)
    def fail(*args, **kwargs):
        raise DocumentError("MODEL_TRANSPORT_FAILURE", "Synthetic transport failure")
    if where == "proposal":
        result = investigate(graph, root, model="synthetic", provider=fail)
    else:
        monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", fail)
        action = review if where == "review" else lambda c: {"type": "REQUEST_REREAD",
            "source_id": c["sources"][0]["source_id"], "locations": [next(iter(c["observations"].values()))["location"]]}
        result = run(graph, root, [action])
    assert result["stop_reason"] == "PROVIDER_FAILURE"
    assert result["feedback"]["rejection_code"] == "MODEL_TRANSPORT_FAILURE"
    assert result["graph"] == before == graph
    assert replay_evidence(result["graph"], root) == graph


@pytest.mark.parametrize("budget,reason,count", [
    (Budget(max_turns=1), "TURN_BUDGET_EXHAUSTED", 1),
    (Budget(max_repeated_state=2), "REPEATED_SEMANTIC_STATE", 1),
    (Budget(max_stagnant_turns=2), "NO_NEW_EVIDENCE_OR_RESOLUTION", 2)])
def test_budget_and_no_progress_are_explicit(tmp_path, monkeypatch, budget, reason, count):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    result = run(graph, root, [{"type": "REFRESH_RELATIONS"}] * 8, budget=budget)
    assert result["stop_reason"] == reason and result["metrics"]["turns"] == count
    assert result["calculation"] is None


def test_repeated_rejection_stops_and_cannot_fabricate_human(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    def action(c):
        return {"type": "REQUEST_REVIEW", "target": next(iter(c["occurrences"])), "reviewer_role": "HUMAN"}
    result = run(graph, root, [action] * 4)
    assert result["stop_reason"] == "REPEATED_REJECTION"
    assert result["graph"]["reviews"] == {}
    assert result["metrics"]["rejected_actions"] == 2


@pytest.mark.parametrize("action", [{"type": "READY"}, {"type": "PROPOSE_READY"},
    {"type": "PROPOSE_READY", "status": "SUPPORTED_DETERMINISTIC"},
    {"type": "PROPOSE_CLAIM", "proposal": "bad shape"}])
def test_ready_never_bypasses_python_and_malformed_actions_are_feedback(tmp_path, monkeypatch, action):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    result = run(graph, root, [action], budget=Budget(max_turns=1))
    assert result["status"] == "UNRESOLVED"
    assert result["remaining_issues"] and result["calculation"] is None
    assert state_hash(result["graph"]) == state_hash(graph)


def test_provider_cannot_mutate_state_through_context(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    def malicious(context):
        context["observations"].clear()
        context["occurrences"].clear()
        return {"issue_id": context["issue_id"], "action": {"type": "MARK_UNRESOLVED", "reason": "No proof"}}
    result = investigate(graph, root, model="synthetic", provider=malicious)
    assert graph == result["graph"]


def test_semantic_progress_ignores_repeated_review_invocations(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    before = progress_view(graph)
    receipt = invoke_occurrence_review(graph, targets[0], root, model="synthetic")
    changed = reduce_review(graph, receipt, root)
    assert state_hash(graph) != state_hash(changed)
    assert progress_view(changed) == before


def test_complete_generic_graph_reaches_deterministic_calculation(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    result = run(graph, root, [{"type": "PROPOSE_READY"}])
    assert result["status"] == "SUPPORTED_DETERMINISTIC" and result["stop_reason"] == "CALCULATED"
    assert result["calculation"]["groups"][0]["difference"] == "5.00"
    assert result["calculation"]["groups"][0]["expected_amount"] == "34.00"
    assert result["remaining_issues"] == {}
    assert replay_evidence(result["graph"], root) == result["graph"]


def test_unresolved_observation_blocks_otherwise_complete_calculation(tmp_path, monkeypatch):
    root, graph, targets = complete_graph(tmp_path, monkeypatch)
    # A new unreviewed atomic observation from the original invoice.
    document = next(d for d in graph["batch"]["documents"] if d["source_id"] == graph["occurrences"][targets[0]]["source_id"])
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"observations": [{"semantic_type": "description", "value": "Record 0", "quote": "Record 0"}], "limitations": []}, .1))
    sha = invoke_read(graph, document["source_id"], root, model="synthetic", role="RECOVERY")
    graph = reduce_read(graph, sha, root)
    result = run(graph, root, [{"type": "PROPOSE_READY"}], budget=Budget(max_turns=1))
    assert result["status"] == "UNRESOLVED" and result["calculation"] is None
    assert result["remaining_issues"]


def atomic_ask(prompt, images, **kwargs):
    if 'Report atomic observations' in prompt:
        context = json.loads(prompt.rsplit('\n', 1)[1])
        rows = []
        for unit in context["units"]:
            for line in unit["text"].splitlines():
                if ': ' not in line:
                    continue
                field, value = line.split(': ', 1)
                if value in {'True', 'False'}:
                    value = value == 'True'
                elif field == 'minimum_days':
                    value = int(value)
                rows.append({"semantic_type": field, "value": value, "quote": line, "location": unit["location"]})
        return {"observations": rows, "limitations": []}, .1
    return {"verdict": "SUPPORTED", "reason": "Synthetic source-backed review"}, .1


def generic_provider(context):
    gap = context["issue"]
    kind = gap.get("kind")
    if kind == "SOURCE_UNREAD":
        action = {"type": "REQUEST_REREAD", "source_id": gap["target"], "locations": []}
    elif kind == "SEMANTIC_CLAIM":
        action = {"type": "REQUEST_REVIEW", "target": gap["target"]}
    elif any(review is None for review in context["reviews"].values()):
        action = {"type": "REQUEST_REVIEW", "target": next(t for t, r in context["reviews"].items() if r is None)}
    elif kind == "COMMERCIAL_REVIEW_REQUIRED":
        target = gap["target"]
        claim_kind = gap["field"]
        ids = [oid for group in context["occurrences"][target]["fields"].values() for oid in group]
        action = {"type": "PROPOSE_CLAIM", "proposal": {"kind": claim_kind, "target": target,
            "value": "RENTAL" if claim_kind == "CHARGE_MEANING" else "GOVERNING",
            "evidence_ids": ids, "reason": "Explicit source-supported terms and accepted status"}}
    elif context["observations"] and not context["occurrences"]:
        ids = list(context["observations"])
        fields = {row["semantic_type"] for row in context["observations"].values()}
        action = {"type": "DECLARE_OCCURRENCE", "kind": "INVOICE_LINE" if "invoice_id" in fields else "RENTAL_SCOPE",
            "evidence_ids": ids, "anchor_ids": ids}
    else:
        action = {"type": "PROPOSE_READY"}
    return {"issue_id": context["issue_id"], "action": action}


def test_sources_atomic_reader_loop_readiness_adapter_calculation(tmp_path, monkeypatch):
    root, prepared, _ = complete_graph(tmp_path, monkeypatch)
    graph = empty_graph(SourceBatch.from_dict(prepared["batch"]))
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", atomic_ask)
    result = investigate(graph, root, model="synthetic", provider=generic_provider)
    assert result["status"] == "SUPPORTED_DETERMINISTIC", result["turns"]
    assert result["calculation"]["groups"][0]["difference"] == "5.00"
    assert result["calculation"]["groups"][0]["limitations"] == []
    assert any(t["action"]["type"] == "REQUEST_REREAD" for t in result["turns"])
    assert all(review["reviewer_role"] == "MODEL" for review in result["graph"]["reviews"].values())
    assert replay_evidence(result["graph"], root) == result["graph"]
    head = read_json(root / "case_graph_v2" / "head.json")
    assert head["graph_sha256"] == result["final_graph_sha256"]


def test_reviewed_non_material_atom_does_not_block_calculation(tmp_path, monkeypatch):
    root, graph, targets = complete_graph(tmp_path, monkeypatch)
    sid = graph["occurrences"][targets[0]]["source_id"]
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"observations": [{"semantic_type": "description", "value": "Record 0", "quote": "Record 0"}], "limitations": []}, .1))
    graph = reduce_read(graph, invoke_read(graph, sid, root, model="synthetic", role="RECOVERY"), root)
    oid = next(oid for oid, row in graph["observations"].items() if row["source_id"] == sid and row["semantic_type"] == "description")
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"verdict": "SUPPORTED", "reason": "Record counter is not a financial term"}, .1))
    def disposition(context):
        return {"type": "PROPOSE_CLAIM", "proposal": {"kind": "OBSERVATION_DISPOSITION", "target": oid,
            "value": "IRRELEVANT", "evidence_ids": [oid], "reason": "Non-financial record counter"}}
    def claim_review(context):
        return {"type": "REQUEST_REVIEW", "target": context["issue"]["target"]}
    result = run(graph, root, [disposition, claim_review, {"type": "PROPOSE_READY"}])
    assert result["status"] == "SUPPORTED_DETERMINISTIC"
    assert result["lineage"]["frontier"]["observations"][oid] == "IRRELEVANT"
    assert result["calculation"]["groups"][0]["difference"] == "5.00"


def test_scoped_reader_coverage_never_declares_other_units_read(tmp_path, monkeypatch):
    from tests.test_rental_case_graph_reader import source
    from againward.domains.rental.case_graph_frontier import materiality_frontier
    root, graph, doc = source(tmp_path, "Invoice AAA.\nNet 53.00 EUR.")
    from againward.documents.readers import read_document
    units = read_document(doc, root).units
    assert len(units) == 2
    def ask(prompt, images, **kwargs):
        context = json.loads(prompt.rsplit('\n', 1)[1])
        assert len(context["units"]) == 1
        unit = context["units"][0]
        row = ({"semantic_type": "invoice_id", "value": "AAA", "quote": "AAA"} if 'AAA' in unit["text"]
               else {"semantic_type": "net_amount", "value": "53.00", "quote": "53.00"})
        return {"observations": [{**row, "location": unit["location"]}], "limitations": []}, .1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", ask)
    graph = reduce_read(graph, invoke_read(graph, doc.source_id, root, model="synthetic", role="PRIMARY", locations=[units[0].location]), root)
    blockers = materiality_frontier(graph)["blockers"]
    assert any(g["kind"] == "SOURCE_PARTIALLY_READ" and g["missing_locations"] == [units[1].location] for g in blockers)
    graph = reduce_read(graph, invoke_read(graph, doc.source_id, root, model="synthetic", role="RECOVERY", locations=[units[1].location]), root)
    assert not any(g["kind"] == "SOURCE_PARTIALLY_READ" for g in materiality_frontier(graph)["blockers"])
    assert replay_evidence(graph, root) == graph


def test_local_inspection_uses_exact_window_and_avoids_other_source(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0],
        ("RENTAL_SCOPE", {"agreement_id": "UNRELATED-LEASE", "asset_id": "OTHER-ASSET"})], review=False)
    seen = []
    def inspect(context):
        assert len(context["sources"]) == 1
        row = next(iter(context["observations"].values()))
        seen.append(row)
        return {"type": "INSPECT_SOURCE", "source_id": row["source_id"], "location": row["location"],
                "start": row["source_span"][0], "end": row["source_span"][1]}
    result = run(graph, root, [inspect], budget=Budget(max_turns=1))
    assert result["feedback"]["text"] == seen[0]["quote"]
    assert result["graph"] == graph
    assert result["metrics"]["model_calls_by_role"] == {"investigator": 1, "reader": 0, "review": 0}


def test_cross_source_action_does_not_expand_local_context(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0],
        ("RENTAL_SCOPE", {"agreement_id": "UNRELATED-LEASE", "asset_id": "OTHER-ASSET"})], review=False)
    def foreign(context):
        local = {row["source_id"] for row in context["observations"].values()}
        oid = next(oid for oid, row in graph["observations"].items() if row["source_id"] not in local)
        return {"type": "ATTACH_OBSERVATIONS", "target": next(iter(context["occurrences"])), "evidence_ids": [oid]}
    result = run(graph, root, [foreign], budget=Budget(max_turns=1))
    assert result["feedback"]["rejection_code"] == "SOURCE_LOCATION_INVALID"
    assert result["graph"] == graph


def test_failure_after_committed_progress_preserves_head_and_replay(tmp_path, monkeypatch):
    root, graph, targets = occurrences(tmp_path, monkeypatch, [PAIR[0]], review=False)
    def fail(context):
        raise RuntimeError("Synthetic provider crash")
    result = run(graph, root, [review, fail])
    assert result["stop_reason"] == "PROVIDER_FAILURE"
    assert current_review(result["graph"], targets[0])["verdict"] == "SUPPORTED"
    assert replay_evidence(result["graph"], root) == result["graph"]
    assert read_json(root / "case_graph_v2" / "head.json")["graph_sha256"] == result["final_graph_sha256"]


def test_equivalent_reviews_cannot_extend_budget_as_new_evidence(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, [PAIR[0]])
    result = run(graph, root, [review] * 8, budget=Budget(max_stagnant_turns=2, max_repeated_state=10))
    assert result["stop_reason"] == "NO_NEW_EVIDENCE_OR_RESOLUTION"
    assert result["metrics"]["turns"] == 2


def test_investigator_can_select_another_open_issue(tmp_path, monkeypatch):
    root, graph, _ = occurrences(tmp_path, monkeypatch, PAIR, review=False)
    selected = []
    def select(context):
        iid = next(row["issue_id"] for row in context["open_issues"] if row["issue_id"] != context["issue_id"])
        selected.append(iid)
        return {"type": "INSPECT_ISSUE", "target": iid}
    def stop(context):
        assert context["issue_id"] == selected[0]
        return {"type": "MARK_UNRESOLVED", "reason": "Material uncertainty"}
    result = run(graph, root, [select, stop])
    assert result["stop_reason"] == "MATERIAL_AMBIGUITY"
    assert result["graph"] == graph


def test_engine_limitation_cannot_be_returned_as_supported_amount(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    monkeypatch.setattr("againward.domains.rental.case_investigator.reconcile", lambda case:
        {"groups": [{"group_id": "synthetic-group", "difference": None, "limitations": ["unsupported_calendar"]}]})
    result = run(graph, root, [{"type": "PROPOSE_READY"}])
    assert result["status"] == "UNRESOLVED" and result["calculation"] is result["rental_case"] is None
    assert result["stop_reason"] == "DETERMINISTIC_ENGINE_UNSUPPORTED"
    assert result["remaining_issues"]
