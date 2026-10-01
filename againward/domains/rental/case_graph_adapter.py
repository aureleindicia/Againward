"""Verified V2 graph projection into the unchanged deterministic RentalCase.

Technical record IDs are derived from reviewed occurrences. Evidence references
continue to name their original sources; commercial claims add their own proof
references, never synthetic observations in the invoice.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from pathlib import Path
from typing import Any

from againward.documents.contracts import DocumentError
from againward.evidence.hashing import stable_hash

from .case_graph import graph_hash, replay_evidence
from .case_graph_claims import current_claims
from .case_graph_readiness import prerequisites
from .case_graph_relations import occurrence_values, relation_view
from .models import RentalCase, RateTerm, ActualCharge, RentalEvent


def _stop(code: str, target: str, field: str) -> None:
    raise DocumentError("EXTRACTION_INCOMPLETE", "V2 canonical projection requires current supported evidence",
        diagnostic={"stage": "CASE_READINESS", "validation_code": code,
                    "schema_path": f"$.occurrences.{target}.{field}"})


def load_graph_case(graph: dict[str, Any], root: Path) -> tuple[RentalCase, dict[str, Any]]:
    replay_evidence(graph, root)
    assessment = prerequisites(graph)
    if not assessment["prerequisites_satisfied"]:
        first = assessment["gaps"][0]
        _stop(first["kind"], first["target"], first.get("field") or "evidence")
    subjects = graph["occurrences"]
    values = {target: occurrence_values(graph, target) for target in subjects}
    relations = relation_view(graph)
    derivations: list[dict[str, Any]] = []

    def technical(prefix: str, target: str) -> str:
        identifier = prefix + "-" + target.removeprefix("occ-")
        derivations.append({"field": prefix, "value": identifier, "occurrence": target,
                            "origin": "DERIVED_STRUCTURE", "rule": "REVIEWED_OCCURRENCE_ID"})
        return identifier

    def refs(target: str, only: set[str] | None = None, *, commercial: bool = False) -> list[dict[str, Any]]:
        ids = {oid for field, group in subjects[target]["fields"].items() if only is None or field in only for oid in group}
        if commercial:
            for kind in ("CHARGE_MEANING", "GOVERNING_TERM"):
                ids.update(oid for claim in current_claims(graph, kind, target) for oid in claim["proposal"]["evidence_ids"])
        result = {}
        for oid in sorted(ids):
            row = graph["observations"][oid]
            ref = {"document_id": row["source_id"], "location": row["location"], "field": row["semantic_type"]}
            result[stable_hash(ref)] = ref
        return [result[key] for key in sorted(result)]

    def linked(target: str, kind: str) -> str:
        matches = {edge["right"] for edge in relations.values() if edge["left"] == target
                   and edge["type"] == kind and edge["state"] == "CONFIRMED"}
        if len(matches) != 1:
            _stop("UNIQUE_RELATION_REQUIRED", target, kind)
        return next(iter(matches))

    def meaning(target: str) -> str:
        decisions = {claim["proposal"]["value"] for claim in current_claims(graph, "CHARGE_MEANING", target)}
        if len(decisions) != 1:
            _stop("CHARGE_MEANING_REQUIRED", target, "charge_type")
        return next(iter(decisions))

    def optional(target: str, record_type, excluded: set[str]) -> dict[str, Any]:
        return {field.name: values[target][field.name] for field in fields(record_type)
                if field.name not in excluded and values[target].get(field.name) is not None}

    case: dict[str, Any] = {"schema_version": "againward-rental-case-v1", **{key: [] for key in (
        "documents", "parties", "items", "periods", "terms", "events", "actual_charges", "credits")}}
    # Readiness supplies the same reviewed metadata the adapter consumes.
    # No second source-wide lookup may restore rejected role/status evidence.
    case["documents"] = deepcopy(assessment["documents"])
    periods: dict[str, str] = {}
    parties: dict[str, dict[str, Any]] = {}
    for target, subject in sorted(subjects.items()):
        if subject["kind"] != "RENTAL_SCOPE":
            continue
        row = values[target]
        pid, item = technical("period", target), technical("item", target)
        periods[target] = pid
        for field, role in (("supplier_id", "RENTAL_VENDOR"), ("client_id", "CLIENT")):
            party = {"party_id": row[field], "role": role, "evidence_refs": refs(target, {field})}
            previous = parties.get(row[field])
            if previous and previous["role"] != role:
                _stop("PARTY_ROLE_CONFLICT", target, field)
            if previous:
                party["evidence_refs"] = sorted({stable_hash(ref): ref for ref in
                    [*previous["evidence_refs"], *party["evidence_refs"]]}.values(), key=stable_hash)
            parties[row[field]] = party
        case["items"].append({"item_id": item, "description": row["description"], "evidence_refs": refs(target),
            **{key: row[key] for key in ("asset_id", "serial_number", "supplier_item_id", "category") if row.get(key) is not None}})
        case["periods"].append({"period_id": pid, "item_id": item, "evidence_refs": refs(target),
            **{key: row[key] for key in ("agreement_id", "supplier_id", "client_id", "start", "end", "quantity")},
            **{key: row[key] for key in ("site_id", "cost_center_id") if row.get(key) is not None}})
    case["parties"] = [parties[key] for key in sorted(parties)]
    for target, subject in sorted(subjects.items()):
        if subject["kind"] != "RATE_TERM" and not (subject["kind"] == "RENTAL_SCOPE" and values[target].get("rate") is not None):
            continue
        scope = target if subject["kind"] == "RENTAL_SCOPE" else linked(target, "APPLIES_TO")
        charge_type = meaning(target)
        # This is an internal matching key, never a source-observed identifier.
        key = values[target].get("charge_key") or charge_type.lower()
        if values[target].get("charge_key") is None:
            derivations.append({"field": "charge_key", "value": key, "occurrence": target,
                "origin": "DERIVED_STRUCTURE", "rule": "REVIEWED_CHARGE_MEANING_KEY"})
        excluded = {"term_id", "period_id", "charge_key", "charge_type", "evidence_refs"}
        # Scope quantity counts rented items, not the independent denominator
        # of a per-lot rate. A separate RATE_TERM may carry its own quantity.
        if subject["kind"] == "RENTAL_SCOPE":
            excluded.add("quantity")
        case["terms"].append({**optional(target, RateTerm, excluded),
            "term_id": technical("term", target), "period_id": periods[scope], "charge_key": key,
            "charge_type": charge_type, "evidence_refs": refs(target, commercial=True)})
    charges = {}
    for target, subject in sorted(subjects.items()):
        row = values[target]
        if subject["kind"] == "INVOICE_LINE":
            pid, charge_type = periods[linked(target, "SAME_RENTAL")], meaning(target)
            keys = {term["charge_key"] for term in case["terms"] if term["period_id"] == pid
                    and term["charge_type"] == charge_type and term["currency"] == row["currency"]}
            if row.get("charge_key") is not None:
                keys &= {row["charge_key"]}
            if len(keys) != 1:
                _stop("UNIQUE_CHARGE_SCOPE_REQUIRED", target, "charge_key")
            line = row.get("invoice_line_id") or technical("line", target)
            charges[target] = str(row["invoice_id"]) + "/" + str(line)
            case["actual_charges"].append({**optional(target, ActualCharge, {"invoice_line_id", "period_id", "charge_key", "charge_type", "evidence_refs"}),
                "invoice_line_id": line, "period_id": pid, "charge_key": next(iter(keys)),
                "charge_type": charge_type, "evidence_refs": refs(target, commercial=True)})
        elif subject["kind"] == "EVENT":
            case["events"].append({**optional(target, RentalEvent, {"event_id", "period_id", "evidence_refs"}),
                "event_id": technical("event", target), "period_id": periods[linked(target, "BELONGS_TO")],
                "evidence_refs": refs(target)})
    for target, subject in sorted(subjects.items()):
        if subject["kind"] != "CREDIT":
            continue
        row = values[target]
        allocated = row["allocation_state"] in {"CONFIRMED_ALLOCATION", "PARTIALLY_ALLOCATED_CREDIT"}
        case["credits"].append({**{key: row[key] for key in ("credit_id", "net_amount", "currency", "status", "allocation_state")},
            **{key: row[key] for key in ("allocated_amount", "invoice_id") if row.get(key) is not None},
            "charge_id": charges[linked(target, "ALLOCATES_TO")] if allocated else None, "evidence_refs": refs(target)})
    try:
        canonical = RentalCase.from_dict(case)
    except (ValueError, TypeError) as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "V2 RentalCase validation failed",
            diagnostic={"stage": "CASE_READINESS", "validation_code": "CANONICAL_RECORD_INVALID",
                        "schema_path": "$.canonical_case"}) from exc
    lineage = {"schema_version": "againward-rental-graph-lineage-v2", "graph_sha256": graph_hash(graph),
        "canonical_case_sha256": stable_hash(canonical.to_dict()), "technical_derivations": derivations,
        "observations": graph["observations"], "occurrences": subjects, "relations": relations,
        "reviews": graph["reviews"], "frontier": assessment["frontier"]}
    return canonical, deepcopy(lineage)
