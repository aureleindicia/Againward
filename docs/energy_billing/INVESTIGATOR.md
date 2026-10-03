# Local Investigator checkpoint

## Entry and ownership

Latest clean engine `81497e9` passes **1549 full tests** and a fresh actual-model
blank-state path through this runtime to calculation/internal PDF: 16 calls,
11 turns, 32 atoms, two occurrences, one relation, three reviews, zero repair.
The earlier usage-limit stop below is preserved and explicitly continued in four
new calls. Both outputs pass 22 independent post-terminal checks on the known
synthetic one-line truth. See [the measured record](FROZEN_INVESTIGATOR_RECOVERY.json)
and [continuation details](PROVIDER_CONTINUATION.md). Material frontier/conflicts,
post-calculation model QA and corpus quality remain open.

`againward.domains.energy_billing.loop.investigate(root, model, transport, budget)`
starts from an existing initialized and privacy-approved SourceBatch. It is an
internal callable, not a real-client intake command. No source approval, HUMAN
review or delivery authorization is synthesized.

The small agenda derives one local missing source/occurrence, missing or stale
facts review, missing GOVERNS relation, authority review or final readiness root.
Python orders immutable identities, never filenames. The model chooses one
action; the runtime does not impose the earlier fixed declaration/link script.
Related evidence, occurrences, relations, quarantine, local reviews, native
source handles and the previous focused rejection/inspection are supplied.
Unrelated source observations remain outside that action context.

All eight action forms are explicit: DECLARE_INVOICE, DECLARE_TARIFF,
LINK_TARIFF, REQUEST_REVIEW, REQUEST_INSPECTION, REQUEST_REREAD,
MARK_UNRESOLVED and PROPOSE_READY. Original native inspection returns one
source/hash/location-bound unit, limited to 8000 characters. Re-reading is
source-local, original-only, bounded by the existing 32 units / 40000 characters
reader; it sees no earlier candidate facts. Review always uses the separate
independent original-source boundary. Python alone commits and calculates.

Wrong review target kinds and unlisted inspection locations are checked inside
the model boundary, with one protocol repair and no domain mutation. Business
missing fields/conflicts remain causal local rejections rather than becoming
protocol errors. The provider now preserves original causal metadata when
passing a nonprotocol exception through its boundary.

## Budgets and interruption

Defaults: 24 turns, 32 actual calls, 4 source readings/re-readings, 3 stagnant
turns, 4 visits to a semantic state, 2 identical causal rejections, 4 total
protocol repairs, 900 active wall seconds; one repair per individual boundary.
The budget includes the first source readings and independent review calls.
Per-call timeout belongs to the supplied transport (CLI default: 90 seconds).
The wall deadline is checked before and after each transport invocation; an
in-flight invocation is bounded by its transport timeout.

A separate process lease prevents concurrent investigators. Each call is
reserved in a hashed runtime checkpoint before invoking the provider; each
domain transition still uses the existing short artifact transaction. A long
transaction is deliberately avoided because staged writes would not survive
an interrupted model call. The runtime reserves pending turns and preserves
all counters. Identical terminal state returns its recorded result without new
calls. Runtime-v2 permits at most two explicit provider continuations under the
original lifetime budgets, preserving prior hashes/failures and focused feedback;
see [provider continuation](PROVIDER_CONTINUATION.md). External state change may permit continuation under the same lifetime
budgets; changing model or budgets is refused. An interrupted pending turn is
explicit RUNTIME_INTERRUPTED and needs operator inspection; it cannot silently
rerun a remote call with unknown outcome.

Semantic progress requires new valid atoms/objects, added occurrence evidence
or newly supported current local reviews. Receipt/wording churn, inspections,
negative reviews, novel invalid rows and weakened support do not count.
Review coverage, date conventions and authority/disposition semantics are part
of the fingerprint: clearing an INCOMPLETE coverage gap counts; rephrasing the
same SUPPORTED review does not. A dedicated regression covers two stagnant
inspection turns followed by coverage resolution and successful calculation.
Fingerprint changes alone are insufficient: a stream of different invalid
rows changes quarantine while the stagnant-turn budget still stops it.
PROPOSE_READY cannot override an unresolved material prerequisite.

## Evidence and reproducible live command

[Actual action probe](INVESTIGATOR_ACTION_PROBE.json): all eight forms plus a
bad-focus repair pass with `gpt-6.1-sol`, 9 tasks, 10 CLI calls,
99.0310650060128 seconds. This dirty-tree nonfinancial engineering probe tests
provider compatibility, not financial correctness or full Investigator quality.

Deterministic integration covers source → local actions/reviews → calculation,
a missing original quantity recovered through re-reading, premature READY,
wrong review target repair, repeated protocol failure, provider timeout,
repeated business rejection, local inspection, invalid-row churn, all lifetime
limits, durable interruption, concurrent leases and explicit indexed-tariff
abstention. Full latest-code regression results are recorded after completion.

Latest focused suite: **118 passed in 24.22 seconds**; Ruff and configured mypy
pass (36 files). The first uncommitted full pass, before the coverage-progress
correction, recorded **1526 passed, 2 failed in 652.66 seconds**. Both failures
are unchanged HOLDOUT guards refusing a working tree different from HEAD, in
physical-expertise and signal-intelligence preparation. They are retained and
not skipped or weakened. A fresh full suite on the clean committed checkpoint
is required to verify the final code and both integrity guards.

## Frozen checkpoint outcome

Clean engine `0d753490f8c4cf798ea0e8bf5eccc572e0dee03b` passes **1530 tests
in 671.59 seconds**, including both unchanged HOLDOUT integrity guards. The
earlier dirty-tree failures remain historical context, not skipped controls.

Its actual-model gate reaches 33 bound observations, zero quarantine, two
occurrences and two independent supported facts reviews. The model chooses
source inspection, re-reading, declaration and independent review through the
real local action schema. At the missing GOVERNS relation, the thirteenth CLI
invocation fails with an explicit usage-limit message and no response. Nine
turns are reserved; eight complete. No relation, calculation or PDF is created.
There is zero protocol repair. Valid evidence, both occurrences and both
reviews survive; termination is MODEL_PROVIDER_FAILURE, not UNSUPPORTED.

The run takes 278.92075755499536 seconds; exact timing and hashes are in
[the frozen gate record](FROZEN_INVESTIGATOR_GATE.json). It does not prove a
complete Investigator financial E2E. CLI usage availability is external state;
the observed retry-time message is not an account-entitlement guarantee.
Full-suite and live-gate timing overlap, so neither is an isolated benchmark.

Frozen actual-model gate, fresh output and clean SHA required:

```sh
python -m benchmarks.energy_billing.investigator_gate \
  --model gpt-6.1-sol --output scratch/eb-investigator-01
```

The known synthetic PDFs contain only source facts, not expected answers.
All decisions in this gate use the real model; raw evaluation responses remain
private. Terminal calculation may feed the existing internal scoped PDF.
Post-calculation QA remains NOT_PERFORMED and delivery remains
INTERNAL_REVIEW_REQUIRED. Financial DEV/HOLDOUT accuracy is not established.

## Remaining full Goal work

The subsequent [local disposition implementation](MATERIAL_DISPOSITIONS.md)
adds independent material-quarantine recovery, supersession/irrelevance decisions
and a preserved material inventory. Its actual-model acceptance measurements
remain separate from the earlier thin checkpoint described above. Competing
authority and multi-PDL ambiguity must abstain without arbitrary selection.
Post-calculation objections need source-bound independent receipts, local
reopening/resolution, the same lifetime budgets and at most two reopen cycles;
a later PASS must never erase a pending objection. Subscription, simple bands/
periods, dated public taxes and credits remain separate tested expansion work.
See [the unchanged full-scope continuation](WORK_PLAN.md).
