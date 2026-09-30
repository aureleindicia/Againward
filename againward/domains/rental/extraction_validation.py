"""Early local checks for Rental model proposals; never repair source meaning."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from typing import Iterable

from againward.documents.contracts import DocumentError
from againward.documents.extraction import DocumentExtraction, contradictory_source_limitations
from againward.documents.readers import ParsedDocument
from againward.evidence.hashing import stable_hash

from .entity_contract import (COMPLETENESS_TRIGGER_FIELDS, ENTITY_KINDS,
    DOCUMENT_ROLES, DOCUMENT_STATUSES, PACKAGE_SOURCE_REQUIRED,
    CREDIT_REFERENCE_FIELDS, MATERIAL_FIELDS, is_non_entity_observation)


# Ownership boundary: source/hash/location/span are runtime-bound; entity_id is
# a runtime occurrence identity once its source-local anchor is established.
# model_entity_hint is retained only for trace/debug. entity_kind is structural
# classification supported by a source observation. document_role is source
# structure; document_status is source-bound but may carry commercial meaning,
# so it is preserved only as the exact reviewed/read value and conflicts remain
# conflicts. Invoice/asset/agreement identifiers, charge type and rate terms
# remain source-supported semantics; Python may bind but never invent them.
SOURCE_STRUCTURAL_FIELDS = frozenset({"document_role", "document_status"})
OCCURRENCE_ANCHOR_FIELDS = {
    "INVOICE_LINE": ("invoice_id", "invoice_line_id"),
    "CREDIT": ("credit_id",),
    "RENTAL_SCOPE": ("agreement_id", "asset_id"),
    "RETURN": ("agreement_id", "asset_id", "event_type", "date"),
    "RATE_AMENDMENT": ("agreement_id", "asset_id", "effective_from"),
}

# A decimal rate can be emitted under either contract field when two readers
# describe the same cited rate term. This is only an occurrence-assignment
# equivalence; it does not rewrite the observation or derive a new rate.
_RATE_OBSERVATION_EQUIVALENTS = frozenset({"rate", "unit_rate"})


def _proof_identity(candidate, source_sha256: str) -> tuple[object, ...] | None:
    """A locatable exact native proof identity; page-only visual cites cannot assign scope."""
    if (candidate.source_span is None or candidate.unit_sha256 is None
            or not candidate.source_id or not source_sha256):
        return None
    return (candidate.source_id, source_sha256, candidate.location,
            candidate.unit_sha256, tuple(candidate.source_span))


def _same_observed_value(left, right) -> bool:
    if left.semantic_type in _RATE_OBSERVATION_EQUIVALENTS and right.semantic_type in _RATE_OBSERVATION_EQUIVALENTS:
        try:
            left_value = Decimal(str(left.value))
            right_value = Decimal(str(right.value))
        except (InvalidOperation, ValueError):
            return left.value == right.value
        return left_value.is_finite() and right_value.is_finite() and left_value == right_value
    return left.semantic_type == right.semantic_type and left.value == right.value


def _group_values(candidates) -> dict[str, set[object]]:
    fields: dict[str, set[object]] = defaultdict(set)
    for candidate in candidates:
        fields[candidate.semantic_type].add(candidate.value)
    return fields


def _identity_fields(extraction: DocumentExtraction, candidates) -> dict[str, set[object]]:
    fields = _group_values(candidates)
    # A source with exactly one printed invoice ID can bind a split row fragment
    # that omitted the repeated envelope field. This is identity context only;
    # no invoice_id candidate is created or moved by this helper.
    invoice_ids = {candidate.value for candidate in extraction.candidates
                   if candidate.semantic_type == "invoice_id" and candidate.value is not None}
    if (len(invoice_ids) == 1 and len(fields.get("invoice_line_id", set())) == 1
            and not fields.get("invoice_id")):
        fields["invoice_id"] = invoice_ids
    return fields


def _occurrence_anchor(source_id: str, fields: dict[str, set[object]],
                       kind: str | None) -> tuple[str, ...] | None:
    """Return only explicit source-local identities, never model group labels."""
    kinds = fields.get("entity_kind", set())
    if kind is None and len(kinds) == 1:
        value = next(iter(kinds))
        kind = value if isinstance(value, str) else None
    if kind is not None:
        required = OCCURRENCE_ANCHOR_FIELDS.get(kind)
        if required is not None and all(len(fields.get(field, set())) == 1
                                        for field in required):
            return (source_id, kind, *(str(next(iter(fields[field]))) for field in required))
        return None
    # An invoice line can be aligned across readers by its printed line ID.
    # This is only a provisional match key: it never supplies entity_kind.
    if len(fields.get("invoice_line_id", set())) == 1:
        invoice_ids = fields.get("invoice_id", set())
        invoice_id = next(iter(invoice_ids)) if len(invoice_ids) == 1 else ""
        return (source_id, "INVOICE_LINE", str(invoice_id),
                str(next(iter(fields["invoice_line_id"]))))
    # Credit IDs identify the occurrence; invoice/asset values on a credit are
    # references and deliberately do not participate in its identity.
    if len(fields.get("credit_id", set())) == 1:
        return (source_id, "CREDIT", str(next(iter(fields["credit_id"]))))
    return None


def occurrence_kind_overrides(extraction: DocumentExtraction,
                              supporting: Iterable[DocumentExtraction] = ()) -> dict[str, str]:
    """Resolve only missing group kinds supported by an exact peer anchor."""
    peers = tuple(item for item in supporting
                  if item.source_id == extraction.source_id
                  and item.source_sha256 == extraction.source_sha256)
    groups_by_extraction: list[tuple[DocumentExtraction, dict[str, list]]] = []
    for item in (extraction, *peers):
        grouped: dict[str, list] = defaultdict(list)
        for candidate in item.candidates:
            grouped[candidate.entity_id].append(candidate)
        groups_by_extraction.append((item, grouped))
    anchored_kinds: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for item, groups in groups_by_extraction:
        for rows in groups.values():
            fields = _identity_fields(item, rows)
            kinds = fields.get("entity_kind", set())
            if len(kinds) != 1:
                continue
            kind = next(iter(kinds))
            if isinstance(kind, str):
                anchor = _occurrence_anchor(item.source_id, fields, kind)
                if anchor is not None:
                    anchored_kinds[anchor].add(kind)
    overrides: dict[str, str] = {}
    own_groups = groups_by_extraction[0][1]
    for entity_id, rows in own_groups.items():
        fields = _identity_fields(extraction, rows)
        if fields.get("entity_kind"):
            continue
        anchor = _occurrence_anchor(extraction.source_id, fields, None)
        kinds = anchored_kinds.get(anchor, set()) if anchor is not None else set()
        if len(kinds) == 1:
            overrides[entity_id] = next(iter(kinds))
    return overrides


def reconstruct_runtime_structure(extraction: DocumentExtraction,
                                  supporting: Iterable[DocumentExtraction] = ()) -> DocumentExtraction:
    """Rebuild source/occurrence structure from current, same-source evidence.

    Structural metadata is copied only from exact-hash sibling reads and only
    when the selected extraction lacks it and the sibling evidence is unique.
    Candidate values, citations, spans, hashes and review flags are preserved.
    Model group labels are never identity evidence; explicit source-local anchors
    determine the runtime occurrence ID. Missing or conflicting anchors remain
    untouched for the ordinary fail-closed validator.
    """
    peers = tuple(item for item in supporting
                  if item.source_id == extraction.source_id
                  and item.source_sha256 == extraction.source_sha256)
    grouped: dict[str, list] = defaultdict(list)
    for candidate in extraction.candidates:
        grouped[candidate.entity_id].append(candidate)
    peer_groups = []
    for peer in (extraction, *peers):
        by_entity: dict[str, list] = defaultdict(list)
        for candidate in peer.candidates:
            by_entity[candidate.entity_id].append(candidate)
        peer_groups.extend((peer, _identity_fields(peer, rows), rows) for rows in by_entity.values())

    # Map unambiguous sibling occurrence anchors to source-supported kinds.
    peer_kinds: dict[tuple[str, ...], set[str]] = defaultdict(set)
    peer_kind_candidates: dict[tuple[str, ...], list] = defaultdict(list)
    for _, fields, rows in peer_groups:
        kinds = fields.get("entity_kind", set())
        if len(kinds) != 1:
            continue
        kind = next(iter(kinds))
        if not isinstance(kind, str):
            continue
        anchor = _occurrence_anchor(extraction.source_id, fields, kind)
        if anchor is not None:
            peer_kinds[anchor].add(kind)
            peer_kind_candidates[anchor].extend(
                candidate for candidate in rows if candidate.semantic_type == "entity_kind")

    resolved_kind_by_group: dict[str, str] = {}
    anchor_by_group: dict[str, tuple[str, ...]] = {}
    for entity_id, rows in grouped.items():
        fields = _identity_fields(extraction, rows)
        kinds = fields.get("entity_kind", set())
        if len(kinds) > 1:
            # Leave it visible to the established contradiction validator.
            continue
        kind = next(iter(kinds)) if kinds else None
        anchor = _occurrence_anchor(extraction.source_id, fields,
                                    kind if isinstance(kind, str) else None)
        if kind is None:
            provisional = anchor or _occurrence_anchor(extraction.source_id, fields, None)
            if provisional is not None and len(peer_kinds.get(provisional, set())) == 1:
                kind = next(iter(peer_kinds[provisional]))
                anchor = provisional
                resolved_kind_by_group[entity_id] = kind
        if anchor is not None:
            anchor_by_group[entity_id] = anchor
            if isinstance(kind, str):
                resolved_kind_by_group[entity_id] = kind

    # Conflicting explicit kinds for one selected occurrence are not resolved
    # by source order or sibling preference.
    kinds_by_anchor: dict[tuple[str, ...], set[str]] = defaultdict(set)
    for entity_id, anchor in anchor_by_group.items():
        kind = resolved_kind_by_group.get(entity_id)
        if kind is not None:
            kinds_by_anchor[anchor].add(kind)
    conflicting = [anchor for anchor, kinds in kinds_by_anchor.items() if len(kinds) > 1]
    if conflicting:
        raise DocumentError("EXTRACTION_CONTRADICTION",
            "Structural entity kinds conflict for one source-anchored occurrence",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.candidates[].entity_kind",
                        "validation_code": "STRUCTURAL_METADATA_CONFLICT",
                        "source_id": extraction.source_id,
                        "conflicting_field_count": len(conflicting)})

    runtime_ids = {anchor: "runtime-entity-" + stable_hash({
        "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
        "anchor": anchor})[:24] for anchor in kinds_by_anchor}

    # A model can split one exact native observation into a singleton group
    # while placing an equivalent observation with the occurrence. Reattach
    # only when its current source/hash/location/span exactly matches a
    # compatible typed occurrence and that proof identifies one anchor. This
    # deliberately does not use page, value, proximity, or model labels alone.
    atom_assignments: dict[str, tuple[str, ...]] = {}
    for entity_id, rows in grouped.items():
        if len(rows) != 1 or entity_id in anchor_by_group:
            continue
        candidate = rows[0]
        proof = _proof_identity(candidate, extraction.source_sha256)
        if proof is None:
            continue
        matches: set[tuple[str, ...]] = set()
        for target_id, target_rows in grouped.items():
            if target_id == entity_id:
                continue
            anchor = anchor_by_group.get(target_id)
            kind = resolved_kind_by_group.get(target_id)
            if anchor is None or kind is None:
                continue
            for target in target_rows:
                target_proof = _proof_identity(target, extraction.source_sha256)
                if target_proof != proof or not _same_observed_value(candidate, target):
                    continue
                # Equal field names are assignable only when that field is
                # meaningful on this occurrence. The sole declared decimal
                # vocabulary variation is rate/unit_rate.
                equivalent_rate = (candidate.semantic_type in _RATE_OBSERVATION_EQUIVALENTS
                                   and target.semantic_type in _RATE_OBSERVATION_EQUIVALENTS)
                supported_fields = MATERIAL_FIELDS.get(kind, frozenset())
                if (candidate.semantic_type in supported_fields
                        or (equivalent_rate and bool(supported_fields & _RATE_OBSERVATION_EQUIVALENTS))):
                    matches.add(anchor)
                    break
        if len(matches) == 1:
            atom_assignments[entity_id] = next(iter(matches))

    candidates = []
    for candidate in extraction.candidates:
        if candidate.semantic_type in SOURCE_STRUCTURAL_FIELDS:
            runtime_id = "runtime-source-" + stable_hash({
                "source_id": extraction.source_id,
                "source_sha256": extraction.source_sha256})[:24]
            candidates.append(replace(candidate, entity_id=runtime_id))
            continue
        anchor = anchor_by_group.get(candidate.entity_id)
        if anchor is None:
            anchor = atom_assignments.get(candidate.entity_id)
        runtime_id = runtime_ids.get(anchor) if anchor is not None else None
        candidates.append(replace(candidate, entity_id=runtime_id) if runtime_id else candidate)

    present_source_fields = {candidate.semantic_type for candidate in candidates
                             if candidate.semantic_type in SOURCE_STRUCTURAL_FIELDS}
    for field in sorted(SOURCE_STRUCTURAL_FIELDS - present_source_fields):
        values = {candidate.value for peer in peers for candidate in peer.candidates
                  if candidate.semantic_type == field}
        if len(values) != 1:
            continue
        templates = sorted((candidate for peer in peers for candidate in peer.candidates
                            if candidate.semantic_type == field and candidate.value in values),
                           key=lambda item: (item.location, str(item.source_span or ()),
                                             item.raw_observed_value, str(item.value), item.candidate_id))
        if not templates:
            continue
        template = templates[0]
        candidates.append(replace(template,
            candidate_id="runtime-metadata-" + stable_hash({
                "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
                "field": field, "value": next(iter(values)), "location": template.location,
                "unit_sha256": template.unit_sha256, "source_span": template.source_span,
                "raw_observed_value": template.raw_observed_value})[:24],
            entity_id="runtime-source-" + stable_hash({
                "source_id": extraction.source_id,
                "source_sha256": extraction.source_sha256})[:24]))

    # If a selected occurrence lacks its kind, carry the unique exact-source
    # sibling observation only when its printed anchor identifies that one
    # occurrence. No kind is inferred from an amount, filename or row label.
    present_kind_anchors = {
        anchor_by_group[entity_id] for entity_id, rows in grouped.items()
        if anchor_by_group.get(entity_id) is not None
        and len(_group_values(rows).get("entity_kind", set())) == 1
    }
    for entity_id, kind in resolved_kind_by_group.items():
        anchor = anchor_by_group.get(entity_id)
        if anchor is None or anchor not in runtime_ids or anchor in present_kind_anchors:
            continue
        options = peer_kind_candidates.get(anchor, [])
        peer_values = peer_kinds.get(anchor, set())
        if peer_values != {kind} or not options:
            continue
        template = sorted(options, key=lambda item: (item.location, str(item.source_span or ()),
                                                     item.raw_observed_value, str(item.value),
                                                     item.candidate_id))[0]
        candidates.append(replace(template,
            candidate_id="runtime-kind-" + stable_hash({
                "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
                "anchor": anchor, "kind": kind, "location": template.location,
                "unit_sha256": template.unit_sha256, "source_span": template.source_span,
                "raw_observed_value": template.raw_observed_value})[:24],
            entity_id=runtime_ids[anchor]))
        present_kind_anchors.add(anchor)

    if tuple(candidates) == extraction.candidates:
        return extraction
    return replace(extraction, candidates=tuple(candidates))


def normalize_source_supported_rate_rows(extraction: DocumentExtraction,
                                        parsed: ParsedDocument) -> DocumentExtraction:
    """Bind explicit supporting rate-card rows without granting rate authority.

    A source-level RATE_CARD / SUPPORTING_DOCUMENT reading can describe
    separately priced native rows while the model leaves their local kinds
    blank. When each row is exactly cited, line-bounded, and uniquely anchored
    by asset and serial, the runtime can preserve it as a supporting record.
    This is structural only: the rates never become RentalCase terms, and all
    generated kind observations remain subject to ordinary fact review.
    """
    from againward.evidence.hashing import stable_hash

    if parsed.source_id != extraction.source_id:
        return extraction
    candidates = list(extraction.candidates)
    roles = {candidate.value for candidate in candidates
             if candidate.semantic_type == "document_role"}
    statuses = {candidate.value for candidate in candidates
                if candidate.semantic_type == "document_status"}
    if roles != {"RATE_CARD"} or len(statuses) > 1:
        return extraction
    kinds_in_source = {candidate.value for candidate in candidates
                       if candidate.semantic_type == "entity_kind"}
    if kinds_in_source != {"SUPPORTING_DOCUMENT"}:
        return extraction
    source_key = "runtime-source-" + stable_hash({
        "source_id": extraction.source_id, "source_sha256": extraction.source_sha256})[:24]
    # Header metadata is source-scoped even if a reader assigned separate
    # local labels. Keep each exact fact and its original citation intact.
    agreement_ids = {candidate.value for candidate in candidates
                     if candidate.semantic_type == "agreement_id"}
    if len(agreement_ids) <= 1:
        candidates = [replace(candidate, entity_id=source_key)
                      if candidate.semantic_type in {"document_role", "document_status", "agreement_id", "date"}
                      else candidate for candidate in candidates]

    groups: dict[str, list] = defaultdict(list)
    for candidate in candidates:
        groups[candidate.entity_id].append(candidate)
    witnesses = [(entity_id, rows) for entity_id, rows in groups.items()
                 if {row.value for row in rows if row.semantic_type == "entity_kind"}
                 == {"SUPPORTING_DOCUMENT"}]
    untyped = [(entity_id, rows) for entity_id, rows in groups.items()
               if not any(row.semantic_type == "entity_kind" for row in rows)
               and any(row.semantic_type in {"rate", "unit_rate"} for row in rows)]
    if len(witnesses) != 1 or not untyped:
        return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
    witness_rows = witnesses[0][1]
    witness_kinds = [row for row in witness_rows if row.semantic_type == "entity_kind"]
    if (len(witness_kinds) != 1 or len(witness_rows) != 1
            or witness_kinds[0].source_span is None
            or "VISUAL_TRANSCRIPTION_UNVERIFIED" in witness_kinds[0].ambiguity_flags):
        return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
    witness = witness_kinds[0]
    native_units = {unit.unit_sha256: unit for unit in parsed.units if unit.route == "NATIVE"}
    row_shapes: list[tuple[str, list, str, str, tuple[int, int], str]] = []
    allowed_row_fields = {"asset_id", "serial_number", "rate", "unit_rate", "currency",
                          "billing_unit", "quantity_basis", "weekends_billable", "charge_type"}
    anchors: set[tuple[str, str]] = set()
    for entity_id, rows in untyped:
        fields: dict[str, set[object]] = defaultdict(set)
        for row in rows:
            fields[row.semantic_type].add(row.value)
        if (not set(fields) <= allowed_row_fields
                or not {"asset_id", "serial_number", "currency", "billing_unit", "quantity_basis"} <= set(fields)
                or not (set(fields) & {"rate", "unit_rate"})
                or {"rate", "unit_rate"} <= set(fields)
                or any(len(values) != 1 for values in fields.values())):
            return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
        asset = next(iter(fields["asset_id"]))
        serial = next(iter(fields["serial_number"]))
        if not isinstance(asset, str) or not isinstance(serial, str) or (asset, serial) in anchors:
            return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
        anchors.add((asset, serial))
        spans = [row.source_span for row in rows]
        units = {row.unit_sha256 for row in rows}
        locations = {row.location for row in rows}
        if (any(span is None for span in spans) or len(units) != 1 or len(locations) != 1
                or next(iter(units)) not in native_units):
            return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
        unit = native_units[next(iter(units))]
        start = min(span[0] for span in spans if span is not None)
        end = max(span[1] for span in spans if span is not None)
        if (start < 0 or end > len(unit.text) or start >= end
                or "\n" in unit.text[start:end] or "\r" in unit.text[start:end]):
            return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction
        row_shapes.append((entity_id, rows, asset, serial, (start, end), unit.text[start:end]))
    if len(anchors) != len(untyped):
        return replace(extraction, candidates=tuple(candidates)) if tuple(candidates) != extraction.candidates else extraction

    # The source's exact supporting-document observation is the evidence for
    # this non-authoritative structural kind. Row citations and all commercial
    # values remain their own source-bound facts.
    for entity_id, rows, asset, serial, span, _line_text in row_shapes:
        runtime_id = "runtime-rate-row-" + stable_hash({
            "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
            "asset_id": asset, "serial_number": serial, "source_span": span})[:24]
        candidates = [replace(row, entity_id=runtime_id) if row.entity_id == entity_id else row
                      for row in candidates]
        derived_id = "runtime-kind-" + stable_hash({
            "source_id": extraction.source_id, "source_sha256": extraction.source_sha256,
            "asset_id": asset, "serial_number": serial, "witness": witness.candidate_id})[:24]
        derived = replace(witness, candidate_id=derived_id, entity_id=runtime_id,
            normalization_notes=(witness.normalization_notes + "; " if witness.normalization_notes else "")
                + "Bound same-source supporting classification to one exact native rate row; no rate authority granted.")
        candidates.append(derived)
    if tuple(candidates) == extraction.candidates:
        return extraction
    return replace(extraction, candidates=tuple(candidates))


def validate_rental_extraction(extraction: DocumentExtraction, *,
                               require_package_facts: bool = False,
                               allow_incomplete: bool = False,
                               provisional: bool = False) -> None:
    """Check entity and source-level metadata before QA orchestration.

    Entity kind describes each candidate group. Document role/status describe
    the whole source and must each have one source-bound, non-conflicting value.
    This check never infers a missing value; it only recognizes document-level
    values already validated against exact source evidence.
    """
    by_entity: dict[str, dict[str, set[object]]] = defaultdict(lambda: defaultdict(set))
    for candidate in extraction.candidates:
        fields = by_entity[candidate.entity_id]
        fields[candidate.semantic_type].add(candidate.value)

    entity_kind_gaps: list[str] = []
    invalid: list[dict[str, str]] = []
    source_values: dict[str, set[object]] = {"document_role": set(), "document_status": set()}
    within_entity_conflicts = 0
    within_entity_conflicting_fields: set[str] = set()
    for entity_id, fields in sorted(by_entity.items()):
        kinds = fields.get("entity_kind", set())
        # A credit may cite several invoice/line/asset targets. These are
        # relationship references, not mutually exclusive values of the
        # credit's own identity. They are preserved separately for downstream
        # relationship handling; all intrinsic fields remain conflict checked.
        reference_fields = CREDIT_REFERENCE_FIELDS if kinds == {"CREDIT"} else frozenset()
        for field, allowed in (
            ("entity_kind", ENTITY_KINDS),
            ("document_role", DOCUMENT_ROLES),
            ("document_status", DOCUMENT_STATUSES),
        ):
            values = fields.get(field, set())
            for value in values:
                if value not in allowed:
                    invalid.append({"entity_id": entity_id, "field": field})
        for field, values in fields.items():
            if len(values) > 1 and field not in reference_fields:
                within_entity_conflicts += 1
                within_entity_conflicting_fields.add(field)
        if not kinds and not is_non_entity_observation(fields):
            entity_kind_gaps.append(entity_id)
        for field in source_values:
            values = fields.get(field, set())
            source_values[field].update(values)

    if invalid and not provisional:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Rental structural enum is invalid", diagnostic={
            "error_category": "SCHEMA_ERROR", "schema_path": "$.candidates[].semantic_type/value",
            "validation_code": "STRUCTURAL_ENUM_INVALID", "source_id": extraction.source_id,
            "invalid_structural_field_count": len(invalid),
        })
    if within_entity_conflicts and not provisional:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Rental structural metadata conflicts within source",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.candidates[]", "validation_code": "STRUCTURAL_METADATA_CONFLICT",
                        "source_id": extraction.source_id,
                        "conflicting_field_count": within_entity_conflicts,
                        "conflicting_semantic_types": sorted(within_entity_conflicting_fields)})

    missing_source_fields = sorted(field for field, values in source_values.items() if not values)
    conflicting_source_fields = sorted(field for field, values in source_values.items() if len(values) > 1)
    if conflicting_source_fields and not provisional:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Rental source role/status is not unique",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.candidates[].semantic_type/value",
                        "validation_code": "SOURCE_DOCUMENT_METADATA_CONFLICT",
                        "source_id": extraction.source_id,
                        "conflicting_field_count": len(conflicting_source_fields),
                        "conflicting_semantic_types": conflicting_source_fields})
    conflicts = contradictory_source_limitations(extraction)
    if conflicts and not provisional:
        raise DocumentError("EXTRACTION_CONTRADICTION", "Proposal limitation conflicts with its own observation",
            diagnostic={"error_category": "SEMANTIC_CONTRADICTION",
                        "schema_path": "$.limitations[]", "validation_code": "OBSERVATION_LIMITATION_CONFLICT",
                        "source_id": extraction.source_id, "conflicting_field_count": len(conflicts),
                        "conflicting_semantic_types": sorted({item["semantic_type"] for item in conflicts})})
    if (entity_kind_gaps or missing_source_fields) and not allow_incomplete:
        missing_fields = set(missing_source_fields) | ({"entity_kind"} if entity_kind_gaps else set())
        raise DocumentError("STRUCTURAL_INCOMPLETE", "Rental entity metadata is incomplete", diagnostic={
            "error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[].entity_id",
            "validation_code": "ENTITY_METADATA_REQUIRED", "source_id": extraction.source_id,
            "structural_gap_count": len(entity_kind_gaps) + len(missing_source_fields),
            "missing_structural_fields": sorted(missing_fields),
        })

    if not require_package_facts:
        return
    missing_material = set().union(*package_source_gaps(extraction).values())
    if missing_material:
        raise DocumentError("STRUCTURAL_INCOMPLETE", "Rental package-required source facts are missing",
            diagnostic={"error_category": "STRUCTURAL_INCOMPLETE", "schema_path": "$.candidates[]",
                        "validation_code": "PACKAGE_SOURCE_FACT_REQUIRED",
                        "source_id": extraction.source_id,
                        "structural_gap_count": len(missing_material),
                        "missing_semantic_fields": sorted(missing_material)})


def package_source_gaps(extraction: DocumentExtraction, *,
                        for_comparison: bool = False) -> dict[str, set[str]]:
    """Source-bound commercial facts absent from a proposal, before promotion."""
    by_entity: dict[str, dict[str, set[object]]] = defaultdict(lambda: defaultdict(set))
    for candidate in extraction.candidates:
        by_entity[candidate.entity_id][candidate.semantic_type].add(candidate.value)
    missing_by_entity: dict[str, set[str]] = {}
    for entity_id, fields in by_entity.items():
        kinds = fields.get("entity_kind", set())
        if len(kinds) != 1:
            continue
        kind = next(iter(kinds))
        if kind not in PACKAGE_SOURCE_REQUIRED:
            continue
        present = {field for field, values in fields.items() if any(value is not None for value in values)}
        if for_comparison and not present & COMPLETENESS_TRIGGER_FIELDS.get(kind, frozenset()):
            continue
        missing = set(PACKAGE_SOURCE_REQUIRED[kind] - present)
        if kind == "RENTAL_SCOPE" and present & {"rate", "billing_unit", "charge_key", "charge_type"}:
            missing.update({"currency"} - present)
        if missing:
            missing_by_entity[entity_id] = missing
    return missing_by_entity


def proposal_issues(extraction: DocumentExtraction) -> dict[str, object]:
    """Content issues route to independent reconciliation, never imply approval."""
    try:
        validate_rental_extraction(extraction)
    except DocumentError as exc:
        return {"reason_code": exc.code, **(exc.diagnostic or {})}
    return {}
