# Energy Billing V1 — audit and architecture decision (2026-10-03)

## Authoritative starting state

Origin: `https://github.com/aureleindicia/Againward.git`. The invocation workspace
was `energy-analyzer`, branch `main`, HEAD
`c27f261cd560cb005dd8d9367c8cf6567ebfa155`, with pre-existing changes in the client
skill, business and prospecting files. Those changes are outside this task.
The Goal's Rental V2 baseline exists in `release/first-rental-client-pilot`, HEAD
`8a066e0a5cbb9eb29f528169a981d0c09fc99fb3`, initially clean. Work continues in a
new sibling worktree on `feat/energy-billing-v1` from that exact commit. No branch
switch, reset, merge or migration is required in the original workspace.

The complete external Goal was read. Its phases 0–10 and final deliverable
remain the objective; this checkpoint is not a completion claim.

## Audit and reuse matrix

| Component inspected | Decision | Reason / actual boundary |
|---|---|---|
| `documents/sources.py`, source contracts | Reuse | Hash identity, duplicate snapshots, mutation detection, approved inventory; privacy/lifecycle still enforced. Inventory rejects a bad file globally: do not mistake it for atomic semantic evidence. |
| `documents/readers.py`, PDF worker | Reuse | Bounded native units with page locations and hashes; scans/hybrids remain explicit limitations. |
| `core/artifact_store.py` | Reuse | Fsynced redo journal, process lock, atomic JSON; replay must still validate domain transitions. |
| `evidence/hashing.py` | Reuse | Stable content hashing with nonfinite rejection. Financial inputs remain decimal strings, not floats. |
| `evidence/dataset.py` / query plane | Later adapter | Typed source-bound evidence, but minimal invoice audit does not need the whole query/session layer. |
| `core/privacy*`, contract/lifecycle | Preserve, integrate at real intake | Existing source approval is useful; Energy Billing needs its own preservation policy before real-client entrypoint. No fake clearance or HUMAN. |
| Rental V2 atomic reader | Reuse concept, new implementation | Individual quarantine is useful; imports Rental vocabulary/normalization and `_ask` payload-string transport. |
| Rental V2 actions/claims/relations/readiness | Leave untouched | Rental scope, stop events, dimensions and authority are different business contracts. |
| Rental V2 local review | Reuse concept | Dependency hashes use actual subject evidence; no global graph staleness. New native review contract needed. |
| Rental Investigator native contract | Reuse design, new small contract | Exact fields, enums, validators. Rental's actions and claims are unsuitable. No universal framework extraction now. |
| Rental `_ask` / document provider | Leave untouched | Existing read/review paths contain nested JSON strings, aliases and Rental guidance. Use a narrow CLI transport for Billing with direct schema and bounded repair. |
| Rental Decimal decorator | Reuse concept | Fixed context correct, error message and wrapper domain-specific; small Billing money module preferable. |
| Rental PDF/report authoring | Later low-level renderer only | Financial semantics, evidence pack, author/review gates are Rental-specific; Billing report consumes one calculation artifact. |
| Energy domain pack / `energy_mvp/tariffs.py` | Leave untouched | Operational kWh profiles/time-of-use costing use floats and do not establish invoice authority, taxes or recoverable discrepancies. |
| Existing benchmarks | Regression controls | Rental 15-case and privacy 19-case suites measure software invariants, not live Billing quality. |

Rental's current-state notes honestly record repeated source/schema/review
blockers and zero calculation in multiple known live runs despite extensive
unit coverage. The 2026-10-03 contract fix removed unconstrained nested JSON for
the Investigator only. Its single live MARK_UNRESOLVED probe does not demonstrate
all readers, reviews, actions or financial convergence. These facts argue for a
smaller separate state, not mechanically generalizing the Rental graph.

## Architecture (ADR EB-001)

Dedicated `againward/domains/energy_billing/`. No changes to existing domain
registration or default Energy commands until an explicit Billing entrypoint is
ready. Modules: protocols/transport; atomic observations and quarantine;
typed minimal state and reducers; local authority/reviews; deterministic
readiness and engine; report; bounded investigator; evaluation runner.

Python owns durable facts, evidence IDs, source spans, states, dependencies,
transactions, arithmetic and terminal decisions. The model reads and proposes
one local action or source observations. Independent original-source review is
required for semantic meaning; quoting a price does not establish authority.
No model may replace the case, choose a financial fallback or create HUMAN.

Minimal objects: Invoice, InvoiceLine, DeliveryPoint, ConsumptionPeriod,
TariffTerm, AuthorityReview, CalculationComponent, local Issue. Relations:
line BELONGS_TO invoice; invoice BILLS delivery point; tariff GOVERNS line/period.
Claims: authority of that exact tariff for that exact PDL/supplier/period, charge
meaning, material evidence disposition. No domain ontology expansion by default.

## Envelope and staged engine

France, electricity B2B, EUR, identifiable supplier and PDL/PRM, dated contract,
bounded PDF/text sources. Initial vertical slice verifies ONE explicitly scoped
HT consumption line at a fixed price with one quantity and one dated contract.
It must never call that partial line check a complete invoice audit. A clean
invoice containing extra material charges cannot silently ignore them.

Then expand one tested family at a time: fixed/subscription with explicit period
convention; explicit per-band consumption and dated simple price segments;
versioned standard taxes only where applicability is proven; uniquely attributed
issued credits and regularizations. Whole-invoice status requires disposition
of every potentially material line and matching totals.

UNSUPPORTED: FX, gas, indexed/exotic formulas, unsupported network/demand
conventions or public-tax special regimes. UNRESOLVED: missing authoritative
contract, ambiguous PDL/date/quantity, competing amendment, missing material
line or uninspectable evidence within an otherwise supported case. Neither
state hides a software/protocol/provider error; execution failure is separate.

## Authority and money

Tariff applicability binds contract source/hash, supplier, PDL, exact start/end,
price unit, explicit charge meaning and precedence over amendments. Invoice
unit price is observed billed evidence, never sufficient expected-price authority.
Dates are half-open internally; source inclusive boundaries need explicit reviewed
conversion. Decimal strings, bounded fixed Decimal context, EUR cents, explicit
per-line rounding convention. Components retain inputs, authority, formula,
unrounded decimal and rounded cents. Signed discrepancy is billed minus expected;
not automatic recoverability or legal entitlement.

Official rules are researched before encoding. Each encoded version must retain
official URL, retrieval date, content hash, validity dates, applicability and
exceptions; offline replay never silently retrieves today's rate. No tax rate
has been encoded at this checkpoint. See REGULATORY_RESEARCH.md.

## Failures / recovery / readiness

Separate SOURCE_UNREADABLE/CHANGED; EVIDENCE_BINDING_INVALID;
OBSERVATION_INVALID; MODEL_PROTOCOL_INVALID/FAILURE;
MODEL_PROVIDER_FAILURE; AUTHORITY_UNRESOLVED; RELATION_AMBIGUOUS;
MATERIAL_EVIDENCE_MISSING; UNSUPPORTED_DOMAIN_RULE;
POST_CALC_OBJECTION; REPORT_PROVENANCE_FAILURE.

Diagnostics retain stage, component/source, schema version/hash, faulty path,
expected constraint, received type, response hash, retry and mutated=false.
Private evaluation optionally retains exact raw streams with 0700/0600
permissions. Production retains safe metadata, no raw response by default.
One protocol repair per call, no arbitrary enum mapping; exhaustion explicit.
Provider failure does not become business ambiguity or UNSUPPORTED.

Bad observation C is quarantined while valid A/B/D survive. Material bad C
creates a local root issue blocking its dependents only. Derived readiness,
calculation and report blockers refer to the root rather than multiplying issues.
Review dependency fingerprints include only actual tariff/source/identity/period
inputs. Evidence elsewhere cannot stale the review. Missing material frontier
disposition blocks Python readiness. Agent PROPOSE_READY never bypasses it.

## Thin slice / tests / live probes / benchmarks

Before expanding: native synthetic PDF invoice + contract → atomically bound
observations → minimal occurrences/relations → local review → readiness → exact
line calculation → scoped discrepancy → HTML/Markdown/PDF. At least one real
model action must remove a real issue. Gates A–E must be evidenced separately.

Probe direct reader, all small action forms and review schemas using actual
Codex CLI first, with no financial fixture/oracle. Deliberately invalid focus
tests live bounded repair. Deterministic tests cover malformed JSON/enums/extra
fields/wrong IDs, partial quarantine, invalid action no mutation and exhaustion.
Acceptance cases 1–12 from the Goal are mandatory, as are negative authority
tests (wrong PDL/supplier/dates, competing tariff), duplicate money evidence,
local invalidation and exact-money context independence.

Metamorphic tests: filename/order/layout/irrelevant source invariance; price and
period deltas; changed prerequisite targeted invalidation; duplicate evidence
cannot increase amounts. Scope pass requires facts + authority + evidence +
relations + calculation + no hidden material issue, not amount equality alone.

Frozen DEV: clean engine SHA in dedicated validation worktree, fresh output,
fixed model/runtime/budgets; expected outcomes kept outside pipeline input;
seal pretruth artifacts before scorer access. No patch within campaign. Holdout
is a separately sealed corpus never opened or tuned during DEV. Keep both
integrity guards and full Rental/Energy regression suites. Record stage timings,
calls/turns/retries, observations/quarantine/occurrences/relations/claims/reviews,
root/derived issues, readiness, calculation/report/PDF, reason, source hashes.
Repeated campaigns at same maximum stage require simplification, not blind fixes.

## Commercial pilot hypothesis

French SMEs with several sites, fixed/simple electricity offers and invoices
plus signed commercial conditions accessible to finance/procurement staff;
direct CFO/control/energy contacts and energy/cost-reduction consultant channel.
Ask for 3–10 invoices plus complete effective pricing/amendments and relevant
credits; sample preparation time, missing documents and supported frequency.
Compare verified discrepancy value with processing cost, human review time and
willingness to pay. No outreach is authorized by this development task; market
value, willingness to pay, true human time and real-client precision remain
unmeasured. A short genuine final human review is permitted and delivery remains
controlled. A synthetic success cannot establish paid-pilot readiness.

## Open verification

Baseline full suite running; exact results will be recorded, not inferred from
historical green logs. Existing monthly Energy report reproduced in private
scratch (611850 kWh, 107073.75 EUR); automated output remains candidate signals.
Rental/privacy regressions launched. Gates A–E, DEV, holdout and final report
remain open until inspected evidence proves them.
