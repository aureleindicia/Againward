# AGAINWARD — read first (2026-09-25)

Current first-client decision: **NOT READY — SPECIFIC CRITICAL BLOCKERS**.
The latest v9 eight-source DEV run passed the former rate-card promotion failure
and stopped safely at an unresolved visual return-source disagreement. Final
delivery validation remains in progress; see [the live failure
register](FINAL_AUTONOMOUS_FAILURES.md) and [technical validation](FINAL_AUTONOMOUS_TECHNICAL_VALIDATION.md).
Start with the [release audit](FIRST_CLIENT_RELEASE_AUDIT.md),
[readiness plan](FIRST_CLIENT_READINESS_PLAN.md) and
[internal autonomy/quality contract](AUTONOMOUS_SERVICE_QUALITY.md), then the
[operator playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) for the active
`release/first-rental-client-pilot` draft PR #5 stacked on PR #4. The
eight-document source-to-report report has not completed; the current dossier
is waiting for genuine inspection of its signed-return scan. Blind HOLDOUT and
measured operator rehearsal also remain open. This DEV dossier is not an
approved client report.

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
`python investigate.py rental-case WORKSPACE --model MODEL --evaluation-only`
is the developing single-job Rental entrypoint. It checks contract authority,
attempts Codex-first raw privacy review, applies the deterministic post-check,
then runs source extraction, independent reread/adjudication, fact review,
exact links, calculations and report QA. A live synthetic native-PDF case has
completed this source-to-report model path; this eight-source run currently
waits at source adjudication for a visual scan. Real visual attestations remain
required where applicable. Revisions invalidate dependent artifacts, preserve
query budgets and archive prior analysis. The entrypoint does not authorize
delivery or establish first-client readiness.
The general `investigate.py` path still defaults to Energy and Rental expects
canonical extraction JSON; it is **not** a raw multi-PDF automatic extractor.
`manage_investigation.py`, `query_evidence.py` and `analyze.py` keep Energy-era
CLI interfaces. [Repository layout](REPOSITORY_LAYOUT.md) classifies the other
root scripts. Never run an example command on real data before contract/privacy
clearance; benchmarks generate only synthetic files under ignored `scratch/`.

## Current evidence and blockers

- Current branch: `release/first-rental-client-pilot`, draft PR #5. The current
  v9 rerun regenerated all 8 primary
  extractions and 8 independent rereads. Both passes represented LIFT-5 and
  LIFT-50 as separate rate-row entities; no `UNSUPPORTED_PROMOTION` recurred.
  One material disagreement remains on the visual-only signed-return scan.
  Adjudication v3 selected `UNRESOLVED` because no native quote can verify that
  source. No genuine human scan attestation exists. The workflow is waiting
  before native fact promotion; no client report was produced from this case.
- The earlier synthetic privacy benchmark remains 19/19 (11 ordinary, 8
  unsafe; 0 false blocks, 0 unsafe passes), using scripted visual attestations.
  The current live synthetic probes and limitations are in
  [final metrics](FINAL_AUTONOMOUS_METRICS.md). These results do not measure
  semantic report correctness or vision accuracy.
- Current code regression: 831 tests passed in 337.50 s with no failures or
  skips; Ruff and configured Mypy (16 files) pass. Rental benchmark 15/15, with
  3 TP, 0 FP, 0 FN and 12 TN. These scripted/fixture results do not represent
  independent final-report accuracy.
- Current technical blockers: genuine visual inspection for the disputed scan;
  then completion and challenge of this dossier through fact review, entity
  links, calculations and report QA. A varied blind final challenge, independent
  outcome adjudication, actual founder correction/review time, cost/coverage
  measurements and owner-controlled legal/provider/business permissions remain
  open. The 99% material-correctness and 95% no-correction figures are targets,
  not measured results.
- Historical v7/v8 experiments and earlier scripted-attestation runs are kept in
  [semantic evaluation](SEMANTIC_EXTRACTION_EVALUATION.md) and
  [E2E validation](FIRST_CLIENT_E2E_VALIDATION.md); they are not current approval
  state. The older Goal/Stage audits remain historical evidence only.

Preserve source and derivative hashes, privacy/reviewer versions, complete
lineage, hard STOPs, confidence vs severity, no double counting, and Energy
characterization. Do not copy client data into shared benchmarks, relax a gate
to improve a score, or treat scripted reviews as actual human approval.
