from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from energy_mvp.evidence_plane import (
    EvidenceDataset,
    boundary_ledger,
    contrast_surface,
    relationship_loss_certificate,
    support_atlas,
)
from energy_mvp.evidence_protocol import (
    EvidenceQuerySession,
    QueryBudget,
    validate_finding_provenance,
)
from energy_mvp.io import load_data


class EvidencePlaneTests(unittest.TestCase):
    def dataset(self) -> EvidenceDataset:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        )
        with handle:
            handle.write("timestamp,energy_kwh,production_active,temperature_c,machine_mode\n")
            for index in range(40):
                active = index >= 20
                handle.write(
                    f"2026-01-{1 + index // 24:02d} {index % 24:02d}:00,"
                    f"{10 + active * 5},{str(active).lower()},{5 + active * 2},"
                    f"{'run' if active else 'idle'}\n"
                )
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        loaded = load_data(path)
        return EvidenceDataset.from_loaded_data(loaded, source_sha256="a" * 64)

    def query(self, dataset: EvidenceDataset, query_id: str, operation: str, arguments: dict) -> dict:
        return {
            "schema_version": "indicia-evidence-query-v1",
            "query_id": query_id,
            "dataset_id": dataset.dataset_id,
            "operation": operation,
            "arguments": arguments,
            "purpose": "Tester une hypothèse explicite sans décider automatiquement.",
        }

    def test_dataset_round_trip_preserves_auxiliary_raw_and_hash(self) -> None:
        dataset = self.dataset()

        restored = EvidenceDataset.from_dict(dataset.to_dict())

        self.assertEqual(restored.to_dict(), dataset.to_dict())
        auxiliary = next(item for item in dataset.fields if item["origin"] == "auxiliary")
        self.assertEqual(auxiliary["original_name"], "machine_mode")
        self.assertEqual(restored.raw_auxiliary_for_row(2)[auxiliary["key"]], "idle")

    def test_contrast_relation_inverts_when_groups_are_reversed(self) -> None:
        rows = [
            {"group": "a", "value": value} for value in (1, 2, 3, 4, 5)
        ] + [{"group": "b", "value": value} for value in (6, 7, 8, 9, 10)]

        forward = contrast_surface(rows, group_field="group", left_value="a", right_value="b", fields=["value"])
        reverse = contrast_surface(rows, group_field="group", left_value="b", right_value="a", fields=["value"])

        forward_value = forward["field_evidence"][0]["median_difference_right_minus_left"]
        reverse_value = reverse["field_evidence"][0]["median_difference_right_minus_left"]
        self.assertEqual(forward_value, -reverse_value)
        self.assertIsNone(forward["decision"])

    def test_support_atlas_exposes_dimension_loss_and_blocks_outcome_leakage(self) -> None:
        reference = [
            {"shift": "day", "temperature": value, "energy": 10 + value}
            for value in (10, 11, 12, 13, 14, 15)
        ]
        target = [
            {"shift": "day", "temperature": 12, "energy": 30},
            {"shift": "night", "temperature": 30, "energy": 40},
        ]
        dimensions = [
            {"field": "shift", "kind": "categorical"},
            {"field": "temperature", "kind": "numeric", "tolerance": 2},
        ]

        result = support_atlas(reference, target, dimensions=dimensions, minimum_controls=1)

        self.assertGreaterEqual(
            result["sequential_support"][0]["coverage_with_minimum_controls"],
            result["full_support"]["coverage_with_minimum_controls"],
        )
        self.assertTrue(result["outcome_blind"])
        with self.assertRaisesRegex(ValueError, "outcome"):
            support_atlas(
                reference,
                target,
                dimensions=[{"field": "energy", "kind": "numeric", "tolerance": 2}],
                forbidden_outcome_fields=["energy"],
            )

    def test_boundary_localizes_numeric_and_missingness_change_but_does_not_decide(self) -> None:
        rows = []
        for index in range(100):
            rows.append(
                {
                    "order": index,
                    "energy": 10 if index < 50 else 30,
                    "context": "known" if index < 50 else None,
                    "temperature": 5 if index < 50 else 20,
                }
            )

        result = boundary_ledger(
            rows,
            order_field="order",
            fields=["energy", "context", "temperature"],
            minimum_segment_rows=15,
            comparison_window_rows=20,
            maximum_candidates=5,
        )

        self.assertLessEqual(abs(result["candidates"][0]["boundary_index"] - 50), 2)
        evidence = {item["field"]: item for item in result["candidates"][0]["field_evidence"]}
        self.assertLess(evidence["context"]["completeness_difference_after_minus_before"], 0)
        self.assertIn("seasonality", result["mandatory_alternatives"])
        self.assertGreater(evidence["temperature"]["field_score"], 0)
        self.assertIsNone(result["decision"])

    def test_boundary_ledger_surfaces_both_start_and_shutdown_changes_generically(self) -> None:
        rows = []
        for index in range(140):
            active = 35 <= index < 95
            rows.append(
                {
                    "order": index,
                    "energy": 50 if active else 12,
                    "operating_state": "active" if active else "inactive",
                    "aux_feedback": 1 if active else 0,
                }
            )

        result = boundary_ledger(
            rows,
            order_field="order",
            fields=["energy", "operating_state", "aux_feedback"],
            minimum_segment_rows=15,
            comparison_window_rows=20,
            maximum_candidates=8,
        )
        boundaries = [item["boundary_index"] for item in result["candidates"]]

        self.assertTrue(any(abs(value - 35) <= 2 for value in boundaries))
        self.assertTrue(any(abs(value - 95) <= 2 for value in boundaries))
        self.assertEqual(result["status"], "decision_neutral_query_candidates")

    def test_relationship_certificate_counts_loss_without_pair_materialization(self) -> None:
        result = relationship_loss_certificate(
            ["a", "b", "c", "d"], summarized_relations=[("a", "b")]
        )

        self.assertEqual(result["possible_pairwise_relations"], 6)
        self.assertEqual(result["omitted_pairwise_relation_count"], 5)
        self.assertTrue(result["raw_retrieval_is_executable"])

    def test_protocol_validates_unknown_arguments_and_audits_rejection(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(dataset)
        request = self.query(dataset, "bad", "describe_schema", {"python": "import os"})

        with self.assertRaisesRegex(ValueError, "inconnu"):
            session.execute(dataset, request)

        self.assertEqual(session.calls[0]["status"], "rejected")

    def test_protocol_stops_semantic_repetition_even_with_a_new_id(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(dataset)
        first = self.query(dataset, "q1", "describe_schema", {})
        second = self.query(dataset, "q2", "describe_schema", {})

        session.execute(dataset, first)
        with self.assertRaisesRegex(ValueError, "répétée"):
            session.execute(dataset, second)

        self.assertEqual([item["status"] for item in session.calls], ["success", "rejected"])

    def test_protocol_rejects_support_work_above_the_session_pair_budget(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(
            dataset, budget=QueryBudget(maximum_pair_comparisons=100)
        )
        request = self.query(
            dataset,
            "support",
            "support_atlas",
            {
                "split_field": "production_active",
                "reference_value": False,
                "target_value": True,
                "dimensions": [{"field": "outside_temperature_c", "kind": "numeric", "tolerance": 3}],
            },
        )

        with self.assertRaisesRegex(ValueError, "au-dessus de la borne"):
            session.execute(dataset, request)

        self.assertEqual(session.pair_comparisons_used, 0)

    def test_retrieval_handle_resolves_exact_rows_and_raw_auxiliary(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(dataset)
        auxiliary = next(item["key"] for item in dataset.fields if item["origin"] == "auxiliary")
        contrast = session.execute(
            dataset,
            self.query(
                dataset,
                "contrast",
                "contrast_surface",
                {
                    "group_field": "production_active",
                    "left_value": False,
                    "right_value": True,
                    "fields": ["energy_kwh", auxiliary],
                },
            ),
        )
        left_handle = contrast["retrieval_handles"][0]["handle"]

        raw = session.execute(
            dataset,
            self.query(
                dataset,
                "raw",
                "raw_slice",
                {
                    "handle": left_handle,
                    "fields": ["timestamp", auxiliary],
                    "limit": 3,
                    "representation": "raw_auxiliary",
                },
            ),
        )

        self.assertEqual(raw["result"]["returned"], 3)
        self.assertTrue(all(item[auxiliary] == "idle" for item in raw["result"]["rows"]))
        self.assertTrue(all(item["source_row"] >= 2 for item in raw["result"]["rows"]))

    def test_call_and_row_budgets_are_enforced(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(
            dataset,
            budget=QueryBudget(maximum_calls=2, maximum_returned_rows=2),
        )
        session.execute(
            dataset,
            self.query(dataset, "rows", "raw_slice", {"fields": ["energy_kwh"], "limit": 2}),
        )
        with self.assertRaisesRegex(ValueError, "lignes retournées"):
            session.execute(
                dataset,
                self.query(dataset, "more", "raw_slice", {"fields": ["power_kw"], "limit": 1}),
            )
        self.assertEqual(session.status, "open")  # Rejections have their own bounded allowance.

    def test_session_round_trip_detects_tampering(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(dataset)
        session.execute(dataset, self.query(dataset, "overview", "describe_schema", {}))
        payload = session.to_dict()

        restored = EvidenceQuerySession.from_dict(payload)
        self.assertEqual(restored.to_dict(), payload)
        payload["usage"]["calls"] = 0
        with self.assertRaisesRegex(ValueError, "hash de session"):
            EvidenceQuerySession.from_dict(payload)

    def test_finding_provenance_accepts_abstention_and_rejects_unknown_evidence(self) -> None:
        dataset = self.dataset()
        session = EvidenceQuerySession.create(dataset)
        response = session.execute(dataset, self.query(dataset, "overview", "describe_schema", {}))
        handle = response["retrieval_handles"][0]["handle"]
        self.assertEqual(
            response["evidence_sufficiency"]["status"], "requires_agent_assessment"
        )
        self.assertEqual(
            response["uncertainty"]["status"], "not_resolved_by_deterministic_tool"
        )
        valid = {
            "schema_version": "indicia-agent-findings-v1",
            "ground_truth_used": False,
            "findings": [
                {
                    "finding_id": "F01",
                    "status": "A_CONSERVER_AVEC_RESERVES",
                    "claim_or_abstention": "Relation à approfondir.",
                    "evidence_query_ids": ["overview"],
                    "evidence_handles": [handle],
                    "alternative_explanations_tested": ["qualité des données"],
                },
                {
                    "finding_id": "F02",
                    "status": "ABSTAIN",
                    "claim_or_abstention": "Abstention sur la cause.",
                    "evidence_query_ids": [],
                    "evidence_handles": [],
                    "evidence_gap": "Aucune variable équipement.",
                },
            ],
        }

        validate_finding_provenance(valid, session)
        valid["findings"][0]["evidence_handles"] = ["evh-unknown"]
        with self.assertRaisesRegex(ValueError, "inconnue"):
            validate_finding_provenance(valid, session)


if __name__ == "__main__":
    unittest.main()
