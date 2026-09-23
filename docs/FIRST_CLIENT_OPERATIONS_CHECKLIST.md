# First Rental client: owner-controlled readiness checklist

Status: **NOT READY; no actual client's documents may be processed under this engineering run.**
The code supplies gates and templates, not permission, legal advice, an invoiceable
business or authenticated human review. The owner must record each decision for
the particular client and retain the signed/source version outside Git.

## Owner decisions before accepting a real folder

- [ ] Confirm the legal/business status, quote/order, invoicing and payment process
  for the actual jurisdiction and client. Do not infer this from a passing test.
- [ ] Approve the exact narrow offer and exclusions in
  [the release plan](FIRST_CLIENT_READINESS_PLAN.md): one supplier, EUR/net,
  explicit daily conventions and evidence-based discrepancies only. State that
  neither recovery nor legal enforceability is guaranteed.
- [ ] Obtain client-specific permission for receiving, analyzing and retaining
  the relevant contract, invoice, return, credit and supplier correspondence.
  Confirm confidentiality, purpose, access, permitted derived outputs and what
  to do with irrelevant personal data.
- [ ] Review the actual Codex/OpenAI login, model, processing conditions,
  transfer and retention terms with the client; authorize its use on their
  documents. A Termux workflow is not an on-device model. Confirm who may see
  raw, sanitized, model-submitted and delivered content.
- [ ] Set a per-case model/time budget and a STOP if exceeded. ChatGPT sign-in
  here is not proof of zero marginal cost or a guarantee of future availability.
- [ ] Test a secure channel for client intake and PDF/evidence delivery; do not
  email a raw workspace, sync it by accident, or put it in Git/CI. Control device
  lock, backup scope and loss/incident contacts.
- [ ] Set and review the case retention/purge date and authorized retained paths.
  Confirm backup deletion behavior, interrupted-transaction recovery and a
  documented incident/escalation contact before real data arrives.
- [ ] Name the person who will inspect every scan/hybrid page, review critical
  model facts and entity links, adversarially review every positive financial
  claim and approve the exact final PDF/evidence hashes. The local `actor_id`
  is a claim, not identity authentication.
- [ ] Rehearse the independent synthetic eight-document folder on the intended
  device, including a scan, a credit and an ambiguity; record real human minutes
  and STOP decisions. Scripted tests do not satisfy this item.
- [ ] Explicitly authorize the first real client pilot **after** Gates A/B pass.

## Case-level STOP and feedback

At intake, ask for the accepted agreement/rate sheet, both invoice versions,
line identifiers and net currency, dated return/collection or off-hire evidence,
issued credit allocation and relevant amendments. Missing source, uncertain
identity, gross-only totals, incompatible currency or unsupported billing rule
means `REVIEW_REQUIRED` or `UNSUPPORTED`; request a specific document or exclude
the line, never fill it by intuition. Limit requests to the highest-value
unresolved question(s), not an open-ended fishing list.

An unsupported positive claim, changed source/hash, partial visual inspection,
high-risk personal content, secret, broken PDF, unknown allocation, exhausted
evidence budget or failed delivery gate means STOP. Explain the exact missing
source/decision to the client if authorized; do not patch JSON just to continue.
If no discrepancy is supported, say so expressly and give only relevant
verification options. Record later client corrections, false positives, misses
and outcomes in a minimized case-specific log, without copying raw client data
into examples, benchmarks, prompts for other clients or R&D.

## Software checks versus owner attestations

Software can verify hashes, provenance, candidate syntax, arithmetic,
privacy-policy decisions, review completeness and delivery artifact integrity.
It cannot verify legal permissions, actual human attention, provider terms,
secure transfer or recoverability. These require owner evidence before any
`READY FOR LIMITED HUMAN-SUPERVISED FIRST CLIENT` declaration.
