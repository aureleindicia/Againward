# Handoff court — workflow client unifié

Skill : `.codex/skills/indicia-client-workflow/SKILL.md`. Prompt :
`docs/CLIENT_INVESTIGATION_PROMPT.md`. Le contexte peut être réparti entre le dépôt et
`/storage/emulated/0/Download`; le dépôt reste autoritatif pour le code.

Artefacts canoniques : `investigation_state.json.client_lifecycle`, `questions.json`, et si
applicable `minimal_attribution.json` + `evidence/minimal_attribution_*_ledger.json`.

Organisation : `energy_mvp/workflow_paths.py` accepte workspace (`processed/`), Goal A
(`investigation/`) et dossier direct. Commencer par `python manage_investigation.py status <cas>`.
Les nouveaux workspaces n'ont plus de copies concurrentes de questions/revue à la racine.

Propriétaires : `client_lifecycle.py` (état/reprise), `client_requests.py` (contrat/VOI),
`minimal_attribution.py` (preuves/plafonds), `attribution_workflow.py` (branchement MEA),
`case_lifecycle.py` (delivery gate). `question_batch.json`, `publish_minimum_questions()` et les
batches Goal B sont des adaptateurs/vues dépréciés.

Lire l'état persistant : `ANALYZING`, `WAITING_FOR_REQUIRED_INFORMATION`, `RESUMING`,
`FINALIZABLE`, `DELIVERABLE`. STOP absolu sur BLOCKING. Deux cycles, trois demandes/cycle, zéro par
défaut. Après réponse : provenance, recalcul Python, avant/après, review. Après budget : unknown.

Validation : `python -m pytest -q`, puis `python benchmarks/client_workflow/benchmark.py`. Limites :
VOI et fiabilités non calibrées sur clients réels, compréhension linguistique à revoir par Codex et
humain, aucune attribution mécanique sans preuve terrain. Prochaine étape : premier pilote réel
supervisé avec audit des questions rejetées/retenues, sans modifier les seuils sur un seul cas.
