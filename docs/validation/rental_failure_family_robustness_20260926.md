# Rental model-contract robustness pass — 2026-09-26

This is a bounded engineering pass over previously observed Rental extraction,
adjudication, and review failures. It is not accuracy validation and makes no
claim about the final ≥99% target.

## Scope and implementation

The model-facing Rental extraction schema now closes native `semantic_type`
values to the Rental vocabulary, bounds `limitations`, and continues to require
the existing typed candidate fields. `entity_kind`, `document_role`, and
`document_status` must be `ENUM`; monetary amount fields remain `DECIMAL`, with
currency separate as `CURRENCY`. Runtime validation also checks the structural
values against the canonical Rental sets. Adjudication continues to use its
closed response schema and selection enum; a malformed adjudication response
gets at most one schema-focused retry, then fails closed. Review lifecycle
states remain closed and explicit.

A new deterministic Rental preflight runs immediately after primary and
challenger proposals are source-validated, before the source-QA workflow. It
checks that each candidate entity group contains source-bound structural
metadata, validates canonical structural values, and identifies an explicit
observation/absence-limitation contradiction. It does not fill missing values.
Structural omissions allow one source-bound model retry; the retry asks the
model to re-inspect the same source and emit only supported canonical fields.
If they remain missing, the workflow fails closed with
`STRUCTURAL_INCOMPLETE`. Schema and exact-citation failures retain their
existing one-retry behavior. Semantic contradictions and true ambiguity are
not repaired automatically.

The same local structural validator now checks any new pixel observations from
adjudication before they can proceed to fact review. If an adjudicator-created
observation splits from its required structural metadata, adjudication gets one
bounded source-pixel retry. If the source cannot establish the metadata, the
instruction is to omit the new observation and leave the disagreement
unresolved. Neither attempt approves a fact.

Internal diagnostics map legacy stop codes to the stable categories
`SCHEMA_ERROR`, `STRUCTURAL_INCOMPLETE`, `SEMANTIC_CONTRADICTION`,
`SOURCE_EVIDENCE_MISSING`, `AMBIGUOUS_SOURCE`, `MODEL_INVOCATION_ERROR`, and
`REVIEW_REQUIRED`. Receipts retain only bounded structural information,
including missing structural field names and retry count; they do not retain
candidate quotes, source text, or raw model responses in ordinary workspaces.

Exact native quotes/spans, source and render hashes, mutation checks, visual
review and attestation gates, HUMAN semantics, contract authority, promotion
requirements, and Rental arithmetic are unchanged. Existing synthetic Rental
fixture annotations were updated to use `ENUM` for structural values; their
meanings and expectations were not relaxed.

## Generic failure-family regressions

`tests/test_rental_failure_families.py` covers exact-native-quote rejection,
numeric money typed as `CURRENCY`, incomplete `entity_kind` / role / status,
closed structural values, incomplete supporting-rate entities, contradictory
observation and absence limitation, closed adjudication selection, visual
handoff state, split entity grouping, diagnostic retry count and the error
category mapping. `tests/test_document_adjudication.py` also proves that a
pixel-only observation with incomplete grouping triggers one retry, and that a
corrected adjudication remains an unapproved result for normal fact review.

## Fresh known-case runs

All runs below used byte-identical copies of the known case inputs in newly
created synthetic evaluation workspaces, `gpt-6-luna`, Codex CLI `0.156.1`,
and the regular Rental workflow. They are regression runs only. No oracle or
financial result was supplied to the model, no HUMAN evidence was fabricated,
and no calculation/report was forced.

| Case/run | Progress and local validation | Final state |
| --- | --- | --- |
| CASE A, fresh run 1 | Two primary and two challenger reads; QA resolved two disagreements. No calculator reached. | `FAILED / UNSUPPORTED_PROMOTION` at native `FACT_REVIEW`. The terminal receipt did not identify a candidate; treated as a separate blocker and left unchanged. |
| CASE A, fresh run 2 | Source and pixel review reached; the visual review reported one pixel-created entity missing `entity_kind`, `document_role`, and `document_status`. This exposed that adjudicator-added candidates also needed preflight validation. | `REPAIR_REQUIRED` at `VISUAL_FACT_REVIEW`; no calculation. This observation motivated the bounded adjudicator preflight above. |
| CASE A, fresh run 3 | Two primary and two challenger reads; zero material disagreements; adjudication completed; native fact review and visual model review ran. No structural repair was needed in these responses. | `FAILED / REVIEW_STALE` at `VISUAL_FACT_REVIEW`; no calculation or report. This is a distinct downstream blocker and was not changed. |
| CASE B, fresh run 1 | Stopped on `supplier_email.eml` / `entity_kind` during primary extraction. | `STRUCTURAL_INCOMPLETE`; no source QA or calculation. |
| CASE B, fresh confirmatory run | The email structural omission was corrected by one retry and accepted. Two primary sources were then stored. On `accounting_export.xlsx`, one entity still lacked `document_role` and `document_status`; the local check stopped after exactly one retry. | `STRUCTURAL_INCOMPLETE` at `PRIMARY_EXTRACTION`; diagnostic has `retry_count=1`, model `gpt-6-luna`, source ID, schema path, code, and missing field names. No source QA, calculation, or report. |

The accounting export run therefore demonstrates both outcomes of bounded
repair: a source-supported email group was repaired once; an incomplete export
entity remained fail-closed after one retry. The failed receipt contained no
entity label, quotes, or raw output. The later CASE A `REVIEW_STALE` reason is
not sufficiently field-specific to diagnose in this pass and remains the next
known blocker there.

Financial oracles were not reached in these runs: CASE A EUR 150 and CASE B
LIFT-5 EUR 150 / LIFT-50 EUR 0 remain unverified by this pass. No PDF QA was
reached.

## Checks

- Failure-family and related document/adjudication/source-job suites: **98 passed** on the main robustness commit; the schema-retry regression tests passed on the follow-up.
- Ruff: passed.
- Configured mypy: passed (16 source files).
- Rental benchmark: **15/15**.
- Privacy benchmark: **19/19**.
- Clean full pytest at follow-up `41b5488`: **900 passed in 586.01 s**.
- PR #5 CI at `41b5488`: **8/8 jobs passed**, Python 3.11–3.14 across both configured workflows.

The initial dirty-tree full-suite attempt found one stale test expectation for
the newly expected pair of sanitized diagnostics (first rejected response and
bounded retry). Two HOLDOUT tests also correctly rejected an uncommitted engine
tree. The assertion was updated to check both sanitized receipts; the complete
suite was then rerun after committing the engine and passed. The HOLDOUT checks
were not changed.

The small benchmarks remain scripted policy/arithmetic fixtures. They do not
measure model extraction accuracy or independent material correctness.

## Final local Luna pass — 2026-09-26

This is a fresh-workspace regression follow-up on code commit
`380c0e8be80a48a457d252da002506f72e48c6c1`, using `gpt-6-luna` and Codex CLI
`0.156.1`. It used only the two known synthetic cases. Sources were copied
byte-for-byte from the earlier known workspaces and their SHA256 values were
checked. No unseen case, oracle prompt, manual repair, or additional model
retry was used. Evaluation artifacts remain in ignored `scratch/`; no raw model
answer or source file was added to Git.

| Case | Fresh-run result | Financial/report result |
| --- | --- | --- |
| A, scanned invoice | The prompt-version registry no longer rejects the visual prompt. Primary and challenger reads and source QA completed with zero material disagreements; native fact review and a source/pixel-bound MODEL visual review completed. `load_document_case` then failed closed with `EXTRACTION_INCOMPLETE`: the reviewed `INVOICE_LINE` lacks `invoice_line_id`, `charge_key`, and `charge_type`. The selected visual observation has an invoice ID, agreement, asset, dates, quantity, amount, and EUR currency, but those three required charge fields were absent. No HUMAN approval was created. | No deterministic calculation, EUR 150 oracle, report, or final PDF QA. |
| B, eight-source Rental dossier | The fresh job stopped during `PRIMARY_EXTRACTION` on `accounting_export.xlsx`. Its final structural diagnostic is `STRUCTURAL_INCOMPLETE`, `ENTITY_METADATA_REQUIRED`, path `$.candidates[].entity_id`, with `document_role` and `document_status` missing after exactly one retry (`retry_count=1`). The workbook contains invoice and credit rows and “Mirror only” notes; the corrected contract accepts source-level role/status rather than requiring duplicates per row. The final model proposal still supplied no accepted source-level values. Because the rejected raw answer is not retained in the ordinary receipt, the exact omission pattern across the original and retry responses cannot be compared. | No source QA completion, calculation, LIFT-5 EUR 150 / LIFT-50 EUR 0 oracle, report, or final PDF QA. |

The direct `load_document_case` replay for CASE A confirmed the first new
downstream failure as the missing invoice-line fields above; the workflow's
safe terminal diagnostic itself reports only the stable category and stage.
The visual candidate remained a MODEL-reviewed observation. Neither that
receipt nor the source QA receipt is a HUMAN attestation, and the run did not
approve delivery. No promotion or financial invariant was weakened.

These results separate the fixed local causes from what remains. CASE A's
earlier `REVIEW_STALE` was a deterministic registry omission: the current
prompt-version registry did not include the visual extraction prompt variant
that the workflow had emitted. Tests now enumerate and accept current native,
visual, QA, and bounded-structure-retry variants. CASE B's previous row-scoped
preflight mismatch was corrected to use source-scoped role/status, matching the
document adapter. The fresh Luna output nevertheless remained structurally
incomplete. This supports a localized contract/generation failure, not a broad
claim that the whole architecture is causally unsound. The remaining stops
must stay fail-closed until their missing evidence is supplied or a separately
scoped diagnosis establishes a generic correction.

On this commit, full pytest passed **905 tests** in **580.87 s**; Ruff passed;
configured mypy passed for 16 source files; Rental benchmark passed **15/15**;
privacy benchmark passed **19/19**. PR #5 CI passed all **8/8** Python 3.11–3.14
jobs in each of the two latest runs. PR #5 remains open and draft. This pass
reached neither known financial oracle and provides no new accuracy evidence.
