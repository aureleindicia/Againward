from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from benchmarking.stage4_model_harness import prepare_model_benchmark
from energy_mvp.workflow import prepare_investigation


class Stage4ModelHarnessTests(unittest.TestCase):
    def test_harness_prepares_full_model_context_matrix_without_fabricating_results(self) -> None:
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
                raw_source=source,
            )

            self.assertEqual(set(manifest["condition_order"]), {
                "STATIC_LEGACY_CONTROL",
                "STRONG_RAW_CONTEXT",
                "STRONG_EVIDENCE_PLANE",
                "SMALL_RAW_CONTEXT",
                "SMALL_EVIDENCE_PLANE",
                "SMALL_EVIDENCE_RETRIEVAL",
                "SMALL_WITH_STRONG_ESCALATION",
                "ITERATIVE_AGENT_PRIMITIVES",
            })
            self.assertEqual(manifest["status"], "PREPARED_NOT_RUN")
            self.assertIsNone(manifest["scores"])
            self.assertFalse(manifest["ground_truth_included"])
            query_condition = next(
                item for item in manifest["conditions"]
                if item["condition"] == "SMALL_EVIDENCE_RETRIEVAL"
            )
            self.assertTrue(Path(query_condition["directory"], "evidence_dataset.json").exists())
            self.assertIsNotNone(query_condition["query_command"])
            raw_conditions = [
                item for item in manifest["conditions"]
                if item["context_mode"] == "raw_context"
            ]
            self.assertEqual(len(raw_conditions), 2)
            self.assertTrue(all(list(Path(item["directory"]).glob("RAW_SOURCE.*")) for item in raw_conditions))


if __name__ == "__main__":
    unittest.main()
