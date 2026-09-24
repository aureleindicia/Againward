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
  then failed at native fact promotion. The saved proposals put two valid,
  different rate-card descriptions under one aggregate `rate_card` entity. The
  canonical single-value-per-entity guard correctly rejected that shape. Rental
  extraction guidance now explicitly requires one entity per independently
  priced equipment row; this policy change is unverified by a fresh model run.

## Still open

- The eight-source fresh run has not been repeated under row-level rate-card
  guidance. No genuine human visual attestation has been obtained for its scan.
- Source/guidance/privacy changes fail closed, but automatic revision/recomputation
  and supplemental-document continuation have only partial integration proof.
- All-scan final QA, non-exact relationship adjudication, policy-version replay
  checks and final frozen challenge remain to be completed.
- Actual founder correction/review burden and independently adjudicated report
  correctness are unmeasured. No 99% or 95% success-rate claim is justified.
