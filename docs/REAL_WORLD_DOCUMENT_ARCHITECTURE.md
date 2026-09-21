# Real-world document architecture — implementation in progress

Read [DOCUMENT_INTELLIGENCE_RND.md](DOCUMENT_INTELLIGENCE_RND.md) for the verified
baseline and experiment criteria. The current canonical Rental and Energy paths
remain supported. New documentary inputs use versioned contracts upstream of
`RentalCase`; historical cases are not silently migrated.

Planned active ownership:

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
