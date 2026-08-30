from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from client_intake_pipeline import (
    create_client_case,
    ingest_client_drop,
    publish_question_batch,
    record_structured_findings,
)


class ClientIntakePipelineTests(unittest.TestCase):
    def _case(self, root: Path, drop_name: str = "drop") -> tuple[Path, Path]:
        drop = root / drop_name
        drop.mkdir()
        case_root = root / "cases"
        create_client_case("small_shop", root=case_root)
        return drop, case_root / "small_shop"

    def _ingest(self, drop: Path, case: Path) -> dict:
        return ingest_client_drop(drop, case)

    def test_case_a_messy_excel_extracts_hidden_useful_table_with_lineage(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            workbook = Workbook()
            notes = workbook.active
            notes.title = "Notes commerciales"
            notes.append(["Contact", "Mme Martin"])
            sheet = workbook.create_sheet("Relevé kWh")
            sheet.append([])
            sheet.append(["Export compteur atelier"])
            sheet.append([])
            sheet.append(["Date", "Conso", "Production"])
            sheet.append(["01/01/2026 00:00", "1,50", "0"])
            sheet.append(["01/01/2026 00:30", "1,25", "0"])
            sheet.append(["01/01/2026 00:30", "1,25", "0"])
            sheet.append(["TOTAL", "2,75", "0"])
            workbook.save(drop / "export_awkward.xlsx")

            canonical = self._ingest(drop, case)
            provenance = json.loads((case / "evidence/dataset_provenance.json").read_text())
            dataset = provenance["datasets"][0]

            self.assertEqual(len(canonical["available_datasets"]), 1)
            self.assertEqual(dataset["sheet"], "Relevé kWh")
            self.assertTrue(dataset["analytically_usable"])
            self.assertTrue((case / dataset["normalized_file"]).is_file())
            operations = {item["operation"] for item in dataset["transformations"]}
            self.assertIn("exclude_total_rows", operations)
            self.assertIn("remove_strict_duplicates", operations)
            self.assertEqual(dataset["field_lineage"]["measurement"]["source_column"], "Conso")

    def test_case_b_infers_obvious_interval_kwh_without_question(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "conso.csv").write_text(
                "Date;Conso\n01/01/2026 00:00;1,2\n01/01/2026 00:30;1,4\n01/01/2026 01:00;1,3\n",
                encoding="utf-8",
            )
            canonical = self._ingest(drop, case)
            dataset = canonical["available_datasets"][0]

            self.assertEqual(dataset["data_quality"]["unit_interpretation"]["unit"], "kwh")
            self.assertEqual(dataset["data_quality"]["unit_interpretation"]["status"], "AUTO_FIX_SAFE")
            questions = json.loads((case / "investigation/question_batch.json").read_text())
            self.assertEqual(questions["requests"], [])

    def test_case_c_preserves_material_unit_ambiguity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "measurements.csv").write_text(
                "Date,Energy\n2026-01-01 00:00,48\n2026-01-01 00:30,51\n2026-01-01 01:00,49\n",
                encoding="utf-8",
            )
            canonical = self._ingest(drop, case)

            self.assertEqual(len(canonical["unresolved_material_ambiguities"]), 1)
            dataset = canonical["available_datasets"][0]
            self.assertFalse(dataset["analytically_usable"])
            self.assertTrue(dataset["normalized_file"].endswith(".json"))

    def test_case_d_sparse_but_useful_is_not_blocked_by_missing_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "meter.csv").write_text(
                "timestamp,energy_kwh\n2026-01-02 00:00,6\n2026-01-02 00:30,6\n2026-01-02 01:00,6\n",
                encoding="utf-8",
            )
            canonical = self._ingest(drop, case)
            dataset = canonical["available_datasets"][0]

            self.assertTrue(dataset["analytically_usable"])
            self.assertEqual(canonical["unresolved_material_ambiguities"], [])
            self.assertTrue(canonical["no_finding_is_valid"])

    def test_case_e_rich_underdetermined_is_not_diagnosed_by_intake(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "rich.csv").write_text(
                "timestamp,energy_kwh,production,temp_c,shift\n"
                "2026-01-01 08:00,10,5,5,A\n2026-01-01 08:30,11,5,5,A\n",
                encoding="utf-8",
            )
            canonical = self._ingest(drop, case)

            self.assertIn("hypotheses", canonical["agent_decisions_required"])
            self.assertNotIn("leading_cause", canonical)
            self.assertNotIn("findings", canonical)

    def test_case_f_irrelevant_material_does_not_break_intake(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "energy.csv").write_text(
                "timestamp,energy_kwh\n2026-01-01 00:00,1\n2026-01-01 00:30,1\n",
                encoding="utf-8",
            )
            (drop / "logo_photo.txt").write_text("marketing image", encoding="utf-8")
            self._ingest(drop, case)
            inventory = json.loads((case / "evidence/intake_inventory.json").read_text())

            self.assertEqual(len(inventory["artifacts"]), 2)
            ignored = next(item for item in inventory["artifacts"] if item["original_filename"].endswith("logo_photo.txt"))
            self.assertEqual(ignored["probable_role"], "IRRELEVANT")
            self.assertEqual(ignored["usability"], "irrelevant")

    def test_case_g_question_budget_keeps_a_single_simple_contextualized_question(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "energy.csv").write_text(
                "timestamp,energy_kwh\n2026-04-07 05:15,3\n2026-04-07 05:45,3\n",
                encoding="utf-8",
            )
            self._ingest(drop, case)
            batch = publish_question_batch(case, [{
                "request_id": "REQ-HOURS",
                "request_type": "ASK_CLIENT",
                "client_question": "La préparation commençait-elle plus tôt autour du 7 avril ?",
                "internal_reason": "Cette réponse sépare une demande opérationnelle légitime d'une charge non expliquée.",
                "target_role": "responsable de site",
                "hypotheses_distinguished": ["nouvel horaire", "charge non expliquée"],
                "decision_impact": "Évite de qualifier une activité nécessaire d'anomalie.",
                "expected_effort": "Réponse simple en moins de cinq minutes.",
                "importance": "NON_BLOCKING",
            }])

            self.assertEqual(len(batch["requests"]), 1)
            self.assertTrue(batch["requests"][0]["analysis_can_continue_without_answer"])
            self.assertNotIn("vibration", batch["client_facing_text"].lower())

    def test_case_h_technical_evidence_is_not_rewritten_as_owner_question(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "energy.csv").write_text(
                "timestamp,power_kw\n2026-01-01 00:00,4\n2026-01-01 00:30,4\n",
                encoding="utf-8",
            )
            self._ingest(drop, case)
            batch = publish_question_batch(case, [{
                "request_id": "REQ-TECH",
                "request_type": "REQUEST_TECHNICAL_EVIDENCE",
                "client_question": "Lors de la prochaine visite, pouvez-vous demander au technicien de relever la pression mesurée et la consigne ?",
                "internal_reason": "Une mesure commandée/réelle peut départager des explications restantes.",
                "target_role": "technicien compétent",
                "hypotheses_distinguished": ["commande non suivie", "demande procédé"],
                "decision_impact": "Détermine si une intervention physique est justifiée.",
                "expected_effort": "À inclure dans une visite déjà prévue.",
                "importance": "NON_BLOCKING",
            }])
            self.assertEqual(batch["requests"][0]["request_type"], "REQUEST_TECHNICAL_EVIDENCE")

    def test_case_i_no_finding_has_a_complete_structured_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "stable.csv").write_text(
                "timestamp,energy_kwh\n2026-01-01 00:00,2\n2026-01-01 00:30,2\n",
                encoding="utf-8",
            )
            self._ingest(drop, case)
            payload = record_structured_findings(case, [], no_finding={
                "what_was_analyzed": ["energy interval series"],
                "usable_period": "2026-01-01",
                "operating_regimes": ["stable reference"],
                "limitations": ["short period"],
                "monitoring_baseline_meaningful": False,
            })
            self.assertEqual(payload["findings"], [])
            self.assertIsNotNone(payload["no_finding"])

    def test_case_j_flags_corruption_without_silent_repair(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "corrupt.csv").write_text(
                "timestamp,energy_kwh,production\n"
                "2026-10-25 01:00,3,2\n2026-10-25 01:30,3,2\n"
                "2026-10-25 01:30,5,2000\n2026-10-25 03:00,-1,2\n",
                encoding="utf-8",
            )
            canonical = self._ingest(drop, case)
            dataset = canonical["available_datasets"][0]

            self.assertFalse(dataset["analytically_usable"])
            self.assertGreater(dataset["data_quality"]["conflicting_duplicates"], 0)
            self.assertIn("conflicting_duplicates", [item["issue"] for item in canonical["unresolved_material_ambiguities"]])

    def test_answers_are_append_only_and_second_batch_is_exceptional(self) -> None:
        from client_intake_pipeline import record_client_answers
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            drop, case = self._case(root)
            (drop / "energy.csv").write_text("timestamp,energy_kwh\n2026-01-01 00:00,1\n", encoding="utf-8")
            self._ingest(drop, case)
            request = {
                "request_id": "REQ-1", "request_type": "ASK_CLIENT",
                "client_question": "Le site était-il ouvert à cette heure-là ?",
                "internal_reason": "Le statut d'ouverture change l'interprétation.",
                "target_role": "responsable de site", "hypotheses_distinguished": ["activité", "hors horaires"],
                "decision_impact": "Qualification du comportement.", "expected_effort": "Réponse oui/non.",
            }
            publish_question_batch(case, [request])
            recorded = record_client_answers(case, [{
                "request_id": "REQ-1", "answer": "Non.", "provided_by_role": "responsable de site",
                "source_or_evidence": "planning interne",
            }])
            self.assertEqual(len(recorded["recorded_answers"]), 1)
            with self.assertRaises(ValueError):
                record_client_answers(case, [{
                    "request_id": "REQ-1", "answer": "Oui.", "provided_by_role": "responsable de site",
                    "source_or_evidence": "nouvelle version",
                }])
            follow_up = dict(request)
            follow_up["request_id"] = "REQ-2"
            follow_up["client_question"] = "La fermeture était-elle exceptionnelle ce jour-là ?"
            with self.assertRaises(ValueError):
                publish_question_batch(case, [follow_up])
            second = publish_question_batch(case, [follow_up], exceptional_second_batch_reason="La première réponse ouvre une branche décisionnelle nouvelle.")
            self.assertEqual(second["requests"][0]["request_id"], "REQ-2")
            self.assertTrue((case / "investigation/question_batch_history/batch_001.json").is_file())



if __name__ == "__main__":
    unittest.main()
