"""Small closed contracts at the untrusted document/model boundary."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
from pathlib import PurePosixPath
import re
from typing import Any

from againward.evidence.hashing import stable_hash


class DocumentError(ValueError):
    def __init__(self, code: str, detail: str = "", *,
                 diagnostic: dict[str, Any] | None = None):
        self.code = code
        self.diagnostic = diagnostic
        super().__init__(code + (": " + detail if detail else ""))


# Stable internal categories let receipts and callers distinguish shape errors
# from evidence gaps without changing public workflow error codes.
ERROR_CATEGORIES = frozenset({
    "SCHEMA_ERROR", "STRUCTURAL_INCOMPLETE", "SEMANTIC_CONTRADICTION",
    "SOURCE_EVIDENCE_MISSING", "AMBIGUOUS_SOURCE", "MODEL_INVOCATION_ERROR",
    "REVIEW_REQUIRED",
})

_ERROR_CATEGORY_BY_CODE = {
    "EXTRACTION_SCHEMA_INVALID": "SCHEMA_ERROR",
    "SOURCE_LOCATION_INVALID": "SOURCE_EVIDENCE_MISSING",
    "SOURCE_CHANGED": "SOURCE_EVIDENCE_MISSING",
    "UNSUPPORTED_PROMOTION": "SOURCE_EVIDENCE_MISSING",
    "EXTRACTION_INCOMPLETE": "STRUCTURAL_INCOMPLETE",
    "STRUCTURAL_INCOMPLETE": "STRUCTURAL_INCOMPLETE",
    "EXTRACTION_CONTRADICTION": "SEMANTIC_CONTRADICTION",
    "ENTITY_AMBIGUOUS": "AMBIGUOUS_SOURCE",
    "MODEL_TIMEOUT": "MODEL_INVOCATION_ERROR",
    "MODEL_UNAVAILABLE": "MODEL_INVOCATION_ERROR",
    "MODEL_AUTH_REQUIRED": "MODEL_INVOCATION_ERROR",
    "MODEL_RATE_LIMITED": "MODEL_INVOCATION_ERROR",
    "MODEL_TRANSPORT_FAILURE": "MODEL_INVOCATION_ERROR",
    "MODEL_CONFIGURATION_ERROR": "MODEL_INVOCATION_ERROR",
    "MODEL_CLI_UNAVAILABLE": "MODEL_INVOCATION_ERROR",
    "MODEL_EMPTY_RESPONSE": "MODEL_INVOCATION_ERROR",
    "MODEL_INVOCATION_FAILURE": "MODEL_INVOCATION_ERROR",
    "WAITING_FOR_REQUIRED_INFORMATION": "REVIEW_REQUIRED",
    "REPAIR_REQUIRED": "REVIEW_REQUIRED",
    "WAITING_FOR_VISUAL_REVIEW": "REVIEW_REQUIRED",
    "WAITING_FOR_VISUAL_ATTESTATION": "REVIEW_REQUIRED",
}


def error_category(code: str) -> str:
    """Map stable/legacy workflow codes to a bounded diagnostic category."""
    if code in _ERROR_CATEGORY_BY_CODE:
        return _ERROR_CATEGORY_BY_CODE[code]
    if code.startswith(("MODEL_", "CODEX_")):
        return "MODEL_INVOCATION_ERROR"
    if code.startswith(("SOURCE_", "PRIVACY_")):
        return "SOURCE_EVIDENCE_MISSING"
    if code.startswith(("WAITING_", "REPAIR_", "REVIEW_")):
        return "REVIEW_REQUIRED"
    if code.endswith("AMBIGUOUS"):
        return "AMBIGUOUS_SOURCE"
    return "SCHEMA_ERROR"


def closed(value: Any, keys: set[str], *, optional: set[str] | None = None) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) - keys - (optional or set()) or keys - set(value):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Missing or unknown object fields")
    return value


def text(value: Any, *, maximum: int = 4096, empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > maximum or (not empty and not value.strip()):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Bounded text required")
    return value


def identifier(value: Any) -> str:
    value = text(value, maximum=160)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:/-]*", value):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Invalid identifier")
    return value


def digest(value: Any) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise DocumentError("SOURCE_CHANGED", "Invalid SHA-256")
    return value


def relative_path(value: Any) -> str:
    value = text(value)
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value or not path.parts:
        raise DocumentError("SOURCE_UNSAFE_PATH")
    return value


def exact_decimal(value: Any) -> Decimal:
    if not isinstance(value, str) or not re.fullmatch(r"[+-]?\d+(?:\.\d+)?", value) or len(value) > 40:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Exact bounded decimal string required")
    try:
        result = Decimal(value)
    except InvalidOperation as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Invalid decimal") from exc
    exponent = result.as_tuple().exponent
    if not result.is_finite() or not isinstance(exponent, int) or len(result.as_tuple().digits) > 24 or abs(exponent) > 12:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Decimal outside supported bounds")
    return result


def timestamp(value: Any) -> str:
    value = text(value, maximum=60)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Timestamp required") from exc
    if parsed.tzinfo is None:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Timestamp timezone required")
    return value


def load_json(raw: bytes, *, maximum: int = 4_000_000) -> dict[str, Any]:
    if len(raw) > maximum:
        raise DocumentError("RESOURCE_LIMIT", "JSON bytes exceeded")

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in items:
            if key in result:
                raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Duplicate JSON key")
            result[key] = value
        return result

    def nonfinite(value: str) -> Any:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Nonfinite JSON value")

    try:
        result = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Invalid JSON") from exc
    if not isinstance(result, dict):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "JSON object required")
    return result


@dataclass(frozen=True)
class DocumentLimits:
    maximum_files: int = 200
    maximum_file_bytes: int = 25_000_000
    maximum_batch_bytes: int = 100_000_000
    maximum_pages: int = 200
    maximum_cells: int = 200_000
    maximum_text_characters: int = 2_000_000
    maximum_archive_bytes: int = 100_000_000
    maximum_archive_members: int = 2_000
    maximum_candidates: int = 10_000
    maximum_output_bytes: int = 4_000_000

    def __post_init__(self) -> None:
        if any(type(v) is not int or v < 1 for v in asdict(self).values()):
            raise DocumentError("RESOURCE_LIMIT", "Positive integer limits required")


@dataclass(frozen=True)
class SourceDocument:
    source_id: str
    sha256: str
    byte_size: int
    media_type: str
    blob_path: str
    original_names: tuple[str, ...]

    def __post_init__(self) -> None:
        digest(self.sha256)
        if self.source_id != "src-" + self.sha256:
            raise DocumentError("SOURCE_CHANGED", "Source identity differs from bytes")
        if type(self.byte_size) is not int or self.byte_size < 0:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Invalid byte size")
        text(self.media_type, maximum=120)
        relative_path(self.blob_path)
        if not self.original_names or len(self.original_names) != len(set(self.original_names)):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unique source aliases required")
        for name in self.original_names:
            relative_path(name)


@dataclass(frozen=True)
class SourceBatch:
    documents: tuple[SourceDocument, ...]
    created_at: str
    privacy_manifest_sha256: str | None
    purpose: str
    previous_batch_id: str | None = None
    schema_version: str = "againward-source-batch-v1"

    def __post_init__(self) -> None:
        if self.schema_version != "againward-source-batch-v1":
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown batch version")
        timestamp(self.created_at)
        if self.purpose not in {"INITIAL", "SUPPLEMENTAL", "CORRECTION", "CLIENT_RESPONSE"}:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown batch purpose")
        if self.previous_batch_id is not None:
            identifier(self.previous_batch_id)
        if self.privacy_manifest_sha256 is not None:
            digest(self.privacy_manifest_sha256)
        ids = [d.source_id for d in self.documents]
        if not ids or len(ids) != len(set(ids)):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unique source documents required")

    @property
    def batch_id(self) -> str:
        # Alias names/order/timestamps are receipt metadata, not evidence identity.
        identity = [(d.source_id, d.media_type) for d in sorted(self.documents, key=lambda d: d.source_id)]
        return "batch-" + stable_hash({"documents": identity, "privacy": self.privacy_manifest_sha256,
                                     "previous": self.previous_batch_id, "purpose": self.purpose})

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps({**asdict(self), "batch_id": self.batch_id}))

    @classmethod
    def from_dict(cls, value: Any) -> SourceBatch:
        payload = closed(value, {"documents", "created_at", "privacy_manifest_sha256",
                                 "purpose", "previous_batch_id", "schema_version", "batch_id"})
        if not isinstance(payload["documents"], list):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Document array required")
        documents = []
        for raw in payload["documents"]:
            row = closed(raw, {"source_id", "sha256", "byte_size", "media_type", "blob_path", "original_names"})
            if not isinstance(row["original_names"], list):
                raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Alias array required")
            documents.append(SourceDocument(**{**row, "original_names": tuple(row["original_names"])}))
        batch = cls(tuple(documents), payload["created_at"], payload["privacy_manifest_sha256"],
                    payload["purpose"], payload["previous_batch_id"], payload["schema_version"])
        if payload["batch_id"] != batch.batch_id:
            raise DocumentError("SOURCE_CHANGED", "Batch identity mismatch")
        return batch
