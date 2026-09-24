# Final autonomous technical validation — in progress

Mission: authorized raw Rental documents → autonomous investigation and QA →
finished source-backed report, with real final delivery authority retained.

This is not a completion certificate or a frozen evaluation. Current branch:
`release/first-rental-client-pilot`, draft stacked PR
[5](https://github.com/aureleindicia/Againward/pull/5), not merged.

## Verified development evidence

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

The refreshed eight-source run currently stops at native fact promotion: two
distinct rate-card row descriptions were assigned to one aggregate entity, so
the single-value-per-entity invariant rejected them. Rental guidance now requires
row-level entities for each independently priced asset, but the refreshed
end-to-end run has not yet tested that change. Its signed-return scan still needs
genuine pixel inspection before those visual facts can be promoted.

Also open: frozen varied final challenge; independent final-report adjudication;
measured founder review burden; full supplemental/revision integration evidence.
Do not infer 99% correctness or 95% correction-free operation from unit tests or
a few synthetic reports.

See [failures](FINAL_AUTONOMOUS_FAILURES.md),
[metrics](FINAL_AUTONOMOUS_METRICS.md) and
[release boundaries](FINAL_RELEASE_BOUNDARIES.md).
