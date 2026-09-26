# AGAINWARD — read first (2026-09-25)

Current first-client decision: **NOT READY — INDEPENDENT QUALITY MEASUREMENT OPEN**.
An earlier v9 eight-source DEV run passed the former rate-card promotion failure
and completed a model-QA-checked evaluation PDF without HUMAN scan transcription.
A later fresh replay stopped at native `FACT_REVIEW` on an orphan rate-sheet date.
The source-local structural review is now corrected and a new eight-source
current-code run reached `EVALUATION_ONLY_QA_PASSED` with a QA-checked PDF. Final
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

The later 2026-09-26 visual semantic redesign is only partially validated: its
two known live regression runs produced bound visual observations, but neither
reached calculation or report QA. Do not treat the earlier eight-source PDF
pass below as an E2E result for the redesigned code; see the
[visual redesign record](validation/visual_semantic_path_redesign_20260926.md).

The first Rental failure-family robustness pass moves structural metadata,
canonical enum and observation/limitation checks before source QA, with one
bounded source-bound retry. It also preflights adjudicator-created pixel facts.
Fresh CASE A / CASE B runs still stop before calculation: CASE A most recently
stopped on `REVIEW_STALE` during visual review; CASE B stopped on an accounting
export entity missing structural metadata after one retry. See the
[robustness record](validation/rental_failure_family_robustness_20260926.md).

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
  not a correctness claim. At that checkpoint, seventeen cases and independent
  report adjudication remained outstanding; the next five-case tranche is
  recorded below.
- A further five preselected cases were run on production-code commit
  `6213430c8bd9dd58ac6c84f4fc33c2cc1fe8f502`; per-case pretruth records were
  sealed before oracle access. Two cases produced drafts with correct material
  amounts (EUR 0 clean and EUR 550 return) but both stopped at report QA; two
  oracle-required abstentions were correct; one scan case failed before visual
  review and missed a supported EUR 150 discrepancy. Aggregate: 4/5 correct
  end-to-end outcomes, 1 unjustified stop/material miss, 0 final-QA-passed
  reports, and no amount, false-positive or provenance errors. This small
  synthetic tranche is evidence of a generic scan extraction gap and report
  authoring QA friction, not a ≥99% estimate. Detailed seals and adjudications:
  [five-case cohort](validation/adversarial_cohort_5_6213430/).
- The c06894 visual-source routing defect is corrected narrowly: a selected
  proposal with only visual candidates and only native-text/pixel-verification
  limitations may proceed to original-pixel adjudication and the existing
  visual review. The other completeness limits still stop; a selected visual
  proposal also needs an exact hash-bound pixel citation before proceeding.
  Regression tests model the original primary-visual / empty-challenger shape
  through MODEL visual receipts, and keep ambiguous pixels on the HUMAN/WAIT
  path. A fresh live replay with the configured model `gpt-6-luna` had zero
  invoice candidates from both passes; multimodal adjudication left the source
  unresolved and the workflow waited at `SOURCE_ADJUDICATION`. It did not
  reproduce the old pre-visual `EXTRACTION_INCOMPLETE`, but did not reach the
  known EUR 150 result. This is regression evidence, not a new accuracy sample.
  The successful eight-source signed-scan MODEL receipt was reverified against
  its source, adjudication and rendered pixels, with no HUMAN attestation.
  [Regression record](validation/visual_source_routing_20260925.json).
- Validation on production fix `7bfb232` and order-independent test follow-up
  `12af083`: 843 pytest cases passed (395.34 s), Ruff passed, configured mypy
  passed (16 files), Rental benchmark 15/15 (3 TP, 0 FP, 0 FN, 12 TN), privacy
  benchmark 19/19 (0 false blocks, 0 unsafe passes). PR #5 CI passed twice,
  8/8 jobs each across Python 3.11–3.14; PR remains draft and unmerged. The
  first CI run on `7bfb232` found the visual test's PDF-order assumption; the
  test was made source-ID based and both CI runs on `12af083` passed.
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
  validated at that checkpoint. This was a core coverage defect, not a client
  clarification or a reason to relax the entity invariant.
- Current fact-review policy v3 checks structural completeness only for accepted
  source-local entities and withholds promotion during repair. A date detached
  from any valid entity must be rejected; dates on complete rate/document
  entities remain valid. Targeted regression covers the orphan, bounded repair,
  complete dated LIFT-5/LIFT-50 rows and malformed entities. A fresh synthetic
  eight-source run used the same source hashes with 8 primary and 8 independent
  reads, 0 material source disagreements, 150 accepted native facts, 10 pixel-
  bound visual `MODEL` facts, 2 invoice lines, finding QA and report-author v4
  repair. Final original-source/PDF QA passed:
  `EVALUATION_ONLY_QA_PASSED`, PDF SHA256
  `07e8c9d31c2c2505c053ebe3761c1c83e8da0388139e2d34bb5364a55971ecb7`.
  The DEV oracle is EUR 150 for LIFT-5 after the EUR 100 issued credit and EUR 0
  for LIFT-50. No HUMAN evidence or delivery approval was created. This known
  dossier and same-model QA are not independent accuracy measurements.
- Post-fix scripted checks: 838 pytest cases passed in 310.49 s from committed
  code; Ruff and configured mypy (16 files) passed. Rental benchmark 15/15
  (3 TP, 0 FP, 0 FN, 12 TN); privacy benchmark 19/19 (11 ordinary, 8 unsafe;
  0 false blocks, 0 unsafe passes). PR #5 CI passed 8/8 Python 3.11–3.14
  pytest jobs. These checks are regression evidence, not independent accuracy.
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

- Luna visual robustness characterization (10 fresh runs; DEV only) is recorded
  in [luna_visual_robustness_10_20260925.json](validation/luna_visual_robustness_10_20260925.json).
  Across 5 repeats each of known scanned-invoice case `c06894c2744f1010` and the
  known eight-source signed-return dossier, there were 0 useful scanned facts
  from either extraction pass, 0 successful pixel recoveries, 0 calculations,
  and 0 QA-passed reports. Three invoice runs waited for required information;
  the known original scan supports the EUR 150 discrepancy, so those waits are
  recorded as oracle-unjustified misses. This is repeatability evidence on two
  known synthetic cases, not independent accuracy evidence or a ≥99% estimate.

- Causal visual-path audit at `dff2905` (known cases only) is recorded in
  [causal_visual_architecture_audit_20260926.json](validation/causal_visual_architecture_audit_20260926.json).
  Luna read the scanned invoice at both 120 and 300 DPI and the signed return at
  300 DPI under simple prompts. The current Againward raw primary extraction
  returned zero candidates for both visual sources; the validators accepted
  those empty proposals. The evidence points to a materially overconstrained
  visual extraction/adjudication path, with 120 DPI a secondary precision
  issue. Exact raw outputs are retained in the artifact; historical rejected
  `SOURCE_LOCATION_INVALID` response bodies were not retained, so their emitted
  locations cannot be reconstructed.

- Current visual redesign commit `04a2990` changes only the model-facing visual
  semantic read and pixel-observation recovery path; native exact-span behavior
  and serialization stay compatible. It uses 300-DPI page renders and binds
  observations to current source/page/render hashes after model response. The
  fresh known CASE A run (`c06894c2744f1010`) yielded 15 primary and 13
  challenger visual candidates, including invoice ID and EUR 2,670 net; QA
  found two material disagreements and the adjudication call ended
  `MODEL_UNAVAILABLE`. No EUR 150 calculation, report, PDF QA or HUMAN evidence
  resulted. The fresh eight-source CASE B run read all eight primary sources;
  the signed-return scan yielded 16 pixel-bound candidates including a LIFT-5
  return dated 2026-09-05 and separate LIFT-50 evidence. It failed before
  challenger reread when native exact-span validation rejected a model quote in
  the supplier email; no financial calculation or report resulted. These are
  known regression results, not accuracy evidence. Focused tests passed 65/65;
  current full-suite and CI results are recorded in the
  [redesign artifact](validation/visual_semantic_path_redesign_20260926.md).

- Follow-up to those two blockers is recorded separately in
  [visual path blocker follow-up](validation/visual_path_blocker_followup_20260926.md).
  Runtime inspection traced A's reported `MODEL_UNAVAILABLE` to an HTTP 400
  strict-schema error (`observations` missing from adjudication's required
  fields); that schema and failure classification are fixed. B's non-exact
  email citations are now excluded individually without altering exact-span
  validation; both primary and challenger email passes completed. The known
  reruns reached distinct later blockers (A: visual review waiting for required
  attestation; B: `CURRENCY_MISMATCH` from a wrongly typed accounting-export
  amount). Neither case reached calculation/report QA in this follow-up.

- The next narrow correction and reruns are recorded in
  [visual lifecycle and money types follow-up](validation/visual_review_and_money_types_followup_20260926.md).
  The earlier live-state wording above is historical: `WAITING_FOR_VISUAL_REVIEW`
  was the native-review handoff, not the final visual receipt. CASE A now stops
  explicitly at `REPAIR_REQUIRED` for missing visual entity identity fields,
  without an attestation. CASE B no longer reports `CURRENCY_MISMATCH`, but its
  accounting extraction had no candidates and the run stops at
  `SOURCE_ADJUDICATION` on unresolved rate-sheet and signed-return disagreements;
  numeric live amount passage remains unverified. Focused tests (91), Ruff,
  mypy, full pytest (856 passed), Rental (15/15), and privacy (19/19) pass. PR
  #5 CI passed 8/8 jobs across Python 3.11–3.14. The full details are in the
  linked follow-up; no calculation/report result is claimed for either rerun.

- The next scoped stabilization at `a95cf62` is documented in
  [three known-case blockers stabilization](validation/three_known_case_blockers_stabilization_20260926.md).
  Visual extraction guidance now requires complete, source-supported structural
  observations grouped with their invoice line. Adjudication distinguishes
  selecting source-local rate rows from approving a governing tariff, and
  resolves grouping-only return-scan differences only when the original pixels
  support the same event. Exact native citations and downstream review gates
  remain strict. In fresh `gpt-6-luna` reruns, CASE A's pixel adjudication
  resolved, then stopped before fact review on a contradictory extraction
  limitation; CASE B resolved its rate-sheet and signed-scan disagreements,
  then stopped at fact review with five structural gaps in native-source
  proposals. Neither run reached calculation, report, or PDF QA; no known
  financial oracle was calculated. Targeted tests (32), Ruff, configured mypy,
  Rental (15/15), and privacy (19/19) pass. Full pytest passed 859/859 on the
  committed engine; the first dirty-tree run's two expected HOLDOUT-integrity
  failures disappeared after commit. PR #5 CI passed 8/8 checks on Python
  3.11–3.14 across push and pull-request workflows. These are known-case
  regression runs, not accuracy evidence. PR #5 remains open and draft.

- Follow-up for source-limitation semantics and native structural metadata is
  recorded in [the 2026-09-26 stabilization note](validation/source_limitation_and_native_entity_stabilization_20260926.md).
  Native extraction contracts now describe source-supported metadata for
  correspondence, accounting-export rows, and supporting rate sheets. The
  limitation checker distinguishes an absent additional amount from an
  already stated net amount while retaining the limitation and visual review
  gate. The fresh CASE A rerun passed the former false-positive check but
  stopped at adjudication with `EXTRACTION_SCHEMA_INVALID`; fresh CASE B
  completed 8+8 reads and QA, then stopped with `EXTRACTION_INCOMPLETE` before
  fact review. Neither reached calculation, report, or PDF QA; neither known
  oracle was calculated. This remains regression evidence only.

## Diagnostic observability follow-up (2026-09-26)

Fresh instrumented reruns did not reproduce the prior opaque adjudication stops.
CASE A instead stopped fail-closed on a source-completeness contradiction at
`$.decisions[0].selection` involving `net_amount`. CASE B resolved all 7 source
disagreements and reached FACT_REVIEW, where `supplier_email.eml` entity
`email-1` is missing `entity_kind`. Neither reached calculation or report QA.
The prior raw adjudication answers were not retained, so the exact historical
fields cannot be reconstructed. New receipts retain safe stage/source/decision/
schema-path/code/shape/version/hash metadata; raw answers remain evaluation-only
private scratch data. See the [diagnostic observability
record](validation/fail_closed_diagnostic_observability_20260926.md). The
instrumentation checkpoint passed 873 pytest tests, Ruff, configured mypy
(16 files), Rental 15/15 and privacy 19/19. PR #5 CI passed 8/8 jobs across
Python 3.11–3.14. These are regression checks, not accuracy evidence. PR #5
remains open and draft.

## Rental failure-family robustness (2026-09-26)

The current implementation adds deterministic Rental structural and semantic
preflight before source QA and checks new pixel observations before they enter
the fact-review path. Structural omissions and malformed adjudication schemas
receive at most one bounded, source-bound retry; unresolved structure remains
fail-closed. Exact native spans, provenance and render hashes, visual review,
attestation, HUMAN semantics, contract authority, and Rental arithmetic were
not relaxed. The fresh known CASE A run now reaches visual review but stops at
`REVIEW_STALE`; CASE B's one retry corrected the email entity, then the
accounting-export entity remained structurally incomplete after its one retry.
Neither reached calculation or report QA; the EUR 150 / LIFT-5 EUR 150 and
LIFT-50 EUR 0 oracles remain unverified. Full pytest passed 900 tests on the
clean follow-up commit; Ruff, configured mypy, Rental 15/15, privacy 19/19, and
PR #5 CI 8/8 passed. See the [failure-family robustness
record](validation/rental_failure_family_robustness_20260926.md). This is
regression evidence only, not accuracy evidence.

### Final local Luna pass

The fresh known-case reruns on `380c0e8be80a48a457d252da002506f72e48c6c1`
supersede the earlier `REVIEW_STALE` / row-scoped accounting-export status.
CASE A now passes current prompt-version validation, completes source QA and
MODEL visual review, then stops at document-package validation because its
invoice-line observation lacks `invoice_line_id`, `charge_key`, and
`charge_type`. CASE B stops at primary extraction on `accounting_export.xlsx`:
source-level `document_role` and `document_status` remain absent after one
bounded retry. Neither known financial oracle, calculation, report, or final
PDF QA was reached. No HUMAN evidence was created. Full pytest passed 905,
Ruff/mypy passed, Rental was 15/15, privacy was 19/19, and PR #5 CI passed all
8 jobs in each of the latest two runs. Details and limitations are in the
[final failure-family follow-up](validation/rental_failure_family_robustness_20260926.md).
