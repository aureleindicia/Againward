"""Canonical extraction ingestion with source hashes and explicit table mappings.

Codex supplies semantic extraction from documents; Python verifies types, source
locations, hashes and declared mappings. No vendor heuristic authorizes a rate.
"""
from __future__ import annotations

import csv
from copy import deepcopy
from dataclasses import asdict, fields
import json
from datetime import date, datetime
from pathlib import Path

from againward.core.privacy import assert_source_approved_for_analysis, case_root_for_path, privacy_manifest_path
from againward.core.workflow import fingerprint
from againward.evidence.dataset import EvidenceDataset
from againward.evidence.hashing import stable_hash
from .models import RentalCase, SCHEMA, _RECORD_TYPES, _ID_FIELDS, decimal_value
from .arithmetic import deterministic_decimal

EXTRACTION_SCHEMA = "againward-rental-extraction-v1"


def _local_source(root: Path, relative: str) -> Path:
    owner = case_root_for_path(root)
    if not isinstance(relative, str) or Path(relative).is_absolute() or (owner is None and ".." in Path(relative).parts):
        raise ValueError("Rental document path must be relative to the extraction directory.")
    path = root / relative
    if not path.is_file() or not path.resolve().is_relative_to((owner or root).resolve()):
        raise ValueError("Rental document is absent or outside the extraction directory.")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise ValueError("Symlink source documents are refused.")
    return path


def _read_table(path: Path, *, sheet: str | None = None):
    if path.suffix.lower() == ".csv":
        if sheet is not None:
            raise ValueError("CSV has no worksheets.")
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
    elif path.suffix.lower() == ".xlsx":
        from openpyxl import load_workbook
        book = load_workbook(path, read_only=True, data_only=False)
        try:
            if sheet not in book.sheetnames:
                raise ValueError("An explicit existing XLSX worksheet is required.")
            rows = list(book[sheet].iter_rows(values_only=True))
            if any(isinstance(value, str) and value.startswith("=") for row in rows for value in row):
                raise ValueError("Formula-derived Rental values need an explicit reviewed export.")
        finally:
            book.close()
    else:
        raise ValueError("Mapped Rental tables support CSV/XLSX; other documents need canonical semantic extraction.")
    if not rows or not rows[0]:
        raise ValueError("Empty Rental source table.")
    headers = [str(value) if value is not None else "" for value in rows[0]]
    if any(not h for h in headers) or len(headers) != len(set(headers)):
        raise ValueError("Empty or duplicate table headers are ambiguous.")
    if any(len(row) != len(headers) for row in rows[1:]):
        raise ValueError("Inconsistent Rental table width.")
    return headers, rows[1:]


def _expand_extraction(payload, root: Path, *, output_directory=None):
    if set(payload) != {"schema_version", "case", "tables"} or not isinstance(payload["tables"], list):
        raise ValueError("Malformed canonical extraction package.")
    result = deepcopy(payload["case"])
    if result.get("schema_version") != SCHEMA:
        raise ValueError("Extraction package requires an explicit canonical case schema.")
    documents = {d["document_id"]: d for d in result["documents"]}
    transformations = []
    for spec in payload["tables"]:
        if not isinstance(spec, dict) or set(spec) - {"record_type", "document_id", "columns", "constants", "sheet"}:
            raise ValueError("Unknown table mapping fields.")
        record_type = spec.get("record_type")
        if record_type not in _RECORD_TYPES or record_type == "documents":
            raise ValueError("Table record_type must name a canonical Rental record.")
        doc = documents.get(spec.get("document_id"))
        if doc is None:
            raise ValueError("Mapped source document not declared.")
        path = _local_source(root, doc["path"])
        assert_source_approved_for_analysis(path, output_directory=output_directory)
        if fingerprint(path) != doc["sha256"]:
            raise ValueError("Mapped source document changed after extraction.")
        headers, rows = _read_table(path, sheet=spec.get("sheet"))
        mapping, constants = spec.get("columns"), spec.get("constants", {})
        allowed = {f.name for f in fields(_RECORD_TYPES[record_type])} - {"evidence_refs"}
        if (not isinstance(mapping, dict) or not mapping or not isinstance(constants, dict)
                or set(mapping) & set(constants) or (set(mapping) | set(constants)) - allowed
                or any(name not in headers for name in mapping.values())):
            raise ValueError("Canonical table mapping is incomplete, overlapping or unknown.")
        indices = {field: headers.index(column) for field, column in mapping.items()}
        for ordinal, row in enumerate(rows, 2):
            values = dict(constants)
            for field, index in indices.items():
                raw = row[index]
                if raw is None or raw == "":
                    values[field] = None
                elif field in {"minimum_days", "tier_min_days", "tier_max_days"}:
                    value = decimal_value(str(raw), name=field)
                    if value != value.to_integral_value():
                        raise ValueError("Fractional integer in Rental source.")
                    values[field] = int(value)
                elif field in {"weekends_billable", "stop_day_billable"}:
                    if str(raw).lower() not in {"true", "false"}:
                        raise ValueError("Mapped boolean must explicitly be true or false.")
                    values[field] = str(raw).lower() == "true"
                elif field in {"start", "end", "date", "extended_end", "effective_from"} and isinstance(raw, (date, datetime)):
                    if isinstance(raw, datetime) and (raw.hour or raw.minute or raw.second or raw.microsecond or raw.tzinfo):
                        raise ValueError("Rental calendar dates cannot silently discard a spreadsheet time or timezone.")
                    values[field] = raw.date().isoformat() if isinstance(raw, datetime) else raw.isoformat()
                else:
                    # Spreadsheet numeric cells are normalized to their displayed decimal
                    # value without any float arithmetic; the original bytes stay hash-bound.
                    values[field] = str(raw)
            location = f"sheet:{spec['sheet']}/row:{ordinal}" if spec.get("sheet") else f"row:{ordinal}"
            values["evidence_refs"] = [{"document_id": doc["document_id"], "location": location, "field": field}
                                        for field in mapping]
            # Constants are explicit analyst extraction, linked to the same source row.
            result[record_type].append(values)
        transformations.append({"document_id": doc["document_id"], "record_type": record_type,
                                "rows": len(rows), "columns": mapping, "constants": constants,
                                "operation": "EXPLICIT_CANONICAL_MAPPING_NO_DEDUPLICATION"})
    return result, transformations


def load_rental_case(source: str | Path, *, output_directory=None):
    source = Path(source)
    assert_source_approved_for_analysis(source, output_directory=output_directory)
    if source.suffix.lower() != ".json":
        raise ValueError("Rental ingestion requires a canonical JSON extraction or mapped-table manifest.")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Rental extraction must be an object.")
    transformations = []
    if payload.get("schema_version") == EXTRACTION_SCHEMA:
        payload, transformations = _expand_extraction(payload, source.parent, output_directory=output_directory)
    document_lineage = None
    if payload.get("schema_version") == "againward-rental-document-case-v1":
        from .document_adapter import load_document_case
        case, document_lineage = load_document_case(payload, source.parent)
    else:
        case = RentalCase.from_dict(payload)
    inventory = []
    for doc in case.documents:
        path = _local_source(source.parent, doc.path)
        assert_source_approved_for_analysis(path, output_directory=output_directory)
        if fingerprint(path) != doc.sha256:
            raise ValueError("Source document hash does not match the semantic extraction: " + doc.document_id)
        inventory.append({**asdict(doc), "bytes": path.stat().st_size, "classification_basis": "EXPLICIT_SEMANTIC_EXTRACTION"})
    owner = case_root_for_path(source)
    privacy_path = privacy_manifest_path(owner) if owner is not None else None
    result = {"schema_version": "againward-rental-inventory-v1", "documents": inventory,
                  "privacy_manifest_sha256": fingerprint(privacy_path) if privacy_path and privacy_path.is_file() else None,
                  "extraction": {"path": str(source.resolve()), "sha256": fingerprint(source)},
                  "transformations": transformations, "semantic_extraction_required": True,
                  "no_silent_corrections": True, "decision": None}
    if document_lineage is not None:
        result["document_lineage"] = document_lineage
    return case, result


@deterministic_decimal
def build_evidence_dataset(case: RentalCase, *, document_lineage=None) -> EvidenceDataset:
    rows, row_refs = [], {}
    numeric = {"net_amount": "amount_minor"}
    for table in ("parties", "items", "periods", "terms", "events", "actual_charges", "credits"):
        for record in getattr(case, table):
            ordinal = len(rows) + 1
            body = asdict(record)
            body.pop("evidence_refs")
            if table == "credits":
                if body["allocation_state"] == "CONFIRMED_ALLOCATION":
                    body.pop("allocation_state")
                if body["allocated_amount"] is None:
                    body.pop("allocated_amount")
            row = {"source_row": ordinal, "record_type": table, "record_id": getattr(record, _ID_FIELDS[table])}
            for key, value in body.items():
                if value is not None:
                    row[key] = str(value).lower() if type(value) is bool else str(value)
                    if key in numeric:
                        row[numeric[key]] = int(decimal_value(value) * 100)
            rows.append(row)
            row_refs[str(ordinal)] = [{"source_id": ref.document_id, "location": ref.location,
                                       **({"field": ref.field} if ref.field else {})} for ref in record.evidence_refs]
    if document_lineage is not None:
        from .document_evidence import append_document_evidence
        append_document_evidence(case, document_lineage, rows, row_refs)
    keys = sorted({key for row in rows for key in row})
    catalog = [{"key": key, "data_type": "integer" if key in {"source_row", "amount_minor"} else "string",
                "unit": "currency_minor_unit" if key == "amount_minor" else None} for key in keys]
    sources = [{"source_id": doc.document_id, "sha256": doc.sha256, "path": doc.path, "role": doc.role}
               for doc in case.documents]
    identity = stable_hash(case.to_dict()) if document_lineage is None else stable_hash(
        {"case": case.to_dict(), "document_lineage": document_lineage})
    return EvidenceDataset.from_records(dataset_id="rental-" + identity[:20], records=rows, fields=catalog,
        provenance={"sources": sources, "rows": row_refs},
        metadata={"domain": "rental", "canonical_schema": SCHEMA, "period_convention": "START_INCLUSIVE_END_EXCLUSIVE",
                  "money_basis": "NET_EXCLUDING_TAX", "money_query_policy": "amount_minor requires same currency; never aggregate mixed currencies",
                  **({"document_lineage_sha256": stable_hash(document_lineage)} if document_lineage is not None else {})})
