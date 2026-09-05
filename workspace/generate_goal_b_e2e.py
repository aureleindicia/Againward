"""Crée le cas synthétique Goal A → Goal B, sans données ou vérité client cachée."""
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
)


def _action(identifier: str, title: str, action_type: str, reversibility: str, effect_ref: str | None = None) -> dict:
    return {
        "action_id": identifier,
        "finding_ids": ["FIND-EXCESS-01"], "title": title,
        "description": "Option structurée par Codex dans un cas synthétique.",
        "action_type": action_type,
        "technical_rationale": "Excès énergétique mesuré; cause physique encore non départagée.",
        "operational_rationale": "Doit respecter la fenêtre de maintenance et la production du matin.",
        "implementation_scope": "Système thermique concerné.",
        "requires_professional_validation": True,
        "assumptions": ["Cause physique non confirmée."], "constraints": ["CONS-PROD-01"],
        "dependencies": [], "alternatives": [], "reversibility": reversibility, "energy_effect_ref": effect_ref,
        "validation_plan": {
            "metric": "kWh par lot de production comparable", "expected_direction": "baisse si la cause est confirmée",
            "comparison_window": "quatre semaines avant/après", "confounders": "mix produit, météo, volume",
            "minimum_evidence": "baisse persistante après correction, normalisée par production",
        },
    }


def generate(root: str | Path = "examples") -> Path:
    root = Path(root)
    raw = root / "goal_b_e2e_input"
    case_root = root / "goal_b_e2e_case"
    if raw.exists() or case_root.exists():
        raise FileExistsError("Les fixtures Goal B existent déjà; elles ne seront pas écrasées.")
    raw.mkdir(parents=True)
    (raw / "energy_interval_export.csv").write_text(
        "timestamp,energy_kwh,production\n"
        "2026-06-01 05:00,5.0,0\n2026-06-01 05:30,5.2,0\n"
        "2026-06-01 06:00,2.0,0\n2026-06-01 06:30,2.2,12\n"
        "2026-06-02 05:00,5.1,0\n2026-06-02 05:30,5.0,0\n"
        "2026-06-02 06:00,2.1,0\n2026-06-02 06:30,2.2,11\n",
        encoding="utf-8",
    )
    (raw / "production_approx.csv").write_text(
        "date,production\n2026-06-01,12\n2026-06-02,11\n", encoding="utf-8"
    )
    (raw / "planning_ouverture.txt").write_text(
        "Préparation habituelle à 06:30; livraison clients à partir de 07:30.\n", encoding="utf-8"
    )
    (raw / "maintenance_note.txt").write_text(
        "Le technicien a signalé une dérive possible, sans diagnostic confirmé.\n", encoding="utf-8"
    )
    (raw / "facture_tarif.txt").write_text(
        "Contrat électricité : 0,20 EUR/kWh moyen sur la période.\n", encoding="utf-8"
    )
    (raw / "supplier_quote.txt").write_text(
        "Devis remplacement indicatif : 12 000 EUR, à confirmer.\n", encoding="utf-8"
    )
    (raw / "meter_without_unit.csv").write_text(
        "timestamp,Energy\n2026-06-01 05:00,50\n2026-06-01 05:30,51\n", encoding="utf-8"
    )
    (raw / "logo_photo.txt").write_text("matériel marketing sans pertinence analytique\n", encoding="utf-8")
    create_client_case("artisan_sme", root=case_root, synthetic=True)
    case = case_root / "artisan_sme"
    ingest_client_drop(raw, case)
    inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
    artifact_ids = {item["raw_relative_path"]: item["artifact_id"] for item in inventory["artifacts"]}
    record_structured_findings(case, [{
        "finding_id": "FIND-EXCESS-01", "observation": "Excès récurrent avant préparation observé dans la série synthétique.",
        "time_context_window": "05:00–06:00, deux jours comparables", "quantitative_evidence": {"excess_energy_kwh": 6.0, "source": "DS-001"},
        "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "possible_explanations": ["dérive technique", "préparation opérationnelle non documentée"],
        "current_leading_explanation": None, "counter_explanations": ["horaire exceptionnel"],
        "missing_material_information": ["statut opérationnel de la préparation précoce"],
        "client_question": None, "technical_evidence_request": "Inspection ciblée pendant visite planifiée.",
        "confidence": "MEDIUM", "provenance": ["evidence/dataset_provenance.json"],
        "recommended_next_analytical_step": "Comparer périodes comparables après inspection.",
        "predictive_degradation_note": None,
    }])
    # B.1: Goal A evidence is exposed to Codex before an economic packet exists.
    economic_handoff(case)
    initialize_economic_state(case)
    effect = {
        "effect_id": "EFF-EXCESS-01", "basis": "COUNTERFACTUAL_ESTIMATE", "baseline": "créneau pré-ouverture de référence",
        "unit": "kWh/year", "period": "hypothèse de récurrence annuelle", "scenarios": {"LOW": 4000, "BASE": 7000, "HIGH": 10000},
        "finding_refs": ["FIND-EXCESS-01"], "source_refs": ["DS-001-01"],
    }
    scenarios = calculate_economic_scenarios(
        effect, tariff_per_kwh={"LOW": .20, "BASE": .20, "HIGH": .20},
        intervention_cost={"LOW": 12000, "BASE": 12000, "HIGH": 12000},
        recurring_cost={"LOW": 0, "BASE": 0, "HIGH": 0},
        input_references={
            "energy_effect": {item: ["FIND-EXCESS-01"] for item in ("LOW", "BASE", "HIGH")},
            "tariff_per_kwh": {item: ["ECON-TARIFF-01"] for item in ("LOW", "BASE", "HIGH")},
            "intervention_cost": {item: ["ECON-CAPEX-01"] for item in ("LOW", "BASE", "HIGH")},
            "recurring_cost": {item: ["ECON-RECUR-01"] for item in ("LOW", "BASE", "HIGH")},
        },
    )
    packet = {
        "technical_finding_refs": [{"finding_id": "FIND-EXCESS-01", "technical_status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "technical_confidence": "MEDIUM", "provenance": "investigation/structured_findings.json"}],
        "economic_inputs": [
            {"input_id": "ECON-TARIFF-01", "kind": "electricity_tariff", "value": .20, "unit": "EUR/kWh", "currency": "EUR", "period": "per_kwh", "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [artifact_ids["facture_tarif.txt"]]}, "confidence": "MEDIUM"},
            {"input_id": "ECON-CAPEX-01", "kind": "replacement_quote", "value": 12000, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"source_refs": [artifact_ids["supplier_quote.txt"]]}, "confidence": "LOW"},
        ],
        "scenario_assumptions": [{"assumption_id": "ECON-RECUR-01", "description": "Aucun coût récurrent additionnel dans cette fixture.", "value": 0, "unit": "EUR/year", "currency": "EUR", "period": "annual", "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "explicit zero scenario"}}],
        "operational_constraints": [{"constraint_id": "CONS-PROD-01", "category": "PRODUCTION", "description": "Le système ne peut pas être indisponible pendant la préparation/livraison du matin.", "source_status": "EXPLICIT", "source_refs": [artifact_ids["planning_ouverture.txt"], artifact_ids["production_approx.csv"]], "hard": True, "material": True, "affected_action_ids": ["ACT-INSPECT-01", "ACT-REPLACE-01"], "unresolved_uncertainty": None}],
        "candidate_actions": [_action("ACT-INSPECT-01", "Inspection ciblée pendant visite planifiée", "diagnostic", "REVERSIBLE"), _action("ACT-REPLACE-01", "Remplacement après confirmation", "replacement", "IRREVERSIBLE", "EFF-EXCESS-01")],
        "relationships": [{"relationship_id": "REL-SEQ-01", "type": "SEQUENTIAL", "action_a": "ACT-INSPECT-01", "action_b": "ACT-REPLACE-01", "rationale": "La décision de remplacement dépend du résultat de l'inspection.", "sequence": ["ACT-INSPECT-01", "ACT-REPLACE-01"]}],
        "scenario_calculations": {"ACT-REPLACE-01": scenarios},
        "economic_requests": [{"request_id": "ECO-REQ-01", "request_type": "REQUEST_QUOTE", "client_question": "Avez-vous un devis récent ou un remplacement déjà planifié pour cet équipement ?", "internal_reason": "Le coût/timing peut modifier la comparaison après inspection.", "target_role": "dirigeant", "decision_impact": "Planifier, remplacer ou conserver l'équipement.", "expected_effort": "Envoyer un document existant si disponible.", "importance": "NON_BLOCKING"}],
        "decision": {"decision_id": "DEC-E2E-01", "decision": "INVESTIGATE_FIRST", "selected_action_ids": ["ACT-INSPECT-01"], "considered_action_ids": ["ACT-INSPECT-01", "ACT-REPLACE-01"], "reason": "Le gain potentiel justifie un contrôle peu coûteux, mais la cause ne justifie pas encore un remplacement.", "priority_reasoning": "Préserver la production, limiter le risque CAPEX et départager une cause technique d'un horaire légitime.", "technical_confidence": "MEDIUM", "economic_importance": "HIGH", "constraint_assessments": [{"constraint_id": "CONS-PROD-01", "disposition": "MITIGATED", "rationale": "Inspection seulement pendant une visite de maintenance hors préparation."}], "evidence_acquisition": {"what_it_resolves": "dérive technique versus préparation opérationnelle", "decision_that_can_change": "engager ou non un remplacement", "cost_or_burden": "inspection ciblée pendant maintenance prévue", "why_worth_it": "évite un CAPEX élevé si la charge est légitime"}},
    }
    persist_economic_packet(case, packet)
    economic_handoff(case)
    return case


if __name__ == "__main__":
    print(generate())
