# Visual review lifecycle and monetary typing follow-up — 2026-09-26

This narrow follow-up addresses two blockers found after the visual-path
redesign. It uses only the two known synthetic Rental cases and makes no claim
about unseen-case accuracy. Both fresh reruns used `gpt-6-luna`, current
source bytes, evaluation-only workspaces, and normal workflow gates.

## Root causes and minimal corrections

### CASE A: visual review lifecycle

The previous follow-up conflated two different receipts. The native analyst
review emits `WAITING_FOR_VISUAL_REVIEW` as a handoff indicating that visual
fact review must run. It is not the final visual-review state and cannot stand
in for an attestation. The visual-review contract's final state is
`WAITING_FOR_VISUAL_ATTESTATION`; when required structural identity fields are
missing, the visual reviewer returns `REPAIR_REQUIRED`.

The source-job continuation previously mapped every non-attestation result to a
generic `WAITING_FOR_REQUIRED_INFORMATION`, obscuring the actual structural
repair state. It now accepts only the canonical final attestation state,
propagates `REPAIR_REQUIRED` with its structural gaps, and rejects the handoff
state if it appears as a final visual-review receipt. No alias or bypass was
added. The promotion and attestation gates are unchanged.

Regression test:
`test_visual_review_handoff_is_not_an_attestation_or_final_receipt_state`
checks the handoff, required-attestation, and structural-repair outcomes.

### CASE B: accounting amount semantic type

The model assigned `value_type=CURRENCY` to numeric money observations such as
`net_amount=900.00`; `CURRENCY` is reserved for an ISO code such as `EUR`. The
strict ISO currency validator was correct. The extraction contract did not
state monetary field/type separation clearly enough, and deterministic
semantic/type validation did not reject a mismatch between a money semantic
field and `CURRENCY` early enough.

The generic and Rental guidance now specify numeric `DECIMAL` for `net_amount`,
`rate`, `unit_rate`, and `allocated_amount`, with a separate `currency` field
using `CURRENCY` and an ISO code. Deterministic semantic/type validation
enforces that pairing for native and visual proposals and adjudicator
observations. The visual path no longer converts combined text such as
`150.00 EUR` into a numeric value. No permissive fallback or financial rule
change was made; exact native spans remain mandatory.

Regression test:
`test_accounting_export_keeps_amounts_numeric_and_currency_separate` uses a
representative workbook export, checks related money fields, and verifies that
wrongly typed values fail closed. Existing currency-code validation remains
strict.

## Fresh known-case reruns

### CASE A — `c06894c2744f1010`

The run completed source comparison, original-pixel adjudication, native fact
review, and reached final visual fact review. It ended `REPAIR_REQUIRED` at
`VISUAL_FACT_REVIEW`, with two structural entity gaps in the visual source:
one missing `entity_kind`; another missing `entity_kind`, `document_role`, and
`document_status`. No visual attestation was fabricated. Calculation, report,
and final PDF QA were not reached; the EUR 150 oracle was not calculated.

The prior report of a final visual receipt at
`WAITING_FOR_VISUAL_REVIEW` was incorrect: that value belonged to the native
review handoff. The current code now reports the actual downstream structural
repair requirement without treating either state as attestation.

### CASE B — known eight-source signed-return dossier

All eight primary reads and independent rereads completed, including the
accounting export. The run passed source comparison for six sources, then
stopped at `SOURCE_ADJUDICATION` with two unresolved material disagreements:
`accepted_rate_sheet.pdf` and `signed_return_scan.pdf`. The adjudication receipt
records the rate sheet as not supplying a complete governing tariff
representation and the scan as a material disagreement between the proposals.

The rerun did not stop with `CURRENCY_MISMATCH`. However, the accounting export
produced zero candidates in both stored extraction receipts, so this run does
not demonstrate that live numeric monetary candidates traversed the workflow.
The contract behavior is covered by the representative-workbook regression
test. No calculation, report, or final PDF QA was reached; the known DEV
financial oracle remains EUR 150 for LIFT-5 and EUR 0 for LIFT-50 and was not
calculated in this run.

## Validation

- Focused visual/source/adjudication/provider and extraction contract tests:
  **91 passed**.
- Ruff: **passed**.
- Configured mypy: **passed**, 16 source files.
- Rental benchmark: **15/15**; 3 TP, 0 FP, 0 FN, 12 TN.
- Privacy benchmark: **19/19**; 0 false blocks, 0 unsafe passes.
- Full pytest and PR #5 CI results are added after the run completes.

These benchmark fixtures are scripted regression checks. The two live runs are
known-case diagnostics only, not independent accuracy evidence.
