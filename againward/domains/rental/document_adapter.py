"""Reviewed documentary facts -> Rental v1, with explicit foreign-key evidence.

The adapter deliberately stops before financial calculation if a material entity
is unassigned. It cannot discard a credit/return to make a case easier to price.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from againward.documents.contracts import DocumentError, SourceBatch, closed
from againward.documents.extraction import promote_facts, replay_extraction
from againward.documents.resolution import (
    Entity, MatchPolicy, RelationshipState, entities_from_facts, resolve_entities,
    review_relationships,
)
from againward.evidence.hashing import stable_hash
from .models import DOCUMENT_ROLES, RentalCase

DOCUMENT_CASE_SCHEMA = "againward-rental-document-case-v1"
RENTAL_MATCH = MatchPolicy(
    "SAME_RENTAL",
    (("INVOICE_LINE", "RENTAL_SCOPE"), ("RETURN", "RENTAL_SCOPE")),
    blocking_keys=("agreement_id", "asset_id", "serial_number"),
    anchor_keys=(("agreement_id", "asset_id"), ("agreement_id", "serial_number")),
    contradiction_keys=("supplier_id", "agreement_id", "asset_id", "serial_number"),
    required_scope_keys=("supplier_id",),
    exclusive_left_kinds=("INVOICE_LINE", "RETURN"),
    prefix_blocking_keys=("agreement_id",),
)
CREDIT_MATCH = MatchPolicy(
    "CREDIT_FOR", (("CREDIT", "INVOICE_LINE"),),
    blocking_keys=("invoice_id", "invoice_line_id"),
    anchor_keys=(("invoice_id", "invoice_line_id"),),
    contradiction_keys=("supplier_id", "invoice_id", "invoice_line_id", "currency"),
    required_scope_keys=("supplier_id",),
    exclusive_left_kinds=("CREDIT",),
)


def _refs(entity: Entity, fields: set[str] | None = None) -> list[dict[str, Any]]:
    refs = []
    for fact in entity.facts:
        c = fact.candidate
        if fields is None or c.semantic_type in fields:
            span = f"/chars:{c.source_span[0]}:{c.source_span[1]}" if c.source_span else "/visual"
            ref = {"document_id": c.source_id, "location": c.location + span, "field": c.semantic_type}
            if ref not in refs:
                refs.append(ref)
    return refs


def _required(entity: Entity, keys: tuple[str, ...]) -> dict[str, Any]:
    values = entity.values
    if any(values.get(k) is None for k in keys):
        raise DocumentError("EXTRACTION_INCOMPLETE",
                            entity.entity_id + " missing " + ",".join(k for k in keys if values.get(k) is None))
    return {key: values[key] for key in keys}


def _optional(entity: Entity, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: entity.values[key] for key in keys if key in entity.values}


def load_document_case(payload: Any, root: Path) -> tuple[RentalCase, dict[str, Any]]:
    p = closed(payload, {"schema_version", "batch", "extractions", "fact_review",
                         "rental_relationship_review", "credit_relationship_review"})
    if p["schema_version"] != DOCUMENT_CASE_SCHEMA:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown Rental document package")
    batch = SourceBatch.from_dict(p["batch"])
    if not isinstance(p["extractions"], list):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Validated extractions required")
    extractions = tuple(replay_extraction(e, batch, root) for e in p["extractions"])
    if (len(extractions) != len(batch.documents)
            or {e.source_id for e in extractions} != {d.source_id for d in batch.documents}):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Every source requires one explicit extraction/classification")
    facts = promote_facts(extractions, p["fact_review"], batch, root)
    if any(e.limitations for e in extractions):
        raise DocumentError("EXTRACTION_INCOMPLETE",
                            "Unextracted/missing components must be resolved before financial preparation")
    entities = entities_from_facts(facts)
    if any(e.kind not in {"RENTAL_SCOPE", "INVOICE_LINE", "RETURN", "CREDIT", "IRRELEVANT"} for e in entities):
        raise DocumentError("EXTRACTION_INCOMPLETE", "Unsupported material entity kind")
    by_source: dict[str, list[Entity]] = {}
    for e in entities:
        by_source.setdefault(e.source_id, []).append(e)
    documents = []
    for source in batch.documents:
        source_entities = by_source.get(source.source_id, [])
        roles = {e.values.get("document_role") for e in source_entities}
        statuses = {e.values.get("document_status") for e in source_entities}
        if len(roles) != 1 or not roles <= DOCUMENT_ROLES or len(statuses) != 1:
            raise DocumentError("EXTRACTION_INCOMPLETE", "Reviewed source role/status required without conflict")
        role, status = next(iter(roles)), next(iter(statuses))
        if role in {"IRRELEVANT", "UNKNOWN"} and any(e.kind != "IRRELEVANT" for e in source_entities):
            raise DocumentError("UNSUPPORTED_PROMOTION", "Unclassified source cannot support financial facts")
        documents.append({"document_id": source.source_id, "path": source.blob_path, "sha256": source.sha256,
                          "role": role, "status": status})
    resolution = resolve_entities(entities, RENTAL_MATCH)
    if p["rental_relationship_review"] is not None:
        resolution = review_relationships(resolution, p["rental_relationship_review"])
    credit_resolution = resolve_entities(entities, CREDIT_MATCH)
    if p["credit_relationship_review"] is not None:
        credit_resolution = review_relationships(credit_resolution, p["credit_relationship_review"])
    links = {r.left: r.right for r in resolution.relationships if r.state == RelationshipState.CONFIRMED}
    credit_links = {r.left: r.right for r in credit_resolution.relationships if r.state == RelationshipState.CONFIRMED}
    material = [e for e in entities if e.kind in {"INVOICE_LINE", "RETURN"} and e.entity_id not in links]
    material += [e for e in entities if e.kind == "CREDIT" and e.entity_id not in credit_links]
    if material:
        raise DocumentError("ENTITY_AMBIGUOUS", "Unassigned material occurrences: " + ",".join(e.entity_id for e in material))
    case: dict[str, Any] = {"schema_version": "againward-rental-case-v1", "documents": documents,
                            "parties": [], "items": [], "periods": [], "terms": [],
                            "events": [], "actual_charges": [], "credits": []}
    parties: dict[str, dict[str, Any]] = {}
    period_ids = {}
    for e in entities:
        if e.kind != "RENTAL_SCOPE":
            continue
        values = _required(e, ("agreement_id", "supplier_id", "client_id", "start", "end", "quantity", "description"))
        pid = "period-" + e.entity_id.removeprefix("entity-")
        iid = "item-" + e.entity_id.removeprefix("entity-")
        period_ids[e.entity_id] = pid
        for field, role in (("supplier_id", "RENTAL_VENDOR"), ("client_id", "CLIENT")):
            party = {"party_id": values[field], "role": role, "evidence_refs": _refs(e, {field})}
            previous = parties.get(values[field])
            if previous and previous["role"] != role:
                raise DocumentError("ENTITY_AMBIGUOUS", "Supplier/client identifiers conflict")
            if previous:
                previous["evidence_refs"].extend(ref for ref in party["evidence_refs"] if ref not in previous["evidence_refs"])
            else:
                parties[values[field]] = party
        case["items"].append({"item_id": iid, "description": values.pop("description"), "evidence_refs": _refs(e),
                              **_optional(e, ("asset_id", "serial_number", "category"))})
        case["periods"].append({"period_id": pid, "item_id": iid, **values, "evidence_refs": _refs(e),
                                **_optional(e, ("site_id", "cost_center_id"))})
        if any(key in e.values for key in ("rate", "billing_unit", "charge_key", "charge_type")):
            term = _required(e, ("charge_key", "charge_type", "currency"))
            term.update(_optional(e, ("rate", "billing_unit", "weekends_billable", "minimum_days",
                                     "partial_period_policy", "stop_event", "stop_day_billable", "discount_fraction")))
            case["terms"].append({"term_id": "term-" + e.entity_id.removeprefix("entity-"),
                                  "period_id": pid, **term, "evidence_refs": _refs(e)})
    case["parties"] = sorted(parties.values(), key=lambda party: party["party_id"])
    charges = {}
    for e in entities:
        if e.kind == "INVOICE_LINE":
            charge = _required(e, ("invoice_id", "invoice_line_id", "charge_key", "charge_type", "currency", "net_amount"))
            charge.update(_optional(e, ("start", "end", "quantity", "unit_rate", "billed_units")))
            case["actual_charges"].append({**charge, "period_id": period_ids[links[e.entity_id]], "evidence_refs": _refs(e)})
            charges[e.entity_id] = str(charge["invoice_id"]) + "/" + str(charge["invoice_line_id"])
        elif e.kind == "RETURN":
            event = _required(e, ("event_type", "date", "quantity", "verification"))
            case["events"].append({"event_id": "event-" + e.entity_id.removeprefix("entity-"),
                                  "period_id": period_ids[links[e.entity_id]], **event, "evidence_refs": _refs(e)})
    for e in entities:
        if e.kind == "CREDIT":
            credit = _required(e, ("credit_id", "currency", "net_amount", "status"))
            case["credits"].append({**credit, "charge_id": charges[credit_links[e.entity_id]], "evidence_refs": _refs(e)})
    canonical = RentalCase.from_dict(case)
    lineage = {"schema_version": "againward-rental-document-lineage-v1", "batch_id": batch.batch_id,
               "canonical_case_sha256": stable_hash(canonical.to_dict()),
               "facts": [f.to_dict() for f in facts], "entities": [asdict(e) for e in entities],
               "rental_resolution": resolution.to_dict(), "credit_resolution": credit_resolution.to_dict(),
               "limitations": sorted({limit for extraction in extractions for limit in extraction.limitations}),
               "queryable_source_units": "Native location and character span retained in every evidence reference",
               "human_delivery_approval": False}
    # Normalize tuples exactly as on disk so fresh replay and stored lineage agree.
    import json
    return canonical, json.loads(json.dumps(lineage))
