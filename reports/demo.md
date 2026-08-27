# Rapport d'analyse energetique

Source : `examples/sample_energy.csv`

## Synthese

- Periode couverte (fin exclue) : 01/01/2026 -> 01/01/2027
- Consommation totale : 611 850 kWh
- Cout energetique estime : 107 073,75 EUR
- Consommation hors production : 41 100 kWh (6,7 %)
- Production totale : 101 500,00 unites
- Intensite energetique : 6,028 kWh/unite
- Pointe de puissance : 198,0 kW

## Signaux a examiner

### [CANDIDAT — FAIBLE] Consommation hors production limitee

6.7% de l'energie est consommee sur des lignes ou la production renseignee est <= 0. Ce volume est une consommation observee, pas une economie recuperable.

Elements quantitatifs :
- `energie_hors_production_kwh=41100`
- `part_sur_couverture_production=0.0671733`

Limites avant confirmation :
- La charge incompressible n'est pas encore estimee.
- La cause physique et la part evitable exigent une investigation.

## Detail mensuel

| Mois | Energie (kWh) | Cout | Production | Intensite |
|---|---:|---:|---:|---:|
| 2026-01 | 12 500 | 2 187,50 EUR | 0,00 | - |
| 2026-02 | 58 200 | 10 185,00 EUR | 10 400,00 | 5,596 |
| 2026-03 | 61 750 | 10 806,25 EUR | 11 100,00 | 5,563 |
| 2026-04 | 59 400 | 10 395,00 EUR | 10 950,00 | 5,425 |
| 2026-05 | 63 200 | 11 060,00 EUR | 11 300,00 | 5,593 |
| 2026-06 | 14 800 | 2 590,00 EUR | 0,00 | - |
| 2026-07 | 65 500 | 11 462,50 EUR | 11 600,00 | 5,647 |
| 2026-08 | 13 800 | 2 415,00 EUR | 0,00 | - |
| 2026-09 | 67 400 | 11 795,00 EUR | 11 800,00 | 5,712 |
| 2026-10 | 70 100 | 12 267,50 EUR | 12 050,00 | 5,817 |
| 2026-11 | 64 800 | 11 340,00 EUR | 11 500,00 | 5,635 |
| 2026-12 | 60 400 | 10 570,00 EUR | 10 800,00 | 5,593 |

## Qualite des donnees

- Lignes lues : 12
- Lignes analysees : 12
- Lignes ecartees : 0
- Mode energie : interval
- Nature de mesure : energy_per_interval
- Bornes de periode estimees avec l'intervalle nominal detecte; utiliser --interval-minutes si la derniere borne doit etre contractuelle.
- Frequence nominale : 44 640,000 minutes
- Couverture temporelle estimee : 100,0 %
- Transformations tracees :
  - Frequence nominale detectee: 44640 minute(s).
  - Les timestamps sont traites par defaut comme debuts d'intervalles; utiliser --timestamp-position end si la source suit l'autre convention.
- Resolution insuffisante pour une analyse horaire, nocturne ou de demarrage.
- Aucun avertissement de qualite detecte.

## Limites

Ce rapport est un outil de pre-diagnostic. Les signaux sont des pistes a verifier avec le contexte d'exploitation, les factures, les courbes de charge et un professionnel qualifie. Il ne remplace pas un audit energetique reglementaire.
