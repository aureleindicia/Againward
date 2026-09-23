# AGAINWARD — read first (2026-09-23)

AGAINWARD is a local-first, evidence-grounded investigation toolkit for Codex
and deterministic Python. The current commercial focus is Rental B2B: contracts,
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
explicit fact/link review → Rental calculations → human review/delivery.
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
`validate`, `promote`; they require approved source state and supplied reviews.
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
  `rnd/real-world-document-intelligence` PR #3 → this branch PR #4, all unmerged
  at this date. Verify live status before further work.
- Generated document-intelligence DEV/ADVERSARIAL routing baseline remains
  0 semantic recall without independent model/analyst proposals. No honest
  claim of broad unseen-document comprehension or first-client readiness yet.
- Before a first real client: accountable visual-review operation and retention
  authority; a real source-to-fact proposal/review pilot with varied vendor
  layouts; calibrated entity/blocking and financial evidence quality;
  resolution of unsupported temporal/credit semantics and review burden.
  Privacy clearance alone does not satisfy these.

Preserve source and derivative hashes, privacy/reviewer versions, complete
lineage, hard STOPs, confidence vs severity, no double counting, and Energy
characterization. Do not copy client data into shared benchmarks, relax a gate
to improve a score, or treat scripted reviews as actual human approval.
