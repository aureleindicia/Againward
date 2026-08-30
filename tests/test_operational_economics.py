from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from client_intake_pipeline import create_client_case, ingest_client_drop
from operational_economics import (
    aggregate_declared_portfolio,
    build_economic_request_batch,
    calculate_economic_scenarios,
    calculate_time_aligned_savings,
    calculate_time_aligned_savings_with_tariff_plan,
    economic_handoff,
    initialize_economic_state,
    persist_economic_packet,
    validate_decision,
    validate_economic_input,
    validate_energy_effect,
)


def _effect() -> dict[str, object]:
    return {
        "effect_id": "EFF-01",
        "basis": "DIRECTLY_MEASURED_HISTORICAL_EXCESS",
        "baseline": "historical healthy off-hours reference",
        "unit": "kWh/year",
        "period": "annualized from recurring observations",
        "scenarios": {"LOW": 800.0, "BASE": 1000.0, "HIGH": 1200.0},
        "source_refs": ["FIND-01", "DS-001"],
    }


def _action(action_id: str = "ACT-01") -> dict[str, object]:
    return {
        "action_id": action_id,
        "finding_ids": ["FIND-01"],
        "title": "Réparer la fuite confirmée",
        "description": "Intervention proposée par l'analyste.",
        "action_type": "maintenance",
        "technical_rationale": "Le finding associé justifie l'option sans prouver une économie réalisée.",
        "operational_rationale": "À planifier pendant une fenêtre de maintenance.",
        "implementation_scope": "Zone compresseur concernée.",
        "requires_professional_validation": True,
        "assumptions": [],
        "constraints": [],
        "dependencies": [],
        "alternatives": [],
        "reversibility": "PARTIALLY_REVERSIBLE",
        "validation_plan": {
            "metric": "kWh hors production",
            "expected_direction": "baisse",
            "comparison_window": "quatre semaines comparables",
            "confounders": "production et horaires",
            "minimum_evidence": "baisse récurrente après intervention",
        },
    }


def _input() -> dict[str, object]:
    return {
        "input_id": "ECON-01",
        "kind": "electricity_tariff",
        "value": 0.20,
        "unit": "EUR/kWh",
        "provenance": "DOCUMENT_EXTRACTED",
        "source": {"artifact_id": "ART-01", "field": "tariff"},
        "confidence": "HIGH",
    }


class OperationalEconomicsTests(unittest.TestCase):
    def test_scenarios_calculate_net_benefit_and_meaningful_payback(self) -> None:
        result = calculate_economic_scenarios(
            _effect(),
            tariff_per_kwh={"LOW": 0.15, "BASE": 0.20, "HIGH": 0.25},
            intervention_cost={"LOW": 200, "BASE": 300, "HIGH": 500},
            recurring_cost={"LOW": 10, "BASE": 20, "HIGH": 30},
        )
        base = result["scenarios"]["BASE"]
        self.assertEqual(base["gross_annual_energy_cost_avoided"], 200.0)
        self.assertEqual(base["net_annual_benefit"], 180.0)
        self.assertAlmostEqual(base["simple_payback_years"], 300 / 180)

    def test_unknown_tariff_stays_unknown_and_no_fake_payback_is_emitted(self) -> None:
        result = calculate_economic_scenarios(_effect(), tariff_per_kwh=None)
        self.assertIsNone(result["scenarios"]["BASE"]["gross_annual_energy_cost_avoided"])
        self.assertIsNone(result["scenarios"]["BASE"]["simple_payback_years"])
        self.assertEqual(result["scenarios"]["BASE"]["payback_status"], "not_meaningful_or_unknown")

    def test_negative_benefit_does_not_emit_payback(self) -> None:
        result = calculate_economic_scenarios(
            _effect(), tariff_per_kwh={item: 0.1 for item in ("LOW", "BASE", "HIGH")},
            intervention_cost={item: 100 for item in ("LOW", "BASE", "HIGH")},
            recurring_cost={item: 200 for item in ("LOW", "BASE", "HIGH")},
        )
        self.assertLess(result["scenarios"]["BASE"]["net_annual_benefit"], 0)
        self.assertIsNone(result["scenarios"]["BASE"]["simple_payback_years"])

    def test_mwh_conversion_and_invalid_energy_scenarios_are_rejected(self) -> None:
        effect = _effect()
        effect["unit"] = "MWh/year"
        effect["scenarios"] = {"LOW": 1, "BASE": 2, "HIGH": 3}
        result = calculate_economic_scenarios(effect, tariff_per_kwh={item: 0.2 for item in ("LOW", "BASE", "HIGH")})
        self.assertEqual(result["scenarios"]["BASE"]["annual_energy_saving_kwh"], 2000.0)
        effect["scenarios"] = {"LOW": 3, "BASE": 2, "HIGH": 4}
        with self.assertRaises(ValueError):
            validate_energy_effect(effect)

    def test_time_aligned_tariff_calculation_uses_explicit_prices(self) -> None:
        result = calculate_time_aligned_savings(
            [{"timestamp": "2026-01-01T01:00:00", "energy_saving_kwh": 10}, {"timestamp": "2026-01-01T18:00:00", "energy_saving_kwh": 4}],
            price_for_timestamp=lambda timestamp: 0.10 if "T01" in timestamp else 0.30,
        )
        self.assertEqual(result["time_aligned_energy_saving_kwh"], 14.0)
        self.assertAlmostEqual(result["time_aligned_cost_saving"], 2.2)

    def test_time_of_use_plan_is_used_only_when_savings_are_time_resolved(self) -> None:
        result = calculate_time_aligned_savings_with_tariff_plan(
            [{"timestamp": "2026-01-05T01:00:00", "energy_saving_kwh": 10}, {"timestamp": "2026-01-05T18:00:00", "energy_saving_kwh": 10}],
            {"currency": "EUR", "flat_price_per_kwh": 0.1, "time_of_use_periods": [{"name": "peak", "weekdays": [0], "start": "18:00", "end": "20:00", "price_per_kwh": 0.3}]},
        )
        self.assertEqual(result["tariff_alignment"], "time_resolved")
        self.assertAlmostEqual(result["time_aligned_cost_saving"], 4.0)

    def test_portfolio_refuses_overlap_and_exclusivity_without_a_declared_model(self) -> None:
        table = calculate_economic_scenarios(_effect(), tariff_per_kwh={item: .2 for item in ("LOW", "BASE", "HIGH")})
        tables = {"ACT-A": table, "ACT-B": table}
        overlap = [{"relationship_id": "REL-1", "type": "OVERLAPPING", "action_a": "ACT-A", "action_b": "ACT-B", "rationale": "same excess", "combined_effect_ref": "COMB-1"}]
        with self.assertRaisesRegex(ValueError, "effet combiné"):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], tables, overlap)
        aggregated = aggregate_declared_portfolio(
            ["ACT-A", "ACT-B"], tables, overlap,
            combined_effects={"COMB-1": {"LOW": 160, "BASE": 200, "HIGH": 240}},
        )
        self.assertEqual(aggregated["net_annual_benefit"]["BASE"], 200.0)
        exclusive = [{"relationship_id": "REL-2", "type": "MUTUALLY_EXCLUSIVE", "action_a": "ACT-A", "action_b": "ACT-B", "rationale": "repair or replace"}]
        with self.assertRaises(ValueError):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], tables, exclusive)

    def test_independent_portfolio_sums_only_declared_independent_actions(self) -> None:
        first = calculate_economic_scenarios(_effect(), tariff_per_kwh={item: .2 for item in ("LOW", "BASE", "HIGH")})
        second_effect = _effect()
        second_effect["effect_id"] = "EFF-02"
        second_effect["scenarios"] = {"LOW": 100, "BASE": 200, "HIGH": 300}
        second = calculate_economic_scenarios(second_effect, tariff_per_kwh={item: .2 for item in ("LOW", "BASE", "HIGH")})
        result = aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": first, "ACT-B": second}, [])
        self.assertEqual(result["net_annual_benefit"]["BASE"], 240.0)

    def test_economic_input_unknown_requires_no_fake_value(self) -> None:
        unknown = {"input_id": "CAPEX", "kind": "capex", "provenance": "UNKNOWN", "status": "UNKNOWN", "value": None, "unknown_reason": "No quote available."}
        validate_economic_input(unknown)
        unknown["value"] = 5000
        with self.assertRaises(ValueError):
            validate_economic_input(unknown)

    def test_state_persists_agent_decision_but_never_selects_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop = root / "drop"
            drop.mkdir()
            (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
            create_client_case("case", root=root / "cases")
            case = root / "cases" / "case"
            ingest_client_drop(drop, case)
            initialize_economic_state(case)
            packet = {
                "technical_finding_refs": [{"finding_id": "FIND-01", "status": "supported", "provenance": "investigation/structured_findings.json"}],
                "economic_inputs": [_input()], "candidate_actions": [_action()], "operational_constraints": [], "relationships": [],
                "scenario_calculations": {"ACT-01": calculate_economic_scenarios(_effect(), tariff_per_kwh={item: .2 for item in ("LOW", "BASE", "HIGH")})},
                "decision": {"decision_id": "DEC-01", "decision": "ACT_NOW", "action_ids": ["ACT-01"], "reason": "Codex conclusion based on supplied evidence.", "priority_reasoning": "Codex comparison, not weighted score.", "technical_confidence": "HIGH", "economic_importance": "MEDIUM"},
            }
            state = persist_economic_packet(case, packet)
            self.assertEqual(state["decisions"][0]["decision"], "ACT_NOW")
            self.assertFalse(state["deterministic_recommendation_engine"])
            self.assertIn("candidate actions", economic_handoff(case)["codex_must_decide"])

    def test_hard_constraint_is_explicit_for_operational_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop = root / "drop"
            drop.mkdir()
            (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
            create_client_case("case", root=root / "cases")
            case = root / "cases" / "case"
            ingest_client_drop(drop, case)
            initialize_economic_state(case)
            constraint = {"constraint_id": "CONS-01", "category": "HYGIENE", "description": "Ventilation obligatoire pendant le nettoyage.", "source_status": "EXPLICIT", "source_ref": "ART-SCHEDULE", "hard": True, "material": True, "affected_action_ids": ["ACT-01"], "unresolved_uncertainty": None}
            packet = {"economic_inputs": [], "candidate_actions": [_action()], "operational_constraints": [constraint], "relationships": [], "decision": {"decision_id": "DEC-02", "decision": "OPERATIONALLY_NOT_JUSTIFIED", "action_ids": [], "reason": "La contrainte d'hygiène bloque l'action proposée.", "priority_reasoning": "Sécurité et hygiène priment sur l'économie théorique.", "technical_confidence": "HIGH", "economic_importance": "MEDIUM", "blocking_constraint_ids": ["CONS-01"]}}
            self.assertEqual(persist_economic_packet(case, packet)["decisions"][0]["decision"], "OPERATIONALLY_NOT_JUSTIFIED")

    def test_hard_constraint_on_selected_action_requires_an_explicit_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop = root / "drop"
            drop.mkdir()
            (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
            create_client_case("case", root=root / "cases")
            case = root / "cases" / "case"
            ingest_client_drop(drop, case)
            initialize_economic_state(case)
            constraint = {"constraint_id": "CONS-HARD", "category": "SAFETY", "description": "Arrêt interdit sans consignation professionnelle.", "source_status": "EXPLICIT", "source_ref": "ART-SAFETY", "hard": True, "material": True, "affected_action_ids": ["ACT-01"], "unresolved_uncertainty": None}
            decision = {"decision_id": "DEC-HARD", "decision": "ACT_NOW", "action_ids": ["ACT-01"], "reason": "Analyst judgement.", "priority_reasoning": "No score.", "technical_confidence": "HIGH", "economic_importance": "HIGH"}
            with self.assertRaisesRegex(ValueError, "ne peut pas être ignorée"):
                persist_economic_packet(case, {"economic_inputs": [], "candidate_actions": [_action()], "operational_constraints": [constraint], "relationships": [], "decision": decision})

    def test_investigate_first_requires_evidence_that_can_change_decision(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop = root / "drop"
            drop.mkdir()
            (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
            create_client_case("case", root=root / "cases")
            case = root / "cases" / "case"
            ingest_client_drop(drop, case)
            initialize_economic_state(case)
            decision = {"decision_id": "DEC-03", "decision": "INVESTIGATE_FIRST", "action_ids": ["ACT-01"], "reason": "Cause non départagée avant CAPEX.", "priority_reasoning": "Test ciblé moins coûteux que l'intervention.", "technical_confidence": "LOW", "economic_importance": "HIGH", "evidence_acquisition": {"what_it_resolves": "fouling versus demande légitime", "decision_that_can_change": "remplacer ou ne pas remplacer", "cost_or_burden": "inspection planifiée faible coût", "why_worth_it": "peut éviter un CAPEX inutile"}}
            state = persist_economic_packet(case, {"economic_inputs": [], "candidate_actions": [_action()], "operational_constraints": [], "relationships": [], "decision": decision})
            self.assertEqual(state["decisions"][0]["decision"], "INVESTIGATE_FIRST")

    def test_quote_request_and_question_budget_are_low_friction(self) -> None:
        batch = build_economic_request_batch([{"request_type": "REQUEST_QUOTE", "client_question": "Avez-vous déjà un devis pour ce remplacement ?", "internal_reason": "Le CAPEX peut inverser la décision.", "target_role": "dirigeant", "decision_impact": "Comparer réparation et remplacement.", "expected_effort": "Envoyer un devis existant.", "importance": "NON_BLOCKING"}])
        self.assertEqual(batch["requests"][0]["request_type"], "REQUEST_QUOTE")
        with self.assertRaises(ValueError):
            build_economic_request_batch([batch["requests"][0]] * 4)

    def test_fixture_catalogue_covers_all_required_reasoning_families(self) -> None:
        payload = json.loads((Path("examples") / "goal_b_fixture_catalog.json").read_text(encoding="utf-8"))
        identifiers = {item["fixture_id"] for item in payload["fixtures"]}
        self.assertEqual(identifiers, {f"B-{letter}" for letter in "ABCDEFGHIJKLMNO"})
        self.assertIn("INVESTIGATE_FIRST", {item["expected_agent_decision"] for item in payload["fixtures"]})
        self.assertIn("DO_NOTHING", {item["expected_agent_decision"] for item in payload["fixtures"]})

    def test_all_decision_semantics_are_available_without_hidden_choice_rules(self) -> None:
        base = {
            "decision_id": "DEC", "reason": "Analyst rationale.", "priority_reasoning": "Analyst comparison.",
            "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM",
        }
        for decision in ("ACT_NOW", "MONITOR", "DEFER"):
            validate_decision({**base, "decision": decision, "action_ids": ["ACT-01"]}, {"ACT-01"})
        for decision in ("DO_NOTHING", "NO_ECONOMIC_CASE", "INSUFFICIENT_FOR_ECONOMIC_DECISION"):
            validate_decision({**base, "decision": decision, "action_ids": []}, {"ACT-01"})
        with self.assertRaises(ValueError):
            validate_decision({**base, "decision": "OPERATIONALLY_NOT_JUSTIFIED", "action_ids": []}, {"ACT-01"})


if __name__ == "__main__":
    unittest.main()
