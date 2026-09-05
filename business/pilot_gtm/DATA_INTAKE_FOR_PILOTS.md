# Intake de données pilote

## Demande simple au prospect

Avant devis définitif, demander un exemple d’export brut ou une capture d’en-têtes et :

1. quel site, compteur et quels équipements sont couverts ;
2. la période, le pas de temps et la timezone ;
3. s’il s’agit de `kW`, d’énergie par intervalle (`kWh`) ou d’un index cumulé ;
4. les contextes existants : production, tonnage/cycles, horaires, arrêts, shifts, campagnes,
   température et tarif ;
5. la décision à préparer dans les 30–60 jours.

Privilégier CSV/XLSX exportés directement. Ne pas demander de nettoyage manuel. Demander au client
d’exclure les mots de passe, tokens, données RH/médicales et données personnelles manifestement
inutiles ; le privacy gate reste néanmoins obligatoire à réception.

## Privacy gate avant faisabilité

Le dépôt reçu est placé temporairement dans `incoming/`. Codex est le premier lecteur sémantique et
décide `PASS`, `SANITIZED` ou `BLOCKED`. Python vérifie ensuite l’absence de motifs évidents et la
préservation des données industrielles avant de créer `privacy_manifest.json` et d’autoriser
`sanitized/` comme source.

Le statut de faisabilité énergétique n’est évalué qu’après `PRIVACY_CLEARED`. En cas de
`PRIVACY_BLOCKED`, ne pas ouvrir les données dans le pipeline métier et convenir d’un nouvel export
minimal ou d’un protocole adapté.

## Gate de faisabilité énergétique

| Statut | Conditions | Décision commerciale |
| --- | --- | --- |
| PRÊT | timestamp, valeur, type/unité et périmètre clairs ; historique et fréquence compatibles | proposer le pilote standard |
| PRÊT AVEC LIMITES | couverture ou contexte partiel mais question reformulable | proposer avec limites écrites |
| À COMPLÉTER | unité/périmètre ambigu ou contexte critique manquant | demande minimale à forte valeur |
| NON ADAPTÉ | granularité incompatible, absence d’export ou incohérence insoluble | ne pas vendre le pilote |

Une donnée mensuelle ne prouve rien sur une nuit, un week-end ou un démarrage. Une série de
puissance irrégulière n’est jamais intégrée silencieusement.

## Cadrage contractuel et fin de mission

- Confirmer timezone, convention des intervalles, unité, compteur et période.
- Identifier travaux, arrêts, changements de production, tarif ou mesure.
- Définir la décision, la personne capable de vérifier le site et la restitution.
- Définir le canal de transfert, la date de purge et les rares livrables à conserver.
- Laisser `derived_retention_authorized: false` sauf autorisation spécifique et finalité démontrée.
- Clore la mission puis exécuter la purge ; conserver `PURGE_RECEIPT.json`.

## Formulation exacte sur le traitement

Le workspace, l’orchestration et les artefacts sont locaux ; le moteur analytique n’effectue pas
d’upload automatique arbitraire et les données client sont exclues de Git. Codex/OpenAI traite
cependant le contenu nécessaire au service selon la configuration utilisée. Ne pas affirmer que
Codex est purement local, qu’aucune donnée ne quitte jamais l’appareil, qu’un chiffrement est fourni
ou qu’une anonymisation parfaite est garantie.

Ces contrôles sont techniques et doivent être alignés avec le contrat applicable ; ils ne
constituent pas un conseil juridique définitif.
