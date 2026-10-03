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
reached the same EUR 150.00 / EUR 0.00 deterministic groups. The independent
v8 source reread found 6/8 exact entity differences and one material
disagreement: whether the off-hire request email is only supporting evidence
or a `RETURN` event. The email itself disclaims physical-return proof and the
agreement says a request does not stop billing. The QA correctly blocks
delivery pending cross-document adjudication. No genuine scan attestation,
blind outcome evaluation or final client report has been completed. These
remain release blockers.

The new `documents adjudicate-qa` path reopens all eight original DEV sources
and validates each returned native quote against its exact source unit/hash.
On the frozen v8 dispute it selected the primary email classification as
supporting evidence, citing both the email's disclaimer and the accepted
agreement's explicit request-versus-return rule. This changed the material
disagreement count from one unresolved to **zero unresolved for fact review**.
It approved zero facts and did not recompute or approve a final report. Five
advisory bundle differences remain; same-model adjudication is not an
independent correctness estimate. The ignored local receipt is under
`scratch/first_client_e2e_dossier/runtime_v8/documents/adjudications/`.

The next live internal analyst pass made one explicit decision per candidate:
first pass accepted 148 native facts and rejected one source-status
classification too literally; a single recorded source-local repair reopened
the email and accepted the justified `EXTRACTED` classification. It then
accepted **149 native facts** and deferred all **10 visual facts**. A separate
vision-model pass on the original return page first rejected the signed
record's `ACCEPTED` status, then corrected that classification in one bounded
pixel reread. It proposed 10/10 visual facts for a *real* operator check;
all visual flags remain unresolved and no human attestation was produced.
The immutable local proposals, repair histories and review receipts are under
`scratch/first_client_e2e_dossier/runtime_v8/documents/analyst_*`.

A deliberately scripted, **non-human/non-autonomous downstream fixture** then
exercised the actual package, Rental adapter, Evidence Plane, reconciliation,
review contracts and PDF renderer. It reached 159 facts, two EUR groups at
150.00 and 0.00, and a five-page PDF under ignored
`scratch/first_client_e2e_dossier/runtime_v8/integration_probe/`. The PDF is
not a deliverable: its findings were scripted and its first rendering displayed
debug hashes/generic fixture prose.

A later **model-driven downstream DEV run** reused that same fixture package,
without reading generator-private truth. One model assessment selected the
contract-supported quantity discrepancy; a separate original-source challenge
first rejected overconfident recovery wording. A bounded correction and repeat
produced a validated L2 finding: **EUR 150.00 documentary difference**, no
recovery-grade amount, with later credits/replacements explicitly unresolved.
All eight required adversarial finding checks passed. The first report QA found
client-visible internal labels and an unclear net/credit explanation; the
renderer now displays the deterministic 13 asset-days, EUR 900.00 invoice,
EUR 100.00 issued credit, EUR 800.00 net billed and EUR 650.00 expected charge.
A later independent original-source/PDF reread returned PASS with zero reported
unsupported claims and zero reported missed discrepancies on a five-page PDF.
The final evaluation PDF is watermarked on every page; SHA-256 is
`6f9ec76a8e27a2a691d57db6918877142b9ec7d5243e1a4e23c3be4952886a1d`.
The evidence-pack file SHA-256 is
`67464c51ede52692b852ed8a8a50a44b48ea0cf33900e39e7d0b4a5414c832de`.
Receipts and PDF are in ignored `scratch/first_client_e2e_dossier/runtime_v8/model_review_probe/`.
This is **one known synthetic dossier with a scripted visual attestation**, not
human review, a blind correctness score or permission to deliver. Same-family
model author/QA agreement cannot establish 99% material correctness.

`python investigate.py rental-autonomous PACKAGE --output-dir CASE --model MODEL`
now resumes a hash-bound reviewed-package-to-PDF job, records state/events,
returns an unchanged successful report without new model calls, and leaves
delivery unapproved. This is **not yet** a one-command raw authorized dossier
workflow. Authentic scan attestation, raw intake/privacy orchestration,
independent challenge dossiers and measured founder burden remain open.

## Missing integrated proof

The generator is committed, but a genuine operator has not visually inspected
the raster scan or signed final PDF/evidence hashes. The reviewed-package
downstream run is not a complete raw-to-report production job. Initial privacy,
fresh extraction/review/linking, authentic visual attestation, supplemental
privacy clearance and WAIT/RESUME must be integrated and rehearsed as one job.
No independent blind report-correctness rate, human correction/review time,
complete receipt-to-report time or token cost exists. Source/report mutation,
failure recovery and a clean fresh end-to-end repeat still need demonstration.
These are Gate A/B blockers despite the watermarked DEV sample PDF.

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
