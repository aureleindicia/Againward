"""E2E compact Goal B.4 : demande → preuve native → reprise économique."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client_intake_pipeline import create_client_case, ingest_client_drop, record_structured_findings
from operational_economics import (
    calculate_economic_scenarios,
    economic_handoff,
    initialize_economic_state,
    persist_economic_packet,
    publish_economic_request_batch,
    record_goal_b_evidence,
)
from energy_mvp.client_lifecycle import complete_resume, record_existing_data_exhaustion


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _tariff_input(source_ref: str) -> dict:
    return {
        "input_id": "TAR-CLIENT-01", "kind": "electricity_tariff", "value": 0.20,
        "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh",
        "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN",
        "source": {"source_refs": [source_ref]}, "confidence": "MEDIUM",
    }


def _action() -> dict:
    return {
        "action_id": "ACT-INSPECT-01", "finding_ids": ["FIND-EXCESS-01"],
        "title": "Inspection ciblée", "description": "Option formulée par Codex.",
        "action_type": "diagnostic", "technical_rationale": "Cause concurrente non tranchée.",
        "operational_rationale": "À réaliser hors production.",
        "implementation_scope": "Équipement associé au régime pré-ouverture.",
        "requires_professional_validation": True, "reversibility": "REVERSIBLE",
        "energy_effect_ref": "EFF-EXCESS-01",
        "validation_plan": {
            "metric": "kWh pré-ouverture", "expected_direction": "baisse",
            "comparison_window": "quatre semaines", "confounders": "production et horaires",
            "minimum_evidence": "baisse récurrente à régime comparable",
        },
    }


def _effect() -> dict:
    return {
        "effect_id": "EFF-EXCESS-01", "basis": "COUNTERFACTUAL_ESTIMATE",
        "baseline": "créneau pré-ouverture comparable", "unit": "kWh/year", "period": "annual",
        "scenarios": {"LOW": 1200, "BASE": 1800, "HIGH": 2400},
        "finding_refs": ["FIND-EXCESS-01"], "source_refs": ["DS-001-01"],
    }


def _calculation(capex: float | None, capex_id: str | None) -> dict:
    refs = {
        "energy_effect": {scenario: ["FIND-EXCESS-01"] for scenario in ("LOW", "BASE", "HIGH")},
        "tariff_per_kwh": {scenario: ["TAR-CLIENT-01"] for scenario in ("LOW", "BASE", "HIGH")},
    }
    if capex_id:
        refs["intervention_cost"] = {scenario: [capex_id] for scenario in ("LOW", "BASE", "HIGH")}
    return calculate_economic_scenarios(
        _effect(), tariff_per_kwh={scenario: .20 for scenario in ("LOW", "BASE", "HIGH")},
        intervention_cost=None if capex is None else {scenario: capex for scenario in ("LOW", "BASE", "HIGH")},
        input_references=refs,
    )


def _decision(constraint: bool = False) -> dict:
    decision = {
        "decision_id": "DEC-B4-01", "decision": "INVESTIGATE_FIRST",
        "selected_action_ids": ["ACT-INSPECT-01"], "considered_action_ids": ["ACT-INSPECT-01"],
        "reason": "La cause reste indéterminée; un devis et la fenêtre d'arrêt changent la décision.",
        "priority_reasoning": "Question faible effort avant intervention.",
        "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM",
        "evidence_acquisition": {
            "what_it_resolves": "coût et faisabilité de l'inspection",
            "decision_that_can_change": "agir maintenant ou différer",
            "cost_or_burden": "devis et réponse simple", "why_worth_it": "évite une intervention non planifiable",
        },
    }
    if constraint:
        decision["constraint_assessments"] = [{
            "constraint_id": "CONS-PROD-01", "disposition": "MITIGATED",
            "rationale": "Intervention planifiée hors période de production.",
        }]
    return decision


def generate(root: str | Path = "examples") -> Path:
    root = Path(root)
    raw, case_root = root / "goal_b_4_e2e_input", root / "goal_b_4_e2e_case"
    if raw.exists() or case_root.exists():
        raise FileExistsError("Les fixtures B.4 existent déjà; elles ne seront pas écrasées.")
    raw.mkdir(parents=True)
    (raw / "energy.csv").write_text("timestamp,energy_kwh,production\n2026-07-01 05:00,5.0,0\n2026-07-01 06:30,2.0,10\n", encoding="utf-8")
    (raw / "tariff.txt").write_text("Tarif moyen électricité : 0,20 EUR/kWh.\n", encoding="utf-8")
    create_client_case("b4_artisan", root=case_root, synthetic=True)
    case = case_root / "b4_artisan"
    ingest_client_drop(raw, case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    artifact_ids = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    record_structured_findings(case, [{
        "finding_id": "FIND-EXCESS-01", "observation": "Excès pré-ouverture récurrent observé.",
        "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "confidence": "MEDIUM",
        "possible_explanations": ["dérive", "préparation légitime"],
        "provenance": ["evidence/dataset_provenance.json"],
        "recommended_next_analytical_step": "Tester l'état réel pendant le créneau.",
    }])
    pre = economic_handoff(case)
    _write(case / "investigation" / "codex_economic_reasoning_contract.json", {
        "input_handoff_ref": pre["artifact"], "codex_decides": ["action", "questions", "constraint", "decision"],
        "python_calculates_and_validates": True, "not_a_deterministic_recommendation": True,
    })
    initialize_economic_state(case)
    record_existing_data_exhaustion(case, analysis_inventory_ref="derived/canonical_case.json", reviewed_sources=["evidence/intake_inventory.json", "investigation/structured_findings.json"])
    requests = [
        {"request_id": "ECO-REQ-QUOTE", "request_type": "REQUEST_QUOTE", "client_question": "Pouvez-vous transmettre le devis de l'inspection ciblée ?", "internal_reason": "Le coût conditionne la priorité économique.", "target_role": "dirigeant", "decision_impact": "Comparer coût et bénéfice.", "expected_effort": "Envoyer le devis."},
        {"request_id": "ECO-REQ-DOWNTIME", "request_type": "ASK_CLIENT", "client_question": "La machine peut-elle être arrêtée pendant les heures de production ?", "internal_reason": "La fenêtre d'arrêt conditionne la faisabilité.", "target_role": "responsable site", "decision_impact": "Planifier ou différer.", "expected_effort": "Réponse simple."},
    ]
    requests[0].update({"related_hypothesis_ids": ["H-CAPEX"], "hypotheses_distinguished": ["coût compatible", "coût incompatible"], "plausible_answers": [{"answer_id": "LOW", "label": "Coût compatible", "decision_effects": ["Intervention économiquement plausible."]}, {"answer_id": "HIGH", "label": "Coût trop élevé", "decision_effects": ["Intervention à différer."]}], "decision_impact_dimensions": ["economic_materiality"], "effort": 1, "availability": .9, "reliability": .9, "expected_source_type": "EXISTING_DOCUMENT", "importance": "BLOCKING"})
    requests[1].update({"related_hypothesis_ids": ["H-DOWNTIME"], "hypotheses_distinguished": ["arrêt possible", "arrêt impossible"], "plausible_answers": [{"answer_id": "YES", "label": "Arrêt possible", "decision_effects": ["Planifier pendant la production."]}, {"answer_id": "NO", "label": "Arrêt impossible", "decision_effects": ["Planifier hors production."]}], "decision_impact_dimensions": ["field_action"], "effort": 1, "availability": .9, "reliability": .7, "importance": "BLOCKING"})
    initial_packet = {
        "technical_finding_refs": [{"finding_id": "FIND-EXCESS-01"}], "economic_inputs": [_tariff_input(artifact_ids["tariff.txt"])],
        "scenario_assumptions": [], "candidate_actions": [_action()], "operational_constraints": [],
        "relationships": [], "combined_effects": {}, "scenario_calculations": {"ACT-INSPECT-01": _calculation(None, None)},
        "economic_requests": [], "decision": _decision(),
    }
    persist_economic_packet(case, initial_packet)
    publish_economic_request_batch(case, requests)
    quote = record_goal_b_evidence(case, {
        "evidence_id": "GBE-QUOTE-01", "evidence_type": "GOAL_B_CLIENT_RESPONSE",
        "content": {"response_text": "Le devis est de 450 EUR."},
        "structured_value": {"value": 450, "unit": "EUR", "currency": "EUR", "period": "one_off"},
        "request_id": "ECO-REQ-QUOTE",
    })
    downtime = record_goal_b_evidence(case, {
        "evidence_id": "GBE-DOWNTIME-01", "evidence_type": "GOAL_B_CLIENT_RESPONSE",
        "content": {"response_text": "La machine ne peut pas être arrêtée pendant la production."},
        "request_id": "ECO-REQ-DOWNTIME",
    })
    resume = economic_handoff(case)
    capex = {
        "input_id": "CAP-QUOTE-01", "kind": "inspection_quote", "value": 450,
        "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "CLIENT_EXPLICIT",
        "status": "KNOWN", "source": {"goal_b_evidence_refs": [quote["evidence_id"]]}, "confidence": "HIGH",
    }
    updated_packet = {
        "technical_finding_refs": [{"finding_id": "FIND-EXCESS-01"}],
        "economic_inputs": [_tariff_input(artifact_ids["tariff.txt"]), capex], "scenario_assumptions": [],
        "candidate_actions": [_action()],
        "operational_constraints": [{
            "constraint_id": "CONS-PROD-01", "category": "PRODUCTION",
            "description": "Pas d'arrêt pendant la production.", "source_status": "EXPLICIT",
            "goal_b_evidence_refs": [downtime["evidence_id"]], "hard": True, "material": True,
            "affected_action_ids": ["ACT-INSPECT-01"],
        }],
        "relationships": [], "combined_effects": {},
        "scenario_calculations": {"ACT-INSPECT-01": _calculation(450, "CAP-QUOTE-01")},
        "decision": _decision(constraint=True),
    }
    final_state = persist_economic_packet(case, updated_packet)
    _write(case / "investigation" / "goal_b_4_e2e_trace.json", {
        "workflow": ["Goal A evidence", "pre-reasoning handoff", "Codex reasoning contract", "economic request", "client response", "persistent Goal B evidence", "resume handoff", "deterministic calculations", "persisted Goal B state"],
        "pre_handoff": pre["artifact"], "resume_handoff": resume["artifact"],
        "evidence_ids": [quote["evidence_id"], downtime["evidence_id"]],
        "economic_input_ref": "CAP-QUOTE-01", "constraint_ref": "CONS-PROD-01",
        "final_decision": final_state["decisions"][0]["decision"],
    })
    resume_dimensions = {key: "reassessed" for key in ("evidence_level", "asset_attribution", "alternatives", "confidence", "economic_materiality", "investigation_priority", "field_action", "false_conclusion_risk")}
    complete_resume(case, recalculation_refs=["investigation/economic_decision_state.json"], adversarial_review_ref="investigation/goal_b_4_e2e_trace.json", before_after=[{"hypothesis_id": "H-CAPEX", "before": "coût inconnu", "after": "devis 450 EUR", "decision_dimensions": resume_dimensions}, {"hypothesis_id": "H-DOWNTIME", "before": "fenêtre inconnue", "after": "arrêt hors production requis", "decision_dimensions": resume_dimensions}])
    return case


if __name__ == "__main__":
    print(generate())
