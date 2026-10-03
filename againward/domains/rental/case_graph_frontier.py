"""Current material evidence accounting, a prerequisite rather than READY.

This view is evaluated on a replay-verified graph by the calculation boundary.
Persisted issue/disposition flags are not approvals. Unrecognized issue kinds
remain visible and blocking until an explicit supported resolution exists.
"""
from __future__ import annotations

from typing import Any

from againward.evidence.hashing import stable_hash

from .case_graph_claims import READING_ISSUES, current_claims, observation_disposition
from .case_graph_relations import relation_view
from .case_graph_review import current_review


def materiality_frontier(graph: dict[str, Any]) -> dict[str, Any]:
    dispositions = {oid: observation_disposition(graph, oid)
                    for oid in sorted(graph["observations"])}
    relations = relation_view(graph)
    blockers: list[dict[str, Any]] = []
    for target in sorted(graph["occurrences"]):
        for kind in ("CHARGE_MEANING", "GOVERNING_TERM"):
            claims = current_claims(graph, kind, target)
            if len({claim["proposal"]["value"] for claim in claims}) > 1:
                blockers.append({"kind": "COMMERCIAL_CLAIM_CONFLICT", "target": target,
                                 "source_id": graph["occurrences"][target]["source_id"],
                                 "claim_kind": kind})
    for oid, disposition in dispositions.items():
        if disposition == "UNRESOLVED":
            blockers.append({"kind": "OBSERVATION_UNRESOLVED", "target": oid,
                             "source_id": graph["observations"][oid]["source_id"]})
    for iid, issue in sorted(graph["issues"].items()):
        kind = issue["kind"]
        ids = issue["observation_ids"]
        settled = False
        if kind == "OBSERVATION_REVIEW":
            settled = bool(ids) and all(dispositions.get(oid, "UNRESOLVED") != "UNRESOLVED" for oid in ids)
        elif kind == "SEMANTIC_CONFLICT":
            # Rejecting one interpretation may settle the conflict; approving
            # both incompatible values never does. No issue flag can override it.
            active = [graph["observations"][oid] for oid in ids
                      if dispositions.get(oid) in {"USED", "DUPLICATE"}]
            settled = (bool(ids) and all(dispositions.get(oid, "UNRESOLVED") != "UNRESOLVED" for oid in ids)
                       and len({stable_hash((row["semantic_type"], row["value"])) for row in active}) <= 1)
        elif kind == "SEMANTIC_CLAIM":
            settled = (current_review(graph, iid) or {}).get("verdict") == "SUPPORTED"
        elif kind == "OCCURRENCE_REVIEW":
            target = issue.get("details", {}).get("target")
            settled = target in graph["occurrences"] and (current_review(graph, target) or {}).get("verdict") == "SUPPORTED"
        elif kind == "RELATIONSHIP":
            relation = relations.get(issue.get("details", {}).get("relation_id"))
            settled = bool(relation and relation["state"] in {"CONFIRMED", "REJECTED"})
        elif kind == "POST_CALC_OBJECTION":
            resolutions = current_claims(graph, "POST_CALC_RESOLUTION", iid)
            settled = len({row["proposal"]["value"] for row in resolutions}) == 1
        elif kind in READING_ISSUES:
            resolutions = current_claims(graph, "READING_ISSUE_RESOLUTION", iid)
            settled = len({row["proposal"]["value"] for row in resolutions}) == 1
        if not settled:
            blockers.append({"kind": kind, "target": iid, "source_id": issue.get("source_id")})
    # Empty/unread sources cannot disappear from the frontier merely because
    # the investigator selected useful evidence elsewhere in the dossier.
    read_sources = {reading["extraction"]["source_id"] for reading in graph["readings"].values()}
    for document in graph["batch"]["documents"]:
        if document["source_id"] not in read_sources:
            blockers.append({"kind": "SOURCE_UNREAD", "target": document["source_id"],
                             "source_id": document["source_id"]})
    for sid in sorted(read_sources):
        scoped = [event for event in graph["actions"] if event.get("source_id") == sid and "inspected_locations" in event]
        legacy_import = any(event["type"] == "IMPORT_READING" and graph["readings"][event["reading_id"]]["extraction"]["source_id"] == sid
                            for event in graph["actions"])
        if scoped and not legacy_import and not any(event["prior_full_read"] for event in scoped):
            inspected = {location for event in scoped for location in event["inspected_locations"]}
            required = set(scoped[-1]["source_unit_locations"])
            if required - inspected:
                blockers.append({"kind": "SOURCE_PARTIALLY_READ", "target": sid, "source_id": sid,
                                 "missing_locations": sorted(required - inspected)})
    return {"observations": dispositions, "blockers": sorted(blockers, key=stable_hash),
            "accounted_for": not blockers}
