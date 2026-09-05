from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from workspace.evaluate_blind_sessions import (
    evaluate_after_blind_phase,
    freeze_public_phase,
)
from workspace.prepare_blind_sessions import main as prepare_sessions


class BlindComparisonTests(unittest.TestCase):
    def test_frozen_v2_reviews_reproduce_python_vs_codex_comparison(self) -> None:
        repository = Path(__file__).resolve().parents[1]
        reviews = sorted((repository / "reports" / "blind_sessions").glob("*.json"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "blind"
            self.assertEqual(prepare_sessions([str(root)]), 0)

            frozen = freeze_public_phase(root / "public", reviews)
            result = evaluate_after_blind_phase(frozen, root / "private_truth")

        self.assertEqual(result["design"]["independent_codex_sessions"], 3)
        self.assertEqual(result["python_only_same_public_cases"]["false_positives"], 6)
        self.assertAlmostEqual(result["python_only_same_public_cases"]["f1"], 2 / 9)
        self.assertTrue(all(
            item["temporal_detection"]["f1"] == 1.0
            for item in result["python_plus_codex_sessions"]
        ))
        self.assertAlmostEqual(
            result["stability"]["mean_exact_case_disposition_agreement"], 8 / 9
        )


if __name__ == "__main__":
    unittest.main()
