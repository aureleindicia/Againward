"""Generic V2 originals → calculation → independent QA → existing client PDF."""
from copy import deepcopy
import json
from pathlib import Path

from pypdf import PdfReader
import pytest

from againward.core.artifact_store import read_json
from againward.documents.contracts import DocumentError, SourceBatch
from againward.domains.rental.case_graph import empty_graph, replay_evidence, state_hash
from againward.domains.rental.case_graph_delivery import investigate_to_report, load_calculated_package
from againward.domains.rental.case_post_calculation import invoke_qa, reduce_objections, verify_qa, validate_response
from againward.domains.rental.domain_pack import RentalDomainPack
from tests.test_rental_case_graph_adapter import complete_graph
from tests.test_rental_case_investigator import atomic_ask, generic_provider

PASS = {"verdict": "PASS", "objections": []}
ALTERNATIVE = "An external adjustment could explain the documentary difference."


def report_ask(prompt, images, **kwargs):
    if 'Report atomic observations' in prompt or 'Independently review one proposed' in prompt:
        return atomic_ask(prompt, images, **kwargs)
    context = json.loads(prompt.rsplit('\n', 1)[1])
    citations = [{"source_id": source["source_id"], "location": source["units"][0]["location"],
                  "quote": source["units"][0]["text"].splitlines()[0]} for source in context["original_sources"]]
    if "internal Rental analyst" in prompt:
        return {"assessments": [{"finding_id": row["finding_id"], "status": "A_CONSERVER_AVEC_RESERVES",
            "evidence_level": "L2", "best_reason_false": ALTERNATIVE,
            "alternative_tests": [{"test_id": "external-adjustment", "description": ALTERNATIVE,
                "result": "UNRESOLVED", "evidence_ref_indices": list(range(len(row["evidence_refs"])))}],
            "limitations": ["External adjustments have not been supplied."],
            "unresolved_questions": ["Ask for any subsequent adjustment."],
            "confidence": {"level": "MEDIUM", "justification": "Original accepted scope and invoice compared."},
            "commercial_scope_reviewed": True, "operational_scope_reviewed": True,
            "identity_scope_reviewed": True,
            "claim_or_abstention": "Documentary difference only; no recovery established."}
            for row in context["reconciliation"]["candidates"]]}, .1
    if "internal report author" in prompt:
        return {"synthesis": "La facture a été comparée aux conditions acceptées. Un écart documentaire reste à clarifier. Demander les éventuels ajustements au fournisseur avant toute réclamation. Aucun recouvrement n’est démontré."}, .1
    if "Independent adversarial report QA" in prompt:
        assert context["actual_pdf_text"] if "actual_pdf_text" in context else context["pdf_text"]
        return {"verdict": "PASS", "source_citations": citations, "unsupported_claims": [],
            "missed_discrepancies": [], "financial_check": "Documentary arithmetic matches the supplied calculation; no recovery claim.",
            "correction_guidance": ""}, .1
    return {"verdict": "PASS", "source_citations": citations, "missed_discrepancies": [],
        "reviewed_findings": [{"finding_id": row["finding_id"], "best_reason_false": ALTERNATIVE,
            "checks": {name: {"status": "passed", "evidence": "Original scope, invoice and deterministic calculation checked with reservations."}
                for name in RentalDomainPack.review_checks}} for row in context["reconciliation"]["candidates"]]}, .1


def ready_provider(context):
    return {"issue_id": context["issue_id"], "action": {"type": "PROPOSE_READY"}}


def test_originals_atomic_investigator_qa_report_actual_pdf(tmp_path, monkeypatch):
    root, prepared, _ = complete_graph(tmp_path, monkeypatch)
    graph = empty_graph(SourceBatch.from_dict(prepared["batch"]))
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", report_ask)
    monkeypatch.setattr("againward.domains.rental.autonomous_report._ask", report_ask)
    output = tmp_path / "report"
    result = investigate_to_report(graph, root, output, model="scripted-synthetic",
        provider=generic_provider, qa_provider=lambda c: PASS, evaluation_only=True)
    assert result["status"] == "EVALUATION_ONLY_QA_PASSED", result
    assert len(result["rounds"]) == 1
    assert result["calculation"]["groups"][0]["difference"] == "5.00"
    assert result["calculation"]["groups"][0]["expected_amount"] == "34.00"
    pdf = output / "rental_client_report.pdf"
    text = '\n'.join(page.extract_text() for page in PdfReader(pdf).pages)
    assert "5.00" in text and "34.00" in text
    assert "NOT FOR CLIENT DELIVERY" in text
    assert not result["report"]["human_approval"] and not result["report"]["approved_for_delivery"]
    assert replay_evidence(result["graph"], root) == result["graph"]
    package = read_json(Path(result["package"]))
    assert package["schema_version"] == "againward-rental-graph-calculated-case-v2"
    case, lineage = load_calculated_package(package, root)
    pack = read_json(output / "rental_evidence_pack.json")
    assert pack["document_lineage"] == lineage
    assert pack["document_lineage"]["post_calculation_qa_sha256"] == result["rounds"][0]["qa_receipt_sha256"]
    assert set(pack["document_lineage"]["observations"]) == set(result["graph"]["observations"])
    refs = read_json(output / "evidence_dataset.json")["provenance"]["rows"]
    assert all(ref["source_id"] in case.documents_by_id for rows in refs.values() for ref in rows)


def test_qa_cannot_mutate_graph_or_claim_human(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    before = deepcopy(graph)
    def malicious(context):
        context["subjects"].clear()
        context["material_evidence"].clear()
        context["case"]["terms"].clear()
        return PASS
    sha = invoke_qa(graph, root, model="synthetic", provider=malicious)
    assert graph == before
    receipt = verify_qa(graph, sha, root)
    assert receipt["reviewer_role"] == "MODEL"
    with pytest.raises(DocumentError):
        invoke_qa(graph, root, model="synthetic", provider=lambda c: {**PASS, "reviewer_role": "HUMAN"})
    assert graph == before


@pytest.mark.parametrize("defect", ["foreign", "invented", "cosmetic", "same_value", "vague"])
def test_invalid_objection_cannot_reopen_or_alter_graph(tmp_path, monkeypatch, defect):
    root, graph, targets = complete_graph(tmp_path, monkeypatch)
    target = targets[1]
    rate = next(oid for oid, row in graph["observations"].items() if row["semantic_type"] == "rate")
    objection = {"target": target, "field": "rate", "expected_value": "18.00", "observation_ids": [rate],
        "reason": "The original amendment establishes a different applicable rate."}
    if defect == "foreign":
        objection["target"] = targets[0]
    elif defect == "invented":
        objection["observation_ids"] = ["fabricated"]
    elif defect == "cosmetic":
        objection["field"] = "description"
    elif defect == "same_value":
        objection["expected_value"] = "17.00"
    else:
        objection["reason"] = "Maybe wrong"
    before = deepcopy(graph)
    with pytest.raises(DocumentError):
        invoke_qa(graph, root, model="synthetic", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    assert graph == before
    assert replay_evidence(graph, root) == before


def test_qa_failure_cleanly_stops_without_report_or_positive_amount(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    before = state_hash(graph)
    def fail(context):
        raise DocumentError("MODEL_TRANSPORT_FAILURE", "Synthetic provider failure")
    result = investigate_to_report(graph, root, tmp_path / "report", model="synthetic", provider=ready_provider, qa_provider=fail)
    assert result["stop_reason"] == "POST_CALC_QA_FAILURE"
    assert result["calculation"] is result["report"] is None
    assert state_hash(result["graph"]) == before
    assert not (tmp_path / "report").exists()


def test_stale_qa_cannot_pass_after_original_source_changes(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    sha = invoke_qa(graph, root, model="synthetic", provider=lambda c: PASS)
    (root / graph["batch"]["documents"][0]["blob_path"]).write_text("changed")
    with pytest.raises(DocumentError):
        verify_qa(graph, sha, root)


@pytest.mark.parametrize("limit", [-1, 3, True])
def test_reopening_limit_is_bounded(limit):
    with pytest.raises(ValueError):
        investigate_to_report({}, Path('.'), Path('.'), model="synthetic", max_reopen_cycles=limit)


def graph_with_alternative(tmp_path, monkeypatch):
    """A historical source rate was locally excluded; QA can question that exclusion."""
    from againward.domains.rental.case_graph_reader import invoke_read, reduce_read
    from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
    from againward.domains.rental.case_graph_review import invoke_occurrence_review, reduce_review
    root, graph, targets = complete_graph(tmp_path, monkeypatch,
        scope_changes={"description": "Portable pump; historical rate: 18.00"})
    sid = graph["occurrences"][targets[1]]["source_id"]
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"observations": [{"semantic_type": "rate", "value": "18.00", "quote": "historical rate: 18.00"}], "limitations": []}, .1))
    graph = reduce_read(graph, invoke_read(graph, sid, root, model="scripted", role="RECOVERY"), root)
    oid = next(oid for oid, atom in graph["observations"].items() if atom["semantic_type"] == "rate" and atom["value"] == "18.00")
    proposal = {"kind": "OBSERVATION_DISPOSITION", "target": oid, "value": "IRRELEVANT", "evidence_ids": [oid],
        "reason": "Historical rate is explicitly labelled historical; current accepted rate governs."}
    graph = reduce_claim(graph, bind_claim(graph, proposal))
    claim = next(iid for iid, row in graph["issues"].items() if row.get("details", {}).get("proposal") == proposal)
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", report_ask)
    graph = reduce_review(graph, invoke_occurrence_review(graph, claim, root, model="scripted"), root)
    objection = {"target": targets[1], "field": "rate", "expected_value": "18.00", "observation_ids": [oid],
        "reason": "The other quoted rate could alter expected rental unless its historical scope is confirmed."}
    validate_response(graph, {"verdict": "OBJECT", "objections": [objection]})
    return root, graph, targets, objection


def resolving_provider(context):
    if context["issue"].get("kind") == "POST_CALC_OBJECTION":
        return {"issue_id": context["issue_id"], "action": {"type": "PROPOSE_CLAIM", "proposal": {
            "kind": "POST_CALC_RESOLUTION", "target": context["issue"]["target"], "value": "NO_MATERIAL_EFFECT",
            "evidence_ids": context["stored_issue"]["observation_ids"],
            "reason": "The alternative is explicitly historical; the current accepted rate remains applicable."}}}
    return generic_provider(context)


def test_valid_material_objection_reinvestigated_recalculated_and_pdf(tmp_path, monkeypatch):
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    before = deepcopy(graph["observations"])
    monkeypatch.setattr("againward.domains.rental.autonomous_report._ask", report_ask)
    calls = []
    def qa(context):
        calls.append(context["calculation"])
        return {"verdict": "OBJECT", "objections": [objection]} if len(calls) == 1 else PASS
    output = tmp_path / "report"
    result = investigate_to_report(graph, root, output, model="scripted-synthetic",
        provider=resolving_provider, qa_provider=qa, max_reopen_cycles=1, evaluation_only=True)
    assert result["status"] == "EVALUATION_ONLY_QA_PASSED", result
    assert len(result["rounds"]) == 2 and len(calls) == 2
    assert [row["qa_verdict"] for row in result["rounds"]] == ["OBJECT", "PASS"]
    assert all(row["investigator_status"] == "SUPPORTED_DETERMINISTIC" for row in result["rounds"])
    assert result["graph"]["observations"] == before
    issues = {iid: row for iid, row in result["graph"]["issues"].items() if row["kind"] == "POST_CALC_OBJECTION"}
    assert len(issues) == 1 and result["remaining_issues"] == {}
    resolutions = [row for row in result["graph"]["issues"].values()
                   if row.get("details", {}).get("proposal", {}).get("kind") == "POST_CALC_RESOLUTION"]
    assert len(resolutions) == 1 and resolutions[0]["state"] == "RESOLVED"
    assert (output / "rental_client_report.pdf").is_file()
    assert replay_evidence(result["graph"], root) == result["graph"]


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_repeated_verified_objection_stops_at_cycle_limit(tmp_path, monkeypatch, limit):
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    result = investigate_to_report(graph, root, tmp_path / "report", model="scripted",
        provider=resolving_provider, qa_provider=lambda c: {"verdict": "OBJECT", "objections": [objection]}, max_reopen_cycles=limit)
    assert result["stop_reason"] == "REOPEN_BUDGET_EXHAUSTED", result
    assert len(result["rounds"]) == limit + 1
    assert result["remaining_issues"] and result["calculation"] is result["report"] is None
    assert replay_evidence(result["graph"], root) == result["graph"]
    assert not (tmp_path / "report").exists()


def test_unreviewed_objection_resolution_never_bypasses_readiness(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_readiness import evaluate_readiness
    from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    receipt = invoke_qa(graph, root, model="scripted", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    reopened = reduce_objections(graph, receipt, root)
    assert graph["observations"] == reopened["observations"]
    assert graph["occurrences"] == reopened["occurrences"]
    assert graph["relations"] == reopened["relations"]
    iid = next(iid for iid, row in reopened["issues"].items() if row["kind"] == "POST_CALC_OBJECTION")
    proposal = {"kind": "POST_CALC_RESOLUTION", "target": iid, "value": "NO_MATERIAL_EFFECT",
        "evidence_ids": objection["observation_ids"], "reason": "Historical rate is excluded by the current accepted agreement."}
    proposed = reduce_claim(reopened, bind_claim(reopened, proposal))
    assert evaluate_readiness(proposed, root)["status"] == "UNRESOLVED"
    proposed["issues"][iid]["state"] = "RESOLVED"
    with pytest.raises(DocumentError):
        evaluate_readiness(proposed, root)


def test_resolution_review_keeps_only_real_local_dependencies(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
    from againward.domains.rental.case_graph_review import current_review, invoke_occurrence_review, reduce_review
    from againward.domains.rental.case_graph_reader import invoke_read, reduce_read
    root, graph, targets, objection = graph_with_alternative(tmp_path, monkeypatch)
    sha = invoke_qa(graph, root, model="synthetic", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    graph = reduce_objections(graph, sha, root)
    target = next(iid for iid, row in graph["issues"].items() if row["kind"] == "POST_CALC_OBJECTION")
    proposal = {"kind": "POST_CALC_RESOLUTION", "target": target, "value": "NO_MATERIAL_EFFECT",
        "evidence_ids": objection["observation_ids"], "reason": "Historical rate does not apply to the current accepted rental."}
    graph = reduce_claim(graph, bind_claim(graph, proposal))
    cid = next(iid for iid, row in graph["issues"].items() if row.get("details", {}).get("proposal") == proposal)
    graph = reduce_review(graph, invoke_occurrence_review(graph, cid, root, model="synthetic"), root)
    original = current_review(graph, cid)
    assert original["verdict"] == "SUPPORTED"
    # New reading in the unrelated invoice does not alter the objection's term prerequisites.
    sid = graph["occurrences"][targets[0]]["source_id"]
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"observations": [{"semantic_type": "description", "value": "Record 0", "quote": "Record 0"}], "limitations": []}, .1))
    other = reduce_read(graph, invoke_read(graph, sid, root, model="synthetic", role="RECOVERY"), root)
    assert current_review(other, cid) == original
    # An actual change to the prerequisite term review invalidates the resolution.
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", lambda *a, **k:
        ({"verdict": "AMBIGUOUS", "reason": "The historical rate applicability remains materially ambiguous."}, .1))
    changed = reduce_review(graph, invoke_occurrence_review(graph, targets[1], root, model="synthetic"), root)
    assert current_review(changed, cid) is None
    assert changed["observations"] == graph["observations"]


def test_correction_resolution_requires_actual_reviewed_correction(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_claims import bind_claim, reduce_claim
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    sha = invoke_qa(graph, root, model="synthetic", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    graph = reduce_objections(graph, sha, root)
    target = next(iid for iid, row in graph["issues"].items() if row["kind"] == "POST_CALC_OBJECTION")
    proposal = {"kind": "POST_CALC_RESOLUTION", "target": target, "value": "CORRECTED",
        "evidence_ids": objection["observation_ids"], "reason": "Pretend that the graph was corrected without changing its reviewed rate."}
    rejected = reduce_claim(graph, bind_claim(graph, proposal))
    assert rejected["actions"][-1]["rejection_code"] == "EXTRACTION_INCOMPLETE"
    assert rejected["issues"] == graph["issues"]


def test_reopening_budget_persists_across_restart(tmp_path, monkeypatch):
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    def qa(context):
        return {"verdict": "OBJECT", "objections": [objection]}
    first = investigate_to_report(graph, root, tmp_path / "report", model="synthetic",
        provider=resolving_provider, qa_provider=qa)
    assert first["stop_reason"] == "REOPEN_BUDGET_EXHAUSTED"
    count = sum(event["type"] == "POST_CALC_OBJECTION" for event in first["graph"]["actions"])
    assert count == 2
    again = investigate_to_report(first["graph"], root, tmp_path / "report", model="synthetic",
        provider=resolving_provider, qa_provider=qa)
    assert again["stop_reason"] == "REOPEN_BUDGET_EXHAUSTED" and len(again["rounds"]) == 1
    assert sum(event["type"] == "POST_CALC_OBJECTION" for event in again["graph"]["actions"]) == count


def test_native_package_rejects_forged_qa_and_stale_head(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph import commit_transition
    from againward.domains.rental.case_graph_adapter import load_graph_case
    from againward.domains.rental.reconciliation import reconcile
    from againward.evidence.hashing import stable_hash
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    graph = commit_transition(graph, root, lambda current: current)
    sha = invoke_qa(graph, root, model="scripted", provider=lambda c: PASS)
    case, _ = load_graph_case(graph, root)
    package = {"schema_version": "againward-rental-graph-calculated-case-v2", "graph": graph,
        "qa_receipt_sha256": sha, "case_sha256": stable_hash(case.to_dict()),
        "calculation_sha256": stable_hash(reconcile(case))}
    assert load_calculated_package(package, root)[0].to_dict() == case.to_dict()
    wrong = deepcopy(package)
    wrong["calculation_sha256"] = '0' * 64
    with pytest.raises(DocumentError):
        load_calculated_package(wrong, root)
    from againward.core.artifact_store import write_json
    receipt = read_json(root / "case_graph_v2" / "post_calculation_qa" / (sha + '.json'))
    receipt["reviewer_role"] = "HUMAN"
    body = {key: value for key, value in receipt.items() if key != "receipt_sha256"}
    forged = stable_hash(body)
    write_json(root / "case_graph_v2" / "post_calculation_qa" / (forged + '.json'), {**body, "receipt_sha256": forged})
    wrong["qa_receipt_sha256"] = forged
    with pytest.raises(DocumentError):
        load_calculated_package(wrong, root)
    write_json(root / "case_graph_v2" / "head.json", {"graph_sha256": '0' * 64})
    with pytest.raises(DocumentError):
        load_calculated_package(package, root)


def test_commercial_qa_challenge_never_grants_new_authority(tmp_path, monkeypatch):
    from againward.domains.rental.case_graph_claims import current_claims
    root, graph, targets = complete_graph(tmp_path, monkeypatch)
    target = targets[1]
    ids = [oid for key in ("document_status", "agreement_id", "asset_id", "rate") for oid in graph["occurrences"][target]["fields"][key]]
    objection = {"target": target, "field": "GOVERNING_TERM", "expected_value": "NOT_GOVERNING",
        "observation_ids": ids, "reason": "The accepted term's scope must be challenged against its cited asset and period."}
    sha = invoke_qa(graph, root, model="synthetic", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    reopened = reduce_objections(graph, sha, root)
    assert {claim["proposal"]["value"] for claim in current_claims(reopened, "GOVERNING_TERM", target)} == {"GOVERNING"}
    assert reopened["occurrences"] == graph["occurrences"]
    assert reopened["observations"] == graph["observations"]
    objection["expected_value"] = "INVENTED_AUTHORITY"
    with pytest.raises(DocumentError):
        validate_response(graph, {"verdict": "OBJECT", "objections": [objection]})


def test_default_independent_qa_invocation_uses_verified_projection(tmp_path, monkeypatch):
    root, graph, _ = complete_graph(tmp_path, monkeypatch)
    calls = []
    def ask(prompt, images, **kwargs):
        payload = json.loads(prompt.rsplit('\n', 1)[1])
        assert payload["calculation"]["groups"][0]["difference"] == "5.00"
        assert payload["material_evidence"] and payload["report_candidates"] and payload["claims"]
        assert 'actions' not in payload and 'issues' not in payload
        calls.append(payload)
        return PASS, .1
    monkeypatch.setattr("againward.domains.rental.autonomous_review._ask", ask)
    receipt = invoke_qa(graph, root, model="scripted")
    assert len(calls) == 1
    assert verify_qa(graph, receipt, root)["response"] == PASS


def test_new_verified_objection_invalidates_earlier_pass_at_same_graph(tmp_path, monkeypatch):
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    old = invoke_qa(graph, root, model="scripted", provider=lambda c: PASS)
    current = invoke_qa(graph, root, model="scripted", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    with pytest.raises(DocumentError, match="REVIEW_STALE"):
        verify_qa(graph, old, root)
    assert verify_qa(graph, current, root)["response"]["verdict"] == "OBJECT"
    reopened = reduce_objections(graph, current, root)
    # A later inspection at the old prefix must not invalidate historical replay.
    invoke_qa(graph, root, model="scripted", provider=lambda c: {"verdict": "OBJECT", "objections": [objection]})
    assert replay_evidence(reopened, root) == reopened


def test_budget_stop_objection_cannot_be_dismissed_by_fresh_pass(tmp_path, monkeypatch):
    root, graph, _, objection = graph_with_alternative(tmp_path, monkeypatch)
    stopped = investigate_to_report(graph, root, tmp_path / "report", model="scripted",
        provider=ready_provider, qa_provider=lambda c: {"verdict": "OBJECT", "objections": [objection]}, max_reopen_cycles=0)
    assert stopped["stop_reason"] == "REOPEN_BUDGET_EXHAUSTED"
    sha = stopped["rounds"][0]["qa_receipt_sha256"]
    resumed = investigate_to_report(stopped["graph"], root, tmp_path / "report", model="scripted",
        provider=ready_provider, qa_provider=lambda c: PASS)
    assert resumed["status"] == "UNRESOLVED" and resumed["stop_reason"] == "POST_CALC_QA_FAILURE"
    assert resumed["calculation"] is resumed["report"] is None
    assert resumed["remaining_issues"]
    assert verify_qa(stopped["graph"], sha, root)["response"]["verdict"] == "OBJECT"
    assert not (tmp_path / "report").exists()
