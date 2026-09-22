"""Actual ledgers, keyed reconciliation and candidate discrepancies, never claims."""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from againward.evidence.hashing import stable_hash
from .models import RentalCase, decimal_value
from .pricing import build_expected_ledger, money, refs_payload
from .arithmetic import deterministic_decimal

FINDING_FAMILIES = frozenset({"DUPLICATE_BILLING", "WRONG_RATE", "WRONG_RATE_TIER",
    "POST_OFF_HIRE_BILLING", "POST_RETURN_BILLING", "INCORRECT_QUANTITY", "INCORRECT_DURATION",
    "UNAUTHORIZED_FEE", "MISSING_DISCOUNT", "MISSING_CREDIT", "PROMISED_CREDIT_NOT_APPLIED",
    "TRANSPORT_CHARGE_MISMATCH", "DELIVERY_CHARGE_MISMATCH", "COLLECTION_CHARGE_MISMATCH",
    "DAMAGE_WAIVER_MISMATCH", "FUEL_CHARGE_MISMATCH", "UNKNOWN_CONTRACTUAL_BASIS"})

ALTERNATIVES = {
    "DUPLICATE_BILLING": "Distinct quantities, assets, sites or authorized split charges may explain similar lines.",
    "WRONG_RATE": "An accepted amendment, negotiated rate, minimum duration or different rate tier may apply.",
    "WRONG_RATE_TIER": "The duration or contractual tier eligibility may differ from the extracted schedule.",
    "POST_RETURN_BILLING": "A collection request is not possession; partial return, extension or reused asset ID may explain billing.",
    "POST_OFF_HIRE_BILLING": "The agreement may stop billing at collection rather than at the off-hire request.",
    "INCORRECT_QUANTITY": "A second asset, replacement or partial delivery may justify the invoiced quantity.",
    "INCORRECT_DURATION": "Minimum periods, weekend charging, extensions or inclusive dates may explain duration.",
    "MISSING_DISCOUNT": "The discount may be conditional or already reflected in the net amount.",
    "PROMISED_CREDIT_NOT_APPLIED": "A credit may be issued outside the supplied export or allocated to another invoice.",
    "UNKNOWN_CONTRACTUAL_BASIS": "Missing accepted contractual evidence may explain the charge.",
}


@deterministic_decimal
def build_actual_ledger(case: RentalCase) -> dict:
    credits_by_charge = defaultdict(list)
    for credit in case.credits:
        credits_by_charge[credit.charge_id].append(credit)
    entries = []
    for charge in case.actual_charges:
        issued = Decimal(0)
        promised = Decimal(0)
        limitations = []
        refs = list(charge.evidence_refs)
        for credit in credits_by_charge[charge.charge_id]:
            refs.extend(credit.evidence_refs)
            if credit.status == "PROMISED":
                promised += decimal_value(credit.net_amount)
            elif case.evidence_status(credit.evidence_refs, roles={"CREDIT_NOTE"}):
                issued += decimal_value(credit.net_amount)
            else:
                limitations.append("credit_not_supported_by_accepted_credit_note:" + credit.credit_id)
        gross = decimal_value(charge.net_amount)
        if issued > gross:
            raise ValueError("Allocated credits exceed the referenced invoice line; reconciliation requires clarification.")
        if not case.evidence_status(charge.evidence_refs, roles={"INVOICE"}):
            limitations.append("invoice_evidence_not_accepted")
        entries.append({"charge_id": charge.charge_id, "invoice_id": charge.invoice_id,
            "invoice_line_id": charge.invoice_line_id, "period_id": charge.period_id,
            "charge_key": charge.charge_key, "charge_type": charge.charge_type,
            "currency": charge.currency, "invoiced_amount": money(gross), "issued_credit": money(issued),
            "net_amount": money(gross - issued), "unapplied_promised_credit": money(max(Decimal(0), promised - issued)),
            "quantity": charge.quantity, "unit_rate": charge.unit_rate, "billed_units": charge.billed_units,
            "start": charge.start, "end": charge.end,
            "evidence_refs": refs_payload(refs), "limitations": limitations})
    return {"schema_version": "againward-actual-charge-ledger-v1", "amount_basis": "NET_EXCLUDING_TAX",
            "entries": entries, "decision": None}


def _families(actual, expected, difference):
    if expected is None or expected["amount"] is None:
        families = ["UNKNOWN_CONTRACTUAL_BASIS"]
        if actual[0]["charge_type"] != "RENTAL":
            families.append("UNAUTHORIZED_FEE")
    elif difference <= 0:
        return ["PROMISED_CREDIT_NOT_APPLIED"] if any(decimal_value(row["unapplied_promised_credit"]) > 0 for row in actual) else []
    else:
        families = []
        if expected.get("shortened") and any(r.get("end") and r["end"] > expected["end"] for r in actual):
            families.append("POST_OFF_HIRE_BILLING" if expected.get("stop_event") == "OFF_HIRE_REQUESTED" else "POST_RETURN_BILLING")
        if expected.get("rate") is not None and any(
                r.get("unit_rate") is not None and decimal_value(r["unit_rate"]) > decimal_value(expected["rate"])
                for r in actual):
            families.append("WRONG_RATE")
        if expected.get("segments") and len({s["rate"] for s in expected["segments"]}) > 1:
            families.append("WRONG_RATE")
        if expected.get("segments") and len({s["quantity"] for s in expected["segments"]}) > 1:
            families.append("INCORRECT_QUANTITY")
        if expected.get("quantity") is not None and any(r.get("quantity") is not None and decimal_value(r["quantity"]) > decimal_value(expected["quantity"]) for r in actual):
            families.append("INCORRECT_QUANTITY")
        if expected.get("units") is not None and any(r.get("billed_units") is not None and decimal_value(r["billed_units"]) > Decimal(expected["units"]) for r in actual):
            families.append("INCORRECT_DURATION")
        if expected.get("discount_fraction") and decimal_value(expected["discount_fraction"]) > 0:
            # This remains a hypothesis even if another cause could explain the same gap.
            families.append("MISSING_DISCOUNT")
        fee_family = {"TRANSPORT": "TRANSPORT_CHARGE_MISMATCH", "DELIVERY": "DELIVERY_CHARGE_MISMATCH",
            "COLLECTION": "COLLECTION_CHARGE_MISMATCH", "DAMAGE_WAIVER": "DAMAGE_WAIVER_MISMATCH",
            "FUEL": "FUEL_CHARGE_MISMATCH", "REFUELING": "FUEL_CHARGE_MISMATCH"}.get(actual[0]["charge_type"])
        if fee_family:
            families.append(fee_family)
        if not families:
            families.append("INCORRECT_DURATION" if actual[0]["charge_type"] == "RENTAL" else "UNAUTHORIZED_FEE")
    signatures = defaultdict(int)
    for row in actual:
        signature = tuple(row.get(key) for key in ("charge_type", "start", "end", "quantity", "unit_rate", "billed_units", "invoiced_amount"))
        signatures[signature] += 1
    if any(count > 1 for count in signatures.values()):
        families.append("DUPLICATE_BILLING")
    if any(decimal_value(row["unapplied_promised_credit"]) > 0 for row in actual):
        families.append("PROMISED_CREDIT_NOT_APPLIED")
    return list(dict.fromkeys(families))


@deterministic_decimal
def reconcile(case: RentalCase) -> dict:
    expected = build_expected_ledger(case)
    actual = build_actual_ledger(case)
    expected_by_scope = {(r["period_id"], r["charge_key"]): r for r in expected["entries"]}
    terms_by_id = {t.term_id: t for t in case.terms}
    grouped = defaultdict(list)
    for row in actual["entries"]:
        grouped[(row["period_id"], row["charge_key"], row["currency"])].append(row)
    groups, candidates = [], []
    totals = defaultdict(lambda: {"actual": Decimal(0), "supported_positive_discrepancy": Decimal(0)})
    for (period_id, charge_key, currency), lines in sorted(grouped.items()):
        exp = expected_by_scope.get((period_id, charge_key))
        limitations = [gap for line in lines for gap in line["limitations"]]
        if exp:
            limitations.extend(exp["limitations"])
            limitations.extend(exp.get("contradictions", []))
            if exp.get("currency") not in {None, currency}:
                limitations.append("currency_mismatch_no_conversion")
            if exp.get("charge_type") not in {None, lines[0]["charge_type"]}:
                limitations.append("charge_type_mismatch")
        if len({line["charge_type"] for line in lines}) != 1:
            limitations.append("inconsistent_charge_types_in_scope")
        actual_amount = sum((decimal_value(line["net_amount"]) for line in lines), Decimal(0))
        expected_amount = decimal_value(exp["amount"]) if exp and exp["amount"] is not None and not limitations else None
        difference = actual_amount - expected_amount if expected_amount is not None else None
        scope = {"period_id": period_id, "charge_key": charge_key, "currency": currency}
        group_id = "RG-" + stable_hash(scope)[:20]
        refs = [ref for line in lines for ref in line["evidence_refs"]]
        if exp:
            refs += [ref for ref in exp["evidence_refs"] if ref not in refs]
        group = {"group_id": group_id, **scope, "charge_ids": [r["charge_id"] for r in lines],
                 "actual_amount": money(actual_amount), "expected_amount": money(expected_amount) if expected_amount is not None else None,
                 "difference": money(difference) if difference is not None else None,
                 "evidence_refs": refs, "limitations": list(dict.fromkeys(limitations)),
                 "amount_basis": "CONTRACT_SUPPORTED_DISCREPANCY" if difference is not None else "UNQUANTIFIED_SIGNAL",
                 "recoverable_amount": None, "decision": None}
        groups.append(group)
        totals[currency]["actual"] += actual_amount
        if difference is not None:
            totals[currency]["supported_positive_discrepancy"] += max(Decimal(0), difference)
        families = _families(lines, exp if expected_amount is not None else None, difference)
        if "WRONG_RATE" in families and exp and any(terms_by_id[tid].tier_min_days is not None or terms_by_id[tid].tier_max_days is not None for tid in exp["term_ids"]):
            families.append("WRONG_RATE_TIER")
        for family in families:
            candidates.append({"finding_id": "RF-" + stable_hash({"group": group_id, "family": family})[:20],
                "family": family, **group, "status": "CANDIDATE", "evidence_level": "L2" if difference is not None else "L1",
                "difference_is_shared_group_amount": True,
                "best_alternative_explanation": ALTERNATIVES.get(family, "A separately accepted fee, surcharge or invoice adjustment may explain the amount."),
                "tests_performed": ["contract_term_selection", "calendar_pricing", "invoice_credit_allocation", "charge_scope_reconciliation"],
                "unresolved_questions": ["Analyst must check amendments, operational evidence and contractual exceptions."],
                "confidence": {"status": "NOT_ASSESSED", "reason": "Deterministic difference does not establish a recoverable claim."}})
    return {"schema_version": "againward-rental-reconciliation-v1", "expected_ledger": expected,
            "actual_ledger": actual, "groups": groups, "candidates": candidates,
            "totals_by_currency": {currency: {key: money(value) for key, value in values.items()} for currency, values in totals.items()},
            "aggregation_policy": "one amount per period/charge_key/currency, never sum finding families",
            "recoverable_amount": None, "decision": None}
