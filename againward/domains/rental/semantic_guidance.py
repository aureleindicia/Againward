"""Rental interpretation vocabulary supplied to a neutral source-unit provider."""

from .entity_contract import observation_instructions

GUIDANCE_VERSION = "rental-semantic-guidance-v15-canonical-entity-contract"

STRUCTURE_RETRY_INSTRUCTIONS = (
    "Reinspect this source. Each material entity needs entity_kind, not document_role; source role/status need one supported value. "
    "Mirror-only export rows are SUPPORTING_DOCUMENT even if Type says INVOICE or CREDIT. "
    "Do not infer a role/status from a filename. "
    "Use exact evidence for semantic facts, including charge_type; retain unknowns. "
    "Keep material rows distinct; validation will stop if still invalid. One bounded retry."
)


def guidance() -> str:
    return """Rental B2B source interpretation, not authority or arithmetic.
Classify each relevant document and material local entity. Use
separate entity IDs for separate invoice lines, rental scopes, returns, and
independently priced equipment rows; IDs are local to this source and never
establish a cross-document relationship. In a multi-row rate card, do not group
all rows under one aggregate rate_card entity: each asset's description, rate,
unit, and identifiers belong to that row's distinct entity. A semantic field
must have only one value per entity; preserve different row values as separate
entities rather than treating them as conflicting alternatives.
Do not put document identity in a metadata-only entity_id beside another ID
for the same message or row. Never borrow a value from another source.
An agreement, invoice, issued credit and signed return have distinct document
roles when the source supports them. Do not infer ACCEPTED from a mere quote.

Do not output contact details as analytical facts. Prices and IDs are relevant.

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
The invoice-line charge_type must be justified by the invoice's own charge
description; do not copy its commercial meaning from another document. A
charge_key is a technical reconciliation key resolved after reviewed source
facts and an exact relationship; emit it only when explicitly supported by
this source. Include charge_type RENTAL and net_amount only
when the invoice explicitly labels the amount net or excluding tax. A
source-local INVOICE_LINE needs invoice_id, agreement_id,
equipment anchor, currency and a distinct entity_id per line. Do not omit
source-supported charge_type merely because "rental" feels obvious; otherwise the
downstream ledger must STOP. Python derives a technical charge_key from a unique
reviewed charge scope when it is not printed. An explicitly issued invoice or
issued credit note has document_status ISSUED, not EXTRACTED or ACCEPTED;
ACCEPTED is for an accepted commercial term or signed/accepted return record.
ISSUED confirms document provenance, not the customer's acceptance of its
charges. A quote is PROPOSED unless explicitly accepted. Explain every
normalized enum in
normalization_notes with the exact local wording. Do not assert ACCEPTED
agreement status from a mere quote or proposal. Keep decimal quantities as
exact strings when the source uses decimals; do not derive billed units.
IDENTIFIER values (especially invoice_line_id) must be safe IDs without spaces.
For "Line 1", use invoice_line_id "1" with exact raw quote "Line 1"; if no
stable line ID is printed, leave it absent.
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
SUPPORTING_DOCUMENT entities with source-supported document_role RATE_CARD or
PAYMENT_EXPORT, document_status and any exact corroborating IDs/amounts. Keep
each separately priced rate row or mirrored export record under its own
entity_id and source-supported entity_kind. The source-level role/status may
be recorded once when it applies consistently to the workbook. These facts
remain auditable but do not create Rental periods, charges or credits. An email that
only requests off-hire and says a separate return note is proof may likewise
be SUPPORTING_DOCUMENT with role EMAIL_EVIDENCE; do not promote its mention of
the return note into a documented physical RETURN. The operator decides
cross-document links and whether corroboration changes a conclusion. Keep an
email message and its request facts under one source-local correspondence
entity unless the source establishes a distinct document or event; each
accepted entity still requires its own source-bound entity_kind.
When one accounting-export workbook contains both invoice and credit rows,
PAYMENT_EXPORT and EXTRACTED describe the workbook's document role/status when
source-supported and may be observed once for the source. The Type cell is a
row label; a mirror-only invoice or credit row remains SUPPORTING_DOCUMENT and
must not become an issued charge or credit. Do not copy row classifications
across entities when the document contains mixed or contradictory source roles.
An accepted rate sheet that explicitly duplicates accepted-agreement prices
and says it makes no amendment is a SUPPORTING_DOCUMENT with document_role
RATE_CARD and document_status ACCEPTED. That classifies evidentiary role only;
the signed agreement remains governing.
An invoice without the contract's daily rate or stop clause is a normal
separate document, not an extraction limitation. Keep such absent fields
absent; only report a limitation when this source itself is unreadable,
incomplete or internally ambiguous. Do not claim source spans were omitted;
the deterministic validator adds exact native spans or refuses the proposal.
Limitations must be atomic, source-local claims. Do not state that a value is
absent or not visible when an observation in the same response reports that
value. Do not combine a true omission (such as a rate not present) with a
contradictory claim about a visible amount; independent adjudication must
explicitly resolve any conflict.

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
reviews only material unresolved exceptions and the finished delivery.
For net_amount, rate, unit_rate and allocated_amount, use value_type DECIMAL
with the numeric amount only. Use value_type CURRENCY only for semantic_type
currency, and give it the source's separate ISO code. Never combine amount and
currency into one value or use CURRENCY for a number.""" + "\n" + observation_instructions()


def visual_guidance() -> str:
    """Light source-local vocabulary for observing pixels before evidence binding."""
    return """Rental document observation vocabulary, not authority or calculation.
Describe material facts that are actually visible. A page may contain an
agreement scope, invoice line, return, rate amendment, credit, or supporting
document. Group facts about the same printed document/line/asset with one
short descriptive entity_hint; it is a local grouping label, not an ID.

Allowed entity_kind: RENTAL_SCOPE, INVOICE_LINE, RETURN, RATE_AMENDMENT,
CREDIT, SUPPORTING_DOCUMENT, IRRELEVANT.
Allowed document_role: RENTAL_AGREEMENT, RATE_CARD, QUOTE, PURCHASE_ORDER,
AMENDMENT, INVOICE, CREDIT_NOTE, DELIVERY_NOTE, RETURN_NOTE, OFF_HIRE_NOTICE,
EMAIL_EVIDENCE, ASSET_LIST, PAYMENT_EXPORT, TEXT_NOTE, UNKNOWN, IRRELEVANT.
Allowed document_status: ACCEPTED, ISSUED, PROPOSED, VOID, EXTRACTED.
Useful semantic fields include agreement_id, supplier_id, item_id, asset_id,
serial_number, description, start, end, effective_from, date, quantity, rate,
currency, billing_unit, invoice_id, invoice_line_id, net_amount, unit_rate,
billed_units, credit_id, event_type, verification, extended_end, status,
charge_key, charge_type, stop_event, stop_day_billable, and terms_unchanged.
Represent net_amount, rate, unit_rate and allocated_amount as DECIMAL numeric
values; represent currency separately as an ISO-code observation with
semantic_type currency and value_type CURRENCY. Never label a numeric amount
as CURRENCY or combine amount and currency into one value.
An issued invoice is document_status ISSUED; ACCEPTED describes accepted terms
or a signed/accepted return, not the customer's acceptance of an invoice.
Use the same entity_hint consistently for entity_kind and the facts of the same
invoice line or return. document_role and document_status classify the source
document and must each have one source-supported value when applicable; they
may be emitted with a representative entity when the same value applies to
the whole source. On a multi-line invoice, keep each line separate and use
INVOICE_LINE for each billed line; do not change the source-level invoice role
to match row type.
For visual pages, each material invoice line is an INVOICE_LINE entity; do not
classify its billed line as SUPPORTING_DOCUMENT merely because it is scanned,
attached, or has a supporting heading. Keep its entity_kind and line facts
under the same entity_hint; include the source-level INVOICE role and status
when the page establishes them.
Use a separate SUPPORTING_DOCUMENT entity only for a genuinely separate
document-level statement, and give it a source-bound entity_kind. If the pixels do not establish a required field, leave it absent and
preserve the review gap; never fill it from another source or from a default.

Preserve visible wording, uncertainty, and document role. Do not decide whether
a charge is contractually due, link different documents, compute totals, or
infer an absent term. Use a null value when a visible value cannot be read;
mark ambiguity instead of guessing. The runtime will bind source and pixel
identity after your observations.""" + "\n" + observation_instructions()
