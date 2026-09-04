---
name: indicia-client-workflow
description: Conduire ou reprendre un dossier client INDICIA / Energy Analyzer local, avec analyse exhaustive, questions à forte valeur, STOP bloquant, provenance, attribution minimale et finalisation honnête. Utiliser pour toute investigation client réelle, reprise après réponse, sélection de demande ou préparation de livraison INDICIA.
---
# Workflow client INDICIA

Reconstruire le contexte depuis le dépôt et `/storage/emulated/0/Download` : objectifs, handoffs,
R&D, benchmarks et données peuvent être répartis. Le dépôt reste autoritatif pour le code; ne pas
versionner les données client de Download.

Lire `AGENTS.md`, `docs/CLIENT_WORKFLOW.md`, `docs/CLIENT_INFORMATION_REQUEST_POLICY.md`,
`docs/VALUE_OF_INFORMATION_POLICY.md` et, si pertinent, `docs/MINIMAL_EVIDENCE_ATTRIBUTION.md`.
Déterminer le mode depuis les fichiers : `INITIAL`, ou `REPRISE` si
`investigation_state.json.client_lifecycle.state == RESUMING`.
Commencer par `python manage_investigation.py status <dossier>` : la commande est en lecture seule,
reconnaît racine de workspace, cas Goal A ou dossier direct, et indique le chemin canonique et la
prochaine action. Lire aussi `docs/REPOSITORY_LAYOUT.md` en cas d'ambiguïté de navigation.

Sources de vérité : `energy_mvp/client_lifecycle.py` possède l'état/reprise,
`energy_mvp/client_requests.py` le contrat/VOI/dédoublonnage,
`energy_mvp/minimal_attribution.py` les preuves et plafonds,
`energy_mvp/attribution_workflow.py` le branchement MEA, et `energy_mvp/case_lifecycle.py` le gate.
Artefacts canoniques : `investigation_state.json.client_lifecycle`, `questions.json`, puis
`minimal_attribution.json` et son ledger seulement lorsque MEA est applicable. `question_batch.json`
et les batches Goal B sont des adaptateurs/vues dépréciés, jamais une seconde autorité.

## INITIAL

1. Inventorier et analyser toutes les sources existantes; calculer avec Python et tracer
   `data-exhausted`.
2. Conduire observations, hypothèses concurrentes, tests, falsification, quantification et review.
3. Avec signature anonyme + inventaire, appeler `run_minimal_attribution`; sinon consigner
   `not_applicable`.
4. Rassembler les candidats Goal A/attribution/Goal B. Publier via le sélecteur global. Zéro question
   par défaut; préférer micro-question/document/observation à export/instrumentation équivalents.
5. Si `must_stop=true`, transmettre les demandes et leur utilité puis **arrêter la session**. Ne pas
   inventer de réponse, promouvoir la piste, finaliser son économie/action ou générer le rapport.
6. Sans question utile, review adversariale, limites, `FINALIZABLE`, rapport puis gate humain.

## REPRISE

1. Relire `questions.json`, demandes/réponses append-only, auteur/date, provenance, type,
   contradictions et corrections. Une absence n'est pas une confirmation.
2. Mettre à jour l'EvidenceLedger si concerné. Une `CLIENT_DECLARATION` ou un
   `EXISTING_DOCUMENT` n'est jamais automatiquement une ancre vérifiée.
3. Recalculer avec Python, revoir alternatives, attribution, confiance, économie, priorité/action;
   tracer avant/après pour les huit dimensions exigées par `complete_resume` et refaire la review.
4. Fermer via `complete-resume`. Second cycle seulement pour une branche matérielle nouvelle; deux
   cycles maximum, jamais de question équivalente.
5. Si insuffisant, `close-budget` puis finaliser unknown/non identifiable/cause non démontrée.

Toujours séparer détection, signature, composant anonyme, compatibilité, attribution, mécanisme et
pronostic. Python porte les chiffres; Codex choisit et interprète les tests.

Avant livraison ou modification du workflow, exécuter au minimum :

```sh
python -m pytest -q tests/test_client_workflow_unification.py tests/test_workflow_paths.py
python benchmarks/client_workflow/benchmark.py
python -m pytest -q
```

Ne jamais contourner un échec de validation, inventer une réponse, traiter une déclaration comme
ancre terrain, exposer une donnée client à Git ou confondre compatibilité, attribution et cause.
