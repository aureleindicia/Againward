# V2 post-calculation QA and report/PDF checkpoint

Starting engine: `6dbfe89f0a5d03196d079a47ff0b89515ad0c490`.
This checkpoint completes the engineering path through a synthetic PDF. It does
not measure live model quality or authorize client delivery. No CASE A/B campaign,
financial oracle, HOLDOUT case, fixture or financial engine was changed/run.

## Explicit V2 entrypoint

```sh
python -m againward.domains.rental.case_graph_delivery batch-or-graph.json \
  --root approved-document-root --output-dir separate-report-directory \
  --model MODEL --max-turns 64 --max-reopen-cycles 2
```

Privacy-authorized original sources are still required upstream. An empty graph
uses the atomic reader and the existing issue-driven investigator. A replayed
ready graph can resume directly at calculation. Existing production-compatible
legacy entrypoints remain executable.

## Calculation and independent objections

The investigator proposes `PROPOSE_READY`; Python replays the graph, checks the
materiality frontier/readiness, projects `RentalCase` and calls unchanged
`reconcile`. Unsupported engine conventions or any material gap stop without an
affirmative final amount.

`case_post_calculation` receives only a detached verified case, deterministic
calculation/candidates, material subjects and their original evidence, current
semantic claims and limitations. It includes reviewed exclusions from relevant
sources so earlier irrelevance decisions can be challenged. The runtime supplies
actual original pixels for visual evidence; all native spans, source bytes,
pixels and local review receipts are replayed before and after invocation.
Context is bounded to 256 observations / 100,000 serialized characters and four
visual pages; exceeding a bound stops rather than truncating evidence.

The closed response is `PASS` or `OBJECT`, with at most two precise objections.
Each objection identifies an occurrence, material field/claim, alternative value,
existing observation IDs and explicit reason. For observed fields Python requires
an exact alternative normalized value from that same source and semantic field.
For `CHARGE_MEANING` / `GOVERNING_TERM`, existing commercial claim eligibility
checks constrain the enum, currently reviewed subject and eligible original
proof (confirmed local relationships are required for expanded evidence).
Unknown evidence, foreign evidence, cosmetic fields, an unchanged value, vague
reason, free graph patch or HUMAN role are rejected; they cannot reopen anything.
An invalid/provider answer stops QA, never becomes a fabricated PASS.

Python writes a content-addressed MODEL invocation receipt bound to the whole
verified case/calculation/evidence context. Only its verified `OBJECT` can create
a `POST_CALC_OBJECTION` journal event/targeted blocking Issue. This reducer changes
only Issues and the causal log, never facts, occurrences, relationships, authority
or amounts. Replay independently revalidates the receipt against the prefix.

The same investigator then handles the Issue with its existing bounded actions,
local rereads, repairs and independent reviews. `POST_CALC_RESOLUTION` is a reviewed
semantic claim: `CORRECTED` requires the exact correction already present in the
currently reviewed subject; `NO_MATERIAL_EFFECT` requires independent original
source support for excluding the alternative. Unsupported/ambiguous reviews do
not settle the Issue. Local dependencies include the precise objection, bound
observations, subject/review and commercial interpretation when challenged;
unrelated invoice evidence does not stale a term resolution. Python readiness
must pass again, followed by fresh deterministic calculation and fresh QA.

At most **two lifetime reopening events** are permitted in a graph, enforced in
the reducer and orchestration, including after restart. A configurable lower
per-run limit is available. With the default there are at most three investigator
runs / three QA passes, each investigator retaining its existing 64-turn,
repeated-state/rejection/no-new-evidence budgets. A final objection at exhaustion
is exposed without a third graph reopening, calculation/report are withheld, and
its OBJECT receipt cannot authorize a package. All stops and successful PDF jobs
have a persisted delivery-run transcript. There is no global adjudication step.

## Genuine V2 source context downstream

A `againward-rental-graph-calculated-case-v2` package under the original root's
`packages/` retains the actual graph and current successful calculation-QA receipt,
plus hashes of the canonical case and deterministic calculation. It contains no
legacy fact-review/reviewed-package fabrication. Ingestion verifies replay,
current graph head, readiness, projection/calculation and latest QA before each use.
A new OBJECT on the identical graph invalidates an earlier PASS; historical
objection events still replay against their original receipt and prefix.
The current-calculation and finding-review delivery guards therefore also reject
changed sources, stale graphs, forged MODEL/HUMAN receipts and altered amounts.

Native graph lineage includes original observations (quotes/spans/pixel bindings),
occurrences, recomputed exact relationships, semantic claims, local MODEL reviews,
materiality dispositions, post-calculation Issues and final QA hash. The existing
Evidence Plane gains native graph observation/relationship/claim rows with original
source references; canonical Rental records keep their source references. Findings
retain materialized Evidence Plane queries/handles, unchanged evidence ceilings
and no automatic recoverability.

`autonomous_review._source_context` has a minimal V2 branch: verify the real package,
then read/render its original SourceBatch with the same existing source isolation
and citation checks. Visual quotes come only from currently used replay-verified
graph evidence, never forged human attestations. The report pack manifest reads
native graph provenance directly. The PDF narrative's existing identifier guard
can admit only used graph-backed asset identifiers.

Reused unchanged owners: `RentalCase`, pricing/calendar/arithmetic, expected/actual
ledgers, reconciliation, `review_findings`, Evidence Plane queries and provenance,
`run_autonomous_finding_review`, `run_reviewed_package_job`, `run_autonomous_report`,
`render_report`, the existing stdlib PDF renderer/PdfReader QA and existing real
human/contract/delivery gates. Only their minimal V2 source/lineage adapters changed.

## Generic proof and limits

`tests/test_rental_case_graph_delivery.py` starts from generic original text sources
and an empty graph; actual atomic reader, investigator, readiness, canonical case,
calculation, post-calculation QA, finding review, original-source challenge, report
rendering, actual PDF text extraction/QA and evidence-pack validation all execute.
The supported documentary arithmetic is actual **39.00 EUR**, expected **34.00 EUR**,
difference **5.00 EUR**, with external-adjustment reservations and no recovery claim.
The PDF is watermarked **NOT FOR CLIENT DELIVERY**, and no human approval is created.

A second real PDF test challenges an excluded historical rate, opens a material
Issue, independently reviews its source-backed non-applicability, re-evaluates
readiness/recalculates and passes a fresh QA. The correct supported amount remains
unchanged. The test does not pretend that a historical alternative governs merely
because QA cited it. Negative tests cover foreign/fabricated/cosmetic/vague/same-value
objections, direct mutation/HUMAN attempts, source staleness, false correction,
unreviewed resolution, local dependency invalidation, all cycle limits, restart
budget, package/calculation/head/receipt forgery and exact graph replay.

These are **scripted synthetic model responses** exercising real Python boundaries,
not live model-quality, OCR or human-approval measurements. New material assertions
must reference existing graph evidence; source material needing fresh observation
must first pass the bounded reader. Oversized source/report contexts, real ambiguity,
invalid evidence and exhausted budgets intentionally stop. No conditional or
unverified calculation fallback was added.

## Validation

- Final targeted selection: **177 passed in 143.74s**; the later same-graph
  QA supersession test is additionally checked, and all tests run in the full suite.
- Ruff configured and explicit V2: pass; mypy configured **18 files**, explicit
  V2 **14 files**: pass.
- Rental: **15/15**, privacy: **19/19**, zero false blocks / unsafe passes.
- Clean-engine full suite, HOLDOUT guards and remote CI are recorded after validation.

## Pytest performance

`pytest-xdist` is development-only. `pytest.ini` runs two workers with load scheduling
and reports the 20 slowest tests. CPU count is not used to spawn an unbounded number
of PDF workers on Termux. CI installs `.[dev]` and uses the same suite and explicit
V2 Ruff/mypy checks. No test, guard, subprocess isolation or evidence check is skipped.
For single-process debugging use `python -m pytest -q -n 0`; after edits use the
relevant file/test selection, and run the full suite once for the checkpoint.
The unchanged 28-investigator-test selection measured **41.79s serial → 35.08s
with two workers** (about 16%); full-suite timing will be recorded below separately.

## Before the first DEV A×1 / B×1

Freeze the validated engineering SHA and use fresh isolated authorized DEV
workspaces with the explicit V2 entrypoint, original-source privacy clearance and
real model configuration. Record model identity, calls, turns, bounded rejections,
QA/reopening receipts, graph/replay/readiness, calculation, report/PDF provenance
and wall time. Run only the separately authorized first A×1/B×1 then diagnose generic
failures, adding generic tests before fresh reruns. Score known financial oracles
only after independent calculation; no tuning on HOLDOUT. Reproducibility A×2/B×2,
independent quality/HOLDOUT measurement and actual human/client delivery approval
remain later milestones. This checkpoint is not first-client readiness.
