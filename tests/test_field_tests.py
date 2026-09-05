from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.field_tests import (
    preregister_field_test,
    record_field_test_outcome,
    verify_registration,
)


def plan() -> dict[str, object]:
    return {
        "test_id": "FT-01",
        "hypothesis_id": "HX",
        "action": "Arrêter la ventilation de confort pendant 30 minutes hors production.",
        "owner_role": "responsable maintenance",
        "client_effort": "45 minutes",
        "safety_preconditions": ["Aucune personne dans la zone", "Autorisation maintenance"],
        "stop_conditions": ["Température zone supérieure à 28 °C", "Alarme procédé"],
        "decision_if_confirmed": "La ventilation contribue au palier observé.",
        "decision_if_refuted": "Rechercher un autre auxiliaire.",
        "prediction": {
            "metric": "mean_power_kw",
            "unit": "kW",
            "expected_direction": "decrease",
            "expected_effect": -8.0,
            "quantitative_source": "evidence.json",
            "value_path": "prediction.delta_kw",
            "comparison_method": "moyenne 30 min avant contre 30 min pendant",
        },
    }


class FieldTestTests(unittest.TestCase):
    def test_prediction_is_locked_and_compared_after_test(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.json").write_text(
                json.dumps({"prediction": {"delta_kw": -8.0}}), encoding="utf-8"
            )
            registered_path = root / "registered.json"
            registration = preregister_field_test(plan(), registered_path, base_directory=root)
            verify_registration(registration)
            result = record_field_test_outcome(
                registered_path,
                {"metric": "mean_power_kw", "unit": "kW", "baseline_mean": 30.0, "test_mean": 22.5},
                root / "outcome.json",
            )
            self.assertEqual(result["computed"]["observed_delta"], -7.5)
            self.assertTrue(result["computed"]["direction_matches_prediction"])

    def test_prediction_cannot_be_rewritten_or_disagree_with_python_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.json").write_text(
                json.dumps({"prediction": {"delta_kw": -7.0}}), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "ne correspond pas exactement"):
                preregister_field_test(plan(), root / "registered.json", base_directory=root)

            (root / "evidence.json").write_text(
                json.dumps({"prediction": {"delta_kw": -8.0}}), encoding="utf-8"
            )
            target = root / "registered.json"
            preregister_field_test(plan(), target, base_directory=root)
            with self.assertRaises(FileExistsError):
                preregister_field_test(plan(), target, base_directory=root)

    def test_tampering_is_detected_before_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "evidence.json").write_text(
                json.dumps({"prediction": {"delta_kw": -8.0}}), encoding="utf-8"
            )
            target = root / "registered.json"
            preregister_field_test(plan(), target, base_directory=root)
            payload = json.loads(target.read_text())
            payload["plan"]["prediction"]["expected_effect"] = -9.0
            with self.assertRaisesRegex(ValueError, "modifiée"):
                verify_registration(payload)


if __name__ == "__main__":
    unittest.main()
