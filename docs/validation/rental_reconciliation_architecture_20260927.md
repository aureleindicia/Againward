# Rental reconciliation architecture — 2026-09-27

Software architecture/regression evidence, **not live accuracy evidence**. No
CASE A/B replay, unseen dossier or model evaluation was performed in this mission.
Parent checkpoint: `e771e8091db0213eb8385a0d6097544f0e1c4aeb`.

## Causal audit before implementation

The recent sequence (`e380943`, `ea35e11`, `4f09289`, `e771e80`) centralized some
entity requirements and deferred missing structure, but retained incompatible
roles for an extraction: provisional model observations, complete source record,
and selected financial evidence. Semantic contradictions still terminated the
first read before the challenger; different subsets of fields triggered gates
at different stages. Model-local grouping and source-level authority had also
been confused with entity/line requirements.

The adjudicator selected a whole primary/challenger extraction and could append
new **visual** observations. It could not explicitly reconcile complementary
native candidates. A single batch-level response simultaneously had to reproduce
the disputed-source count, cite all sources and observe the correct native/visual
route. The global context contained non-disputed documents, making extra decisions
and native sources incorrectly addressed as visual pages possible.

The observed post-FACT_REVIEW `IndexError` is independently explained by code:
`review_visual_with_codex`'s final loop called `visual_gaps([])` on each native
extraction in a mixed batch; the helper indexed `visual[0]`. It was a programming
error, not model unavailability. This audit does not claim to have recovered a
historical traceback absent from the campaign record.

Identical source bytes can therefore encounter different first failures because
model observations, grouping, limitations and selected peers vary. Early schema,
semantic and completeness gates previously prevented later independent evidence
from reconciling these differences. The deterministic arithmetic is not implicated.

## Producer/consumer contract map

| Producer → consumer | Data/scope | Source-bound versus derived | Gate |
|---|---|---|---|
| Reader → native extractor | Native unit text/location | Python owns bytes, source/unit hashes | Exact quoted substring and span |
| Renderer → visual extractor | Original visual units | Python owns 300-DPI render/page hashes | Current page and render binding |
| Model → validated provisional observation | Typed value, quote/visible text, entity grouping, limitations | Values/classifications require source interpretation; runtime binds IDs/hashes | Schema, canonical enum/type and provenance strict; content conflicts remain provisional |
| Primary + independent challenger → QA | Source metadata + material entity bundles | Comparison ignores model-local group labels and numeric formatting | Record gaps, contradictions, omissions and differences; no approval |
| QA → source-scoped adjudicator | One disputed source; other originals as context | Exact native citations or current original pixels | One decision for that source; native observations cannot claim visual pages |
| Explicit candidate dispositions → assembly | INCLUDE/REJECT for every parent candidate; target entity groups | Python copies existing candidate values/evidence only | Complete disposition coverage, current parent replay, new candidate/extraction hashes |
| Assembly → new QA/adjudication | New proposal, both original parents and assembly plan | No inherited decision/review | One assembly round; forced fresh adjudication, no second assembly |
| Selected proposal → fact/pixel review | Canonical source/entity structure | Required commercial fields must be source-supported; no automatic metadata defaults | Strict completeness and consistency; independent fact decisions and visual receipts |
| Reviewed facts → document package | Reviewed entities and explicit document authority | Source-level role/status shared only where legitimate; rejected local metadata cannot inherit authority | Same canonical structural requirements; reviewed values cannot be null |
| Reviewed package → calculation | Contract links, lines, charge scopes | Technical line ID/charge key derived; commercial charge type remains source-bound | Exact entity links, original financial parser/invariants |
| Calculation → findings/report/final QA | Deterministically calculated ledgers and reviewed evidence | Existing financial/report authority unchanged | Finding review, original-source/PDF QA and delivery controls unchanged |

Canonical field/enumeration/scope requirements remain owned by
`againward/domains/rental/entity_contract.py`. Native and visual instructions
consume its generated required-field description. Source role/status are not
required on every row; entity kind remains per entity. Invoice classification,
charge type, rates, dates, currencies, amounts, contractual authority and business
links are semantic evidence, never technical defaults. Descriptions/anchors not
required by the relevant entity contract remain observations when available;
missing links that prevent financial attribution still stop package construction.

Technical line identifiers are derived from reviewed source/value/occurrence
anchors instead of arbitrary native model group names. A visual occurrence also
retains its reviewed local grouping so identical amounts on one page do not merge.
Printed IDs take precedence; ambiguous printed labels stop. Charge keys retain
the existing unique reviewed charge-scope derivation. No financial rule changed.

## Implemented flow

Before:

`read → mixed completeness/conflict gate → choose whole pass → review → late gaps/crash`

After:

`source-valid provisional reads → independent QA → source-scoped reconciliation`

`→ complete consistent selection → fresh fact/pixel review → reviewed canonical package → calculation`

If readings are complementary:

`explicit dispositions → new unapproved extraction/hash → new QA → full re-adjudication → new reviews`

There is no automatic union, removal of limitations, synthesized business value,
or reused review. Assembly retains both parents' limitations and source evidence.
Its hash-bound lineage receipt records both parent extractions and all rejected
and included candidate references. The assembled extraction carries that receipt
hash: both package replay and job resume rebuild the assembly from current parent
evidence and verify exact equality. Nested assemblies are refused. An assembly is
immutable in final adjudication; missing facts cannot be appended to that lineage.
Conflicting selected values fail closed, including conflicts beyond structural
enums. The source job also validates the selected source/hash map before lookup.

Incomplete commercial evidence now yields `WAITING_FOR_REQUIRED_INFORMATION`
with stage/source/field diagnostics where available. Malformed decision coverage
and schema errors remain controlled failures rather than requests for client data.
The empty visual-list crash is removed, including the mixed native/visual case.
Visual analyst wording now matches the existing MODEL-receipt/HUMAN-fallback gate;
it never generates an attestation or resolves those flags by itself.

## Tests and limits

Generic architecture tests cover explicit complementary native assembly, candidate
coverage, fresh hashes/QA/adjudication/reviews and resume; source mutation; native/
visual canonical convergence; stale render rejection; unreviewed visual facts;
semantic contradictions deferred only for provisional reads; missing commercial
facts; technical native IDs independent of group labels; rejected metadata;
source-scoped decision cardinality; native pixel prohibition; mixed-source visual
review; and controlled package stops without arithmetic.

Existing exact-span, review/attestation, provenance, financial and privacy tests
remain active. No existing test assertion was weakened.

The first exploratory full-suite execution overlapped implementation changes and
is invalid as candidate evidence: 924 passed / 3 integrity failures (changed or
uncommitted engine). It is superseded by the frozen software validation recorded
below. Integrity checks were not disabled.

Residual limitations: semantic classification, grouping and omission detection
remain probabilistic; identical reader errors can survive comparison. Assembly
cannot erase conflicting limitations or create a missing native commercial fact.
It can therefore still result in an explicit unresolved outcome. Source-scoped
adjudication uses at most two attempts per disputed source; one assembly can add
one full re-adjudication round. This increases bounded call count. No live model
success rate or end-to-end correctness improvement is claimed from these tests.

## Prefreeze checks

- Generic architecture suite: **13 passed**.
- Existing targeted suites plus the first nine architecture tests: **100 passed**;
  subsequent focused architecture/adapter check: **31 passed**.
- Ruff (configured tree and explicitly all modified Rental modules/new tests): passed.
- Configured mypy: passed, 17 files.

Frozen full pytest, Rental/privacy benchmarks and exact-head CI results follow in
this record after the implementation checkpoint is validated.
