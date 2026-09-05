from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.blind_suite import CASE_NAMES, generate_blind_case


class BlindSuiteTests(unittest.TestCase):
    def test_public_input_and_private_truth_are_separate_and_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = root / "first.csv"
            second = root / "second.csv"
            generate_blind_case("progressive_drift", first, root / "i1.json", root / "t1.json", seed=9)
            generate_blind_case("progressive_drift", second, root / "i2.json", root / "t2.json", seed=9)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            self.assertNotIn("anomaly", first.read_text(encoding="utf-8").splitlines()[0])
            truth = json.loads((root / "t1.json").read_text())
            self.assertEqual(truth["investigation_access"], "forbidden")
            self.assertEqual(truth["generator_family"], "independent_hourly_operational")

    def test_suite_contains_negative_legitimate_and_unknown_rule_cases(self) -> None:
        self.assertIn("normal_scheduled", CASE_NAMES)
        self.assertIn("legitimate_point_maintenance", CASE_NAMES)
        self.assertIn("normal_24_7_multi_regime", CASE_NAMES)
        self.assertIn("short_cycling_unknown", CASE_NAMES)


if __name__ == "__main__":
    unittest.main()
