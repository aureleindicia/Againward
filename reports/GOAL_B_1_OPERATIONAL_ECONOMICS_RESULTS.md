# Goal B.1 — Correctif ciblé Operational Economics

## Portée

B.1 corrige des contrats génériques de Goal B. Il ne modifie ni le moteur
analytique V2.1 ni la pipeline Goal A, et ne crée aucun moteur déterministe de
recommandation. Codex choisit toujours les actions, relations, hypothèses,
contraintes, décisions et plans de validation ; Python calcule et refuse les
états numériques ou structurels non reproductibles.

## Correctifs implémentés

- `economic_handoff()` fonctionne avant tout packet Goal B. Il expose les
  findings Goal A, leur incertitude, les documents opérationnels/économiques
  disponibles, les rôles de preuve et les ambiguïtés matérielles, sans décider
  une action.
- L'E2E B.1 matérialise : `Goal A evidence → pre-reasoning economic handoff →
  Codex reasoning contract → deterministic scenario calculations → persisted
  Goal B state`.
- L'agrégation de portefeuille est fail-closed : une relation omise vaut
  `UNKNOWN`; seule une relation `INDEPENDENT` explicite peut être additive.
- Les baselines différentes exigent une réconciliation/compatibilité déclarée
  et traçable par Codex. Python ne décide jamais leur compatibilité physique.
- Les effets combinés sont typés. Un effet énergie combiné doit être recalculé
  par le calculateur déterministe; un effet économique direct porte devise,
  `EUR/year`, période, baseline, scénarios et provenance.
- `persist_economic_packet()` reconstruit tout tableau LOW/BASE/HIGH depuis son
  contrat de calcul. Il refuse action absente, bénéfice/payback inventé, unité
  invalide, calcul non reproductible et provenance inexistante.
- Les demandes économiques ont un vocabulaire fermé et conservent le budget de
  trois demandes externes. `INFER_AUTOMATICALLY` est journalisable mais n'est
  pas une question client.
- Les décisions distinguent `selected_action_ids` et `considered_action_ids` :
  une action rejetée pour contrainte opérationnelle reste auditable sans devenir
  une recommandation.

## Fixtures et E2E

`examples/goal_b_1_fixtures.json` contient les 15 fixtures B-A à B-O avec
findings, effets, inputs, actions, contraintes, relations, demandes et décision
attendue. Les tests les valident réellement; les familles overlap et options
exclusives tentent une agrégation et vérifient le refus.

`examples/goal_b_1_e2e_case/artisan_sme/` est un cas synthétique isolé qui
montre le nouveau handoff pré-raisonnement. L'ancien E2E Goal B est conservé;
son générateur a été rendu compatible avec les contrats B.1.

## Vérification

- `pytest -q` : **205 passed** en 29,35 s ;
- `pytest -q tests/test_operational_economics.py` : **17 passed** ;
- les tests comprennent les refus adversariaux de double comptage par omission,
  baseline non réconciliée, effet combiné non typé, valeurs modifiées après
  calcul, action inexistante, provenance forgée et type de demande inconnu.

## Protection des composants gelés

- Candidate V2.1 : tag `expert-benchmark-candidate-v2.1`, empreinte protégée
  `60b3f1b60bd4eedd0c3efa12ae72638dfc7ce795b478effb479f563ef1dea3b9`.
- Goal A : commit gelé (tag pelé) `3c62fdff2a7dedd7c8d75042243933234a1ff78c`.
- L'ancienne valeur `909196be3439a09fa288e8c634dc12ece0a8dd83` de
  `GOAL_A_COMMIT.txt` est l'objet **annotated tag**, non un commit ni une
  empreinte. Le bundle B.1 utilise explicitement le commit pelé et documente
  séparément l'objet tag.

## Limites

B.1 ne prouve ni une économie client réelle, ni la compatibilité physique
d'une relation déclarée, ni la qualité commerciale d'une action. Les fixtures
testent les contrats et non les décisions de Codex. Goal C n'est pas déclaré
prêt par ce correctif.
