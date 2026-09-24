# Final autonomous technical validation — in progress

Mission: authorized raw Rental documents → autonomous investigation and QA →
finished source-backed report, with real final delivery authority retained.

This is not a completion certificate or a frozen evaluation. Current branch:
`release/first-rental-client-pilot`, draft stacked PR
[5](https://github.com/aureleindicia/Againward/pull/5), not merged.

## Verified development evidence

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

Live proof of raw privacy orchestration; complete refreshed eight-source run;
freeze and varied final challenge; independent final-report adjudication;
measured founder review burden; end-to-end supplemental/revision and failure
injection receipts. Do not infer 99% correctness or 95% correction-free operation
from unit tests or a few synthetic reports.

See [failures](FINAL_AUTONOMOUS_FAILURES.md),
[metrics](FINAL_AUTONOMOUS_METRICS.md) and
[release boundaries](FINAL_RELEASE_BOUNDARIES.md).
