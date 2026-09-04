"""Contrats et calculs reproductibles pour les décisions opérationnelles-économiques.

Codex formule les findings à retenir, les actions, les contraintes, les
relations et la décision. Python ne fait que calculer, valider les unités, les
références et la reproductibilité des nombres avant persistance.
"""
from __future__ import annotations

import json
from math import isclose
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable

from energy_mvp.tariffs import tariff_plan_from_dict


DECISIONS = {"ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "DEFER", "DO_NOTHING", "NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED", "INSUFFICIENT_FOR_ECONOMIC_DECISION"}
RELATIONSHIP_TYPES = {"INDEPENDENT", "OVERLAPPING", "MUTUALLY_EXCLUSIVE", "DEPENDENT", "SEQUENTIAL", "ALTERNATIVE", "UNKNOWN"}
INPUT_PROVENANCE = {"CLIENT_EXPLICIT", "DOCUMENT_EXTRACTED", "INFERRED_FROM_CLIENT_DATA", "EXTERNAL_ASSUMPTION", "SCENARIO_ASSUMPTION", "UNKNOWN"}
CONSTRAINT_CATEGORIES = {"SAFETY", "QUALITY", "HYGIENE", "PRODUCTION", "THROUGHPUT", "STAFFING", "OPENING_HOURS", "MAINTENANCE_WINDOW", "DOWNTIME", "REDUNDANCY", "REGULATORY", "CUSTOMER_SERVICE", "SEASONALITY", "CASH", "PROCUREMENT", "SPACE", "NOISE", "TEMPERATURE", "PROCESS", "RELIABILITY", "OTHER"}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH", "NOT_CALIBRATED"}
SCENARIOS = ("LOW", "BASE", "HIGH")
REQUEST_TYPES = {"INFER_AUTOMATICALLY", "ASK_CLIENT", "REQUEST_EXISTING_DOCUMENT", "REQUEST_TECHNICAL_EVIDENCE", "OPTIONAL_FUTURE_INSTRUMENTATION", "REQUEST_QUOTE"}
GOAL_B_EVIDENCE_TYPES = {"GOAL_B_CLIENT_RESPONSE", "GOAL_B_DOCUMENT_RESPONSE"}
ENERGY_UNITS = {"kWh/year", "MWh/year"}
ECONOMIC_UNITS = {"EUR/year"}
BASELINE_RESOLUTION_STATUSES = {"COMPATIBLE_DECLARED", "RECONCILED"}
ECONOMIC_COMPONENTS = {
    "tariff_per_kwh": ("/kWh", "per_kwh"),
    "intervention_cost": ("", "one_off"),
    "recurring_cost": ("/year", "annual"),
    "other_annual_benefit": ("/year", "annual"),
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _read(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Objet JSON attendu: {path}")
    return payload


def _require_text(payload: dict[str, Any], fields: Iterable[str], label: str) -> None:
    missing = [field for field in fields if not str(payload.get(field, "")).strip()]
    if missing:
        raise ValueError(f"{label}: champs texte requis absents: {', '.join(missing)}.")


def _non_negative(value: Any, name: str, *, allow_none: bool = False) -> float | None:
    if value is None and allow_none:
        return None
    if not isinstance(value, (int, float)) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{name} doit être un nombre non négatif.")
    return float(value)


def _scenario_values(values: dict[str, Any] | None, label: str) -> dict[str, float] | None:
    if values is None:
        return None
    if not isinstance(values, dict) or set(values) != set(SCENARIOS):
        raise ValueError(f"{label} exige LOW, BASE et HIGH.")
    return {scenario: float(_non_negative(values[scenario], f"{label}/{scenario}")) for scenario in SCENARIOS}


def _validate_ref_map(references: dict[str, Any], component: str, *, required: bool) -> None:
    mapping = references.get(component)
    if mapping is None and not required:
        return
    if not isinstance(mapping, dict) or set(mapping) != set(SCENARIOS):
        raise ValueError(f"Provenance {component} exige LOW, BASE et HIGH.")
    for scenario in SCENARIOS:
        refs = mapping[scenario]
        if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
            raise ValueError(f"Provenance {component}/{scenario} absente ou invalide.")


def validate_economic_input(payload: dict[str, Any]) -> None:
    """Valide une donnée économique; ne la devine jamais."""
    _require_text(payload, ("input_id", "kind", "provenance"), "Input économique")
    if payload["provenance"] not in INPUT_PROVENANCE:
        raise ValueError("Provenance économique inconnue.")
    if payload["provenance"] == "SCENARIO_ASSUMPTION":
        raise ValueError("Une variation de scénario doit utiliser ScenarioAssumption, pas EconomicInput.")
    status = payload.get("status", "KNOWN")
    if status not in {"KNOWN", "UNKNOWN", "SCENARIO"}:
        raise ValueError("Statut économique inconnu.")
    if status == "UNKNOWN":
        if payload.get("value") is not None:
            raise ValueError("Une donnée UNKNOWN ne porte pas de valeur inventée.")
        _require_text(payload, ("unknown_reason",), "Input économique UNKNOWN")
    else:
        _non_negative(payload.get("value"), "Valeur économique")
        _require_text(payload, ("unit", "currency"), "Input économique")
        if not isinstance(payload.get("source"), dict):
            raise ValueError("Une donnée économique connue exige une provenance structurée.")
        if not str(payload["unit"]).startswith(str(payload["currency"])):
            raise ValueError("L'unité économique doit être cohérente avec sa devise.")
        if "/year" in payload["unit"] and payload.get("period") != "annual":
            raise ValueError("Une valeur annuelle exige period=annual.")
        if "/kWh" in payload["unit"] and payload.get("period") != "per_kwh":
            raise ValueError("Un tarif exige period=per_kwh.")
        if payload["unit"] == payload["currency"] and payload.get("period") != "one_off":
            raise ValueError("Un coût ponctuel exige period=one_off.")
    if payload.get("confidence") and payload["confidence"] not in CONFIDENCE_LEVELS:
        raise ValueError("Niveau de confiance économique inconnu.")


def validate_scenario_assumption(payload: dict[str, Any]) -> None:
    _require_text(payload, ("assumption_id", "description", "provenance", "unit", "currency", "period"), "Hypothèse de scénario")
    if payload["provenance"] != "SCENARIO_ASSUMPTION" or payload.get("status") != "SCENARIO" or not isinstance(payload.get("source"), dict):
        raise ValueError("Une hypothèse de scénario exige SCENARIO_ASSUMPTION, status=SCENARIO et une provenance structurée.")
    _non_negative(payload.get("value"), "Valeur d'hypothèse de scénario")
    if not str(payload["unit"]).startswith(str(payload["currency"])):
        raise ValueError("L'unité de l'hypothèse doit être cohérente avec sa devise.")


def validate_energy_effect(payload: dict[str, Any]) -> None:
    _require_text(payload, ("effect_id", "basis", "baseline", "unit", "period"), "Effet énergie")
    if payload["unit"] not in ENERGY_UNITS:
        raise ValueError("Goal B attend un effet annualisé en kWh/year ou MWh/year.")
    if payload.get("basis") not in {"DIRECTLY_MEASURED_HISTORICAL_EXCESS", "COUNTERFACTUAL_ESTIMATE", "MODELED_REDUCTION", "ENGINEERING_ASSUMPTION", "SCENARIO_ESTIMATE"}:
        raise ValueError("Base d'effet énergétique inconnue.")
    values = _scenario_values(payload.get("scenarios"), "Effet énergie")
    assert values is not None
    if not values["LOW"] <= values["BASE"] <= values["HIGH"]:
        raise ValueError("Les scénarios énergie doivent respecter LOW ≤ BASE ≤ HIGH.")
    if not isinstance(payload.get("source_refs"), list) or not payload["source_refs"]:
        raise ValueError("Un effet énergie doit référencer une preuve ou une hypothèse explicite.")
    if not isinstance(payload.get("finding_refs"), list) or not payload["finding_refs"]:
        raise ValueError("Un effet énergie doit référencer au moins un finding Goal A.")


def _value_source_index(inputs: list[dict[str, Any]], assumptions: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for item in inputs:
        validate_economic_input(item)
        identifier = item["input_id"]
        if identifier in records:
            raise ValueError("Identifiants de sources économiques dupliqués.")
        records[identifier] = item
    for item in assumptions:
        validate_scenario_assumption(item)
        identifier = item["assumption_id"]
        if identifier in records:
            raise ValueError("Identifiants de sources économiques dupliqués.")
        records[identifier] = item
    return records


def _validate_component_source(value: float, source: dict[str, Any], component: str, currency: str, scenario: str) -> None:
    suffix, period = ECONOMIC_COMPONENTS[component]
    expected_unit = f"{currency}{suffix}"
    if source.get("status", "KNOWN") == "UNKNOWN" or source.get("unit") != expected_unit or source.get("currency") != currency or source.get("period") != period:
        raise ValueError(f"Source {component}/{scenario} incompatible (valeur, unité, devise ou période).")
    if not isclose(float(source.get("value")), float(value), rel_tol=0.0, abs_tol=1e-12):
        raise ValueError(f"Valeur {component}/{scenario} incohérente avec sa source économique déclarée.")


def validate_constraint(payload: dict[str, Any]) -> None:
    _require_text(payload, ("constraint_id", "category", "description", "source_status"), "Contrainte")
    if payload["category"] not in CONSTRAINT_CATEGORIES or payload["source_status"] not in {"EXPLICIT", "INFERRED", "UNKNOWN"}:
        raise ValueError("Catégorie ou statut de source de contrainte inconnu.")
    if not isinstance(payload.get("hard"), bool) or not isinstance(payload.get("material"), bool) or not isinstance(payload.get("affected_action_ids"), list):
        raise ValueError("Une contrainte exige hard/material booléens et affected_action_ids liste.")
    if payload["source_status"] != "UNKNOWN":
        refs = payload.get("source_refs")
        goal_b_refs = payload.get("goal_b_evidence_refs")
        legacy_ref = payload.get("source_ref")
        if goal_b_refs is not None:
            if not isinstance(goal_b_refs, list) or not goal_b_refs or not all(isinstance(item, str) and item.strip() for item in goal_b_refs):
                raise ValueError("goal_b_evidence_refs d'une contrainte doit être une liste non vide de références.")
        elif refs is not None:
            if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
                raise ValueError("source_refs d'une contrainte doit être une liste non vide de références.")
        elif not isinstance(legacy_ref, str) or not legacy_ref.strip():
            raise ValueError("Une contrainte connue doit citer une ou plusieurs sources.")


def validate_candidate_action(payload: dict[str, Any]) -> None:
    """Valide une action proposée par Codex, sans choisir sa pertinence."""
    _require_text(payload, ("action_id", "title", "description", "action_type", "technical_rationale", "operational_rationale", "implementation_scope", "reversibility"), "Action candidate")
    if not isinstance(payload.get("finding_ids"), list) or not payload["finding_ids"]:
        raise ValueError("Une action candidate doit référencer au moins un finding.")
    if not isinstance(payload.get("requires_professional_validation"), bool):
        raise ValueError("requires_professional_validation doit être booléen.")
    if payload["reversibility"] not in {"REVERSIBLE", "PARTIALLY_REVERSIBLE", "IRREVERSIBLE", "UNKNOWN"}:
        raise ValueError("Réversibilité inconnue.")
    validation = payload.get("validation_plan")
    if not isinstance(validation, dict):
        raise ValueError("Une action doit inclure un plan de validation.")
    _require_text(validation, ("metric", "expected_direction", "comparison_window", "confounders", "minimum_evidence"), "Plan de validation")
    if payload.get("energy_effect_ref") is not None and not str(payload["energy_effect_ref"]).strip():
        raise ValueError("energy_effect_ref doit être non vide lorsqu'il est fourni.")


def validate_relationship(payload: dict[str, Any], action_ids: set[str]) -> None:
    _require_text(payload, ("relationship_id", "type", "action_a", "action_b", "rationale"), "Relation")
    if payload["type"] not in RELATIONSHIP_TYPES:
        raise ValueError("Type de relation inconnu.")
    if payload["action_a"] == payload["action_b"] or {payload["action_a"], payload["action_b"]} - action_ids:
        raise ValueError("Relation d'action invalide.")
    if payload["type"] == "OVERLAPPING" and not payload.get("combined_effect_ref"):
        raise ValueError("Un recouvrement exige une estimation combinée ou un blocage explicite.")
    if payload["type"] in {"DEPENDENT", "SEQUENTIAL"} and not payload.get("sequence"):
        raise ValueError("Une relation dépendante/séquentielle exige une séquence déclarée.")
    resolution = payload.get("baseline_resolution")
    if resolution is not None:
        if not isinstance(resolution, dict) or resolution.get("status") not in BASELINE_RESOLUTION_STATUSES:
            raise ValueError("Résolution de baseline inconnue.")
        _require_text(resolution, ("rationale",), "Résolution de baseline")
        if not isinstance(resolution.get("source_refs"), list) or not resolution["source_refs"]:
            raise ValueError("Une résolution de baseline doit être traçable.")


def validate_decision(payload: dict[str, Any], action_ids: set[str]) -> None:
    """Valide la décision Codex sans règle déterministe de choix."""
    _require_text(payload, ("decision_id", "decision", "reason", "priority_reasoning"), "Décision")
    if payload["decision"] not in DECISIONS:
        raise ValueError("Décision économique inconnue.")
    selected = payload.get("selected_action_ids", payload.get("action_ids", []))
    considered = payload.get("considered_action_ids", selected)
    if not isinstance(selected, list) or not isinstance(considered, list) or set(selected) - action_ids or set(considered) - action_ids:
        raise ValueError("Une décision référence une action inconnue.")
    if set(selected) - set(considered):
        raise ValueError("Toute action sélectionnée doit aussi être considérée.")
    if payload["decision"] in {"ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "DEFER"} and not selected:
        raise ValueError("Cette décision exige au moins une action explicitement choisie par Codex.")
    if payload["decision"] in {"DO_NOTHING", "NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} and selected:
        raise ValueError("Une décision de non-action ne doit pas masquer une action sélectionnée.")
    if payload["decision"] == "OPERATIONALLY_NOT_JUSTIFIED" and not considered:
        raise ValueError("Une non-justification opérationnelle doit conserver l'action considérée.")
    if payload.get("technical_confidence") not in CONFIDENCE_LEVELS or payload.get("economic_importance") not in CONFIDENCE_LEVELS:
        raise ValueError("Confiance technique et importance économique doivent être distinctes.")
    if payload["decision"] == "INVESTIGATE_FIRST":
        evidence = payload.get("evidence_acquisition")
        if not isinstance(evidence, dict):
            raise ValueError("INVESTIGATE_FIRST exige une action d'acquisition de preuve.")
        _require_text(evidence, ("what_it_resolves", "decision_that_can_change", "cost_or_burden", "why_worth_it"), "Acquisition de preuve")
    if payload["decision"] == "OPERATIONALLY_NOT_JUSTIFIED" and not payload.get("blocking_constraint_ids"):
        raise ValueError("Une non-justification opérationnelle exige une contrainte explicitement citée.")
    for assessment in payload.get("constraint_assessments", []):
        _require_text(assessment, ("constraint_id", "disposition", "rationale"), "Évaluation de contrainte")
        if assessment["disposition"] not in {"BLOCKS", "MITIGATED", "NOT_APPLICABLE"}:
            raise ValueError("Disposition de contrainte inconnue.")


def _as_kwh(value: float, unit: str) -> float:
    if unit == "kWh/year":
        return value
    if unit == "MWh/year":
        return value * 1000
    raise ValueError("Unité d'énergie annuelle inconnue.")


def calculate_economic_scenarios(energy_effect: dict[str, Any], *, tariff_per_kwh: dict[str, float] | None, intervention_cost: dict[str, float] | None = None, recurring_cost: dict[str, float] | None = None, other_annual_benefit: dict[str, float] | None = None, input_references: dict[str, Any], currency: str = "EUR") -> dict[str, Any]:
    """Calcule un tableau traçable; tout nombre matériel porte ses références."""
    validate_energy_effect(energy_effect)
    inputs = {"tariff_per_kwh": _scenario_values(tariff_per_kwh, "tariff_per_kwh"), "intervention_cost": _scenario_values(intervention_cost, "intervention_cost"), "recurring_cost": _scenario_values(recurring_cost, "recurring_cost"), "other_annual_benefit": _scenario_values(other_annual_benefit, "other_annual_benefit")}
    if not isinstance(input_references, dict):
        raise ValueError("Les calculs économiques exigent des références d'inputs structurées.")
    _validate_ref_map(input_references, "energy_effect", required=True)
    for component, values in inputs.items():
        _validate_ref_map(input_references, component, required=values is not None)
    if not isinstance(currency, str) or not currency.strip():
        raise ValueError("Une devise explicite est obligatoire.")
    output: dict[str, Any] = {"schema_version": 2, "calculation_method": "deterministic_scenario_v2", "currency": currency, "effect_id": energy_effect["effect_id"], "baseline": energy_effect["baseline"], "period": energy_effect["period"], "scenarios": {}, "calculation_notes": [], "reproducibility": {"calculator": "calculate_economic_scenarios", "calculator_schema_version": 2, "energy_effect": energy_effect, "input_values": inputs, "input_references": input_references}}
    if inputs["tariff_per_kwh"] is None:
        output["calculation_notes"].append("Tarif inconnu : bénéfice monétaire et payback non calculés.")
    for scenario in SCENARIOS:
        energy_kwh = _as_kwh(float(energy_effect["scenarios"][scenario]), energy_effect["unit"])
        tariff = None if inputs["tariff_per_kwh"] is None else inputs["tariff_per_kwh"][scenario]
        gross = None if tariff is None else energy_kwh * tariff
        recurring = None if inputs["recurring_cost"] is None else inputs["recurring_cost"][scenario]
        other = None if inputs["other_annual_benefit"] is None else inputs["other_annual_benefit"][scenario]
        net = None if gross is None else gross + (other or 0.0) - (recurring or 0.0)
        cost = None if inputs["intervention_cost"] is None else inputs["intervention_cost"][scenario]
        payback = None if net is None or cost is None or net <= 0 else cost / net
        output["scenarios"][scenario] = {"annual_energy_saving_kwh": energy_kwh, "tariff_per_kwh": tariff, "gross_annual_energy_cost_avoided": gross, "incremental_recurring_cost": recurring, "other_supported_annual_benefit": other, "net_annual_benefit": net, "intervention_cost": cost, "simple_payback_years": payback, "payback_status": "meaningful" if payback is not None else "not_meaningful_or_unknown"}
    return output


def _verify_deterministic_calculation(calculation: dict[str, Any]) -> None:
    reproducibility = calculation.get("reproducibility")
    if not isinstance(reproducibility, dict) or reproducibility.get("calculator") != "calculate_economic_scenarios":
        raise ValueError("Calcul économique non reproductible ou généré hors calculateur déterministe.")
    expected = calculate_economic_scenarios(reproducibility.get("energy_effect", {}), tariff_per_kwh=reproducibility.get("input_values", {}).get("tariff_per_kwh"), intervention_cost=reproducibility.get("input_values", {}).get("intervention_cost"), recurring_cost=reproducibility.get("input_values", {}).get("recurring_cost"), other_annual_benefit=reproducibility.get("input_values", {}).get("other_annual_benefit"), input_references=reproducibility.get("input_references", {}), currency=calculation.get("currency", ""))
    fields = ("schema_version", "calculation_method", "currency", "effect_id", "baseline", "period", "scenarios", "calculation_notes", "reproducibility")
    if {key: calculation.get(key) for key in fields} != {key: expected.get(key) for key in fields}:
        raise ValueError("Calcul économique soumis incohérent avec sa reproduction déterministe.")


def _validate_calculation_provenance(calculation: dict[str, Any], *, value_sources: dict[str, dict[str, Any]], allowed_energy_refs: set[str]) -> None:
    _verify_deterministic_calculation(calculation)
    references = calculation["reproducibility"]["input_references"]
    energy_refs = {ref for values in references["energy_effect"].values() for ref in values}
    if energy_refs - allowed_energy_refs:
        raise ValueError("Calcul économique référence une preuve énergétique absente du cas Goal A.")
    values = calculation["reproducibility"]["input_values"]
    for component, scenario_values in values.items():
        if scenario_values is None:
            continue
        mapping = references.get(component)
        if not isinstance(mapping, dict):
            raise ValueError(f"Provenance {component} absente.")
        for scenario in SCENARIOS:
            refs = mapping.get(scenario)
            if not isinstance(refs, list) or len(refs) != 1 or refs[0] not in value_sources:
                raise ValueError(f"Chaque valeur {component}/{scenario} doit référencer exactement une source économique existante.")
            _validate_component_source(float(scenario_values[scenario]), value_sources[refs[0]], component, calculation["currency"], scenario)


def calculate_time_aligned_savings(timed_savings: Iterable[dict[str, Any]], *, price_for_timestamp: callable) -> dict[str, Any]:
    total_kwh = 0.0
    total_cost = 0.0
    entries = 0
    for item in timed_savings:
        timestamp = item.get("timestamp")
        kwh = _non_negative(item.get("energy_saving_kwh"), "Économie horodatée")
        if not isinstance(timestamp, str) or not timestamp:
            raise ValueError("Une économie horodatée exige timestamp.")
        price = price_for_timestamp(timestamp)
        _non_negative(price, "Tarif horodaté")
        total_kwh += float(kwh)
        total_cost += float(kwh) * float(price)
        entries += 1
    return {"entries": entries, "time_aligned_energy_saving_kwh": total_kwh, "time_aligned_cost_saving": total_cost, "approximation": False}


def calculate_time_aligned_savings_with_tariff_plan(timed_savings: Iterable[dict[str, Any]], tariff_payload: dict[str, Any]) -> dict[str, Any]:
    plan = tariff_plan_from_dict(tariff_payload)
    def price(timestamp: str) -> float:
        local = datetime.fromisoformat(timestamp)
        minute = local.hour * 60 + local.minute
        matches = [period for period in plan.time_of_use if period.matches(local.weekday(), minute)]
        resolved = matches[0].price_per_kwh if matches else plan.default_price_per_kwh
        if resolved is None:
            raise ValueError("Le plan tarifaire ne couvre pas cet instant d'économie.")
        return float(resolved)
    output = calculate_time_aligned_savings(timed_savings, price_for_timestamp=price)
    output.update({"currency": plan.currency, "tariff_alignment": "time_resolved"})
    return output


def _baseline_is_resolved(left: dict[str, Any], right: dict[str, Any], relation: dict[str, Any]) -> bool:
    return left["baseline"] == right["baseline"] or relation.get("baseline_resolution", {}).get("status") in BASELINE_RESOLUTION_STATUSES


def _combined_table(entry: dict[str, Any], value_sources: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if not isinstance(entry, dict):
        raise ValueError("Un effet combiné doit être un objet typé, jamais un nombre nu.")
    if entry.get("effect_type") == "ENERGY":
        effect, calculation = entry.get("energy_effect"), entry.get("economic_calculation")
        validate_energy_effect(effect if isinstance(effect, dict) else {})
        if not isinstance(calculation, dict):
            raise ValueError("Un effet énergie combiné exige un recalcul économique déterministe.")
        _verify_deterministic_calculation(calculation)
        if calculation.get("effect_id") != effect["effect_id"] or calculation.get("baseline") != effect["baseline"]:
            raise ValueError("L'effet énergie combiné et son calcul ne correspondent pas.")
        _validate_calculation_provenance(calculation, value_sources=value_sources, allowed_energy_refs=set(effect["finding_refs"]) | set(effect["source_refs"]))
        return calculation
    if entry.get("effect_type") == "ECONOMIC":
        _require_text(entry, ("effect_id", "unit", "period", "baseline", "currency"), "Effet économique combiné")
        if entry["unit"] not in ECONOMIC_UNITS or entry["period"] != "annual":
            raise ValueError("Un effet économique combiné doit expliciter EUR/year et une période annualisée.")
        scenarios = _scenario_values(entry.get("scenarios"), "Effet économique combiné")
        assert scenarios is not None
        references = entry.get("value_source_refs")
        if not isinstance(references, dict) or set(references) != set(SCENARIOS):
            raise ValueError("Un effet économique combiné direct exige une source de valeur par scénario.")
        for scenario in SCENARIOS:
            refs = references[scenario]
            if not isinstance(refs, list) or len(refs) != 1 or refs[0] not in value_sources:
                raise ValueError("Un effet économique combiné direct référence une provenance inexistante.")
            _validate_component_source(scenarios[scenario], value_sources[refs[0]], "other_annual_benefit", entry["currency"], scenario)
        return {"currency": entry["currency"], "baseline": entry["baseline"], "scenarios": {scenario: {"net_annual_benefit": scenarios[scenario]} for scenario in SCENARIOS}}
    raise ValueError("Type d'effet combiné invalide; ENERGY ou ECONOMIC explicite requis.")


def aggregate_declared_portfolio(selected_action_ids: list[str], scenario_tables: dict[str, dict[str, Any]], relationships: list[dict[str, Any]], *, combined_effects: dict[str, dict[str, Any]] | None = None, economic_value_sources: list[dict[str, Any]] | None = None, scenario_assumptions: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Agrège seulement un portefeuille entièrement déclaré et dimensionnellement sûr."""
    selected = set(selected_action_ids)
    if not selected or selected - set(scenario_tables):
        raise ValueError("Le portefeuille doit sélectionner des actions avec scénarios connus.")
    value_sources = _value_source_index(economic_value_sources or [], scenario_assumptions or [])
    for table in scenario_tables.values():
        _verify_deterministic_calculation(table)
    relationship_by_pair: dict[frozenset[str], dict[str, Any]] = {}
    for relation in relationships:
        pair = frozenset((relation.get("action_a"), relation.get("action_b")))
        if len(pair) != 2 or pair in relationship_by_pair:
            raise ValueError("Relation de portefeuille invalide ou concurrente.")
        relationship_by_pair[pair] = relation
    base = {scenario: 0.0 for scenario in SCENARIOS}
    adjustments = {scenario: 0.0 for scenario in SCENARIOS}
    for action_id in selected:
        for scenario in SCENARIOS:
            benefit = scenario_tables[action_id]["scenarios"][scenario]["net_annual_benefit"]
            if benefit is None:
                raise ValueError("Un portefeuille ne somme pas un bénéfice annuel inconnu.")
            base[scenario] += float(benefit)
    for left, right in combinations(sorted(selected), 2):
        relation = relationship_by_pair.get(frozenset((left, right)))
        if relation is None:
            raise ValueError("Relation UNKNOWN par omission : aucune agrégation n'est autorisée.")
        relation_type = relation.get("type")
        if relation_type not in RELATIONSHIP_TYPES:
            raise ValueError("Type de relation inconnu dans le portefeuille.")
        if not _baseline_is_resolved(scenario_tables[left], scenario_tables[right], relation):
            raise ValueError("Baselines différentes sans compatibilité ou réconciliation explicitement déclarée.")
        if relation_type == "INDEPENDENT":
            continue
        if relation_type in {"MUTUALLY_EXCLUSIVE", "ALTERNATIVE"}:
            raise ValueError("Des actions mutuellement exclusives/alternatives ne peuvent pas être sommées.")
        if relation_type in {"DEPENDENT", "SEQUENTIAL", "UNKNOWN"}:
            raise ValueError("Relation dépendante, séquentielle ou inconnue : fournir un modèle combiné explicite.")
        if relation_type != "OVERLAPPING":
            raise ValueError("Relation de portefeuille non traitable.")
        reference = relation.get("combined_effect_ref")
        if not reference or not combined_effects or reference not in combined_effects:
            raise ValueError("Recouvrement sans effet combiné déclaré: aucune somme n'est autorisée.")
        combined = _combined_table(combined_effects[reference], value_sources)
        if combined.get("currency") != scenario_tables[left].get("currency") or combined.get("currency") != scenario_tables[right].get("currency"):
            raise ValueError("Devises incompatibles pour effet combiné.")
        if not _baseline_is_resolved(scenario_tables[left], combined, relation) or not _baseline_is_resolved(scenario_tables[right], combined, relation):
            raise ValueError("Baseline de l'effet combiné non résolue.")
        for scenario in SCENARIOS:
            value = combined["scenarios"][scenario]["net_annual_benefit"]
            if value is None:
                raise ValueError("Effet combiné sans bénéfice annuel monétaire calculable.")
            separate = scenario_tables[left]["scenarios"][scenario]["net_annual_benefit"] + scenario_tables[right]["scenarios"][scenario]["net_annual_benefit"]
            adjustments[scenario] += float(value) - float(separate)
    return {"selected_action_ids": sorted(selected), "net_annual_benefit": {scenario: base[scenario] + adjustments[scenario] for scenario in SCENARIOS}, "relationship_adjustments": adjustments, "deterministic_decision": None}


def initialize_economic_state(case_directory: str | Path) -> dict[str, Any]:
    case = Path(case_directory)
    if not (case / "case_manifest.json").is_file():
        raise ValueError("Le dossier doit être un cas Goal A valide.")
    path = case / "investigation" / "economic_decision_state.json"
    if path.exists():
        raise FileExistsError("L'état économique existe déjà et ne sera pas réinitialisé.")
    canonical = _read(case / "derived" / "canonical_case.json")
    state = {"schema_version": 5, "created_at_utc": _now(), "status": "awaiting_codex_economic_reasoning", "technical_finding_refs": [], "economic_inputs": [], "scenario_assumptions": [], "operational_constraints": [], "candidate_actions": [], "relationships": [], "combined_effects": {}, "scenario_calculations": {}, "decisions": [], "economic_requests": [], "goal_b_evidence": [], "recommendation_provenance": None, "unresolved_blockers": canonical.get("unresolved_material_ambiguities", []), "provenance_context": {"canonical_case": "derived/canonical_case.json", "dataset_provenance": "evidence/dataset_provenance.json", "technical_findings": "investigation/structured_findings.json", "goal_b_evidence": "investigation/economic_decision_state.json#goal_b_evidence"}, "history": [{"at_utc": _now(), "action": "economic_state_initialized"}], "ground_truth_used": False, "deterministic_recommendation_engine": False}
    _write(path, state)
    return state


def _pre_reasoning_context(case: Path) -> dict[str, Any]:
    canonical = _read(case / "derived" / "canonical_case.json")
    findings_path = case / "investigation" / "structured_findings.json"
    findings_payload = _read(findings_path) if findings_path.exists() else {"findings": [], "no_finding": None}
    inventory_path = case / "evidence" / "intake_inventory.json"
    inventory = _read(inventory_path) if inventory_path.exists() else {"artifacts": []}
    roles = {"TARIFF", "INVOICE", "SCHEDULE", "MAINTENANCE", "MACHINE_METADATA", "PROCESS_CONTEXT", "PRODUCTION", "TEXT_NOTE"}
    documents = [{key: artifact.get(key) for key in ("artifact_id", "original_filename", "probable_role", "usability", "role_evidence")} for artifact in inventory.get("artifacts", []) if artifact.get("probable_role") in roles]
    ambiguities = list(canonical.get("unresolved_material_ambiguities", []))
    for dataset in canonical.get("available_datasets", []):
        interpretation = dataset.get("data_quality", {}).get("unit_interpretation", {})
        if interpretation.get("status") == "MATERIAL_AMBIGUITY":
            ambiguities.append({"dataset_id": dataset.get("dataset_id"), "issue": interpretation.get("basis")})
    return {"technical_findings": findings_payload.get("findings", []), "technical_no_finding": findings_payload.get("no_finding"), "technical_findings_source": "investigation/structured_findings.json", "known_facts": canonical.get("known_facts", []), "available_context_roles": canonical.get("evidence_by_role", {}), "available_economic_operational_documents": documents, "unresolved_material_ambiguities": ambiguities, "dataset_provenance_ref": "evidence/dataset_provenance.json", "canonical_case_ref": "derived/canonical_case.json"}


def _case_provenance_ids(case: Path) -> set[str]:
    """Références Goal A réellement disponibles, sans inventer une preuve économique."""
    canonical = _read(case / "derived" / "canonical_case.json")
    identifiers = {dataset.get("dataset_id") for dataset in canonical.get("available_datasets", []) if dataset.get("dataset_id")}
    identifiers.update(item.get("artifact_id") for item in canonical.get("known_facts", []) if item.get("artifact_id"))
    for values in canonical.get("evidence_by_role", {}).values():
        identifiers.update(value for value in values if isinstance(value, str))
    inventory_path = case / "evidence" / "intake_inventory.json"
    if inventory_path.exists():
        identifiers.update(item.get("artifact_id") for item in _read(inventory_path).get("artifacts", []) if item.get("artifact_id"))
    return identifiers


def _goal_a_findings(case: Path) -> dict[str, dict[str, Any]]:
    findings_path = case / "investigation" / "structured_findings.json"
    if not findings_path.exists():
        return {}
    payload = _read(findings_path)
    findings = payload.get("findings", [])
    if not isinstance(findings, list):
        raise ValueError("Artefact Goal A structured_findings.json invalide.")
    result: dict[str, dict[str, Any]] = {}
    for item in findings:
        if not isinstance(item, dict) or not item.get("finding_id"):
            continue
        _require_text(item, ("status", "confidence"), "Finding Goal A")
        result[item["finding_id"]] = item
    return result


def _canonical_no_finding(case: Path) -> dict[str, Any] | None:
    """Retourne uniquement une conclusion no-finding Goal A complète et canonique."""
    findings_path = case / "investigation" / "structured_findings.json"
    if not findings_path.exists():
        return None
    payload = _read(findings_path)
    no_finding = payload.get("no_finding")
    if payload.get("findings") != [] or not isinstance(no_finding, dict):
        return None
    required = ("what_was_analyzed", "usable_period", "operating_regimes", "limitations", "monitoring_baseline_meaningful")
    if any(field not in no_finding for field in required):
        return None
    return no_finding


def _source_refs(payload: dict[str, Any], *, label: str) -> list[str]:
    """Extrait une provenance explicite, sans accepter un nom de fichier libre."""
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError(f"{label} exige une provenance structurée.")
    refs = source.get("source_refs")
    if refs is None:
        # Compatibilité strictement structurée pour les producteurs existants;
        # les aliases de type `artifact: filename.txt` ne sont pas acceptés.
        refs = [source[key] for key in ("artifact_id", "dataset_id") if isinstance(source.get(key), str) and source[key].strip()]
    if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
        raise ValueError(f"{label} exige source.source_refs ou un artifact_id/dataset_id structuré.")
    return list(dict.fromkeys(refs))


def _goal_b_evidence_refs(payload: dict[str, Any], *, label: str) -> list[str]:
    source = payload.get("source")
    if not isinstance(source, dict):
        raise ValueError(f"{label} exige une provenance structurée.")
    refs = source.get("goal_b_evidence_refs")
    if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
        raise ValueError(f"{label} exige source.goal_b_evidence_refs structurées.")
    return list(dict.fromkeys(refs))


def _goal_b_evidence_index(state: dict[str, Any]) -> dict[str, dict[str, Any]]:
    evidence = state.get("goal_b_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("L'état Goal B contient des preuves natives invalides.")
    index: dict[str, dict[str, Any]] = {}
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("evidence_id"), str) or not item["evidence_id"].strip():
            raise ValueError("Une preuve native Goal B doit avoir un evidence_id stable.")
        if item["evidence_id"] in index:
            raise ValueError("Identifiants de preuves Goal B dupliqués.")
        if item.get("evidence_type") not in GOAL_B_EVIDENCE_TYPES or not isinstance(item.get("content"), dict):
            raise ValueError("Une preuve native Goal B est incomplète ou de type inconnu.")
        index[item["evidence_id"]] = item
    return index


def _case_provenance_metadata(case: Path) -> dict[str, dict[str, Any]]:
    """Métadonnées structurées seulement; aucune interprétation de texte libre."""
    metadata: dict[str, dict[str, Any]] = {}
    inventory_path = case / "evidence" / "intake_inventory.json"
    if inventory_path.exists():
        for item in _read(inventory_path).get("artifacts", []):
            if item.get("artifact_id"):
                metadata[item["artifact_id"]] = {"probable_role": item.get("probable_role"), "usability": item.get("usability")}
    canonical = _read(case / "derived" / "canonical_case.json")
    for dataset in canonical.get("available_datasets", []):
        if dataset.get("dataset_id"):
            metadata.setdefault(dataset["dataset_id"], {"probable_role": dataset.get("role"), "usability": "usable"})
    return metadata


def _reject_irrelevant_source(refs: list[str], metadata: dict[str, dict[str, Any]], payload: dict[str, Any], *, label: str) -> None:
    """Rejette une incompatibilité explicite, sauf justification structurée de Codex."""
    irrelevant = [ref for ref in refs if metadata.get(ref, {}).get("probable_role") == "IRRELEVANT"]
    if irrelevant and not str(payload.get("source_justification", "")).strip():
        raise ValueError(f"{label} ne peut pas s'appuyer silencieusement sur un artefact IRRELEVANT.")


def _validate_economic_input_sources(
    inputs: list[dict[str, Any]], known_goal_a_refs: set[str], goal_b_evidence: dict[str, dict[str, Any]], source_metadata: dict[str, dict[str, Any]],
) -> None:
    """Ferme les sources client de Goal B sur les artefacts/datasets réels du cas."""
    for item in inputs:
        provenance = item["provenance"]
        if item.get("status", "KNOWN") == "UNKNOWN":
            continue
        if provenance in {"CLIENT_EXPLICIT", "DOCUMENT_EXTRACTED", "INFERRED_FROM_CLIENT_DATA"}:
            source = item.get("source", {})
            if source.get("goal_b_evidence_refs") is not None:
                refs = _goal_b_evidence_refs(item, label=f"EconomicInput {item['input_id']}")
                if set(refs) - set(goal_b_evidence):
                    raise ValueError(f"EconomicInput {item['input_id']} référence une preuve Goal B inexistante.")
                if provenance == "CLIENT_EXPLICIT" and any(goal_b_evidence[ref]["evidence_type"] != "GOAL_B_CLIENT_RESPONSE" for ref in refs):
                    raise ValueError("CLIENT_EXPLICIT doit citer une réponse client Goal B lorsqu'il utilise une preuve Goal B.")
                structured_values = [goal_b_evidence[ref].get("structured_value") for ref in refs]
                if len(refs) != 1 or not isinstance(structured_values[0], dict):
                    raise ValueError("Une valeur économique Goal B doit provenir d'une preuve structurée unique.")
                value = structured_values[0]
                for field in ("value", "unit", "currency", "period"):
                    if value.get(field) != item.get(field):
                        raise ValueError(f"EconomicInput {item['input_id']} ne correspond pas à la valeur de sa preuve Goal B.")
            else:
                refs = _source_refs(item, label=f"EconomicInput {item['input_id']}")
                if set(refs) - known_goal_a_refs:
                    raise ValueError(f"EconomicInput {item['input_id']} référence une source Goal A inexistante.")
                _reject_irrelevant_source(refs, source_metadata, item, label=f"EconomicInput {item['input_id']}")
        elif provenance == "EXTERNAL_ASSUMPTION":
            source = item.get("source", {})
            if source.get("source_type") != "GOAL_B_EXTERNAL_ASSUMPTION":
                raise ValueError("Une valeur externe Goal B exige source_type=GOAL_B_EXTERNAL_ASSUMPTION.")
            _require_text(source, ("description",), "Provenance externe Goal B")


def _constraint_refs(constraint: dict[str, Any]) -> list[str]:
    refs = constraint.get("source_refs")
    if refs is None:
        refs = [constraint["source_ref"]] if isinstance(constraint.get("source_ref"), str) else []
    if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
        raise ValueError("Une contrainte factuelle exige au moins une référence structurée.")
    return list(dict.fromkeys(refs))


def _validate_constraint_sources(
    constraints: list[dict[str, Any]], known_goal_a_refs: set[str], goal_b_evidence: dict[str, dict[str, Any]], source_metadata: dict[str, dict[str, Any]],
) -> None:
    for constraint in constraints:
        if constraint["source_status"] == "UNKNOWN":
            continue
        if constraint.get("goal_b_evidence_refs") is not None:
            refs = constraint["goal_b_evidence_refs"]
            if not isinstance(refs, list) or not refs or not all(isinstance(item, str) and item.strip() for item in refs):
                raise ValueError("Une contrainte Goal B exige goal_b_evidence_refs structurées.")
            if set(refs) - set(goal_b_evidence):
                raise ValueError(f"Contrainte {constraint['constraint_id']} référence une preuve Goal B inexistante.")
        else:
            refs = _constraint_refs(constraint)
            if set(refs) - known_goal_a_refs:
                raise ValueError(f"Contrainte {constraint['constraint_id']} référence une source Goal A inexistante.")
            _reject_irrelevant_source(refs, source_metadata, constraint, label=f"Contrainte {constraint['constraint_id']}")


def _resolve_technical_finding_refs(
    references: list[dict[str, Any]], findings: dict[str, dict[str, Any]], *, allow_canonical_no_finding: bool = False,
) -> list[dict[str, Any]]:
    """Résout la vérité technique depuis Goal A; Goal B ne peut pas la réécrire."""
    if allow_canonical_no_finding and references == []:
        return []
    if not isinstance(references, list) or not references:
        raise ValueError("Goal B doit référencer au moins un finding Goal A réel.")
    resolved: list[dict[str, Any]] = []
    seen: set[str] = set()
    for reference in references:
        if not isinstance(reference, dict) or not isinstance(reference.get("finding_id"), str):
            raise ValueError("Référence de finding Goal A invalide.")
        finding_id = reference["finding_id"]
        if finding_id in seen or finding_id not in findings:
            raise ValueError("technical_finding_refs doit référencer des findings réellement présents dans Goal A.")
        finding = findings[finding_id]
        for field, source_field in (("technical_status", "status"), ("technical_confidence", "confidence")):
            if field in reference and reference[field] != finding[source_field]:
                raise ValueError(f"Goal B ne peut pas altérer {field} du finding Goal A {finding_id}.")
        if "provenance" in reference and reference["provenance"] != "investigation/structured_findings.json":
            raise ValueError("La provenance technique Goal B doit rester l'artefact canonique Goal A.")
        resolved.append({
            "finding_id": finding_id,
            "technical_status": finding["status"],
            "technical_confidence": finding["confidence"],
            "provenance": "investigation/structured_findings.json",
        })
        seen.add(finding_id)
    return resolved


def _build_recommendation_provenance(
    decisions: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    calculations: dict[str, dict[str, Any]],
    value_sources: dict[str, dict[str, Any]],
    constraints: list[dict[str, Any]],
) -> dict[str, Any]:
    """Matérialise une chaîne auditable sans décider ni interpréter l'action.

    B.4 persistait un seul record de décision.  Goal C.1 peut désormais
    communiquer plusieurs décisions indépendantes dans un même cas; cette
    fonction conserve donc le rattachement décision → action, sans jamais
    choisir elle-même les actions ni leur priorité.
    """
    selected = set().union(*(set(item.get("selected_action_ids", item.get("action_ids", []))) for item in decisions)) if decisions else set()
    considered = set().union(*(set(item.get("considered_action_ids", item.get("selected_action_ids", item.get("action_ids", [])))) for item in decisions)) if decisions else set()
    constraints_by_action = {
        action_id: [item["constraint_id"] for item in constraints if action_id in item["affected_action_ids"]]
        for action_id in considered
    }
    chains: list[dict[str, Any]] = []
    decision_by_action = {
        action_id: decision["decision_id"]
        for decision in decisions
        for action_id in decision.get("considered_action_ids", decision.get("selected_action_ids", decision.get("action_ids", [])))
    }
    for action in actions:
        if action["action_id"] not in considered:
            continue
        calculation = calculations.get(action["action_id"])
        source_links: list[dict[str, Any]] = []
        if calculation is not None:
            refs = calculation["reproducibility"]["input_references"]
            values = calculation["reproducibility"]["input_values"]
            for component, scenario_values in values.items():
                if scenario_values is None:
                    continue
                source_links.append({
                    "component": component,
                    "scenario_source_ids": {scenario: refs[component][scenario][0] for scenario in SCENARIOS},
                })
        chains.append({
            "action_id": action["action_id"],
            "decision_id": decision_by_action.get(action["action_id"]),
            "selection_status": "SELECTED" if action["action_id"] in selected else "CONSIDERED_ONLY",
            "finding_ids": action["finding_ids"],
            "energy_effect_ref": action.get("energy_effect_ref"),
            "calculation_ref": action["action_id"] if calculation is not None else None,
            "economic_source_links": source_links,
            "constraint_ids": constraints_by_action[action["action_id"]],
        })
    return {
        "schema_version": 2,
        "decision_ids": [item["decision_id"] for item in decisions],
        "selected_action_chains": [item for item in chains if item["selection_status"] == "SELECTED"],
        "considered_action_chains": [item for item in chains if item["selection_status"] == "CONSIDERED_ONLY"],
        "economic_sources": [
            {
                "source_id": source_id,
                "provenance": source["provenance"],
                "status": source.get("status", "KNOWN"),
                "source": source.get("source"),
            }
            for source_id, source in sorted(value_sources.items())
        ],
        "chain_is_reference_validated": True,
    }


def economic_handoff(case_directory: str | Path) -> dict[str, Any]:
    """Produit un handoff nommé pré-raisonnement ou reprise, sans écrasement."""
    case = Path(case_directory)
    if not (case / "case_manifest.json").is_file():
        raise ValueError("Le dossier doit être un cas Goal A valide.")
    state_path = case / "investigation" / "economic_decision_state.json"
    state = _read(state_path) if state_path.exists() else None
    phase = "pre_reasoning" if state is None else "resume_reasoning"
    artifact = "economic_handoff_pre_reasoning.json" if state is None else "economic_handoff_resume.json"
    payload = {"schema_version": 4, "phase": phase, "artifact": f"investigation/{artifact}", "purpose": "Contexte Goal A → Goal B pour raisonnement Codex; pas une recommandation automatique.", **_pre_reasoning_context(case), "existing_economic_state": None if state is None else {"economic_inputs": state["economic_inputs"], "scenario_assumptions": state.get("scenario_assumptions", []), "constraints": state["operational_constraints"], "candidate_actions": state["candidate_actions"], "relationships": state["relationships"], "combined_effects": state.get("combined_effects", {}), "decisions": state["decisions"], "economic_requests": state["economic_requests"], "goal_b_evidence": state.get("goal_b_evidence", [])}, "codex_must_decide": ["candidate actions", "material constraints", "relationships", "baseline reconciliation", "economic assumptions", "evidence worth buying", "decision", "priority", "validation"], "python_can_calculate": ["scenario table", "time-aligned tariff impact", "payback when meaningful", "declared portfolio arithmetic", "reproducibility validation"], "deterministic_recommendation_engine": False}
    _write(case / "investigation" / artifact, payload)
    return payload


def build_economic_request_batch(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Valide un batch faible-friction rédigé par Codex; ne formule aucune question."""
    if sum(item.get("request_type") != "INFER_AUTOMATICALLY" for item in requests) > 3:
        raise ValueError("Un batch économique normal est limité à trois demandes.")
    normalized = []
    for index, request in enumerate(requests, start=1):
        if request.get("request_type") not in REQUEST_TYPES:
            raise ValueError("Type de demande économique invalide.")
        if request["request_type"] == "INFER_AUTOMATICALLY":
            _require_text(request, ("internal_reason", "decision_impact"), "Inférence économique")
            normalized.append({**request, "request_id": request.get("request_id", f"ECO-REQ-{index:02d}"), "client_question": None, "target_role": None, "expected_effort": "NONE", "analysis_can_continue_without_answer": True})
            continue
        _require_text(request, ("client_question", "internal_reason", "target_role", "decision_impact", "expected_effort"), "Demande économique")
        if len(request["client_question"].strip()) < 12:
            raise ValueError("Demande économique trop vague.")
        normalized.append({**request, "request_id": request.get("request_id", f"ECO-REQ-{index:02d}"), "analysis_can_continue_without_answer": request.get("importance", "NON_BLOCKING") != "BLOCKING"})
    return {"schema_version": 2, "requests": normalized, "default_question_count": 0, "generated_by": "Codex; Python validated schema only"}

def publish_economic_request_batch(case_directory: str | Path, requests: list[dict[str, Any]], *, new_material_branch: dict[str, Any] | None = None) -> dict[str, Any]:
    """Adaptateur Goal B vers l'unique `questions.json`."""
    from energy_mvp.client_lifecycle import publish_client_requests
    return publish_client_requests(case_directory,[x for x in requests if x.get("request_type")!="INFER_AUTOMATICALLY"],new_material_branch=new_material_branch)


def record_goal_b_evidence(case_directory: str | Path, evidence: dict[str, Any]) -> dict[str, Any]:
    """Ajoute une réponse post-Goal A immuable, sans la déguiser en artefact Goal A.

    La fonction ne tire aucune conclusion du contenu : elle vérifie seulement
    l'identité, le lien éventuel avec une demande connue et la forme d'une
    valeur structurée lorsqu'elle est présente.
    """
    case = Path(case_directory)
    path = case / "investigation" / "economic_decision_state.json"
    if not path.exists():
        raise ValueError("Initialisez l'état Goal B avant d'enregistrer une réponse post-Goal A.")
    state = _read(path)
    _require_text(evidence, ("evidence_id", "evidence_type"), "Preuve Goal B")
    if evidence["evidence_type"] not in GOAL_B_EVIDENCE_TYPES:
        raise ValueError("Type de preuve Goal B inconnu.")
    case_id = _read(case / "case_manifest.json").get("case_id", case.name)
    if evidence.get("case_id") not in {None, case_id}:
        raise ValueError("La preuve Goal B appartient à un autre case_id.")
    if not isinstance(evidence.get("content"), dict) or not evidence["content"]:
        raise ValueError("Une preuve Goal B exige un contenu structuré non vide.")
    if evidence.get("structured_value") is not None:
        value = evidence["structured_value"]
        if not isinstance(value, dict):
            raise ValueError("structured_value Goal B doit être un objet.")
        _non_negative(value.get("value"), "Valeur de preuve Goal B")
        _require_text(value, ("unit", "currency", "period"), "Valeur de preuve Goal B")
        if not str(value["unit"]).startswith(str(value["currency"])):
            raise ValueError("L'unité de la valeur Goal B doit être cohérente avec sa devise.")
    requests = {item.get("request_id"): item for item in state.get("economic_requests", [])}
    request_id = evidence.get("request_id")
    if request_id is not None and request_id not in requests:
        raise ValueError("La preuve Goal B référence une demande économique inexistante.")
    indexed = _goal_b_evidence_index(state)
    if evidence["evidence_id"] in indexed:
        raise ValueError("Une preuve Goal B est immuable : evidence_id déjà enregistré.")
    recorded = {
        **evidence,
        "case_id": case_id,
        "acquisition_order": len(indexed) + 1,
        "recorded_at_utc": _now(),
    }
    canonical_path=case/"investigation/questions.json"
    if request_id is not None and canonical_path.exists():
        canonical=_read(canonical_path); target=next((x for x in canonical.get("questions",[]) if x.get("request_id")==request_id and x.get("status")=="open"),None)
        if target is not None:
            from energy_mvp.client_lifecycle import record_canonical_answers
            response=evidence.get("content",{}).get("response_text")
            if not isinstance(response,str) or not response.strip(): raise ValueError("Une réponse Goal B canonique exige content.response_text.")
            result=record_canonical_answers(case,[{"answer_id":f"ANS-{evidence['evidence_id']}","request_id":request_id,"answer":response,
              "provided_by_role":evidence.get("provided_by_role","interlocuteur client Goal B"),"source_or_evidence":evidence.get("provenance",f"investigation/economic_decision_state.json#{evidence['evidence_id']}"),
              "source_type":"EXISTING_DOCUMENT" if evidence["evidence_type"]=="GOAL_B_DOCUMENT_RESPONSE" else "CLIENT_DECLARATION","provided_at_utc":evidence.get("provided_at_utc",_now()),"reliability":float(evidence.get("reliability",.65))}])
            recorded["canonical_answer_id"]=result["recorded_answers"][0]["answer_id"]
    state.setdefault("goal_b_evidence", []).append(recorded)
    state.setdefault("history", []).append({"at_utc": _now(), "action": "goal_b_evidence_recorded", "evidence_id": recorded["evidence_id"], "request_id": request_id})
    _write(path, state)
    return recorded


def persist_economic_packet(case_directory: str | Path, packet: dict[str, Any]) -> dict[str, Any]:
    """Persiste un paquet Codex seulement après recalcul et vérification complète."""
    from energy_mvp.client_lifecycle import assert_workflow_action_allowed
    assert_workflow_action_allowed(case_directory,"economic_promotion")
    case = Path(case_directory)
    path = case / "investigation" / "economic_decision_state.json"
    state = _read(path)
    inputs = packet.get("economic_inputs", [])
    for item in inputs:
        validate_economic_input(item)
    assumptions = packet.get("scenario_assumptions", [])
    for item in assumptions:
        validate_scenario_assumption(item)
    value_sources = _value_source_index(inputs, assumptions)
    known_goal_a_refs = _case_provenance_ids(case)
    goal_b_evidence = _goal_b_evidence_index(state)
    source_metadata = _case_provenance_metadata(case)
    _validate_economic_input_sources(inputs, known_goal_a_refs, goal_b_evidence, source_metadata)
    actions = packet.get("candidate_actions", [])
    for action in actions:
        validate_candidate_action(action)
    action_ids = {item["action_id"] for item in actions}
    if len(action_ids) != len(actions):
        raise ValueError("Identifiants d'actions dupliqués.")
    constraints = packet.get("operational_constraints", [])
    for constraint in constraints:
        validate_constraint(constraint)
        if set(constraint["affected_action_ids"]) - action_ids:
            raise ValueError("Contrainte référence une action inconnue.")
    _validate_constraint_sources(constraints, known_goal_a_refs, goal_b_evidence, source_metadata)
    relationships = packet.get("relationships", [])
    for relationship in relationships:
        validate_relationship(relationship, action_ids)
    calculations = packet.get("scenario_calculations", {})
    if not isinstance(calculations, dict) or set(calculations) - action_ids:
        raise ValueError("Un calcul économique doit référencer une action candidate existante.")
    if "decision" in packet and "decisions" in packet:
        raise ValueError("Utilisez decision (compatibilité) ou decisions (multi-décision), pas les deux.")
    decisions = packet.get("decisions") if "decisions" in packet else ([packet["decision"]] if packet.get("decision") is not None else [])
    if not isinstance(decisions, list):
        raise ValueError("decisions doit être une liste de records de décision.")
    decision_ids: set[str] = set()
    action_decision_refs: set[str] = set()
    for decision in decisions:
        validate_decision(decision, action_ids)
        if decision["decision_id"] in decision_ids:
            raise ValueError("Identifiants de décision dupliqués.")
        decision_ids.add(decision["decision_id"])
        considered = set(decision.get("considered_action_ids", decision.get("selected_action_ids", decision.get("action_ids", []))))
        if action_decision_refs & considered:
            raise ValueError("Une action ne peut pas appartenir à deux décisions client concurrentes.")
        action_decision_refs |= considered
    real_goal_a_findings = _goal_a_findings(case)
    canonical_no_finding = _canonical_no_finding(case)
    no_finding_packet = (
        not real_goal_a_findings
        and canonical_no_finding is not None
        and packet.get("technical_finding_refs", []) == []
    )
    if no_finding_packet:
        if len(decisions) != 1 or decisions[0].get("decision") != "DO_NOTHING":
            raise ValueError("Un no-finding Goal A canonique n'autorise ici que DO_NOTHING.")
        if actions or calculations or decisions[0].get("selected_action_ids", decisions[0].get("action_ids", [])) or decisions[0].get("considered_action_ids", []):
            raise ValueError("DO_NOTHING après no-finding ne peut pas contenir actions, calculs ou actions considérées.")
    resolved_technical_refs = _resolve_technical_finding_refs(
        packet.get("technical_finding_refs", []), real_goal_a_findings, allow_canonical_no_finding=no_finding_packet,
    )
    technical_refs = {item["finding_id"] for item in resolved_technical_refs}
    if any(set(action["finding_ids"]) - technical_refs for action in actions):
        raise ValueError("Chaque action doit référencer un finding Goal A déclaré dans technical_finding_refs.")
    for action_id, calculation in calculations.items():
        action = next(item for item in actions if item["action_id"] == action_id)
        if not action.get("energy_effect_ref"):
            raise ValueError("Toute action avec économie d'énergie calculée doit identifier son baseline via energy_effect_ref.")
        energy_effect = calculation.get("reproducibility", {}).get("energy_effect", {})
        finding_refs = set(energy_effect.get("finding_refs", []))
        if not finding_refs or finding_refs - technical_refs or finding_refs - set(real_goal_a_findings):
            raise ValueError("Un effet énergétique persistant doit référencer au moins un finding technique du packet.")
        _validate_calculation_provenance(calculation, value_sources=value_sources, allowed_energy_refs=technical_refs | known_goal_a_refs)
        if calculation.get("effect_id") != action["energy_effect_ref"] or not calculation.get("baseline"):
            raise ValueError("Le calcul économique ne correspond pas à energy_effect_ref/baseline de l'action.")
    combined_effects = packet.get("combined_effects", {})
    if not isinstance(combined_effects, dict):
        raise ValueError("combined_effects doit être un objet indexé par référence.")
    for reference, entry in combined_effects.items():
        if not isinstance(reference, str) or not reference:
            raise ValueError("Référence d'effet combiné invalide.")
        if entry.get("effect_type") == "ENERGY":
            effect = entry.get("energy_effect", {})
            if set(effect.get("finding_refs", [])) - technical_refs or set(effect.get("finding_refs", [])) - real_goal_a_findings:
                raise ValueError("Un effet combiné énergie doit référencer des findings Goal A réels.")
        _combined_table(entry, value_sources)
    for relationship in relationships:
        if relationship["type"] == "OVERLAPPING" and relationship["combined_effect_ref"] not in combined_effects:
            raise ValueError("Un recouvrement persistant exige son combined_effect validé.")
    for decision in decisions:
        selected = set(decision.get("selected_action_ids", decision.get("action_ids", [])))
        hard_affected = {item["constraint_id"] for item in constraints if item["hard"] and item["material"] and set(item["affected_action_ids"]) & selected}
        assessments = {item["constraint_id"]: item for item in decision.get("constraint_assessments", [])}
        if hard_affected - set(assessments):
            raise ValueError("Une contrainte dure affectant une action sélectionnée ne peut pas être ignorée.")
        if decision["decision"] == "ACT_NOW" and any(assessments[item]["disposition"] == "BLOCKS" for item in hard_affected):
            raise ValueError("ACT_NOW est incompatible avec une contrainte dure déclarée bloquante.")
        if decision.get("blocking_constraint_ids") and set(decision["blocking_constraint_ids"]) - {item["constraint_id"] for item in constraints}:
            raise ValueError("Décision référence une contrainte inconnue.")
    request_payload = packet["economic_requests"] if "economic_requests" in packet else state.get("economic_requests", [])
    requests = build_economic_request_batch(request_payload)["requests"] if request_payload else []
    provenance_chain = _build_recommendation_provenance(decisions, actions, calculations, value_sources, constraints)
    state.update({"status": "economic_reasoning_recorded", "technical_finding_refs": resolved_technical_refs, "economic_inputs": inputs, "scenario_assumptions": assumptions, "operational_constraints": constraints, "candidate_actions": actions, "relationships": relationships, "combined_effects": combined_effects, "scenario_calculations": calculations, "decisions": decisions, "economic_requests": requests, "unresolved_blockers": packet.get("unresolved_blockers", state["unresolved_blockers"]), "recommendation_provenance": provenance_chain})
    state["history"].append({"at_utc": _now(), "action": "economic_packet_persisted", "action_ids": sorted(action_ids), "decision_ids": sorted(decision_ids), "decision_classes": [item["decision"] for item in decisions]})
    _write(path, state)
    return state
