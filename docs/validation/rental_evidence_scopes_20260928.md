# Rental evidence scopes and rate dimensions — 2026-09-28

Starting checkpoint: `a0de5498228534d645fe1aa5d791c79a84b985a4`
(engine `3de8ea9e19fb988642e37848c6703abce534913f`). This is an engineering
checkpoint, not a live A/B convergence or accuracy certificate. No CASE A/B
end-to-end run, unseen dossier, holdout or financial oracle was used to choose
the changes. The next independent Luna campaign must use a frozen commit.

## Causal findings

The complete private campaign report was read from
`/data/data/com.termux/files/usr/tmp/againward_luna_normalized_a0de549/campaign_report.md`.
It reports 79 successful provider calls, six business retries and 0/6 calculations.
Its detailed records remain private. This document does not rewrite that evidence.

Earlier normalization fixed important transport responsibilities: Python owns
technical IDs/types, partial reads can reach comparison, and explicit assembly
restarts QA/adjudication. The latest source passes no longer stopped on the
earlier supplier-email schema or model-provider failures. That did **not** fix
the distinction between a source observation and a dossier-level interpretation.

Code tracing established three related boundary problems:

1. `adjudicate_with_codex` fanned out to one decision per source but supplied
   **every source and every scan** to each invocation. It advertised all their
   locators while demanding a source-local decision. The repeated email→scan
   citation failures were correctly rejected by validation; the invocation
   contract itself invited an incompatible evidentiary scope.
2. `PACKAGE_SOURCE_REQUIRED` and `package_source_gaps` required charge meaning
   locally before review, while the adapter demanded it again before it could
   use reviewed document relationships. Guidance emphasized invoice meaning
   even for contractual rental terms. A2/A3 exposed this mismatch; they are not
   proof that the business evidence was genuinely absent. Filling an invoice
   observation from a contract would conceal provenance and is not acceptable.
3. `billing_unit` mixed the time denominator with quantity/calendar dimensions.
   Token normalization preserved the compound spelling, but `RateTerm` only
   accepted time-unit enums. Its `ValueError` escaped the workflow's
   `DocumentError` handler and became an opaque CLI termination after reviews.

The shared cause is an incomplete separation of observed content, canonical
business meaning and the evidentiary scope of a decision. More aliases alone
would hide some of the problem; more source-local required fields would amplify it.

## Resulting responsibilities

| Scope | Owner and invariant |
|---|---|
| Original source fact | Reader plus native/pixel fact review. Exact source, quote/span or page/render binding never moves to another source. |
| Source role/status | Reviewed source metadata. No inheritance from a linked invoice, signature on another document, filename or classification review. |
| Source entity | Local grouping and observations. Source selection still requires intrinsic facts such as invoice ID, currency and amount. |
| Cross-source identity | Existing exact reviewed identifier resolver. Contradicted or ambiguous links do not supply classification context. Identity is not charge meaning or contractual authority. |
| Package classification | Separate explicit claim on the business occurrence, with two independent model judgments, current reviewed fact references and relationship hashes. It may remain unresolved. |
| Technical IDs | Python; no model-generated hashes, global identities or decision cardinalities. |
| Rate dimensions | Bounded deterministic decomposition of explicit wording; each new observation keeps the original evidence and remains unapproved before normal review. |
| Commercial authority | Existing source role/status and financial authority rules. Neither a relationship nor a classification receipt grants authority. |
| Arithmetic | Python's existing decimal/time rules. Explicit quantity basis determines which proven quantity those rules consume. |

The order is now: local observation → local QA/adjudication → native/pixel fact
review → explicit package classification where required → strict canonical
package validation → deterministic arithmetic → finding/report/final QA.

## Changes

**Source-local adjudication is isolated by construction.** Each call receives
only its disputed source's original units and rendered pages. Prior assembly
context is filtered too. Citation source identity is removed from the model
schema and bound by Python. An explicitly emitted foreign source is rejected,
never reassigned or dropped; diagnostics identify `FOREIGN_SOURCE_CITATION`.
Legacy durable receipts remain replayable under their existing exact validators.

**Charge classification has an explicit package scope.** Missing `charge_type`
does not make an otherwise valid invoice/term observation unreadable. It still
must exist before canonical financial construction. A new bounded review uses
only promoted facts and exact current relationships between invoice lines and
rental scopes. It reopens the implicated originals, including pixels, but does
not see an oracle or the other judgment. Two agreeing supported judgments are
required; null, disagreement, conflicting cited classifications or unavailable
proof stop. There are no semantic retries. Up to 24 missing classifications
can be considered, with bounded context/pages and two calls each.

The model sees explicit short evidence handles and semantic rows, rather than
internal fact IDs, hashes, registry details or an implicit counting task. Python
binds the handles to current fact IDs and persists a hash-bound receipt. The
result is a package claim, **not** a fabricated source observation. Its full
premises appear in lineage and in `package_classification` Evidence Plane rows.
Rejected local classifications cannot be revived through this route. A matching
agreement/asset alone does not establish that a line is rental; reviewers must
establish the actual charge meaning. A billed statement cannot authorize terms.

**Rate denominator dimensions stay separate.** For example, “per asset per
calendar day” yields `billing_unit=DAY`, `quantity_basis=PER_ITEM` and the explicit
calendar-day convention. “Per lot per month” instead has `PER_SCOPE`. Compound
wording never becomes just `DAY` while losing its quantity dimension. Rates and
amounts are not altered. Explicit per-scope rates use one scope; per-item rates
use the contractual item quantity. Conflicting explicit quantities produce an
unknown contractual basis. Legacy records without the new optional field retain
their existing behavior. Unsupported dimensions (including unmodeled calendar
week/month qualifiers and working-day holiday conventions) stop explicitly.

**Controlled errors remain in workflow evidence.** Unknown rate dimensions
identify the exact canonical field in a `DocumentError`. Other canonical-record
validation errors are sanitized, and the job persists a stage/code/receipt for
caught `ValueError` failures without leaking the exception's source content.

## Tests and diagnostic evidence

Generic tests cover native/visual dimension equivalence, unchanged quotes,
multiple quantity bases, unknown units, conflicting quantity semantics,
cross-source classification with both original provenances, classification of
contractual terms, rejected metadata, independent review isolation, stale/mutated
evidence, many-to-one identities, conflicting identifiers, missing/contradictory
meaning, Evidence Plane visibility, and source-isolated model context/citations.
Existing missing-local-amount tests remain strict. Tests requiring charge type
*before* review were changed to assert the new scope plus a mandatory final
classification review; the canonical requirement was not removed. Original
pixel recovery can still target a uniquely identified missing charge field.

One generic two-document micro-fixture was used solely at the package-review
boundary with Luna; it is neither CASE A nor CASE B. The first two-call probe
rejected an out-of-graph model reference. A second diagnostic probe on the same
interface returned valid references; both raw answers remain in private scratch.
This exposed the unnecessary implicit indexing task, so the final model view
prints evidence handles and removes internal machinery. The final isolated probe
made two fresh `gpt-6-luna` calls; both returned a supported `RENTAL`
classification and the receipt replayed. Its private artifact is
`/data/data/com.termux/files/usr/tmp/againward-scope-handles-uk5t6d72/scope_review.json`.
No calculation/report ran. All three exploratory probes are retained in this
account; they are not a success-rate estimate.

No A/B extraction, reread, adjudication, financial calculation or report run was
executed in this change. A1's unit phrase was reproduced as a generic parser
test; email/source isolation and split commercial meaning use independent
micro-fixtures. The historical report supplied failure shapes, not financial truth.

## Residual risks

- Two fresh judgments by the same model are correlated; they are review gates,
  not independent accuracy evidence. Misreading or misclassification remains possible.
- The new relational projection concerns charge meaning, not arbitrary merging
  of missing dates, quantities, currencies or authority. Other split or ambiguous
  commercial scopes still require demonstrated identity and supported semantics;
  this change does not guess them or claim universal dossier convergence.
- Exact identity resolution remains conservative. Missing anchors, multiple
  plausible scopes, unreviewed original facts and conflicting commercial evidence
  continue to stop. Source-local observation quality is still important.
- Unknown tariff dimensions remain unsupported, with a precise diagnostic.
- A/B calculation and report success must be measured independently on the final
  SHA. No 95% structural reliability, ≥99% accuracy or client readiness is claimed.

## Frozen software validation

The implementation is committed as `754e0649c7a7cbef49cbeebb4b15994e5651a2e1`
and pushed to `release/first-rental-client-pilot`. No integrity test was
disabled to obtain green. The final local suite on that exact commit reports
**1027 passed** in 13m39s. Ruff and configured mypy pass, Rental is **15/15**,
and privacy is **19/19** with zero false blocks and zero unsafe passes.

GitHub Actions was triggered for both push and draft PR checks, but every job
was refused before starting. GitHub's check-run annotation states that recent
account payments failed or the spending limit must be increased. This is an
external Actions billing/runner blocker, not a test failure; no CI result is
claimed as green.

- Latest focused scope/failure-family/adjudication suites: **85 passed**.
- Ruff configured tree plus all changed Rental modules/new tests: passed.
- Configured mypy: passed (18 files); explicit new-module mypy: passed (2 files).
- Earlier development checks exposed the old pre-review charge-type expectations,
  one stale test helper import and a malformed-container binding bug. They were
  corrected; the original malformed-container regression remains active and green.
