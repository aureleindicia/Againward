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
    publish_economic_request_batch,
    record_goal_b_evidence,
    validate_candidate_action,
    validate_constraint,
    validate_decision,
    validate_economic_input,
    validate_energy_effect,
    validate_relationship,
)
from energy_mvp.client_lifecycle import record_existing_data_exhaustion
from workspace.generate_goal_b_2_e2e import generate as generate_goal_b_2_e2e
from workspace.generate_goal_b_4_e2e import generate as generate_goal_b_4_e2e


SCENARIOS = ("LOW", "BASE", "HIGH")


def _input(identifier: str, value: float, unit: str, period: str, kind: str = "economic_input") -> dict:
    return {"input_id": identifier, "kind": kind, "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "DOCUMENT_EXTRACTED", "status": "KNOWN", "source": {"artifact_id": "ART-01"}, "confidence": "HIGH"}


def _assumption(identifier: str, value: float, unit: str, period: str) -> dict:
    return {"assumption_id": identifier, "description": "Hypothèse de scénario explicite.", "value": value, "unit": unit, "currency": "EUR", "period": period, "provenance": "SCENARIO_ASSUMPTION", "status": "SCENARIO", "source": {"method": "sensitivity"}}


def _effect(identifier: str = "EFF-01", baseline: str = "healthy reference") -> dict:
    return {"effect_id": identifier, "basis": "DIRECTLY_MEASURED_HISTORICAL_EXCESS", "baseline": baseline, "unit": "kWh/year", "period": "annual", "scenarios": {"LOW": 800.0, "BASE": 1000.0, "HIGH": 1200.0}, "finding_refs": ["FIND-01"], "source_refs": ["DS-001-01"]}


def _action(identifier: str = "ACT-01", effect: str = "EFF-01") -> dict:
    return {"action_id": identifier, "finding_ids": ["FIND-01"], "title": "Action proposée", "description": "Option formulée par Codex.", "action_type": "maintenance", "technical_rationale": "Finding associé.", "operational_rationale": "À planifier pendant maintenance.", "implementation_scope": "Équipement concerné.", "requires_professional_validation": True, "reversibility": "PARTIALLY_REVERSIBLE", "energy_effect_ref": effect, "validation_plan": {"metric": "kWh hors production", "expected_direction": "baisse", "comparison_window": "quatre semaines", "confounders": "production", "minimum_evidence": "baisse récurrente"}}


def _references(tariff: dict[str, str], capex: dict[str, str] | None = None, recurring: dict[str, str] | None = None) -> dict:
    refs = {"energy_effect": {s: ["FIND-01"] for s in SCENARIOS}, "tariff_per_kwh": {s: [tariff[s]] for s in SCENARIOS}}
    if capex is not None:
        refs["intervention_cost"] = {s: [capex[s]] for s in SCENARIOS}
    if recurring is not None:
        refs["recurring_cost"] = {s: [recurring[s]] for s in SCENARIOS}
    return refs


def _calculation(effect: dict | None = None, *, tariff: dict[str, float] | None = None, tariff_refs: dict[str, str] | None = None, capex: dict[str, float] | None = None, capex_refs: dict[str, str] | None = None, recurring: dict[str, float] | None = None, recurring_refs: dict[str, str] | None = None) -> dict:
    tariff = tariff or {s: .2 for s in SCENARIOS}
    tariff_refs = tariff_refs or {s: "TAR" for s in SCENARIOS}
    return calculate_economic_scenarios(effect or _effect(), tariff_per_kwh=tariff, intervention_cost=capex, recurring_cost=recurring, input_references=_references(tariff_refs, capex_refs, recurring_refs))


def _decision(kind: str = "ACT_NOW", selected: list[str] | None = None, considered: list[str] | None = None) -> dict:
    selected = ["ACT-01"] if selected is None else selected
    result = {"decision_id": "DEC-01", "decision": kind, "selected_action_ids": selected, "considered_action_ids": selected if considered is None else considered, "reason": "Jugement Codex sur les preuves disponibles.", "priority_reasoning": "Comparaison explicite sans score.", "technical_confidence": "MEDIUM", "economic_importance": "MEDIUM"}
    if kind == "INVESTIGATE_FIRST":
        result["evidence_acquisition"] = {"what_it_resolves": "cause concurrente", "decision_that_can_change": "agir ou non", "cost_or_burden": "test faible coût", "why_worth_it": "évite CAPEX inutile"}
    return result


class OperationalEconomicsB2Tests(unittest.TestCase):
    def _case(self) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        drop = root / "drop"
        drop.mkdir()
        (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
        create_client_case("case", root=root / "cases")
        case = root / "cases" / "case"
        ingest_client_drop(drop, case)
        inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
        self._real_artifact_id = inventory["artifacts"][0]["artifact_id"]
        self._real_dataset_id = inventory["artifacts"][0]["extracted_dataset_ids"][0]
        record_structured_findings(case, [{"finding_id": "FIND-01", "observation": "Excès confirmé.", "status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "confidence": "MEDIUM", "possible_explanations": ["A", "B"], "provenance": ["evidence/dataset_provenance.json"], "recommended_next_analytical_step": "Comparer régimes."}])
        record_existing_data_exhaustion(case, analysis_inventory_ref="derived/canonical_case.json", reviewed_sources=["evidence/intake_inventory.json", "investigation/structured_findings.json"])
        return case, directory

    def _packet(self, calculation: dict | None = None) -> dict:
        sources = [_input("TAR", .2, "EUR/kWh", "per_kwh"), _input("CAP", 300, "EUR", "one_off"), _input("REC", 20, "EUR/year", "annual")]
        for source in sources:
            source["source"] = {"source_refs": [self._real_artifact_id]}
        calculation = calculation or _calculation(capex={s: 300 for s in SCENARIOS}, capex_refs={s: "CAP" for s in SCENARIOS}, recurring={s: 20 for s in SCENARIOS}, recurring_refs={s: "REC" for s in SCENARIOS})
        return {"technical_finding_refs": [{"finding_id": "FIND-01", "technical_status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "technical_confidence": "MEDIUM", "provenance": "investigation/structured_findings.json"}], "economic_inputs": sources, "scenario_assumptions": [], "candidate_actions": [_action()], "operational_constraints": [], "relationships": [], "combined_effects": {}, "scenario_calculations": {"ACT-01": calculation}, "economic_requests": [], "decision": _decision()}

    def _no_finding_case(self, *, canonical: bool) -> tuple[Path, tempfile.TemporaryDirectory[str]]:
        directory = tempfile.TemporaryDirectory()
        root = Path(directory.name)
        drop = root / "drop"
        drop.mkdir()
        (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
        create_client_case("case", root=root / "cases")
        case = root / "cases" / "case"
        ingest_client_drop(drop, case)
        if canonical:
            record_structured_findings(case, [], no_finding={
                "what_was_analyzed": "Série énergie disponible.",
                "usable_period": "2026-01-01.",
                "operating_regimes": "Unique régime observé.",
                "limitations": "Période courte.",
                "monitoring_baseline_meaningful": False,
            })
        return case, directory

    @staticmethod
    def _no_finding_packet() -> dict:
        return {"technical_finding_refs": [], "economic_inputs": [], "scenario_assumptions": [], "candidate_actions": [], "operational_constraints": [], "relationships": [], "combined_effects": {}, "scenario_calculations": {}, "economic_requests": [], "decision": _decision("DO_NOTHING", selected=[], considered=[])}

    def test_calculation_rejects_value_that_does_not_match_referenced_input(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            calculation = _calculation(tariff={"LOW": .2, "BASE": 99.0, "HIGH": .2})
            with self.assertRaisesRegex(ValueError, "incohérente avec sa source"):
                persist_economic_packet(case, self._packet(calculation))

    def test_low_and_high_require_explicit_scenario_assumptions_when_they_differ(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            calculation = _calculation(tariff={"LOW": .18, "BASE": .2, "HIGH": .23}, tariff_refs={"LOW": "TAR-LOW", "BASE": "TAR", "HIGH": "TAR-HIGH"})
            packet = self._packet(calculation)
            packet["scenario_assumptions"] = [_assumption("TAR-LOW", .18, "EUR/kWh", "per_kwh"), _assumption("TAR-HIGH", .23, "EUR/kWh", "per_kwh")]
            state = persist_economic_packet(case, packet)
            self.assertEqual(state["scenario_calculations"]["ACT-01"]["scenarios"]["BASE"]["tariff_per_kwh"], .2)

    def test_numeric_provenance_rejects_wrong_unit_and_multiple_sources(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["economic_inputs"][0]["unit"] = "EUR/year"
            packet["economic_inputs"][0]["period"] = "annual"
            with self.assertRaises(ValueError):
                persist_economic_packet(case, packet)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-01"]["reproducibility"]["input_references"]["tariff_per_kwh"]["BASE"] = ["TAR", "TAR"]
            with self.assertRaisesRegex(ValueError, "exactement une source"):
                persist_economic_packet(case, packet)

    def test_packet_rejects_nonexistent_goal_a_finding_everywhere(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            for mutator in (
                lambda packet: packet["technical_finding_refs"][0].update({"finding_id": "FIND-DOES-NOT-EXIST"}),
                lambda packet: packet["candidate_actions"][0].update({"finding_ids": ["FIND-DOES-NOT-EXIST"]}),
                lambda packet: packet["scenario_calculations"]["ACT-01"]["reproducibility"]["energy_effect"].update({"finding_refs": ["FIND-DOES-NOT-EXIST"]}),
            ):
                packet = self._packet()
                mutator(packet)
                with self.assertRaises(ValueError):
                    persist_economic_packet(case, packet)

    def test_packet_rejects_unresolved_factual_economic_and_constraint_sources(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["economic_inputs"][0]["source"] = {"source_refs": ["ART-DOES-NOT-EXIST"]}
            with self.assertRaisesRegex(ValueError, "source Goal A inexistante"):
                persist_economic_packet(case, packet)
            packet = self._packet()
            packet["operational_constraints"] = [{"constraint_id": "CONS-01", "category": "PRODUCTION", "description": "Contrainte explicitement observée.", "source_status": "EXPLICIT", "source_ref": "ART-DOES-NOT-EXIST", "hard": True, "material": True, "affected_action_ids": ["ACT-01"]}]
            with self.assertRaisesRegex(ValueError, "source Goal A inexistante"):
                persist_economic_packet(case, packet)

    def test_goal_b_cannot_rewrite_goal_a_metadata_and_resolves_it_canonically(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            for field, value in (("technical_status", "CAUSE_CONFIRMED"), ("technical_confidence", "HIGH")):
                packet = self._packet()
                packet["technical_finding_refs"][0][field] = value
                with self.assertRaisesRegex(ValueError, "ne peut pas altérer"):
                    persist_economic_packet(case, packet)
            state = persist_economic_packet(case, self._packet())
            self.assertEqual(state["technical_finding_refs"], [{"finding_id": "FIND-01", "technical_status": "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN", "technical_confidence": "MEDIUM", "provenance": "investigation/structured_findings.json"}])

    def test_real_and_multisource_goal_a_provenance_builds_complete_chain(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["operational_constraints"] = [{"constraint_id": "CONS-01", "category": "PRODUCTION", "description": "Déduit du planning et de la série énergie.", "source_status": "INFERRED", "source_refs": [self._real_artifact_id, self._real_dataset_id], "hard": False, "material": True, "affected_action_ids": ["ACT-01"]}]
            state = persist_economic_packet(case, packet)
            chain = state["recommendation_provenance"]
            self.assertTrue(chain["chain_is_reference_validated"])
            self.assertEqual(chain["selected_action_chains"][0]["finding_ids"], ["FIND-01"])
            self.assertEqual(chain["selected_action_chains"][0]["constraint_ids"], ["CONS-01"])

    def test_combined_economic_effect_requires_real_value_source_and_exact_value(self) -> None:
        table = _calculation()
        relation = [{"relationship_id": "REL", "type": "OVERLAPPING", "action_a": "A", "action_b": "B", "rationale": "same load", "combined_effect_ref": "COMB"}]
        entry = {"effect_type": "ECONOMIC", "effect_id": "COMB", "unit": "EUR/year", "period": "annual", "baseline": table["baseline"], "currency": "EUR", "scenarios": {s: 200 for s in SCENARIOS}, "value_source_refs": {s: ["COMB-SOURCE"] for s in SCENARIOS}}
        source = _input("COMB-SOURCE", 200, "EUR/year", "annual", "combined_economic_effect")
        result = aggregate_declared_portfolio(["A", "B"], {"A": table, "B": table}, relation, combined_effects={"COMB": entry}, economic_value_sources=[source])
        self.assertEqual(result["net_annual_benefit"]["BASE"], 200.0)
        bad = copy.deepcopy(entry)
        bad["scenarios"]["BASE"] = 999999
        with self.assertRaisesRegex(ValueError, "incohérente avec sa source"):
            aggregate_declared_portfolio(["A", "B"], {"A": table, "B": table}, relation, combined_effects={"COMB": bad}, economic_value_sources=[source])
        with self.assertRaisesRegex(ValueError, "provenance inexistante"):
            aggregate_declared_portfolio(["A", "B"], {"A": table, "B": table}, relation, combined_effects={"COMB": entry}, economic_value_sources=[])

    def test_portfolio_remains_fail_closed_for_missing_relation_and_baseline(self) -> None:
        first = _calculation(_effect("EFF-A", "baseline A"))
        second = _calculation(_effect("EFF-B", "baseline B"))
        with self.assertRaisesRegex(ValueError, "UNKNOWN par omission"):
            aggregate_declared_portfolio(["A", "B"], {"A": first, "B": second}, [])
        relation = [{"relationship_id": "REL", "type": "INDEPENDENT", "action_a": "A", "action_b": "B", "rationale": "Codex relation."}]
        with self.assertRaisesRegex(ValueError, "Baselines différentes"):
            aggregate_declared_portfolio(["A", "B"], {"A": first, "B": second}, relation)
        relation[0]["baseline_resolution"] = {"status": "RECONCILED", "rationale": "Fenêtres réconciliées par Codex.", "source_refs": ["FIND-01"]}
        result = aggregate_declared_portfolio(["A", "B"], {"A": first, "B": second}, relation)
        self.assertIsNone(result["deterministic_decision"])

    def test_persistence_recalculates_and_rejects_invented_net_benefit(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-01"]["scenarios"]["BASE"]["net_annual_benefit"] = 99999
            with self.assertRaisesRegex(ValueError, "incohérent"):
                persist_economic_packet(case, packet)

    def test_unknown_input_never_carries_a_value(self) -> None:
        unknown = {"input_id": "UNKNOWN", "kind": "capex", "provenance": "UNKNOWN", "status": "UNKNOWN", "value": None, "unknown_reason": "Aucun devis."}
        validate_economic_input(unknown)
        unknown["value"] = 1
        with self.assertRaises(ValueError):
            validate_economic_input(unknown)

    def test_handovers_are_separate_and_e2e_order_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = generate_goal_b_2_e2e(Path(directory))
            trace = json.loads((case / "investigation" / "goal_b_2_e2e_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["workflow"], ["Goal A evidence", "pre-reasoning handoff", "Codex reasoning contract", "deterministic calculations", "persisted Goal B state", "optional resume handoff"])
            self.assertTrue((case / "investigation" / "economic_handoff_pre_reasoning.json").exists())
            self.assertTrue((case / "investigation" / "economic_handoff_resume.json").exists())
            self.assertNotEqual((case / "investigation" / "economic_handoff_pre_reasoning.json").read_text(), (case / "investigation" / "economic_handoff_resume.json").read_text())
            inventory = json.loads((case / "evidence" / "intake_inventory.json").read_text(encoding="utf-8"))
            actual_refs = {item["artifact_id"] for item in inventory["artifacts"]}
            state = json.loads((case / "investigation" / "economic_decision_state.json").read_text(encoding="utf-8"))
            for item in state["economic_inputs"]:
                self.assertTrue(set(item["source"]["source_refs"]) <= actual_refs)
            self.assertTrue(set(state["operational_constraints"][0]["source_refs"]) <= actual_refs)
            self.assertEqual(state["technical_finding_refs"][0]["technical_status"], "ANOMALY_CONFIRMED_CAUSE_UNCERTAIN")
            self.assertTrue(state["recommendation_provenance"]["chain_is_reference_validated"])

    def test_b_a_to_b_o_have_distinct_properties_not_just_labels(self) -> None:
        fixtures = json.loads((Path("examples") / "goal_b_2_fixtures.json").read_text(encoding="utf-8"))["fixtures"]
        self.assertEqual({fixture["fixture_id"] for fixture in fixtures}, {f"B-{letter}" for letter in "ABCDEFGHIJKLMNO"})
        by_id = {fixture["fixture_id"]: fixture for fixture in fixtures}
        calculations: dict[str, dict[str, dict]] = {}
        for fixture in fixtures:
            for item in fixture["economic_inputs"]:
                validate_economic_input(item)
            for effect in fixture["energy_effects"]:
                validate_energy_effect(effect)
            actions = fixture["candidate_actions"]
            action_ids = {action["action_id"] for action in actions}
            for action in actions:
                validate_candidate_action(action)
            for constraint in fixture["operational_constraints"]:
                validate_constraint(constraint)
            for relationship in fixture["relationships"]:
                validate_relationship(relationship, action_ids)
            validate_decision(fixture["decision"], action_ids)
            if fixture["economic_requests"]:
                build_economic_request_batch(fixture["economic_requests"])
            effects = {effect["effect_id"]: effect for effect in fixture["energy_effects"]}
            calculations[fixture["fixture_id"]] = {}
            for action_id, spec in fixture["calculation_specs"].items():
                calculations[fixture["fixture_id"]][action_id] = calculate_economic_scenarios(effects[spec["effect_id"]], tariff_per_kwh=spec["tariff_per_kwh"], intervention_cost=spec.get("intervention_cost"), recurring_cost=spec.get("recurring_cost"), input_references=spec["input_references"])

        self.assertGreater(calculations["B-A"]["ACT-A"]["scenarios"]["BASE"]["net_annual_benefit"], 0)
        self.assertLess(calculations["B-A"]["ACT-A"]["scenarios"]["BASE"]["simple_payback_years"], 1)
        self.assertGreater(calculations["B-B"]["ACT-B-REPLACE"]["scenarios"]["BASE"]["intervention_cost"], 10 * 350)
        self.assertGreater(calculations["B-C"]["ACT-C"]["scenarios"]["BASE"]["simple_payback_years"], 30)
        self.assertTrue(by_id["B-D"]["operational_constraints"][0]["hard"])
        self.assertEqual(by_id["B-D"]["operational_constraints"][0]["affected_action_ids"], ["ACT-D"])
        self.assertEqual(by_id["B-E"]["energy_effects"], [])
        self.assertTrue(by_id["B-E"]["operational_constraints"][0]["hard"])
        with self.assertRaises(ValueError):
            aggregate_declared_portfolio(["ACT-F1", "ACT-F2"], calculations["B-F"], by_id["B-F"]["relationships"])
        with self.assertRaises(ValueError):
            aggregate_declared_portfolio(["ACT-G-R", "ACT-G-X"], calculations["B-G"], by_id["B-G"]["relationships"])
        self.assertTrue(by_id["B-H"]["operational_constraints"][0]["material"])
        low = calculations["B-I"]["ACT-I"]["scenarios"]["LOW"]["simple_payback_years"]
        high = calculations["B-I"]["ACT-I"]["scenarios"]["HIGH"]["simple_payback_years"]
        self.assertGreater(low / high, 5)
        self.assertLess(by_id["B-L"]["operating_evidence"]["naive_raw_energy_delta_kwh"], 0)
        self.assertGreater(by_id["B-L"]["operating_evidence"]["production_adjusted_excess_kwh"], 0)
        gross_m = calculations["B-M"]["ACT-M"]["scenarios"]["BASE"]["gross_annual_energy_cost_avoided"]
        net_m = calculations["B-M"]["ACT-M"]["scenarios"]["BASE"]["net_annual_benefit"]
        self.assertGreater(gross_m, net_m)
        self.assertGreater(net_m, 0)
        self.assertLessEqual(calculations["B-N"]["ACT-N"]["scenarios"]["BASE"]["net_annual_benefit"], 0)
        self.assertEqual(len(by_id["B-O"]["economic_requests"]), 0)
        self.assertIsNotNone(calculations["B-O"]["ACT-O"]["scenarios"]["BASE"]["net_annual_benefit"])
        self.assertEqual(by_id["B-J"]["goal_a_case"]["findings"], [])
        self.assertTrue(by_id["B-J"]["goal_a_case"]["no_finding"]["monitoring_baseline_meaningful"])

    def test_controlled_requests_and_time_of_use_remain_non_decisional(self) -> None:
        inferred = build_economic_request_batch([{"request_type": "INFER_AUTOMATICALLY", "internal_reason": "Document déjà disponible.", "decision_impact": "Éviter une question."}])
        self.assertIsNone(inferred["requests"][0]["client_question"])
        with self.assertRaises(ValueError):
            build_economic_request_batch([{"request_type": "UNKNOWN", "client_question": "Texte suffisamment long", "internal_reason": "x", "target_role": "x", "decision_impact": "x", "expected_effort": "x"}])
        request = {"request_type": "REQUEST_QUOTE", "client_question": "Avez-vous un devis récent pour cette intervention ?", "internal_reason": "CAPEX matériel.", "target_role": "dirigeant", "decision_impact": "Comparer options.", "expected_effort": "Envoyer un document."}
        with self.assertRaises(ValueError):
            build_economic_request_batch([request] * 4)
        result = calculate_time_aligned_savings_with_tariff_plan([{"timestamp": "2026-01-05T01:00:00", "energy_saving_kwh": 10}], {"currency": "EUR", "flat_price_per_kwh": .2})
        self.assertEqual(result["time_aligned_cost_saving"], 2.0)

    def test_deterministic_scenarios_keep_units_and_never_emit_false_payback(self) -> None:
        calculation = _calculation(
            _effect(), capex={s: 300 for s in SCENARIOS}, capex_refs={s: "CAP" for s in SCENARIOS},
            recurring={s: 20 for s in SCENARIOS}, recurring_refs={s: "REC" for s in SCENARIOS},
        )
        self.assertEqual(calculation["scenarios"]["BASE"]["gross_annual_energy_cost_avoided"], 200.0)
        self.assertEqual(calculation["scenarios"]["BASE"]["net_annual_benefit"], 180.0)
        effect_mwh = _effect()
        effect_mwh.update({"unit": "MWh/year", "scenarios": {"LOW": 1, "BASE": 2, "HIGH": 3}})
        self.assertEqual(_calculation(effect_mwh)["scenarios"]["BASE"]["annual_energy_saving_kwh"], 2000.0)
        unknown = calculate_economic_scenarios(
            _effect(), tariff_per_kwh=None,
            intervention_cost={s: 100 for s in SCENARIOS},
            input_references={"energy_effect": {s: ["FIND-01"] for s in SCENARIOS}, "intervention_cost": {s: ["CAP"] for s in SCENARIOS}},
        )
        self.assertIsNone(unknown["scenarios"]["BASE"]["gross_annual_energy_cost_avoided"])
        negative = _calculation(
            recurring={s: 300 for s in SCENARIOS}, recurring_refs={s: "REC" for s in SCENARIOS},
        )
        self.assertLess(negative["scenarios"]["BASE"]["net_annual_benefit"], 0)
        self.assertIsNone(negative["scenarios"]["BASE"]["simple_payback_years"])

    def test_combined_energy_is_recalculated_and_exclusive_paths_are_not_summed(self) -> None:
        individual = _calculation()
        combined_effect = _effect("EFF-C")
        combined = _calculation(combined_effect)
        relation = [{"relationship_id": "REL", "type": "OVERLAPPING", "action_a": "A", "action_b": "B", "rationale": "Same physical load.", "combined_effect_ref": "COMB"}]
        entry = {"effect_type": "ENERGY", "energy_effect": combined_effect, "economic_calculation": combined}
        tariff_source = _input("TAR", .2, "EUR/kWh", "per_kwh")
        result = aggregate_declared_portfolio(
            ["A", "B"], {"A": individual, "B": individual}, relation,
            combined_effects={"COMB": entry}, economic_value_sources=[tariff_source],
        )
        self.assertEqual(result["net_annual_benefit"]["BASE"], 200.0)
        for relationship_type in ("MUTUALLY_EXCLUSIVE", "ALTERNATIVE", "UNKNOWN", "SEQUENTIAL"):
            item = {"relationship_id": "REL", "type": relationship_type, "action_a": "A", "action_b": "B", "rationale": "Not additive."}
            if relationship_type == "SEQUENTIAL":
                item["sequence"] = ["A", "B"]
            with self.assertRaises(ValueError):
                aggregate_declared_portfolio(["A", "B"], {"A": individual, "B": individual}, [item])

    def test_pre_reasoning_handoff_contains_real_goal_a_context_before_packet(self) -> None:
        case, directory = self._case()
        with directory:
            handoff = economic_handoff(case)
            self.assertEqual(handoff["phase"], "pre_reasoning")
            self.assertEqual(handoff["technical_findings"][0]["finding_id"], "FIND-01")
            self.assertIsNone(handoff["existing_economic_state"])
            self.assertTrue((case / "investigation" / "economic_handoff_pre_reasoning.json").exists())

    def test_persistence_rejects_unknown_action_and_preserves_safety_and_rejected_action_audit(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["scenario_calculations"]["ACT-MISSING"] = packet["scenario_calculations"].pop("ACT-01")
            with self.assertRaisesRegex(ValueError, "action candidate existante"):
                persist_economic_packet(case, packet)
            safety = {"constraint_id": "CONS-SAFE", "category": "SAFETY", "description": "Arrêt interdit sans professionnel.", "source_status": "EXPLICIT", "source_ref": self._real_artifact_id, "hard": True, "material": True, "affected_action_ids": ["ACT-01"]}
            with self.assertRaisesRegex(ValueError, "ne peut pas être ignorée"):
                persist_economic_packet(case, {**self._packet(), "operational_constraints": [safety]})
            rejected = _decision("OPERATIONALLY_NOT_JUSTIFIED", selected=[], considered=["ACT-01"])
            rejected["blocking_constraint_ids"] = ["CONS-SAFE"]
            state = persist_economic_packet(case, {**self._packet(), "operational_constraints": [safety], "decision": rejected})
            self.assertEqual(state["decisions"][0]["selected_action_ids"], [])
            self.assertEqual(state["decisions"][0]["considered_action_ids"], ["ACT-01"])

    def test_time_aligned_calculation_remains_measurement_not_recommendation(self) -> None:
        result = calculate_time_aligned_savings(
            [{"timestamp": "2026-01-01T01:00:00", "energy_saving_kwh": 10}, {"timestamp": "2026-01-01T18:00:00", "energy_saving_kwh": 4}],
            price_for_timestamp=lambda timestamp: .1 if "T01" in timestamp else .3,
        )
        self.assertAlmostEqual(result["time_aligned_cost_saving"], 2.2)

    def test_true_goal_a_no_finding_allows_only_empty_do_nothing_packet(self) -> None:
        case, directory = self._no_finding_case(canonical=True)
        with directory:
            initialize_economic_state(case)
            state = persist_economic_packet(case, self._no_finding_packet())
            self.assertEqual(state["decisions"][0]["decision"], "DO_NOTHING")
            self.assertEqual(state["technical_finding_refs"], [])
            self.assertEqual(state["candidate_actions"], [])
            self.assertEqual(state["decisions"][0]["considered_action_ids"], [])

    def test_empty_findings_without_canonical_no_finding_cannot_bypass_contract(self) -> None:
        case, directory = self._no_finding_case(canonical=False)
        with directory:
            initialize_economic_state(case)
            with self.assertRaisesRegex(ValueError, "finding Goal A réel"):
                persist_economic_packet(case, self._no_finding_packet())

    def test_goal_b_client_quote_is_persistent_evidence_for_exact_economic_input(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            request = {"request_id": "ECO-REQ-QUOTE", "request_type": "REQUEST_QUOTE", "client_question": "Pouvez-vous transmettre le devis récent de cette intervention ?", "internal_reason": "Le CAPEX conditionne la comparaison économique.", "target_role": "dirigeant", "decision_impact": "Comparer coût et bénéfice.", "expected_effort": "Envoyer le devis."}
            request.update({"related_hypothesis_ids": ["H-CAPEX"], "hypotheses_distinguished": ["CAPEX compatible", "CAPEX incompatible"], "plausible_answers": [{"answer_id": "LOW", "label": "Devis compatible", "decision_effects": ["L'action peut rester rentable."]}, {"answer_id": "HIGH", "label": "Devis trop élevé", "decision_effects": ["L'action peut être différée."]}], "decision_impact_dimensions": ["economic_materiality"], "effort": 1, "availability": .9, "reliability": .9, "expected_source_type": "EXISTING_DOCUMENT"})
            publish_economic_request_batch(case, [request])
            first = self._packet()
            first["economic_requests"] = [request]
            persist_economic_packet(case, first)
            recorded = record_goal_b_evidence(case, {"evidence_id": "GBE-QUOTE-01", "evidence_type": "GOAL_B_CLIENT_RESPONSE", "content": {"response_text": "Le devis est de 450 EUR."}, "structured_value": {"value": 450, "unit": "EUR", "currency": "EUR", "period": "one_off"}, "request_id": "ECO-REQ-QUOTE"})
            self.assertEqual(recorded["acquisition_order"], 1)
            calculation = _calculation(capex={s: 450 for s in SCENARIOS}, capex_refs={s: "CAP-QUOTE" for s in SCENARIOS})
            packet = self._packet(calculation)
            packet["economic_inputs"] = [item for item in packet["economic_inputs"] if item["input_id"] != "CAP"] + [{"input_id": "CAP-QUOTE", "kind": "supplier_quote", "value": 450, "unit": "EUR", "currency": "EUR", "period": "one_off", "provenance": "CLIENT_EXPLICIT", "status": "KNOWN", "source": {"goal_b_evidence_refs": ["GBE-QUOTE-01"]}, "confidence": "HIGH"}]
            del packet["economic_requests"]
            state = persist_economic_packet(case, packet)
            self.assertEqual(state["scenario_calculations"]["ACT-01"]["scenarios"]["BASE"]["intervention_cost"], 450.0)
            self.assertEqual(state["goal_b_evidence"][0]["evidence_id"], "GBE-QUOTE-01")

    def test_goal_b_operational_answer_survives_resume_and_supports_constraint(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            request = {"request_id": "ECO-REQ-DOWNTIME", "request_type": "ASK_CLIENT", "client_question": "La machine peut-elle être arrêtée pendant les heures de production ?", "internal_reason": "La contrainte d'arrêt conditionne l'intervention.", "target_role": "responsable site", "decision_impact": "Planifier ou différer.", "expected_effort": "Réponse simple."}
            request.update({"related_hypothesis_ids": ["H-DOWNTIME"], "hypotheses_distinguished": ["arrêt possible", "arrêt impossible"], "plausible_answers": [{"answer_id": "YES", "label": "Arrêt possible", "decision_effects": ["Planifier en production."]}, {"answer_id": "NO", "label": "Arrêt impossible", "decision_effects": ["Planifier hors production."]}], "decision_impact_dimensions": ["field_action"], "effort": 1, "availability": .9, "reliability": .7})
            publish_economic_request_batch(case, [request])
            first = self._packet()
            first["economic_requests"] = [request]
            persist_economic_packet(case, first)
            record_goal_b_evidence(case, {"evidence_id": "GBE-DOWNTIME-01", "evidence_type": "GOAL_B_CLIENT_RESPONSE", "content": {"response_text": "La machine ne peut pas s'arrêter pendant la production."}, "request_id": "ECO-REQ-DOWNTIME"})
            resumed = economic_handoff(case)
            self.assertEqual(resumed["phase"], "resume_reasoning")
            self.assertEqual(resumed["existing_economic_state"]["goal_b_evidence"][0]["evidence_id"], "GBE-DOWNTIME-01")
            packet = self._packet()
            packet["operational_constraints"] = [{"constraint_id": "CONS-DOWNTIME", "category": "PRODUCTION", "description": "La machine ne peut pas s'arrêter pendant la production.", "source_status": "EXPLICIT", "goal_b_evidence_refs": ["GBE-DOWNTIME-01"], "hard": True, "material": True, "affected_action_ids": ["ACT-01"]}]
            packet["decision"]["constraint_assessments"] = [{"constraint_id": "CONS-DOWNTIME", "disposition": "MITIGATED", "rationale": "Intervention prévue hors production."}]
            del packet["economic_requests"]
            state = persist_economic_packet(case, packet)
            self.assertEqual(state["operational_constraints"][0]["goal_b_evidence_refs"], ["GBE-DOWNTIME-01"])

    def test_nonexistent_goal_b_evidence_and_irrelevant_source_are_rejected(self) -> None:
        case, directory = self._case()
        with directory:
            initialize_economic_state(case)
            packet = self._packet()
            packet["economic_inputs"][0]["provenance"] = "CLIENT_EXPLICIT"
            packet["economic_inputs"][0]["source"] = {"goal_b_evidence_refs": ["GBE-MISSING"]}
            with self.assertRaisesRegex(ValueError, "preuve Goal B inexistante"):
                persist_economic_packet(case, packet)
            inventory_path = case / "evidence" / "intake_inventory.json"
            inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            inventory["artifacts"][0]["probable_role"] = "IRRELEVANT"
            inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "IRRELEVANT"):
                persist_economic_packet(case, self._packet())

    def test_goal_b4_e2e_preserves_request_response_evidence_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = generate_goal_b_4_e2e(Path(directory))
            trace = json.loads((case / "investigation" / "goal_b_4_e2e_trace.json").read_text(encoding="utf-8"))
            self.assertEqual(trace["workflow"], ["Goal A evidence", "pre-reasoning handoff", "Codex reasoning contract", "economic request", "client response", "persistent Goal B evidence", "resume handoff", "deterministic calculations", "persisted Goal B state"])
            state = json.loads((case / "investigation" / "economic_decision_state.json").read_text(encoding="utf-8"))
            self.assertEqual([item["evidence_id"] for item in state["goal_b_evidence"]], ["GBE-QUOTE-01", "GBE-DOWNTIME-01"])
            quote_input = next(item for item in state["economic_inputs"] if item["input_id"] == "CAP-QUOTE-01")
            self.assertEqual(quote_input["source"]["goal_b_evidence_refs"], ["GBE-QUOTE-01"])
            self.assertEqual(state["operational_constraints"][0]["goal_b_evidence_refs"], ["GBE-DOWNTIME-01"])
            resume = json.loads((case / "investigation" / "economic_handoff_resume.json").read_text(encoding="utf-8"))
            self.assertEqual(len(resume["existing_economic_state"]["goal_b_evidence"]), 2)


if __name__ == "__main__":
    unittest.main()
