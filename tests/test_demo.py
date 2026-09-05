from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from energy_mvp.demo import generate_demo
from energy_mvp.io import load_data


class DemoGeneratorTests(unittest.TestCase):
    def test_demo_is_reproducible_and_contains_required_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_a = root / "a.csv"
            csv_b = root / "b.csv"
            truth_a = root / "a.json"
            truth_b = root / "b.json"

            first = generate_demo(csv_a, truth_a, days=100, seed=7)
            second = generate_demo(csv_b, truth_b, days=100, seed=7)

            self.assertEqual(csv_a.read_bytes(), csv_b.read_bytes())
            self.assertEqual(first, second)
            event_types = {event["type"] for event in first["anomalies"]}
            self.assertEqual(
                event_types,
                {
                    "night_anomaly",
                    "weekend_anomaly",
                    "progressive_drift",
                    "point_spike",
                    "efficiency_drop",
                    "permanent_baseline_shift",
                },
            )
            self.assertTrue(
                all(event["expected_energy_impact"] > 0 for event in first["anomalies"])
            )
            self.assertEqual(first["investigation_access"], "forbidden")

    def test_demo_data_quality_issues_are_detected_without_truth_access(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            csv_path = root / "demo.csv"
            truth_path = root / "truth.json"
            truth = generate_demo(csv_path, truth_path, days=100, seed=11)

            loaded = load_data(csv_path)

            self.assertEqual(loaded.input_rows, truth["written_rows"])
            self.assertEqual(loaded.quality.identical_duplicates_removed, 1)
            self.assertEqual(loaded.quality.invalid_timestamp_rows, 1)
            self.assertEqual(loaded.quality.missing_measurement_rows, 1)
            self.assertEqual(loaded.quality.impossible_value_rows, 1)
            self.assertGreaterEqual(loaded.quality.gap_count, 1)
            log = " ".join(loaded.quality.processing_log)
            self.assertIn("timestamp invalide", log)
            self.assertIn("sans mesure energetique", log)
            self.assertIsNotNone(loaded.readings[0].outside_temperature_c)
            self.assertIsNotNone(loaded.readings[0].production_active)
            self.assertAlmostEqual(
                loaded.readings[0].energy_kwh,
                (loaded.readings[0].power_kw or 0.0) * 0.25,
                places=5,
            )

    def test_no_anomaly_scenario_has_empty_ground_truth(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            truth = generate_demo(
                root / "normal.csv",
                root / "normal.json",
                days=100,
                seed=3,
                include_anomalies=False,
            )

            self.assertFalse(truth["anomalies_enabled"])
            self.assertEqual(truth["anomalies"], [])


if __name__ == "__main__":
    unittest.main()
