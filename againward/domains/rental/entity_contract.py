"""One Rental observation contract shared by readers, review and package assembly.

Source observations retain their original citations. The two technical keys
listed below are produced only after cited facts and relationships are reviewed;
they are never promoted as model observations.
"""
from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from typing import Any, Iterable

ENTITY_KINDS = frozenset({"RENTAL_SCOPE", "INVOICE_LINE", "RETURN", "RATE_AMENDMENT",
                          "CREDIT", "SUPPORTING_DOCUMENT", "IRRELEVANT"})
DOCUMENT_ROLES = frozenset({"RENTAL_AGREEMENT", "RATE_CARD", "QUOTE", "PURCHASE_ORDER",
    "AMENDMENT", "INVOICE", "CREDIT_NOTE", "DELIVERY_NOTE", "RETURN_NOTE",
    "OFF_HIRE_NOTICE", "EMAIL_EVIDENCE", "ASSET_LIST", "PAYMENT_EXPORT",
    "TEXT_NOTE", "UNKNOWN", "IRRELEVANT"})
DOCUMENT_STATUSES = frozenset({"ACCEPTED", "ISSUED", "PROPOSED", "VOID", "EXTRACTED"})
CHARGE_TYPES = frozenset({"RENTAL", "TRANSPORT", "DELIVERY", "COLLECTION", "FUEL",
    "REFUELING", "DAMAGE_WAIVER", "ENVIRONMENTAL_FEE", "CONSUMABLE",
    "CLEANING", "SURCHARGE", "OTHER"})
BILLING_UNITS = frozenset({"DAY", "WEEK", "MONTH", "FIXED", "PERCENT"})

# Every value here is eligible for source-bound observation. Technical keys are
# retained because printed line IDs and explicitly named charge keys are facts.
ANALYTICAL_FIELDS = frozenset({
    "entity_kind", "document_role", "document_status", "agreement_id", "supplier_id",
    "client_id", "item_id", "description", "asset_id", "serial_number", "category",
    "site_id", "cost_center_id", "start", "end", "quantity", "rate", "charge_key",
    "charge_type", "currency", "billing_unit", "weekends_billable", "minimum_days",
    "partial_period_policy", "stop_event", "stop_day_billable", "discount_fraction",
    "percentage_of", "tier_min_days", "tier_max_days", "effective_from", "terms_unchanged",
    "invoice_id", "invoice_line_id", "net_amount", "unit_rate", "billed_units",
    "event_type", "date", "verification", "extended_end", "credit_id", "status",
    "allocated_amount",
})

FIELD_SCOPE = {"entity_kind": "ENTITY", "document_role": "SOURCE",
               "document_status": "SOURCE", "invoice_line_id": "LINE_OR_TECHNICAL",
               "charge_key": "CHARGE_SCOPE_OR_TECHNICAL"}
TECHNICAL_DERIVATIONS = frozenset({"invoice_line_id", "charge_key"})
DOCUMENT_ENVELOPE_FIELDS = frozenset({"document_role", "document_status", "invoice_id", "supplier_id"})

# These facts must be observed from this source if the entity is to enter the
# financial package. The technical keys above are resolved after fact review.
PACKAGE_SOURCE_REQUIRED = {
    "RENTAL_SCOPE": frozenset({"agreement_id", "supplier_id", "client_id", "start", "end",
                               "quantity", "description"}),
    "INVOICE_LINE": frozenset({"invoice_id", "charge_type", "currency", "net_amount"}),
    "RETURN": frozenset({"event_type", "date", "quantity", "verification"}),
    "RATE_AMENDMENT": frozenset({"charge_type", "currency", "rate", "effective_from",
                                 "terms_unchanged"}),
    "CREDIT": frozenset({"credit_id", "currency", "net_amount", "status"}),
    "SUPPORTING_DOCUMENT": frozenset(),
    "IRRELEVANT": frozenset(),
}

# A classification-only source record is still checked at selected-package
# validation. QA reopens an agreed omission only when a financial/event record
# was actually proposed, avoiding false disputes over empty classifications.
COMPLETENESS_TRIGGER_FIELDS = {
    "RENTAL_SCOPE": frozenset({"start", "end", "quantity", "rate", "billing_unit", "charge_type"}),
    "INVOICE_LINE": frozenset({"invoice_id", "net_amount", "charge_type", "currency"}),
    "RETURN": frozenset({"event_type", "date", "quantity", "verification"}),
    "RATE_AMENDMENT": frozenset({"rate", "effective_from"}),
    "CREDIT": frozenset({"credit_id", "net_amount"}),
}

# Material comparison is independent of where source-level metadata happens to
# be attached. Do not include document_role/status in entity bundles.
MATERIAL_FIELDS = {
    "RENTAL_SCOPE": frozenset({"entity_kind", "agreement_id", "supplier_id", "client_id",
        "asset_id", "serial_number", "start", "end", "quantity", "rate", "currency",
        "charge_key", "charge_type", "billing_unit", "weekends_billable", "minimum_days",
        "partial_period_policy", "stop_event", "stop_day_billable", "discount_fraction"}),
    "INVOICE_LINE": frozenset({"entity_kind", "invoice_id", "invoice_line_id", "supplier_id",
        "agreement_id", "asset_id", "serial_number", "currency", "net_amount", "charge_key",
        "charge_type", "start", "end", "quantity", "unit_rate", "billed_units"}),
    "CREDIT": frozenset({"entity_kind", "credit_id", "supplier_id", "currency", "net_amount",
        "status", "invoice_id", "invoice_line_id", "allocated_amount"}),
    "RETURN": frozenset({"entity_kind", "agreement_id", "asset_id", "serial_number",
        "event_type", "date", "quantity", "verification"}),
    "RATE_AMENDMENT": frozenset({"entity_kind", "agreement_id", "supplier_id", "asset_id",
        "serial_number", "rate", "currency", "charge_key", "charge_type",
        "effective_from", "terms_unchanged"}),
    "SUPPORTING_DOCUMENT": frozenset({"entity_kind"}),
    "IRRELEVANT": frozenset({"entity_kind"}),
}


def observation_instructions() -> str:
    """Render the same structural contract for native, visual and retry prompts."""
    required = "; ".join(kind + ": " + ", ".join(sorted(fields))
                         for kind, fields in sorted(PACKAGE_SOURCE_REQUIRED.items()) if fields)
    return (
        "Intermediate readings may be partial. Keep omissions and conflicting readings explicit; "
        "they require reconciliation, not invented facts. Only the selected reviewed proposal must "
        "be complete before calculation. Required source-bound fields by entity kind: " + required + ". "
        "Rental observation contract: entity_kind is required for each distinct material entity; "
        "allowed kinds are " + ", ".join(sorted(ENTITY_KINDS)) + ". "
        "document_role and document_status classify the SOURCE, not every row. "
        "Provide one source-supported, non-conflicting value for each on any representative entity; "
        "do not repeat them merely to satisfy a row. Allowed roles: "
        + ", ".join(sorted(DOCUMENT_ROLES)) + ". Allowed statuses: "
        + ", ".join(sorted(DOCUMENT_STATUSES)) + ". "
        "A mirror-only accounting/export row is SUPPORTING_DOCUMENT regardless of whether its Type cell "
        "says INVOICE or CREDIT; the row type is source data, not entity_kind or document_role. "
        "PAYMENT_EXPORT is a possible SOURCE role only when the workbook content supports it. "
        "For an INVOICE_LINE, observe invoice_id, charge_type, currency and net_amount when the source "
        "supports them. charge_type is a commercial classification and must cite this source. "
        "invoice_line_id and charge_key may be omitted when they are only internal technical keys; "
        "Python can derive them after review from a unique source-local entity or reviewed charge scope. "
        "Never invent a printed line ID, charge type, document authority or status. "
    )


def structural_gaps(accepted: Iterable[tuple[str, str, str]], *,
                    visual_sources: frozenset[str] = frozenset(),
                    offered: Iterable[tuple[str, str, str]] = ()) -> list[dict[str, object]]:
    """Find missing authority without inheriting explicitly rejected evidence."""
    by_entity: dict[tuple[str, str], set[str]] = defaultdict(set)
    offered_entity: dict[tuple[str, str], set[str]] = defaultdict(set)
    by_source: dict[str, set[str]] = defaultdict(set)
    for source_id, entity_id, field in offered:
        offered_entity[(source_id, entity_id)].add(field)
    for source_id, entity_id, field in accepted:
        by_entity[(source_id, entity_id)].add(field)
        by_source[source_id].add(field)
    gaps: list[dict[str, object]] = []
    for (source_id, entity_id), fields in sorted(by_entity.items()):
        missing = ({"entity_kind"} - fields)
        if missing:
            # An untyped semantic fragment cannot borrow another entity's
            # source authority merely because it shares the document.
            missing.update({"document_role", "document_status"} - fields)
        else:
            # A rejected role/status on this entity must stay rejected. Other
            # rows may inherit source metadata only when no competing local
            # candidate was offered for this row.
            missing.update(((offered_entity[(source_id, entity_id)] &
                             {"document_role", "document_status"}) - fields) & by_source[source_id])
        if missing:
            gaps.append({"source_id": source_id, "entity_id": entity_id,
                         "missing": [field for field in ("entity_kind", "document_role", "document_status")
                                     if field in missing]})
    for source_id, fields in sorted(by_source.items()):
        if source_id in visual_sources:
            continue
        missing = sorted({"document_role", "document_status"} - fields)
        if missing:
            gaps.append({"source_id": source_id, "entity_id": None, "missing": missing})
    return gaps


def normalize_single_line_document_groups(raw: dict[str, Any], *, visual: bool) -> tuple[dict[str, Any], int]:
    """Attach a source envelope to its sole invoice line before evidence binding.

    This changes only local grouping, never values, quotes, pages or citations.
    Ambiguous/multi-line groupings retain their original shape and fail closed.
    """
    result = deepcopy(raw)
    key = "observations" if visual else "candidates"
    group_key = "entity_hint" if visual else "entity_id"
    rows = result.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return result, 0
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        group = row.get(group_key)
        if not isinstance(group, str):
            return result, 0
        groups[group].append(row)
    targets = [group for group, members in groups.items()
               if any(row.get("semantic_type") == "entity_kind" and row.get("value") == "INVOICE_LINE"
                      for row in members)]
    if len(targets) != 1:
        return result, 0
    target = targets[0]
    target_members = groups[target]
    target_fields = {row.get("semantic_type"): row.get("value") for row in target_members}
    target_pages = {row.get("page") for row in target_members} if visual else set()
    changed = 0
    for group, members in groups.items():
        if group == target:
            continue
        fields = {row.get("semantic_type") for row in members}
        if not fields or not fields <= DOCUMENT_ENVELOPE_FIELDS:
            continue
        if visual and {row.get("page") for row in members} != target_pages:
            continue
        if fields & target_fields.keys():
            continue
        values = defaultdict(set)
        for row in members:
            values[row.get("semantic_type")].add(str(row.get("value")))
        if any(len(value) != 1 for value in values.values()):
            continue
        for row in members:
            row[group_key] = target
            changed += 1
        target_fields.update({row.get("semantic_type"): row.get("value") for row in members})
    return result, changed


def unique_pixel_entity_for_required_field(semantic: str, location: str,
                                           candidates: list[Any]) -> str | None:
    """Find the sole current-page entity missing a required semantic field.

    This only binds a new *unapproved* pixel observation to an already cited
    entity. It never determines the field value or grants fact authority.
    """
    by_entity: dict[str, dict[str, set[Any]]] = defaultdict(lambda: defaultdict(set))
    for candidate in candidates:
        if candidate.location == location:
            by_entity[candidate.entity_id][candidate.semantic_type].add(candidate.value)
    eligible = []
    for entity_id, fields in by_entity.items():
        kinds = fields.get("entity_kind", set())
        if len(kinds) != 1:
            continue
        kind = next(iter(kinds))
        if semantic in PACKAGE_SOURCE_REQUIRED.get(kind, frozenset()) and semantic not in fields:
            eligible.append(entity_id)
    return eligible[0] if len(eligible) == 1 else None
