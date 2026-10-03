# Explicit provider continuation

The runtime-v2 checkpoint adds `resume_provider_failure=True` to the internal
`investigate` callable. Default calls still return a recorded provider failure
without making another remote call, even if external evidence has changed.
Continuation admits only a terminal MODEL_PROVIDER_FAILURE. A pending invocation,
protocol failure, business abstention or exhausted continuation allowance cannot
be replayed through this option.

At most two explicit continuations are permitted in the runtime lineage. Original
model, turn/call/reread/protocol limits and active wall time remain unchanged.
The previous terminal receipt hash, failure, schema, state hashes and counters
are recorded before another turn. Completed steps, diagnostics, valid evidence,
independent reviews, stagnation and visited-state counts survive. Last focused
inspection/rejection feedback is recovered from the completed step.

Legacy runtime-v1 receipts are verified against their original hash/model/budget
before an additive migration. A default read of a terminal legacy runtime leaves
its bytes intact. Explicit continuation adds only the new two-resumption budget
and lineage field; no original resource count is refunded. Active wall seconds
exclude the external interval during which the runtime was stopped.

## Provider diagnosis

The CLI echoes the whole input in stderr. Classification removes the exact input
and examines only consecutive terminal ERROR lines. A usage-limit message becomes
MODEL_PROVIDER_FAILURE / USAGE_LIMIT; a terminal output-schema rejection remains
MODEL_PROTOCOL_FAILURE / SCHEMA_REJECTED. Unknown errors and unrecognized or
truncated echo formats conservatively remain provider CLI_EXIT. Raw strings are
not copied into public diagnostics; invocation, stream and response hashes remain
available. A document containing schema-error or quota text cannot by itself
change the failure category. There is no automatic retry or model substitution.

## Private evaluation command

```sh
python -m benchmarks.energy_billing.investigator_gate \
  --model gpt-6.1-sol \
  --continue-from scratch/eb-investigator-01 \
  --output scratch/eb-investigator-continuation-01
```

The command requires a clean current engine and a stopped frozen synthetic gate.
It verifies the prior result/runtime/state/source bindings under a process lease,
then copies the snapshot byte for byte into a new private output. Original
result, sources and responses are retained. Symlinks, model changes, nested
outputs and real privacy-bound workspaces are refused. Production cases must
continue inside their original authorized workspace.

The record labels this as a preserved continuation, with origin/current engine
SHAs, origin result and snapshot hashes, original counters, lifetime counters
and new calls/turns. It is not a fresh single-engine financial E2E or DEV/HOLDOUT
measurement. Subsequent continuations must use the latest result in the same
lineage; branching from an earlier synthetic snapshot is a separate experiment,
not a way to extend a case's lifetime budget.

## Verified software evidence

Billing-focused suite: **137 passed in 28.93 seconds**; Ruff passes and configured
mypy passes on 36 source files. New tests cover exact source-echo counterexamples,
usage-limit/schema/unknown errors, explicit-only continuation, both supported
reviews and atoms surviving, all consumed calls retained, the two-resume ceiling,
active wall and call exhaustion, pending-call refusal, legacy migration, focused
inspection/stagnation preservation, immutable original snapshot and refused
changed result/model. Scripted transports prove engineering invariants only.
Clean full regressions and actual-model continuation are measured separately.

This does not complete material dispositions/conflict recovery, post-calculation
QA, charge expansion, frozen DEV/HOLDOUT or client delivery. See WORK_PLAN.md.
