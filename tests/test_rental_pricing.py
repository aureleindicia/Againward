from copy import deepcopy
from datetime import date
from decimal import Decimal

import pytest

from againward.domains.rental.models import RentalCase, decimal_value
from againward.domains.rental.pricing import build_expected_ledger, chargeable_days
from tests.rental_fixtures import rental_packet


def expected(packet):
    return build_expected_ledger(RentalCase.from_dict(packet))["entries"]


def test_weekly_contract_transport_and_waiver_are_deterministic():
    packet = rental_packet()
    base = packet["terms"][0]
    packet["terms"] += [
        {**base, "term_id": "TRANSPORT", "charge_key": "transport", "charge_type": "TRANSPORT", "billing_unit": "FIXED", "rate": "120"},
        {**base, "term_id": "WAIVER", "charge_key": "waiver", "charge_type": "DAMAGE_WAIVER", "billing_unit": "PERCENT", "rate": "8", "percentage_of": "hire"}]
    entries = {e["charge_key"]: e for e in expected(packet)}
    assert {k: e["amount"] for k, e in entries.items()} == {"hire": "700.00", "transport": "120.00", "waiver": "56.00"}
    assert all(e["evidence_refs"] and e["decision"] is None for e in entries.values())
    assert entries["waiver"]["base_charge_id"] == "PERIOD/hire"


@pytest.mark.parametrize("value", [0.1, True, "NaN", "Infinity", "-1", "1e100"])
def test_money_refuses_lossy_or_impossible_inputs(value):
    with pytest.raises(ValueError): decimal_value(value)


@pytest.mark.parametrize("field", ["rate", "discount_fraction", "minimum_days", "weekends_billable", "partial_period_policy"])
def test_missing_contractual_basis_never_becomes_zero_or_guessed_rate(field):
    packet = rental_packet()
    packet["terms"][0].pop(field)
    entry = expected(packet)[0]
    assert entry["amount"] is None
    assert entry["status"] == "UNKNOWN_CONTRACTUAL_BASIS"
    assert entry["limitations"]


def test_months_use_calendar_anniversaries_not_thirty_days():
    packet = rental_packet()
    packet["periods"][0].update(start="2026-01-31", end="2026-03-31")
    packet["terms"][0].update(billing_unit="MONTH", partial_period_policy="EXACT", rate="500")
    assert expected(packet)[0]["amount"] == "1000.00"
    packet["periods"][0]["end"] = "2026-03-01"
    assert expected(packet)[0]["amount"] is None


def test_daily_quantity_discount_weekend_and_minimum():
    packet = rental_packet()
    packet["terms"][0].update(billing_unit="DAY", rate="10.05", quantity="2", weekends_billable=False, discount_fraction="0.10")
    assert expected(packet)[0]["amount"] == "90.45"
    packet["terms"][0]["minimum_days"] = 10
    assert expected(packet)[0]["amount"] == "180.90"
    assert chargeable_days(date(2026, 9, 1), date(2026, 9, 8), weekends_billable=False) == 5


def add_return(packet, *, quantity="1", verification="DOCUMENTED"):
    packet["documents"].append({"document_id": "RETURN", "role": "RETURN_NOTE", "path": "return.txt", "sha256": "c" * 64, "status": "ACCEPTED"})
    packet["events"].append({"event_id": "E1", "period_id": "PERIOD", "event_type": "RETURNED", "date": "2026-09-05",
                             "quantity": quantity, "verification": verification,
                             "evidence_refs": [{"document_id": "RETURN", "location": "signed:1"}]})


def test_documented_return_applies_only_contract_stop_convention():
    packet = rental_packet()
    add_return(packet)
    entry = expected(packet)[0]
    assert entry["amount"] == "400.00"
    assert entry["end"] == "2026-09-05" and entry["shortened"]
    packet["terms"][0]["stop_event"] = "COLLECTED"
    assert expected(packet)[0]["amount"] == "700.00"


@pytest.mark.parametrize("quantity,verification", [("0.5", "DOCUMENTED"), ("1", "DECLARED"), (None, "DOCUMENTED")])
def test_partial_or_unverified_returns_abstain_from_expected_amount(quantity, verification):
    packet = rental_packet()
    add_return(packet, quantity=quantity, verification=verification)
    assert expected(packet)[0]["amount"] is None
    assert expected(packet)[0]["contradictions"]


def test_later_signed_extension_is_a_material_contradiction():
    packet = rental_packet()
    add_return(packet)
    packet["events"].append({"event_id": "E2", "period_id": "PERIOD", "event_type": "EXTENDED", "date": "2026-09-06",
        "extended_end": "2026-09-15", "verification": "DOCUMENTED", "evidence_refs": packet["terms"][0]["evidence_refs"]})
    entry = expected(packet)[0]
    assert entry["amount"] is None
    assert "authorized_extension_after_stop" in entry["contradictions"]


def test_accepted_amendment_supersedes_rate_but_proposal_does_not():
    packet = rental_packet()
    packet["documents"].append({"document_id": "AMEND", "role": "AMENDMENT", "path": "amend.txt", "sha256": "d" * 64, "status": "PROPOSED"})
    packet["terms"].append({**packet["terms"][0], "term_id": "RATE2", "rate": "850", "supersedes_term_id": "RATE",
                            "evidence_refs": [{"document_id": "AMEND", "location": "page:1"}]})
    assert expected(packet)[0]["amount"] == "700.00"
    packet["documents"][-1]["status"] = "ACCEPTED"
    assert expected(packet)[0]["amount"] == "850.00"


def test_invoice_alone_cannot_supply_contractual_rate_authority():
    packet = rental_packet()
    packet["terms"][0]["evidence_refs"] = packet["actual_charges"][0]["evidence_refs"]
    assert expected(packet)[0]["amount"] is None


def test_unknown_fields_duplicate_ids_and_bad_links_fail_loudly():
    packet = rental_packet()
    packet["terms"].append(deepcopy(packet["terms"][0]))
    with pytest.raises(ValueError, match="duplicate"): RentalCase.from_dict(packet)
    packet = rental_packet(); packet["periods"][0]["item_id"] = "MISSING"
    with pytest.raises(ValueError, match="unknown item"): RentalCase.from_dict(packet)
    packet = rental_packet(); packet["terms"][0]["machine_btp_type"] = "excavator"
    with pytest.raises(ValueError, match="unknown record"): RentalCase.from_dict(packet)
