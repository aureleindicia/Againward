# Final autonomous metrics — frozen-code development checkpoint

No independently adjudicated final report sample has been completed.

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
| Prior clean regression at `4b536e4` | **833 passed in 318.78 s; 0 failed, 0 skipped**; Ruff clean; configured mypy 16 files clean | New v2 review/evaluator metadata commit still needs its own full run |
| Varied challenge corpus | 20 synthetic ADVERSARIAL cases generated with separated private truth | Prepared, not a blinded final-report result; author has seen generator |
| ADVERSARIAL source→report probes (nonblind) | 3/20 attempted: 2/3 evaluation PDFs passed model QA, both show the precommitted EUR 150 financial difference; 1/3 stopped at source adjudication because a CSV row did not establish issued-invoice authority | Delivered coverage 2/3 in this selected subset; 2/2 oracle financial amounts matched, **not** independently adjudicated report correctness; 17 cases unrun; no HUMAN correction measured |
| Founder final review minutes / factual corrections | Not measured | No actual operator rehearsal |
| Human report passages | Not measured in production | Model authored DEV synthesis; engineering changes do not establish correction-free service |
| Model costs/tokens | Not measured | CLI subscription usage not inferred as free |
| Blind coverage/recall/abstention/residual errors | Not measured | Frozen challenge not completed |

Ignored benchmark receipts: `scratch/final_validation_9e3a7e8/rental/`,
`scratch/final_validation_4b536e4/rental/`,
`scratch/final_validation_4b536e4/privacy/`,
`scratch/final_validation_4b536e4/challenge/`,
`scratch/final_validation_9e3a7e8/privacy/`, `scratch/final_privacy_dfe9fdd/`,
`scratch/final_rental_dfe9fdd/`, and `scratch/model_privacy_dev_v2/results.json`,
plus the secret retry output in the development session record. Source-job events
record successful extraction attempts and wall time; failed-call time and total
monetary cost are not fully metered. Preserve that distinction in any aggregate.
