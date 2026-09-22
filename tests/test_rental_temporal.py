"""Independent unit-day arithmetic for documented partial returns and dated rates."""
from copy import deepcopy
from decimal import Decimal

import pytest

from againward.domains.rental.models import RentalCase
from againward.domains.rental.pricing import build_expected_ledger
from againward.domains.rental.reconciliation import reconcile
from tests.rental_fixtures import rental_packet


def packet():
    p = rental_packet()
    p["periods"][0].update(quantity="4", end="2026-09-18")
    p["terms"][0].update(quantity="4", billing_unit="DAY", rate="75.00", discount_fraction="0",
                          minimum_days=0, weekends_billable=True, stop_event="RETURNED",
                          stop_day_billable=False)
    p["actual_charges"][0].update(net_amount="5100.00", quantity="4", unit_rate="75.00",
                                   billed_units="17", end="2026-09-18")
    p["documents"].append({"document_id": "RETURN", "role": "RETURN_NOTE", "path": "return.txt",
                           "sha256": "c" * 64, "status": "ACCEPTED"})
    return p


def returning(p, date, quantity, label):
    p["events"].append({"event_id": label, "period_id": "PERIOD", "event_type": "RETURNED",
                         "date": date, "quantity": quantity, "verification": "DOCUMENTED",
                         "evidence_refs": [{"document_id": "RETURN", "location": f"signed:{label}"}]})


def amendment(p, date="2026-09-08", rate="60.00", *, status="ACCEPTED"):
    p["documents"].append({"document_id": "AMEND", "role": "AMENDMENT", "path": "amend.txt",
                           "sha256": "d" * 64, "status": status})
    p["terms"].append({**p["terms"][0], "term_id": "RATE2", "rate": rate,
                       "effective_from": date, "supersedes_term_id": "RATE",
                       "evidence_refs": [{"document_id": "AMEND", "location": "page:1/rate"}]})


def entry(p):
    return build_expected_ledger(RentalCase.from_dict(p))["entries"][0]


def test_two_partial_returns_conserve_unit_days_and_stop_last_units():
    p = packet()
    returning(p, "2026-09-10", "2", "R1")
    returning(p, "2026-09-17", "2", "R2")
    result = entry(p)
    # 4 units x 9 days + 2 units x 7 days = 50 unit-days.
    assert result["amount"] == "3750.00"
    assert result["shortened"] and result["end"] == "2026-09-17"
    assert [(s["quantity"], s["days"], s["rate"]) for s in result["segments"]] == [
        ("4", 9, "75.00"), ("2", 7, "75.00")]
    assert result["unit_days"] == "50"
    assert {r["document_id"] for r in result["evidence_refs"]} == {"AGREEMENT", "RETURN"}
    assert reconcile(RentalCase.from_dict(p))["groups"][0]["difference"] == "1350.00"


def test_effective_rate_and_partial_return_compose_without_retroactive_rate():
    p = packet()
    returning(p, "2026-09-10", "2", "R1")
    amendment(p)
    result = entry(p)
    # 4 x 7 x 75 + 4 x 2 x 60 + 2 x 8 x 60 = 3540.
    assert result["amount"] == "3540.00"
    assert [(s["quantity"], s["days"], s["rate"]) for s in result["segments"]] == [
        ("4", 7, "75.00"), ("4", 2, "60.00"), ("2", 8, "60.00")]
    assert {r["document_id"] for r in result["evidence_refs"]} == {"AGREEMENT", "RETURN", "AMEND"}
    assert reconcile(RentalCase.from_dict(p))["groups"][0]["difference"] == "1560.00"
    assert {c["family"] for c in reconcile(RentalCase.from_dict(p))["candidates"]} >= {"INCORRECT_QUANTITY"}


def test_proposed_amendment_does_not_change_original_daily_rate():
    p = packet()
    amendment(p, status="PROPOSED")
    assert entry(p)["amount"] == "5100.00"


@pytest.mark.parametrize("change", ["undocumented", "over_return", "missing_rule", "minimum", "fork", "extension"])
def test_material_ambiguity_remains_unknown(change):
    p = packet()
    returning(p, "2026-09-10", "2", "R1")
    if change == "undocumented":
        p["events"][0]["verification"] = "DECLARED"
    elif change == "over_return":
        returning(p, "2026-09-11", "3", "R2")
    elif change == "missing_rule":
        p["terms"][0].pop("stop_day_billable")
    elif change == "minimum":
        p["terms"][0]["minimum_days"] = 7
    elif change == "fork":
        amendment(p)
        p["documents"].append({"document_id": "AMEND2", "role": "AMENDMENT", "path": "second.txt",
                               "sha256": "e" * 64, "status": "ACCEPTED"})
        p["terms"].append({**p["terms"][-1], "term_id": "RATE3", "rate": "80.00",
                           "evidence_refs": [{"document_id": "AMEND2", "location": "page:1"}]})
    else:
        p["events"].append({"event_id": "EXT", "period_id": "PERIOD", "event_type": "EXTENDED",
                            "date": "2026-09-16", "extended_end": "2026-09-25", "verification": "DOCUMENTED",
                            "evidence_refs": p["terms"][0]["evidence_refs"]})
    result = entry(p)
    assert result["amount"] is None and result["status"] == "UNKNOWN_CONTRACTUAL_BASIS"
    assert result["limitations"] or result["contradictions"]
    assert reconcile(RentalCase.from_dict(p))["groups"][0]["difference"] is None


def test_stop_day_billable_delays_quantity_decrease_one_day():
    p = packet()
    returning(p, "2026-09-10", "2", "R1")
    p["terms"][0]["stop_day_billable"] = True
    # 4 x 10 days + 2 x 7 days = 54 unit-days.
    assert entry(p)["amount"] == "4050.00"


def test_conflicting_rate_date_is_not_chosen_by_list_order():
    p = packet()
    amendment(p)
    reverse = deepcopy(p)
    reverse["terms"].reverse()
    assert entry(p) == entry(reverse)


def test_decimal_amount_from_segments_uses_one_charge_rounding():
    p = packet()
    p["terms"][0]["rate"] = "0.005"
    returning(p, "2026-09-10", "2", "R1")
    # 4 x 9 + 2 x 8 = 52 exact unit-days, rounded once: 0.260.
    assert Decimal(entry(p)["amount"]) == Decimal("0.26")


def test_old_canonical_serialization_does_not_gain_null_effective_date():
    original = rental_packet()
    normalized = RentalCase.from_dict(original).to_dict()
    assert all("effective_from" not in term for term in normalized["terms"])
    assert normalized == RentalCase.from_dict(normalized).to_dict()
