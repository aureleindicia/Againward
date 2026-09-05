from __future__ import annotations

import unittest

from energy_mvp.investigation import information_request, next_information_request, validate_follow_up_logic


def request(priority: int = 1) -> dict[str, object]:
    return information_request(
        request_id=f"Q{priority}", request_type="question_metier",
        ask_client="Confirmer si le site etait ferme le 12 mars entre 00:00 et 05:00.",
        why_useful="Le statut du site permet de tester si la charge correspond a une activite.",
        information_value="elevee: la reponse change la decision.",
        hypotheses_distinguished=("site ferme avec charge inutile", "activite legitime"),
        responsible_role="responsable de site",
        client_effort="Une reponse oui/non, moins de cinq minutes.", effort_level="tres_faible",
        expected_if_true="Si la charge est inutile, le site sera confirme ferme sans activite.",
        priority=priority,
    )


class InvestigationFollowUpTests(unittest.TestCase):
    def test_uncertain_hypothesis_requires_precise_follow_up(self) -> None:
        with self.assertRaisesRegex(ValueError, "demande de poursuite"):
            validate_follow_up_logic([{"hypothesis_id": "H1", "decision": "INSUFFISAMMENT_ETAYE"}])

    def test_resolved_hypothesis_does_not_trigger_systematic_question(self) -> None:
        validate_follow_up_logic([
            {"hypothesis_id": "H1", "decision": "CONFIRME", "follow_up_requests": []},
            {"hypothesis_id": "H2", "decision": "REJETE", "follow_up_requests": []},
        ])
        with self.assertRaisesRegex(ValueError, "decision tranchee"):
            validate_follow_up_logic([{"hypothesis_id": "H1", "decision": "CONFIRME", "follow_up_requests": [request()]}])

    def test_terminal_unknown_does_not_force_a_low_value_question(self) -> None:
        validate_follow_up_logic([{
            "hypothesis_id": "H-UNKNOWN", "decision": "INSUFFISAMMENT_ETAYE",
            "follow_up_requests": [], "terminal_status": "non_identifiable",
            "why_no_further_request": "Aucune information proportionnée ne départage les actifs.",
        }])

    def test_vague_request_is_rejected(self) -> None:
        values = request()
        values["ask_client"] = "Plus de donnees"
        with self.assertRaisesRegex(ValueError, "trop vague"):
            validate_follow_up_logic([{"hypothesis_id": "H1", "decision": "INSUFFISAMMENT_ETAYE", "follow_up_requests": [values]}])

    def test_lowest_priority_number_is_the_next_minimum_request(self) -> None:
        self.assertEqual(next_information_request({"follow_up_requests": [request(2), request(1)]})["request_id"], "Q1")


if __name__ == "__main__":
    unittest.main()
