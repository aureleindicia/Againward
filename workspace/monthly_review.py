#!/usr/bin/env python3
"""Review Codex de la fixture mensuelle; lit les nombres calcules par Python."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from energy_mvp.models import AnalysisBundle
from energy_mvp.report import write_bundle_json
from workspace.demo_review import render_html


def fmt(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def build_review(quantitative: dict[str, Any]) -> dict[str, Any]:
    tests = quantitative["tests"]
    return {
        "schema_version": 1,
        "analysis_type": "agentic_energy_prediagnostic_monthly",
        "source": quantitative["source"],
        "ground_truth_used": False,
        "hypotheses": [
            {
                "hypothesis_id": "M01",
                "observation": "Trois mois ont une production declaree nulle.",
                "hypothesis": "Leur consommation constitue une economie recuperable.",
                "tests_requested": [
                    "Quantifier energie et cout associe.",
                    "Rechercher heures actives, charge incompressible et jours couverts.",
                ],
                "results": tests["M01_zero_production_months"],
                "alternative_explanations": [
                    "Charges fixes legitimes.",
                    "Production partielle non visible dans l'agregat.",
                    "Arret planifie avec utilites maintenues.",
                ],
                "best_reason_false": (
                    "Un total mensuel a production nulle ne separe ni la charge incompressible "
                    "ni les heures d'exploitation."
                ),
                "decision": "INSUFFISAMMENT_ETAYE",
                "confidence": {"observation": "elevee", "opportunity": "faible"},
            },
            {
                "hypothesis_id": "M02",
                "observation": "La valeur de puissance declaree en octobre est la plus haute.",
                "hypothesis": "Un demarrage simultane d'equipements explique cette pointe.",
                "tests_requested": [
                    "Verifier la duree et l'heure de la pointe.",
                    "Comparer production et demarrages a granularite fine.",
                ],
                "results": tests["M02_declared_power"],
                "alternative_explanations": [
                    "Maximum mensuel normal.",
                    "Convention de colonne non documentee.",
                    "Production mensuelle legerement superieure.",
                ],
                "best_reason_false": (
                    "Un timestamp mensuel et une puissance unique ne donnent ni heure ni duree; "
                    "la cause de demarrage est intestable."
                ),
                "decision": "REJETE",
                "confidence": {"observation": "elevee", "cause": "nulle"},
            },
            {
                "hypothesis_id": "M03",
                "observation": "L'intensite d'octobre depasse la mediane des mois actifs.",
                "hypothesis": "Octobre revele une degradation robuste d'efficacite.",
                "tests_requested": [
                    "Comparer l'ecart a la dispersion des mois actifs.",
                    "Chercher une baseline validee passe-vers-futur.",
                ],
                "results": tests["M03_intensity"],
                "alternative_explanations": [
                    "Mix produit et charges fixes non mesures.",
                    "Nombre de jours ouvres different.",
                    "Variabilite mensuelle normale.",
                ],
                "best_reason_false": (
                    "Neuf points actifs ne permettent pas une baseline temporelle robuste ni le "
                    "controle des facteurs confondants."
                ),
                "decision": "INSUFFISAMMENT_ETAYE",
                "confidence": {"observation": "elevee", "opportunity": "faible"},
            },
        ],
        "final_review": {
            "confirmed": [],
            "with_reservations": [],
            "insufficient": ["M01", "M03"],
            "rejected": ["M02"],
            "annualization_performed": False,
            "recoverable_savings_claimed": False,
            "intraday_claim_made": False,
        },
    }


def render_markdown(review: dict[str, Any], quantitative: dict[str, Any]) -> str:
    tests = quantitative["tests"]
    inactive = tests["M01_zero_production_months"]
    power = tests["M02_declared_power"]
    intensity = tests["M03_intensity"]
    return "\n".join([
        "# Pre-diagnostic energetique agentique — donnees mensuelles", "",
        "## 1. Resume executif", "",
        "Aucune opportunite energetique n'est confirmee. Les totaux sont calculables, mais la granularite mensuelle interdit les conclusions nocturnes, horaires et de demarrage.", "",
        "## 2. Donnees analysees", "",
        f"- 12 mesures couvrant {quantitative['dataset']['coverage_start']} -> {quantitative['dataset']['coverage_end']}.",
        "- Energie, production, tarif et une valeur de puissance par mois.", "",
        "## 3. Qualite des donnees", "",
        "Les douze lignes sont exploitables pour les totaux. La resolution, et non la proprete du fichier, constitue la limitation dominante.", "",
        "## 4. Profil energetique", "",
        f"Les trois mois a production nulle totalisent {fmt(inactive['observed_energy_kwh'])} kWh, soit {fmt(inactive['associated_cost'], 2)} EUR de cout associe observe.", "",
        "## 5. Baseline", "",
        "Aucune baseline validee n'est retenue : neuf mois actifs ne suffisent pas pour une calibration passe-vers-futur robuste avec variables contextuelles.", "",
        "## 6. Investigations realisees", "",
        "M01 consommation sans production, M02 puissance d'octobre, M03 intensite d'octobre.", "",
        "## 7. Opportunites confirmees", "", "Aucune.", "",
        "## 8. Efficacite energetique", "",
        f"Octobre atteint {fmt(intensity['october_kwh_per_unit'], 3)} kWh/unite, soit {fmt(intensity['october_delta_percent_vs_median'], 1)} % au-dessus de la mediane. Ce signal reste insuffisamment etaye sans mix produit, jours ouvres et temperature.", "",
        "## 9. Impact economique", "",
        "Le cout des mois sans production est un cout observe, pas une economie. Aucun potentiel recuperable ni projection annuelle n'est publie.", "",
        "## 10. Opportunites necessitant verification", "",
        "- Obtenir des courbes de charge horaires ou 15 minutes pour les mois sans production.",
        "- Documenter la signification exacte de la colonne de puissance.",
        "- Ajouter jours ouvres, mix produit et temperature avant de revoir l'intensite.", "",
        "## 11. Hypotheses rejetees importantes", "",
        f"M02 est rejetee : {fmt(power['maximum_power_kw'], 1)} kW en octobre ne permet pas d'affirmer un demarrage simultane sans heure ni duree.", "",
        "## 12. Recommandations", "",
        "1. Collecter au minimum quatre semaines a 15 minutes.",
        "2. Confirmer les unites, la position des timestamps et le sens de la puissance.",
        "3. Reprendre ensuite M01 et M03 avec des periodes comparables.", "",
        "## 13. Limites", "",
        "Douze agregats mensuels, aucune temperature, aucun horaire, aucune mesure machine et aucune preuve de causalite.", "",
        "## 14. Methodologie", "",
        "Normalisation deterministe, controles de resolution, quantification Python, formulation d'hypotheses, recherche de contre-explications et review contradictoire Codex.", "",
    ])


def main() -> int:
    quantitative = json.loads(Path("reports/monthly_quantitative_results.json").read_text(encoding="utf-8"))
    automatic = json.loads(Path("reports/demo.json").read_text(encoding="utf-8"))
    review = build_review(quantitative)
    markdown = render_markdown(review, quantitative)
    bundle = AnalysisBundle(
        automatic_analysis=automatic,
        quantitative_results=quantitative,
        investigation=review,
        events=[],
        artifacts={
            "investigation_json": "reports/monthly_investigation.json",
            "report_markdown": "reports/monthly_final.md",
            "report_html": "reports/monthly_final.html",
        },
    )
    write_bundle_json(bundle, "reports/monthly_analysis.json")
    Path("reports/monthly_investigation.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path("reports/monthly_final.md").write_text(markdown, encoding="utf-8")
    Path("reports/monthly_final.html").write_text(render_html(markdown), encoding="utf-8")
    print("Review mensuelle ecrite: reports/monthly_investigation.json")
    print("Rapports mensuels ecrits: reports/monthly_final.md, reports/monthly_final.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
