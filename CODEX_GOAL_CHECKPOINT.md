# Checkpoint — Candidate V2

## Phase terminée

État initial figé et audit documentaire/architectural de référence terminé.

- HEAD initial : `a37018d29ad214cd41ed7adb0a059797ac20735b`
- branche Candidate V2 : `candidate-v2`
- commit de checkpoint sans changement fonctionnel :
  `ccf9e4eff0cbb9a0735ebab1559a906dcbf425bc`
- baseline analytique : `expert-benchmark-baseline-v1`, commit
  `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`
- empreinte baseline du moteur (32 fichiers) :
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a`
- diff des chemins analytiques protégés avant V2 : vide
- aucune ground truth, aucun payload oracle privé et aucun fichier `revealed/`
  n'a été lu pendant cet audit.

## Fichiers modifiés

- `CODEX_GOAL_CHECKPOINT.md` (nouveau journal de reprise)
- `reports/CANDIDATE_V2_DIAGNOSTIC_PLAN.md` (diagnostic préalable)

Les fichiers utilisateur non suivis présents au départ restent hors périmètre et intacts :
`ENERGY_ANALYZER_MEGA_GOAL.md`, `PROSPECTION_VEILLE_GOAL.md` et
`reports/REALISTIC_CLIENT_TEST_POSTMORTEM.md`.

## Tests

- `pytest -q` : **147 passed** en 15,12 s
- `pytest -q tests/test_physical_expertise_benchmark.py` : **24 passed** en 11,05 s

## Commit courant

`ccf9e4eff0cbb9a0735ebab1559a906dcbf425bc`

## Prochaine action

Concevoir puis implémenter, sans règle par cas, le contrat de raisonnement physique,
la knowledge layer auditable et les outils déterministes à forte valeur générale.

## Tâches restantes

- implémenter la couche de raisonnement et la connaissance par famille ;
- ajouter les calculateurs physiques génériques ;
- durcir le fallback `NO_MATCH` de l'oracle ;
- ajouter les tests synthétiques et la garde anti-hardcoding ;
- documenter et tester Candidate V2 ;
- geler/taguer Candidate V2 ;
- exécuter une seule campagne DEV V2, avec `a17` exclu des agrégats ;
- produire les deux rapports finaux et la revue adversariale ;
- vérifier les empreintes, commits et l'intégrité de V1.


## Contrainte d architecture ajoutee

Le code Candidate V2 ne doit produire ni cause, ni question, ni intervention, ni decision
analytique. Codex reste l enqueteur principal ; Python mesure ; les fiches physiques sont
des references non exhaustives. La revue finale doit inclure un AGENTICITY AUDIT et
considerer comme regression toute amelioration DEV obtenue par un moteur a regles.


## Checkpoint phase 2 — couche physique et oracle V3

### Phase terminée

- couche de raisonnement physique générique et non décisionnelle pour six familles ;
- knowledge layer locale, structurée et non exhaustive ;
- calculateurs Python physiques retournant mesures/limites sans cause ni action ;
- canevas Physical Differential, chaîne énergétique, demande de service et commande/feedback ;
- matcher `semantic-v3-blind-fallback` : un apparent non-match structuré et physiquement
  pertinent passe en revue aveugle ; demandes vagues, hors sujet, non discriminantes ou
  déjà répondues seulement en `NO_MATCH` automatique ;
- protection contre une double révélation dans un même cycle ;
- tests synthétiques de principes, d'agenticité, d'anti-hardcoding et d'oracle ajoutés.

### Fichiers modifiés

- `energy_mvp/physical_diagnostics.py`, `energy_mvp/physical_tools.py`,
  `energy_mvp/workflow.py`, `energy_mvp/__init__.py` ;
- `knowledge/physical_diagnostics/` (six familles et README) ;
- `docs/PHYSICAL_DIAGNOSTICS.md`, `docs/ANALYSIS_TOOLS.md`,
  `docs/CLIENT_WORKFLOW.md`, `docs/PHYSICAL_EXPERTISE_BENCHMARK_IMPLEMENTATION.md` ;
- `benchmarking/physical_expertise.py` ;
- tests Candidate V2 et oracle ;
- `reports/CANDIDATE_V2_DIAGNOSTIC_PLAN.md`.

### Tests

- ciblés Candidate V2/oracle/workflow : **51 passed, 1 deselected** ;
- suite presque complète : **170 passed, 1 deselected** ;
- le test HOLDOUT temporairement exclu exige que les nouveaux chemins moteur soient
  d'abord commités, ce qui est précisément le prochain checkpoint.
- corpus oracle indépendant historique : précision **1.0**, rappel automatique **0.923077**,
  2 cas routés en revue aveugle, 0 faux positif automatique.

### Prochaine action

Créer un commit propre de cette implémentation, exécuter la suite complète y compris la
protection HOLDOUT, corriger uniquement les défauts génériques éventuels, puis figer et
taguer Candidate V2 avant l'unique rerun DEV.
