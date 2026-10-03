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

The subsequent terminal record on the same clean implementation SHA `9daed77`
passes **1576 full tests in 720.10 seconds**, including the unchanged HOLDOUT
integrity guards and existing Rental/Energy regressions. See
[exact synthetic measurements](FROZEN_MATERIAL_DISPOSITIONS.json).

Actual native CLI probes pass 3/3 in four calls, including one precise invalid
proof-location repair. The added-decorative-source run reaches calculation/PDF
with 33 bound atoms, one independently supported source disposition, two
occurrences, one relation and three reviews: 19 calls, 13 turns, zero repairs,
388.34792525399826 seconds. Original financial bytes, facts, authority, exact
16500/19208/2708-cent result and complete 36-item frontier pass independent checks.
The internal four-page PDF's pages 1/4 were visually inspected; the raw technical
proof dump still needs final Codex synthesis.

The competing accepted-price run preserves 50 atoms, both tariff candidates and
three independent facts reviews, then stops UNRESOLVED with no amount or report:
19 calls, 13 turns, zero repairs, 382.35501609998755 seconds. The original contracts
have identical identity/effect periods and different prices, without precedence.
Independent complete-case abstention checks pass.

The two-PDL run inspects the combined unallocated invoice and abstains in two
calls/two turns, 23.46047146298224 seconds. It creates no financial claim and makes
no arbitrary PDL selection. Its **complete-state evaluator remains failed**:
zero atoms/occurrences were constructed and the other original was not read.
This verifies early abstention only; it does not prove complete ambiguity state
or full material inventory. The runtime focus remains SOURCE_NOT_READ even though
the terminal explanation identifies the actual allocation ambiguity. Structured
cause/state coverage remains further acceptance work.

The private evaluator is post-terminal, uses manual synthetic truth, independent
Decimal and direct original PDF spans/hashes; the shared pypdf parser is a known
limitation. Its reading-summary API assumption was corrected from actual artifacts;
no pipeline code or frozen input changed. Truth never entered model prompts.
Full regressions and live gates ran concurrently, so timings are not a controlled
performance comparison. Invalid-material-atom recovery currently has scripted
original-source integration plus real native contract evidence. The subsequent
[explicit material-fault run](FROZEN_MATERIAL_RECOVERY.json) adds a frozen full
live recovery scenario on `68ca673` (documentation-only changes from `9daed77`).

One quantity row with an invalid `page:999` reference was deliberately appended
**after** the real reader returned. Its actual raw response, scalar, quote and
all valid siblings were preserved. The real Investigator inspected the source,
obtained an independent local rejection, then refined it to an explicit same-field
replacement after the invoice facts reviewer abstained. Separate facts/authority
reviews and Python readiness then reached the exact calculation/internal PDF:
34 bound atoms, one preserved material quarantine, two occurrences, one relation,
three current reviews, a complete 37-item frontier, 23 calls/15 turns, zero repairs
or provider failures, 476.91158833599184 seconds. Independent original-span,
processed/original response hash, selected quantity, money, history and frontier
checks all pass. This is controlled recovery evidence, not a naturally occurring
reader-error rate, a DEV/HOLDOUT result or post-calculation QA.

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
