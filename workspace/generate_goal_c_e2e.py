"""Fixtures E2E synthétiques Goal C, construites par les contrats Goal A/B publics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client_delivery import generate_client_report
from client_intake_pipeline import create_client_case, ingest_client_drop, record_structured_findings
from operational_economics import calculate_economic_scenarios, initialize_economic_state, persist_economic_packet


def _action(identifier: str, title: str, effect: str) -> dict:
    return {
        "action_id": identifier, "finding_ids": ["FIND-OFFHOURS-01"], "title": title,
        "description": "Option formulée par Codex pour la fixture Goal C.", "action_type": "maintenance",
        "technical_rationale": "Charge hors production établie par l'investigation.",
        "operational_rationale": "Planifier hors activité client.", "implementation_scope": "Installation concernée.",
        "requires_professional_validation": True, "reversibility": "PARTIALLY_REVERSIBLE", "energy_effect_ref": effect,
        "validation_plan": {"metric": "kWh hors production", "expected_direction": "baisse", "comparison_window": "semaines comparables", "confounders": "ouverture et activité", "minimum_evidence": "baisse persistante à activité comparable"},
    }


def _effect(identifier: str, low: float, base: float, high: float, dataset_id: str) -> dict:
    return {"effect_id": identifier, "basis": "DIRECTLY_MEASURED_HISTORICAL_EXCESS", "baseline": "créneaux fermés comparables", "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": low, "BASE": base, "HIGH": high}, "finding_refs": ["FIND-OFFHOURS-01"], "source_refs": [dataset_id]}


def _input(identifier: str, kind: str, value: float, unit: str, period: str, source_ref: str) -> dict:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [source_ref]}, "confidence": "HIGH"}


def _calc(effect: dict, capex: float, capex_id: str) -> dict:
    refs = {"energy_effect": {name: ["FIND-OFFHOURS-01"] for name in ("LOW", "BASE", "HIGH")}, "tariff_per_kwh": {name: ["TAR-01"] for name in ("LOW", "BASE", "HIGH")}, "intervention_cost": {name: [capex_id] for name in ("LOW", "BASE", "HIGH")}}
    return calculate_economic_scenarios(effect, tariff_per_kwh={name: .20 for name in ("LOW", "BASE", "HIGH")}, intervention_cost={name: capex for name in ("LOW", "BASE", "HIGH")}, input_references=refs)


def _narrative(dataset_id: str) -> dict:
    return {
        "site_name": "Boulangerie du Centre", "report_title": "Analyse de performance énergétique", "analysis_period": "Période de données fournie",
        "executive_message": "Une action de maintenance peut être planifiée sans perturber la production, tandis que le remplacement reste une solution alternative à comparer.",
        "cards": {"ACT-REPAIR-01": {
            "headline": "Réparer la charge hors horaires", "what_we_found": "Une charge subsiste lorsque la production est arrêtée.",
            "why_this_matters": "Cette consommation ne participe pas au service vendu pendant les périodes de fermeture et justifie une intervention proportionnée.",
            "recommendation": "Faire contrôler puis corriger la charge pendant une fenêtre de maintenance planifiée.",
            "uncertainty": "Le composant exact reste à confirmer par le professionnel avant toute réparation."}},
        "no_action_items": [{"title": "Ne pas remplacer immédiatement", "explanation": "Le remplacement est une option alternative et ne doit pas être engagé avant comparaison avec la réparation ciblée."}],
        "what_we_checked": ["La consommation pendant les créneaux de fermeture", "La compatibilité de l intervention avec l activité du site"],
        "chart_requests": [{"type": "ENERGY_SERIES", "dataset_id": dataset_id, "title": "Consommation sur la période analysée", "purpose": "Le profil met en évidence la différence entre les créneaux actifs et les créneaux fermés."}],
        "limitations": ["La cause précise nécessite la confirmation du professionnel qui interviendra."],
        "method": "Les montants reprennent les calculs économiques validés et les décisions enregistrées avant la livraison.",
    }


def _no_finding_narrative() -> dict:
    return {
        "site_name": "Atelier de référence", "report_title": "Analyse de performance énergétique", "analysis_period": "Période de données fournie",
        "executive_message": "Aucune anomalie énergétique significative ne justifie actuellement une dépense corrective.", "cards": {},
        "no_action_items": [{"title": "Aucune action corrective nécessaire", "explanation": "Les éléments disponibles sont compatibles avec le fonctionnement attendu et ne justifient pas une intervention supplémentaire."}],
        "what_we_checked": ["Les régimes de consommation disponibles", "Les limites de qualité et de période des données"],
        "limitations": ["La période courte sert de référence mais ne remplace pas un suivi lorsque l activité change."],
        "method": "La conclusion conserve la décision no finding et ne transforme pas une absence de signal en recommandation.",
    }


def generate(root: str | Path = "examples") -> tuple[Path, Path]:
    root = Path(root)
    main_root, empty_root = root / "goal_c_e2e_case", root / "goal_c_no_finding_case"
    if main_root.exists() or empty_root.exists():
        raise FileExistsError("Les fixtures Goal C existent déjà et ne seront pas écrasées.")
    raw = root / "goal_c_e2e_input"
    raw.mkdir(parents=True)
    (raw / "energy_interval.csv").write_text("timestamp,energy_kwh,production\n2026-07-01 00:00,6,0\n2026-07-01 02:00,6,0\n2026-07-01 04:00,5,0\n2026-07-01 06:00,5,0\n2026-07-01 08:00,2,12\n2026-07-01 10:00,3,18\n2026-07-01 12:00,3,18\n2026-07-01 14:00,3,17\n2026-07-01 16:00,3,16\n2026-07-01 18:00,3,0\n2026-07-01 20:00,5,0\n2026-07-01 22:00,6,0\n", encoding="utf-8")
    (raw / "tarif_electricite.txt").write_text("Tarif contractualisé : 0,20 EUR/kWh.\n", encoding="utf-8")
    (raw / "devis_reparation.txt").write_text("Devis réparation : 450 EUR. Remplacement : 3200 EUR.\n", encoding="utf-8")
    (raw / "planning.txt").write_text("Production et ouverture de sept heures à dix-huit heures.\n", encoding="utf-8")
    create_client_case("boulangerie_centre", root=main_root)
    case = main_root / "boulangerie_centre"
    ingest_client_drop(raw, case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    refs = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    dataset_id = json.loads((case / "derived" / "canonical_case.json").read_text(encoding="utf-8"))["available_datasets"][0]["dataset_id"]
    record_structured_findings(case, [{"finding_id": "FIND-OFFHOURS-01", "observation": "Charge récurrente hors production dans les créneaux fermés.", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "confidence": "HIGH", "possible_explanations": ["charge résiduelle", "fonctionnement nécessaire non documenté"], "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Contrôle professionnel pendant fermeture."}])
    initialize_economic_state(case)
    repair, replace = _effect("EFF-REPAIR-01", 1800, 2160, 2520, dataset_id), _effect("EFF-REPLACE-01", 1900, 2280, 2660, dataset_id)
    inputs = [_input("TAR-01", "electricity_tariff", .20, "EUR/kWh", "per_kwh", refs["tarif_electricite.txt"]), _input("CAP-REPAIR-01", "repair_quote", 450, "EUR", "one_off", refs["devis_reparation.txt"]), _input("CAP-REPLACE-01", "replacement_quote", 3200, "EUR", "one_off", refs["devis_reparation.txt"])]
    packet = {"technical_finding_refs": [{"finding_id": "FIND-OFFHOURS-01"}], "economic_inputs": inputs, "scenario_assumptions": [], "candidate_actions": [_action("ACT-REPAIR-01", "Réparation ciblée", "EFF-REPAIR-01"), _action("ACT-REPLACE-01", "Remplacement", "EFF-REPLACE-01")], "operational_constraints": [{"constraint_id": "CONS-OPENING-01", "category": "OPENING_HOURS", "description": "Intervention à prévoir hors production et ouverture.", "source_status": "EXPLICIT", "source_refs": [refs["planning.txt"]], "hard": True, "material": True, "affected_action_ids": ["ACT-REPAIR-01", "ACT-REPLACE-01"]}], "relationships": [{"relationship_id": "REL-REPAIR-REPLACE", "type": "MUTUALLY_EXCLUSIVE", "action_a": "ACT-REPAIR-01", "action_b": "ACT-REPLACE-01", "rationale": "Deux réponses au même équipement."}], "combined_effects": {}, "scenario_calculations": {"ACT-REPAIR-01": _calc(repair, 450, "CAP-REPAIR-01"), "ACT-REPLACE-01": _calc(replace, 3200, "CAP-REPLACE-01")}, "economic_requests": [], "decision": {"decision_id": "DEC-REPAIR-01", "decision": "ACT_NOW", "selected_action_ids": ["ACT-REPAIR-01"], "considered_action_ids": ["ACT-REPAIR-01", "ACT-REPLACE-01"], "reason": "Réparation proportionnée au bénéfice et à la contrainte d activité.", "priority_reasoning": "Intervention faible coût et réversible avant remplacement.", "technical_confidence": "HIGH", "economic_importance": "HIGH", "constraint_assessments": [{"constraint_id": "CONS-OPENING-01", "disposition": "MITIGATED", "rationale": "Planification hors ouverture."}]}}
    persist_economic_packet(case, packet)
    generate_client_report(case, _narrative(dataset_id))
    raw_empty = root / "goal_c_no_finding_input"
    raw_empty.mkdir()
    (raw_empty / "energy.csv").write_text("timestamp,energy_kwh\n2026-07-01 00:00,2\n2026-07-01 12:00,2\n", encoding="utf-8")
    create_client_case("atelier_reference", root=empty_root)
    empty_case = empty_root / "atelier_reference"
    ingest_client_drop(raw_empty, empty_case)
    record_structured_findings(empty_case, [], no_finding={"what_was_analyzed": "Consommation disponible", "usable_period": "Période fournie", "operating_regimes": "Régime stable observé", "limitations": "Période courte", "monitoring_baseline_meaningful": False})
    initialize_economic_state(empty_case)
    persist_economic_packet(empty_case, {"technical_finding_refs": [], "economic_inputs": [], "scenario_assumptions": [], "candidate_actions": [], "operational_constraints": [], "relationships": [], "combined_effects": {}, "scenario_calculations": {}, "economic_requests": [], "decision": {"decision_id": "DEC-NO-FINDING-01", "decision": "DO_NOTHING", "selected_action_ids": [], "considered_action_ids": [], "reason": "Aucune anomalie significative établie.", "priority_reasoning": "Aucune dépense corrective justifiée.", "technical_confidence": "MEDIUM", "economic_importance": "LOW"}})
    generate_client_report(empty_case, _no_finding_narrative())
    return case, empty_case


if __name__ == "__main__":
    main, no_finding = generate()
    print(main)
    print(no_finding)
