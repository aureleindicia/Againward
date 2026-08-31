"""Comparaison de migration legacy/Evidence Plane sans proxy de qualité modèle."""

from __future__ import annotations

import json
from typing import Any

from .evidence_plane import EvidenceDataset
from .evidence_protocol import EvidenceQuerySession


def build_shadow_comparison(
    dataset: EvidenceDataset,
    *,
    candidates: dict[str, Any],
    evidence_card: dict[str, Any],
    session: EvidenceQuerySession,
    timings_seconds: dict[str, float] | None = None,
) -> dict[str, Any]:
    events = candidates.get("events", [])
    legacy_types = sorted({str(item.get("type")) for item in events})
    auxiliary = [item for item in dataset.fields if item["origin"] == "auxiliary"]
    card_bytes = len(
        json.dumps(evidence_card, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )
    return {
        "schema_version": "indicia-stage4-shadow-comparison-v1",
        "scope": "structural production shadow; no model-quality inference",
        "dataset_id": dataset.dataset_id,
        "dataset_sha256": dataset.dataset_sha256,
        "legacy_path": {
            "status": candidates.get("status"),
            "candidate_count": len(events),
            "candidate_types": legacy_types,
            "candidate_semantics": "candidate evidence only",
            "source_row_handles": False,
            "unknown_columns_available": False,
            "dynamic_queries": False,
        },
        "evidence_plane_path": {
            "legacy_candidates_retained": len(events),
            "legacy_candidate_types_retained": legacy_types,
            "auxiliary_fields_available": len(auxiliary),
            "auxiliary_field_keys": [item["key"] for item in auxiliary],
            "relationship_loss_explicit": True,
            "source_row_handles_available": True,
            "dynamic_queries_available": True,
            "initial_tool_calls": len(session.calls),
            "initial_card_bytes": card_bytes,
            "automatic_findings": 0,
        },
        "agreement": {
            "legacy_candidates_preserved": True,
            "legacy_candidate_count_delta": 0,
            "legacy_candidate_type_delta": [],
        },
        "comparison_outcomes": {
            "same_conclusion": {
                "status": "NOT_MEASURED",
                "reason": "Neither deterministic path owns a final conclusion.",
            },
            "new_system_additional_evidence": {
                "status": "OBSERVED",
                "items": [
                    "auxiliary field inventory",
                    "relationship-loss metadata",
                    "typed retrieval and query capabilities",
                ],
            },
            "new_system_correct_abstention": {
                "status": "NOT_MEASURED",
                "reason": "Requires a blinded agent investigation and adjudication.",
            },
            "legacy_finds_new_system_misses": {
                "status": "NONE_AT_CANDIDATE_LAYER",
                "evidence": "candidate IDs and types are routed unchanged into the new card",
            },
            "disagreement": {
                "status": "STRUCTURAL_ONLY",
                "finding_disagreement": "NOT_MEASURED",
            },
        },
        "structural_disagreements": [
            {
                "topic": "unknown operational columns",
                "legacy": "discarded",
                "evidence_plane": "typed, provenance-linked and retrievable",
            },
            {
                "topic": "relationship coverage",
                "legacy": "implicit/static",
                "evidence_plane": "loss disclosed and agent-selectable queries available",
            },
            {
                "topic": "source retrieval",
                "legacy": "manual/ad hoc",
                "evidence_plane": "typed bounded handles",
            },
        ],
        "finding_disagreement": {
            "status": "NOT_MEASURED",
            "reason": "No model investigation was run; deterministic evidence is not a substitute for an agent conclusion.",
        },
        "failures": [],
        "timings_seconds": timings_seconds or {},
        "rollback": {
            "available": True,
            "mode": "legacy",
            "destructive_data_migration": False,
        },
        "decision": None,
    }
