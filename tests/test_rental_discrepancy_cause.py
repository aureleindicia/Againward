"""A measured difference does not establish an unobserved billing cause."""
from decimal import Decimal

from againward.domains.rental.reconciliation import _families


def test_unexplained_rental_difference_does_not_invent_duration_error():
    actual = [{"charge_type": "RENTAL", "unapplied_promised_credit": "0.00",
               "invoiced_amount": "2250.00", "quantity": "4"}]
    expected = {"amount": "2100.00", "quantity": "4", "units": "7", "rate": "75"}
    assert _families(actual, expected, Decimal("150")) == ["DOCUMENTARY_CHARGE_DIFFERENCE"]
    assert _families(actual, expected, Decimal("0")) == []
    actual[0]["billed_units"] = "8"
    assert _families(actual, expected, Decimal("150")) == ["INCORRECT_DURATION"]
