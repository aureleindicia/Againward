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
