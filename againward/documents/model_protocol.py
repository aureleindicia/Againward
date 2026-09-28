"""Recover transport notation, never missing evidence or commercial decisions.

This boundary runs only on fresh model output. Durable receipts still replay
against the exact strict schema, hashes, quotes and review versions.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import re
from typing import Any

from againward.domains.rental.entity_contract import (ENUM_ALIASES, ENUM_FIELDS, DECIMAL_FIELDS,
    DATE_FIELDS, BOOLEAN_FIELDS, MODEL_VALUE_TYPES)

from .contracts import DocumentError

VERSION = "model-observation-boundary-v2-rate-dimensions"


def load_model_json(raw: bytes, *, maximum: int) -> dict[str, Any]:
    """Allow an outer JSON fence and trailing commas, not truncated/duplicate data."""
    if len(raw) > maximum:
        raise DocumentError("RESOURCE_LIMIT", "Model response exceeds byte budget")
    try:
        content = raw.decode("utf-8-sig").strip()
        if content.startswith("```json\n") and content.endswith("```"):
            content = content[8:-3].strip()
        elif content.startswith("```\n") and content.endswith("```"):
            content = content[4:-3].strip()
        # Token-aware removal: commas inside evidence strings are untouched.
        chars, quoted, escaped = [], False, False
        for i, ch in enumerate(content):
            if quoted:
                chars.append(ch)
                if escaped:
                    escaped = False
                elif ch == "\\":
                    escaped = True
                elif ch == '"':
                    quoted = False
            elif ch == '"':
                quoted = True
                chars.append(ch)
            elif ch == ",":
                after = i + 1
                while after < len(content) and content[after].isspace():
                    after += 1
                if after == len(content) or content[after] not in "}]":
                    chars.append(ch)
            else:
                chars.append(ch)

        def unique(pairs):
            result = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate object member")
                result[key] = value
            return result

        result = json.loads("".join(chars), object_pairs_hook=unique, parse_float=str,
                            parse_constant=lambda _: (_ for _ in ()).throw(ValueError("Nonfinite number")))
        if not isinstance(result, dict):
            raise ValueError("Object required")
        return result
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unambiguous bounded model JSON required") from exc


def token(value: str) -> str:
    return re.sub(r"[\s-]+", "_", value.strip()).upper()




def normalize_row(row: dict[str, Any], *, visual: bool, rental: bool) -> dict[str, Any]:
    result = deepcopy(row)
    if not visual and "entity_hint" in result and "entity_id" not in result:
        hint = result.pop("entity_hint")
        if isinstance(hint, str) and hint:
            result["entity_id"] = "group-" + hashlib.sha256(hint.encode()).hexdigest()[:24]
        else:
            result["entity_id"] = hint
    field = result.get("semantic_type")
    if not isinstance(field, str):
        return result
    if rental:
        field = field.strip().lower().replace("-", "_").replace(" ", "_")
        result["semantic_type"] = field
        value = result.get("value")
        if field in ENUM_FIELDS and isinstance(value, str):
            canonical = token(value)
            result["value"] = ENUM_ALIASES.get(field, {}).get(canonical, canonical)
            result["value_type"] = "ENUM"
        elif field in DECIMAL_FIELDS:
            result["value_type"] = "DECIMAL"
            if type(value) is int:
                result["value"] = str(value)
        elif field == "currency":
            result["value_type"] = "CURRENCY"
            if isinstance(value, str):
                result["value"] = value.strip().upper()
        elif field in DATE_FIELDS:
            result["value_type"] = "DATE"
        elif field in BOOLEAN_FIELDS:
            result["value_type"] = "BOOLEAN"
        elif field.endswith("_id") or field in {"serial_number", "charge_key"}:
            result["value_type"] = "IDENTIFIER"
    if rental and field in MODEL_VALUE_TYPES:
        result["value_type"] = MODEL_VALUE_TYPES[field]
    if "value_type" not in result:
        # The model still supplies unfamiliar types; a missing type is unknown,
        # never a permissive text fallback for an unspecified semantic field.
        result["value_type"] = "TEXT" if field in {"description", "verification"} else "UNKNOWN"
    elif isinstance(result["value_type"], str):
        result["value_type"] = token(result["value_type"])
    if visual:
        page = result.get("page")
        if isinstance(page, str) and re.fullmatch(r"[1-9][0-9]{0,5}", page):
            result["page"] = int(page)
        result.setdefault("ambiguity", [])
        group_key = "entity_hint"
    else:
        result.setdefault("ambiguity_flags", [])
        result.setdefault("normalization_notes", "")
        flags = result.get("ambiguity_flags")
        if isinstance(flags, list):
            normalized_flags = []
            notes = []
            for flag in flags:
                if isinstance(flag, str) and flag and len(flag) <= 500 and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", flag):
                    normalized_flags.append("MODEL_AMBIGUITY_" + hashlib.sha256(flag.encode()).hexdigest()[:16])
                    notes.append(flag)
                else:
                    normalized_flags.append(flag)
            result["ambiguity_flags"] = normalized_flags
            if notes and isinstance(result["normalization_notes"], str):
                result["normalization_notes"] += "; Model uncertainty: " + "; ".join(notes)
        group_key = "entity_id"
    group = result.get(group_key)
    if group is None or group == "":
        # An ungrouped observation stays an isolated fragment. No document/line
        # identity is guessed from a filename, position or neighbouring amount.
        result[group_key] = "fragment-" + hashlib.sha256(
            json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:24]
    elif not visual and isinstance(group, str) and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,159}", group):
        result[group_key] = "group-" + hashlib.sha256(group.encode()).hexdigest()[:24]
    return result


def normalize_read(raw: dict[str, Any], parsed: Any, *, rental: bool) -> dict[str, Any]:
    result = deepcopy(raw)
    visual = any(unit.route != "NATIVE" for unit in parsed.units)
    has_native = any(unit.route == "NATIVE" for unit in parsed.units)
    # Exactly one known envelope, never select between competing payloads.
    if set(result) in ({"result"}, {"extraction"}):
        nested = next(iter(result.values()))
        if isinstance(nested, dict):
            result = nested
    result.setdefault("status", "NEEDS_REVIEW")
    result.setdefault("limitations", [])
    if isinstance(result.get("status"), str):
        result["status"] = token(result["status"])
    keys = ["observations"] if visual else ["candidates"]
    if visual and has_native:
        keys.append("native_candidates")
    # A legacy visual fixture has candidates. Preserve that explicit route.
    if visual and "candidates" in result:
        keys.append("candidates")
    for key in keys:
        if key not in result or not isinstance(result[key], list):
            continue
        if rental:
            from againward.domains.rental.rate_dimensions import rate_dimensions
            expanded = []
            for row in result[key]:
                dimensions = rate_dimensions(row.get("value")) if isinstance(row, dict) and row.get("semantic_type") == "billing_unit" else None
                if not dimensions:
                    expanded.append(row)
                    continue
                for field, value in dimensions.items():
                    derived = {**row, "semantic_type": field, "value": value}
                    # The exact original quote/page stays attached to EACH
                    # unapproved dimension. All pass normal source/review gates.
                    if key != "observations":
                        derived["normalization_notes"] = "Explicit rate denominator decomposition"
                    expanded.append(derived)
            result[key] = expanded
        result[key] = [normalize_row(row, visual=key == "observations", rental=rental)
                       if isinstance(row, dict) else row for row in result[key]
                       if not (isinstance(row, dict) and "value" in row and row["value"] is None)]
        if key == "observations":
            continue
        for row in result[key]:
            if not isinstance(row, dict):
                continue
            location = row.get("location")
            if (location is not None and not isinstance(location, str)) or location in {unit.location for unit in parsed.units}:
                continue
            quote = row.get("raw_observed_value")
            if not isinstance(quote, str) or not quote:
                continue
            units = [unit for unit in parsed.units if unit.route == "NATIVE" and unit.text.count(quote) == 1]
            if len(units) == 1 and sum(unit.text.count(quote) for unit in parsed.units if unit.route == "NATIVE") == 1:
                row["location"] = units[0].location
    return result


def normalize_decision(raw: dict[str, Any], *, source_id: str) -> dict[str, Any]:
    """Single-source invocation owns source identity/cardinality, never selection."""
    result = deepcopy(raw)
    if set(result) == {"decision"} and isinstance(result["decision"], dict):
        result = {"decisions": [result["decision"]]}
    elif "selection" in result:
        result = {"decisions": [result]}
    elif isinstance(result.get("decisions"), dict):
        result["decisions"] = [result["decisions"]]
    rows = result.get("decisions")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        return result
    row = rows[0]
    row.setdefault("source_id", source_id)
    if isinstance(row.get("selection"), str):
        row["selection"] = token(row["selection"])
    for key in ("citations", "observations", "candidate_selections"):
        row.setdefault(key, [])
    for reference in row["candidate_selections"] if isinstance(row["candidate_selections"], list) else []:
        if not isinstance(reference, dict):
            continue
        for key in ("reader", "decision"):
            if isinstance(reference.get(key), str):
                reference[key] = token(reference[key])
        number = reference.get("candidate_index")
        if isinstance(number, str) and re.fullmatch(r"[1-9][0-9]{0,7}", number):
            reference["candidate_index"] = int(number)
        group = reference.get("entity_id")
        if isinstance(group, str) and group and not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,159}", group):
            reference["entity_id"] = "group-" + hashlib.sha256(group.encode()).hexdigest()[:24]
    for citation in row["citations"] if isinstance(row["citations"], list) else []:
        if isinstance(citation, dict):
            citation.setdefault("source_id", source_id)
    return result
