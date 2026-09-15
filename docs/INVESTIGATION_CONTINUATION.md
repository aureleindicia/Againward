# Investigation continuation and recovery

Budgets bound resource use; they do not establish that evidence is sufficient.
Codex still chooses hypotheses, useful tests, uncertainty and conclusions. No automatic
confidence score, causal claim or recoverable saving follows from a continuation.

## Evidence queries

The initial allowance is 16 successful queries, plus 8 rejected attempts. Rejections
are audited separately. Successful repeated tests remain rejected; a failed test can
be retried after its resource constraint is corrected. The CLI trace records attempts
even after the bounded session rejection ledger fills.

When further evidence could change a material decision, Codex records a checkpoint:

```json
{
  "budget": {"maximum_calls": 20},
  "progress_query_ids": ["contrast_01", "support_01"],
  "unresolved_hypotheses": ["H03"],
  "next_tests": ["Compare the remaining matched operating period"],
  "decision_impact": "The alternative production explanation is still unresolved"
}
```

```sh
python query_evidence.py CASE --continue-investigation checkpoint.json
```

The checkpoint must cite successful queries not cited by an earlier continuation.
It cannot reset usage, reopen a deliberately closed session, or extend the failure
allowance. Each grant adds at most `max(4, 2 × distinct unresolved hypotheses)` calls.
Whole-session ceilings remain 100 successful calls, 10,000 returned rows, 20 MB of
response context, 10 million pair comparisons and 500 handles. These are resource
circuit breakers, not scientifically calibrated optimal budgets. Other resource
allowances can be raised within those ceilings with the same checkpoint.

`context_bytes` counts canonical compact UTF-8 response bytes including the digest,
not model tokens or bytes in pretty-printed files. Pair work already performed is
charged even when the resulting response is rejected. Old session hashes are verified
before loading; subsequent writes add continuation metadata and the rejection allowance.
Historical response hashes are never rewritten.

The model's account of decision relevance is a reviewable judgment. The protocol verifies
links and resource bounds, not the truth of that judgment. Rotating novel but useless
tests remains possible up to the global ceiling. Prefer abstention to more irrelevant data.

## Client clarification

Normal allowance: two cycles, at most three requests per cycle, zero by default.
Questions sharing a hypothesis are equivalent only when they partition the same
explanations in the same way. An optional `information_target` distinguishes a new
measurement scope or period. It is an analyst declaration, not a semantic detector.
Without a complete answer partition, deduplication uses normalized question text.

Selection recomputes marginal information after each choice. It assumes uniform
hypotheses and deterministic answer partitions, then adjusts for availability,
reliability and effort. With at most 12 requests sharing a complete hypothesis model,
scope and equal cost/reliability weights, selection searches all subsets of up to three.
Larger or heterogeneous sets use a bounded greedy heuristic. Neither is a posterior,
a monetary value of information estimate, or a proof of optimal real-world decisions.
Unmapped questions retain the
documented decision-dimension heuristic and the uncalibrated 0.05 publication threshold.

When the normal allowance is consumed and a new branch remains material:

```sh
python manage_investigation.py continue-clarification CASE continuation.json
```

The JSON contains `progress_answer_ids` (actual answer IDs), new `candidates` in the
normal request contract, and `decision_impact`. All pending blocking questions must
already be answered, and reanalysis/review completed. Previously consumed progress
cannot justify another grant. Each grant opens one additional cycle; the whole-case
resource ceiling is eight cycles. Publish the candidates normally afterwards, with
`new_material_branch`. Its historical `trigger_response_ids` field uses request IDs.

A grant does not publish a question or bypass STOP. `close-budget` cannot cancel an
outstanding blocking request or required reanalysis. Every received answer, including
a nonblocking answer or correction, requires reanalysis. Corrections must supersede
the latest active answer; previous cycles remain auditable.

## Durable state

Lifecycle changes, query response/session/trace writes, and attribution answer/ledger
updates use a shared JSON transaction mechanism. A durable redo journal is the commit
point. Updates after that point must be recovered, not retried as a new answer.
Separate processes serialize through a per-case advisory lock. JSON remains the
canonical readable artifact format; there is no second database authority.

```sh
python manage_investigation.py status CASE
python manage_investigation.py recover-artifacts CASE
```

Status is read-only and reports `RECOVER_ARTIFACT_TRANSACTION` for an interrupted
commit. Recovery checks every target against its recorded before/after hash before
writing any target. A conflicting manual edit stops recovery for investigation.
Normal mutating commands also recover an interrupted transaction under the lock.
Never delete a pending journal to make a gate pass.

Scope: local POSIX filesystems with working locks, rename and fsync, including Termux.
This is not protection against malicious local writers, hardware that ignores flushes,
or arbitrary scripts bypassing the store. Report files outside the canonical analysis
directory retain their existing semantic hash and human-review checks; this mechanism
does not make all report rendering and privacy file moves one cross-directory transaction.
Journals are confidential case artifacts covered by normal workspace exclusion and purge.

## Provenance boundary

Finding validation and delivery re-open persisted query responses and verify their
hashes, dataset/session association, and handle ownership. A retained handle must be
cited with its source query. A valid reference is still not proof that the prose claim
follows from those values. Analytical and human review remain necessary.
