# Physical Expertise Candidate V2 — résultats DEV Terra

## Périmètre

- Campagne : `CANDIDATE_V2_DEV_TERRA`.
- Moteur : `expert-benchmark-candidate-v2`, commit analytique `7acc43fc00007af87c459fd60cc89d972515c59a`.
- Modèle participant : `gpt-5.6-terra`, effort `high`, pour les 17 runs.
- `case_a17` est exclu : `EXCLUDED_PENDING_CASE_VALIDATION`.
- Les trois runs Sol archivés sont exclus de tout agrégat.
- Aucun score ground truth n’est accessible : ce rapport décrit uniquement les métriques observables.

## Résultats observables

- Cas scellés et vérifiés : **17/17**.
- Cycles de questions : **28** au total, moyenne **1.65**.
- Demandes : **28** au total, moyenne **1.65**.
- Follow-ups révélés : **12**.
- Revues aveugles indépendantes : **15**.
- Coût oracle : **22**.

### Décisions finales

- `CAUSE_CONFIRMED` : 1
- `CAUSE_PROBABLE` : 5
- `INSUFFICIENT_INFORMATION` : 7
- `NORMAL_OPERATION` : 4

### Détail par cas

| Cas | Décision | Cycles | Demandes | Follow-ups | Revues aveugles | Coût oracle |
|---|---|---:|---:|---:|---:|---:|
| b42 | NORMAL_OPERATION | 1 | 1 | 1 | 0 | 2 |
| c08 | INSUFFICIENT_INFORMATION | 3 | 3 | 1 | 2 | 3 |
| d31 | INSUFFICIENT_INFORMATION | 2 | 2 | 1 | 1 | 1 |
| e55 | NORMAL_OPERATION | 0 | 0 | 0 | 0 | 0 |
| f63 | CAUSE_PROBABLE | 2 | 2 | 1 | 2 | 1 |
| g14 | CAUSE_PROBABLE | 2 | 2 | 1 | 1 | 3 |
| h27 | CAUSE_PROBABLE | 3 | 3 | 1 | 2 | 2 |
| j90 | INSUFFICIENT_INFORMATION | 2 | 2 | 1 | 0 | 2 |
| k22 | CAUSE_CONFIRMED | 1 | 1 | 1 | 0 | 2 |
| l48 | NORMAL_OPERATION | 0 | 0 | 0 | 0 | 0 |
| m76 | INSUFFICIENT_INFORMATION | 2 | 2 | 1 | 2 | 1 |
| n05 | CAUSE_PROBABLE | 1 | 1 | 1 | 0 | 2 |
| p39 | INSUFFICIENT_INFORMATION | 1 | 1 | 0 | 1 | 0 |
| q81 | INSUFFICIENT_INFORMATION | 1 | 1 | 0 | 1 | 0 |
| r24 | CAUSE_PROBABLE | 3 | 3 | 1 | 0 | 2 |
| s67 | NORMAL_OPERATION | 1 | 1 | 0 | 1 | 0 |
| t12 | INSUFFICIENT_INFORMATION | 3 | 3 | 1 | 2 | 1 |

## Incidents d’infrastructure

- Une première tentative Terra `b42_run_001` a été abandonnée avant scellement à cause d’un répertoire de reprise incorrect. Le run officiel `b42_run_002` est frais, scellé et le seul agrégé.
- Des adaptateurs temporaires de revue aveugle ont normalisé un champ de justification ; aucune règle analytique ni donnée privée n’a été modifiée.

## Limites

- Sans scorecard indépendante et sans ground truth accessible, aucune affirmation top-1/top-3, faux positif/négatif ou score expert n’est faite.
- Cette campagne DEV vérifie la cohérence du protocole et les comportements observables ; elle ne démontre pas la généralisation.
