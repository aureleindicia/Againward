from __future__ import annotations

import copy
import csv
import json
import tempfile
import unittest
from pathlib import Path

from client_delivery import _range_or_exact, _resolve_chart_requests, build_client_report_model, render_client_report_pdf, validate_client_report_model
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
            self.assertEqual(card["client_directive"], "Action non recommandée dans les conditions actuelles")
            self.assertEqual(card["claims"]["contextual_rationale"]["claim_type"], "CONTEXTUAL_RATIONALE")
            self.assertIsNone(card["next_step"])

    def test_free_context_cannot_reverse_deterministic_directive(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-A"], self._model(cases["C-A"])
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["claims"]["contextual_rationale"]["text"] = "Ne réalisez aucune intervention avant une nouvelle décision."
            changed["decision_cards"][0]["contextual_rationale"] = changed["decision_cards"][0]["claims"]["contextual_rationale"]["text"]
            validate_client_report_model(changed, case)
            self.assertEqual(changed["decision_cards"][0]["client_directive"], "Action recommandée")
            self.assertNotIn("recommendation", changed["decision_cards"][0])

    def test_cross_action_economic_and_constraint_references_are_rejected(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case, model = cases["C-F"], self._model(cases["C-F"])
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["claim_refs"]["economic_calculation_refs"] = ["A-C-F-REPLACE"]
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, case)

            case, model = cases["C-MULTI"], self._model(cases["C-MULTI"])
            card = next(item for item in model["decision_cards"] if item["action_ref"] == "A-MULTI-NOW")
            card["claim_refs"]["constraint_refs"] = ["K-MULTI-OPS"]
            card["operational_constraints"] = [{"constraint_ref": "K-MULTI-OPS", "description": "Les horaires de production ne peuvent pas être déplacés sans perte de fraîcheur.", "hard": True, "material": True}]
            with self.assertRaises(ValueError):
                validate_client_report_model(model, case)

    def test_local_action_provenance_and_decision_aware_next_steps(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            model = self._model(cases["C-A"])
            card = model["decision_cards"][0]
            self.assertEqual(card["claim_refs"]["economic_calculation_refs"], [card["action_ref"]])
            self.assertEqual(card["next_step"]["kind"], "POST_ACTION_VALIDATION")
            self.assertEqual(card["next_step"]["title"], "Comment vérifier après action")
            model = self._model(cases["C-B"])
            self.assertEqual(model["decision_cards"][0]["next_step"]["kind"], "PRE_INVESTMENT_VERIFICATION")
            self.assertIn("avant d'investir", model["decision_cards"][0]["next_step"]["title"])
            model = self._model(cases["C-MULTI"])
            monitor = next(item for item in model["decision_cards"] if item["decision"] == "MONITOR")
            self.assertEqual(monitor["next_step"]["kind"], "MONITORING")
            self.assertIn("surveiller", monitor["next_step"]["title"].lower())
            negative = next(item for item in model["decision_cards"] if item["decision"] == "OPERATIONALLY_NOT_JUSTIFIED")
            self.assertIsNone(negative["next_step"])

    def test_binary_operational_context_uses_background_bands_not_interpolation(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            chart = self._model(cases["C-A"])["charts"][0]
            self.assertEqual(chart["operation_encoding"], "BACKGROUND_BANDS")
            self.assertIn("bandes orange", chart["legend"])
            self.assertTrue((cases["C-A"] / "outputs/client_report" / chart["relative_path"]).is_file())

    @staticmethod
    def _chart_request(chart_type: str, dataset_id: str) -> dict:
        return {"chart_requests": [{"type": chart_type, "dataset_id": dataset_id, "title": "Consommation et contexte", "purpose": "Le graphique compare la consommation aux régimes réellement disponibles."}]}

    def test_operation_context_requires_real_goal_a_source(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case = cases["C-A"]
            canonical_path = case / "derived/canonical_case.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            dataset = canonical["available_datasets"][0]
            dataset["field_lineage"].pop("production")
            canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "source Goal A explicite"):
                _resolve_chart_requests(case, self._chart_request("ENERGY_WITH_OPERATION_STATUS", dataset["dataset_id"]), Path(temporary.name) / "no-context")

    def test_missing_operational_values_remain_unknown_not_inactive(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case = cases["C-A"]
            canonical_path = case / "derived/canonical_case.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            dataset = canonical["available_datasets"][0]
            dataset["data_quality"]["production_coverage_ratio"] = 0.8
            canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
            normalized = case / dataset["normalized_file"]
            with normalized.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
                fields = list(rows[0])
            rows[1]["production"] = ""
            with normalized.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            charts = _resolve_chart_requests(case, self._chart_request("ENERGY_WITH_OPERATION_STATUS", dataset["dataset_id"]), Path(temporary.name) / "unknown-status")
            self.assertEqual(charts[0]["operation_context"]["unknown_interval_count"], 1)
            self.assertIn("statut inconnu", charts[0]["legend"])
            self.assertEqual(charts[0]["operation_encoding"], "BACKGROUND_BANDS")

    def test_energy_only_chart_has_no_operational_bands_without_source(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            case = cases["C-A"]
            canonical_path = case / "derived/canonical_case.json"
            canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
            dataset = canonical["available_datasets"][0]
            dataset["field_lineage"].pop("production")
            canonical_path.write_text(json.dumps(canonical), encoding="utf-8")
            charts = _resolve_chart_requests(case, self._chart_request("ENERGY_SERIES", dataset["dataset_id"]), Path(temporary.name) / "energy-only")
            self.assertEqual(charts[0]["operation_encoding"], "NONE")
            self.assertIsNone(charts[0]["operation_context"])
            self.assertNotIn("activité/production", charts[0]["legend"])

    def test_sme_contextual_tradeoffs_are_specific(self) -> None:
        cases, temporary = self._fixtures()
        with temporary:
            c_d = self._model(cases["C-D"])["decision_cards"][0]["why_this_matters"].lower()
            c_i = self._model(cases["C-I"])["decision_cards"][0]["why_this_matters"].lower()
            self.assertIn("fraîcheur", c_d)
            self.assertIn("quotidienne", c_d)
            self.assertIn("petit gain", c_i)
            self.assertIn("personnel", c_i)

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
