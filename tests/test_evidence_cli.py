from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from energy_mvp.evidence_cli import execute_case_query, validate_case_findings
from energy_mvp.workflow import prepare_investigation


class EvidenceCliTests(unittest.TestCase):
    def prepared_case(self, root: Path) -> Path:
        source = root / "source.csv"
        rows = ["timestamp,energy_kwh,production_active,machine_mode"]
        for index in range(12):
            rows.append(
                f"2026-01-01 {index:02d}:00,{5 + index},{str(index >= 6).lower()},"
                f"{'run' if index >= 6 else 'idle'}"
            )
        source.write_text("\n".join(rows) + "\n", encoding="utf-8")
        case = root / "case"
        prepare_investigation(source, case)
        return case

    def write_request(self, root: Path, dataset_id: str, query_id: str = "overview") -> Path:
        path = root / f"{query_id}.json"
        path.write_text(
            json.dumps(
                {
                    "schema_version": "indicia-evidence-query-v1",
                    "query_id": query_id,
                    "dataset_id": dataset_id,
                    "operation": "describe_schema",
                    "arguments": {},
                    "purpose": "Inventorier la preuve disponible avant de choisir un contraste.",
                }
            ),
            encoding="utf-8",
        )
        return path

    def test_case_query_persists_response_session_and_trace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.prepared_case(root)
            state = json.loads((case / "investigation_state.json").read_text())
            request = self.write_request(root, state["evidence_plane"]["dataset_id"])

            response = execute_case_query(case, request)

            self.assertIsNone(response["decision"])
            self.assertTrue((case / "evidence_queries" / "overview.json").exists())
            session = json.loads((case / "evidence_query_session.json").read_text())
            self.assertEqual(session["usage"]["calls"], 1)
            trace = json.loads((case / "trace.json").read_text())
            self.assertEqual(trace["entries"][-1]["action"], "evidence_query_executed")

    def test_rejected_request_is_persisted_in_the_audit_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.prepared_case(root)
            state = json.loads((case / "investigation_state.json").read_text())
            request = self.write_request(root, state["evidence_plane"]["dataset_id"])
            payload = json.loads(request.read_text())
            payload["arguments"] = {"arbitrary_code": "open('/etc/passwd').read()"}
            request.write_text(json.dumps(payload), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "inconnu"):
                execute_case_query(case, request)

            session = json.loads((case / "evidence_query_session.json").read_text())
            self.assertEqual(session["calls"][0]["status"], "rejected")
            trace = json.loads((case / "trace.json").read_text())
            self.assertEqual(trace["entries"][-1]["action"], "evidence_query_rejected")

    def test_agent_findings_validation_uses_persisted_handles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            case = self.prepared_case(root)
            state = json.loads((case / "investigation_state.json").read_text())
            request = self.write_request(root, state["evidence_plane"]["dataset_id"])
            response = execute_case_query(case, request)
            findings = root / "findings.json"
            findings.write_text(
                json.dumps(
                    {
                        "schema_version": "indicia-agent-findings-v1",
                        "ground_truth_used": False,
                        "findings": [
                            {
                                "finding_id": "F01",
                                "status": "A_CONSERVER_AVEC_RESERVES",
                                "claim_or_abstention": "Le contexte mérite un test ciblé.",
                                "evidence_query_ids": ["overview"],
                                "evidence_handles": [response["retrieval_handles"][0]["handle"]],
                                "alternative_explanations_tested": ["export incomplet"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = validate_case_findings(case, findings)

            self.assertEqual(result, {"status": "valid", "findings": 1})


if __name__ == "__main__":
    unittest.main()
