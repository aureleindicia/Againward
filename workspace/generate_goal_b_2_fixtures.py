"""Génère les fixtures B-A → B-O B.2, distinctes et sans règles de production."""
from __future__ import annotations

import json
from pathlib import Path


SCENARIOS = ("LOW", "BASE", "HIGH")


def _input(identifier: str, kind: str, value: float, unit: str, period: str, *, provenance: str = "DOCUMENT_EXTRACTED") -> dict:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": provenance, "status": "KNOWN", "source": {"artifact_id": f"ART-{identifier}"}, "confidence": "MEDIUM"}


def _assumption(identifier: str, value: float, unit: str, period: str, description: str) -> dict:
    return {"assumption_id": identifier, "description": description, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "explicit scenario sensitivity"}}


def _effect(identifier: str, values: dict[str, float], baseline: str, finding: str = "FIND-01") -> dict:
    return {"effect_id": identifier, "basis": "COUNTERFACTUAL_ESTIMATE", "baseline": baseline, "unit": "kWh/year", "period": "annual", "scenarios": values, "finding_refs": [finding], "source_refs": ["DS-ENERGY-01"]}


def _action(identifier: str, effect: str, *, title: str, reversible: str = "PARTIALLY_REVERSIBLE") -> dict:
    return {"action_id": identifier, "finding_ids": ["FIND-01"], "title": title, "description": "Option candidate formulée par Codex dans une fixture synthétique.", "action_type": "maintenance_or_operation", "technical_rationale": "Finding technique explicitement référencé.", "operational_rationale": "Contexte et contraintes propres à la fixture.", "implementation_scope": "Équipement/processus concerné.", "requires_professional_validation": True, "reversibility": reversible, "energy_effect_ref": effect, "validation_plan": {"metric": "kWh normalisés par régime comparable", "expected_direction": "baisse", "comparison_window": "avant/après comparable", "confounders": "activité, calendrier et météo", "minimum_evidence": "effet récurrent sans régression opérationnelle"}}


def _decision(kind: str, selected: list[str], considered: list[str] | None = None) -> dict:
    result = {"decision_id": f"DEC-{kind}", "decision": kind, "selected_action_ids": selected, "considered_action_ids": selected if considered is None else considered, "reason": "Décision proposée par Codex pour cette situation synthétique.", "priority_reasoning": "Argumentation qualitative; aucun score déterministe.", "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM"}
    if kind == "INVESTIGATE_FIRST":
        result["evidence_acquisition"] = {"what_it_resolves": "une explication concurrente matériellement différente", "decision_that_can_change": "intervenir, différer ou ne rien faire", "cost_or_burden": "test ciblé à faible coût", "why_worth_it": "évite un investissement irréversible mal justifié"}
    return result


def _calculation_spec(effect_id: str, tariff: dict[str, float] | None, tariff_refs: dict[str, str] | None, capex: dict[str, float] | None = None, capex_refs: dict[str, str] | None = None, recurring: dict[str, float] | None = None, recurring_refs: dict[str, str] | None = None) -> dict:
    refs: dict[str, dict[str, list[str]]] = {"energy_effect": {scenario: ["FIND-01"] for scenario in SCENARIOS}}
    if tariff is not None:
        refs["tariff_per_kwh"] = {scenario: [tariff_refs[scenario]] for scenario in SCENARIOS}
    if capex is not None:
        refs["intervention_cost"] = {scenario: [capex_refs[scenario]] for scenario in SCENARIOS}
    if recurring is not None:
        refs["recurring_cost"] = {scenario: [recurring_refs[scenario]] for scenario in SCENARIOS}
    return {"effect_id": effect_id, "tariff_per_kwh": tariff, "intervention_cost": capex, "recurring_cost": recurring, "input_references": refs}


def _base_fixture(identifier: str, family: str, decision: dict, effect: dict | None, actions: list[dict], inputs: list[dict], assumptions: list[dict], specs: dict[str, dict]) -> dict:
    return {"fixture_id": identifier, "family": family, "technical_finding": {"finding_id": "FIND-01", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN" if decision["decision"] == "INVESTIGATE_FIRST" else "CAUSE_PROBABLE", "uncertainty": "explicitement conservée lorsque matériel", "provenance": ["DS-ENERGY-01"]}, "energy_effects": [] if effect is None else [effect], "economic_inputs": inputs, "scenario_assumptions": assumptions, "candidate_actions": actions, "operational_constraints": [], "relationships": [], "combined_effects": {}, "economic_requests": [], "decision": decision, "calculation_specs": specs, "expected_agent_decision": decision["decision"], "expected_properties": {}}


def generate(path: str | Path = "examples/goal_b_2_fixtures.json") -> Path:
    path = Path(path)
    if path.exists():
        raise FileExistsError("Les fixtures B.2 existent déjà; elles ne seront pas écrasées.")
    fixtures: list[dict] = []

    # B-A: réparation faible coût et bénéfice significatif.
    inp = [_input("TAR-A", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-A", "leak_repair", 800, "EUR", "one_off"), _input("REC-A", "maintenance", 100, "EUR/year", "annual")]
    eff = _effect("EFF-A", {"LOW": 10000, "BASE": 12000, "HIGH": 14000}, "off-hours healthy reference")
    fixtures.append(_base_fixture("B-A", "obvious_low_cost", _decision("ACT_NOW", ["ACT-A"]), eff, [_action("ACT-A", "EFF-A", title="Réparer une fuite hors production")], inp, [], {"ACT-A": _calculation_spec("EFF-A", {s: .20 for s in SCENARIOS}, {s: "TAR-A" for s in SCENARIOS}, {s: 800 for s in SCENARIOS}, {s: "CAP-A" for s in SCENARIOS}, {s: 100 for s in SCENARIOS}, {s: "REC-A" for s in SCENARIOS})}))
    fixtures[-1]["expected_properties"] = {"positive_net": True, "max_base_payback_years": 1.0}

    # B-B: replacement coûteux, cause incertaine, inspection bon marché.
    inp = [_input("TAR-B", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-B", "replacement_quote", 25000, "EUR", "one_off"), _input("TEST-B", "diagnostic_quote", 350, "EUR", "one_off")]
    eff = _effect("EFF-B", {"LOW": 10000, "BASE": 30000, "HIGH": 45000}, "production-adjusted current reference")
    fixtures.append(_base_fixture("B-B", "uncertain_expensive", _decision("INVESTIGATE_FIRST", ["ACT-B-TEST"], ["ACT-B-TEST", "ACT-B-REPLACE"]), eff, [_action("ACT-B-TEST", "EFF-B", title="Inspection discriminante", reversible="REVERSIBLE"), _action("ACT-B-REPLACE", "EFF-B", title="Remplacement après confirmation", reversible="IRREVERSIBLE")], inp, [], {"ACT-B-REPLACE": _calculation_spec("EFF-B", {s: .20 for s in SCENARIOS}, {s: "TAR-B" for s in SCENARIOS}, {s: 25000 for s in SCENARIOS}, {s: "CAP-B" for s in SCENARIOS})}))
    fixtures[-1]["expected_properties"] = {"diagnostic_cost_lt_capex": True, "uncertain_cause": True}

    # B-C: finding réel mais trop petit face au CAPEX.
    inp = [_input("TAR-C", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-C", "retrofit_quote", 4000, "EUR", "one_off")]
    eff = _effect("EFF-C", {"LOW": 200, "BASE": 300, "HIGH": 400}, "current measured baseline")
    fixtures.append(_base_fixture("B-C", "trivial_saving", _decision("NO_ECONOMIC_CASE", [], ["ACT-C"]), eff, [_action("ACT-C", "EFF-C", title="Retrofit faible impact")], inp, [], {"ACT-C": _calculation_spec("EFF-C", {s: .20 for s in SCENARIOS}, {s: "TAR-C" for s in SCENARIOS}, {s: 4000 for s in SCENARIOS}, {s: "CAP-C" for s in SCENARIOS})}))
    fixtures[-1]["expected_properties"] = {"base_payback_gt_years": 30}

    # B-D: déplacer l'horaire serait économique mais bloque fraîcheur/production.
    inp = [_input("TAR-D", "electricity_tariff", .30, "EUR/kWh", "per_kwh"), _input("CAP-D", "schedule_change", 100, "EUR", "one_off")]
    eff = _effect("EFF-D", {"LOW": 4000, "BASE": 5000, "HIGH": 6000}, "peak-hour load reference")
    item = _base_fixture("B-D", "operationally_absurd_tariff_optimization", _decision("OPERATIONALLY_NOT_JUSTIFIED", [], ["ACT-D"]), eff, [_action("ACT-D", "EFF-D", title="Déplacer la production hors pointe")], inp, [], {"ACT-D": _calculation_spec("EFF-D", {s: .30 for s in SCENARIOS}, {s: "TAR-D" for s in SCENARIOS}, {s: 100 for s in SCENARIOS}, {s: "CAP-D" for s in SCENARIOS})})
    item["decision"]["blocking_constraint_ids"] = ["CONS-D"]
    item["operational_constraints"] = [{"constraint_id": "CONS-D", "category": "CUSTOMER_SERVICE", "description": "Produits frais exigés avant l'ouverture; le décalage détruit le service.", "source_status": "EXPLICIT", "source_ref": "ART-SCHEDULE-D", "hard": True, "material": True, "affected_action_ids": ["ACT-D"]}]
    item["expected_properties"] = {"blocking_constraint": True, "positive_energy_case_but_rejected": True}
    fixtures.append(item)

    # B-E: charge obligatoire : aucun effet, aucune action.
    item = _base_fixture("B-E", "mandatory_safety_quality_load", _decision("DO_NOTHING", [], []), None, [], [], [], {})
    item["technical_finding"] = {"finding_id": "FIND-01", "status": "NORMAL_OPERATION", "uncertainty": "aucune anomalie démontrée", "provenance": ["ART-HYGIENE-E"]}
    item["operational_constraints"] = [{"constraint_id": "CONS-E", "category": "HYGIENE", "description": "Ventilation et maintien thermique obligatoires.", "source_status": "EXPLICIT", "source_ref": "ART-HYGIENE-E", "hard": True, "material": True, "affected_action_ids": []}]
    item["expected_properties"] = {"no_energy_saving_claim": True, "mandatory_constraint": True}
    fixtures.append(item)

    # B-F: deux actions sur la même charge, relation overlap.
    inp = [_input("TAR-F", "electricity_tariff", .20, "EUR/kWh", "per_kwh")]
    effects = [_effect("EFF-F1", {s: 7000 for s in SCENARIOS}, "same baseload"), _effect("EFF-F2", {s: 6000 for s in SCENARIOS}, "same baseload")]
    item = _base_fixture("B-F", "overlapping_actions", _decision("INVESTIGATE_FIRST", ["ACT-F1"], ["ACT-F1", "ACT-F2"]), effects[0], [_action("ACT-F1", "EFF-F1", title="Réparer fuite"), _action("ACT-F2", "EFF-F2", title="Optimiser régulation")], inp, [], {"ACT-F1": _calculation_spec("EFF-F1", {s: .20 for s in SCENARIOS}, {s: "TAR-F" for s in SCENARIOS}), "ACT-F2": _calculation_spec("EFF-F2", {s: .20 for s in SCENARIOS}, {s: "TAR-F" for s in SCENARIOS})})
    item["energy_effects"] = effects
    item["relationships"] = [{"relationship_id": "REL-F", "type": "OVERLAPPING", "action_a": "ACT-F1", "action_b": "ACT-F2", "rationale": "Les deux réduisent le même baseload.", "combined_effect_ref": "COMB-F"}]
    item["expected_properties"] = {"naive_additive_rejected": True}
    fixtures.append(item)

    # B-G: réparer OU remplacer.
    inp = [_input("TAR-G", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-G-R", "repair_quote", 1500, "EUR", "one_off"), _input("CAP-G-X", "replacement_quote", 12000, "EUR", "one_off")]
    effects = [_effect("EFF-G-R", {s: 5000 for s in SCENARIOS}, "current faulty asset"), _effect("EFF-G-X", {s: 8000 for s in SCENARIOS}, "current faulty asset")]
    item = _base_fixture("B-G", "mutually_exclusive_repair_replacement", _decision("DEFER", ["ACT-G-R"], ["ACT-G-R", "ACT-G-X"]), effects[0], [_action("ACT-G-R", "EFF-G-R", title="Réparer"), _action("ACT-G-X", "EFF-G-X", title="Remplacer", reversible="IRREVERSIBLE")], inp, [], {"ACT-G-R": _calculation_spec("EFF-G-R", {s: .20 for s in SCENARIOS}, {s: "TAR-G" for s in SCENARIOS}, {s: 1500 for s in SCENARIOS}, {s: "CAP-G-R" for s in SCENARIOS}), "ACT-G-X": _calculation_spec("EFF-G-X", {s: .20 for s in SCENARIOS}, {s: "TAR-G" for s in SCENARIOS}, {s: 12000 for s in SCENARIOS}, {s: "CAP-G-X" for s in SCENARIOS})})
    item["energy_effects"] = effects
    item["relationships"] = [{"relationship_id": "REL-G", "type": "MUTUALLY_EXCLUSIVE", "action_a": "ACT-G-R", "action_b": "ACT-G-X", "rationale": "Une même intervention ne peut être réparation et remplacement."}]
    item["expected_properties"] = {"exclusive_actions_rejected_from_sum": True}
    fixtures.append(item)

    # B-H: intéressant, mais shutdown planifié.
    inp = [_input("TAR-H", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-H", "retrofit_quote", 2000, "EUR", "one_off")]
    eff = _effect("EFF-H", {s: 10000 for s in SCENARIOS}, "current operating baseline")
    item = _base_fixture("B-H", "planned_shutdown", _decision("DEFER", ["ACT-H"]), eff, [_action("ACT-H", "EFF-H", title="Installer pendant shutdown")], inp, [], {"ACT-H": _calculation_spec("EFF-H", {s: .20 for s in SCENARIOS}, {s: "TAR-H" for s in SCENARIOS}, {s: 2000 for s in SCENARIOS}, {s: "CAP-H" for s in SCENARIOS})})
    item["operational_constraints"] = [{"constraint_id": "CONS-H", "category": "MAINTENANCE_WINDOW", "description": "Shutdown planifié le mois prochain, fenêtre optimale.", "source_status": "EXPLICIT", "source_ref": "ART-SHUTDOWN-H", "hard": False, "material": True, "affected_action_ids": ["ACT-H"]}]
    item["expected_properties"] = {"positive_net": True, "planned_shutdown": True}
    fixtures.append(item)

    # B-I: tarif incertain qui change fortement le payback.
    inp = [_input("TAR-I-BASE", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-I", "retrofit_quote", 3000, "EUR", "one_off")]
    ass = [_assumption("TAR-I-LOW", .05, "EUR/kWh", "per_kwh", "Tarif bas non confirmé."), _assumption("TAR-I-HIGH", .40, "EUR/kWh", "per_kwh", "Tarif haut non confirmé.")]
    eff = _effect("EFF-I", {s: 10000 for s in SCENARIOS}, "measured excess baseline")
    item = _base_fixture("B-I", "material_tariff_uncertainty", _decision("INSUFFICIENT_FOR_ECONOMIC_DECISION", [], ["ACT-I"]), eff, [_action("ACT-I", "EFF-I", title="Retrofit soumis au tarif")], inp, ass, {"ACT-I": _calculation_spec("EFF-I", {"LOW": .05, "BASE": .20, "HIGH": .40}, {"LOW": "TAR-I-LOW", "BASE": "TAR-I-BASE", "HIGH": "TAR-I-HIGH"}, {s: 3000 for s in SCENARIOS}, {s: "CAP-I" for s in SCENARIOS})})
    item["economic_requests"] = [{"request_type": "REQUEST_EXISTING_DOCUMENT", "client_question": "Pouvez-vous partager la dernière facture d'électricité si elle est facilement disponible ?", "internal_reason": "Le tarif fait varier matériellement la comparaison.", "target_role": "dirigeant", "decision_impact": "Départager intervention et non-intervention.", "expected_effort": "Envoyer une facture existante.", "importance": "BLOCKING"}]
    item["expected_properties"] = {"tariff_changes_stakes": True}
    fixtures.append(item)

    # B-J: aucune anomalie, aucun projet.
    item = _base_fixture("B-J", "no_finding_no_action", _decision("DO_NOTHING", [], []), None, [], [], [], {})
    item["technical_finding"] = {"finding_id": "FIND-01", "status": "NORMAL_OPERATION", "uncertainty": "aucun gaspillage significatif détecté", "provenance": ["DS-ENERGY-01"]}
    item["expected_properties"] = {"no_action": True}
    fixtures.append(item)

    # B-K: essai réversible bon marché avant modification permanente.
    inp = [_input("TAR-K", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("TEST-K", "trial_cost", 150, "EUR", "one_off")]
    eff = _effect("EFF-K", {"LOW": 3000, "BASE": 5000, "HIGH": 7000}, "comparable operating regime")
    item = _base_fixture("B-K", "reversible_experiment", _decision("INVESTIGATE_FIRST", ["ACT-K"]), eff, [_action("ACT-K", "EFF-K", title="Essai de consigne réversible", reversible="REVERSIBLE")], inp, [], {"ACT-K": _calculation_spec("EFF-K", {s: .20 for s in SCENARIOS}, {s: "TAR-K" for s in SCENARIOS}, {s: 150 for s in SCENARIOS}, {s: "TEST-K" for s in SCENARIOS})})
    item["expected_properties"] = {"reversible": True, "test_cost_lt_base_benefit": True}
    fixtures.append(item)

    # B-L: delta brut opposé au diagnostic normalisé.
    inp = [_input("TAR-L", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-L", "control_repair", 900, "EUR", "one_off")]
    eff = _effect("EFF-L", {"LOW": 4000, "BASE": 5000, "HIGH": 6000}, "production-adjusted baseline")
    item = _base_fixture("B-L", "production_adjusted_baseline", _decision("ACT_NOW", ["ACT-L"]), eff, [_action("ACT-L", "EFF-L", title="Corriger dérive spécifique")], inp, [], {"ACT-L": _calculation_spec("EFF-L", {s: .20 for s in SCENARIOS}, {s: "TAR-L" for s in SCENARIOS}, {s: 900 for s in SCENARIOS}, {s: "CAP-L" for s in SCENARIOS})})
    item["operating_evidence"] = {"naive_raw_energy_delta_kwh": -10000, "production_change_percent": -40, "production_adjusted_excess_kwh": 5000}
    item["expected_properties"] = {"normalized_differs_materially_from_raw": True}
    fixtures.append(item)

    # B-M: OPEX récurrent réduit mais ne détruit pas le gain.
    inp = [_input("TAR-M", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-M", "retrofit_quote", 5000, "EUR", "one_off"), _input("REC-M", "filter_service", 2500, "EUR/year", "annual")]
    eff = _effect("EFF-M", {s: 20000 for s in SCENARIOS}, "current baseline")
    item = _base_fixture("B-M", "recurring_cost_reduces_economics", _decision("DEFER", ["ACT-M"]), eff, [_action("ACT-M", "EFF-M", title="Retrofit avec entretien")], inp, [], {"ACT-M": _calculation_spec("EFF-M", {s: .20 for s in SCENARIOS}, {s: "TAR-M" for s in SCENARIOS}, {s: 5000 for s in SCENARIOS}, {s: "CAP-M" for s in SCENARIOS}, {s: 2500 for s in SCENARIOS}, {s: "REC-M" for s in SCENARIOS})})
    item["expected_properties"] = {"positive_net": True, "recurring_material": True}
    fixtures.append(item)

    # B-N: l'entretien récurrent annule le gain.
    inp = [_input("TAR-N", "electricity_tariff", .20, "EUR/kWh", "per_kwh"), _input("CAP-N", "retrofit_quote", 1000, "EUR", "one_off"), _input("REC-N", "service_contract", 900, "EUR/year", "annual")]
    eff = _effect("EFF-N", {s: 4000 for s in SCENARIOS}, "current baseline")
    item = _base_fixture("B-N", "negative_economics", _decision("NO_ECONOMIC_CASE", [], ["ACT-N"]), eff, [_action("ACT-N", "EFF-N", title="Retrofit à coût récurrent")], inp, [], {"ACT-N": _calculation_spec("EFF-N", {s: .20 for s in SCENARIOS}, {s: "TAR-N" for s in SCENARIOS}, {s: 1000 for s in SCENARIOS}, {s: "CAP-N" for s in SCENARIOS}, {s: 900 for s in SCENARIOS}, {s: "REC-N" for s in SCENARIOS})})
    item["expected_properties"] = {"non_positive_net": True}
    fixtures.append(item)

    # B-O: petite entreprise, peu de sources, pas de question superflue.
    inp = [_input("TAR-O", "electricity_tariff", .20, "EUR/kWh", "per_kwh")]
    eff = _effect("EFF-O", {"LOW": 3000, "BASE": 4000, "HIGH": 5000}, "historical off-hours reference")
    item = _base_fixture("B-O", "sparse_sme_economics", _decision("INVESTIGATE_FIRST", ["ACT-O"]), eff, [_action("ACT-O", "EFF-O", title="Vérification opérationnelle sans CAPEX", reversible="REVERSIBLE")], inp, [], {"ACT-O": _calculation_spec("EFF-O", {s: .20 for s in SCENARIOS}, {s: "TAR-O" for s in SCENARIOS})})
    item["expected_properties"] = {"sparse_inputs": True, "external_question_count": 0, "monetary_estimate_available": True}
    fixtures.append(item)

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 2, "purpose": "Fixtures B.2 distinctes : données/contrats à raisonner, jamais règles de production.", "fixtures": fixtures}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(generate())
