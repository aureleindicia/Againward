"""Compact Rental client PDF from already validated evidence and analyst prose.

The existing stdlib PDF primitive is reused; no Energy arithmetic or claim
policy is imported. This is a human-review candidate, never auto-delivered.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import textwrap

from client_delivery import _PdfPage, _wrap, _write_pdf_pages


_MONEY = re.compile(r"\b(EUR|USD|GBP|CHF|CAD|AUD|NZD)\s*([0-9]+(?:[.,][0-9]+)?)\b", re.I)
RENDER_VERSION = "againward-rental-reviewed-evidence-v2"


def _allowed_amounts(pack: dict) -> set[tuple[str, Decimal]]:
    result = set()
    for row in [*pack["charge_groups"], *pack["findings"]["findings"]]:
        currency = row.get("currency")
        for key in ("actual_amount", "expected_amount", "difference", "recovery_grade_amount"):
            value = row.get(key)
            if currency and value is not None:
                result.add((currency, Decimal(str(value))))
    return result


def _allowed_asset_identifiers(pack: dict) -> set[str]:
    lineage = pack.get("document_lineage", {})
    facts = lineage.get("facts", []) if isinstance(lineage, dict) else []
    result = set()
    if lineage.get("schema_version") == "againward-rental-graph-lineage-v2":
        for oid, atom in lineage["observations"].items():
            if (lineage["frontier"]["observations"][oid] == "USED" and atom["semantic_type"] in {"asset_id", "serial_number"}
                    and isinstance(atom["value"], str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{1,63}", atom["value"])):
                result.add(atom["value"])
        return result
    for fact in facts:
        candidate = fact.get("candidate", {}) if isinstance(fact, dict) else {}
        if candidate.get("semantic_type") in {"asset_id", "serial_number"}:
            value = candidate.get("value")
            if isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{1,63}", value):
                result.add(value)
    return result


def validate_synthesis(synthesis: str, pack: dict) -> None:
    """Prose may select exact calculated amounts, never invent one."""
    if not isinstance(synthesis, str) or not synthesis.strip() or len(synthesis) > 1800:
        raise ValueError("A concise nonempty analyst synthesis is required")
    if re.search(r"\S+@\S+", synthesis):
        raise ValueError("Do not include professional/personal contact addresses in client narrative")
    allowed = _allowed_amounts(pack)
    spans = []
    for match in _MONEY.finditer(synthesis):
        try:
            amount = Decimal(match.group(2).replace(",", "."))
        except InvalidOperation as exc:
            raise ValueError("Invalid narrative amount") from exc
        if (match.group(1).upper(), amount) not in allowed:
            raise ValueError("Narrative amount is not present in validated Rental evidence")
        spans.append(match.span())
    remainder = list(synthesis)
    for start, end in spans:
        remainder[start:end] = " " * (end - start)
    for identifier in sorted(_allowed_asset_identifiers(pack), key=len, reverse=True):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(identifier) + r"(?![A-Za-z0-9])"
        for match in re.finditer(pattern, "".join(remainder)):
            remainder[match.start():match.end()] = " " * (match.end() - match.start())
    if re.search(r"\d", "".join(remainder)):
        raise ValueError("Free numeric/date/identifier claims need a validated structured citation")


def render_rental_pdf(pack: dict, synthesis: str, target: Path, *, evaluation_only: bool = False) -> dict:
    validate_synthesis(synthesis, pack)
    pages: list[_PdfPage] = []

    def new_page(title: str) -> _PdfPage:
        page = _PdfPage([])
        pages.append(page)
        page.text("AGAINWARD  |  Rental invoice verification", size=9, bold=True)
        if evaluation_only:
            page.text("SYNTHETIC EVALUATION — NOT FOR CLIENT DELIVERY", size=9, bold=True)
        page.line()
        page.text(title, size=17, bold=True)
        return page

    def add(page: _PdfPage, value: str, *, size: int = 10, bold: bool = False) -> _PdfPage:
        if len(value) > 900:
            raise ValueError("One report paragraph is too long for bounded PDF composition")
        needed = len(_wrap(value, 70 if size >= 14 else 88)) * (size + 4) + 8
        if page.y - needed < 65:
            page = new_page("Continued")
        page.text(value, size=size, bold=bold)
        return page

    page = new_page("Review summary")
    for paragraph in textwrap.wrap(synthesis, width=850, break_long_words=False,
                                   break_on_hyphens=False):
        page = add(page, paragraph)
    page = add(page, "This is a documented comparison, not a debt, legal opinion or guaranteed recovery.")
    page = add(page, "The comparison below uses net amounts excluding tax. "
                    "Any source uncertainty is identified with the relevant finding.")

    page = new_page("Documents and scope")
    roles: dict[str, int] = {}
    for document in pack["documents"]:
        roles[document["role"]] = roles.get(document["role"], 0) + 1
    page = add(page, f"Reviewed documentary sources: {len(pack['documents'])}.")
    page = add(page, "Source types: " + "; ".join(
        f"{role.replace('_', ' ').lower()} ({count})" for role, count in sorted(roles.items())) + ".")
    page = add(page, "The comparison covers only the supplied, reviewed documents. "
                    "Source locations and integrity hashes are retained in the accompanying evidence pack.")

    page = new_page("Calculated comparison")
    groups = pack["charge_groups"]
    expected_by_period = {(entry["period_id"], entry["charge_key"]): entry for entry in
                          pack.get("expected_ledger", {}).get("entries", [])}
    actual_by_charge = {entry["charge_id"]: entry for entry in
                        pack.get("actual_ledger", {}).get("entries", [])}
    if not groups:
        page = add(page, "No comparable charge group was supported by the supplied reviewed evidence.")
    for group in groups:
        currency = group["currency"]
        expected = group.get("expected_amount") or "Unknown"
        actual = group.get("actual_amount") or "Unknown"
        difference = group.get("difference") or "Unknown"
        charge_ids = group.get("charge_ids", [])
        label = ", ".join(charge_ids) if charge_ids else "Unallocated charge group"
        page = add(page, f"Invoice line: {label}.", bold=True)
        expected_entry = expected_by_period.get((group.get("period_id"), group.get("charge_key")))
        if expected_entry is not None:
            units = expected_entry.get("unit_days") or expected_entry.get("units")
            unit_name = "asset-days" if expected_entry.get("unit_days") is not None else (
                str(expected_entry.get("billing_unit", "units")).lower() + "s")
            rate = expected_entry.get("rate")
            if units is not None and rate is not None:
                quantity = expected_entry.get("quantity")
                basis = f"{units} {unit_name}"
                if quantity is not None and expected_entry.get("unit_days") is None:
                    basis += f" × {quantity} units"
                page = add(page, f"Contract basis: {basis} at {currency} {rate}; "
                                f"expected net {currency} {expected}.")
        actual_entries = [actual_by_charge[charge_id] for charge_id in charge_ids
                          if charge_id in actual_by_charge]
        if len(actual_entries) == 1:
            line = actual_entries[0]
            if line["issued_credit"] == "0.00":
                page = add(page, f"Invoice amount {currency} {line['invoiced_amount']}; "
                                f"no issued credit applied to this line in the supplied-record calculation; "
                                f"billed amount shown {currency} {actual}. Later credits are unverified.")
            else:
                page = add(page, f"Invoice amount {currency} {line['invoiced_amount']}; issued credit "
                                f"{currency} {line['issued_credit']}; net billed after issued credit "
                                f"{currency} {actual}.")
        else:
            page = add(page, f"Net billed {currency} {actual}; expected {currency} {expected}.")
        page = add(page, f"Documentary difference: {currency} {difference}.")
        if group.get("difference") not in {None, "0.00"}:
            page = add(page, "A billing difference is not automatically a recoverable balance.")
        limitations = group.get("limitations", [])
        if limitations:
            page = add(page, "Limitations: " + "; ".join(str(item) for item in limitations), size=9)
    page = add(page, "A positive difference is a supported discrepancy only when source terms, "
                    "identity, dates, credits and conventions were actually reviewed.")

    page = new_page("Findings and limitations")
    findings = pack["findings"]["findings"]
    if not findings:
        page = add(page, "No supported discrepancy was selected for a client-facing claim.")
    for finding in findings:
        decision = {"CONFIRME": "Supported by the supplied records",
                    "A_CONSERVER_AVEC_RESERVES": "Supported with reservations",
                    "INSUFFISAMMENT_ETAYE": "Not sufficiently supported",
                    "REJETE": "Not supported", "ABSTAIN": "No conclusion from supplied records"}
        page = add(page, f"{finding['family'].replace('_', ' ').capitalize()} — "
                         f"{decision.get(finding['status'], 'Review pending')}; "
                         f"documentary difference {finding['currency']} "
                         f"{finding['difference'] if finding['difference'] is not None else 'unknown'}.",
                   bold=True)
        page = add(page, "What the records support: " + str(finding["claim_or_abstention"]))
        page = add(page, "Possible alternative: " + str(finding["best_reason_false"]), size=9)
        for limitation in finding.get("limitations", []):
            page = add(page, "Limit: " + str(limitation), size=9)
    page = add(page, "Each invoice-charge difference is counted only once in the financial summary.")

    page = new_page("Evidence and next action")
    page = add(page, "The accompanying technical evidence pack contains exact source locations, "
                    "quoted spans, entity-link decisions, ledger groups and review hashes.")
    if any(finding["status"] in {"CONFIRME", "A_CONSERVER_AVEC_RESERVES"} for finding in findings):
        page = add(page, "Suggested next step: ask the supplier in writing to reconcile the "
                        "documented charge difference against any accepted changes, asset substitutions "
                        "and credits not present in the supplied records. This is a request for explanation, "
                        "not a demand for payment.")
    elif any(group.get("difference") not in {None, "0.00"} for group in groups):
        page = add(page, "A documentary difference appears in the calculated comparison, but its "
                        "cause and recoverability are not established by the supplied evidence. "
                        "Obtain the specifically missing source documents before making a financial claim.")
    else:
        page = add(page, "No supported client-facing discrepancy was established from the "
                        "supplied evidence. Obtain the specifically missing source documents before "
                        "making a financial claim.")
    page = add(page, "A difference is not an automatic saving or a confirmed debt. "
                    "The accompanying evidence pack records the calculation and open questions.")

    if not 4 <= len(pages) <= 8:
        raise ValueError("Rental client PDF must remain 4–8 pages for the measured pilot envelope")
    return _write_pdf_pages(pages, [], target, renderer=RENDER_VERSION)
