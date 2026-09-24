# First supervised Rental pilot — release audit (in progress)

Decision: **NOT READY — SPECIFIC CRITICAL BLOCKERS**. The three gates in the
[authoritative readiness plan](FIRST_CLIENT_READINESS_PLAN.md) are independent.
Passing tests is not a substitute for a client-style source-to-report run.
This is a checkpoint, not the final-SHA audit; update it after the next frozen
evaluation and operator rehearsal.

| Gate | Evidence now | Missing to pass |
|---|---|---|
| A — software/evidence | Real `gpt-6-sol` DEV/ADV source-unit submissions; strict exact quote validation; v8 eight-source technical source→ledger probe; independent QA fail-closed on one material disagreement; hash-bound package handoff regression; 15-case Rental and 19-case privacy benchmarks | Cross-document QA adjudication, fresh varied v8 DEV/ADV, independent blind HOLDOUT or declared substitute, complete eight-document privacy→report run with genuine scan attestation, positive/zero/abstain findings, failure injection, measured model/labor/cost |
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

The current code SHA `c59d8f1` passed **787 local tests in 310.59 s**;
all eight Python 3.11–3.14 CI jobs passed. Ruff and the configured CI mypy
scope (14 files) passed. A deliberately broader `mypy againward benchmarking`
check reported 161 existing typing errors in 24 files; that debt is not
covered by the CI type gate. The Rental benchmark passed 15/15 (fixture
TP 3 / FP 0 / FN 0 / TN 12; 10k-line ledger 3.017 s excluding documents).
The privacy benchmark passed 19/19 (11 ordinary, eight unsafe, zero false
blocks and zero unsafe passes; scripted visual fixtures). These are not
end-to-end model-driven report accuracy rates. The eight-source technical
probe produced exact EUR 150.00 / EUR 0.00 groups,
but used agent-reviewed facts and a scripted scan-attestation fixture, with
no human delivery review or client-style report. Do not describe it as an
approved client claim.

The independent v8 reread exposed one material off-hire-email classification
disagreement and set `RECONCILIATION_REQUIRED`. The accepted agreement says
the request alone does not stop billing. A new original-source adjudication
probe selected the supporting-document interpretation with exact email and
agreement citations, reducing unresolved material source differences from
one to zero **for fact review only**; it approved no facts or report. General
cross-document adjudication and blind final-outcome validation remain unproven.
The 99% report correctness
and 95% no-correction objectives are unverified targets, not achieved metrics.

Subsequent v8 DEV work exercised autonomous native fact review: 148/149 native
facts were accepted on the first pass and the one metadata-status error was
repaired by one new source-bound model call. A pixel-inspecting model pass
proposed 10/10 return-page facts after one recorded repair, but all await a
real visual attestation. A scripted test-only visual/downstream review reached
the actual five-page PDF with EUR 150.00 and EUR 0.00 groups. That PDF failed
the product usability objective (debug hashes/generic fixture prose/founder
claim-check instructions). A subsequent model-driven finding reviewer and
independent original-source challenger corrected an overconfident claim and
validated an L2 EUR 150.00 difference without a recoverable amount. A model
then wrote the client synthesis; PDF/original-source QA exposed internal
labels and incomplete credit explanation, triggering a renderer correction.
The resulting five-page PDF passed a later model QA (zero reported unsupported
claims or omissions) and is watermarked synthetic evaluation. This is one
known DEV dossier, using a **scripted non-human scan attestation**. It does not
validate report correctness rates or a real client approval path.

The current reviewed-package-to-PDF job is resumable, but raw privacy intake,
fresh document processing/link review, authentic scan attestation and a blind
challenge remain outside that job. A genuine complete raw authorized dossier
to report run is still a **specific technical blocker**. Founder correction
burden, end-to-end time, token cost and quality targets remain unmeasured.

Owner actions are listed in
[operations checklist](FIRST_CLIENT_OPERATIONS_CHECKLIST.md). Neither a
legal signoff nor model-provider permission for real client data has been
confirmed. The stacked [PR #5](https://github.com/aureleindicia/Againward/pull/5)
must remain draft/unmerged until the code gate is evidenced; merge order is
PR #2 → #3 → #4 → #5 unless the upstream stack changes.
