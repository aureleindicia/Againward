from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
