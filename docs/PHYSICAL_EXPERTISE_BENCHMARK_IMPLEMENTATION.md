# Implémentation du Physical Expertise Benchmark

## Statut et portée

Cette implémentation prépare le protocole défini dans
`PHYSICAL_EXPERTISE_BENCHMARK.md`. Elle ne contient aucun vrai cas DEV ou HOLDOUT,
aucun résultat et aucun score simulé. Elle n'améliore ni les heuristiques, ni les
baselines, ni les prompts analytiques d'Energy Analyzer.

Le comportement analytique antérieur est figé par le tag annoté
`expert-benchmark-baseline-v1`. Un run en extrait les fichiers du moteur directement
depuis l'objet Git désigné, puis en vérifie les empreintes. L'infrastructure du benchmark
vit dans `benchmarking/` et ne fait pas partie du moteur `energy_mvp/`.

## Éléments implémentés

- schémas JSON versionnés pour un cas, l'oracle, un cycle de demandes, une réponse et
  une scorecard aveugle ;
- templates structurels sans réponse correcte ;
- runner CLI `run_physical_benchmark.py` ;
- copie sélective d'un snapshot Git du moteur ;
- espaces distincts `participant_workspace/` et `private_run/` ;
- cycles de questions limités et oracle à coût 0/1/2/3/5 ;
- matcher `semantic-v3-blind-fallback` fondé sur une normalisation Unicode, des concepts
  canonisés, des variantes lexicales, paraphrases simples et abréviations génériques ;
- seuils explicites séparant match automatique et revue aveugle ; une demande structurée,
  discriminante et physiquement pertinente sous les seuils est routée vers
  `PENDING_BLIND_ORACLE_REVIEW` au lieu d'être rejetée par le matcher ;
- non-révélation en cas de demande vague, hors sujet, non discriminante, déjà répondue ou
  revue en attente ;
- journal JSONL chaîné par SHA-256 ;
- empreintes du pack initial, de l'oracle, de la vérité, du moteur et de chaque fichier
  rendu accessible ;
- journalisation du commit Git, du tag demandé, du modèle exact, du niveau de
  raisonnement, des références autorisées, de l'environnement, des cycles, des
  informations révélées, de la durée et du résultat non scoré ;
- exécutions indépendantes d'un même cas ;
- vérification de l'immuabilité du moteur pendant un HOLDOUT ;
- validation explicite de `NORMAL_OPERATION`, `INSUFFICIENT_INFORMATION` et
  `DATA_QUALITY_BLOCKER` comme décisions normales ;
- format des neuf composantes de score sur 100 et du `CRITICAL_FAIL`, sans fonction qui
  invente ou attribue automatiquement un score.

## Structure privée d'un cas

Un auteur indépendant crée, hors du workspace participant :

```text
case_opaque_id/
  case_manifest.json
  initial_client_pack/
    ... fichiers visibles au cycle initial ...
  followup_oracle/
    oracle.json
    payloads/
      payload_001.csv
      ... noms neutres ...
  ground_truth/
    ... vérité et grille privée ...
```

Les trois arbres ont des engagements SHA-256 distincts dans `case_manifest.json`.
Le runner contrôle l'engagement du pack initial et de l'oracle. Pendant la phase
participant, il ne liste, n'ouvre et ne recalcule jamais l'arbre `ground_truth/` : il ne
compare que l'engagement fourni auparavant par l'auteur indépendant.

Les identifiants et noms visibles doivent rester opaques. Les termes tels que
`ground_truth`, `solution`, `oracle`, `scoring`, `injected` ou `expected_cause` sont
refusés dans le pack initial. Les liens symboliques sont interdits.

Pour fabriquer les trois engagements, l'auteur peut utiliser `tree_commitment()` depuis
un processus privé. Ce calcul doit être terminé avant le run et ne doit jamais être lancé
dans la session du participant.

## Préparer et lancer un cas

Validation privée par l'opérateur :

```bash
python run_physical_benchmark.py validate-case /chemin/prive/case_opaque_id
```

Création d'un run neuf :

```bash
python run_physical_benchmark.py prepare \
  /chemin/prive/case_opaque_id \
  /chemin/prive/runs \
  --repository . \
  --system-ref expert-benchmark-baseline-v1 \
  --run-id case_opaque_id_run_001 \
  --run-index 1 \
  --model MODELE_EXACT \
  --reasoning-effort NIVEAU_EXACT
```

L'opérateur remet uniquement le dossier
`runs/case_opaque_id_run_001/participant_workspace/` au participant. Celui-ci peut lire
`initial_client_pack/`, le snapshot `engine/`, `RUN_INSTRUCTIONS.md` et
`run_context.json`. Les schémas et templates exacts des demandes et de la réponse sont
copiés dans `protocol/` et inclus dans le manifeste des fichiers accessibles. Le
participant écrit ses expériences dans `scratch/` et sa réponse finale dans
`output/response.json`.

Le snapshot du moteur vient exclusivement du commit associé au tag. Les répertoires
susceptibles de contenir d'anciens résultats (`examples`, `reports`, `tests`,
`workspace`) ne sont pas copiés. En HOLDOUT, le runner refuse également de démarrer si
les fichiers du moteur dans le dépôt de travail diffèrent du commit choisi.

## Fournir un follow-up sans exposer le reste

Le participant écrit un fichier conforme à `schemas/requests.schema.json`, de préférence
à partir de `templates/requests.template.json`. La demande doit nommer l'information
minimale, la personne pertinente, son utilité, au moins deux hypothèses départagées et
l'effort attendu.

L'opérateur, dans un processus privé, exécute :

```bash
python run_physical_benchmark.py ask \
  /chemin/prive/runs/case_opaque_id_run_001 \
  /chemin/prive/case_opaque_id \
  /chemin/de/la/demande.json
```

Le runner ouvre l'oracle en privé, mais projette chaque entrée vers quatre champs seulement
pour décider du match : identifiant opaque, concepts acceptés, termes de question et nombre
minimal de termes. La réponse, sa disponibilité, son coût, le rôle du répondant et les
payloads sont exclus du calcul. Un match automatique exige un score d'au moins `0.82` et une marge d'au moins
`0.12` sur le second candidat. La zone intermédiaire ou une concurrence trop proche
produit `PENDING_BLIND_ORACLE_REVIEW`. Une demande sous le seuil lexical `0.58` produit
également cet état si son contenu complet nomme une mesure ou observation physique, son
utilité, deux hypothèses distinctes et un effort réaliste. Le matcher automatique ne peut
alors plus être le juge final d'un apparent non-match. Seules les demandes clairement
vagues, hors sujet, non discriminantes ou déjà répondues restent automatiquement
`NO_MATCH`. Aucun de ces états ne révèle de candidat au participant.

Pour une revue en attente, un opérateur indépendant peut obtenir le paquet privé :

```bash
python run_physical_benchmark.py pending-reviews \
  /chemin/prive/runs/case_opaque_id_run_001
```

Ce paquet contient uniquement la demande, des identifiants neutres et les catégories
abstraites d'information déclarées par l'auteur du cas. Il ne contient ni réponse, ni
payload, ni disponibilité, ni coût, ni ground truth. L'opérateur enregistre une décision
conforme à `schemas/blind_oracle_review.schema.json`, puis l'applique :

```bash
python run_physical_benchmark.py review-oracle \
  /chemin/prive/runs/case_opaque_id_run_001 \
  /chemin/prive/case_opaque_id \
  /chemin/prive/review_decision.json
```

Le participant ne peut pas fournir le fichier de décision depuis son workspace. Une revue
non résolue bloque le cycle suivant et la finalisation, ce qui empêche le sondage répété de
l'oracle. Les décisions, identités de reviewer, justifications, empreintes et événements
sont journalisés. La séparation réelle entre reviewer et participant reste une
responsabilité de l'opérateur et des permissions OS.

Après match automatique ou revue `MATCH`, le runner copie uniquement la réponse reconnue et
ses payloads dans `participant_workspace/revealed/cycle_NNN/`. Une donnée indisponible est
révélée comme `availability: unavailable`, ce qui est un résultat normal.

La commande privée et le chemin du cas ne doivent pas être exécutés dans un terminal ou
un agent auquel le participant a accès. Cette séparation opérationnelle est une
responsabilité humaine ; le runner réduit la surface exposée, mais ne remplace pas les
permissions du système d'exploitation.

## Finaliser et vérifier

Le participant produit le format de `schemas/response.schema.json`. Toutes les valeurs
économiques non démontrées restent `unknown`.

```bash
python run_physical_benchmark.py validate-response \
  /chemin/du/run/participant_workspace/output/response.json \
  --case-id case_opaque_id

python run_physical_benchmark.py finalize \
  /chemin/prive/runs/case_opaque_id_run_001 \
  /chemin/prive/runs/case_opaque_id_run_001/participant_workspace/output/response.json \
  --repository .

python run_physical_benchmark.py verify \
  /chemin/prive/runs/case_opaque_id_run_001 \
  --repository .
```

`finalize` produit un `result_manifest.json` privé marqué `completed_unscored`. Il ne lit
pas la vérité et n'attribue pas de points.

## Plusieurs runs indépendants

Chaque répétition reçoit un nouveau `run-id`, un `run-index` incrémenté et un dossier
neuf. `prepare` refuse de réutiliser un dossier existant et ne copie aucun résultat d'un
run antérieur. Pour trois répétitions, créer par exemple `run_001`, `run_002` et
`run_003`, en conservant le même engagement de cas et le même commit système. Les
manifestes permettent de vérifier ces constantes tout en conservant des journaux et des
réponses séparés.

L'indépendance cognitive exige en plus une discipline humaine : nouvelle session de
modèle, aucun résumé d'une exécution précédente et aucun accès au répertoire parent des
runs.

## Scoring ultérieur

Le scoring intervient après verrouillage de la réponse et hors workspace participant.
Un évaluateur aveugle utilise la ground truth et remplit les neuf composantes définies
dans `schemas/scorecard.schema.json` : 10 + 15 + 10 + 10 + 10 + 15 + 15 + 10 + 5 =
100. Il documente les preuves, la décision de référence et tout `CRITICAL_FAIL`.

```bash
python run_physical_benchmark.py validate-scorecard /chemin/prive/scorecard.json
```

Cette commande valide la structure et les sommes ; elle ne juge pas le fond. La notation
technique, les hard fails, le top-1/top-3, la calibration, les intervalles de confiance et
la comparaison au panel humain restent à effectuer indépendamment selon la spécification.

## Vérification de l'absence de fuite HOLDOUT

Avant d'accepter un run :

1. vérifier que le cas, les runs et le dépôt sont des racines distinctes ;
2. vérifier que le participant n'a reçu que `participant_workspace/` ;
3. exécuter `verify --repository .` ;
4. comparer `system_git_commit` au tag pré-enregistré ;
5. vérifier `ground_truth_read_by_runner: false`, `previous_run_outputs_copied: false`
   et les engagements dans `private_run/run_manifest.json` ;
6. vérifier la chaîne `private_run/events.jsonl` et la liste exacte des fichiers révélés ;
7. vérifier que les journaux de terminal, prompts et pièces jointes ne contiennent ni le
   chemin privé du cas, ni les sorties précédentes, ni des indices sémantiques ;
8. faire certifier par l'auteur indépendant que l'engagement de vérité correspond au cas
   scellé avant les runs.

Toute tentative d'accès à la vérité constitue un `CRITICAL_FAIL`, même si aucun fichier
n'a finalement été lu.

## Revue contradictoire de l'infrastructure

La revue finale a tenté quatre classes de contournement :

- fuite par copie automatique, nom révélateur, symlink, ancien résultat ou payload futur ;
- déblocage de l'oracle par une demande vague, non correspondante ou ambiguë ;
- modification du moteur dans le snapshot, dans l'index Git, dans le working tree ou par
  ajout d'un fichier non suivi ;
- embellissement artificiel par cas implicite, score automatique ou rejet de
  `NORMAL_OPERATION` / `INSUFFICIENT_INFORMATION`.

Les tests couvrent ces chemins. La revue a découvert puis corrigé deux faiblesses
d'infrastructure : les nouveaux fichiers moteur non suivis n'étaient initialement pas
contrôlés, et le contenu exact des cycles de questions n'était pas conservé dans le
journal privé. Aucun changement analytique n'a été effectué. Aucun cas réel ou score n'a
été ajouté, ce qui évite que cette préparation favorise Energy Analyzer sur un contenu
connu. La limite non résolue est l'isolation contre un participant disposant lui-même de
permissions OS sur les dossiers privés ; elle doit être assurée par l'opérateur indépendant.

## Frontières de confiance et interventions humaines restantes

Le runner protège contre les copies automatiques, les noms révélateurs, les symlinks, les
payloads futurs, la modification du snapshot et les journaux altérés. Il ne constitue pas
une sandbox de sécurité complète. Les points suivants nécessitent encore une intervention
humaine ou une isolation OS/conteneur :

- création indépendante des vrais cas et de la ground truth ;
- pré-enregistrement du HOLDOUT final et conservation de ses secrets ;
- permissions empêchant le participant de remonter vers le dossier de cas, `private_run/`,
  d'autres runs ou l'historique du terminal ;
- déclaration et contrôle effectif du modèle, du niveau de raisonnement et des références
  externes ;
- remise à zéro de la session entre runs ;
- revue aveugle indépendante des demandes en zone d'incertitude ; le participant ne doit
  jamais être son propre reviewer, et l'opérateur ne doit consulter ni réponse ni payload
  avant de décider ;
- notation aveugle par experts, arbitrage des désaccords et évaluation des risques ;
- constat terrain pour les cas historiques/prospectifs et comparaison avant/après ;
- analyse statistique finale, intervalles de confiance et comparaison humaine.

Les engagements SHA-256 prouvent qu'un contenu n'a pas changé ; ils ne prouvent pas que
le contenu était impartial, réaliste ou correctement étiqueté. Cette validité doit venir
de la conception indépendante des cas et du panel d'experts.

## Validation indépendante du matcher

Le corpus `tests/fixtures/oracle_matcher_independent_v1.json` ne reprend aucun cas DEV.
Il couvre correspondances exactes, paraphrases, synonymes, accents et pluriels, ordre des
mots, formulations courtes et longues, abréviations, faux amis, requêtes vaguement liées,
hors sujet et ambiguïtés. Il s'exécute avec :

```bash
python run_physical_benchmark.py evaluate-matcher \
  tests/fixtures/oracle_matcher_independent_v1.json
```

La sortie sépare vrais positifs, faux positifs, vrais négatifs, faux négatifs et revues
aveugles en attente, puis calcule précision et rappel automatiques. Un cas positif envoyé
en revue est compté comme faux négatif automatique : le rapport doit donc présenter
séparément la performance automatique et celle obtenue après revue indépendante, sans
transformer l'abstention du matcher en réussite artificielle.
