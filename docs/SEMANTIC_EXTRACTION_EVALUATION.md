# Semantic extraction evaluation — real participant, not yet a release result

Baseline at clean `70f187e`: DEV seed 7421 and ADVERSARIAL seed 19341 each had
zero semantic submissions, TP 0 / FP 0 / FN 6 / TN 14 and annotated-field
recall 0. The routing-only scorer correctly reports precision null. See
[first-client plan](FIRST_CLIENT_READINESS_PLAN.md) and
[document benchmark](REAL_WORLD_RENTAL_BENCHMARKS.md).

## Participant and authority boundary

`againward/documents/codex_provider.py` now implements an opt-in
`ExtractionProvider` participant. It receives only approved native source units
(and at most four rendered visual pages when present), not generator truth or
case-level financial answers. It invokes an ephemeral Codex CLI session in a
temporary read-only working directory; a closed JSON response is converted to
exact unit-hash/location/quote-span candidates and passed through the existing
deterministic proposal validator. A missing/ambiguous quote fails. An unexplained
normalization is flagged for review, never auto-approved. No model output becomes
a canonical fact, entity match, privacy decision or client claim by itself.

Current participant declaration: Codex CLI 0.155.1, `gpt-6-sol`, low reasoning
effort, prompt `againward-source-facts-v1`, extractor
`codex-cli-source-units-v1`, Rental guidance `rental-semantic-guidance-v1`.
`codex login status` reports ChatGPT subscription login on this device;
there is no API-key fallback in this adapter. [Official OpenAI authentication
documentation](https://learn.chatgpt.com/docs/auth) distinguishes ChatGPT
subscription access from separately billed API-key access. Actual client
processing still requires owner verification of provider policy/permission and
cost limits; no real client files were submitted in this experiment.

One genuine DEV public synthetic invoice source (case
`0214b4ad0071f373`, `billing.pdf`) produced **14 validated candidates**,
status `PARTIAL`, with zero approved facts. The source was inventoried and read
from ordinary PDF bytes; the model had no private truth input. Its response
included source-bound invoice ID, asset/serial, period, quantity, currency and
net amount, alongside explicit uncertainty. This is a single feasibility probe,
not a scored accuracy result. The immutable extraction is in ignored
`scratch/first_client_baseline_doc_dev_run/0214b4ad0071f373/extractions/`.

Early operational failures were observable: `gpt-5.3-codex` was rejected for
this ChatGPT login, then the first `gpt-6-sol` responses failed closed on an
unrecognized value type and unexplained normalization. The schema was narrowed
and unexplained normalization now requires review. Do not suppress these
failures or count the successful third call as independent benchmark accuracy.

## Required next evaluation

Run a participant-only path on all DEV and ADVERSARIAL public files, with
source-bound candidate scoring against the private decisive-field annotations
*after* observations freeze. Record failures, latency, model attempts/usage,
review burden, critical fact errors and downstream abstentions separately.
No scripted fact-review decisions count as semantic quality. Freeze code,
prompt and policy before a truly independent HOLDOUT; because the generating
repository is accessible to the implementation agent, a separate restricted
context or external reviewer is necessary to claim blindness. Until then,
HOLDOUT remains **OPEN** and Gate A cannot pass.
