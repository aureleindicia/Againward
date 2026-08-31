from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from benchmarking.stage4_model_harness import prepare_model_benchmark
from energy_mvp.workflow import prepare_investigation


class Stage4ModelHarnessTests(unittest.TestCase):
    def test_harness_prepares_three_randomized_arms_without_fabricating_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "input.csv"
            source.write_text(
                "timestamp,energy_kwh,machine_mode\n"
                "2026-01-01,10,idle\n2026-01-02,11,run\n",
                encoding="utf-8",
            )
            case = root / "case"
            prepare_investigation(source, case)

            manifest = prepare_model_benchmark(
                case,
                root / "benchmark",
                case_id="case_blind_001",
                randomization_seed=42,
            )

            self.assertEqual(set(manifest["arm_order"]), {
                "STATIC_LEGACY", "RELATIONAL_CARD_V2", "EXECUTABLE_QUERY",
            })
            self.assertEqual(manifest["status"], "PREPARED_NOT_RUN")
            self.assertIsNone(manifest["scores"])
            self.assertFalse(manifest["ground_truth_included"])
            query_arm = next(item for item in manifest["arms"] if item["arm"] == "EXECUTABLE_QUERY")
            self.assertTrue(Path(query_arm["directory"], "evidence_dataset.json").exists())
            self.assertIsNotNone(query_arm["query_command"])


if __name__ == "__main__":
    unittest.main()
