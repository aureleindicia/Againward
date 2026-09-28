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
    "charge_type", "currency", "billing_unit", "quantity_basis", "weekends_billable", "minimum_days",
    "partial_period_policy", "stop_event", "stop_day_billable", "discount_fraction",
    "percentage_of", "tier_min_days", "tier_max_days", "effective_from", "terms_unchanged",
    "invoice_id", "invoice_line_id", "net_amount", "unit_rate", "billed_units",
    "event_type", "date", "verification", "extended_end", "credit_id", "status",
    "allocated_amount",
})

FIELD_SCOPE = {"charge_type": "ENTITY_OR_REVIEWED_RELATION", "billing_unit": "TERM_TIME",
               "quantity_basis": "TERM_QUANTITY", "entity_kind": "ENTITY", "document_role": "SOURCE",
               "document_status": "SOURCE", "invoice_line_id": "LINE_OR_TECHNICAL",
               "charge_key": "CHARGE_SCOPE_OR_TECHNICAL"}
TECHNICAL_DERIVATIONS = frozenset({"invoice_line_id", "charge_key"})
DOCUMENT_ENVELOPE_FIELDS = frozenset({"document_role", "document_status", "invoice_id", "supplier_id"})

# Some source-local observations are not entities. Source role/status live at
# document scope; identifiers in a group by themselves can be references to
# entities described elsewhere (for example, an invoice referenced by a credit
# note). They remain source-bound observations and are retained in lineage, but
# must not be assigned a guessed entity_kind just to satisfy entity validation.
NON_ENTITY_OBSERVATION_FIELDS = frozenset({
    "document_role", "document_status", "invoice_id", "invoice_line_id", "asset_id",
})

# These identifiers describe the target of a credit, rather than attributes of
# the credit instrument itself. Keep them as independently source-bound
# references; a model-local entity label does not turn them into credit fields.
CREDIT_REFERENCE_FIELDS = frozenset({"invoice_id", "invoice_line_id", "asset_id"})


def is_non_entity_observation(fields: Iterable[str]) -> bool:
    """Whether an untyped source-local group contains only metadata/references.

    This does not promote or merge observations. Any commercial datum outside
    the narrow source-metadata/reference vocabulary still requires an explicit
    entity kind.
    """
    values = set(fields)
    if not values or not values <= NON_ENTITY_OBSERVATION_FIELDS:
        return False
    # An asset identifier alone can describe a business-bearing rental entity.
    # Only an explicit invoice target makes this narrow group a reference.
    references = values & CREDIT_REFERENCE_FIELDS
    if references:
        return bool(references & {"invoice_id", "invoice_line_id"})
    return values <= {"document_role", "document_status"}

# Intrinsic source observations required before source selection/fact review.
# Charge meaning can instead be established by an explicit package-scope review;
# canonical financial records still require it. Keys are derived after review.
PACKAGE_SOURCE_REQUIRED = {
    "RENTAL_SCOPE": frozenset({"agreement_id", "supplier_id", "client_id", "start", "end",
                               "quantity", "description"}),
    "INVOICE_LINE": frozenset({"invoice_id", "currency", "net_amount"}),
    "RETURN": frozenset({"event_type", "date", "quantity", "verification"}),
    "RATE_AMENDMENT": frozenset({"charge_type", "currency", "rate", "effective_from",
                                 "terms_unchanged"}),
    "CREDIT": frozenset({"credit_id", "currency", "net_amount", "status"}),
    "SUPPORTING_DOCUMENT": frozenset(),
    "IRRELEVANT": frozenset(),
}

# These remain mandatory on applicable canonical financial records, but may be
# established by reviewed relationships rather than duplicated on every source.
PACKAGE_RELATIONAL_FIELDS = {"INVOICE_LINE": frozenset({"charge_type"}),
                             "RENTAL_SCOPE": frozenset({"charge_type"})}

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
        "charge_key", "charge_type", "billing_unit", "quantity_basis", "weekends_billable", "minimum_days",
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
        "supports them. charge_type applies to terms as well as invoice lines; missing charge classification requires explicit package relation review. "
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
        if "entity_kind" not in fields and is_non_entity_observation(fields):
            # Keep source metadata and relationship references in the offered /
            # accepted fact set, but do not misclassify them as an entity.
            continue
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
        missing_document_fields = sorted({"document_role", "document_status"} - fields)
        if missing_document_fields:
            gaps.append({"source_id": source_id, "entity_id": None, "missing": missing_document_fields})
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
        required = PACKAGE_SOURCE_REQUIRED.get(kind, frozenset()) | PACKAGE_RELATIONAL_FIELDS.get(kind, frozenset())
        if semantic in required and semantic not in fields:
            eligible.append(entity_id)
    return eligible[0] if len(eligible) == 1 else None


def normalize_document_envelopes(raw: dict[str, Any], *, visual: bool) -> dict[str, Any]:
    """Bind unique source-envelope facts to the same-source entities they identify.

    Source IDs and citations never change. A unique invoice number may be
    attached to invoice lines in its own uniquely classified invoice document;
    an issued credit note's own document status may supply its credit status.
    These are still unapproved observations and retain the envelope citation.
    No filename, sibling source, or ambiguous envelope is used.
    """
    result = deepcopy(raw)
    key, group_key = ("observations", "entity_hint") if visual else ("candidates", "entity_id")
    rows = result.get(key)
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return result
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        group = row.get(group_key)
        if not isinstance(group, str):
            return result
        groups[group].append(row)
    envelope_fields = DOCUMENT_ENVELOPE_FIELDS | {"entity_kind", "agreement_id", "client_id"}
    targets = {name: members for name, members in groups.items()
               if any(row.get("semantic_type") not in envelope_fields for row in members)}
    for name, members in groups.items():
        if name in targets or not members:
            continue
        kinds = {row.get("value") for row in members if row.get("semantic_type") == "entity_kind"}
        if kinds and not kinds <= {"RENTAL_SCOPE", "INVOICE_LINE"}:
            continue
        eligible = []
        for target, material in targets.items():
            combined: dict[str, set[str]] = defaultdict(set)
            for row in members + material:
                field = row.get("semantic_type")
                if field in envelope_fields:
                    combined[field].add(str(row.get("value")))
            if any(len(values) != 1 for values in combined.values()):
                continue
            # A document classification can accompany a unique row. An explicit
            # entity kind must agree; role/status alone never confer that kind.
            if visual and {row.get("page") for row in members} != {row.get("page") for row in material}:
                continue
            eligible.append(target)
        if len(eligible) == 1:
            for row in members:
                row[group_key] = eligible[0]

    # `invoice_id` is a source/document identity but is required on each
    # canonical invoice line. When an otherwise structural SUPPORTING_DOCUMENT
    # group carries the one ID for a source explicitly classified as an
    # invoice, rebind that observation to every line in that same source.
    # Keep no duplicate standalone ID fact; its exact quote/page stays intact.
    def string_values(members: list[dict[str, Any]], semantic: str) -> set[str] | None:
        values = [row.get("value") for row in members if row.get("semantic_type") == semantic]
        if any(not isinstance(value, str) or not value for value in values):
            return None
        return {value for value in values if isinstance(value, str)}

    roles = string_values(rows, "document_role")
    invoice_ids = string_values(rows, "invoice_id")
    if not invoice_ids:
        invoice_ids = None
    current_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        current_groups[row[group_key]].append(row)
    invoice_lines = sorted(group for group, members in current_groups.items()
                           if any(row.get("semantic_type") == "entity_kind"
                                  and row.get("value") == "INVOICE_LINE" for row in members))
    if roles == {"INVOICE"} and invoice_ids is not None and len(invoice_ids) == 1 and invoice_lines:
        invoice_id = next(iter(invoice_ids))
        id_rows = [row for row in rows if row.get("semantic_type") == "invoice_id"
                   and row.get("value") == invoice_id]
        compatible = all(
            (line_ids := string_values(current_groups[group], "invoice_id")) is not None
            and line_ids <= {invoice_id}
            for group in invoice_lines)
        if compatible:
            template = sorted(id_rows, key=lambda row: (
                str(row.get("location", row.get("page", ""))),
                str(row.get("raw_observed_value", row.get("visible_text", "")))))[0]
            line_id_groups = set(invoice_lines)
            rows[:] = [row for row in rows if row.get("semantic_type") != "invoice_id"
                       or row.get(group_key) in line_id_groups]
            current_groups = defaultdict(list)
            for row in rows:
                current_groups[row[group_key]].append(row)
            for group in invoice_lines:
                if not any(row.get("semantic_type") == "invoice_id" for row in current_groups[group]):
                    bound = deepcopy(template)
                    bound[group_key] = group
                    if not visual:
                        note = "Bound the unique invoice document ID to its source-local invoice line."
                        prior = bound.get("normalization_notes", "")
                        bound["normalization_notes"] = "; ".join(
                            part for part in (prior.strip() if isinstance(prior, str) else "", note) if part)
                    rows.append(bound)

    # Credit.status is a required commercial fact, but an unambiguous ISSUED
    # state is already stated by the same source's role/status metadata. Project
    # that exact, source-bound observation onto CREDIT entities so it still
    # enters ordinary review. Never infer PROMISED, VOID, or a state from role,
    # filename, or another document.
    source_roles = string_values(rows, "document_role")
    source_statuses = string_values(rows, "document_status")
    status_rows = [row for row in rows if row.get("semantic_type") == "document_status"
                   and row.get("value") == "ISSUED"]
    current_groups = defaultdict(list)
    for row in rows:
        current_groups[row[group_key]].append(row)
    if source_roles == {"CREDIT_NOTE"} and source_statuses == {"ISSUED"} and status_rows:
        template = sorted(status_rows, key=lambda row: (
            str(row.get("location", row.get("page", ""))),
            str(row.get("raw_observed_value", row.get("visible_text", "")))))[0]
        for group, members in current_groups.items():
            entity_kinds = string_values(members, "entity_kind")
            fields = {row.get("semantic_type") for row in members}
            if entity_kinds == {"CREDIT"} and "status" not in fields:
                derived = deepcopy(template)
                derived[group_key] = group
                derived["semantic_type"] = "status"
                if not visual:
                    note = "Derived CREDIT status ISSUED from this source's CREDIT_NOTE / ISSUED metadata."
                    prior = derived.get("normalization_notes", "")
                    derived["normalization_notes"] = "; ".join(
                        part for part in (prior.strip() if isinstance(prior, str) else "", note) if part)
                rows.append(derived)
    return result


# Synonyms only. No accepted/issued, requested/returned, or document-authority inference.
ENUM_ALIASES = {
    "billing_unit": {"DAILY": "DAY", "DAYS": "DAY", "CALENDAR_DAY": "DAY",
                     "WEEKLY": "WEEK", "WEEKS": "WEEK", "MONTHLY": "MONTH", "MONTHS": "MONTH",
                     "FIXED_FEE": "FIXED", "PERCENTAGE": "PERCENT"},
    "entity_kind": {"RENTAL_PERIOD": "RENTAL_SCOPE", "INVOICE_ITEM": "INVOICE_LINE",
                    "SUPPORTING_RECORD": "SUPPORTING_DOCUMENT"},
    "document_role": {"CREDIT_MEMO": "CREDIT_NOTE", "EMAIL": "EMAIL_EVIDENCE",
                      "CORRESPONDENCE": "EMAIL_EVIDENCE", "RATE_SHEET": "RATE_CARD"},
    "charge_type": {"EQUIPMENT_RENTAL": "RENTAL"},
}
ENUM_FIELDS = frozenset({"entity_kind", "document_role", "document_status", "charge_type", "billing_unit", "quantity_basis"})
DECIMAL_FIELDS = frozenset({"net_amount", "rate", "unit_rate", "allocated_amount", "quantity", "billed_units",
                            "discount_fraction"})
DATE_FIELDS = frozenset({"start", "end", "date", "effective_from", "extended_end"})
BOOLEAN_FIELDS = frozenset({"weekends_billable", "stop_day_billable", "terms_unchanged"})


# Complete type ownership for this vocabulary: no financial value is computed.
MODEL_VALUE_TYPES = {field: "TEXT" for field in ANALYTICAL_FIELDS}
MODEL_VALUE_TYPES.update({field: "ENUM" for field in ENUM_FIELDS | {
    "event_type", "status", "partial_period_policy", "stop_event"}})
MODEL_VALUE_TYPES.update({field: "DECIMAL" for field in DECIMAL_FIELDS})
MODEL_VALUE_TYPES.update({field: "DATE" for field in DATE_FIELDS})
MODEL_VALUE_TYPES.update({field: "BOOLEAN" for field in BOOLEAN_FIELDS})
MODEL_VALUE_TYPES.update({field: "INTEGER" for field in {"minimum_days", "tier_min_days", "tier_max_days"}})
MODEL_VALUE_TYPES.update({field: "IDENTIFIER" for field in ANALYTICAL_FIELDS
                         if field.endswith("_id") or field in {"serial_number", "charge_key", "percentage_of"}})
MODEL_VALUE_TYPES["currency"] = "CURRENCY"
