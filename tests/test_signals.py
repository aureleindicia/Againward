from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from energy_mvp.blind_suite import generate_blind_case
from energy_mvp.demo import generate_demo
from energy_mvp.io import load_data
from energy_mvp.signals import detect_candidate_events


class CandidateSignalTests(unittest.TestCase):
    def test_signals_remain_candidates_and_find_multiple_event_families(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "demo.csv"
            truth = root / "truth.json"
            generate_demo(source, truth, days=120, seed=42)

            result = detect_candidate_events(load_data(source))

            self.assertEqual(result["status"], "candidate_signals_only")
            self.assertTrue(all(item["status"] == "candidate_signal" for item in result["events"]))
            types = {item["type"] for item in result["events"]}
            self.assertIn("point_spike", types)
            self.assertIn("progressive_drift", types)
            self.assertIn("permanent_baseline_shift", types)
            self.assertTrue(result["baseline"]["robust_refit"])
            self.assertGreater(result["baseline"]["robust_trimmed_rows"], 0)
            self.assertIn("initial_validation_metrics", result["baseline"])

    def test_detector_degrades_to_available_context_instead_of_requiring_demo_columns(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "minimal.csv"
            rows = ["timestamp,energy_kwh"]
            start = datetime(2026, 1, 1)
            for index in range(60 * 24):
                energy = 100.0 if 40 * 24 <= index < 40 * 24 + 2 else 5.0
                rows.append(
                    f"{(start + timedelta(hours=index)).isoformat(sep=' ')},{energy}"
                )
            source.write_text("\n".join(rows) + "\n", encoding="utf-8")

            result = detect_candidate_events(load_data(source))

            self.assertEqual(result["predictors_used"], [])
            self.assertIn("efficiency", result["disabled_signal_families"])
            self.assertIn("inactive_drift", result["disabled_signal_families"])
            self.assertTrue(
                any(item["type"] == "point_spike" for item in result["events"])
            )

    def test_weather_sensitive_case_selects_validated_weather_baseline_without_signal(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_blind_case(
                "weather_variation", root / "input.csv", root / "intake.json",
                root / "truth.json", seed=777,
            )

            result = detect_candidate_events(load_data(
                root / "input.csv", interval_minutes=60, site_timezone="Europe/Paris"
            ))

            self.assertEqual(result["selected_baseline"], "degree_18")
            self.assertIn("cooling_degree_c", result["predictors_used"])
            self.assertEqual(result["events"], [])

    def test_site_timezone_is_explicit_in_external_event_timestamps(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            generate_blind_case(
                "legitimate_point_maintenance", root / "input.csv", root / "intake.json",
                root / "truth.json", seed=778,
            )

            result = detect_candidate_events(load_data(
                root / "input.csv", interval_minutes=60, site_timezone="Europe/Paris"
            ))
            spike = next(item for item in result["events"] if item["type"] == "point_spike")

            self.assertRegex(spike["start"], r"[+]0[12]:00$")
            self.assertRegex(spike["end"], r"[+]0[12]:00$")


if __name__ == "__main__":
    unittest.main()
