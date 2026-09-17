# Domain kernel migration — implementation record

## Baseline and isolation

The full goal in `AGAINWARD_GIGA_GOAL_DOMAIN_KERNEL_RENTAL.md` was read before
implementation. Remote `main` was fetched at `c27f261`. The original worktree has
uncommitted prospecting work; it is preserved without stashing or including it.
Migration work lives in the sibling `againward-domain-kernel` worktree on
`refactor/domain-kernel`. No changes are made to `main`.

An existing, unmerged architecture branch at `0736bf6` contains proven lifecycle,
artifact recovery and evidence-budget corrections. Those corrections will be
integrated before extraction, preserving their history and regression tests.
In particular, a pending blocking request must not be dismissed by budget closure.

## Inspection and intended boundaries

The current `workflow.py` mixes quantitative Energy preparation with lifecycle,
evidence persistence, templates and report gates. `EvidenceDataset` constructs
its rows directly from `LoadedData`. Client request selection imports the
electrical attribution module only for generic question partition calculations.
The delivery gate also mixes reusable review mechanics and Energy-specific
physical recommendations/economics/report policy.

Extraction will therefore follow semantics rather than move every module:

* Core owns lifecycle, bounded requests, durable artifacts, case paths, privacy,
  workspace creation and domain-neutral review/orchestration contracts.
* Evidence owns typed record snapshots, hashes, bounded queries and handles.
  The existing v1 Energy snapshot remains readable and reproducible through an
  explicit compatibility adapter; new domains use a versioned generic schema.
* Energy retains its numerical engine and physical/economic policies. Its domain
  pack supplies preparation and review policy to shared orchestration.
* Rental owns commercial documents, item/event identities, exact-decimal charge
  ledgers, reconciliation and finding evidence requirements. Construction is an
  optional vocabulary/profile, never a requirement of the Rental ledger.

No network services, new LLM API, automatic claims or domain auto-detection are
introduced. Client-facing semantic decisions remain agent/human responsibilities.

## Characterization

Before migration, the monthly and 15-minute demo reports were reproduced through
`analyze.py`. Tests freeze the JSON and Markdown SHA-256 values and a complete
Energy v1 evidence snapshot. A direct unit check verifies two quarter-hours at
100 kW produce 50 kWh. Full-suite results and subsequent checkpoints are recorded
below as execution completes.

## Completion tracking

Pending: neutral kernel extraction; neutral evidence boundary; domain routing;
Energy compatibility; Rental model/ingestion/ledgers/findings; Construction profile;
R01–R06 and adversarial benchmarks; privacy and delivery integration; broad tests;
architecture/user documentation; branch push and unmerged PR.

Initial main baseline: `python -m pytest -q` — **516 passed in 108.22 s**.
New characterization checks: **3 passed**; both reports and the snapshot match.

## Kernel and Evidence checkpoints

The shared mechanics now live in `againward/core`; historical module aliases refer
to the same objects (including transaction locks and monkeypatch points). Workspace
creation accepts explicit domain context. Question utility no longer imports the
electrical attribution engine. The existing closed learning-retention schema is
isolated in `againward/compat`, without importing Energy learning/economics.

Targeted extraction: **128 passed**; workspace/attribution/learning: **39 passed**;
dependency checks: **3 passed**. A broad run begun before extraction finished with
546 passed and one HOLDOUT integrity failure because files changed during the run.
That is not accepted as full validation; the immutable committed engine must be
rerun at a later checkpoint. HOLDOUT integrity checks remain enabled.

The v2 evidence envelope accepts typed records and hashes dataset identity, source
set, per-row document locations and arbitrary metadata. It has no physical model.
The Energy adapter constructs its existing v1 envelope without changing bytes.
Generic queries can read v1 without importing Energy, and v2 source slices include
only their bounded source references. Benchmark engine exports now include the
new package, preventing incomplete participant environments after extraction.
