# Rental reconstruction and union readiness — 2026-09-30

Base: `71d839463dc5b39994874c10d9b7a379788b116b`.

## Scope and evidence

Code/history and existing private run receipts were inspected read-only. No new
CASE A/B invocation, replay test, smoke, or end-to-end run is authorized or used
in this change. All executable regressions use generic synthetic observations.

The observed adjudication failures have distinct mechanical causes at a shared
boundary: reconstruction and QA must evaluate the complete selected state, not
mistake lineage or an incomplete grouping for a complete occurrence.

1. Reconstruction moved `document_role` and `document_status` out of an explicit
   documentary envelope, leaving its supplier/date behind. The date then lost
   its documentary scope witness and the strict validator correctly reported an
   untyped group. Reconstruction had made a valid source structurally invalid.
2. Two reads could omit `entity_kind` despite carrying a printed invoice/line
   identity, amount, currency and an explicit INVOICE source role. Provisional
   identity alone allowed fact reconciliation, whose scope-based grouping split
   references from material observations of UNKNOWN scope.
3. Fresh QA treated a verified union receipt as semantic equivalence without
   retaining current unknown/conflict diagnostics or treating remaining
   structural gaps as requiring reconciliation. Lineage proves origin, not scope
   or completeness.

## Changes and ownership

- Move an entire explicit, non-business documentary envelope together. Only
  existing role/status/supplier/agreement/date/terms-unchanged observations in
  an envelope with an explicit role/status witness qualify. Standalone dates,
  reference groups and business-bearing groups do not gain documentary scope.
- Derive only the INVOICE_LINE *container* when the same observed group contains
  exactly one invoice ID, printed line ID, amount and currency, the source role
  is unambiguously INVOICE, and no credit/event discriminator or existing kind
  contradicts it. Preserve original values, citation, location, span/hash and
  ambiguity flags. This does not derive a charge classification or authority.
- The same structural derivation is used for canonical QA kind overrides and
  selected-state reconstruction. Model labels do not become business IDs.
- Refuse automatic material unions whose scope remains UNKNOWN, even with a
  provisional anchor. Ordinary source adjudication remains available.
- Union lineage cannot erase a conflict or unknown scope. An incomplete union
  remains marked for reconciliation before selected-state replay.
- Version the changed QA/union semantics. Prior union receipts are not silently
  re-approved under the new contract.

No financial, currency, native quote/span, render/page, privacy, HUMAN, review,
source mutation or package completeness gate is weakened. ASSEMBLE uses only its
selected facts for reconstruction; it does not resurrect rejected parent data.

## Generic regressions

- Explicit source envelope remains valid and reconstruction is idempotent;
  all original candidate proofs/values are preserved.
- Standalone date remains untyped and fails structural validation.
- Provisional line anchor with UNKNOWN material scope cannot authorize union.
- Verified union lineage does not approve incomplete structure.
- Complete invoice tuple supplies only its container; omission of each required
  tuple member or source role remains blocked.
- Both readers can omit the kind; union reconstruction and exact replay agree.
- Different printed line IDs remain distinct despite equal monetary values.
- Different explicit kind/source role is not overwritten by invoice inference.
- Visual review flags and page binding survive the structural derivation.

## Limitations

This removes reproduced mechanical failures, not all possible model omissions.
Unanchored observations, contradictory structure, absent commercial evidence and
ambiguous relationships remain fail-closed. Without a new independent live
campaign, no claim is made that A/B consistently reach calculation or that the
pipeline is production-ready. Unit/benchmark success cannot establish that.

## Validation

- Targeted independent QA, adjudication, reconciliation and failure families:
  **180 passed** (including 9 new parametrized regression cases).
- Pre-commit full pytest: **1155 passed, 2 failed**. The only failures are
  `test_holdout_engine_mutation_invalidates_the_run` and
  `test_correct_negative_abstention_is_not_counted_as_attribution_or_quantification`:
  both reject an engine differing from Git HEAD. Neither guard was changed.
- Ruff: passed. Configured mypy: passed (18 files). `git diff --check`: passed.
- Rental benchmark: **15/15**. Privacy benchmark: **19/19**.
- Added production lines inspected for fixture filenames, identifiers and oracles:
  none found. PR #5 remains draft/unmerged.
- Clean-HEAD verification and CI are performed after this commit; their results
  are reported separately rather than claiming them before they run.

Local ignored evidence: `scratch/generic-boundary-targeted-final.log`,
`scratch/generic-boundary-pytest.log`, `scratch/generic-boundary-rental/validation.json`,
`scratch/generic-boundary-privacy/validation.json`.
