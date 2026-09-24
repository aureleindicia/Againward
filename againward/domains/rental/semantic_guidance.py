"""Rental interpretation vocabulary supplied to a neutral source-unit provider."""

GUIDANCE_VERSION = "rental-semantic-guidance-v8"


def guidance() -> str:
    return """Rental B2B source interpretation, not authority or arithmetic.
Classify each relevant document and material local entity. Use entity_kind values
RENTAL_SCOPE, INVOICE_LINE, RETURN, RATE_AMENDMENT, CREDIT,
SUPPORTING_DOCUMENT or IRRELEVANT. Use
separate entity IDs for separate invoice lines, rental scopes or returns; IDs
are local to this source and never establish a cross-document relationship.
For each source include source-backed document_role and document_status for
each material entity. Do not infer ACCEPTED from mere existence of a quote.
document_role is the document type, NOT entity_kind or a free-form label. Use
only RENTAL_AGREEMENT, RATE_CARD, QUOTE, PURCHASE_ORDER, AMENDMENT, INVOICE,
CREDIT_NOTE, DELIVERY_NOTE, RETURN_NOTE, OFF_HIRE_NOTICE, EMAIL_EVIDENCE,
ASSET_LIST, PAYMENT_EXPORT, TEXT_NOTE, UNKNOWN or IRRELEVANT. Thus a signed
agreement's RENTAL_SCOPE has document_role RENTAL_AGREEMENT, an invoice line
has INVOICE, an issued credit has CREDIT_NOTE, and a signed return has
RETURN_NOTE. The same source must have one consistent role/status across its
entities. Never use RENTAL_SCOPE, CREDIT or RETURN as document_role.

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
maps to CONTRACT_END, not CONTRACTUAL_END.
For a rule where returned units stop on their documented return date and
unreturned units remain chargeable through the contractual period end, emit
exactly one stop_event RETURNED for that rental scope. The contract end is
the fallback period end, NOT a second stop_event candidate. Include
stop_day_billable false only if the source explicitly excludes the return
date from billing; do not infer it from a different document.
partial_period_policy concerns fractional billing TIME periods only. If the
source explicitly defines how a partial day/week/month is priced, use only
EXACT, STARTED or PRORATA and quote that clause. A statement that partial
QUANTITIES are billed exactly describes unit counts, not fractional time;
do not emit partial_period_policy for it. If no partial-time rule is stated,
leave partial_period_policy absent. Never copy source prose into this enum.
The same invoice-line charge_key
must be justified by the invoice's own rental-charge description; do not copy
it from a different document. Include charge_type RENTAL and net_amount only
when the invoice explicitly labels the amount net or excluding tax. A
source-local INVOICE_LINE needs invoice_id, invoice_line_id, agreement_id,
equipment anchor, currency and a distinct entity_id per line. Do not omit
charge_key/charge_type merely because "rental" feels obvious; otherwise the
downstream ledger must STOP. Use canonical enum values, never a free-form
phrase: billing_unit DAY/WEEK/MONTH/FIXED/PERCENT; document_status
ACCEPTED/ISSUED/PROPOSED/VOID/EXTRACTED. An explicitly issued invoice or
issued credit note has document_status ISSUED, not EXTRACTED or ACCEPTED;
ACCEPTED is for an accepted commercial term or signed/accepted return record.
ISSUED confirms document provenance, not the customer's acceptance of its
charges. A quote is PROPOSED unless explicitly accepted. Explain every
normalized enum in
normalization_notes with the exact local wording. Do not assert ACCEPTED
agreement status from a mere quote or proposal. Keep decimal quantities as
exact strings when the source uses decimals; do not derive billed units.
IDENTIFIER values (especially invoice_line_id) must be safe IDs without spaces.
For "Line 1", use invoice_line_id "1" with raw quote "Line 1" and an explicit
normalization note; never use "Line 1" as an IDENTIFIER value. If no stable
line ID is printed, leave it absent rather than inventing one.
For a CREDIT, distinguish net_amount (the total issued credit) from an
allocation. Use status ISSUED only if issued, or PROMISED if merely promised.
Include credit_id, supplier_id, currency, net_amount and source-supported
invoice/line reference when printed. Only emit allocated_amount for an
explicitly PARTIAL allocation smaller than net_amount; a full allocation is
represented by the invoice/line link, not a duplicate amount field. Never
turn a mirrored export row into a second issued credit or invoice charge.
For a RETURN, include event_type RETURNED, date, quantity and verification
DOCUMENTED only when this source is a signed/accepted physical-return record.
An email requesting off-hire is OFF_HIRE_REQUESTED with verification DECLARED;
its mention of a different return record is not proof of physical return.
Use asset_id or serial_number only when supported by this source. A return
note saying one unit remains on hire does not create a new RENTAL_SCOPE;
only an accepted agreement or accepted amendment defines a rental scope.
Likewise, a rate card explicitly saying it duplicates an agreement does not
create a second independent hire, and an accounting export marked mirror-only
does not create a new invoice or credit. Represent these as source-local
SUPPORTING_DOCUMENT entities with document_role RATE_CARD or PAYMENT_EXPORT,
document_status and any exact corroborating IDs/amounts. These facts remain
auditable but do not create Rental periods, charges or credits. An email that
only requests off-hire and says a separate return note is proof may likewise
be SUPPORTING_DOCUMENT with role EMAIL_EVIDENCE; do not promote its mention of
the return note into a documented physical RETURN. The operator decides
cross-document links and whether corroboration changes a conclusion.
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
as unverified and later checked against original pixels by a human. Do not turn
a promised credit into an issued one, assign an unreferenced credit to a line,
or decide legal priority between conflicting clauses. If critical fields are
absent, leave them absent and add a limitation; do not guess. An internal
analyst and independent source reread verify ordinary proposals; the owner
reviews only material unresolved exceptions and the finished delivery."""
