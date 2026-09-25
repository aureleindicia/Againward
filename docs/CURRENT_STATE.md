# AGAINWARD — read first (2026-09-25)

Current first-client decision: **NOT READY — INDEPENDENT QUALITY MEASUREMENT OPEN**.
An earlier v9 eight-source DEV run passed the former rate-card promotion failure
and completed a model-QA-checked evaluation PDF without HUMAN scan transcription.
The latest fresh replay on code checkpoint `1760abb` stopped at native
`FACT_REVIEW` because a rate-sheet date was accepted on an entity missing
required identity/authority fields; it did not produce a current-code PDF. Final
delivery validation remains in progress; see [the live failure
register](FINAL_AUTONOMOUS_FAILURES.md) and [technical validation](FINAL_AUTONOMOUS_TECHNICAL_VALIDATION.md).
Start with the [release audit](FIRST_CLIENT_RELEASE_AUDIT.md),
[readiness plan](FIRST_CLIENT_READINESS_PLAN.md) and
[internal autonomy/quality contract](AUTONOMOUS_SERVICE_QUALITY.md), then the
[operator playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) for the active
`release/first-rental-client-pilot` draft PR #5 stacked on PR #4. The
eight-document source-to-report path has completed in synthetic evaluation mode. Blind HOLDOUT and
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
exact links, calculations and report QA. Both a synthetic native-PDF case and
the eight-source dossier with a signed scan completed this source-to-report
model path under an earlier policy. The current v4 fresh replay stopped before
calculation on a separate native structural gap. Clear scanned facts can use source/QA/pixel-bound `MODEL` receipts;
genuinely ambiguous pixels still require exceptional HUMAN review. Revisions invalidate dependent artifacts, preserve
query budgets and archive prior analysis. The entrypoint does not authorize
delivery or establish first-client readiness.
The general `investigate.py` path still defaults to Energy and Rental expects
canonical extraction JSON; it is **not** a raw multi-PDF automatic extractor.
`manage_investigation.py`, `query_evidence.py` and `analyze.py` keep Energy-era
CLI interfaces. [Repository layout](REPOSITORY_LAYOUT.md) classifies the other
root scripts. Never run an example command on real data before contract/privacy
clearance; benchmarks generate only synthetic files under ignored `scratch/`.

## Current evidence and blockers

- Current branch: `release/first-rental-client-pilot`, draft PR #5. The v9
  eight-source rerun regenerated 8 primary and 8 independent rereads. Both
  passes represented LIFT-5 and LIFT-50 as separate rate-row entities; no
  `UNSUPPORTED_PROMOTION` recurred. Adjudication v4 reopened the exact disputed
  scan pixels, then the visual analyst accepted 18 facts under `MODEL`, not
  `HUMAN`, receipts. The integrated path promoted 168 facts and 2 invoice
  lines, completed deterministic calculation and model PDF QA, and returned
  `EVALUATION_ONLY_QA_PASSED`. PDF SHA256:
  `bccb8d73719329768bdc73c86e98306159bea78ae392d1d447c239e6984e870e`.
  Delivery and HUMAN approval remain false.
- The earlier synthetic privacy benchmark remains 19/19 (11 ordinary, 8
  unsafe; 0 false blocks, 0 unsafe passes), using scripted visual attestations.
  The current live synthetic probes and limitations are in
  [final metrics](FINAL_AUTONOMOUS_METRICS.md). These results do not measure
  semantic report correctness or vision accuracy.
- Three selected cases from a 20-case synthetic ADVERSARIAL corpus were run
  beyond the known eight-source dossier: two reached QA-checked evaluation PDFs
  (one native invoice, one scanned invoice) and matched their precommitted
  EUR 150 financial oracle; one CSV-only billing record stopped for missing
  issued-invoice/charge authority. Coverage is 2/3 in this tiny nonblind subset,
  not a correctness claim. Seventeen cases and independent report adjudication
  remain outstanding.
- Prior clean-code regression at `4b536e4`: 833 tests passed in 318.78 s with no failures or
  skips; Ruff and configured Mypy (16 files) pass. Rental benchmark 15/15, with
  3 TP, 0 FP, 0 FN and 12 TN. These scripted/fixture results do not represent
  independent final-report accuracy.
- Current code checkpoint `ef6e849` passed 833 tests in 347.26 s (0 failed,
  0 skipped), Ruff, configured mypy (16 files), Rental 15/15, privacy 19/19
  with 0 false blocks/unsafe passes, and PR #5 CI 8/8. These remain regression
  evidence, not an independently adjudicated quality rate.
- Current checkpoint `1760abb` passed 835 tests in 306.77 s from a clean
  worktree (0 failed/skipped), Ruff and configured mypy (16 files); PR #5 CI
  passed 8/8 jobs. Rental remained 15/15, privacy 19/19 with 0 false blocks
  and 0 unsafe passes. A multiply revised eight-source workspace exhausted
  its preserved Evidence Plane budget; a separate byte-identical fresh run
  resolved two material disagreements, including the original-pixel scan,
  but stopped at native `FACT_REVIEW` on a structurally incomplete rate-sheet
  date entity. The current report-author v4 repair is unit-tested, not live-E2E
  validated. Treat this as an unresolved core coverage defect, not a client
  clarification or a reason to relax the entity invariant.
- Current technical blockers: a varied blind final challenge, independent
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
