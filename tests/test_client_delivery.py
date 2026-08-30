from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from client_delivery import _range_or_exact, build_client_report_model, render_client_report_pdf, validate_client_report_model
from workspace.generate_goal_c_1_fixtures import generate


class ClientDeliveryC1Tests(unittest.TestCase):
    def _fixtures(self) -> tuple[dict[str, Path], tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        return generate(Path(temporary.name)), temporary

    @staticmethod
    def _model(case: Path) -> dict:
        return json.loads((case / "outputs/client_report/CLIENT_REPORT_MODEL.json").read_text(encoding="utf-8"))

    def test_all_c_a_to_c_j_are_real_executable_cases(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            self.assertEqual({f"C-{letter}" for letter in "ABCDEFGHIJ"}, {key for key in cases if key != "C-MULTI"})
            for case in cases.values():
                self.assertTrue((case / "investigation/economic_decision_state.json").is_file())
                self.assertTrue((case / "outputs/client_report/CLIENT_REPORT_MODEL.json").is_file())
                self.assertTrue((case / "outputs/client_report/ENERGY_ANALYSIS_REPORT.pdf").read_bytes().startswith(b"%PDF-1.4"))

    def test_fixture_properties_are_economic_and_operational_not_labels(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            state_a = json.loads((cases["C-A"] / "investigation/economic_decision_state.json").read_text())
            calc_a = next(iter(state_a["scenario_calculations"].values()))["scenarios"]["BASE"]
            self.assertGreater(calc_a["net_annual_benefit"], 0)
            state_c = json.loads((cases["C-C"] / "investigation/economic_decision_state.json").read_text())
            calc_c = next(iter(state_c["scenario_calculations"].values()))["scenarios"]["BASE"]
            self.assertGreater(calc_c["simple_payback_years"], 5)
            state_d = json.loads((cases["C-D"] / "investigation/economic_decision_state.json").read_text())
            self.assertEqual(state_d["decisions"][0]["decision"], "OPERATIONALLY_NOT_JUSTIFIED")
            self.assertTrue(state_d["decisions"][0]["blocking_constraint_ids"])
            state_f = json.loads((cases["C-F"] / "investigation/economic_decision_state.json").read_text())
            self.assertEqual(state_f["relationships"][0]["type"], "MUTUALLY_EXCLUSIVE")
            model_h = self._model(cases["C-H"])
            self.assertEqual(model_h["decision_cards"][0]["economic_impact"]["annual_net_benefit"]["kind"], "RANGE")

    def test_multiple_decisions_are_preserved_in_one_report(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            model = self._model(cases["C-MULTI"])
            self.assertEqual({"ACT_NOW", "INVESTIGATE_FIRST", "MONITOR", "OPERATIONALLY_NOT_JUSTIFIED"}, {item["decision"] for item in model["decision_cards"]})
            negative = next(item for item in model["decision_cards"] if item["decision"] == "OPERATIONALLY_NOT_JUSTIFIED")
            self.assertEqual(negative["considered_action_ref"], negative["action_ref"])
            self.assertTrue(negative["claim_refs"]["constraint_refs"])

    def test_negative_decision_is_structured_and_sourced(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            model = self._model(cases["C-D"])
            card = model["decision_cards"][0]
            self.assertEqual(card["decision"], "OPERATIONALLY_NOT_JUSTIFIED")
            self.assertIsNotNone(card["economic_impact"])
            self.assertTrue(card["operational_constraints"])
            self.assertEqual(card["claims"]["recommendation"]["claim_type"], "NO_ACTION_OPERATIONAL")

    def test_recommendation_claim_class_prevents_structured_contradiction(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-A"], self._model(cases["C-A"])
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["claims"]["recommendation"]["claim_type"] = "NO_ACTION_REQUIRED"
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, case)

    def test_unsupported_no_action_and_checked_claims_are_rejected(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-D"], self._model(cases["C-D"])
            changed = copy.deepcopy(model)
            changed["no_action_items"][0]["claim"]["finding_refs"] = ["FIND-DOES-NOT-EXIST"]
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, case)
            changed = copy.deepcopy(model)
            changed["what_we_checked"][0]["evidence_refs"] = ["DS-DOES-NOT-EXIST"]
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, case)

    def test_alternatives_include_decision_useful_economics_and_burden(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            group = self._model(cases["C-F"])["alternative_groups"][0]
            self.assertTrue(group["not_additive"])
            for option in group["options"]:
                self.assertIsNotNone(option["economic_impact"]["annual_net_benefit"])
                self.assertIsNotNone(option["economic_impact"]["intervention_cost"])
                self.assertIn("downtime", option)
                self.assertIn("operational_burden", option)
                self.assertIn("major_uncertainty", option)

    def test_true_no_finding_is_compact_and_has_no_fake_action(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            model = self._model(cases["C-E"])
            self.assertEqual(model["decision_cards"], [])
            self.assertEqual(model["executive_summary"]["recommended_actions"], 0)
            self.assertTrue(model["no_action_items"])
            pages = (cases["C-E"] / "outputs/client_report/ENERGY_ANALYSIS_REPORT.pdf").read_bytes().count(b"/Type /Page ")
            self.assertLessEqual(pages, 3)

    def test_render_revalidates_tampered_model(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-A"], self._model(cases["C-A"])
            model["decision_cards"][0]["economic_impact"]["annual_net_benefit"]["high"] += 1
            with self.assertRaises(ValueError):
                render_client_report_pdf(model, case / "outputs/client_report/CLIENT_REPORT_MODEL.json", Path(temporary.name) / "tampered.pdf", case_directory=case)

    def test_all_visible_metadata_is_sanitized(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-A"], self._model(cases["C-A"])
            for field in ("report_title", "analysis_period", "site_name"):
                changed = copy.deepcopy(model)
                changed["metadata"][field] = "/data/data/com.termux/files/home/ART-SECRET"
                with self.assertRaises(ValueError):
                    validate_client_report_model(changed, case)

    def test_every_major_client_facing_field_rejects_internal_leakage(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-D"], self._model(cases["C-D"])
            forbidden = "/home/user/FIND-SECRET"
            mutations = [
                lambda item: item["decision_cards"][0].__setitem__("headline", forbidden),
                lambda item: (item["decision_cards"][0]["claims"]["why_this_matters"].__setitem__("text", forbidden), item["decision_cards"][0].__setitem__("why_this_matters", forbidden)),
                lambda item: item["no_action_items"][0].__setitem__("title", forbidden),
                lambda item: item["what_we_checked"][0].__setitem__("text", forbidden),
                lambda item: item["charts"][0].__setitem__("caption", forbidden),
                lambda item: item["technical_appendix"]["sources"][0].__setitem__("label", forbidden),
                lambda item: item["technical_appendix"].__setitem__("method", forbidden),
                lambda item: item["decision_cards"][0]["operational_constraints"][0].__setitem__("description", forbidden),
            ]
            # `caption` is not a contract field: an unrendered injected field is
            # harmless.  The other visible fields must fail validation.
            for mutate in mutations[0:5] + mutations[5:]:
                changed = copy.deepcopy(model)
                mutate(changed)
                with self.assertRaises(ValueError):
                    validate_client_report_model(changed, case)

    def test_long_valid_narrative_reflows_without_overflow(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-A"], self._model(cases["C-A"])
            text = "Cette explication conserve le lien avec la décision et reste lisible pour le dirigeant. " * 7
            claim = model["decision_cards"][0]["claims"]["why_this_matters"]
            claim["text"] = text.strip()
            model["decision_cards"][0]["why_this_matters"] = claim["text"]
            output = Path(temporary.name) / "long.pdf"
            rendered = render_client_report_pdf(model, case / "outputs/client_report/CLIENT_REPORT_MODEL.json", output, case_directory=case)
            self.assertTrue(output.exists())
            self.assertLessEqual(rendered["page_count"], 8)

    def test_precise_economics_stays_precise(self) -> None:
        exact = _range_or_exact({name: {"net": 4320} for name in ("LOW", "BASE", "HIGH")}, field="net", currency="EUR", period="an")
        self.assertEqual(exact["display"], "€4 320/an")
        self.assertEqual(exact["kind"], "EXACT")

    def test_goal_b_response_update_is_visible_without_reasking(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            model = self._model(cases["C-J"])
            self.assertEqual(model["client_dialogue"]["pending_questions"], [])
            self.assertTrue(model["client_dialogue"]["resolved_goal_b_evidence_refs"])


if __name__ == "__main__":
    unittest.main()
