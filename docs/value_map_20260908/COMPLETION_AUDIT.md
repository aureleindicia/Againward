# Audit de l’extension économique — 9 septembre 2026

## Réponses aux seize questions

1. **Avant :** Operational Economics calculait des scénarios d’effets énergétiques annualisés, tarifs (dont effets alignés temporellement), coûts d’intervention/récurrents, autres bénéfices supportés, bénéfice net et payback ; il validait actions, contraintes, décisions, références et portefeuilles déclarés. Il ne représentait pas explicitement la réduction du champ d’investigation, les heures contrefactuelles ou les résultats réalisés séparés des estimations.
2. **Maintenant :** le même état économique porte `value_assessment`. Sa projection `value_map.json` sépare énergie, économie directe, investigation, décision et potentiel non vérifié, avec relations, provenance, coûts/contraintes et versions historiques. Les fonctions économiques existantes restent en place.
3. **Investigation distincte de l’énergie :** oui, catégories et objets séparés, sans conversion du nombre d’hypothèses éliminées en argent ou en pourcentage de coût évité.
4. **Fausse piste éliminée :** oui, elle peut être enregistrée sans montant ni finding positif. L’utilité de la réfutation est un jugement sourcé ; Python ne décide pas qu’une piste est réfutée.
5. **Temps sans argent :** oui, personnes × heures sont calculées à partir de références LOW/BASE/HIGH ; sans coût horaire valide, `time_value_eur` reste `null`. Inconnu n’est jamais remplacé par zéro.
6. **Monétisation :** coût horaire EUR/h, période `per_hour`, source économique persistée et validée, et temps sourcé. Une hypothèse de coût ou de temps reste étiquetée scénario ; aucun coût horaire client par défaut. La valorisation ne devient pas une économie réalisée.
7. **Contrefactuels :** base, confiance et statut explicites ; temps documenté, estimation client et scénario séparés. UNKNOWN reste UNKNOWN. Une déclaration structurée n’est pas une preuve indépendante de causalité : pertinence et solidité du contrefactuel doivent être revues.
8. **Double comptage :** énergie et argent correspondant au même effet sont intrinsèquement DEPENDENT ; relations non renseignées UNKNOWN. Aucune somme transversale n’est proposée, même si les relations sont INDEPENDENT. Le portefeuille existant conserve son périmètre ; mélanges de devises/périodes et corrections de recouvrements multiples partageant une action sont désormais refusés.
9. **Gros chiffre artificiel :** aucun champ d’entrée de total Value Map n’est accepté ; sa sortie `total_value` est toujours `null`. Le rapport revalide la section et son total économique contre les calculs canoniques. Un modèle ou total manipulé est refusé. Cela protège le chemin logiciel supporté, pas un document externe écrit manuellement ni un mensonge humain enregistré comme source.
10. **Avant/après :** les entrées antérieures et leurs projections chiffrées ne sont pas réécrites ; nouvelles entrées et snapshots. POST_ACTION_OBSERVED_RESULT exige action, chronologie, preuves post-action correspondantes, comparaison et revue des confondants. Les mesures réalisées doivent venir des preuves post-action, jamais d’hypothèses ou du temps potentiellement évité initial.
11. **PDF :** oui, section « Valeur de l’investigation », valeurs recalculées depuis l’état économique avant rendu ; tests de falsification du modèle et trois PDF synthétiques. La livraison conserve les gates et exige en plus une approbation humaine portant sur l’empreinte exacte de la carte. Les exemples ne simulent pas une approbation de livraison.
12. **Pilot learning :** oui, fonctions de revue Markdown/JSON, sélection explicite de composants, inconnus conservés. Export fermé uniquement après autorisation et revue de désidentification déclarées ; agrégation descriptive, dénominateurs connus/inconnus et médianes énergie/argent stratifiées par base. Aucune conclusion commerciale automatique.
13. **Jugement humain/agent :** définition et réfutation d’hypothèses, utilité/nouveauté, pertinence des contrefactuels, causalité, indépendance, choix d’action et de prochaine information, qualité des extraits documentaires, comparaison post-action, consentement/désidentification et approbation finale. Python vérifie et calcule ; il ne recommande pas automatiquement.
14. **Tests ajoutés :** `tests/test_value_map.py` et `tests/test_pilot_learning.py` couvrent les vingt exigences de validation et des attaques supplémentaires : faux evidence injectés dans un packet, changement rétroactif de sources, chiffres libres, mauvais total PDF, mélanges de devises, corrections de recouvrement, revue humaine périmée, NaN/inf et contamination d’un temps documenté par un scénario.
15. **Résultats :** voir `VALIDATION_RESULTS.json`, qui distingue référence initiale, tests ciblés, suite globale et exemples. La référence initiale avait un échec documentaire préexistant (prompt de lancement dépourvu de termes requis par le test de workflow) ; le prompt a été corrigé, sans modifier le test.
16. **Fichiers :** nouveaux `value_map.py`, `pilot_learning.py`, les deux fichiers de tests, `workspace/generate_value_map_examples.py`, `docs/VALUE_MAP.md`, ce dossier d’audit. Modifiés `operational_economics.py`, `client_delivery.py`, `energy_mvp/case_lifecycle.py` (seulement liaison de la revue humaine à la Value Map), et les documents de découverte des outils, modèle de rapport, moteur économique et prompt client. Aucun détecteur, benchmark, ground truth ni module de l’Evidence Plane modifié.

## Correspondance des exigences de validation

| Exigences V | Preuve principale |
|---|---|
| 1–5 : temps inconnu, documenté, coûts et scénarios | tests `unknown_time`, `client_documented_hours`, `hourly_rate`, `time_monetization`, `scenario_hours`, `scenario_counterfactual` |
| 6–9 : réfutation, intervention inconnue, décision sans argent, DO_NOTHING | tests `false_lead`, `intervention_cost`, `decision_value` ; exemple C-E |
| 10–11 : relations / doubles comptes | six types dans `relationships_never_generate_cross_category_total`, `free_total_value`, `portfolio_rejects`, `overlapping_pair_corrections` |
| 12–13 : avant/après et réalisation | tests `pre_action_estimate`, `source_rewrite`, `realized_requires`, `realized_appends`, `realization_cannot_promote`, `realized_quantities` |
| 14–16 : plages et provenance existante | `inconsistent_hypotheses_and_ranges`, `packet_cannot_inject`, suite Operational Economics existante, suite globale |
| 17 : rapport sans fausse réalisation | `pdf_uses_revalidated_value_map`, `time_monetization`, exemples PDF avec labels et absence de total |
| 18–19 : abstention économique / contrefactuel inconnu | `no_economic_data`, `unknown_counterfactual` |
| 20 : gates conservés | `waiting_gate`, `value_map_human_review`, suite globale lifecycle / Evidence Plane |

## Limites délibérées et risques restant à mesurer

- Cette extension représente des preuves et jugements ; elle ne prouve pas la valeur commerciale, le temps réellement évité ou un lien causal. Les trois exemples sont synthétiques et ne mesurent aucune performance terrain.
- Les nouvelles quantités historiques / heures proviennent d’extraits Goal B structurés ou d’hypothèses existantes. L’extraction et la signification du chiffre doivent être revues ; une référence existante ne garantit pas qu’un texte a été correctement interprété.
- Le calcul net existant conserve ses conventions de coûts facultatifs. Un coût manquant n’est pas une preuve d’absence de coût ; la carte expose aussi actions et contraintes. La décision économique reste à l’agent et peut s’abstenir.
- Pas de théorie EVSI/EVPI automatisée, ni modèle financier de réduction d’incertitude. Aucun total transversal même si certains composants pourraient, après expertise, être indépendants.
- Les textes de valeur destinés au client n’acceptent pas de chiffres libres. Utiliser les quantités référencées ; les désignations numériques d’équipements doivent rester dans les preuves/références, pas devenir des chiffres économiques libres dans le narratif.
- Les comparaisons post-action restent sensibles au choix de baseline, aux variations de production et aux autres changements. Les attestations structurées de revue ne remplacent pas une validation terrain.
- Les états et snapshots restent locaux ; ce n’est pas un journal cryptographique inviolable. Une écriture interrompue peut exiger de régénérer la projection depuis l’état canonique ; le gate refuse une projection absente ou différente.
- Le PDF conserve les limites de taille du rapport existant ; une carte trop volumineuse doit être synthétisée avec justification et revue, pas tronquée silencieusement.
- La structure pilote permet les métriques demandées mais nécessite des annotations sourcées et une sélection explicite du composant pertinent. Aucun échantillon minimal n’autorise automatiquement une promesse commerciale ; biais de sélection, autorisation, confidentialité et réidentification restent à examiner humainement.
