"""Issue-local views and semantic progress, independent of receipt churn."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from againward.evidence.hashing import stable_hash
from .case_graph_actions import observation_dependency
from .case_graph_claims import observation_disposition
from .case_graph_readiness import prerequisites
from .case_graph_relations import relation_view
from .case_graph_review import current_review


def open_issues(graph: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Include deterministic prerequisite gaps as runtime issues, never approvals."""
    return {"gap-" + stable_hash(gap): deepcopy(gap) for gap in prerequisites(graph)["gaps"]}


def local_context(graph: dict[str, Any], issue_id: str | None,
                  feedback: dict[str, Any] | None) -> dict[str, Any]:
    issues = open_issues(graph)
    gap = issues.get(issue_id, {}) if issue_id is not None else {}
    target = gap.get("target")
    issue = graph["issues"].get(target, {})
    ids = set(issue.get("observation_ids", []))
    if target in graph["observations"]:
        ids.add(target)
    subjects: set[str] = {target} if isinstance(target, str) and target in graph["occurrences"] else set()
    proposal = issue.get("details", {}).get("proposal", {})
    if proposal.get("target") in graph["occurrences"]:
        subjects.add(proposal["target"])
    if issue.get("details", {}).get("target") in graph["occurrences"]:
        subjects.add(issue["details"]["target"])
    edges = relation_view(graph)
    relation = edges.get(issue.get("details", {}).get("relation_id"))
    if relation:
        subjects.update((relation["left"], relation["right"]))
    for oid, subject in graph["occurrences"].items():
        if ids & {i for group in subject["fields"].values() for i in group}:
            subjects.add(oid)
    relevant_edges = {rid: edge for rid, edge in edges.items()
                      if subjects & {edge["left"], edge["right"]}}
    for edge in relevant_edges.values():
        subjects.update((edge["left"], edge["right"]))
    for oid in subjects:
        ids.update(i for group in graph["occurrences"][oid]["fields"].values() for i in group)
    sources = {graph["observations"][oid]["source_id"] for oid in ids}
    sources.update(graph["occurrences"][oid]["source_id"] for oid in subjects)
    if gap.get("source_id"):
        sources.add(gap["source_id"])
    if target in {doc["source_id"] for doc in graph["batch"]["documents"]}:
        sources.add(target)
    # Nearby unassigned atoms help grouping/repair without importing another dossier.
    locations = {(graph["observations"][oid]["source_id"], graph["observations"][oid]["location"]) for oid in ids}
    ids.update(oid for oid, row in graph["observations"].items()
               if (row["source_id"], row["location"]) in locations)
    if not subjects or gap.get("kind") in {"FIELD_REQUIRED", "DOCUMENT_METADATA_REQUIRED"}:
        ids.update(oid for oid, row in graph["observations"].items() if row["source_id"] in sources)
    selected = sorted(ids)[:128]
    claims = {iid: {"proposal": deepcopy(row["details"]["proposal"]), "review": current_review(graph, iid)}
              for iid, row in graph["issues"].items() if row["kind"] == "SEMANTIC_CLAIM"
              and row["details"]["proposal"]["target"] in subjects | ids | {target}}
    return {"claims": claims, "issue_id": issue_id, "issue": deepcopy(gap), "stored_issue": deepcopy(issue),
        "open_issues": [{"issue_id": iid, **row} for iid, row in sorted(issues.items())[:128]],
        "open_issue_count": len(issues),
        "observations": {oid: deepcopy(graph["observations"][oid]) for oid in selected},
        "omitted_observation_ids": sorted(ids - set(selected)),
        "occurrences": {oid: deepcopy(graph["occurrences"][oid]) for oid in sorted(subjects)},
        "reviews": {oid: current_review(graph, oid) for oid in sorted(subjects)},
        "relations": deepcopy(relevant_edges),
        "sources": [deepcopy(doc) for doc in graph["batch"]["documents"] if doc["source_id"] in sources],
        "feedback": deepcopy(feedback)}


def progress_view(graph: dict[str, Any]) -> dict[str, Any]:
    """Equivalent reads/reviews/rejection logs cannot manufacture progress."""
    def claim_key(target: str) -> str:
        issue = graph["issues"].get(target, {})
        if issue.get("kind") == "SEMANTIC_CLAIM":
            proposal = issue["details"]["proposal"]
            return stable_hash({key: value for key, value in proposal.items() if key != "reason"})
        return target

    evidence = {observation_dependency(row) for row in graph["observations"].values()}
    supported = set()
    subjects = {}
    for target in [*graph["occurrences"], *(iid for iid, row in graph["issues"].items() if row["kind"] == "SEMANTIC_CLAIM")]:
        review = current_review(graph, target)
        verdict = review["verdict"] if review else None
        subjects[claim_key(target)] = verdict
        if verdict == "SUPPORTED":
            supported.add(claim_key(target))
    gaps = {stable_hash({**gap, "target": claim_key(gap["target"])}) for gap in prerequisites(graph)["gaps"]}
    semantic = {"evidence": sorted(evidence), "reviews": subjects, "gaps": sorted(gaps),
        "occurrences": {oid: {key: row[key] for key in ("kind", "source_id", "anchor_ids", "fields")}
                        for oid, row in graph["occurrences"].items()},
        "dispositions": {oid: observation_disposition(graph, oid) for oid in graph["observations"]}}
    return {"fingerprint": stable_hash(semantic), "evidence": evidence, "supported": supported, "gaps": gaps}
