# INDICIA — rapport R&D MinimalEvidenceAttribution

## Décision

La phase produit un **prototype R&D intégrable en mode gardé**, pas une capacité d'attribution terrain démontrée. La politique retenue conserve une liste de compatibilités, mais ne nomme un actif qu'après une preuve discriminante dont l'ancre et la provenance ont été vérifiées. Elle ne produit jamais de mécanisme physique ni de pronostic.

L'approche brute `evidence_aware` est conservée uniquement comme diagnostic de classement. Elle est explicitement interdite comme politique automatique de claim, car les tests adversariaux ont montré qu'un registre ou un événement faux peut la rendre très convaincante et néanmoins erronée.

## Ce qui a été construit

- registre d'équipements partiel sans imputation des champs inconnus ;
- résumé reproductible d'occurrences en composant électrique anonyme, avec incertitudes et provenance ;
- quatre politiques comparées : amplitude, contexte, preuves brutes et preuves gardées ;
- candidat structurel `unknown / non_attributed` ;
- identifiabilité explicite, dont équivalence observationnelle et actif probablement absent ;
- journal append-only révisable de preuves favorables et défavorables ;
- micro-questions classées par entropie, élimination attendue et VOI corrigée de l'effort, de la disponibilité et de la fiabilité ;
- exploitation prudente d'événements naturels avec audit des co-événements ;
- plan de mesure temporaire de dernier recours et réutilisation historique refusée en cas de dérive ;
- validation déterministe du plafond de claim afin qu'une rédaction ne puisse pas promouvoir le niveau de preuve.

## Échelle de preuve préservée

La couche distingue : changement détectable → signature reproductible → composant anonyme → famille compatible → actif probable → attribution robuste. Son plafond absolu est `ROBUST_ATTRIBUTION`. Les niveaux `PHYSICAL_MECHANISM` et `PROGNOSIS` sont hors de cette API.
Un `compatibility_score` est une proximité heuristique explicable ; `posterior_probability` reste toujours `null`, faute de modèle statistique calibré.

## Protocole de validation

Le benchmark contient 200 cas synthétiques : 20 scénarios obligatoires × 10 seeds. Les cinq premiers seeds forment DEVELOPMENT et les cinq nouveaux seeds HOLDOUT. Les réponses sont écrites et hachées avant l'ouverture de la vérité privée. Cette séparation évite une fuite directe, mais le HOLDOUT ne constitue qu'un changement stochastique : il ne prouve pas une généralisation inter-sites.

Engagement public : `9d060a671bdcf5214b6471ae57bee15646578f29a27e2432a535d08f4df40765`.  
Engagement vérité privée : `d87078ccc2672f5cc8251f9d06ab5649324018fd63ecd60c6a4e6fbcc51a2d53`.

## Comparaison principale

| Méthode | Précision nommée | Faux attrib. | Couverture | Refus correct | Perte asym. |
|---|---:|---:|---:|---:|---:|
| `amplitude_only` | 100.0 % | 0.0 % | 20.0 % | 100.0 % | 0.150 |
| `contextual` | 100.0 % | 0.0 % | 25.0 % | 100.0 % | 0.100 |
| `evidence_aware` | 100.0 % | 0.0 % | 35.0 % | 100.0 % | 0.000 |
| `guarded_evidence` | 100.0 % | 0.0 % | 10.0 % | 100.0 % | 0.250 |

Les 100 % de précision du benchmark principal ne doivent pas être lus isolément : les cas ont été conçus pour tester les états attendus. La différence décisive apparaît dans les falsifications et la corruption de registre. La politique gardée nomme 20/200 cas (10.0 %), sans fausse attribution observée, mais s'abstient sur 71.4 % des cas synthétiquement attribuables. Ce coût de couverture est volontaire.

DEVELOPMENT : 75/100 décisions correctes ; HOLDOUT : 75/100. Aucun écart de seed n'est observé.

## Micro-questions

La stratégie VOI corrigée de la réponse disponible et de l'effort choisit la question cible dans 100.0 % des cas applicables, contre 33,3 % pour l'information gain pure. Le gain sélectionné moyen est 0.792481 bit et la réduction réalisée moyenne 0.792482 bit, avec 1.0 interaction lorsque la question est répondue.

Une falsification supplémentaire altère la partition candidat→réponse. Avec 50 % d'erreurs non déclarées, la stratégie VOI choisit encore la question fragile dans 100.0 % des cas et son gain réalisé tombe à 0.976 bit. Lorsque le risque est déclaré, elle abandonne cette question (sélection fragile 0.0 %) et obtient 1.000 bit. Elle ne peut donc pas auto-corriger un modèle de réponses faux mais présenté comme certain.

## Falsifications

| Méthode | Attributions correctes | Refus sûrs | Fausses attributions |
|---|---:|---:|---:|
| `amplitude_only` | 0 | 5 | 1 |
| `contextual` | 0 | 3 | 3 |
| `evidence_aware` | 0 | 3 | 3 |
| `guarded_evidence` | 0 | 6 | 0 |

Les échecs préservés sont : horaire inventorié obsolète, puissance nominale trompeuse, co-événement absent du journal et canal temporaire mal étiqueté. Le marquage `overlap_ambiguous` bloque correctement l'actif fictif créé par deux charges simultanées. La politique gardée refuse les six cas adversariaux ; ce résultat synthétique ne garantit pas qu'elle détectera toutes les erreurs de provenance réelles.

## Robustesse aux erreurs de registre

| Corruption non signalée | Méthode | Couverture | Précision | Faux attrib. | Perte (FP=10, refus=1) |
|---:|---|---:|---:|---:|---:|
| 0.0 % | `contextual` | 100.0 % | 100.0 % | 0.0 % | 0.000 |
| 0.0 % | `evidence_aware` | 100.0 % | 100.0 % | 0.0 % | 0.000 |
| 0.0 % | `guarded_evidence` | 22.8 % | 100.0 % | 0.0 % | 0.772 |
| 25.0 % | `contextual` | 100.0 % | 75.2 % | 24.8 % | 2.480 |
| 25.0 % | `evidence_aware` | 100.0 % | 79.8 % | 20.2 % | 2.020 |
| 25.0 % | `guarded_evidence` | 20.0 % | 100.0 % | 0.0 % | 0.800 |
| 50.0 % | `contextual` | 100.0 % | 49.0 % | 51.0 % | 5.100 |
| 50.0 % | `evidence_aware` | 100.0 % | 60.2 % | 39.8 % | 3.980 |
| 50.0 % | `guarded_evidence` | 21.4 % | 100.0 % | 0.0 % | 0.786 |

Les taux de corruption sont des interventions synthétiques, pas une estimation de fréquence terrain. Ils montrent néanmoins la pente du risque : à 25 % d'étiquettes permutées non signalées, le contexte brut atteint 24,8 % de fausses attributions, tandis que la politique gardée reste à 0 % et couvre environ le taux d'ancres vérifiées (20 %). Une incertitude de registre explicitement déclarée est neutralisée ; une erreur présentée comme certaine reste fondamentalement indétectable sans preuve indépendante.

## Réutilisation historique

Une première distance moyenne a été falsifiée : elle diluait une forte dérive univariée. La règle retenue exige maintenant une distance moyenne ≤ 0.10 et une distance par dimension ≤ 0,25. Sur 25 cas synthétiques, elle obtient 10 vrais réemplois, 15 vrais refus, 0 faux réemploi et 0 faux refus. Ce seuil n'est pas calibré pour un site réel.

## PX-201

Le scanner reproductible a examiné 2155 fichiers ou archives dans les emplacements de fixtures et n'a trouvé aucune donnée PX-201 exploitable. Le cas réel n'a donc pas été reproduit et aucune valeur réelle `+2.7 kW`, `06:00–22:00` ou attribution n'est revendiquée. Les scénarios synthétiques qui ressemblent à ce format restent explicitement synthétiques.

## Ce qui fonctionne et ce qui ne fonctionne pas

Fonctionne sur les expériences contrôlées : conservation de `unknown`, refus de l'équivalence, réduction d'incertitude par une question simple, promotion après ancre vérifiée, révision du journal et refus après dérive. Ne fonctionne pas sans hypothèse supplémentaire : corriger une identité d'actif fausse mais non signalée, découvrir un co-événement absent, séparer de façon générale des charges superposées ou valider l'identité d'un canal terrain.

## Nouveaux risques

- confiance excessive dans la qualité du registre ;
- confusion entre score de compatibilité et probabilité ;
- ancre terrain mal étiquetée ;
- quasi-expérience confondue par une action non journalisée ;
- réutilisation historique au-delà d'un changement de régime ;
- couverture trop faible si le mode gardé devient une fin plutôt qu'un déclencheur de micro-question.

## Recommandation R&D suivante

Intégrer cette couche seulement en **shadow mode local** sur des dossiers réels prospectifs. Pré-enregistrer l'inventaire, l'identité des canaux, les événements et la question avant de voir l'issue ; mesurer séparément précision, refus, couverture et contradictions. Le prochain jalon doit comprendre plusieurs sites, des registres imparfaits réels, des événements négatifs et au moins une ancre temporaire vérifiée par site. Toute probabilité, mécanisme ou capacité de pronostic reste interdite avant calibration et validation indépendantes.

## Conclusion

L'architecture apporte une valeur suffisante pour une intégration expérimentale : elle transforme une signature pauvre en liste explicable de compatibilités, sait dire pourquoi elle ne peut pas départager les derniers candidats et choisit une information minimale. Elle n'apporte pas encore une attribution industrielle autonome démontrée. Le refus gardé est le résultat principal de cette phase, pas une limitation à dissimuler.
