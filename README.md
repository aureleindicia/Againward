# Energy Analyzer — pre-diagnostic energetique agentique

Energy Analyzer est un environnement local-first dans lequel Codex agit comme analyste
energetique et Python comme couche de calcul verifiable.

```text
donnees -> validation Python -> signaux candidats -> investigation Codex
        -> tests Python -> critique Codex -> review -> rapport humain
```

Le pipeline automatique ne confirme pas d'opportunites et ne remplace pas l'investigation.
Le projet fonctionne sans cloud, serveur, base de donnees ni API OpenAI.

## Installation Termux

```sh
pkg install python git
python -m pip install -r requirements.txt
```

`openpyxl` est optionnel en pratique et ne sert qu'aux fichiers XLSX. Les CSV, calculs,
baselines, validations et PNG utilisent exclusivement la bibliotheque standard Python.

## Analyse initiale

Pour isoler un nouveau dossier client sans automatiser l'investigation :

```sh
python create_workspace.py usine_01
```

Le script cree `input/`, `processed/`, `scratch/` et `outputs/`, refuse d'ecraser un espace
existant et ne copie ni n'analyse aucune donnee. Placer ensuite une copie du fichier source dans
`workspaces/usine_01/input/` avant l'exploration Codex.

```sh
python analyze.py donnees.csv --price-per-kwh 0.175
```

Le rapport automatique et son JSON contiennent des indicateurs fiables et des **signaux
candidats**. Ils ne constituent pas encore le rapport final de Codex.

```sh
python analyze.py donnees.csv \
  --output reports/rapport-initial.md \
  --json-output reports/analysis.json \
  --price-per-kwh 0.175
```

Toutes les options :

```sh
python analyze.py --help
```

## Unites et nature des mesures

Le chargeur distingue explicitement :

- `POWER` : W, kW ou MW, integres avec la duree de l'intervalle ;
- `ENERGY_PER_INTERVAL` : Wh, kWh ou MWh, jamais reintegres ;
- `CUMULATIVE_ENERGY` : index differencie une seule fois.

Exemples :

```sh
# 100 kW mesures toutes les 15 minutes -> 25 kWh par ligne
python analyze.py puissance.csv --power-column puissance --power-unit kw --interval-minutes 15

# En-tete ambigu mais energie connue en Wh par intervalle
python analyze.py energie.csv --energy-column mesure --energy-unit wh --energy-mode interval
```

Une unite absente d'un en-tete generique est refusee. Une puissance a timestamps irreguliers
est refusee sans `--interval-minutes`. Les doublons conflictuels sont refuses ; les doublons
strictement identiques et chaque suppression/conversion sont traces.

Par defaut, un timestamp d'energie ou de puissance designe le debut de son intervalle, tandis
qu'un releve cumulatif designe sa fin. Pour une source qui horodate les fins d'intervalles :

```sh
python analyze.py energie.csv --timestamp-position end
```

## Demonstration complete reproductible

Depuis la racine du depot :

```sh
python generate_demo.py

python analyze.py examples/demo_15min.csv \
  --price-per-kwh 0.175 \
  --output reports/demo_15min.md \
  --json-output reports/demo_15min.json

python -m workspace.demo_investigation
python -m workspace.demo_review
```

Ne pas ouvrir `examples/demo_ground_truth.json` pendant l'investigation. Apres la review :

```sh
python -m workspace.validate_demo
python -m workspace.benchmark_scenarios
```

Livrables principaux :

- `reports/demo_15min.json` : resultat automatique structure ;
- `reports/analysis.json` : bundle commun sans recalcul (analyse, preuves, review, artefacts) ;
- `reports/demo_quantitative_results.json` : tests Python demandes par Codex ;
- `reports/investigation.json` : hypothese, tests, alternatives, decision et confiance ;
- `reports/demo_final.md` et `reports/demo_final.html` : synthese Codex ;
- `reports/charts/` : PNG analytiques sans interface graphique ;
- `reports/validation.json` : validation post-investigation sur les evenements ;
- `reports/validation_scenarios.json` : cinq profils, plusieurs seeds et cas sans anomalie.

Une seconde investigation, volontairement limitee a douze agregats mensuels, verifie que Codex
rejette les conclusions horaires impossibles :

```sh
python analyze.py examples/sample_energy.csv --output reports/demo.md --json-output reports/demo.json
python -m workspace.monthly_investigation
python -m workspace.monthly_review
```

Scenarios disponibles :

- `factory_simple` ;
- `factory_variable` ;
- `factory_temperature_sensitive` ;
- `factory_noisy` ;
- `factory_low_production`.

Un dataset normal sans anomalies peut etre genere avec `--without-anomalies`.

## Colonnes reconnues

| Information | Obligatoire | Exemples | Unite |
|---|---|---|---|
| Date/heure | oui | `date`, `timestamp`, `horodatage` | ISO ou date francaise |
| Energie ou puissance | oui | `energy_kwh`, `index_mwh`, `power_kw` | explicite ou option CLI |
| Production | non | `production`, `quantite_produite` | unite metier/intervalle |
| Production active | non | `production_active`, `is_producing` | booleen |
| Temperature | non | `outside_temperature_c`, `temp_c` | degC |
| Shift | non | `shift`, `equipe`, `poste` | categorie |
| Type produit | non | `product_type`, `type_produit` | categorie |
| Tarif | non | `tarif_kwh`, `eur_kwh` | devise/kWh |

Les donnees mensuelles restent acceptables pour les totaux, mais le moteur desactive
explicitement les conclusions horaires, nocturnes et de demarrage.

## Tests

```sh
python -m unittest discover -s tests -v
```

La suite couvre notamment unites, integration kW/kWh, index cumulatif, timestamps, doublons,
cout partiel, production partielle, division par zero, baselines passe-vers-futur, residuals,
evenements, double comptage, PNG, ground truth et cas sans anomalie.

## Architecture

```text
analyze.py                   CLI de signaux initiaux
generate_demo.py             generateur 15 minutes reproductible
create_workspace.py          isolation locale d'un nouveau dossier client
energy_mvp/io.py             lecture, normalisation et qualite
energy_mvp/units.py          conversions physiques
energy_mvp/analysis.py       indicateurs et signaux candidats simples
energy_mvp/toolbox.py        outils quantitatifs composables pour Codex
energy_mvp/signals.py        detecteur generique de candidats
energy_mvp/validation.py     appariement d'evenements temporels
energy_mvp/charts.py         PNG standard-library
docs/ANALYSIS_TOOLS.md       catalogue des outils
workspace/                   experiences agentiques ad hoc
tests/                       non-regressions deterministes
```

## Positionnement et limites

Le systeme est un outil agentique de pre-diagnostic industriel. Il ne constitue ni audit
reglementaire, ni diagnostic mecanique, ni garantie d'economie. Une surconsommation mesuree
n'est pas automatiquement recuperable. Les causes physiques et actions doivent etre validees
avec l'exploitation et, si necessaire, un professionnel qualifie.
