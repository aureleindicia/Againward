"""Rental interpretation vocabulary supplied to a neutral source-unit provider."""

GUIDANCE_VERSION = "rental-semantic-guidance-v3"


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

For a source-supported RENTAL_SCOPE with a fixed daily price, include both
charge_key (a stable source-backed category such as "rental"), charge_type
RENTAL, currency, rate as DECIMAL, billing_unit DAY, and the applicable
stop_event only when the source states it. Valid stop_event values are
CONTRACT_END, RETURNED, COLLECTED and OFF_HIRE_REQUESTED. "Contractual end"
maps to CONTRACT_END, not CONTRACTUAL_END. The same invoice-line charge_key
must be justified by the invoice's own rental-charge description; do not copy
it from a different document. Include charge_type RENTAL and net_amount only
when the invoice explicitly labels the amount net or excluding tax. A
source-local INVOICE_LINE needs invoice_id, invoice_line_id, agreement_id,
equipment anchor, currency and a distinct entity_id per line. Do not omit
charge_key/charge_type merely because "rental" feels obvious; otherwise the
downstream ledger must STOP. Use canonical enum values, never a free-form
phrase: billing_unit DAY/WEEK/MONTH/FIXED/PERCENT; document_status
ACCEPTED/PROPOSED/VOID/EXTRACTED. Explain every normalized enum in
normalization_notes with the exact local wording. Do not assert ACCEPTED
agreement status from a mere quote or proposal. Keep decimal quantities as
exact strings when the source uses decimals; do not derive billed units.
An invoice without the contract's daily rate or stop clause is a normal
separate document, not an extraction limitation. Keep such absent fields
absent; only report a limitation when this source itself is unreadable,
incomplete or internally ambiguous. Do not claim source spans were omitted;
the deterministic validator adds exact native spans or refuses the proposal.

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
