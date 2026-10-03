"""Minimal typed facts; construction is not authority approval."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re

from .money import exact, money_cents
from .protocol import BillingFailure


@dataclass(frozen=True)
class Period:
    start: date
    end: date

    def __post_init__(self):
        if type(self.start) is not date or type(self.end) is not date or self.start >= self.end:
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="nonempty half-open date period")

    @classmethod
    def from_iso(cls, start: str, end: str) -> Period:
        if (not isinstance(start, str) or not isinstance(end, str)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", start)
                or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", end)):
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="ISO date strings")
        try:
            return cls(date.fromisoformat(start), date.fromisoformat(end))
        except ValueError as exc:
            if isinstance(exc, BillingFailure):
                raise
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="valid calendar date") from exc

    def contains(self, period: Period) -> bool:
        return self.start <= period.start and period.end <= self.end


def _identity(supplier_id: str, pdl: str, currency: str, evidence_ids: tuple[str, ...]) -> None:
    if not isinstance(supplier_id, str) or not 1 <= len(supplier_id.strip()) <= 160:
        raise BillingFailure("OBSERVATION_INVALID", stage="IDENTITY", expected="bounded supplier identity")
    if not isinstance(pdl, str) or not re.fullmatch(r"\d{14}", pdl):
        raise BillingFailure("OBSERVATION_INVALID", stage="IDENTITY", expected="14-digit PDL/PRM")
    if currency != "EUR":
        raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", expected="EUR")
    if (not isinstance(evidence_ids, tuple) or not evidence_ids or len(evidence_ids) > 32
            or any(not isinstance(item, str) or not item for item in evidence_ids)
            or len(evidence_ids) != len(set(evidence_ids))):
        raise BillingFailure("EVIDENCE_BINDING_INVALID", stage="IDENTITY", expected="bounded distinct evidence references")


@dataclass(frozen=True)
class ConsumptionLine:
    invoice_id: str
    supplier_id: str
    pdl: str
    currency: str
    period: Period
    quantity: str
    quantity_unit: str
    billed_amount_eur: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self):
        _identity(self.supplier_id, self.pdl, self.currency, self.evidence_ids)
        if not isinstance(self.invoice_id, str) or not 1 <= len(self.invoice_id) <= 160:
            raise BillingFailure("OBSERVATION_INVALID", stage="IDENTITY", expected="invoice ID")
        if not isinstance(self.period, Period):
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="typed period")
        exact(self.quantity)
        money_cents(self.billed_amount_eur)


@dataclass(frozen=True)
class TariffTerm:
    contract_id: str
    supplier_id: str
    pdl: str
    currency: str
    effective_period: Period
    tariff_type: str
    price: str
    price_unit: str
    rounding_rule: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self):
        _identity(self.supplier_id, self.pdl, self.currency, self.evidence_ids)
        if not isinstance(self.contract_id, str) or not 1 <= len(self.contract_id) <= 160:
            raise BillingFailure("OBSERVATION_INVALID", stage="IDENTITY", expected="contract ID")
        if not isinstance(self.effective_period, Period):
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="typed effective period")
        exact(self.price)
