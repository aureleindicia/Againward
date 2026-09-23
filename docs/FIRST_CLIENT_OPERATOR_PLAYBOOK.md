# Rental internal investigation and short owner handoff (rehearsal pending)

This is the current Termux path, **not** a green light for real client data.
The intended analyst is Codex, which should execute, reconcile and write the
report internally. The founder should not reconstruct ordinary facts or write
the report. See [quality objectives](AUTONOMOUS_SERVICE_QUALITY.md),
[owner checklist](FIRST_CLIENT_OPERATIONS_CHECKLIST.md) and
[readiness plan](FIRST_CLIENT_READINESS_PLAN.md). The orchestration is not yet
fully autonomous, and a document may be readable without being understood.

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

The internal Codex analyst uses a fresh case ID and a controlled local source
directory. Do not use `--incoming` for real material before contract approval.
Examples below use placeholders and do not auto-approve anything.

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
python investigate.py documents independent-qa workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON EXTRACTION_JSON ... --model gpt-6-sol
python investigate.py documents review-template workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON EXTRACTION_JSON ...
```

`extract` sends approved source-unit content to the configured Codex service;
it may be unavailable or take substantial time. The independent pass rereads
the original sources without seeing the primary candidates. It currently
compares complete source-local entity bundles and flags differences; it does
not itself resolve them or certify report correctness. Keep extraction paths,
source hashes, model/prompt versions and its QA receipt. The template starts
with zero approved facts. Codex must inspect each original source, challenger
disagreement and worksheet, verify role, lines, equipment, dates, amount basis,
rate, stop trigger, credit and exact evidence, then write an `ANALYST` review
with explicit reason for each ACCEPT/REJECT/DEFER. Resolve only flags justified
by source evidence. Do not assign `HUMAN` to the analyst's routine review.
When accepted model facts come from a scan, a real operator inspects the
rendered original page and those limited facts through the interactive,
source/pixel/candidate-bound command:

```sh
python investigate.py documents visual-fact-attest workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON ANALYST_FACT_REVIEW_JSON EXTRACTION_JSON ... --actor-id OWNER_ID
```

Use the emitted attested review path for the next commands. A scripted test
attestation is not a human inspection. Then Codex continues:

```sh
python investigate.py documents promote workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON ATTESTED_OR_NATIVE_ANALYST_REVIEW_JSON EXTRACTION_JSON ...
python investigate.py documents link-review-template workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON ATTESTED_OR_NATIVE_ANALYST_REVIEW_JSON EXTRACTION_JSON ...
python investigate.py documents package-rental workspaces/CASE_ID/processed/documents BATCH_RECEIPT_JSON ATTESTED_OR_NATIVE_ANALYST_REVIEW_JSON EXTRACTION_JSON ...
```

`package-rental` creates the closed Rental package, replays every source and
fact review, and refuses unresolved material links. For ambiguous links, the
internal analyst must inspect the exact supporting/contradicting facts and supply
source-bound `--rental-links` or `--credit-links` review files; a fuzzy match
cannot be confirmed just because it looks plausible. The relationship-review
worksheet starts without a reviewer, time or decisions. Its matching fact IDs
are eligible support, not proof that a particular link is right. Escalate only
a genuinely unresolved, material relationship. The eight-document complete
rehearsal is **not yet complete**; this remains a Gate A blocker.

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
until the owner briefly inspects and approves the exact PDF, report, review and evidence
hashes. No generated `HUMAN` field counts as approval. If the gate fails,
inspect its reason and return to the underlying source/review; never edit a
hash or amount to force green. A changed PDF or source revokes approval.

For supplemental evidence during WAIT, first obtain authorization and stage
new bytes, run a **fresh** privacy review with `--supplemental`, create a new
source batch referring to the previous receipt, then resume the existing
question/evidence lifecycle. Old clearance does not apply to new files.

## Report and decision rules

For each positive amount, the internal analyst and adversarial QA must inspect
the accepted clause and source location, entity link, exact ledger period/formula, invoice,
return trigger, credits, alternative explanation, limitations and permitted
claim. Do not sum two finding families on the same group. A discrepancy is
not guaranteed recovery. If evidence supports no discrepancy, use “No
supported discrepancy in the supplied evidence”; do not turn missing evidence
into a zero or a fabricated saving. Ask only the few missing high-value items
that can change the decision, or STOP/abstain if unavailable.
