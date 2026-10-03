"""Small event-sourced Billing state. Python reducers alone own durable changes."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

from againward.core.artifact_store import assert_artifacts_consistent, read_json, transaction, write_json
from againward.documents.contracts import SourceBatch
from againward.documents.sources import assert_document_action
from againward.evidence.hashing import stable_hash

from .protocol import BillingFailure, validate_action
from .reader import reading_summary, replay_reading

VERSION = "energy-billing-state-v1"
REQUIRED = {
    "INVOICE": ("invoice_id", "supplier_id", "pdl", "currency", "period_start", "period_end",
                "quantity", "quantity_unit", "billed_amount"),
    "TARIFF": ("contract_id", "supplier_id", "pdl", "currency", "effective_start", "effective_end",
               "tariff_price", "price_unit", "rounding_rule", "tariff_type"),
}


def empty_state(batch: SourceBatch) -> dict[str, Any]:
    return {"schema_version": VERSION, "batch": batch.to_dict(), "readings": {}, "observations": {},
            "quarantine": {}, "occurrences": {}, "relations": {}, "reviews": {}}


def fields(state: dict[str, Any], ids: list[str]) -> dict[str, str]:
    collected: dict[str, set[str]] = {}
    for eid in ids:
        atom = state["observations"].get(eid)
        if atom is None:
            raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", expected="known evidence ID", actual=eid)
        if atom["field"] != "note":
            collected.setdefault(atom["field"], set()).add(atom["value"])
    conflicts = sorted(key for key, values in collected.items() if len(values) > 1)
    if conflicts:
        raise BillingFailure("OCCURRENCE_AMBIGUOUS", stage="ACTION", expected="one evidenced value per field",
                             conflicting_fields=conflicts)
    return {key: next(iter(values)) for key, values in collected.items()}


def declare(state: dict[str, Any], kind: str, ids: list[str]) -> str:
    from .disposition import excluded_ids

    excluded = excluded_ids(state)
    if set(ids) & excluded:
        raise BillingFailure('BUSINESS_AMBIGUITY', stage='ACTION', expected='current non-discarded occurrence evidence')
    sources = {state["observations"][eid]["source_id"] for eid in ids}
    if len(sources) != 1:
        raise BillingFailure("OCCURRENCE_AMBIGUOUS", stage="ACTION", expected="one original document per occurrence")
    value = fields(state, ids)
    missing = sorted(set(REQUIRED[kind]) - set(value))
    if missing:
        raise BillingFailure("MATERIAL_EVIDENCE_MISSING", stage="ACTION", expected="required occurrence fields", missing=missing)
    source = next(iter(sources))
    # Every observation of those same scalar fields in this source participates
    # in conflict detection. Selecting convenient evidence cannot hide two PDLs.
    all_ids = [eid for eid, row in state["observations"].items()
               if row["source_id"] == source and row["field"] in REQUIRED[kind] and eid not in excluded]
    fields(state, all_ids)
    identity = {key: value[key] for key in REQUIRED[kind]}
    oid = "eb-o-" + stable_hash({"kind": kind, "source_id": source, "identity": identity})
    old = state["occurrences"].get(oid, {})
    state["occurrences"][oid] = {"kind": kind, "source_id": source,
                               "evidence_ids": sorted(set(ids) | (set(old.get("evidence_ids", [])) - excluded))}
    return oid


def reduce_event(state: dict[str, Any], event: dict[str, Any], root: Path) -> dict[str, Any]:
    if not isinstance(event, dict) or not isinstance(event.get("type"), str):
        raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="typed event object")
    result = deepcopy(state)
    if event["type"] == "READ":
        if set(event) != {"type", "receipt_sha256"}:
            raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="closed read event")
        digest = event["receipt_sha256"]
        reading = replay_reading(SourceBatch.from_dict(state["batch"]), root, digest, verify_current=False)
        summary = reading_summary(reading)
        result["readings"][digest] = summary
        result["observations"].update(summary["observations"])
        for row in summary["quarantine"]:
            result["quarantine"][row["root_issue_id"]] = row
    elif event["type"] == "ACTION":
        if set(event) != {"type", "response", "focus"}:
            raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="closed action event")
        response = event["response"]
        validate_action(response, issue_id=event["focus"])
        action = response["action"]
        kind = action["type"]
        if "evidence_ids" in action and any(eid not in result["observations"] for eid in action["evidence_ids"]):
            raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", expected="known evidence IDs")
        if kind in {"DECLARE_INVOICE", "DECLARE_TARIFF"}:
            declare(result, kind.removeprefix("DECLARE_"), action["evidence_ids"])
        elif kind == "LINK_TARIFF":
            left, right = action["invoice_id"], action["tariff_id"]
            if (result["occurrences"].get(left, {}).get("kind") != "INVOICE"
                    or result["occurrences"].get(right, {}).get("kind") != "TARIFF"):
                raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", expected="invoice and tariff targets")
            required = set(result["occurrences"][left]["evidence_ids"] + result["occurrences"][right]["evidence_ids"])
            if not set(action["evidence_ids"]) <= required:
                raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", expected="evidence from linked subjects")
            rid = "eb-r-" + stable_hash({"invoice": left, "tariff": right})
            result["relations"][rid] = {"kind": "GOVERNS", "invoice_id": left, "tariff_id": right,
                                       "evidence_ids": sorted(action["evidence_ids"])}
        else:
            # Inspection/review/readiness/unresolved intents are handled by the
            # bounded runtime. They cannot enact approval or financial state.
            raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", expected="durable reducer action")
    elif event["type"] == "REVIEW":
        if set(event) != {"type", "receipt_sha256"}:
            raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="closed review event")
        from .review import reduce_review
        return reduce_review(result, event["receipt_sha256"], root)
    elif event['type'] == 'DISPOSITION':
        if set(event) != {'type', 'receipt_sha256'}:
            raise BillingFailure('STATE_REPLAY_INVALID', stage='REPLAY', expected='closed disposition event')
        from .disposition import reduce_disposition
        return reduce_disposition(result, event['receipt_sha256'], root)
    else:
        raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="known event type")
    return result


def load_state(root: Path) -> dict[str, Any]:
    assert_artifacts_consistent(root)
    payload = read_json(root / "energy_billing" / "state.json")
    if set(payload) != {"schema_version", "batch", "events", "state_sha256"} or payload["schema_version"] != VERSION:
        raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="closed state journal")
    state = empty_state(SourceBatch.from_dict(payload["batch"]))
    for event in payload["events"]:
        state = reduce_event(state, event, root)
    if stable_hash(state) != payload["state_sha256"]:
        raise BillingFailure("STATE_REPLAY_INVALID", stage="REPLAY", expected="replayed state hash")
    return state


def initialize(batch: SourceBatch, root: Path) -> dict[str, Any]:
    assert_document_action(root, mutation=True)
    with transaction(root):
        path = root / "energy_billing" / "state.json"
        if path.exists():
            state = load_state(root)
            if state["batch"] != batch.to_dict():
                raise BillingFailure("STATE_REPLAY_INVALID", stage="INITIALIZE", expected="existing immutable batch")
            return state
        state = empty_state(batch)
        write_json(path, {"schema_version": VERSION, "batch": batch.to_dict(), "events": [],
                          "state_sha256": stable_hash(state)})
        return state


def commit_event(state: dict[str, Any], event: dict[str, Any], root: Path) -> dict[str, Any]:
    assert_document_action(root, mutation=True)
    with transaction(root):
        current = load_state(root)
        if stable_hash(current) != stable_hash(state):
            raise BillingFailure("STATE_CHANGED", stage="COMMIT", expected="current Python state")
        result = reduce_event(current, event, root)
        if result == current:
            return current
        payload = read_json(root / "energy_billing" / "state.json")
        write_json(root / "energy_billing" / "state.json", {**payload, "events": [*payload["events"], event],
                                                              "state_sha256": stable_hash(result)})
        return result
