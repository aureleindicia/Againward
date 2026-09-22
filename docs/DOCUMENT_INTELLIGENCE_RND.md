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

## Document corpus and completeness counterexample

The new generator produces actual files for twenty A–T families and keeps truth
outside the public document folders. Poppler rasterizes meaningful invoice text;
the scan has no hidden text layer. XLSX ZIP/core timestamps are frozen for byte
reproducibility. A runner accepts external source-bound proposals and invokes the
real adapter, while the scorer reads truth only after observations are frozen.

Initial DEV routing-only baseline: TP 0, FP 0, FN 6, TN 14; recall 0, 9/9 required
abstentions, no denominator for precision. No semantic extractor ran. This is
deliberately a failing intelligence baseline, not acceptance. Date/link/lifecycle
scoring and independent semantic runs remain open; see REAL_WORLD_RENTAL_BENCHMARKS.

A PDF completeness probe found direct-XObject inspection missed images nested
inside Form XObjects or inline content. Both now route to hybrid review. The
reader contract is bumped to v2; old proposal replay requires explicit
revalidation, rather than silently trusting the old component classification.

Integration commit fc10275 passed all remote Python 3.11/3.12/3.13/3.14 checks.
New corpus/adapter/parser selection: 48 passed in 28.62 s before the reader-version
regression test. The final clean-worktree suite still needs to be recorded.

## Clean milestone validation at 465f392

Detached validation worktree: **693 passed, zero skipped, in 239.29 s**, CPython
3.14.6 on Termux. The two dirty-tree HOLDOUT refusals are resolved by testing the
committed tree, not by altering the guards. Ruff and gradual mypy pass. Legacy
Rental again passes 13/13. Concurrent-load timing sample: 1,000 lines 0.286041 s,
10,000 lines 2.946299 s; do not compare this contended sample as a clean regression
measurement against the earlier isolated baseline.

Clean-engine document routing runs: DEV seed 7421 and ADVERSARIAL seed 19341,
20 folders each, both TP 0 / FP 0 / FN 6 / TN 14, required abstention 9/9 and
semantic recall 0. No extractor was invoked and HOLDOUT remains unevaluated.
The generated scan invoice was visually inspected: meaningful readable invoice
text exists as pixels, with no hidden text layer. This is renderer verification,
not a visual extraction quality measurement.

Remote CI at 465f392 initially passed all four Python versions with 689 passed
and four skipped: Poppler was absent. The workflow now installs the synthetic
scan renderer explicitly so those tests cannot silently disappear from CI.
Only workflow/docs change after this tested implementation milestone.

## H4: documented unit-day segments and dated rates (2026-09-23)

Baseline `tests/test_rental_pricing.py` refused a partial return because the old
timeline only accepted full-quantity stop events. A dated amendment had no
effective-date field and its accepted version replaced the rate for the whole
period. New `temporal.py` activates only for a documented partial return under
an explicit RETURNED stop rule with daily billing, or for an accepted dated
amendment. It splits the interval at return and rate boundaries and rounds once
for the whole charge. The ordinary single-term path remains in use otherwise.

Independent arithmetic probe: four units start 1 September; two return on day
10 and two on day 17. Expected 4×9 + 2×7 = **50 unit-days**, at EUR 75 =
**EUR 3,750**. A rate change on day 8 to EUR 60 yields 4×7×75 + 4×2×60 +
2×8×60 = **EUR 3,540**. Before this change both patterns abstained or applied
the amended rate retroactively. Source spans for the accepted agreement,
amendment and signed return remain in each segment's references.

Unsupported weekly partial returns still abstain. A declared or over-quantity
return, missing stop-day convention, nonzero minimum, incompatible amendment,
forked effective dates or extension with segments yields an unknown amount.
The dated amendment adapter inherits prior conventions only when an accepted,
reviewed `terms_unchanged` clause explicitly supports that inheritance.
Legacy canonical v1 serialization omits absent `effective_from`, so unchanged
cases keep their previous normalized shape. This is not proof that the generated
document benchmark's partial-return/rate-amendment families have been extracted
and scored; those semantic runs remain outstanding.

## H8: unallocated and partially allocated credit notes (2026-09-23)

Before: Rental v1 required every credit to name a known invoice line. A source
credit note referencing only an invoice, or an issued credit allocated in part,
could not enter reconciliation without assigning the whole amount to a line.
The baseline synthetic invoice was EUR 850 against an expected EUR 700; a fully
allocated issued EUR 150 credit correctly brought the net to EUR 700.

Now credit state is explicit: unallocated, candidate, partially allocated or
confirmed. With no confirmed line, an accepted issued EUR 150 credit remains
in the unallocated register; the EUR 850 line is unchanged and the affected
group has no supported numeric difference. For a source-supported EUR 80 partial
allocation from that EUR 150 note, the line nets to EUR 770 while the remaining
EUR 70 blocks a supported difference. An exact confirmed full allocation still
nets to EUR 700 with zero discrepancy. A documented invoice ID bounds the
uncertainty to groups containing that invoice; absent invoice ID, it conservatively
affects same-currency groups. No cross-currency application occurs. Promised
credits never reduce issued net. New source-to-ledger tests use quoted synthetic
credit notes; their annotations are scripted and do not count as model accuracy.

The model refuses over-allocation, missing line links for asserted allocations,
currency mismatch and invoice-ID contradiction. Legacy fully allocated credit
serialization and Evidence Plane rows retain their prior shape. The decision
to suppress an affected numeric gap is conservative: without the credit note's
line allocation, EUR 150 may or may not offset the candidate invoice line.
Independent semantic extraction of these notes remains unevaluated.
The contractual benchmark now has 15/15 passing explicit cases (TP 3, FP 0,
FN 0, TN 12 on supported positive discrepancy). Its new credit assertions also
require exact applied and unallocated amounts and a null group difference.
Targeted reconciliation, document-adapter and benchmark tests: 34 passed.

## Rental privacy continuation baseline (2026-09-23)

The authoritative continuation goal is
`AGAINWARD_GOAL_RENTAL_PRIVACY_REPO_HARDENING.md` (SHA-256
`47e435639302fa210c1045a3a55b98a29c90edbe2730b0e63003e49effa41c16`).
Start: clean `rnd/real-world-document-intelligence` HEAD `94d9d2a`, draft PR #3
still stacked on open PR #2. A new worktree/branch
`rnd/rental-privacy-repo-hardening` keeps the original main worktree untouched.
Baseline full suite: 722 passed in 293.79 s; privacy/source subset: 88 passed
in 14.14 s. Ruff and configured mypy passed. Five generated native/scan/hybrid
PDF probes all failed at `_scan()` solely because `.pdf` was not inspectable;
the full gate blocked a clean native contract. Root AGENTS: 38,051 bytes,
2,069 lines, with historical Energy build steps and obsolete ownership notes.
The next experiments measure both false blocks and unsafe passes, not just
successful PDF parsing. Privacy clearance remains distinct from semantic
document extraction and from business confidentiality.
