# Workflow d'un dossier client INDICIA

Workflow local-first : Codex choisit les investigations et interprète; Python calcule et applique
les contrats; un humain autorise la livraison. Un signal automatique n'est jamais une opportunité.
Prompt autonome : [`CLIENT_INVESTIGATION_PROMPT.md`](CLIENT_INVESTIGATION_PROMPT.md). Migration :
[`CLIENT_WORKFLOW_MIGRATION.md`](CLIENT_WORKFLOW_MIGRATION.md). Organisation des dossiers :
[`REPOSITORY_LAYOUT.md`](REPOSITORY_LAYOUT.md).

Commencer ou reprendre par cette commande en lecture seule :

```sh
python manage_investigation.py status workspaces/usine_01
```

Elle accepte aussi un dossier Goal A ou un répertoire d'analyse direct et indique le propriétaire
canonique des artefacts. Les exemples ci-dessous utilisent la racine du workspace.

## 1. Contexte et intake

Reconstruire le contexte depuis le dépôt et `/storage/emulated/0/Download`. Créer le workspace,
placer une copie des données dans son `input/`, compléter l'intake puis exécuter :

```sh
python investigate.py workspaces/usine_01/input/mesures.csv \
  --intake workspaces/usine_01/intake.json \
  --output-dir workspaces/usine_01/processed
python manage_investigation.py init workspaces/usine_01
```

Avant toute demande, analyser toutes les données/documents disponibles, puis tracer les sources :

```sh
python manage_investigation.py data-exhausted workspaces/usine_01 \
  analysis_inventory.json prepared_analysis.json candidate_signals.json evidence_card.json
```

## 2. Investigation

Pour chaque piste : observation, hypothèses concurrentes, tests Python, résultat quantifié,
contre-explication, meilleure raison d'être fausse, décision et limites. Codex peut conclure
`unknown`, non identifiable ou information insuffisante sans question si aucune acquisition ne
justifie l'effort. Détection, signature, composant anonyme, compatibilité, attribution, mécanisme et
pronostic restent des niveaux distincts.

Avec signature reproductible et inventaire, utiliser `attribution_workflow`; sinon consigner
`not_applicable`. Les scores de compatibilité ne sont pas des probabilités.

## 3. Demandes externes

Rassembler les candidats Goal A, attribution et Goal B. Chaque candidat décrit deux réponses
plausibles et leurs effets distincts sur preuve, attribution, économie, priorité, action ou risque :

```sh
python manage_investigation.py publish-candidates \
  workspaces/usine_01 candidates.json
```

Python classe globalement, déduplique et retient zéro à trois demandes (cible une), en préférant
inférence, micro-question, document, observation, test terrain, export, puis instrumentation.
La préférence de source sert de départage après la valeur ajustée par disponibilité, fiabilité et
effort; une micro-question faible ne gagne donc pas automatiquement. Une VOI inférieure à `0.05`
est rejetée par défaut (seuil conservateur à recalibrer sur les pilotes).
`questions.json` est l'unique autorité. Un `BLOCKING` passe à
`WAITING_FOR_REQUIRED_INFORMATION`. STOP complet : aucune réponse inventée, promotion, économie ou
action finale, rapport ou livraison.

## 4. Réponse et reprise

Une réponse fournit `answer`, `provided_by_role`, `source_or_evidence`, `source_type`,
`provided_at_utc`, `reliability`. Types : `CLIENT_DECLARATION`, `EXISTING_DOCUMENT`,
`FIELD_OBSERVATION`, `PREREGISTERED_TEST`, `INSTRUMENT_MEASUREMENT`. Déclaration/document ne sont pas
des ancres terrain. Enregistrer :

```sh
python manage_investigation.py record-answers workspaces/usine_01 answers.json
```

En `RESUMING`, relire demande/provenance, mettre à jour les ledgers, recalculer, revoir
alternatives/attribution/confiance/économie/priorité/action, tracer avant/après et refaire la review :

Chaque entrée `before_after` contient `decision_dimensions` avec exactement : `evidence_level`,
`asset_attribution`, `alternatives`, `confidence`, `economic_materiality`,
`investigation_priority`, `field_action`, `false_conclusion_risk` (utiliser `not_applicable` si une
dimension ne concerne réellement pas la piste).

```sh
python manage_investigation.py complete-resume workspaces/usine_01 resume.json
```

Deux cycles maximum; le second référence la réponse créant une branche matérielle. Aucun doublon.
Après épuisement, `close-budget` exige une limite honnête.

## 5. Review, finalisation et livraison

La review contrôle calculs, qualité, baseline, alternatives, causalité, annualisation, économie
récupérable et double comptage. Sans BLOCKING/reprise :

```sh
python manage_investigation.py finalizable workspaces/usine_01 investigation.json
python manage_investigation.py check workspaces/usine_01
```

Le gate exige investigation, review, rapport et approbation humaine puis passe à `DELIVERABLE`.
Cette prestation n'est ni audit réglementaire ni diagnostic mécanique garanti.
