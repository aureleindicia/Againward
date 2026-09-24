# AGAINWARD — read first (2026-09-24)

Current first-client decision: **NOT READY — SPECIFIC CRITICAL BLOCKERS**.
Start with the [release audit](FIRST_CLIENT_RELEASE_AUDIT.md),
[readiness plan](FIRST_CLIENT_READINESS_PLAN.md) and
[internal autonomy/quality contract](AUTONOMOUS_SERVICE_QUALITY.md), then the
[operator playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) for the active
`release/first-rental-client-pilot` draft PR #5 stacked on PR #4. The
eight-document source-to-report run, blind HOLDOUT and actual operator
rehearsal remain open. The eight-source DEV intake/extraction and separate
source reread now exist, but they are not an approved report.

AGAINWARD is an asynchronous B2B analysis/advisory service whose internal
production uses Codex and deterministic Python. The current commercial focus
is Rental B2B: contracts,
rates, invoices, returns, credits, correspondence and exports. Energy remains an
actively protected compatibility domain. This is **not** an automatic invoice
recovery service, a complete OCR system or a certified financial decision.

## Active map

| Owner | Responsibility |
|---|---|
| `againward/core/` | Contract/retention and privacy gates; lifecycle, transaction and workspace authorities. Domain risk/preservation policies are injected. |
| `againward/documents/` | Approved source inventory, bounded readers, source-bound proposals, provenance and explicit entity resolution. No automatic semantic truth. |
| `againward/evidence/` | Durable evidence and bounded queries, not Rental-specific meaning. |
| `againward/domains/rental/` | Rental preservation policy, reviewed fact adapter, dated quantity/rate arithmetic, cautious discrepancy reporting. |
| `againward/domains/energy/`, `energy_mvp/` | Energy domain and historical import/CLI compatibility; preserve characterization tests. |
| `benchmarking/`, `tests/` | Synthetic generators, independent scorers, unit/integration/adversarial checks. No real client truth in fixtures. |

Real-client order: contract authority → copy bytes to `incoming/` → Codex's
first substantive privacy review → bounded Python privacy post-check →
hash/version-bound `privacy_manifest.json` approving analysis → approved
`sanitized/` sources → document inventory/readers → source-bound proposals →
independent original-source reread → internal fact/link investigation and
adversarial QA → Rental calculations → finished report → short human final
review/delivery approval.
Uninspectable visual components and high-risk data STOP; neither PDF format nor
ordinary professional contact data alone is a STOP. A visual `HUMAN` JSON role
is an attestation, not authenticated identity. Business confidentiality is
tracked separately and does not erase contract rates or invoice amounts.

## Where to read next

Use [docs/README.md](README.md) as the index. In particular:
[Rental privacy](RENTAL_PRIVACY_ARCHITECTURE.md), [document architecture](REAL_WORLD_DOCUMENT_ARCHITECTURE.md),
[entity resolution](ENTITY_RESOLUTION.md), [Rental](RENTAL.md),
[acceptance status](REAL_WORLD_ACCEPTANCE.md). The latter is *not* a completion
certificate. [Document R&D](DOCUMENT_INTELLIGENCE_RND.md) retains measured
experiments; older Goal/Stage completion audits are historical evidence only.

## Canonical commands and compatibility

```sh
python -m pytest -q
ruff check .
mypy
python investigate.py documents --help
python investigate.py --help
python manage_investigation.py --help
python run_rental_privacy_benchmark.py --output scratch/privacy-run
python run_rental_benchmark.py --output scratch/rental-run
python run_document_benchmark.py --help
```

`againward` (installed project script) and `python investigate.py` share the
package CLI. Its `documents` subcommands are `inventory`, `inspect`,
`extract`, `independent-qa`, `compare-independent-qa`, `adjudicate-qa`,
`analyst-review`, `visual-analyst-review`, `review-template`,
`visual-fact-attest`, `validate`, `promote`, `link-review-template` and
`package-rental`; they require approved source state and supplied reviews.
`python investigate.py rental-autonomous PACKAGE --output-dir CASE --model MODEL`
resumes a privacy-approved, reviewed Rental document package through model
finding QA, report writing and original-source PDF QA. Finding review now
materializes bounded, paged Evidence Plane rows (up to 600 source rows) in the
model context rather than retaining only query handles. It is not raw intake,
cannot approve delivery and records a machine-readable job state. Use
`--evaluation-only` for synthetic evaluation packages.
The general `investigate.py` path still defaults to Energy and Rental expects
canonical extraction JSON; it is **not** a raw multi-PDF automatic extractor.
`manage_investigation.py`, `query_evidence.py` and `analyze.py` keep Energy-era
CLI interfaces. [Repository layout](REPOSITORY_LAYOUT.md) classifies the other
root scripts. Never run an example command on real data before contract/privacy
clearance; benchmarks generate only synthetic files under ignored `scratch/`.

## Current evidence and blockers

- Starting document branch `rnd/real-world-document-intelligence` at `94d9d2a`
  rejected all five probed ordinary/sensitive PDF forms as `.pdf`; 722 tests
  passed. Rental privacy branch `rnd/rental-privacy-repo-hardening` adds native
  PDF inspection, strict component-bound scan review and B2B policy, while
  preserving Energy's stricter behavior. Its synthetic privacy benchmark passes
  19/19, with 0 false blocks and 0 unsafe passes in 11 ordinary/8 unsafe cases.
  See [benchmark scope](RENTAL_PRIVACY_BENCHMARKS.md); this does not measure
  human/vision accuracy. Branch PR stack: `refactor/domain-kernel` PR #2 →
  `rnd/real-world-document-intelligence` PR #3 →
  `rnd/rental-privacy-repo-hardening` PR #4 → first-client draft PR #5, all
  unmerged at this checkpoint. Verify live status before further work.
- The routing-only baseline had zero semantic recall. A real Codex CLI model
  submitted DEV/ADVERSARIAL proposals; frozen v1 runs lacked complete material
  entities. The eight-source DEV dossier has 8/8 validated proposals;
  corrected structural preflight scored v7 at 4/6 and v8 at 6/6 material
  entities. Independent v8 reread found 6/8 strict source differences,
  including one material off-hire-email role dispute. An original-source
  adjudicator now resolves that DEV dispute with exact email/agreement
  citations for further fact review. A seven-call native analyst pass accepted
  149 facts after one bounded metadata repair; a two-call visual pass proposed
  10 scan facts after one bounded repair. Real scan attestation and report QA
  remain open for a genuine client. A downstream model-driven DEV job now
  produced a five-page watermarked synthetic PDF after finding and PDF QA;
  it used a scripted, explicitly non-human scan attestation. Five advisory
  bundle differences remain diagnostic. No report accuracy rate,
  human-correction rate or blind performance is measured.
  A prior two-PDF technical probe reached a source-linked ledger without human
  delivery approval. See
  [semantic evaluation](SEMANTIC_EXTRACTION_EVALUATION.md) and
  [E2E validation](FIRST_CLIENT_E2E_VALIDATION.md). Neither proves first-client
  readiness or an independently blind holdout.
- Before a first real client: genuine accountable scan/final review; a complete
  model-driven source-to-report run, independent outcome challenge and measured
  autonomy/coverage/cost; verified business/privacy/provider authority;
  calibrated entity, financial and report quality on varied vendor layouts.
  Privacy clearance alone does not satisfy these.

Preserve source and derivative hashes, privacy/reviewer versions, complete
lineage, hard STOPs, confidence vs severity, no double counting, and Energy
characterization. Do not copy client data into shared benchmarks, relax a gate
to improve a score, or treat scripted reviews as actual human approval.
