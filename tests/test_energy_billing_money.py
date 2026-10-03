from dataclasses import replace
from decimal import ROUND_DOWN, localcontext
from fractions import Fraction

import pytest

from againward.domains.energy_billing.models import ConsumptionLine, Period, TariffTerm
from againward.domains.energy_billing.money import consumption_component, exact, money_cents
from againward.domains.energy_billing.protocol import BillingFailure


def component(**updates):
    inputs = {"quantity": "1375", "quantity_unit": "kWh", "price": "0.120",
              "price_unit": "EUR/kWh", "rounding_rule": "HALF_UP_PER_LINE"}
    return consumption_component(**{**inputs, **updates})


def test_exact_result_independent_of_callers_decimal_context():
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_DOWN
        result = component()
        # Independent rational reference, no Decimal implementation mirrored.
        reference = Fraction(1375) * Fraction(120, 1000) * 100
        assert reference.denominator == 1
        assert result["expected_cents"] == reference.numerator
        assert result["unrounded_eur"] == "165.000"
        assert money_cents("192.08") == 19208


@pytest.mark.parametrize("quantity,quantity_unit,price,price_unit", [
    ("1.375", "MWh", "120", "EUR/MWh"),
    ("1375000", "Wh", "0.00012", "EUR/Wh"),
    ("1375", "kWh", "120", "EUR/MWh"),
])
def test_explicit_energy_units_equivalent(quantity, quantity_unit, price, price_unit):
    assert component(quantity=quantity, quantity_unit=quantity_unit, price=price,
                     price_unit=price_unit)["expected_cents"] == component()["expected_cents"]


@pytest.mark.parametrize("quantity,half_up,half_even", [("1", 1, 0), ("3", 2, 2)])
def test_per_line_tie_rule_explicit(quantity, half_up, half_even):
    assert component(quantity=quantity, price="0.005")["expected_cents"] == half_up
    assert component(quantity=quantity, price="0.005", rounding_rule="HALF_EVEN_PER_LINE")["expected_cents"] == half_even


@pytest.mark.parametrize("value", [0.12, True, 12, "NaN", "Infinity", "1e3", "0,12", "-0.12", "9" * 41])
def test_no_float_nonfinite_locale_or_implicit_conversion(value):
    with pytest.raises(BillingFailure) as failure:
        exact(value)
    assert failure.value.code == "OBSERVATION_INVALID"


@pytest.mark.parametrize("update", [{"quantity_unit": "kW"}, {"price_unit": "USD/kWh"},
                                     {"rounding_rule": "INVOICE_ROUNDING"}])
def test_unsupported_conventions_explicit(update):
    with pytest.raises(BillingFailure) as failure:
        component(**update)
    assert failure.value.code == "UNSUPPORTED_DOMAIN_RULE"


def test_minor_units_never_silently_round_and_credit_is_explicit():
    with pytest.raises(BillingFailure):
        money_cents("1.001")
    with pytest.raises(BillingFailure):
        money_cents("-1.00")
    assert money_cents("-1.00", signed=True) == -100
    assert component(quantity="0")["expected_cents"] == 0


@pytest.mark.parametrize("start,end", [("2026-02-30", "2026-03-01"), ("2026-01-01", "2026-01-01"),
                                      ("2026-02-01", "2026-01-01"), ("20260101", "2026-02-01")])
def test_bad_period_is_local_error(start, end):
    with pytest.raises(BillingFailure) as failure:
        Period.from_iso(start, end)
    assert failure.value.code == "OBSERVATION_INVALID"


def test_boundary_date_and_required_evidence():
    period = Period.from_iso("2026-09-01", "2026-10-01")
    authority = Period.from_iso("2026-01-01", "2026-10-01")
    assert authority.contains(period)
    assert not authority.contains(Period.from_iso("2026-09-01", "2026-10-02"))
    line = ConsumptionLine("INV", "SUPPLIER", "01234567890123", "EUR", period, "1375", "kWh", "192.08", ("e1",))
    term = TariffTerm("CONTRACT", "SUPPLIER", "01234567890123", "EUR", authority, "FIXED", "0.120",
                      "EUR/kWh", "HALF_UP_PER_LINE", ("e2",))
    assert term.effective_period.contains(line.period)
    with pytest.raises(BillingFailure):
        replace(line, evidence_ids=())
    with pytest.raises(BillingFailure):
        replace(term, pdl="not-a-PDL")
