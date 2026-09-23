# Semantic extraction evaluation — real model, incomplete release evidence

## Current checkpoint (2026-09-23)

The current Rental guidance is v7. On the published, agent-authored
[eight-source DEV dossier](../benchmarking/first_client_dossier.py), a real
`gpt-6-sol` primary run from ordinary PDF, scanned PDF, EML and XLSX bytes
returned **8/8 validated source proposals, 162 candidate facts and 6/6
structurally complete material entities**. This counts field presence and
enum shape, not approved facts, correct links, financial findings or report
accuracy. The local primary source batch is
`batch-919a3f56396ed854a77522d4231e82ad1a601436b5669b43bc5dd300de57919a`
under ignored `scratch/first_client_e2e_dossier/runtime_v7/documents/`.
The generator produced identical eight source hashes in two separate local
runs, but its private expected values are known to the implementation agent;
this is not a blind HOLDOUT.

The new `documents independent-qa` command made eight separate original-source
model calls without passing primary candidates to the challenger. Its first
attempt failed closed on an invalid/nonunique quote; a bounded one-retry
validator-preserving change then completed eight challenger proposals (all
eight calls succeeded on the relaunch). An entity-level comparison found
strict differences on **6/8 sources**, but **0/8 disagreements in the
declared ledger-material fields**. The six advisory differences are chiefly
value-type labels, an omitted supporting agreement reference, alternate
category/item labeling on the return, an invoice date, and an optional invoice
billing unit. The challenger is the same model family and can share omissions;
agreement is diagnostic, not an independently adjudicated correctness rate.
The replayable comparison receipt is ignored local
`scratch/first_client_e2e_dossier/runtime_v7/documents/independent_qa/2c5f13833f0f2fc770d196a3a8cf9928d81c113c5ff2d1300f339965ce6fbda6.json`.
No fact, scan, link, finding or report has been approved by a real operator.
Processing time/cost and human corrections are not yet end-to-end measured.

Historical v1 and v3 results below are retained for before/after context;
they are not directly comparable as a single frozen blind evaluation.

The prior clean v3 participant benchmark, before v4–v7 Rental guidance,
processed 20 DEV cases / 51 documents and 20 ADVERSARIAL cases / 51 documents.
Both returned 60/60 exact matches on the narrow agreement/asset/original-rate
annotations. DEV had 23/43 structurally complete material entities and seven
schema-invalid billing PDFs; ADV had 23/44 complete and six schema-invalid
billing PDFs. The frozen observation SHA-256 values are respectively
`0b9b3192dd6766bab1348930ac049e75a2f2832a09bf4ffe175ee1b641377ff4`
and `2020f6906cd30525f5cbb130dd161b6df098f99ea7757b2e8202973159878893`.
Finding precision/recall are **null**, because neither run made reviewed
financial findings. The v7 eight-source result is a targeted remediation
probe, not a substitute for a fresh varied DEV/ADV or blind holdout score.

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

The frozen initial DEV/ADVERSARIAL participant used Codex CLI 0.155.1, `gpt-6-sol`,
low reasoning effort, prompt `againward-source-facts-v1`, extractor
`codex-cli-source-units-v1`, and Rental guidance
`rental-semantic-guidance-v1`. Later remediation uses prompt v3 and
Rental guidance v7; its guidance hash is part of the replayed prompt version.
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

The participant-only runner and separate private scorer are now available:

```sh
python run_semantic_benchmark.py run scratch/first_client_baseline_doc_dev/public \
  scratch/semantic-dev-run --split DEV --model gpt-6-sol
python run_semantic_benchmark.py score scratch/first_client_baseline_doc_dev \
  scratch/semantic-dev-run
```

Run all DEV and ADVERSARIAL public files, then score source-bound candidates
against private decisive-field annotations *after* observations freeze. The
runner imports no generator/scorer truth and records zero human decisions or
client-facing financial claims. The scorer measures only annotated fields;
financial precision/recall remain null until genuine review and ledgers run.
Record failures, latency, model attempts/usage, review burden, critical fact
errors and downstream abstentions separately.
No scripted fact-review decisions count as semantic quality. Freeze code,
prompt and policy before a truly independent HOLDOUT; because the generating
repository is accessible to the implementation agent, a separate restricted
context or external reviewer is necessary to claim blindness. Until then,
HOLDOUT remains **OPEN** and Gate A cannot pass.

## Frozen real DEV run, observed 2026-09-23

The actual `gpt-6-sol` participant completed all 20 DEV case folders / 51
ordinary source documents on frozen clean HEAD
`53f9fd80ddaa4f7d22491c449e716e6bf09e5824`, split seed 7421. Its
observation SHA-256 is
`ce59c6ee304fcb7ba6a3f43dce4add13a07683f247e99fcd2a297f7d4f60b4d6`.
After the observation file was frozen, the private scorer found 60/60 exact
annotated fields and 1.0 precision **within those annotations only**. The
annotations are just agreement ID, asset ID and original rate on the main
commercial document (three per case). They do **not** score invoice net amount,
dates, return trigger, credit allocation, governing clause, entity links or
financial outcome. Seven of 51 document submissions abstained due to
`EXTRACTION_SCHEMA_INVALID`; 33 had status `NEEDS_REVIEW` and 11 `PARTIAL`.
There were 695 candidate facts, 365 carrying at least one ambiguity flag.
Model wall time summed to 1,910.65 seconds for the 51 documents (median 34.98
seconds per document, 90th observed rank 54.8 seconds); this excludes human
review, privacy intake and end-to-end report work. Token usage and monetary
cost were not exposed by the participant receipt and are **unmeasured**.

An additional post-run structural audit, which does **not** use private truth
or approve any fact, found 43 material entity proposals and **0/43** meeting
the conservative pilot field/enum checklist. Missing `charge_key` and
`charge_type` each affected 40 entities; 25 billing-unit values and 23 stop
trigger values used noncanonical enums. This is why 60/60 is not even close to
a working source-to-ledger success claim. The observed straightforward invoice
had correct source-bound net amount but omitted both charge fields; the
contract used a free-text billing unit and `CONTRACTUAL_END` instead of the
supported `DAY`/`CONTRACT_END`. Downstream would STOP, not silently guess.

Raw immutable artifacts are in ignored `scratch/semantic_dev_run/` and
`scratch/semantic_dev_corpus/` of the detached validation worktree. Reproduce
the scorer with `python run_semantic_benchmark.py score CORPUS RUN` once per
fresh observation; the preflight with `python run_semantic_benchmark.py audit
RUN`. Do not overwrite the scored run. The later guidance/prompt update to v3
is a **separate remediation**, not part of this frozen result. No HOLDOUT exists.

The matching frozen ADVERSARIAL run (seed 19341, same clean HEAD and v1
participant) completed 20 case folders / 51 source documents. It found
**33/60** exact annotated commercial fields (0.55 recall within the same
three-field annotation scope) and 28 document abstentions. Of those, 22 were
`MODEL_UNAVAILABLE`, five `EXTRACTION_SCHEMA_INVALID` and one
`SOURCE_LOCATION_INVALID`. All 22 unavailable calls ended in 3.0–3.9 seconds,
while successful calls had a 45.2-second median; this points to an invocation
or service availability failure, but the old participant did not retain a safe
diagnostic category, so its exact cause is unknown. A subsequent minimal
Codex call succeeded; do not reinterpret the frozen run as if it had succeeded.
The other 23 documents produced 365 candidates, 183 flagged. Structural
preflight found 22 material entities and **0/22** complete for the narrow
pilot. Model time summed to 1,315.50 seconds across the run. Financial,
entity-link and human-review metrics remain null/unmeasured. Raw observation,
score and audit artifacts are in ignored `scratch/semantic_adv_run/` in the
detached validation worktree. ADV is a challenge of the old frozen v1 prompt,
not evidence that v3 generalizes. A fresh v3 DEV/ADV comparison and an
independent blind HOLDOUT are still required.

## Targeted remediation probe, not a second benchmark

The first DEV case's exact same commercial and invoice bytes were submitted
again after updating Rental guidance and the base prompt to v3. The original
v1 proposals lacked `charge_key`/`charge_type` on both entities and used
unsupported free-text billing/stop enums on the agreement: **0/2** material
entities met structural pilot preflight. V3 produced 21 agreement and 16
invoice candidates with **2/2** structurally complete entities, canonical
`DAY`/`CONTRACT_END`/`RENTAL` values, validated source spans and no
extraction-level limitations. It still approved **zero** facts; 37 candidate
decisions and cross-document links remain to be reviewed. This is one
repeated synthetic case with prompt tuning, not a generalization score.

The intermediate v2 run exposed a separate blocker: the model listed an
ordinary invoice's lack of the contract's stop clause as a document
limitation, which made the adapter STOP despite correct invoice facts. V3
instructs the model to reserve extraction-level limitations for unreadable or
ambiguous source-local content. The deterministic adapter still refuses any
genuine unresolved limitation. Extracted prompt versions now include a hash of
the Rental guidance; replay under changed guidance requires fresh extraction
and fact review. One earlier attempt failed on an invalid model identifier;
the response contract now specifies the accepted grammar and reports a
candidate index without printing source content. All this must be challenged
on independent varied documents before launch.

The same two ordinary PDF bytes were also passed through a source-checked
**technical** review and the real adapter/reconciliation path. Thirty-seven
v3 model candidates became 37 facts after an agent checked the original PDF
text and exact candidate values; the invoice linked to the agreement through
matching reviewed identifiers. The Decimal ledger computed EUR 1,400.00
expected against EUR 1,550.00 invoiced, i.e. an EUR 150.00 potential
discrepancy. This is a two-document integration probe, not independent model
accuracy, human approval, a delivered report or an eight-document rehearsal.
The source hashes are `03f49eb83589849c372d8309b0e46c884c6d5a859998c870e9c2ffe081df3cea`
and `b14e53de6177a014a3679d0994dbc44c7cadf70743f55e02be85378c8d9bed6d`.
The ignored local probe is `scratch/model_pair_technical_probe.py`; its
explicit expected-value map is *not* a benchmark participant or human review.

The old ADV run's 22 `MODEL_UNAVAILABLE` outcomes remain of unknown cause.
Current provider invocations now emit only fixed categories for authentication,
rate limits, transport failures, timeout, missing response and generic
unavailability, without persisting raw CLI stderr that might contain client
content. This classification has unit tests, but no claim is made that it
retrospectively explains the frozen ADV failures.
