# Final autonomous metrics — development checkpoint

No independently adjudicated final report sample has been completed.

**MEASURED: not yet measured / N=0 independently adjudicated final cases.**
**TARGET: ≥99% material correctness; ≥95% supported cases without human correction.**

| Measurement | Observed evidence | Limitation |
|---|---|---|
| Rental kernel benchmark | 15/15; 3 TP, 0 FP, 0 FN, 12 TN | Small scripted fixtures; not model/report accuracy |
| Privacy policy benchmark | 19/19; 0 false blocks, 0 unsafe passes | 11 ordinary / 8 unsafe; scripted visual attestations |
| Live synthetic privacy probes | Ordinary professional-contact PDF passed; medical/HR-sensitive file blocked; synthetic secret blocked on retry | N=3; first secret response failed schema validation; not blind, not a benchmark |
| Saved eight-source disagreement comparison | 3 → 1 material; 4 → 4 strict differences | Same frozen extraction pair, comparator change only |
| Fresh eight-source extraction under v9 | 8/8 primary and 8/8 independent rereads completed; both passes used distinct LIFT-5 / LIFT-50 rate-row entities | DEV known dossier; v9 correction verified for this rate-card; not broad extraction accuracy |
| Fresh eight-source adjudication under v3 | Correctly left the visual-only signed-return disagreement unresolved; no `UNSUPPORTED_PROMOTION` | Waits for visual attestation; no facts promoted and no report generated |
| Raw native-PDF-to-client-PDF run | One synthetic two-PDF case passed source, finding and actual-PDF QA | Evaluation-only; same development case family; no independent adjudication |
| Full local regression before `d047c4b` | 829 passed, 2 HOLDOUT integrity tests detected the then-uncommitted engine changes; both targeted tests passed against the resulting committed engine | Final v3 commit regression is being run; see PR CI before treating as final |
| Live synthetic privacy probes | Ordinary professional contact allowed; medical/HR file blocked; secret blocked after a schema-invalid first response and retry | N=3; not blinded; schema retry reliability remains a known issue |
| Founder final review minutes / factual corrections | Not measured | No actual operator rehearsal |
| Human report passages | Not measured in production | Model authored DEV synthesis; engineering changes do not establish correction-free service |
| Model costs/tokens | Not measured | CLI subscription usage not inferred as free |
| Blind coverage/recall/abstention/residual errors | Not measured | Frozen challenge not completed |

Ignored benchmark receipts: `scratch/final_privacy_dfe9fdd/`,
`scratch/final_rental_dfe9fdd/`, `scratch/final_easy_medium/rental/`,
`scratch/final_easy_medium/privacy/`, `scratch/model_privacy_dev_v2/results.json`, and
the secret retry output in the development session record. Source-job events
record successful extraction attempts and wall time; failed-call time and total
monetary cost are not fully metered. Preserve that distinction in any aggregate.
