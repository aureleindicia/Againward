"""Génère un E2E B.1 : Goal A → handoff → contrat Codex → Python → état B."""
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


def _action() -> dict:
    return {
        "action_id": "ACT-INSPECT-01", "finding_ids": ["FIND-EXCESS-01"],
        "title": "Inspection ciblée pendant la maintenance planifiée",
        "description": "Action candidate formulée par Codex dans cette fixture synthétique.",
        "action_type": "diagnostic", "technical_rationale": "L'excès est observé, mais la cause physique reste concurrente.",
        "operational_rationale": "Préserver la préparation du matin et utiliser la visite déjà prévue.",
        "implementation_scope": "Système concerné par l'excès pré-ouverture.",
        "requires_professional_validation": True, "assumptions": [], "constraints": ["CONS-PROD-01"],
        "dependencies": [], "alternatives": [], "reversibility": "REVERSIBLE", "energy_effect_ref": "EFF-EXCESS-01",
        "validation_plan": {"metric": "kWh par créneau pré-ouverture comparable", "expected_direction": "baisse si une dérive est corrigée", "comparison_window": "quatre semaines avant/après", "confounders": "production, horaires, météo", "minimum_evidence": "baisse persistante normalisée par les conditions comparables"},
    }


def generate(root: str | Path = "examples") -> Path:
    root = Path(root)
    raw, case_root = root / "goal_b_1_e2e_input", root / "goal_b_1_e2e_case"
    if raw.exists() or case_root.exists():
        raise FileExistsError("Les fixtures B.1 existent déjà; elles ne seront pas écrasées.")
    raw.mkdir(parents=True)
    (raw / "energy_interval_export.csv").write_text("timestamp,energy_kwh,production\n2026-06-01 05:00,5.0,0\n2026-06-01 05:30,5.2,0\n2026-06-01 06:00,2.0,0\n2026-06-01 06:30,2.2,12\n2026-06-02 05:00,5.1,0\n2026-06-02 05:30,5.0,0\n2026-06-02 06:00,2.1,0\n2026-06-02 06:30,2.2,11\n", encoding="utf-8")
    (raw / "production_approx.csv").write_text("date,production\n2026-06-01,12\n2026-06-02,11\n", encoding="utf-8")
    (raw / "planning_ouverture.txt").write_text("Préparation habituelle à 06:30; livraison clients à partir de 07:30.\n", encoding="utf-8")
    (raw / "maintenance_note.txt").write_text("Le technicien a signalé une dérive possible, sans diagnostic confirmé.\n", encoding="utf-8")
    (raw / "facture_tarif.txt").write_text("Contrat électricité : 0,20 EUR/kWh moyen sur la période.\n", encoding="utf-8")
    (raw / "supplier_quote.txt").write_text("Devis inspection : 300 EUR; devis remplacement indicatif : 12 000 EUR.\n", encoding="utf-8")
    (raw / "meter_without_unit.csv").write_text("timestamp,Energy\n2026-06-01 05:00,50\n2026-06-01 05:30,51\n", encoding="utf-8")
    (raw / "logo_photo.txt").write_text("matériel marketing sans pertinence analytique\n", encoding="utf-8")
    create_client_case("artisan_sme", root=case_root)
    case = case_root / "artisan_sme"
    ingest_client_drop(raw, case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    artifact_ids = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    record_structured_findings(case, [{
        "finding_id": "FIND-EXCESS-01", "observation": "Excès récurrent avant préparation observé dans la série synthétique.",
        "time_context_window": "05:00–06:00, deux jours comparables", "quantitative_evidence": {"excess_energy_kwh": 6.0, "source": "DS-001"},
        "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "possible_explanations": ["dérive technique", "préparation opérationnelle non documentée"],
        "current_leading_explanation": None, "counter_explanations": ["horaire exceptionnel"],
        "missing_material_information": ["statut opérationnel de la préparation précoce"], "client_question": None,
        "technical_evidence_request": "Inspection ciblée pendant visite planifiée.", "confidence": "MEDIUM",
        "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Comparer périodes comparables après inspection.", "predictive_degradation_note": None,
    }])
    pre_handoff = economic_handoff(case)
    _write(case / "investigation" / "codex_economic_reasoning_contract.json", {
        "schema_version": 1, "input_handoff_ref": pre_handoff["artifact"], "handoff_phase": pre_handoff["phase"],
        "codex_responsibilities": ["choose candidate actions", "declare operational constraints", "choose baselines and relationships", "choose whether evidence is worth buying", "select a decision"],
        "python_responsibilities": ["calculate scenario arithmetic", "validate provenance, units and reproducibility", "persist only valid state"],
        "not_a_deterministic_recommendation": True,
    })
    initialize_economic_state(case)
    effect = {"effect_id": "EFF-EXCESS-01", "basis": "COUNTERFACTUAL_ESTIMATE", "baseline": "créneau pré-ouverture de référence", "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": 4000, "BASE": 7000, "HIGH": 10000}, "finding_refs": ["FIND-EXCESS-01"], "source_refs": ["DS-001-01"]}
    refs = {"energy_effect": {item: ["FIND-EXCESS-01"] for item in ("LOW", "BASE", "HIGH")}, "tariff_per_kwh": {"LOW": ["TAR-LOW"], "BASE": ["ECON-TARIFF-01"], "HIGH": ["TAR-HIGH"]}, "intervention_cost": {"LOW": ["CAP-LOW"], "BASE": ["ECON-INSPECTION-01"], "HIGH": ["CAP-HIGH"]}}
    scenarios = calculate_economic_scenarios(effect, tariff_per_kwh={"LOW": .18, "BASE": .20, "HIGH": .23}, intervention_cost={"LOW": 250, "BASE": 300, "HIGH": 400}, input_references=refs)
    packet = {
        "technical_finding_refs": [{"finding_id": "FIND-EXCESS-01", "technical_status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "technical_confidence": "MEDIUM", "provenance": "investigation/structured_findings.json"}],
        "economic_inputs": [
            {"input_id": "ECON-TARIFF-01", "kind": "electricity_tariff", "value": .20, "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh", "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [artifact_ids["facture_tarif.txt"]]}, "confidence": "MEDIUM"},
            {"input_id": "ECON-INSPECTION-01", "kind": "diagnostic_quote", "value": 300, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [artifact_ids["supplier_quote.txt"]]}, "confidence": "MEDIUM"},
        ],
        "scenario_assumptions": [
            {"assumption_id": "TAR-LOW", "description": "Tarif bas plausible.", "value": .18, "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "sensitivity"}},
            {"assumption_id": "TAR-HIGH", "description": "Tarif haut plausible.", "value": .23, "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "sensitivity"}},
            {"assumption_id": "CAP-LOW", "description": "Coût bas plausible.", "value": 250, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "quote range"}},
            {"assumption_id": "CAP-HIGH", "description": "Coût haut plausible.", "value": 400, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "quote range"}},
        ],
        "operational_constraints": [{"constraint_id": "CONS-PROD-01", "category": "PRODUCTION", "description": "Pas d'indisponibilité pendant la préparation/livraison du matin.", "source_status": "EXPLICIT", "source_refs": [artifact_ids["planning_ouverture.txt"], artifact_ids["production_approx.csv"]], "hard": True, "material": True, "affected_action_ids": ["ACT-INSPECT-01"]}],
        "candidate_actions": [_action()], "relationships": [], "scenario_calculations": {"ACT-INSPECT-01": scenarios},
        "economic_requests": [{"request_id": "ECO-REQ-01", "request_type": "REQUEST_QUOTE", "client_question": "Avez-vous un devis récent de remplacement à partager si vous l'avez déjà ?", "internal_reason": "Un CAPEX de remplacement peut changer l'étape suivante après inspection.", "target_role": "dirigeant", "decision_impact": "Comparer inspection, réparation et remplacement.", "expected_effort": "Envoyer un document existant si disponible.", "importance": "NON_BLOCKING"}],
        "decision": {"decision_id": "DEC-E2E-01", "decision": "INVESTIGATE_FIRST", "selected_action_ids": ["ACT-INSPECT-01"], "considered_action_ids": ["ACT-INSPECT-01"], "reason": "Le gain potentiel justifie un contrôle peu coûteux, mais la cause ne justifie pas encore un remplacement.", "priority_reasoning": "Préserver la production et départager une cause technique d'un horaire légitime.", "technical_confidence": "MEDIUM", "economic_importance": "HIGH", "constraint_assessments": [{"constraint_id": "CONS-PROD-01", "disposition": "MITIGATED", "rationale": "Inspection pendant une visite hors préparation."}], "evidence_acquisition": {"what_it_resolves": "dérive technique versus préparation opérationnelle", "decision_that_can_change": "réparer/remplacer ou ne pas intervenir", "cost_or_burden": "inspection ciblée planifiée", "why_worth_it": "évite un investissement irréversible non justifié"}},
    }
    persist_economic_packet(case, packet)
    economic_handoff(case)
    _write(case / "investigation" / "goal_b_1_e2e_trace.json", {"workflow": ["Goal A evidence", "pre-reasoning economic handoff", "Codex reasoning contract", "deterministic scenario calculations", "persisted Goal B state", "optional resume handoff"], "pre_handoff": pre_handoff["artifact"], "reasoning_contract": "investigation/codex_economic_reasoning_contract.json", "state": "investigation/economic_decision_state.json", "resume_handoff": "investigation/economic_handoff_resume.json"})
    return case


if __name__ == "__main__":
    print(generate())
