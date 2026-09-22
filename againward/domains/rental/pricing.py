"""Deterministic expected-charge ledger from explicit contractual evidence.

No numeric gap is a claim. An unresolved convention yields amount=None, with a
specific gap; it never silently becomes a zero-price contractual obligation.
"""
from __future__ import annotations

from calendar import monthrange
from collections import defaultdict, deque
from dataclasses import asdict
from datetime import date, timedelta
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP

from .models import RentalCase, RentalPeriod, RateTerm, decimal_value, iso_date
from .arithmetic import deterministic_decimal

CENT = Decimal("0.01")


@deterministic_decimal
def money(value: Decimal) -> str:
    return format(value.quantize(CENT, rounding=ROUND_HALF_UP), ".2f")


def refs_payload(refs):
    values = [asdict(ref) for ref in refs]
    return list({(v["document_id"], v["location"], v["field"]): v for v in values}.values())


def chargeable_days(start: date, end: date, *, weekends_billable: bool) -> int:
    days = max(0, (end - start).days)
    if weekends_billable:
        return days
    weeks, remainder = divmod(days, 7)
    return weeks * 5 + sum((start.weekday() + offset) % 7 < 5 for offset in range(remainder))


def _month_anchor(start: date, months: int) -> date:
    ordinal = start.year * 12 + start.month - 1 + months
    year, month0 = divmod(ordinal, 12)
    month = month0 + 1
    return date(year, month, min(start.day, monthrange(year, month)[1]))


@deterministic_decimal
def billable_units(start: date, end: date, term: RateTerm) -> tuple[Decimal | None, list[str]]:
    if term.billing_unit == "FIXED":
        return Decimal(1), []
    if term.billing_unit not in {"DAY", "WEEK", "MONTH"}:
        return None, ["billing_unit_missing_or_not_a_duration"]
    if term.weekends_billable is None or term.minimum_days is None:
        return None, ["weekend_or_minimum_period_convention_missing"]
    days = max(term.minimum_days, chargeable_days(start, end, weekends_billable=term.weekends_billable))
    if term.billing_unit == "DAY":
        return Decimal(days), []
    if term.partial_period_policy is None:
        return None, ["partial_period_convention_missing"]
    if term.billing_unit == "WEEK":
        units = Decimal(days) / Decimal(7 if term.weekends_billable else 5)
    else:
        if not term.weekends_billable:
            return None, ["monthly_weekday_only_pricing_not_supported"]
        effective_end = max(end, start + timedelta(days=term.minimum_days))
        months = (effective_end.year - start.year) * 12 + effective_end.month - start.month
        if _month_anchor(start, months) > effective_end:
            months -= 1
        anchor = _month_anchor(start, months)
        if anchor == effective_end:
            units = Decimal(months)
        else:
            following = _month_anchor(start, months + 1)
            units = Decimal(months) + Decimal((effective_end - anchor).days) / Decimal((following - anchor).days)
    if term.partial_period_policy == "STARTED":
        return units.to_integral_value(rounding=ROUND_CEILING), []
    if term.partial_period_policy == "EXACT" and units != units.to_integral_value():
        return None, ["incomplete_period_without_authorized_proration"]
    return units, []


def resolve_timeline(case: RentalCase, period: RentalPeriod, term: RateTerm, *, events=None):
    """Apply documented events only under an explicit contract stop rule.

    Conflicting evidence is exposed, never resolved by a last-row-wins rule.
    Partial returns require an allocation model and therefore remain unresolved.
    """
    start, end = iso_date(period.start), iso_date(period.end)
    refs = list(period.evidence_refs)
    limitations, contradictions = [], []
    if not case.evidence_status(period.evidence_refs, roles={"RENTAL_AGREEMENT", "PURCHASE_ORDER", "AMENDMENT", "EMAIL_EVIDENCE"}):
        limitations.append("rental_period_not_supported_by_accepted_commercial_evidence")
    stops, extensions = [], []
    if term.billing_unit in {"FIXED", "PERCENT"}:
        return {"start": start, "end": end, "evidence_refs": refs,
                "limitations": limitations, "contradictions": [], "shortened": False}
    for event in (events if events is not None else case.events):
        if event.period_id != period.period_id:
            continue
        if event.event_type == "EXTENDED":
            refs.extend(event.evidence_refs)
            if event.verification == "DOCUMENTED" and case.evidence_status(event.evidence_refs, roles={
                    "RENTAL_AGREEMENT", "AMENDMENT", "PURCHASE_ORDER", "EMAIL_EVIDENCE"}) and event.extended_end:
                extensions.append(event)
            else:
                contradictions.append("extension_not_supported_or_boundary_missing:" + event.event_id)
        if event.event_type == term.stop_event:
            refs.extend(event.evidence_refs)
            stop_roles = {"RETURNED": {"RETURN_NOTE", "EMAIL_EVIDENCE"},
                          "COLLECTED": {"RETURN_NOTE", "EMAIL_EVIDENCE"},
                          "OFF_HIRE_REQUESTED": {"OFF_HIRE_NOTICE", "EMAIL_EVIDENCE"}}.get(event.event_type, set())
            if event.verification != "DOCUMENTED" or not case.evidence_status(event.evidence_refs, roles=stop_roles):
                contradictions.append("stop_event_not_documented:" + event.event_id)
            elif event.quantity is None or decimal_value(event.quantity) != decimal_value(period.quantity):
                contradictions.append("partial_or_unknown_return_quantity:" + event.event_id)
            elif term.stop_day_billable is None:
                limitations.append("stop_day_charging_convention_missing")
            else:
                boundary = iso_date(event.date) + timedelta(days=int(term.stop_day_billable))
                if boundary < start:
                    contradictions.append("stop_precedes_period:" + event.event_id)
                else:
                    stops.append((boundary, event))
    if extensions:
        end = max(end, *(iso_date(e.extended_end) for e in extensions))
        refs.extend(r for event in extensions for r in event.evidence_refs)
    if stops:
        distinct = {boundary for boundary, _ in stops}
        if len(distinct) > 1:
            contradictions.append("conflicting_documented_stop_dates")
        stop, event = min(stops, key=lambda pair: pair[0])
        # A later signed extension is material contrary evidence, not proof it is an error.
        if any(iso_date(e.date) >= iso_date(event.date) and iso_date(e.extended_end) > stop for e in extensions):
            contradictions.append("authorized_extension_after_stop")
        end = min(end, stop)
        refs.extend(r for _, event in stops for r in event.evidence_refs)
    if term.stop_event is None and any(e.period_id == period.period_id and e.event_type in {
            "RETURNED", "COLLECTED", "OFF_HIRE_REQUESTED"} for e in (events if events is not None else case.events)):
        limitations.append("contractual_stop_trigger_missing")
    return {"start": start, "end": end, "evidence_refs": refs,
            "limitations": limitations, "contradictions": contradictions,
            "shortened": end < iso_date(period.end)}


@deterministic_decimal
def build_expected_ledger(case: RentalCase) -> dict:
    periods = {p.period_id: p for p in case.periods}
    terms_by_scope = defaultdict(list)
    events_by_period = defaultdict(list)
    for term in case.terms:
        terms_by_scope[(term.period_id, term.charge_key)].append(term)
    for event in case.events:
        events_by_period[event.period_id].append(event)
    entries = {}
    pending_percentages = []
    for scope, candidates in sorted(terms_by_scope.items()):
        period = periods[scope[0]]
        accepted = [t for t in candidates if case.evidence_status(t.evidence_refs, roles={
            "RENTAL_AGREEMENT", "RATE_CARD", "QUOTE", "PURCHASE_ORDER", "AMENDMENT", "EMAIL_EVIDENCE"})]
        dated = any(t.effective_from is not None for t in accepted)
        partial_daily_return = any(
            event.event_type == "RETURNED" and event.quantity is not None
            and decimal_value(event.quantity) < decimal_value(period.quantity)
            for event in events_by_period[period.period_id]
        ) and any(t.billing_unit == "DAY" for t in accepted)
        if dated or partial_daily_return:
            from .temporal import price_daily_segments
            segment = price_daily_segments(case, period, accepted, events_by_period[period.period_id])
            entries[scope] = {"expected_charge_id": "/".join(scope), "period_id": scope[0], "charge_key": scope[1],
                              "decision": None, **segment}
            continue
        superseded = {t.supersedes_term_id for t in accepted if t.supersedes_term_id}
        eligible = []
        for t in accepted:
            if t.term_id in superseded:
                continue
            timeline = resolve_timeline(case, period, t, events=events_by_period[period.period_id])
            duration = (timeline["end"] - timeline["start"]).days
            if ((t.tier_min_days is None or duration >= t.tier_min_days)
                    and (t.tier_max_days is None or duration <= t.tier_max_days)):
                eligible.append(t)
        entry = {"expected_charge_id": "/".join(scope), "period_id": scope[0], "charge_key": scope[1],
                 "amount": None, "status": "UNKNOWN_CONTRACTUAL_BASIS", "limitations": [],
                 "evidence_refs": refs_payload(r for t in candidates for r in t.evidence_refs),
                 "term_ids": [t.term_id for t in eligible], "decision": None}
        entries[scope] = entry
        if len(eligible) != 1:
            entry["limitations"] = ["missing_or_ambiguous_accepted_rate_term"]
            continue
        term = eligible[0]
        entry.update(currency=term.currency, charge_type=term.charge_type, rate=term.rate,
                     billing_unit=term.billing_unit, discount_fraction=term.discount_fraction)
        timeline = resolve_timeline(case, period, term, events=events_by_period[period.period_id])
        entry.update(start=timeline["start"].isoformat(), end=timeline["end"].isoformat(),
                     shortened=timeline["shortened"], stop_event=term.stop_event,
                     contradictions=timeline["contradictions"])
        entry["evidence_refs"] = refs_payload([*term.evidence_refs, *timeline["evidence_refs"]])
        entry["limitations"].extend(timeline["limitations"])
        if term.rate is None or term.billing_unit is None:
            entry["limitations"].append("rate_or_billing_unit_missing")
            continue
        if term.discount_fraction is None:
            entry["limitations"].append("discount_convention_missing")
            continue
        if timeline["contradictions"] or timeline["limitations"]:
            continue
        if term.billing_unit == "PERCENT":
            pending_percentages.append((scope, term))
            continue
        units, gaps = billable_units(timeline["start"], timeline["end"], term)
        entry["limitations"].extend(gaps)
        quantity = term.quantity if term.quantity is not None else (period.quantity if term.charge_type == "RENTAL" else None)
        if units is None or quantity is None:
            if quantity is None:
                entry["limitations"].append("contractual_charge_quantity_missing")
            continue
        amount = units * decimal_value(quantity) * decimal_value(term.rate) * (1 - decimal_value(term.discount_fraction))
        entry.update(amount=money(amount), status="CONTRACT_SUPPORTED", quantity=quantity,
                     units=str(units), formula="round_half_up(units * quantity * rate * (1 - discount_fraction), 0.01)")
    # Resolve keyed dependencies once, with a bounded depth for evidence expansion.
    dependents = defaultdict(list)
    unresolved = dict(pending_percentages)
    for scope, term in pending_percentages:
        dependents[(scope[0], term.percentage_of)].append(scope)
    ready = deque((scope, 0) for scope, entry in entries.items() if entry["amount"] is not None)
    while ready:
        base_scope, depth = ready.popleft()
        base = entries[base_scope]
        for scope in dependents[base_scope]:
            term = unresolved.pop(scope)
            entry = entries[scope]
            if base.get("currency") != term.currency or depth >= 32:
                entry["limitations"].append("percentage_base_currency_mismatch" if depth < 32 else "percentage_dependency_depth_exceeds_32")
                continue
            amount = decimal_value(base["amount"]) * decimal_value(term.rate) / 100 * (1 - decimal_value(term.discount_fraction))
            entry.update(amount=money(amount), status="CONTRACT_SUPPORTED", base_charge_id=base["expected_charge_id"],
                         base_amount=base["amount"], formula="round_half_up(base_amount * rate / 100 * (1 - discount_fraction), 0.01)")
            references = {(r["document_id"], r["location"], r.get("field")): r for r in [*entry["evidence_refs"], *base["evidence_refs"]]}
            entry["evidence_refs"] = list(references.values())
            ready.append((scope, depth + 1))
    for scope in unresolved:
        entries[scope]["limitations"].append("missing_or_cyclic_percentage_base")
    return {"schema_version": "againward-expected-charge-ledger-v1", "amount_basis": "NET_EXCLUDING_TAX",
            "rounding": "ROUND_HALF_UP_PER_EXPECTED_CHARGE_TO_0.01", "entries": list(entries.values()), "decision": None}
