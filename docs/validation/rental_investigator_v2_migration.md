# Rental Agentic Case Investigator V2 — migration record

Baseline: `c43cb924a7547f081f8d0ffa2dbc349a126b9beb`.
Status: evidence graph, structural proposal actions and local original-source
reviews implemented; investigator, relations, readiness and downstream adapter
remain in progress. No V2
end-to-end result claimed.

## Causal boundary

The legacy source job selects or reconstructs whole `DocumentExtraction` objects.
`independent_qa` compares derived observations, but `reconciliation`, adjudication,
structural validation, promotion and the document adapter still consume grouped
proposals. Consequently a semantic decision can force reconstruction of unrelated
structure. Visual review also depends on proposal/QA/adjudication receipts instead
of only the reviewed evidence and semantic prerequisites. A successful comparison
does not establish a complete financial case.

The most recent baseline smoke illustrates both boundaries: native and visual
review were reached in one dossier before `REVIEW_STALE`; another stopped on
missing kinds on rate rows despite completed independent reads. Neither result
establishes a financial outcome. These observations motivate the migration;
they are not specifications for derivation rules.

## Retained authorities

| Component | V2 responsibility |
| --- | --- |
| Privacy intake, source inventory, `verify_batch` | Authorization and immutable source bytes |
| Readers, exact proposal validation, page/render binding | Evidence validity, not semantic approval |
| Codex CLI transport | Bounded model invocation and runtime diagnostics |
| Artifact transactions and stable hashing | Durable, replayable state changes |
| RentalCase, pricing, temporal reconciliation, credits | Existing deterministic financial semantics |
| Finding review, report and PDF QA, delivery gates | Downstream criticism and controlled delivery |

## New middle, explicit opt-in

V2 will have its own entrypoint. The legacy job remains callable unchanged.
The canonical graph owns observations, occurrences, relations and open issues.
Reader outputs are evidence proposals, never alternative complete worlds.
Observations keep their raw evidence and lineage; canonical occurrence identity
does not use model-local labels. A derived container is recorded as
`DERIVED_STRUCTURE`, not fabricated as a quotation asserting its kind.

Small semantic actions act on graph subjects. Python validates a delta against
its evidence and prerequisite identities and records accepted **and rejected**
material actions with before/after hashes. Reviews bind local dependencies.
Unrelated additions do not invalidate them; actual changed prerequisites do.
No model-provided HUMAN role authenticates a human.

Readiness accounts for every potentially material observation and issue before
adapting to RentalCase. Complementary evidence is retained, contradiction is an
issue, and missing identity is unresolved rather than an invented occurrence.
Structural classification grants no contractual authority. Readiness is not
merely successful dataclass construction.

## Migration and verification sequence

1. Immutable graph evidence import/replay; exact native and visual binding tests.
2. Reader convergence and conservative occurrence/issue construction.
3. Transactional semantic actions, rejection receipts and deterministic replay.
4. Bounded issue-driven investigator with original-source inspection.
5. Materiality frontier, readiness and adapter to existing financial engine.
6. Local review dependencies and original-pixel review.
7. Independent adversarial final QA with bounded issue reopening.
8. Generic checks, DEV runs, frozen confirmation, independent holdout.

Each stage adds positive and adversarial tests before claiming its invariant.
The migration does not claim that known fixtures prove generalization. Financial
oracles are evaluation-only and never inputs to semantic actions or decisions.
Global proposal selection, global assembly and global adjudication remain legacy
compatibility mechanisms, not the intended V2 progression path.

## Interface findings from the baseline audit

- `replay_extraction` and `validate_proposal` already re-read native spans and
  re-render visual bindings. They can secure evidence import without invoking
  Rental structural completeness or granting semantic approval.
- `record_model_visual_review` currently binds global QA and adjudication hashes,
  selected whole-extraction hashes, and a source selection test. V2 must not
  manufacture these legacy receipts to obtain a pixel review. It needs genuine
  original-pixel review with local observation/prerequisite bindings.
- `load_document_case` mixes evidence promotion, entity construction,
  relationships, charge-meaning review and canonical record projection. V2 must
  not synthesize a legacy proposal/review package to satisfy that mixed contract.
  Projection arithmetic and record conventions can be shared after an explicit
  V2 readiness boundary.
- `load_rental_case` is the existing financial entry boundary. A versioned V2
  package branch can replay the graph, verify readiness, and return the existing
  RentalCase plus lineage. The pricing engine need not change.
- Finding/report QA obtains original sources through `_source_context`, currently
  restricted to the legacy package version. Its V2 branch must verify the graph
  and its reviews, then supply the same original sources; bypassing this check
  or pretending V2 is a legacy package would lose auditability.
- The existing source provider can filter failed observations or normalize
  structural containers. V2 ingestion must account for rejected material
  observations and distinguish structural derivation from source observation;
  silently importing only surviving candidates would violate the frontier.

## Foundation checks (work in progress)

Fifteen generic evidence-store/question tests pass, including native and actual rendered
visual evidence, reverse import order, repeated exact amounts at distinct spans,
cross-source separation, source mutation and a rehashed stale-render attack.
Ruff and configured mypy pass; explicit mypy on the new graph module also passes.
Rental benchmark: 15/15. Privacy benchmark: 19/19.
The first full pytest run completed: 1160 passed, two HOLDOUT guards rejected
the uncommitted engine (829.92 s). The subsequently expanded foundation suite
passes all 15 targeted tests. The two guards will be rerun after commit; they
remain unchanged. These checks validate only the foundation, not the
investigator, readiness, or the Goal's end-to-end success criteria.

Imports produce replayable runtime events with pre/post semantic hashes; the full
snapshot additionally hashes the ordered receipt log. Reverse reading order has
the same semantic state but intentionally retains a different causal audit log.
Question generation retains complementary observations and identifies opposing
values only at a proven common evidence position or explicit source scope.
Unassigned observations remain unassigned; a model label does not resolve them.

## Action boundary to implement next

Use observation IDs as evidence references, not model-written amounts/hashes.
The minimal mutation vocabulary will cover occurrence classification/attachment,
relations and explicit observation/issue disposition. Source inspection and
additional reading are requests to runtime tools; READY is a request to the
deterministic evaluator, not a writable state.

An occurrence proposal is not approved commercial truth. Its exact field
attachments and its semantic classification require review; a source-supported
container derived by Python records its rule and witnesses separately. Source
role/status is not inherited as agreement authority. Relations preserve both
source identities and require reviewed prerequisites, uniqueness and absence of
contradicting anchors. Rejected and unresolved observations remain in the graph.

Two important implementation constraints follow:

1. Exact quote validity proves where a model read, not that its interpretation
   is correct. A valid evidence import is never a semantic approval.
2. Coalescing exact observations cannot coalesce distinct occurrences merely
   because their values match. Differing proof locations remain separate until
   an identity decision has sufficient explicit evidence.

Action application and replay must share one reducer. The semantic state hash
excludes the append-only action log so a rejected action can record an audit
event with identical pre/post semantic hashes. The full snapshot hash includes
that log. Semantic dependency hashes exclude debugging labels and unrelated
state, but include actual values, evidence and prerequisite decisions.

## Foundation checkpoint

`0d576a5101a7a4d233f7d580a42aa461c6233c7b` is pushed. Both unchanged HOLDOUT
guards pass on that clean engine. GitHub push and PR workflows
`36799057422` / `36799061800` both completed successfully.

## Structural proposal actions

`DECLARE_OCCURRENCE` and `ATTACH_OBSERVATIONS` now share one reducer for live
execution and replay. The model supplies only intent and observation references;
Python binds local prerequisite hashes, assigns technical IDs and records the
receipt. Accepted proposals remain `PROPOSED`, with `authority=NONE` and no
observation promotion. They are not a semantic review or proof of co-reference.
Unknown witnesses, foreign facts, conflicting field values and stale local
prerequisites produce rejected receipts with identical pre/post semantic hashes.

The transaction records an immutable snapshot and updates a compare-and-swap
head. Stale concurrent writers cannot overwrite it. Repeated actions and redundant
attachments do not change semantic state or occurrence revisions. Unrelated
actions commute semantically and do not stale local prerequisites. Forged success
receipts and invented HUMAN/review state fail replay.

31 targeted graph/action tests pass; explicit Ruff and mypy on all three new
modules pass. The initial full regression/benchmarks above remain the baseline
checks; another full suite is required as the migration progresses. No A/B live
run has been launched. Semantic review, relations, material dispositions and the
readiness gate are not yet supplied by these structural proposal actions.

## Local original-source review

An occurrence review now consumes the original native units and actual rendered
pages, plus the exact attached observations and proposed grouping. Runtime owns
the invocation receipt, role (`MODEL` only), local prerequisite digest and render
hashes. Replaying a review verifies these dependencies without another model call.
The latest matching review governs; an older positive review cannot override a
new ambiguous verdict. Structural support still grants no contractual authority.

Unrelated occurrences and equivalent rereads do not invalidate a local review.
Changing the actual subject does. A rejected grouping keeps its observations and
creates an explicit open issue. Both reviews and proposal actions use one
transactional persistence path, with full replay before updating the graph head;
an unjournaled promotion cannot commit.

42 targeted tests pass, including native and actual rendered visual review,
source mutation, forged HUMAN receipts, local invalidation, latest-review
selection, equivalent reread, and concurrent/stale writes. Configured Ruff/mypy
and explicit checks of the four V2 modules pass. Rental 15/15 and privacy 19/19
pass again. The expanded full regression completed with 1195 passed and the two
unchanged HOLDOUT guards refusing the uncommitted engine (786.42 s). The final
targeted suite additionally covers two transaction tests added during that run.
The guards will be checked on the committed engine. This is not an end-to-end
claim. Both CI runs for checkpoint `42651db` completed successfully.

Local reviews checkpoint: `0211ae65afc0a531c665a2db32fbf14baf5b6122`, pushed.
Both unchanged HOLDOUT guards pass on that committed engine (12.51 s).

## Exact occurrence relationships

The V2 graph can now derive identity links from exact reviewed anchors, without
constructing legacy entity/fact-review artifacts. Agreement plus asset/serial
can identify a unique rental scope; invoice plus printed line and matching
currency can identify a credit target. Any supplied contradicting identifier
rejects the pair. A partial second plausible target prevents convenient selection
of the stronger match. An unreviewed endpoint cannot produce a confirmed edge.

These relationships preserve both source IDs and all anchor observation IDs.
No attributes are copied. Identity confirmation grants neither contractual
authority, billing-stop effect, nor a financial allocation amount. Incomplete
identity remains a candidate for investigation; non-exact semantic relationships
still need the forthcoming bounded action/review path.

The relationship view is recomputed from current local subjects, their latest
reviews, and competing targets. A deterministic refresh journals the view and
its issues for replay. Adding a plausible alternative or changing a prerequisite
review cannot preserve an earlier confirmation. Downstream readiness must use
this current view rather than an old stored `CONFIRMED` flag.

57 targeted graph tests pass, including 15 relationship tests (unique and partial
anchors, conflicting suppliers/currencies, unreviewed subjects, newly competing
scopes, changed reviews, replay forgery, identity versus commercial effect, and
order invariance). Ruff and explicit mypy on the five graph modules pass. This
step does not yet resolve semantic links that lack exact identifier anchors.

## Reviewed semantic deltas

Bounded claims now distinguish charge meaning, governing-term authority and
observation disposition from structural occurrence review. Each claim is an open
issue until its own independent original-source review supports it. The shared
review runner renders each referenced source separately and binds all current
source hashes and pixels. It does not copy a related commercial observation into
the invoice. Commercial evidence must belong to the reviewed target or an exact,
current, confirmed relationship; unrelated or ambiguous relationships cannot
expand that evidence set. Governing authority additionally requires explicit
reviewed acceptance evidence; a rate-card role is insufficient.

Rejected/irrelevant/duplicate dispositions preserve the original observation.
Equal text alone cannot establish duplication. The effective materiality frontier
consults current claim reviews, not editable disposition flags. A rejection that
conflicts with a current occurrence approval remains unresolved. Stale claims
cannot retain authority merely because their issue once became `RESOLVED`.

All live claim application and replay use one reducer and the common transaction
path. 70 targeted graph tests pass, with 13 new semantic-claim tests covering
cross-source support, unrelated/ambiguous evidence, rejected subjects, authority,
current dependency invalidation, competing dispositions, forged receipts and
HUMAN flags. Ruff and explicit mypy on six V2 modules pass. No investigator run,
readiness success, calculation, or end-to-end validation is claimed yet.

The committed semantic-claims checkpoint
`e0c0b77771270b0379a20e4c33f6e3155c1053f1` passed the complete suite in a clean,
detached validation worktree: **1227 passed in 767.84 seconds**. This result
includes the unchanged HOLDOUT guards. It does not validate later reader edits.

## Atomic source reader (integration in progress)

The V2 reader requests observations and limitations from the original native
units or rendered pages. Python binds source identity, spans, hashes, types and
technical identifiers. Intermediate reads do not have an entity-completeness
requirement. Each response is retained in a content-addressed runtime receipt;
replay reruns exact binding using the recorded normalization version. Invalid
observations create explicit potentially material issues while independently
valid observations remain available. Empty reads and limitations also remain
visible issues; they are not successful completeness decisions.

A single generic native-source interface probe with `gpt-6-luna` completed in
16.42 seconds. It supplied a monetary value with an ISO currency annotation,
although the exact quote supported both. A bounded normalization now accepts
that representation only when the exact amount/currency pair occurs uniquely
in its quote. It preserves the digits and citation, does not derive a missing
currency field, and does not perform FX or locale guessing. Rebinding the same
historical response recovered all ten observations without another model call.
This was neither an A/B run nor a calculation test.

Reader regressions cover native and visual binding, invalid citations, unknown
pages, stale renders, null values, repeated quotes, isolated rate contradictions,
empty reads, source mutation and unambiguous JSON serialization recovery.
Monetary tests additionally reject mismatched currencies/amounts, unknown codes,
ambiguous repeated amounts and unsupported locale notation. The materiality
gate and investigator still need to resolve or explicitly account for these
issues before any V2 calculation can be permitted.

Reader checkpoint checks: 211 targeted graph/protocol/provider/review tests pass
in 87.61 seconds, plus the separately added normalization-version replay guard.
Repository Ruff, explicit V2 Ruff, configured mypy (18 files), explicit graph
mypy (7 files), Rental 15/15, privacy 19/19 and `git diff --check` pass.
The new full regression on this reader checkpoint remains to be run. No A/B
end-to-end run has been executed on V2.
