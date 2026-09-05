# Goal C.2 — Protected-component verification

Références gelées vérifiées avant le freeze C.2 :

- Candidate V2.1 : tag `expert-benchmark-candidate-v2.1`, commit
  `67f4931c729e1f8ad0e2b497e8f71fe291e9586a`.
- Goal A : tag `energy-analyzer-client-pipeline-goal-a`, commit
  `3c62fdff2a7dedd7c8d75042243933234a1ff78c`.
- Goal B.4 : tag `energy-analyzer-operational-economics-goal-b.4`, commit
  `39ed8f872e611fcfa45c50a040385bb67987b931`.
- Goal C.1 de départ : tag
  `energy-analyzer-client-delivery-goal-c.1`, commit
  `63e01cbd887ddb51e15e292dee913f2109930e14`.

Le diff C.2 est limité à la livraison client : `client_delivery.py`, sa
documentation, les générateurs de fixtures/E2E Goal C et les tests Goal C. Il
ne modifie ni `client_intake_pipeline.py`, ni `operational_economics.py`, ni le
moteur Candidate V2.1. L'extension multi-décision Goal B déjà introduite par
Goal C.1 reste inchangée.
