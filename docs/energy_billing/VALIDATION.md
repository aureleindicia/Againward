# Checkpoint 0 / early boundary validation

This record proves an early engineering boundary, not completed Billing V1.
Implementation starts at `8a066e0a5cbb9eb29f528169a981d0c09fc99fb3` in the
isolated `feat/energy-billing-v1` worktree.

## Actual live evidence

CLI `0.159.3`, configured model `gpt-6.1-sol`, low effort. No financial
fixture, truth, business case or mutation. First reader probe passed; first
review probe failed with provider HTTP schema rejection at `evidence_ids`:
`uniqueItems` is not permitted. Exact private schema/streams were retained.
Failure handling then exposed a Python circular diagnostic reference. Both
defects were fixed before financial integration; no business evidence was lost.

The native schema removes the unsupported keyword; distinct IDs remain an
explicit prompt/Python constraint. No aliases or business selection repair.
The [official Structured Outputs guide](https://developers.openai.com/api/docs/guides/structured-outputs)
documents the supported subset and strict required/closed object behavior;
the exact uniqueItems rejection is established by the local live provider log.

Second probe campaign: **10/10** contracts/tasks passed, **11** actual calls,
**80.93918638900504 s**. Reader, independent review, every one of seven action
types and real model repair of deliberately obsolete focus. Repair took two
CLI calls total, recorded `$.issue_id` and `state_mutated=false`. See
[machine-readable summary](EARLY_PROTOCOL_PROBE.json). These were dirty-tree
engineering probes, not frozen DEV financial-quality runs. Private outputs:
`scratch/energy_billing_protocol_probe_01/` and `_02/`; raw files 0600,
invocation directories 0700. No real customer data was used.

## Software checks

- New boundary/atomic evidence tests: **35 passed** in 3.80 s (two workers).
  Includes all actions, malformed/duplicate/nonfinite JSON, exact paths,
  rejected action no mutation, one repair/exhaustion, provider distinction,
  schema error diagnostic serialization, private permissions, partial atom
  quarantine, native spans/source mutation and duplicate label identity.
- Configured Ruff passes, configured mypy passes **23 source files**.
  Configuration now explicitly includes the new Billing modules/probe/tests.
- Existing Energy CLI reproduced the monthly example in ignored scratch:
  **611850 kWh**, **107073.75 EUR**, candidate-only findings and correct
  monthly resolution limitation.
- Existing Rental deterministic benchmark **15/15** and privacy **19/19**,
  with zero false blocks/unsafe passes in the latter. They are scripted
  software regressions, not live Billing accuracy measurements.
- Initial full existing suite: **1411 passed, 1 failed in 576.95 s**. The
  failure `test_correct_negative_abstention_is_not_counted_as_attribution_or_quantification`
  refused untracked engine files created while that suite was running. This
  run was not isolated from development and is not a clean baseline proof.
  The integrity check remains unchanged. Clean frozen validation is required
  and will be recorded separately; no test is skipped or weakened.

## Current limits / next evidence

Native evidence binder preserves independently valid atoms and marks invalid
material atoms for a local root issue. Quotes/hashes/spans prove source binding,
not semantic correctness or contractual authority. Source snapshot/parser
replay remains the required upstream boundary. Binder alone cannot make a
case ready, and existing Energy/Rental entrypoints are unchanged.

No financial calculation, minimal state, authority/readiness, report, PDF,
real-case investigator action, DEV/holdout quality run or human-time measurement
is claimed yet. Gates B–E remain open; Gate A still needs actual source-to-model
PDF integration. The architecture checkpoint defines all fifteen requested
planning artifacts, and the complete Goal remains active.

## Clean frozen check and native PDF checkpoint

After commit `952418424edf0a2d22fd90319694c5464502effd`, a separate detached
clean worktree ran the entire suite unchanged: **1447 passed in 657.73 s**,
including the unchanged HOLDOUT integrity checks, Rental and Energy tests.
Development continued only in the Billing branch worktree. This corrects the
earlier mixed-worktree validation context; no integrity control was weakened.

New source-local reader integrates the existing source inventory and actual
PDF parser with the direct model contract. Runtime binds immutable receipts;
replay checks current source bytes, parser context and each quoted span.
Only the selected source is a reading dependency; mutating another blob fails
its own consumers while preserving the independent valid reading. Native data
survives alongside explicitly retained visual/parser gaps. No visual semantic
extraction or complete client entrypoint is claimed.

First actual-PDF live run produced independent observations but exposed a
prompt defect: the generic provider demanded evidence IDs even in the reader
schema that lacks such a field. Models recorded that impossible requirement as
a limitation. Provider now applies the constraint only to schemas containing
evidence IDs. Reader instructions also distinguish source-local ambiguity from
normal fields supplied by a different document type. No returned business
values or durable source quotes were silently rewritten.

Second live run: two actual synthetic PDFs, two independent source readings
each, **four calls**, **110.79775415998301 s**. Accepted observations per reading:
**12, 16, 16, 15**; **zero quarantined rows**, **zero protocol diagnostics**.
Invoice identity/PDL/supplier/currency/period/quantity/billed amount and contract
identity/PDL/supplier/price/unit/effective dates/rounding were observed in both
passes. The first invoice primary included a charge-meaning observation that
the independent pass omitted; this is visible and must be resolved at local
semantic review, not hidden by declaring complete agreement.
[Native gate summary](EARLY_NATIVE_GATE.json) preserves source and receipt hashes.
Its dirty-tree engineering run is Gate A source-binding evidence, not frozen
financial DEV quality. Valid-atom preservation under an injected invalid
sibling is established separately by actual-PDF deterministic tests.

Typed Period/ConsumptionLine/TariffTerm and Decimal primitives now exist.
Units are explicit Wh/kWh/MWh and EUR per the respective energy unit; power
and FX are refused. Exact cents reject silent rounding of billed amounts.
Per-line half-up/half-even is explicit, caller Decimal context cannot alter
results, and an independent rational reference checks arithmetic. These
primitives do not approve authority or produce a final supported case.

Latest targeted tests after the final benchmark typing annotation:
**66 passed in 6.12 s**; configured Ruff passes and configured mypy passes
**27 source files**, including the entire Billing benchmark directory.
The full 1447-test clean result belongs specifically to `9524184`, not the
later reader/money checkpoint. Full latest-code validation remains due before
financial benchmark campaigns. Gates B–E, DEV, holdout and pilot remain open.
Continuation and all twelve acceptance cases: [WORK_PLAN](WORK_PLAN.md).
