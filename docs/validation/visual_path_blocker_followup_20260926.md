# Visual-path blocker follow-up — 2026-09-26

This records a narrow engineering follow-up to the historical known-case
redesign run in
[`visual_semantic_path_redesign_20260926.md`](visual_semantic_path_redesign_20260926.md).
The earlier `MODEL_UNAVAILABLE` and `SOURCE_LOCATION_INVALID` outcomes remain
preserved there as historical results. No unseen case was used. Model:
`gpt-6-luna`; Codex CLI: `codex-cli 0.156.1`.

## Causes and changes

### CASE A: adjudication `MODEL_UNAVAILABLE`

The original A source passes and QA had succeeded; only source adjudication
failed. An evaluation-only reproduction retained the CLI runtime stderr in the
private ignored workspace. Codex returned HTTP 400
`invalid_request_error / invalid_json_schema`, not a transient service outage.
The adjudication decision schema declared `observations` in `properties` but
omitted it from the decision object's `required` list. The strict response
format requires every declared property to be required. The old classifier
looked only at stderr and mapped this request/configuration error to the generic
`MODEL_UNAVAILABLE`, incorrectly making it appear retryable.

The decision schema now requires `observations`, consistent with the response
validator, which already accepts an empty observation list. Invocation failure
classification now inspects both stdout and stderr and distinguishes explicit
service unavailability from HTTP 400/schema/configuration errors, CLI absence,
and unclassified process failures. Sanitized failure metadata records model,
CLI version, exit code, stream sizes, stage, and category. Raw stderr is retained
only in a private `--evaluation-only` workspace. Configuration/invocation
errors are not treated as model-availability retries.

### CASE B: non-exact native quotes

`supplier_email.eml` has native unit `part:1`. The model sometimes returned a
semantic paraphrase or altered whitespace as `raw_observed_value`; the existing
exact substring/span validator correctly rejected it. Previously one such row
aborted the complete proposal before other exact rows could be retained.

The provider now screens only native candidate quotes against their named
native unit before proposal assembly. A quote is retained only when it occurs
exactly once, byte-for-character as the decoded source text. Missing or
non-unique quotes are discarded as unsupported candidates; they are never
normalized, rebound to another location, or converted into evidence. A
mixed-validity proposal is marked `PARTIAL`, and a safe private diagnostic
records candidate index, semantic type, location, quote hash, and rejection
code. In ordinary workspaces it does not retain the quote text. If every native
candidate is rejected, or a location is invalid, the source still fails closed.
The unchanged deterministic validator continues to require exact source spans
for every retained native fact.

## Regressions and checks

New tests cover: the strict adjudication schema requiring every declared
decision property; HTTP 400 schema/configuration classification from stdout;
safe adjudication failure metadata; mixed exact and paraphrased native
candidates retaining only exact citations; and all-invalid native output
failing closed. Existing exact span tests remain unchanged.

- Focused provider/adjudication/source-job tests: **36 passed**.
- Ruff: **passed**.
- Configured mypy: **passed**, 16 source files.
- Rental benchmark: **15/15** (3 TP, 0 FP, 0 FN, 12 TN).
- Privacy benchmark: **19/19** (0 false blocks, 0 unsafe passes).
- Full pytest: pending at artifact creation; result will be appended before
  commit.

## Live known-case reruns after the fixes

Both runs used fresh synthetic evaluation workspaces, unchanged source bytes,
`gpt-6-luna`, and normal workflow gates. No HUMAN approval/evidence was created.

### CASE A — `c06894c2744f1010`

The rerun completed 2 primary reads, 2 independent rereads, source comparison,
and pixel adjudication (`QA_DISAGREEMENT_RESOLVED`, zero unresolved sources).
Native fact review accepted 22 native facts. It then stopped at visual fact
review with `WAITING_FOR_REQUIRED_INFORMATION`, stage `VISUAL_FACT_REVIEW`:
the review receipt was `WAITING_FOR_VISUAL_REVIEW` with 24 candidates pending
attestation and 2 deferred, while the normal source-job continuation requires
`WAITING_FOR_VISUAL_ATTESTATION`. No calculation, report, or final PDF QA was
reached. The EUR 150 oracle was not calculated. This is a distinct downstream
visual-review blocker; this follow-up does not change its gates.

The earlier adjudication failure is resolved for its architectural cause:
the repaired schema now allows the normal adjudication request to execute and
the source disagreement was resolved. This does not establish that every
adjudication will resolve correctly.

### CASE B — known eight-source signed-return dossier

All 8 primary reads completed. The first challenger passes completed for
`supplier_email.eml` and `issued_credit.pdf`; processing then stopped on the
accounting export with `CURRENCY_MISMATCH`. On the email, the primary returned
13 native candidates: 2 candidates with non-exact quotes were rejected and 11
exact candidates were retained in a `PARTIAL` proposal. The independent email
challenger returned 9 candidates with exact spans and completed successfully.
Thus neither email pass failed with `SOURCE_LOCATION_INVALID`, and all retained
citations remain source-exact. Comparison/adjudication/calculation were not
reached because the accounting export model output assigned `value_type=CURRENCY`
to `net_amount` values such as `900.00`; the deterministic currency validator
correctly accepts only ISO currency codes for `CURRENCY`. That separate
semantic typing error was not weakened or changed. The known DEV oracle remains
EUR 150 for LIFT-5 and EUR 0 for LIFT-50; neither was calculated in this run.

## Scope and limits

The two targeted blockers are corrected without weakening exact native spans,
visual promotion, source/render hashes, or ambiguity gates. CASE A still needs
the existing visual review to reach its required attestation state. CASE B
still needs the model's accounting-export type error resolved before the source
comparison and financial path can run. These known-case regression runs are
not blind accuracy evidence and do not support a ≥99% claim.
