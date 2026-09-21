# Document intelligence R&D — active work

Mission specification: AGAINWARD Giga Goal, read in full on 2026-09-21.
SHA-256: aaba6c33d9986878e8841ce3b7e98a47da8a8f3d397e733f3d913f25cb611378.
This report records experiments and unfinished work; it is not an acceptance claim.

## Verified baseline before implementation

Base: `b6369bec0e9d4e41ed800b99f26af61ad4150102`, branch
`refactor/domain-kernel`. Main remains `c27f261`. PR #2 is open, not merged,
and both reported GitHub checks pass. Work is isolated on
`rnd/real-world-document-intelligence`; the original dirty prospecting worktree
is untouched. The eventual PR targets `refactor/domain-kernel`.

An initially clean worktree ran on Termux CPython 3.14.6:

| Check | Observed result |
|---|---|
| Full pytest | 631 passed, 293.63 s |
| Energy characterization, boundaries, workflow/path tests | 47 passed, 7.43 s |
| Existing Rental benchmark | 13/13; TP 3, FP 0, FN 0, TN 10 |
| Rental 1,000 invoice lines | 0.314389 s |
| Rental 10,000 invoice lines | 2.452171 s |
| Privacy 10k / 100k / 500k rows | PASS; 0.188 / 0.937 / 5.514 s |
| Question selection 10 / 100 / 1,000 candidates | 3 selected; median 5.604 / 51.541 / 477.17 ms |
| Architecture probes | WAIT cannot finalize; optional answer requires RESUME; two independent questions preserved; 100 kW × two quarters = 50 kWh; exhausted session remains readable |

Commands: `python -m pytest -q`; `python run_rental_benchmark.py --output
scratch/document_baseline_rental --performance`; `python
benchmarks/client_workflow/benchmark.py`; `python
benchmarks/privacy_gate/benchmark.py`; `python -m
benchmarking.architecture_probe`. Benchmarks updated their own tracked result
files; these measured baselines are included in the baseline commit.
No source code changed during the full-suite run. Timings are device observations,
not thresholds, and some probes ran concurrently. Rental timing excludes extraction.

## Observed weaknesses

1. Rental starts from canonical JSON or explicit table mappings. The historical
   generator writes canonical records inside source text; it does not measure
   understanding of realistic documents.
2. `EvidenceRef.location` validates only a nonempty string. A read-only probe
   replaced an invoice location with `page:99999/line:99999` and
   `RentalCase.from_dict` accepted it. Hash validity does not prove location
   validity or semantic truth.
3. Entity links are preassigned IDs. There is no ambiguity state upstream of
   these assignments and no measured blocking recall.
4. Partial returns abstain; rate amendments replace whole terms rather than
   expressing effective dates. Credits require a known invoice line.
5. Domain preparation receives Energy loading defaults through the shared CLI.
6. Rental recalculation correctly preserves snapshots and remaining query budget,
   but owns the multi-artifact revision sequence directly.
7. Privacy has 1,644 lines; evidence protocol has 754 and plane 521. Size alone
   does not justify moving them. Existing gates must remain authoritative.
8. The privacy post-check refuses PDF/images. Adding an analytical parser does
   not authorize a real binary source or justify bypassing this gate.
9. CI tests only Python 3.11 despite exact Energy fixtures reflecting summation
   differences across versions.
10. Repository layout documentation still describes historical owners, and root
    instructions mix permanent invariants with completed historical tasks.

## Preregistered experiments

| ID | Hypothesis / minimal candidate | Baseline / acceptance evidence |
|---|---|---|
| H1 | Content-bound source batches centralize inventory, deduplication and privacy binding | Compare per-file gate/hash checks; duplicate/rename/order invariance, supplemental privacy and source-mutation tests |
| H2 | Candidate facts plus exact source units prevent unsupported location promotion | Baseline accepts impossible location; candidate validator must reject nonexistent location, altered quote, changed hash, invalid numeric/date and stale extraction |
| H3 | Explicit relationship states and deterministic blocking reduce false financial links | Ambiguous and conflicting IDs cannot become confirmed; measure candidate recall and confirmed pair precision separately |
| H4 | Quantity/rate segments safely quantify documented partial returns and effective rates | Baseline abstains; compare independently calculated unit-days; keep abstention for unknown conventions and conflicts |
| H5 | Neutral options and shared revision intent reduce domain leakage | Third document-only domain needs no Energy fields and no core business imports; preserve exact Energy characterization |
| H6 | Small navigation map is enough to distinguish active code from history | Correct active owners and runnable entry points; avoid mechanical file relocation |
| H7 | Privacy/evidence decomposition pays for itself only through changed responsibilities | Defer broad split unless document support creates a specific tested boundary; preserve transaction store |

## Execution order and evidence discipline

Source inventory/routing → structured extraction and validated replay → explicit
resolution → reviewed canonical promotion → Rental/Evidence integration →
document-generated DEV/ADVERSARIAL/HOLDOUT benchmark → temporal extensions →
kernel/CLI/tooling improvements justified by probes → clean validation and acceptance.

Benchmark truth belongs to the generator/scorer, never the participant. Scripted
extraction/review fixtures must be labelled and cannot count as model accuracy.
No paid provider calls, real-client evidence, human approval or merge is implicit
in this engineering mission. Offline semantic proposals are an intended provider
boundary; uncaptured scans stop for review rather than being transcribed by guess.

## First implementation experiments (2026-09-21)

H1/H2 now have executable probes in `tests/test_document_sources.py`.
Snapshots preserve approved bytes and aliases separately; a supplemental receipt
binds the union and current privacy manifest. Historical receipts remain immutable.
Candidate validation re-reads the source, checks exact location/character span,
raw quote, schema, finite bounded values and extractor versions. Confidence has no
promotion effect. Fact review binds the exact extraction hashes; formula values
require a fixed-value source and ambiguous dates retain a review flag.

Initial run: 27 passed and three PDF failures. The fixed 384 MiB address-space
ceiling aborted the worker on Android before parsing: a small trusted pypdf
process measured VmSize 10,890,256 KiB versus VmRSS 34,880 KiB. The corrected guard
limits additional address space after trusted imports, with a CPU limit and
parent timeout. This is resource containment, not a complete hostile-PDF sandbox.
Native, scan-only and hybrid routing subsequently passed.

First source/resolution suite: 45 passed in 3.60 s. Broadened check (including
Energy characterization, Rental privacy/ingestion and artifact recovery):
70 passed in 6.94 s. Gradual mypy: eight new document modules, no issues.
These are contract tests, not end-to-end acceptance or model accuracy.

H3 probes: 100 exact source pairs among 200 entity occurrences are retrieved with
100 comparisons instead of the 19,900 theoretical all-pairs comparisons.
Ambiguous alternatives lower a unique match to AMBIGUOUS; conflicting IDs remain
CONTRADICTED. Reused model-local entity labels never merge different documents.
The fixture proves these declared keys, not real-world blocking recall.

Ruff installation first failed on Android with `Text file busy` in a parallel
Rust build. The single-job retry also aborted in Rust compilation. The native
Termux package (`apt-get install ruff`, 0.16.8) succeeded without adding a runtime
dependency. CI expands to Python 3.11–3.14; remote results remain to be checked.

## Reviewed source-to-Rental integration (2026-09-22)

The optional document package now replays every source extraction, promotes only
explicitly reviewed facts and derives Rental foreign keys from confirmed links.
An unassigned material entity or unextracted component blocks financial
preparation. Missing rates remain unknown. This conservative gate does not yet
provide partial-case investigation of an unresolved credit or visual component.

Facts and relationships are typed Evidence Plane rows, including exact quotes,
source spans and extraction/review hashes. Fresh replay checks the entire stored
lineage; changing provenance alone invalidates review. The human evidence pack
retains this chain, without granting delivery approval. Legacy case datasets are
unchanged when no document lineage is present.

Verification: 47 document contract tests in 5.06 s; 15 Rental adapter/legacy
ingestion/workflow tests in 4.84 s before the final report-chain test was added.
Full working-tree run: **682 passed, 2 failed in 241.78 s**. Both failures were
the pre-existing HOLDOUT clean-engine guards refusing intentional uncommitted
engine changes. Do not weaken these guards: repeat from a clean committed
validation worktree before treating the full suite as passed.

Old Rental benchmark remains 13/13, TP 3 / FP 0 / FN 0 / TN 10. Current canonical
performance: 1,000 lines 0.275663 s; 10,000 lines 2.538831 s versus baseline
0.314389 / 2.452171 s. Single noisy samples, not evidence of a speed improvement.
Gradual mypy passes eight document modules; targeted Ruff checks pass after
fixing fixture formatting and an ambiguous variable name.

Still pending: completed real-document semantic benchmark (not merely routing),
temporal extensions, final privacy binary-format decision, acceptance matrix,
clean full validation and first-client challenge. The mission is not complete.
