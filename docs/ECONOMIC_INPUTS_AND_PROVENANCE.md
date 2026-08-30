# Entrées économiques et provenance

Une entrée économique possède un identifiant stable, une nature, une valeur et
unité si elle est connue, sa provenance, une source structurée et éventuellement
une confiance qualitative. Les provenances autorisées sont :

- `CLIENT_EXPLICIT` ;
- `DOCUMENT_EXTRACTED` ;
- `INFERRED_FROM_CLIENT_DATA` ;
- `EXTERNAL_ASSUMPTION` ;
- `SCENARIO_ASSUMPTION` ;
- `UNKNOWN`.

Une entrée `UNKNOWN` ne peut porter aucune valeur. Une hypothèse de scénario ne
devient jamais une donnée client parce qu'elle est utilisée dans un calcul.

La chaîne d'audit est : décision → calcul de scénario → effet énergétique et
baseline → finding → dataset normalisé/document → artefact Goal A. Pour un coût
d'intervention : décision → CAPEX → devis/facture/scénario → document source.

Un effet énergie porte aussi sa base (`DIRECTLY_MEASURED_HISTORICAL_EXCESS`,
`COUNTERFACTUAL_ESTIMATE`, `MODELED_REDUCTION`, `ENGINEERING_ASSUMPTION` ou
`SCENARIO_ESTIMATE`), sa baseline, son unité annualisée, ses trois scénarios et
ses références. Les chiffres restent donc remplaçables et auditables.
