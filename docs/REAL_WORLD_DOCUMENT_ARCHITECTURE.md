# Real-world document architecture — implementation in progress

Read [DOCUMENT_INTELLIGENCE_RND.md](DOCUMENT_INTELLIGENCE_RND.md) for the verified
baseline and experiment criteria. The current canonical Rental and Energy paths
remain supported. New documentary inputs use versioned contracts upstream of
`RentalCase`; historical cases are not silently migrated.

Active ownership:

- `againward/documents/`: domain-neutral sources, deterministic source units,
  extraction proposals, location validation, resolution records and promotion.
- `againward/domains/rental/`: mapping reviewed documentary facts to Rental
  concepts, pricing, reconciliation and financial evidence boundaries.
- `againward/core/`: existing privacy, lifecycle, requests and durable store.
- `againward/evidence/`: existing neutral snapshots, bounded queries and budgets.
- `benchmarking/`: synthetic file generators and independent scorers.

The source identity is the cryptographic identity of approved bytes, not the
filename. Sanitized bytes are the durable analytical source in real cases; raw
personal bytes still follow the existing deletion policy. A source batch is not
a privacy approval. Every source is checked against the current gate before
reading, and extraction replay revalidates hashes.

Native PDF text is extracted per page; it is not a semantic table parser.
Scanned components require a multimodal proposal and review. PDF coordinates are
not universally reliable: see the [pypdf extraction documentation](https://pypdf.readthedocs.io/en/stable/user/extract-text.html).
Spreadsheet cells retain exact raw representation, formula/merge metadata and
locations. Neither formula caches nor model confidence establish authority.

No parser output alone is a contractual fact. The implementation must retain
source → candidate → reviewed fact → relationship → canonical record lineage,
including unresolved contradictions. Delivery approval remains separate.

## Implemented upstream workflow

`python investigate.py documents inventory SOURCE_DIRECTORY DOCUMENT_ROOT`
checks the existing gate, snapshots immutable approved bytes under `sources/`,
and writes a receipt under `batches/`. In a real workspace DOCUMENT_ROOT belongs
under `processed/`; incoming bytes must first complete the existing Codex privacy
workflow. Receipt identity ignores names/order but retains every alias.

`python investigate.py documents inspect DOCUMENT_ROOT BATCH_RECEIPT` returns
native units: PDF pages, CSV cells, exact XLSX XML values/styles/formulas/merges,
DOCX body paragraphs or EML text parts. Unread components and image pages remain
explicit. Sources are never truncated to satisfy a limit.

Supply a model/analyst proposal using the closed contract in
`documents/extraction.py::proposal_context`, then use:

```sh
python investigate.py documents validate DOCUMENT_ROOT BATCH_RECEIPT PROPOSAL
python investigate.py documents promote DOCUMENT_ROOT BATCH_RECEIPT FACT_REVIEW EXTRACTION...
```

No command calls a provider, changes question budgets or creates delivery approval.
Every proposal carries source/batch identity, reader/extractor/model/prompt version,
status and source-local candidates. A native quote must match exact half-open
character offsets. A visual transcription is only a proposal and requires supplied
human source inspection. Formula caches cannot be promoted as measured values.

Semantic correctness remains a reviewed judgment. A valid quote can still be
misclassified, and a syntactically valid normalization can still misunderstand a
clause. Source-supported numeric literals cannot be rewritten by a model note.
Conflicting values on one source-local field are refused during promotion.

Stored extraction artifacts are versioned, content-hashed and replayed against
current immutable source bytes. Changing a source, reader, extraction or privacy
batch invalidates replay; it does not silently rewrite old results. A supplemental
batch preserves previous approved blobs and receipt while creating a new identity.

## Rental integration

`againward-rental-document-case-v1` is an opt-in source package, next to the
content-addressed `sources/` directory. It contains `batch`, validated
`extractions`, `fact_review`, `rental_relationship_review` and
`credit_relationship_review` (the latter two may be null). The existing Rental
prepare entrypoint detects this schema. `document_adapter.py` owns business
mapping and injects its matching policies; the source layer knows no off-hire or
credit-allocation vocabulary. See `tests/test_rental_document_adapter.py` for a
complete synthetic example; its scripted review is not a real human approval.

Every source must be classified. Material invoice/return/credit occurrences
require a confirmed relationship; a shared model-local label is insufficient.
Rate amendments also require a confirmed link to one rental and a reviewed
effective date. Only an explicit reviewed unchanged-terms clause allows the
adapter to carry older billing conventions into a new dated rate term.
The adapter derives canonical IDs from source-bound entity occurrences and does
not copy missing rates from invoices. Any unextracted component blocks financial
preparation for now, even when some other fields are readable.

`artifact_inventory.json.document_lineage` retains promoted facts, quote/span
support and relationship decisions. The Evidence Plane adds `document_fact` and
`document_relationship` rows. Monetary fact rows deliberately have no
`amount_minor`: aggregating them with ledger records would double count money.
Fresh calculation/review replays the source package and compares the complete
lineage, not just monetary totals. The human evidence pack includes that chain.
Legacy v1 canonical inputs retain their existing dataset representation.
Documented partial physical returns and dated accepted rates now use exact
daily quantity/rate segments when all required conventions are known. See
`againward/domains/rental/temporal.py` and the H4 experiment log. Weekly partial
returns and uncertain extensions remain unknown, with explicit limitations.

## Current limits

The reviewed native-document path is connected to Rental, but the mission's full
real-world capability is not implemented or validated yet.
The real-client privacy gate still refuses binary files it cannot post-check.
Native parsing does not authorize them. Poor scans, signatures and handwritten
text need source review. PDF annotations/forms and non-body DOCX components are
flagged, not silently treated as fully extracted. The PDF process guard accounts
for Android virtual reservations and is not a universal document sandbox.
