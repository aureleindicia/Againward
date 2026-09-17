from copy import deepcopy

import pytest

from againward.domains.rental.findings import review_findings
from againward.domains.rental.models import RentalCase
from againward.domains.rental.reconciliation import reconcile
from tests.rental_fixtures import rental_packet
from tests.test_rental_pricing import add_return


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


def test_l2_numeric_gap_does_not_create_recovery_grade_amount():
    case = RentalCase.from_dict(rental_packet()); result = reconcile(case)
    reviewed = review_findings(case, result, [assessment(result["candidates"][0])])
    assert reviewed["recovery_grade_totals_by_currency"] == {}
    assert reviewed["findings"][0]["recovery_grade_amount"] is None
    assert reviewed["recoverable_amount"] is None


def test_l3_overlapping_families_have_single_deterministic_claim_basis():
    packet = rental_packet(); add_return(packet)
    case = RentalCase.from_dict(packet); result = reconcile(case)
    reviewed = review_findings(case, result, [assessment(c, level="L3", status="CONFIRME") for c in result["candidates"]])
    assert reviewed["recovery_grade_totals_by_currency"] == {"EUR": "450.00"}
    assert len(reviewed["recovery_groups"]) == 1
    assert not reviewed["unreviewed_candidate_ids"]


@pytest.mark.parametrize("mutation", ["open_question", "counterevidence", "missing_scope_review", "money_override", "unknown_reference"])
def test_recovery_grade_requires_supported_explicit_review(mutation):
    case = RentalCase.from_dict(rental_packet()); result = reconcile(case)
    review = assessment(result["candidates"][0], level="L3", status="CONFIRME")
    if mutation == "open_question": review["unresolved_questions"] = ["Was the rate amended?"]
    if mutation == "counterevidence": review["alternative_tests"][0]["result"] = "SUPPORTED"
    if mutation == "missing_scope_review": review["operational_scope_reviewed"] = False
    if mutation == "money_override": review["recoverable_amount"] = "9999"
    if mutation == "unknown_reference": review["alternative_tests"][0]["evidence_refs"] = [{"document_id": "UNKNOWN", "location": "page:1"}]
    with pytest.raises(ValueError): review_findings(case, result, [review])


def test_missing_contract_cannot_be_promoted_despite_asserted_confidence():
    packet = rental_packet(); packet["terms"] = []
    case = RentalCase.from_dict(packet); result = reconcile(case)
    review = assessment(result["candidates"][0], level="L3", status="CONFIRME")
    with pytest.raises(ValueError, match="L3"): review_findings(case, result, [review])
