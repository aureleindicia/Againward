"""Exact bounded financial primitives; no authority/readiness or final-case claims."""
from __future__ import annotations

from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, ROUND_HALF_UP, localcontext
import re

from .protocol import BillingFailure

VERSION = "energy-billing-money-v1"
CONTEXT = Context(prec=128, rounding=ROUND_HALF_UP)
QUANTITY_UNITS = {"Wh": Decimal("0.001"), "kWh": Decimal("1"), "MWh": Decimal("1000")}
PRICE_UNITS = {"EUR/Wh": Decimal("1000"), "EUR/kWh": Decimal("1"), "EUR/MWh": Decimal("0.001")}
ROUNDING = {"HALF_UP_PER_LINE": ROUND_HALF_UP, "HALF_EVEN_PER_LINE": ROUND_HALF_EVEN}


def exact(value: str, *, signed: bool = False) -> Decimal:
    if not isinstance(value, str) or len(value) > 40 or not re.fullmatch(r"-?\d+(?:\.\d+)?", value):
        raise BillingFailure("OBSERVATION_INVALID", stage="MONEY", expected="plain exact decimal string", actual=value)
    result = Decimal(value)
    exponent = result.as_tuple().exponent
    if (not result.is_finite() or not isinstance(exponent, int) or abs(exponent) > 12
            or len(result.as_tuple().digits) > 24 or (not signed and result < 0)):
        raise BillingFailure("OBSERVATION_INVALID", stage="MONEY", expected="bounded finite decimal", actual=value)
    return result


def money_cents(amount_eur: str, *, signed: bool = False) -> int:
    with localcontext(CONTEXT):
        cents = exact(amount_eur, signed=signed) * Decimal(100)
        if cents != cents.to_integral_value():
            raise BillingFailure("OBSERVATION_INVALID", stage="MONEY", expected="amount with exact minor units")
        return int(cents)


def consumption_component(*, quantity: str, quantity_unit: str, price: str,
                          price_unit: str, rounding_rule: str) -> dict:
    """Calculate supplied vetted inputs; caller still owns authority and readiness.

    Unit conversion is explicit and recorded. No tariff defaults, implicit cents,
    currency conversion, tax or unproven invoice-level result is produced here.
    """
    for name, value, supported in (("quantity_unit", quantity_unit, QUANTITY_UNITS),
                                   ("price_unit", price_unit, PRICE_UNITS),
                                   ("rounding_rule", rounding_rule, ROUNDING)):
        if not isinstance(value, str) or value not in supported:
            raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="CALCULATION", path="$." + name,
                                 expected="explicit supported convention", actual=value)
    try:
        with localcontext(CONTEXT):
            quantity_kwh = exact(quantity) * QUANTITY_UNITS[quantity_unit]
            price_eur_kwh = exact(price) * PRICE_UNITS[price_unit]
            unrounded = quantity_kwh * price_eur_kwh
            rounded = unrounded.quantize(Decimal("0.01"), rounding=ROUNDING[rounding_rule])
            cents = int(rounded * Decimal(100))
            return {"rule_version": VERSION, "currency": "EUR", "formula": "quantity_kwh * price_eur_kwh",
                    "inputs": {"quantity": quantity, "quantity_unit": quantity_unit, "price": price,
                               "price_unit": price_unit, "rounding_rule": rounding_rule},
                    "quantity_kwh": format(quantity_kwh, "f"), "price_eur_kwh": format(price_eur_kwh, "f"),
                    "unrounded_eur": format(unrounded, "f"), "expected_cents": cents}
    except DecimalException as exc:
        raise BillingFailure("DETERMINISTIC_ENGINE_FAILURE", stage="CALCULATION",
                             expected="bounded decimal arithmetic", cause=type(exc).__name__) from exc
