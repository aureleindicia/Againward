# Rental privacy benchmark — synthetic policy test

Run from a clean output directory:

```sh
python run_rental_privacy_benchmark.py --output scratch/rental-privacy-run
```

The runner generates ordinary and adversarial PDF/scan fixtures locally, stages
each in a synthetic Rental workspace, performs a scripted privacy review, runs
the actual contract/privacy gate, and checks the resulting decision and failure
code. The ordinary folder also passes eight approved documents (six PDFs,
including a return-note scan; one XLSX; one EML) through source inventory and
readers. Its scan must retain a `MULTIMODAL_REQUIRED` route.

Measured on Termux, Python 3.14, 2026-09-23: **19/19 cases passed**;
11 ordinary cases accepted; eight unsafe cases rejected; **0 false blocks,
0 unsafe passes**. The starting branch rejected all five native/scan/hybrid
PDF probes merely as `.pdf`; this run accepts native business PDFs and
source-bound human-reviewed scans, while rejecting corrupt, secret, medical,
HR-sensitive and identity-document sources. The result is saved as
`validation.json`, with per-case expected/actual decisions, failure taxonomy,
counts and runtime. The test suite replays these assertions; a nonempty output
directory is refused to preserve a prior result.

This is a *policy enforcement* benchmark, not an OCR, human visual detection,
semantic extraction or real-client accuracy benchmark. Visual reviews are
scripted test attestations. The `HUMAN` role in a review JSON is not an
authenticated identity; a real reviewer must inspect every required visual
component and stop when that is not possible. The separate document-intelligence
benchmark still reports zero semantic recall without independent proposals.
