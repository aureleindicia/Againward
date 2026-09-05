---
name: indicia-client-workflow
description: Conduire ou reprendre un dossier client INDICIA / Energy Analyzer local, avec analyse exhaustive, questions à forte valeur, STOP bloquant, provenance, attribution minimale et finalisation honnête. Utiliser pour toute investigation client réelle, reprise après réponse, sélection de demande ou préparation de livraison INDICIA.
---
# Workflow client INDICIA

Reconstruire le contexte depuis le dépôt et `/storage/emulated/0/Download` : objectifs, handoffs,
R&D, benchmarks et données peuvent être répartis. Le dépôt reste autoritatif pour le code; ne pas
versionner les données client de Download.

Lire `AGENTS.md`, `docs/CLIENT_WORKFLOW.md`, `docs/PRIVACY_ARCHITECTURE.md`,
`docs/PRIVACY_THREAT_MODEL.md`, `docs/CLIENT_INFORMATION_REQUEST_POLICY.md`,
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
`energy_mvp/privacy.py` possède le gate privacy, le manifest, la rétention et la purge.
Artefacts canoniques : `investigation_state.json.client_lifecycle`, `questions.json`, puis
`minimal_attribution.json` et son ledger seulement lorsque MEA est applicable. `question_batch.json`
et les batches Goal B sont des adaptateurs/vues dépréciés, jamais une seconde autorité.

## PRIVACY GATE — obligatoire avant INITIAL ou REPRISE

Pour tout `REAL_CLIENT`, commencer par `python manage_investigation.py status <dossier>`. Ne jamais
lire substantiellement `incoming/` pour une investigation énergétique, même si le contenu semble
déjà connu ou a été vu dans une conversation précédente.

1. Si le dépôt n'est pas encore staged, créer/stager sans lecture avec `create_workspace.py
   <id> --incoming <dépôt>` ou `intake_client_case.py stage <id> <dépôt>`.
2. Codex est le premier lecteur sémantique de tous les fichiers `incoming/`. Rechercher personnes,
   contacts, identifiants individuels, texte libre personnel, RH/médical et secrets.
3. Préserver strictement machines, compteurs, lignes, sites, timestamps, unités, énergie,
   puissance, production, volumes, cycles, shifts, lots, produits, température, maintenance et
   relations utiles à l'attribution. Le privacy cleanup n'est jamais un nettoyage métier.
4. Écrire `privacy/review.json` sans aucune valeur retirée. Utiliser des pseudonymes stables sans
   table d'identité si une relation est utile. Choisir `BLOCKED` au moindre nettoyage incertain.
5. Exécuter `python manage_investigation.py privacy-validate <dossier>
   <dossier>/privacy/review.json`. Continuer uniquement si le statut déterministe est
   `PRIVACY_CLEARED` et `approved_for_analysis == true`.
6. En `PRIVACY_BLOCKED`, **arrêter complètement** : pas d'intake, calcul énergétique, hypothèse,
   attribution, finding, rapport ou extrapolation depuis ce qui vient d'être lu.
7. Ne jamais contourner le gate sous prétexte que Codex connaît déjà le contenu. Un ancien dossier
   `PRIVACY_MIGRATION_REQUIRED` est migré manuellement vers un nouveau workspace, jamais réécrit
   automatiquement.

## INITIAL

1. Lancer l'intake exclusivement depuis `sanitized/`, puis inventorier et analyser toutes les
   sources existantes; calculer avec Python et tracer
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

## LIVRAISON ET PURGE

La revue humaine reste obligatoire. Après livraison/clôture, configurer la rétention contractuelle
et exécuter `manage_investigation.py purge`. `derived_retention_authorized` reste `false` par
défaut. Ne conserver un dérivé que dans `retained_derived/`, avec autorisation et revue de
désidentification explicites. Vérifier `PURGE_RECEIPT.json`; un `partial_failure` n'est jamais une
purge réussie. Un dossier `PURGED` ne peut pas être repris analytiquement.

Avant livraison ou modification du workflow, exécuter au minimum :

```sh
python -m pytest -q tests/test_client_workflow_unification.py tests/test_workflow_paths.py
python benchmarks/client_workflow/benchmark.py
python -m pytest -q
```

Ne jamais contourner un échec de validation, inventer une réponse, traiter une déclaration comme
ancre terrain, exposer une donnée client à Git ou confondre compatibilité, attribution et cause.
