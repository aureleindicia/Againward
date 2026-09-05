# Audit de complétude — phase R&D MinimalEvidenceAttribution

## Source et périmètre

Le document `INDICIA_MINIMAL_EVIDENCE_ATTRIBUTION_RND_GOAL.md` a été lu intégralement :
535 lignes, 18 888 octets, SHA-256
`c2ce89f60fc347f74f60bf0b4999e97ae3618da0c3047eed50b43306d7442f50`.
Il n'était pas présent dans le dépôt ; seule la copie explicitement fournie dans le stockage
local a été lue. Aucun fichier extérieur n'a été modifié.

L'architecture, les handoffs, les résultats R&D stages 1–4, les benchmarks Signal Intelligence
et Physical Expertise, les rapports client, les tests et les calculs fondamentaux existants ont
été inspectés. La nouvelle couche est additive et n'a pas remplacé les API stables.

## Axes A–J

| Axe | Preuve d'implémentation | Preuve de validation | Statut |
|---|---|---|---|
| A — registre incomplet | `EquipmentRecord`, champs `None`, `unknown_fields`, fiabilité par champ | tests partiel/invalide/corruption déclarée | atteint |
| B — composant anonyme | `ComponentOccurrence`, `build_anonymous_component`, heures circulaires, incertitudes, `overlap_ambiguous` | tests provenance/minuit/superposition + scénarios 9–11 | atteint avec séparation générale non démontrée |
| C — compatibilité | amplitude, contexte, preuves brutes, politique gardée, `unknown`, scores non probabilistes | comparaison 200 cas + corruption + falsifications | atteint ; méthodes brutes limitées à shortlist |
| D — identifiabilité | six statuts et booléen « même type de données utile » | scénarios équivalence, insuffisance, absent, bruit | atteint |
| E — micro-questions | entropie, élimination, VOI/effort/disponibilité/fiabilité | trois stratégies + falsification de partition | atteint sous partitions fournies |
| F — événements naturels | `NaturalOperationalEvent`, audit de portée, génération de preuve | événement discriminant/non discriminant/co-événement caché | atteint avec audit externe requis |
| G — mémoire locale | `EvidenceLedger` append-only, supersession, contradictions, historique d'assessments | tests révision et conflit | atteint |
| H — mesure temporaire | plan de dernier recours, cycles/durée/decision/sécurité | mesure résolutive et mesure courte insuffisante | atteint ; durée heuristique |
| I — ancre historique | distance multidimensionnelle et refus de dérive | 25 cas, 5 seeds, ablation de seuils | atteint synthétiquement |
| J — niveaux de preuve | `EvidenceLevel`, finding machine-readable, validator et schema JSON | tests de promotion frauduleuse | atteint jusqu'à attribution robuste uniquement |

## Vingt scénarios obligatoires

| # | Scénario du cahier | Identifiant exécutable |
|---:|---|---|
| 1 | actif facile | `easy_asset` |
| 2 | deux actifs distincts | `two_distinct_assets` |
| 3 | presque identiques | `two_nearly_identical` |
| 4 | équivalents observationnels | `observationally_equivalent` |
| 5 | actif absent | `real_asset_absent_inventory` |
| 6 | mauvais candidat plausible | `plausible_wrong_candidate` |
| 7 | information terrain erronée | `wrong_field_information` |
| 8 | information contradictoire | `contradictory_field_information` |
| 9 | dérive de signature | `signature_drift` |
| 10 | charges simultanées | `simultaneous_loads` |
| 11 | signature faible | `weak_signature_in_aggregate` |
| 12 | événement discriminant | `discriminating_natural_event` |
| 13 | événement non discriminant | `non_discriminating_natural_event` |
| 14 | question utile | `useful_micro_question` |
| 15 | question inutile | `useless_micro_question` |
| 16 | mesure résolutive | `temporary_measurement_resolves` |
| 17 | mesure courte insuffisante | `short_measurement_insufficient` |
| 18 | historique insuffisant | `insufficient_history` |
| 19 | bruit/manquants | `noisy_missing_data` |
| 20 | meilleure conclusion unknown | `best_conclusion_unknown` |

Chaque scénario est instancié sur dix seeds, soit 200 réponses par approche. Le manifest et les
hashes de vérité/réponses se trouvent dans
`reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_RESULTS.json`.

## Métriques demandées

| Exigence | Chemin machine-readable |
|---|---|
| précision, fausse attribution, refus, couverture | `approach_comparison` et `retained_policy.benchmark_metrics.attribution` |
| calibration | `confidence_calibration_diagnostic` ; posterior explicitement absent |
| rank/top-k | `retained_policy.benchmark_metrics.ranking` |
| incertitude/information/interactions | `retained_policy.benchmark_metrics.micro_questions` |
| information erronée | `registry_corruption_full_experiment` et `question_misspecification` |
| stabilité temporelle | `historical_anchor_drift` |
| coût asymétrique | pertes FP=5/refus=1 dans le benchmark, FP=10/refus=1 en robustesse |

## Falsifications et décisions

Les six cas adversariaux sont conservés dans `falsifications.cases`. Ils ont rejeté l'attribution
automatique par contexte ou preuve brute (trois fausses attributions chacun) et retenu la
politique gardée (six refus sûrs, zéro fausse attribution). Une falsification distincte a rejeté
la distance historique moyenne seule. Une autre démontre qu'une micro-question mal modélisée
reste trompeuse si son risque n'est pas déclaré.

Ces résultats ne sont pas convertis en preuve terrain. La revue complète est dans
`reports/MINIMAL_EVIDENCE_ATTRIBUTION_ADVERSARIAL_REVIEW.md`.

## PX-201

`scan_px201_fixture_sources()` a parcouru les dossiers de fixtures et les archives racine. Résultat :
aucune fixture data-like, `fixture_available=false`. Conformément au cahier, aucune information
réelle PX-201 n'a été fabriquée. L'exemple conceptuel dans la documentation est marqué synthétique.

## Livrables 1–10

1. Prototype : `energy_mvp/minimal_attribution.py`.
2. Tests : `tests/test_minimal_attribution.py` et `tests/test_minimal_attribution_benchmark.py`.
3. Benchmark : `benchmarking/minimal_attribution_benchmark.py` et CLI racine.
4. Résultats machine-readable : JSON R&D et exemples JSON.
5. Architecture : `docs/MINIMAL_EVIDENCE_ATTRIBUTION.md`.
6. Limites : documentation, rapport et review adversariale.
7. Décisions : `examples/minimal_attribution_decisions.json`.
8. Comparaison : `approach_comparison` et rapport R&D.
9. Falsifications : objet JSON détaillé et review.
10. Prochaine R&D : shadow mode prospectif multi-sites décrit dans le rapport.

## Reproductibilité et tests

Commande de benchmark : documentée dans `benchmarks/minimal_attribution/README.md`. Les réponses
publiques sont écrites et hachées avant lecture de `private_truth.json`. Les sorties de travail
sont ignorées par Git ; les résultats consolidés sont versionnés.

Après commit du moteur afin de satisfaire les contrôles d'intégrité HOLDOUT :

- `python -m pytest -q` → **310 passed** en 73,48 s ;
- `python -m pytest -q tests prospecting/tests research/indicia_rnd research/indicia_rnd_stage2 research/indicia_rnd_stage3` → **368 passed** en 170,88 s.

## Limites empêchant une revendication supérieure

- aucune fixture PX-201 ;
- aucune validation prospective sur site ;
- HOLDOUT stochastique, non structurel ;
- qualité de registre et identité d'ancre fournies de l'extérieur ;
- désagrégation générale impossible sous équivalence ;
- seuils de réutilisation non calibrés terrain ;
- aucune probabilité postérieure, causalité, économie, mécanisme ou défaillance prédite.

## Verdict de complétude

Les actions et livrables définis pour cette **phase R&D** sont présents, exécutés et audités.
Le résultat de la phase n'est pas « attribution résolue » : c'est un prototype falsifiable qui
progresse vers l'actif lorsqu'une ancre le permet et refuse sinon. L'intégration durable est
recommandée uniquement en shadow mode jusqu'à validation prospective indépendante.
