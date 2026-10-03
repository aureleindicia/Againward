# V2 Investigator response contract correction — 2026-10-03

## Evidence and limits

The frozen DEV campaign executed `1c971b7a0c6eb92e1d3695aab8e2d4a23b9087bc`.
Its artifacts are preserved outside Git under
`../againward-rental-v2-campaign-20261003/`. Neither A nor B was rerun.
Both terminal investigation receipts record `action: null`,
`EXTRACTION_SCHEMA_INVALID`, and `PROVIDER_FAILURE`. The old `_ask` used
`--ephemeral`, a temporary output file, and captured stdout/stderr without
persisting them. No terminal raw answer remains in the receipts, temporary
folders or local session history. The exact terminal malformed field cannot
honestly be reconstructed. This correction does not claim to establish it.

A's earlier rejected proposal *is* retained: `OBSERVATION_DISPOSITION` with
`value: EXCLUDE` and `evidence_ids: []`. Calling the original frozen `_shape`
on this proposal reproduces `Unknown semantic decision`; changing only the
value to an allowed enum reveals `Bounded unique evidence IDs required`.
These are two independent defects, not financial ambiguity. The model prompt
listed claim shapes but omitted their allowed values and evidence constraints.
The supplied model output schema constrained only a `payload` string. Python
then had to parse another unconstrained JSON object. The provider exception
handler discarded even the available diagnostic. B's separate reader rejections
are outside this correction and remain open.

## Generic change

`case_investigator_contract.py` owns one closed direct structured-output schema
and validates the same field definitions in Python. Every action has its exact
field set. Claim values are shared with the durable claim validator through
`CLAIM_VALUES`; no fixture identifiers, financial oracle, or enum alias is used.
The output is `{issue_id, action}`, not JSON serialized inside a string.
Scripted providers pass the same boundary. Shape admissibility does not grant
source eligibility, structure review, commercial authority or readiness.

Unknown/extra fields, unsupported enums, missing evidence, duplicate IDs,
wrong focus, multiple actions, invalid coordinate types, nonfinite values and
oversized responses remain rejected. In particular `EXCLUDE` is not mapped to
`IRRELEVANT` or another decision. Existing source/provenance gates, deterministic
arithmetic, review requirements, budgets, retry policy and stopping rules remain.
Existing durable graph/claim/read receipts keep their original replay versions.

Errors now preserve safe stage, schema version, expected field path, rule and
actual type. JSON parsing failures also retain exact output byte hash, schema
hash, byte count and (for syntax errors) parser coordinates. Duplicate members,
truncation, concatenated answers and nonfinite JSON are rejected. The established
fence/trailing-comma normalization remains limited to unambiguous fresh notation.

With explicit `evaluation_only=True`, native Investigator calls retain exact raw
model bytes, output schema, command and process streams in private local scratch
before parsing. Files use mode 0600, directories 0700; linked scratch is refused.
The delivery entrypoint propagates its existing evaluation flag. Ordinary calls
do not retain raw provider streams. Receipt metadata preserves diagnostics even
when the invocation fails. There is no automatic retry or A/B rerun.

## Verification

72 new contract tests cover all action forms and claim enums; positive and
negative schema boundaries; real `_ask` with only the CLI process substituted;
exact-byte private retention; malformed-terminal diagnostic persistence; bounded
feedback after rejection; and actual Python readiness/calculation. The incomplete
generic graph blocks, while the complete generic graph calculates its independent
5.00 EUR difference. Existing full graph-to-PDF tests protect later phases.

A separate live protocol-only probe used `gpt-6-luna`, medium effort, Codex CLI,
exactly one call, no sources/case/oracle and no Investigator loop. It accepted
the direct schema and returned `MARK_UNRESOLVED` / `Original evidence is absent.`
in 7.059 seconds. This measures native schema compatibility, not investigation
quality or A/B end-to-end success.

Local logs and raw probe receipts are outside Git at
`../againward-rental-v2-contract-validation-20261003/`; `receipt_audit.json`
records the read-only historical comparison, and `live_protocol_probe.json`
records the isolated live result. Full validation results are appended after
completion. No remote CI or deployment is implied.

Validation before the requested quick commit: 72 new contract tests pass;
105 existing Investigator/reader/model-protocol tests pass; the separately
collected delivery/contract selection passes 94 tests (including actual PDF
production). Ruff configured and explicit V2/autonomous-review checks pass;
configured mypy (18 files) and explicit V2 mypy (15 files) pass. Rental is
15/15 and privacy is 19/19. The unchanged integrity guards pass 2/2 on the
frozen base. The full suite is already running and is not restarted. Its initial
uncommitted-tree integrity refusal will be rechecked on the committed correction.

## Completed full validation

The single full-suite launch completed with **1411 passed, 1 failed in 588.89s**.
The sole failure is `test_holdout_engine_mutation_invalidates_the_run`: its
setup selected the frozen base `1c971b7` while the correction was still
uncommitted, and correctly refused the modified engine before the test mutation.
This is a validation-context integrity refusal, not an accepted unsafe response
or a functional regression. No test or gate was skipped, mocked or weakened.

After code commit `4f2bfb72aab068133b3026351beb252ca435ee44`, both unchanged
integrity guards were rerun on the clean correction: **2 passed in 6.90s**.
They also passed on the unchanged frozen base: **2 passed in 4.42s**. The full
suite was not rerun after the user's request to accelerate the commit. Therefore
this record does not claim a second, completely green clean-start full-suite run.
All 1412 tests have passing coverage across the full pass and that focused
clean-engine recheck. No code changed after the code commit; only this evidence
record is updated.

Ruff, both mypy checks, Rental **15/15**, privacy **19/19** (0 false blocks,
0 unsafe passes) and the one-call live protocol probe pass. The 74 historical
campaign artifacts were hashed and verified unchanged. The campaign worktree
remains clean at the frozen SHA; the original main worktree's existing user
changes were preserved. No A/B run, financial oracle comparison, HOLDOUT quality
campaign, remote push, PR or deployment was performed in this correction.
