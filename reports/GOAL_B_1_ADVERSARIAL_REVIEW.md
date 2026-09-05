# Goal B.1 — Revue adversariale

## Tests de rupture effectués

- **Double comptage par omission** : deux actions sans relation échouent; une
  omission n'est plus assimilée à `INDEPENDENT`.
- **Baselines incompatibles** : l'agrégation échoue tant que Codex ne fournit
  pas une réconciliation structurée. Le code ne déduit aucune compatibilité.
- **Effet combiné ambigu** : un dictionnaire de nombres nus est rejeté. Les
  effets énergie exigent un recalcul tarifaire déterministe; les effets euros
  directs doivent porter unité, devise, période, baseline et provenance.
- **Nombres agent inventés** : altérer net annual benefit, payback ou les
  entrées de calcul après calculateur entraîne un rejet par reproduction Python.
- **Provenance forgée** : les références d'inputs absentes, et un effet sans
  finding Goal A lié, sont rejetés avant persistance.
- **Relation/action impossible** : calcul lié à une action inconnue et
  relations exclusives/inconnues/séquentielles non modélisées sont refusés.
- **Demande client** : type inconnu rejeté; inférence automatique sans question
  client admise; plus de trois demandes externes refusé.
- **Auditabilité de non-action** : une action considérée mais bloquée apparaît
  dans `considered_action_ids`, jamais dans `selected_action_ids`.

## Risques qui restent volontairement hors du déterminisme

Codex peut déclarer une relation ou une réconciliation physique erronée. Python
ne peut pas l'établir sans transformer Goal B en moteur expert à règles. La
mitigation est l'obligation de rationale et de sources, la revue professionnelle
et la validation avant/après. Les valeurs des documents source peuvent elles
aussi être erronées : B.1 garantit leur traçabilité et ses calculs, pas leur
vérité métier.

## Conclusion critique

Le changement réduit des chemins de sur-agrégation et d'invention numérique
réels. Il peut augmenter les refus lorsque Codex ne déclare pas assez de
structure; c'est voulu pour une sortie économique agrégée, car l'alternative
serait un double comptage silencieux. Une action seule reste utilisable sans
portefeuille agrégé.
