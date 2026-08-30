# Entrées économiques et provenance

Une entrée économique possède un identifiant stable, une nature, une valeur et
unité si elle est connue, sa provenance, une source structurée et éventuellement
une confiance qualitative. Les provenances autorisées sont :

- `CLIENT_EXPLICIT` ;
- `DOCUMENT_EXTRACTED` ;
- `INFERRED_FROM_CLIENT_DATA` ;
- `EXTERNAL_ASSUMPTION` ;
- `UNKNOWN`.

Une entrée `UNKNOWN` ne peut porter aucune valeur. Une hypothèse de scénario ne
devient jamais une donnée client parce qu'elle est utilisée dans un calcul :
elle est portée par le type distinct `ScenarioAssumption`, et non par un
`EconomicInput`.

La chaîne d'audit est : décision → calcul de scénario → effet énergétique et
baseline → finding → dataset normalisé/document → artefact Goal A. Pour un coût
d'intervention : décision → CAPEX → devis/facture/scénario → document source.

Un effet énergie porte aussi sa base (`DIRECTLY_MEASURED_HISTORICAL_EXCESS`,
`COUNTERFACTUAL_ESTIMATE`, `MODELED_REDUCTION`, `ENGINEERING_ASSUMPTION` ou
`SCENARIO_ESTIMATE`), sa baseline, son unité annualisée, ses trois scénarios et
ses références. Les chiffres restent donc remplaçables et auditables.

## B.1 — provenance des scénarios calculés

Pour chaque LOW/BASE/HIGH, le calcul persiste les valeurs d'entrée et une liste
de références par composant (`energy_effect`, tarif, CAPEX, coût récurrent,
autre bénéfice). Une référence économique doit désigner un `EconomicInput` ou
une hypothèse `SCENARIO_ASSUMPTION` explicitement stockée ; l'effet énergétique
doit remonter à un finding/preuve. Avant persistance, Python reconstruit le
tableau à partir de ce contrat et refuse une divergence de net benefit, payback,
unité ou devise.

## B.2 — provenance liée à la valeur effectivement utilisée

Une référence ne suffit plus. Pour chaque composant matériel et chaque scénario,
Python exige exactement une source de valeur existante dont le `value`, l'unité,
la devise et la période correspondent à la valeur réellement calculée :

- tarif : `EUR/kWh`, `per_kwh` ;
- coût ponctuel : `EUR`, `one_off` ;
- coût récurrent ou bénéfice annuel : `EUR/year`, `annual`.

Si LOW ou HIGH diffère d'un fait client BASE, cette valeur doit venir d'une
`SCENARIO_ASSUMPTION` persistée portant elle-même la valeur et sa provenance.
Faire pointer 0,18 ou 0,23 EUR/kWh vers un input client de 0,20 EUR/kWh est
refusé. Les effets énergie portent aussi `finding_refs`, qui sont résolus contre
les findings réels de Goal A au moment de la persistance.

## B.3 — source factuelle résolue et chaîne complète

Un `EconomicInput` de provenance `CLIENT_EXPLICIT`, `DOCUMENT_EXTRACTED` ou
`INFERRED_FROM_CLIENT_DATA` porte `source.source_refs` (ou, pour compatibilité
structurée, un unique `artifact_id`/`dataset_id`). À la persistance, Python
résout ces identifiants contre les artefacts et datasets réellement présents
dans le cas Goal A. Un nom de fichier libre ou un `ART-*` inventé ne suffit pas.

Une variation LOW/HIGH reste une `SCENARIO_ASSUMPTION` autonome. Une valeur
introduite après Goal A doit être une hypothèse de scénario ou une
`EXTERNAL_ASSUMPTION` clairement marquée
`source_type=GOAL_B_EXTERNAL_ASSUMPTION`; elle ne simule jamais un document
client.

L'état contient `recommendation_provenance`, une chaîne compacte décision →
action → finding → calcul → inputs/hypothèses → source réelle. Elle n'ajoute
aucune logique de recommandation : elle rend seulement les choix Codex et les
mesures Python auditables.

## B.4 — preuves natives acquises après Goal A

Une réponse obtenue pendant Goal B n'est ni un faux artefact Goal A ni une
`EXTERNAL_ASSUMPTION`. Elle est enregistrée immuablement dans
`economic_decision_state.json#goal_b_evidence`, avec un `evidence_id`, le cas,
le type (`GOAL_B_CLIENT_RESPONSE` ou `GOAL_B_DOCUMENT_RESPONSE`), le contenu
structuré, le lien éventuel vers la demande économique et son ordre
d'acquisition.

Une valeur reçue (par exemple un devis) porte aussi un `structured_value`.
Un `EconomicInput CLIENT_EXPLICIT` la cite avec
`source.goal_b_evidence_refs`; Python vérifie la valeur, l'unité, la devise et
la période au lieu de faire confiance à une simple référence. Une contrainte
opérationnelle peut de la même manière citer une réponse Goal B persistée.

Les sources Goal A explicitement classées `IRRELEVANT` sont refusées pour un
tarif ou une contrainte factuelle, sauf justification structurée explicite de
Codex. C'est un contrôle de cohérence des métadonnées, pas une lecture ou une
interprétation automatique du document.
