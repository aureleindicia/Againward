# Corrections implémentées

| Fichier | Avant | Après | Non-régression |
|---|---|---|---|
| `energy_mvp/toolbox.py` | Recette B implicite dans le nominal ; valeurs nouvelles confondues avec la référence | Vocabulaire passé générique, plusieurs recettes/interactions, couverture et catégories non supportées explicites | `tests/test_baseline_categories.py` : bijections, permutations, Unicode, 2/3/4 modalités, rare/nouvelle/manquante, sérialisation, validation sans fuite |
| `energy_mvp/toolbox.py` | Pente arbitraire possible avec prédicteur constant | Support d'une variable constante limité à sa valeur apprise | Production constante déplacée refusée ; production variable réellement normalisée |
| `energy_mvp/signals.py` | Nettoyage des résidus de validation et nouveau split | Trimming apprentissage seul, frontière conservée | Outlier de validation conservé dans le RMSE |
| `energy_mvp/signals.py` | Pas de palier persistant agrégé compteur seul ; marche étiquetée pente | Séries journalières de durée contrôlée, niveau/pente/transitoire distincts, référence calendrier, support exposé | `tests/test_signal_regimes.py` : 10→20, 10→12, baisse, rampe, retour, production identifiable, bruit, semaine, météo et cycle |
| `energy_mvp/signals.py` | Plusieurs vues du même changement commun comptées séparément | Consolidation conditionnelle, facettes conservées en preuve | Même benchmark gelé, 4 TP/8 FP/5 FN → 4 TP/4 FP/5 FN |
| `energy_mvp/quantification.py` (nouveau) | Aire positive facilement lue comme excès net ; références peu comparables | Bilan signé/aires séparés ; sensibilité conditionnelle et abstention explicites | `tests/test_quantification.py` : bilan nul, NaN/inf, fourchette, signe contradictoire, in-sample, trous et justification |
| `energy_mvp/evidence_card.py`, `energy_mvp/workflow.py` | Limites du support peu visibles dans le paquet agent | Couverture, portée/persistance, limites du zéro candidat et estimands visibles | Suite Evidence Plane/workflow, préparation des cinq dossiers d'évaluation |
| `benchmarking/final_workflow.py` (nouveau) | Pas de mesure commune de toutes les étapes | Préparation/scellement/score, candidats distincts des constats finaux, abstentions et ressources | `tests/test_final_workflow_benchmark.py` : omission, doublon, falsification absente, référence numérique absente, mutations, intervalle trop large |
| `tests/test_blind_comparison.py` | Exigeait que le moteur courant reproduise exactement les anciens FP | Archive historique vérifiée inchangée ; moteur courant ne doit pas perdre de TP ni dépasser les FP historiques | Même préparation, mêmes reviews et même scoreur ; aucun label ni critère de benchmark changé |
| `docs/ANALYSIS_TOOLS.md` | Outils nouveaux non découvrables | API, entrées/sorties, hypothèses, limites et exemples documentés | Lecture/reproduction des exemples dans les tests |

## Validation et traçabilité

- Le JSON comparatif contient les sorties complètes des 33 contre-exemples, 14 cas historiques
  et 20 démos, avec hashes des données identiques avant/après ; les probes originaux sont inclus.
- Les erreurs intermédiaires ne sont pas effacées : `after_first` et les logs dans
  `scratch/critical_remediation_20260907/` documentent la fausse extrapolation de production et
  le faux transitoire sur rampe, corrigés avant le résultat retenu.
- Deux tests HOLDOUT imposent un moteur identique au commit déclaré. Ils sont exécutés après
  commit des corrections, sans désactivation de ce contrôle d'intégrité.
- Le benchmark spécialisé V2, les générateurs de données, les truths et les scoreurs historiques
  restent inchangés. Les sorties nouvelles ne sont pas substituées aux archives existantes.

## Reproduire

Depuis la racine du dépôt :

```sh
python -m pytest -q tests prospecting/tests
PYTHONPATH=. python scratch/critical_remediation_20260907/capture.py scratch/critical_remediation_20260907/verification_neuve
python -m benchmarking.final_workflow score scratch/critical_remediation_20260907/end_to_end/manifest.json scratch/critical_remediation_20260907/end_to_end/sealed.json scratch/critical_remediation_20260907/end_to_end/private_truth.json scratch/critical_remediation_20260907/end_to_end/score_reproduit.json
```

Les destinations de capture/scellement/score doivent être nouvelles. Pour une nouvelle session
indépendante, préparer une nouvelle cohorte et faire écrire la soumission avant ouverture de
la vérité ; ne pas recycler les décisions non aveugles de cette remédiation.
