# Rental fact-level reconciliation, Phase 2

## Scope

Engineering validation of source-bound fact reconciliation and rate-dimension
normalization. Historical A01/A02/B01 evaluation artifacts were inspected
offline. No new CASE A/B end-to-end run was launched and no oracle values were
used to choose behavior.

## Causal findings

- The A01/A02 agreement-source differences were largely presentation changes:
  the same source facts were split between document-envelope and material
  groups. A deterministic identity is supportable only when the current source
  uniquely states the rental-agreement role, one rental-scope kind, one
  agreement ID and one asset ID. The invoice difference is distinct: its
  document-status readings conflict, so it remains a real source metadata
  disagreement and is not unioned.
- B01's rate-dimension rejection was a field-projection mismatch. The model's
  value described one dimension while its exact source quote expressed a
  composite denominator. The prior validator compared the whole composite
  with a single field. The quote can be decomposed without trusting the
  incompatible model value; competing expressions and unsupported calendar
  conventions remain fail-closed.
- Fact union also exposed an output-shape gap: source-bound invoice identity
  could be split from the invoice-line entity during deterministic assembly,
  even though that exact ID is required on the canonical line. QA now scopes
  it to a line only when the source extraction already establishes a typed,
  anchored invoice line.

## Change

Primary and challenger observations are canonicalized before QA. When their
material facts are complementary and every material observation has a safe
source-local anchor, Python creates a deterministic, unapproved union. Its
receipt binds both exact parent extractions, dispositions, source identity and
current hashes. Conflicts, limitations, unanchored material facts and stale
bindings still prevent automatic union. The union is then replayed and checked
through QA and the existing review gates; no fact is approved by reconciliation.

Rate normalization now quarantines a model value that conflicts with one
unambiguous dimension expression in its own exact quote and preserves the
quote-derived dimensions. Ordinary diagnostics contain hashes and the rejection
reason, not the quote itself; private evaluation-only artifacts retain the
already-authorized raw response. Multiple competing expressions are quarantined
as incomplete; unsupported calendar conventions still stop.

## Evidence and limits

Generic tests cover reordered/relabelled facts, complementary anchored reads,
source metadata conflicts, invoice-line identity scope, ambiguous or
unsupported rates, preserved citation spans and immutable parent lineage.
These tests show that the examined representation variants can be reconciled
without weakening provenance. They do not establish live-model repeatability,
CASE A/B calculation success, or client-population accuracy. A fresh independent
Luna smoke remains necessary after this commit.
