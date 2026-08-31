"""Représentation probatoire compacte, relation-aware et récupérable."""

from __future__ import annotations

from typing import Any

from .evidence_plane import EvidenceDataset, relationship_loss_certificate
from .evidence_protocol import EvidenceQuerySession, query_contract


LEGACY_CAPABILITY_REGISTRY = [
    {
        "capability": "generic_multi_event_detection",
        "status": "retained_candidate_generation",
        "production_role": "legacy evidence and fallback; never a confirmed finding",
        "implementation": "energy_mvp.signals.detect_candidate_events",
    },
    {
        "capability": "H01_intervention_effect",
        "status": "research_regression_only",
        "production_role": "no fixed production conclusion; compose contrast/support queries when relevant",
    },
    {
        "capability": "H02_temporal_coupling",
        "status": "research_regression_only",
        "production_role": "legacy evidence pattern; agent selects temporal contrasts dynamically",
    },
    {
        "capability": "H03_flexibility_envelope",
        "status": "rejected_current_candidate_retained_as_negative_evidence",
        "production_role": "not promoted; Stage 2 regression evidence remains frozen",
    },
    {
        "capability": "H05_natural_experiment",
        "status": "research_regression_only",
        "production_role": "no automatic recoverability claim; support/contrast tools may test a chosen experiment",
    },
]


def build_evidence_card(
    dataset: EvidenceDataset,
    *,
    inspection: dict[str, Any],
    candidates: dict[str, Any],
    session: EvidenceQuerySession,
) -> dict[str, Any]:
    """Construit un point de départ compact, sans lignes brutes ni diagnostic."""

    compact_candidates = [
        {
            key: event.get(key)
            for key in ("event_id", "type", "start", "end", "status", "score_kw")
            if key in event
        }
        for event in candidates.get("events", [])
    ]
    certificate = relationship_loss_certificate(
        sorted(dataset.field_keys), omitted_examples_limit=10
    )
    return {
        "schema_version": "indicia-evidence-card-v2",
        "status": "initial_evidence_not_a_conclusion",
        "dataset": {
            "dataset_id": dataset.dataset_id,
            "dataset_sha256": dataset.dataset_sha256,
            "source_sha256": dataset.source_sha256,
            "rows": len(dataset.rows),
            "period": {"start": inspection.get("start"), "end": inspection.get("end")},
            "measurement_kind": dataset.measurement_kind,
            "frequency_minutes": inspection.get("frequency_minutes"),
            "coverage_ratio": inspection.get("coverage_ratio"),
        },
        "field_inventory": dataset.fields,
        "data_quality": inspection.get("quality", {}),
        "legacy_candidate_evidence": {
            "classification": "candidate evidence only",
            "status": candidates.get("status"),
            "events": compact_candidates,
            "disabled_signal_families": candidates.get("disabled_signal_families", []),
        },
        "relationship_loss": certificate,
        "retrieval": {
            "session_id": session.session_id,
            "dataset_snapshot": "evidence_dataset.json",
            "session_state": "evidence_query_session.json",
            "request_command": "python query_evidence.py CASE_DIRECTORY REQUEST.json",
            "raw_rows_embedded": False,
            "raw_auxiliary_retrievable": True,
        },
        "query_capabilities": query_contract()["operations"],
        "legacy_capability_registry": LEGACY_CAPABILITY_REGISTRY,
        "agent_workflow": [
            "inspect this overview and formulate competing hypotheses",
            "request a bounded contrast, support, boundary or source slice",
            "test the strongest alternative explanation",
            "repeat only when the next query can change the decision",
            "record an evidence-linked finding or abstain",
        ],
        "decision": None,
    }
