from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.case_lifecycle import (
    archive_answered_question_cycle,
    evaluate_delivery_gate,
    publish_minimum_questions,
    record_client_answers,
    validate_adversarial_review,
    validate_investigation_document,
)
from energy_mvp.client_lifecycle import record_existing_data_exhaustion
from energy_mvp.evidence_cli import execute_case_query
from energy_mvp.investigation import information_request
from energy_mvp.workflow import prepare_investigation


def _request() -> dict[str, object]:
    return information_request(
        request_id="H1-Q1",
        request_type="question_metier",
        ask_client="Le site était-il fermé le 12 mars entre 00:00 et 05:00 ?",
        why_useful="Le statut d'exploitation distingue une activité légitime d'une charge hors horaires.",
        information_value="Élevée : une réponse datée peut changer la décision.",
        hypotheses_distinguished=("activité légitime", "charge sans activité"),
        responsible_role="responsable de site",
        client_effort="Réponse oui/non à partir du planning, moins de cinq minutes.",
        effort_level="tres_faible",
        expected_if_true="Si la charge est sans activité, le planning confirmera une fermeture complète.",
    )


def _hypothesis(decision: str, *, request: bool) -> dict[str, object]:
    return {
        "hypothesis_id": "H1",
        "observation": "Palier nocturne mesuré.",
        "hypothesis": "Une charge existe hors horaires.",
        "tests_requested": ["Comparer aux nuits historiques comparables."],
        "results": {"mean_delta_kw": 12.5, "quantitative_source": "scratch/test.json"},
        "alternative_explanations": ["Activité nocturne légitime."],
        "best_reason_false": "Le planning peut contenir une activité non présente dans les données.",
        "decision": decision,
        "confidence": {"observation": "moyenne"},
        "physical_cause_status": "non_etablie_avec_les_donnees_disponibles",
        "follow_up_requests": [_request()] if request else [],
    }


def _review() -> dict[str, object]:
    checks = {
        name: {"status": "passed", "evidence": f"Contrôle {name} consigné."}
        for name in (
            "calculations", "data_quality", "baseline_robustness",
            "alternative_explanations", "causality", "annualization",
            "recoverable_saving", "double_counting",
        )
    }
    return {
        "schema_version": 1,
        "ground_truth_used": False,
        "reviewed_hypotheses": [{
            "hypothesis_id": "H1",
            "best_reason_false": "Une activité légitime non mesurée peut expliquer le signal.",
            "checks": checks,
            "final_decision": "A_CONSERVER_AVEC_RESERVES",
        }],
    }


def _initialize_case(root: Path, investigation: dict[str, object]) -> None:
    (root / "investigation.json").write_text(
        json.dumps(investigation), encoding="utf-8"
    )
    (root / "questions.json").write_text(
        json.dumps({"schema_version": 1, "questions": [], "responses": []}),
        encoding="utf-8",
    )
    (root / "trace.json").write_text(
        json.dumps({"schema_version": 1, "entries": []}), encoding="utf-8"
    )


class CaseLifecycleTests(unittest.TestCase):
    def test_question_cycle_publishes_only_next_request_and_never_rewrites_answer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _initialize_case(root, {"ground_truth_used": False, "hypotheses": [_hypothesis(
                "A_CONSERVER_AVEC_RESERVES", request=True
            )]})
            record_existing_data_exhaustion(root,analysis_inventory_ref="investigation.json",reviewed_sources=["investigation.json"])
            published = publish_minimum_questions(root)
            self.assertEqual([item["request_id"] for item in published["questions"]], ["H1-Q1"])
            answers = root / "answers.json"
            answers.write_text(json.dumps({"answers": [{
                "request_id": "H1-Q1",
                "answer": "Oui, le site était fermé.",
                "provided_by_role": "responsable de site",
                "source_or_evidence": "Planning d'ouverture du 12 mars.",
            }]}), encoding="utf-8")
            recorded = record_client_answers(root, answers)
            self.assertEqual(recorded["questions"][0]["status"], "answered")
            with self.assertRaisesRegex(ValueError, "déjà enregistrée"):
                record_client_answers(root, answers)
            archived = archive_answered_question_cycle(root)
            self.assertTrue(archived.is_file())
            reset = json.loads((root / "questions.json").read_text())
            self.assertEqual(reset["questions"], [])
            self.assertEqual(reset["previous_cycle"], "question_cycles/questions_cycle_001.json")

    def test_delivery_gate_requires_adversarial_and_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            investigation = {"ground_truth_used": False, "hypotheses": [_hypothesis(
                "A_CONSERVER_AVEC_RESERVES", request=True
            )]}
            _initialize_case(root, investigation)
            (root / "review.json").write_text(json.dumps(_review()), encoding="utf-8")
            (root / "report.md").write_text("# Rapport\n", encoding="utf-8")
            (root / "human_review.json").write_text(json.dumps({
                "status": "not_reviewed", "approved_for_delivery": False,
                "reviewer_role": None, "reviewed_at_utc": None,
            }), encoding="utf-8")
            self.assertFalse(evaluate_delivery_gate(root)["ready_for_delivery"])
            (root / "human_review.json").write_text(json.dumps({
                "status": "approved", "approved_for_delivery": True,
                "reviewer_role": "ingénieur énergie",
                "reviewed_at_utc": "2026-08-27T13:00:00+00:00",
                "reservations": ["Cause physique à vérifier."],
            }), encoding="utf-8")
            self.assertTrue(evaluate_delivery_gate(root)["ready_for_delivery"])

    def test_failed_review_check_cannot_remain_confirmed(self) -> None:
        investigation = {
            "ground_truth_used": False,
            "hypotheses": [_hypothesis("CONFIRME", request=False)],
        }
        review = _review()
        review["reviewed_hypotheses"][0]["checks"]["causality"] = {
            "status": "failed", "evidence": "Cause non démontrée."
        }
        review["reviewed_hypotheses"][0]["final_decision"] = "CONFIRME"
        with self.assertRaisesRegex(ValueError, "ne peut rester CONFIRME"):
            validate_adversarial_review(review, investigation)

    def test_stage4_retained_hypothesis_requires_evidence_references(self) -> None:
        investigation = {
            "ground_truth_used": False,
            "evidence_plane_session": "session-test",
            "hypotheses": [_hypothesis("A_CONSERVER_AVEC_RESERVES", request=True)],
        }

        with self.assertRaisesRegex(ValueError, "preuves Evidence Plane"):
            validate_investigation_document(investigation)

        investigation["hypotheses"][0]["evidence_query_ids"] = ["q1"]
        investigation["hypotheses"][0]["evidence_handles"] = ["evh-test"]
        validate_investigation_document(investigation)

    def test_stage4_delivery_gate_requires_valid_agent_finding_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_text(
                "timestamp,energy_kwh,machine_mode\n"
                "2026-01-01,10,idle\n2026-01-02,11,run\n",
                encoding="utf-8",
            )
            case = root / "case"
            state = prepare_investigation(source, case)
            request = root / "request.json"
            request.write_text(json.dumps({
                "schema_version": "indicia-evidence-query-v1",
                "query_id": "q1",
                "dataset_id": state["evidence_plane"]["dataset_id"],
                "operation": "describe_schema",
                "arguments": {},
                "purpose": "Inventorier les preuves avant de conserver une piste.",
            }), encoding="utf-8")
            response = execute_case_query(case, request)
            handle = response["retrieval_handles"][0]["handle"]
            hypothesis = _hypothesis("A_CONSERVER_AVEC_RESERVES", request=True)
            hypothesis["evidence_query_ids"] = ["q1"]
            hypothesis["evidence_handles"] = [handle]
            investigation = {
                "ground_truth_used": False,
                "evidence_plane_session": json.loads(
                    (case / "evidence_query_session.json").read_text()
                )["session_id"],
                "hypotheses": [hypothesis],
            }
            (case / "investigation.json").write_text(json.dumps(investigation), encoding="utf-8")
            (case / "review.json").write_text(json.dumps(_review()), encoding="utf-8")
            (case / "report.md").write_text("# Rapport\n", encoding="utf-8")
            (case / "human_review.json").write_text(json.dumps({
                "status": "approved", "approved_for_delivery": True,
                "reviewer_role": "ingénieur énergie",
                "reviewed_at_utc": "2026-08-31T12:00:00+00:00",
            }), encoding="utf-8")

            blocked = evaluate_delivery_gate(case)
            self.assertIn("agent_findings.json", " ".join(blocked["blocking_reasons"]))

            (case / "agent_findings.json").write_text(json.dumps({
                "schema_version": "indicia-agent-findings-v1",
                "ground_truth_used": False,
                "findings": [{
                    "finding_id": "F01",
                    "status": "A_CONSERVER_AVEC_RESERVES",
                    "claim_or_abstention": "Signal à vérifier.",
                    "evidence_query_ids": ["q1"],
                    "evidence_handles": [handle],
                    "alternative_explanations_tested": ["qualité des données"],
                }],
            }), encoding="utf-8")

            self.assertTrue(evaluate_delivery_gate(case)["ready_for_delivery"])


if __name__ == "__main__":
    unittest.main()
