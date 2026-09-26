# Fail-closed diagnostic observability — 2026-09-26

This is a known-case engineering and observability record. It is not accuracy
validation. No production semantics, prompts, provenance checks, financial
rules, or promotion gates were changed.

## Binding and run conditions

- Branch: `release/first-rental-client-pilot`.
- Starting repository HEAD: `ea73fea73fefea0b2875389dd3836e328e7a4531`.
- Production candidate under investigation: `30c4d9a8f54f075a5a0673c7c157c0926471e55c`.
- Diagnostic implementation commit: `2969dee989eb68f419d376b0e18c71d29c8d2585`.
- Runtime: `gpt-6-luna`; Codex CLI `0.156.1`; adjudication policy
  `againward-source-adjudication-v9-entity-consistent-pixel-observations`.
- Extraction prompt binding: `againward-source-facts-v9-entity-structure-limits-e6da799673e9a71a`.
- Each replay used a newly created synthetic evaluation workspace and fresh
  source/model artifacts. Source bytes were copied from the prior known-case
  workspaces and SHA-256 compared before running.
- CASE A hashes: `billing.pdf` `2d25acb7869713ad72c6180a458d626d15f8ef1a05864c22710df155b8eb6ea7`;
  `commercial.pdf` `312c2c6d5742c685112669e7c54b8cf8445be620675d34f5b18bbd5128537065`.
- CASE B used the same eight source hashes recorded in
  [the prior stabilization record](source_limitation_and_native_entity_stabilization_20260926.md).

## Diagnostic changes

Adjudication validation now records a stable, content-safe diagnostic with the
stage, source ID when known, decision index, exact schema path, stable
validation code/category, expected type, received shape, bounded retry count,
model and prompt/schema versions, CLI version, and invocation/prompt/schema/
response hashes. Incomplete decisions also identify the missing source
coverage or evidence condition. Terminal source-job events retain only this
allowlisted structured diagnostic and the reason code.

Ordinary workspaces never persist raw adjudicator responses, source quotes, or
exception text in these diagnostics. In synthetic `evaluation-only` runs, raw
response details may be held in the existing private
`scratch/visual_model_diagnostics/` directory, mode `0600`; they are not copied
to ordinary receipts or committed. Tests verify both retention behaviors.

The validator remains fail-closed. Schema errors still raise
`EXTRACTION_SCHEMA_INVALID`; missing decisions/evidence still raise
`EXTRACTION_INCOMPLETE`; exact native spans, hash bindings, visual review and
fact-promotion requirements are unchanged.

## Fresh replay results

| Case | Replay outcome | Exact finding | Calculation/report |
| --- | --- | --- | --- |
| CASE A `c06894c2744f1010` | `FAILED / EXTRACTION_CONTRADICTION` during source adjudication | Decision 0, source `billing.pdf`; schema path `$.decisions[0].selection`; the selected primary proposal self-contradicts its absence limitation and its own observation of `net_amount`. The private evaluation response identified the semantic conflict as `net_amount`. This is a semantic disagreement, so no automatic repair was made. | No calculation or report. |
| CASE B known eight-source signed-return dossier | Adjudication resolved all 7 material disagreements (`unresolved=0`); then `WAITING_FOR_REQUIRED_INFORMATION` at `FACT_REVIEW / REPAIR_REQUIRED` | `supplier_email.eml`, source ID `src-1a54df7c6524bfe066e05f664fc09b4d567b614f9ab003d0204764542fe2ea42`, entity `email-1`, missing `entity_kind`. This is the next distinct structural review blocker. | No calculation or report. |

The previous CASE A `EXTRACTION_SCHEMA_INVALID` and CASE B
`EXTRACTION_INCOMPLETE` did **not** recur in these fresh responses. Their old
workspaces retained only terminal codes and had already discarded the
adjudicator response, so the historical field/decision cannot be reconstructed
without guessing. The new instrumentation is in place for any future
occurrence. In the CASE A replay, the response passed the closed schema and was
stopped later by the explicit source-completeness contradiction check. In CASE
B, adjudication completed and the workflow reached fact review, where the
remaining gap is now explicit.

These differing outcomes show model/workflow variation on the same known
source bytes; a single replay does not establish repeatability. The fresh
workspaces are ignored development artifacts and contain evaluation-only raw
model detail; they are intentionally not checked in.

## Regression and validation evidence

- Focused adjudication, source-job, and visual-limitation routing tests:
  **35 passed**.
- Ruff: passed.
- Configured mypy: passed (16 source files).
- Rental benchmark: **15/15**.
- Privacy benchmark: **19/19**.
- Full pytest on the clean committed tree: **873 passed in 609.71 s**, no
  failures or skips. The first dirty-tree attempt exposed six fixtures missing
  members already required by the live response schema and two expected
  HOLDOUT-integrity rejections. Fixtures were aligned with the existing schema;
  the clean run then passed, including the HOLDOUT checks.
- PR #5 CI: pending commit/push.

No schema/completeness validator was relaxed, no native span or hash/source/
render check changed, no review or attestation was bypassed, and no default
entity metadata or financial result was invented.
