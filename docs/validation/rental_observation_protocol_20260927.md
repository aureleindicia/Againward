# Rental observation protocol normalization — 2026-09-27

Base: `85048a195bfc7ea017a4a012f63b64bde419f136`.
Scope: general architecture and scripted software validation. No live CASE A/B
pipeline or unseen dossier is executed in this change. Historical 0/6 financial
coverage remains the latest live evidence for the old checkpoint.

## Causal finding

The old boundary used the durable internal representation as a model protocol.
Readers supplied both commercial observations and machine types/identifiers;
intermediate omissions triggered retries before independent evidence could help.
Adjudication demanded exhaustive input enumeration and could recover a new fact
from pixels but not from native text. Consequently, equivalent units, optional
null amounts, grouping choices and output wrappers could prevent useful evidence
from reaching review. Full financial completeness is still needed on the selected
proposal and reviewed package, but not on each independent reading.

## Current responsibility map

| Transition | Model responsibility | Deterministic responsibility |
| --- | --- | --- |
| Source → observations | Read original text/pixels, describe facts, uncertainty and meaningful groups | Current source identity, exact native quotes/spans, page/render binding |
| Fresh output → canonical proposal | No additional call for recognized notation changes | Bounded JSON notation recovery, canonical Rental aliases and types, technical grouping IDs |
| Primary + reread → QA | Independent original-source observations | Compare canonical content; retain omissions/conflicts as reconciliation issues |
| QA → adjudication | One semantic decision for the focused source, original evidence, selected observations and recovered facts | Source/cardinality binding, complete input ledger, new proposal hash and lineage |
| Assembly → selected proposal | Re-adjudicate actual business content against originals | New QA, immutable parent/recovery receipt, no reuse of old review |
| Selected proposal → facts | Explicit native/visual meaning review | Strict source/structural completeness, current reviews, no promotion of unknown/unreviewed observations |
| Facts → package/calculation/report | Existing link, finding and report review | Existing financial arithmetic and delivery gates |

## Removed obligations and safe recovery

- Rental first readers no longer author `value_type`; Python assigns it from the
  shared domain vocabulary. Native `entity_hint` is a semantic group label, not
  an internal ID. Values, source wording and business classifications remain
  model observations requiring review.
- A small fresh-output boundary accepts one JSON fence, trailing commas outside
  strings, known single-result envelopes and equivalent decision wrappers.
  It rejects duplicate keys, truncated/multiple payloads, nonfinite numbers and
  ambiguous shapes. JSON decimal tokens retain their exact decimal spelling.
  Durable receipt parsing is unchanged.
- Explicit unit/role/kind aliases are canonicalized. Examples: `calendar_day`
  and `DAY`; `credit_memo` and `CREDIT_NOTE`. Unknown statuses such as `DECLARED`
  are **not** interpreted as `ACCEPTED`, `ISSUED` or `EXTRACTED`.
- Null observations are withheld, never converted to zero or accepted facts.
  Safe diagnostics count these withheld observations. Required missing fields
  still fail the selected-proposal/package checks; optional absence need not
  create a fabricated fact or a schema repair request.
- Missing/nonexistent native locators may be bound only when the unchanged quote
  has exactly one occurrence across current native units. An existing conflicting
  locator is not silently moved. Paraphrases and ambiguous occurrences are not
  evidence. Visual page identity is never inferred from a default page.
- Partial structural readings enter QA on their first validated source read.
  Their issues are recorded. Actual schema/source errors retain bounded retries;
  final selection and promotion remain strict.
- One model decision per source replaces model-generated decision cardinality and
  source ID. Candidate views expose semantic observations and local positions,
  excluding repeated internal candidate hashes, timestamps and evidence machinery.
- An explicit `ASSEMBLE` requests selected observations. Python records every
  omitted input as **DEFER**, not model rejection or approval. Every input remains
  in immutable lineage and the fresh QA/adjudication context. No automatic union
  or conflict resolution is introduced.
- Adjudication can recover exact native observations as well as pixel observations.
  Recovery may accompany an explicit assembly. The new proposal remains unapproved
  and receives fresh QA/adjudication and later reviews. Recovered native facts
  retain exact spans; pixels never become native text or HUMAN evidence.
- Unique compatible document envelopes can be attached to their material group.
  Independent accounting rows, distinct rates and competing entity identities
  are not merged. This is not a general inference of document/entity relationships.

Prompt and assembly versions change. Prior reviews are not reused on changed
observations; historical workspaces remain historical evidence. Use fresh
workspaces for the next independent checkpoint campaign.

## Software evidence and limits

Generic tests cover unit/role aliases, optional unknown amounts, explicit unknown
authority, safe JSON recovery, duplicate/truncated JSON rejection, exact quote
binding, technical ID omission, complementary sparse assembly, native and pixel
recovery, fresh QA/review requirements, mutation invalidation, redundant/reordered
observations, distinct accounting rows, commercial conflicts and missing required
facts. Existing tests for generated adjudication schemas now assert a single
source-bound decision object rather than a model-authored array/source ID.

Validated implementation commit: `3de8ea9e19fb988642e37848c6703abce534913f`.

| Check | Result |
| --- | --- |
| Focused protocol/source/adjudication/architecture/failure-family suite | 149 passed before the final small defensive additions |
| Latest protocol + source-job tests | 52 passed |
| Invalid decision-container regression | 3 passed; null/integer/string containers produce a diagnosed schema stop after the existing bounded retry, never a Python exception |
| Full pytest on committed engine, Termux Python 3.14 | **994 passed**, 742.28 seconds |
| Ruff | Passed |
| Configured mypy | Passed, 18 source files |
| Rental benchmark on committed engine | **15/15**, TP 3 / FP 0 / FN 0 / TN 12 |
| Privacy benchmark on committed engine | **19/19**, zero false blocks and unsafe passes |
| GitHub CI, implementation commit | **8/8 passed**, push + draft PR #5, Python 3.11–3.14 |

CI evidence: [push run](https://github.com/aureleindicia/Againward/actions/runs/36345875583)
and [PR run](https://github.com/aureleindicia/Againward/actions/runs/36345879084).
Each CI interpreter passed all 994 tests plus Ruff and configured mypy.
The focused counts overlap; they are not additional independent measurements.
Local logs and benchmark outputs are outside the checkout under the Termux
temporary directory (`againward-protocol-full-3de8ea9.log`,
`againward-rental-3de8ea9/validation.json`, `againward-privacy-3de8ea9/validation.json`).
This documentation-only follow-up does not alter the validated engine or prompts.

An initial suite executed during edits had 946 passes and 3 repository-integrity
failures: those tests require the engine to match Git HEAD. It is not a clean
baseline or a validation certificate; no integrity check was relaxed.

Residual risks: the model still must read the document correctly, distinguish
commercial roles/statuses and resolve true grouping/authority conflicts. Unknown
aliases, ambiguous exact-quote matches, contradictory limitations, unparseable
responses, or incomplete final evidence can still stop. The bounded assembly
round remains finite. These scripted tests do not establish live convergence,
95% structural robustness, 99% correctness, or client readiness. Independent
Luna CASE A×3/B×3 on the final frozen SHA remains required.
