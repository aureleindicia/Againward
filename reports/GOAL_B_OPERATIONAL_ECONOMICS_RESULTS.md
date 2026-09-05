# Goal B — Operational Economics / Economic Decision Engine

## Architecture

Goal B ajoute `operational_economics.py`, externe aux composants V2.1/Goal A
gelés. Il contient les contrats pour entrées économiques, effets énergie,
contraintes, actions, relations, décisions, scénarios, provenance et état
persistant. Le handoff économique fournit à Codex le contexte compact nécessaire
pour raisonner; il ne génère ni action, ni priorité, ni décision.

Principaux calculs déterministes : conversion MWh/kWh annuelle, coût évité,
bénéfice annuel net, CAPEX, coût récurrent, payback seulement si positif et
connu, scénarios LOW/BASE/HIGH, tarif time-aligned et portefeuille déclaré.

## Fixtures et E2E

`examples/goal_b_fixture_catalog.json` couvre B-A à B-O : action simple,
investigation avant CAPEX, no-action, contrainte obligatoire, recouvrement,
alternatives, arrêt planifié, tarif inconnu, essai réversible, production
normalisée, coût récurrent et économie SME sparse.

Le cas `examples/goal_b_e2e_case/artisan_sme/` relie Goal A à Goal B avec export
intervalle, production, planning, note maintenance, facture, devis, donnée
ambiguë et fichier hors périmètre. Il contient finding, entrées économiques,
deux actions, contrainte de production, relation séquentielle, scénarios,
demande de devis et décision `INVESTIGATE_FIRST`. Il ne recommande pas le CAPEX
tant que l'inspection ciblée n'a pas départagé la cause.

## Tests et gel

- Suite complète : 204 tests passent.
- V2.1 protégé : identique au tag `expert-benchmark-candidate-v2.1`.
- Empreinte V2.1 protégée : `60b3f1b60bd4eedd0c3efa12ae72638dfc7ce795b478effb479f563ef1dea3b9`.
- Goal A protégé : identique au tag `energy-analyzer-client-pipeline-goal-a`.
- Goal B est gelé par le tag `energy-analyzer-operational-economics-goal-b` ;
  le commit exact et le diff Goal A → Goal B sont enregistrés dans le bundle de revue.
- Goal B reste compatible avec les cas Goal A sans informations économiques :
  tarif/CAPEX inconnus donnent des sorties inconnues, non des valeurs fabriquées.

## Limites et travail différé

Goal B n'implémente ni NPV/IRR, ni finance avancée, ni bases de devis, ni OCR
PDF, ni probabilités de panne, ni monitoring, ni rapport client final. Goal C
devra transformer ces artefacts internes en livrable client, workflow de revue et
suivi de validation.

Les résultats synthétiques démontrent une architecture; ils ne démontrent ni
valeur commerciale, ni économies réalisées, ni précision de coûts chez de vrais
clients.
