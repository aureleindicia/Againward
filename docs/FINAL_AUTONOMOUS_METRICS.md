# Final autonomous metrics — frozen-code development checkpoint

No QA-passed delivered report cohort has been independently adjudicated. A
separate five-case synthetic pre-freeze tranche has now been scored against its
precommitted case oracles; none of its reports passed final QA, so its
delivered-report denominator is zero.

**MEASURED: not yet measured / N=0 independently adjudicated final cases.**
**TARGET: ≥99% material correctness; ≥95% supported cases without human correction.**

| Measurement | Observed evidence | Limitation |
|---|---|---|
| Rental kernel benchmark at `4b536e4` | 15/15; 3 TP, 0 FP, 0 FN, 12 TN; 10,000 invoice lines in 3.36836 s | Small scripted fixtures; performance excludes document extraction/report I/O; not model/report accuracy |
| Privacy policy benchmark at `4b536e4` | 19/19; 0 false blocks, 0 unsafe passes; 11 ordinary / 8 unsafe | Scripted visual approvals test policy enforcement, not human/vision accuracy |
| Live synthetic privacy probes | Ordinary professional-contact PDF passed; medical/HR-sensitive file blocked; synthetic secret blocked on retry | N=3; first secret response failed schema validation; not blind, not a benchmark |
| Saved eight-source disagreement comparison | 3 → 1 material; 4 → 4 strict differences | Same frozen extraction pair, comparator change only |
| Fresh eight-source extraction under v9 | 8/8 primary and 8/8 independent rereads completed; both passes used distinct LIFT-5 / LIFT-50 rate-row entities | DEV known dossier; v9 correction verified for this rate-card; not broad extraction accuracy |
| Eight-source adjudication under v4 | Original scan pixels cited with source/render hashes; one material dispute resolved; 18 visual facts promoted via `MODEL` receipt; 168 total facts; 2 invoice lines; PDF QA passed | Known synthetic DEV case; visual semantics and PDF QA are probabilistic model judgments, not independent accuracy |
| Eight-source final PDF | SHA256 `bccb8d73719329768bdc73c86e98306159bea78ae392d1d447c239e6984e870e`; EUR 150 documentary difference after EUR 100 credit; LIFT-50 EUR 0 | `EVALUATION_ONLY_QA_PASSED`; zero HUMAN attestations and no delivery approval; one case cannot establish 99%/95% |
| Raw native-PDF-to-client-PDF run | One synthetic two-PDF case passed source, finding and actual-PDF QA | Evaluation-only; same development case family; no independent adjudication |
| Prior clean regression at `4b536e4` | **833 passed in 318.78 s; 0 failed, 0 skipped**; Ruff clean; configured mypy 16 files clean | Historical baseline before native review v2 |
| Current code regression at `ef6e849` | **833 passed in 347.26 s; 0 failed, 0 skipped**; Ruff and configured mypy (16 files) clean; CI 8/8 pytest jobs green | Local run began on clean HEAD; later documentation-only edits do not change tested code |
| Current code benchmarks at `ef6e849` | Rental 15/15 (3 TP, 0 FP, 0 FN, 12 TN), 10,000 lines in 2.571854 s; privacy 19/19, 0 false blocks, 0 unsafe passes | Scripted fixtures, not material report correctness |
| Current code checkpoint `1760abb` | **835 passed in 306.77 s; 0 failed/skipped** from a clean worktree; Ruff and configured mypy (16 files) clean; PR #5 CI 8/8 pytest jobs green | Report-author v4 repair has unit coverage, but no successful live v4 report-author repair yet |
| Current checkpoint benchmarks | Rental 15/15 (3 TP, 0 FP, 0 FN, 12 TN); privacy 19/19 (11 ordinary, 8 unsafe), 0 false blocks and 0 unsafe passes | Scripted synthetic fixtures; no blind report accuracy or real privacy authority |
| Eight-source v4 fresh replay (historical failure) | Eight primary and eight challenger reads; two material disagreements resolved, including pixel-bound scan adjudication; **STOP at FACT_REVIEW** | Native reviewer accepted an orphan rate-sheet date lacking required entity metadata; no PDF/final QA for that replay |
| Eight-source current-code fresh run | Eight primary + eight independent reads; 0 material disagreements; 150 native + 10 pixel-bound visual `MODEL` facts; two invoice lines; live report-author v4 repair; final PDF QA `PASS`; PDF SHA256 `07e8c9d31c2c2505c053ebe3761c1c83e8da0388139e2d34bb5364a55971ecb7` | `EVALUATION_ONLY_QA_PASSED`, EUR 150 LIFT-5 after EUR 100 credit and EUR 0 LIFT-50; no HUMAN or delivery approval; known DEV case and same-model QA, not independent accuracy |
| Post-fix committed-code regression | 838 pytest passed in 310.49 s, 0 failed; Ruff clean; configured mypy clean on 16 files; PR #5 CI 8/8 pytest jobs green on Python 3.11–3.14 | Scripted regression, not independent report accuracy |
| Post-fix scripted benchmarks | Rental 15/15 (3 TP, 0 FP, 0 FN, 12 TN); privacy 19/19 (11 ordinary, 8 unsafe; 0 false blocks, 0 unsafe passes) | Known fixtures and scripted visual reviews, not blind outcome measurement |
| Eight-source old-workspace replay | Reached 161 facts, 10 visual MODEL-reviewed, two invoice lines, then stopped on 17,066-byte remaining Evidence Plane context budget | Budget carried across revisions; it was not reset. Different run from the fresh v4 replay |
| Varied challenge corpus | 20 synthetic ADVERSARIAL cases generated with separated private truth | Prepared, not a blinded final-report result; author has seen generator |
| ADVERSARIAL source→report probes (nonblind) | 3/20 attempted: 2/3 evaluation PDFs passed model QA, both show the precommitted EUR 150 financial difference; 1/3 stopped at source adjudication because a CSV row did not establish issued-invoice authority | Delivered coverage 2/3 in this selected subset; 2/2 oracle financial amounts matched, **not** independently adjudicated report correctness; synthetic privacy exemption, 17 cases unrun; no HUMAN correction measured |
| Next five ADVERSARIAL outcomes on build `6213430` | 5/5 attempted from public-side preselection; 2 PDF drafts generated and both match the oracle material financial outcome (EUR 0 clean; EUR 550); 2 justified abstentions; 1 unjustified scan stop with an EUR 150 miss | 0/5 final QA-passed reports; 2 report QA stops for authoring/presentation defects; 4/5 correct end-to-end outcomes including justified stops/abstentions; 0 false positives, 0 amount errors, 0 provenance errors, 0 HUMAN escalations. Small synthetic tranche; not a blind population estimate |
| Founder final review minutes / factual corrections | Not measured | No actual operator rehearsal |
| Human report passages | Not measured in production | Model authored DEV synthesis; engineering changes do not establish correction-free service |
| Model costs/tokens | Not measured | CLI subscription usage not inferred as free |
| Blind coverage/recall/abstention/residual errors | Not measured | Frozen challenge not completed |

Ignored benchmark receipts: `scratch/final_validation_9e3a7e8/rental/`,
`scratch/final_validation_4b536e4/rental/`,
`scratch/final_validation_4b536e4/privacy/`,
`scratch/final_validation_4b536e4/challenge/`,
`scratch/final_validation_ef6e849/rental/`,
`scratch/final_validation_ef6e849/privacy/`,
`scratch/final_validation_report_v4/rental/`,
`scratch/final_validation_report_v4/privacy/`,
`scratch/final_validation_report_v4/rental_eight_v4_fresh_eval/`,
`scratch/current_code_eight_source/eight_fact_v3_fresh/`,
and the tracked pre-truth-sealed five-case cohort in
`docs/validation/adversarial_cohort_5_6213430/`.
`scratch/final_validation_9e3a7e8/privacy/`, `scratch/final_privacy_dfe9fdd/`,
`scratch/final_rental_dfe9fdd/`, and `scratch/model_privacy_dev_v2/results.json`,
plus the secret retry output in the development session record. Source-job events
record successful extraction attempts and wall time; failed-call time and total
monetary cost are not fully metered. Preserve that distinction in any aggregate.
