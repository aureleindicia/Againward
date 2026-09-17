# Workflow d’un dossier client Againward

Againward est local-first pour le workspace et l’orchestration. Codex reste l’analyste et la
première étape capable de lire sémantiquement le contenu brut reçu ; Python applique ensuite les
contrats fail-closed, calcule et trace. Le fonctionnement du service implique donc un traitement
par Codex/OpenAI selon la configuration utilisée : il ne faut pas promettre que les données ne
quittent jamais l’appareil.

Le flux obligatoire des futurs dossiers réels est :

```text
CLIENT → dossier vide → contract_policy + revue humaine → incoming/ temporaire → CODEX PRIVACY GATE
       → PASS | SANITIZED | BLOCKED
       → post-check Python → privacy_manifest.json
       → suppression du brut temporaire → PRIVACY_CLEARED
       → intake depuis sanitized/ → investigation → revue humaine → livraison
       → rétention configurée → purge → PURGE_RECEIPT.json
```

Un signal automatique reste un candidat, jamais une opportunité confirmée. Détection, signature,
composant, attribution d’actif, mécanisme physique et pronostic restent distincts.

Références : [architecture privacy](PRIVACY_ARCHITECTURE.md),
[menaces et limites](PRIVACY_THREAT_MODEL.md), [migration](CLIENT_WORKFLOW_MIGRATION.md) et
[prompt autonome](CLIENT_INVESTIGATION_PROMPT.md).

## 1. Créer et recevoir sans analyser

Workspace standard :

```sh
python create_workspace.py usine_01 --root workspaces
python manage_investigation.py contract-record workspaces/usine_01 contracts_packet.json
python manage_investigation.py stage-incoming workspaces/usine_01 /chemin/du/depot_recu
python manage_investigation.py status workspaces/usine_01
```

Cas Goal A hétérogène :

```sh
python intake_client_case.py create usine_01 --root client_cases
python manage_investigation.py contract-record client_cases/usine_01 contracts_packet.json
python manage_investigation.py stage-incoming client_cases/usine_01 /chemin/du/depot_recu
python manage_investigation.py status client_cases/usine_01
```

Le staging copie les octets et les chemins dans `incoming/`, sans parser, normaliser, classifier ni
hasher le contenu. `incoming/` est temporaire et n’est jamais la source analytique durable.

## 2. Privacy gate Codex-first

Avant toute autre lecture substantielle, Codex inspecte tous les fichiers de `incoming/`. Il doit :

- préserver les timestamps, mesures, unités, production, compteurs, machines, lignes, sites,
  shifts, lots, campagnes, maintenance et relations utiles à l’attribution ;
- supprimer une identité inutile ;
- utiliser un pseudonyme stable (`OPERATOR_001`, par exemple) si la relation opérateur-machine-
  shift est utile, sans conserver de table de correspondance ;
- supprimer les secrets techniques inutiles ;
- choisir `BLOCKED` pour les données médicales/RH, un format non vérifiable ou tout nettoyage dont
  la sûreté ou la préservation industrielle est incertaine ;
- ne faire aucune correction d’unité, interpolation, déduplication ou normalisation métier.

Codex produit `privacy/review.json`. Les champs sont bornés : codes de catégorie/action, comptes,
identifiants `FILE-001`, chemins temporaires, et attestations. Aucune valeur retirée ne doit être
recopiée. Pour `SANITIZED`, la copie candidate reste dans `privacy/candidate/`. Les raisons de
blocage sont des codes (`SPECIAL_CATEGORY_DATA`, `UNSUPPORTED_FORMAT`,
`INDUSTRIAL_PRESERVATION_UNCERTAIN`), pas du contenu source.

Valider ensuite :

```sh
python manage_investigation.py privacy-validate \
  workspaces/usine_01 workspaces/usine_01/privacy/review.json
```

Python vérifie la couverture de tous les fichiers, les colonnes personnelles explicites, emails,
téléphones, secrets et contenus RH/médicaux évidents. Il compare ensuite original et candidat :
type, feuilles, lignes, timestamps, unités par en-têtes, valeurs énergie/puissance/production et
identifiants industriels. Une mutation non expliquée bloque le dossier.

Après succès, `sanitized/` devient la source canonique, le brut `incoming/`, le candidat et la
review de travail sont supprimés, et `privacy/privacy_manifest.json` porte
`approved_for_analysis: true`. Si une suppression échoue, le dossier reste `PRIVACY_BLOCKED`.

`BLOCKED` est un STOP complet. Aucun intake, finding, calcul métier, attribution, rapport ou
livraison n’est permis.

## 3. Intake et préparation

Pour un workspace standard :

```sh
python investigate.py workspaces/usine_01/sanitized/mesures.csv \
  --intake workspaces/usine_01/intake.json \
  --output-dir workspaces/usine_01/processed
```

Pour Goal A :

```sh
python intake_client_case.py intake client_cases/usine_01
```

Les commandes vérifient le manifest et, pour une source `sanitized/`, son SHA-256. Elles refusent
`incoming/`, un hash non approuvé et tout état autre que `PRIVACY_CLEARED`. L’intake de qualité de
données commence seulement ici ; ses conversions restent séparées des transformations privacy.

Avant toute demande au client, analyser et inventorier toutes les sources disponibles :

```sh
python manage_investigation.py data-exhausted workspaces/usine_01 \
  analysis_inventory.json prepared_analysis.json candidate_signals.json evidence_card.json
```

## 4. Investigation, questions et reprise

Pour chaque piste : observation, hypothèses concurrentes, tests Python, résultat quantifié,
contre-explication, meilleure raison d’être fausse, décision et limites. Avec signature
reproductible et inventaire, utiliser l’attribution minimale ; sinon consigner `not_applicable`.

Les candidats à une demande sont dédupliqués et classés par valeur décisionnelle. Zéro question est
la valeur par défaut ; une micro-question ou observation ponctuelle prévaut sur un export lourd à
valeur équivalente. Au plus trois demandes par cycle (cible : une) et deux cycles par défaut :

```sh
python manage_investigation.py publish-candidates workspaces/usine_01 candidates.json
```

La sélection utilise l'information marginale conditionnelle quand les partitions de réponses
sont complètes. Deux demandes sur la même hypothèse ne sont pas nécessairement équivalentes.
Les continuations justifiées et la récupération après interruption sont décrites dans
[INVESTIGATION_CONTINUATION.md](INVESTIGATION_CONTINUATION.md). Un plafond de ressources ne
constitue jamais une preuve de complétude. `close-budget` ne contourne ni STOP ni REPRISE.

Un candidat `BLOCKING` passe à `WAITING_FOR_REQUIRED_INFORMATION`. Codex transmet la question et
son utilité puis arrête complètement la session : aucune réponse inventée, promotion, économie,
action finale ou génération de rapport.

À réception, enregistrer la provenance et le type (`CLIENT_DECLARATION`, `EXISTING_DOCUMENT`,
`FIELD_OBSERVATION`, `PREREGISTERED_TEST`, `INSTRUMENT_MEASUREMENT`) :

```sh
python manage_investigation.py record-answers workspaces/usine_01 answers.json
python manage_investigation.py complete-resume workspaces/usine_01 resume.json
```

Une déclaration n’est pas une preuve terrain. La reprise recalcule avec Python et réévalue les huit
dimensions du contrat : preuve, attribution, alternatives, confiance, importance économique,
priorité, action terrain et risque de fausse conclusion. Après le budget courant, si aucune
continuation n'est justifiée par de nouvelles preuves décisionnelles, finaliser
honnêtement avec `unknown`, `non identifiable` ou `information insuffisante`.

## 5. Revue, livraison, rétention et purge

La review contradictoire précède toujours l’approbation humaine. Pour la composition Codex du PDF,
les hashes de revue, le post-mortem et les dérivés retenables, suivre
[FINAL_CLIENT_MISSION.md](FINAL_CLIENT_MISSION.md). La rétention doit être configurée avant livraison.

```sh
python manage_investigation.py finalizable workspaces/usine_01 investigation.json
python manage_investigation.py check workspaces/usine_01
```

Configurer la rétention à partir du template, avec une date contractuelle et `mission_closed: true`
seulement lorsque la mission est effectivement close :

```sh
python manage_investigation.py retention-configure \
  workspaces/usine_01 retention_policy.json
python manage_investigation.py purge workspaces/usine_01
```

`derived_retention_authorized` vaut `false` par défaut. S’il vaut `true`, seuls des fichiers placés
dans `retained_derived/` et couverts par une revue de désidentification stricte peuvent survivre.
La purge efface les sources, dérivés reconstructibles, scratch, caches et artefacts temporaires,
préserve uniquement les contrats/facturation, PDF et dérivés explicitement autorisés et validés, écrit
`PURGE_RECEIPT.json`, puis interdit toute nouvelle analyse du dossier purgé.

Cette architecture réduit les risques techniques ; elle ne constitue ni un avis juridique, ni une
certification de sécurité, ni une garantie d’anonymisation parfaite.
