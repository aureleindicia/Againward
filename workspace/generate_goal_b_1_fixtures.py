"""Crée les fixtures compactes B-A → B-O pour tester les contrats B.1."""
from __future__ import annotations

import json
from pathlib import Path


def _action(identifier: str, effect: str = "EFF-01", *, reversibility: str = "PARTIALLY_REVERSIBLE") -> dict:
    return {"action_id": identifier, "finding_ids": ["FIND-01"], "title": f"Action {identifier}", "description": "Option candidate explicitement formulée pour fixture.", "action_type": "maintenance", "technical_rationale": "Finding technique lié.", "operational_rationale": "Contraintes documentées dans la fixture.", "implementation_scope": "Équipement concerné.", "requires_professional_validation": True, "reversibility": reversibility, "energy_effect_ref": effect, "validation_plan": {"metric": "kWh normalisés", "expected_direction": "baisse", "comparison_window": "avant/après comparable", "confounders": "activité", "minimum_evidence": "effet récurrent"}}


def _effect(identifier: str = "EFF-01", baseline: str = "baseline courant") -> dict:
    return {"effect_id": identifier, "basis": "COUNTERFACTUAL_ESTIMATE", "baseline": baseline, "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": 100, "BASE": 200, "HIGH": 300}, "source_refs": ["FIND-01"]}


def _input(identifier: str, kind: str, value: float, unit: str) -> dict:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "provenance": "DOCUMENT_EXTRACTED", "source": {"artifact_id": "ART-01"}, "confidence": "MEDIUM"}


def _decision(kind: str, selected: list[str], considered: list[str] | None = None) -> dict:
    output = {"decision_id": f"DEC-{kind}", "decision": kind, "selected_action_ids": selected, "considered_action_ids": selected if considered is None else considered, "reason": "Raisonnement de fixture fourni à Codex; aucune règle de production.", "priority_reasoning": "Comparaison qualitative explicite.", "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM"}
    if kind == "INVESTIGATE_FIRST":
        output["evidence_acquisition"] = {"what_it_resolves": "cause concurrente", "decision_that_can_change": "agir ou non", "cost_or_burden": "test faible coût", "why_worth_it": "évite une action irréversible"}
    return output


def generate(path: str | Path = "examples/goal_b_1_fixtures.json") -> Path:
    path = Path(path)
    if path.exists():
        raise FileExistsError("Les fixtures B.1 existent déjà; elles ne seront pas écrasées.")
    fixtures = []
    specs = [
        ("B-A", "ACT_NOW", "obvious_low_cost", []),
        ("B-B", "INVESTIGATE_FIRST", "uncertain_expensive", []),
        ("B-C", "NO_ECONOMIC_CASE", "trivial_saving", []),
        ("B-D", "OPERATIONALLY_NOT_JUSTIFIED", "production_schedule_blocks", ["constraint"]),
        ("B-E", "DO_NOTHING", "mandatory_safety_load", ["constraint"]),
        ("B-F", "INVESTIGATE_FIRST", "overlap", ["overlap"]),
        ("B-G", "DEFER", "mutually_exclusive", ["exclusive"]),
        ("B-H", "DEFER", "planned_shutdown", ["constraint"]),
        ("B-I", "INSUFFICIENT_FOR_ECONOMIC_DECISION", "tariff_uncertainty", ["request"]),
        ("B-J", "DO_NOTHING", "normal_operation", []),
        ("B-K", "INVESTIGATE_FIRST", "reversible_experiment", ["reversible"]),
        ("B-L", "ACT_NOW", "production_adjusted_baseline", ["production_baseline"]),
        ("B-M", "NO_ECONOMIC_CASE", "recurring_cost", ["recurring"]),
        ("B-N", "NO_ECONOMIC_CASE", "negative_economics", ["negative"]),
        ("B-O", "INVESTIGATE_FIRST", "sparse_sme", ["sparse"]),
    ]
    for fixture_id, decision_kind, family, flags in specs:
        actions = [_action("ACT-01", reversibility="REVERSIBLE" if "reversible" in flags else "PARTIALLY_REVERSIBLE")]
        constraints: list[dict] = []
        decision = _decision(decision_kind, ["ACT-01"] if decision_kind not in {"DO_NOTHING", "NO_ECONOMIC_CASE", "OPERATIONALLY_NOT_JUSTIFIED", "INSUFFICIENT_FOR_ECONOMIC_DECISION"} else [], ["ACT-01"])
        if decision_kind == "OPERATIONALLY_NOT_JUSTIFIED":
            decision["blocking_constraint_ids"] = ["CONS-01"]
        if "constraint" in flags:
            constraints = [{"constraint_id": "CONS-01", "category": "HYGIENE" if fixture_id == "B-E" else "PRODUCTION", "description": "Contrainte opérationnelle explicite.", "source_status": "EXPLICIT", "source_ref": "ART-01", "hard": fixture_id in {"B-D", "B-E"}, "material": True, "affected_action_ids": ["ACT-01"]}]
        if "overlap" in flags or "exclusive" in flags:
            actions.append(_action("ACT-02", "EFF-02"))
        relationships: list[dict] = []
        if "overlap" in flags:
            relationships = [{"relationship_id": "REL-01", "type": "OVERLAPPING", "action_a": "ACT-01", "action_b": "ACT-02", "rationale": "Même excès physique.", "combined_effect_ref": "COMB-01"}]
            decision["considered_action_ids"] = ["ACT-01", "ACT-02"]
        if "exclusive" in flags:
            relationships = [{"relationship_id": "REL-01", "type": "MUTUALLY_EXCLUSIVE", "action_a": "ACT-01", "action_b": "ACT-02", "rationale": "Réparer ou remplacer."}]
            decision["considered_action_ids"] = ["ACT-01", "ACT-02"]
        request = []
        if "request" in flags:
            request = [{"request_type": "REQUEST_EXISTING_DOCUMENT", "client_question": "Pouvez-vous transmettre votre dernière facture d'électricité si elle est disponible ?", "internal_reason": "Le tarif peut modifier la décision.", "target_role": "dirigeant", "decision_impact": "Établir si le projet est matériel.", "expected_effort": "Envoyer un document existant.", "importance": "BLOCKING"}]
        fixture = {"fixture_id": fixture_id, "technical_finding": {"finding_id": "FIND-01", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN" if decision_kind == "INVESTIGATE_FIRST" else "CAUSE_PROBABLE", "uncertainty": "cause ou économie à valider selon le scénario", "provenance": ["ART-01"]}, "family": family, "energy_effects": [_effect(), _effect("EFF-02")][0:len(actions)], "economic_inputs": [_input("ECON-TARIFF", "electricity_tariff", .2, "EUR/kWh"), _input("ECON-CAPEX", "capex", 300, "EUR"), _input("ECON-RECUR", "recurring_cost", 20, "EUR/year")], "candidate_actions": actions, "operational_constraints": constraints, "relationships": relationships, "economic_requests": request, "decision": decision, "expected_agent_decision": decision_kind, "expected_contract": {"portfolio_behavior": "REFUSE_UNRESOLVED_OVERLAP" if "overlap" in flags else "REFUSE_MUTUALLY_EXCLUSIVE" if "exclusive" in flags else "NOT_AGGREGATED", "requires_normalized_baseline": "production_baseline" in flags, "sparse_information": "sparse" in flags, "recurring_cost_must_be_net": "recurring" in flags or "negative" in flags}}
        fixtures.append(fixture)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"schema_version": 1, "purpose": "Fixtures de contrat B.1, sans règles de recommandation en production.", "fixtures": fixtures}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    print(generate())
