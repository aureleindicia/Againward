"""Deterministic investigation prerequisites before projection to RentalCase.

This is not financial arithmetic and a clear prerequisite list alone is not an
authorization to calculate. Projection must still validate the resulting case
and the existing pricing engine remains authoritative about supported rules.
"""
from __future__ import annotations

from typing import Any

from againward.evidence.hashing import stable_hash

from .case_graph_claims import current_claims
from .case_graph_frontier import materiality_frontier
from .case_graph_relations import occurrence_values, relation_view
from .case_graph_review import current_review

REQUIRED = {
    "INVOICE_LINE": ("invoice_id", "net_amount", "currency"),
    "RENTAL_SCOPE": ("agreement_id", "supplier_id", "client_id", "start", "end", "quantity", "description"),
    "RATE_TERM": ("currency", "billing_unit", "rate", "discount_fraction"),
    "EVENT": ("event_type", "date", "quantity", "verification"),
    "CREDIT": ("credit_id", "net_amount", "currency", "status"),
    "SUPPORTING_RECORD": (),
}
LINKS = {"INVOICE_LINE": "SAME_RENTAL", "RATE_TERM": "APPLIES_TO", "EVENT": "BELONGS_TO"}


def prerequisites(graph: dict[str, Any]) -> dict[str, Any]:
    """List exact local gaps; never fill absent commercial values with defaults."""
    frontier = materiality_frontier(graph)
    gaps = list(frontier["blockers"])
    relations = relation_view(graph)
    values = {oid: occurrence_values(graph, oid) for oid in graph["occurrences"]}
    documents: list[dict[str, Any]] = []

    def gap(target: str, code: str, field: str | None = None) -> None:
        gaps.append({"kind": code, "target": target, "field": field})

    def require(target: str, fields: tuple[str, ...]) -> None:
        for field in fields:
            if values[target].get(field) is None:
                gap(target, "FIELD_REQUIRED", field)

    def claim(target: str, kind: str, expected: str | None = None) -> None:
        decisions = {row["proposal"]["value"] for row in current_claims(graph, kind, target)}
        if len(decisions) != 1 or (expected is not None and decisions != {expected}):
            gap(target, "COMMERCIAL_REVIEW_REQUIRED", kind)

    used_sources = {subject["source_id"] for subject in graph["occurrences"].values()}
    for source in graph["batch"]["documents"]:
        sid = source["source_id"]
        if sid not in used_sources:
            continue
        metadata = {}
        for field in ("document_role", "document_status"):
            found = {row["value"] for oid, row in graph["observations"].items()
                     if row["source_id"] == sid and row["semantic_type"] == field
                     and frontier["observations"][oid] == "USED"}
            if len(found) != 1:
                gap(sid, "DOCUMENT_METADATA_REQUIRED", field)
            else:
                metadata[field] = next(iter(found))
        if len(metadata) == 2:
            documents.append({"document_id": sid, "path": source["blob_path"], "sha256": source["sha256"],
                "role": metadata["document_role"], "status": metadata["document_status"]})

    # Different technical containers cannot spend the same monetary evidence
    # twice. Local model labels and separate positive reviews do not cure this.
    monetary_owners: dict[tuple[str, str], list[str]] = {}
    for target, occurrence in graph["occurrences"].items():
        if occurrence["kind"] in {"INVOICE_LINE", "CREDIT"}:
            for oid in occurrence["fields"].get("net_amount", []):
                monetary_owners.setdefault((occurrence["kind"], oid), []).append(target)
    for (_, oid), owners in sorted(monetary_owners.items()):
        if len(owners) > 1:
            gap(oid, "MATERIAL_OBSERVATION_REUSED", "net_amount")

    for target, occurrence in sorted(graph["occurrences"].items()):
        kind = occurrence["kind"]
        if (current_review(graph, target) or {}).get("verdict") != "SUPPORTED":
            gap(target, "OCCURRENCE_REVIEW_REQUIRED")
        require(target, REQUIRED[kind])
        row = values[target]
        if kind == "SUPPORTING_RECORD" and any(row.get(field) is not None for field in (
                "net_amount", "rate", "unit_rate", "allocated_amount", "stop_event", "event_type")):
            # A supporting-container review does not establish that a monetary
            # or contractual observation can be excluded from the calculation.
            gap(target, "SUPPORTING_MATERIALITY_REVIEW_REQUIRED")
        if kind in LINKS:
            linked = [edge for edge in relations.values() if edge["left"] == target
                      and edge["type"] == LINKS[kind] and edge["state"] == "CONFIRMED"]
            if len(linked) != 1:
                gap(target, "UNIQUE_RELATION_REQUIRED", LINKS[kind])
        if kind == "INVOICE_LINE":
            claim(target, "CHARGE_MEANING")
            if (row.get("start") is None) != (row.get("end") is None):
                require(target, ("start", "end"))
        if kind == "RENTAL_SCOPE":
            if not any(row.get(field) is not None for field in ("asset_id", "serial_number", "supplier_item_id")):
                gap(target, "ITEM_IDENTITY_REQUIRED")
            external = [edge for edge in relations.values() if edge["right"] == target
                        and edge["type"] == "APPLIES_TO" and edge["state"] == "CONFIRMED"]
            if not external and row.get("rate") is None:
                gap(target, "APPLICABLE_TERM_REQUIRED")
        if kind == "RATE_TERM" or (kind == "RENTAL_SCOPE" and row.get("rate") is not None):
            require(target, REQUIRED["RATE_TERM"])
            claim(target, "CHARGE_MEANING")
            claim(target, "GOVERNING_TERM", "GOVERNING")
            if row.get("billing_unit") in {"DAY", "WEEK", "MONTH"}:
                require(target, ("weekends_billable", "minimum_days", "quantity_basis", "stop_event"))
            if row.get("billing_unit") in {"WEEK", "MONTH"}:
                require(target, ("partial_period_policy",))
            if row.get("billing_unit") == "PERCENT":
                require(target, ("percentage_of",))
        if kind == "CREDIT":
            # Identity confirmation does not by itself establish an allocation.
            require(target, ("allocation_state",))
            if row.get("allocation_state") in {"CONFIRMED_ALLOCATION", "PARTIALLY_ALLOCATED_CREDIT"}:
                linked = [edge for edge in relations.values() if edge["left"] == target
                          and edge["type"] == "ALLOCATES_TO" and edge["state"] == "CONFIRMED"]
                if len(linked) != 1:
                    gap(target, "UNIQUE_RELATION_REQUIRED", "ALLOCATES_TO")
                if row["allocation_state"] == "PARTIALLY_ALLOCATED_CREDIT":
                    require(target, ("allocated_amount",))
    if not any(row["kind"] == "INVOICE_LINE" for row in graph["occurrences"].values()):
        gap("case", "INVOICE_REQUIRED")
    if not any(row["kind"] == "RENTAL_SCOPE" for row in graph["occurrences"].values()):
        gap("case", "RENTAL_SCOPE_REQUIRED")
    return {"frontier": frontier, "documents": documents, "gaps": sorted(gaps, key=stable_hash),
            "prerequisites_satisfied": not gaps}


def evaluate_readiness(graph: dict[str, Any], root) -> dict[str, Any]:
    """Python-only authorization; replay precedes any supported status.

    Supported prerequisites authorize projection, whose canonical validation and
    the financial engine can still refuse unsupported calculation conventions.
    """
    from .case_graph import replay_evidence
    replay_evidence(graph, root)
    assessment = prerequisites(graph)
    return {**assessment, "status": "SUPPORTED_DETERMINISTIC" if assessment["prerequisites_satisfied"] else "UNRESOLVED"}
