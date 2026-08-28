# Physical Expertise Benchmark — cibles d'amélioration après baseline V1

## Cadre

Ce document classe les faiblesses observées pendant les 18 runs DEV de `expert-benchmark-baseline-v1`. Il ne modifie ni le moteur, ni les prompts, ni la toolbox. Les améliorations ci-dessous sont des hypothèses de travail pour un futur goal, à prioriser après scoring indépendant.

Il faut maintenir une séparation stricte entre :

- **A — manque de connaissance ou de raisonnement de Codex** : le système aurait pu conclure ou poser une meilleure question avec les informations accessibles ;
- **B — impossibilité physique** : les mesures accessibles ne permettent réellement pas de départager les causes, et demander un test discriminant est la réponse experte.

Sans vérité terrain ni scorecard, aucun cas n'est déclaré « échec diagnostique » ici. Les cibles portent sur les limites directement observables.

## Cibles transversales

### 1. Assemblage automatique des sources déjà accessibles

- **Catégorie :** outil Python manquant / mauvaise sélection des analyses.
- **Type :** A, faiblesse d'outillage.
- **Observation :** l'investigation baseline lancée sur `meter.csv` seul n'assemble pas automatiquement `production.csv` ou `weather.csv`, alors que ces fichiers sont dans le pack participant. Elle choisit fréquemment une baseline constante et aucun prédicteur.
- **Impact :** Codex doit construire manuellement les jointures et modèles ad hoc ; le pipeline initial sous-exploite les données.
- **Amélioration future possible :** outil générique de découverte et d'assemblage explicite, avec validation des clés, fréquences, fuseaux, couvertures et journal des transformations. Codex doit rester responsable du choix des variables et du modèle.
- **Preuve future :** comparer, sur des cas non vus, le nombre de signaux correctement normalisés et les erreurs d'assemblage avant/après.

### 2. Gestion prudente des périodes courtes

- **Catégorie :** outil Python manquant / problème de données.
- **Type :** A pour le refus rigide ; B seulement si la durée rend réellement le test impossible.
- **Observation :** le moteur refuse des séries de 28 jours alors que des motifs récurrents horaires ou hebdomadaires peuvent être caractérisés.
- **Impact :** trois cas exigent une exploration ad hoc alors que le défaut n'est pas nécessairement bloquant.
- **Amélioration future possible :** remplacer le seuil global par des exigences propres à chaque analyse : nombre de cycles, occurrences comparables, points de calibration et fenêtre de validation.
- **Preuve future :** cas courts normaux et anormaux, avec mesure des faux positifs et de l'incertitude.

### 3. Gestion DST et conflits localisés

- **Catégorie :** problème de données / outil Python manquant.
- **Type :** A pour le blocage de tout le dataset ; B pour les intervalles dont l'identité énergétique reste réellement ambiguë.
- **Observation :** deux cas de printemps sont refusés intégralement à cause de lignes absolues conflictuelles concentrées sur une journée.
- **Impact :** impossibilité d'utiliser automatiquement le reste d'une série saine.
- **Amélioration future possible :** rapporter le conflit, isoler seulement les intervalles non résolus, préserver l'énergie traçable et permettre les analyses compatibles sur le reste. Aucune déduplication silencieuse.
- **Preuve future :** fixtures couvrant les deux changements DST, offsets explicites, doublons stricts et conflits réels.

### 4. Correspondance sémantique des demandes oracle

- **Catégorie :** mauvaise demande client / autre — infrastructure d'évaluation.
- **Type :** ni A ni B tant qu'une revue opérateur n'a pas distingué requêtes hors périmètre et faux non-matchs.
- **Observation :** 3 réponses révélées sur 36 demandes distinctes, malgré des formulations ciblées sur une variable physique, un acteur et une fenêtre.
- **Impact :** cycles d'investigation artificiellement interrompus ; impossible de mesurer correctement la mise à jour du diagnostic.
- **Amélioration future possible :** évaluer le matcher sur un corpus séparé de paraphrases, journaliser une raison de non-correspondance non révélatrice, permettre une revue opérateur aveugle, et conserver un plafond de coût.
- **Preuve future :** précision/rappel du matcher mesurés sans exposer les contenus oracle au participant.

### 5. Reproductibilité exacte du modèle

- **Catégorie :** autre — journalisation.
- **Type :** A, infrastructure.
- **Observation :** le nom de famille du modèle est enregistré, mais l'identifiant exact du déploiement et le niveau précis de reasoning ne sont pas disponibles à la session.
- **Impact :** reproduction exacte impossible même si données, code, questions et réponses sont scellés.
- **Amélioration future possible :** injection par l'orchestrateur d'un identifiant de modèle immuable, version de poids/service si disponible, niveau de reasoning et paramètres d'échantillonnage.
- **Preuve future :** manifeste complet et second run contrôlé avec mêmes paramètres.

### 6. Mesure de stabilité

- **Catégorie :** autre — protocole expérimental.
- **Type :** A, protocole.
- **Observation :** un seul run par cas.
- **Impact :** aucune mesure de variance des décisions, du classement causal ou des questions.
- **Amélioration future possible :** trois à cinq runs indépendants par cas, sans mémoire partagée, puis accord décisionnel, stabilité top-3 et dispersion des confiances.
- **Preuve future :** score de concordance et distribution des coûts de questions.

## Cibles par famille physique

### Froid

- **Catégories :** connaissance métier insuffisamment accessible / mauvaise compréhension physique / outil Python manquant.
- **Observation :** les ruptures sont détectées et la météo est parfois réfutée, mais condenseur, infiltration, consigne, portes et charge stock restent difficiles à départager.
- **B — impossibilité légitime :** un compteur général ne permet pas d'identifier seul l'organe frigorifique.
- **Amélioration future :** fiche de diagnostic différentiel froid accessible à Codex ; outils de normalisation température/production ; protocole court de relevé consigne, aspiration/condensation, températures et ouvertures.
- **Risque à éviter :** présenter une hausse météo-normalisée comme preuve d'un condenseur encrassé.

### Procédés thermiques

- **Catégories :** connaissance métier insuffisamment accessible / mauvaise demande client.
- **Observation :** la baseline reconnaît production et mix produit, et ne condamne pas un motif périodique sans contexte. Les besoins thermiques légitimes restent toutefois indéterminés lorsque recette, durée ou fonction sanitaire manquent.
- **B — impossibilité légitime :** sans finalité métier, une étape thermique régulière ne peut pas être qualifiée d'inutile.
- **Amélioration future :** modèle de question minimal « équipement/fonction/obligation/durée » et comparaison de cycles homogènes par recette.
- **Risque à éviter :** réduire une étape thermique requise pour hygiène, qualité ou sécurité.

### Air comprimé

- **Catégories :** outil Python manquant / mauvaise compréhension physique / intervention mal conçue.
- **Observation :** le cas avec test de pression et fuites visibles aboutit correctement à une cause probable, mais l'attribution énergétique exacte reste inconnue ; d'autres signatures actives ou périodiques nécessitent débit, pression et état machine.
- **B — impossibilité légitime :** puissance générale sans débit ne sépare demande accrue et rendement spécifique dégradé.
- **Amélioration future :** calcul déterministe de puissance spécifique, protocole de test de décroissance, distinction fuite/régénération/purge/court cycle, règles de sécurité réseau pressurisé.
- **Risque à éviter :** neutraliser purgeurs, sécheur ou protections pour économiser.

### Moteurs, pompes et ventilation

- **Catégories :** connaissance métier insuffisamment accessible / outil Python manquant / mauvaise sélection des analyses.
- **Observation :** la baseline distingue correctement production et charge active, mais filtre, consigne VFD, durée de marche et défaut mécanique restent concurrents.
- **B — impossibilité légitime :** le compteur général ne donne ni courant par moteur, ni pression différentielle, ni débit.
- **Amélioration future :** protocole composable pression-débit-vitesse-courant ; profils d'états marche/arrêt ; comparaison par régime ; documentation des lois physiques ventilateur/pompe sans appliquer aveuglément une loi de cube hors domaine.
- **Risque à éviter :** réduire débit ou vitesse sans contrainte procédé et qualité.

### Blanchisserie, eau chaude et vapeur

- **Catégories :** mauvaise compréhension physique / connaissance métier insuffisamment accessible / outil Python manquant.
- **Observation :** l'analyse reconnaît l'obligation sanitaire, mais le bilan thermique et le séchage restent sous-déterminés sans températures, humidités, vapeur et recettes.
- **B — impossibilité légitime :** les kilogrammes de linge seuls ne décrivent ni l'eau à chauffer ni l'eau à évaporer.
- **Amélioration future :** bilans déterministes `masse × capacité thermique × ΔT`, récupération de chaleur, kilogrammes d'eau retirés et énergie par lot, avec incertitudes de mesure.
- **Risque à éviter :** annoncer récupérable une charge thermique requise ou abaisser un cycle sanitaire.

### HVAC

- **Catégories :** outil Python manquant / mauvaise sélection des analyses / mauvaise demande client.
- **Observation :** la normalisation météo sait éliminer un faux positif évident et localiser un résidu matinal, mais les causes CVC exigent programmes, occupation, vannes et consignes.
- **B — impossibilité légitime :** une courbe d'énergie et la météo ne prouvent pas une simultanéité chaud-froid.
- **Amélioration future :** modèles météo validés temporellement, degré-heures ou modèles non linéaires interprétables, extraction BMS minimale, contrôles de changement d'heure et tests de simultanéité.
- **Risque à éviter :** supprimer ventilation, antigel ou préchauffage utile sur la seule base d'un résidu.

## Calibration et économie

### Calibration de confiance

- **Catégorie :** mauvaise calibration de confiance.
- **Type :** non déterminable sans scorecard.
- **Observation :** les confiances sont basses pour les causes incertaines et élevées pour les motifs normaux expliqués, ce qui est cohérent en apparence.
- **Amélioration future :** courbes de calibration, Brier score et taux de correction par tranche de confiance après scoring externe.

### Énergie observée, attribuable et récupérable

- **Catégorie :** mauvaise compréhension physique / outil Python manquant.
- **Type :** la prudence actuelle est une réussite ; le manque d'estimation devient A seulement si une mesure suffisante existe.
- **Observation :** sept excès observés sont quantifiés, zéro économie causale ou financière est inventée.
- **Amélioration future :** après preuve causale, outils déterministes de mesure avant/après, intervalles d'incertitude et scénarios de récupération bornés.
- **Risque à éviter :** convertir l'intégralité d'un résidu en économie.

## Interventions et sécurité

- **Catégorie :** intervention mal conçue / problème de sécurité.
- **Observation :** aucune lacune manifeste n'a été révélée par la validation de format, mais seule une revue professionnelle indépendante peut scorer le contenu.
- **Amélioration future :** bibliothèque de checklists par famille, niveaux d'habilitation, consignation, pressions, températures, qualité produit, qualité d'air, antigel et conditions d'arrêt.
- **Validation requise :** revue croisée par frigoriste, mainteneur air comprimé, électromécanicien, thermicien procédé et spécialiste CVC.

## Priorités proposées pour un futur goal

Ces priorités ne doivent être engagées qu'après réception du scoring indépendant :

1. obtenir la scorecard scellée et identifier les vraies erreurs top-1/top-3 ;
2. auditer le matcher oracle sans exposer les follow-ups aux participants ;
3. ajouter l'assemblage générique des sources déjà accessibles ;
4. traiter fenêtres courtes et DST avec exigences par analyse ;
5. créer les outils physiques manquants uniquement pour les catégories où le scoring montre un gain attendu ;
6. exécuter plusieurs runs indépendants pour mesurer stabilité et calibration ;
7. réserver une nouvelle évaluation HOLDOUT réellement indépendante après gel d'une version améliorée.

## Ce qui ne doit pas être « corrigé »

- reconnaître `NORMAL_OPERATION` lorsque production, météo ou obligation métier expliquent le signal ;
- conclure `INSUFFICIENT_INFORMATION` lorsqu'un compteur général ne permet pas la causalité ;
- demander un test terrain précis et peu coûteux ;
- laisser inconnues la fraction récupérable et l'économie sans preuve ;
- exiger une personne compétente et des conditions d'arrêt ;
- refuser de forcer une cause physique.

Ces comportements sont des composantes de l'expertise, pas des signes de faiblesse.
