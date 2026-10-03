"""One closed intent contract for structured output and Python validation.

No aliases, missing-field recovery or semantic selection. Evidence eligibility,
source coordinates, reviews and readiness remain owned by their existing gates.
"""
from __future__ import annotations

import json
from typing import Any

from againward.documents.contracts import DocumentError
from .case_graph_actions import KINDS
from .case_graph_claims import CLAIM_VALUES

VERSION = "rental-investigator-response-v1"
MAX_RESPONSE_BYTES = 32_000


def _object(properties: dict[str, Any]) -> dict[str, Any]:
    return {"type": "object", "additionalProperties": False,
            "required": list(properties), "properties": properties}


def _enum(values) -> dict[str, Any]:
    return {"type": "string", "enum": sorted(values)}


REFERENCE = {"type": "string", "minLength": 1, "maxLength": 160}
REASON = {"type": "string", "minLength": 1, "maxLength": 2000}
IDS = {"type": "array", "minItems": 1, "maxItems": 64, "items": REFERENCE}
ACTION_FIELDS = {
    "DECLARE_OCCURRENCE": {"kind": _enum(KINDS), "evidence_ids": IDS, "anchor_ids": IDS},
    "ATTACH_OBSERVATIONS": {"target": REFERENCE, "evidence_ids": IDS},
    "REPLACE_OBSERVATIONS": {"target": REFERENCE, "evidence_ids": IDS},
    "PROPOSE_CLAIM": {"proposal": {"anyOf": [
        _object({"kind": _enum([kind]), "target": REFERENCE, "value": _enum(values),
                 "evidence_ids": IDS, "reason": REASON}) for kind, values in CLAIM_VALUES.items()]}},
    "REQUEST_REVIEW": {"target": REFERENCE},
    "REQUEST_REREAD": {"source_id": REFERENCE, "locations": {
        "type": "array", "minItems": 0, "maxItems": 64, "items": REFERENCE}},
    "INSPECT_SOURCE": {"source_id": REFERENCE, "location": REFERENCE,
                       "start": {"type": "integer", "minimum": 0},
                       "end": {"type": "integer", "minimum": 1}},
    "INSPECT_OCCURRENCE": {"target": REFERENCE},
    "INSPECT_ISSUE": {"target": REFERENCE},
    "REFRESH_RELATIONS": {},
    "MARK_UNRESOLVED": {"reason": REASON},
    "PROPOSE_READY": {},
}
RESPONSE_SCHEMA = _object({
    "issue_id": {"type": ["string", "null"]},
    "action": {"anyOf": [_object({"type": _enum([kind]), **fields})
                         for kind, fields in ACTION_FIELDS.items()]},
})


def _invalid(path: str, rule: str, value: Any) -> None:
    # Only schema-owned paths/rule names and shapes; never source or model text.
    raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Closed investigator intent required",
        diagnostic={"stage": "INVESTIGATOR_RESPONSE_CONTRACT", "schema_version": VERSION,
                    "schema_path": path, "rule": rule, "actual_type": type(value).__name__})


def _validate(value: Any, schema: dict[str, Any], path: str) -> None:
    """Validate only the small schema vocabulary constructed in this module."""
    if "anyOf" in schema:
        # Discriminator selection is exact, never choose a convenient branch.
        discriminator = "type" if path == "$.action" else "kind"
        if not isinstance(value, dict):
            _invalid(path, "object", value)
        tag = value.get(discriminator)
        branches = [branch for branch in schema["anyOf"]
                    if tag in branch["properties"][discriminator]["enum"]]
        if len(branches) != 1:
            _invalid(path + "." + discriminator, "enum", tag)
        _validate(value, branches[0], path)
        return
    kind = schema["type"]
    if kind == ["string", "null"]:
        if value is not None and (not isinstance(value, str) or not value.strip() or len(value) > 160):
            _invalid(path, "nullable_reference", value)
    elif kind == "object":
        if not isinstance(value, dict):
            _invalid(path, "object", value)
        if set(value) - set(schema["properties"]):
            _invalid(path, "additionalProperties", value)
        for key in schema["required"]:
            if key not in value:
                _invalid(path + "." + key, "required", None)
            _validate(value[key], schema["properties"][key], path + "." + key)
    elif kind == "string":
        if not isinstance(value, str):
            _invalid(path, "string", value)
        if "enum" in schema and value not in schema["enum"]:
            _invalid(path, "enum", value)
        if not value.strip() or not schema.get("minLength", 1) <= len(value) <= schema.get("maxLength", 160):
            _invalid(path, "length", value)
    elif kind == "integer":
        if type(value) is not int or value < schema["minimum"]:
            _invalid(path, "integer_range", value)
    elif kind == "array":
        if not isinstance(value, list) or not schema["minItems"] <= len(value) <= schema["maxItems"]:
            _invalid(path, "array_length", value)
        for i, item in enumerate(value):
            _validate(item, schema["items"], path + f"[{i}]")
        if len(value) != len(set(value)):
            _invalid(path, "unique_items", value)
    else:
        raise RuntimeError("Unsupported internal investigator schema type")


def validate_response(response: Any, focus: str | None) -> None:
    try:
        size = len(json.dumps(response, allow_nan=False).encode("utf-8"))
    except (ValueError, TypeError, RecursionError) as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Finite JSON intent required",
            diagnostic={"stage": "INVESTIGATOR_RESPONSE_CONTRACT", "schema_version": VERSION,
                        "schema_path": "$", "rule": "finite_json"}) from exc
    if size > MAX_RESPONSE_BYTES:
        raise DocumentError("RESOURCE_LIMIT", "Single bounded action exceeds response budget")
    _validate(response, RESPONSE_SCHEMA, "$")
    if response["issue_id"] != focus:
        _invalid("$.issue_id", "focused_issue", response["issue_id"])
