# Goal B.4 — fermeture fonctionnelle

## Portée

Cette itération ferme deux contrats fonctionnels restants de Goal B sans
modifier Goal A ni Candidate V2.1 : le vrai résultat Goal A sans finding et la
provenance native des informations acquises après le handoff économique.

## No-finding canonique

`DO_NOTHING` avec `technical_finding_refs: []` est accepté uniquement lorsque
`investigation/structured_findings.json` contient réellement `findings: []` et
un `no_finding` Goal A complet. Le packet doit alors rester vide d'actions,
d'actions considérées et de calculs. Un dossier Goal A sans finding mais sans
conclusion canonique reste refusé.

La fixture B-J représente désormais ce cas réel plutôt qu'un finding
`NORMAL_OPERATION` artificiel.

## Preuves Goal B postérieures à Goal A

L'état économique (schéma 5) contient `goal_b_evidence`. Une preuve est
enregistrée avec un identifiant stable, le `case_id`, son type, le contenu
structuré, le lien à la demande économique quand il existe, l'ordre et la date
d'acquisition. Elle ne peut pas être réécrite sous le même ID.

- Une réponse client contenant un devis peut alimenter un `EconomicInput
  CLIENT_EXPLICIT` avec une valeur, unité, devise et période vérifiées.
- Une réponse opérationnelle peut alimenter une `OperationalConstraint`.
- Le handoff `resume_reasoning` expose ces preuves à Codex avant sa reprise.
- Une référence Goal B inexistante est rejetée.

Les sources Goal A classées explicitement `IRRELEVANT` sont rejetées pour une
entrée économique ou une contrainte factuelle, sauf justification structurée
de Codex. Python ne lit pas le sens libre des documents.

## E2E B.4

`workspace/generate_goal_b_4_e2e.py` et
`examples/goal_b_4_e2e_case/` démontrent l'ordre suivant :

```text
Goal A evidence
→ pre-reasoning handoff
→ Codex reasoning contract
→ economic request
→ client response
→ persistent Goal B evidence
→ resume handoff
→ deterministic calculations
→ persisted Goal B state
```

Le devis et la contrainte de disponibilité sont traçables de la demande à la
preuve native, puis à l'input/contrainte, au calcul déterministe et à la
décision persistée.

## Validation

- `pytest -q tests/test_operational_economics.py` : **25 passed**.
- `pytest -q` : **213 passed**.
- Les fixtures B-A à B-O sont rejouées par les tests; B-J vérifie maintenant
  explicitement une conclusion Goal A `findings=[]` + `no_finding`.

## Composants gelés

Les diffs contre le tag Goal A et le tag Candidate V2.1 ne montrent aucun
changement dans leurs chemins protégés. Goal B.4 ne modifie ni le diagnostic
physique, ni le moteur de raisonnement, ni la sélection déterministe d'une
recommandation.
