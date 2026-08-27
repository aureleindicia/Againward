#!/usr/bin/env python3
"""Review Codex de la fixture mensuelle; lit les nombres calcules par Python."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from energy_mvp.investigation import (
    information_request,
    next_information_request,
    validate_follow_up_logic,
)
from energy_mvp.models import AnalysisBundle
from energy_mvp.report import write_bundle_json
from workspace.demo_review import render_html


def fmt(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def build_review(quantitative: dict[str, Any]) -> dict[str, Any]:
    tests = quantitative["tests"]
    review = {
        "schema_version": 2,
        "analysis_type": "agentic_energy_investigation_monthly",
        "source": quantitative["source"],
        "ground_truth_used": False,
        "follow_up_policy": {
            "required_for": ["INSUFFISAMMENT_ETAYE", "A_CONSERVER_AVEC_RESERVES"],
            "forbidden_for": ["CONFIRME", "REJETE"],
            "trigger": "incertitude materielle que la reponse peut reduire",
            "selection": "information minimale, realiste et la moins couteuse d'abord",
        },
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
                "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
                "follow_up_requests": [information_request(
                    request_id="M01-Q1", request_type="question_metier",
                    ask_client=("Pour chacun des trois mois a production nulle, confirmer en une ligne "
                                "si le site etait ferme et quelles utilites devaient obligatoirement rester actives."),
                    why_useful=("Cette reponse indique si l'energie correspond a un arret reel, a une "
                                "activite non renseignee ou a des besoins incompressibles connus."),
                    information_value="elevee: la reponse determine si les mois sont comparables a une fermeture reelle.",
                    hypotheses_distinguished=("charge potentiellement evitable pendant fermeture",
                                              "charge legitime ou production manquante dans le fichier"),
                    responsible_role="responsable du site",
                    client_effort="Environ 10 minutes avec le calendrier d'exploitation.",
                    effort_level="tres_faible",
                    expected_if_true=("Si une charge evitable existe, le client confirmera une fermeture complete "
                                      "sans procede ni exigence de securite expliquant tout ou partie de la consommation."),
                )],
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
                "physical_cause_status": "non_etablie_et_non_inferable_a_cette_resolution",
                "follow_up_requests": [],
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
                "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
                "follow_up_requests": [information_request(
                    request_id="M03-Q1", request_type="question_metier",
                    ask_client=("Indiquer si octobre avait un mix produit, un nombre de jours ouvres ou des "
                                "horaires sensiblement differents d'un mois actif habituel, et lequel."),
                    why_useful=("Ces trois facteurs simples peuvent expliquer le ratio mensuel sans "
                                "degradation energetique et evitent une collecte instrumentee prematuree."),
                    information_value="elevee: un changement operationnel documente peut expliquer le ratio sans instrumentation.",
                    hypotheses_distinguished=("degradation reelle de l'efficacite en octobre",
                                              "effet normal du mix produit, des jours ouvres ou des horaires"),
                    responsible_role="responsable de production",
                    client_effort="Environ 10 a 15 minutes avec le responsable de production.",
                    effort_level="tres_faible",
                    expected_if_true=("Si la degradation est reelle, aucun changement operationnel important ne "
                                      "sera signale alors que l'intensite restera anormalement haute."),
                )],
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
    validate_follow_up_logic(review["hypotheses"])
    return review


def render_markdown(review: dict[str, Any], quantitative: dict[str, Any]) -> str:
    tests = quantitative["tests"]
    by_id = {item["hypothesis_id"]: item for item in review["hypotheses"]}

    def request_lines(hypothesis_id: str) -> list[str]:
        request = next_information_request(by_id[hypothesis_id])
        if request is None:
            return []
        return [
            f"### {hypothesis_id} — prochaine verification minimale", "",
            f"- A demander : {request['ask_client']}",
            f"- Pourquoi : {request['why_useful']}",
            f"- Valeur informationnelle : {request['information_value']}",
            "- Hypotheses departagees : " + " / ".join(request["hypotheses_distinguished"]) + ".",
            f"- Responsable pressenti : {request['responsible_role']}.",
            f"- Effort client : {request['client_effort']} ({request['effort_level']}).",
            f"- Attendu si l'hypothese est vraie : {request['expected_if_true']}",
            "- Cause physique : non etablie avec les donnees disponibles.", "",
        ]
    inactive = tests["M01_zero_production_months"]
    power = tests["M02_declared_power"]
    intensity = tests["M03_intensity"]
    return "\n".join([
        "# Analyse et investigation de performance energetique — donnees mensuelles", "",
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
        "Les questions ci-dessous ne sont posees que parce que M01 et M03 restent indeterminees; "
        "M02, deja rejetee, ne declenche aucune demande.", "",
        *request_lines("M01"),
        *request_lines("M03"),
        "## 11. Hypotheses rejetees importantes", "",
        f"M02 est rejetee : {fmt(power['maximum_power_kw'], 1)} kW en octobre ne permet pas d'affirmer un demarrage simultane sans heure ni duree.", "",
        "## 12. Recommandations", "",
        "1. Poser d'abord les deux questions minimales M01 et M03 ci-dessus.",
        "2. Ne demander une courbe 15 minutes que si leurs reponses laissent une incertitude "
        "materielle et que l'enjeu justifie cet effort supplementaire.",
        "3. Ne rien demander pour M02 : l'hypothese de demarrage est deja rejetee.",
        "Aucune cause physique n'est etablie avec ces douze agregats mensuels.", "",
        "## 13. Limites", "",
        "Douze agregats mensuels, aucune temperature, aucun horaire, aucune mesure machine et aucune preuve de causalite.",
        "Cette prestation ne constitue pas un audit energetique reglementaire.", "",
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
