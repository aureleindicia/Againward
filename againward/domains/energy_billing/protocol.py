"""Closed native model contracts shared by prompts, CLI and Python validators.

This module grants no authority and mutates no domain state. Individual reader
rows are validated separately so one malformed atom cannot erase its siblings.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

VERSION = "energy-billing-model-v1"
MAX_BYTES = 64_000


class BillingFailure(ValueError):
    def __init__(self, code: str, *, stage: str, path: str = "$", expected: str = "",
                 actual: Any = None, **metadata: Any):
        self.code = code
        self.diagnostic = {"code": code, "stage": stage, "component": "energy_billing",
                           "schema_version": VERSION, "path": path, "expected": expected,
                           "actual_type": type(actual).__name__, "state_mutated": False, **metadata}
        super().__init__(f"{code}: {stage} {path} ({expected})")


def obj(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "properties": properties, "required": list(properties)}


def enum(*values: str) -> dict[str, Any]:
    return {"type": "string", "enum": list(values)}


REFERENCE = {"type": "string", "minLength": 1, "maxLength": 160}
REASON = {"type": "string", "minLength": 1, "maxLength": 1200}
# CLI's strict schema subset rejects uniqueItems. Distinct evidence IDs are an
# explicit additional Python reference constraint, also stated in model prompts.
IDS = {"type": "array", "minItems": 1, "maxItems": 32, "items": REFERENCE}
FIELDS = (
    "invoice_id", "supplier_id", "pdl", "currency", "period_start", "period_end",
    "quantity", "quantity_unit", "billed_amount", "billed_price", "contract_id",
    "tariff_price", "price_unit", "effective_start", "effective_end", "charge_kind",
    "rounding_rule", "invoice_total", "credit_amount", "tariff_type", "note",
)
ATOM_SCHEMA = obj({
    "field": enum(*FIELDS), "group": REFERENCE,
    "value": {"type": "string", "minLength": 1, "maxLength": 500},
    "location": REFERENCE, "quote": {"type": "string", "minLength": 1, "maxLength": 2000},
})
READ_SCHEMA = obj({
    "observations": {"type": "array", "minItems": 0, "maxItems": 128, "items": ATOM_SCHEMA},
    "limitations": {"type": "array", "minItems": 0, "maxItems": 32, "items": REASON},
})
ACTION_FIELDS = {
    "DECLARE_INVOICE": {"evidence_ids": IDS},
    "DECLARE_TARIFF": {"evidence_ids": IDS},
    "LINK_TARIFF": {"invoice_id": REFERENCE, "tariff_id": REFERENCE, "evidence_ids": IDS},
    "REQUEST_REVIEW": {"target": REFERENCE},
    "REQUEST_INSPECTION": {"source_id": REFERENCE, "location": REFERENCE},
    "MARK_UNRESOLVED": {"reason": REASON},
    "PROPOSE_READY": {},
}
ACTION_SCHEMA = obj({
    "issue_id": REFERENCE,
    "action": {"anyOf": [obj({"type": enum(kind), **fields}) for kind, fields in ACTION_FIELDS.items()]},
})
REVIEW_SCHEMA = obj({"verdict": enum("SUPPORTED", "AMBIGUOUS", "REJECTED"),
                     "evidence_ids": IDS, "reason": REASON})
FACT_REVIEW_SCHEMA = obj({
    **REVIEW_SCHEMA["properties"],
    "coverage": enum("ALL_MATERIAL_FACTS_BOUND", "INCOMPLETE"),
    "charge_kind": enum("CONSUMPTION_HT", "OTHER", "UNRESOLVED"),
    "end_convention": enum("EXCLUSIVE", "INCLUSIVE", "UNRESOLVED"),
    "nonmaterial_quarantine_ids": {"type": "array", "minItems": 0, "maxItems": 32, "items": REFERENCE},
})
TARIFF_REVIEW_SCHEMA = obj({
    **FACT_REVIEW_SCHEMA["properties"],
    "tariff_type": enum("FIXED", "INDEXED", "OTHER", "UNRESOLVED"),
    "rounding_rule": enum("HALF_UP_PER_LINE", "HALF_EVEN_PER_LINE", "OTHER", "UNRESOLVED"),
})
AUTHORITY_REVIEW_SCHEMA = obj({
    **REVIEW_SCHEMA["properties"],
    # Each of the two declared subjects may carry 32 independently valid atoms.
    # Their authority review must be able to cite the complete union, including
    # source qualifications, without dropping facts to fit a smaller contract.
    "evidence_ids": {**IDS, "maxItems": 64},
    "authority_kind": enum("ACCEPTED_CONTRACT", "INVOICE_PRICE", "UNRESOLVED"),
})


def validate(value: Any, schema: dict[str, Any], *, stage: str, path: str = "$") -> None:
    def fail(expected: str, received: Any = value, where: str = path) -> None:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage=stage, path=where,
                             expected=expected, actual=received)

    if "anyOf" in schema:
        if not isinstance(value, dict):
            fail("object")
        branches = [s for s in schema["anyOf"] if value.get("type") in s["properties"]["type"]["enum"]]
        if len(branches) != 1:
            fail("exact action enum", value.get("type"), path + ".type")
        validate(value, branches[0], stage=stage, path=path)
        return
    kind = schema["type"]
    if kind == "object":
        if not isinstance(value, dict):
            fail("object")
        if set(value) - set(schema["properties"]):
            fail("no additional fields")
        for key in schema["required"]:
            if key not in value:
                fail("required field", None, path + "." + key)
            validate(value[key], schema["properties"][key], stage=stage, path=path + "." + key)
    elif kind == "string":
        if not isinstance(value, str):
            fail("string")
        if "enum" in schema and value not in schema["enum"]:
            fail("enum: " + ", ".join(schema["enum"]))
        if not value.strip() or not schema.get("minLength", 1) <= len(value) <= schema.get("maxLength", 160):
            fail("bounded nonempty text")
        if value.lstrip().startswith(("{", "[")):
            try:
                nested = json.loads(value)
            except ValueError:
                pass
            else:
                if isinstance(nested, (dict, list)):
                    fail("no embedded JSON structure")
    elif kind == "array":
        if not isinstance(value, list) or not schema["minItems"] <= len(value) <= schema["maxItems"]:
            fail("bounded array")
        for index, item in enumerate(value):
            validate(item, schema["items"], stage=stage, path=f"{path}[{index}]")
        if path.endswith(".evidence_ids") and len(value) != len(set(value)):
            fail("unique references")
    else:
        raise RuntimeError(f"Internal unsupported schema vocabulary: {kind}")


def decode(raw: bytes, *, stage: str) -> dict[str, Any]:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_member")
            result[key] = value
        return result

    def finite(_):
        raise ValueError("nonfinite_number")

    digest = hashlib.sha256(raw).hexdigest()
    if len(raw) > MAX_BYTES:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage=stage, expected="bounded response",
                             response_sha256=digest, response_bytes=len(raw))
    try:
        result = json.loads(raw, object_pairs_hook=unique, parse_constant=finite)
        if not isinstance(result, dict):
            raise ValueError("object_required")
        return result
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage=stage, expected="strict finite JSON object",
                             response_sha256=digest, response_bytes=len(raw),
                             cause=type(exc).__name__) from exc


def validate_read_envelope(value: Any) -> None:
    # Keep row validation local; malformed envelope/limitations triggers repair.
    envelope = obj({**READ_SCHEMA["properties"], "observations": {
        "type": "array", "minItems": 0, "maxItems": 128, "items": obj({})}})
    observations = value.get("observations") if isinstance(value, dict) else None
    if not isinstance(value, dict) or set(value) != {"observations", "limitations"}:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="READ", expected="reader envelope", actual=value)
    if not isinstance(observations, list) or len(observations) > 128:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="READ", path="$.observations",
                             expected="bounded array", actual=observations)
    validate(value["limitations"], envelope["properties"]["limitations"], stage="READ", path="$.limitations")


def validate_action(value: Any, *, issue_id: str, targets: set[str] | None = None) -> None:
    validate(value, ACTION_SCHEMA, stage="ACTION")
    if value["issue_id"] != issue_id:
        raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", path="$.issue_id",
                             expected="focused issue " + issue_id, actual=value["issue_id"])
    for field in ("target", "invoice_id", "tariff_id", "source_id"):
        if targets is not None and field in value["action"] and value["action"][field] not in targets:
            raise BillingFailure("MODEL_PROTOCOL_INVALID", stage="ACTION", path="$.action." + field,
                                 expected="known local target", actual=value["action"][field])
