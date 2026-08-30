from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from client_intake_pipeline import create_client_case, ingest_client_drop, record_structured_findings
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
    validate_candidate_action,
    validate_economic_input,
    validate_energy_effect,
    validate_constraint,
    validate_relationship,
)
from workspace.generate_goal_b_1_e2e import generate as generate_goal_b_1_e2e


def _effect(identifier: str = "EFF-01", baseline: str = "historical healthy off-hours reference") -> dict[str, object]:
    return {"effect_id": identifier, "basis": "DIRECTLY_MEASURED_HISTORICAL_EXCESS", "baseline": baseline, "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": 800.0, "BASE": 1000.0, "HIGH": 1200.0}, "source_refs": ["FIND-01"]}


def _refs(*, tariff: bool = True, capex: bool = False, recurring: bool = False) -> dict[str, object]:
    output: dict[str, object] = {"energy_effect": {item: ["FIND-01"] for item in ("LOW", "BASE", "HIGH")}}
    if tariff:
        output["tariff_per_kwh"] = {item: ["ECON-TARIFF"] for item in ("LOW", "BASE", "HIGH")}
    if capex:
        output["intervention_cost"] = {item: ["ECON-CAPEX"] for item in ("LOW", "BASE", "HIGH")}
    if recurring:
        output["recurring_cost"] = {item: ["ECON-RECUR"] for item in ("LOW", "BASE", "HIGH")}
    return output


def _calculation(effect: dict[str, object] | None = None, *, tariff: float | None = 0.2, capex: float | None = None, recurring: float | None = None) -> dict[str, object]:
    return calculate_economic_scenarios(effect or _effect(), tariff_per_kwh=None if tariff is None else {item: tariff for item in ("LOW", "BASE", "HIGH")}, intervention_cost=None if capex is None else {item: capex for item in ("LOW", "BASE", "HIGH")}, recurring_cost=None if recurring is None else {item: recurring for item in ("LOW", "BASE", "HIGH")}, input_references=_refs(tariff=tariff is not None, capex=capex is not None, recurring=recurring is not None))


def _action(action_id: str = "ACT-01", effect_id: str | None = "EFF-01") -> dict[str, object]:
    return {"action_id": action_id, "finding_ids": ["FIND-01"], "title": "Action proposée", "description": "Option formulée par Codex.", "action_type": "maintenance", "technical_rationale": "Le finding associé justifie l'option sans prouver une économie réalisée.", "operational_rationale": "À planifier pendant une fenêtre de maintenance.", "implementation_scope": "Équipement concerné.", "requires_professional_validation": True, "assumptions": [], "constraints": [], "dependencies": [], "alternatives": [], "reversibility": "PARTIALLY_REVERSIBLE", "energy_effect_ref": effect_id, "validation_plan": {"metric": "kWh hors production", "expected_direction": "baisse", "comparison_window": "quatre semaines comparables", "confounders": "production et horaires", "minimum_evidence": "baisse récurrente après intervention"}}


def _input(identifier: str, kind: str, value: float, unit: str = "EUR") -> dict[str, object]:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "provenance": "DOCUMENT_EXTRACTED", "source": {"artifact_id": "ART-01", "field": kind}, "confidence": "HIGH"}


def _decision(decision: str = "ACT_NOW", *, selected: list[str] | None = None, considered: list[str] | None = None) -> dict[str, object]:
    selected = ["ACT-01"] if selected is None else selected
    considered = selected if considered is None else considered
    payload: dict[str, object] = {"decision_id": "DEC-01", "decision": decision, "selected_action_ids": selected, "considered_action_ids": considered, "reason": "Conclusion formulée par Codex sur les preuves disponibles.", "priority_reasoning": "Comparaison explicite, sans score pondéré.", "technical_confidence": "HIGH", "economic_importance": "MEDIUM"}
    if decision == "INVESTIGATE_FIRST":
        payload["evidence_acquisition"] = {"what_it_resolves": "cause concurrente", "decision_that_can_change": "intervenir ou non", "cost_or_burden": "inspection planifiée", "why_worth_it": "évite un CAPEX inutile"}
    return payload


def _relation(kind: str = "INDEPENDENT", *, baseline_resolution: dict | None = None) -> dict[str, object]:
    result: dict[str, object] = {"relationship_id": "REL-01", "type": kind, "action_a": "ACT-A", "action_b": "ACT-B", "rationale": "Relation déclarée par Codex."}
    if kind == "OVERLAPPING":
        result["combined_effect_ref"] = "COMB-01"
    if baseline_resolution:
        result["baseline_resolution"] = baseline_resolution
    return result


class OperationalEconomicsTests(unittest.TestCase):
    def test_scenarios_are_reproducible_and_provenanced(self) -> None:
        result = _calculation(_effect(), tariff=.2, capex=300, recurring=20)
        base = result["scenarios"]["BASE"]
        self.assertEqual(base["gross_annual_energy_cost_avoided"], 200.0)
        self.assertEqual(base["net_annual_benefit"], 180.0)
        self.assertAlmostEqual(base["simple_payback_years"], 300 / 180)
        self.assertEqual(result["reproducibility"]["input_references"]["tariff_per_kwh"]["BASE"], ["ECON-TARIFF"])

    def test_unknown_tariff_and_negative_benefit_never_emit_payback(self) -> None:
        unknown = _calculation(tariff=None)
        self.assertIsNone(unknown["scenarios"]["BASE"]["gross_annual_energy_cost_avoided"])
        negative = _calculation(tariff=.1, capex=100, recurring=200)
        self.assertLess(negative["scenarios"]["BASE"]["net_annual_benefit"], 0)
        self.assertIsNone(negative["scenarios"]["BASE"]["simple_payback_years"])

    def test_units_and_time_aligned_tariff_are_deterministic(self) -> None:
        effect = _effect()
        effect["unit"] = "MWh/year"
        effect["scenarios"] = {"LOW": 1, "BASE": 2, "HIGH": 3}
        self.assertEqual(_calculation(effect)["scenarios"]["BASE"]["annual_energy_saving_kwh"], 2000.0)
        effect["scenarios"] = {"LOW": 3, "BASE": 2, "HIGH": 4}
        with self.assertRaises(ValueError):
            validate_energy_effect(effect)
        result = calculate_time_aligned_savings([{"timestamp": "2026-01-01T01:00:00", "energy_saving_kwh": 10}, {"timestamp": "2026-01-01T18:00:00", "energy_saving_kwh": 4}], price_for_timestamp=lambda timestamp: .1 if "T01" in timestamp else .3)
        self.assertAlmostEqual(result["time_aligned_cost_saving"], 2.2)
        tou = calculate_time_aligned_savings_with_tariff_plan([{"timestamp": "2026-01-05T01:00:00", "energy_saving_kwh": 10}, {"timestamp": "2026-01-05T18:00:00", "energy_saving_kwh": 10}], {"currency": "EUR", "flat_price_per_kwh": .1, "time_of_use_periods": [{"name": "peak", "weekdays": [0], "start": "18:00", "end": "20:00", "price_per_kwh": .3}]})
        self.assertAlmostEqual(tou["time_aligned_cost_saving"], 4.0)

    def test_portfolio_fails_closed_when_relation_is_omitted(self) -> None:
        first, second = _calculation(_effect("EFF-A")), _calculation(_effect("EFF-B"))
        with self.assertRaisesRegex(ValueError, "UNKNOWN par omission"):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": first, "ACT-B": second}, [])
        result = aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": first, "ACT-B": second}, [_relation()])
        self.assertEqual(result["net_annual_benefit"]["BASE"], 400.0)

    def test_baseline_compatibility_is_declared_not_inferred(self) -> None:
        first = _calculation(_effect("EFF-A", "baseline A"))
        second = _calculation(_effect("EFF-B", "baseline B"))
        with self.assertRaisesRegex(ValueError, "Baselines différentes"):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": first, "ACT-B": second}, [_relation()])
        resolution = {"status": "RECONCILED", "rationale": "Codex a réconcilié les fenêtres comparables.", "source_refs": ["FIND-01"]}
        result = aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": first, "ACT-B": second}, [_relation(baseline_resolution=resolution)])
        self.assertEqual(result["net_annual_benefit"]["BASE"], 400.0)

    def test_overlap_rejects_bare_numbers_and_accepts_recalculated_energy_effect(self) -> None:
        individual = _calculation(_effect("EFF-A"))
        tables = {"ACT-A": individual, "ACT-B": individual}
        relation = [_relation("OVERLAPPING")]
        with self.assertRaisesRegex(ValueError, "Type d'effet combiné"):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], tables, relation, combined_effects={"COMB-01": {"LOW": 100}})
        combined_effect = _effect("EFF-C")
        combined_effect["scenarios"] = {"LOW": 800, "BASE": 1000, "HIGH": 1200}
        combined_calculation = _calculation(combined_effect)
        result = aggregate_declared_portfolio(["ACT-A", "ACT-B"], tables, relation, combined_effects={"COMB-01": {"effect_type": "ENERGY", "energy_effect": combined_effect, "economic_calculation": combined_calculation}})
        self.assertEqual(result["net_annual_benefit"]["BASE"], 200.0)

    def test_overlap_rejects_incompatible_direct_economic_units(self) -> None:
        table = _calculation()
        with self.assertRaisesRegex(ValueError, "EUR/year"):
            aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": table, "ACT-B": table}, [_relation("OVERLAPPING")], combined_effects={"COMB-01": {"effect_type": "ECONOMIC", "effect_id": "COMB", "unit": "kWh/year", "period": "annual", "baseline": table["baseline"], "currency": "EUR", "provenance_refs": ["FIND-01"], "scenarios": {"LOW": 1, "BASE": 1, "HIGH": 1}}})

    def test_exclusive_and_unknown_relations_are_not_summed(self) -> None:
        table = _calculation()
        for kind in ("MUTUALLY_EXCLUSIVE", "ALTERNATIVE", "UNKNOWN", "SEQUENTIAL"):
            relation = _relation(kind)
            if kind == "SEQUENTIAL":
                relation["sequence"] = ["ACT-A", "ACT-B"]
            with self.assertRaises(ValueError):
                aggregate_declared_portfolio(["ACT-A", "ACT-B"], {"ACT-A": table, "ACT-B": table}, [relation])

    def _case(self) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        drop = root / "drop"
        drop.mkdir()
        (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
        (drop / "tariff_note.txt").write_text("0.20 EUR/kWh\n", encoding="utf-8")
        create_client_case("case", root=root / "cases")
        case = root / "cases" / "case"
        ingest_client_drop(drop, case)
        record_structured_findings(case, [{"finding_id": "FIND-01", "observation": "Excès confirmé.", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "possible_explanations": ["cause A", "cause B"], "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Comparer les régimes."}])
        return case, directory

    def _packet(self, *, calculation: dict[str, object] | None = None, decision: dict[str, object] | None = None, requests: list[dict[str, object]] | None = None) -> dict[str, object]:
        calculation = _calculation(_effect(), tariff=.2, capex=300, recurring=20) if calculation is None else calculation
        return {"technical_finding_refs": [{"finding_id": "FIND-01", "technical_status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "technical_confidence": "MEDIUM", "provenance": "investigation/structured_findings.json"}], "economic_inputs": [_input("ECON-TARIFF", "electricity_tariff", .2, "EUR/kWh"), _input("ECON-CAPEX", "capex", 300), _input("ECON-RECUR", "recurring_cost", 20)], "candidate_actions": [_action()], "operational_constraints": [], "relationships": [], "scenario_calculations": {"ACT-01": calculation}, "decision": _decision() if decision is None else decision, "economic_requests": [] if requests is None else requests}

    def test_pre_reasoning_handoff_exposes_goal_a_evidence_before_packet(self) -> None:
        case, directory = self._case()
        with directory:
            handoff = economic_handoff(case)
            self.assertEqual(handoff["phase"], "pre_reasoning")
            self.assertEqual(handoff["technical_findings"][0]["finding_id"], "FIND-01")
            self.assertIsNone(handoff["existing_economic_state"])
            self.assertTrue(handoff["available_economic_operational_documents"])
            initialize_economic_state(case)
            state = persist_economic_packet(case, self._packet())
            self.assertEqual(state["scenario_calculations"]["ACT-01"]["scenarios"]["BASE"]["net_annual_benefit"], 180.0)

    def test_persistence_rejects_invented_or_non_reproducible_numbers(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-01"]["scenarios"]["BASE"]["net_annual_benefit"] = 99999
            with self.assertRaisesRegex(ValueError, "incohérent"):
                persist_economic_packet(case, packet)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-MISSING"] = packet["scenario_calculations"].pop("ACT-01")
            with self.assertRaisesRegex(ValueError, "action candidate existante"):
                persist_economic_packet(case, packet)

    def test_persistence_rejects_missing_baseline_reference_or_unknown_provenance(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["candidate_actions"][0].pop("energy_effect_ref")
            with self.assertRaisesRegex(ValueError, "baseline"):
                persist_economic_packet(case, packet)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-01"]["reproducibility"]["input_references"]["tariff_per_kwh"]["BASE"] = ["MADE-UP"]
            with self.assertRaises(ValueError):
                persist_economic_packet(case, packet)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-01"]["reproducibility"]["energy_effect"]["source_refs"] = ["MADE-UP"]
            with self.assertRaisesRegex(ValueError, "finding technique"):
                persist_economic_packet(case, packet)

    def test_economic_requests_use_controlled_vocabulary_and_budget(self) -> None:
        request = {"request_type": "REQUEST_QUOTE", "client_question": "Avez-vous déjà un devis récent pour cette action ?", "internal_reason": "Le CAPEX peut modifier la décision.", "target_role": "dirigeant", "decision_impact": "Comparer les options.", "expected_effort": "Envoyer un devis existant.", "importance": "NON_BLOCKING"}
        self.assertEqual(build_economic_request_batch([request])["requests"][0]["request_type"], "REQUEST_QUOTE")
        inferred = build_economic_request_batch([{"request_type": "INFER_AUTOMATICALLY", "internal_reason": "Le document contient déjà la valeur.", "decision_impact": "Éviter une question inutile."}])
        self.assertIsNone(inferred["requests"][0]["client_question"])
        bad = {**request, "request_type": "SOMETHING_ELSE"}
        with self.assertRaises(ValueError):
            build_economic_request_batch([bad])
        with self.assertRaises(ValueError):
            build_economic_request_batch([request] * 4)

    def test_persistence_validates_requests_and_keeps_rejected_actions_auditable(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            decision = _decision("OPERATIONALLY_NOT_JUSTIFIED", selected=[], considered=["ACT-01"])
            decision["blocking_constraint_ids"] = ["CONS-01"]
            constraint = {"constraint_id": "CONS-01", "category": "HYGIENE", "description": "Charge obligatoire.", "source_status": "EXPLICIT", "source_ref": "ART-01", "hard": True, "material": True, "affected_action_ids": ["ACT-01"]}
            packet = self._packet(decision=decision, requests=[{"request_type": "BAD", "client_question": "Avez-vous un document concernant ce coût ?", "internal_reason": "test", "target_role": "dirigeant", "decision_impact": "test", "expected_effort": "minime"}])
            packet["operational_constraints"] = [constraint]
            with self.assertRaises(ValueError):
                persist_economic_packet(case, packet)
            packet["economic_requests"] = []
            state = persist_economic_packet(case, packet)
            persisted = state["decisions"][0]
            self.assertEqual(persisted["selected_action_ids"], [])
            self.assertEqual(persisted["considered_action_ids"], ["ACT-01"])

    def test_hard_constraint_and_decision_contracts_remain_safety_checks(self) -> None:
        decision = _decision("ACT_NOW")
        validate_decision(decision, {"ACT-01"})
        with self.assertRaises(ValueError):
            validate_decision(_decision("OPERATIONALLY_NOT_JUSTIFIED", selected=[], considered=[]), {"ACT-01"})
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            constraint = {"constraint_id": "CONS-SAFE", "category": "SAFETY", "description": "Arrêt interdit sans professionnel.", "source_status": "EXPLICIT", "source_ref": "ART-01", "hard": True, "material": True, "affected_action_ids": ["ACT-01"]}
            with self.assertRaisesRegex(ValueError, "ne peut pas être ignorée"):
                persist_economic_packet(case, {**self._packet(), "operational_constraints": [constraint]})

    def test_unknown_economic_input_has_no_fake_value(self) -> None:
        unknown = {"input_id": "CAPEX", "kind": "capex", "provenance": "UNKNOWN", "status": "UNKNOWN", "value": None, "unknown_reason": "No quote available."}
        validate_economic_input(unknown)
        unknown["value"] = 1
        with self.assertRaises(ValueError):
            validate_economic_input(unknown)

    def test_b_a_to_b_o_are_real_structured_contract_fixtures(self) -> None:
        payload = json.loads((Path("examples") / "goal_b_1_fixtures.json").read_text(encoding="utf-8"))
        fixtures = payload["fixtures"]
        self.assertEqual({item["fixture_id"] for item in fixtures}, {f"B-{letter}" for letter in "ABCDEFGHIJKLMNO"})
        for fixture in fixtures:
            for item in fixture["economic_inputs"]:
                validate_economic_input(item)
            actions = fixture["candidate_actions"]
            action_ids = {item["action_id"] for item in actions}
            for action in actions:
                validate_candidate_action(action)
            for constraint in fixture["operational_constraints"]:
                validate_constraint(constraint)
            for relationship in fixture["relationships"]:
                validate_relationship(relationship, action_ids)
            validate_decision(fixture["decision"], action_ids)
            if fixture["economic_requests"]:
                build_economic_request_batch(fixture["economic_requests"])
            for effect in fixture["energy_effects"]:
                validate_energy_effect(effect)
            tables = {action["action_id"]: _calculation(effect) for action, effect in zip(actions, fixture["energy_effects"], strict=True)}
            if fixture["fixture_id"] == "B-F":
                with self.assertRaises(ValueError):
                    aggregate_declared_portfolio(["ACT-01", "ACT-02"], tables, fixture["relationships"])
            if fixture["fixture_id"] == "B-G":
                with self.assertRaises(ValueError):
                    aggregate_declared_portfolio(["ACT-01", "ACT-02"], tables, fixture["relationships"])

    def test_goal_a_to_goal_b_1_e2e_has_pre_reasoning_handoff_then_persisted_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = generate_goal_b_1_e2e(Path(directory))
            trace = json.loads((case / "investigation" / "goal_b_1_e2e_trace.json").read_text(encoding="utf-8"))
            contract = json.loads((case / "investigation" / "codex_economic_reasoning_contract.json").read_text(encoding="utf-8"))
            state = json.loads((case / "investigation" / "economic_decision_state.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["workflow"], ["Goal A evidence", "pre-reasoning economic handoff", "Codex reasoning contract", "deterministic scenario calculations", "persisted Goal B state"])
            self.assertEqual(contract["handoff_phase"], "pre_reasoning")
            self.assertEqual(state["decisions"][0]["decision"], "INVESTIGATE_FIRST")


if __name__ == "__main__":
    unittest.main()
