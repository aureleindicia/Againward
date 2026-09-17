"""Versioned, generic rental records. No construction vocabulary or vendor parsing.

Money is net of tax in a declared two-decimal currency; values are decimal strings.
All dates are ISO dates and all periods are [start, end), after explicit extraction
of source conventions. Missing terms stay None and cannot silently become zero.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields
from datetime import date
from decimal import Decimal, InvalidOperation
from functools import cached_property
import re
from typing import Any

SCHEMA = "againward-rental-case-v1"
DOCUMENT_ROLES = frozenset({"RENTAL_AGREEMENT", "RATE_CARD", "QUOTE", "PURCHASE_ORDER", "AMENDMENT",
    "INVOICE", "CREDIT_NOTE", "DELIVERY_NOTE", "RETURN_NOTE", "OFF_HIRE_NOTICE", "EMAIL_EVIDENCE",
    "ASSET_LIST", "PAYMENT_EXPORT", "TEXT_NOTE", "UNKNOWN", "IRRELEVANT"})
EVENT_TYPES = frozenset({"BOOKED", "RESERVED", "DELIVERED", "ON_HIRE", "EXTENDED", "RATE_CHANGED",
    "OFF_HIRE_REQUESTED", "COLLECTION_REQUESTED", "COLLECTED", "RETURNED", "INVOICED", "CREDITED", "CANCELLED"})
CHARGE_TYPES = frozenset({"RENTAL", "TRANSPORT", "DELIVERY", "COLLECTION", "FUEL", "REFUELING",
    "DAMAGE_WAIVER", "ENVIRONMENTAL_FEE", "CONSUMABLE", "CLEANING", "SURCHARGE", "OTHER"})
BILLING_UNITS = frozenset({"DAY", "WEEK", "MONTH", "FIXED", "PERCENT"})
# Do not silently impose two decimal places on other currencies.
CURRENCIES = frozenset({"EUR", "USD", "GBP", "CHF", "CAD", "AUD", "NZD"})


def decimal_value(value, *, name="value", nonnegative=True) -> Decimal:
    if not isinstance(value, (str, int, Decimal)) or isinstance(value, bool):
        raise ValueError(f"{name}: exact decimal string required (no binary float).")
    try:
        result = Decimal(value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name}: invalid decimal.") from exc
    if not result.is_finite() or (nonnegative and result < 0):
        raise ValueError(f"{name}: finite nonnegative value required.")
    if len(result.as_tuple().digits) > 24 or abs(result.as_tuple().exponent) > 12:
        raise ValueError(f"{name}: decimal precision outside supported bounds.")
    return result


def iso_date(value: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        raise ValueError("ISO date YYYY-MM-DD required.")
    return date.fromisoformat(value)


def _identifier(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}", value):
        raise ValueError(f"{label}: stable nonempty identifier required.")


def _currency(value):
    if value not in CURRENCIES:
        raise ValueError("Unsupported or absent currency; no implicit conversion/rounding.")


@dataclass(frozen=True)
class EvidenceRef:
    document_id: str
    location: str
    field: str | None = None

    def __post_init__(self):
        _identifier(self.document_id, "document_id")
        if not isinstance(self.location, str) or not self.location.strip() or len(self.location) > 500:
            raise ValueError("Source extraction location required.")


def _evidence(value):
    if not isinstance(value, tuple) or not value or any(not isinstance(r, EvidenceRef) for r in value):
        raise ValueError("At least one source extraction reference required.")


@dataclass(frozen=True)
class Document:
    document_id: str
    role: str
    path: str
    sha256: str
    status: str = "EXTRACTED"

    def __post_init__(self):
        _identifier(self.document_id, "document_id")
        if self.role not in DOCUMENT_ROLES or self.status not in {"EXTRACTED", "ACCEPTED", "PROPOSED", "VOID"}:
            raise ValueError("Unknown document role/status.")
        if not isinstance(self.path, str) or not self.path.strip():
            raise ValueError("Document source path required.")
        if not re.fullmatch(r"[0-9a-f]{64}", self.sha256):
            raise ValueError("Document SHA-256 required.")


@dataclass(frozen=True)
class Party:
    party_id: str
    role: str
    evidence_refs: tuple[EvidenceRef, ...]

    def __post_init__(self):
        _identifier(self.party_id, "party_id")
        if self.role not in {"CLIENT", "SUPPLIER", "RENTAL_VENDOR"}:
            raise ValueError("Unknown rental party role.")
        _evidence(self.evidence_refs)


@dataclass(frozen=True)
class RentalItem:
    item_id: str
    description: str
    evidence_refs: tuple[EvidenceRef, ...]
    category: str | None = None
    supplier_item_id: str | None = None
    asset_id: str | None = None
    serial_number: str | None = None

    def __post_init__(self):
        _identifier(self.item_id, "item_id")
        _evidence(self.evidence_refs)


@dataclass(frozen=True)
class RentalPeriod:
    period_id: str
    agreement_id: str
    item_id: str
    supplier_id: str
    client_id: str
    start: str
    end: str
    quantity: str
    evidence_refs: tuple[EvidenceRef, ...]
    site_id: str | None = None
    cost_center_id: str | None = None

    def __post_init__(self):
        for key in ("period_id", "agreement_id", "item_id", "supplier_id", "client_id"):
            _identifier(getattr(self, key), key)
        if iso_date(self.end) <= iso_date(self.start):
            raise ValueError("Rental periods must be nonempty, with end exclusive.")
        if decimal_value(self.quantity, name="quantity") <= 0:
            raise ValueError("Positive contractual quantity required.")
        _evidence(self.evidence_refs)


@dataclass(frozen=True)
class RateTerm:
    term_id: str
    period_id: str
    charge_key: str
    charge_type: str
    currency: str
    evidence_refs: tuple[EvidenceRef, ...]
    billing_unit: str | None = None
    rate: str | None = None
    quantity: str | None = None
    weekends_billable: bool | None = None
    minimum_days: int | None = None
    partial_period_policy: str | None = None
    stop_event: str | None = None
    stop_day_billable: bool | None = None
    discount_fraction: str | None = None
    percentage_of: str | None = None
    tier_min_days: int | None = None
    tier_max_days: int | None = None
    supersedes_term_id: str | None = None

    def __post_init__(self):
        for key in ("term_id", "period_id", "charge_key"):
            _identifier(getattr(self, key), key)
        _currency(self.currency)
        _evidence(self.evidence_refs)
        if self.charge_type not in CHARGE_TYPES or self.billing_unit not in BILLING_UNITS | {None}:
            raise ValueError("Unknown charge type or billing unit.")
        for key in ("rate", "quantity", "discount_fraction"):
            if getattr(self, key) is not None:
                result = decimal_value(getattr(self, key), name=key)
                if key == "discount_fraction" and result > 1:
                    raise ValueError("Discount fraction exceeds one.")
        for key in ("minimum_days", "tier_min_days", "tier_max_days"):
            value = getattr(self, key)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError(f"{key}: nonnegative integer required.")
        if (self.tier_min_days is not None and self.tier_max_days is not None
                and self.tier_min_days > self.tier_max_days):
            raise ValueError("Reversed duration tier.")
        for key in ("weekends_billable", "stop_day_billable"):
            if getattr(self, key) is not None and type(getattr(self, key)) is not bool:
                raise ValueError(f"{key}: explicit boolean required.")
        if self.partial_period_policy not in {None, "EXACT", "STARTED", "PRORATA"}:
            raise ValueError("Unknown partial-period pricing convention.")
        if self.stop_event not in {None, "CONTRACT_END", "RETURNED", "COLLECTED", "OFF_HIRE_REQUESTED"}:
            raise ValueError("Unsupported contract stop trigger.")


@dataclass(frozen=True)
class RentalEvent:
    event_id: str
    period_id: str
    event_type: str
    date: str
    evidence_refs: tuple[EvidenceRef, ...]
    quantity: str | None = None
    extended_end: str | None = None
    verification: str = "DECLARED"

    def __post_init__(self):
        _identifier(self.event_id, "event_id")
        _identifier(self.period_id, "period_id")
        if self.event_type not in EVENT_TYPES or self.verification not in {"DECLARED", "DOCUMENTED"}:
            raise ValueError("Unknown rental event/verification status.")
        iso_date(self.date)
        if self.extended_end is not None:
            iso_date(self.extended_end)
            if self.event_type != "EXTENDED" or iso_date(self.extended_end) <= iso_date(self.date):
                raise ValueError("Invalid extension boundary.")
        if self.quantity is not None:
            decimal_value(self.quantity, name="event quantity")
        _evidence(self.evidence_refs)


@dataclass(frozen=True)
class ActualCharge:
    invoice_id: str
    invoice_line_id: str
    period_id: str
    charge_key: str
    charge_type: str
    currency: str
    net_amount: str
    evidence_refs: tuple[EvidenceRef, ...]
    start: str | None = None
    end: str | None = None
    quantity: str | None = None
    unit_rate: str | None = None
    billed_units: str | None = None

    @property
    def charge_id(self):
        return f"{self.invoice_id}/{self.invoice_line_id}"

    def __post_init__(self):
        for key in ("invoice_id", "invoice_line_id", "period_id", "charge_key"):
            _identifier(getattr(self, key), key)
        if self.charge_type not in CHARGE_TYPES:
            raise ValueError("Unknown invoice charge type.")
        _currency(self.currency)
        for key in ("net_amount", "quantity", "unit_rate", "billed_units"):
            if getattr(self, key) is not None:
                decimal_value(getattr(self, key), name=key)
        if decimal_value(self.net_amount).as_tuple().exponent < -2:
            raise ValueError("Invoice net amount must use currency minor units.")
        if (self.start is None) != (self.end is None):
            raise ValueError("Both invoiced period bounds are required together.")
        if self.start is not None and iso_date(self.end) <= iso_date(self.start):
            raise ValueError("Empty or reversed invoice period.")
        _evidence(self.evidence_refs)


@dataclass(frozen=True)
class Credit:
    credit_id: str
    charge_id: str
    currency: str
    net_amount: str
    evidence_refs: tuple[EvidenceRef, ...]
    status: str = "ISSUED"

    def __post_init__(self):
        _identifier(self.credit_id, "credit_id")
        _currency(self.currency)
        value = decimal_value(self.net_amount, name="credit amount")
        if value.as_tuple().exponent < -2 or self.status not in {"ISSUED", "PROMISED"}:
            raise ValueError("Invalid credit amount or status.")
        _evidence(self.evidence_refs)


_RECORD_TYPES = {"documents": Document, "parties": Party, "items": RentalItem,
                 "periods": RentalPeriod, "terms": RateTerm, "events": RentalEvent,
                 "actual_charges": ActualCharge, "credits": Credit}
_ID_FIELDS = {"documents": "document_id", "parties": "party_id", "items": "item_id",
              "periods": "period_id", "terms": "term_id", "events": "event_id",
              "actual_charges": "charge_id", "credits": "credit_id"}


@dataclass(frozen=True)
class RentalCase:
    documents: tuple[Document, ...]
    parties: tuple[Party, ...]
    items: tuple[RentalItem, ...]
    periods: tuple[RentalPeriod, ...]
    terms: tuple[RateTerm, ...]
    events: tuple[RentalEvent, ...]
    actual_charges: tuple[ActualCharge, ...]
    credits: tuple[Credit, ...]

    @classmethod
    def from_dict(cls, payload: dict[str, Any]):
        if (not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA
                or set(payload) != set(_RECORD_TYPES) | {"schema_version"}):
            raise ValueError("Unknown/incomplete Rental schema; explicit v1 extraction required.")
        decoded = {}
        for name, record_type in _RECORD_TYPES.items():
            if not isinstance(payload[name], list):
                raise ValueError(f"{name}: list required.")
            records = []
            for row in payload[name]:
                if not isinstance(row, dict) or set(row) - {f.name for f in fields(record_type)}:
                    raise ValueError(f"{name}: unknown record fields.")
                values = dict(row)
                if name != "documents":
                    refs = values.get("evidence_refs")
                    if not isinstance(refs, list):
                        raise ValueError(f"{name}: evidence_refs list required.")
                    try:
                        values["evidence_refs"] = tuple(EvidenceRef(**r) for r in refs)
                    except (TypeError, KeyError) as exc:
                        raise ValueError("Malformed extraction reference.") from exc
                try:
                    records.append(record_type(**values))
                except TypeError as exc:
                    raise ValueError(f"{name}: missing or invalid canonical fields.") from exc
            ids = [getattr(r, _ID_FIELDS[name]) for r in records]
            if len(ids) != len(set(ids)):
                raise ValueError(f"{name}: duplicate stable identifier; no silent deduplication.")
            decoded[name] = tuple(records)
        result = cls(**decoded)
        result.validate_links()
        return result

    def validate_links(self):
        documents = {d.document_id: d for d in self.documents}
        parties = {p.party_id: p for p in self.parties}
        items = {i.item_id for i in self.items}
        periods = {p.period_id: p for p in self.periods}
        terms = {t.term_id: t for t in self.terms}
        charges = {c.charge_id: c for c in self.actual_charges}
        if not documents or not periods:
            raise ValueError("Rental investigation requires documents and identified periods.")
        for name in _RECORD_TYPES:
            for record in getattr(self, name):
                for ref in getattr(record, "evidence_refs", ()):
                    if ref.document_id not in documents or documents[ref.document_id].role in {"IRRELEVANT", "UNKNOWN"}:
                        raise ValueError("Source reference is unknown or not classified for analytical use.")
        for p in self.periods:
            if (p.item_id not in items or p.supplier_id not in parties or p.client_id not in parties
                    or parties[p.supplier_id].role not in {"SUPPLIER", "RENTAL_VENDOR"}
                    or parties[p.client_id].role != "CLIENT"):
                raise ValueError("Rental period refers to an unknown item/party or mismatched party role.")
        for record in (*self.terms, *self.events, *self.actual_charges):
            if record.period_id not in periods:
                raise ValueError("Unknown rental period.")
        for term in self.terms:
            if term.supersedes_term_id is not None:
                old = terms.get(term.supersedes_term_id)
                if old is None or old.term_id == term.term_id or (old.period_id, old.charge_key) != (term.period_id, term.charge_key):
                    raise ValueError("Amendment must supersede a known term for the same charge scope.")
            visited, current = set(), term
            while current.supersedes_term_id is not None:
                if current.term_id in visited:
                    raise ValueError("Cyclic contractual amendments.")
                visited.add(current.term_id)
                current = terms[current.supersedes_term_id]
        for credit in self.credits:
            if credit.charge_id not in charges or credit.currency != charges[credit.charge_id].currency:
                raise ValueError("Credit must refer to a known invoice line in the same currency.")

    def to_dict(self):
        # JSON round-trip turns tuples into arrays and permits only canonical values.
        import json
        return json.loads(json.dumps({"schema_version": SCHEMA, **asdict(self)}))

    @cached_property
    def documents_by_id(self):
        return {d.document_id: d for d in self.documents}

    def evidence_status(self, refs, *, roles=None):
        documents = self.documents_by_id
        if roles is not None and not any(documents[r.document_id].role in roles for r in refs):
            return False
        return all(documents[r.document_id].status == "ACCEPTED" for r in refs)
