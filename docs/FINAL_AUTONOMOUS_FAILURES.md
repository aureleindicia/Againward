# Final autonomous validation — failure register (in progress)

This is a development register, not a release certificate. All cases below are
synthetic DEV fixtures; none establishes independently blind accuracy.

## Observed and corrected

- Raw privacy orchestration is now integrated before Rental source parsing. The
  live synthetic probe passed an ordinary professional-contact PDF and blocked
  a medical/HR-sensitive attachment. A synthetic secret was blocked on retry,
  but its first response failed schema validation; this is a remaining
  robustness gap, not a clean first-pass result.

- Two-source approved-document job: original PDF QA stopped after two report
  attempts. The renderer omitted the quantity multiplier, claimed no discrepancy
  despite a calculated difference, and described a zero applied credit as if the
  existence of all credits had been verified. Corrected renderer distinguishes
  documentary difference, cause and recoverability, shows quantity without
  multiplying aggregate asset-days again, and scopes credits to the calculation.
  Original stopped PDF SHA: `66c50fe5a40c4d0ba534da665fbf590368ebfdefd3ce90a3d3b21f09f357335b`.
  Resumed run passed source/report model QA, PDF SHA:
  `5bbe3b6f87881f7f6f3b1adcfa8240c618047a1c07998013fbdff5b35764bacc`.
  Receipt in ignored workspace:
  `scratch/source_job_dev_cases/pair_1f408/processed/autonomous_report/report-a0852fa0958d37b33ac703aae4edb2b4089f90e7118b5cb561f832a75a06b9cb.json`.
  This run predates the generic discrepancy-family correction below and is not
  a final frozen run.
- Numeric representation (`9` versus `"9"`, decimal formatting) and descriptive
  labels created false material source disagreements. On the saved eight-source
  DEV rereads, material differences decreased from 3 to 1; strict differences
  remain 4. Actual amount differences remain material and tested. This measures
  comparator behavior, not model accuracy.
- Kernel fallback called an unexplained Rental difference `INCORRECT_DURATION`
  without evidence of incorrect days. Added `DOCUMENTARY_CHARGE_DIFFERENCE`;
  observed billed-day mismatches retain their specific family. Fresh model-run
  validation of this change is still required.
- Multiple visual-source renders used identical temporary filenames. Each source
  now has a distinct rendering directory; a regression verifies distinct pixels.
- A transient `MODEL_UNAVAILABLE` during report QA left a resumable WAIT. Retry
  completed without re-extracting or fabricating the missing answer.
- A refreshed eight-source model run resolved both original reread disputes,
  then failed at native fact promotion because two rate-card rows shared an
  aggregate `rate_card` entity. Under guidance v9, fresh primary and challenger
  runs now use separate LIFT-5 and LIFT-50 row entities with no conflicting
  field values; `UNSUPPORTED_PROMOTION` did not recur. The canonical guard was
  not weakened and both rows remain represented.
- The first v9 adjudication attempt failed closed with
  `EXTRACTION_INCOMPLETE`: it cited the agreement, not the disputed signed-return
  scan. Policy v3 then stopped at `UNRESOLVED` solely because the scan lacked
  native text. This was an orchestration defect, not evidence that pixels were
  unreadable. Policy v4 reopened exact original pixels; its first responses
  failed exact location/quote validation, leading to constrained unit locations
  and one bounded repair. The accepted response cited the disputed scan itself
  and selected `CHALLENGER`, still subject to fact/report QA.
- The next automatic stop was `WAITING_FOR_VISUAL_ATTESTATION` despite all 18
  scan candidates being accepted by the visual analyst. The existing promotion
  gate now permits a separately verified `MODEL` visual receipt only when the
  independent source reread, any material pixel adjudication, candidate set and
  rendered pixels are current. HUMAN attestation remains the exception path.
  The eight-source DEV run then completed a QA-checked PDF; no HUMAN receipt
  was fabricated, and neither a model receipt nor same-model PDF QA is
  independent correctness evidence.
- In the first varied ADVERSARIAL source-to-report probe, the native reviewer
  deferred a clearly printed EUR 1,550 invoice amount solely because it
  disagreed with the contract calculation. That conflated documentary
  transcription with financial reconciliation. Native review policy v2 now
  directs the model to accept source-supported billed amounts while deterministic
  code calculates the difference. The source job also routes an unresolved
  native review to `WAITING_FOR_REQUIRED_INFORMATION` rather than falling
  through to a generic `EXTRACTION_INCOMPLETE` packaging failure. On rerun,
  the case reached QA-checked PDF with EUR 1,400 expected and EUR 150
  documentary difference; this is DEV feedback, not a held-out score.
- A later eight-source replay under native-review v2 reached calculation and
  finding QA but first paused at report QA with transient `MODEL_UNAVAILABLE`.
  On resume, the author supplied a free return date in prose. The deterministic
  structured-claim validator correctly rejected it, but the job raised a raw
  error instead of allowing a bounded author correction. Report policy v4 keeps
  the validator and permits one source-bound repair; a second invalid draft
  returns `STOP_INVALID_MODEL_REPORT_AUTHOR`. The repair has targeted tests but
  has not yet been exercised by a live author draft.
- The same multiply revised DEV workspace then stopped during Evidence Plane
  retrieval: only 17,066 context bytes remained, and its first 200-row query
  exceeded that preserved budget. This is a real revision-budget STOP; it was
  not reset to make the old investigation pass. A separate fresh synthetic
  workspace was created with byte-identical eight sources to test current code.
- That fresh v4 run regenerated eight primary and eight challenger reads,
  resolved two material disagreements (including the signed scan using the
  disputed original pixels), then stopped safely at `FACT_REVIEW` with
  `REPAIR_REQUIRED`. The selected primary rate sheet contained a standalone
  `rate_sheet` date candidate with no `entity_kind`, `document_role` or
  `document_status`; the native reviewer accepted that orphan candidate even
  after repair while acknowledging the structural gap. The priced LIFT-5 and
  LIFT-50 rows remained separate. This is a model extraction/review reliability
  defect, not missing source bytes or a reason to weaken the entity guard.
- Fact-review policy v3 now checks only accepted source-local entities for
  completeness and withholds promotion whenever one lacks identity/authority
  fields. Its bounded repair explicitly rejects a detached printed date with
  no analytical entity role. Regression covers the exact orphan pattern, its
  repair, two valid dated rate rows and a malformed partial entity. A separate
  fresh eight-source current-code run reached `EVALUATION_ONLY_QA_PASSED` with
  a QA-checked PDF and the EUR 150/0 DEV oracle. The v4 STOP remains historical
  failure evidence, not an unresolved current blocker.

## Still open

- No independently adjudicated final-report cohort has been completed.
  The eight-source result is a known synthetic DEV case with same-model source
  and report QA, not a blind quality score. The prior fresh v4 replay did not
  reach a report; the current fresh run exercised report-author v4 repair and
  final PDF QA.
- A separate ADVERSARIAL "correct invoice" case stopped at source adjudication:
  its only billing record is a CSV row with invoice reference and net amount,
  but no charge description or evidence that an issued invoice exists.
  Primary/challenger both marked limitations; adjudication refused to confer
  invoice authority. This is a genuine evidence/coverage limitation requiring
  a proper invoice or clarification, not a zero-discrepancy report.
- Source/guidance/privacy changes fail closed, but automatic revision/recomputation
  and supplemental-document continuation have only partial integration proof.
- All-scan final QA, non-exact relationship adjudication, wider policy-version
  replay checks and the frozen challenge outcome remain to be completed.
- Actual founder correction/review burden and independently adjudicated report
  correctness are unmeasured. No 99% or 95% success-rate claim is justified.

## Additional measured failures: five-case cohort on build 6213430

The next five preselected synthetic corpus cases were scored after immutable
pretruth sealing. One visual invoice case stopped with `EXTRACTION_INCOMPLETE`
before original-pixel review, calculation, or HUMAN escalation, although the
oracle supported a EUR 150 discrepancy and required scan review rather than
abstention. This is one unjustified stop and one material miss. It is a generic
scan extraction/continuation failure candidate and must be addressed before a
freeze decision.

Two other cases reached authored PDF drafts with correct oracle material
outcomes (EUR 0 clean and EUR 550 partial return), but report QA twice rejected
authoring/presentation language and no final QA-passed report was produced.
These are justified workflow stops, while showing a report-author QA friction
class. The two remaining cases abstained as the oracle required. Across the
five: 4/5 correct end-to-end outcomes, 0 false positives, 0 amount errors, 0
provenance/evidence errors, 0 HUMAN escalations, and 0/5 final-QA-passed
reports. Detailed case results and immutable pretruth records are linked from
[the cohort artifact](validation/adversarial_cohort_5_6213430/).

This is a small synthetic pre-freeze tranche, not independent population-level
proof and not a ≥99% estimate. Same-model QA is not counted as independent
correctness evidence; final delivered-report correctness is undefined because
its denominator is zero. Production code, prompts, and policy were not changed
during these five runs.
