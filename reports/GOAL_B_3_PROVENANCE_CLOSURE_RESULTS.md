# Goal B.3 — fermeture de provenance

## Portée

B.3 ferme les derniers liens de provenance Goal B, sans modifier Goal A ni le
moteur analytique Candidate V2.1. Codex continue de proposer actions,
contraintes, relations, scénarios et décision. Python résout les références,
recalcule les nombres et refuse les chaînes incomplètes.

## Corrections

- Un `EconomicInput` client/document/inféré doit désormais référencer un ou
  plusieurs artefacts/datasets réellement présents dans le cas Goal A.
- Une contrainte factuelle `EXPLICIT` ou `INFERRED` doit référencer une ou
  plusieurs sources canoniques. Les contraintes multi-sources sont supportées.
- `technical_finding_refs` est résolu depuis
  `investigation/structured_findings.json`. Goal B ne peut pas augmenter ou
  modifier le statut ou la confiance techniques.
- L'état persisté contient `recommendation_provenance` : décision → action →
  finding → calcul → inputs/hypothèses → références source réelles.
- L'E2E B.2 régénéré expose effectivement le tarif, le devis et la contrainte
  de production via leurs IDs canoniques Goal A, et non via des noms de fichier
  ou IDs autoréférentiels.

## Vérifications finales

| Contrôle | Résultat |
| --- | --- |
| Can an EconomicInput cite a nonexistent source? | **NO** |
| Can an operational constraint cite a nonexistent source as factual provenance? | **NO** |
| Can Goal B alter the technical status or confidence of a real Goal A finding? | **NO** |
| Can the complete recommendation provenance chain terminate on an unresolved reference? | **NO** |

Les tests B.3 comprennent les refus adversariaux correspondants, une source
Goal A réelle acceptée, une `ScenarioAssumption` autonome, une contrainte
multi-source et la résolution canonique du finding.

## Tests

- suite complète : **207 passed** ;
- contrat Goal B / provenance : **19 passed** ;
- les fixtures B-A → B-O et l'E2E Goal A → Goal B sont rejoués dans ces
  contrôles, sans transformer leurs décisions en règles de production.

Cette fermeture ne prouve pas une économie client réelle et ne déclare pas Goal
C prêt : elle rend simplement les décisions économiques auditables jusqu'aux
sources réellement disponibles.
