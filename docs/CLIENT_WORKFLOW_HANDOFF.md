# Handoff court — workflow client unifié

Skill : `.codex/skills/indicia-client-workflow/SKILL.md`. Prompt :
`docs/CLIENT_INVESTIGATION_PROMPT.md`. Le contexte peut être réparti entre le dépôt et
`/storage/emulated/0/Download`; le dépôt reste autoritatif pour le code.

Artefacts canoniques : `investigation_state.json.client_lifecycle`, `questions.json`, et si
applicable `minimal_attribution.json` + `evidence/minimal_attribution_*_ledger.json`.

Lire l'état persistant : `ANALYZING`, `WAITING_FOR_REQUIRED_INFORMATION`, `RESUMING`,
`FINALIZABLE`, `DELIVERABLE`. STOP absolu sur BLOCKING. Deux cycles, trois demandes/cycle, zéro par
défaut. Après réponse : provenance, recalcul Python, avant/après, review. Après budget : unknown.
