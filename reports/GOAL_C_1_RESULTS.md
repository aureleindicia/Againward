# Goal C.1 — Client report fidelity, multi-decision and presentation hardening

## Delivered changes

- Goal B accepts a backward-compatible `decisions` list while preserving its
  former single `decision` field.
- Goal C builds one report containing heterogeneous decision classes.
- `NO_ECONOMIC_CASE` and `OPERATIONALLY_NOT_JUSTIFIED` are rendered as
  first-class, sourced decision cards using considered actions.
- Critical narrative blocks are structured claims tied to the objects they
  explain; no-action and checked claims cannot be free facts.
- Alternatives retain economic and operational comparison information without
  becoming additive recommendations.
- The PDF renderer validates the exact model immediately before rendering,
  sanitizes every visible value and reflows blocks dynamically.
- C-A through C-J are executable fixtures, plus `C-MULTI` for the
  mixed-decision E2E.

## Protected components

Goal A intake/analysis and Candidate V2.1 paths were not modified. The only
Goal B change is multi-record persistence/provenance, documented as the minimal
Goal C integration extension. It neither selects actions nor changes decision
semantics, calculations, provenance checks or portfolio aggregation.

## Validation evidence

See `tests/test_client_delivery.py`, the fixture generator, rendered review
pages, `GOAL_C_1_FIDELITY_REVIEW.md`, `GOAL_C_1_ADVERSARIAL_REVIEW.md`,
`GOAL_C_1_CLIENT_SIMPLICITY_AUDIT.md`, and `GOAL_C_1_VISUAL_REVIEW.md`.
