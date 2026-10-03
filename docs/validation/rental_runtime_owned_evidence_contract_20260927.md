# Rental: runtime-owned evidence binding and shared semantic contract

Development architecture work from `b7537557f58862a7e15528705d451cf68a3d3f22`.
No new CASE A/B pipeline run, live model call, or unseen case was executed in
this pass. Historical private evaluation artifacts were inspected; new tests
use generic synthetic sources and scripted model responses. This is software
regression evidence, not evidence of production accuracy or successful live E2E.

## Causal findings

The common boundary error was treating model serialization and duplicated
interpretation instructions as if they were source-evidence requirements.
The checkpoint already had explicit reconciliation and strict reviewed package
gates; these are retained. The new correction addresses interfaces feeding them.

| Historical stop | Reproduced cause | Correction / remaining limit |
|---|---|---|
| B1/B2/B3 native reread schema failure | The initial native response validates as evidence but has a structural omission. Composing the repair prompt with independent-reread instructions exceeds the provider's 12,000-character limit (12,628 before a diagnostic hint). `text()` raises `EXTRACTION_SCHEMA_INVALID` **before any model call**. | Compact shared guidance fits all reader/retry combinations. Local prompt-budget failures are `MODEL_CONFIGURATION_ERROR`, with stage `PROMPT_CONSTRUCTION` and `model_invoked=false`. Retry budgets are unchanged. |
| A1 visual review defers `document_status` | The offered value was `ISSUED`, not absent from extraction. Both visual reviews demand literal proof of issuance from an invoice labelled accepted. The reader's domain definition of issuance was not supplied to visual review. | Native/visual readers, adjudication, and native/visual reviews receive the same interpretation contract. Issuance is explicitly distinct from customer acceptance; classification still needs source evidence and review. No automatic status conversion or reviewer override. |
| A2 unresolved charge classification | The adjudicator interprets a charge classification more literally than the extraction guidance; the source phrase was treated as an agreement reference rather than a billed rental description. | Shared semantics distinguish a source-supported commercial classification from a bare agreement reference. This historical semantic dispute is **not proven resolved** by software tests. Genuine ambiguity still waits. |
| A3 visual location failure after retry | Source/page/render bindings were valid. The visual citation combined visible text, but did not exactly equal one prior candidate's or new observation's quoted string. A candidate-locked transcription check raised `SOURCE_LOCATION_INVALID`. | A visual citation is a new, unapproved transcription tied to the exact attached pixels. It need not equal an earlier transcription. It cannot create or approve facts. Native unique-substring checks remain unchanged. |

Historical count correction: the previously reported “59 successful runtime
invocations” included provider attempts that failed while constructing a local
prompt. In particular, the three B structural retries never reached Codex CLI.
The private records contain 49 extraction raw responses, five adjudication
responses/receipts (including the first rejected A2 response and its retry), and
three A1 review calls: 57 responses/calls reconstructed. The previous count also
omitted the A2 adjudication retry; it was not a reliable subprocess counter.
The earlier 0/6 calculation outcome is unchanged. These counts are reconstructed
from historical artifacts, not new runtime measurements.

## Producer / consumer boundaries

| Stage | Model responsibility | Python responsibility / gate |
|---|---|---|
| Native read / independent reread | Partial source-local observations, exact quote, business classification | Exact native location/span, source identity/hash, normalized value validation; bounded retry |
| Visual read / independent reread | Partial visible observations, page and grouping, uncertainty | Current source/page/render binding; observations remain unapproved |
| QA | Independent readers have no access to one another | Material comparison and completeness gaps, not automatic primary preference |
| Adjudication | Select, explicitly assemble, or abstain; reopen originals; optionally discover visual observations | Bind assembly reader/index to exact immutable parent hash/candidate ID; bind visual citations to invocation render hashes; validate native quotes and source/page membership |
| Explicit assembly | INCLUDE/REJECT every parent candidate; choose source-local grouping | No silent union. New proposal/hash, parent lineage, fresh QA/adjudication and all reviews. Incomplete dispositions still fail |
| Fact / pixel review | Independently accept/reject/defer source-supported facts using the same domain definitions | Reject stale evidence, preserve visual attestation gate; never create HUMAN approval |
| Package / calculation | No model authority to fill commercial gaps or compute discrepancy | Strict reviewed completeness and relationship authority; deterministic technical IDs and arithmetic unchanged |

Shared semantic guidance is composed from the canonical entity contract once.
Native and visual differ in evidence transport, not documentary meaning.
Review cache keys include the semantic guidance; changed semantics cannot reuse
an earlier review result. The native retry including QA and structural repair
is below 7,000 characters, without raising the existing provider budget.

The model-facing adjudication schema no longer asks for render hashes or parent
extraction hashes. Assembly references use `reader` plus one-based
`candidate_index`; Python binds them to the exact proposals used in that
invocation. Invalid indices, booleans, missing parents and unknown readers fail
closed. Durable receipts retain full hashes/IDs; replay still validates these
bindings. Legacy receipt hashes, if supplied, are checked, never overwritten.

The visual citation change is deliberately narrow: it removes string equality
between *two model transcriptions*, not any comparison with source bytes.
A citation by itself never becomes an observation or a promoted fact. Every
selected/new visual fact still goes through the existing original-pixel review
and promotion gates. An incorrect transcription remains possible and must be
caught by review; matching an earlier model string did not establish truth.

Existing evaluation-only CLI capture was retained and hardened: exclusive 0600
files in a 0700 private scratch tree, linked directories rejected, environment
allowlist only, no raw output added to ordinary receipts. Artifact-write errors
are not misclassified as Codex process failures. This capture is diagnostic,
not a business evidence source.

## Validation

Pending final local test totals and CI for the implementation commit.

Added generic tests cover:

- every native/visual/primary/challenger/retry prompt within its existing budget
  and current prompt registry;
- pre-invocation configuration failure without launching a subprocess;
- runtime-bound assembly references with unchanged explicit dispositions and
  no approval; invalid index/type fails closed;
- fresh visual transcription outside both candidate quote sets, with current
  render binding, zero promoted facts, invalid-page and stale-render rejection;
- unchanged rejection of native paraphrases;
- actual model-facing schema without hash obligations;
- changed shared semantics invalidate native review caches;
- private diagnostic capture permissions, environment minimization, immutable
  writes and symlink rejection.

Existing architecture tests retain complementary partial reconciliation, fresh
QA/re-adjudication/reviews, native/visual convergence, deterministic technical
IDs, rejected metadata isolation, lineage replay, decision counts, controlled
incomplete-evidence stops and the mixed-review empty-list crash regression.

## Residual risks / separate frozen evaluation

- Software tests do not establish that Luna follows the shared interpretation
  contract reliably. A1/A2 may still abstain for semantic reasons.
- Review remains model-based. Exact hashes prove which evidence was inspected,
  not that its interpretation is correct.
- Explicit assembly still depends on a model choosing complete dispositions;
  incomplete or conflicting evidence cannot be silently merged.
- Native citations must remain exact, and genuine incomplete source evidence
  still blocks calculation. No claims about financial results, report or PDF QA
  on the new code are made here.
- The independent Luna A×3/B×3 campaign must run separately on the resulting
  frozen commit. It is required before claiming improved end-to-end reliability.
