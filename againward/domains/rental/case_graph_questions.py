"""Deterministic questions over observations, without selecting reader worlds.

Shared model labels, pages and values do not establish occurrence identity.
Before attachment is reviewed, only exact proof positions or explicitly
source-scoped fields can establish a contradiction slot.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from againward.evidence.hashing import stable_hash

SOURCE_FIELDS = frozenset({"document_role", "document_status"})


def observation_questions(graph: dict[str, Any]) -> dict[str, Any]:
    slots: dict[str, list[str]] = defaultdict(list)
    issues: dict[str, Any] = {}

    def add(kind: str, source: str, observation_ids: list[str], **details: Any) -> None:
        body = {"kind": kind, "source_id": source,
                "observation_ids": sorted(observation_ids), "details": details,
                "state": "OPEN", "materiality": "POTENTIALLY_MATERIAL"}
        identity = {"kind": kind, "source_id": source, "observation_ids": sorted(observation_ids),
                    "details": {key: value for key, value in details.items() if key != "corroborated"}}
        issues["issue-" + stable_hash(identity)] = body

    for oid, observation in graph["observations"].items():
        field = observation["semantic_type"]
        scope = "SOURCE" if field in SOURCE_FIELDS else "UNASSIGNED"
        proof = None if scope == "SOURCE" else {
            "location": observation["location"], "span": observation["source_span"],
            "unit_sha256": observation["unit_sha256"],
            # A visual page without a text span is not an occurrence anchor.
            "visual_observation": oid if observation["source_span"] is None else None}
        slot = {"source_id": observation["source_id"], "semantic_type": field,
                "scope": scope, "proof": proof}
        slots[stable_hash(slot)].append(oid)
        readings = {origin["reading_id"] for origin in observation["origins"]}
        hashes_by_role: dict[str, set[str]] = defaultdict(set)
        for rid in readings:
            reading = graph["readings"][rid]
            hashes_by_role[reading["role"]].add(reading["extraction"]["extraction_sha256"])
        # Relabeling a single saved response as an independent read is not
        # corroboration. Independence itself will be bound by runtime receipts.
        corroborated = any(p != r for p in hashes_by_role["PRIMARY"]
                           for r in hashes_by_role["INDEPENDENT"])
        add("OBSERVATION_REVIEW", observation["source_id"], [oid],
            scope=scope, corroborated=corroborated,
            visual=observation["visual_binding"] is not None)
    for ids in slots.values():
        rows = [graph["observations"][oid] for oid in ids]
        if len({stable_hash(row["value"]) for row in rows}) > 1:
            add("SEMANTIC_CONFLICT", rows[0]["source_id"], ids,
                semantic_type=rows[0]["semantic_type"])
    for rid, reading in graph["readings"].items():
        extraction = reading["extraction"]
        if not extraction["candidates"]:
            add("EMPTY_READING", extraction["source_id"], [], reading_id=rid)
        for limitation in extraction["limitations"]:
            add("READING_LIMITATION", extraction["source_id"], [],
                reading_id=rid, limitation=limitation)
    return dict(sorted(issues.items()))
