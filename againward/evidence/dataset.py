"""Domain-neutral typed records with versioned, content-bound provenance.

``source_row`` is a unique positive ordinal *within this snapshot*. Actual source
locations (including multiple documents) belong in provenance, not in that ordinal.
The legacy envelope is read losslessly; only domain adapters construct legacy data.
"""
from __future__ import annotations

from bisect import bisect_left
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
import math
import re
from typing import Any, Iterable

from .hashing import stable_hash

EVIDENCE_DATASET_SCHEMA = "againward-evidence-dataset-v2"
LEGACY_SCHEMA = "indicia-evidence-dataset-v1"
_DIGEST = re.compile(r"[0-9a-f]{64}")
_TYPES = {"integer", "number", "boolean", "datetime", "string", "mixed", "empty"}


def _validate_records(rows, fields):
    if not isinstance(rows, list) or not isinstance(fields, list) or not fields:
        raise ValueError("Typed rows and field definitions are required.")
    keys = [item.get("key") for item in fields if isinstance(item, dict)]
    if (len(keys) != len(fields) or any(not isinstance(k, str) or not k for k in keys)
            or len(keys) != len(set(keys)) or "source_row" not in keys):
        raise ValueError("Unique named fields including source_row are required.")
    types = {item["key"]: item.get("data_type") for item in fields}
    if set(types.values()) - _TYPES or types["source_row"] != "integer":
        raise ValueError("Unknown field type or invalid source_row type.")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) - set(keys):
            raise ValueError("Row contains undeclared fields.")
        ordinal = row.get("source_row")
        if type(ordinal) is not int or ordinal < 1 or ordinal in seen:
            raise ValueError("source_row must be a unique positive integer.")
        seen.add(ordinal)
        for key, value in row.items():
            if value is None:
                continue
            kind = types[key]
            valid = (
                (kind == "integer" and type(value) is int)
                or (kind == "number" and type(value) in (int, float) and math.isfinite(value))
                or (kind == "boolean" and type(value) is bool)
                or (kind in {"string", "datetime"} and isinstance(value, str))
                or (kind == "mixed" and type(value) in (str, int, float, bool))
            )
            if not valid or (type(value) is float and not math.isfinite(value)):
                raise ValueError(f"Value does not match declared type: {key}.")
            if kind == "datetime":
                try:
                    datetime.fromisoformat(value.replace("Z", "+00:00"))
                except ValueError as exc:
                    raise ValueError(f"Invalid ISO datetime: {key}.") from exc


def _validate_provenance(provenance, rows):
    if not isinstance(provenance, dict) or set(provenance) != {"sources", "rows"}:
        raise ValueError("Provenance must contain sources and row references.")
    sources = provenance["sources"]
    if not isinstance(sources, list) or not sources:
        raise ValueError("At least one hashed source is required.")
    ids = set()
    for source in sources:
        if (not isinstance(source, dict) or not isinstance(source.get("source_id"), str)
                or not source["source_id"] or source["source_id"] in ids
                or not _DIGEST.fullmatch(str(source.get("sha256", "")))):
            raise ValueError("Source IDs must be unique and source hashes valid.")
        ids.add(source["source_id"])
    references = provenance["rows"]
    if not isinstance(references, dict) or set(references) != {str(r["source_row"]) for r in rows}:
        raise ValueError("Every normalized row must link to its original sources.")
    for refs in references.values():
        if not isinstance(refs, list) or not refs:
            raise ValueError("Empty source linkage.")
        for ref in refs:
            if (not isinstance(ref, dict) or ref.get("source_id") not in ids
                    or not isinstance(ref.get("location"), str) or not ref["location"].strip()):
                raise ValueError("Unknown source or missing extraction location.")


@dataclass(frozen=True, slots=True)
class EvidenceDataset:
    dataset_id: str
    source_sha256: str
    dataset_sha256: str
    rows: list[dict[str, Any]]
    fields: list[dict[str, Any]]
    raw_auxiliary_source_rows: list[int] = field(default_factory=list)
    raw_auxiliary_columns: dict[str, list[Any]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)
    schema_version: str = EVIDENCE_DATASET_SCHEMA

    @classmethod
    def from_records(cls, *, dataset_id: str, records: Iterable[dict[str, Any]],
                     fields: list[dict[str, Any]], provenance: dict[str, Any],
                     metadata: dict[str, Any] | None = None,
                     raw_auxiliary_source_rows: list[int] | None = None,
                     raw_auxiliary_columns: dict[str, list[Any]] | None = None):
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            raise ValueError("dataset_id is required.")
        rows = deepcopy(list(records))
        _validate_records(rows, fields)
        _validate_provenance(provenance, rows)
        catalog = []
        for definition in fields:
            present = sum(row.get(definition["key"]) is not None for row in rows)
            catalog.append({"origin": "canonical", "original_name": definition["key"],
                            **deepcopy(definition), "present_count": present,
                            "missing_count": len(rows) - present,
                            "completeness": present / len(rows) if rows else 0.0})
        payload = {
            "schema_version": EVIDENCE_DATASET_SCHEMA,
            "dataset_id": dataset_id,
            "source_sha256": stable_hash(provenance["sources"]),
            "rows": rows,
            "fields": catalog,
            "raw_auxiliary_source_rows": list(raw_auxiliary_source_rows or []),
            "raw_auxiliary_columns": deepcopy(raw_auxiliary_columns or {}),
            "metadata": deepcopy(metadata or {}),
            "provenance": deepcopy(provenance),
        }
        payload["dataset_sha256"] = stable_hash(payload)
        return cls.from_dict(payload)

    @property
    def field_keys(self) -> set[str]:
        return {item["key"] for item in self.fields}

    def require_fields(self, names: Iterable[str]) -> list[str]:
        normalized = list(dict.fromkeys(str(name) for name in names))
        unknown = sorted(set(normalized) - self.field_keys)
        if unknown:
            raise ValueError("Champ(s) inconnu(s): " + ", ".join(unknown) + ".")
        return normalized

    def raw_auxiliary_for_row(self, source_row: int) -> dict[str, Any]:
        index = bisect_left(self.raw_auxiliary_source_rows, source_row)
        if index >= len(self.raw_auxiliary_source_rows) or self.raw_auxiliary_source_rows[index] != source_row:
            return {}
        return {key: values[index] for key, values in self.raw_auxiliary_columns.items()}

    def source_references(self, source_row: int) -> list[dict[str, Any]]:
        if self.schema_version == LEGACY_SCHEMA:
            return [{"source_sha256": self.source_sha256, "location": f"row:{source_row}"}]
        return deepcopy(self.provenance["rows"].get(str(source_row), []))

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "schema_version": self.schema_version,
            "dataset_id": self.dataset_id,
            "source_sha256": self.source_sha256,
            "dataset_sha256": self.dataset_sha256,
            "rows": self.rows,
            "fields": self.fields,
            "raw_auxiliary_source_rows": self.raw_auxiliary_source_rows,
            "raw_auxiliary_columns": self.raw_auxiliary_columns,
        }
        if self.schema_version == LEGACY_SCHEMA:
            payload.update(self.metadata)
        else:
            payload.update(metadata=self.metadata, provenance=self.provenance)
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]):
        schema = payload.get("schema_version")
        if schema not in {EVIDENCE_DATASET_SCHEMA, LEGACY_SCHEMA}:
            raise ValueError("Version de snapshot Evidence Plane inconnue.")
        rows, fields = payload.get("rows"), payload.get("fields")
        raw_rows = payload.get("raw_auxiliary_source_rows", [])
        raw_columns = payload.get("raw_auxiliary_columns", {})
        if (not isinstance(rows, list) or not isinstance(fields, list)
                or not isinstance(raw_rows, list) or raw_rows != sorted(set(raw_rows))
                or not isinstance(raw_columns, dict)
                or any(not isinstance(v, list) or len(v) != len(raw_rows) for v in raw_columns.values())):
            raise ValueError("Snapshot Evidence Plane invalide.")
        common = {"schema_version", "dataset_id", "dataset_sha256", "source_sha256",
                  "rows", "fields", "raw_auxiliary_source_rows", "raw_auxiliary_columns"}
        if schema == LEGACY_SCHEMA:
            metadata = {k: v for k, v in payload.items() if k not in common}
            body = {k: v for k, v in payload.items() if k not in {"schema_version", "dataset_id", "dataset_sha256"}}
            provenance = {}
        else:
            if set(payload) != common | {"metadata", "provenance"}:
                raise ValueError("Unknown or missing snapshot fields.")
            _validate_records(rows, fields)
            provenance = payload["provenance"]
            _validate_provenance(provenance, rows)
            if payload["source_sha256"] != stable_hash(provenance["sources"]):
                raise ValueError("Source-set hash mismatch.")
            metadata = payload["metadata"]
            if not isinstance(metadata, dict):
                raise ValueError("Metadata must be an object.")
            body = {k: v for k, v in payload.items() if k != "dataset_sha256"}
        actual = stable_hash(body)
        if actual != payload.get("dataset_sha256"):
            raise ValueError("Le hash du snapshot Evidence Plane ne correspond pas au contenu.")
        return cls(dataset_id=str(payload["dataset_id"]), source_sha256=str(payload["source_sha256"]),
                   dataset_sha256=actual, rows=rows, fields=fields,
                   raw_auxiliary_source_rows=raw_rows, raw_auxiliary_columns=raw_columns,
                   metadata=metadata, provenance=provenance, schema_version=schema)
