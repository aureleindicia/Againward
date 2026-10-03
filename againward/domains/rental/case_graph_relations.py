"""Exact reviewed occurrence links, without copying facts or granting authority.

This view is always recomputed from current subjects and reviews. In particular,
a newly discovered plausible target invalidates uniqueness of an older edge.
An identity link alone never establishes a governing rate or a credit amount.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from pathlib import Path
from typing import Any

from againward.documents.contracts import DocumentError
from againward.evidence.hashing import stable_hash

from .case_graph_review import current_review, review_request

VERSION = "rental-graph-exact-relations-v1"
# Each left occurrence must identify a unique target. These are identity rules,
# not authority/effectivity or financial allocation rules.
POLICIES = (
    ("SAME_RENTAL", "INVOICE_LINE", "RENTAL_SCOPE", (("agreement_id", "asset_id"),
                                                       ("agreement_id", "serial_number"))),
    ("APPLIES_TO", "RATE_TERM", "RENTAL_SCOPE", (("agreement_id", "asset_id"),
                                                   ("agreement_id", "serial_number"))),
    ("BELONGS_TO", "EVENT", "RENTAL_SCOPE", (("agreement_id", "asset_id"),
                                                ("agreement_id", "serial_number"))),
    ("ALLOCATES_TO", "CREDIT", "INVOICE_LINE", (("invoice_id", "invoice_line_id", "currency"),)),
)


def occurrence_values(graph: dict[str, Any], target: str) -> dict[str, Any]:
    result = {}
    for field, ids in graph["occurrences"][target]["fields"].items():
        values = {stable_hash(graph["observations"][oid]["value"]): graph["observations"][oid]["value"]
                  for oid in ids}
        if len(values) != 1:
            raise DocumentError("ENTITY_AMBIGUOUS", "Occurrence contains an unresolved field conflict")
        result[field] = next(iter(values.values()))
    return result


def relation_view(graph: dict[str, Any]) -> dict[str, Any]:
    """Pure current view; stored CONFIRMED state is never a reusable authority."""
    subjects = graph["occurrences"]
    values = {target: occurrence_values(graph, target) for target in subjects}
    reviews = {target: current_review(graph, target) for target in subjects}
    dependencies = {target: {"subject_sha256": review_request(graph, target)["request_sha256"],
        "review": reviews[target]} for target in subjects}
    relations: dict[str, Any] = {}
    for kind, left_kind, right_kind, anchors in POLICIES:
        keys = {key for group in anchors for key in group}
        # Currency is a consistency constraint, not an identity blocking key.
        blocking = keys - {"currency"}
        contradiction_keys = keys | {"supplier_id"}
        if kind != "ALLOCATES_TO":
            contradiction_keys |= {"asset_id", "serial_number"}
        index: dict[tuple[str, str], set[str]] = defaultdict(set)
        for right, subject in subjects.items():
            if subject["kind"] == right_kind:
                for key in blocking:
                    if values[right].get(key) is not None:
                        index[(key, stable_hash(values[right][key]))].add(right)
        for left, subject in sorted(subjects.items()):
            if subject["kind"] != left_kind:
                continue
            targets = set().union(*(index.get((key, stable_hash(values[left][key])), set())
                for key in blocking if values[left].get(key) is not None))
            edges = []
            for right in sorted(targets - {left}):
                if len(relations) >= 20_000:
                    raise DocumentError("RESOURCE_LIMIT", "Narrow the occurrence relationship investigation")
                lv, rv = values[left], values[right]
                support = sorted(key for key in contradiction_keys
                                 if lv.get(key) is not None and lv.get(key) == rv.get(key))
                contradictions = sorted(key for key in contradiction_keys
                    if lv.get(key) is not None and rv.get(key) is not None and lv[key] != rv[key])
                anchored = any(set(group) <= set(support) for group in anchors)
                reviewed = all((reviews[target] or {}).get("verdict") == "SUPPORTED"
                               for target in (left, right))
                state, reason = ("REJECTED", "CONTRADICTING_ANCHORS") if contradictions else (
                    ("CANDIDATE", "INSUFFICIENT_ANCHORS") if not anchored else (
                    ("CONFIRMED", "EXACT_REVIEWED_IDENTIFIERS") if reviewed else
                    ("CANDIDATE", "UNREVIEWED_PREREQUISITE")))
                rid = "rel-" + stable_hash({"type": kind, "left": left, "right": right, "version": VERSION})
                evidence = sorted({oid for target in (left, right)
                    for field in set(support) | set(contradictions)
                    for oid in subjects[target]["fields"].get(field, [])})
                relations[rid] = {"type": kind, "left": left, "right": right,
                    "state": state, "reason": reason, "support": support, "contradictions": contradictions,
                    "source_ids": sorted({subjects[target]["source_id"] for target in (left, right)}),
                    "evidence_ids": evidence, "authority": "NONE",
                    "prerequisites": {target: dependencies[target] for target in (left, right)}}
                edges.append(rid)
            plausible = [rid for rid in edges if relations[rid]["state"] != "REJECTED"]
            if len(plausible) > 1:
                for rid in plausible:
                    relations[rid].update(state="AMBIGUOUS", reason="MULTIPLE_PLAUSIBLE_TARGETS")
            # Include alternatives: checking only the chosen endpoints would
            # incorrectly preserve a link after another compatible scope arrives.
            candidate_hash = stable_hash({rid: relations[rid] for rid in edges})
            for rid in edges:
                relations[rid]["candidate_set_sha256"] = candidate_hash
    return dict(sorted(relations.items()))


def reduce_relations(graph: dict[str, Any]) -> dict[str, Any]:
    """Journal one deterministic refresh, replayable without model decisions."""
    from .case_graph import state_hash
    result = deepcopy(graph)
    result["relations"] = relation_view(graph)
    result["issues"] = {qid: issue for qid, issue in result["issues"].items()
                        if issue["kind"] != "RELATIONSHIP"}
    for rid, relation in result["relations"].items():
        result["issues"]["issue-" + stable_hash({"relation": rid})] = {
            "kind": "RELATIONSHIP", "origin": "ACTION", "source_id": None,
            "observation_ids": relation["evidence_ids"],
            "details": {"relation_id": rid, "reason": relation["reason"]},
            "state": "RESOLVED" if relation["state"] in {"CONFIRMED", "REJECTED"} else "OPEN",
            "materiality": "POTENTIALLY_MATERIAL"}
    if state_hash(result) == state_hash(graph):
        return result
    result["actions"].append({"type": "RELATION_REFRESH", "validator_version": VERSION,
        "pre_state_hash": state_hash(graph), "post_state_hash": state_hash(result)})
    return result


def commit_relations(graph: dict[str, Any], root: Path) -> dict[str, Any]:
    from .case_graph import commit_transition
    return commit_transition(graph, root, reduce_relations)
