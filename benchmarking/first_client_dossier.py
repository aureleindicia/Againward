"""Reproducible DEV-only eight-source Rental dossier; never a blind holdout.

Pass only ``public/rental-eight-sources`` to semantic participants. Private
expected values are for post-run checks and are not report-writing authority.
"""
from __future__ import annotations

from email.message import EmailMessage
import hashlib
import json
from pathlib import Path

from openpyxl import Workbook

from benchmarking.document_renderers import pdf, xlsx


def generate(root: Path) -> dict:
    root = Path(root)
    if root.exists():
        raise ValueError("Dossier already exists; preserve frozen source bytes")
    public = root / "public" / "rental-eight-sources"
    private = root / "private"
    public.mkdir(parents=True)
    private.mkdir()
    pdf(public / "accepted_agreement.pdf", [
        "ACCEPTED EQUIPMENT RENTAL AGREEMENT AG-PILOT-26, dated 2026-08-28.",
        "Supplier RENTAL-NORTH; customer SITE-EAST; net EUR, tax excluded.",
        "Scope A: asset LIFT-5, serial SN-L5-204, electric platform, quantity 2.",
        "Scope B: asset LIFT-50, serial SN-L50-830, electric platform, quantity 1.",
        "Hire starts 2026-09-01; agreement ends 2026-09-10, end date excluded.",
        "Accepted daily rates: LIFT-5 EUR 50.00 per asset per calendar day;",
        "LIFT-50 EUR 30.00 per asset per calendar day. Weekends are chargeable.",
        "No minimum hire period; no discount. No tax is included in these rates.",
        "For each returned unit, billing stops on its signed return date, excluded.",
        "An off-hire request alone does not stop billing. Unreturned units stop",
        "at the agreement end date, excluded. Partial quantities are billed exactly.",
    ])
    pdf(public / "accepted_rate_sheet.pdf", [
        "ACCEPTED NEGOTIATED RATE SHEET for agreement AG-PILOT-26, 2026-08-28.",
        "This duplicates the daily prices in the signed agreement; no amendment.",
        "LIFT-5 / SN-L5-204: net EUR 50.00 per asset per calendar day.",
        "LIFT-50 / SN-L50-830: net EUR 30.00 per asset per calendar day.",
        "The agreement governs start, stop, weekend and minimum conventions.",
    ])
    pdf(public / "invoice_01.pdf", [
        "ISSUED INVOICE INV-PILOT-01, supplier RENTAL-NORTH, 2026-09-11.",
        "Line L1: rental agreement AG-PILOT-26, asset LIFT-5, serial SN-L5-204.",
        "Billed 2026-09-01 to 2026-09-10 exclusive; quantity 2 throughout.",
        "Net rental amount EUR 900.00 excluding tax (18 asset-days x EUR 50.00).",
        "Professional contact: Jean Dupont, jean.dupont@supplier.example.",
    ])
    pdf(public / "invoice_02.pdf", [
        "ISSUED INVOICE INV-PILOT-02, supplier RENTAL-NORTH, 2026-09-11.",
        "Line L1: rental agreement AG-PILOT-26, asset LIFT-50, serial SN-L50-830.",
        "Billed 2026-09-01 to 2026-09-10 exclusive; quantity 1 throughout.",
        "Net rental amount EUR 270.00 excluding tax (9 asset-days x EUR 30.00).",
        "This is a distinct asset from LIFT-5, not a duplicate line.",
    ])
    pdf(public / "issued_credit.pdf", [
        "ISSUED CREDIT NOTE CN-PILOT-01 dated 2026-09-12, RENTAL-NORTH.",
        "Allocated solely to invoice INV-PILOT-01 line L1, asset LIFT-5.",
        "Net credit EUR 100.00 excluding tax. Not a promise or draft credit.",
        "No part of this credit applies to invoice INV-PILOT-02 / LIFT-50.",
    ])
    pdf(public / "signed_return_scan.pdf", [
        "SIGNED RETURN / OFF-HIRE RECORD, agreement AG-PILOT-26.",
        "One of two LIFT-5 units, serial SN-L5-204, returned 2026-09-05.",
        "One LIFT-5 unit remains on hire through the contract end, 2026-09-10.",
        "Synthetic professional signature: J. Dupont; site confirmation: M. Martin.",
        "The LIFT-50 asset is not returned by this record.",
    ], scan=True)
    mail = EmailMessage()
    mail["From"] = "jean.dupont@supplier.example"
    mail["To"] = "purchasing@client.example"
    mail["Subject"] = "Collection request for AG-PILOT-26 / LIFT-5"
    mail.set_content(
        "On 2026-09-04 we requested off-hire and collection of one LIFT-5 unit.\n"
        "The signed return record is dated 2026-09-05; the email itself is not\n"
        "proof of an earlier physical return. LIFT-50 remains separate.\n"
    )
    (public / "supplier_email.eml").write_bytes(mail.as_bytes())
    book = Workbook()
    sheet = book.active
    sheet.title = "Export"
    sheet.append(["Type", "Source reference", "Agreement", "Asset", "Net EUR", "Note"])
    sheet.append(["INVOICE", "INV-PILOT-01/L1", "AG-PILOT-26", "LIFT-5", "900.00", "Mirror only"])
    sheet.append(["INVOICE", "INV-PILOT-02/L1", "AG-PILOT-26", "LIFT-50", "270.00", "Mirror only"])
    sheet.append(["CREDIT", "CN-PILOT-01", "AG-PILOT-26", "LIFT-5", "100.00", "INV-PILOT-01/L1"])
    xlsx(public / "accounting_export.xlsx", book)
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
              for path in sorted(public.iterdir())}
    (private / "expected_after_review.json").write_text(json.dumps({
        "not_for_participant": True, "source_hashes": hashes,
        "expected_lift_5": {"invoice_net": "900.00", "credit": "100.00",
                            "expected_net": "650.00", "potential_discrepancy": "150.00"},
        "expected_lift_50": {"invoice_net": "270.00", "credit": "0.00",
                             "expected_net": "270.00", "potential_discrepancy": "0.00"},
        "limits": ["Agent-authored synthetic case, not blind evaluation",
                   "Credit and signed visual return require independent review"],
    }, indent=2) + "\n", encoding="utf-8")
    return {"public": str(public), "source_count": len(hashes), "source_hashes": hashes,
            "private_truth_not_submitted": str(private)}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    print(json.dumps(generate(parser.parse_args().root), indent=2))
