# First supervised Rental pilot — release audit (in progress)

Decision: **NOT READY — SPECIFIC CRITICAL BLOCKERS**. The three gates in the
[authoritative readiness plan](FIRST_CLIENT_READINESS_PLAN.md) are independent.
Passing tests is not a substitute for a client-style source-to-report run.
This is a checkpoint, not the final-SHA audit; update it after the next frozen
evaluation and operator rehearsal.

| Gate | Evidence now | Missing to pass |
|---|---|---|
| A — software/evidence | Real `gpt-6-sol` DEV/ADV source-unit submissions; strict exact quote validation; v8 eight-source technical source→ledger probe; hash-bound package handoff regression; prior 15-case Rental and 19-case privacy benchmarks | Fresh varied v8 DEV/ADV, independent blind HOLDOUT or declared substitute, complete eight-document privacy→report run with genuine scan attestation, positive/zero/abstain findings, failure injection, measured model/labor/cost, final full tests/benchmarks/CI |
| B — real operator | Visual packet and fact/link worksheets exist; local SOP drafted | Named person actually inspects scan and all financial claims, rehearses intake/delivery and approves exact PDF/evidence hashes on intended device |
| C — business/permission | Owner checklist and narrow offer drafted | Owner confirms business/invoicing status, client-specific scope/permissions, suitable terms, provider-processing conditions, transfer/retention, and explicit first-client authorization |

The frozen v1 DEV model run extracted 60/60 **narrowly annotated** agreement,
asset and rate fields, but 0/43 material entities passed the full pilot field
preflight. ADV found 33/60 annotated fields, had 28/51 document abstentions
(22 model unavailable) and 0/22 structurally complete material entities. A
single tuned v3 two-PDF case improved from 0/2 to 2/2 structurally complete.
The eight-source DEV probe moved from 4/6 under corrected v7 preflight to
6/6 under v8, but the dossier and private answer were authored by the agent;
this is not a blind benchmark score. Financial precision/recall, unsafe positive
count and provenance coverage for release-blocking model-driven cases remain
**unmeasured**, not zero. There is no blind HOLDOUT result. See
[semantic evaluation](SEMANTIC_EXTRACTION_EVALUATION.md) for denominators and
raw-artifact locations.

The latest fully observed local suite at `28903e3` was **786 passed in
327.62 s**; Python 3.11–3.14 CI passed at that SHA. The current v8 guidance
and stricter preflight still require final-SHA regression and CI. The
eight-source technical probe produced exact EUR 150.00 / EUR 0.00 groups,
but used agent-reviewed facts and a scripted scan-attestation fixture, with
no human delivery review or client-style report. Do not describe it as an
approved client claim.

Owner actions are listed in
[operations checklist](FIRST_CLIENT_OPERATIONS_CHECKLIST.md). Neither a
legal signoff nor model-provider permission for real client data has been
confirmed. The stacked [PR #5](https://github.com/aureleindicia/Againward/pull/5)
must remain draft/unmerged until the code gate is evidenced; merge order is
PR #2 → #3 → #4 → #5 unless the upstream stack changes.
