#!/usr/bin/env python3
"""Review Codex specifique a la demo ; les chiffres sont lus, jamais recalcules ici."""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from energy_mvp.charts import (
    plot_daily_residual,
    plot_energy_production,
    plot_observed_expected,
    plot_power_timeseries,
)
from energy_mvp.io import load_data
from energy_mvp.investigation import (
    information_request,
    next_information_request,
    validate_follow_up_logic,
)
from energy_mvp.models import AnalysisBundle, AnalysisEvent
from energy_mvp.recommendations import validate_recommendations
from energy_mvp.report import write_bundle_json
from energy_mvp.toolbox import calculate_residuals


def fmt(value: float, decimals: int = 1) -> str:
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def build_operational_recommendations(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_id = {entry["hypothesis_id"]: entry for entry in entries}
    new_requests = {
        "H04": information_request(
            request_id="H04-Q1", request_type="donnee_complementaire",
            ask_client=("Comparer le journal de production et les changements de recette, cadence ou réglage "
                        "pendant les 11 jours concernés avec les 15 jours précédents."),
            why_useful=("Le journal peut séparer une contrainte de procédé non mesurée d'une dégradation "
                        "énergétique réelle à production comparable."),
            information_value="élevée: la réponse peut confirmer ou déclasser l'interprétation d'efficacité.",
            hypotheses_distinguished=("dégradation énergétique du procédé", "changement légitime de recette ou cadence"),
            responsible_role="responsable de production",
            client_effort="20 à 30 minutes sur les journaux existants", effort_level="faible",
            expected_if_true=("Si l'efficacité s'est réellement dégradée, aucun changement de recette, cadence "
                              "ou exigence qualité suffisant ne coïncidera avec les 11 jours."),
        ),
        "H05": information_request(
            request_id="H05-Q1", request_type="test_terrain_simple",
            ask_client=("Lors d'un prochain arrêt autorisé, relever pendant 30 minutes la pression réseau et "
                        "le nombre de démarrages compresseur sans ouvrir de vanne ni modifier de sécurité."),
            why_useful=("Un maintien de pression accompagné de cycles compresseur permet de prioriser une fuite "
                        "ou un auxiliaire pneumatique avant une campagne de mesure plus coûteuse."),
            information_value="moyenne: le test cible une cause plausible mais n'explique pas tous les auxiliaires.",
            hypotheses_distinguished=("dérive du réseau d'air comprimé", "autre charge fixe ou dérive de régulation"),
            responsible_role="responsable maintenance",
            client_effort="30 minutes pendant un arrêt déjà planifié", effort_level="faible",
            expected_if_true=("Si l'air comprimé contribue à la dérive, le compresseur cyclera ou la pression "
                              "baissera mesurablement sans demande de production."),
        ),
        "H06": information_request(
            request_id="H06-Q1", request_type="question_metier",
            ask_client=("Lister les équipements, consignes, travaux ou exigences d'exploitation ajoutés ou "
                        "modifiés autour du début exact du nouveau palier."),
            why_useful=("Un changement daté peut expliquer le palier permanent et éviter d'accuser à tort une panne."),
            information_value="élevée: une modification concordante peut rendre la hausse légitime ou cibler un test.",
            hypotheses_distinguished=("nouveau besoin permanent légitime", "équipement ou consigne resté actif inutilement"),
            responsible_role="responsable de site avec maintenance",
            client_effort="entretien de 15 minutes et consultation du journal de travaux", effort_level="tres_faible",
            expected_if_true=("Si le palier est involontaire, aucun nouveau besoin permanent suffisant ne sera "
                              "documenté à sa date d'apparition."),
        ),
    }
    causes = {
        "H01": ["utilité nocturne nécessaire", "consigne ou équipement maintenu sans besoin"],
        "H02": ["maintenance ou nettoyage", "charge de week-end non planifiée"],
        "H03": ["opération ponctuelle légitime", "incident ou mesure capteur erronée"],
        "H04": ["dégradation du procédé", "recette, cadence ou qualité non mesurée"],
        "H05": ["fuite d'air comprimé", "dérive de régulation", "autre auxiliaire fixe"],
        "H06": ["nouveau besoin légitime", "consigne modifiée", "auxiliaire maintenu actif"],
    }
    owners = {
        "H01": "responsable de site", "H02": "responsable de production ou maintenance",
        "H03": "opérateur présent", "H04": "responsable de production",
        "H05": "responsable maintenance", "H06": "responsable de site avec maintenance",
    }
    recommendations = []
    for hypothesis_id in ("H01", "H02", "H03", "H04", "H05", "H06"):
        entry = by_id[hypothesis_id]
        results = entry["results"]
        energy_key = "excess_after_fixed_drift_removal_kwh" if hypothesis_id == "H04" else "excess_energy_kwh"
        request = (
            entry["follow_up_requests"][0]
            if entry.get("follow_up_requests") else new_requests[hypothesis_id]
        )
        confidence = "high" if entry["confidence"].get("opportunity") == "elevee" else "medium" if entry["confidence"].get("opportunity") == "moyenne" else "low"
        recommendations.append({
            "recommendation_id": f"R-{hypothesis_id}",
            "finding_id": hypothesis_id,
            "measured_anomaly": entry["observation"],
            "observed_impact": {
                "period": f"{results['period'][0]}/{results['period'][1]}",
                "excess_energy_kwh": results[energy_key],
                "associated_cost": results["cost"],
                "quantitative_source": f"reports/demo_quantitative_results.json#hypotheses.{hypothesis_id}.{energy_key}",
            },
            "confidence": {"level": confidence, "basis": entry["tests_requested"]},
            "plausible_causes": [
                {"rank": index, "cause": cause, "evidence_status": "untested"}
                for index, cause in enumerate(causes[hypothesis_id], start=1)
            ],
            "physical_cause_status": "plausible_not_proven",
            "action_status": "verification_only",
            "next_verification": request,
            "owner_role": owners[hypothesis_id],
            "verification_effort": request["client_effort"],
            "expected_if_hypothesis_true": request["expected_if_true"],
            "post_action_measurement": {
                "metric": "puissance moyenne ou énergie sur la même fenêtre comparable",
                "baseline_definition": "périodes comparables antérieures utilisées dans l'investigation",
                "evaluation_window": "au moins trois occurrences comparables après intervention",
                "success_rule": "effet cohérent avec une prédiction pré-enregistrée et hors variabilité de référence",
            },
            "recoverable_saving": None,
        })
    validate_recommendations(recommendations)
    return recommendations


def build_review(quantitative: dict[str, Any]) -> dict[str, Any]:
    hypotheses = quantitative["hypotheses"]

    def evidence(hypothesis_id: str) -> dict[str, Any]:
        return hypotheses[hypothesis_id]

    entries = [
        {
            "hypothesis_id": "H01",
            "observation": "Hausse nocturne bornee du residu de puissance.",
            "hypothesis": "Une charge additionnelle fonctionne la nuit sans production.",
            "tests_requested": [
                "Comparer les nuits a la reference et a la periode posterieure.",
                "Verifier production, recurrence et temperature.",
                "Quantifier l'energie au-dessus du residu nocturne de reference.",
            ],
            "results": evidence("H01"),
            "alternative_explanations": [
                "Temperature exterieure.",
                "Utilite nocturne necessaire au procede.",
                "Artefact lie aux trous de donnees.",
            ],
            "best_reason_false": (
                "La charge peut etre une utilite nocturne legitime ; les donnees ne prouvent "
                "ni l'equipement responsable ni la part evitable."
            ),
            "adversarial_review": (
                "Production nulle sur 100 % des points, recurrence 15/15 jours, retour au "
                "niveau de reference apres la fenetre. La temperature n'explique que "
                f"{evidence('H01')['temperature_explained_delta_kw']:.6f} kW."
            ),
            "decision": "A_CONSERVER_AVEC_RESERVES",
            "confidence": {"observation": "elevee", "opportunity": "moyenne"},
            "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
            "follow_up_requests": [information_request(
                request_id="H01-Q1", request_type="question_metier",
                ask_client=("Demander au responsable de site quels equipements ou utilites devaient rester "
                            "actifs entre 00:00 et 05:00 pendant les 15 nuits concernees."),
                why_useful=("Une liste courte des usages nocturnes permet de distinguer un besoin de procede "
                            "d'un equipement reste actif par habitude ou erreur de consigne."),
                information_value="elevee: la reponse peut faire passer la piste de reservee a rejetee ou a test terrain.",
                hypotheses_distinguished=("charge nocturne necessaire au procede",
                                          "charge nocturne non requise ou consigne incorrecte"),
                responsible_role="responsable de site",
                client_effort="Entretien de 10 minutes, sans mesure ni arret d'equipement.",
                effort_level="tres_faible",
                expected_if_true=("Si la charge est non requise, aucun usage nocturne obligatoire ne sera identifie "
                                  "pour expliquer le palier observe."),
            )],
            "severity": "moyenne",
            "report_section": "verification",
        },
        {
            "hypothesis_id": "H02",
            "observation": "Charge de jour sur quatre jours de week-end consecutifs.",
            "hypothesis": "Une charge inhabituelle fonctionne le week-end sans production.",
            "tests_requested": [
                "Comparer aux week-ends anterieurs et posterieurs a heures egales.",
                "Verifier production, recurrence et temperature.",
            ],
            "results": evidence("H02"),
            "alternative_explanations": [
                "Maintenance ou nettoyage planifie.",
                "Temperature.",
                "Derive de charge fixe."
            ],
            "best_reason_false": (
                "Une activite non mesuree par la production peut etre normale pendant ces week-ends."
            ),
            "adversarial_review": (
                "Production nulle, signal present 4/4 jours et absent avant. La temperature "
                f"n'explique que {evidence('H02')['temperature_explained_delta_kw']:.6f} kW. "
                "La periode posterieure contient deja le debut d'une autre derive, donc elle "
                "n'est pas utilisee pour gonfler l'exces."
            ),
            "decision": "A_CONSERVER_AVEC_RESERVES",
            "confidence": {"observation": "elevee", "opportunity": "moyenne"},
            "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
            "follow_up_requests": [information_request(
                request_id="H02-Q1", request_type="question_metier",
                ask_client=("Verifier dans le planning si maintenance, nettoyage ou production non comptabilisee "
                            "avait lieu pendant les quatre jours de week-end identifies."),
                why_useful=("Le planning existant suffit a tester l'explication operationnelle la plus probable "
                            "avant toute visite ou instrumentation."),
                information_value="elevee: le planning peut expliquer completement les quatre occurrences sans nouvelle mesure.",
                hypotheses_distinguished=("activite de week-end legitime mais absente de la production",
                                          "charge de week-end sans activite planifiee"),
                responsible_role="responsable de production ou maintenance",
                client_effort="Lecture du planning et reponse oui/non, environ 5 minutes.",
                effort_level="tres_faible",
                expected_if_true=("Si la charge est anormale, le planning ne montrera ni maintenance, ni nettoyage, "
                                  "ni production pendant ces quatre jours."),
            )],
            "severity": "faible",
            "report_section": "verification",
        },
        {
            "hypothesis_id": "H03",
            "observation": "Huit quarts d'heure consecutifs depassent la baseline de plus de 80 kW.",
            "hypothesis": "Un evenement ponctuel de deux heures a cree un pic inhabituel.",
            "tests_requested": [
                "Regrouper les points en evenement.",
                "Comparer production, temperature et mardis a heures egales.",
                "Rechercher la recurrence."
            ],
            "results": evidence("H03"),
            "alternative_explanations": [
                "Demarrage normal d'equipement.",
                "Operation exceptionnelle necessaire.",
                "Valeur capteur erronee."
            ],
            "best_reason_false": (
                "L'evenement est unique ; sans journal d'exploitation, son caractere evitable "
                "ne peut pas etre etabli."
            ),
            "adversarial_review": (
                "Production et temperature sont comparables ; les huit points forment un seul "
                "evenement. Aucune recurrence ni projection annuelle n'est retenue."
            ),
            "decision": "A_CONSERVER_AVEC_RESERVES",
            "confidence": {"observation": "elevee", "opportunity": "faible"},
            "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
            "follow_up_requests": [information_request(
                request_id="H03-Q1", request_type="question_metier",
                ask_client=("Demander ce qui s'est passe le jour et pendant les deux heures exactes du pic: "
                            "demarrage, essai, incident, maintenance ou aucune operation connue."),
                why_useful=("Le journal ou la memoire de l'operateur permet de separer un evenement normal et "
                            "necessaire d'un incident ou d'une valeur capteur douteuse."),
                information_value="moyenne: la reponse peut classer le pic comme operation legitime, incident ou mesure douteuse.",
                hypotheses_distinguished=("operation ponctuelle legitime",
                                          "incident energetique ou mesure capteur erronee"),
                responsible_role="operateur present ou responsable de production",
                client_effort="Question de 5 minutes a l'operateur; aucun test terrain demande.",
                effort_level="tres_faible",
                expected_if_true=("Si le pic correspond a un incident energetique, l'operateur signalera un "
                                  "fonctionnement inhabituel plutot qu'un demarrage planifie."),
            )],
            "severity": "faible",
            "report_section": "verification",
        },
        {
            "hypothesis_id": "H04",
            "observation": "Le residu actif augmente sans hausse equivalente du residu inactif.",
            "hypothesis": "L'efficacite energie-production se degrade temporairement.",
            "tests_requested": [
                "Controler production, temperature, activite et mix produit.",
                "Retrancher le residu inactif journalier pour isoler la derive fixe.",
                "Verifier la recurrence sur chaque jour de production."
            ],
            "results": evidence("H04"),
            "alternative_explanations": [
                "Production plus elevee.",
                "Mix produit B.",
                "Temperature.",
                "Double comptage avec la derive fixe H05."
            ],
            "best_reason_false": (
                "Le type produit A/B peut ne pas decrire toute la complexite du mix ou des cadences."
            ),
            "adversarial_review": (
                "Production moyenne quasi stable, part de produit B legerement plus faible et "
                f"effet contextuel modele de {evidence('H04')['modelled_context_delta_kw']:.6f} kW. "
                "Le calcul d'exces retire explicitement H05 avant integration."
            ),
            "decision": "CONFIRME",
            "confidence": {"observation": "elevee", "opportunity": "elevee"},
            "severity": "moyenne",
            "report_section": "confirmed",
        },
        {
            "hypothesis_id": "H05",
            "observation": "Le residu inactif augmente progressivement pendant trente jours.",
            "hypothesis": "La charge fixe derive independamment de la production.",
            "tests_requested": [
                "Mesurer la pente sur les seules periodes inactives.",
                "Comparer la pente a celle impliquee par la temperature.",
                "Verifier la qualite d'ajustement et quantifier par jour."
            ],
            "results": evidence("H05"),
            "alternative_explanations": [
                "Rechauffement exterieur.",
                "Hausse de production.",
                "Effet de H04."
            ],
            "best_reason_false": (
                "Une variable saisonniere non mesuree et correlee au temps pourrait imiter une derive."
            ),
            "adversarial_review": (
                "Le signal existe lorsque la production est nulle. La pente observee est "
                f"{evidence('H05')['inactive_trend']['slope_per_day']:.6f} kW/j avec "
                f"R2={evidence('H05')['inactive_trend']['r_squared']:.6f}, contre "
                f"{evidence('H05')['temperature_implied_residual_slope_kw_per_day']:.6f} kW/j "
                "implique par la temperature."
            ),
            "decision": "CONFIRME",
            "confidence": {"observation": "elevee", "opportunity": "elevee"},
            "severity": "elevee",
            "report_section": "confirmed",
        },
        {
            "hypothesis_id": "H06",
            "observation": "Apres la derive, un niveau residuel inactif reste durablement eleve.",
            "hypothesis": "La baseline fixe a change de niveau de facon persistante.",
            "tests_requested": [
                "Comparer trente jours a la reference inactive.",
                "Verifier stabilite, recurrence et temperature.",
                "Limiter la quantification a la periode observee."
            ],
            "results": evidence("H06"),
            "alternative_explanations": [
                "Temperature saisonniere.",
                "Production ou mix produit.",
                "Changement de qualite des donnees."
            ],
            "best_reason_false": (
                "Un nouveau besoin permanent mais legitime peut expliquer le niveau sans constituer une economie."
            ),
            "adversarial_review": (
                "Signal present 30/30 jours et mesure sur les seules periodes inactives. "
                f"Ecart moyen {evidence('H06')['post_inactive_residual_mean_kw']:.6f} kW, "
                f"ecart-type journalier {evidence('H06')['post_inactive_residual_sd_kw']:.6f} kW ; "
                f"temperature explicative {evidence('H06')['temperature_explained_delta_kw']:.6f} kW."
            ),
            "decision": "CONFIRME",
            "confidence": {"observation": "elevee", "opportunity": "elevee"},
            "severity": "elevee",
            "report_section": "confirmed",
        },
        {
            "hypothesis_id": "H07",
            "observation": "L'intensite mensuelle de mai est nettement plus haute.",
            "hypothesis": "Mai constitue une opportunite d'intensite independante.",
            "tests_requested": [
                "Verifier la couverture du mois.",
                "Comparer a production equivalente et aux residus des hypotheses existantes."
            ],
            "results": {
                "may_is_partial": True,
                "covered_days": 4,
                "overlaps_with": ["H04", "H05", "H06"],
            },
            "alternative_explanations": ["Mois incomplet.", "Charge fixe a faible production."],
            "best_reason_false": "Le ratio agrege est confondu et deja explique par des signaux temporels plus solides.",
            "adversarial_review": "Aucune energie ni economie additionnelle n'est attribuee a ce ratio.",
            "decision": "REJETE",
            "confidence": {"observation": "moyenne", "opportunity": "nulle"},
            "severity": "non_applicable",
            "report_section": "rejected",
        },
        {
            "hypothesis_id": "H08",
            "observation": "Le signal automatique de pointe vise les memes huit points que H03.",
            "hypothesis": "La pointe de puissance constitue une opportunite supplementaire.",
            "tests_requested": ["Comparer les timestamps et l'energie attribuee a H03."],
            "results": quantitative["double_counting"]["automatic_spike_and_peak_signal_same_event"],
            "alternative_explanations": ["Deux methodes detectent le meme evenement."],
            "best_reason_false": "Additionner les deux signaux doublerait exactement l'energie du pic.",
            "adversarial_review": "H08 est fusionnee dans H03 et ne porte aucune valeur additionnelle.",
            "decision": "REJETE",
            "confidence": {"observation": "elevee", "opportunity": "nulle"},
            "severity": "non_applicable",
            "report_section": "rejected",
        },
    ]
    validate_follow_up_logic(entries)
    recommendations = build_operational_recommendations(entries)
    event_types = {
        "H01": "night_anomaly",
        "H02": "weekend_anomaly",
        "H03": "point_spike",
        "H04": "efficiency_drop",
        "H05": "progressive_drift",
        "H06": "permanent_baseline_shift",
    }
    supporting_methods = {
        "H01": ["production_activity_baseline", "night_comparison", "temperature_control"],
        "H02": ["production_activity_baseline", "weekend_comparison", "temperature_control"],
        "H03": ["robust_residual", "temporal_grouping", "similar_period_comparison"],
        "H04": ["production_baseline", "product_mix_control", "inactive_residual_removal"],
        "H05": ["inactive_residual_trend", "linear_trend", "temperature_falsification"],
        "H06": ["inactive_level_comparison", "persistence_test", "temperature_falsification"],
    }
    related = {"H04": ["H05"], "H05": ["H04"], "H03": ["H08"]}
    by_entry = {entry["hypothesis_id"]: entry for entry in entries}
    events = []
    for hypothesis_id, event_type in event_types.items():
        entry = by_entry[hypothesis_id]
        values = entry["results"]
        energy_key = (
            "excess_after_fixed_drift_removal_kwh"
            if hypothesis_id == "H04"
            else "excess_energy_kwh"
        )
        excess = values[energy_key]
        candidate = values["candidate"]
        observed = candidate["energy_kwh"]
        events.append(
            {
                "event_id": f"EV-{hypothesis_id}",
                "type": event_type,
                "start": values["period"][0],
                "end": values["period"][1],
                "duration_hours": values["window_duration_hours"],
                "evaluated_hours": candidate["evaluated_hours"],
                "observed_energy_kwh": observed,
                "expected_energy_kwh": max(observed - excess, 0.0),
                "excess_energy_kwh": excess,
                "cost": values["cost"],
                "potential_saving_kwh": None,
                "recoverability": "unknown",
                "severity": entry["severity"],
                "confidence": entry["confidence"],
                "decision": entry["decision"],
                "supporting_methods": supporting_methods[hypothesis_id],
                "related_hypotheses": related.get(hypothesis_id, []),
            }
        )
    return {
        "schema_version": 2,
        "analysis_type": "agentic_energy_prediagnostic",
        "source": "examples/demo_15min.csv",
        "quantitative_source": "reports/demo_quantitative_results.json",
        "ground_truth_used": False,
        "follow_up_policy": {
            "required_for": ["INSUFFISAMMENT_ETAYE", "A_CONSERVER_AVEC_RESERVES"],
            "forbidden_for": ["CONFIRME", "REJETE"],
            "trigger": "incertitude materielle que la reponse peut reduire",
            "selection": "information minimale, realiste et la moins couteuse d'abord",
        },
        "responsibility_split": {
            "codex": "hypotheses, tests choisis, critique, decisions, synthese",
            "python": "calculs, baselines, metriques, energie, cout, chevauchements",
        },
        "hypotheses": entries,
        "events": events,
        "recommendations": recommendations,
        "final_review": {
            "confirmed": ["H04", "H05", "H06"],
            "with_reservations": ["H01", "H02", "H03"],
            "rejected": ["H07", "H08"],
            "double_counting": quantitative["double_counting"],
            "annualization_performed": False,
            "recoverable_savings_claimed": False,
            "causal_equipment_claimed": False,
        },
    }


def render_markdown(review: dict[str, Any], automatic: dict[str, Any]) -> str:
    by_id = {item["hypothesis_id"]: item for item in review["hypotheses"]}

    def follow_up_lines(hypothesis_ids: list[str]) -> list[str]:
        lines: list[str] = []
        for hypothesis_id in hypothesis_ids:
            request = next_information_request(by_id[hypothesis_id])
            if request is None:
                continue
            lines.extend([
                f"### {hypothesis_id} — prochaine verification minimale", "",
                f"- A demander : {request['ask_client']}",
                f"- Pourquoi : {request['why_useful']}",
                f"- Valeur informationnelle : {request['information_value']}",
                "- Hypotheses departagees : " + " / ".join(request["hypotheses_distinguished"]) + ".",
                f"- Responsable pressenti : {request['responsible_role']}.",
                f"- Effort client : {request['client_effort']} ({request['effort_level']}).",
                f"- Attendu si l'hypothese est vraie : {request['expected_if_true']}",
                "- Cause physique : non etablie avec les donnees disponibles.", "",
            ])
        return lines

    def recommendation_lines() -> list[str]:
        lines: list[str] = []
        for recommendation in review["recommendations"]:
            impact = recommendation["observed_impact"]
            request = recommendation["next_verification"]
            causes = " ; ".join(
                f"{item['rank']}. {item['cause']} ({item['evidence_status']})"
                for item in recommendation["plausible_causes"]
            )
            lines.extend([
                f"### {recommendation['recommendation_id']} — {recommendation['finding_id']}", "",
                f"- Anomalie mesurée : {recommendation['measured_anomaly']}",
                f"- Impact observé : {fmt(impact['excess_energy_kwh'], 1)} kWh, "
                f"{fmt(impact['associated_cost'], 2)} EUR sur {impact['period']}.",
                f"- Confiance : {recommendation['confidence']['level']}.",
                f"- Causes plausibles classées : {causes}.",
                "- Cause physique : plausible mais non prouvée ; aucune économie récupérable publiée.",
                f"- Prochaine vérification : {request['ask_client']}",
                f"- Responsable : {recommendation['owner_role']}.",
                f"- Effort : {recommendation['verification_effort']}.",
                f"- Attendu si l'hypothèse est vraie : {recommendation['expected_if_hypothesis_true']}",
                "- Mesure après intervention : "
                f"{recommendation['post_action_measurement']['metric']}, "
                f"{recommendation['post_action_measurement']['evaluation_window']}; "
                f"succès = {recommendation['post_action_measurement']['success_rule']}.", "",
            ])
        return lines

    def observed_line(hypothesis_id: str, energy_key: str = "excess_energy_kwh") -> str:
        values = by_id[hypothesis_id]["results"]
        return (
            f"{fmt(values[energy_key], 1)} kWh sur la periode, soit "
            f"{fmt(values['cost'], 2)} EUR au tarif de 0,175 EUR/kWh."
        )

    baseline = json.loads(
        Path("reports/demo_quantitative_results.json").read_text(encoding="utf-8")
    )["baseline_candidates"]["production_temperature_activity_product_interaction"]
    quality = automatic["metadata"]["data_quality"]
    lines = [
        "# Pre-diagnostic energetique agentique — demonstration",
        "",
        "## 1. Resume executif",
        "",
        "Trois comportements sont confirmes par les donnees : une derive progressive de la charge "
        "fixe, une baisse temporaire d'efficacite a production comparable et un nouveau niveau "
        "de charge inactive persistant. Trois autres signaux (nuit, week-end et pic ponctuel) "
        "meritent une verification operationnelle.",
        "",
        "Les kWh ci-dessous sont des surconsommations observees par rapport a une baseline, pas des "
        "economies garanties. Aucun total portefeuille ni projection annuelle n'est publie, car "
        "certaines fenetres se chevauchent et la part recuperable est inconnue.",
        "",
        "## 2. Donnees analysees",
        "",
        f"- Periode couverte (fin exclue) : {automatic['start']} -> {automatic['end']}.",
        f"- Mesures valides : {automatic['valid_rows']} quarts d'heure.",
        f"- Energie totale : {fmt(automatic['total_energy_kwh'], 1)} kWh.",
        f"- Production : {fmt(automatic['total_production'], 1)} unites.",
        "- Variables de controle : production active, temperature exterieure, shift et type produit.",
        "",
        "## 3. Qualite des donnees",
        "",
        f"Couverture estimee : {fmt(quality['coverage_ratio'] * 100, 3)} %. "
        f"Le chargeur a trace {quality['invalid_timestamp_rows']} timestamp invalide, "
        f"{quality['missing_measurement_rows']} mesure manquante, "
        f"{quality['impossible_value_rows']} valeur impossible et "
        f"{quality['identical_duplicates_removed']} doublon strict. Les quatre trous sont localises ; "
        "ils ne coincident pas avec les longues tendances conservees.",
        "",
        "## 4. Profil energetique",
        "",
        f"La consommation hors production atteint {fmt(automatic['off_production_kwh'], 1)} kWh "
        f"({fmt(automatic['off_production_share'] * 100, 1)} %). Elle inclut une charge de base "
        "legitime et ne constitue pas en bloc une economie.",
        "",
        "![Puissance dans le temps](charts/power_timeseries.png)",
        "",
        "![Puissance observee et attendue](charts/observed_expected.png)",
        "",
        "![Residu quotidien moyen](charts/daily_residual.png)",
        "",
        "![Relation production-puissance](charts/production_power.png)",
        "",
        "## 5. Baseline",
        "",
        "La baseline retenue utilise production, temperature, activite, type produit B et interaction "
        "production-produit. Elle est calibree sur le passe puis validee sur la periode suivante.",
        "",
        f"- Validation MAE : {fmt(baseline['validation_metrics']['mae'], 3)} kW.",
        f"- Validation RMSE : {fmt(baseline['validation_metrics']['rmse'], 3)} kW.",
        f"- Validation R2 : {fmt(baseline['validation_metrics']['r_squared'], 4)}.",
        "",
        "## 6. Investigations realisees",
        "",
        "H01 a H06 ont suivi observation -> hypothese -> test -> contre-hypothese -> nouveau test -> "
        "quantification -> decision. H07 et H08 ont ete explicitement rejetes pour confusion et "
        "double comptage. Le detail complet se trouve dans `reports/investigation.json`.",
        "",
        "## 7. Opportunites confirmees",
        "",
        "### #1 — H06 : nouveau niveau de charge inactive",
        "",
        observed_line("H06"),
        "",
        f"Le residu inactif moyen reste a {fmt(by_id['H06']['results']['post_inactive_residual_mean_kw'], 2)} kW "
        "sur 30/30 jours. La temperature n'en explique que "
        f"{fmt(by_id['H06']['results']['temperature_explained_delta_kw'], 3)} kW.",
        "",
        "Ce que les donnees demontrent : un changement durable de niveau existe hors production.",
        "",
        "Ce qu'elles ne demontrent pas : l'equipement responsable ni la part arretable.",
        "",
        "A verifier : nouvelles utilites, consignes, fuites, ventilation, pompes ou maintien en temperature.",
        "",
        "### #2 — H05 : derive progressive de charge fixe",
        "",
        observed_line("H05"),
        "",
        f"Pente inactive : {fmt(by_id['H05']['results']['inactive_trend']['slope_per_day'], 3)} kW/j "
        f"(R2 {fmt(by_id['H05']['results']['inactive_trend']['r_squared'], 3)}). "
        "La pente imputable a la temperature est "
        f"{fmt(by_id['H05']['results']['temperature_implied_residual_slope_kw_per_day'], 4)} kW/j.",
        "",
        "Ce que les donnees demontrent : la charge fixe se degrade progressivement, y compris a production nulle.",
        "",
        "A verifier : encrassement, fuite croissante, derive de regulation et auxiliaire restant charge.",
        "",
        "### #3 — H04 : baisse temporaire d'efficacite",
        "",
        observed_line("H04", "excess_after_fixed_drift_removal_kwh"),
        "",
        f"Apres retrait de la derive fixe, l'ecart actif passe de "
        f"{fmt(by_id['H04']['results']['prior_active_minus_inactive_residual_kw'], 2)} a "
        f"{fmt(by_id['H04']['results']['candidate_active_minus_inactive_residual_kw'], 2)} kW, "
        "sur 11/11 jours. Production et mix produit sont comparables.",
        "",
        "Ce que les donnees demontrent : davantage de puissance est necessaire pour une production comparable.",
        "",
        "Ce qu'elles ne demontrent pas : la cause mecanique exacte.",
        "",
        "## 8. Efficacite energetique",
        "",
        "Le signal mensuel d'intensite n'est pas conserve comme opportunite autonome : mai ne contient "
        "que quatre jours et le ratio recouvre H04-H06. L'analyse a production comparable est plus solide.",
        "",
        "## 9. Impact economique",
        "",
        "Les couts ci-dessus portent uniquement sur les periodes observees. La review de chevauchement "
        f"trouve {fmt(review['final_review']['double_counting']['confirmed_temporal_overlap_audit']['double_counted_kwh'], 1)} kWh "
        "sur des timestamps communs ; H04 retranche H05, mais aucun total global n'est affiche sans "
        "allocation causale. Aucune annualisation n'est effectuee.",
        "",
        "## 10. Opportunites necessitant verification",
        "",
        f"- H01 nuit : {observed_line('H01')} Recurrence 15/15 jours, production nulle.",
        f"- H02 week-end : {observed_line('H02')} Recurrence 4/4 jours, production nulle.",
        f"- H03 pic ponctuel : {observed_line('H03')} Un seul evenement de deux heures ; pas d'annualisation.",
        "",
        *follow_up_lines(["H01", "H02", "H03"]),
        "## 11. Hypotheses rejetees importantes",
        "",
        "- H07 : l'intensite de mai n'est ni comparable ni independante.",
        "- H08 : le signal de pointe et H03 couvrent exactement les memes huit points ; les additionner "
        f"doublerait {fmt(by_id['H08']['results']['double_counted_kwh'], 1)} kWh.",
        "",
        "## 12. Recommandations",
        "",
        "Aucune cause physique n'est etablie par ce dataset. Les actions ci-dessous sont des "
        "verifications, pas des diagnostics d'equipement ni des investissements prescrits.",
        "",
        *recommendation_lines(),
        "## 13. Limites",
        "",
        "Dataset synthetique, quatre mois, tarif simple, aucune mesure par equipement et aucune preuve "
        "de causalite physique. Les surconsommations ne sont pas des economies garanties.",
        "",
        "## 14. Methodologie",
        "",
        "Validation et normalisation deterministes, baseline passee->future, residualisation, comparaisons "
        "contextuelles, recherche d'explications alternatives, quantification Python, review adversariale "
        "Codex et controle des chevauchements.",
        "",
    ]
    return "\n".join(lines)


def render_html(markdown: str) -> str:
    blocks = []
    in_list = False
    for raw in markdown.splitlines():
        line = raw.strip()
        if not line:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            continue
        if line.startswith("![") and "](" in line and line.endswith(")"):
            alt, source = line[2:-1].split("](", 1)
            blocks.append(
                f'<figure><img src="{html.escape(source)}" alt="{html.escape(alt)}" '
                f'loading="lazy"><figcaption>{html.escape(alt)}</figcaption></figure>'
            )
        elif line.startswith("### "):
            blocks.append(f"<h3>{html.escape(line[4:])}</h3>")
        elif line.startswith("## "):
            blocks.append(f"<h2>{html.escape(line[3:])}</h2>")
        elif line.startswith("# "):
            blocks.append(f"<h1>{html.escape(line[2:])}</h1>")
        elif line.startswith("- ") or (len(line) > 3 and line[0].isdigit() and line[1:3] == ". "):
            if not in_list:
                blocks.append("<ul>")
                in_list = True
            text = line[2:] if line.startswith("- ") else line[3:]
            blocks.append(f"<li>{html.escape(text)}</li>")
        else:
            if in_list:
                blocks.append("</ul>")
                in_list = False
            blocks.append(f"<p>{html.escape(line)}</p>")
    if in_list:
        blocks.append("</ul>")
    body = "\n".join(blocks)
    return f"""<!doctype html>
<html lang="fr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pre-diagnostic energetique</title><style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:auto;padding:20px;color:#17202a;line-height:1.55}}
h1{{color:#123c69}}h2{{margin-top:2rem;border-bottom:1px solid #ccd6dd;padding-bottom:.3rem}}
h3{{color:#236192}}p,li{{font-size:1rem}}code{{background:#eef2f5;padding:.1rem .25rem}}
figure{{margin:1.25rem 0}}img{{max-width:100%;height:auto;border:1px solid #d8dee4}}figcaption{{font-size:.9rem;color:#52606d}}
@media(max-width:600px){{body{{padding:12px}}h1{{font-size:1.55rem}}h2{{font-size:1.25rem}}}}
</style></head><body>{body}</body></html>"""


def main() -> int:
    quantitative = json.loads(
        Path("reports/demo_quantitative_results.json").read_text(encoding="utf-8")
    )
    automatic = json.loads(Path("reports/demo_15min.json").read_text(encoding="utf-8"))
    review = build_review(quantitative)
    data = load_data("examples/demo_15min.csv")
    model_name = quantitative["method"]["selected_baseline"]
    residuals = calculate_residuals(
        data.readings, quantitative["baseline_candidates"][model_name]
    )
    chart_directory = Path("reports/charts")
    plot_power_timeseries(data.readings, chart_directory / "power_timeseries.png")
    plot_observed_expected(residuals, chart_directory / "observed_expected.png")
    plot_daily_residual(residuals, chart_directory / "daily_residual.png")
    plot_energy_production(data.readings, chart_directory / "production_power.png")
    bundle = AnalysisBundle(
        automatic_analysis=automatic,
        quantitative_results=quantitative,
        investigation=review,
        events=[AnalysisEvent(**event) for event in review["events"]],
        artifacts={
            "investigation_json": "reports/investigation.json",
            "report_markdown": "reports/demo_final.md",
            "report_html": "reports/demo_final.html",
            "charts": {
                "power_timeseries": "reports/charts/power_timeseries.png",
                "observed_expected": "reports/charts/observed_expected.png",
                "daily_residual": "reports/charts/daily_residual.png",
                "production_power": "reports/charts/production_power.png",
            },
        },
    )
    markdown = render_markdown(review, automatic)
    write_bundle_json(bundle, "reports/analysis.json")
    Path("reports/investigation.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path("reports/demo_final.md").write_text(markdown, encoding="utf-8")
    Path("reports/demo_final.html").write_text(render_html(markdown), encoding="utf-8")
    print("Bundle ecrit: reports/analysis.json")
    print("Review ecrite: reports/investigation.json")
    print("Rapports ecrits: reports/demo_final.md, reports/demo_final.html")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
