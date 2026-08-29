# Physical Expertise Benchmark — correctif du matcher oracle

## Résultat

L'incident de la première campagne venait d'un matcher lexical trop strict, pas d'une
preuve que les 33 demandes non reconnues étaient mauvaises. Le matcher `exact-v1`
exigeait simultanément :

- une égalité exacte entre un `requested_concept` et un `accepted_concept` après une
  normalisation limitée à la casse, aux accents et à la ponctuation ;
- la présence littérale d'un nombre minimal de `question_terms` dans la question ;
- au moins cinq mots dans la question ;
- un meilleur score unique, toute égalité devenant un non-match.

Il ne gérait ni synonymes, ni flexions, ni abréviations, ni ordre différent des mots,
ni paraphrases simples. Une question physiquement précise pouvait donc rester sans
réponse pour une différence purement lexicale.

Le correctif remplace ce comportement par `semantic-v2`, ajoute l'état
`PENDING_BLIND_ORACLE_REVIEW` et conserve l'intelligence analytique d'Energy Analyzer
strictement inchangée.

## Versions et séparation expérimentale

- baseline analytique : `expert-benchmark-baseline-v1` ;
- commit analytique : `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d` ;
- empreinte moteur avant et après :
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a` ;
- commit principal du matcher :
  `d1451413cdbef54f96ad029278c8718707710489` ;
- commit d'orchestration ajoutant les contrats scellés au workspace participant :
  `e7b4bcd1908c06075810c4561addaf11ec108c06` ;
- empreinte du runner enregistrée dans les 18 runs :
  `8d8f4b4bf54d8003303613fa74d2dea5eb2bb46e389e1c03eb339af77f80dad9`.

Le diff des chemins analytiques protégés par rapport au tag baseline est vide. Aucun
module `energy_mvp`, seuil analytique, baseline, prompt d'investigation, profil métier,
outil physique ou recommandation n'a été modifié.

## Matching `semantic-v2`

### Projection privée minimale

Le calcul du match ne reçoit que quatre champs de chaque entrée oracle :

- identifiant opaque ;
- concepts acceptés ;
- termes de question ;
- nombre minimal de termes.

La réponse, les payloads, la disponibilité, le coût et le rôle du répondant sont exclus
du calcul. Un test fait varier tous ces champs secrets tout en vérifiant que la décision
du matcher reste strictement identique.

### Normalisation et concepts

Le matcher applique :

- normalisation Unicode NFKD, casse, accents et ponctuation ;
- suppression de mots outils français et anglais ;
- flexions simples singulier/pluriel et quelques suffixes anglais ;
- groupes sémantiques bilingues génériques pour horaires, maintenance, mesure,
  température, consigne, pression, débit, puissance, vitesse, alarmes, CVC, etc. ;
- expansion d'abréviations génériques : BMS/GTB, HVAC/CVC et VFD/VSD ;
- comparaison conjointe de la question libre et des concepts explicitement demandés.

Ce lexique ne contient aucun identifiant des 18 cas DEV, aucune cause cachée et aucune
réponse oracle.

### Score et seuils explicites

Le score d'un candidat est :

```text
0,55 × couverture du concept
+ 0,30 × satisfaction du minimum de termes
+ 0,10 × couverture de tous les termes
+ 0,05 × spécificité de la question
```

Un match automatique exige notamment :

- couverture conceptuelle d'au moins `0.75` ;
- nombre minimal de termes atteint ;
- score d'au moins `0.82` ;
- marge d'au moins `0.12` sur un second candidat éventuel.

Un candidat à score inférieur à `0.58` est rejeté. La zone intermédiaire ou des
candidats concurrents trop proches déclenchent une revue aveugle. Les demandes vagues
restent des non-matchs même si leurs concepts déclarés tentent de nommer une entrée.

## Revue aveugle indépendante

Une décision incertaine devient `PENDING_BLIND_ORACLE_REVIEW`. Le participant voit
seulement cet état et `independent_review_required`, jamais les candidats.

Le paquet opérateur contient uniquement :

- la question et sa justification ;
- un identifiant de revue ;
- les identifiants opaques candidats ;
- une description abstraite minimale des catégories d'information.

Il exclut réponse, payload, disponibilité, coût, rôle et ground truth. L'opérateur choisit
`MATCH` vers un seul candidat ou `NO_MATCH`. Une revue non résolue bloque le cycle suivant
et la finalisation. Le participant ne peut pas fournir une décision depuis son propre
workspace.

Le paquet, la décision et l'enregistrement résolu sont copiés dans la zone privée,
empreintés et vérifiés lors du contrôle d'intégrité. Le reviewer, sa justification, la
décision et les hashes sont inscrits dans le journal chaîné du run.

## Corpus synthétique indépendant

Le corpus `tests/fixtures/oracle_matcher_independent_v1.json` contient 22 fixtures sans
lien avec les cas DEV : 13 positives et 9 négatives. Il couvre égalités exactes,
paraphrases, synonymes, accents, pluriels, ordre des mots, questions courtes et longues,
abréviations, faux amis, proximité insuffisante et hors sujet.

| Mesure automatique | Résultat |
|---|---:|
| fixtures | 22 |
| vrais positifs | 12 |
| faux positifs | 0 |
| vrais négatifs | 9 |
| faux négatifs | 1 |
| revues aveugles en attente | 2 |
| précision | 100,0 % |
| rappel | 92,3 % |

Le faux négatif automatique est une abstention positive envoyée en revue, pas une
révélation erronée. La seconde revue concerne une fixture négative volontairement
ambiguë. Une revue correcte permettrait de résoudre les deux, mais cette performance
humaine potentielle n'est pas ajoutée artificiellement aux métriques automatiques.

Commande reproductible :

```bash
python run_physical_benchmark.py evaluate-matcher \
  tests/fixtures/oracle_matcher_independent_v1.json
```

## Comportement observé lors du rerun DEV

Les 18 cas réels n'ont pas de labels de correspondance accessibles au participant. Les
chiffres ci-dessous décrivent donc le comportement, pas la précision ni le rappel réels :

- 28 demandes ;
- 7 matchs automatiques ;
- 16 non-matchs automatiques ;
- 5 revues aveugles ;
- 2 revues `MATCH` et 3 revues `NO_MATCH` ;
- 9 follow-ups révélés au total ;
- 19 non-matchs finaux ;
- coût oracle total : 14 unités protocolaires.

Le taux de révélation passe de 3/36 dans la première campagne à 9/28. Ce gain est
compatible avec un rappel supérieur, mais ne le prouve pas : certaines nouvelles
questions étaient différentes et aucune ground truth de matching n'a été ouverte.

## Fichiers d'infrastructure modifiés ou ajoutés

- `benchmarking/physical_expertise.py` ;
- `benchmarking/physical_expertise_cli.py` ;
- `benchmarks/physical_expertise/README.md` ;
- `benchmarks/physical_expertise/schemas/blind_oracle_review.schema.json` ;
- `benchmarks/physical_expertise/templates/blind_oracle_review.template.json` ;
- `docs/PHYSICAL_EXPERTISE_BENCHMARK_IMPLEMENTATION.md` ;
- `tests/fixtures/oracle_matcher_independent_v1.json` ;
- `tests/test_physical_expertise_benchmark.py`.

Les schémas et templates exacts des demandes et réponses sont également copiés et
empreintés dans chaque nouveau workspace participant, afin que le prompt externe ne soit
pas la seule source du contrat.

## Revue contradictoire et protections

### Fuite de réponse ou payload

Le matcher travaille sur une projection sûre et les tests confirment que modifier les
champs secrets ne change pas la décision. La revue aveugle ne reçoit pas ces champs. Une
réponse n'est copiée qu'après match automatique ou décision indépendante `MATCH`.

### Surmatching

Une couverture conceptuelle, un minimum de termes, un score et une marge sont requis.
Les faux amis et requêtes vaguement liées du corpus donnent zéro faux positif. Le rerun
n'a pas été optimisé pour maximiser les révélations : 19/28 demandes restent finalement
sans match.

### Sondage de l'oracle

Une revue en attente bloque toute nouvelle demande ; chaque demande ne révèle au plus
qu'une entrée et une entrée déjà révélée ne peut pas l'être à nouveau. Les identifiants
candidats et scores ne sont jamais publics. Le protocole conserve toutefois jusqu'à trois
cycles et applique une pénalité au-delà de cinq demandes plutôt qu'un verrou dur : un
participant malveillant disposant de nombreux identifiants de requêtes conserve une
capacité résiduelle de sondage. Le runner est un dispositif expérimental, pas une sandbox
de sécurité complète.

### Raisons de non-match

Les raisons publiques sont volontairement grossières (`no_sufficient_match`,
`independent_review_required` et `independent_blind_review_no_match`) et ne nomment ni
candidat ni cause. La raison technique plus précise reste dans le journal privé. Les
états publics révèlent néanmoins un bit de couverture générale ; cette fuite résiduelle
est inhérente à un oracle interactif et doit rester limitée par les cycles et l'isolation.

### Intégrité de la revue

L'indépendance du reviewer est déclarée et journalisée mais ne peut pas être prouvée par
le JSON lui-même. Elle exige des permissions OS et un opérateur réellement distinct. Les
catégories abstraites sont fournies par l'auteur du cas ; elles doivent rester neutres,
car le runner ne peut pas détecter automatiquement une description sémantiquement trop
révélatrice.

### Contamination et moteur

Les anciens runs sont restés inchangés, avec l'empreinte agrégée :
`3f05386f44f2bd467a550c401a135e93880dad9f1b5208e51d74c1b8d2b37a8a`.
La nouvelle campagne utilise une racine distincte. Chaque run extrait le moteur du commit
analytique, enregistre son engagement et refuse une altération du snapshot. Aucun
identifiant réel des cas DEV n'est présent dans le code ou les fixtures du matcher.

## Limites restantes

- l'identifiant exact du déploiement modèle et le niveau précis de raisonnement ne sont
  pas exposés par la session ;
- les métriques synthétiques ne garantissent pas le rappel sur toutes les formulations
  métier réelles ;
- le lexique générique devra être évalué sur d'autres corpus indépendants avant HOLDOUT ;
- la séparation reviewer/participant et la neutralité des descriptions abstraites
  restent des responsabilités opérateur ;
- aucun résultat DEV ne mesure la justesse physique sans scoring indépendant.

## Vérifications finales

- `pytest -q tests/test_physical_expertise_benchmark.py` : **24 passed** en 11,78 s ;
- `pytest -q` : **147 passed** en 20,49 s ;
- validation JSON du schéma de revue et du corpus : réussie ;
- recherche d'identifiants des vrais cas dans le matcher et ses fixtures : aucun résultat ;
- vérification d'intégrité après scellement : 18/18 runs ;
- diff des chemins analytiques protégés : vide ;
- revues aveugles non résolues : 0.
