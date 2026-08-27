# Pre-diagnostic energetique agentique — demonstration

## 1. Resume executif

Trois comportements sont confirmes par les donnees : une derive progressive de la charge fixe, une baisse temporaire d'efficacite a production comparable et un nouveau niveau de charge inactive persistant. Trois autres signaux (nuit, week-end et pic ponctuel) meritent une verification operationnelle.

Les kWh ci-dessous sont des surconsommations observees par rapport a une baseline, pas des economies garanties. Aucun total portefeuille ni projection annuelle n'est publie, car certaines fenetres se chevauchent et la part recuperable est inconnue.

## 2. Donnees analysees

- Periode couverte (fin exclue) : 2026-01-05T00:00:00 -> 2026-05-05T00:00:00.
- Mesures valides : 11515 quarts d'heure.
- Energie totale : 153 411,4 kWh.
- Production : 143 191,6 unites.
- Variables de controle : production active, temperature exterieure, shift et type produit.

## 3. Qualite des donnees

Couverture estimee : 99,957 %. Le chargeur a trace 1 timestamp invalide, 1 mesure manquante, 1 valeur impossible et 1 doublon strict. Les quatre trous sont localises ; ils ne coincident pas avec les longues tendances conservees.

## 4. Profil energetique

La consommation hors production atteint 41 708,1 kWh (27,2 %). Elle inclut une charge de base legitime et ne constitue pas en bloc une economie.

![Puissance dans le temps](charts/power_timeseries.png)

![Puissance observee et attendue](charts/observed_expected.png)

![Residu quotidien moyen](charts/daily_residual.png)

![Relation production-puissance](charts/production_power.png)

## 5. Baseline

La baseline retenue utilise production, temperature, activite, type produit B et interaction production-produit. Elle est calibree sur le passe puis validee sur la periode suivante.

- Validation MAE : 1,237 kW.
- Validation RMSE : 1,558 kW.
- Validation R2 : 0,9968.

## 6. Investigations realisees

H01 a H06 ont suivi observation -> hypothese -> test -> contre-hypothese -> nouveau test -> quantification -> decision. H07 et H08 ont ete explicitement rejetes pour confusion et double comptage. Le detail complet se trouve dans `reports/investigation.json`.

## 7. Opportunites confirmees

### #1 — H06 : nouveau niveau de charge inactive

5 979,0 kWh sur la periode, soit 1 046,33 EUR au tarif de 0,175 EUR/kWh.

Le residu inactif moyen reste a 8,30 kW sur 30/30 jours. La temperature n'en explique que 0,168 kW.

Ce que les donnees demontrent : un changement durable de niveau existe hors production.

Ce qu'elles ne demontrent pas : l'equipement responsable ni la part arretable.

A verifier : nouvelles utilites, consignes, fuites, ventilation, pompes ou maintien en temperature.

### #2 — H05 : derive progressive de charge fixe

4 232,3 kWh sur la periode, soit 740,65 EUR au tarif de 0,175 EUR/kWh.

Pente inactive : 0,414 kW/j (R2 0,992). La pente imputable a la temperature est 0,0015 kW/j.

Ce que les donnees demontrent : la charge fixe se degrade progressivement, y compris a production nulle.

A verifier : encrassement, fuite croissante, derive de regulation et auxiliaire restant charge.

### #3 — H04 : baisse temporaire d'efficacite

2 123,7 kWh sur la periode, soit 371,65 EUR au tarif de 0,175 EUR/kWh.

Apres retrait de la derive fixe, l'ecart actif passe de 0,11 a 12,18 kW, sur 11/11 jours. Production et mix produit sont comparables.

Ce que les donnees demontrent : davantage de puissance est necessaire pour une production comparable.

Ce qu'elles ne demontrent pas : la cause mecanique exacte.

## 8. Efficacite energetique

Le signal mensuel d'intensite n'est pas conserve comme opportunite autonome : mai ne contient que quatre jours et le ratio recouvre H04-H06. L'analyse a production comparable est plus solide.

## 9. Impact economique

Les couts ci-dessus portent uniquement sur les periodes observees. La review de chevauchement trouve 1 119,1 kWh sur des timestamps communs ; H04 retranche H05, mais aucun total global n'est affiche sans allocation causale. Aucune annualisation n'est effectuee.

## 10. Opportunites necessitant verification

- H01 nuit : 2 152,8 kWh sur la periode, soit 376,74 EUR au tarif de 0,175 EUR/kWh. Recurrence 15/15 jours, production nulle.
- H02 week-end : 877,3 kWh sur la periode, soit 153,53 EUR au tarif de 0,175 EUR/kWh. Recurrence 4/4 jours, production nulle.
- H03 pic ponctuel : 239,2 kWh sur la periode, soit 41,86 EUR au tarif de 0,175 EUR/kWh. Un seul evenement de deux heures ; pas d'annualisation.

## 11. Hypotheses rejetees importantes

- H07 : l'intensite de mai n'est ni comparable ni independante.
- H08 : le signal de pointe et H03 couvrent exactement les memes huit points ; les additionner doublerait 239,2 kWh.

## 12. Recommandations

1. Rechercher d'abord le changement de charge inactive apparu en fin de periode.
2. Examiner les tendances de pression, debit, consignes et cycles des utilites pendant H05.
3. Comparer journaux de production, produits et etats machine pendant H04.
4. Identifier les equipements actifs pendant H01 et les quatre jours H02.
5. Rapprocher H03 du journal d'exploitation avant toute action.

## 13. Limites

Dataset synthetique, quatre mois, tarif simple, aucune mesure par equipement et aucune preuve de causalite physique. Les surconsommations ne sont pas des economies garanties.

## 14. Methodologie

Validation et normalisation deterministes, baseline passee->future, residualisation, comparaisons contextuelles, recherche d'explications alternatives, quantification Python, review adversariale Codex et controle des chevauchements.
