"""Small evidence-referenced semantic deltas awaiting original-source review.

Claims are issues until reviewed. They never overwrite observations or copy a
commercial value into another source. Only their local dependencies can support
a decision; a model cannot provide a prerequisite hash or a HUMAN attestation.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from againward.documents.contracts import DocumentError, closed
from againward.evidence.hashing import stable_hash

from .case_graph_actions import _ids, observation_dependency
from .entity_contract import CHARGE_TYPES

VERSION = "rental-graph-claims-v2-reading-issues"
KEYS = {"kind", "target", "value", "evidence_ids", "reason"}
DISPOSITIONS = {"REJECTED_WITH_EVIDENCE", "IRRELEVANT", "DUPLICATE"}
READING_ISSUES = {"READING_REJECTION", "READING_LIMITATION", "EMPTY_READING"}


def _shape(proposal: dict[str, Any]) -> None:
    closed(proposal, KEYS)
    if (not isinstance(proposal["kind"], str)
            or proposal["kind"] not in {"CHARGE_MEANING", "GOVERNING_TERM", "OBSERVATION_DISPOSITION", "READING_ISSUE_RESOLUTION"}
            or not isinstance(proposal["target"], str) or not 1 <= len(proposal["target"]) <= 160
            or not isinstance(proposal["value"], str)
            or not isinstance(proposal["reason"], str) or not 1 <= len(proposal["reason"]) <= 2000):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Bounded semantic claim required")
    allowed = (CHARGE_TYPES if proposal["kind"] == "CHARGE_MEANING" else
               {"GOVERNING", "NOT_GOVERNING"} if proposal["kind"] == "GOVERNING_TERM" else
               {"RECOVERED", "NO_MATERIAL_EFFECT"} if proposal["kind"] == "READING_ISSUE_RESOLUTION" else DISPOSITIONS)
    if proposal["value"] not in allowed:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown semantic decision")
    _ids(proposal["evidence_ids"])


def claim_context(graph: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    """Current local dependencies, including alternative relationship targets."""
    from .case_graph_review import current_review, review_request
    from .case_graph_relations import relation_view
    target = proposal["target"]
    ids = proposal["evidence_ids"]
    dependencies: dict[str, Any] = {"observations": {oid: observation_dependency(graph["observations"][oid])
                    for oid in ids if oid in graph["observations"]}, "subjects": {}, "relations": {}}
    if proposal["kind"] == "READING_ISSUE_RESOLUTION":
        issue = graph["issues"].get(target)
        dependencies["issue"] = {key: value for key, value in (issue or {}).items() if key != "state"}
        source = issue.get("source_id") if issue else None
        # Later evidence in this source can overturn an old irrelevance or
        # recovery judgment. Unrelated sources do not invalidate it.
        dependencies["source_observations"] = {oid: observation_dependency(row)
            for oid, row in graph["observations"].items() if row["source_id"] == source}
        subjects = {oid for oid, occurrence in graph["occurrences"].items()
                    if set(ids) & {i for group in occurrence["fields"].values() for i in group}}
    elif proposal["kind"] == "OBSERVATION_DISPOSITION":
        if target in graph["observations"]:
            dependencies["observations"][target] = observation_dependency(graph["observations"][target])
        subjects = {oid for oid, occurrence in graph["occurrences"].items()
                    if target in {i for values in occurrence["fields"].values() for i in values}}
    else:
        subjects = {target} if target in graph["occurrences"] else set()
        # Only identity-confirmed relationships can expand semantic evidence.
        for rid, relation in relation_view(graph).items():
            if target in {relation["left"], relation["right"]}:
                dependencies["relations"][rid] = relation
                if relation["state"] == "CONFIRMED":
                    subjects.update((relation["left"], relation["right"]))
    for oid in sorted(subjects):
        dependencies["subjects"][oid] = {"request": review_request(graph, oid)["request_sha256"],
                                          "review": current_review(graph, oid)}
    return dependencies


def bind_claim(graph: dict[str, Any], proposal: dict[str, Any]) -> dict[str, Any]:
    _shape(proposal)
    body = {**deepcopy(proposal), "evidence_ids": sorted(proposal["evidence_ids"])}
    return {**body, "prerequisites": claim_context(graph, body)}


def validate_claim(graph: dict[str, Any], proposal: dict[str, Any]) -> None:
    """Eligibility to ask a reviewer, never automatic semantic approval."""
    _shape(proposal)
    ids = set(proposal["evidence_ids"])
    if not ids <= graph["observations"].keys():
        raise DocumentError("SOURCE_LOCATION_INVALID", "Claim cites unknown observations")
    target = proposal["target"]
    context = claim_context(graph, proposal)
    if proposal["kind"] == "READING_ISSUE_RESOLUTION":
        issue = graph["issues"].get(target)
        if not issue or issue["kind"] not in READING_ISSUES or not issue.get("source_id"):
            raise DocumentError("ENTITY_AMBIGUOUS", "Known source-local reading issue required")
        if any(graph["observations"][oid]["source_id"] != issue["source_id"] for oid in ids):
            raise DocumentError("SOURCE_LOCATION_INVALID", "Reading issue cannot borrow foreign evidence")
        if proposal["value"] == "RECOVERED":
            reviewed = {oid for subject, dependency in context["subjects"].items()
                if dependency["review"] and dependency["review"]["verdict"] == "SUPPORTED"
                for group in graph["occurrences"][subject]["fields"].values() for oid in group}
            if not ids <= reviewed:
                raise DocumentError("REVIEW_STALE", "Recovered observations require current review")
        return
    if proposal["kind"] == "OBSERVATION_DISPOSITION":
        row = graph["observations"].get(target)
        if row is None or target not in ids:
            raise DocumentError("SOURCE_LOCATION_INVALID", "Disposition must inspect its original observation")
        if any(graph["observations"][oid]["source_id"] != row["source_id"] for oid in ids):
            raise DocumentError("SOURCE_LOCATION_INVALID", "Local rejection cannot borrow foreign evidence")
        if proposal["value"] == "DUPLICATE":
            equivalents = {oid for oid in ids - {target} if all(graph["observations"][oid][key] == row[key]
                           for key in ("source_id", "semantic_type", "value_type", "value"))}
            shared = any(dependency["review"] and dependency["review"]["verdict"] == "SUPPORTED"
                and equivalents & {oid for values in graph["occurrences"][subject]["fields"].values() for oid in values}
                for subject, dependency in context["subjects"].items())
            if not shared:
                raise DocumentError("ENTITY_AMBIGUOUS", "Duplicate needs equivalent evidence in the same reviewed occurrence")
        return
    occurrence = graph["occurrences"].get(target)
    if occurrence is None:
        raise DocumentError("ENTITY_AMBIGUOUS", "Claim target occurrence absent")
    own_review = context["subjects"][target]["review"]
    if not own_review or own_review["verdict"] != "SUPPORTED":
        raise DocumentError("REVIEW_STALE", "Commercial claim requires a currently reviewed subject")
    eligible = {oid for subject, dependency in context["subjects"].items()
                if dependency["review"] and dependency["review"]["verdict"] == "SUPPORTED"
                for values in graph["occurrences"][subject]["fields"].values() for oid in values}
    if not ids <= eligible:
        raise DocumentError("SOURCE_LOCATION_INVALID", "Claim evidence is not local or on a confirmed reviewed relation")
    if proposal["kind"] == "CHARGE_MEANING":
        if occurrence["kind"] not in {"INVOICE_LINE", "RENTAL_SCOPE", "RATE_TERM"}:
            raise DocumentError("ENTITY_AMBIGUOUS", "Charge meaning requires a charge-bearing occurrence")
    elif occurrence["kind"] not in {"RENTAL_SCOPE", "RATE_TERM"}:
        raise DocumentError("ENTITY_AMBIGUOUS", "Rate authority requires a term occurrence")
    elif proposal["value"] == "GOVERNING":
        # A structural role or a relation alone is never acceptance evidence.
        if not any(graph["observations"][oid]["semantic_type"] == "document_status"
                   and graph["observations"][oid]["value"] == "ACCEPTED" for oid in ids):
            raise DocumentError("EXTRACTION_INCOMPLETE", "Explicit reviewed acceptance evidence required")


def reduce_claim(graph: dict[str, Any], action: dict[str, Any], *, validator_version: str = VERSION) -> dict[str, Any]:
    from .case_graph import state_hash
    closed(action, KEYS | {"prerequisites"})
    if validator_version not in {VERSION, "rental-graph-claims-v1"} or (
            validator_version == "rental-graph-claims-v1" and action["kind"] == "READING_ISSUE_RESOLUTION"):
        raise DocumentError("SOURCE_CHANGED", "Unknown or incompatible claim validator version")
    proposal = {key: action[key] for key in KEYS}
    _shape(proposal)
    action_id = "claim-action-" + stable_hash(action)
    if any(event.get("action_id") == action_id for event in graph["actions"]):
        return deepcopy(graph)
    result = deepcopy(graph)
    code = None
    try:
        if claim_context(graph, proposal) != action["prerequisites"]:
            raise DocumentError("REVIEW_STALE", "Claim prerequisites changed")
        validate_claim(graph, proposal)
        claim_id = "claim-" + stable_hash(proposal)
        result["issues"][claim_id] = {"kind": "SEMANTIC_CLAIM", "origin": "ACTION",
            "source_id": None, "observation_ids": proposal["evidence_ids"],
            "details": {"proposal": deepcopy(proposal)}, "state": "OPEN", "materiality": "POTENTIALLY_MATERIAL"}
    except DocumentError as exc:
        result = deepcopy(graph)
        code = exc.code
    result["actions"].append({"type": "CLAIM_PROPOSAL", "action_id": action_id, "action": deepcopy(action),
        "validator_version": validator_version, "pre_state_hash": state_hash(graph), "post_state_hash": state_hash(result),
        "result": "REJECTED" if code else "ACCEPTED_PROPOSAL", "rejection_code": code})
    return result


def current_claims(graph: dict[str, Any], kind: str, target: str) -> list[dict[str, Any]]:
    """Do not trust persisted RESOLVED/disposition flags after dependencies change."""
    from .case_graph_review import current_review
    result = []
    for claim_id, issue in graph["issues"].items():
        if issue["kind"] != "SEMANTIC_CLAIM":
            continue
        proposal = issue["details"]["proposal"]
        if proposal["kind"] == kind and proposal["target"] == target:
            review = current_review(graph, claim_id)
            if review and review["verdict"] == "SUPPORTED":
                result.append({"claim_id": claim_id, "proposal": deepcopy(proposal), "review": review})
    return sorted(result, key=lambda row: row["claim_id"])


def observation_disposition(graph: dict[str, Any], target: str) -> str:
    """Effective frontier state, including incompatible current review decisions."""
    from .case_graph_review import current_review
    decisions = {row["proposal"]["value"] for row in current_claims(graph, "OBSERVATION_DISPOSITION", target)}
    used = any((current_review(graph, oid) or {}).get("verdict") == "SUPPORTED"
        for oid, subject in graph["occurrences"].items()
        if target in {i for ids in subject["fields"].values() for i in ids})
    if len(decisions) > 1 or (used and decisions & {"REJECTED_WITH_EVIDENCE", "IRRELEVANT"}):
        return "UNRESOLVED"
    if decisions:
        return next(iter(decisions))
    return "USED" if used else "UNRESOLVED"


def commit_claim(graph: dict[str, Any], action: dict[str, Any], root: Path) -> dict[str, Any]:
    from .case_graph import commit_transition
    return commit_transition(graph, root, lambda current: reduce_claim(current, action))
