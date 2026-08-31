# Statut du benchmark modèle Stage 4

Statut : **PREPARED_NOT_RUN**.

Aucun endpoint ou runner de modèle externe n’était disponible dans l’environnement local accordé.
Aucun score, préférence de bras, gain de qualité, token count ou conclusion « petit modèle » n’a
été fabriqué.

Le harness exécutable est implémenté dans :

- `benchmarking/stage4_model_harness.py` ;
- `prepare_stage4_model_benchmark.py` ;
- `tests/test_stage4_model_harness.py`.

Il prépare trois bras randomisés sur le même dossier :

1. `STATIC_LEGACY` : analyse et candidats historiques ;
2. `RELATIONAL_CARD_V2` : carte compacte relation-aware ;
3. `EXECUTABLE_QUERY` : carte, snapshot, contrat et session de requêtes autonome.

Exemple après préparation d’un dossier aveugle :

```sh
python prepare_stage4_model_benchmark.py DOSSIER_CASE DOSSIER_RUN \
  --case-id case_blind_001 --seed 7421
```

Chaque bras reçoit un `TASK.md` identique et un `TRANSCRIPT.json` à l’état `NOT_RUN`. Le manifest
exige le même modèle exact, snapshot et effort, des contextes frais, l’ordre randomisé, la trace
complète des outils/erreurs, tokens, latence, réponses finales et deux reviewers aveugles ou une
adjudication. Les échecs critiques incluent chiffre inventé, causalité non étayée, accès à la vérité
terrain et signal candidat présenté comme opportunité confirmée.

Le harness ne contient pas de ground truth et n’implémente aucun proxy de qualité. Une future
exécution doit ajouter des cas client-like réellement indépendants, isoler leur vérité/adjudication,
geler le code et préserver les transcriptions brutes avant tout score.

Le harness Stage 3 gelé reste intact sous `research/indicia_rnd_stage3/model_harness/`; il constitue
un antécédent de recherche, pas un résultat Stage 4.
