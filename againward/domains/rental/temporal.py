"""Conservative daily rental segments from accepted rates and physical returns.

Only explicit, dated amendments and documented return quantities move a
boundary. Unit days are exact; rounding happens once for the whole charge.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from .models import EvidenceRef, RentalCase, RentalPeriod, RateTerm, RentalEvent, decimal_value, iso_date
from .pricing import chargeable_days, money, refs_payload


def price_daily_segments(case: RentalCase, period: RentalPeriod, terms: list[RateTerm],
                         events: list[RentalEvent]) -> dict:
    start, end = iso_date(period.start), iso_date(period.end)
    result = {"amount": None, "status": "UNKNOWN_CONTRACTUAL_BASIS", "limitations": [],
              "contradictions": [], "term_ids": sorted(t.term_id for t in terms), "segments": [],
              "evidence_refs": refs_payload([*period.evidence_refs,
                                            *(ref for term in sorted(terms, key=lambda t: t.term_id)
                                              for ref in term.evidence_refs)]),
              "start": period.start, "end": period.end, "shortened": False,
              "charge_type": "RENTAL", "billing_unit": "DAY"}

    def refuse(reason: str, *, contradiction=False) -> dict:
        result["contradictions" if contradiction else "limitations"].append(reason)
        return result

    bases = [t for t in terms if t.effective_from is None and t.supersedes_term_id is None]
    dated = sorted((t for t in terms if t.effective_from is not None),
                   key=lambda t: (t.effective_from or "", t.term_id))
    if len(bases) != 1 or len(bases) + len(dated) != len(terms):
        return refuse("missing_or_ambiguous_accepted_rate_term")
    base = bases[0]
    chain = [base]
    for term in dated:
        if (term.supersedes_term_id != chain[-1].term_id
                or term.effective_from is None
                or not start < iso_date(term.effective_from) < end):
            return refuse("conflicting_or_out_of_period_rate_amendment", contradiction=True)
        if not case.evidence_status(term.evidence_refs, roles={"AMENDMENT", "PURCHASE_ORDER", "EMAIL_EVIDENCE"}):
            return refuse("dated_rate_not_supported_by_accepted_amendment")
        chain.append(term)
    result["term_ids"] = [t.term_id for t in chain]
    result.update(currency=base.currency, rate=base.rate if not dated else None,
                  discount_fraction=base.discount_fraction if not dated else None,
                  stop_event=base.stop_event)
    initial = decimal_value(period.quantity)
    if not case.evidence_status(period.evidence_refs, roles={
            "RENTAL_AGREEMENT", "PURCHASE_ORDER", "AMENDMENT", "EMAIL_EVIDENCE"}):
        return refuse("rental_period_not_supported_by_accepted_commercial_evidence")
    for term in chain:
        if term.quantity_basis == "PER_SCOPE":
            return refuse("scope_rate_daily_segments_requires_review")
        if (term.charge_type != "RENTAL" or term.billing_unit != "DAY"
                or term.currency != base.currency or term.stop_event != base.stop_event
                or term.stop_day_billable != base.stop_day_billable):
            return refuse("dated_or_partial_daily_convention_incompatible")
        if (term.rate is None or term.discount_fraction is None or term.weekends_billable is None
                or term.minimum_days != 0
                or term.tier_min_days is not None or term.tier_max_days is not None):
            return refuse("daily_segment_convention_missing_or_unsupported")
        if term.quantity is not None and decimal_value(term.quantity) != initial:
            return refuse("contractual_quantity_differs_from_initial_period", contradiction=True)
    if any(e.event_type == "EXTENDED" for e in events):
        return refuse("extension_with_quantity_or_rate_segments_requires_review", contradiction=True)
    returns = defaultdict(list)
    for event in events:
        if event.event_type != "RETURNED":
            continue
        if base.stop_event != "RETURNED":
            return refuse("contractual_stop_trigger_not_returned")
        if base.stop_day_billable is None:
            return refuse("stop_day_charging_convention_missing")
        if (event.verification != "DOCUMENTED" or event.quantity is None
                or not case.evidence_status(event.evidence_refs, roles={"RETURN_NOTE", "EMAIL_EVIDENCE"})):
            return refuse("return_quantity_or_documentation_missing", contradiction=True)
        quantity = decimal_value(event.quantity)
        boundary = iso_date(event.date) + timedelta(days=int(base.stop_day_billable))
        if quantity <= 0 or not start < boundary <= end:
            return refuse("return_quantity_or_date_outside_period", contradiction=True)
        returns[boundary].append(event)
    remaining = initial
    rate_dates = {iso_date(t.effective_from): t for t in dated if t.effective_from is not None}
    boundaries = sorted({start, end, *rate_dates, *returns})
    active = base
    total = Decimal(0)
    unit_days = Decimal(0)
    all_refs = [*period.evidence_refs, *(ref for term in chain for ref in term.evidence_refs)]
    return_refs: list[EvidenceRef] = []
    for left, right in zip(boundaries, boundaries[1:]):
        for event in sorted(returns.get(left, ()), key=lambda e: e.event_id):
            remaining -= decimal_value(event.quantity)
            return_refs.extend(event.evidence_refs)
            if remaining < 0:
                return refuse("documented_returns_exceed_hired_quantity", contradiction=True)
        if left in rate_dates:
            active = rate_dates[left]
        if remaining == 0:
            continue
        days = chargeable_days(left, right, weekends_billable=bool(active.weekends_billable))
        units = remaining * days
        price = units * decimal_value(active.rate) * (1 - decimal_value(active.discount_fraction))
        unit_days += units
        total += price
        result["segments"].append({"start": left.isoformat(), "end": right.isoformat(),
                                   "quantity": str(remaining), "days": days, "unit_days": str(units),
                                   "rate": active.rate, "term_id": active.term_id,
                                   "unrounded_amount": str(price),
                                   "evidence_refs": refs_payload([*period.evidence_refs,
                                                                 *active.evidence_refs, *return_refs])})
    for event in sorted(returns.get(end, ()), key=lambda e: e.event_id):
        remaining -= decimal_value(event.quantity)
        return_refs.extend(event.evidence_refs)
        if remaining < 0:
            return refuse("documented_returns_exceed_hired_quantity", contradiction=True)
    final_end = result["segments"][-1]["end"] if result["segments"] else period.start
    result.update(amount=money(total), status="CONTRACT_SUPPORTED", end=final_end,
                  shortened=iso_date(final_end) < end, unit_days=str(unit_days),
                  evidence_refs=refs_payload([*all_refs, *return_refs]),
                  formula="round_half_up(sum(segment_unit_days * rate * (1 - discount_fraction)), 0.01)")
    return result
