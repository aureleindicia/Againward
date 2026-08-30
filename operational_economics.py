"""Contrats et calculs reproductibles pour les décisions opérationnelles-économiques.

Codex fournit les actions, contraintes, relations et décisions.  Ce module ne
les infère jamais: il les valide, les persiste et calcule leurs conséquences
chiffrées à partir d'hypothèses explicites.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from energy_mvp.tariffs import tariff_plan_from_dict


DECISIONS = {
    "ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "DEFER", "DO_NOTHING",
    "NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED",
    "INSUFFICIENT_FOR_ECONOMIC_DECISION",
}
RELATIONSHIP_TYPES = {
    "INDEPENDENT", "OVERLAPPING", "MUTUALLY_EXCLUSIVE", "DEPENDENT",
    "SEQUENTIAL", "ALTERNATIVE", "UNKNOWN",
}
INPUT_PROVENANCE = {
    "CLIENT_EXPLICIT", "DOCUMENT_EXTRACTED", "INFERRED_FROM_CLIENT_DATA",
    "EXTERNAL_ASSUMPTION", "SCENARIO_ASSUMPTION", "UNKNOWN",
}
CONSTRAINT_CATEGORIES = {
    "SAFETY", "QUALITY", "HYGIENE", "PRODUCTION", "THROUGHPUT", "STAFFING",
    "OPENING_HOURS", "MAINTENANCE_WINDOW", "DOWNTIME", "REDUNDANCY",
    "REGULATORY", "CUSTOMER_SERVICE", "SEASONALITY", "CASH", "PROCUREMENT",
    "SPACE", "NOISE", "TEMPERATURE", "PROCESS", "RELIABILITY", "OTHER",
}
CONFIDENCE_LEVELS = {"LOW", "MEDIUM", "HIGH", "NOT_CALIBRATED"}
SCENARIOS = ("LOW", "BASE", "HIGH")
REQUEST_TYPES = {
    "INFER_AUTOMATICALLY", "ASK_CLIENT", "REQUEST_EXISTING_DOCUMENT",
    "REQUEST_TECHNICAL_EVIDENCE", "OPTIONAL_FUTURE_INSTRUMENTATION", "REQUEST_QUOTE",
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


def validate_economic_input(payload: dict[str, Any]) -> None:
    """Valide une donnée économique; ne la devine jamais."""

    _require_text(payload, ("input_id", "kind", "provenance"), "Input économique")
    if payload["provenance"] not in INPUT_PROVENANCE:
        raise ValueError("Provenance économique inconnue.")
    status = payload.get("status", "KNOWN")
    if status not in {"KNOWN", "UNKNOWN", "SCENARIO"}:
        raise ValueError("Statut économique inconnu.")
    if status == "UNKNOWN":
        if payload.get("value") is not None:
            raise ValueError("Une donnée UNKNOWN ne porte pas de valeur inventée.")
        _require_text(payload, ("unknown_reason",), "Input économique UNKNOWN")
    else:
        _non_negative(payload.get("value"), "Valeur économique")
        _require_text(payload, ("unit",), "Input économique")
    provenance = payload.get("source")
    if status != "UNKNOWN" and not isinstance(provenance, dict):
        raise ValueError("Une donnée économique connue exige une provenance structurée.")
    if payload.get("confidence") and payload["confidence"] not in CONFIDENCE_LEVELS:
        raise ValueError("Niveau de confiance économique inconnu.")


def validate_energy_effect(payload: dict[str, Any]) -> None:
    _require_text(payload, ("effect_id", "basis", "baseline", "unit", "period"), "Effet énergie")
    if payload["unit"] not in {"kWh/year", "MWh/year"}:
        raise ValueError("Goal B attend un effet annualisé en kWh/year ou MWh/year.")
    if payload.get("basis") not in {
        "DIRECTLY_MEASURED_HISTORICAL_EXCESS", "COUNTERFACTUAL_ESTIMATE",
        "MODELED_REDUCTION", "ENGINEERING_ASSUMPTION", "SCENARIO_ESTIMATE",
    }:
        raise ValueError("Base d'effet énergétique inconnue.")
    scenarios = payload.get("scenarios")
    if not isinstance(scenarios, dict) or set(scenarios) != set(SCENARIOS):
        raise ValueError("L'effet énergétique exige les scénarios LOW, BASE et HIGH.")
    values = []
    for scenario in SCENARIOS:
        values.append(_non_negative(scenarios[scenario], f"Effet {scenario}"))
    if not values[0] <= values[1] <= values[2]:
        raise ValueError("Les scénarios énergie doivent respecter LOW ≤ BASE ≤ HIGH.")
    if not isinstance(payload.get("source_refs"), list) or not payload["source_refs"]:
        raise ValueError("Un effet énergie doit référencer une preuve ou une hypothèse explicite.")


def validate_constraint(payload: dict[str, Any]) -> None:
    _require_text(payload, ("constraint_id", "category", "description", "source_status"), "Contrainte")
    if payload["category"] not in CONSTRAINT_CATEGORIES:
        raise ValueError("Catégorie de contrainte inconnue.")
    if payload["source_status"] not in {"EXPLICIT", "INFERRED", "UNKNOWN"}:
        raise ValueError("Statut de source de contrainte inconnu.")
    if not isinstance(payload.get("hard"), bool) or not isinstance(payload.get("material"), bool):
        raise ValueError("Une contrainte doit préciser hard et material booléens.")
    affected = payload.get("affected_action_ids")
    if not isinstance(affected, list):
        raise ValueError("affected_action_ids doit être une liste.")
    if payload.get("source_status") != "UNKNOWN" and not payload.get("source_ref"):
        raise ValueError("Une contrainte connue doit citer sa provenance.")


def validate_candidate_action(payload: dict[str, Any]) -> None:
    """Valide une action proposée par Codex, sans choisir sa pertinence."""

    _require_text(payload, (
        "action_id", "title", "description", "action_type", "technical_rationale",
        "operational_rationale", "implementation_scope", "reversibility",
    ), "Action candidate")
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


def validate_decision(payload: dict[str, Any], action_ids: set[str]) -> None:
    """Valide la décision déjà raisonnée par Codex, sans règles de choix."""

    _require_text(payload, ("decision_id", "decision", "reason", "priority_reasoning"), "Décision")
    if payload["decision"] not in DECISIONS:
        raise ValueError("Décision économique inconnue.")
    selected = payload.get("action_ids", [])
    if not isinstance(selected, list) or set(selected) - action_ids:
        raise ValueError("Une décision référence une action inconnue.")
    if payload["decision"] in {"ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "DEFER"} and not selected:
        raise ValueError("Cette décision exige au moins une action explicitement choisie par Codex.")
    if payload["decision"] in {"DO_NOTHING", "NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED"} and selected:
        raise ValueError("Une décision de non-action ne doit pas masquer une action sélectionnée.")
    if payload.get("technical_confidence") not in CONFIDENCE_LEVELS or payload.get("economic_importance") not in CONFIDENCE_LEVELS:
        raise ValueError("Confiance technique et importance économique doivent être distinctes.")
    if payload["decision"] == "INVESTIGATE_FIRST":
        evidence = payload.get("evidence_acquisition")
        if not isinstance(evidence, dict):
            raise ValueError("INVESTIGATE_FIRST exige une action d'acquisition de preuve.")
        _require_text(evidence, ("what_it_resolves", "decision_that_can_change", "cost_or_burden", "why_worth_it"), "Acquisition de preuve")
    if payload["decision"] == "OPERATIONALLY_NOT_JUSTIFIED" and not payload.get("blocking_constraint_ids"):
        raise ValueError("Une non-justification opérationnelle exige une contrainte explicitement citée.")
    assessments = payload.get("constraint_assessments", [])
    if not isinstance(assessments, list):
        raise ValueError("constraint_assessments doit être une liste.")
    for assessment in assessments:
        _require_text(assessment, ("constraint_id", "disposition", "rationale"), "Évaluation de contrainte")
        if assessment["disposition"] not in {"BLOCKS", "MITIGATED", "NOT_APPLICABLE"}:
            raise ValueError("Disposition de contrainte inconnue.")


def _as_kwh(value: float, unit: str) -> float:
    if unit == "kWh/year":
        return value
    if unit == "MWh/year":
        return value * 1000
    raise ValueError("Unité d'énergie annuelle inconnue.")


def calculate_economic_scenarios(
    energy_effect: dict[str, Any],
    *,
    tariff_per_kwh: dict[str, float] | None,
    intervention_cost: dict[str, float] | None = None,
    recurring_cost: dict[str, float] | None = None,
    other_annual_benefit: dict[str, float] | None = None,
    currency: str = "EUR",
) -> dict[str, Any]:
    """Calcule un tableau de scénarios; une absence de tarif reste inconnue."""

    validate_energy_effect(energy_effect)
    for label, values in (("tariff_per_kwh", tariff_per_kwh), ("intervention_cost", intervention_cost), ("recurring_cost", recurring_cost), ("other_annual_benefit", other_annual_benefit)):
        if values is not None:
            if set(values) != set(SCENARIOS):
                raise ValueError(f"{label} exige LOW, BASE et HIGH.")
            for scenario in SCENARIOS:
                _non_negative(values[scenario], f"{label}/{scenario}")
    output: dict[str, Any] = {"schema_version": 1, "currency": currency, "effect_id": energy_effect["effect_id"], "baseline": energy_effect["baseline"], "scenarios": {}, "calculation_notes": []}
    if tariff_per_kwh is None:
        output["calculation_notes"].append("Tarif inconnu : bénéfice monétaire et payback non calculés.")
    for scenario in SCENARIOS:
        energy_kwh = _as_kwh(float(energy_effect["scenarios"][scenario]), energy_effect["unit"])
        tariff = None if tariff_per_kwh is None else float(tariff_per_kwh[scenario])
        gross = None if tariff is None else energy_kwh * tariff
        recurring = 0.0 if recurring_cost is None else float(recurring_cost[scenario])
        other = 0.0 if other_annual_benefit is None else float(other_annual_benefit[scenario])
        net = None if gross is None else gross + other - recurring
        cost = None if intervention_cost is None else float(intervention_cost[scenario])
        payback = None if net is None or cost is None or net <= 0 else cost / net
        output["scenarios"][scenario] = {
            "annual_energy_saving_kwh": energy_kwh,
            "tariff_per_kwh": tariff,
            "gross_annual_energy_cost_avoided": gross,
            "incremental_recurring_cost": recurring if recurring_cost is not None else None,
            "other_supported_annual_benefit": other if other_annual_benefit is not None else None,
            "net_annual_benefit": net,
            "intervention_cost": cost,
            "simple_payback_years": payback,
            "payback_status": "meaningful" if payback is not None else "not_meaningful_or_unknown",
        }
    return output


def calculate_time_aligned_savings(
    timed_savings: Iterable[dict[str, Any]], *, price_for_timestamp: callable
) -> dict[str, Any]:
    """Somme des économies si chaque kWh évité est associé à une période tarifaire connue."""

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


def calculate_time_aligned_savings_with_tariff_plan(
    timed_savings: Iterable[dict[str, Any]], tariff_payload: dict[str, Any]
) -> dict[str, Any]:
    """Applique un plan tarifaire existant aux kWh évités horodatés.

    Sans série temporelle d'économies, cette fonction ne doit pas être utilisée :
    le calcul de scénarios reste alors explicitement une approximation tarifaire.
    """

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


def aggregate_declared_portfolio(
    selected_action_ids: list[str],
    scenario_tables: dict[str, dict[str, Any]],
    relationships: list[dict[str, Any]],
    *,
    combined_effects: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    """Agrège seulement un portefeuille déclaré; refuse les recouvrements non résolus."""

    selected = set(selected_action_ids)
    if not selected or selected - set(scenario_tables):
        raise ValueError("Le portefeuille doit sélectionner des actions avec scénarios connus.")
    relationship_by_pair = {frozenset((item["action_a"], item["action_b"])): item for item in relationships}
    base = {scenario: 0.0 for scenario in SCENARIOS}
    for action_id in selected:
        for scenario in SCENARIOS:
            benefit = scenario_tables[action_id]["scenarios"][scenario]["net_annual_benefit"]
            if benefit is None:
                raise ValueError("Un portefeuille ne somme pas un bénéfice annuel inconnu.")
            base[scenario] += float(benefit)
    adjustments = {scenario: 0.0 for scenario in SCENARIOS}
    for left in sorted(selected):
        for right in sorted(selected):
            if left >= right:
                continue
            relation = relationship_by_pair.get(frozenset((left, right)))
            if relation is None or relation["type"] == "INDEPENDENT":
                continue
            if relation["type"] in {"MUTUALLY_EXCLUSIVE", "ALTERNATIVE"}:
                raise ValueError("Des actions mutuellement exclusives/alternatives ne peuvent pas être sommées.")
            if relation["type"] == "OVERLAPPING":
                reference = relation.get("combined_effect_ref")
                if not reference or not combined_effects or reference not in combined_effects:
                    raise ValueError("Recouvrement sans effet combiné déclaré: aucune somme n'est autorisée.")
                for scenario in SCENARIOS:
                    combined = _non_negative(combined_effects[reference].get(scenario), f"Effet combiné/{scenario}")
                    separate = scenario_tables[left]["scenarios"][scenario]["net_annual_benefit"] + scenario_tables[right]["scenarios"][scenario]["net_annual_benefit"]
                    adjustments[scenario] += float(combined) - float(separate)
            elif relation["type"] in {"DEPENDENT", "SEQUENTIAL", "UNKNOWN"}:
                raise ValueError("Relation dépendante, séquentielle ou inconnue : fournir un modèle combiné explicite.")
    return {"selected_action_ids": sorted(selected), "net_annual_benefit": {scenario: base[scenario] + adjustments[scenario] for scenario in SCENARIOS}, "relationship_adjustments": adjustments, "deterministic_decision": None}


def initialize_economic_state(case_directory: str | Path) -> dict[str, Any]:
    """Ajoute un état Goal B adjacent à Goal A sans modifier ses artefacts gelés."""

    case = Path(case_directory)
    if not (case / "case_manifest.json").is_file():
        raise ValueError("Le dossier doit être un cas Goal A valide.")
    path = case / "investigation" / "economic_decision_state.json"
    if path.exists():
        raise FileExistsError("L'état économique existe déjà et ne sera pas réinitialisé.")
    canonical = _read(case / "derived" / "canonical_case.json")
    state = {
        "schema_version": 1, "created_at_utc": _now(), "status": "awaiting_codex_economic_reasoning",
        "technical_finding_refs": [], "economic_inputs": [], "operational_constraints": [], "candidate_actions": [],
        "relationships": [], "scenario_calculations": {}, "decisions": [], "economic_requests": [],
        "unresolved_blockers": canonical.get("unresolved_material_ambiguities", []),
        "provenance_context": {"canonical_case": "derived/canonical_case.json", "dataset_provenance": "evidence/dataset_provenance.json"},
        "history": [{"at_utc": _now(), "action": "economic_state_initialized"}],
        "ground_truth_used": False, "deterministic_recommendation_engine": False,
    }
    _write(path, state)
    return state


def persist_economic_packet(case_directory: str | Path, packet: dict[str, Any]) -> dict[str, Any]:
    """Persiste un paquet composé par Codex après validation de cohérence des contrats."""

    case = Path(case_directory)
    path = case / "investigation" / "economic_decision_state.json"
    state = _read(path)
    for item in packet.get("economic_inputs", []):
        validate_economic_input(item)
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
    relationships = packet.get("relationships", [])
    for relationship in relationships:
        validate_relationship(relationship, action_ids)
    decision = packet.get("decision")
    if decision is not None:
        validate_decision(decision, action_ids)
        hard_affected = {
            item["constraint_id"] for item in constraints
            if item["hard"] and item["material"] and set(item["affected_action_ids"]) & set(decision.get("action_ids", []))
        }
        assessments = {item["constraint_id"]: item for item in decision.get("constraint_assessments", [])}
        if hard_affected - set(assessments):
            raise ValueError("Une contrainte dure affectant une action sélectionnée ne peut pas être ignorée.")
        if decision["decision"] == "ACT_NOW" and any(
            assessments[item]["disposition"] == "BLOCKS" for item in hard_affected
        ):
            raise ValueError("ACT_NOW est incompatible avec une contrainte dure déclarée bloquante.")
        if decision.get("blocking_constraint_ids"):
            valid_constraints = {item["constraint_id"] for item in constraints}
            if set(decision["blocking_constraint_ids"]) - valid_constraints:
                raise ValueError("Décision référence une contrainte inconnue.")
    state.update({
        "status": "economic_reasoning_recorded", "technical_finding_refs": packet.get("technical_finding_refs", []),
        "economic_inputs": packet.get("economic_inputs", []), "operational_constraints": constraints,
        "candidate_actions": actions, "relationships": relationships,
        "scenario_calculations": packet.get("scenario_calculations", {}), "decisions": [decision] if decision else [],
        "economic_requests": packet.get("economic_requests", []), "unresolved_blockers": packet.get("unresolved_blockers", state["unresolved_blockers"]),
    })
    state["history"].append({"at_utc": _now(), "action": "economic_packet_persisted", "action_ids": sorted(action_ids), "decision": decision.get("decision") if decision else None})
    _write(path, state)
    return state


def economic_handoff(case_directory: str | Path) -> dict[str, Any]:
    """Produit un résumé compact pour Codex, sans décider de la recommandation."""

    case = Path(case_directory)
    state = _read(case / "investigation" / "economic_decision_state.json")
    canonical = _read(case / "derived" / "canonical_case.json")
    payload = {
        "schema_version": 1, "purpose": "Contexte pour raisonnement opérationnel-économique Codex, pas une recommandation automatique.",
        "technical_findings": state["technical_finding_refs"], "economic_inputs": state["economic_inputs"],
        "constraints": state["operational_constraints"], "unresolved_blockers": state["unresolved_blockers"],
        "available_context_roles": canonical.get("evidence_by_role", {}),
        "codex_must_decide": ["candidate actions", "material constraints", "relationships", "evidence worth buying", "decision", "priority", "validation"],
        "python_can_calculate": ["scenario table", "time-aligned tariff impact", "payback when meaningful", "declared portfolio arithmetic"],
    }
    _write(case / "investigation" / "economic_handoff.json", payload)
    return payload


def build_economic_request_batch(requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Valide un batch faible-friction rédigé par Codex; ne formule aucune question."""

    if len(requests) > 3:
        raise ValueError("Un batch économique normal est limité à trois demandes.")
    normalized = []
    for index, request in enumerate(requests, start=1):
        _require_text(request, ("client_question", "internal_reason", "target_role", "decision_impact", "expected_effort"), "Demande économique")
        if request.get("request_type") not in REQUEST_TYPES - {"INFER_AUTOMATICALLY"}:
            raise ValueError("Type de demande économique invalide.")
        if len(request["client_question"].strip()) < 12:
            raise ValueError("Demande économique trop vague.")
        normalized.append({**request, "request_id": request.get("request_id", f"ECO-REQ-{index:02d}"), "analysis_can_continue_without_answer": request.get("importance", "NON_BLOCKING") != "BLOCKING"})
    return {"schema_version": 1, "requests": normalized, "default_question_count": 0, "generated_by": "Codex; Python validated schema only"}
