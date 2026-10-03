# Local independent evidence dispositions

`REQUEST_DISPOSITION` proposes one source/atom/quarantine decision. It is never
a durable approval action. A separate `DISPOSITION` model call reads the complete
bounded original sources without a previous verdict, and Python binds its quotes
to exact native spans before a receipt can enter the event journal.

Supported decisions: `SUPERSEDED`, `DUPLICATE`, `REJECTED_WITH_EVIDENCE`,
`IRRELEVANT`; `UNRESOLVED` or an independent negative verdict remains a material
blocker. Every original observation, rejected row and earlier occurrence remains
in history. A replaced candidate becomes inactive; a refreshed identity cannot
merge a disposed citation back into its financial inputs.

Python refuses cross-source/field atom replacements, financial facts marked
decorative, source dismissal for one bad atom, unequal duplicate scalar facts,
different supplier/PDL/currency supersession, stale originals/dependencies and
replacement chains/cycles. Source supersession requires an independent judgment
of an explicit accepted change. Its business semantics remain model-reviewed,
not a lexical matching rule. Two plausible accepted prices or two genuine PDLs
cannot be resolved by selecting a convenient subset.

Source decisions may depend on separately resolved bad atoms. Atom decisions
never depend on source decisions. Later atom reopening invalidates its dependent
source decision. Review invalidation uses local decision meaning; wording,
receipt churn and unrelated source decisions do not count as progress.

Calculations involving dispositions include the complete inventory in
`material_frontier` and disposition receipts. Used original context remains
visible alongside selected calculation inputs. Potentially material quarantine
must be resolved individually even when its parent source is superseded.
Legacy thin states without this ledger preserve their prior shape and hashes.

## Frozen live verification commands

Pre-freeze verification: 164 Billing-focused tests pass in 40.93 seconds;
Ruff passes and configured mypy passes for 38 source files. This includes 21
original-source disposition tests and five source-scenario contract tests.
Full regression and actual-model evidence are still pending at this commit.

After targeted checks and a clean implementation commit:

```sh
python -m benchmarks.energy_billing.probe --model gpt-6.1-sol --dispositions-only --output scratch/eb-disposition-probe-01
python -m benchmarks.energy_billing.investigator_gate --model gpt-6.1-sol --scenario decorative --output scratch/eb-frontier-decorative-01
python -m benchmarks.energy_billing.investigator_gate --model gpt-6.1-sol --scenario competing_tariffs --output scratch/eb-frontier-competing-01
python -m benchmarks.energy_billing.investigator_gate --model gpt-6.1-sol --scenario two_pdl --output scratch/eb-frontier-two-pdl-01
```

Each gate starts from original synthetic PDFs and blank runtime. No action order
or financial oracle is supplied to the Investigator. The gate exit status means
report reached; unresolved cases need post-terminal abstention evaluation, not
an assumed failure or success from the process exit code. These are development
acceptance variations, not a frozen DEV corpus or sealed HOLDOUT. No post-calc QA
or human delivery approval is implied. Actual measured results are recorded
separately after the processes are terminal; the commands alone prove nothing.

Post-calculation objections, bounded reopening, charge expansion, independent
corpus scoring and commercial pilot rehearsal remain required full Goal work.
