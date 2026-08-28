# Vérification de faisabilité des données

Ce document permet de vérifier, avant un pilote, si les données disponibles peuvent soutenir une
investigation de performance énergétique sur données. Il ne constitue pas un audit énergétique et
ne demande pas au site de créer manuellement de nouvelles mesures.

## Objectif

L'objectif est de savoir si un export existant permet de :

- détecter des changements ou dérives de consommation ;
- comparer des périodes de fonctionnement similaires ;
- distinguer une activité normale d'un comportement à vérifier ;
- quantifier une surconsommation observée, sans promettre une économie ;
- préparer une vérification terrain ciblée si les données le justifient.

## Ce que nous demandons en priorité

Un export brut existant du compteur du site, bâtiment ou atelier concerné, idéalement sur **8 à 12
semaines**, au format CSV ou Excel. Une ligne doit correspondre à une mesure ou à un intervalle.

Les éléments indispensables sont :

| Information | Exemple | Pourquoi |
|---|---|---|
| Date et heure | `2026-05-14 08:15:00` | Situer une consommation par rapport aux horaires et événements du site. |
| Valeur mesurée | `42.8` | Mesurer l'énergie ou la puissance. |
| Nature de la mesure | puissance, énergie par intervalle ou index cumulatif | Ces trois formats ne se calculent pas de la même façon. |
| Unité exacte | `kW`, `kWh`, `W`, `Wh`, `MWh` | Éviter une erreur de facteur 1 000 ou de durée. |
| Périmètre du compteur | site entier, atelier, groupe froid, etc. | Éviter d'attribuer une charge au mauvais procédé. |
| Fuseau du site et convention d'horodatage | `Europe/Paris`, début ou fin d'intervalle | Interpréter correctement les horaires et les changements d'heure. |

Une granularité de 10, 15, 30 ou 60 minutes est très utile. Des relevés journaliers ou mensuels
restent exploitables pour un bilan global, mais ne permettent pas de conclure sur les nuits,
week-ends, démarrages ou cycles machines.

### Colonnes minimales possibles

Un seul des trois modèles suivants suffit :

```text
timestamp,power_kw
2026-05-14 08:15:00,42.8
```

```text
timestamp,energy_kwh
2026-05-14 08:15:00,10.7
```

```text
timestamp,cumulative_energy_kwh
2026-05-14 08:15:00,128450.3
```

Ne pas cumuler ou convertir les valeurs manuellement : transmettre l'export tel qu'il est produit
par le compteur, le fournisseur ou le système de supervision, avec une courte explication si
nécessaire.

## Contexte utile, mais non obligatoire

Les informations suivantes servent seulement à départager des explications possibles. Leur absence
ne bloque pas automatiquement l'analyse ; elle limite ce qui pourra être conclu.

| Information | Forme suffisante pour commencer | Ce qu'elle permet de départager |
|---|---|---|
| Horaires habituels | créneaux par jour de semaine | activité normale ou charge hors horaires |
| Production ou marche/arrêt | quantité quotidienne, lots ou simple indicateur actif/inactif | effet de production ou dérive indépendante |
| Arrêts, fermetures, maintenance | quelques dates et motifs | événement normal ou anomalie persistante |
| Changement d'équipement / réglage | date approximative de mise en service | changement de baseline lié dans le temps ou simple variation |
| Température extérieure | seulement si chauffage, froid ou séchage sont importants | météo ou anomalie opérationnelle |
| Tarif | prix moyen au kWh, heures pleines/creuses ou puissance facturée | conversion prudente d'énergie en coût associé |

## Informations à ne pas transmettre

Ne pas transmettre de noms de salariés, clients, coordonnées personnelles, mots de passe,
identifiants de portail, factures complètes ou données de production confidentielles non nécessaires.
Si un identifiant de machine ou de produit est utile, il peut être remplacé par un code interne.

## Réponse rapide demandée avant transfert

Avant tout dépôt de fichier, répondre aux cinq questions suivantes :

1. Quel compteur ou périmètre souhaitez-vous examiner ?
2. Le système peut-il exporter des mesures horodatées ? À quel pas de temps approximatif ?
3. La valeur est-elle une puissance, une énergie par intervalle ou un index cumulatif ? Quelle unité ?
4. Quelle période peut être exportée sans travail manuel important ?
5. Qui peut confirmer les horaires, une intervention ou un changement d'équipement si nécessaire ?

Cette réponse permet de décider objectivement entre :

- **FAISABLE** : données temporelles et périmètre suffisamment définis ;
- **FAISABLE AVEC LIMITES** : analyse globale possible, mais certaines conclusions horaires ou
  causales seront interdites ;
- **NON ADAPTÉ À CE STADE** : seules des factures mensuelles ou des données ambiguës sont
  disponibles ; aucune investigation fine ne sera vendue sur cette base.

## Transmission et suite

Après confirmation du périmètre, le fichier est transmis dans un dossier privé ou une archive
chiffrée. Le mot de passe, le cas échéant, est communiqué par un autre canal. Les données restent
dans un espace local isolé pour ce client et ne sont ni ajoutées à Git ni réutilisées pour un autre
client.

À réception, Energy Analyzer produit d'abord une note de faisabilité : période réellement couverte,
unité reconnue, fréquence, trous, doublons, périmètre connu et analyses réellement possibles. Une
investigation complète ne commence qu'après cette validation.
