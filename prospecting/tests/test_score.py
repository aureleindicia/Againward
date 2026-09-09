from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "score.py"
SPEC = importlib.util.spec_from_file_location("prospecting_score", MODULE_PATH)
assert SPEC and SPEC.loader
score_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(score_module)


def dimensions(rating: int) -> dict[str, dict[str, object]]:
    return {
        key: {"rating": rating, "rationale": "justification"}
        for key in score_module.WEIGHTS
    }


class ProspectScoringTests(unittest.TestCase):
    def test_weighted_score_is_deterministic(self) -> None:
        exact, display = score_module.calculate_score(dimensions(4))
        self.assertEqual(exact, 80.0)
        self.assertEqual(display, 80)

    def test_invalid_dimension_rating_is_refused(self) -> None:
        values = dimensions(4)
        values["energy_potential"]["rating"] = 5.5
        with self.assertRaisesRegex(ValueError, "entier de 0 à 5"):
            score_module.calculate_score(values)

    def test_fact_based_gate_overrides_raw_score(self) -> None:
        self.assertEqual(score_module._priority(95, "hors ICP"), "REJECTED")

    def test_all_repository_assessments_are_valid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "scores.json"
            payload = score_module.score(output_path=output)
            self.assertEqual(len(payload["prospects"]), 10)
            self.assertEqual(
                payload["counts"],
                {"PRIORITY_A": 3, "PRIORITY_B": 3, "PRIORITY_C": 2, "REJECTED": 2},
            )
            self.assertFalse(payload["contacting_performed"])
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["counts"], payload["counts"])

    def test_outreach_preparation_is_diversified_and_never_authorizes_contact(self) -> None:
        data = MODULE_PATH.parent / "data"
        outreach = json.loads((data / "outreach_preparation.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as directory:
            scores = score_module.score(output_path=Path(directory) / "scores.json")
        priorities = {item["prospect_id"]: item["priority"] for item in scores["prospects"]}

        selected = outreach["prospects"]
        self.assertEqual(len(selected), 5)
        self.assertFalse(outreach["contacting_authorized"])
        self.assertEqual(outreach["contacts_sent"], 0)
        self.assertTrue(all(priorities[item["prospect_id"]] in {"PRIORITY_A", "PRIORITY_B"} for item in selected))
        self.assertTrue(all(item["public_personalization_fact"] for item in selected))
        self.assertTrue(all(item["first_qualification_question"] for item in selected))

    def test_tracking_covers_every_prospect_and_records_no_contact(self) -> None:
        data = MODULE_PATH.parent / "data"
        raw = json.loads((data / "prospects_raw.json").read_text(encoding="utf-8"))
        tracking = json.loads((data / "commercial_tracking.json").read_text(encoding="utf-8"))
        raw_ids = {item["prospect_id"] for item in raw["prospects"]}
        tracked_ids = {item["prospect_id"] for item in tracking["prospects"]}

        self.assertEqual(tracked_ids, raw_ids)
        self.assertTrue(all(not item["contacted"] for item in tracking["prospects"]))
        self.assertTrue(all(item["response"] is None for item in tracking["prospects"]))


    def test_async_compatibility_is_a_required_scoring_dimension(self) -> None:
        values = dimensions(3)
        values.pop("async_compatibility")
        with self.assertRaisesRegex(ValueError, "Dimensions invalides"):
            score_module.calculate_score(values)

if __name__ == "__main__":
    unittest.main()
