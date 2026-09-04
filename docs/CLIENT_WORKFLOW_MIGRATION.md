# Migration du workflow client

`energy_mvp.client_lifecycle` possède les transitions et `energy_mvp.client_requests` le contrat,
la VOI et la sélection. `questions.json` et `investigation_state.json.client_lifecycle` sont les
seules sources de vérité. `attribution_workflow` branche conditionnellement MEA/EvidenceLedger.

`question_batch.json`, `publish_minimum_questions()` et `economic_requests` restent des vues ou
adaptateurs dépréciés. Goal A et le workflow générique délèguent au canonique;
`publish_economic_request_batch()` fait de même pour Goal B. Les types historiques sont traduits.

Chemin : `ANALYZING → WAITING_FOR_REQUIRED_INFORMATION → RESUMING → ANALYZING → FINALIZABLE →
DELIVERABLE`. Deux cycles maximum. Le second référence la réponse créant une branche matérielle; la
troisième tentative et les doublons sémantiques sont refusés.

`energy_mvp.workflow_paths` résout sans écriture les trois layouts supportés : workspace standard
(`processed/`), cas Goal A (`investigation/`) et dossier d'analyse direct. Pour les nouveaux
workspaces, les anciennes copies racine `questions.json` et `human_review.json` ne sont plus créées.
Les dossiers déjà existants ne sont ni déplacés ni réécrits; le contenu canonique reste celui du
répertoire d'analyse résolu. Vérifier avec `python manage_investigation.py status <dossier>`.
