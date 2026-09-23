# Single-operator Rental pilot playbook (candidate; rehearsal pending)

This is the shortest supported path currently available on Termux. It is **not**
a green light for real client data. See [owner checklist](FIRST_CLIENT_OPERATIONS_CHECKLIST.md)
and [readiness plan](FIRST_CLIENT_READINESS_PLAN.md). A document may be
machine-readable without its business meaning being approved.

## Input and preflight

Request one accepted Rental agreement/rate sheet, two invoices including
line-level net EUR amounts, any issued credit note, dated return or off-hire
evidence, relevant supplier correspondence and an export spreadsheet. For
each claimed term identify accepted status, equipment/serial, daily billing
convention, start/stop event and whether credits apply to the exact line.
The eight-file folder is a **test envelope**, not an automatically safe cap.
Weekly/monthly partial returns, conflicting accepted terms, unallocated
credits, gross-only charges, mixed currency or missing pages require explicit
review/clarification or exclusion before a positive finding.

## Exact local flow

Use a fresh unique case ID and a separately controlled, local source directory.
Do not use `--incoming` for real material before contract approval. Examples
below use placeholders and are not a script that auto-approves anything.

```sh
python create_workspace.py --domain rental CASE_ID
python manage_investigation.py contract-record workspaces/CASE_ID CONTRACT_PACKET_JSON
python manage_investigation.py stage-incoming workspaces/CASE_ID AUTHORIZED_DROP_DIRECTORY
```

Codex must perform the first semantic privacy read of **all** `incoming/`
components under the authorized provider configuration. It then supplies a
closed `privacy/review.json`, classifying high-risk data and preserving business
prices/terms. This is a human/agent judgment step, not automatically generated
by the following commands. For visual components, the **operator** follows
[the visual SOP](VISUAL_REVIEW_OPERATIONS.md):

```sh
python manage_investigation.py privacy-visual-prepare workspaces/CASE_ID workspaces/CASE_ID/privacy/review.json
python manage_investigation.py privacy-visual-attest workspaces/CASE_ID workspaces/CASE_ID/privacy/review.json --actor-id OWNER_ID
python manage_investigation.py privacy-validate workspaces/CASE_ID workspaces/CASE_ID/privacy/review.json
```

If there are no visual components, skip the two visual commands. A refusal
leaves the case blocked. Only after clearance, snapshot and inspect the
approved bytes; keep DOCUMENT_ROOT under this case's `processed/`:

```sh
python investigate.py documents inventory workspaces/CASE_ID/sanitized workspaces/CASE_ID/processed/documents
python investigate.py documents inspect workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON
python investigate.py documents extract workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON --model gpt-6-sol
python investigate.py documents review-template workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON EXTRACTION_JSON ...
```

`extract` sends approved source-unit content to the configured Codex service;
it may be unavailable or take substantial time. Keep the saved extraction
paths, source hashes, model and prompt versions. The template starts with zero
approved facts and all decisions DEFER. Open each original approved source and
worksheet. Verify role, invoice line, equipment, dates, net/gross, rate, stop
trigger, credit status/allocation, quote, location and any visual transcription.
Reject/defer doubtful candidates; record meaningful reasons and the actual
reviewer/time. Do not resolve a contradictory flag without source proof. Then:

```sh
python investigate.py documents promote workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON COMPLETED_FACT_REVIEW_JSON EXTRACTION_JSON ...
```

The current CLI does **not yet** fully assemble and review the Rental document
package or all entity-link decisions from this promotion artifact. Until an
end-to-end operator rehearsal proves that step practical, it is a **Gate A
blocker**: an ordinary operator must not improvise dozens of internal JSON
records for a paying client. `docs/REAL_WORLD_DOCUMENT_ARCHITECTURE.md` defines
the exact `againward-rental-document-case-v1` package and strict link review.

When a reviewed canonical package exists, the existing downstream commands
prepare Rental calculations and Evidence Plane, collect explicit assessments,
test alternatives, mark source exhaustion/finalizability and render a PDF:

```sh
python investigate.py --domain rental DOCUMENT_CASE_JSON --output-dir workspaces/CASE_ID/processed
python manage_investigation.py status workspaces/CASE_ID
python manage_investigation.py rental-review workspaces/CASE_ID COMPLETED_ASSESSMENTS_JSON
python manage_investigation.py data-exhausted workspaces/CASE_ID artifact_inventory.json REVIEWED_SOURCE_NAME ...
python manage_investigation.py finalizable workspaces/CASE_ID investigation.json
python manage_investigation.py rental-report workspaces/CASE_ID SYNTHESIS_MD
python manage_investigation.py check workspaces/CASE_ID
```

The report renderer rejects free unvalidated numbers. It produces a five-page
client PDF and evidence pack from reviewed calculations; `check` must stay red
until a real operator approves the exact PDF, report, review and evidence
hashes. No generated `HUMAN` field counts as approval. If the gate fails,
inspect its reason and return to the underlying source/review; never edit a
hash or amount to force green. A changed PDF or source revokes approval.

For supplemental evidence during WAIT, first obtain authorization and stage
new bytes, run a **fresh** privacy review with `--supplemental`, create a new
source batch referring to the previous receipt, then resume the existing
question/evidence lifecycle. Old clearance does not apply to new files.

## Report and decision rules

For each positive amount, the operator must inspect the accepted clause and
source location, reviewed entity link, exact ledger period/formula, invoice,
return trigger, credits, alternative explanation, limitations and permitted
claim. Do not sum two finding families on the same group. A discrepancy is
not guaranteed recovery. If evidence supports no discrepancy, use “No
supported discrepancy in the supplied evidence”; do not turn missing evidence
into a zero or a fabricated saving. Ask only the few missing high-value items
that can change the decision, or STOP/abstain if unavailable.
