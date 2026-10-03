"""Single readiness owner and replayed exact HT consumption-line calculation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date, timedelta
from pathlib import Path
import re
from typing import Any

from againward.core.artifact_store import transaction, write_json
from againward.documents.contracts import DocumentError, SourceBatch
from againward.documents.sources import assert_document_action
from againward.evidence.hashing import stable_hash

from .models import ConsumptionLine, Period, TariffTerm
from .money import PRICE_UNITS, QUANTITY_UNITS, ROUNDING, consumption_component, exact, money_cents
from .protocol import BillingFailure
from .review import current_review
from .state import fields, load_state

VERSION = "energy-billing-consumption-case-v1"
SCOPE = "ONE_CONSUMPTION_HT_LINE"


def period(start: str, end: str, convention: str) -> Period:
    if convention not in {"EXCLUSIVE", "INCLUSIVE"}:
        raise BillingFailure("BUSINESS_AMBIGUITY", stage="PERIOD", expected="source-established end convention")
    if convention == "INCLUSIVE":
        try:
            end = (date.fromisoformat(end) + timedelta(days=1)).isoformat()
        except (ValueError, OverflowError) as exc:
            raise BillingFailure("OBSERVATION_INVALID", stage="PERIOD", expected="bounded calendar date") from exc
    return Period.from_iso(start, end)


def numeric_proof(state: dict[str, Any], ids: list[str], names: set[str]) -> None:
    """Minimum lexical cross-check, in addition to independent semantic review.

    Supports plain decimal comma/point only here. Grouped ambiguous number
    formats abstain until a separately tested normalization is implemented.
    A quote containing a number alone does not establish its business meaning.
    """
    for eid in ids:
        row = state["observations"][eid]
        if row["field"] in names:
            value = exact(row["value"])
            tokens = re.findall(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w.,])", row["quote"])
            if not any(exact(token.replace(",", ".")) == value for token in tokens):
                raise BillingFailure("EVIDENCE_BINDING_INVALID", stage="READINESS", expected="exact scalar in its own quote",
                                     evidence_id=eid, field=row["field"])


def _prerequisites(state: dict[str, Any], root: Path) -> tuple[str, ConsumptionLine, TariffTerm]:
    from .disposition import active_occurrences, excluded_ids, validate_current

    validate_current(state, root)
    excluded = excluded_ids(state)
    # Root causes, in dependency order. No expected-amount/report pseudo-issues.
    material = [row["root_issue_id"] for row in state["quarantine"].values()
                if row["potentially_material"] and row['root_issue_id'] not in excluded]
    if material:
        raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="READINESS", expected="material quarantine resolved",
                             root_issue_ids=sorted(material))
    # Coverage wording cannot make a known credit or invoice-level total vanish
    # from a single-line calculation. These need a supported explicit treatment.
    other_financial = sorted(eid for eid, row in state["observations"].items()
                             if row["field"] in {"credit_amount", "invoice_total"} and eid not in excluded and row['source_id'] not in excluded)
    if other_financial:
        raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="READINESS",
                             expected="explicit supported disposition of credit / invoice-level amount",
                             unresolved_evidence_ids=other_financial)
    active = active_occurrences(state)
    invoices = {key: row for key, row in active.items() if row["kind"] == "INVOICE"}
    tariffs = {key: row for key, row in active.items() if row["kind"] == "TARIFF"}
    if len(invoices) != 1:
        raise BillingFailure("OCCURRENCE_AMBIGUOUS" if invoices else "MATERIAL_EVIDENCE_MISSING", stage="IDENTITY",
                             expected="one scoped invoice consumption line", count=len(invoices))
    if len(tariffs) != 1:
        raise BillingFailure("AUTHORITY_UNRESOLVED", stage="AUTHORITY", expected="one established applicable tariff",
                             count=len(tariffs))
    iid, tid = next(iter(invoices)), next(iter(tariffs))
    invoice, tariff = invoices[iid], tariffs[tid]
    # This first slice covers two complete scoped documents. Unknown documents
    # cannot quietly disappear. A later source-disposition action can widen this.
    used = {invoice["source_id"], tariff["source_id"]}
    unknown = {d.source_id for d in SourceBatch.from_dict(state["batch"]).documents} - used - excluded
    if unknown:
        raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="READINESS", expected="source disposition before calculation",
                             source_ids=sorted(unknown))
    ir = current_review(state, iid, root)
    tr = current_review(state, tid, root)
    if tr["tariff_type"] in {"INDEXED", "OTHER"} or tr["rounding_rule"] == "OTHER":
        raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", expected="fixed tariff with supported per-line rounding")
    for response in (ir, tr):
        if response["coverage"] != "ALL_MATERIAL_FACTS_BOUND":
            raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="READINESS", expected="complete material source coverage")
        if response["charge_kind"] == "OTHER":
            raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", expected="consumption HT line")
        if response["charge_kind"] != "CONSUMPTION_HT":
            raise BillingFailure("BUSINESS_AMBIGUITY", stage="READINESS", expected="established consumption HT scope")
    dismissed = set(ir["nonmaterial_quarantine_ids"] + tr["nonmaterial_quarantine_ids"])
    pending_notes = sorted(key for key, row in state['quarantine'].items()
                           if key not in dismissed | excluded and row['source_id'] not in excluded)
    if pending_notes:
        raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="READINESS", expected="independent disposition of quarantined notes",
                             root_issue_ids=pending_notes)
    if tr["tariff_type"] != "FIXED" or tr["rounding_rule"] not in ROUNDING:
        raise BillingFailure("AUTHORITY_UNRESOLVED", stage="AUTHORITY", expected="established tariff and rounding")
    iv, tv = fields(state, invoice["evidence_ids"]), fields(state, tariff["evidence_ids"])
    numeric_proof(state, invoice["evidence_ids"], {"quantity", "billed_amount"})
    numeric_proof(state, tariff["evidence_ids"], {"tariff_price"})
    line = ConsumptionLine(iv["invoice_id"], iv["supplier_id"], iv["pdl"], iv["currency"],
                           period(iv["period_start"], iv["period_end"], ir["end_convention"]),
                           iv["quantity"], iv["quantity_unit"], iv["billed_amount"], tuple(invoice["evidence_ids"]))
    term = TariffTerm(tv["contract_id"], tv["supplier_id"], tv["pdl"], tv["currency"],
                      period(tv["effective_start"], tv["effective_end"], tr["end_convention"]),
                      tr["tariff_type"], tv["tariff_price"], tv["price_unit"], tr["rounding_rule"], tuple(tariff["evidence_ids"]))
    if (line.supplier_id, line.pdl, line.currency) != (term.supplier_id, term.pdl, term.currency):
        raise BillingFailure("RELATION_AMBIGUOUS", stage="IDENTITY", expected="matching supplier, PDL and currency")
    if not term.effective_period.contains(line.period):
        raise BillingFailure("AUTHORITY_UNRESOLVED", stage="AUTHORITY", expected="tariff effective throughout billed period")
    if line.quantity_unit not in QUANTITY_UNITS or term.price_unit not in PRICE_UNITS:
        raise BillingFailure("UNSUPPORTED_DOMAIN_RULE", stage="ENVELOPE", expected="explicit supported energy/price units")
    relations = {key: row for key, row in state["relations"].items()
                 if row["invoice_id"] == iid and row["tariff_id"] == tid}
    if len(relations) != 1:
        raise BillingFailure("AUTHORITY_UNRESOLVED", stage="RELATION", expected="reviewed GOVERNS relation")
    rid = next(iter(relations))
    ar = current_review(state, rid, root)
    if ar["authority_kind"] != "ACCEPTED_CONTRACT":
        raise BillingFailure("AUTHORITY_UNRESOLVED", stage="AUTHORITY", expected="accepted contractual price, not invoice price")
    return rid, line, term


def readiness(state: dict[str, Any], root: Path) -> dict[str, Any]:
    """Abstention contains no final expected amount. Technical errors stay errors."""
    if load_state(root) != state:
        raise BillingFailure("STATE_CHANGED", stage="READINESS", expected="replayed Python state")
    try:
        rid, line, term = _prerequisites(state, root)
    except (BillingFailure, DocumentError) as exc:
        code = exc.code
        diagnostic = exc.diagnostic if isinstance(exc, BillingFailure) else {"code": code, "stage": "SOURCE"}
        support = "UNSUPPORTED" if code == "UNSUPPORTED_DOMAIN_RULE" else "UNRESOLVED"
        if code in {"MODEL_PROTOCOL_INVALID", "STATE_REPLAY_INVALID", "STATE_CHANGED"}:
            raise
        return {"schema_version": VERSION, "scope": SCOPE, "support_state": support,
                "root_issues": [diagnostic], "derived_blockers": ["CALCULATION_BLOCKED"], "ready": False}
    facts = {"line": asdict(line), "tariff": asdict(term)}
    for key in facts:
        facts[key]["evidence_ids"] = list(facts[key]["evidence_ids"])
        for field in ("period", "effective_period"):
            if field in facts[key]:
                facts[key][field] = {k: v.isoformat() for k, v in facts[key][field].items()}
    return {"schema_version": VERSION, "scope": SCOPE, "support_state": "SUPPORTED_DETERMINISTIC",
            "root_issues": [], "derived_blockers": [], "ready": True, "relation_id": rid,
            **facts}


def calculate(state: dict[str, Any], root: Path, *, persist: bool = True) -> dict[str, Any]:
    assert_document_action(root, mutation=persist)
    with transaction(root):
        decision = readiness(state, root)
        if not decision["ready"]:
            raise BillingFailure("READINESS_BLOCKED", stage="CALCULATION", expected="unique deterministic readiness",
                                 root_issues=decision["root_issues"], support_state=decision["support_state"])
        rid, line, term = _prerequisites(state, root)
        component = consumption_component(quantity=line.quantity, quantity_unit=line.quantity_unit, price=term.price,
                                          price_unit=term.price_unit, rounding_rule=term.rounding_rule)
        billed = money_cents(line.billed_amount_eur)
        body = {"schema_version": VERSION, "scope": SCOPE, "currency": "EUR", "readiness": decision,
                "component": component, "billed_cents": billed,
                "expected_cents": component["expected_cents"], "discrepancy_cents": billed - component["expected_cents"],
                "authority": {"relation_id": rid, "contract_id": term.contract_id,
                              "contract_acceptance_evidence": state["reviews"][rid]["authority_evidence"],
                              "evidence_ids": sorted(set(line.evidence_ids + term.evidence_ids)),
                              "review_receipts": sorted(row["receipt_sha256"] for target, row in state["reviews"].items()
                                                       if target in {rid, state["relations"][rid]["invoice_id"],
                                                                     state["relations"][rid]["tariff_id"]})},
                "qualification": "Observed billed difference on one HT consumption line; not a recoverable amount or legal entitlement."}
        if state.get('dispositions'):
            from .disposition import excluded_ids, frontier
            body['disposition_receipts'] = {key: state['dispositions'][key]['receipt_sha256'] for key in sorted(excluded_ids(state))}
            body['material_frontier'] = frontier(state, [state['relations'][rid]['invoice_id'], state['relations'][rid]['tariff_id']])
        digest = stable_hash(body)
        result = {**body, "calculation_sha256": digest}
        if persist:
            write_json(root / "energy_billing" / "calculations" / (digest + ".json"), result)
        return result
