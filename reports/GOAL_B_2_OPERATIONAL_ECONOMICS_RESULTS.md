# Goal B.2 — résultats de durcissement

## Portée

Goal B.2 durcit uniquement les contrats de persistance, de provenance et de
portefeuille de Goal B. Il ne choisit aucune action, décision, priorité ou
compatibilité physique : ces éléments restent déclarés par Codex. Python
calcule, valide les unités, les références et la reproductibilité, puis refuse
un état qui ne respecte pas le contrat.

Les chemins analytiques de Candidate V2.1 et de Goal A n'ont pas été modifiés
dans cette mission.

## Correctifs réalisés

- Chaque valeur tarifaire, CAPEX, coût récurrent ou autre bénéfice matériel de
  LOW/BASE/HIGH doit désormais correspondre exactement à une source économique
  structurée unique : valeur, unité, devise et période comprises.
- Une variation LOW/HIGH ne peut plus réutiliser implicitement un input client
  BASE : elle exige une `ScenarioAssumption` explicite et traçable.
- Les `technical_finding_refs`, `action.finding_ids` et
  `energy_effect.finding_refs` sont résolus contre le vrai
  `investigation/structured_findings.json` du cas Goal A.
- Les effets combinés `ECONOMIC` nécessitent une source quantitative
  structurée par scénario. Un montant libre, une unité incompatible ou une
  provenance absente est refusé. Les effets `ENERGY` restent recalculés avec
  le calculateur déterministe.
- Les handoffs sont maintenant deux artefacts distincts : pré-raisonnement et
  reprise après persistance. Le premier n'est jamais écrasé.
- Les fixtures B-A à B-O sont de vrais contrats économiques et opérationnels
  distincts, testés sur leurs propriétés, pas seulement sur leurs labels.

## E2E B.2

La fixture exécutable se trouve sous
`examples/goal_b_2_e2e_case/artisan_sme/`. Son trace documente exactement :

```text
Goal A evidence
→ pre-reasoning handoff
→ Codex reasoning contract
→ deterministic calculations
→ persisted Goal B state
→ optional resume handoff
```

Les artefacts distincts sont :

- `investigation/economic_handoff_pre_reasoning.json`
- `investigation/codex_economic_reasoning_contract.json`
- `investigation/economic_decision_state.json`
- `investigation/economic_handoff_resume.json`

Les générateurs historiques Goal B et B.1 ont aussi été exécutés dans des
répertoires temporaires après le changement de contrat : ils restent
compatibles sans réécrire leurs artefacts historiques.

## Tests

- suite complète : **204 passed** ;
- contrats Goal B.2 : **16 passed** ;
- les tests couvrent notamment finding inexistant, valeur/source incohérente,
  effet combiné arbitraire, relation omise, baseline non réconciliée, contrainte
  dure, scénarios négatifs, handoff séparé et propriétés de B-A à B-O.

## Contrôles finaux

| Question | Réponse |
| --- | --- |
| Can a calculation cite a source whose value does not match? | **NO** |
| Can Goal B reference a nonexistent Goal A finding? | **NO** |
| Can an arbitrary combined economic effect enter the portfolio without validated quantitative provenance? | **NO** |
| Do B-A → B-O now represent genuinely distinct economic/operational situations? | **YES** |

Le résultat ne déclare pas Goal C prêt : une revue indépendante reste requise.
