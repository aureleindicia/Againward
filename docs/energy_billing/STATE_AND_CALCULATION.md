# Minimal state and calculation checkpoint

This implements phases 3–4 for **one electricity consumption HT line**, not a
whole invoice audit, a complete autonomous Investigator, or a delivered client
report. Gates B/C and PDF generation have scripted source-to-state integration
evidence. The frozen actual-model path must still be measured on this commit.

## Durable ownership

`state.py` owns a closed append-only READ/ACTION/REVIEW journal. Reducers replay
source-bound reading receipts and independent local review receipts. Atomic
transactions refuse an outdated caller state. Unknown evidence IDs, wrong
targets or rejected declarations do not mutate the journal. Duplicate
declarations and links are idempotent and do not add money.

Occurrences are INVOICE (one scoped line) and TARIFF. GOVERNS is a proposed
invoice-to-tariff relation, not authority by itself. One source with conflicting
required scalar values cannot be resolved by choosing convenient evidence IDs.
This intentionally abstains on multiple lines/PDLs rather than pretending to
support their grouping. Multi-line support remains later work.

Reader v2 archives the exact native parser context in its hashed receipt.
Historical replay preserves already valid evidence even if another current blob
is broken. Consumers independently verify the bytes of their own dependencies;
archived text cannot authorize a calculation after source mutation. Reader v1
receipts remain compatible but need current bytes for historical reconstruction.

## Independent reviews

`review.py` requests three exact source-bound contracts:

- INVOICE: every selected fact, material coverage, HT consumption scope and date
  end convention;
- TARIFF: those checks plus explicit fixed/indexed/other tariff meaning and the
  source-established per-line rounding convention;
- GOVERNS: accepted contractual authority, supplier, PDL, currency and effect
  period. An invoice price is explicitly insufficient.

Review prompts supply original source text and a local proposal, no prior review
verdict. Positive fact responses cite all occurrence evidence; positive authority
responses cite their focused relation plus an exact original acceptance clause. Raw values
and quotes remain immutable; canonical tariff/rounding/date conventions are
explicit reviewed decisions, never alias fallback. Native schema validation and
known reference checks allow one protocol repair, not business correction.
Fact reviews cite at most 32 atoms from one occurrence. The authority review
may cite up to 64 atoms from its two subjects; it does not have to repeat their
already mandatory independent fact reviews.
Native parser limitations or uninspected locations block approval before a
model call, and again when an existing review is consumed.

Dependency hashes include the subject, its source-bound observations (including
financial notes), quarantine and limitations. An invoice fact change stales its
invoice and GOVERNS reviews while preserving the independent tariff review. A
changed tariff blob blocks tariff consumers while keeping invoice evidence and
review usable. Source renaming and receipt timestamps are not dependencies.

Invalid material atoms remain root blockers. Invalid notes are not silently
irrelevant: the independent source reviewer must explicitly disposition their
quarantine IDs as nonmaterial using the retained raw proposal and original
source. The field name `note` alone grants no calculation permission.

## Single readiness owner

`calculation.readiness()` replays Python state and checks:

1. material quarantine;
2. exactly one invoice line and tariff term;
3. disposition of every supplied source;
4. current independent facts/scope reviews;
5. explicit supported conventions;
6. original numeric tokens in each financial quote;
7. typed identity, period, units and exact decimal values;
8. supplier/PDL/currency matching and full tariff period coverage;
9. current independent contractual authority review.

The first causal failure is reported as a root issue with one derived calculation
blocker. Unsupported rules return UNSUPPORTED. Missing/conflicting material
facts return UNRESOLVED without a final expected amount. Protocol/state failures
are technical errors, not unsupported business cases. There is no default
currency, tariff, date boundary or rounding rule.
Known credits or invoice-level totals cannot be dropped because a model returns
complete coverage. They require explicit supported treatment before this first
single-line calculation. Typed action targets are checked inside bounded model
repair as well as by the durable reducer; exchanging invoice/tariff IDs does not
become a late state mutation.

The lexical numeric check supports plain decimal point/comma only. Grouped or
ambiguous formats require further tested normalization; an unbound normalized
amount cannot pass just because a scripted/model reviewer returns SUPPORTED.
Semantic meaning still requires independent original-source review and later
strict held-out scoring. This check does not prove causal/legal truth.

## Calculation and reporting

`calculate()` traces explicit quantity/price units, accepted authority,
half-open dates, rounding rule/version, expected integer cents, billed integer
cents and signed difference. Monetary arithmetic uses the existing exact Decimal
primitive. No legal entitlement or recoverable amount is calculated.

`reporting.render_report()` reads the stored calculation, independently replays
its current prerequisites and exact result, and refuses an altered artifact.
The lightweight Markdown/HTML/PDF consume one report model. The shared stdlib
PDF serialization primitive is reused; Rental report semantics are untouched.
QA is explicitly NOT_PERFORMED and delivery INTERNAL_REVIEW_REQUIRED.

## Actual-model path

After committing and checking a clean tree:

```sh
python -m benchmarks.energy_billing.vertical --model gpt-6.1-sol \
  --output scratch/eb-vertical-01
```

The script generates fresh synthetic native PDFs, makes real local occurrence
and relationship action decisions, requests independent original-source reviews,
then runs readiness, exact calculation and report/PDF. It receives no hidden
amount/discrepancy oracle. There are at most three action turns, no rereads,
sixteen calls including repairs, and a 600-second wall budget checked before
each call (a running call additionally has the transport timeout). New receipts
alone do not count as semantic progress.

This early bounded path abstains rather than recovery-looping. The complete
issue scheduler, all inspection/review/READY intents, supplemental sources,
reviewed irrelevance, local conflict resolution and bounded post-calculation
reopening remain phases 5–7 work. No expansion before actual convergence.

## Validation before frozen run

86 focused tests pass in 10.15 seconds; configured Ruff passes; mypy passes on
33 source files. The initial report integration caught tuple-versus-list JSON
replay inequality and was corrected before the frozen run. New live review
schema probes pass 13/13 with 14 actual CLI calls in 113.410643 seconds: one
deliberately wrong focus repaired once, no business fixture or graph mutation.
These probes used a dirty engineering tree at `99c9694`; they are compatibility
evidence, not a frozen accuracy benchmark. Full latest-code regressions and the
frozen thin run are recorded separately when terminal results exist.

## First frozen vertical result and correction

At clean SHA `514dd7a986d29e282824b1be9396d74370d197dc`, the actual-model run
created 33 bound atoms, two occurrences, one GOVERNS relation and two positive
independent facts reviews. Its nine calls took 340.155134 seconds. The authority
review stopped with MODEL_PROTOCOL_FAILURE after one repair: the two selected
subjects contained 16 + 17 atoms while the response could cite at most 32 and
the checker required all 33. No calculation or report was reached. Valid state
and reviews survived; the precise root is a protocol cardinality mismatch, not
business ambiguity or unsupported tariff. The original runner's
`protocol_retries=2` counted rejected responses; the actual repair count was one.

The correction derives the authority bound from its two inputs (2 × 32), keeps
all facts and qualifications, and tests both 33 and 64 atoms. All other evidence
arrays keep their existing bound. New protocol probes exercise an actual
64-reference response with no money fixture; 13/13 pass in 14 CLI calls and
123.863377 seconds on an engineering tree based on `514dd7a`. They are not an
accuracy campaign. Runner retry instrumentation now counts repair attempts and
retains per-call timing/hash diagnostics.

The full unchanged `514dd7a` tree passed **1,498 tests in 720.97 seconds**.
Rental deterministic benchmark: 15/15. Rental privacy: 19/19, zero false blocks,
zero unsafe passes. Both original worktrees retain their inspected state. No
Rental/Energy semantics or shared document parser code changed. A fresh frozen
run on the correction is required; the failed run is never silently relabelled
successful.

## Second frozen result: scope error, then architectural simplification

Clean SHA `247ccc66deccbfb31802bed4f188d7f4671ade0d` passes **1,503 tests in
682.51 seconds**. Its frozen actual-model run again reaches 33 atoms, two
occurrences, one relation and two positive facts reviews, but no calculation.
Nine calls take 331.365585 seconds. Both preserved authority responses cite
every evidence ID of the focused GOVERNS relation. Python additionally required
all other occurrence atoms, including invoice quantity, billed amount and
decorative synthetic labels: evidence already owned by separate mandatory
facts reviews. Increasing the schema cardinality therefore did not resolve the
scope mismatch. This is not factual source ambiguity. All valid state survives.

The Goal's stop rule applies: expansion is stopped and the review is simplified,
not repaired with another broad recitation prompt. Authority v2 owns only its
relation and accepted applicability. It cites the exact source/location/quote
establishing accepted terms, which Python binds atomically to the original
native context. An invoice cannot supply contractual acceptance proof. Facts,
quantity, billed amount, tariff type, price and rounding still require their
independent current reviews and deterministic checks before calculation.

Review v2 receipts archive bounded original contexts and the runtime-bound
authority clause. Replay preserves v1 facts reviews; a v1 authority verdict
needs local renewal because it lacks this explicit clause. Old runs replay
their 33 atoms, two occurrences and two reviews unchanged. The calculation and
report carry the acceptance evidence alongside arithmetic provenance. Wrong
source/location/quote is rejected with one repair, no journal mutation. Missing
focused citations now identify the exact missing evidence IDs in diagnostics.

New protocol probes pass the changed closed schema (13 tasks, 14 calls,
140.431398 seconds). Additional real CLI probes bind a nonfinancial accepted
agreement and repair a deliberately wrong location once; no billing fixture,
oracle, source rejection or durable state mutation is involved. Targeted and
fresh frozen results for this simplification are recorded after completion.
