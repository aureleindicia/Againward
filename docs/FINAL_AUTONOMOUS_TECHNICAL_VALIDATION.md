# Final autonomous technical validation — in progress

Mission: authorized raw Rental documents → autonomous investigation and QA →
finished source-backed report, with real final delivery authority retained.

This is not a completion certificate or a frozen evaluation. Current branch:
`release/first-rental-client-pilot`, draft stacked PR
[5](https://github.com/aureleindicia/Againward/pull/5), not merged.

## Verified development evidence

- Eight-source v9 rerun: all 8 primary extractions and all 8 independent
  rereads were regenerated after the guidance hash changed. On the rate sheet,
  both passes now represent LIFT-5 and LIFT-50 as separate row entities, each
  with its own identifier, rate, currency and billing unit. No row was dropped,
  no entity contains conflicting values for a semantic field, and the previous
  `UNSUPPORTED_PROMOTION` failure did not recur.
- The case then reached source adjudication. The first adjudication answer failed
  because it cited the agreement instead of the disputed return scan. Adjudication
  guidance v3 now explicitly requires `UNRESOLVED` when the disputed source has
  no verifiable native-text citation. The resumed run selected `UNRESOLVED` with
  no citations and correctly stopped at `WAITING_FOR_REQUIRED_INFORMATION` for
  the signed-return scan. No visual attestation was added; delivery and human
  approval remain false.
- Changing only adjudication policy reused exactly 16 source passes (8 primary,
  8 challenger); it invalidated and regenerated the adjudication and later review
  stages. This is the permitted reuse boundary, not evidence reuse across the v9
  guidance change.
- A fresh raw, real-style synthetic case completed the integrated privacy and
  native-document path through an actual client PDF. Both originals were native
  PDFs; Codex read the originals, Python bound their hashes, deterministic code
  calculated the ledger, and Codex performed findings and PDF QA. The run was
  evaluation-only and did not authorize delivery. It does not establish accuracy
  on independent cases.
- A live synthetic privacy probe allowed an ordinary professional-contact PDF
  and blocked a medical/HR-sensitive attachment. A synthetic secret was blocked
  on retry; its first model response failed schema validation. These three probes
  are development checks, not a blinded privacy benchmark.
- Two native PDF sources passed the approved-source job through extraction,
  separate source reread, fact review, deterministic reconciliation, model
  findings and actual PDF QA. The first run required renderer corrections.
- A fresh run after the generic discrepancy-family correction stopped on exact
  citation/schema validation; a revised QA prompt retained strict validation and
  the resumed run passed. Synthetic PDF SHA:
  `d665d43df0b26685cf20b0611e93d75b10b7328f3e99813d9b07e1838a02184e`.
  Receipt:
  `scratch/source_job_dev_cases/pair_v2/processed/autonomous_report/report-adc293aeee96b6baf9b405e135cc50b1e6eec339c2b67891a48d97df3623ab17.json`.
  This was DEV before later policy-binding changes, not a frozen final run.
- All results remain `EVALUATION_ONLY_QA_PASSED`, with human approval and
  delivery authorization false. Separate same-model QA is not independent
  outcome adjudication.

## Acceptance still open

The refreshed eight-source run stops before native fact review because a
material disagreement concerns a visual-only signed-return scan. The adjudicator
correctly refuses to select either proposal without source evidence that can be
verified independently. The next step requires genuine inspection/attestation
of that scan, after which the case can continue into native/visual fact review,
entity links, calculations and report QA.

Also open: frozen varied final challenge; independent final-report adjudication;
measured founder review burden; full supplemental/revision integration evidence.
Do not infer 99% correctness or 95% correction-free operation from unit tests or
a few synthetic reports.

See [failures](FINAL_AUTONOMOUS_FAILURES.md),
[metrics](FINAL_AUTONOMOUS_METRICS.md) and
[release boundaries](FINAL_RELEASE_BOUNDARIES.md).
