# Value Map — extension d’Operational Economics

La valeur d’une investigation n’est pas réduite à un produit kWh × tarif. Cette extension
représente aussi les pistes éliminées, le périmètre mieux défini, une décision devenue possible
et des coûts potentiellement évités **lorsqu’un contrefactuel est documenté**. Elle ne prouve
ni la valeur commerciale d’AGAINWARD ni des économies réalisées.

## Architecture et sources de vérité

`operational_economics.py` conserve ses inputs, hypothèses, effets énergie, actions, contraintes,
relations, décisions et calculs LOW/BASE/HIGH. `value_map.py` est son extension de représentation,
pas un moteur de décision autonome. Les nouveaux jugements sont fournis à
`persist_economic_packet(case, packet)` dans `packet["value_assessment"]` :

```json
{"records": [], "relationships": [], "limitations": []}
```

Ils sont validés dans l’état canonique `investigation/economic_decision_state.json`. La projection
`investigation/value_map.json` est produite par Python. Le reporting la reconstruit depuis l’état
canonique ; modifier ce JSON ne permet pas d’injecter un chiffre dans le PDF. Le handoff économique
de reprise expose également cette extension. Les anciennes API et les anciennes décisions restent
valides ; aucun détecteur ni contrat Evidence Plane n’a été modifié.

L’état conserve `value_map_revisions` : snapshots successifs différents. Les records explicitement
ajoutés ont des IDs immuables ; modifier leur texte, leurs sources ou leur calcul résolu est refusé.
Il faut conserver l’estimation et ajouter un nouveau record. Les sources référencées doivent rester
accessibles, même après ajout d’une nouvelle version d’un input.

## Taxonomie : catégorie et statut sont deux axes différents

| Catégorie | Contenu | Ce qu’elle ne signifie pas |
|---|---|---|
| `DIRECT_ENERGY_VALUE` | Effet Goal B annualisé ou observation historique kWh/MWh sourcée | Excès historique ≠ énergie récupérable |
| `DIRECT_ECONOMIC_VALUE` | Calculs existants : tarif, coût énergétique associé/évitable sous hypothèse, CAPEX, récurrents, autres bénéfices, net et payback | Aucun calcul seul ne prouve un gain réalisé |
| `INVESTIGATION_VALUE` | Pistes considérées/rejetées/restantes, périmètre, faux chemins, temps/interventions potentiellement évités | Réduire dix pistes à deux ne signifie pas réduire le coût de 80 % |
| `DECISION_VALUE` | Avant/après décision et incertitude, action permise/empêchée/reportée, délais sourcés | Aucune conversion automatique en euros |
| `UNVERIFIED_POTENTIAL_VALUE` | Possibilité explicitement non démontrée | Ni fait observé ni promesse commerciale |

Statuts : `OBSERVED_VALUE`, `ESTIMATED_AVOIDED_VALUE`, `POTENTIAL_VALUE`, `REALIZED_VALUE`.
`REALIZED_VALUE` est un statut, pas une catégorie additionnelle à sommer. Il exige
`POST_ACTION_OBSERVED_RESULT`, une action existante, des dates cohérentes et une preuve post-action
persistée. Une estimation reste `PRE_ACTION_ESTIMATE` et n’est jamais réécrite pour lui faire
correspondre le résultat. Les temps potentiellement évités restent contrefactuels ; les temps
réellement passés ont un autre champ.

Les bases énergétiques existantes restent intactes : `DIRECTLY_MEASURED_HISTORICAL_EXCESS`,
`COUNTERFACTUAL_ESTIMATE`, `MODELED_REDUCTION`, `ENGINEERING_ASSUMPTION`, `SCENARIO_ESTIMATE`.
La Value Map ne répare pas magiquement une annualisation non représentative : l’agent doit
justifier la référence et sa sensibilité dans l’analyse technique.

## Contrat d’un record

Champs de base : `value_id`, `category`, `phase`, `value_status`, `source_status`, `source_refs`,
`finding_ids`, `provenance`, `limitations`. Les dimensions métier inconnues peuvent être absentes
ou null. Les ensembles d’hypothèses inconnus restent null, distincts d’un ensemble vide examiné.

Les quatre confiances `technical_confidence`, `economic_confidence`, `counterfactual_confidence`,
`realization_confidence` restent indépendantes et valent `NOT_CALIBRATED` par défaut. Les autres
niveaux sont `LOW`, `MEDIUM`, `HIGH`. Ils sont des jugements, pas des probabilités calibrées.
Un contrefactuel `UNKNOWN` conserve une confiance `NOT_CALIBRATED`.

`provenance` accepte les listes typées `finding_refs`, `source_refs`, `calculation_refs`,
`client_statement_refs`, `scenario_assumption_refs`, `action_refs`, `decision_refs`. Python les
résout contre le dossier, les findings Goal A, les preuves natives Goal B, les calculs, les
hypothèses et les décisions réellement disponibles. Une référence valide n’établit pas à elle
seule la véracité d’une extraction ou la causalité : la revue doit examiner ce sens.

### InvestigationValue

Les champs qualitatifs incluent `question_resolved`, `initial_search_scope`, `final_search_scope`,
`false_leads_avoided`, `investigation_steps_avoided`, `field_checks_avoided`,
`external_interventions_avoided`, `instrumentation_avoided`. Ils sont sourcés et ne portent pas de
chiffres libres. Les nombres appartiennent aux quantités référencées ; les descriptions restent
qualitatives.

`hypotheses_considered`, `hypotheses_rejected`, `hypotheses_remaining` contiennent des IDs choisis
par l’agent. Les ensembles ne doivent pas se contredire ; si les trois sont renseignés, la partition
est complète. Python calcule `hypothesis_counts`. Il n’infère ni la validité d’une réfutation ni un
pourcentage de coûts évités. Les agrégats `internal_hours_potentially_avoided` et
`external_cost_potentially_avoided` sont des sorties calculées, pas des inputs numériques libres.
Plusieurs interventions ne sont jamais additionnées silencieusement.

### Quantités et temps évité

Les heures proviennent d’une preuve native enregistrée via `record_goal_b_evidence` :

```json
{
  "evidence_id": "GBE-TIME",
  "evidence_type": "GOAL_B_CLIENT_RESPONSE",
  "content": {
    "response_text": "Estimation explicitement reçue du client, avec auteur et date conservés.",
    "measurements": {
      "people": {"value": 2, "unit": "person"},
      "hours": {"value": 4, "unit": "h"}
    }
  }
}
```

Chaque quantité dans le record fournit uniquement des références LOW/BASE/HIGH :

```json
{
  "LOW": {"evidence_ref": "GBE-TIME", "measurement_key": "hours"},
  "BASE": {"evidence_ref": "GBE-TIME", "measurement_key": "hours"},
  "HIGH": {"evidence_ref": "GBE-TIME", "measurement_key": "hours"}
}
```

`time` contient `people_count`, `hours_per_person`, `role`, `source_status`, `source_refs`,
`confidence`, `counterfactual_status`, éventuellement `hourly_cost_refs`. Python multiplie personnes
et heures. Inconnu n’est jamais converti en zéro.

Statuts : `MEASURED`, `CLIENT_ESTIMATED`, `DOCUMENTED_PROCESS_ESTIMATE`, `SCENARIO_ONLY`, `UNKNOWN`.
Seuls les trois premiers constituent une estimation documentée ; `MEASURED` exige un processus
observé. Un temps client exige une déclaration client native. Le caractère documenté d’un processus
n’établit pas qu’il aurait effectivement eu lieu dans ce dossier.

Les sources descriptives autorisées sont `CLIENT_EXPLICIT`, `DOCUMENT_EXTRACTED`,
`OBSERVED_INTERNAL_PROCESS`, `EXTERNAL_QUOTE`, `SCENARIO_ASSUMPTION`, `UNKNOWN`.
Pour une hypothèse non monétaire, réutiliser `ScenarioAssumption` avec
`quantity_type=NON_MONETARY`, unité `person`, `h`, `day`, `count`, `kWh` ou `MWh`, sans devise,
`status=SCENARIO` et provenance structurée. La référence est alors `{"assumption_ref":"ID"}`.
Un scénario ne peut pas devenir une estimation documentée par simple changement d’étiquette.

### Monétisation et interventions évitées

`time_saved_hours` et `time_value_eur` sont distincts dans `time_calculation`. Sans coût horaire,
le second reste null. `hourly_cost_refs` doit désigner un input économique ou une hypothèse par
scénario, unité `EUR/h`, devise `EUR`, période `per_hour`. Les sources économiques existantes
sont revalidées ; aucun taux métier n’est fourni par défaut. Une hypothèse de taux reste
`SCENARIO_ONLY` même si les heures sont estimées par le client.

`avoided_actions` peut enregistrer une description, l’action concernée, ses sources,
`was_considered`, `causal_link_supported`, et `cost_refs` optionnel. Le coût doit référencer des
inputs ponctuels EUR. Sans coût, `cost_avoided_eur=null`. Sans action réellement envisagée et lien
raisonnablement documenté, la possibilité reste descriptive et la monétisation est refusée.
Ces attestations restent à contrôler par l’agent et la revue humaine.

Bases contrefactuelles : `DIRECT_CLIENT_STATEMENT`, `DOCUMENTED_STANDARD_PROCESS`,
`HISTORICAL_CLIENT_BEHAVIOR`, `EXTERNAL_QUOTE`, `SCENARIO_ASSUMPTION`, `UNKNOWN`.
Un coût évité chiffré ou un temps potentiellement évité exige une base explicite. Aucun n’est
présenté comme une économie réalisée.

### DecisionValue et valeur de l’information

Champs : `decision_before/after`, `uncertainty_before/after`, `action_enabled/prevented/deferred`,
`evidence_needed_before/after`, `decision_that_changed` (ID canonique). `decision_delay_before/after`
référencent des quantités en jours. Une accélération est calculée uniquement avec les deux délais
et un contrefactuel explicite ; elle peut être négative et n’est jamais monétisée automatiquement.

`INVESTIGATE_FIRST` garde son contrat `evidence_acquisition` : `what_it_resolves`,
`decision_that_can_change`, `cost_or_burden`, `why_worth_it`. Il peut désormais préciser
`information_to_acquire`, `acquisition_burden`, `possible_decision_value`, et
`acquisition_cost={"economic_input_ref":"ID"}`. Aucun score EVSI ou moteur de recommandation
n’est ajouté. Les demandes passent toujours par le lifecycle et `questions.json`.

## Relations et absence de total artificiel

Les catégories restent séparées. Le vocabulaire existant de relations est réutilisé :
`INDEPENDENT`, `OVERLAPPING`, `DEPENDENT`, `ALTERNATIVE`, `SEQUENTIAL`, `UNKNOWN` et
`MUTUALLY_EXCLUSIVE`. Les relations de valeur utilisent `component_a`, `component_b`, `type`,
`rationale`, `source_refs`. Elles ne remplacent pas les relations entre actions.

L’effet énergie et sa traduction économique portent automatiquement `DEPENDENT`. Une relation
non instruite devient `UNKNOWN`. **La Value Map n’offre aucun total transversal, même si toutes
les composantes sont déclarées indépendantes** : son `total_value` reste null. Le portefeuille
économique ancien conserve son périmètre limité ; devise/période différentes et recouvrements
multiples non modélisés conjointement sont refusés. Le PDF revalide également ce total ancien.

## Résultats post-action et approbation humaine

`post_action` référence une action existante, `action_completed_at`, `observed_at`, les sources
Goal B, `comparison_supported=true`, `confounders_reviewed=true`. Chaque preuve doit porter
`content.post_action_observation` avec la même action et les mêmes dates.
Les quantités optionnelles `energy_reduction_kwh`, `actual_intervention_cost_eur`,
`actual_time_spent_hours`, `observed_saving_eur` doivent provenir de mesures de ces mêmes preuves,
jamais de scénarios. Un nouveau record peut citer `pre_action_ref` ; l’ancien reste inchangé.

Les gates privacy et WAITING restent actifs. Le PDF est une préparation de livrable, pas une
approbation humaine. Pour livrer un dossier muni d’une Value Map, la revue humaine doit aussi
référencer son empreinte `value_map_sha256` calculée par `value_map_digest`. Le gate reconstruit
la carte et refuse une projection modifiée ou une approbation périmée. Cette empreinte ne remplace
pas l’approbation réelle ; l’agent ne doit jamais la fabriquer.

## Trois exemples et ce qui peut être additionné

1. **Surconsommation quantifiée.** Un effet annuel et le tarif produisent une exposition économique.
   Les kWh et euros sont deux représentations du même phénomène ; ils ne s’additionnent pas.
   Le bénéfice net est déjà dérivé des bénéfices et coûts inclus : ne pas lui ajouter son brut.
   Le portefeuille d’actions ne peut additionner que des effets compatibles explicitement traités.
2. **Fausse piste éliminée.** La production explique une suspicion de dérive. Une décision
   `DO_NOTHING` peut conserver la valeur de cette réfutation, sans inventer d’énergie évitée.
   Une intervention non documentée reste « possible », coût inconnu. Aucune somme monétaire.
3. **Énergie + temps client.** Une hypothèse de contrôle annoncée par le client donne une plage
   de 8–15 h dans l’exemple exécutable, sans coût horaire : euros du temps inconnus. L’énergie
   annualisée et ces heures ponctuelles restent séparées. Même avec un taux documenté, vérifier
   les recouvrements avec les interventions/net benefit ; la Value Map ne produit pas de total.

Reproduction (dossier de sortie neuf) :

```sh
PYTHONPATH=. python workspace/generate_value_map_examples.py scratch/value_map_examples_nouveau
```

Ce sont des fixtures de contrats et reporting, pas trois pilotes ni une validation de détection.
Elles réutilisent la préparation Goal A/B/C existante et génèrent cartes, PDF et revues pilotes.

## Pilot learning et statistiques ultérieures

`pilot_learning.build_pilot_learning_review` consomme la carte et des appréciations sourcées.
`render_pilot_learning_review` produit `PILOT_LEARNING_REVIEW.md`. Utilité, nouveauté pour le client,
conclusion négative utile, décision concrète, abstention pertinente et valeur principale sont
inconnues tant qu’aucune appréciation étayée n’est fournie. Un seul composant désigné est retenu
pour chaque métrique de valeur ; les composants qui se recouvrent ne sont pas sommés.

`export_authorized_pilot_metrics` exige autorisation et revue de désidentification explicites.
Il n’exporte que des métriques fermées et un ID opaque, aucun chemin, nom, verbatim ou référence
client. L’autorisation complète reste locale. Les obligations de rétention existantes s’appliquent.
L’export ne prouve pas lui-même qu’un consentement a été donné ni qu’un très petit agrégat est
sans risque de réidentification ; la revue humaine reste nécessaire.

`aggregate_pilot_metrics` distingue dénominateurs connus et inconnus, médianes et pourcentages.
Les valeurs énergétiques et économiques sont stratifiées par base d’estimation. Un petit
échantillon produit des descriptifs, jamais une conclusion commerciale automatique. Les sources
synthétiques ne doivent pas être présentées comme des pilotes réels autorisés.
