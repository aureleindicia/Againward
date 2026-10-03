# Documentation map

This index separates active authority from retained experiment and migration
records. Filenames containing “completion” describe their original scope, not
current product acceptance. Do not mechanically delete or move their evidence.

## Read first

- [Current state](CURRENT_STATE.md) — owners, commands, PR stack, blockers.
- [First-client release audit](FIRST_CLIENT_RELEASE_AUDIT.md) — current Gate A/B/C decision.
- [First-client readiness plan](FIRST_CLIENT_READINESS_PLAN.md) — narrow pilot scope and stop/go matrix.
- [Internal autonomy and quality](AUTONOMOUS_SERVICE_QUALITY.md) — authoritative 99%/95% objectives, metrics and asynchronous service journey; targets are unverified.
- [Operator playbook](FIRST_CLIENT_OPERATOR_PLAYBOOK.md) and
  [operations checklist](FIRST_CLIENT_OPERATIONS_CHECKLIST.md) — actual controlled workflow and owner tasks.
- [Repository layout](REPOSITORY_LAYOUT.md) — workspace and root-script roles.
- [Real-world acceptance](REAL_WORLD_ACCEPTANCE.md) — explicit partial/open items.

## Active architecture

- [Energy Billing V1 checkpoint](energy_billing/CHECKPOINT_0.md),
  [minimal Billing state and calculation](energy_billing/STATE_AND_CALCULATION.md),
  [bounded local Investigator](energy_billing/INVESTIGATOR.md),
  [official-source research](energy_billing/REGULATORY_RESEARCH.md),
  [early live boundary validation](energy_billing/VALIDATION.md) — separate new
  domain; full financial E2E and pilot readiness are still open.

- [Architecture](ARCHITECTURE.md), [document architecture](REAL_WORLD_DOCUMENT_ARCHITECTURE.md),
  [entity resolution](ENTITY_RESOLUTION.md), [client workflow](CLIENT_WORKFLOW.md).

## Active Rental

- [Rental](RENTAL.md), [Rental benchmarks](RENTAL_BENCHMARKS.md),
  [economic decision semantics](ECONOMIC_DECISION_SEMANTICS.md).

## Document intelligence

- [Document R&D / evidence and failures](DOCUMENT_INTELLIGENCE_RND.md),
  [real-world document benchmark](REAL_WORLD_RENTAL_BENCHMARKS.md),
  [real semantic evaluation](SEMANTIC_EXTRACTION_EVALUATION.md),
  [source-to-report validation](FIRST_CLIENT_E2E_VALIDATION.md).
  A routed file is not a correctly understood document.

## Privacy

- [Rental policy and PDF/scan path](RENTAL_PRIVACY_ARCHITECTURE.md),
  [privacy benchmark](RENTAL_PRIVACY_BENCHMARKS.md),
  [inherited gate](PRIVACY_ARCHITECTURE.md), [threat model](PRIVACY_THREAT_MODEL.md).

## Active benchmarks

- [Rental synthetic cases](RENTAL_BENCHMARKS.md),
  [Rental privacy decisions](RENTAL_PRIVACY_BENCHMARKS.md),
  [document routing/semantic baseline](REAL_WORLD_RENTAL_BENCHMARKS.md).
  Run scripts from the repository root and keep generated outputs in ignored
  `scratch/`.

## Compatibility / Energy

- [Analysis tools](ANALYSIS_TOOLS.md), [physical diagnostics](PHYSICAL_DIAGNOSTICS.md),
  [Energy privacy history](PRIVACY_VALIDATION_REPORT.md).
  `energy_mvp/` and legacy root wrappers remain supported until explicitly
  migrated; their tests are part of every full regression.

## Historical R&D

- [Domain-kernel acceptance](DOMAIN_KERNEL_ACCEPTANCE.md),
  [domain-kernel migration](DOMAIN_KERNEL_MIGRATION.md),
  [architecture experiments](architecture_rnd_20260916/RESEARCH_RECORD.md),
  [Stage 4 evidence plane](stage4_evidence_plane/ARCHITECTURE_AFTER_STAGE4.md),
  [critical remediation](critical_remediation_20260907/ROOT_CAUSE_ANALYSIS.md),
  [prior client mission audit](final_client_mission_20260909/COMPLETION_AUDIT.md),
  [Mega Goal audit](MEGA_GOAL_AUDIT.md).
  These are preserved reproducibility/history, not current acceptance gates.
  The former 2,069-line Energy-first root instructions are recoverable with
  `git show 94d9d2a:AGENTS.md`.
