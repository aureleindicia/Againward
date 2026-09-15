# AGAINWARD architecture R&D — 2026-09-16

## Scope and baseline

Starting commit: `c27f261cd560cb005dd8d9367c8cf6567ebfa155`. Work is isolated on
`rnd/architecture-autonomy-20260916`; pre-existing prospecting changes in the original
worktree are excluded. No client case or external service was used as an experiment.

Baseline: **516 tests passed in 132.20 seconds**. Reproduced the 90-day, seed-42
`factory_variable` demo with 8,639 input rows, using the existing generator and CLI.
The basic independent unit check returned 50 kWh for two quarter-hours at 100 kW.
Ground truth remains separate and was not used for architectural decisions.

The audit followed these boundaries and their integration tests:

| Boundary | Assumption examined | Disposition |
|---|---|---|
| IO → Reading → analysis/toolbox | Typed quantities and temporal normalization precede inference | Retained; numerical regression suite and reproduced report |
| Context store → EvidenceDataset → query protocol | Immutable persisted snapshots plus bounded neutral queries | Retained; tightened response/handle binding and accounting |
| Codex → query budget | 16 attempts are a suitable universal stopping condition | Falsified; useful work, rejection allowance and continuation now separate |
| Questions → selection | Same hypothesis means same question | Falsified by complementary partitions |
| Questions → lifecycle | Optional answers cannot require a mandatory review | Falsified; all answers invalidate the current analytical decision |
| Lifecycle → persistence | Independent file replacements provide a coherent update | Falsified by interruption between question and state writes |
| Lifecycle → stopping | `close-budget` can clear a pending blocking request | Rejected; it contradicted the documented STOP contract |
| Attribution ledger → assessed asset | Declared information is weaker than a verified field anchor | Retained; existing adversarial tests exercise the claim ceiling |
| Findings → delivery | A session reference alone establishes persisted evidence exists | Falsified; response files and snapshot binding are now verified |
| Economics/value map → report | Quantities must come from deterministic provenance; human review binds semantics | Retained; existing domain and delivery tests |
| Orchestration → model | The model should choose tests and interpret uncertainty | Retained; no automatic claim or cause selection added |

The repository's workflows, schemas, CLI adapters, report boundaries, privacy gates,
benchmark harnesses and relevant skill were reviewed. Historical Download handoff
paths were inventoried; old clone code and client contents were not imported.

## Counterexamples and implementation

`python -m benchmarking.architecture_probe` runs the same synthetic observations
before and after. Results are committed as `before.json` and `after.json`:

| Behavior | Before | After |
|---|---:|---:|
| Pending blocking question can reach finalizable through budget closure | yes | no |
| Nonblocking answer requires resume/review | no | yes |
| Independent questions preserved for one hypothesis | 1 | 2 |
| Exhausted evidence session remains readable after another rejected call | no | yes |
| Two quarter-hours at 100 kW | 50 kWh | 50 kWh |

The old tests explicitly endorsed the premature closure and optional-answer shortcuts.
Those expectations were replaced, with tests preserving the legitimate answered-and-reviewed
closure path. Failed tests were not bypassed by weakening the gates.

### Recoverable case artifacts

`energy_mvp/artifact_store.py` provides a common JSON store with a per-case process lock,
staged writes, a durable redo journal, validated recovery and shared locks for canonical
lifecycle reads. The commit point is the fsynced journal; an interruption afterwards is
completed, not silently rolled back or interpreted as a second answer.

Migrated callers: lifecycle transitions; evidence response/session/trace; question adapters;
attribution answer/ledger/assessment. Repeated bespoke write logic was removed from these
paths. JSON remains canonical; no duplicate SQLite state is introduced. Existing valid
artifacts migrate on their next write, preserving IDs, histories and responses.

Fault injection after the journal and after each of the two question/state materializations
recovers the same waiting state and request. Invalid batches produce no partial answer.
A second process is refused while an update is active. Conflicting external edits cause
recovery to refuse rather than overwrite. The read-only status exposes recovery explicitly.

This is not a universal database transaction around all repository operations. Privacy
promotion/purge and rendering into outputs retain their existing safeguards. A custom script
that ignores locks is outside cooperative isolation. POSIX rename/fsync and working local
filesystem semantics are assumptions, not claims about arbitrary Android shared storage.

### Continuation instead of fixed epistemic stopping

Query sessions retain the initial 16 **successful** calls and separately bound rejected
attempts at eight. Resource use is never reset. Additional calls require a recorded analyst
checkpoint with fresh successful query references, unresolved hypotheses, next tests and
decision impact. Global hard resource ceilings remain. Semantic repeats of successful tests
are rejected; failed tests do not poison retries. Common raw-slice defaults and field order
are normalized for repetition detection. Deliberately closed or failure-exhausted sessions
cannot be reopened through a continuation.

Client clarification retains two cycles initially and three questions per batch. A completed
answer/reanalysis cycle may justify one more cycle using new answer references and useful,
nonduplicate candidates, up to an eight-cycle resource ceiling. It never bypasses waiting,
review, privacy or human approval. Corrections must target the latest active answer.

These ceilings are engineering bounds, not experimentally calibrated optimums. Decision
relevance remains a model judgment. An analyst can misuse novel but unhelpful tests up to
the ceiling; the implementation does not pretend to estimate a reliable expected value of
information from prose. No trained confidence estimator or speculative autonomous planner
was introduced.

### Question selection: ablate, falsify, improve

`python -m benchmarking.architecture_evaluation --output RESULT.json` compares three
policies over 30 seeded synthetic problems with three independent information dimensions:

| Policy | Mean information retained (bits) |
|---|---:|
| Historical subject-only deduplication | 0.980229 |
| Independent top-three ranking | 2.466667 |
| Conditional selection | 3.000000 |
| Exhaustive reference optimum | 3.000000 |

This favorable construction was then attacked using 50 randomized partitions. The first
greedy prototype missed the exhaustive optimum in **16/50** cases, by up to **1/6 bit**.
It was consequently replaced for small comparable sets by exhaustive subset selection.
Production uses exact selection only for ≤12 candidates with the same complete hypothesis
model, scope and equal utility weights; heterogeneous/larger sets remain greedy. The final
JSON records the greedy ablation and final production gaps separately.

The utility model still assumes uniform hypotheses and declared answer partitions. It is
not a calibrated probability model, causal discriminator, or monetary EVSI. Unmapped
questions retain the documented heuristic and 0.05 threshold. Exact optimization of an
imperfect model is not evidence that the underlying questions are good.

### Budget episodes

Synthetic episodes requiring 4, 12, 20 and 40 distinct queries complete 4/12/16/16 under the
fixed 16-call policy, and 4/12/20/40 with checkpoints. The latter require 0/0/1/6 continuations;
the 40-call episode returns only 40 rows. Crucially, the harness supplies the needed episode
length: **this demonstrates removal of premature protocol stopping, not improved LLM accuracy**.

### Storage alternatives and measured cost

The same harness compares three metadata writes with per-file atomic JSON, journaled JSON
and a SQLite transaction over 20 repetitions. SQLite is faster than journaled JSON on this
device. See `experiments.json` for measured medians and maxima; these timings vary with device
load. The SQLite prototype does not export JSON artifacts.

The production choice is journaled JSON because the current model/tool interface reads and
writes standalone artifacts, and a SQLite authority plus JSON projections would require a
larger ownership migration. It fixes the demonstrated recovery failures with measurable
latency overhead. SQLite remains the leading alternative if state size, concurrent use or
metadata update frequency make that overhead material; JSON was not chosen for speed.

### Evidence integrity

Resource counters are checked against successful records and charged failed computation.
Response bytes include the response hash. Session loading checks successful IDs, counters,
handle hashes, dataset ownership and valid status. Finding IDs must be unique, and each
handle must accompany its owning query. Both finding validation and delivery re-open the
response files and verify their digests and dataset/session binding.

Integrity hashes detect drift; they are not signatures against a malicious local editor.
A valid numeric reference does not establish that a natural-language causal claim follows
from it. This semantic boundary deliberately remains Codex's adversarial review and the
human reviewer's responsibility.

## System performance

`run_stage4_performance.py` was rerun at 10,000, 100,000 and 500,000 rows on Termux.
`performance.json` preserves timings and Python allocation peaks. The 500,000-row snapshot
is 142,117,840 bytes, with 861,990,667 peak traced Python bytes. Loading took 148.44 seconds;
snapshot build 47.08 seconds, serialization 20.37 seconds. The boundary query took 0.77 seconds.

This confirms that ingestion/snapshot representation, not neutral query dispatch alone,
is the large-case bottleneck. These measurements do not establish a speed regression from
the earlier Stage 4 record: device load differs and tracemalloc adds overhead. No claim of
analytical or ingestion speedup is made. The large-row benchmark is batch capacity, not a
recommendation for repeated interactive loading on a constrained device.

## What deliberately survived

- Deterministic physical quantities, temporal validation and refusal of ambiguous units.
- Neutral evidence tools and analyst ownership of hypotheses and semantic decisions.
- Candidate signals as starting points, including honest zero-candidate limitations.
- Minimal Evidence's explicit unknown candidate and declaration/field-anchor separation.
- Signed energy differences distinct from positive residual exposure and recoverable savings.
- Economic source binding, action relationships and double-counting safeguards.
- Privacy-first workspaces, human approval and report semantic hashes.
- The six-operation query interface: arbitrary executable query text was not necessary.
- No new model API, network telemetry, SaaS infrastructure, or multi-agent runtime.

## Sources and how they influenced the work

[SQLite's atomic commit design](https://www.sqlite.org/atomiccommit.html) informed the
failure model: separate atomic replacements are insufficient, and readers need isolation.
Its journal/locking discussion is a reference, not a claim that this smaller JSON store
provides all of SQLite's guarantees.

[Budget-Aware Tool Use Enables Effective Agent Scaling](https://arxiv.org/abs/2511.17006)
motivated measuring quality/cost tradeoffs rather than interpreting larger budgets as
automatically better. Its results do not validate our energy workflow or chosen ceilings.

[Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)
supports keeping explicit tool contracts and testing task outcomes before adding orchestration.
Here the concrete counterexamples, not the literature alone, justified implementation.

## Unresolved R&D

1. Real-case or blinded model evaluation of continuation checkpoints, question burden and
   final decision quality. This work has no calibrated client-outcome evidence.
2. Decision-critical contradiction resolution still depends on the documented review;
   recording an explicit contradiction is not automatic semantic reconciliation.
3. Complete prose-to-calculation claim binding across ad hoc scripts and all report formats.
4. Streaming or indexed large snapshots; compare SQLite column projections and compact
   row storage against current read latency, memory and context fidelity before migration.
5. Calibrate the unmapped-question score and stopping thresholds from authorized, reviewed
   pilot metadata, without retaining confidential case content.
6. Cross-directory transactional report publication and privacy operations, if failures
   demonstrate a need beyond the existing semantic hashes and fail-closed gates.

## Validation record

The full pre-commit suite found the expected legacy answer-shortcut test and two HOLDOUT
integrity guards requiring committed engine code. The shortcut expectation was corrected;
the HOLDOUT guards remain intact. Final committed-suite results and the remote commit are
recorded in the completion section after validation.
