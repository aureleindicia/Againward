"""Synthetic lifecycle and delivery integration; approvals here are test fixtures only."""
import json

import pytest

from againward.core.artifact_store import read_json, write_json
from againward.core.workflow import prepare_investigation
from againward.core.client_lifecycle import record_existing_data_exhaustion, mark_finalizable
from againward.core.delivery import evaluate_delivery_gate
from againward.entrypoints import get_domain
from againward.evidence.cli import execute_case_query
from againward.domains.rental.workflow import record_assessments, recalculate
from againward.domains.rental.review_policy import RentalDeliveryPolicy, validate_current_review
from againward.domains.rental.reporting import render_report
from tests.test_rental_ingestion import write_packet
from tests.test_rental_findings import assessment


def query_sources(root, query_id="q1"):
    state = read_json(root / "investigation_state.json")
    request = root / (query_id + "-request.json")
    write_json(request, {"query_id": query_id, "dataset_id": state["evidence_plane"]["dataset_id"],
        "operation": "raw_slice", "arguments": {"fields": ["record_type", "record_id", "rate", "amount_minor"], "limit": 100},
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


def test_review_report_and_human_approval_bound_to_current_evidence(tmp_path):
    source, _ = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    validate_current_review(root)
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json", reviewed_sources=["agreement.txt", "invoice.csv"])
    mark_finalizable(root, conclusion_ref="investigation.json")
    report = render_report(root, "Synthetic analyst synthesis: EUR 150 discrepancy; no guaranteed recovery.")
    gate = evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())
    assert not gate["ready_for_delivery"]
    write_json(root / "human_review.json", {"status": "approved", "approved_for_delivery": True,
        "reviewer_role": "SYNTHETIC TEST REVIEWER", "reviewed_at_utc": "2026-09-18T08:00:00Z",
        "reviewed_artifact_hashes": report["reviewed_artifact_hashes"]})
    gate = evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())
    assert gate["ready_for_delivery"], gate["blocking_reasons"]
    (root / "report.md").write_text("Altered claim")
    assert not evaluate_delivery_gate(root, policy=RentalDeliveryPolicy())["ready_for_delivery"]
    assert read_json(root / "investigation_state.json")["client_lifecycle"]["state"] == "FINALIZABLE"


def test_recalculation_archives_and_preserves_remaining_query_budget(tmp_path):
    source, packet = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    synthetic_review(root)
    old_session = read_json(root / "evidence_query_session.json")
    packet["actual_charges"][0]["net_amount"] = "800.00"
    revised = source.with_name("revised.json")
    revised.write_text(json.dumps(packet))
    result = recalculate(root, revised)
    assert result["review_required"]
    new_session = read_json(root / "evidence_query_session.json")
    assert new_session["budget"]["maximum_calls"] == old_session["budget"]["maximum_calls"] - 1
    assert list((root / "evidence_revisions").glob("*/rental_findings.json"))
    with pytest.raises(ValueError, match="stale"): validate_current_review(root)
    synthetic_review(root, query_id="q2")
    validate_current_review(root)
    with pytest.raises(ValueError, match="Unchanged"): recalculate(root, revised)


def test_stale_or_tampered_calculations_and_source_refuse_review(tmp_path):
    source, _ = write_packet(tmp_path / "source")
    root = tmp_path / "case"
    prepare_investigation(source, root, domain=get_domain("rental"))
    result = read_json(root / "prepared_analysis.json")
    result["groups"][0]["difference"] = "999.00"
    write_json(root / "prepared_analysis.json", result)
    with pytest.raises(ValueError, match="stale or altered"):
        record_assessments(root, [])
