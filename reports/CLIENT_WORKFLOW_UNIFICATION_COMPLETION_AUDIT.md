# Audit de complétion — workflow client

La validation ciblée compte 39 tests (`32` workflow + `7` navigation) et deux E2E. Elle couvre les
26 familles exigées : zéro question,
STOP, rapport bloqué, mixte, reprise, contradiction, déclaration/document, préférence micro,
instrumentation rejetée, ranking/dédoublonnage/valeur, budget, unknown, MEA oui/non, ledger, gate,
migration, échec sûr, nouvelle instance, skill et prompt. La suite complète passe à `350/350`.

Reproduire :

```sh
python -m pytest -q tests/test_client_workflow_unification.py tests/test_workflow_paths.py
python -m pytest -q
python benchmarks/client_workflow/benchmark.py
python /data/data/com.termux/files/home/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/indicia-client-workflow
```

Démontré par code/tests : contrats et transitions. Démontré seulement en synthétique : E2E et
charge. Non démontré : performance client réelle, calibration VOI/fiabilité, attribution physique
sans preuve terrain.

Résultats structurés et matrice exigée : `reports/CLIENT_WORKFLOW_UNIFICATION_RESULTS.json`.
Organisation GitHub : résolveur de layouts testé, données sous `workspaces/*` ignorées par défaut,
guide `docs/REPOSITORY_LAYOUT.md` et CI `.github/workflows/tests.yml`.
