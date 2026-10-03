"""Scoped evidence report consuming a replayed calculation, without arithmetic."""
from __future__ import annotations

import hashlib
from html import escape
from pathlib import Path
from typing import Any

from againward.core.artifact_store import read_json, write_json
from againward.evidence.hashing import stable_hash

from .calculation import calculate
from .protocol import BillingFailure
from .state import load_state

VERSION = "energy-billing-line-report-v1"


def eur(cents: int) -> str:
    if type(cents) is not int:
        raise BillingFailure("REPORT_PROVENANCE_FAILURE", stage="REPORT", expected="integer cents")
    sign = "-" if cents < 0 else ""
    value = abs(cents)
    return f"{sign}{value // 100}.{value % 100:02d} EUR"


def render_report(root: Path, calculation_sha256: str) -> dict[str, Any]:
    import re
    from client_delivery import _PdfPage, _wrap, _write_pdf_pages

    if not isinstance(calculation_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", calculation_sha256):
        raise BillingFailure("REPORT_PROVENANCE_FAILURE", stage="REPORT", expected="calculation receipt hash")
    state = load_state(root)
    stored = read_json(root / "energy_billing" / "calculations" / (calculation_sha256 + ".json"))
    replayed = calculate(state, root, persist=False)
    if stored != replayed or replayed["calculation_sha256"] != calculation_sha256:
        raise BillingFailure("REPORT_PROVENANCE_FAILURE", stage="REPORT", expected="current source-bound replayed calculation")
    line, tariff = stored["readiness"]["line"], stored["readiness"]["tariff"]
    sections = [
        ("Verification de facturation electricite", ["Evaluation technique sur sources synthetiques / rapport interne. Review humaine avant livraison."]),
        ("Perimetre", ["Une ligne de consommation HT. Le total de la facture, abonnement, reseau et taxes ne sont pas verifies.",
                       f"Facture {line['invoice_id']} ; fournisseur {line['supplier_id']} ; PDL / PRM {line['pdl']}.",
                       f"Periode : {line['period']['start']} inclus au {line['period']['end']} exclu."]),
        ("Resultat", [f"Montant facture de cette ligne : {eur(stored['billed_cents'])}.",
                      f"Montant attendu de cette ligne : {eur(stored['expected_cents'])}.",
                      f"Ecart facture moins attendu : {eur(stored['discrepancy_cents'])}.",
                      "Cet ecart observe ne constitue pas un montant recuperable ni un droit juridique etabli."]),
        ("Calcul et autorite", [f"Quantite : {line['quantity']} {line['quantity_unit']}.",
                               f"Prix contractuel : {tariff['price']} {tariff['price_unit']} ; contrat {tariff['contract_id']}.",
                               f"Formule : {stored['component']['formula']} ; arrondi {tariff['rounding_rule']}.",
                               f"Regle de calcul : {stored['component']['rule_version']}.",
                               "Identite, periode, portee et autorite contractuelle ont une review independante sur les textes sources."]),
        ("A verifier avant action", ["Confirmer la completude des pieces et la validite contractuelle avec le responsable du dossier.",
                                    "Faire verifier cet ecart par le fournisseur en joignant la facture et les clauses citees."]),
    ]
    evidence = []
    for eid in stored["authority"]["evidence_ids"]:
        row = state["observations"][eid]
        evidence.append({"evidence_id": eid, **row})
    sections.append(("Preuves", [f"{row['field']} = {row['value']} ; {row['source_id']} ; {row['location']} ; "
                                f"citation : {row['quote']}" for row in evidence]))
    model = {"schema_version": VERSION, "calculation_sha256": calculation_sha256, "sections": sections,
             "evidence": evidence, "delivery_state": "INTERNAL_REVIEW_REQUIRED", "qa_state": "NOT_PERFORMED"}
    digest = stable_hash(model)
    output = root / "energy_billing" / "reports" / digest
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "report_model.json", {**model, "report_sha256": digest})
    markdown = "\n\n".join("## " + title + "\n\n" + "\n\n".join(lines) for title, lines in sections) + "\n"
    (output / "report.md").write_text(markdown, encoding="utf-8")
    html = '<!doctype html><html lang="fr"><meta charset="utf-8"><title>Verification de facturation</title>'
    html += '<style>body{font:16px sans-serif;max-width:850px;margin:auto;padding:20px;overflow-wrap:anywhere}h2{color:#16465d}</style>'
    html += "".join("<section><h2>" + escape(title) + "</h2>" + "".join("<p>" + escape(text) + "</p>" for text in lines) + "</section>"
                    for title, lines in sections) + "</html>"
    (output / "report.html").write_text(html, encoding="utf-8")
    pages = [_PdfPage([])]
    for title, lines in sections:
        for text, size, bold in [(title, 14, True), *((line, 10, False) for line in lines)]:
            for part in _wrap(text, 70 if size >= 14 else 88):
                if pages[-1].y < 90:
                    pages.append(_PdfPage([]))
                pages[-1].text(part, size=size, bold=bold)
    _write_pdf_pages(pages, [], output / "report.pdf", renderer=VERSION)
    result = {"report_sha256": digest, "calculation_sha256": calculation_sha256,
              "delivery_state": "INTERNAL_REVIEW_REQUIRED", "qa_state": "NOT_PERFORMED",
              "files": {name: {"path": str((output / name).relative_to(root)),
                               "sha256": hashlib.sha256((output / name).read_bytes()).hexdigest()}
                        for name in ("report_model.json", "report.md", "report.html", "report.pdf")}}
    write_json(output / "receipt.json", result)
    return result
