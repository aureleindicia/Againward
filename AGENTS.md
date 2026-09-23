# AGAINWARD — permanent agent instructions

Read [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md) first. This repository is an
existing local-first investigation system, not a greenfield project. The active
commercial focus is Rental B2B document intelligence; Energy remains supported.
Work in small, evidence-backed changes. Termux/Android CPU and memory are real
constraints. Do not add cloud, SaaS, telemetry or a model API by default.

## Non-negotiable boundaries

- Codex investigates: it reads evidence, forms and falsifies hypotheses, weighs
  alternative explanations, makes explicit review decisions and writes the
  human-facing synthesis. Python parses, validates, calculates, persists and
  reproduces numbers. Neither should impersonate the other.
- A real client's `incoming/` is for Codex's first substantive semantic review.
  Before that, Python may create a workspace and copy bytes without parsing.
  After review, the privacy post-check must issue a current
  `privacy_manifest.json` with `approved_for_analysis=true` before business
  parsing, source inventory or investigation. Never bypass this for PDFs.
- Ordinary professional names, contact channels and signatures can be valid
  Rental evidence under the Rental policy. Business confidentiality is distinct
  from privacy risk: preserve commercial terms, prices, dates, assets and
  relationships needed to analyse a case. Minimize downstream contact fields.
  Secrets, medical/HR-sensitive content, unnecessary identity documents,
  unreadable sources and uninspected visual components remain hard stops.
- A visual review must cover each required component and bind exact source hash,
  inspection version and reviewer decision. JSON `HUMAN` is a claimed role, not
  identity authentication. Do not claim machine vision, OCR accuracy or real
  human approval from synthetic fixtures.
- Bind every source, derivative, extraction, evidence item and review to exact
  hashes/versions. Source changes and supplemental batches invalidate dependent
  review. Conflicts, missing provenance, unsupported semantics or ambiguous
  entity links must abstain/STOP, not become financial claims.
- Do not add monetary claims by LLM arithmetic or double-count a discrepancy.
  Candidate overcharge is not recoverable savings. Preserve human approval and
  contract/retention gates before delivery.
- Do not send client data to Git, benchmarks, telemetry or another client.
  Treat Codex/OpenAI processing according to its actual configuration; never
  promise that Codex itself is offline. Keep workspaces and sensitive scratch
  ignored. No destructive cleanup of client material without explicit scope.

## Navigation and verification

- Active architecture, branches, commands and blockers:
  [docs/CURRENT_STATE.md](docs/CURRENT_STATE.md).
- Indexed active and historical evidence: [docs/README.md](docs/README.md).
- Domain-neutral authorities live in `againward/core`, `againward/documents`
  and `againward/evidence`; domain semantics live in `againward/domains`.
  `energy_mvp` and many root scripts are compatibility surfaces, not new owners.
- For code changes, run focused tests, then `python -m pytest -q`, `ruff check .`
  and `mypy` where configured. Run relevant Rental, privacy, document and Energy
  benchmarks when touching their contracts. Measure before/after for architecture
  claims and record false blocks *and* unsafe passes for privacy changes.
- Inspect `git status`, branch/PR stack and existing user edits before changes.
  Use a dedicated branch/worktree and coherent incremental commits. Do not
  rewrite history or merge automatically. Keep CI green across supported Python
  versions and hand off exact evidence plus remaining limits.

The previous 2,069-line Energy-first instruction file remains recoverable from
Git history at `94d9d2a:AGENTS.md`. Its historical analysis methods remain
valuable; this short root file states current standing invariants, not a claim
that all historical missions were completed.
