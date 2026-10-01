"""Bounded structural proposals against V2 state, with a single replay reducer.

Acceptance here means an admissible proposal, NOT reviewed commercial truth.
Occurrences remain PROPOSED until the independent semantic review boundary.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from againward.documents.contracts import DocumentError, closed
from againward.evidence.hashing import stable_hash

VERSION = "rental-graph-actions-v1"
KINDS = frozenset({"INVOICE_LINE", "RENTAL_SCOPE", "RATE_TERM", "EVENT", "CREDIT", "SUPPORTING_RECORD"})
KEYS = {"type", "target", "kind", "evidence_ids", "anchor_ids"}


def observation_dependency(row: dict[str, Any]) -> str:
    # Reader labels and another equivalent read do not alter the evidence.
    return stable_hash({key: value for key, value in row.items() if key not in {"origins", "disposition"}})


def _ids(value: Any) -> list[str]:
    if (not isinstance(value, list) or not value or len(value) > 64
            or any(not isinstance(item, str) or len(item) > 160 for item in value)
            or len(value) != len(set(value))):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Bounded unique evidence IDs required")
    return sorted(value)


def bind_action(graph: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Python supplies prerequisite hashes; the model supplies semantic intent."""
    closed(proposal, {"type", "evidence_ids"}, optional={"target", "kind", "anchor_ids"})
    proposal = {"target": "", "kind": "", "anchor_ids": [], **proposal}
    if (not isinstance(proposal["type"], str)
            or proposal["type"] not in {"DECLARE_OCCURRENCE", "ATTACH_OBSERVATIONS"}
            or not isinstance(proposal["target"], str) or len(proposal["target"]) > 160
            or not isinstance(proposal["kind"], str)):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown semantic action shape")
    evidence = _ids(proposal["evidence_ids"])
    anchors = _ids(proposal["anchor_ids"]) if proposal["type"] == "DECLARE_OCCURRENCE" else []
    if proposal["type"] == "ATTACH_OBSERVATIONS" and proposal["anchor_ids"] != []:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Attachment cannot replace identity")
    dependencies = {}
    for oid in evidence:
        if oid in graph["observations"]:
            dependencies["observation:" + oid] = observation_dependency(graph["observations"][oid])
    target = proposal["target"]
    if target in graph["occurrences"]:
        dependencies["occurrence:" + target] = stable_hash(graph["occurrences"][target])
    return {**deepcopy(proposal), "evidence_ids": evidence, "anchor_ids": anchors,
            "prerequisites": dependencies}


def _validate_dependencies(graph: dict[str, Any], action: dict[str, Any]) -> None:
    rebound = bind_action(graph, {key: action[key] for key in KEYS})
    if action["prerequisites"] != rebound["prerequisites"]:
        raise DocumentError("REVIEW_STALE", "Action prerequisites changed")


def _fields(graph: dict[str, Any], ids: list[str], source: str) -> dict[str, list[str]]:
    fields: dict[str, list[str]] = {}
    for oid in ids:
        row = graph["observations"].get(oid)
        if row is None or row["source_id"] != source:
            raise DocumentError("SOURCE_LOCATION_INVALID", "Unknown or foreign occurrence evidence")
        fields.setdefault(row["semantic_type"], []).append(oid)
    for ids_for_field in fields.values():
        if len({stable_hash(graph["observations"][oid]["value"]) for oid in ids_for_field}) != 1:
            raise DocumentError("EXTRACTION_CONTRADICTION", "Conflicting field requires an explicit Issue decision")
        ids_for_field.sort()
    return fields


def _change(graph: dict[str, Any], action: dict[str, Any]) -> None:
    _validate_dependencies(graph, action)
    evidence = action["evidence_ids"]
    rows = [graph["observations"].get(oid) for oid in evidence]
    if not rows or any(row is None for row in rows):
        raise DocumentError("SOURCE_LOCATION_INVALID", "Unknown observation")
    sources = {row["source_id"] for row in rows if row is not None}
    if len(sources) != 1:
        raise DocumentError("SOURCE_LOCATION_INVALID", "An occurrence cannot copy foreign facts")
    source = next(iter(sources))
    if action["type"] == "DECLARE_OCCURRENCE":
        if action["kind"] not in KINDS or action["target"]:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Runtime assigns occurrence IDs")
        anchors = action["anchor_ids"]
        if not anchors or not set(anchors) <= set(evidence):
            raise DocumentError("ENTITY_AMBIGUOUS", "Source-bound occurrence witnesses required")
        # This is an auditable identity hypothesis. Exact evidence coordinates
        # establish its technical ID, not its commercial truth or authority.
        identity = {"source_id": source, "kind": action["kind"], "anchor_ids": anchors}
        oid = "occ-" + stable_hash(identity)
        if oid in graph["occurrences"]:
            raise DocumentError("ENTITY_AMBIGUOUS", "Use attachment to extend an existing occurrence")
        graph["occurrences"][oid] = {**identity, "fields": _fields(graph, evidence, source),
            "origin": "MODEL_STRUCTURE_PROPOSAL", "state": "PROPOSED", "revision": 1,
            "authority": "NONE"}
    elif action["type"] == "ATTACH_OBSERVATIONS":
        occurrence = graph["occurrences"].get(action["target"])
        if occurrence is None or occurrence["source_id"] != source or action["kind"]:
            raise DocumentError("ENTITY_AMBIGUOUS", "Known same-source target required")
        existing = {oid for values in occurrence["fields"].values() for oid in values}
        if set(evidence) <= existing:
            return
        occurrence["fields"] = _fields(graph, sorted(existing | set(evidence)), source)
        occurrence["state"] = "PROPOSED"
        occurrence["revision"] += 1
    else:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown semantic action")


def reduce_action(graph: dict[str, Any], action: dict[str, Any]) -> dict[str, Any]:
    """Pure reducer shared by live execution and replay; rejected delta is atomic."""
    from .case_graph import state_hash
    closed(action, KEYS | {"prerequisites"})
    # Validate bounded model notation even during replay; no arbitrary patch API.
    bind_action(graph, {key: action[key] for key in KEYS})
    action_id = "action-" + stable_hash(action)
    if any(row.get("action_id") == action_id for row in graph["actions"]):
        return deepcopy(graph)
    result = deepcopy(graph)
    code = None
    try:
        _change(result, action)
    except DocumentError as exc:
        result = deepcopy(graph)
        code = exc.code
    result["actions"].append({"type": "SEMANTIC_ACTION", "action_id": action_id,
        "action": deepcopy(action), "validator_version": VERSION,
        "pre_state_hash": state_hash(graph), "post_state_hash": state_hash(result),
        "result": "REJECTED" if code else "ACCEPTED_PROPOSAL", "rejection_code": code})
    return result


def apply_action(graph: dict[str, Any], action: dict[str, Any], root: Path) -> dict[str, Any]:
    from .case_graph import replay_evidence
    replay_evidence(graph, root)
    return reduce_action(graph, action)


def commit_action(graph: dict[str, Any], action: dict[str, Any], root: Path) -> dict[str, Any]:
    """Atomically persist the receipt/state and compare-and-swap the local head."""
    from againward.core.artifact_store import read_json, transaction, write_json
    from .case_graph import graph_hash
    head = root / "case_graph_v2" / "head.json"
    with transaction(root):
        if head.exists() and read_json(head).get("graph_sha256") != graph_hash(graph):
            raise DocumentError("REVIEW_STALE", "A concurrent action changed the graph head")
        result = apply_action(graph, action, root)
        sha = graph_hash(result)
        path = root / "case_graph_v2" / (sha + ".json")
        if path.exists() and read_json(path) != result:
            raise DocumentError("SOURCE_CHANGED", "Immutable graph snapshot changed")
        write_json(path, result)
        write_json(head, {"graph_sha256": sha})
    return result
