# Candidate V2 — diagnostic et plan d'amélioration physique

## Périmètre et intégrité

Ce diagnostic précède toute modification analytique de Candidate V2. Il repose sur le
code et la documentation versionnés, les rapports non scorés de V1, les réponses finales
et les demandes participant déjà visibles. Il n'utilise ni ground truth, ni score privé,
ni payload follow-up non révélé. Les signaux du scoring externe fournis dans la
spécification sont traités comme des cibles génériques à tester, pas comme des réponses à
reproduire.

La baseline est intacte sous `expert-benchmark-baseline-v1` au commit
`6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`, empreinte moteur
`e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a`.
Candidate V2 part de la branche `candidate-v2`, checkpoint `ccf9e4e`.

## A — Faiblesses d'infrastructure

### Oracle : un non-match automatique reste trop définitif

`semantic-v2` protège bien la précision des révélations, mais une demande structurée peut
encore devenir `NO_MATCH` dès qu'aucun candidat ne franchit le seuil lexical de revue.
Cette issue confond « hors sujet » et « formulation physiquement pertinente que le
matcher ne sait pas relier ». La correction V2 doit conserver les matchs automatiques
très sûrs et envoyer le second cas à `PENDING_BLIND_ORACLE_REVIEW`. Seules une question
vague, hors sujet, non discriminante ou déjà répondue doit finir automatiquement sans
revue.

### Contrat participant incomplet pour le raisonnement physique

Le schéma V1 impose preuve favorable, preuve contraire et falsification, mais pas le
mécanisme, la prédiction observable, la chaîne énergétique, la demande de service, la
distinction commande/feedback ni la mesure discriminante. Une réponse conforme peut donc
rester électriquement descriptive et déléguer trop vite à un sous-comptage.

### Reproductibilité cognitive

Le runner fige le code et les preuves, mais l'identifiant exact du déploiement modèle et
le niveau de raisonnement n'étaient pas exposés. Il ne garantit pas non plus à lui seul
l'absence de mémoire entre sessions. Candidate V2 doit journaliser ce qui est disponible
sans prétendre résoudre une limite de l'orchestrateur.

## B — Faiblesses de données

- Un compteur général localise un phénomène dans le temps mais attribue rarement un
  service physique ou un équipement.
- Des totaux de production ne décrivent pas toujours la demande utile : recette, masse,
  humidité, température d'entrée, pression, débit, occupation ou qualité peuvent manquer.
- Une programmation décrit une commande voulue, pas l'état réel de la vanne, du registre,
  du moteur ou du service rendu.
- Une note de maintenance est une preuve contextuelle ; sans grandeur physique avant/après
  comparable, elle ne démontre pas la causalité.

V2 doit transformer ces lacunes en décisions explicites sur la prochaine mesure, pas en
collecte générique. L'absence de variable essentielle peut légitimement conduire à
`INSUFFICIENT_INFORMATION`.

## C — Faiblesses de calcul déterministe

La toolbox V1 couvre correctement les unités, l'intégration temporelle, les baselines
linéaires/temporelles, les résidus, dérives, ruptures, coûts et doubles comptages. Les
briques physiques transversales manquantes sont surtout :

1. comparaison avant/après normalisée et appariement de régimes comparables ;
2. énergie spécifique à service observé constant ;
3. commande versus feedback avec matrice de discordances et durées ;
4. durée de marche/duty cycle par régime ;
5. degré-heures paramétrable ;
6. test de décroissance de pression avec hypothèses explicites ;
7. bilans thermiques et récupération de chaleur avec unités et limites ;
8. aides pompe/ventilateur limitées à des scénarios documentés, jamais utilisées comme
   classifieur de cause.

Ces fonctions doivent retourner des mesures, hypothèses et avertissements, jamais une
cause automatique.

## D — Faiblesses de raisonnement

### La grandeur discriminante n'est pas choisie explicitement

V1 formule souvent un test valide, mais ne justifie pas toujours pourquoi il sépare mieux
les hypothèses qu'une mesure plus coûteuse. V2 doit comparer qualitativement la valeur
d'information de mesures candidates et privilégier un discriminant physique direct ou
procédé lorsque celui-ci est réaliste.

### La demande légitime n'est pas une étape obligatoire

La production est souvent contrôlée, mais « le service réellement demandé a-t-il
changé ? » n'est pas un verrou formel. V2 doit examiner `SERVICE_DEMAND_CHANGED?` avant
`SYSTEM_EFFICIENCY_CHANGED?`. Une hausse liée à un nouveau service utile n'est pas un
défaut, même si son coût est réel.

### Le différentiel n'est pas relié à une chaîne énergétique

Les causes peuvent rester au niveau du départ électrique. V2 doit suivre, lorsque
pertinent : entrée énergétique → équipement → service physique → sortie procédé. Si le
service ou la sortie n'est pas observé, la conclusion causale doit être limitée.

### Abstention à clarifier

`ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` convient lorsque le comportement anormal est démontré
mais pas son organe. `INSUFFICIENT_INFORMATION` est requis lorsque l'existence même d'un
défaut ne peut être séparée d'une demande légitime ou lorsque la variable procédé
essentielle manque. La présence d'un signal énergétique ne suffit pas à choisir la
première classe.

## E — Faiblesses de connaissance physique

La connaissance existe aujourd'hui principalement dans le raisonnement libre et quelques
documents. Elle n'est ni structurée ni facilement auditée par famille. V2 doit fournir
une petite couche locale pour froid, thermique/fours, air comprimé, moteurs-pompes-
ventilateurs, blanchisserie/eau chaude/vapeur et HVAC. Chaque fiche décrira variables de
demande, commande, feedback et environnement, mécanismes possibles, prédictions,
discriminants, tests peu coûteux, risques et compétences nécessaires.

Cette couche ne doit contenir aucune règle `symptôme => cause` ni score causal. Elle sert
à construire et falsifier un différentiel.

## F — Impossibilités physiques d'inférer la cause

Même un bon raisonnement ne peut pas toujours conclure :

- puissance électrique sans débit/pression ne sépare pas demande utile et rendement ;
- énergie thermique sans masse, humidité ou températures ne sépare pas recette et perte ;
- commande sans feedback ne prouve pas l'état réel ;
- compteur général sans service ni état ne localise pas l'équipement ;
- deux mécanismes produisant les mêmes observables restent indiscernables jusqu'au test
  approprié.

Dans ces situations, choisir la mesure minimale et s'abstenir est un résultat expert. V2
ne doit pas convertir cette impossibilité en faible confiance sur une cause devinée.

## Plan d'implémentation générique

1. Créer un contrat `PhysicalDifferential` auditable : mécanisme, preuves favorables et
   contraires, observables attendus, discriminant, falsificateur et sécurité.
2. Créer un contexte d'investigation imposant chaîne énergétique, demande de service,
   efficacité et commande/feedback.
3. Classer les mesures par valeur d'information qualitative, coût/effort, risque et
   disponibilité, avec dérogation motivée possible par Codex.
4. Ajouter la knowledge layer par famille, chargée et validée sans conclusion automatique.
5. Ajouter les calculateurs physiques transversaux justifiés ci-dessus.
6. Faire évoluer les briefs/templates et la validation pour que Codex utilise ce contrat,
   tout en conservant le rôle décisionnel de Codex.
7. Ajouter des fixtures synthétiques qui testent les principes et une recherche stricte
   des identifiants DEV dans les nouveaux fichiers analytiques et de connaissance.
8. Durcir l'oracle par revue aveugle des demandes structurées/pertinentes que le matcher
   automatique ne peut trancher.
9. Geler Candidate V2, exécuter une seule campagne DEV, exclure `a17` des agrégats en le
   marquant `EXCLUDED_PENDING_CASE_VALIDATION`, puis analyser uniquement les métriques
   observables sans retuning par cas.

## Critères de non-régression

- aucune économie récupérable sans preuve causale ;
- aucune intervention risquée sans compétence, préconditions et arrêt ;
- `NORMAL_OPERATION`, `INSUFFICIENT_INFORMATION` et `DATA_QUALITY_BLOCKER` restent des
  résultats normaux ;
- aucune règle ne choisit une cause à la place de Codex ;
- aucun identifiant, timestamp, valeur, machine ou réponse DEV n'entre dans le moteur ;
- le tag, le commit, les runs et les rapports V1 restent inchangés.
