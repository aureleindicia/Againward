# Audit critique du méga-goal

Date de vérification : 27 août 2026.

Cet audit utilise trois statuts : **PROUVÉ** quand une commande et un artefact reproductible
couvrent réellement l'exigence, **PARTIEL** lorsque le mécanisme existe mais que la preuve reste
trop étroite, et **NON PROUVÉ** lorsqu'aucune preuve suffisante n'existe. Un test de schéma n'est
pas traité comme une preuve de pertinence énergétique.

## Résultat d'ensemble

Energy Analyzer n'est plus uniquement une démo codée autour de H01–H08. Il dispose d'un workflow
générique, d'un questionnaire, d'une préparation sans ground truth, d'une toolbox, d'un cycle de
questions/réponses, d'une review adversariale validée et d'un verrou humain de livraison. Trois
sessions Codex indépendantes ont aussi été évaluées à l'aveugle sur six cas publics.

Le résultat ne justifie toutefois pas de parler de produit client mature. Le détecteur Python se
généralise mal sur la batterie indépendante de quatorze cas (F1 0,381), aucune donnée réelle ni
aucun test terrain prospectif n'ont été terminés, et les recommandations n'ont pas été évaluées par
un ingénieur énergie indépendant.

## Matrice des exigences du méga-goal

| Domaine | Statut | Preuve actuelle | Limite restante |
|---|---|---|---|
| Dataset inconnu sans dates/Hxx codés | PROUVÉ | `investigate.py`, `workflow.py`, `test_workflow.py`; trois sessions sur des dossiers publics inconnus | Pas encore de dataset client réel |
| Inspection et limites selon les variables | PROUVÉ | `inspect_dataset`, `intake_assessment.json`, familles désactivées, granularité mensuelle refusée | La matérialité métier d'une variable dépend toujours de Codex |
| Codex choisit tests/hypothèses/contre-explications | PROUVÉ sur synthétique | Reviews v2 figées dans `reports/blind_sessions/`; scripts Python seuls restent des candidats | Seulement six cas et un même modèle de Codex |
| Plusieurs hypothèses concurrentes et falsification | PROUVÉ sur synthétique | 8 à 11 hypothèses par session, faux signaux nuit/week-end/maintenance rejetés | Pas de mesure sur un procédé réel complexe |
| Baselines multiples et temporelles | PROUVÉ | linéaire, activité, temps, rolling passé, météo par degrés, modèles par régime; tests | Choix optimal hors synthétique non établi |
| Régimes, saisonnalité, 24/7 | PROUVÉ comme outils | `summarize_operating_regimes`, `fit_regime_baselines`, cas 24/7/mix/météo | Le détecteur ne segmente pas automatiquement tout changement non déclaré |
| Séparation signal/anomalie/cause/action/économie | PROUVÉ | statuts candidats, décisions, cause physique explicite, recommandations validées, aucune économie si cause non prouvée | Discipline encore dépendante du contrat de sortie Codex |
| Information supplémentaire minimale | PROUVÉ au niveau contrat | `InformationRequest`, extraction de la priorité 1, refus des formulations vagues, 3 demandes aveugles | Pertinence métier non validée par expert indépendant |
| Pas de question systématique si évident | PROUVÉ | décisions confirmées/rejetées interdisent une demande; nature/unité évidentes déduites de l'en-tête | Une cause distincte d'une observation confirmée peut encore nécessiter une vérification de recommandation |
| Test terrain avec prédiction préalable | PROUVÉ comme mécanisme | hash de prédiction, source Python obligatoire, refus d'écrasement/tampering, comparaison après test | Aucun test terrain réel encore exécuté |
| Synthèse dirigeant | PROUVÉ sur démo | Markdown/HTML final avec faits, limites, recommandations et causes non prouvées | Pas de rapport générique évalué par un dirigeant client |
| Workflow client complet | PROUVÉ comme procédure locale | préparation, templates, questions, réponses non réécrites, cycles archivés, gate et validation humaine | Nécessite encore un opérateur Codex compétent et une revue manuelle |
| Rapport révisable et traçabilité | PROUVÉ | `trace.json`, hashes de source/réponses/review/livrables, décision review synchronisée | Pas de signature cryptographique d'identité humaine |
| Confidentialité/local-first/Termux | PROUVÉ | aucune API/télémétrie, `.gitignore`, standard library + `tzdata`, benchmark 500k | RSS ~319 Mo à 500k, élevé pour certains téléphones |

## Validation aveugle

### Python seul — batterie indépendante de 14 cas

Source : `reports/validation_blind.json`.

| TP | FP | FN | Précision | Rappel | F1 | Erreur énergétique absolue moyenne |
|---:|---:|---:|---:|---:|---:|---:|
| 4 | 8 | 5 | 0,333 | 0,444 | 0,381 | 30,75 % |

Cette métrique est l'indicateur principal de généralisation du détecteur. Elle contredit toute
affirmation selon laquelle la détection automatique serait déjà fiable pour un nouveau client.
Les principaux échecs sont les motifs intermittents/cycliques inconnus et la fragmentation de
dérives en plusieurs familles candidates.

### Scénarios apparentés à la démo

Source : `reports/validation_scenarios.json`.

- 20 cas, 230 380 lignes ;
- 81 TP, 0 FP, 9 FN ;
- précision 1,000, rappel 0,900, F1 0,947 ;
- 0 faux positif sur les 5 cas normaux.

Ce bon score est conservé comme non-régression, mais il ne remplace pas la batterie aveugle car le
générateur et les anomalies restent proches de ceux ayant guidé le développement.

### Python + Codex — sous-ensemble aveugle indépendant de 6 cas

Sources : `reports/blind_codex_comparison.json` et reviews brutes figées.

| Système/session | TP temporels | FP | FN | Précision | Rappel | F1 |
|---|---:|---:|---:|---:|---:|---:|
| Python seul, mêmes 6 cas | 1 | 6 | 1 | 0,143 | 0,500 | 0,222 |
| Codex session 1 | 2 | 0 | 0 | 1,000 | 1,000 | 1,000 |
| Codex session 2 | 2 | 0 | 0 | 1,000 | 1,000 | 1,000 |
| Codex session 3 | 2 | 0 | 0 | 1,000 | 1,000 | 1,000 |

Codex a rejeté le pic de maintenance et l'activité nocturne légitime, rejeté les doublons
nuit/week-end créés par les dérives, et découvert le motif cyclique que les règles Python ne
savaient pas typer. C'est une valeur ajoutée mesurée, pas seulement rédactionnelle.

Les réserves sont importantes :

- seulement six cas synthétiques et un seul générateur indépendant ;
- les trois sessions utilisent la même famille de modèle et le même brief ;
- le F1 de type libre exact vaut 0,0, 0,5 et 0,5, car Codex nomme différemment les découvertes ad hoc ;
- le F1 temporel accepte donc volontairement une taxonomie libre et le publie séparément ;
- la quantification kWh de Codex n'était pas standardisée dans ce protocole ;
- aucune recommandation complète n'était demandée aux sessions.

La stabilité des événements retenus est 1,000 en F1 temporel pairwise. L'accord exact sur la
disposition de chaque cas est 0,889 : une session conserve le cycle avec réserves, deux confirment
l'observation tout en laissant la cause insuffisante.

## Questions et effort client

Les trois sessions proposent une seule vérification matérielle, toutes pour la cause du cycle
inconnu : consultation des journaux existants ou observation synchronisée de 2 à 4 heures. Deux
demandes sont d'effort faible et une modérée. Les trois ont une prédiction mesurable et un
responsable identifié. L'audit postérieur atteint 17 critères sur 18 dans
`reports/blind_question_audit.json`.

Cette note n'est pas une validation d'expert : elle prouve surtout que les demandes sont précises,
réalistes et falsifiables. La pertinence réelle devra être jugée pendant un pilote.

## Qualité quantitative

Éléments désormais couverts et testés :

- POWER, ENERGY_PER_INTERVAL et CUMULATIVE_ENERGY ;
- W/kW/MW et Wh/kWh/MWh ;
- convention début/fin, couverture exclusive et différenciation d'index ;
- trous, doublons identiques/conflictuels, fréquence variable et corrections tracées ;
- UTC interne, heure locale opérationnelle, offsets explicites, refus des heures DST inexistantes
  ou ambiguës ;
- validation passé-vers-futur, rolling sans futur et refit robuste tracé ;
- profils par activité/shift/produit/saison ;
- tarification plate, plages traversant minuit et coût mensuel de pointe ;
- annualisation prudente, invariants et déduplication de surconsommation.

La suite compte 112 tests. Cela démontre la cohérence du code couvert, pas l'exactitude de toutes
les baselines possibles sur le terrain.

## Performance Termux

Source : `reports/performance.json`.

| Lignes | Chargement | Analyse | Pic RSS | Total kWh vérifié |
|---:|---:|---:|---:|---:|
| 10 000 | 0,177 s | 0,058 s | 99,2 Mo | oui |
| 100 000 | 1,756 s | 0,581 s | 99,2 Mo | oui |
| 500 000 | 9,227 s | 2,972 s | 319,0 Mo | oui |

La stack actuelle reste assez rapide. La mémoire à 500k impose néanmoins de tester le téléphone
réel du pilote avant d'affirmer que ce volume est confortable partout.

## Notes critiques

| Dimension | Note /10 | Justification |
|---|---:|---|
| Fiabilité quantitative | **8,0** | Fondamentaux, DST, coûts, fuites et invariants fortement testés; pas encore de validation externe sur factures/compteurs réels |
| Qualité de détection | **6,0** | Très bonne non-régression mais F1 aveugle Python de 0,381; Codex améliore fortement seulement sur 6 cas |
| Capacité d'investigation | **7,0** | Valeur Codex démontrée sur 3 sessions, falsification et découverte ad hoc; preuve encore synthétique et taxonomie instable |
| Qualité des recommandations | **6,0** | Contrat opérationnel solide et démo détaillée; aucune action réelle ni évaluation indépendante |
| Valeur commerciale potentielle | **7,0** | Investigation locale autonome, quantification et questions actionnables; ROI, volonté de payer et temps humain non validés |
| Maturité pour un vrai client | **5,5** | Intake, traçabilité et gate existent; aucun pilote réel, aucune validation terrain et dépendance à un opérateur expert |

Aucune note n'est relevée à 8 pour compenser une autre faiblesse. La seule dimension à 8 est la
fiabilité quantitative interne, soutenue par des tests ciblés et des reproductions déterministes.

## Ce qui empêche encore de vendre sans réserve

1. Réaliser au moins trois pilotes sur des données réelles différentes, avec vérification manuelle
   des totaux, factures, calendriers et événements.
2. Exécuter au moins un test terrain pré-enregistré jusqu'à son résultat, avec sécurité et mesure
   avant/après.
3. Faire relire questions, causalité et recommandations par un ingénieur énergie indépendant.
4. Mesurer le temps analyste réel et la part de dossiers qui débouchent sur une action acceptée.
5. Stabiliser une taxonomie d'événements sans empêcher les découvertes ad hoc de Codex.
6. Améliorer le détecteur aveugle sans ajuster ses seuils sur un unique générateur.

Le système est donc praticable pour une **investigation pilote supervisée**, pas encore pour une
prestation automatique ou une promesse contractuelle d'économie. Cette limite de maturité ne
réduit pas le service à la préparation d'un audit réglementaire.
