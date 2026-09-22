"""Reproducible Rental contract tests; truth is consumed only by the scorer."""
from copy import deepcopy
from decimal import Decimal
from pathlib import Path
import time

from againward.core.artifact_store import read_json, write_json
from againward.core.client_lifecycle import (record_existing_data_exhaustion, publish_client_requests,
    record_canonical_answers, complete_resume, mark_finalizable, RESUME_DIMENSIONS)
from againward.core.workflow import prepare_investigation
from againward.domains.rental.models import RentalCase
from againward.domains.rental.reconciliation import reconcile
from againward.domains.rental.review_policy import validate_current_review
from againward.domains.rental.workflow import recalculate
from againward.entrypoints import get_domain
from .rental_cases import cases, write_sources, rental_packet
from .rental_review import query_sources, synthetic_review


def _blocking_request(finding_ids):
    return {"request_id": "RETURN-PROOF", "request_type": "REQUEST_EXISTING_DOCUMENT", "importance": "BLOCKING",
        "client_question": "Provide the signed return note identifying the full quantity under agreement A1, period PERIOD.",
        "internal_reason": "An unverified declaration cannot establish the contractual return boundary.",
        "target_role": "rental coordinator", "related_hypothesis_ids": finding_ids, "related_finding_ids": finding_ids,
        "hypotheses_distinguished": ["full documented return", "declaration only"],
        "answer_by_hypothesis": {"full documented return": "signed full return", "declaration only": "no signed return"},
        "plausible_answers": [{"answer_id": "SIGNED", "label": "Signed full return", "decision_effects": ["Recalculate the supported billing boundary."]},
            {"answer_id": "MISSING", "label": "No signed return", "decision_effects": ["Abstain from a recovery claim."]}],
        "decision_impact_dimensions": ["evidence_level", "false_conclusion_risk"],
        "expected_effort": "One existing return note", "effort": 1.0, "availability": 0.9, "reliability": 0.95,
        "source_cost": 0, "expected_source_type": "EXISTING_DOCUMENT"}


def exercise_resume(root, packet, sources_root):
    """Explicitly simulated client answer. Never used to bypass a real client's WAIT."""
    ids = [c["finding_id"] for c in read_json(root / "prepared_analysis.json")["candidates"]]
    query_sources(root, "before-answer")
    record_existing_data_exhaustion(root, analysis_inventory_ref="artifact_inventory.json",
        reviewed_sources=[d["path"] for d in packet["documents"]])
    wait = publish_client_requests(root, [_blocking_request(ids)])
    if wait["state"] != "WAITING_FOR_REQUIRED_INFORMATION":
        raise AssertionError("The material evidence request did not stop the case.")
    blocked = False
    try:
        query_sources(root, "forbidden-during-wait")
    except ValueError as exc:
        blocked = "STOP" in str(exc)
    if not blocked:
        raise AssertionError("WAIT did not block evidence queries.")
    revised = deepcopy(packet)
    revised["documents"][-1]["role"] = "RETURN_NOTE"
    revised["events"][0]["verification"] = "DOCUMENTED"
    source = write_sources(sources_root / "answer", revised)
    resumed = record_canonical_answers(root, [{"answer_id": "SYNTHETIC-ANSWER", "request_id": "RETURN-PROOF",
        "answer": "Synthetic signed full-quantity return on 2026-09-05.", "provided_by_role": "SYNTHETIC rental coordinator",
        "source_or_evidence": str(source.parent / "return.txt"), "source_type": "EXISTING_DOCUMENT",
        "provided_at_utc": "2026-09-18T09:00:00Z", "reliability": 0.95}])
    recalculation = recalculate(root, source)
    reviewed = synthetic_review(root, query_id="after-answer")
    validate_current_review(root)
    complete_resume(root, recalculation_refs=["prepared_analysis.json", "rental_findings.json"], adversarial_review_ref="review.json",
        before_after=[{"hypothesis_id": fid, "before": "Unverified return; no supported amount.",
            "after": "Signed complete return; EUR 300 contractual discrepancy, recovery not guaranteed.",
            "decision_dimensions": {key: "Reassessed against the signed full return; recorded in review.json." for key in RESUME_DIMENSIONS}}
            for fid in ids])
    final = mark_finalizable(root, conclusion_ref="investigation.json")
    return {"states": [wait["state"], resumed["state"], recalculation["state"], final["client_lifecycle"]["state"]],
            "wait_query_blocked": blocked, "request_count": len(wait["selected"]),
            "after_answer_supported_discrepancy": read_json(root / "prepared_analysis.json")["totals_by_currency"]["EUR"]["supported_positive_discrepancy"],
            "recovery_grade_totals": reviewed["recovery_grade_totals_by_currency"], "review_validated": True,
            "synthetic_answer": True, "human_approval_fabricated": False}


def run_benchmark(output):
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise ValueError("Use an empty benchmark output directory to preserve previous traces.")
    output.mkdir(parents=True, exist_ok=True)
    packets, truth = cases()
    observed = {}
    for name, packet in packets.items():
        source = write_sources(output / "sources" / name, packet)
        root = output / "cases" / name
        prepare_investigation(source, root, domain=get_domain("rental", profile="construction"))
        result = read_json(root / "prepared_analysis.json")
        observed[name] = {"supported_discrepancy": result["totals_by_currency"]["EUR"]["supported_positive_discrepancy"],
            "families": sorted({c["family"] for c in result["candidates"]}),
            "candidate_count": len(result["candidates"]), "automatic_recovery_claims": sum(c["recoverable_amount"] is not None for c in result["candidates"])}
        if packet["credits"]:
            actual = result["actual_ledger"]
            observed[name]["credit_accounting"] = {
                "issued_credit": format(sum((Decimal(row["issued_credit"]) for row in actual["entries"]), Decimal(0)), ".2f"),
                "unallocated_credit": format(sum((Decimal(row["net_amount"]) for row in actual.get("unallocated_credits", [])), Decimal(0)), ".2f"),
                "group_difference": result["groups"][0]["difference"]}
        if name == "R06_ambiguous_return":
            observed[name]["resume"] = exercise_resume(root, packet, output / "sources" / name)
        else:
            synthetic_review(root)
            validate_current_review(root)
    # Only the scorer sees expectations, after all participant calculations/reviews.
    tp = fp = fn = tn = 0
    for name, expected in truth.items():
        result = observed[name]
        positive = result["supported_discrepancy"] != "0.00"
        tp += positive and expected["positive_supported_case"]
        fp += positive and not expected["positive_supported_case"]
        fn += not positive and expected["positive_supported_case"]
        tn += not positive and not expected["positive_supported_case"]
        result["passed"] = (result["supported_discrepancy"] == expected["supported_discrepancy"]
            and set(expected["required_families"]) <= set(result["families"])
            and ("credit_accounting" not in expected or result.get("credit_accounting") == expected["credit_accounting"])
            and result["automatic_recovery_claims"] == 0)
    resume = observed["R06_ambiguous_return"]["resume"]
    observed["R06_ambiguous_return"]["passed"] &= (resume["after_answer_supported_discrepancy"] == "300.00"
        and resume["states"] == ["WAITING_FOR_REQUIRED_INFORMATION", "RESUMING", "RESUMING", "FINALIZABLE"]
        and resume["request_count"] == 1 and resume["wait_query_blocked"])
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    report = {"schema_version": "againward-rental-benchmark-v1", "cases": observed,
        "passed": sum(r["passed"] for r in observed.values()), "total": len(observed),
        "metrics": {"unit": "case-level supported positive discrepancy, not candidate-family or agent quality",
                    "true_positives": tp, "false_positives": fp, "false_negatives": fn, "true_negatives": tn,
                    "precision": precision, "recall": recall, "F1": 2 * precision * recall / (precision + recall) if precision + recall else 0},
        "limits": ["Small explicit contract fixtures, not unseen vendor-document accuracy.",
                   "Reviews and the R06 answer are scripted synthetic fixtures, not autonomous agent or human approval.",
                   "No real client data or ground truth provided to the engine."]}
    write_json(output / "scorer_ground_truth.json", truth)
    write_json(output / "validation.json", report)
    return report


def benchmark_performance(sizes=(1000, 10000)):
    results = []
    for size in sizes:
        packet = rental_packet()
        packet["items"], packet["periods"], packet["terms"], packet["actual_charges"] = [], [], [], []
        base = rental_packet()
        for n in range(size):
            pid, iid = f"P{n}", f"ITEM{n}"
            packet["items"].append({**base["items"][0], "item_id": iid})
            packet["periods"].append({**base["periods"][0], "period_id": pid, "item_id": iid})
            packet["terms"].append({**base["terms"][0], "period_id": pid, "term_id": f"T{n}"})
            packet["actual_charges"].append({**base["actual_charges"][0], "period_id": pid, "invoice_line_id": str(n), "net_amount": "700", "unit_rate": "700"})
        started = time.perf_counter()
        result = reconcile(RentalCase.from_dict(packet))
        results.append({"invoice_lines": size, "seconds": round(time.perf_counter() - started, 6),
                        "groups": len(result["groups"]), "candidates": len(result["candidates"])})
    return {"scope": "canonical validation plus both ledgers and reconciliation; excludes document extraction and report I/O",
            "measurements": results}
