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
  (`explicit_interval`, `inferred_nominal_interval` ou differences d'index cumulatif), ainsi que
  le fuseau local déclaré. L'ordre et les durées utilisent UTC ; les profils utilisent l'horloge
  locale conservée dans chaque `Reading`.
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

## Régimes d'exploitation et saisonnalité

`summarize_operating_regimes()` sépare les distributions par activité, shift, type produit,
mois ou saison. `fit_regime_baselines()` ajuste ensuite une baseline production/température
distincte dans chaque groupe et conserve pour chacune une calibration passée et une validation
future.

- Objectif : éviter qu'un fonctionnement 24/7, un poste de nuit ou un mix produit soit traité
  comme une seule population artificielle.
- Entrée : lectures et champs de régime choisis par Codex.
- Sortie : résumés ou modèles par régime, groupes insuffisants explicitement listés,
  `decision=None`.
- Hypothèses : les colonnes de régime sont fiables et chaque sous-groupe contient assez de passé.
- Limitations : le découpage ne découvre pas une cause et peut sur-segmenter ; Codex doit comparer
  sa stabilité et sa réalité métier.
- Exemple : `fit_regime_baselines(readings, regime_fields=("shift", "product_type"),
  predictors=("production", "cooling_degree_c"))`.

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
  `production_active`, `product_type_b`, `production_product_b`, `heating_degree_c`,
  `cooling_degree_c`, `heating_degree_10_c`, `cooling_degree_20_c`.
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

## `calculate_tariff_cost(readings, plan)`

- Objectif : calculer séparément charges d'énergie par plages horaires et facturation mensuelle
  de puissance.
- Entrée : lectures et `TariffPlan` avec prix par défaut, plages semaine/nuit éventuellement
  traversant minuit et coût mensuel par kW.
- Sortie : ventilation mensuelle, couverture tarifaire, coût énergie, coût de pointe et total
  uniquement si toute l'énergie est tarifée.
- Hypothèses : les horaires locaux du site et le contrat ont été correctement saisis.
- Limitations : ne traite pas taxes, dépassements contractuels complexes ni marchés dynamiques ;
  `recoverable_saving` reste toujours `None`.
- Exemple : construire le plan avec `tariff_plan_from_dict(intake["cost"])`.

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
- Entree : un `LoadedData` haute frequence ; production, activite, temperature et type produit
  sont facultatifs et activent seulement les familles compatibles.
- Sortie : evenements marques `candidate_signal`, baseline et seuils utilises.
- Hypotheses : au moins trente jours, fréquence connue d'au plus une heure et première période
  exploitable comme référence strictement passée.
- Limitations : aucune sortie n'est une opportunite confirmee. Les predicteurs sont choisis selon
  leur couverture et une validation temporelle parcimonieuse ; un réajustement robuste peut retirer
  une petite minorité d'outliers de référence et le trace explicitement. Les familles incompatibles
  avec le contexte disponible sont listees comme desactivees. Le benchmark aveugle reste la mesure
  de généralisation autoritaire, pas la seule démo.
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
## Poursuite objective d'une investigation incertaine

`information_request()` construit une prochaine verification minimale et
`validate_follow_up_logic()` controle le journal avant sa publication.

Une demande n'est permise que pour `INSUFFISAMMENT_ETAYE` ou
`A_CONSERVER_AVEC_RESERVES`. Une hypothese `CONFIRME` ou `REJETE` ne declenche aucune
question systematique. Chaque demande doit pouvoir modifier la decision ou la confiance et precise :

- la question, la donnee ou le test terrain exact a demander ;
- son utilite ;
- au moins deux hypotheses qu'il departage ;
- l'effort concret et son niveau ;
- le resultat attendu si l'hypothese examinee est vraie.

`next_information_request()` choisit la priorite la plus basse numeriquement : Codex commence par
la question metier ou le controle existant le moins couteux, avant une nouvelle instrumentation.
Les formulations generiques telles que « plus de donnees » sont refusees. Si aucune verification
realiste ne permet d'etablir une cause physique, le journal conserve explicitement
`physical_cause_status = non_etablie_avec_les_donnees_disponibles` et ne force pas de recommandation.

- Objectif : reduire une incertitude materielle par la prochaine action minimale.
- Entree : decision Codex et demande structuree issue de la review contradictoire.
- Sortie : champs serialisables dans `investigation.json` et affichables dans le rapport.
- Hypotheses : la demande peut reellement departager les explications encore plausibles.
- Limitations : le module valide la precision et la coherence, mais Codex reste responsable de la
  pertinence metier de la question.
- Exemple : demander si un nettoyage etait planifie durant quatre week-ends anormaux avant de
  proposer une mesure machine ou un test d'arret.

## Cycle de dossier client

`prepare_investigation()` crée le paquet quantitatif générique. `publish_minimum_questions()`
extrait uniquement la prochaine demande de chaque piste incertaine ou cause non prouvée.
`record_client_answers()` consigne la réponse, son auteur et sa preuve sans autoriser une
réécriture. `evaluate_delivery_gate()` contrôle l'investigation, les huit axes de review
adversariale, le rapport et l'approbation humaine.

- Objectif : rendre les itérations Codex/client traçables sans transformer Python en analyste.
- Entrée : dossier préparé, journal Codex, réponses client et review humaine.
- Sortie : `questions.json`, trace appendue et `delivery_gate.json`.
- Hypothèses : Codex a produit les hypothèses et tests ; Python ne vérifie que leur contrat et les
  garde-fous de livraison.
- Limitations : une validation de schéma ne prouve pas à elle seule la pertinence énergétique ; la
  review humaine reste obligatoire.
- Exemple : `python manage_investigation.py check workspaces/usine_01/processed`.
