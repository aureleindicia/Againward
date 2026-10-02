# V2 investigator → deterministic calculation checkpoint

Starting engine: `ed067e14002ba3990fa78b23b6ddf26fdb21e966`.

The supplied `energy-analyzer` directory is the dirty `main` worktree. Its
prospecting changes were inspected and preserved. The existing clean
`againward-first-client` worktree owns `release/first-rental-client-pilot`; it
was advanced from `1d2437c` to the supplied remote checkpoint by fast-forward.
No uncommitted investigator prototype was present in either inspected worktree.
The existing graph, reader, structural repair, local reviews, claims, exact
relations, frontier, readiness prerequisites and adapter remain authoritative.

## Explicit entrypoint

```sh
python -m againward.domains.rental.case_investigator GRAPH_OR_BATCH.json \
  --root DOCUMENT_ROOT --model MODEL --max-turns 64
```

`input` is a replayable V2 graph or an already authorized immutable SourceBatch.
This command does not authorize new client data or bypass source/privacy gates.
It leaves legacy entrypoints executable and never synthesizes an adjudication
package. It produces a calculation checkpoint, not a report or delivery approval.
The Python `investigate` API additionally accepts a callable action provider for
controlled integration tests; production defaults to the existing bounded Codex
invocation boundary. Document content remains untrusted data.

## Issue loop

1. Replay the incoming graph against the actual sources and invocation receipts.
2. Derive current open issues from materiality and financial prerequisites.
   Persisted issue flags cannot hide stale decisions. Missing prerequisites have
   stable runtime gap IDs; they are not model-authored facts.
3. Focus one issue. Unread/partially read sources precede case-wide missing
   containers. Context contains relevant atoms, containers, pending claims,
   current reviews, and relationship alternatives, plus small issue summaries.
   Observations are capped at 128 with explicitly listed omitted IDs. Nearby
   atoms or the same source's atoms can help a grouping/missing-field issue.
   No dossier-wide proposal or source-text dump is sent to the investigator.
4. Request one action. The detached context cannot mutate canonical state.
   Python checks the closed response, 32 kB action limit and issue-local scope,
   binds prerequisites, and invokes existing reducers/validators transactionally.
5. Feed the accepted/rejected receipt back on the next turn. Rejection codes are
   machine-readable. Protocol/scope rejections are retained in the run transcript;
   structural/claim proposals use their existing replayable graph journals.
6. A proposed claim exposes its pending review issue before a repeated commercial
   proposal. The investigator explicitly requests its independent original-source
   MODEL review. Actual native/pixel bindings and source-local prerequisites are
   verified by the existing review runner, not by a supplied role flag.
7. Continue from updated state or stop. `INSPECT_ISSUE` selects another current
   gap; it cannot settle it. `MARK_UNRESOLVED` stops without changing facts.

Bounded actions reuse `DECLARE_OCCURRENCE`, `ATTACH_OBSERVATIONS`,
`REPLACE_OBSERVATIONS`, and existing claim proposals. Runtime operations are
`REQUEST_REVIEW`, `REQUEST_REREAD`, `INSPECT_SOURCE` (exact native window of at
most 4000 characters), `INSPECT_OCCURRENCE`, `INSPECT_ISSUE`,
`REFRESH_RELATIONS`, `MARK_UNRESOLVED`, and `PROPOSE_READY`. There is no writable
READY, HUMAN, arbitrary patch, financial value or relationship invention API.
Exact relationship derivation remains Python-owned. Unsupported non-exact links
remain unresolved; legacy adjudication is not a fallback.

Scoped atomic rereads retain their inspected unit locations in the invocation
receipt. Replay revalidates scope against original units. The graph journal
records inspected and required unit sets. The frontier blocks
`SOURCE_PARTIALLY_READ` until their union covers the source, preserving historical
unscoped reading journals. An empty locations request is allowed only before a
source has observations; subsequent rereads require explicit unit locations.
Inspection is contextual evidence, not an imported fact or semantic approval.

## Progress and budget

Defaults: 64 turns, 240 seconds per model invocation, five consecutive turns
without new evidence/resolution, four visits to the same effective semantic state,
and two identical rejected actions for the same issue/code.

The progress fingerprint excludes receipt chronology, invocation IDs, equivalent
reading origins, occurrence revision counters, and claim explanation churn.
It includes source-bound atoms, occurrence identity/fields, effective observation
dispositions, current review verdicts and deterministic gaps. Progress requires
new source-bound evidence, a new supported decision, a removed prerequisite gap,
or a genuinely new exact inspection delivered to the next turn. An accepted
proposal or repeated positive review alone cannot reset stagnation indefinitely.
Inspection results are tracked separately from graph mutations.

Explicit stops include turn budget, repeated semantic state, repeated rejection,
no evidence/resolution, genuine material ambiguity, provider failure, evidence
failure and deterministic engine refusal. Every successful transition is already
committed before a later provider failure. Failure returns no calculation or
canonical-case amount and cannot erase valid observations. The content-addressed
run transcript retains turns, feedback, before/after hashes and model-call counts
by investigator/reader/reviewer role, plus elapsed time.

## Calculation gate

`PROPOSE_READY` calls `evaluate_readiness`: replay plus current deterministic
prerequisites. `CASE_NOT_READY` includes the actual gaps. It never mutates the
graph or settles an issue. Only `SUPPORTED_DETERMINISTIC` authorizes the existing
`load_graph_case` adapter. Canonical RentalCase validation still applies. The
unchanged `reconcile` engine performs money/calendar/pricing arithmetic.
If projection fails or a reconciliation group has limitations or no deterministic
difference, the checkpoint is `UNRESOLVED`; case and calculation outputs are null
and engine issues are exposed. There is no positive fallback or conditional mode.
The engine's candidate discrepancy remains distinct from recoverability or a
client-approved claim.

## Generic proof and tests

The synthetic integration starts from an empty graph and two original native
sources. Actual atomic reader binding, structural/claim reducers, independent
review receipts, readiness, projection and reconciliation run in the same loop.
The action/reader/reviewer model responses are scripted. The resulting invoice
is EUR 39.00, the contractual expected ledger is EUR 34.00 and the documentary
difference is EUR 5.00 with no group limitation. Full evidence replay reconstructs
the same graph and its persisted head names the final snapshot. This proves the
software connection, not live-model accuracy on unseen documents.

The new investigator tests cover one-action review resolution, rejected action
feedback/correction, local repair and retained observations, authentic local
prerequisites, ambiguity, early/late provider failure, all progress budgets,
forged HUMAN/READY/evidence attempts, detached context, repeated equivalent
reviews, material and independently disposed non-material atoms, source-local
inspection, cross-source scope, selecting another issue, scoped coverage and
financial engine refusal. Existing graph tests retain actual-pixel review,
local staleness, unrelated mutation, stale-source, foreign-citation, ambiguous
relationships, material frontier and reducer replay coverage.

Targeted V2 suite: **140 passed in 135.22 seconds**. Full regression results
will be recorded after the clean-engine run. Before commit: repository and explicit V2 Ruff pass; configured mypy (18 files) and
explicit V2 mypy (12 files) pass; Rental benchmark 15/15; privacy benchmark 19/19;
`git diff --check` passes. Benchmark outputs/logs are local temporary artifacts.

## Next milestone

No CASE A/B campaign or final report was run or generated. A/B and HOLDOUT
fixtures were not changed, and no financial oracle was used for implementation.
Before the first authorized DEV A×1/B×1, freeze the clean validated engine and
choose the live model/budgets/source intake for this explicit V2 entrypoint.
Post-calculation adversarial source-backed QA and bounded issue reopening,
report/package lifecycle integration and live document performance remain later
Goal work. No delivery readiness or V2 Goal completion is claimed here.
