"""Recover transport notation, never missing evidence or commercial decisions.

This boundary runs only on fresh model output. Durable receipts still replay
against the exact strict schema, hashes, quotes and review versions.
"""
from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import hashlib
import json
import re
from typing import Any

from againward.domains.rental.entity_contract import (ENUM_ALIASES, ENUM_FIELDS, DECIMAL_FIELDS,
    DATE_FIELDS, BOOLEAN_FIELDS, MODEL_VALUE_TYPES)

from .contracts import DocumentError

VERSION = "model-observation-boundary-v2-rate-dimensions"
_RATE_DIMENSION_FIELDS = frozenset({"billing_unit", "quantity_basis", "weekends_billable"})


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




def _normalize_quoted_billed_units(row: dict[str, Any]) -> None:
    """Recover a billed-unit count only from its own exact quoted phrase.

    A read can place wording such as ``9 asset-days`` in the numeric
    ``billed_units`` field. Normalize it only when that candidate's quote has
    one unique count immediately bound to the same unit words. The quote stays
    unchanged and must still pass the ordinary exact-source check. A mismatch
    or multiple possible counts is left untouched and fails closed at decimal
    validation.
    """
    value = row.get("value")
    quote = row.get("raw_observed_value")
    if not isinstance(value, str) or not isinstance(quote, str):
        return
    value_match = re.fullmatch(
        r"\s*(?:(?P<count>[+-]?\d+(?:\.\d+)?)\s+)?(?P<unit>[A-Za-z][A-Za-z0-9 -]{0,39})\s*",
        value,
    )
    if value_match is None:
        return
    unit = value_match.group("unit").strip()
    words = re.split(r"[\s-]+", unit)
    if not words or any(not word for word in words):
        return
    unit_pattern = r"[\s-]+".join(re.escape(word) for word in words)
    source_counts = list(re.finditer(
        rf"(?<![\w.+-])(?P<count>[+-]?\d+(?:\.\d+)?)\s+{unit_pattern}(?![\w-])",
        quote,
        flags=re.IGNORECASE,
    ))
    if len(source_counts) != 1:
        return
    source_count = source_counts[0].group("count")
    model_count = value_match.group("count")
    if model_count is not None and Decimal(model_count) != Decimal(source_count):
        return
    row["value"] = source_count
    note = "Parsed billed_units from its unique quoted unit expression."
    previous = row.get("normalization_notes", "")
    if isinstance(previous, str):
        row["normalization_notes"] = "; ".join(part for part in (previous.strip(), note) if part)


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
            if field == "billed_units":
                _normalize_quoted_billed_units(result)
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


def _normalize_rate_dimension_rows(rows: list[Any], *, visual: bool,
                                   group_key: str) -> list[Any]:
    """Canonicalize dimensions only when the same candidate quote states them.

    A model can split one explicit denominator across fields (for example,
    ``billing_unit=DAY`` and ``quantity_basis=PER_ASSET`` while quoting
    ``per asset per calendar day``). Parse that source-bound expression,
    reconcile supplied dimensions, and fill only dimensions explicitly present
    in the expression. Quotes, locations/pages and grouping remain unchanged.
    """
    from againward.domains.rental.rate_dimensions import (
        has_unsupported_calendar_rate_convention, rate_dimensions,
    )

    prepared: list[Any] = []
    quote_key = "visible_text" if visual else "raw_observed_value"
    for value in rows:
        if not isinstance(value, dict) or value.get("semantic_type") not in _RATE_DIMENSION_FIELDS:
            prepared.append(value)
            continue
        row = deepcopy(value)
        value_dimensions = rate_dimensions(row.get("value"))
        quote = row.get(quote_key)
        if isinstance(quote, str) and has_unsupported_calendar_rate_convention(quote):
            raise DocumentError("UNSUPPORTED_RATE_DIMENSION",
                "Source states an unsupported calendar rate convention",
                diagnostic={"stage": "MODEL_OUTPUT_NORMALIZATION",
                    "schema_path": f"$.{('observations' if visual else 'candidates')}[].{quote_key}",
                    "validation_code": "UNSUPPORTED_CALENDAR_RATE_CONVENTION",
                    "error_category": "SOURCE_EVIDENCE_MISSING"})
        quote_dimensions = rate_dimensions(quote) if isinstance(quote, str) else None
        if (quote_dimensions is not None and value_dimensions is not None
                and any(value_dimensions.get(key) != value for key, value in quote_dimensions.items()
                        if key in value_dimensions)):
            raise DocumentError("EXTRACTION_CONTRADICTION",
                "Rate dimension value conflicts with its exact source wording",
                diagnostic={"stage": "MODEL_OUTPUT_NORMALIZATION",
                    "schema_path": f"$.{('observations' if visual else 'candidates')}[].value",
                    "validation_code": "RATE_DIMENSION_EVIDENCE_CONFLICT",
                    "error_category": "SEMANTIC_CONTRADICTION"})
        dimensions = quote_dimensions
        if (dimensions is None and value_dimensions is not None
                and isinstance(quote, str) and isinstance(row.get("value"), str)):
            normalized_value = token(row["value"])
            normalized_quote = token(quote)
            if normalized_value and normalized_value in normalized_quote:
                dimensions = value_dimensions
        if dimensions is None:
            prepared.append(row)
            continue

        field = row["semantic_type"]
        expected = dimensions.get(field)
        supplied = row.get("value")
        supplied_token = token(supplied) if isinstance(supplied, str) else supplied
        compatible = (value_dimensions is not None or supplied_token == expected)
        # This is deliberately evidence-sensitive, not a global enum alias:
        # only the established parser's exact ``per asset`` wording maps to
        # the Rental contract's per-item quantity basis.
        if (not compatible and field == "quantity_basis" and supplied_token == "PER_ASSET"
                and expected == "PER_ITEM"):
            compatible = True
        if expected is not None and not compatible:
            raise DocumentError("EXTRACTION_CONTRADICTION",
                "Explicit rate dimension conflicts with its exact source wording",
                diagnostic={"stage": "MODEL_OUTPUT_NORMALIZATION",
                    "schema_path": f"$.{('observations' if visual else 'candidates')}[].value",
                    "validation_code": "RATE_DIMENSION_EVIDENCE_CONFLICT",
                    "error_category": "SEMANTIC_CONTRADICTION"})
        if expected is not None:
            row["value"] = expected
            if supplied != expected:
                note = "Canonicalized from the exact source rate-denominator wording."
                previous = row.get("normalization_notes", "")
                if isinstance(previous, str):
                    row["normalization_notes"] = "; ".join(
                        part for part in (previous.strip(), note) if part)
        prepared.append(row)

        # Materialize other explicitly stated dimensions when the model emitted
        # only one field for the compound wording. Existing same-quote claims
        # are reconciled above rather than duplicated.
        for derived_field, derived_value in dimensions.items():
            if derived_field == field:
                continue
            represented = any(
                isinstance(other, dict)
                and other.get(group_key) == row.get(group_key)
                and other.get("semantic_type") == derived_field
                and other.get(quote_key) == quote
                and (not visual or other.get("page") == row.get("page"))
                for other in rows
            )
            if not represented:
                derived = deepcopy(row)
                derived["semantic_type"] = derived_field
                derived["value"] = derived_value
                derived["value_type"] = "BOOLEAN" if derived_field == "weekends_billable" else "ENUM"
                if not visual:
                    derived["normalization_notes"] = "Explicit rate denominator decomposition."
                prepared.append(derived)

    # Multiple dimension observations can quote the same denominator. Collapse
    # only equivalent rows with the same source-local group and exact evidence.
    deduplicated: list[Any] = []
    seen: set[str] = set()
    for row in prepared:
        if not isinstance(row, dict) or row.get("semantic_type") not in _RATE_DIMENSION_FIELDS:
            deduplicated.append(row)
            continue
        identity = {key: row.get(key) for key in (
            group_key, "semantic_type", "value", "location", "page",
            "raw_observed_value", "visible_text")}
        fingerprint = json.dumps(identity, sort_keys=True, ensure_ascii=False)
        if fingerprint not in seen:
            seen.add(fingerprint)
            deduplicated.append(row)
    return deduplicated


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
            group_key = ("entity_hint" if key == "observations" or any(
                isinstance(row, dict) and "entity_hint" in row and "entity_id" not in row
                for row in result[key]) else "entity_id")
            result[key] = _normalize_rate_dimension_rows(result[key], visual=key == "observations",
                                                         group_key=group_key)
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
