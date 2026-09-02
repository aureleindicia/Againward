# INDICIA Signal Intelligence Benchmark V2

## Question de recherche

Ce benchmark ne présume ni que le compteur central suffit, ni qu'il est insuffisant.
Il mesure la frontière empirique suivante :

> À partir d'un seul point de mesure électrique et d'un budget limité d'informations
> métier, jusqu'où le système INDICIA peut-il découvrir des signatures d'actifs,
> détecter un phénomène anormal, localiser un sous-système, quantifier une dépense
> énergétique, recommander une vérification sûre et anticiper un événement maintenance ?

Le benchmark sépare cinq affirmations qui ne doivent jamais être confondues :

1. un changement électrique est détectable ;
2. une signature latente est reproductible ;
3. cette signature peut être rattachée à un actif ou sous-système ;
4. un mécanisme physique peut être étayé ;
5. son évolution prédit un événement maintenance dans un horizon défini.

Une réussite à un niveau ne vaut pas preuve du niveau suivant.

## Architecture évaluée

```text
compteur central
      ↓
Signal Plane déterministe
      - unités et temps
      - agrégations multi-résolutions
      - événements et morphologies
      - signatures latentes
      - dérives et changements de régime
      ↓
Codex / couche agentique
      - choisit les pistes
      - relie signal, actif et métier
      - demande l'information minimale
      - cherche les explications concurrentes
      - décide de s'abstenir ou d'alerter
      ↓
Python
      - vérifie tous les chiffres
      - quantifie énergie, erreur et calibration
      ↓
action maintenance / optimisation vérifiable
```

Le benchmark compare au minimum :

- une réponse nulle pré-enregistrée ;
- un moteur quantitatif sans raisonnement agentique ;
- INDICIA complet ;
- plus tard, un ou plusieurs analystes humains soumis aux mêmes données.

## Niveaux de données

Chaque famille de scénario est rejouée avec plusieurs niveaux. La vérité physique reste
identique ; seules les données visibles changent.

| Niveau | Données visibles | Question testée |
|---|---|---|
| `L0_E15` | énergie active agrégée toutes les 15 minutes | que peut démontrer un export PME ordinaire ? |
| `L1_PQ1` | puissance active et réactive à la minute | les cycles et états grossiers deviennent-ils séparables ? |
| `L2_EDGE` | `L1` + événements électriques extraits au tableau central | les transitoires et morphologies permettent-ils une attribution fiable ? |

`L2_EDGE` reste un point de mesure unique. Il ne donne ni sous-compteur, ni identifiant
d'actif. Les caractéristiques événementielles peuvent provenir d'un analyseur central
ou d'un extracteur edge. La vérité cachée est volontairement plus riche que le produit :
elle sert uniquement à savoir si le produit a raison.

Le protocole est extensible vers `L3_WAVEFORM` pour des formes d'onde haute fréquence,
mais V2 n'invente pas un capteur que le dépôt ne sait pas encore ingérer.

## Généralisation

La généralisation est testée par mécanismes physiques et par secteurs :

- plasturgie : presses, séchage matière, refroidissement et air comprimé ;
- froid industriel : compresseurs, évaporateurs, dégivrages et manutention ;
- blanchisserie industrielle : laveuses, séchoirs, ventilation et auxiliaires thermiques.

Les familles de cas comprennent :

- fonctionnement normal difficile à distinguer d'une anomalie ;
- gaspillage énergétique sans panne ;
- dégradation progressive avec événement maintenance futur ;
- comportement de commande anormal ;
- artefact de compteur ou de données ;
- chevauchement de charges et actifs électriquement proches.

Un score moyen élevé ne suffit pas. Les résultats sont ventilés par secteur, niveau de
mesure, mécanisme et site tenu hors apprentissage. La pire strate et les abstentions sont
publiées.

## Vérité, fuite et temporalité

Un cas privé contient :

```text
case_id/
  case_manifest.json
  initial_client_pack/     # visible au participant
  followup_oracle/         # révélé uniquement sur demande admissible
  ground_truth/            # jamais visible avant verrouillage
```

La vérité privée contient notamment :

- les puissances ou énergies par actif utilisées par le simulateur ou constatées sur site ;
- les événements anormaux et normaux ;
- l'actif et le mécanisme de référence ;
- la date de début ;
- l'énergie excédentaire de référence ;
- l'événement maintenance ou l'absence d'événement après la date de coupure ;
- les actions acceptables et dangereuses ;
- le lien vers la famille physique appariée entre niveaux de mesure.

La donnée visible s'arrête à `analysis_cutoff`. La période est construite en jours
calendaires locaux, pas en durée UTC fixe : le passage heure d'hiver/heure d'été ne doit
jamais créer un jour visible sans contexte opérationnel. Toute intervention, alarme ou panne
postérieure utilisée pour noter la prévision reste cachée jusqu'à la finalisation.

Les engagements SHA-256 couvrent les trois arbres. Le manifeste de suite utilise des
chemins relatifs portables et embarque un snapshot privé autonome du générateur, du
runner, du scorer et du contrat. Le participant reçoit uniquement son
workspace. Un HOLDOUT n'est valide que si le modèle n'a accès ni au générateur, ni aux cas
privés, ni à une session ayant vu leur contenu.

## Réponse structurée

La réponse V2 force l'analyste à produire :

- une évaluation de la qualité et des limites de mesure ;
- des signatures latentes avec candidats actifs probabilisés ;
- des findings séparant observation, classe, mécanismes et énergie ;
- une évaluation principale avec probabilité d'anomalie ;
- une prévision datée ou une abstention explicite ;
- une action sûre et un plan avant/après ;
- les hypothèses concurrentes et éléments falsifiants.

Les probabilités sont notées comme des prédictions. Elles ne sont jamais interprétées
comme une confiance valide avant calibration sur plusieurs HOLDOUT.

## Scoring automatique verrouillé

Le scoring automatique intervient uniquement après verrouillage de la réponse. Il mesure :

| Composante | Points |
|---|---:|
| classe du phénomène principal | 15 |
| probabilité d'anomalie (score de Brier) | 10 |
| actif top-1 / top-3 ou abstention correcte | 15 |
| mécanisme top-1 / top-3 | 15 |
| localisation temporelle | 10 |
| quantification de l'énergie excédentaire | 10 |
| pronostic post-coupure ou abstention | 15 |
| action et sécurité structurées | 5 |
| traçabilité des preuves | 5 |
| **Total** | **100** |

Le score composite mesure également les abstentions correctes, mais il ne définit pas une
capacité. Le rapport expose donc des gates séparés, avec `non applicable` plutôt que
`réussi` lorsqu'une vérité ne permet pas de tester la couche :

- détection binaire ;
- classification du phénomène ;
- signature reproductible ;
- attribution d'actif ;
- mécanisme physique ;
- quantification de l'excès ;
- pronostic d'un outcome futur ;
- capacité complète.

Une signature peut passer sans nommer le bon actif. Une attribution ne passe pas par
simple abstention sur un cas sans cible. Le pronostic n'est évalué comme capacité que sur
les outcomes positifs ; sa spécificité sur les négatifs reste visible dans la calibration.

Le rapport de suite ajoute, sans les masquer dans une moyenne :

- précision, rappel et F1 des alertes ;
- Brier et erreur de calibration ;
- précision et couverture au seuil 0,90 ;
- top-1 et top-3 d'actif et de mécanisme ;
- erreur relative d'énergie ;
- délai d'alerte avant événement ;
- faux positifs sur fonctionnement normal ;
- résultats par niveau et secteur ;
- frontière minimale de données par famille appariée ;
- écart entre moteur seul et architecture agentique.

Un seuil à 90 % n'est promu que si sa précision observée et son intervalle d'incertitude
sont publiés avec le nombre d'alertes concernées. Une couverture nulle ne constitue pas
une réussite. Les intervalles globaux sont supprimés dès que des niveaux ou variantes
partagent une même réalisation physique. Ils ne sont calculés que dans les strates avec
une carte par famille indépendante.

## Conditions de réussite

Le benchmark ne déclare jamais le produit validé sur les seuls cas synthétiques. Il peut :

1. réfuter une architecture ou un niveau de mesure ;
2. démontrer que le protocole et le raisonnement fonctionnent sur vérité contrôlée ;
3. sélectionner les hypothèses à tester sur le terrain ;
4. définir la spécification minimale du capteur central.

La promotion vers une revendication client exige ensuite des cas historiques confirmés,
puis des cas prospectifs multi-sites avec interventions réellement observées.

## Contrôles quantitatifs actuels

Le protocole `2.3` possède deux contrôles exécutables :

- `PRE_REGISTERED_NULL_V2`, qui mesure le plancher d'abstention ;
- `detection-and-motif-v2`, limité à la détection candidate, la quantification prudente
  et la découverte de motifs L2.

Le second utilise une baseline production+température pour décider qu'un changement est
candidat, une baseline production séparée pour estimer l'énergie, et la morphologie
P/Q/ramp/inrush/harmoniques pour regrouper les événements. Il laisse volontairement
vides l'attribution principale et le mécanisme, et s'abstient toujours de pronostic.

Les résultats synthétiques complets et les falsifications sont publiés dans
`reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_COMPLETION_AUDIT.md` et
`reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_RESULTS.json`. Aucun chiffre de ces fichiers
ne doit être présenté comme validation terrain.

## Commandes

Générer un corpus privé reproductible :

```bash
python run_signal_intelligence_benchmark.py generate-suite \
  /chemin/prive/indicia_signal_v2 \
  --profile full \
  --seed 260902 \
  --replicates 1
```

`--replicates 1` produit le corpus Termux de référence. Une campagne de calibration
plus puissante peut utiliser plusieurs réalisations indépendantes (`--replicates 3` ou
plus) sur une machine disposant du stockage nécessaire. Les répétitions d'une même
famille reçoivent des graines et identifiants distincts ; les trois niveaux d'une même
répétition restent une ablation appariée et ne sont jamais comptés comme trois vérités
indépendantes.

Valider un cas sans lire sa vérité :

```bash
python run_signal_intelligence_benchmark.py validate-case \
  /chemin/prive/indicia_signal_v2/cases/HOLDOUT/CASE_ID
```

Préparer un run isolé :

```bash
python run_signal_intelligence_benchmark.py prepare \
  /chemin/prive/indicia_signal_v2/cases/HOLDOUT/CASE_ID \
  /chemin/prive/runs \
  --repository . \
  --system-ref COMMIT_FIGE \
  --model MODELE_EXACT \
  --reasoning-effort NIVEAU_EXACT \
  --variant AGENTIC
```

Les demandes d'informations utilisent la commande `ask` du runner V2. La réponse finale
est écrite dans `participant_workspace/output/response.json`.

Finaliser, scorer et agréger :

```bash
python run_signal_intelligence_benchmark.py finalize RUN RESPONSE --repository .
python run_signal_intelligence_benchmark.py score RUN CASE
python run_signal_intelligence_benchmark.py aggregate DOSSIER_DE_SCORES
```

`score` lit la vérité uniquement après finalisation et écrit dans `private_run/`. Aucun
score ni extrait de vérité n'est recopié dans le workspace participant.

Auditer une suite privée, puis exécuter les contrôles complets :

```bash
python run_signal_intelligence_benchmark.py audit-suite SUITE --output SUITE/PRIVATE_SUITE_AUDIT.json
python run_signal_intelligence_benchmark.py run-null-suite SUITE RUNS/null --repository .
python run_signal_intelligence_benchmark.py run-deterministic-suite \
  SUITE RUNS/deterministic --repository .
python run_signal_intelligence_benchmark.py aggregate RUNS --output RUNS/COMBINED_AGGREGATE.json
```

Ablation reproductible d'une méthode sur un seul niveau :

```bash
python run_signal_intelligence_benchmark.py run-deterministic-suite \
  SUITE RUNS/ablation \
  --repository . \
  --tier L0_E15 \
  --detection-method production_temperature \
  --energy-method production \
  --signature-method morphology
```
