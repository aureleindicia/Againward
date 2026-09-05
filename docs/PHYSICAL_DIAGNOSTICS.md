# Raisonnement diagnostique physique — Candidate V2

Ce document est une aide à l'enquête de Codex. Ce n'est ni un arbre de décision ni un
moteur de causes. Les fiches `knowledge/physical_diagnostics/` sont non exhaustives :
Codex peut et doit proposer une hypothèse, une variable ou un test absent lorsqu'il est
mieux adapté au dossier.

## Répartition des responsabilités

- Codex choisit le phénomène à investiguer, les hypothèses, les comparaisons, les outils,
  la mesure suivante, l'intervention et la décision finale.
- Python mesure, compare, vérifie les unités et expose les hypothèses/limites du calcul.
- La knowledge layer rappelle des mécanismes, variables, prédictions, tests et risques.
  Elle ne transforme jamais une observation en cause.

Une sortie Python avec `decision: null`, `analyst_decision: null` ou
`automatic_causal_conclusion: null` est volontairement incomplète : Codex doit
l'interpréter et peut la rejeter.

## Canevas interne d'une piste importante

Avant la conclusion, produire dans le scratch un objet de raisonnement contenant :

1. l'observation quantitative et ses limites ;
2. la chaîne `ENERGY INPUT → EQUIPMENT → PHYSICAL SERVICE → PROCESS OUTPUT` ;
3. `SERVICE_DEMAND_CHANGED?`, avec la variable métier manquante si la réponse est
   inconnue ;
4. `SYSTEM_EFFICIENCY_CHANGED?`, interprété seulement après avoir explicité la demande
   de service ;
5. `COMMAND` versus `ACTUAL STATE / FEEDBACK` pour tout système commandé ;
6. trois causes concurrentes lorsque le problème reste ouvert ;
7. pour chaque cause : mécanisme, preuves favorables, preuves contraires, prédictions
   observables, meilleure mesure discriminante, falsificateur et contraintes de sécurité.

Cette liste est un contrat de review, pas un ordre d'exécution. Codex reste libre de
commencer par n'importe quelle analyse, d'utiliser un outil inattendu, de revenir en
arrière et de changer totalement de direction.

## Choisir une mesure discriminante

Question de contrôle : « Quelle mesure réaliste sépare le mieux les hypothèses qui
restent ? »

Catégories consultatives, non obligatoires :

1. `DIRECT_PHYSICAL_DISCRIMINATOR` ;
2. `PROCESS_DISCRIMINATOR` ;
3. `CONTROL_STATE` ;
4. `MAINTENANCE_EVIDENCE` ;
5. `SUBMETERING` ;
6. `GENERIC_CONTEXT`.

L'ordre n'est pas une règle. Une mesure directe dangereuse ou indisponible peut être
moins appropriée qu'un journal de maintenance ; un sous-comptage existant peut être plus
simple qu'une nouvelle sonde. Codex documente effort, lieu, moment, personne compétente,
risque et prédiction propre à chaque hypothèse. Une seule demande minimale est préférée
lorsqu'elle suffit.

## Demande utile versus défaut

Une hausse de consommation peut correspondre à davantage de service utile. Avant de
parler de panne ou d'énergie récupérable, examiner explicitement production, recette,
masse, humidité, température initiale, pression/débit utile, occupation, air neuf,
sanitation, qualité et disponibilité selon le procédé.

- Si le service demandé a augmenté, quantifier éventuellement son coût mais ne pas le
  présenter comme défaut.
- Si le service est comparable et l'énergie spécifique augmente, il existe un signal
  d'efficacité à expliquer, pas encore une cause.
- Si la variable de service essentielle manque et qu'un fonctionnement légitime produit
  exactement le même signal qu'un défaut, l'existence du défaut peut rester
  `INSUFFICIENT_INFORMATION`.
- `ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` suppose que l'anormalité elle-même est démontrée,
  même si l'organe physique ne l'est pas.

Codex décide de la classe finale ; aucune fonction Python ne le fait à sa place.

## Commande versus état réel

Une consigne ou un planning correct ne prouve pas le fonctionnement physique : comparer,
si pertinent, ordre et feedback. Exemples : commande/position vanne, commande/position
registre, ordre/courant-vitesse moteur, consigne/pression mesurée, consigne/température,
programme/équipement actif.

Une discordance ne prouve pas automatiquement un actionneur défaillant : temporisation,
sécurité, override, capteur ou erreur de synchronisation sont des contre-explications.

## Abstention et intervention

Ne pas forcer une cause. Si les preuves sont indiscernables, demander le test minimal ou
s'abstenir. Toute intervention garde les préconditions, l'exécuteur compétent, les
risques, les conditions d'arrêt, le résultat attendu et la validation avant/après.
Une baisse après correction renforce une hypothèse, mais une concomitance seule ne prouve
pas nécessairement le mécanisme.


## Maximum justified claim et classes de décision

Règle : produire la conclusion la plus forte justifiée par les preuves disponibles,
ni plus forte ni plus faible. Le volume de données n'est pas la force probante : une
observation rare mais très discriminante peut suffire ; des données riches laissant des
explications concurrentes intactes imposent encore l'abstention.

- `NORMAL_OPERATION` : une opération légitime explique l'événement et aucune anomalie
  ne reste établie. Identifier pourquoi elle consomme n'en fait pas une cause anormale.
- `ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` : le phénomène anormal est établi, mais les
  mécanismes physiques concurrents ne sont pas encore départagés.
- `CAUSE_PROBABLE` / `CAUSE_CONFIRMED` : uniquement la cause d'un phénomène anormal.
- `INSUFFICIENT_INFORMATION` : une information absente bloque la décision requise, pas
  seulement une amélioration souhaitable de l'explication.
- `DATA_QUALITY_BLOCKER` : la qualité empêche de qualifier le phénomène lui-même.

Codex peut appliquer `validate_epistemic_decision_semantics` à ses déclarations. Ce
contrôle ne sélectionne aucune décision, cause, mesure ni intervention.
