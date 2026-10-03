# Known-case blocker stabilization — 2026-09-26

This narrow pass addresses three observed failures in two already-known Rental
cases. It changes only visual semantic guidance/provider wording and source
adjudication instructions. Native quote/span validation, evidence bindings,
fact-review requirements, and financial rules remain unchanged. These known
case reruns are regression diagnostics, not accuracy evidence.

## Root causes and minimal changes

### CASE A — visual structural metadata split across entities

Visual observations reached fact review but required `entity_kind`,
`document_role`, and `document_status` were absent from some entities. The
visual contract asked the model to group observations with `entity_hint`, but
did not make consistent grouping and complete source-supported structural
observations explicit enough. Separate hints split the metadata from the
invoice-line observations, leaving incomplete analytical entities. The
downstream completeness gate correctly returned `REPAIR_REQUIRED`.

The visual prompt and Rental guidance now require all three source-supported
structural observations on each material visual invoice line, with the same
entity hint as its line facts (`INVOICE_LINE` / `INVOICE` for a billed line).
A genuinely separate support statement gets its own complete entity. Missing
or ambiguous source metadata remains absent and is still rejected by review;
the prompt explicitly forbids defaults or cross-source completion.

Regression coverage:
`test_visual_invoice_reader_keeps_structural_metadata_on_the_billed_line`
checks the model-facing contract and the incomplete-metadata fail-closed path.

### CASE B — accepted rate sheet

The source states that the accepted sheet duplicates signed-agreement daily
prices and makes no amendment; it gives separate EUR 50/LIFT-5 and
EUR 30/LIFT-50 rows. The earlier adjudication prompt conflated selecting
source-supported rows for later fact review with establishing a complete
governing tariff. It could therefore reject the sheet for not restating the
agreement's start/stop/weekend/minimum conventions.

Adjudication now explicitly treats selection as source-local observation
selection, not contractual approval. It may select the two evidenced rows as
`SUPPORTING_DOCUMENT` observations while retaining the governing agreement as
authority for other conventions. It must not create a second tariff or charge.
The focused regression confirms a resolved selection remains unapproved and
creates zero facts.

### CASE B — signed return scan

The scan is legible and states that one of two LIFT-5 units, serial SN-L5-204,
was returned on 2026-09-05; the other remains on hire, and the LIFT-50 asset is
not returned by this record. The previous adjudication could treat different
grouping/wording as a material disagreement even when the original pixels
supported the same material event.

The adjudication prompt now asks for semantic comparison and allows a
source-supported selection when grouping alone differs. It also allows
source-visible omitted facts to enter as unapproved pixel observations for
normal fact review. It leaves genuinely competing readings unresolved. The
regression checks that pixel reopening resolves the grouping-only difference
without approving facts or delivery.

## Fresh known-case reruns

Both runs used fresh evaluation-only workspaces, unchanged known source bytes,
the current code/prompt/policy generation, and `gpt-6-luna`.

### CASE A — `c06894c2744f1010`

Two primary reads and two independent rereads completed. Source QA found one
material disagreement. Pixel adjudication resolved it (`unresolved=0`) and
created an extraction whose structural observations share one entity hint:
`INVOICE_LINE`, `INVOICE`, and `ISSUED`; it includes invoice `INV-79732` and
net amount EUR 2,670. No facts were approved by adjudication.

The workflow then failed closed with `EXTRACTION_INCOMPLETE` before native fact
review. The selected extraction is `NEEDS_REVIEW` and carries the limitation
“Only page 1 was provided; no rates or invoice total are visible,” while that
same extraction contains `net_amount=2670.00`. This is a new contradictory
completeness/limitation blocker, not one of the three targeted fixes. No
calculation, report, PDF QA, or EUR 150 oracle result was reached.

### CASE B — known eight-source signed-return dossier

All eight primary reads and all eight independent rereads completed. Source QA
reported six material disagreements. Adjudication completed with
`unresolved=0`; the accepted rate sheet selected its evidenced EUR 50 and EUR
30 rows as supporting observations, and the return scan was resolved from its
original pixels. Neither action approved facts.

The run stopped at `FACT_REVIEW` with `REPAIR_REQUIRED`. Five structural gaps
remain in native-source proposals: the supplier email, accounting export, and
accepted rate sheet. The gaps are respectively missing `entity_kind` on the
email entity; missing role/status on its off-hire entity; missing role/status
on the accounting mirror entity; and missing `entity_kind` on each rate-sheet
support entity. These are distinct native-source structural repair failures;
the visual prompts and adjudication changes did not bypass them. No facts were
promoted, no calculation/report/PDF QA was reached, and the known LIFT-5 EUR
150 / LIFT-50 EUR 0 oracle was not calculated.

No HUMAN attestation or other approval was fabricated in either run.

## Validation

- Targeted provider/adjudication tests: **32 passed**.
- Ruff: **passed**.
- Configured mypy: **passed**, 16 source files.
- Rental benchmark: **15/15**; 3 TP, 0 FP, 0 FN, 12 TN.
- Privacy benchmark: **19/19**; 0 false blocks and 0 unsafe passes.
- Full pytest on the dirty working tree initially produced **857 passed, 2
  failed** in 499.03 seconds. Both failures were HOLDOUT integrity tests that
  correctly reject an engine changed relative to its referenced commit. After
  committing the engine change, full pytest passed: **859 passed** in 537.64
  seconds.
- PR #5 CI on commit `34bd35f3625532dfe6fc87a43a5c18277227827c`: **8/8** matrix
  checks passed (Python 3.11–3.14 across push and pull-request workflows). PR
  #5 remains open and draft.

The benchmark results are scripted checks. These two known-case runs do not
measure unfamiliar-case accuracy and do not support a ≥99% claim.
