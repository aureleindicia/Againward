# First Rental client — controlled autonomous-service release plan (2026-09-23)

Status: **NOT READY**. This is a preregistered, limited launch scope and test
plan, not a claim that a real client can be accepted now. Base is clean
`70f187e65fa1e977d14705804d0e790754c406aa` (PR #4); work proceeds on
`release/first-rental-client-pilot` stacked on PR #4. The original `main`
worktree's unrelated prospecting changes are untouched.

## Offer and frozen evaluation envelope

We verify equipment-rental invoices against supplied accepted terms and
operational evidence, identify documented billing discrepancies, and deliver
an evidence-based review/action dossier. Unsupported cases are clarified or
excluded. No savings, enforceability or recovery guarantee; no supplier contact
or payment action is delegated to the software.

The initial **evaluation envelope** is one supplier, one currency (EUR), net
amounts, one accepted agreement and rate sheet, two invoices, one issued credit,
one signed return/off-hire record, one supplier email and one export spreadsheet.
It is eight ordinary files, matching the tested privacy folder. This is not
yet a validated maximum: document count, invoice-line count, model time and
reviewer burden become the launch cap only after the representative end-to-end
run is measured. A case outside the measured envelope requires an explicit new
review, not an automatic financial answer.

| Capability | Pilot decision | Enforced fallback / evidence needed |
|---|---|---|
| Native-text PDF, CSV/XLSX cells, plain EML | SUPPORTED for inspection, not automatic semantic authority | Privacy clearance, full component inventory, model proposal and fact review. |
| Scan/image-only/hybrid PDF | REVIEW_REQUIRED | Exact source/page visual inspection by accountable operator; model may propose, never approve. No inspectable review → STOP. |
| Fixed daily EUR net rate, explicit billed quantity, documented start/return and day convention | Candidate SUPPORTED | Source-backed accepted clause, date and exact equipment link; Decimal ledger. Reclassify if benchmark detects silent error. |
| Daily partial return and accepted date-effective daily rate | Candidate SUPPORTED | Explicit quantity and effective-date evidence; otherwise REVIEW_REQUIRED. |
| Weekly/monthly rate with partial return, added quantities, minimum duration, weekend or unusual stop convention | REVIEW_REQUIRED / UNSUPPORTED for positive claims | Detect before calculation; request exact convention or exclude affected line. |
| Return, collection and off-hire request | REVIEW_REQUIRED until contractual stop trigger is identified | Never equate request with return. |
| Accepted rate amendment, conflicting clauses or multiple contract versions | REVIEW_REQUIRED | Explicit source priority/acceptance; no legal precedence inferred. No positive finding while unresolved. |
| Issued allocated/partially allocated credit | Candidate SUPPORTED | Exact invoice-line relationship; subtract only documented amount once. |
| Promised or unallocated credit, replacement/duplicate invoice | REVIEW_REQUIRED | Preserve possible offset and relationship uncertainty; no unsupported positive claim. |
| Gross/VAT amounts, mixed currencies, FX | UNSUPPORTED for pilot financial comparison | Detect and STOP/segregate; no guessed net amount or cross-currency sum. |
| Similar equipment IDs, missing serials, disputed links | REVIEW_REQUIRED | Exact reviewed anchors or abstention; no fuzzy confirmation. |
| Encrypted, corrupt, missing-page, active/opaque attachment or uninspectable source | UNSUPPORTED until safe source supplied | Fail closed with a concrete client request. |

“Candidate SUPPORTED” is a hypothesis pending model-driven benchmark and a
supervised dry run. The intake/preflight must enforce this matrix before any
client-facing financial claim; a document being parseable is not equivalent to
its business rule being understood.

## Baseline evidence and discrepancies

On Termux Python 3.14 from the clean base, `python -m pytest -q
--junitxml=scratch/first_client_baseline_pytest.xml` gave **748 passed in
286.86 s**. Energy characterization: 5 passed. Rental benchmark:
15/15 (TP 3, FP 0, FN 0, TN 12); its 1,000/10,000-line ledger runs took
0.251/2.547 s, excluding documents. Privacy benchmark: 19/19, 11 ordinary
accepted, eight risky refused, 0 false blocks/0 unsafe passes on scripted
fixtures. Ruff and configured mypy passed.

Fresh routing-only DEV seed 7421 and ADVERSARIAL seed 19341 each scored TP 0,
FP 0, FN 6, TN 14, supported-discrepancy recall 0, annotated-field recall 0,
9/9 required abstentions and 9/20 exact financial outcomes, all by abstention.
Raw corpus/run/score artifacts are under ignored `scratch/first_client_baseline_*`.
No model participated. `docs/RENTAL.md` and a paragraph of
`docs/REAL_WORLD_DOCUMENT_ARCHITECTURE.md` still say the privacy gate refuses
binary PDFs even though PR #4 added bounded PDF inspection; these must be
corrected without claiming visual OCR or general semantic coverage.

## Testable hypotheses and milestones

1. **Real semantic proposals:** a versioned Codex-CLI/analyst adapter using
   approved native units yields validated source-bound candidates from public
   files, without oracle truth or fabricated human decisions. Measure latency,
   tokens/usage if exposed, exact critical fields and abstentions. The local
   Codex CLI currently reports ChatGPT subscription login, not an API key;
   API-backed or additionally billed provider calls require owner permission.
2. **Independent benchmark:** run genuine participant submissions on DEV and
   ADVERSARIAL, score after observations freeze, inspect errors, repair only
   critical silent claims. Freeze code/prompt/schema and use a separate blind
   HOLDOUT context or explicitly mark independent challenge outstanding.
3. **Internal autonomous path:** Codex performs ordinary fact/link/finding
   review and report writing, with independent source reread and a clear STOP.
   A real operator, not a scripted `HUMAN` JSON value, inspects only required
   original pixels and briefly authorizes the finished delivery; measure actual
   correction rate, review time and exception burden.
4. **Actual report chain:** privacy-cleared source → proposals → reviewed facts
   and links → canonical case → exact ledgers → Evidence Plane → adversarial
   review → 4–8-page client-style PDF and evidence pack → hash-bound delivery
   approval. Mutations and a supplemental batch must invalidate/revalidate.
5. **Release evidence:** full regression, Energy, privacy/Rental/document and
   security/recovery checks, Ruff/mypy, Python 3.11–3.14 CI at final SHA.
   Publish operator/operations documents and three independent gate statuses.

## Preregistered acceptance targets

- **Zero** known unsupported client-facing positive financial claims in the
  release-blocking corpus; zero silent cross-currency aggregation; zero missing
  or forged provenance in accepted claims. An uncertain positive must become
  review/abstention, not a tempting unsupported number.
- Correct handling or explicit STOP for scan review, changed hashes, wrong
  quote/span, ambiguous links, credits, conflicting terms and privacy re-clearance.
- Critical amount/date/equipment/rate/credit errors must be caught by
  independent validation or internal adversarial review, not by assuming the
  founder will manually verify every fact. Field and finding recall, coverage,
  abstention, correction burden, latency and cost need denominators. The
  [99% report / 95% no-correction targets](AUTONOMOUS_SERVICE_QUALITY.md)
  are engineering objectives, not verified release performance.
- A clean-workspace supervised synthetic report and operator rehearsal exist.
  No scripted reviewer fixture counts as an actual human rehearsal.

## Independent gates and owner actions

| Gate | Current evidence | GO condition |
|---|---|---|
| A — software/evidence | Privacy and ledger unit/fixture tests pass; semantic recall remains zero | Genuine model DEV/ADV and independent HOLDOUT/challenge; full traceable source-to-report rehearsal; final regression/CI and measured cost/labor. |
| B — real operator | No accountable non-scripted rehearsal recorded | Owner/operator visually inspects required scan facts, briefly reviews the finished synthetic report/exception pack, tests secure intake/delivery and approves exact hashes. The product must not need routine fact-by-fact human correction. |
| C — business/permission | No client-specific contract, provider processing authority or legal/business confirmation supplied | Owner verifies invoicing status, offer/terms, provider data handling and permissions, retention/transfer, and explicitly authorizes a first real case. |

Do not process actual confidential client files, spend on an API, sign terms,
contact suppliers or merge PRs as part of this engineering plan. If A remains
open, release stays **NOT READY — SPECIFIC CRITICAL BLOCKERS**. If A passes but
B/C do not, status may only become **TECHNICALLY READY — OWNER ACTIONS PENDING**.
