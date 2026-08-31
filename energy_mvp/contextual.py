from __future__ import annotations

import json
import math
import re
import unicodedata
from datetime import date, datetime
from typing import Any, Iterable

from .models import AuxiliaryFieldDefinition, ContextualFieldStore


_MISSING_MARKERS = {"", "na", "n/a", "nan", "null", "none", "-"}
_BOOLEAN_TRUE = {"true", "yes", "oui", "active", "actif"}
_BOOLEAN_FALSE = {"false", "no", "non", "inactive", "inactif"}
_NUMBER_PATTERN = re.compile(r"^[+-]?(?:\d+(?:[.,]\d+)?|[.,]\d+)$")


def _normalize(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(character for character in text if not unicodedata.combining(character))
    return re.sub(r"[^a-z0-9]+", "_", text.casefold()).strip("_")


def _is_missing(value: Any) -> bool:
    return value is None or str(value).strip().casefold() in _MISSING_MARKERS


def _json_safe_raw(value: Any, maximum_characters: int) -> tuple[Any, bool]:
    if value is None or isinstance(value, (bool, int)):
        return value, False
    if isinstance(value, float):
        return value if math.isfinite(value) else str(value), False
    if isinstance(value, (datetime, date)):
        return value.isoformat(), False
    text = str(value)
    if len(text) <= maximum_characters:
        return text, False
    return text[:maximum_characters], True


def _strict_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    text = _normalize(value)
    if text in _BOOLEAN_TRUE:
        return True
    if text in _BOOLEAN_FALSE:
        return False
    return None


def _strict_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not _NUMBER_PATTERN.fullmatch(text):
        return None
    unsigned = text.lstrip("+-")
    integer_part = re.split(r"[.,]", unsigned, maxsplit=1)[0]
    if len(integer_part) > 1 and integer_part.startswith("0"):
        # Conserve les identifiants tels que 00123 sous forme textuelle.
        return None
    try:
        numeric = float(text.replace(",", "."))
    except ValueError:
        return None
    return numeric if math.isfinite(numeric) else None


def _strict_datetime(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()).isoformat()
    text = str(value).strip()
    if not text:
        return None
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    try:
        return datetime.fromisoformat(candidate).isoformat()
    except ValueError:
        return None


def _infer_type(original_name: str, values: list[Any]) -> str:
    if not values:
        return "empty"
    booleans = [_strict_boolean(value) for value in values]
    if all(value is not None for value in booleans):
        return "boolean"
    numbers = [_strict_number(value) for value in values]
    if all(value is not None for value in numbers):
        return "number"
    normalized = _normalize(original_name)
    timestamp_hint = any(
        token in normalized.split("_")
        for token in ("date", "time", "timestamp", "datetime", "horodatage")
    )
    datetimes = [_strict_datetime(value) for value in values]
    if timestamp_hint and all(value is not None for value in datetimes):
        return "datetime"
    if (
        any(value is not None for value in numbers)
        or timestamp_hint and any(value is not None for value in datetimes)
        or any(value is not None for value in booleans)
    ):
        return "mixed"
    return "string"


def _coerce(value: Any, inferred_type: str) -> Any:
    if _is_missing(value):
        return None
    if inferred_type == "boolean":
        return _strict_boolean(value)
    if inferred_type == "number":
        return _strict_number(value)
    if inferred_type == "datetime":
        return _strict_datetime(value)
    return value


def _field_key(index: int, original_name: str) -> str:
    normalized = _normalize(original_name) or "unnamed"
    return f"aux_{index + 1:04d}_{normalized}"


def build_contextual_store(
    headers: list[str],
    rows: list[list[Any]],
    *,
    canonical_indices: Iterable[int | None],
    retained_source_rows: Iterable[int],
    maximum_fields: int = 128,
    maximum_value_characters: int = 4096,
) -> ContextualFieldStore:
    """Préserve les colonnes inconnues sans les promouvoir au noyau physique."""

    if maximum_fields < 0 or maximum_fields > 512:
        raise ValueError("maximum_auxiliary_fields doit être compris entre 0 et 512.")
    if not 64 <= maximum_value_characters <= 65_536:
        raise ValueError(
            "maximum_auxiliary_value_characters doit être compris entre 64 et 65536."
        )
    selected = {index for index in canonical_indices if index is not None}
    auxiliary_columns = [
        (index, header, _field_key(index, header))
        for index, header in enumerate(headers)
        if index not in selected
    ]
    if len(auxiliary_columns) > maximum_fields:
        raise ValueError(
            f"{len(auxiliary_columns)} colonnes auxiliaires dépassent la limite "
            f"déclarée de {maximum_fields}; augmentez explicitement "
            "maximum_auxiliary_fields ou réduisez la source."
        )
    if not auxiliary_columns:
        return ContextualFieldStore(
            maximum_fields=maximum_fields,
            maximum_value_characters=maximum_value_characters,
        )
    retained = set(retained_source_rows)
    source_rows: list[int] = []
    raw_columns: dict[str, list[Any]] = {
        key: [] for _, _, key in auxiliary_columns
    }
    truncations: dict[str, int] = {key: 0 for _, _, key in auxiliary_columns}
    for source_row, row in enumerate(rows, start=2):
        if source_row not in retained:
            continue
        source_rows.append(source_row)
        for index, _, key in auxiliary_columns:
            original = row[index] if index < len(row) else None
            raw, truncated = _json_safe_raw(original, maximum_value_characters)
            truncations[key] += int(truncated)
            raw_columns[key].append(raw)
    store = ContextualFieldStore(
        source_rows=source_rows,
        raw_columns=raw_columns,
        typed_columns={key: list(values) for key, values in raw_columns.items()},
        maximum_fields=maximum_fields,
        maximum_value_characters=maximum_value_characters,
    )
    _finalize_store(store, auxiliary_columns, truncations)
    return store


def _finalize_store(
    store: ContextualFieldStore,
    columns: list[tuple[int, str, str]],
    truncations: dict[str, int] | None = None,
) -> None:
    truncations = truncations or {
        item.key: item.truncated_value_count for item in store.fields
    }
    row_count = len(store.source_rows)
    definitions: list[AuxiliaryFieldDefinition] = []
    for index, original_name, key in columns:
        raw_values = store.raw_columns.get(key, [None] * row_count)
        present = [value for value in raw_values if not _is_missing(value)]
        inferred_type = _infer_type(original_name, present)
        store.typed_columns[key] = [
            _coerce(value, inferred_type) for value in raw_values
        ]
        distinct = len(
            {
                json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
                for value in present
            }
        )
        definitions.append(
            AuxiliaryFieldDefinition(
                key=key,
                original_name=original_name,
                normalized_name=_normalize(original_name),
                source_column_index=index,
                inferred_type=inferred_type,
                present_count=len(present),
                missing_count=row_count - len(present),
                distinct_count=distinct,
                high_cardinality=(
                    len(present) >= 50 and distinct / len(present) >= 0.5
                ),
                truncated_value_count=truncations.get(key, 0),
            )
        )
    store.fields = definitions


def retain_contextual_rows(
    store: ContextualFieldStore, retained_source_rows: Iterable[int]
) -> None:
    retained = set(retained_source_rows)
    positions = [
        index for index, source_row in enumerate(store.source_rows)
        if source_row in retained
    ]
    store.source_rows = [store.source_rows[index] for index in positions]
    store.raw_columns = {
        key: [values[index] for index in positions]
        for key, values in store.raw_columns.items()
    }
    store.typed_columns = {
        key: [values[index] for index in positions]
        for key, values in store.typed_columns.items()
    }
    columns = [
        (item.source_column_index, item.original_name, item.key) for item in store.fields
    ]
    _finalize_store(store, columns)
