# Boite a outils d'analyse

Ces fonctions sont des instruments quantitatifs. Elles produisent des mesures et des
diagnostics reproductibles ; elles ne confirment pas seules une opportunite. Codex choisit
les tests, confronte les explications alternatives et decide de conserver ou rejeter une
hypothese.

Toutes les energies retournees sont en `kWh` et toutes les puissances en `kW`.

## `inspect_dataset(data)`

- Objectif : obtenir rapidement structure, periode, frequence, couverture et incidents de qualite.
- Entree : un `LoadedData` produit par `load_data()`.
- Sortie : dictionnaire serialisable.
- Hypotheses : le chargement et la normalisation ont deja ete effectues.
- Limitations : ne juge pas si les variables disponibles suffisent a une conclusion metier.
- Convention temporelle : expose les timestamps bruts, les bornes de couverture et leur methode
  (`explicit_interval`, `inferred_nominal_interval` ou differences d'index cumulatif).
- Exemple : `inspect_dataset(load_data("examples/demo_15min.csv"))`.

## `extract_period(readings, start, end)`

- Objectif : isoler une fenetre `[start, end[` sans modifier les mesures.
- Entree : lectures et deux `datetime`.
- Sortie : liste de `Reading`.
- Hypotheses : timestamps comparables et sans fuseau apres normalisation.
- Limitations : ne complete pas les trous.
- Exemple : `extract_period(data.readings, datetime(2026, 2, 1), datetime(2026, 3, 1))`.

## `summarize_readings(readings)`

- Objectif : mesurer energie, puissance moyenne, production et intensite d'un sous-ensemble.
- Entree : sequence de `Reading`.
- Sortie : dictionnaire de totaux et moyennes.
- Hypotheses : l'intensite exige une production complete et strictement positive.
- Limitations : une moyenne globale peut masquer les horaires et les produits.
- Exemple : `summarize_readings(data.readings)`.

## `compare_groups(readings, first_filter, second_filter)`

- Objectif : comparer deux groupes definis par Codex avec les memes indicateurs.
- Entree : lectures et deux predicats Python.
- Sortie : resumes des groupes, ecart de puissance absolu et relatif.
- Hypotheses : les groupes doivent etre comparables pour que l'interpretation soit valable.
- Limitations : l'outil ne controle pas lui-meme les facteurs confondants.
- Exemple : comparer nuits de reference et nuits recentes.

## `daily_profile(readings, weekdays_only=None)`

- Objectif : construire un profil moyen par quart d'heure.
- Entree : lectures et filtre optionnel jours ouvres/week-end.
- Sortie : 96 points au maximum avec puissance et production moyennes.
- Hypotheses : frequence infra-journaliere suffisamment reguliere.
- Limitations : une moyenne peut lisser un evenement rare ou un changement de regime.
- Exemple : `daily_profile(data.readings, weekdays_only=True)`.

## `estimate_baseload(readings, inactive_only=True)`

- Objectif : comparer plusieurs estimations robustes de charge de base.
- Entree : au moins 20 lectures, inactives par defaut.
- Sortie : quantiles 10/25 %, mediane des 20 % plus basses et minimum absolu temoin.
- Hypotheses : les periodes inactives sont correctement identifiees.
- Limitations : aucune methode n'etablit a elle seule la charge incompressible physique.
- Exemple : `estimate_baseload(data.readings)`.

## `fit_linear_baseline(readings, predictors, calibration_fraction=0.7)`

- Objectif : ajuster une baseline interpretable puissance-production-temperature.
- Entree : lectures, noms de predicteurs parmi `production`, `outside_temperature_c`,
  `production_active`, `product_type_b`, `production_product_b`.
- Sortie : coefficients, periodes et metriques MAE/RMSE/R2/MAPE de calibration et validation.
- Hypotheses : relation approximativement lineaire et donnees completes.
- Limitations : MAPE vaut `None` en presence de cible nulle ; une bonne correlation ne prouve
  aucune causalite. Les premieres 70 % des lignes calibrent, les suivantes valident afin
  d'eviter la fuite d'information.
- Exemple : `fit_linear_baseline(data.readings, predictors=("production", "outside_temperature_c"))`.

## `calculate_residuals(readings, model)`

- Objectif : calculer `observe - attendu` pour chaque mesure utilisable.
- Entree : lectures et baseline lineaire issue de `fit_linear_baseline()`.
- Sortie : timestamp, observe, attendu, residu et duree.
- Hypotheses : le modele correspond au meme procede et aux memes unites.
- Limitations : un residu positif est un signal, pas une economie ni une cause.
- Exemple : `calculate_residuals(data.readings, model)`.

## Baselines active/inactive, temporelle et rolling median

`fit_activity_baseline()` estime separement les regimes actif et inactif.
`fit_time_baseline()` utilise la mediane par jour de semaine, heure et activite, avec fallback
horaire. `fit_rolling_median_baseline()` ne consulte que les lignes anterieures a chaque point.

- Objectif : comparer des modeles simples et interpretables au modele production/temperature.
- Entree : lectures chronologiques et fraction/fenetre explicite.
- Sortie : modele, periodes calibration/validation, metriques et residus si glissant.
- Hypotheses : historique representatif et granularite suffisante.
- Limitations : une mediane temporelle peut absorber un mauvais comportement recurrent ; Codex
  doit choisir la baseline selon le contexte, pas uniquement selon le meilleur R2.
- Exemple : `fit_rolling_median_baseline(data.readings, window_rows=96 * 7)`.

## `measure_linear_drift(points, value_key="residual_kw")`

- Objectif : mesurer une pente par jour et sa qualite d'ajustement sans conclure automatiquement.
- Entree : points horodates contenant une valeur quantitative, trois au minimum.
- Sortie : pente, intercept, R2, periode et `decision=None`.
- Hypotheses : relation lineaire utile comme premier test; timestamps distincts.
- Limitations : saisonnalite et ruptures de niveau peuvent imiter une pente; Codex doit tester les
  contre-explications.
- Exemple : `measure_linear_drift(residuals)`.

## `compare_level_shift(before, after)`

- Objectif : mesurer un changement robuste entre deux regimes choisis par Codex.
- Entree : au moins trois valeurs avant et apres.
- Sortie : medianes, MAD, ecart absolu/relatif et `decision=None`.
- Hypotheses : les periodes sont comparables et leur frontiere est justifiee.
- Limitations : ne localise pas la cause et ne choisit pas le point de rupture.
- Exemple : `compare_level_shift(residus_reference, residus_recents)`.

## `group_residual_events(residuals, threshold_kw, max_gap_minutes)`

- Objectif : regrouper des points residuels proches en evenements temporels.
- Entree : residus, seuil positif et ecart maximal.
- Sortie : debut, fin, nombre de points, pic et energie excedentaire au-dessus de la baseline.
- Hypotheses : seuil choisi et baseline justifies dans l'investigation.
- Limitations : ne donne ni severite finale ni confiance ; les evenements voisins peuvent avoir
  des causes differentes.
- Exemple : `group_residual_events(residuals, threshold_kw=15, max_gap_minutes=30)`.

## `calculate_excess_energy(observed_kw, expected_kw, interval_hours)`

- Objectif : integrer uniquement la partie positive de `observe - attendu`.
- Entree : trois series de meme longueur.
- Sortie : kWh excedentaires observes.
- Hypotheses : les durees sont positives et la baseline est applicable.
- Limitations : surconsommation observee ne signifie pas economie recuperable.
- Exemple : `calculate_excess_energy([100], [75], [0.25]) == 6.25`.

## `calculate_cost(energy_kwh, price_per_kwh)`

- Objectif : calculer un cout deterministe.
- Entree : energie et tarif non negatifs.
- Sortie : cout dans la devise du tarif.
- Hypotheses : tarif simple constant par kWh.
- Limitations : aucun cout de pointe, plage tarifaire ou contrat complexe.
- Exemple : `calculate_cost(1000, 0.175) == 175`.

## `annualize_effect(...)`

- Objectif : projeter un effet recurrent sans presenter automatiquement la surconsommation
  comme une economie recuperable.
- Entree : energie observee, occurrences observees/eligibles, duree, couverture, occasions
  annuelles et declaration explicite de representativite ; tarif et part recuperable facultatifs.
- Sortie : recurrence, impact annuel projete, cout associe et, uniquement si elle est fournie,
  scenario de part recuperable.
- Hypotheses : au moins trois occurrences sur 28 jours, couverture d'au moins 90 %, periode
  documentee comme representative et nombre annuel d'occasions justifie.
- Limitations : refuse les evenements ponctuels et les donnees faibles ; ne fabrique aucun
  intervalle de confiance et ne prouve ni causalite ni economie.
- Exemple : `annualize_effect(observed_excess_energy_kwh=600, observed_occurrences=6,
  eligible_occurrences=8, observation_days=56, annual_eligible_occurrences=250,
  representative_period=True, coverage_ratio=0.98)`.

## `union_excess_energy(events)`

- Objectif : detecter et supprimer le double comptage temporel entre signaux.
- Entree : une liste de dictionnaires `{timestamp: excess_kwh}`.
- Sortie : somme naive, somme dedupliquee, kWh doubles et nombre de chevauchements.
- Hypotheses : chaque valeur represente le meme concept d'exces au meme intervalle.
- Limitations : retient prudemment le maximum ; une allocation causale exige le contexte procede.
- Exemple : `union_excess_energy([signal_nuit, signal_inactif])`.

## `detect_candidate_events(data)`

- Objectif : produire automatiquement des points de depart nuit, week-end, pic, efficacite,
  derive et changement de niveau.
- Entree : un `LoadedData` haute frequence avec production, activite, temperature et type produit.
- Sortie : evenements marques `candidate_signal`, baseline et seuils utilises.
- Hypotheses : les premiers jours forment une reference exploitable.
- Limitations : aucune sortie n'est une opportunite confirmee ; le profil bruite produit encore
  des faux positifs que Codex doit examiner. Les predicteurs sont choisis selon leur couverture ;
  les familles incompatibles avec le contexte disponible sont listees comme desactivees.
- Exemple : `detect_candidate_events(load_data("examples/demo_15min.csv"))`.

## Graphiques PNG

Les fonctions `plot_power_timeseries`, `plot_observed_expected`, `plot_daily_residual` et
`plot_energy_production` ecrivent des PNG sans interface graphique ni dependance externe.

- Objectif : visualiser uniquement les relations utiles a l'investigation.
- Entree : lectures ou residus deja calcules.
- Sortie : fichier PNG.
- Hypotheses : les unites ont ete normalisees avant tracage.
- Limitations : le rendu volontairement leger laisse titres et explications au rapport HTML.
- Exemple : `plot_daily_residual(residuals, "reports/charts/residual.png")`.

## Generateur de demonstration

`python generate_demo.py` produit `examples/demo_15min.csv` et une ground truth separee.
Le moteur d'analyse ne lit jamais le fichier de ground truth. Les scenarios disponibles sont :

- `factory_simple` ;
- `factory_variable` ;
- `factory_temperature_sensitive` ;
- `factory_noisy` ;
- `factory_low_production`.

La ground truth n'est ouverte qu'apres la fin des investigations, pour calculer les metriques
de validation.
