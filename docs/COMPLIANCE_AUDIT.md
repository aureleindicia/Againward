# Audit de conformite a `AGENTS.md`

Date de verification : 27 aout 2026.

Cet audit distingue une preuve reproductible d'une intention architecturale. Les statuts sont :

- **PROUVE** : code ou artefact present, avec test ou commande reproductible adaptee ;
- **PARTIEL** : principe present mais couverture encore insuffisante pour tout nouveau client ;
- **A FAIRE** : exigence explicite non encore satisfaite.

## Exigences 1 a 16 — architecture et fondations

| # | Statut | Preuve actuelle ou ecart restant |
|---:|---|---|
| 1 | PROUVE | Separation Codex/Python montree par `workspace/demo_investigation.py`, la review et les resultats quantitatifs. |
| 2 | PROUVE | Calculs dans `energy_mvp/`, choix et interpretation dans le journal d'investigation. |
| 3 | PROUVE | Le pipeline automatique ne produit que des `candidate_signal`; Codex conserve ou rejette huit hypotheses. |
| 4 | PARTIEL | Boucle complete H01-H08 sur la demo; orchestration a refaire par Codex pour chaque nouveau client. |
| 5 | PROUVE | Chaque hypothese importante contient alternatives, contre-tests et `best_reason_false`. |
| 6 | PROUVE | `workspace/demo_review.py` execute une review distincte avant synthese. |
| 7 | PROUVE | La review lit les JSON quantitatifs; les nombres ne sont pas recalcules dans le rendu. |
| 8 | PARTIEL | Unites, fuites temporelles et invariants sont testes; l'audit numerique exhaustif reste a etendre aux contextes invalides. |
| 9 | PROUVE | Depot initial inspecte, scripts executes et rapport mensuel reproduit avant extension. |
| 10 | PROUVE | `MeasurementKind`, conversions W/kW/MW et Wh/kWh/MWh, refus des unites ambigues. |
| 11 | PROUVE | `generate_demo.py` produit 120 jours a 15 minutes de maniere deterministe. |
| 12 | PROUVE | Charge fixe, production, horaires, week-ends, shifts, temperature, mix et bruit simules. |
| 13 | PROUVE | Six familles d'anomalies et cinq incidents de donnees dans une ground truth separee. |
| 14 | PROUVE | Appariement evenementiel et metriques precision/rappel/F1 dans `validation.py`. |
| 15 | PROUVE | Detecteur generique explicitement borne a `candidate_signals_only`. |
| 16 | PARTIEL | Toolbox composable importante disponible; des comparaisons multi-compteurs et change-points plus generiques restent possibles. |

## Exigences 17 a 32 — outils, baselines et quantification

| # | Statut | Preuve actuelle ou ecart restant |
|---:|---|---|
| 17 | PROUVE | `docs/ANALYSIS_TOOLS.md` documente objectif, entree, sortie, hypotheses, limites et exemples. |
| 18 | PROUVE | `workspace/` isole experiences, calculs ad hoc et validation. |
| 19 | PROUVE | Les apprentissages sont devenus fonctions/tests; aucune donnee client n'est presente. |
| 20 | PROUVE | Baselines lineaire, active/inactive, temporelle et rolling median. |
| 21 | PROUVE | MAE, RMSE, R2, MAPE conditionnel et decoupage passe-vers-futur testes. |
| 22 | PROUVE | Consommation inactive presentee comme observee et non comme inutile/recuperable. |
| 23 | PROUVE | Charge de base par quantiles et mediane basse; minimum seulement comme temoin. |
| 24 | PROUVE | Intensite calculee sans division par zero et critiquee a faible production dans H07. |
| 25 | PROUVE | Derive progressive, efficacite et changement de niveau recherches separement. |
| 26 | PROUVE | Pics regroupes, contextualises et H08 rejete comme doublon de H03. |
| 27 | PROUVE | `AnalysisEvent` impose champs, periode, duree, energies, cout, severite, confiance et liens. |
| 28 | PROUVE | Severite et confiance sont deux champs distincts dans l'investigation. |
| 29 | PROUVE | `--price-per-kwh` et calcul deterministe; aucun tarif complexe premature. |
| 30 | PROUVE | Surconsommation, cout associe et part recuperable sont separes partout. |
| 31 | PROUVE | `annualize_effect()` refuse evenement ponctuel, periode courte, faible couverture ou representativite non documentee. |
| 32 | PROUVE | Union temporelle testee; chevauchement H04/H05 traite et total portefeuille retenu. |

## Exigences 33 a 48 — qualite, investigation et rapports

| # | Statut | Preuve actuelle ou ecart restant |
|---:|---|---|
| 33 | PROUVE | Lignes, periode, frequence, couverture, trous, doublons, valeurs manquantes par colonne, timestamps, impossibles, changements de frequence et outliers sont suivis. |
| 34 | PROUVE | Suppressions, deduplication, tri, unites, index, fuseaux et contextes invalides sont traces. |
| 35 | PROUVE | `reports/investigation.json` contient observations, tests, resultats, alternatives, decisions et confiance. |
| 36 | PROUVE | H07 et H08 sont explicitement rejetees. |
| 37 | PROUVE | Toutes les pistes H01-H08 ont test, quantification, alternative, limite et decision. |
| 38 | PROUVE | Review adversariale distincte, avec nouveaux controles et audit de chevauchement. |
| 39 | PROUVE | Decisions finales conformes : confirme, reserve ou rejete. |
| 40 | PROUVE | Rapport final hierarchise faits, interpretations, causes non prouvees et verifications. |
| 41 | PROUVE | Opportunites finales presentent observation, recurrence, preuves, impact, confiance et limites. |
| 42 | PROUVE | Les quatorze sections recommandees sont presentes dans le rapport final. |
| 43 | PROUVE | `AnalysisBundle` et `AnalysisEvent` alimentent JSON/Markdown/HTML sans recalcul critique. |
| 44 | PROUVE | Quatre PNG analytiques utiles, sans interface graphique ni dependance lourde. |
| 45 | PROUVE | HTML/CSS autonome leger et lisible sur mobile. |
| 46 | PROUVE | 66 tests couvrent notamment unites, temps, aggregation multi-mois, baselines, evenements, couts, annualisation et double comptage. |
| 47 | PROUVE | Vide, mesure unique, production nulle, constante, sans anomalie, anomalie massive, sans tarif, mensuel et irregularite sont explicites. |
| 48 | PARTIEL | Energie, cout, hors-production, exces et chevauchement controles; borne economie/cout total a formaliser si une economie est publiee. |

## Exigences 49 a 65 — demonstration, exploitation et trajectoire

| # | Statut | Preuve actuelle ou ecart restant |
|---:|---|---|
| 49 | PROUVE | Suite reproductible generateur -> analyse -> investigation -> review -> rapport. |
| 50 | PROUVE | `reports/validation.json` lit la ground truth seulement apres la review. |
| 51 | PROUVE | Cinq profils, trois seeds anormaux et un seed normal chacun. |
| 52 | PROUVE | Tous les chiffres critiques proviennent des scripts Python et sont serialises. |
| 53 | PROUVE | Aucune API OpenAI integree. |
| 54 | PROUVE | Local-first, aucune telemetrie; `.gitignore` protege les espaces clients. |
| 55 | PROUVE | Positionnement de pre-diagnostic explicite dans tous les rapports. |
| 56 | PROUVE | Les observations solides sont affirmees clairement, sans inventer la cause physique. |
| 57 | PROUVE | `create_workspace.py` cree l'isolation input/processed/scratch/outputs et refuse tout ecrasement. |
| 58 | PROUVE | Aucun SaaS, React, paiement, cloud, microservice ou base vectorielle. |
| 59 | PROUVE | Benchmarks 10k/100k/500k; 500k reste acceptable sans Polars/DuckDB. |
| 60 | A FAIRE | Le dossier importe ne contient pas de metadonnees `.git`; aucun commit ne peut encore prouver l'historique. |
| 61 | PROUVE | Travail autonome, sans secret ni action externe. |
| 62 | PARTIEL | Sequence complete prouvee sur la demo; un nouveau client depend encore de l'exploration Codex ad hoc, ce qui est voulu, mais le cadrage de workspace doit etre formalise. |
| 63 | PROUVE | Les signaux automatiques restent candidats et la selection H01-H08 apporte une valeur distincte. |
| 64 | PROUVE | Python est la seule source des nombres; la review ne modifie pas les valeurs. |
| 65 | PROUVE | Les sept etapes immediates ont ete executees au moins sur le scenario de demonstration. |

## Prochaines preuves prioritaires

1. Etendre l'investigation agentique a un second dataset de forme differente de la demo principale.
2. Ajouter des comparaisons multi-compteurs lorsque des donnees adaptees existent.
3. Formaliser davantage les criteres de severite sans automatiser la decision analytique.
4. Initialiser un historique Git local et produire des commits coherents apres verification.

Les performances multi-scenarios actuelles sont : 90 vrais positifs, 2 faux positifs,
0 faux negatif, precision 0,9783, rappel 1,0000 et F1 0,9890. Ces valeurs sont une preuve de
non-regression sur les scenarios synthetiques, pas une garantie de performance client.
