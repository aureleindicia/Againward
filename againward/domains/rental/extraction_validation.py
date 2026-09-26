"""Early local checks for Rental model proposals; never repair source meaning."""
from __future__ import annotations

from collections import defaultdict

from againward.documents.contracts import DocumentError
from againward.documents.extraction import DocumentExtraction, contradictory_source_limitations

from .entity_contract import (ENTITY_KINDS, DOCUMENT_ROLES, DOCUMENT_STATUSES,
                              PACKAGE_SOURCE_REQUIRED)
_STRUCTURAL_FIELDS = frozenset({"entity_kind", "document_role", "document_status"})


def validate_rental_extraction(extraction: DocumentExtraction, *,
                               require_package_facts: bool = False) -> None:
    """Check entity and source-level metadata before QA orchestration.

    Entity kind describes each candidate group. Document role/status describe
    the whole source and must each have one source-bound, non-conflicting value.
    This check never infers a missing value; it only recognizes document-level
    values already validated against exact source evidence.
    """
    by_entity: dict[str, dict[str, set[object]]] = defaultdict(lambda: defaultdict(set))
    for candidate in extraction.candidates:
        fields = by_entity[candidate.entity_id]
        if candidate.semantic_type in _STRUCTURAL_FIELDS:
            fields[candidate.semantic_type].add(candidate.value)

    entity_kind_gaps: list[str] = []
    invalid: list[dict[str, str]] = []
    source_values: dict[str, set[object]] = {"document_role": set(), "document_status": set()}
    within_entity_conflicts = 0
    within_entity_conflicting_fields: set[str] = set()
    for entity_id, fields in sorted(by_entity.items()):
        for field, allowed in (
            ("entity_kind", ENTITY_KINDS),
            ("document_role", DOCUMENT_ROLES),
            ("document_status", DOCUMENT_STATUSES),
        ):
            values = fields.get(field, set())
            for value in values:
                if value not in allowed:
                    invalid.append({"entity_id": entity_id, "field": field})
            if len(values) > 1:
                within_entity_conflicts += 1
                within_entity_conflicting_fields.add(field)
        kinds = fields.get("entity_kind", set())
        if not kinds:
            entity_kind_gaps.append(entity_id)
        for field in source_values:
            values = fields.get(field, set())
            source_values[field].update(values)

    if invalid:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Rental structural enum is invalid", diagnostic={
            "error_category": "SCHEMA_ERROR", "schema_path": "$.candidates[].semantic_type/value",
            "validation_code": "STRUCTURAL_ENUM_INVALID", "source_id": extraction.source_id,
            "invalid_structural_field_count": len(invalid),
        })
    if within_entity_conflicts:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Rental structural metadata conflicts within source",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.candidates[]", "validation_code": "STRUCTURAL_METADATA_CONFLICT",
                        "source_id": extraction.source_id,
                        "conflicting_field_count": within_entity_conflicts,
                        "conflicting_semantic_types": sorted(within_entity_conflicting_fields)})

    missing_source_fields = sorted(field for field, values in source_values.items() if not values)
    conflicting_source_fields = sorted(field for field, values in source_values.items() if len(values) > 1)
    if conflicting_source_fields:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Rental source role/status is not unique",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.candidates[].semantic_type/value",
                        "validation_code": "SOURCE_DOCUMENT_METADATA_CONFLICT",
                        "source_id": extraction.source_id,
                        "conflicting_field_count": len(conflicting_source_fields),
                        "conflicting_semantic_types": conflicting_source_fields})
    if entity_kind_gaps or missing_source_fields:
        missing_fields = set(missing_source_fields) | ({"entity_kind"} if entity_kind_gaps else set())
        raise DocumentError("STRUCTURAL_INCOMPLETE", "Rental entity metadata is incomplete", diagnostic={
            "error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[].entity_id",
            "validation_code": "ENTITY_METADATA_REQUIRED", "source_id": extraction.source_id,
            "structural_gap_count": len(entity_kind_gaps) + len(missing_source_fields),
            "missing_structural_fields": sorted(missing_fields),
        })

    conflicts = contradictory_source_limitations(extraction)
    if conflicts:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Proposal limitation conflicts with its own observation",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.limitations[]", "validation_code": "OBSERVATION_LIMITATION_CONFLICT",
                        "source_id": extraction.source_id, "conflicting_field_count": len(conflicts),
                        "conflicting_semantic_types": sorted({item["semantic_type"] for item in conflicts})})

    if not require_package_facts:
        return
    missing_material: set[str] = set()
    for entity_id, fields in by_entity.items():
        kind = next(iter(fields["entity_kind"]))
        present = {candidate.semantic_type for candidate in extraction.candidates
                   if candidate.entity_id == entity_id and candidate.value is not None}
        missing_material.update(PACKAGE_SOURCE_REQUIRED[kind] - present)
        if kind == "RENTAL_SCOPE" and present & {"rate", "billing_unit", "charge_key", "charge_type"}:
            missing_material.update({"charge_type", "currency"} - present)
    if missing_material:
        raise DocumentError("STRUCTURAL_INCOMPLETE", "Rental package-required source facts are missing",
            diagnostic={"error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[]",
                        "validation_code": "PACKAGE_SOURCE_FACT_REQUIRED",
                        "source_id": extraction.source_id,
                        "structural_gap_count": len(missing_material),
                        "missing_semantic_fields": sorted(missing_material)})
