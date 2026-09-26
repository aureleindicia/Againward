"""Early local checks for Rental model proposals; never repair source meaning."""
from __future__ import annotations

from collections import defaultdict

from againward.documents.contracts import DocumentError
from againward.documents.extraction import DocumentExtraction, contradictory_source_limitations

from .models import DOCUMENT_ROLES

_ENTITY_KINDS = frozenset({"RENTAL_SCOPE", "INVOICE_LINE", "RETURN", "RATE_AMENDMENT",
                           "CREDIT", "SUPPORTING_DOCUMENT", "IRRELEVANT"})
_DOCUMENT_STATUSES = frozenset({"ACCEPTED", "ISSUED", "PROPOSED", "VOID", "EXTRACTED"})
_STRUCTURAL_FIELDS = frozenset({"entity_kind", "document_role", "document_status"})


def validate_rental_extraction(extraction: DocumentExtraction) -> None:
    """Reject mechanically incomplete/conflicting proposals before QA orchestration.

    This check does not infer missing values. It raises bounded diagnostics so
    the caller may request one source-bound structural retry, then fail closed.
    """
    by_entity: dict[str, dict[str, object]] = defaultdict(dict)
    for candidate in extraction.candidates:
        fields = by_entity[candidate.entity_id]
        if candidate.semantic_type in _STRUCTURAL_FIELDS:
            fields[candidate.semantic_type] = candidate.value

    gaps = []
    invalid = []
    for entity_id, fields in sorted(by_entity.items()):
        kind = fields.get("entity_kind")
        role = fields.get("document_role")
        status = fields.get("document_status")
        for field, value, allowed in (
            ("entity_kind", kind, _ENTITY_KINDS),
            ("document_role", role, DOCUMENT_ROLES),
            ("document_status", status, _DOCUMENT_STATUSES),
        ):
            if value is not None and value not in allowed:
                invalid.append({"entity_id": entity_id, "field": field})
        missing = sorted(_STRUCTURAL_FIELDS - fields.keys())
        if missing:
            gaps.append({"entity_id": entity_id, "missing": missing})

    if invalid:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Rental structural enum is invalid", diagnostic={
            "error_category": "SCHEMA_ERROR", "schema_path": "$.candidates[].semantic_type/value",
            "validation_code": "STRUCTURAL_ENUM_INVALID", "source_id": extraction.source_id,
            "invalid_structural_field_count": len(invalid),
        })
    if gaps:
        raise DocumentError("STRUCTURAL_INCOMPLETE", "Rental entity metadata is incomplete", diagnostic={
            "error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[].entity_id",
            "validation_code": "ENTITY_METADATA_REQUIRED", "source_id": extraction.source_id,
            "structural_gap_count": len(gaps),
            "missing_structural_fields": sorted({field for gap in gaps for field in gap["missing"]}),
        })

    conflicts = contradictory_source_limitations(extraction)
    if conflicts:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Proposal limitation conflicts with its own observation",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.limitations[]", "validation_code": "OBSERVATION_LIMITATION_CONFLICT",
                        "source_id": extraction.source_id, "conflicting_field_count": len(conflicts),
                        "conflicting_semantic_types": sorted({item["semantic_type"] for item in conflicts})})
