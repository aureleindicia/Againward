# Source limitation and native entity stabilization — 2026-09-26

This is a known-case engineering regression record. It does not add accuracy
evidence and does not replace the historical runs in the earlier validation
artifacts.

## Binding

- Branch: `release/first-rental-client-pilot`
- Production candidate: `30c4d9a` (`Distinguish absent totals from existing net amounts`)
- Runtime model: `gpt-6-luna`
- Codex CLI: `0.156.1`
- Extraction prompt contract: `againward-source-facts-v9-entity-structure-limits`
- Rental guidance: `GUIDANCE_VERSION` v13
- Adjudication contract: v9
- Fresh evaluation workspaces: `case_a_c06894c2744f1010_final_v3_20260926`,
  `case_a_c06894c2744f1010_final_v4_20260926`, and
  `known_eight_source_signed_return_final_v3_20260926`
- CASE A input SHA256: `billing.pdf`
  `2d25acb7869713ad72c6180a458d626d15f8ef1a05864c22710df155b8eb6ea7`;
  `commercial.pdf`
  `312c2c6d5742c685112669e7c54b8cf8445be620675d34f5b18bbd5128537065`.
- CASE B retained the same eight source hashes as the known dossier: supplier
  email `1a54df7c6524bfe066e05f664fc09b4d567b614f9ab003d0204764542fe2ea42`,
  issued credit `1c155ef52e0f9c6f570949b39203cfc36b30ba4e0fbd1daac2eb52c7c68d9729`,
  accounting export `45fe271a8a035d9b8229fbee454b1f5e19bf5140155747e83fcb54a940d77b0d`,
  rate sheet `4859e47b714ae15d80b98eeeed9598cc05aae4d9f3e9b66b3fa00d34d4a37f6b`,
  agreement `507b47a239dbcad34da5030673d3886f97f6a580b1f4ab998797e2e7b50a6a2b`,
  signed return scan `86adf5d440419a956208ab35c3292b0ab6e0d39f1158fc614a337d988ce747a4`,
  invoice 02 `ac8d41f4bc5455bb5bdede7498a363f9c8c13b573111491220fb34dbe10c312b`,
  and invoice 01 `b86d1e5152c8ada26525100963f453956ec67fc2ab9a21f2dc11a939f3770efb`.

## Root causes and narrow changes

### CASE A — limitation wording and source-bound amount

The extraction carried a supported `net_amount=2670.00` alongside this
limitation: “Page 1 does not show a unit rate or separate line amount beyond
the stated net amount.” The earlier contradiction detector searched for the
phrase “net amount” anywhere in an absence limitation. It therefore mistook a
statement that no *additional* amount exists beyond the stated net amount for a
claim that the observed net amount is absent.

The detector now recognizes this bounded “separate/additional amount beyond
the stated net amount” wording as scope clarification. It retains the
limitation, keeps the source/page/render bindings, and still routes visual
facts through pixel review. A direct claim such as “No net amount is visible”
continues to fail closed as `EXTRACTION_CONTRADICTION`. No value or limitation
is silently discarded.

The v3 run before this correction failed closed on the overbroad phrase match.
The v4 run passed that point but ended after the bounded adjudication retry
with `EXTRACTION_SCHEMA_INVALID`. The workspace stores the terminal code and
stage but not the adjudicator's field-level validation message or raw response;
the precise schema member that failed cannot be recovered from this run. It
did not reach visual fact review, calculation, or report generation.

### CASE B — structural metadata contracts

The extraction prompt and Rental guidance described required entity metadata,
but did not spell out how it applies to each row of an accounting export or to
a non-governing accepted rate-sheet duplicate. The native reviewer also risked
confusing “supporting” with “not a valid entity.” The prompt, guidance, and
bounded repair instructions now request source-supported `entity_kind`,
`document_role`, and `document_status` on those entities, without inferring
them from a filename, a row type alone, or the fact that a rate sheet is not
governing. A supporting rate card remains supporting; the agreement remains
the governing source. Exact native quotes and spans are unchanged.

In the fresh v3 proposals, both readers emitted the full structural trio for
both accepted rate-sheet rows, and independent QA found no material rate-sheet
disagreement. The primary accounting-export pass emitted the trio on all three
rows; the challenger still omitted role/status on the credit row. For the
supplier email, the challenger emitted the trio while the primary omitted
`entity_kind`. The native prompts therefore improved representation, but live
pass-to-pass completeness is not yet consistent.

The CASE B run completed all 8 primary reads, all 8 challenger reads, and
source QA (`material_disagreements=7`), then stopped with
`EXTRACTION_INCOMPLETE` before FACT_REVIEW. No calculation or report was
produced. The state receipt does not retain an adjudication field-level
validation message, so the specific incomplete decision cannot be asserted.
The run does not establish whether the remaining structural omissions would
have blocked FACT_REVIEW.

## Results and validation

| Check | Result |
| --- | ---: |
| Focused source/adjudication/review/provider tests | 58 passed |
| Full pytest | 868 passed on the prior code commit; the clean-tree run for `30c4d9a` is in progress |
| Ruff | passed |
| Configured mypy | passed (16 source files) |
| Rental benchmark | 15/15; 3 TP, 0 FP, 0 FN, 12 TN |
| Rental privacy benchmark | 19/19; 0 false blocks, 0 unsafe passes |
| CASE A known EUR 150 calculation | not reached |
| CASE B known LIFT-5 EUR 150 / LIFT-50 EUR 0 | not reached |
| Report / final original-source PDF QA | not reached |
| HUMAN evidence or attestation fabricated | no |

The tests exercise fail-closed contradiction detection, retained page-scoped
limitations, source-supported EML/export/rate-sheet metadata, and entity
grouping for repeated pixel observations. They are scripted regression
evidence, not independent extraction accuracy.

## Remaining stop

CASE A's next stop is adjudication `EXTRACTION_SCHEMA_INVALID` after one normal
bounded retry; the exact invalid field is not persisted. CASE B's next stop is
adjudication `EXTRACTION_INCOMPLETE` after source QA. Both precede calculation,
report authoring, and final PDF QA. The known financial oracles remain
uncalculated. No unseen validation case was used, no Rental financial rule was
changed, and exact source spans, source/render hashes, review/promotion gates,
and HUMAN fallback semantics were not relaxed.
