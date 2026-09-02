# MinimalEvidenceAttribution — architecture R&D

## Rôle et frontière

`energy_mvp.minimal_attribution` est une couche située **après** la détection et la
construction d'une signature reproductible. Elle ne détecte pas une anomalie, ne
désagrège pas le compteur, ne calcule pas d'économie, ne diagnostique pas de mécanisme
physique et ne produit aucun pronostic.

Son entrée est une signature agrégée avec provenance, un registre d'équipements
volontairement incomplet et, éventuellement, quelques preuves locales. Sa sortie indique :

- les actifs compatibles et éliminés ;
- l'hypothèse obligatoire `unknown` ;
- le statut d'identifiabilité ;
- le plafond de preuve autorisé ;
- la prochaine micro-question ou la justification d'une mesure temporaire.

Cette séparation préserve la chaîne :

```text
détection → signature reproductible → composant anonyme
          → compatibilités → actif probable/attribution robuste
          → [autre protocole] mécanisme physique
          → [autre protocole] pronostic
```

## Objets principaux

### `EquipmentRecord`

Registre partiel : identité, famille, puissance ponctuelle ou plage, horaires, jours,
mode continu/intermittent/batch, dépendance à la production, simultanéités, auxiliaires,
installation, maintenances, arrêts et métadonnées locales. Une valeur absente reste
`None` et apparaît dans `unknown_fields`; aucune puissance ou plage horaire n'est imputée.

`metadata.field_reliability` peut diminuer l'influence d'un champ explicitement incertain.
Une fiabilité nulle rend la comparaison neutre (`0.5`), sans inventer la bonne valeur.

### `ComponentOccurrence` et `AnonymousElectricalComponent`

Une occurrence provient d'un détecteur séparé et conserve `source_ref`. La fonction
`build_anonymous_component()` résume les amplitudes, heures circulaires, durées,
fréquence observée, jours observés, stabilité, répétabilité, relation à la production et
incertitudes robustes. Elle n'infère pas la couverture calendaire manquante.

Le champ `separation_status` vaut :

- `aggregate_signature_not_submetering` par défaut ;
- `overlap_ambiguous` si des charges superposées sont plausibles ;
- `field_anchored` seulement après ancre externe.

Un composant anonyme est une régularité du compteur, jamais un sous-compteur virtuel.

### `EvidenceItem` et `EvidenceLedger`

Chaque preuve porte date, direction favorable/défavorable, candidats visés, fiabilité,
provenance, origine observée/inférée, type de source et marqueur synthétique. Une ancre
n'est discriminante que si `anchor_verified=True` : cela signifie que l'identité du canal
ou la portée de l'événement a été contrôlée, pas seulement que l'observation paraît fiable.

Le ledger est append-only. Une correction utilise `supersedes_evidence_id`; l'ancienne
entrée reste auditable mais ne participe plus au calcul courant. Chaque assessment peut
être ajouté à `assessment_history`, ce qui rend une révision ultérieure visible.

## Compatibilité et identifiabilité

`assess_attribution()` compare quatre politiques :

| Politique | Usage autorisé |
|---|---|
| `amplitude_only` | baseline de recherche ; très sensible à la puissance nominale |
| `contextual` | shortlist explicable amplitude/temps/jours/production |
| `evidence_aware` | diagnostic expérimental ajoutant les preuves |
| `guarded_evidence` | politique retenue : ne nomme qu'après discriminateur vérifié |

Les scores sont des `compatibility_score` bornés, pas des probabilités. Le champ
`posterior_probability` reste toujours `null` et son statut explique l'absence de
calibration. Le score `unknown` empêche de forcer le « moins mauvais » actif connu.

Statuts d'identifiabilité :

- `identifiable` ;
- `partially_identifiable` ;
- `multiple_compatible_candidates` ;
- `observationally_equivalent` ;
- `insufficient_evidence` ;
- `likely_absent_from_inventory`.

`observationally_equivalent` implique `more_same_type_data_will_help=false`. Une analyse
plus longue du même compteur ne séparera pas deux empreintes strictement identiques.
`overlap_ambiguous` bloque également toute attribution sans ancre indépendante, car une
somme de charges peut imiter un actif plus puissant.

## Planificateur de micro-questions

`rank_micro_questions()` traite les hypothèses restantes comme un ensemble décisionnel
uniforme. Il ne construit pas de posterior d'actif. Trois stratégies sont comparées :

- information gain / réduction d'entropie ;
- nombre attendu d'hypothèses éliminées ;
- `information_gain × disponibilité × fiabilité / effort`.

La dernière est retenue expérimentalement. Une question dont toutes les hypothèses ont la
même réponse obtient zéro bit. Une question parfaite mais probablement impossible et très
coûteuse peut être classée sous une question un peu moins séparatrice mais disponible.

## Événements naturels et mesure temporaire

`evidence_from_natural_event()` n'émet une preuve discriminante que si : un seul candidat
est visé, aucun co-événement connu n'est présent, la fiabilité atteint le seuil et
`confounder_audit_status=verified_scope`. Un journal incomplet reste une limite physique,
pas un problème que le score peut résoudre.

`plan_temporary_measurement()` intervient seulement si l'ambiguïté demeure et qu'aucune
micro-question disponible n'a une utilité suffisante. Le nombre de cycles (trois ou cinq)
est une heuristique explicitement étiquetée ; une durée en jours n'est fournie que si la
fréquence observée la justifie. Aucune instruction électrique dangereuse n'est générée.

## Réutilisation historique

`reuse_historical_anchor()` exige au moins trois dimensions communes, trois occurrences,
une répétabilité suffisante, une distance moyenne ≤ `0.10` et aucune distance unitaire
> `0.25`. La double condition vient d'une falsification : la moyenne seule diluait une
forte dérive sur une dimension. Une acceptation signifie « signature historique
compatible », pas nouvelle validation physique.

## Plafond de claim

`build_evidence_finding()` expose observé/inféré, preuves, contradictions, alternatives,
identifiabilité, confiance, prochaine information et limites. `validate_evidence_finding()`
compare ensuite cette projection à l'assessment calculé. Il refuse :

- la modification de l'actif sélectionné ;
- la promotion du niveau de preuve ;
- l'ajout d'une fausse probabilité ;
- le retrait des interdictions mécanisme/pronostic/économie récupérable.

Le maximum possible dans cette couche est `ROBUST_ATTRIBUTION`. La confiance qualifie la
solidité de l'assessment, pas la probabilité qu'un actif soit responsable.

## Intégration avec INDICIA

La couche réutilise sans les modifier :

- les timestamps, unités et lectures normalisées ;
- l'Evidence Plane et ses références de source ;
- le détecteur de signaux candidats et le benchmark Signal Intelligence V2 ;
- les protocoles de tests terrain pré-enregistrés ;
- le journal d'investigation et les plafonds de claims ;
- les moteurs physiques et économiques, qui restent en aval et séparés.

L'enchaînement recommandé est : Codex sélectionne une signature candidate, Python la résume,
Codex formule les hypothèses de registre, Python calcule les compatibilités et la question,
Codex examine les contre-explications, puis Python valide le plafond du finding final.

## Exemple minimal

```python
from energy_mvp.minimal_attribution import (
    EquipmentRecord, AnonymousElectricalComponent, assess_attribution,
)

component = AnonymousElectricalComponent(
    component_id="PX201-C01",
    amplitude_kw=2.7,
    typical_start_hour=6.0,
    typical_stop_hour=22.0,
    operating_days=(0, 1, 2, 3, 4),
    stability=0.85,
    repeatability=0.9,
    occurrence_count=30,
)
inventory = [EquipmentRecord(asset_id="asset-A", nominal_power_kw=3.0)]
assessment = assess_attribution(component, inventory, method="guarded_evidence")
assert assessment.selected_asset_id is None  # aucune ancre vérifiée
```

Cet exemple est conceptuel et synthétique. Il ne reproduit pas PX-201.

