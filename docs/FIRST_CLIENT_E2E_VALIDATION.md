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

## Missing integrated proof

The required independent eight-or-more-document folder does not yet exist as
a stable source-backed sample. In particular, a genuine operator has not
visually inspected a raster scan, resolved an ambiguity, approved every
positive claim, or signed the final PDF/evidence hashes. The real Codex model
has not been challenged through the complete eight-document privacy-first
workflow. No measured receipt-to-report time, token cost, human labor or
sample client PDF exists. Source/report mutation, supplemental privacy
clearance, WAIT/RESUME and clean repeat still need to be demonstrated on that
same dossier. Those are Gate A/B blockers, not inferred passes from unit tests.

## Required next rehearsal, in order

1. Generate and freeze one coherent eight-document synthetic dossier with
   accepted rates, two invoices, issued credit, raster return, email and
   spreadsheet, including a discrepancy and a confusing non-discrepancy.
2. Run the [operator playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) from a fresh
   workspace, recording exact source/extraction/review/package/report hashes
   and machine/model/human time separately.
3. Have the owner or named operator perform the visual, semantic, link,
   finding and PDF review personally. Preserve STOP on unreviewed components;
   no generated `HUMAN` assertion counts as that action.
4. Challenge mutations, recovery, supplemental intake and a second clean run;
   record whether each invalidates approval or reproduces the result.

Until these steps are evidenced, report status remains **NOT READY**.
