"""Génère un E2E B.2 avec handoffs pré-raisonnement et reprise séparés."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from client_intake_pipeline import create_client_case, ingest_client_drop, record_structured_findings
from operational_economics import calculate_economic_scenarios, economic_handoff, initialize_economic_state, persist_economic_packet


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _input(identifier: str, kind: str, value: float, unit: str, period: str, source_refs: list[str]) -> dict:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": source_refs}, "confidence": "MEDIUM"}


def _assumption(identifier: str, value: float, description: str) -> dict:
    return {"assumption_id": identifier, "description": description, "value": value, "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "tariff sensitivity"}}


def generate(root: str | Path = "examples") -> Path:
    root = Path(root)
    raw, case_root = root / "goal_b_2_e2e_input", root / "goal_b_2_e2e_case"
    if raw.exists() or case_root.exists():
        raise FileExistsError("Les fixtures B.2 existent déjà; elles ne seront pas écrasées.")
    raw.mkdir(parents=True)
    (raw / "energy_interval_export.csv").write_text("timestamp,energy_kwh,production\n2026-06-01 05:00,5.0,0\n2026-06-01 05:30,5.2,0\n2026-06-01 06:00,2.0,0\n2026-06-01 06:30,2.2,12\n2026-06-02 05:00,5.1,0\n2026-06-02 05:30,5.0,0\n2026-06-02 06:00,2.1,0\n2026-06-02 06:30,2.2,11\n", encoding="utf-8")
    (raw / "production_approx.csv").write_text("date,production\n2026-06-01,12\n2026-06-02,11\n", encoding="utf-8")
    (raw / "planning_ouverture.txt").write_text("Préparation habituelle à 06:30; livraison clients à partir de 07:30.\n", encoding="utf-8")
    (raw / "maintenance_note.txt").write_text("Le technicien a signalé une dérive possible, sans diagnostic confirmé.\n", encoding="utf-8")
    (raw / "facture_tarif.txt").write_text("Contrat électricité : 0,20 EUR/kWh moyen sur la période.\n", encoding="utf-8")
    (raw / "supplier_quote.txt").write_text("Inspection : 300 EUR; remplacement indicatif : 12 000 EUR.\n", encoding="utf-8")
    (raw / "meter_without_unit.csv").write_text("timestamp,Energy\n2026-06-01 05:00,50\n2026-06-01 05:30,51\n", encoding="utf-8")
    (raw / "logo_photo.txt").write_text("matériel marketing sans pertinence analytique\n", encoding="utf-8")
    create_client_case("artisan_sme", root=case_root)
    case = case_root / "artisan_sme"
    ingest_client_drop(raw, case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    artifact_ids = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    record_structured_findings(case, [{"finding_id": "FIND-EXCESS-01", "observation": "Excès pré-ouverture récurrent dans les données synthétiques.", "time_context_window": "05:00–06:00", "quantitative_evidence": {"excess_energy_kwh": 6.0, "source": "DS-001"}, "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "possible_explanations": ["dérive technique", "préparation opérationnelle"], "current_leading_explanation": None, "counter_explanations": ["horaire exceptionnel"], "missing_material_information": ["statut de préparation"], "client_question": None, "technical_evidence_request": "Inspection pendant visite prévue.", "confidence": "MEDIUM", "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Comparer après inspection.", "predictive_degradation_note": None}])
    pre = economic_handoff(case)
    _write(case / "investigation" / "codex_economic_reasoning_contract.json", {"schema_version": 2, "input_handoff_ref": pre["artifact"], "handoff_phase": "pre_reasoning", "codex_responsibilities": ["choose actions, assumptions, constraints, relationships and decision"], "python_responsibilities": ["calculate and validate quantitative provenance"], "not_a_deterministic_recommendation": True})
    initialize_economic_state(case)
    effect = {"effect_id": "EFF-EXCESS-01", "basis": "COUNTERFACTUAL_ESTIMATE", "baseline": "créneau pré-ouverture de référence", "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": 4000, "BASE": 7000, "HIGH": 10000}, "finding_refs": ["FIND-EXCESS-01"], "source_refs": ["DS-001-01"]}
    refs = {"energy_effect": {s: ["FIND-EXCESS-01"] for s in ("LOW", "BASE", "HIGH")}, "tariff_per_kwh": {"LOW": ["TAR-LOW"], "BASE": ["TAR-BASE"], "HIGH": ["TAR-HIGH"]}, "intervention_cost": {"LOW": ["CAP-LOW"], "BASE": ["CAP-INSPECT"], "HIGH": ["CAP-HIGH"]}}
    calc = calculate_economic_scenarios(effect, tariff_per_kwh={"LOW": .18, "BASE": .20, "HIGH": .23}, intervention_cost={"LOW": 250, "BASE": 300, "HIGH": 400}, input_references=refs)
    action = {"action_id": "ACT-INSPECT-01", "finding_ids": ["FIND-EXCESS-01"], "title": "Inspection ciblée pendant maintenance", "description": "Option formulée par Codex pour cette fixture.", "action_type": "diagnostic", "technical_rationale": "Excès confirmé, cause concurrente.", "operational_rationale": "Préserver la préparation du matin.", "implementation_scope": "Système pré-ouverture.", "requires_professional_validation": True, "reversibility": "REVERSIBLE", "energy_effect_ref": "EFF-EXCESS-01", "validation_plan": {"metric": "kWh pré-ouverture comparable", "expected_direction": "baisse", "comparison_window": "quatre semaines", "confounders": "production et horaires", "minimum_evidence": "baisse persistante"}}
    packet = {"technical_finding_refs": [{"finding_id": "FIND-EXCESS-01"}], "economic_inputs": [_input("TAR-BASE", "electricity_tariff", .20, "EUR/kWh", "per_kwh", [artifact_ids["facture_tarif.txt"]]), _input("CAP-INSPECT", "diagnostic_quote", 300, "EUR", "one_off", [artifact_ids["supplier_quote.txt"]])], "scenario_assumptions": [_assumption("TAR-LOW", .18, "Tarif bas plausible."), _assumption("TAR-HIGH", .23, "Tarif haut plausible."), {"assumption_id": "CAP-LOW", "description": "Devis bas plausible.", "value": 250, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "quote range"}}, {"assumption_id": "CAP-HIGH", "description": "Devis haut plausible.", "value": 400, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "quote range"}}], "operational_constraints": [{"constraint_id": "CONS-PROD-01", "category": "PRODUCTION", "description": "Pas d'indisponibilité pendant préparation/livraison.", "source_status": "EXPLICIT", "source_refs": [artifact_ids["planning_ouverture.txt"], artifact_ids["production_approx.csv"]], "hard": True, "material": True, "affected_action_ids": ["ACT-INSPECT-01"]}], "candidate_actions": [action], "relationships": [], "scenario_calculations": {"ACT-INSPECT-01": calc}, "economic_requests": [], "decision": {"decision_id": "DEC-E2E-02", "decision": "INVESTIGATE_FIRST", "selected_action_ids": ["ACT-INSPECT-01"], "considered_action_ids": ["ACT-INSPECT-01"], "reason": "Cause physique non départagée avant intervention irréversible.", "priority_reasoning": "Inspection réversible et faible coût.", "technical_confidence": "MEDIUM", "economic_importance": "HIGH", "constraint_assessments": [{"constraint_id": "CONS-PROD-01", "disposition": "MITIGATED", "rationale": "Inspection hors préparation."}], "evidence_acquisition": {"what_it_resolves": "dérive ou préparation légitime", "decision_that_can_change": "réparer/remplacer ou ne pas intervenir", "cost_or_burden": "inspection planifiée", "why_worth_it": "évite CAPEX non justifié"}}}
    persist_economic_packet(case, packet)
    resume = economic_handoff(case)
    _write(case / "investigation" / "goal_b_2_e2e_trace.json", {"workflow": ["Goal A evidence", "pre-reasoning handoff", "Codex reasoning contract", "deterministic calculations", "persisted Goal B state", "optional resume handoff"], "pre_handoff": pre["artifact"], "reasoning_contract": "investigation/codex_economic_reasoning_contract.json", "state": "investigation/economic_decision_state.json", "resume_handoff": resume["artifact"]})
    return case


if __name__ == "__main__":
    print(generate())
