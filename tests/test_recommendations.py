from __future__ import annotations

import unittest

from energy_mvp.investigation import information_request
from energy_mvp.recommendations import validate_operational_recommendation


def recommendation() -> dict[str, object]:
    return {
        "recommendation_id": "R-01",
        "finding_id": "F-01",
        "measured_anomaly": "Palier de 8 kW hors production pendant 20 nuits.",
        "observed_impact": {
            "period": "2026-01-01/2026-01-21",
            "excess_energy_kwh": 480.0,
            "associated_cost": 96.0,
            "quantitative_source": "results.json#night.excess_energy_kwh",
        },
        "confidence": {"level": "medium", "basis": ["20/20 nuits", "production nulle"]},
        "plausible_causes": [
            {"rank": 1, "cause": "ventilation maintenue", "evidence_status": "untested"},
            {"rank": 2, "cause": "air comprimé", "evidence_status": "untested"},
        ],
        "physical_cause_status": "plausible_not_proven",
        "action_status": "verification_only",
        "next_verification": information_request(
            request_id="Q-01", request_type="question_metier",
            ask_client="Confirmer si la ventilation doit rester active entre 00:00 et 05:00.",
            why_useful="La réponse teste la première cause plausible sans arrêt de procédé.",
            information_value="élevée: elle peut écarter ou prioriser la ventilation.",
            hypotheses_distinguished=("ventilation nécessaire", "ventilation non requise"),
            responsible_role="responsable maintenance",
            client_effort="5 minutes", effort_level="tres_faible",
            expected_if_true="Si elle explique le palier, la ventilation sera déclarée active sur ces horaires.",
        ),
        "owner_role": "responsable maintenance",
        "verification_effort": "5 minutes, sans coût matériel",
        "expected_if_hypothesis_true": "La ventilation est active pendant tout le palier.",
        "post_action_measurement": {
            "metric": "puissance moyenne hors production en kW",
            "baseline_definition": "mêmes heures sur 10 nuits avant action",
            "evaluation_window": "10 nuits après action",
            "success_rule": "baisse persistante cohérente avec la prédiction pré-enregistrée",
        },
        "recoverable_saving": None,
    }


class RecommendationTests(unittest.TestCase):
    def test_complete_verification_recommendation_is_accepted(self) -> None:
        validate_operational_recommendation(recommendation())

    def test_unproven_cause_cannot_become_action_or_recoverable_saving(self) -> None:
        payload = recommendation()
        payload["action_status"] = "ready_for_controlled_action"
        with self.assertRaisesRegex(ValueError, "cause non prouvée"):
            validate_operational_recommendation(payload)

        payload = recommendation()
        payload["recoverable_saving"] = {"energy_kwh": 480.0}
        with self.assertRaisesRegex(ValueError, "économie récupérable"):
            validate_operational_recommendation(payload)

    def test_post_action_measurement_is_mandatory(self) -> None:
        payload = recommendation()
        payload["post_action_measurement"] = {}
        with self.assertRaisesRegex(ValueError, "après intervention"):
            validate_operational_recommendation(payload)


if __name__ == "__main__":
    unittest.main()
