# First-client source-to-report validation — open

Status: **not complete**. This file separates a source-driven technical probe,
scripted regression fixtures, and the still-required accountable rehearsal.
Nothing below authorizes receiving an actual client's confidential files.

## Source-driven technical checkpoint

On 2026-09-23, two ordinary synthetic PDF sources (`commercial.pdf` and
`billing.pdf`) were submitted to the real Codex CLI participant. The source
SHA-256 values are `b14e53de6177a014a3679d0994dbc44c7cadf70743f55e02be85378c8d9bed6d`
and `03f49eb83589849c372d8309b0e46c884c6d5a859998c870e9c2ffe081df3cea`.
The v3 output contained 37 source-bound candidate facts, no extraction-level
limitations and no approved facts. The implementation agent then inspected
both original PDF text streams and every candidate against an explicit
expected-field map in ignored `scratch/model_pair_technical_probe.py`. Running
`python -m scratch.model_pair_technical_probe` in this local worktree produced
37 synthetic technical-review facts, one exact matching Rental relationship,
and a deterministic EUR 1,400.00 expected / EUR 1,550.00 actual / EUR 150.00
potential discrepancy. The probe used `ANALYST`, never `HUMAN`; it did not
authorize delivery. The local ignored extraction and source bytes live under
`scratch/semantic_guidance_v2_probe/`. They are not yet a committed stable
sample dossier, so this checkpoint is not independently reproducible from the
PR alone.

A separate CLI regression test exposed an actual production handoff defect:
`documents package-rental` saved a reviewed package in `documents/packages/`,
while `load_rental_case` looked for `sources/` beneath that directory. Before
the fix, a package emitted by the documented command failed with
`SOURCE_UNREADABLE`. The regression now consumes the exact emitted package,
replays source hashes, prepares the Rental investigation and revalidates the
EUR 150.00 ledger. This fixture uses manually supplied semantic annotations;
it is **not** model accuracy or human rehearsal evidence.

## Eight-source model checkpoint — still not source-to-report

A reproducible DEV generator now exists at
[`benchmarking/first_client_dossier.py`](../benchmarking/first_client_dossier.py).
It emits an accepted agreement, duplicate rate sheet, two issued invoices, an
issued allocated credit, one raster signed return, a supplier off-hire email
and a mirror-only accounting XLSX. Its source files are not canonical JSON.
The expected EUR 150.00 potential LIFT-5 discrepancy and EUR 0.00 LIFT-50
non-discrepancy are agent-authored private generator truth, not blind accuracy
evidence. The public source bytes were regenerated twice with identical
SHA-256 values. The v7 source extractor validated 8/8 proposals,
162 source-backed candidate facts and **4/6** structurally complete material
entities under the corrected enum audit. The prior 6/6 claim missed two
invalid optional partial-period values on agreement scopes. It approved
**zero** facts. A blind second source reread found
6/8 exact entity-bundle differences; a narrower ledger-material projection
found 0/8 disagreements, with the same-model-family caveat. The initial QA
call failed safely on a bad quote before the bounded retry path was added.
See [semantic evaluation](SEMANTIC_EXTRACTION_EVALUATION.md) for the receipt.

This is substantial intake/extraction evidence, but still **not** a complete
privacy-cleared source-to-ledger-to-report demonstration. The private truth is
known to the agent; the case has no independent outcome adjudication, no real
visual attestation, no approved report and no measured human-correction rate.

A DEV-only technical probe rejected the two bad optional policy candidates
with an explicit rationale, then passed 160 source-backed facts through the
actual Rental adapter and deterministic reconciliation. It found EUR 150.00
on one group and EUR 0.00 on the other. The raster fact check used a
`SCRIPTED_FIXTURE_NOT_HUMAN` response solely to exercise protocol mechanics;
it is not a valid human attestation, cannot approve a client report and must
not enter quality numerator counts. The prompt has since changed to v8, so
strict replay correctly marks the v7 package `REVIEW_STALE`; new source
extractions are required.

The same eight source hashes were re-extracted under v8: **8/8** validated
source proposals, **159** candidate facts, **6/6** structurally complete
material entities, and no erroneous partial-period candidate. A fresh
technical probe using the v8 facts and a scripted visual protocol fixture
reached the same EUR 150.00 / EUR 0.00 deterministic groups. No independent
v8 source reread, genuine scan attestation, blind outcome evaluation or final
client report has been completed. These remain release blockers.

## Missing integrated proof

The generator is committed, but a genuine operator has not visually inspected
the raster scan or signed the final PDF/evidence hashes. Internal Codex still
needs to reconcile advisory differences, prepare independently justified
source-backed fact/link decisions, run the Evidence Plane on a genuine
approval path, write and adversarially check the report, and demonstrate
minimal founder correction burden. A technical ledger run alone is not that
rehearsal. No
receipt-to-report time, token cost, actual human labor or sample client PDF
exists. Source/report mutation, supplemental privacy clearance, WAIT/RESUME
and a clean repeat still need demonstration on this dossier. A separate blind
outcome challenge is also missing. These are Gate A/B blockers.

## Required next rehearsal, in order

1. Freeze the current generated eight-document source hashes and record its
   known-truth status. Challenge a genuinely new independent dossier before
   claiming generalization.
2. Run the [internal analyst playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) from a fresh
   workspace, recording exact source/extraction/review/package/report hashes
   and machine/model/human time separately.
3. Have Codex perform ordinary semantic, link, finding and report review;
   measure corrections and independent QA catches. Have the owner or named
   operator inspect only the required scan pixels and briefly approve the
   finished PDF/exception pack. Preserve STOP on unreviewed visual components;
   no generated `HUMAN` assertion counts as that action.
4. Challenge mutations, recovery, supplemental intake and a second clean run;
   record whether each invalidates approval or reproduces the result.

Until these steps are evidenced, report status remains **NOT READY**.
