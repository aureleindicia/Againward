"""Validate analyst decisions against calculated amounts and evidence ceilings.

This enforces a review contract. It does not judge whether natural-language
alternative tests are persuasive; adversarial and human review still own that.
"""
from __future__ import annotations

from decimal import Decimal

from againward.evidence.hashing import stable_hash
from .models import RentalCase, EvidenceRef
from .pricing import money
from .arithmetic import deterministic_decimal

DECISIONS = {"CONFIRME", "A_CONSERVER_AVEC_RESERVES", "INSUFFISAMMENT_ETAYE", "REJETE", "ABSTAIN"}
LEVELS = {"L1": 1, "L2": 2, "L3": 3}
_ASSESSMENT_FIELDS = {"finding_id", "status", "evidence_level", "best_reason_false", "alternative_tests",
    "limitations", "unresolved_questions", "confidence", "commercial_scope_reviewed", "operational_scope_reviewed",
    "identity_scope_reviewed", "claim_or_abstention", "evidence_query_ids", "evidence_handles"}


@deterministic_decimal
def review_findings(case: RentalCase, reconciliation: dict, assessments: list[dict]) -> dict:
    """Calculate approved evidence-grade amounts once per disjoint charge group.

    Assessment authors cannot provide an amount. An L3 decision must be explicit,
    supported by a known positive contractual discrepancy, scoped evidence review
    and completed alternative tests, with no unresolved question or contrary test.
    """
    candidates = {f["finding_id"]: f for f in reconciliation["candidates"]}
    if not isinstance(assessments, list):
        raise ValueError("Explicit analyst assessments must be a list.")
    reviewed, seen = [], set()
    recovery_groups = {}
    for assessment in assessments:
        if not isinstance(assessment, dict) or set(assessment) != _ASSESSMENT_FIELDS:
            raise ValueError("Closed Rental assessment schema required; no free monetary overrides.")
        fid = assessment["finding_id"]
        if fid not in candidates or fid in seen:
            raise ValueError("Unknown or duplicate finding assessment.")
        seen.add(fid)
        candidate = candidates[fid]
        status, level = assessment["status"], assessment["evidence_level"]
        if status not in DECISIONS or level not in LEVELS:
            raise ValueError("Unknown Rental decision or evidence level.")
        for field in ("best_reason_false", "claim_or_abstention"):
            if not isinstance(assessment[field], str) or not assessment[field].strip():
                raise ValueError(f"{field} is required.")
        for field in ("limitations", "unresolved_questions", "evidence_query_ids", "evidence_handles"):
            value = assessment[field]
            if not isinstance(value, list) or any(not isinstance(v, str) or not v.strip() for v in value):
                raise ValueError(f"{field}: list of explicit references/limitations required.")
        confidence = assessment["confidence"]
        if (not isinstance(confidence, dict) or set(confidence) != {"level", "justification"}
                or confidence["level"] not in {"LOW", "MEDIUM", "HIGH"}
                or not isinstance(confidence["justification"], str) or not confidence["justification"].strip()):
            raise ValueError("Analyst confidence must be explicit and justified.")
        for field in ("commercial_scope_reviewed", "operational_scope_reviewed", "identity_scope_reviewed"):
            if type(assessment[field]) is not bool:
                raise ValueError("Review attestations require booleans, never inferred defaults.")
        tests = assessment["alternative_tests"]
        if not isinstance(tests, list) or not tests:
            raise ValueError("Every reviewed finding needs an explicit alternative test or tested limitation.")
        allowed_refs = {(r["document_id"], r["location"]) for r in candidate["evidence_refs"]}
        test_ids = set()
        for test in tests:
            if (not isinstance(test, dict) or set(test) != {"test_id", "description", "result", "evidence_refs"}
                    or not isinstance(test["test_id"], str) or not test["test_id"].strip() or test["test_id"] in test_ids
                    or not isinstance(test["description"], str) or not test["description"].strip()
                    or test["result"] not in {"REFUTED", "SUPPORTED", "UNRESOLVED", "NOT_APPLICABLE"}
                    or not isinstance(test["evidence_refs"], list) or not test["evidence_refs"]):
                raise ValueError("Alternative tests need distinct IDs, result and existing source references.")
            test_ids.add(test["test_id"])
            for reference in test["evidence_refs"]:
                try:
                    ref = EvidenceRef(**reference)
                except TypeError as exc:
                    raise ValueError("Invalid test source reference.") from exc
                if (ref.document_id, ref.location) not in allowed_refs:
                    raise ValueError("Alternative test cites evidence outside this discrepancy scope.")
        if status in {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"} and (
                not assessment["evidence_query_ids"] or not assessment["evidence_handles"]):
            raise ValueError("Retained findings require materialized Evidence Plane queries and handles.")
        if level == "L2" and candidate["evidence_level"] != "L2":
            raise ValueError("Contract-supported grade requires a supported deterministic discrepancy.")
        recovery = None
        if level == "L3":
            if (status != "CONFIRME" or candidate["evidence_level"] != "L2"
                    or candidate["difference"] is None or Decimal(candidate["difference"]) <= 0
                    or candidate["limitations"] or assessment["unresolved_questions"]
                    or not all(assessment[f] for f in ("commercial_scope_reviewed", "operational_scope_reviewed", "identity_scope_reviewed"))
                    or any(t["result"] in {"SUPPORTED", "UNRESOLVED"} for t in tests)):
                raise ValueError("L3 recovery-grade policy is not satisfied; retain with reservations or abstain.")
            if candidate["family"] in {"POST_RETURN_BILLING", "POST_OFF_HIRE_BILLING"}:
                roles = {case.documents_by_id[r["document_id"]].role for r in candidate["evidence_refs"]}
                required = {"RETURN_NOTE", "EMAIL_EVIDENCE"} if candidate["family"] == "POST_RETURN_BILLING" else {"OFF_HIRE_NOTICE", "EMAIL_EVIDENCE"}
                if not roles & required:
                    raise ValueError("Post-hire claim requires specific operational evidence.")
            recovery = candidate["difference"]
            recovery_groups[candidate["group_id"]] = {"group_id": candidate["group_id"],
                "currency": candidate["currency"], "amount": recovery, "charge_ids": candidate["charge_ids"]}
        reviewed.append({**candidate, **assessment, "recovery_grade_amount": recovery,
                         "recoverable_amount": None, "human_review_required": True})
    totals = {}
    for group in recovery_groups.values():
        totals[group["currency"]] = totals.get(group["currency"], Decimal(0)) + Decimal(group["amount"])
    return {"schema_version": "againward-rental-reviewed-findings-v1", "ground_truth_used": False,
            "case_sha256": stable_hash(case.to_dict()), "reconciliation_sha256": stable_hash(reconciliation),
            "findings": reviewed, "unreviewed_candidate_ids": sorted(set(candidates) - seen),
            "recovery_groups": list(recovery_groups.values()),
            "recovery_grade_totals_by_currency": {c: money(v) for c, v in totals.items()},
            "recoverable_amount": None, "amount_policy": "evidence-grade claim basis, not guaranteed recovery or automatic delivery"}
