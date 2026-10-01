# Rental Agentic Case Investigator V2 — migration record

Baseline: `c43cb924a7547f081f8d0ffa2dbc349a126b9beb`.
Status: audit/design in progress; no V2 end-to-end result claimed.

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
