# Intake de données pilote

## Demande simple à adresser au prospect

Avant tout devis définitif, envoyez un exemple d'export brut ou une capture de ses en-têtes, ainsi que les réponses suivantes :

1. Quel site et quels équipements/charges le compteur couvre-t-il ?
2. Peut-on exporter au moins 8 semaines horodatées ? Quel pas de temps ?
3. La valeur est-elle une puissance (`kW`), une énergie par intervalle (`kWh`) ou un index cumulé ? Quelle unité exacte ?
4. Quelles données de contexte existent : production, tonnage/cycles, horaires, arrêts, shifts, campagnes, température, tarif ?
5. Quelle décision souhaitez-vous préparer dans les 30–60 jours ?

Formats privilégiés : CSV ou XLSX exportés directement. Ne pas demander de nettoyage manuel ni de conversion d'unités. Exclure mots de passe, données personnelles inutiles et factures complètes si un tarif suffit.

## Gate de faisabilité

| Statut | Conditions | Décision commerciale |
| --- | --- | --- |
| PRÊT | timestamp, valeur, type/unité et périmètre clairs ; ≥8 semaines ; fréquence compatible avec la question | proposer pilote standard |
| PRÊT AVEC LIMITES | couverture ou contexte partiel mais question reformulable | proposer pilote avec limites écrites |
| À COMPLÉTER | colonne/unité/périmètre ambigu, historique trop court, contexte critique manquant | Data Scoping ou demande précise de complément |
| NON ADAPTÉ | seulement mensuel pour question horaire, absence d'export, incohérence non résoluble | ne pas vendre le pilote ; expliquer le besoin minimal |

Une donnée quotidienne/mensuelle peut permettre un profil global, mais pas une conclusion crédible sur nuit, week-end, démarrage ou pic de quart d'heure. Une série puissance à intervalles irréguliers ne doit pas être intégrée silencieusement ; elle est corrigée avec trace explicite ou refusée.

## Cadrage après accord

- Confirmer timezone, convention timestamp (début/fin d'intervalle), unité, compteur et période.
- Identifier changements opérationnels connus : travaux, production, arrêts, changement tarifaire ou de mesure.
- Écrire la question de décision et au plus trois hypothèses initiales ; elles restent des hypothèses, pas des résultats.
- Fixer la personne qui peut vérifier sur site et le format de restitution.
- Définir rétention/destruction des fichiers, contact de traitement et canal de transfert privé adapté à la politique du client.

## Données et confidentialité

La configuration actuelle traite localement les fichiers dans un espace de mission isolé et ne réalise pas d'upload automatique depuis le moteur. Cela ne vaut pas certification de sécurité ni accord de traitement complet. Si les exports comportent des données personnelles ou identifiants, minimiser les colonnes, pseudonymiser quand possible et faire valider les clauses de confidentialité/traitement appropriées avant transfert. Ne promettre aucun chiffrement ou délai de rétention qui n'est pas effectivement mis en œuvre.

Toute suppression, déduplication, conversion, interpolation ou exclusion doit être tracée dans le livrable technique. Les valeurs source restent la référence.
