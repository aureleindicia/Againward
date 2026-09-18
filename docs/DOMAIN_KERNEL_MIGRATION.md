# Domain kernel migration — implementation record

## Baseline and isolation

The full goal in `AGAINWARD_GIGA_GOAL_DOMAIN_KERNEL_RENTAL.md` was read before
implementation. Remote `main` was fetched at `c27f261`. The original worktree has
uncommitted prospecting work; it is preserved without stashing or including it.
Migration work lives in the sibling `againward-domain-kernel` worktree on
`refactor/domain-kernel`. No changes are made to `main`.

An existing, unmerged architecture branch at `0736bf6` contained lifecycle,
artifact recovery and evidence-budget corrections. Those corrections were merged
before extraction, preserving their history and regression tests.
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

Implemented: neutral kernel and evidence boundary; explicit domain routing; Energy
adapter and compatibility; generic Rental ingestion/model/ledgers/findings;
Construction profile; R01–R06 plus seven adversarial benchmarks; shared review and
delivery integration; additional privacy batches preserving WAIT/RESUME.

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

Committed Evidence/kernel checkpoint `ede4029`: **561 passed in 196.44 s** in a
separate immutable worktree (full suite including HOLDOUT packaging/integrity).
Energy preparation now delegates through `DomainPack` to the shared workflow;
quantitative work and physical policy remain in `EnergyDomainPack`. A document-only
pack exercises the same orchestration with no physical fields. Explicit workspace
and selected-domain mismatches fail before parsing. Routing-focused checks:
**97 passed**, then **19 passed** including direct domain equivalence checks.

## Rental integration and audit

`9496e15`: full suite in the immutable validation worktree — **619 passed in
234.19 s**, no skips or failures. This includes the existing Energy, privacy,
Evidence Plane, lifecycle, delivery and benchmark tests plus Rental integration.

R01–R06 plus seven adversarial variants: **13/13 passed**. The scorer reports three
supported-positive cases, zero false positives, zero false negatives and ten
negative/ambiguous cases before the R06 answer. No automatic recovery claim is
created. R06 proves a single BLOCKING request, a blocked query during WAIT, a
synthetic answer, budget-preserving recalculation, review and FINALIZABLE state.
These scripted fixtures are not an evaluation of autonomous agent reasoning.

The numerical review additionally fixed caller-dependent Decimal precision,
duration-tier selection after return, documentary authority for operational events,
and quadratic amendment/percentage dependency traversal. Seven dedicated adverse
tests brought targeted Rental coverage to **61 passed**.

Additional evidence uncovered a real workflow gap: a previously cleared manifest
must not authorize a new incoming batch. New batches now need their own semantic
review and deterministic post-check. They preserve earlier sanitized documents,
approval history and pending client questions; they cannot overwrite old sources.
An unsolicited accepted batch requires RESUME. Rental calculations bind the privacy
manifest version and require recalculation after it changes. Validation: **141
targeted tests passed**, then the enriched five privacy tests passed separately.

See [ARCHITECTURE.md](ARCHITECTURE.md), [RENTAL.md](RENTAL.md) and
[RENTAL_BENCHMARKS.md](RENTAL_BENCHMARKS.md) for final boundaries, supported conventions,
explicit limits and reproducible commands. Compatibility aliases remain deliberate.

## Final validation

Committed implementation and documentation checkpoint `72170ec`, executed from a
separate immutable worktree: `python -m pytest -q` — **629 executed, 629 passed,
0 skipped, 0 failed in 215.76 s**. No test expectations were relaxed to conceal
Energy regressions. Monthly and 15-minute report hashes and the original v1
evidence fixture remain identical.

The final standalone Rental benchmark also passed **13/13** on `72170ec`.
Portable aggregates, exact metrics and timing scope are committed under
`benchmarks/rental/`. Final timing: 1,000 invoice lines in 0.397 s and 10,000 in
3.836 s for canonical validation, ledgers and reconciliation. The subsequent
acceptance/results commit changes documentation and benchmark result artifacts
only, not the tested implementation.

Main remained `c27f261` locally and remotely at the final verification. Its original
uncommitted prospecting work was left in place; this worktree stays separate.
The feature branch is published as `refactor/domain-kernel`; no automatic merge
is performed. [DOMAIN_KERNEL_ACCEPTANCE.md](DOMAIN_KERNEL_ACCEPTANCE.md) maps the
Goal's completion criteria to concrete implementation and validation evidence.

## CI portability correction

The first GitHub CPython 3.11 run passed 628 tests and exposed one characterization
fixture mismatch: the demo JSON had been frozen on CPython 3.14. The Energy engine
was unchanged; the pre-3.12 `sum()` algorithm explains the low-order float difference.
An independent export of original `c27f261` with that left-fold algorithm reproduced
the exact failing CI hash. Native and legacy fixtures are now both checked strictly,
without numeric tolerances or changing production calculations. Monthly JSON and
both Markdown hashes are identical across these two summation paths. The two new
parameterized checks pass locally; full CI is rerun on the corrected fixtures.
