# Energy Analyzer — Instructions permanentes pour Codex

Le projet `energy-analyzer` existe déjà et possède une première version fonctionnelle.

NE PAS repartir de zéro.

Commencer par inspecter intégralement le dépôt actuel, comprendre l’architecture, exécuter les scripts et les tests, reproduire les rapports existants et identifier ce qui doit être conservé, corrigé ou restructuré.

Le développement se fait principalement depuis :

- Android ;
- Termux ;
- Codex ;
- Python ;
- stockage local ;
- ressources CPU/RAM limitées.

Le projet doit rester léger, local-first, robuste et réellement utilisable dans cet environnement.

---

## 1. Vision fondamentale

L’objectif n’est PAS de construire un logiciel classique qui transforme automatiquement :

```text
CSV → règles prédéfinies → rapport
```

L’objectif est de construire un **environnement spécialisé permettant à Codex d’agir comme analyste énergétique industriel augmenté par des outils quantitatifs fiables**.

Codex doit rester une composante centrale du processus d’analyse.

Architecture conceptuelle :

```text
DONNÉES BRUTES
      ↓
validation / nettoyage / normalisation
      ↓
données fiables et structurées
      ↓

CODEX — PHASE 1 : EXPLORATION
- comprend les données
- observe les comportements
- cherche des signaux
- formule des hypothèses
- décide quoi investiguer
      ↓
hypothèses et questions
      ↓

OUTILS PYTHON DÉTERMINISTES
- statistiques
- baselines
- régressions
- comparaisons
- coûts
- graphiques
- énergie / puissance
      ↓
résultats vérifiables
      ↓

CODEX — PHASE 2 : CRITIQUE
- interprète les résultats
- cherche des contre-explications
- rejette les pistes faibles
- demande de nouveaux tests
      ↓
nouveaux calculs si nécessaire
      ↓
OUTILS PYTHON
      ↓
résultats complémentaires
      ↓

CODEX — PHASE 3 : REVIEW FINAL
- cherche les failles
- vérifie la cohérence globale
- élimine les doubles comptages
- juge le niveau de confiance
- sélectionne les conclusions
      ↓

CODEX — PHASE 4 : SYNTHÈSE
- construit le rapport final
- explique les résultats
- distingue faits / hypothèses
- propose les vérifications
      ↓
REVUE HUMAINE
```

---

## 2. Principe central

La répartition des responsabilités doit rester claire.

### Codex

Codex est responsable de :

- comprendre la structure d’un nouveau dataset ;
- déterminer quelles analyses sont pertinentes ;
- explorer les données ;
- identifier des comportements intéressants ;
- formuler des hypothèses ;
- choisir les outils appropriés ;
- créer une analyse ad hoc lorsqu’aucun outil existant ne suffit ;
- interpréter les sorties ;
- chercher des explications alternatives ;
- décider quelles pistes approfondir ;
- rejeter les pistes faibles ;
- demander de nouveaux calculs ;
- évaluer les limites ;
- hiérarchiser les opportunités ;
- construire la synthèse finale.

### Python et les outils déterministes

Ils sont responsables de :

- calculer ;
- mesurer ;
- agréger ;
- convertir les unités ;
- ajuster les baselines ;
- effectuer les régressions ;
- comparer les périodes ;
- calculer les statistiques ;
- quantifier les anomalies ;
- calculer les kWh ;
- calculer les coûts ;
- produire les graphiques ;
- assurer la reproductibilité.

Principe :

```text
Codex décide quoi mesurer.
Python mesure.
Codex interprète.
Python vérifie.
Codex conclut.
```

---

## 3. Ne pas transformer Codex en simple commentateur

Une architecture où Codex exécute :

```bash
python analyze.py client.csv
```

puis reformule un rapport déjà entièrement produit par le logiciel est insuffisante.

Le pipeline automatique peut générer des signaux de départ.

Il ne doit pas remplacer l’investigation.

Codex doit pouvoir réellement explorer chaque dataset différemment.

Exemple attendu :

```text
Observation :
la consommation augmente vers 05:45 les jours ouvrés.

Hypothèse H01 :
certains équipements démarrent avant la production.

Test :
comparer puissance et production entre 05:30 et 06:30.

Résultat :
la production reste nulle jusqu’à 06:15.

Test supplémentaire :
vérifier si le phénomène est récurrent.

Résultat :
présent sur 91 % des jours ouvrés.

Contre-hypothèse :
cela pourrait être expliqué par la température.

Test :
contrôler la relation avec la température extérieure.

Résultat :
aucune relation suffisante pour expliquer l’écart.

Quantification :
calcul de l’énergie excédentaire et de son coût.

Conclusion :
surconsommation pré-production récurrente confirmée.

Limite :
la cause physique exacte ne peut pas être déterminée avec les données disponibles.
```

C’est ce comportement qui constitue le cœur du produit.

---

## 4. Boucle agentique d’investigation

Pour chaque piste importante, suivre :

```text
OBSERVATION
    ↓
HYPOTHÈSE
    ↓
TEST QUANTITATIF
    ↓
RÉSULTAT
    ↓
CONTRE-HYPOTHÈSE
    ↓
NOUVEAU TEST
    ↓
RÉSULTAT
    ↓
QUANTIFICATION
    ↓
CONFIANCE
    ↓
CONSERVER OU REJETER
```

Une conclusion ne doit pas être conservée uniquement parce qu’elle paraît intuitive.

---

## 5. Codex doit être contradictoire avec lui-même

Lorsqu’un résultat intéressant apparaît, chercher activement pourquoi il pourrait être trompeur.

Questions typiques :

- La production a-t-elle changé ?
- La température explique-t-elle l’écart ?
- Les horaires ont-ils changé ?
- La qualité des données est-elle différente ?
- Le mix produit a-t-il changé ?
- Le signal existe-t-il sur des périodes comparables ?
- Est-ce seulement un outlier ?
- Est-ce un changement permanent ?
- L’effet disparaît-il après normalisation par la production ?
- Est-ce une conséquence normale du procédé ?

Le but n’est pas de confirmer les premières hypothèses.

Le but est d’essayer de les falsifier.

---

## 6. Passage de review final obligatoire

Avant de produire le rapport final, effectuer une nouvelle passe indépendante sur les principales conclusions.

Pour chaque opportunité candidate :

1. relire les preuves ;
2. vérifier les calculs utilisés ;
3. rechercher un double comptage ;
4. rechercher une explication alternative non testée ;
5. vérifier la qualité des données concernées ;
6. vérifier la robustesse de la baseline ;
7. vérifier que la causalité n’est pas affirmée sans preuve ;
8. vérifier que la projection annuelle est raisonnable ;
9. vérifier que l’économie potentielle n’est pas confondue avec la surconsommation ;
10. réduire la confiance ou rejeter la conclusion si nécessaire.

Question obligatoire avant validation :

```text
Quelle est la meilleure raison de penser que cette conclusion pourrait être fausse ?
```

Si une réponse crédible apparaît et peut être testée, effectuer le test avant de conclure.

---

## 7. Le dernier passage Codex ne peut pas modifier librement les chiffres

Codex peut :

- sélectionner les chiffres pertinents ;
- expliquer ;
- comparer ;
- demander un recalcul ;
- remettre en question un résultat.

Codex ne doit PAS :

- inventer une valeur ;
- arrondir arbitrairement un résultat critique ;
- modifier un résultat parce qu’il semble étrange ;
- produire lui-même un coût estimé de tête ;
- fabriquer un intervalle de confiance ;
- remplacer un calcul déterministe.

Si un chiffre semble faux :

```text
Codex → demande un nouveau calcul Python.
```

Pas :

```text
Codex → corrige mentalement le chiffre.
```

---

## 8. Niveau d’exigence

Être sévère avec les résultats et avec le code.

À chaque étape importante, demander :

- Est-ce mathématiquement correct ?
- Les unités sont-elles correctes ?
- Les données permettent-elles réellement cette conclusion ?
- Existe-t-il un faux positif évident ?
- Quelle hypothèse est implicite ?
- Cette hypothèse est-elle documentée ?
- Le résultat est-il reproductible ?
- Est-il possible de retracer son origine ?
- Un ingénieur énergie pourrait-il comprendre la méthode ?
- Qu’est-ce qui pourrait faire perdre confiance dans ce résultat ?
- Est-ce que cette fonction apporte réellement de la valeur ?
- Codex réfléchit-il réellement ou le logiciel décide-t-il tout à sa place ?

Ne pas conserver une implémentation médiocre uniquement parce qu’elle fonctionne.

---

## 9. Auditer le projet existant en premier

Avant toute extension :

- inspecter l’arborescence ;
- lire tous les modules importants ;
- examiner les dépendances ;
- lancer les tests ;
- exécuter le programme ;
- reproduire le rapport actuel ;
- vérifier les calculs manuellement sur quelques cas simples.

Priorités absolues :

```text
timestamps
kW / kWh
intervalles
agrégations
coûts
production
intensité énergétique
période couverte
```

Corriger les erreurs pouvant rendre les résultats numériquement faux avant de poursuivre.

---

## 10. Unités — aucune ambiguïté acceptable

Gérer correctement :

```text
W
kW
MW

Wh
kWh
MWh
```

Exemple :

```text
100 kW pendant 15 minutes
=
25 kWh
```

Mais :

```text
25 kWh enregistrés sur un intervalle
```

représentent déjà une énergie.

Ne pas les réintégrer.

Créer une représentation interne claire permettant de distinguer :

```text
POWER
ENERGY_PER_INTERVAL
CUMULATIVE_ENERGY
```

Si le type est ambigu :

```text
refuser l’analyse
```

et expliquer comment le préciser.

---

## 11. Dataset synthétique haute fréquence

Le dataset mensuel existant peut rester comme fixture simple.

Mais il ne suffit pas pour tester sérieusement l’analyse agentique.

Créer un dataset reproductible à :

```text
15 minutes
```

sur environ :

```text
90 à 180 jours
```

si les performances Termux restent satisfaisantes.

Colonnes minimales :

```text
timestamp
power_kw OU energy_kwh
production
production_active
```

Variables facultatives utiles :

```text
outside_temperature
shift
machine_id
product_type
```

---

## 12. Simulation industrielle plausible

Le générateur doit intégrer :

- charge incompressible ;
- charge variable liée à la production ;
- horaires de fonctionnement ;
- nuits ;
- week-ends ;
- shifts ;
- variabilité naturelle ;
- relation énergie-production ;
- éventuellement relation température-énergie.

Une forme de base peut être :

```text
consommation =
charge_fixe
+
coefficient_production × production
+
effet_température
+
bruit
```

avec des comportements plus riches lorsque nécessaire.

---

## 13. Ground truth

Injecter volontairement des événements connus.

Au minimum :

### anomalie nocturne
Équipement simulé restant actif.

### anomalie week-end
Charge inutile récurrente.

### dérive progressive
Consommation augmentant lentement.

### pic ponctuel
Hausse forte de courte durée.

### baisse d’efficacité
Production similaire mais consommation supérieure.

### changement permanent de baseline

### problèmes de données
- trous ;
- doublons ;
- valeurs manquantes ;
- timestamps irréguliers ;
- valeurs impossibles.

Stocker :

```text
anomaly_id
type
start
end
magnitude
expected_energy_impact
```

Le moteur ne doit pas connaître la ground truth pendant l’analyse.

Elle sert uniquement à la validation.

---

## 14. Mesurer les performances

Comparer les événements trouvés aux événements injectés.

Calculer lorsque pertinent :

```text
true positives
false positives
false negatives
precision
recall
F1
```

Comparer les événements temporels, pas uniquement les lignes individuelles.

Ne pas optimiser artificiellement les paramètres jusqu’à obtenir 100 % sur un unique dataset.

Créer plusieurs seeds/scénarios de validation.

---

## 15. Signaux automatiques = points de départ

Le pipeline peut automatiquement relever :

- pics ;
- anomalies statistiques ;
- dérives ;
- variations nocturnes ;
- changements de baseline ;
- variations d’intensité ;
- différences semaine/week-end.

Mais ces éléments doivent être considérés comme :

```text
CANDIDATE SIGNAL
```

et non :

```text
CONFIRMED OPPORTUNITY
```

Codex décide ensuite lesquels méritent investigation.

---

## 16. Boîte à outils Codex

Construire progressivement des fonctions simples et composables.

Exemples conceptuels :

```text
inspect_dataset()
validate_dataset()
describe_period()
detect_frequency()

summarize_energy()
summarize_production()

extract_period()
compare_periods()
compare_similar_days()
compare_shifts()

daily_profile()
weekly_profile()

estimate_baseload()

fit_time_baseline()
fit_production_baseline()
fit_temperature_baseline()

calculate_residuals()

detect_outliers()
detect_drift()
detect_level_shift()
detect_change_points()

group_events()

energy_vs_production()
energy_vs_temperature()

calculate_excess_energy()
calculate_cost()
annualize_effect()

plot_timeseries()
plot_baseline()
plot_relationship()
```

Ne pas nécessairement reprendre ces noms.

Conserver une API cohérente et intuitive.

---

## 17. Outils faciles à découvrir

Créer :

```text
docs/ANALYSIS_TOOLS.md
```

Chaque outil important doit indiquer :

```text
objectif
entrée
sortie
hypothèses
limitations
exemple
```

Codex doit pouvoir consulter rapidement cette documentation avant de réinventer un outil existant.

---

## 18. Espace d’exploration

Créer un espace dédié :

```text
workspace/
```

ou :

```text
scratch/
```

Codex peut y créer :

- scripts temporaires ;
- analyses spécifiques ;
- graphiques ;
- expériences ;
- comparaisons.

Un script expérimental n’entre pas automatiquement dans la stack principale.

Processus :

```text
expérience
↓
résultat intéressant
↓
validation
↓
généralisation éventuelle
↓
tests
↓
intégration
```

---

## 19. Le système doit apprendre en outils, pas en données clients

Une analyse nouvelle utile peut devenir :

- fonction ;
- méthodologie ;
- test ;
- template ;
- outil réutilisable.

Mais ne jamais réutiliser les données confidentielles d’un client pour un autre.

L’amélioration cumulative doit venir de la stack analytique.

---

## 20. Baselines

Développer plusieurs baselines interprétables.

### baseline temporelle

Selon :

```text
heure
jour de semaine
activité
```

### rolling median

### baseline inactive/active

### relation production-énergie

```text
energy =
intercept +
coefficient × production
```

### relation production + température

si données suffisantes.

Codex doit pouvoir comparer plusieurs baselines et choisir celle qui semble la plus appropriée au contexte.

---

## 21. Validation des baselines

Mesurer notamment :

```text
MAE
RMSE
R²
MAPE
```

lorsque approprié.

Ne pas utiliser MAPE lorsque les valeurs proches de zéro rendent la métrique trompeuse.

Utiliser validation temporelle :

```text
passé → calibration
futur → validation
```

Éviter les fuites d’information.

---

## 22. Consommation hors production

Toujours distinguer :

```text
consommation hors production
```

de :

```text
consommation inutile
```

Estimer :

```text
consommation observée
baseline incompressible
excès potentiel
```

Utiliser des méthodes prudentes.

Exemple :

```text
Consommation inactive :
35 kW

Charge incompressible estimée :
22 kW

Écart :
13 kW

Conclusion :
13 kW potentiellement excédentaires,
à vérifier opérationnellement.
```

---

## 23. Charge de base

Ne pas prendre naïvement le minimum absolu.

Comparer des méthodes robustes :

- quantiles bas ;
- médiane des périodes les plus économes ;
- longues périodes d’arrêt ;
- nuits historiquement efficaces.

Codex peut comparer les estimations et rechercher leur stabilité.

---

## 24. Intensité énergétique

Calculer :

```text
kWh / unité
```

mais contextualiser.

Une faible production peut mécaniquement entraîner un mauvais ratio à cause des charges fixes.

Comparer :

```text
production comparable
→ consommation comparable
```

plutôt que d’utiliser uniquement un seuil absolu de kWh/unité.

---

## 25. Dérives

Rechercher explicitement :

- hausse progressive ;
- changement durable ;
- dégradation de l’efficacité ;
- changement de comportement horaire ;
- variation de la charge de base.

Une dérive faible mais persistante peut coûter davantage qu’un pic spectaculaire.

---

## 26. Pics

Un pic n’est pas automatiquement un problème.

Pour chaque pic candidat, comparer :

```text
heure
jour
production
démarrage
durée
historique comparable
```

Éviter une règle simpliste du type :

```text
>150 % moyenne = anomalie
```

comme conclusion finale.

---

## 27. Événements

Regrouper les points temporels proches.

Un événement doit pouvoir contenir :

```text
event_id
start
end
duration

observed_energy
expected_energy
excess_energy

cost

severity
confidence

supporting_methods
related_hypotheses
```

---

## 28. Sévérité ≠ confiance

### Sévérité

Mesure l’impact potentiel :

- énergie ;
- coût ;
- durée ;
- récurrence.

### Confiance

Mesure la solidité de l’interprétation :

- qualité des données ;
- répétition ;
- force statistique ;
- stabilité de la baseline ;
- explications alternatives ;
- cohérence entre méthodes.

Un événement peut avoir :

```text
Sévérité : élevée
Confiance : faible
```

---

## 29. Coûts

Supporter au minimum :

```bash
--price-per-kwh
```

Plus tard seulement :

- heures pleines/heures creuses ;
- tarifs dynamiques ;
- coûts de pointe ;
- contrats complexes.

Tous les coûts doivent provenir d’un calcul déterministe.

---

## 30. Surconsommation ≠ économie

Toujours distinguer :

```text
surconsommation observée
```

et :

```text
économie effectivement récupérable
```

Une surconsommation apparente peut être nécessaire.

Lorsque l’économie réelle est inconnue, produire des scénarios prudents ou simplement la valeur de la surconsommation sans prétendre qu’elle est récupérable.

---

## 31. Projections annuelles

Ne pas annualiser naïvement un événement ponctuel.

Avant projection :

- mesurer la récurrence ;
- vérifier la représentativité de la période ;
- tenir compte des jours ouvrés ;
- tenir compte des périodes de production ;
- signaler l’incertitude.

---

## 32. Double comptage

C’est une priorité critique.

Le même événement peut apparaître comme :

```text
anomalie nocturne
+
consommation inactive
+
dérive baseline
+
mauvaise intensité
```

Ne jamais additionner ces économies plusieurs fois.

Créer un système permettant de détecter les chevauchements temporels et énergétiques.

Le passage final de Codex doit également vérifier ce problème.

---

## 33. Qualité des données

Avant toute investigation avancée, produire :

```text
nombre de lignes
période
fréquence
couverture
trous
doublons
valeurs manquantes
timestamps invalides
valeurs impossibles
changements de fréquence
outliers
```

La qualité des données doit limiter les analyses possibles.

Exemple :

```text
données mensuelles
→ aucune conclusion sur les horaires nocturnes
```

---

## 34. Aucune correction silencieuse

Tracer toute :

- suppression ;
- interpolation ;
- déduplication ;
- conversion ;
- normalisation.

Exemple :

```text
37 doublons détectés

35 strictement identiques supprimés

2 conflictuels conservés et signalés
```

---

## 35. Journal d’investigation

Créer un fichier structuré :

```text
investigation.json
```

et éventuellement une version Markdown.

Pour chaque piste :

```text
hypothesis_id
observation
hypothesis
tests_requested
results
alternative_explanations
decision
confidence
```

Exemple :

```text
H07

Observation :
hausse nocturne depuis le 14 mars.

Hypothèse :
augmentation de charge inactive.

Test :
comparaison avec 30 nuits historiques.

Résultat :
+27 %.

Alternative :
température extérieure.

Test :
régression température.

Résultat :
effet insuffisant.

Décision :
conserver.

Confiance :
élevée.
```

---

## 36. Codex peut rejeter une hypothèse

C’est essentiel.

Exemple :

```text
H11
Les vendredis semblent consommer davantage.

Résultat :
+1,3 %.

Variabilité historique :
±4,8 %.

Décision :
hypothèse rejetée.
```

Ne pas essayer de transformer toutes les observations en économies.

---

## 37. Fin d’une investigation

Une investigation importante est considérée terminée uniquement si :

- l’observation est définie ;
- l’hypothèse est explicite ;
- au moins un test a été effectué ;
- le résultat est quantifié ;
- une explication alternative a été examinée ;
- les limites sont identifiées ;
- une décision conserver/rejeter existe ;
- le niveau de confiance est justifié.

---

## 38. Review adversariale finale

Après les investigations et avant le rapport :

prendre les principales conclusions comme si elles avaient été produites par quelqu’un d’autre et chercher activement à les démonter.

Questions :

- Est-ce un artefact de données ?
- La baseline est-elle mauvaise ?
- La production suffit-elle à expliquer l’écart ?
- La température suffit-elle à l’expliquer ?
- La projection annuelle est-elle abusive ?
- Y a-t-il double comptage ?
- La causalité est-elle inventée ?
- Le signal est-il suffisamment récurrent ?
- Le coût correspond-il réellement à l’énergie calculée ?
- La confiance affichée est-elle trop élevée ?

Effectuer de nouveaux tests lorsque nécessaire.

---

## 39. Codex à la fin de la boucle

Après la review contradictoire, Codex doit décider :

```text
CONFIRMÉ
À CONSERVER AVEC RÉSERVES
INSUFFISAMMENT ÉTAYÉ
REJETÉ
```

Seuls :

```text
CONFIRMÉ
```

et éventuellement :

```text
À CONSERVER AVEC RÉSERVES
```

doivent apparaître parmi les conclusions principales du rapport.

---

## 40. Synthèse finale par Codex

Codex doit enfin transformer les résultats validés en document compréhensible par un dirigeant ou responsable industriel.

Il doit :

- hiérarchiser ;
- contextualiser ;
- expliquer ;
- distinguer faits et hypothèses ;
- indiquer l’incertitude ;
- proposer des vérifications concrètes ;
- éviter le jargon inutile.

Il ne doit pas simplement recopier `analysis.json`.

---

## 41. Format d’une opportunité

Exemple cible :

```text
OPPORTUNITÉ #1
Surconsommation avant démarrage

OBSERVATION
La puissance moyenne entre 05:45 et 06:15
est supérieure de 18,4 kW à la baseline.

RÉCURRENCE
Présente sur 91 % des jours ouvrés étudiés.

VÉRIFICATIONS
Production :
encore nulle pendant cette période.

Température :
n’explique pas l’écart observé.

Historique :
comportement absent durant la période de référence.

SURCONSOMMATION
4 620 kWh sur la période.

COÛT ASSOCIÉ
808 €.

PROJECTION ANNUELLE
3 600–4 500 €,
sous les hypothèses indiquées.

CONFIANCE
Élevée.

CE QUE LES DONNÉES DÉMONTRENT
Une charge supplémentaire récurrente existe
avant le démarrage de la production.

CE QUE LES DONNÉES NE DÉMONTRENT PAS
L’équipement responsable.

À VÉRIFIER
Équipements démarrés avant production :
compresseurs, ventilation, pompes, etc.
```

---

## 42. Rapport final

Structure recommandée :

```text
1. Résumé exécutif
2. Données analysées
3. Qualité des données
4. Profil énergétique
5. Baseline
6. Investigations réalisées
7. Opportunités confirmées
8. Efficacité énergétique
9. Impact économique
10. Opportunités nécessitant vérification
11. Hypothèses rejetées importantes
12. Recommandations
13. Limites
14. Méthodologie
```

Le client n’a pas besoin de voir toutes les explorations.

Conserver le détail complet dans le journal technique.

---

## 43. Résultats structurés

Créer une représentation commune :

```text
AnalysisResult
```

permettant de générer :

```text
analysis.json
investigation.json
report.md
report.html
charts/
```

Les formats ne doivent pas recalculer indépendamment les métriques.

---

## 44. Graphiques

Créer uniquement des graphiques analytiquement utiles :

- consommation dans le temps ;
- observed vs expected ;
- anomalies confirmées ;
- profil horaire ;
- semaine/week-end ;
- production vs énergie ;
- température vs énergie ;
- intensité énergétique ;
- dérive de baseline.

Export PNG sans interface graphique nécessaire.

---

## 45. Rapport HTML

Créer un HTML autonome léger.

Pas de React.

Pas de stack frontend lourde.

HTML/CSS simples.

Doit pouvoir être ouvert sur Android.

---

## 46. Tests

Utiliser `pytest` si raisonnable.

Tester en priorité :

```text
kW ↔ kWh
intégration temporelle
timestamps
agrégation
production
baseline
résidus
événements
surconsommation
coût
annualisation
double comptage
```

---

## 47. Cas limites

Tester explicitement :

### fichier vide
Erreur propre.

### une seule mesure
Pas d’analyse temporelle inventée.

### production nulle partout
Pas de division par zéro.

### consommation constante
Pas d’anomalies artificielles.

### aucune anomalie synthétique
Faux positifs faibles.

### anomalie massive
Doit être trouvée.

### aucun tarif
Pas de chiffres en euros.

### données mensuelles
Pas d’analyse horaire.

### intervalles irréguliers
Gestion correcte ou refus explicite.

---

## 48. Invariants

Ajouter des contrôles tels que :

```text
énergie totale >= 0

énergie hors production <= énergie totale

surconsommation estimée >= 0

coût associé >= 0

économies annoncées <= coût total
```

sauf cas explicitement justifié.

---

## 49. Mode démo

Créer une expérience reproductible :

```bash
python generate_demo.py
```

puis :

```bash
python analyze.py examples/demo_15min.csv \
  --price-per-kwh 0.175
```

Mais le pipeline automatique n’est que la première étape.

La démonstration complète doit ensuite montrer Codex qui :

1. inspecte les signaux ;
2. formule des hypothèses ;
3. approfondit plusieurs pistes ;
4. rejette certaines pistes ;
5. confirme les plus solides ;
6. fait une review adversariale ;
7. produit la synthèse finale.

---

## 50. Validation du mode démo

Produire :

```text
validation.json
```

avec de vraies métriques :

```text
injected_events
detected_events
true_positives
false_positives
false_negatives
precision
recall
F1
```

La ground truth ne doit jamais être accessible à la phase d’investigation elle-même.

---

## 51. Tester plusieurs scénarios

Ne pas valider le système uniquement sur un dataset parfaitement adapté.

Créer plusieurs profils :

```text
factory_simple
factory_variable
factory_temperature_sensitive
factory_noisy
factory_low_production
```

Le même mécanisme doit raisonnablement fonctionner sur plusieurs situations.

---

## 52. Pas de LLM pour les chiffres

Toutes les valeurs critiques doivent être issues du code.

Codex peut :

```text
interroger
sélectionner
interpréter
critiquer
```

mais pas remplacer les calculs.

---

## 53. Pas besoin d’API OpenAI dans le MVP

Pour cette phase :

```text
utilisateur
+
Codex CLI
+
repository
+
toolbox
+
données
```

constitue une architecture acceptable.

Ne pas intégrer une API uniquement pour donner une apparence de produit fini.

---

## 54. Confidentialité

Local-first.

Aucune télémétrie ajoutée.

Aucun upload automatique.

Aucun appel externe depuis le moteur analytique sans demande explicite.

Les données sensibles doivent être exclues de Git.

Créer `.gitignore` approprié pour :

```text
client_data/
client_cases/
workspaces/*/incoming/
workspaces/*/privacy/
workspaces/*/sanitized/
workspaces/*/processed/
workspaces/*/outputs/
.env
scratch sensible
```

Les exemples synthétiques peuvent être versionnés.

Pour tout futur dossier réel, Codex est la première étape sémantique sur `incoming/`. Python ne
peut avant cela que créer le workspace et copier les octets sans parser. Après la review Codex,
le post-check Python doit produire `privacy_manifest.json` et refuser toute analyse tant que
`approved_for_analysis != true`. Le workspace et l'orchestration sont local-first, mais le service
implique le traitement par Codex/OpenAI selon sa configuration; ne pas affirmer que Codex est
purement local ou qu'aucune donnée ne quitte jamais l'appareil.

---

## 55. Positionnement

Le système est une :

```text
plateforme locale d'analyse et d'investigation de performance énergétique sur données
```

Sa valeur autonome consiste à détecter et quantifier les dérives, éliminer les fausses pistes,
cibler les vérifications terrain puis mesurer l'effet après correction. Il peut aussi compléter
le travail d'un auditeur, frigoriste, électricien ou mainteneur en indiquant où chercher et
pourquoi. Ne pas le réduire à une préparation superficielle avant un autre service.

Il n’est pas :

- un audit énergétique réglementaire ;
- une certification ;
- un diagnostic mécanique définitif ;
- une garantie contractuelle d’économie.

Les conclusions doivent rester proportionnées aux preuves.

---

## 56. Ne pas devenir trop prudent

Ne pas transformer les réserves méthodologiques en rapport inutile.

Si les données démontrent clairement :

```text
la consommation nocturne a augmenté de 29 %
depuis le 14 mars
```

l’écrire clairement.

Ce qui ne peut pas être affirmé sans autre donnée est plutôt :

```text
le compresseur X est responsable
```

Toujours distinguer :

```text
OBSERVATION
INTERPRÉTATION
CAUSE
```

---

## 57. Architecture future

Préparer sans implémenter prématurément la possibilité de :

```text
client
 ↓
workspace isolé
 ↓
préparation
 ↓
Codex
 ↓
toolbox
 ↓
investigation
 ↓
review
 ↓
rapport
```

Structure éventuelle :

```text
workspaces/
  demo/
    incoming/
    privacy/
    sanitized/
    processed/
    scratch/
    outputs/
```

---

## 58. Ce qu’il ne faut pas faire maintenant

Ne pas consacrer du temps à :

- SaaS ;
- authentification ;
- Stripe ;
- paiement ;
- React ;
- application mobile ;
- microservices ;
- Kubernetes ;
- multi-tenancy ;
- infrastructure cloud ;
- ERP spécifiques ;
- IoT temps réel ;
- agents multiples ;
- vector database ;
- marketing ;
- landing page.

Priorité :

```text
QUALITÉ ANALYTIQUE
+
CAPACITÉ D’INVESTIGATION DE CODEX
```

---

## 59. Performance Termux

Tester progressivement :

```text
10 000 lignes
100 000 lignes
500 000 lignes
```

Ne migrer vers Polars/DuckDB que si les benchmarks montrent un besoin réel.

Préférer les solutions simples.

---

## 60. Git

Faire des commits cohérents.

Ne pas laisser le dépôt dans un état cassé.

Avant un refactor important :

```text
tests
→ modification
→ tests
→ vérification manuelle
→ commit
```

---

## 61. Autonomie

Travailler de manière autonome dans la limite des permissions déjà accordées.

Ne pas s’arrêter pour demander :

- noms de fonctions ;
- petits choix de structure ;
- bibliothèque ordinaire ;
- ajout d’un test nécessaire ;
- correction d’un bug évident ;
- refactor mineur ;
- création d’un script exploratoire.

Faire le choix techniquement raisonnable et continuer.

S’arrêter seulement lorsqu’il existe :

- risque réel de perte de données ;
- besoin d’un secret ;
- opération externe sensible ;
- ambiguïté métier réellement impossible à résoudre ;
- blocage technique persistant.

En cas d’échec :

```text
diagnostiquer
→ essayer une alternative raisonnable
→ documenter
→ continuer
```

---

## 62. Critère de succès principal

À terme, un nouveau dataset doit permettre cette séquence :

```text
nouveau dataset
      ↓
Codex comprend les données
      ↓
validation
      ↓
Codex observe
      ↓
Codex formule des hypothèses
      ↓
Python teste
      ↓
Codex interprète
      ↓
Codex cherche à réfuter
      ↓
Python teste à nouveau
      ↓
Codex sélectionne les pistes solides
      ↓
review contradictoire finale
      ↓
nouveaux calculs si nécessaire
      ↓
Codex arbitre
      ↓
Codex synthétise
      ↓
rapport
      ↓
revue humaine
```

Le projet est réussi si **le raisonnement de Codex apporte réellement quelque chose que le pipeline déterministe seul ne ferait pas**.

---

## 63. Question de contrôle permanente

À chaque étape majeure, demander :

```text
Si Codex disparaissait du système demain,
est-ce que l’analyse serait pratiquement identique ?
```

Si la réponse devient :

```text
oui
```

alors l’architecture dérive vers un logiciel analytique classique.

Dans ce cas, corriger cette dérive.

Les outils doivent augmenter Codex.

Ils ne doivent pas le remplacer.

---

## 64. Autre question de contrôle

Demander également :

```text
Si Python disparaissait et que Codex faisait
les calculs lui-même, pourrais-je encore faire confiance
aux chiffres ?
```

La réponse doit être :

```text
non
```

Cela garantit la séparation voulue :

```text
Codex = intelligence analytique
Python = vérité quantitative
```

---

## 65. Action immédiate

Commencer maintenant.

### Étape 1
Inspecter intégralement le repository existant.

### Étape 2
Exécuter les scripts et tests actuels.

### Étape 3
Auditer les calculs fondamentaux.

Corriger en priorité tout problème concernant :

```text
unités
timestamps
périodes
kW/kWh
coûts
agrégations
```

### Étape 4
Identifier les parties du programme actuel qui produisent directement des conclusions trop fortes à partir de règles simples.

Les transformer progressivement en :

```text
signaux candidats
```

que Codex pourra investiguer.

### Étape 5
Créer le dataset synthétique 15 minutes + ground truth.

### Étape 6
Construire une première version de la toolbox analytique.

### Étape 7
Effectuer une première véritable investigation agentique complète.

Codex doit :

```text
observer
→ formuler plusieurs hypothèses
→ sélectionner les plus intéressantes
→ utiliser les outils
→ chercher des explications alternatives
→ rejeter certaines hypothèses
→ approfondir les autres
→ quantifier
→ effectuer une review contradictoire finale
→ demander de nouveaux calculs si nécessaire
→ produire une synthèse
```

### Étape 8
Évaluer objectivement le résultat par rapport à la ground truth.

### Étape 9
Identifier ce qui manque dans la toolbox.

### Étape 10
Améliorer le système et recommencer.

---

## 66. Boucle de développement permanente

Utiliser :

```text
INSPECTER
   ↓
COMPRENDRE
   ↓
FORMULER
   ↓
IMPLÉMENTER
   ↓
EXÉCUTER
   ↓
MESURER
   ↓
CRITIQUER
   ↓
TENTER DE RÉFUTER
   ↓
CORRIGER
   ↓
TESTER
   ↓
REVIEW
   ↓
COMMIT
   ↓
CONTINUER
```

Ne jamais déclarer une fonctionnalité fiable simplement parce que le programme ne plante pas.

Ne jamais considérer un résultat comme valide simplement parce qu’il paraît plausible.

Ne jamais chercher à impressionner par la quantité de fonctionnalités.

Chercher à obtenir un système :

- intelligent ;
- sceptique ;
- quantitativement fiable ;
- traçable ;
- adaptable ;
- autonome ;
- capable d’explorer ;
- capable de se contredire ;
- capable de reconnaître ses limites ;
- réellement utile pour identifier des inefficacités énergétiques.

La finalité n’est pas de construire un logiciel qui remplace Codex.

La finalité est de construire **le laboratoire spécialisé qui permet à Codex de devenir progressivement un analyste énergétique industriel extrêmement performant**.

---

## 67. Contexte et cycle client canonique

Pour Againward, reconstruire le contexte depuis le dépôt courant **et** tout
`/storage/emulated/0/Download`, qui peut contenir objectifs, handoffs, R&D, benchmarks et pièces
client absents du dépôt. Le dépôt reste autoritatif pour le code; ne jamais versionner les données
client de Download ni considérer automatiquement un ancien clone comme plus récent.

Lire `docs/CLIENT_WORKFLOW.md` et `.codex/skills/againward-client-workflow/SKILL.md`. Les sources de
vérité sont `privacy/privacy_manifest.json`, `investigation_state.json.client_lifecycle` et
`questions.json`. États : `AWAITING_PRIVACY_REVIEW`, `PRIVACY_CLEARED`, `PRIVACY_BLOCKED`, `ANALYZING`,
`WAITING_FOR_REQUIRED_INFORMATION`, `RESUMING`, `FINALIZABLE`, `DELIVERABLE`, puis `PURGED`. Un BLOCKING impose
STOP : pas de promotion, économie/action finale, rapport ou livraison. Après réponse : recalcul
Python, alternatives, avant/après et review. Deux cycles par défaut, trois demandes/cycle,
zéro par défaut. Une continuation explicite et liée aux progrès peut ouvrir un cycle additionnel,
sans remettre les compteurs à zéro : voir `docs/INVESTIGATION_CONTINUATION.md`.

Distinguer `CLIENT_DECLARATION`, `EXISTING_DOCUMENT`, `FIELD_OBSERVATION`, `PREREGISTERED_TEST`,
`INSTRUMENT_MEASUREMENT`. Une déclaration opérateur n'est pas une ancre terrain. Préserver :
détection → signature → composant anonyme → compatibilité → attribution → mécanisme → pronostic.

Pour naviguer dans un cas, commencer par `python manage_investigation.py status <dossier>` et lire
`docs/REPOSITORY_LAYOUT.md`. Les commandes acceptent une racine de workspace, un cas Goal A ou un
dossier d'analyse direct. Ne pas recréer `questions.json`, `investigation_state.json` ou
`human_review.json` dans un second emplacement. Le code versionné doit rester portable : aucun
chemin Android/Termux codé en dur; Download n'est qu'une source locale de contexte pour Codex.

Responsabilités : `energy_mvp/client_lifecycle.py` possède l'état et la reprise;
`energy_mvp/privacy.py` le gate Codex-first, le manifest, la rétention et la purge;
`energy_mvp/client_requests.py` le contrat, la VOI et la déduplication;
`energy_mvp/minimal_attribution.py` les preuves/plafonds;
`energy_mvp/attribution_workflow.py` l'intégration MEA; `energy_mvp/case_lifecycle.py` le gate.
`question_batch.json`, `publish_minimum_questions()` et les batches Goal B sont dépréciés comme
autorités et restent seulement des adaptateurs/vues. Valider avec :

```sh
python -m pytest -q tests/test_client_workflow_unification.py tests/test_workflow_paths.py
python benchmarks/client_workflow/benchmark.py
python -m pytest -q
```
