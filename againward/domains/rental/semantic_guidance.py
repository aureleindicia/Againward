"""Rental interpretation vocabulary supplied to a neutral source-unit provider."""

GUIDANCE_VERSION = "rental-semantic-guidance-v1"


def guidance() -> str:
    return """Rental B2B source interpretation, not authority or arithmetic.
Classify each relevant document and material local entity. Use entity_kind values
RENTAL_SCOPE, INVOICE_LINE, RETURN, RATE_AMENDMENT, CREDIT or IRRELEVANT. Use
separate entity IDs for separate invoice lines, rental scopes or returns; IDs
are local to this source and never establish a cross-document relationship.
For each source include source-backed document_role and document_status for
each material entity. Do not infer ACCEPTED from mere existence of a quote.

Allowed analytical semantic_type fields: entity_kind, document_role,
document_status, agreement_id, supplier_id, client_id, item_id, description,
asset_id, serial_number, category, site_id, cost_center_id, start, end,
quantity, rate, charge_key, charge_type, currency, billing_unit,
weekends_billable, minimum_days, partial_period_policy, stop_event,
stop_day_billable, discount_fraction, percentage_of, tier_min_days,
tier_max_days, effective_from, terms_unchanged, invoice_id,
invoice_line_id, net_amount, unit_rate, billed_units, event_type, date,
verification, extended_end, credit_id, status, allocated_amount.
Do not output contact names, email addresses, phone numbers or signatures as
analytical facts. Commercial prices and contractual IDs are relevant.

Distinguish invoice date from rental start, return, collection, off-hire request
and accepted rate-effective date. A quoted amount may be net or gross; do not
call it net_amount unless explicitly net/excluding tax. Do not invent ISO dates
for ambiguous dd/mm strings. Normalize a numeric literal only with an exact
explanation, never compute one. DECIMAL values are plain decimal strings; DATE
values are ISO YYYY-MM-DD; BOOLEAN values are true/false; INTEGER values are
JSON integers. The raw_observed_value must be an exact unique substring of a
named native source unit; a visual quote may be transcribed but must be flagged
as unverified and later reviewed by a human. Do not turn a promised credit into
an issued one, assign an unreferenced credit to a line, or decide legal priority
between conflicting clauses. If critical fields are absent, leave them absent
and add a limitation; do not guess. The operator will review every proposal."""
