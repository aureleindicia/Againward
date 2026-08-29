# Candidate V2 — revue adversariale

## Portée

Cette revue traite le code Candidate V2 comme s'il venait d'un tiers. Elle ne consulte ni
ground truth, ni payload oracle privé, ni score. La partie statique est réalisée sur le tag
`expert-benchmark-candidate-v2`. La partie expérimentale sera complétée après scellement
des 17 runs DEV valides ; aucun résultat DEV ne doit entraîner de retuning dans ce goal.

## Recherche de hardcoding et de fuite

- Aucun identifiant DEV n'apparaît dans le moteur, les fiches physiques ou le guide V2.
- L'anti-hardcoding teste explicitement les 18 identifiants dans ces nouveaux chemins.
- Le snapshot participant exclut rapports, tests, workspaces et anciens runs.
- Le matcher projette l'oracle vers identifiant neutre, concepts abstraits, termes de
  question et minimum de termes ; réponse, disponibilité, coût, rôle et payload restent
  exclus de la décision.
- Le paquet de revue aveugle ne contient que la demande participant, les identifiants
  neutres et les catégories abstraites.

**Limite.** La séparation reviewer/participant dépend encore des permissions OS et de la
discipline d'orchestration. Le même compte système pourrait techniquement violer la
séparation. Les journaux et empreintes détectent des altérations, pas toute lecture hors
protocole.

## Risque de sur-apprentissage des DEV

Les changements reprennent des classes d'erreurs fournies par la revue externe, donc un
biais de développement subsiste même sans vérité privée. Les protections sont : principes
transversaux, fixtures synthétiques différentes, absence de valeurs par cas, un seul rerun
après gel et futur HOLDOUT indépendant.

**Verdict provisoire.** Pas de hardcoding détecté, mais le DEV ne pourra jamais prouver la
généralisation de ces choix.

## Knowledge rules trop déterministes

Les fiches décrivent des mécanismes, prédictions et mesures, ce qui peut ancrer Codex. Elles
ne contiennent ni score causal, ni seuil de décision, ni conclusion automatique. Le
validateur accepte explicitement une cause non répertoriée.

**Risque restant.** Le langage naturel des fiches peut malgré tout rendre une cause listée
plus saillante qu'une cause inconnue. Un futur HOLDOUT doit mesurer ce biais.

## Faux sentiment de causalité et sur-confiance

Les calculateurs portent tous `decision: null` ou un champ décisionnel équivalent. Les
sorties avant/après indiquent qu'une baisse concomitante renforce sans prouver le
mécanisme. Le contrat exige preuve contraire, falsificateur et variable de service.

**Risque restant.** Une structure complète peut donner une apparence de rigueur à des
preuves faibles. La qualité physique du choix des variables reste une capacité de Codex,
pas une propriété validée par le schéma.

## Abstention, sécurité et économies

Le code n'assigne aucune décision benchmark, intervention ou économie. Les guides
distinguent signal, défaut, cause et économie récupérable. Les fiches nomment personne
compétente, risques et arrêts pour les tests terrain.

**Risque restant.** Ces garde-fous sont des contrats de raisonnement. Seul le rerun puis un
scoring indépendant peuvent vérifier qu'ils sont suivis dans les réponses réelles.

## Oracle : sur-révélation et sondage

- Un match automatique exige concept, termes, seuil et marge.
- Un apparent non-match structuré ne révèle rien : il crée une revue aveugle.
- Une revue non résolue bloque le cycle suivant et la finalisation.
- Une entrée déjà répondue devient un non-match sans seconde révélation.
- Le participant ne voit ni candidats, ni score, ni raison privée du matcher.

**Risques restants.** Le fallback limité à huit candidats favorise la confidentialité et
la charge de revue, mais peut perdre du rappel dans un grand oracle. Un participant peut
augmenter le nombre de revues avec des requêtes longues ; le nombre de cycles et le coût
oracle bornent ce sondage.

## Intégrité de la baseline et des anciens résultats

- tag V1 : `expert-benchmark-baseline-v1` →
  `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d` ;
- empreinte moteur V1 reproduite :
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a` ;
- tag V2 distinct : `expert-benchmark-candidate-v2` →
  `7acc43fc00007af87c459fd60cc89d972515c59a` ;
- aucun ancien run ou rapport baseline n'a été réécrit.

## AGENTICITY AUDIT

### 1. Si Codex était retiré, le nouveau code pourrait-il produire sensiblement la même investigation et le même diagnostic ?

**NON.** Le code peut charger des références, calculer des mesures et vérifier qu'un
différentiel écrit par quelqu'un est complet. Il ne choisit ni phénomène, ni variable, ni
fenêtre, ni hypothèse, ni test, ni cause, ni décision, ni intervention.

### 2. Le code Python mesure-t-il les phénomènes ou prend-il les décisions analytiques à la place de Codex ?

Il **mesure les phénomènes**. Les sorties exposent calculs, hypothèses, limites et champs
décisionnels nuls. Le seul ordre produit est une valeur d'information qualitative
consultative, explicitement dérogeable ou ignorable.

### 3. Une cause absente de la knowledge layer peut-elle encore être proposée et investiguée par Codex ?

**OUI.** Le guide et le contrat l'autorisent, et un test valide un différentiel contenant
une cause volontairement absente des fiches.

### 4. Codex peut-il choisir un protocole d'investigation non prévu par les workflows existants ?

**OUI.** Aucun séquenceur ne relie observation à outil, question ou diagnostic. Codex peut
ignorer les outils, écrire un calcul ad hoc, combiner les mesures ou proposer un nouveau
test.

### 5. Les nouveaux outils augmentent-ils la capacité d'action de Codex plutôt qu'ils ne réduisent son espace de décision ?

**OUI, avec un risque d'ancrage documenté.** Ils automatisent des comparaisons et bilans
nécessaires au raisonnement tout en laissant leurs résultats non décisionnels. Les fiches
et le classement consultatif rendent certaines options plus visibles ; le futur HOLDOUT
doit vérifier que cette visibilité ne ferme pas les hypothèses non listées.

## Verdict statique

Candidate V2 respecte l'architecture « Codex décide quoi mesurer, Python mesure, Codex
interprète ». La preuve expérimentale de non-régression, de sécurité et de meilleure
autonomie reste incomplète tant que les 17 runs DEV ne sont pas tous scellés et revus.
