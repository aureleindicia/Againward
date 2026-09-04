# Audit de complétion — workflow client

La suite dédiée compte 27 tests et deux E2E. Elle couvre les 26 familles exigées : zéro question,
STOP, rapport bloqué, mixte, reprise, contradiction, déclaration/document, préférence micro,
instrumentation rejetée, ranking/dédoublonnage/valeur, budget, unknown, MEA oui/non, ledger, gate,
migration, échec sûr, nouvelle instance, skill et prompt.

Reproduire :

```sh
pytest -q tests/test_client_workflow_unification.py
pytest -q
python benchmarks/client_workflow/benchmark.py
python /data/data/com.termux/files/home/.codex/skills/.system/skill-creator/scripts/quick_validate.py .codex/skills/indicia-client-workflow
```

Démontré par code/tests : contrats et transitions. Démontré seulement en synthétique : E2E et
charge. Non démontré : performance client réelle, calibration VOI/fiabilité, attribution physique
sans preuve terrain.
