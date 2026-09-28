# Rental rate dimensions and source-fragment scope — 2026-09-28

## Causes found

### Composite rate denominator

The rate model already represented time unit, quantity basis, and calendar
convention separately. The failure was earlier: model normalization only
expanded a denominator when the whole expression appeared in `billing_unit`.
When a reader split one exact source quote across fields (for example, time
unit in `billing_unit` and asset basis in `quantity_basis`), the unsupported
intermediate value survived to package validation as an unknown rate dimension.
This was a projection gap, not an arithmetic or financial-rule defect.

### Untyped source metadata/reference groups

Structural validation treated every model-local group as a material entity.
That incorrectly required `entity_kind` on source-envelope role/status facts
and invoice-reference-only fragments. At package construction, source role and
status were also collected only from typed entities, so metadata attached to a
separate envelope group could not satisfy the source-level contract. The core
credit entity's own kind was present; the reported gaps were metadata/reference
groups, not a missing type on that credit entity.

## Changes

- Canonicalize a rate dimension from the exact quote attached to that
  observation. Reconcile any separately emitted dimensions, then materialize
  only dimensions explicitly stated in the same quote. Preserve the original
  quote, native location or visual page, and group. A conflict is rejected;
  explicit calendar-week/month conventions outside the supported model remain
  unsupported even if the model also supplies plausible component fields.
- Make the Rental domain contract distinguish non-entity source metadata and
  identifier references from material entities. Rental callers opt into this
  policy explicitly; generic document resolution still fails closed by
  default. Business-bearing groups, including amount/rate/credit/asset facts,
  continue to require their own `entity_kind`.
- Read reviewed role/status at source scope across all promoted same-source
  facts. Retain untyped metadata/reference groups with their fact IDs in
  package lineage; do not turn them into entities or infer relationships,
  authority, or commercial meaning from them.

No filename-derived defaults, cross-source copying, financial-rule changes,
quote relaxation, or review bypass were introduced.

## Regression coverage

Coverage includes split native and visual rate dimensions, per-item and
per-scope denominator forms, supported calendar-day convention, exact-quote
conflicts, unknown/unparsed dimensions, source metadata/reference fragments,
material untyped fragments that must fail, and generic resolver fail-closed
behavior without a Rental policy.

## Validation

The validation commands and final results for this change are recorded in the
change report. No CASE A/B end-to-end run was performed in this stabilization
pass.
