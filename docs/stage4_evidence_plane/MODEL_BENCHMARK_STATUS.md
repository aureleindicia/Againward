# Statut du benchmark modèle Stage 4

Statut : **PREPARED_NOT_RUN**.

Aucun endpoint ou runner de modèle externe n’était disponible dans l’environnement local accordé.
Aucun score, préférence de bras, gain de qualité, token count ou conclusion « petit modèle » n’a
été fabriqué.

Le harness exécutable est implémenté dans :

- `benchmarking/stage4_model_harness.py` ;
- `prepare_stage4_model_benchmark.py` ;
- `tests/test_stage4_model_harness.py`.

Il prépare huit conditions randomisées sur le même dossier :

1. contrôle statique legacy ;
2. modèle fort + contexte brut ;
3. modèle fort + Evidence Plane ;
4. petit modèle + contexte brut ;
5. petit modèle + Evidence Plane compact ;
6. petit modèle + Evidence Plane + retrieval ;
7. petit modèle avec escalade pré-déclarée vers le modèle fort ;
8. agent itératif avec primitives analytiques.

Exemple après préparation d’un dossier aveugle :

```sh
python prepare_stage4_model_benchmark.py DOSSIER_CASE DOSSIER_RUN \
  --case-id case_blind_001 --seed 7421 --raw-source DONNEES.csv
```

Chaque condition reçoit un `TASK.md` identique et un `TRANSCRIPT.json` à l’état `NOT_RUN`. Le
manifest exige les mêmes snapshots/efforts à l’intérieur de chaque rôle de modèle, des contextes
frais, l’ordre randomisé, des déclencheurs d’escalade gelés, la trace complète des outils/erreurs,
tokens, latence, coût, réponses finales et deux reviewers aveugles ou une adjudication. Les échecs
critiques incluent chiffre inventé, causalité non étayée, accès à la vérité terrain et signal
candidat présenté comme opportunité confirmée.

Le harness ne contient pas de ground truth et n’implémente aucun proxy de qualité. Une future
exécution doit ajouter des cas client-like réellement indépendants, isoler leur vérité/adjudication,
geler le code et préserver les transcriptions brutes avant tout score.

Le harness Stage 3 gelé reste intact sous `research/indicia_rnd_stage3/model_harness/`; il constitue
un antécédent de recherche, pas un résultat Stage 4.
