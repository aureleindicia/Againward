from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from energy_mvp.intake import intake_template
from energy_mvp.workflow import prepare_investigation


class GenericWorkflowTests(unittest.TestCase):
    def test_coarse_unknown_dataset_prepares_without_inventing_an_opportunity(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "unknown.csv"
            source.write_text(
                "timestamp,energy_kwh,production\n"
                "2026-01-01,100,10\n2026-02-01,110,11\n2026-03-01,105,10\n",
                encoding="utf-8",
            )
            output = root / "prepared"
            state = prepare_investigation(source, output)
            self.assertEqual(state["status"], "awaiting_codex_exploration")
            self.assertEqual(state["candidate_detection"]["status"], "unavailable")
            self.assertEqual(state["candidate_detection"]["events"], [])
            self.assertFalse(state["source"]["ground_truth_available_to_investigation"])
            positioning = state["service_positioning"]
            self.assertEqual(positioning["category"], "investigation énergétique sur données")
            self.assertTrue(positioning["standalone_use"])
            self.assertFalse(positioning["regulatory_audit"])
            self.assertIn("mainteneur", positioning["complements"])
            self.assertTrue((output / "ANALYST_BRIEF.md").exists())
            self.assertTrue((output / "questions.json").exists())
            self.assertTrue((output / "human_review.json").exists())
            self.assertTrue((output / "investigation_template.json").exists())
            self.assertTrue((output / "review_template.json").exists())
            self.assertTrue((output / "answers_template.json").exists())
            self.assertTrue((output / "evidence_dataset.json").exists())
            self.assertTrue((output / "evidence_card.json").exists())
            self.assertTrue((output / "evidence_query_contract.json").exists())
            self.assertTrue((output / "evidence_query_session.json").exists())
            self.assertTrue(state["evidence_plane"]["authoritative_for_agent_queries"])
            automatic = json.loads((output / "prepared_analysis.json").read_text())
            self.assertTrue(all(item["status"] != "confirmed" for item in automatic["findings"]))

    def test_generic_packet_uses_source_fingerprint_and_no_demo_hypothesis_ids(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "site.csv"
            rows = ["timestamp,power_kw,production,production_active"]
            origin = datetime(2025, 7, 3)
            for index in range(35 * 24):
                timestamp = origin + timedelta(hours=index)
                active = int(timestamp.weekday() < 5 and 8 <= timestamp.hour < 17)
                rows.append(
                    f"{timestamp.isoformat()},{50 if active else 12},{10 if active else 0},{active}"
                )
            source.write_text("\n".join(rows) + "\n", encoding="utf-8")
            intake = intake_template()
            intake["site"].update({"timezone": "Europe/Paris", "meter_scope": "atelier"})
            intake["metering"].update({
                "measurement_kind": "power", "unit": "kW", "timestamp_position": "start",
            })
            output = root / "packet"
            state = prepare_investigation(source, output, intake=intake)
            self.assertEqual(len(state["source"]["sha256"]), 64)
            serialized = json.dumps(state)
            self.assertNotIn("H01", serialized)
            self.assertNotIn("2026-01-25", serialized)
            self.assertEqual(state["candidate_detection"]["status"], "candidate_signals_only")

    def test_intake_time_of_use_plan_creates_separate_deterministic_cost_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cost.csv"
            source.write_text(
                "timestamp,energy_kwh,power_kw\n"
                "2026-01-05 17:00,10,20\n"
                "2026-01-05 18:00,10,40\n",
                encoding="utf-8",
            )
            intake = intake_template()
            intake["cost"].update({
                "flat_price_per_kwh": 0.10,
                "has_time_of_use_or_demand_charges": True,
                "time_of_use_periods": [{
                    "name": "pointe", "weekdays": [0, 1, 2, 3, 4],
                    "start": "18:00", "end": "20:00", "price_per_kwh": 0.30,
                }],
                "demand_charge_per_kw_month": 5.0,
            })
            output = root / "packet"

            state = prepare_investigation(source, output, intake=intake)
            cost = json.loads((output / "tariff_cost.json").read_text())

            self.assertEqual(state["costing"]["method"], "time_of_use_and_demand")
            self.assertAlmostEqual(cost["total_cost"], 204.0)
            self.assertIsNone(cost["recoverable_saving"])

    def test_existing_investigation_is_never_reset_silently(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "site.csv"
            source.write_text(
                "timestamp,energy_kwh\n2026-01-01,10\n2026-01-02,11\n",
                encoding="utf-8",
            )
            output = root / "packet"
            prepare_investigation(source, output)
            original_trace = (output / "trace.json").read_text()

            with self.assertRaisesRegex(FileExistsError, "ne sera pas réinitialisé"):
                prepare_investigation(source, output)

            self.assertEqual((output / "trace.json").read_text(), original_trace)

    def test_legacy_mode_is_a_non_destructive_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "site.csv"
            source.write_text(
                "timestamp,energy_kwh,machine_mode\n"
                "2026-01-01,10,idle\n2026-01-02,11,run\n",
                encoding="utf-8",
            )
            output = root / "legacy"

            state = prepare_investigation(
                source, output, evidence_plane_mode="legacy"
            )

            self.assertFalse(state["evidence_plane"]["enabled"])
            self.assertTrue((output / "candidate_signals.json").exists())
            self.assertFalse((output / "evidence_dataset.json").exists())
            self.assertFalse((output / "evidence_card.json").exists())

    def test_shadow_mode_preserves_legacy_signals_and_records_structural_delta(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "site.csv"
            source.write_text(
                "timestamp,energy_kwh,machine_mode\n"
                "2026-01-01,10,idle\n2026-01-02,11,run\n",
                encoding="utf-8",
            )
            output = root / "shadow"

            state = prepare_investigation(
                source, output, evidence_plane_mode="shadow"
            )
            comparison = json.loads(
                (output / "shadow_comparison.json").read_text(encoding="utf-8")
            )

            self.assertEqual(state["evidence_plane"]["mode"], "shadow")
            self.assertTrue(comparison["agreement"]["legacy_candidates_preserved"])
            self.assertEqual(comparison["finding_disagreement"]["status"], "NOT_MEASURED")
            self.assertEqual(comparison["evidence_plane_path"]["auxiliary_fields_available"], 1)


if __name__ == "__main__":
    unittest.main()
