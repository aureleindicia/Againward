# Rapport d'analyse energetique

Source : `examples/demo_15min.csv`

## Synthese

- Periode analysee : 05/01/2026 -> 04/05/2026
- Consommation totale : 153 411 kWh
- Cout energetique estime : 26 847,00 EUR
- Consommation hors production : 41 708 kWh (27,2 %)
- Production totale : 143 191,64 unites
- Intensite energetique : 1,071 kWh/unite
- Pointe de puissance : 215,2 kW

## Signaux a examiner

### [CANDIDAT — ELEVE] Consommation importante hors production

27.2% de l'energie est consommee sur des lignes ou la production renseignee est <= 0. Ce volume est une consommation observee, pas une economie recuperable.

Elements quantitatifs :
- `energie_hors_production_kwh=41708.1`
- `part_sur_couverture_production=0.271871`

Limites avant confirmation :
- La charge incompressible n'est pas encore estimee.
- La cause physique et la part evitable exigent une investigation.

### [CANDIDAT — MOYEN] Pics de consommation atypiques

9 point(s) depassent le seuil robuste mediane + 3 x ecart absolu median. Ce sont des candidats a regrouper et comparer a des periodes equivalentes.

Elements quantitatifs :
- `points_candidats=9`

Limites avant confirmation :
- Le seuil ne controle pas encore la production, l'heure ou la temperature.

### [CANDIDAT — MOYEN] Intensite energetique variable

L'intensite mensuelle la plus haute depasse d'au moins 25 % la plus basse. Comparer le mix produit, les cadences, les arrets et les conditions meteo.

Elements quantitatifs :
- `intensite_min=0.981342`
- `intensite_max=1.40579`

Limites avant confirmation :
- Un ratio kWh/unite se degrade mecaniquement a faible production.

### [CANDIDAT — MOYEN] Pointe de puissance notable

La pointe (215.2 kW) atteint au moins 150 % de la puissance moyenne mesuree. Examiner sa duree, la production et les demarrages avant toute interpretation.

Elements quantitatifs :
- `pointe_kw=215.182`
- `moyenne_kw=53.291`

Limites avant confirmation :
- Une pointe peut etre normale et n'implique pas automatiquement un surcout.

## Detail mensuel

| Mois | Energie (kWh) | Cout | Production | Intensite |
|---|---:|---:|---:|---:|
| 2026-01 | 32 385 | 5 667,46 EUR | 33 001,21 | 0,981 |
| 2026-02 | 34 022 | 5 953,80 EUR | 33 277,16 | 1,022 |
| 2026-03 | 41 102 | 7 192,92 EUR | 36 805,65 | 1,117 |
| 2026-04 | 41 317 | 7 230,46 EUR | 36 846,21 | 1,121 |
| 2026-05 | 4 585 | 802,35 EUR | 3 261,41 | 1,406 |

## Qualite des donnees

- Lignes lues : 11519
- Lignes analysees : 11515
- Lignes ecartees : 4
- Mode energie : interval
- Nature de mesure : energy_per_interval
- Frequence nominale : 15,000 minutes
- Couverture temporelle estimee : 100,0 %
- Transformations tracees :
  - 1 doublon(s) strictement identique(s) supprime(s).
  - Frequence nominale detectee: 15 minute(s).
  - 1 ligne(s) avec valeur impossible ecartee(s).
  - 1 ligne(s) avec timestamp invalide ecartee(s).
  - 1 ligne(s) sans mesure energetique ecartee(s).
- Attention : 1 doublon(s) strictement identique(s) supprime(s).
- Attention : 4 intervalle(s) different de la frequence nominale.
- Attention : 4 trou(s) temporel(s) probable(s) detecte(s).
- Attention : 4 ligne(s) ecartee(s) de l'analyse (vides, invalides, incompletes, references ou dedupliquees).

## Limites

Ce rapport est un outil de pre-diagnostic. Les signaux sont des pistes a verifier avec le contexte d'exploitation, les factures, les courbes de charge et un professionnel qualifie. Il ne remplace pas un audit energetique reglementaire.
