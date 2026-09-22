from copy import deepcopy

import pytest

from againward.domains.rental.models import RentalCase
from againward.domains.rental.reconciliation import reconcile
from tests.rental_fixtures import rental_packet
from tests.test_rental_pricing import add_return


def run(packet): return reconcile(RentalCase.from_dict(packet))


def test_correct_invoice_has_no_candidate_or_recovery_amount():
    packet = rental_packet()
    packet["actual_charges"][0].update(net_amount="700.00", unit_rate="700")
    result = run(packet)
    assert result["candidates"] == []
    assert result["groups"][0]["difference"] == "0.00"
    assert result["recoverable_amount"] is None


def test_wrong_rate_is_exact_supported_gap_never_automatic_claim():
    result = run(rental_packet())
    finding = next(f for f in result["candidates"] if f["family"] == "WRONG_RATE")
    assert finding["difference"] == "150.00"
    assert finding["expected_amount"] == "700.00" and finding["actual_amount"] == "850.00"
    assert finding["evidence_level"] == "L2"
    assert finding["status"] == "CANDIDATE" and finding["recoverable_amount"] is None
    assert {r["document_id"] for r in finding["evidence_refs"]} == {"AGREEMENT", "INVOICE"}


def test_overlapping_wrong_rate_and_post_return_count_group_once():
    packet = rental_packet()
    add_return(packet)
    result = run(packet)
    assert {f["family"] for f in result["candidates"]} >= {"WRONG_RATE", "POST_RETURN_BILLING"}
    assert {f["group_id"] for f in result["candidates"]} == {result["groups"][0]["group_id"]}
    assert result["totals_by_currency"]["EUR"]["supported_positive_discrepancy"] == "450.00"


def test_duplicate_candidate_does_not_double_count_reconciliation():
    packet = rental_packet()
    packet["actual_charges"][0].update(net_amount="700.00", unit_rate="700")
    second = deepcopy(packet["actual_charges"][0]); second["invoice_line_id"] = "L2"
    packet["actual_charges"].append(second)
    result = run(packet)
    assert "DUPLICATE_BILLING" in {f["family"] for f in result["candidates"]}
    assert result["totals_by_currency"]["EUR"]["supported_positive_discrepancy"] == "700.00"
    assert all(f["recoverable_amount"] is None for f in result["candidates"])


def test_same_description_different_assets_are_not_duplicates():
    packet = rental_packet()
    packet["actual_charges"][0].update(net_amount="700.00", unit_rate="700")
    packet["items"].append({**packet["items"][0], "item_id": "ITEM2"})
    packet["periods"].append({**packet["periods"][0], "period_id": "PERIOD2", "item_id": "ITEM2"})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "period_id": "PERIOD2"})
    packet["actual_charges"].append({**packet["actual_charges"][0], "invoice_line_id": "L2", "period_id": "PERIOD2"})
    assert run(packet)["candidates"] == []


def test_unsupported_fee_and_missing_contract_remain_unquantified():
    packet = rental_packet()
    packet["terms"] = []
    packet["actual_charges"][0].update(charge_type="ENVIRONMENTAL_FEE", charge_key="environment")
    result = run(packet)
    assert "UNAUTHORIZED_FEE" in {f["family"] for f in result["candidates"]}
    assert all(f["evidence_level"] == "L1" and f["difference"] is None for f in result["candidates"])


def add_credit(packet, amount="150.00", status="ISSUED"):
    packet["documents"].append({"document_id": "CREDIT", "role": "CREDIT_NOTE", "path": "credit.txt", "sha256": "c" * 64, "status": "ACCEPTED"})
    packet["credits"].append({"credit_id": "CR1", "charge_id": "I1/L1", "currency": "EUR", "net_amount": amount,
                              "status": status, "evidence_refs": [{"document_id": "CREDIT", "location": "line:1"}]})


def test_correct_credit_offsets_gap_and_avoids_false_recovery():
    packet = rental_packet(); add_credit(packet)
    result = run(packet)
    assert result["candidates"] == []
    assert result["actual_ledger"]["entries"][0]["net_amount"] == "700.00"
    assert result["actual_ledger"]["entries"][0]["issued_credit"] == "150.00"


def test_promised_credit_is_not_treated_as_issued():
    packet = rental_packet(); add_credit(packet, status="PROMISED")
    result = run(packet)
    assert result["actual_ledger"]["entries"][0]["net_amount"] == "850.00"
    assert "PROMISED_CREDIT_NOT_APPLIED" in {f["family"] for f in result["candidates"]}
    assert result["totals_by_currency"]["EUR"]["supported_positive_discrepancy"] == "150.00"


def test_credit_cannot_exceed_charge_or_cross_currency():
    packet = rental_packet(); add_credit(packet, amount="900.00")
    with pytest.raises(ValueError, match="exceed"): run(packet)
    packet["credits"][0].update(net_amount="150.00", currency="USD")
    with pytest.raises(ValueError, match="same currency"): run(packet)


def test_unallocated_issued_credit_blocks_money_claim_without_silent_application():
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0].update(charge_id=None, allocation_state="UNALLOCATED_CREDIT")
    case = RentalCase.from_dict(packet)
    assert case.to_dict()["credits"][0]["allocation_state"] == "UNALLOCATED_CREDIT"
    result = reconcile(case)
    line = result["actual_ledger"]["entries"][0]
    assert line["issued_credit"] == "0.00" and line["net_amount"] == "850.00"
    assert result["actual_ledger"]["unallocated_credits"][0]["net_amount"] == "150.00"
    group = result["groups"][0]
    assert group["difference"] is None and group["recoverable_amount"] is None
    assert "unallocated_credit_requires_allocation:CR1" in group["limitations"]
    assert {ref["document_id"] for ref in group["evidence_refs"]} == {"AGREEMENT", "INVOICE", "CREDIT"}
    assert {f["family"] for f in result["candidates"]} == {"UNALLOCATED_CREDIT"}
    assert result["totals_by_currency"]["EUR"]["supported_positive_discrepancy"] == "0.00"


def test_unallocated_credit_blocks_all_same_currency_groups_but_no_other_currency():
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0].update(charge_id=None, allocation_state="UNALLOCATED_CREDIT")
    packet["periods"].append({**packet["periods"][0], "period_id": "PERIOD2"})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "period_id": "PERIOD2"})
    second = deepcopy(packet["actual_charges"][0]); second["invoice_line_id"] = "L2"
    second["period_id"] = "PERIOD2"
    packet["actual_charges"].append(second)
    third = deepcopy(second); third["invoice_line_id"] = "L3"; third["currency"] = "USD"
    packet["actual_charges"].append(third)
    result = run(packet)
    eur = [g for g in result["groups"] if g["currency"] == "EUR"]
    usd = next(g for g in result["groups"] if g["currency"] == "USD")
    assert len(eur) == 2 and all(g["difference"] is None for g in eur)
    assert usd["difference"] is None  # contractual currency mismatch, not the EUR credit
    assert "unallocated_credit_requires_allocation:CR1" not in usd["limitations"]
    assert "currency_mismatch_no_conversion" in usd["limitations"]


def test_partial_allocation_applies_only_documented_amount_and_blocks_remainder():
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0].update(allocation_state="PARTIALLY_ALLOCATED_CREDIT", allocated_amount="80.00")
    result = run(packet)
    assert result["actual_ledger"]["entries"][0]["issued_credit"] == "80.00"
    assert result["actual_ledger"]["entries"][0]["net_amount"] == "770.00"
    assert result["actual_ledger"]["unallocated_credits"][0]["net_amount"] == "70.00"
    assert result["groups"][0]["difference"] is None


def test_documented_invoice_id_limits_unallocated_credit_uncertainty():
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0].update(charge_id=None, allocation_state="UNALLOCATED_CREDIT", invoice_id="I1")
    packet["periods"].append({**packet["periods"][0], "period_id": "PERIOD2"})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "period_id": "PERIOD2"})
    second = deepcopy(packet["actual_charges"][0]); second.update(invoice_id="I2", period_id="PERIOD2")
    packet["actual_charges"].append(second)
    groups = run(packet)["groups"]
    by_period = {group["period_id"]: group for group in groups}
    assert by_period["PERIOD"]["difference"] is None
    assert by_period["PERIOD2"]["difference"] == "150.00"
    assert not by_period["PERIOD2"]["limitations"]


def test_credit_invoice_id_cannot_contradict_confirmed_line():
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0]["invoice_id"] = "I2"
    with pytest.raises(ValueError, match="contradicts"):
        run(packet)


@pytest.mark.parametrize("change", [
    {"allocation_state": "PARTIALLY_ALLOCATED_CREDIT", "allocated_amount": "160.00"},
    {"allocation_state": "PARTIALLY_ALLOCATED_CREDIT", "allocated_amount": "0.00"},
    {"allocation_state": "PARTIALLY_ALLOCATED_CREDIT"},
    {"charge_id": None},
    {"charge_id": None, "allocation_state": "UNALLOCATED_CREDIT", "allocated_amount": "50.00"},
])
def test_invalid_credit_allocation_refuses_analysis(change):
    packet = rental_packet(); add_credit(packet)
    packet["credits"][0].update(change)
    with pytest.raises(ValueError, match="allocation|credit|invoice line"):
        run(packet)


def test_currency_mismatch_never_becomes_an_arithmetic_claim():
    packet = rental_packet(); packet["actual_charges"][0]["currency"] = "USD"
    result = run(packet)
    assert result["groups"][0]["difference"] is None
    assert "currency_mismatch_no_conversion" in result["groups"][0]["limitations"]
