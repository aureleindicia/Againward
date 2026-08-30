# Candidate V2.1 — minimal epistemic patch

## Scope

This is a generic protocol and epistemic calibration patch. No Candidate V2 DEV case
was rerun, no hidden ground truth was read, and no domain-specific diagnostic heuristic
was added.

## Changes

- Added the `maximum justified claim` principle: evidence strength is determined by its
  ability to eliminate competing explanations, not by data volume alone.
- Clarified decision semantics: `CAUSE_PROBABLE` and `CAUSE_CONFIRMED` require a
  confirmed abnormal phenomenon; a legitimate energy-consuming operation is
  `NORMAL_OPERATION`.
- Added `validate_epistemic_decision_semantics`: it validates consistency of analyst
  declarations but never selects a decision, cause, question, measurement or action.
- Retained `ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` for confirmed abnormality with unresolved
  physical mechanisms; made `INSUFFICIENT_INFORMATION` require an actual decision blocker.
- Updated the blind-oracle review question to assess a primary materially discriminating
  intent. Related details no longer invalidate that intent. Automatic revelation thresholds
  are unchanged; ambiguity remains routed to blind review.

## Genericity and contamination audit

The changed source, documentation and tests contain no DEV case identifiers, timestamps,
case outcome wording, equipment-specific remediation heuristic or hidden-answer term. The
new tests use synthetic abstract schedule/operation examples only. The patch would be
valid if the DEV cases had never existed.

## Tests

- `pytest -q`: **177 passed**.
- `pytest -q tests/test_physical_expertise_benchmark.py`: **31 passed**.
- No DEV run or scorecard was executed.

## Risks

The intent route can increase blind-review volume for requests that name a clear primary
concept but lack enough exact terms for automatic matching. It cannot auto-reveal those
items. The declared-decision validator depends on analyst-provided inputs, deliberately:
it prevents contradictions but cannot evaluate physical truth.
