"""V2 evidence store. Reader group labels are lineage, never occurrence identity.

Import checks the existing exact native/pixel boundary again. This module does
not promote facts, infer authority or make an observation a business entity.
"""
from __future__ import annotations

from copy import deepcopy
from collections.abc import Callable
from pathlib import Path
from typing import Any

from againward.core.artifact_store import read_json, transaction, write_json
from againward.documents.contracts import DocumentError, SourceBatch, closed
from againward.documents.extraction import replay_extraction
from againward.documents.sources import verify_batch
from againward.evidence.hashing import stable_hash

from .case_graph_questions import observation_questions

VERSION = "againward-rental-case-graph-v2"


def _shape(graph: dict[str, Any]) -> None:
    closed(graph, {"schema_version", "batch", "readings", "observations", "occurrences",
                   "relations", "issues", "reviews", "actions"})
    if graph["schema_version"] != VERSION:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown graph version")
    if any(not isinstance(graph[key], dict) for key in (
            "batch", "readings", "observations", "occurrences", "relations", "issues", "reviews")):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Graph maps required")
    if not isinstance(graph["actions"], list):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Graph action log required")
    for reading in graph["readings"].values():
        closed(reading, {"role", "extraction"})
        if not isinstance(reading["extraction"], dict):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Reading extraction required")


def empty_graph(batch: SourceBatch) -> dict[str, Any]:
    return {"schema_version": VERSION, "batch": batch.to_dict(),
            "readings": {}, "observations": {}, "occurrences": {},
            "relations": {}, "issues": {}, "reviews": {}, "actions": []}


def graph_hash(graph: dict[str, Any]) -> str:
    return stable_hash(graph)


def state_hash(graph: dict[str, Any]) -> str:
    """Semantic/evidence state, separate from the causal receipt sequence."""
    return stable_hash({key: value for key, value in graph.items() if key != "actions"})


def import_reading(graph: dict[str, Any], payload: dict[str, Any], root: Path,
                   *, role: str) -> dict[str, Any]:
    """Pure, idempotent import; exact evidence equivalence preserves both readings.

    Different spans/pages/values remain different observations. Coalescing these
    requires an explicit later semantic decision, not identical model labels.
    """
    _shape(graph)
    if not isinstance(role, str) or role not in {"PRIMARY", "INDEPENDENT", "RECOVERY"}:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown reading role")
    batch = SourceBatch.from_dict(graph["batch"])
    extraction = replay_extraction(deepcopy(payload), batch, root)
    reading_hash = extraction.to_dict()["extraction_sha256"]
    reading_id = "reading-" + stable_hash({"hash": reading_hash, "role": role})
    if reading_id in graph["readings"]:
        return deepcopy(graph)
    result = deepcopy(graph)
    result["readings"][reading_id] = {"role": role, "extraction": extraction.to_dict()}
    bindings = {row["location"]: row for row in extraction.visual_bindings}
    for candidate in extraction.candidates:
        # Model/prompt/invocation identify the reading, not the source pixels.
        visual = bindings.get(candidate.location)
        pixel_proof = ({key: visual[key] for key in (
            "render_sha256", "render_version", "render_dpi", "reader_version")}
            if visual else None)
        atom = {"source_id": extraction.source_id,
                "source_sha256": extraction.source_sha256,
                "reader_version": extraction.reader_version,
                "location": candidate.location, "unit_sha256": candidate.unit_sha256,
                "source_span": list(candidate.source_span) if candidate.source_span else None,
                "visual_binding": pixel_proof, "quote": candidate.raw_observed_value,
                "semantic_type": candidate.semantic_type, "value_type": candidate.value_type,
                "value": candidate.value}
        observation_id = "obs-" + stable_hash(atom)
        origin = {"reading_id": reading_id, "candidate_id": candidate.candidate_id,
                  "model_label": candidate.entity_id,
                  "normalization_notes": candidate.normalization_notes,
                  "ambiguity_flags": list(candidate.ambiguity_flags)}
        row = result["observations"].setdefault(observation_id, {
            **atom, "origins": [], "disposition": "UNRESOLVED"})
        row["origins"].append(origin)
        row["origins"].sort(key=stable_hash)
    questions = observation_questions(result)
    for qid, question in questions.items():
        if qid in result["issues"]:
            question["state"] = result["issues"][qid]["state"]
    questions.update({qid: issue for qid, issue in result["issues"].items() if issue.get("origin") == "ACTION"})
    result["issues"] = questions
    result["actions"].append({"type": "IMPORT_READING", "reading_id": reading_id,
                              "validator_version": VERSION, "result": "ACCEPTED",
                              "pre_state_hash": state_hash(graph),
                              "post_state_hash": state_hash(result)})
    return result


def replay_evidence(graph: dict[str, Any], root: Path) -> dict[str, Any]:
    """Revalidate persisted evidence against current bytes before using the store.

    Runtime imports and semantic proposals share an ordered journal. Recompute
    every event instead of trusting editable graph snapshots or receipt hashes.
    """
    _shape(graph)
    batch = SourceBatch.from_dict(graph["batch"])
    verify_batch(batch, root)
    rebuilt = empty_graph(batch)
    for event in graph["actions"]:
        if isinstance(event, dict) and event.get("type") == "POST_CALC_OBJECTION":
            from .case_post_calculation import _reduce_replayed_objections
            closed(event, {"type", "receipt_sha256", "validator_version", "pre_state_hash", "post_state_hash"})
            rebuilt = _reduce_replayed_objections(rebuilt, event["receipt_sha256"], root)
            continue
        if isinstance(event, dict) and event.get("type") == "SOURCE_READ":
            from .case_graph_reader import reduce_read
            closed(event, {"type", "receipt_sha256", "validator_version", "pre_state_hash", "post_state_hash"},
                   optional={"source_id", "inspected_locations", "source_unit_locations", "prior_full_read"})
            rebuilt = reduce_read(rebuilt, event["receipt_sha256"], root)
            continue
        if isinstance(event, dict) and event.get("type") == "CLAIM_PROPOSAL":
            from .case_graph_claims import reduce_claim
            closed(event, {"type", "action_id", "action", "validator_version", "result",
                           "pre_state_hash", "post_state_hash", "rejection_code"})
            rebuilt = reduce_claim(rebuilt, event["action"], validator_version=event["validator_version"])
            continue
        if isinstance(event, dict) and event.get("type") == "RELATION_REFRESH":
            from .case_graph_relations import reduce_relations
            closed(event, {"type", "validator_version", "pre_state_hash", "post_state_hash"})
            rebuilt = reduce_relations(rebuilt)
            continue
        if isinstance(event, dict) and event.get("type") == "MODEL_REVIEW":
            from .case_graph_review import reduce_review
            closed(event, {"type", "receipt_sha256", "validator_version", "pre_state_hash", "post_state_hash"})
            rebuilt = reduce_review(rebuilt, event["receipt_sha256"], root)
            continue
        if isinstance(event, dict) and event.get("type") == "SEMANTIC_ACTION":
            from .case_graph_actions import reduce_action
            closed(event, {"type", "action_id", "action", "validator_version", "result",
                           "pre_state_hash", "post_state_hash", "rejection_code"})
            rebuilt = reduce_action(rebuilt, event["action"], validator_version=event["validator_version"])
            continue
        closed(event, {"type", "reading_id", "validator_version", "result",
                       "pre_state_hash", "post_state_hash"})
        if event["type"] != "IMPORT_READING" or not isinstance(event["reading_id"], str):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown evidence event")
        reading = graph["readings"].get(event["reading_id"])
        if reading is None:
            raise DocumentError("SOURCE_CHANGED", "Event reading is absent")
        rebuilt = import_reading(rebuilt, reading["extraction"], root, role=reading["role"])
    if rebuilt != graph:
        raise DocumentError("SOURCE_CHANGED", "Graph differs from replayed evidence")
    return rebuilt


def save_evidence(graph: dict[str, Any], root: Path) -> Path:
    """Content addressed, case-local snapshot; no mutable authority cache."""
    replay_evidence(graph, root)
    path = root / "case_graph_v2" / (graph_hash(graph) + ".json")
    with transaction(root):
        if path.exists():
            if read_json(path) != graph:
                raise DocumentError("SOURCE_CHANGED", "Graph snapshot was mutated")
        else:
            write_json(path, graph)
    return path


def commit_transition(graph: dict[str, Any], root: Path,
                      transition: Callable[[dict[str, Any]], dict[str, Any]]) -> dict[str, Any]:
    """Single transactional persistence path for Python-validated graph events."""
    head = root / "case_graph_v2" / "head.json"
    with transaction(root):
        if head.exists() and read_json(head).get("graph_sha256") != graph_hash(graph):
            raise DocumentError("REVIEW_STALE", "A concurrent action changed the graph head")
        replay_evidence(graph, root)
        result = transition(deepcopy(graph))
        save_evidence(result, root)  # Replay the entire result before the commit point.
        write_json(head, {"graph_sha256": graph_hash(result)})
    return result
