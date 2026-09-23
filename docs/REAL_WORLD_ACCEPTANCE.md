# Real-world mission acceptance — IN PROGRESS, not client-ready

Scope: authoritative Giga Goal sections 0–96. This is a working acceptance map,
not a completion certificate. `TESTED` refers only to the stated software
contract; it does not imply unseen-document/model accuracy. `PARTIAL` and `OPEN`
are outstanding work. `PRESERVED` means no replacement was introduced.

Evidence shorthand (all paths relative to the repository):

- **S**: `againward/documents/{contracts,sources,readers,pdf_worker}.py` and `tests/test_document_sources.py`.
- **X**: `againward/documents/extraction.py`, its source-contract tests.
- **E**: `againward/documents/resolution.py`, `tests/test_document_resolution.py`.
- **R**: `againward/domains/rental/{document_adapter,document_evidence,ingestion,workflow,review_policy,reporting}.py`, `tests/test_rental_document_adapter.py`.
- **B**: `benchmarking/document_*.py`, `tests/test_document_benchmark.py`, `docs/REAL_WORLD_RENTAL_BENCHMARKS.md`.
- **K**: existing `againward/core/` and `againward/evidence/`; legacy lifecycle, privacy, durable-store and Energy characterization tests.
- **L**: Rental pricing/reconciliation tests and `run_rental_benchmark.py` (historical 13/13 retained; 15-case extension).
- **D**: `docs/DOCUMENT_INTELLIGENCE_RND.md` records baseline, failures and timings.

## Requirement-by-requirement map

| § | State | Implementation / evidence | Remaining qualification |
|---:|---|---|---|
| 0 | OPEN | D, this map | Full mission not achieved. |
| 1 | TESTED | D: baseline b6369be, 631 tests, old benchmarks | Original unrelated worktree preserved. |
| 2 | PRESERVED | K, L; clean 465f392: 693 tests pass | Not final mission acceptance. |
| 3 | PARTIAL | X separates semantic proposals from Python arithmetic | End-to-end agent investigation evaluation pending. |
| 4 | PARTIAL | S native/CSV/XLSX/DOCX/EML and component routing; Rental PDF privacy post-check and hash-bound visual-human fallback now tested | Visual semantic extraction and real reviewer operation remain incomplete. |
| 5 | TESTED | S content-addressed SourceDocument | Approved sanitized bytes, not raw personal retention. |
| 6 | TESTED | S source batches, union/revision/privacy binding | More real-case batch integration coverage needed. |
| 7 | TESTED | S → X candidate → reviewed CanonicalFact | Semantic authority still reviewer judgment. |
| 8 | PARTIAL | X closed source-local candidates | Broad clause vocabulary/exception evaluation pending. |
| 9 | PARTIAL | S/X exact native unit hashes, quotes and spans | Visual evidence needs supplied human inspection. |
| 10 | PARTIAL | E, Rental-injected match policies | Only deterministic key policies evaluated. |
| 11 | TESTED | E explicit five relationship states/history | Corpus-level state-quality metrics pending. |
| 12 | PARTIAL | E exact reviewed anchors and scope | Semantic proposals for hard matching not evaluated. |
| 13 | PARTIAL | E 100/100 sparse fixture pairs, bounded comparisons | Not unseen blocking recall. |
| 14 | TESTED | E/R no cross-link attribute copying | Missing asset identifier blocks material assignment. |
| 15 | PARTIAL | E exact-anchor authority or supplied HUMAN review | JSON reviewer role is not authentication. |
| 16 | OPEN | Conflicting facts/links refuse promotion | No contractual scenario/precedence ledger yet. |
| 17 | TESTED | X hash-bound ACCEPT/REJECT/DEFER/DISPUTED | No confidence-based self-promotion. |
| 18 | PARTIAL | L + `temporal.py`: daily partial returns, dated rates and conservative unallocated/partial credits | Added quantities and weekly partials pending; semantic corpus run absent. |
| 19 | PARTIAL | D H4: 50 unit-days, EUR 3,750; dated-rate/return combination EUR 3,540 | Generated-corpus semantic score pending. |
| 20 | OPEN | K DomainPack preserved | Energy-specific options still cross shared boundary. |
| 21 | PARTIAL | S/X/E typed dataclasses and closed external schemas | Rental adapter/core retain dict boundaries. |
| 22 | PRESERVED | K durable transactions/recovery | Shared revision service hardening pending. |
| 23 | OPEN | Existing trace/revisions retained | Append-only event experiment not completed. |
| 24 | PARTIAL | Privacy inspection and risk policy extracted for PDF/scan work; public gate remains authoritative | No size-only split; real visual-review operations remain a material limit. |
| 25 | DEFERRED | K unchanged query protocol | Bounded targeted document retrieval needs evaluation. |
| 26 | PARTIAL | New document contracts use againward namespace | Existing indicia schemas preserved; migration not done. |
| 27 | PARTIAL | `investigate.py documents` + package entrypoint | Not all wrappers consolidated. |
| 28 | PARTIAL | pyproject, dependencies, optional dev tools | Lint/type scope is new document boundary, not all active code. |
| 29 | TESTED | CI 3.11–3.14 green at 465f392 | Initial four scan skips addressed by explicit Poppler installation. |
| 30 | PARTIAL | B actual-file corpus and external replay runner | No completed semantic run on the generated corpus. |
| 31 | PARTIAL | B renders all twenty A–T families | Rendering a family is not successful processing coverage. |
| 32 | TESTED | B PDFs, raster scans, CSV/XLSX/EML from independent truth | Limited layouts/languages; not representative vendor diversity. |
| 33 | PARTIAL | B split paths, hashes, clean HOLDOUT guard | No blind HOLDOUT score claimed; isolation is procedural. |
| 34 | PARTIAL | S rename/duplicate/revision; E order/noise/conflicts | Full document mutation suite pending. |
| 35 | PARTIAL | S/E/R/K/L existing property probes | Corpus-level full metamorphic matrix pending. |
| 36 | PARTIAL | B explicit null/zero-denominator metrics | Full date/entity/financial/lifecycle scoring pending. |
| 37 | PARTIAL | E/R ambiguity blocks financial preparation | Real precision/recall tradeoff unmeasured. |
| 38 | TESTED | X closed JSON, quotes/hashes/bounds, numeric consistency | Valid quote is not semantic proof. |
| 39 | PARTIAL | B hostile email text; X no instruction execution | No live model prompt-injection evaluation yet. |
| 40 | PARTIAL | S immutable snapshots, exact duplicate aliases | Near-duplicate/replacement commercial semantics pending. |
| 41 | PARTIAL | S missing pages/forms/embedded images/attachments flags | R stops all financial preparation for unresolved components. |
| 42 | PRESERVED | K existing bounded question/STOP rules | New corpus WAIT question run not completed. |
| 43 | TESTED | R fact/link rows and quote/span provenance | Missing temporal/conflict rows depend on later work. |
| 44 | PARTIAL | Existing bounded Evidence queries | `documents inspect` still emits full parsed units; targeted retrieval needed. |
| 45 | PARTIAL | R existing revision archive, complete lineage invalidation | Source-batch-driven full review/resume benchmark pending. |
| 46 | DEFERRED | Conservative full invalidation | No dependency-graph complexity justified yet. |
| 47 | PRESERVED | L candidate discrepancies ≠ recovery claims | Temporal/credit extensions must keep this distinction. |
| 48 | PARTIAL | L existing finding families | No new auto-findings for unsupported document semantics. |
| 49 | PRESERVED | Existing human delivery and scope policies | No legal entitlement or automatic recovery added. |
| 50 | PARTIAL | R reports retain human gate and reviewed hashes | Real reviewer checkpoint/burden evaluation pending. |
| 51 | PARTIAL | R human pack carries facts, links and ledger chain | Needs temporal/conflict coverage and stronger presentation. |
| 52 | PARTIAL | D canonical timings; B per-case runtime | Stage timings, peak memory, snapshot/context costs pending. |
| 53 | TESTED | X per-case version/hash-bound cache and replay | No cross-client cache. |
| 54 | TESTED | X ExtractionProvider protocol, no network default | No paid/live provider evaluated. |
| 55 | TESTED | R offline source/proposal replay to ledgers/review | Generated-corpus semantic submissions still missing. |
| 56 | PARTIAL | B independent generator/scorer, no truth import by runner | Broader independent annotations/scoring pending. |
| 57 | ACTIVE | D preregistered experiments/failure records | Continue mission within authorized engineering scope. |
| 58 | PARTIAL | D H1–H3 evidence, preserved canonical performance | H4–H7 experiments not fully resolved. |
| 59 | PRESERVED | Correctness/abstention prioritized | No tool-call optimization claim. |
| 60 | PARTIAL | Updated architecture/RND/navigation documents | Full active instruction/context audit pending. |
| 61 | PARTIAL | REPOSITORY_LAYOUT owners corrected | No cosmetic file relocation. |
| 62 | PARTIAL | Neutral source layer; Rental injects policies | Extend import-boundary test coverage for new modules. |
| 63 | PRESERVED | Clean 465f392: 693 tests pass, including Energy | Original unrelated worktree untouched. |
| 64 | PRESERVED | Construction profile unchanged, L benchmark | No Construction concepts moved into core. |
| 65 | PRESERVED | L exact Decimal, currency separation, net-tax basis | FX/non-two-decimal currencies still refused. |
| 66 | PARTIAL | X date/numeric ambiguity flags; B FR/EN wording | Locale/units coverage is narrow. |
| 67 | OPEN | Quoted semantic fields possible | Exceptions/precedence/conditional clause benchmark pending. |
| 68 | OPEN | E exposes contradicted links | No general contradiction ledger or alternative scenarios. |
| 69 | PARTIAL | UNKNOWN/abstention/candidate distinctions retained | Full typed result vocabulary not unified. |
| 70 | PARTIAL | S path/archive/file/text/cell/page limits, worker limits | Not a secure parser sandbox; aggregate memory profiling pending. |
| 71 | PARTIAL | Explicit failure codes, failed submissions abstain | Retry scheduling/accounting not implemented. |
| 72 | TESTED | Reader v2, schema/extractor/model/prompt/resolver versions | No implicit reinterpretation of old cached output. |
| 73 | PARTIAL | B deterministic source bytes/seed; S hashes | Live model reproducibility not measured. |
| 74 | PARTIAL | Receipts, extraction hashes, resolution history, traces | Unified case-level document observability pending. |
| 75 | PARTIAL | DocumentError codes + legacy failures | Full stable cross-layer failure taxonomy pending. |
| 76 | PARTIAL | Documents CLI, R package path, benchmark CLI | Needs complete agent-led worked developer example. |
| 77 | PARTIAL | X/E explicit reviews, existing delivery gate | No fabricated real approval; burdensome field review remains. |
| 78 | PARTIAL | B counts supplied decisions | No actual review-time/client-question burden evaluation. |
| 79 | OPEN | Zero-FP contract tests only | Preregister/evaluate corpus false-positive budgets. |
| 80 | OPEN | Existing generic DomainPack remains | New third-domain document probe pending. |
| 81 | PRESERVED | R owns rental/credit policy, S/X/E neutral | Keep temporal business rules out of core. |
| 82 | PARTIAL | Five requested documents now exist | Content explicitly records unfinished acceptance, not DONE. |
| 83 | PARTIAL | This row-by-row matrix | Replace gaps with measured evidence as work proceeds. |
| 84 | PARTIAL | Limits in architecture/benchmark/RND docs | Final tested first-client limits review pending. |
| 85 | PRESERVED | Opt-in new schemas, old canonical readers | Reader v2 requires revalidation; no silent workspace migration. |
| 86 | ACTIVE | Dedicated branch, incremental pushes, draft PR #3 | Never merge automatically. |
| 87 | OPEN | Clean 465f392: 693 tests pass; L 13/13; DEV/ADVERSARIAL routing baseline | Full semantic benchmark/adversarial acceptance not obtained. |
| 88 | PARTIAL | D baseline/current canonical samples | Repeat timings and profile document/peak-memory stages. |
| 89 | PARTIAL | S/X/E/R adversarial tests | Broader malformed/binary/model-input suite pending. |
| 90 | PRESERVED | K/L gates retained; new layer checks privacy/STOP | Full final invariants matrix still required. |
| 91 | PRESERVED | No SaaS/database/cloud/OCR platform built | No scope expansion implied. |
| 92 | ACTIVE | P0 contracts/integration progressed | P0 semantic benchmark and several P1s remain. |
| 93 | OPEN | Native reviewed path demonstrable | Forty messy documents not validated end to end. |
| 94 | OPEN | Interim limits below | Independent final adversarial challenge still required. |
| 95 | OPEN | Branch/PR/tests recorded incrementally | Final mission handoff not yet warranted. |
| 96 | ACTIVE | Source meaning remains analyst-led; arithmetic deterministic | Do not replace missing interpretation with fixture automation. |

## Interim first-client risk register

| Classification | Limit | Current behavior |
|---|---|---|
| BLOCKS_FIRST_CLIENT | Real visual reviewer identity/workflow is not authenticated by a JSON role; bounded PDF inspection is not a complete hostile-document sandbox | Native PDF privacy post-check works; scans require source/component-bound human inspection and STOP when unavailable. Synthetic policy benchmark: 19/19, 0 false blocks, 0 unsafe passes; no claim about actual human vision. |
| BLOCKS_FIRST_CLIENT | No independent semantic evaluation across the actual-document corpus | No model quality claim; routing baseline recall is zero. |
| BLOCKS_FIRST_CLIENT | Weekly partial quantities and broad amendments remain incomplete | Explicit daily source-backed patterns calculate; other cases abstain. Unallocated credits are retained but prevent a supported discrepancy on affected invoice/currency groups. |
| NEEDS_HUMAN_REVIEW | Ambiguous links, visual transcription, contractual authority | Supplied review required; no fabricated approval. |
| NEEDS_FUTURE_R&D | Poor scans, handwriting, broad clause exceptions, vendor layout generalization | Not validated. |
| ACCEPTABLE_LIMIT | No tax advice, FX, legal priority, negotiation or guaranteed recovery | Explicitly outside current product authority. |

Next priorities: complete independent DEV semantic runs and scoring; extend
quantity/rate timelines beyond daily returns; resolve the
real visual-review operation; finish kernel experiments and final validation.
