"""Compact Rental client PDF from already validated evidence and analyst prose.

The existing stdlib PDF primitive is reused; no Energy arithmetic or claim
policy is imported. This is a human-review candidate, never auto-delivered.
"""
from __future__ import annotations

from decimal import Decimal, InvalidOperation
from pathlib import Path
import re

from client_delivery import _PdfPage, _wrap, _write_pdf_pages


_MONEY = re.compile(r"\b(EUR|USD|GBP|CHF|CAD|AUD|NZD)\s*([0-9]+(?:[.,][0-9]+)?)\b", re.I)


def _allowed_amounts(pack: dict) -> set[tuple[str, Decimal]]:
    result = set()
    for row in [*pack["charge_groups"], *pack["findings"]["findings"]]:
        currency = row.get("currency")
        for key in ("actual_amount", "expected_amount", "difference", "recovery_grade_amount"):
            value = row.get(key)
            if currency and value is not None:
                result.add((currency, Decimal(str(value))))
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
    if re.search(r"\d", "".join(remainder)):
        raise ValueError("Free numeric/date/identifier claims need a validated structured citation")


def render_rental_pdf(pack: dict, synthesis: str, target: Path) -> dict:
    validate_synthesis(synthesis, pack)
    pages: list[_PdfPage] = []

    def new_page(title: str) -> _PdfPage:
        page = _PdfPage([])
        pages.append(page)
        page.text("AGAINWARD  |  Rental invoice verification", size=9, bold=True)
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
    page = add(page, synthesis)
    page = add(page, "This is a documented comparison, not a debt, legal opinion or guaranteed recovery.")
    page = add(page, "All amounts below are net and come from the validated evidence pack; "
                    "unresolved sources or contract interpretations require an explicit STOP.")

    page = new_page("Documents and scope")
    page = add(page, f"Reviewed documentary sources: {len(pack['documents'])}.")
    for document in pack["documents"]:
        page = add(page, f"{document['role']}: source SHA-256 {document['sha256'][:20]}...; "
                         f"status {document['status']}.")
    page = add(page, "Full source hashes, exact locations and review decisions are in the accompanying evidence pack.")

    page = new_page("Calculated comparison")
    groups = pack["charge_groups"]
    if not groups:
        page = add(page, "No comparable charge group was supported by the supplied reviewed evidence.")
    for group in groups:
        currency = group["currency"]
        expected = group.get("expected_amount") or "Unknown"
        actual = group.get("actual_amount") or "Unknown"
        difference = group.get("difference") or "Unknown"
        page = add(page, f"{currency} | billed {actual} | expected {expected} | difference {difference}.")
        limitations = group.get("limitations", [])
        if limitations:
            page = add(page, "Limitations: " + "; ".join(str(item) for item in limitations), size=9)
    page = add(page, "A positive difference is a supported discrepancy only when source terms, "
                    "identity, dates, credits and conventions were actually reviewed.")

    page = new_page("Findings and adversarial checks")
    findings = pack["findings"]["findings"]
    if not findings:
        page = add(page, "No supported discrepancy was selected for a client-facing claim.")
    for finding in findings:
        page = add(page, f"{finding['family']} | {finding['status']} | {finding['evidence_level']} | "
                         f"{finding['currency']} {finding['difference'] if finding['difference'] is not None else 'Unknown'}.",
                   bold=True)
        page = add(page, "Claim/abstention: " + str(finding["claim_or_abstention"]))
        page = add(page, "Best reason this may be false: " + str(finding["best_reason_false"]), size=9)
        for limitation in finding.get("limitations", []):
            page = add(page, "Limit: " + str(limitation), size=9)
    page = add(page, "Repeated finding families on one charge group are not added together.")

    page = new_page("Evidence and next action")
    page = add(page, "The accompanying technical evidence pack contains exact source locations, "
                    "quoted spans, entity-link decisions, ledger groups and review hashes.")
    page = add(page, "The owner must inspect each positive financial claim, confirm the cited clause and "
                    "return/credit timeline, and approve the exact PDF hash before delivery.")
    page = add(page, "If no difference is supported, state that the supplied evidence did not establish one; "
                    "do not convert an unknown into zero or an apparent difference into savings.")
    page = add(page, "Only a human may decide what to ask the client or whether a finding merits supplier discussion.")

    if not 4 <= len(pages) <= 8:
        raise ValueError("Rental client PDF must remain 4–8 pages for the measured pilot envelope")
    return _write_pdf_pages(pages, [], target, renderer="againward-rental-reviewed-evidence-v1")
