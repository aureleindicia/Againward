"""Scripted synthetic analyst fixtures, never imported by the investigation engine.

These exercise software contracts only, not autonomous analyst performance.
"""
from againward.core.artifact_store import read_json, write_json
from againward.entrypoints import get_domain
from againward.evidence.cli import execute_case_query
from againward.domains.rental.workflow import record_assessments

def assessment(candidate, *, level="L2", status="A_CONSERVER_AVEC_RESERVES"):
    return {"finding_id": candidate["finding_id"], "status": status, "evidence_level": level,
        "best_reason_false": "A later accepted change could explain this difference.",
        "alternative_tests": [{"test_id": "T1", "description": "Inspect accepted source schedule and all supplied amendments.",
                               "result": "REFUTED", "evidence_refs": candidate["evidence_refs"]}],
        "limitations": ["Synthetic review validates software contracts, not legal entitlement."], "unresolved_questions": [],
        "confidence": {"level": "HIGH", "justification": "Source amounts and normalized charge scope compared explicitly."},
        "commercial_scope_reviewed": True, "operational_scope_reviewed": True, "identity_scope_reviewed": True,
        "claim_or_abstention": "Contract-supported arithmetic discrepancy, subject to review.",
        "evidence_query_ids": ["q1"], "evidence_handles": ["evh-example"]}


def query_sources(root, query_id="q1"):
    state = read_json(root / "investigation_state.json")
    fields = {field["key"] for field in read_json(root / "evidence_dataset.json")["fields"]}
    request = root / (query_id + "-request.json")
    write_json(request, {"query_id": query_id, "dataset_id": state["evidence_plane"]["dataset_id"],
        "operation": "raw_slice", "arguments": {"fields": [f for f in ("record_type", "record_id", "rate", "amount_minor") if f in fields], "limit": 100},
        "purpose": "Test fixture: compare source charges, accepted terms and operational events."})
    return execute_case_query(root, request)


def synthetic_review(root, *, query_id="q1"):
    response = query_sources(root, query_id)
    handle = response["retrieval_handles"][0]["handle"]
    candidates = read_json(root / "prepared_analysis.json")["candidates"]
    assessments = []
    for candidate in candidates:
        item = assessment(candidate)
        item.update(evidence_level=candidate["evidence_level"], evidence_query_ids=[query_id], evidence_handles=[handle])
        if candidate["evidence_level"] == "L1":
            item.update(status="ABSTAIN", unresolved_questions=["Contractual/operational basis incomplete."])
        assessments.append(item)
    reviewed = record_assessments(root, assessments)
    hypotheses = [{"hypothesis_id": f["finding_id"], "observation": f["family"],
        "hypothesis": "Supplied documentary scope supports a discrepancy.", "best_reason_false": f["best_reason_false"],
        "tests_requested": [t["description"] for t in f["alternative_tests"]],
        "results": {k: f[k] for k in ("group_id", "difference", "currency", "recovery_grade_amount")},
        "alternative_explanations": [f["best_reason_false"]],
        "terminal_status": "information_insuffisante", "why_no_further_request": "Synthetic scope ends at supplied documents; actual recovery remains unknown.",
        "decision": "INSUFFISAMMENT_ETAYE" if f["status"] == "ABSTAIN" else f["status"], "confidence": f["confidence"],
        "evidence_query_ids": f["evidence_query_ids"], "evidence_handles": f["evidence_handles"]}
        for f in reviewed["findings"]]
    write_json(root / "investigation.json", {"ground_truth_used": False, "quantitative_source": "prepared_analysis.json",
        "evidence_plane_session": "evidence_query_session.json", "hypotheses": hypotheses})
    write_json(root / "review.json", {"ground_truth_used": False, "reviewed_hypotheses": [
        {"hypothesis_id": h["hypothesis_id"], "best_reason_false": h["best_reason_false"], "final_decision": h["decision"],
         "checks": {name: {"status": "passed", "evidence": "Synthetic test fixture exercises the review contract: " + name}
                    for name in get_domain("rental").review_checks}} for h in hypotheses]})
    return reviewed

