from __future__ import annotations

import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from energy_mvp.case_lifecycle_cli import main
from energy_mvp.case_lifecycle import evaluate_delivery_gate
from energy_mvp.client_lifecycle import (
    initialize_client_lifecycle,
    publish_client_requests,
    record_canonical_answers,
    record_existing_data_exhaustion,
)
from energy_mvp.client_workspace import create_client_workspace
from energy_mvp.workflow_paths import (
    inspect_case_status,
    resolve_analysis_directory,
    resolve_case_layout,
)


class WorkflowPathTests(unittest.TestCase):
    def test_standard_workspace_root_resolves_to_processed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            create_client_workspace("site_a", root=root, synthetic=True)
            case = root / "site_a"

            layout = resolve_case_layout(case)

            self.assertEqual(layout["layout"], "STANDARD_WORKSPACE")
            self.assertEqual(layout["analysis_root"], (case / "processed").resolve())
            self.assertEqual(resolve_analysis_directory(case / "processed"), case / "processed")

    def test_goal_a_root_and_investigation_resolve_to_same_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            case = Path(directory) / "case_a"
            (case / "investigation").mkdir(parents=True)
            (case / "case_manifest.json").write_text("{}", encoding="utf-8")

            from_root = resolve_case_layout(case)
            from_child = resolve_case_layout(case / "investigation")

            self.assertEqual(from_root["layout"], "GOAL_A_CASE")
            self.assertEqual(from_root["analysis_root"], from_child["analysis_root"])

    def test_direct_analysis_directory_remains_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            self.assertEqual(resolve_analysis_directory(path), path.resolve())
            self.assertEqual(
                resolve_case_layout(path)["layout"], "DIRECT_ANALYSIS_DIRECTORY"
            )

    def test_status_is_read_only_and_gives_next_action(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            create_client_workspace("site_b", root=root, synthetic=True)
            case = root / "site_b"

            before = sorted(path.relative_to(case) for path in case.rglob("*"))
            initial = inspect_case_status(case)
            after = sorted(path.relative_to(case) for path in case.rglob("*"))

            self.assertEqual(initial["next_action"], "INITIALIZE_LIFECYCLE")
            self.assertTrue(initial["read_only"])
            self.assertEqual(before, after)

            initialize_client_lifecycle(case)
            analyzing = inspect_case_status(case)
            self.assertEqual(
                analyzing["next_action"], "EXHAUST_AND_INVENTORY_EXISTING_DATA"
            )
            record_existing_data_exhaustion(
                case,
                analysis_inventory_ref="analysis_inventory.json",
                reviewed_sources=["input/source.csv"],
            )
            exhausted = inspect_case_status(case)
            self.assertEqual(
                exhausted["next_action"],
                "INVESTIGATE_THEN_SELECT_REQUESTS_OR_FINALIZE",
            )

    def test_status_cli_accepts_workspace_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            create_client_workspace("site_c", root=root, synthetic=True)
            case = root / "site_c"
            initialize_client_lifecycle(case)
            stdout = StringIO()

            with redirect_stdout(stdout):
                exit_code = main(["status", str(case)])

            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["layout"], "STANDARD_WORKSPACE")
            self.assertEqual(payload["analysis_root"], str((case / "processed").resolve()))

    def test_delivery_gate_output_uses_resolved_analysis_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            create_client_workspace("site_gate", root=root, synthetic=True)
            case = root / "site_gate"
            initialize_client_lifecycle(case)
            (case / "processed" / "trace.json").write_text(
                json.dumps({"schema_version": 1, "entries": []}),
                encoding="utf-8",
            )

            result = evaluate_delivery_gate(case)

            self.assertFalse(result["ready_for_delivery"])
            self.assertTrue((case / "processed" / "delivery_gate.json").is_file())
            self.assertFalse((case / "delivery_gate.json").exists())

    def test_status_exposes_blocking_stop_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "workspaces"
            create_client_workspace("site_d", root=root, synthetic=True)
            case = root / "site_d"
            initialize_client_lifecycle(case)
            record_existing_data_exhaustion(
                case,
                analysis_inventory_ref="analysis_inventory.json",
                reviewed_sources=["input/source.csv"],
            )
            publish_client_requests(case, [{
                "request_id": "Q-1",
                "request_type": "MICRO_QUESTION",
                "client_question": "Le site était-il fermé mardi entre 02:00 et 03:00 ?",
                "internal_reason": "La réponse distingue une activité légitime d'une charge hors horaires.",
                "hypotheses_distinguished": ["activité légitime", "charge hors horaires"],
                "plausible_answers": [
                    {
                        "answer_id": "CLOSED",
                        "label": "Fermé",
                        "decision_effects": ["renforce la piste"],
                    },
                    {
                        "answer_id": "OPEN",
                        "label": "Ouvert",
                        "decision_effects": ["écarte la piste"],
                    },
                ],
                "decision_impact_dimensions": ["evidence_level"],
                "target_role": "responsable de site",
                "expected_source_type": "CLIENT_DECLARATION",
                "effort": 1,
                "availability": 0.9,
                "reliability": 0.7,
                "importance": "BLOCKING",
                "related_hypothesis_ids": ["H-1"],
                "related_finding_ids": ["F-1"],
                "related_component_ids": [],
            }])

            waiting = inspect_case_status(case)
            self.assertEqual(
                waiting["next_action"],
                "WAIT_OR_RECORD_RECEIVED_ANSWERS_AND_STOP",
            )
            self.assertEqual(waiting["open_question_count"], 1)

            record_canonical_answers(case, [{
                "answer_id": "A-1",
                "request_id": "Q-1",
                "answer": "Le site était fermé.",
                "provided_by_role": "responsable de site",
                "source_or_evidence": "réponse datée",
                "source_type": "CLIENT_DECLARATION",
                "provided_at_utc": "2026-09-04T08:00:00+02:00",
                "reliability": 0.7,
            }])
            resuming = inspect_case_status(case)
            self.assertEqual(
                resuming["next_action"],
                "RECALCULATE_REVIEW_AND_COMPLETE_RESUME",
            )
            self.assertEqual(resuming["response_count"], 1)


if __name__ == "__main__":
    unittest.main()
