from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

from client_delivery import _range_or_exact, build_client_report_model, generate_client_report, validate_client_report_model
from workspace.generate_goal_c_e2e import _narrative, _no_finding_narrative, generate


class ClientDeliveryTests(unittest.TestCase):
    def _cases(self) -> tuple[Path, Path, tempfile.TemporaryDirectory[str]]:
        temporary = tempfile.TemporaryDirectory()
        main, no_finding = generate(Path(temporary.name))
        return main, no_finding, temporary

    def test_e2e_pdf_is_short_client_safe_and_has_a_real_chart(self) -> None:
        main, no_finding, temporary = self._cases()
        with temporary:
            main_pdf = main / "outputs" / "client_report" / "ENERGY_ANALYSIS_REPORT.pdf"
            no_pdf = no_finding / "outputs" / "client_report" / "ENERGY_ANALYSIS_REPORT.pdf"
            for pdf in (main_pdf, no_pdf):
                raw = pdf.read_bytes()
                self.assertTrue(raw.startswith(b"%PDF-1.4"))
                self.assertGreaterEqual(raw.count(b"/Type /Page "), 3)
                self.assertLessEqual(raw.count(b"/Type /Page "), 8)
                self.assertNotIn(b"ART-", raw)
                self.assertNotIn(b"FIND-", raw)
                self.assertNotIn(b"/data/data", raw)
            model = json.loads((main / "outputs" / "client_report" / "CLIENT_REPORT_MODEL.json").read_text(encoding="utf-8"))
            self.assertEqual(len(model["charts"]), 1)
            self.assertTrue((main / "outputs" / "client_report" / model["charts"][0]["relative_path"]).exists())

    def test_claim_fidelity_rejects_stronger_decision_increased_saving_and_omitted_constraint(self) -> None:
        main, _, temporary = self._cases()
        with temporary:
            model = json.loads((main / "outputs" / "client_report" / "CLIENT_REPORT_MODEL.json").read_text(encoding="utf-8"))
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["decision"] = "INVESTIGATE_FIRST"
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, main)
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["economic_impact"]["annual_net_benefit"]["high"] += 1
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, main)
            changed = copy.deepcopy(model)
            changed["decision_cards"][0]["operational_constraints"] = []
            with self.assertRaises(ValueError):
                validate_client_report_model(changed, main)

    def test_true_no_finding_has_no_actions_or_savings(self) -> None:
        _, no_finding, temporary = self._cases()
        with temporary:
            model = json.loads((no_finding / "outputs" / "client_report" / "CLIENT_REPORT_MODEL.json").read_text(encoding="utf-8"))
            self.assertEqual(model["decision_cards"], [])
            self.assertEqual(model["executive_summary"]["recommended_actions"], 0)
            self.assertIsNone(model["executive_summary"]["economic_total"])
            self.assertTrue(model["no_action_items"])

    def test_goal_b_response_is_preserved_and_answered_questions_are_not_reasked(self) -> None:
        from workspace.generate_goal_b_4_e2e import generate as generate_b4
        with tempfile.TemporaryDirectory() as temporary:
            case = generate_b4(Path(temporary))
            dataset_id = json.loads((case / "derived" / "canonical_case.json").read_text(encoding="utf-8"))["available_datasets"][0]["dataset_id"]
            narrative = {"site_name": "Atelier", "executive_message": "Une vérification ciblée reste préférable avant toute intervention importante.", "cards": {"ACT-INSPECT-01": {"headline": "Inspection ciblée", "what_we_found": "Une charge subsiste avant le démarrage de la production.", "why_this_matters": "Cette charge peut générer un coût sans service utile clairement établi.", "recommendation": "Planifier une inspection hors production.", "uncertainty": "La cause physique précise reste à confirmer."}}, "no_action_items": [], "what_we_checked": ["Le contexte de production disponible"], "chart_requests": [{"type": "ENERGY_SERIES", "dataset_id": dataset_id, "title": "Profil de consommation", "purpose": "Le profil soutient la vérification proposée."}], "limitations": ["La période disponible est courte."]}
            model = build_client_report_model(case, narrative, output_directory=Path(temporary) / "report")
            self.assertEqual(model["client_dialogue"]["pending_questions"], [])
            self.assertEqual(set(model["client_dialogue"]["resolved_goal_b_evidence_refs"]), {"GBE-QUOTE-01", "GBE-DOWNTIME-01"})

    def test_fixture_catalog_covers_all_required_delivery_situations(self) -> None:
        fixtures = json.loads((Path("examples") / "goal_c_fixtures.json").read_text(encoding="utf-8"))["fixtures"]
        self.assertEqual({item["fixture_id"] for item in fixtures}, {f"C-{letter}" for letter in "ABCDEFGHIJ"})
        self.assertTrue(next(item for item in fixtures if item["fixture_id"] == "C-F")["expected"]["not_additive"])
        self.assertEqual(next(item for item in fixtures if item["fixture_id"] == "C-E")["expected"]["goal_a_findings"], 0)

    def test_exact_and_range_claims_are_not_reformatted_as_false_precision(self) -> None:
        main, _, temporary = self._cases()
        with temporary:
            model = json.loads((main / "outputs" / "client_report" / "CLIENT_REPORT_MODEL.json").read_text(encoding="utf-8"))
            claim = model["decision_cards"][0]["economic_impact"]["annual_net_benefit"]
            self.assertEqual(claim["kind"], "RANGE")
            self.assertIn("–", claim["display"])
            self.assertIsNone(claim["scenario_used_as_expected"])

    def test_precise_and_wide_economic_contracts_follow_the_source_scenarios(self) -> None:
        exact = _range_or_exact({name: {"net": 4320} for name in ("LOW", "BASE", "HIGH")}, field="net", currency="EUR", period="an")
        wide = _range_or_exact({"LOW": {"net": 1200}, "BASE": {"net": 3600}, "HIGH": {"net": 7200}}, field="net", currency="EUR", period="an")
        self.assertEqual(exact["kind"], "EXACT")
        self.assertEqual(exact["display"], "€4 320/an")
        self.assertEqual(wide["kind"], "RANGE")
        self.assertEqual(wide["display"], "€1 200–€7 200/an")
        self.assertIsNone(wide["scenario_used_as_expected"])


if __name__ == "__main__":
    unittest.main()
