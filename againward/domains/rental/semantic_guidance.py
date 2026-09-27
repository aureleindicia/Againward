"""Rental interpretation vocabulary supplied to a neutral source-unit provider."""

from .entity_contract import observation_instructions

GUIDANCE_VERSION = "rental-semantic-guidance-v17-shared-source-semantics"

STRUCTURE_RETRY_INSTRUCTIONS = (
    "Reinspect this source. Each material entity needs entity_kind, not document_role; source role/status need one supported value. "
    "Mirror-only export rows are SUPPORTING_DOCUMENT even if Type says INVOICE or CREDIT. "
    "Do not infer a role/status from a filename. "
    "Use exact evidence for semantic facts, including charge_type; retain unknowns. "
    "Keep material rows distinct; validation will stop if still invalid. One bounded retry."
)


# Native, visual and adjudication share this semantic contract. Evidence
# transport belongs to providers, not duplicated domain guidance.
def guidance() -> str:
    return """Rental B2B source interpretation; no authority decisions or arithmetic.
Read only this source. Keep independently priced equipment rows, invoice lines
and events separate; each asset's description, rate, unit, and identifiers belong
to its own row. A semantic field has one value per entity; preserve conflicting
observations for reconciliation rather than silently choosing one. Local IDs
are grouping labels; local grouping labels do not establish cross-document links. Keep a
message and its request facts together unless it establishes distinct events.
Do not split metadata for the same message or row into orphan groups.
Document role/status describe the source, not every row. Observe them once if
consistent; preserve conflicting local authority rather than inheriting it.
Do not turn contact details or notices unrelated to commercial evidence into
analytical entities; preserve markings that establish document status.

Classify commercial meaning from exact local wording, not literal enum spelling.
A billed rental description can support charge_type RENTAL without printing the
enum. A mere reference to an agreement does not establish what a charge is for.
An issued invoice/credit is ISSUED, not ACCEPTED: this status records issuance,
not customer agreement with the charges. ACCEPTED describes accepted terms or
an accepted/signed return. A quote is PROPOSED unless acceptance is evidenced.
Use normalization_notes to explain native classifications from their citations.
Never infer authority from a filename or another document.

Mirror-only export rows are SUPPORTING_DOCUMENT, not additional invoices or
credits; PAYMENT_EXPORT / EXTRACTED may describe their source when its content
supports that classification. A rate sheet duplicating agreement prices without
amendment is supporting RATE_CARD evidence, not a second rental scope. Preserve
separately priced rows. A return saying units remain on hire does not create a
new agreement. An off-hire request is OFF_HIRE_REQUESTED / DECLARED, not proof
of physical return; a signed physical-return record may support RETURNED /
DOCUMENTED. Do not turn a promised credit into an issued credit. A credit's
net_amount is its total; allocated_amount describes an explicitly partial
allocation only. Full allocation is represented by a reviewed link later.

Observe distinct invoice dates, service dates and effective dates. net_amount
requires evidence of net/excluding-tax semantics; do not relabel gross totals.
Amounts (net_amount, rate, unit_rate, allocated_amount) are DECIMAL numeric
strings; currency is a separate CURRENCY ISO-code field, never a number.
DATE is ISO YYYY-MM-DD only when unambiguous; BOOLEAN is true/false; INTEGER
is a JSON integer. Do not calculate missing quantities, totals or periods.

Rental stop_event is CONTRACT_END, RETURNED, COLLECTED or OFF_HIRE_REQUESTED
only when stated. A return-based stop with contract-end fallback is one RETURNED
rule, not two conflicting stop_event values. stop_day_billable false needs an
explicit exclusion. partial_period_policy (EXACT, STARTED, PRORATA) concerns
fractional TIME, not partial quantities. Leave unstated conventions absent.

Limitations are atomic claims about this source's unreadable, incomplete or
ambiguous evidence. An invoice need not reproduce agreement rates/clauses.
Do not claim a field is absent while reporting it. Preserve genuine uncertainty
instead of guessing. Technical line IDs and charge keys may be absent; Python
resolves these only after review. A printed "Line 1" may yield invoice_line_id "1"
with exact quote "Line 1"; otherwise leave it absent. Do not invent facts.
""" + "\n" + observation_instructions()


def visual_guidance() -> str:
    """Same semantic contract; only the evidence transport differs."""
    return guidance() + (
        "\nRead attached pixels directly. Use one short entity_hint consistently for "
        "each document/line/asset. Report visible wording and page, not native spans "
        "or hashes. All observations remain unapproved until original-pixel review."
    )
