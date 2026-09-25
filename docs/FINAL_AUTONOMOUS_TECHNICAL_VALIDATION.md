# Final autonomous technical validation — current DEV E2E passed

Mission: authorized raw Rental documents → autonomous investigation and QA →
finished source-backed report, with real final delivery authority retained.

This is not a first-client readiness certificate or a blind accuracy result. Current branch:
`release/first-rental-client-pilot`, draft stacked PR
[5](https://github.com/aureleindicia/Againward/pull/5), not merged.

## Verified development evidence

- Eight-source v9 rerun: all 8 primary extractions and all 8 independent
  rereads were regenerated after the guidance hash changed. On the rate sheet,
  both passes now represent LIFT-5 and LIFT-50 as separate row entities, each
  with its own identifier, rate, currency and billing unit. No row was dropped,
  no entity contains conflicting values for a semantic field, and the previous
  `UNSUPPORTED_PROMOTION` failure did not recur.
- Adjudication v4 reopened the exact signed-return pixels and chose the
  `CHALLENGER` proposal with three scan citations bound to `source_sha256`,
  `page:1`, unit and rendered-preview SHA256. Agreement/email/rate evidence was
  contextual, not a substitute for the disputed scan. Native quotes remain
  deterministically checked; visual meaning remains a model judgment. The
  first v4 answers were rejected for invalid citation shape; exact unit-location
  constraints and one bounded repair corrected this without weakening the gate.
- The existing visual analyst then accepted all 18 scan candidates. A separate
  `MODEL` receipt, bound to primary/challenger source QA, adjudication, current
  candidate hashes and pixels, permitted fact promotion; it is not `HUMAN`.
  The canonical single-value-per-entity guard accepted 168 facts and 2 invoice
  lines. The integrated case completed entity/link review, deterministic ledger,
  finding review, PDF generation and original-source/PDF model QA:
  `EVALUATION_ONLY_QA_PASSED`, PDF SHA256
  `bccb8d73719329768bdc73c86e98306159bea78ae392d1d447c239e6984e870e`.
  The PDF identifies a EUR 150 documented LIFT-5 difference after the issued
  EUR 100 credit, and EUR 0 for LIFT-50; it explicitly avoids a recovery claim.
  Human approval and delivery authorization remain false. A replay under that
  earlier code/pixel receipt set produced the same PDF hash.
- Policy-only revisions reused exactly 16 source passes (8 primary, 8
  challenger) and invalidated later judgments. Changed sources, privacy, model,
  semantic guidance or rendered pixels cannot reuse dependent approvals.
- Revision guards passed targeted coverage for source mutation, source/privacy/
  model/policy binding, adjudication-only reuse, preserved Evidence Plane budgets
  and interrupted archive recovery. Row-level rate-card guidance is covered by
  regression tests. Prior clean checkpoint `4b536e4`: **833 passed in 318.78 s,
  0 failed, 0 skipped** from a clean worktree; Ruff passed; configured mypy
  passed on 16 files. Rental benchmark 15/15 (3 TP, 0 FP, 0 FN, 12 TN; 10,000
  invoice lines in 3.36836 s); privacy benchmark 19/19 (0 false blocks,
  0 unsafe passes). Scripted benchmarks do not establish model/report accuracy.
- Native-review v2 and evaluation-metadata code checkpoint `ef6e849` then passed
  **833 tests in 347.26 s, 0 failed/skipped**, on a clean HEAD at run start;
  Ruff and configured mypy (16 files) passed, and PR #5 CI passed 8/8 Python
  3.11–3.14 pytest jobs. On that code, Rental remained 15/15 (3 TP, 0 FP,
  0 FN, 12 TN; 10,000 lines in 2.571854 s) and privacy remained 19/19
  (0 false blocks, 0 unsafe passes). These are scripted regression results.
- Report-author policy v4 added one bounded repair for a deterministic rejection
  of free dates/numbers/identifiers in narrative prose. It does not permit an
  invalid synthesis into the PDF. Code checkpoint `1760abb` passed **835 tests
  in 306.77 s, 0 failed/skipped** from a clean worktree, Ruff, configured mypy
  (16 files), and PR #5 CI 8/8 pytest jobs. Rental benchmark remained 15/15
  (3 TP, 0 FP, 0 FN, 12 TN); privacy remained 19/19 (11 ordinary, 8 unsafe,
  0 false blocks, 0 unsafe passes). The repair is unit-tested, not yet shown
  by a successful live v4 report-author run.
- The historical eight-source workspace was rerun with native-review v2 and
  report policy v4. It advanced through 161 reviewed facts (10 visual `MODEL`
  facts), two invoice lines, calculation input and finding QA, but its
  preserved Evidence Plane budget had only 17,066 context bytes left after
  repeated revisions; the next evidence query was rejected. No budget reset
  or fabricated continuation was applied.
- A fresh synthetic workspace with the same eight source bytes then completed
  eight primary and eight challenger reads. Two material disagreements were
  resolved; the signed-return decision cited the disputed original scan with
  source, unit and preview hashes. It stopped at `FACT_REVIEW`, however: the
  chosen rate-sheet extraction contained an orphan document-date entity and
  the native model review accepted it without required `entity_kind`,
  `document_role` and `document_status`. The row-level LIFT-5/LIFT-50 entities
  remained distinct. No current-code PDF or final report QA was produced in
  this fresh replay. The earlier `4b536e4` PDF is valid DEV evidence for that
  prior policy, not evidence that the current v4 checkpoint passed E2E.
- Fact-review policy v3 checks structural completeness on accepted source-local
  entities and withholds promotion while an accepted entity lacks
  `entity_kind`, `document_role` or `document_status`. A detached date can be
  rejected in the bounded repair; dates on valid rate/document entities remain
  representable. Targeted tests reproduce the accepted orphan, exercise its
  repair, preserve two distinct dated rate rows and fail closed on a partial
  entity.
- A **new** synthetic eight-source workspace on current code used the same eight
  source hashes: 8 primary reads, 8 independent rereads, 0 material source
  disagreements, completed adjudication, 150 accepted native facts, 10
  pixel-bound visual `MODEL` facts and 2 invoice lines. Finding QA passed;
  report-author v4's bounded repair ran live; original-source/PDF model QA
  passed. Final status: `EVALUATION_ONLY_QA_PASSED`; PDF SHA256
  `07e8c9d31c2c2505c053ebe3761c1c83e8da0388139e2d34bb5364a55971ecb7`.
  The deterministic result is LIFT-5 EUR 650 expected, EUR 900 invoiced less
  EUR 100 issued credit, EUR 150 documentary difference; LIFT-50 EUR 270
  expected/invoiced, EUR 0 difference. No `HUMAN` attestation or delivery
  approval was created. This known DEV oracle and same-model QA do not measure
  independent material correctness.
- Post-fix committed-code regression: **838 passed in 310.49 s, 0 failed**;
  Ruff and configured mypy (16 files) clean; Rental benchmark 15/15 (3 TP,
  0 FP, 0 FN, 12 TN); privacy benchmark 19/19 (11 ordinary, 8 unsafe;
  0 false blocks, 0 unsafe passes). PR #5 CI passed 8/8 pytest jobs on Python
  3.11–3.14. These are scripted checks, separate from the model E2E result.
- A fresh raw, real-style synthetic case completed the integrated privacy and
  native-document path through an actual client PDF. Both originals were native
  PDFs; Codex read the originals, Python bound their hashes, deterministic code
  calculated the ledger, and Codex performed findings and PDF QA. The run was
  evaluation-only and did not authorize delivery. It does not establish accuracy
  on independent cases.
- A live synthetic privacy probe allowed an ordinary professional-contact PDF
  and blocked a medical/HR-sensitive attachment. A synthetic secret was blocked
  on retry; its first model response failed schema validation. These three probes
  are development checks, not a blinded privacy benchmark.
- Two native PDF sources passed the approved-source job through extraction,
  separate source reread, fact review, deterministic reconciliation, model
  findings and actual PDF QA. The first run required renderer corrections.
- A fresh run after the generic discrepancy-family correction stopped on exact
  citation/schema validation; a revised QA prompt retained strict validation and
  the resumed run passed. Synthetic PDF SHA:
  `d665d43df0b26685cf20b0611e93d75b10b7328f3e99813d9b07e1838a02184e`.
  Receipt:
  `scratch/source_job_dev_cases/pair_v2/processed/autonomous_report/report-adc293aeee96b6baf9b405e135cc50b1e6eec339c2b67891a48d97df3623ab17.json`.
  This was DEV before later policy-binding changes, not a frozen final run.
- All results remain `EVALUATION_ONLY_QA_PASSED`, with human approval and
  delivery authorization false. Separate same-model QA is not independent
  outcome adjudication.

## Acceptance still open

The historical synthetic eight-source case proves an engineering path, not
repeatable E2E completion or material report correctness in unfamiliar dossiers.
The prior v4 replay exposed a structural review failure, corrected in the
current candidate and tested by the new DEV E2E.
A 20-case varied synthetic
ADVERSARIAL corpus has been prepared with separate private truth under ignored
`scratch/final_validation_4b536e4/challenge/`; this agent has seen its
generator, so its own runs are **not blind**. Three selected cases have been
run source→report after the first known-case success: two produced evaluation
PDFs passing model QA and matched their precommitted EUR 150 financial oracle;
one stopped safely because a CSV record did not establish an issued invoice.
That is 2/3 delivered coverage in a tiny selected subset, not a 99% quality
score; 17 corpus cases remain unrun. The new eight-source PDF is evaluation
output, not a delivered report. These synthetic workspaces bypass real
contract/privacy intake, so they exercise approved-source-to-report behavior,
not raw real-client authority. Independent final-report
adjudication, measured founder corrections/review time, model cost and broad
coverage/abstention evidence remain open. Genuine real-client processing and
delivery still require owner-controlled authority. The 99% correctness and 95%
no-correction objectives remain targets, not observed rates.

## Next frozen measurement (no further feature expansion)

Current code/prompt/policy candidate: semantic guidance v9,
source adjudication v4, native analyst review v3, report author v4. Do not
change it to improve a HOLDOUT score without starting a new declared version.
The structural fact-review stop above is corrected and a clean source-to-report
replay passed. This remains an evaluation candidate, not a release freeze or
readiness claim. Next,
an evaluator who has not seen this DEV generator should prepare a fresh, sealed public/private
challenge with varied vendors, layouts, scans, credits, returns, clean invoices
and genuinely insufficient dossiers. Run every admitted public case source→report;
retain all STOPs and retries in the denominator. Before looking at agent reports,
the independent adjudicator records expected material findings from originals;
then checks each finished report for financial errors, unsupported positives,
misses, provenance, abstentions and material omissions. Compare against the
precommitted oracle only after decisions are sealed. Record review minutes,
human corrections, model/CPU time and actual cost. Same-model QA and the three
selected probes above cannot substitute for that adjudication. A small perfect
sample cannot establish a ≥99% population correctness rate.

See [failures](FINAL_AUTONOMOUS_FAILURES.md),
[metrics](FINAL_AUTONOMOUS_METRICS.md) and
[release boundaries](FINAL_RELEASE_BOUNDARIES.md).
