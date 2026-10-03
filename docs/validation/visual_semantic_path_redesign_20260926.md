# Visual semantic path redesign — 2026-09-26

This is known-regression evidence for the visual-path redesign, not blind or
population-level accuracy evidence. The code change is
[`04a299080cdfa2f4e39f4c444d8abfa8ce253fea`](https://github.com/aureleindicia/Againward/commit/04a299080cdfa2f4e39f4c444d8abfa8ce253fea), based on
`8867329fae032fcbb07be8e144d0927a5fc0d681` on
`release/first-rental-client-pilot`. No unseen DEV/adversarial case was opened.

## Design change

The visual first read now asks for typed semantic observations from attached
original page pixels. It does not ask the model to produce source IDs, hashes,
unit hashes, spans, byte offsets, or internal candidate IDs. A descriptive
entity hint, visible wording, value/type, page number and ambiguity are the
model-facing fields. Native text remains on the previous exact-substring and
exact-span path; native serialized extraction receipts retain their prior shape
when they contain no visual evidence.

Python binds visual observations after the response to the current source ID
and SHA256, page/unit hash, rendered-page SHA256, reader/render version, DPI,
model, prompt and invocation ID. Visual candidates remain unapproved and
component-review-required. Source mutation and stale render checks remain
fail-closed. The independent reread remains; visual comparison uses semantic
facts. Pixel adjudication can add a newly observed fact to the unapproved queue,
but only current source/page/render-bound fact review can promote it. Ambiguity,
HUMAN fallback, deterministic calculations and final QA gates remain.

PDF visual pages use Poppler at 300 DPI (`againward-poppler-png-300dpi-v1`);
existing page, byte and render-time limits remain in force. Diagnostic records
are written to the private workspace `scratch/visual_model_diagnostics/` with
mode 0600. Ordinary workflow records contain only safe rejection metadata;
complete raw model responses are retained only in evaluation-only workspaces.

## Runtime and policy binding

- Model explicitly selected: `gpt-6-luna`.
- Codex CLI: `0.156.1`.
- Prompt: `againward-source-facts-v6-native-preserved-visual-observations`
  with Rental guidance hash bound per source invocation.
- Extraction: `codex-cli-source-units-v2-visual-bound`.
- Independent reread: `rental-independent-source-reread-v2`.
- Adjudication: `againward-source-adjudication-v6-pixel-observations`.
- Visual promotion receipt: `againward-visual-model-evidence-v2-300dpi`.
- PDF renderer binding: `againward-poppler-png-300dpi-v1`.
- Workspaces: fresh evaluation-only CASE A and CASE B workspaces under ignored
  `scratch/visual_semantic_redesign_20260926_v3/`; source bytes were copied
  unchanged and checked by SHA256.

## Live CASE A — `c06894c2744f1010`

Sources: `billing.pdf` SHA256
`2d25acb7869713ad72c6180a458d626d15f8ef1a05864c22710df155b8eb6ea7`;
`commercial.pdf` SHA256
`312c2c6d5742c685112669e7c54b8cf8445be620675d34f5b18bbd5128537065`.

The primary visual read produced 15 unapproved candidates; the independent
visual reread produced 13. Both included invoice `INV-79732`, net EUR 2,670.00,
the LIFT-9003 asset, quantity 4 and the displayed service dates. Current pixel
bindings were validated at 300 DPI: page unit SHA256
`14f60b1db6fa2194b83e2cf6e90733f429fb1711ab66980488709502139ec9b9`, render
SHA256 `d262736fee4ce413130c3e0eff59d28e3f367ea699b717aa857d3ca8445490f8`.
Primary invocation `a91f926c-cc32-4d9d-957e-46bb98740f7d`; challenger
invocation `fa378a88-07e2-4e58-8d4d-e1455e5e2a94`. Independent comparison
completed and found
two material source disagreements. A model adjudication call with the original
visual attached was attempted under the normal bounded workflow; the call
returned `MODEL_UNAVAILABLE` and no adjudication receipt was accepted. The
workflow ended `WAITING_MODEL_RETRY` at source adjudication. No visual/fact
review, calculation, report, PDF QA, HUMAN escalation, or finding was produced.
Known expected result: EUR 150 discrepancy. Actual deterministic result:
none; EUR 150 was not reached.

## Live CASE B — known eight-source Rental DEV dossier

Source SHA256 values (all eight input files):

| Source | SHA256 |
|---|---|
| `supplier_email.eml` | `1a54df7c6524bfe066e05f664fc09b4d567b614f9ab003d0204764542fe2ea42` |
| `issued_credit.pdf` | `1c155ef52e0f9c6f570949b39203cfc36b30ba4e0fbd1daac2eb52c7c68d9729` |
| `accounting_export.xlsx` | `45fe271a8a035d9b8229fbee454b1f5e19bf5140155747e83fcb54a940d77b0d` |
| `accepted_rate_sheet.pdf` | `4859e47b714ae15d80b98eeeed9598cc05aae4d9f3e9b66b3fa00d34d4a37f6b` |
| `accepted_agreement.pdf` | `507b47a239dbcad34da5030673d3886f97f6a580b1f4ab998797e2e7b50a6a2b` |
| `signed_return_scan.pdf` | `86adf5d440419a956208ab35c3292b0ab6e0d39f1158fc614a337d988ce747a4` |
| `invoice_02.pdf` | `ac8d41f4bc5455bb5bdede7498a363f9c8c13b573111491220fb34dbe10c312b` |
| `invoice_01.pdf` | `b86d1e5152c8ada26525100963f453956ec67fc2ab9a21f2dc11a939f3770efb` |

All eight primary source reads completed. The signed-return scan produced 16
unapproved visual candidates, including signed return evidence for LIFT-5 on
2026-09-05, while keeping LIFT-50 a separate item. Its source/page/render
binding validated at 300 DPI: unit SHA256
`19b21ad23573f1e1ef7af75e28f0c02541c9e174c81f9254ad8631c0eb619549`, render
SHA256 `42c3a4a41233bc1ec2ba5b050e437f5e7f96e70c9234525f94b360eb23316411`,
primary invocation `8d622711-5a42-409d-a6b8-bae845a625e0`. The independent
challenger had not started. The job failed before independent reread while
processing the first challenger source (`supplier_email.eml`), with
`SOURCE_LOCATION_INVALID`. Inspection of the private evaluation diagnostic
showed that the native unit location existed (`part:1`), but some model-emitted
quotes were not exact substrings of that unit (for example a reformulated
explanatory sentence or a newline-altered quote). This is the preserved native
exact-span safety check, not a visual binding rejection. No challenger QA,
adjudication, fact review, calculation, report or PDF QA was reached. No fact
was promoted and no HUMAN evidence was created. Known DEV oracle: LIFT-5 EUR
150 discrepancy; LIFT-50 EUR 0. Neither amount was calculated in this run.

## Regression coverage and validation

Focused tests cover hash/page binding after an observation without hashes,
impossible pages, source/render mutation, challenger-only evidence, new
adjudicator-origin observations, rejection of promotion bypass, ambiguous
pixel fallback, native exact-span validation and calculation exclusion of
unreviewed observations. Failure diagnostics distinguish semantic values
present before rejection and emitted versus valid page/unit identifiers; raw
responses remain evaluation-only.

- Focused source/adjudication/visual tests: **65 passed** after the final code
  change.
- Ruff: **passed**.
- Configured mypy: **passed**, 16 source files.
- Full pytest on committed implementation: **847 passed in 491.74 s**, 0
  failed/skipped.
- Rental benchmark: **15/15**, 3 TP, 0 FP, 0 FN, 12 TN.
- Privacy benchmark: **19/19**, 0 false blocks, 0 unsafe passes.
- PR #5 CI on the pushed implementation/documentation checkpoint
  `582f81558d5e84951ff72ee9caf9a1bbabd3c209`: both push and pull-request
  workflows passed all 8 matrix jobs (Python 3.11, 3.12, 3.13 and 3.14).

The first full-suite attempt before the native compatibility correction found
that native proposals were incorrectly required to carry visual keys. The
contract was corrected so native proposal payloads and receipt hashes retain
their previous shape. A HOLDOUT engine-integrity test also requires a committed
engine and is rerun from the code commit.

## Assessment and limitations

The redesign demonstrably changed visual first-read behavior on CASE A and the
signed scan: both readers now returned useful source/page-bound observations,
unlike the prior zero-candidate results. It has not yet demonstrated recovery
through pixel adjudication or downstream deterministic results. CASE A stopped
at model adjudication with `MODEL_UNAVAILABLE`; CASE B stopped on a native exact
quote mismatch before independent reread. No unsupported fact was promoted,
no HUMAN evidence was fabricated, and no amount was calculated. The result is
**PARTIALLY_FIXED**, not a successful source-to-report visual path and not an
accuracy estimate. The next engineering decision should first diagnose the
adjudication model invocation failure and the native email quote mismatch from
safe runtime metadata; do not relax exact native source spans or visual
promotion gates.
