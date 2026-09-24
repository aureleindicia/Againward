# Final autonomous metrics — development checkpoint

No independently adjudicated final report sample has been completed.

**MEASURED: not yet measured / N=0 independently adjudicated final cases.**
**TARGET: ≥99% material correctness; ≥95% supported cases without human correction.**

| Measurement | Observed evidence | Limitation |
|---|---|---|
| Rental kernel benchmark at `9e3a7e8` | 15/15; 3 TP, 0 FP, 0 FN, 12 TN; 10,000 invoice lines in 4.360858 s | Small scripted fixtures; performance excludes document extraction/report I/O; not model/report accuracy |
| Privacy policy benchmark at `9e3a7e8` | 19/19; 0 false blocks, 0 unsafe passes; 11 ordinary / 8 unsafe | Scripted visual approvals test policy enforcement, not human/vision accuracy |
| Live synthetic privacy probes | Ordinary professional-contact PDF passed; medical/HR-sensitive file blocked; synthetic secret blocked on retry | N=3; first secret response failed schema validation; not blind, not a benchmark |
| Saved eight-source disagreement comparison | 3 → 1 material; 4 → 4 strict differences | Same frozen extraction pair, comparator change only |
| Fresh eight-source extraction under v9 | 8/8 primary and 8/8 independent rereads completed; both passes used distinct LIFT-5 / LIFT-50 rate-row entities | DEV known dossier; v9 correction verified for this rate-card; not broad extraction accuracy |
| Fresh eight-source adjudication under v3 | Correctly left the visual-only signed-return disagreement unresolved; no `UNSUPPORTED_PROMOTION` | Waits for visual attestation; no facts promoted and no report generated |
| Raw native-PDF-to-client-PDF run | One synthetic two-PDF case passed source, finding and actual-PDF QA | Evaluation-only; same development case family; no independent adjudication |
| Full local regression at `9e3a7e8` | **831 passed in 337.50 s; 0 failed, 0 skipped** | Clean worktree at tested HEAD |
| Founder final review minutes / factual corrections | Not measured | No actual operator rehearsal |
| Human report passages | Not measured in production | Model authored DEV synthesis; engineering changes do not establish correction-free service |
| Model costs/tokens | Not measured | CLI subscription usage not inferred as free |
| Blind coverage/recall/abstention/residual errors | Not measured | Frozen challenge not completed |

Ignored benchmark receipts: `scratch/final_validation_9e3a7e8/rental/`,
`scratch/final_validation_9e3a7e8/privacy/`, `scratch/final_privacy_dfe9fdd/`,
`scratch/final_rental_dfe9fdd/`, and `scratch/model_privacy_dev_v2/results.json`,
plus the secret retry output in the development session record. Source-job events
record successful extraction attempts and wall time; failed-call time and total
monetary cost are not fully metered. Preserve that distinction in any aggregate.
