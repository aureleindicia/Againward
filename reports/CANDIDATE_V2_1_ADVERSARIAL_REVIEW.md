# Candidate V2.1 — adversarial review

## Epistemic risks checked

- **Overclaiming:** cause decisions are rejected by the consistency guard when the analyst
  has not declared an abnormal phenomenon.
- **Underclaiming:** sparse evidence is not treated as weak solely because it is sparse;
  `INSUFFICIENT_INFORMATION` now requires an analyst-declared decision blocker.
- **Legitimate demand mistaken for defect:** `NORMAL_OPERATION` requires a declared
  legitimate explanation and no confirmed abnormality.
- **False oracle disclosure:** auto-match thresholds are unchanged. The new primary-intent
  route is blind-review-only and competing candidates remain non-revealed.
- **Safety regression:** the physical differential, falsifier, command/feedback,
  service-demand-before-efficiency, intervention preconditions, risks and stop-condition
  contracts are unchanged and covered by the full suite.

## Agenticity audit

1. Codex still decides what to investigate: **yes**.
2. Codex still generates/ranks physical hypotheses: **yes**.
3. Codex still chooses information requests and sufficiency: **yes**.
4. Codex still chooses intervention and abstention: **yes**.
5. Python still returns validation/measurements/comparisons rather than diagnoses: **yes**.
6. If Codex were removed, could deterministic code reproduce essentially the same
   investigation? **NO.** The new validator only rejects logical contradictions in
   analyst-declared fields; it cannot identify an anomaly, select a cause, rank a test or
   recommend an action.

## Contamination audit

No V2.1 change contains a DEV case ID, case timestamp, ground-truth term, prior outcome,
or new domain-specific diagnosis rule. No DEV case was rerun. This patch is suitable for a
fresh independent HOLDOUT, not evidence of improved DEV performance.

## Residual risk

A blind reviewer can still misjudge semantic intent. Its decision is logged and
reproducible, but it remains an independent human/model review boundary rather than a
source of physical truth.
