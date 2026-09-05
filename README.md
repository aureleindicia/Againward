# Energy Analyzer — investigation energetique sur donnees

Energy Analyzer est un environnement local-first dans lequel Codex agit comme analyste
energetique et Python comme couche de calcul verifiable.

Sa valeur centrale est une **analyse de performance énergétique sur données** : détecter des
dérives et anomalies difficiles à voir dans les factures, quantifier leur coût observé, tester
les explications concurrentes, indiquer précisément ce qui mérite une vérification terrain, puis
mesurer l'effet après correction. Ce résultat peut être utile de façon autonome ; il n'est pas
présenté comme une simple préparation avant le « vrai » travail.

L'investigation peut également compléter un auditeur énergétique, un frigoriste, un électricien
ou un mainteneur en lui indiquant quelles périodes, quels équipements plausibles et quelles
contre-explications examiner. Lorsque le comportement corrigé doit rester sous contrôle, le même
cadre permet un monitoring continu fondé sur une baseline et une règle d'alerte explicites.

Le positionnement commercial et les formulations autorisées sont détaillés dans
[`docs/POSITIONING.md`](docs/POSITIONING.md).

```text
dépôt client -> privacy gate sémantique Codex -> validation privacy Python
              -> source sanitized -> validation métier Python -> signaux candidats
              -> investigation Codex -> tests Python -> critique -> revue humaine
```

Le pipeline automatique ne confirme pas d'opportunites et ne remplace pas l'investigation.
Quand une review reste incertaine, elle produit une prochaine verification minimale structuree
(question metier, donnee precise ou test terrain simple). Une decision deja confirmee ou rejetee
ne declenche pas de demande systematique, et une cause physique non prouvable reste explicitement
non etablie.
Le workspace, l'orchestration et les calculs sont local-first, sans serveur applicatif, base de
données distante, télémétrie ni upload automatique arbitraire. Codex reste cependant nécessaire à
l'analyse et traite le contenu utile via OpenAI selon la configuration utilisée : ne pas présenter
le service comme un traitement purement local ou garantir qu'aucune donnée ne quitte l'appareil.

## Installation Termux

```sh
pkg install python git
python -m pip install -r requirements.txt
```

`openpyxl` est optionnel en pratique et ne sert qu'aux fichiers XLSX. `tzdata` est une petite
base de fuseaux nécessaire sur Android, car sa base système n'est pas directement lisible par
`zoneinfo`. Les CSV, calculs, baselines, validations et PNG n'ajoutent aucune dépendance lourde.

## Analyse initiale

Pour isoler un nouveau dossier client sans automatiser l'investigation :

```sh
python create_workspace.py usine_01 --incoming /chemin/du/depot_recu
```

Le script crée un workspace isolé, refuse tout écrasement et copie le dépôt sans lire son contenu
dans `incoming/`. Codex doit être le premier lecteur sémantique : il produit la privacy review,
puis Python post-vérifie et promeut la source autorisée dans `sanitized/`. Aucun intake ou calcul
énergétique n'est permis avant `PRIVACY_CLEARED`.

Afficher à tout moment le layout détecté, l'état canonique, les artefacts présents et la prochaine
action permise (commande strictement en lecture seule) :

```sh
python manage_investigation.py status workspaces/usine_01
```

Les commandes du lifecycle acceptent la racine du workspace; le résolveur trouve automatiquement
`processed/`. Voir [`docs/REPOSITORY_LAYOUT.md`](docs/REPOSITORY_LAYOUT.md) pour la convention de
dossiers et les garanties de publication GitHub/confidentialité.

```sh
python analyze.py donnees.csv --price-per-kwh 0.175
```

Le rapport automatique et son JSON contiennent des indicateurs fiables et des **signaux
candidats**. Ils ne constituent pas encore le rapport final de Codex.

Pour un dataset inconnu, utiliser plutôt le workflow générique. Il prépare un paquet local
avec empreinte de la source, questionnaire, inspection, limites de capacité, signaux candidats
legacy et Evidence Plane interactif, sans hypothèse Hxx ni date issue de la démo :

```sh
python manage_investigation.py privacy-validate \
  workspaces/usine_01 workspaces/usine_01/privacy/review.json
python investigate.py workspaces/usine_01/sanitized/mesures.csv \
  --intake workspaces/usine_01/intake.json \
  --output-dir workspaces/usine_01/processed \
  --price-per-kwh 0.175
```

Les colonnes opérationnelles inconnues sont conservées dans un magasin contextuel séparé du
noyau physique. Elles sont découvrables dans `evidence_card.json` mais ne contaminent jamais les
calculs kW/kWh. Codex choisit ensuite ses tests via un protocole fini et borné. Par exemple, après
avoir lu `evidence_query_contract.json` :

```sh
python query_evidence.py workspaces/usine_01/processed request.json
```

Chaque réponse contient hashes, provenance, limites relationnelles et handles de récupération,
avec `decision: null`. Les appels répétés ou hors budget sont refusés et tracés. Les modes de
migration sont `preferred` (défaut), `shadow`, et `legacy` pour le rollback immédiat :

```sh
python investigate.py donnees.csv --output-dir workspaces/rollback/processed \
  --evidence-plane-mode legacy
```

Codex conduit ensuite l'exploration dans ce dossier et écrit `investigation.json`, `review.json`,
`agent_findings.json` et `report.md`. Une conclusion Stage 4 conservée référence obligatoirement
les query IDs et handles qui l’étayent ; une abstention explicite est valide. Le cycle client
reste explicite et vérifiable :

```sh
# Publie seulement les demandes retenues par le contrat canonique
python manage_investigation.py publish-candidates workspaces/usine_01 candidates.json

# Enregistre des réponses préparées dans answers.json, sans pouvoir les réécrire
python manage_investigation.py record-answers workspaces/usine_01 answers.json

# Refuse la livraison tant que review contradictoire et revue humaine ne sont pas valides
python manage_investigation.py check workspaces/usine_01
```

Le workflow canonique utilise `investigation_state.json.client_lifecycle` et `questions.json` :
zéro question par défaut, STOP réel sur BLOCKING, reprise avec provenance/recalcul/review, deux
cycles maximum et finalisation honnête. Le contexte INDICIA peut être réparti entre le dépôt et
`/storage/emulated/0/Download`.

Le détail des formats et du passage humain est dans
[`docs/CLIENT_WORKFLOW.md`](docs/CLIENT_WORKFLOW.md).
La fiche simple à transmettre avant un pilote est
[`docs/CLIENT_DATA_FEASIBILITY_REQUEST.md`](docs/CLIENT_DATA_FEASIBILITY_REQUEST.md).

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

Pour des timestamps locaux sans décalage UTC, fournir le fuseau IANA du site :

```sh
python analyze.py energie.csv --site-timezone Europe/Paris
```

Le stockage chronologique interne est alors en UTC, tandis que les profils horaires utilisent
l'heure locale du site. Une heure inexistante au passage d'été est refusée. Une heure répétée au
passage d'hiver exige un décalage explicite dans la source (`+02:00` ou `+01:00`) : le logiciel ne
devine jamais lequel des deux intervalles est mesuré.

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

La démo conserve volontairement une horloge synthétique fixe afin de rester une fixture de
régression pour ses investigations datées. Les changements d'heure réels sont couverts séparément
par les tests du chargeur et le générateur aveugle v2 à offsets explicites.

## Validation aveugle et comparaison Codex

Le benchmark indépendant de 14 cas ne réutilise ni `demo.py` ni sa ground truth :

```sh
python -m workspace.benchmark_blind
```

Pour une comparaison réellement aveugle, préparer un dossier neuf, confier uniquement `public/`
à plusieurs sessions Codex, puis évaluer après gel et validation de leurs reviews :

```sh
python -m workspace.prepare_blind_sessions /tmp/energy-blind
# Les sessions écrivent chacune review.json sans ouvrir private_truth/.
python -m workspace.evaluate_blind_sessions /tmp/energy-blind \
  --reviews-dir reports/blind_sessions
```

Les preuves figées sont `reports/validation_blind.json`,
`reports/blind_codex_comparison.json` et `reports/blind_sessions/`. L'audit publie séparément le
score favorable des scénarios apparentés à la démo et le score aveugle plus faible :
[`docs/MEGA_GOAL_AUDIT.md`](docs/MEGA_GOAL_AUDIT.md).

Livrables principaux :

- `reports/demo_15min.json` : resultat automatique structure ;
- `reports/analysis.json` : bundle commun sans recalcul (analyse, preuves, review, artefacts) ;
- `reports/demo_quantitative_results.json` : tests Python demandes par Codex ;
- `reports/investigation.json` : hypothese, tests, alternatives, decision et confiance ;
- `reports/demo_final.md` et `reports/demo_final.html` : synthese Codex ;
- `reports/charts/` : PNG analytiques sans interface graphique ;
- `reports/validation.json` : validation post-investigation sur les evenements ;
- `reports/validation_scenarios.json` : cinq profils, plusieurs seeds et cas sans anomalie.
- `reports/validation_blind.json` : quatorze cas indépendants et quantification ;
- `reports/blind_codex_comparison.json` : Python seul contre trois sessions Codex.

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

## Benchmark Signal Intelligence V2

Le dépôt contient un protocole privé local pour tester séparément : détection, classe du
phénomène, signature reproductible, attribution d'actif, mécanisme physique, quantification
et pronostic. Les cas synthétiques appariés existent aux niveaux énergie 15 minutes, P/Q minute
et événements électriques centraux.

```sh
python run_signal_intelligence_benchmark.py --help
```

Le contrôle déterministe actuel démontre seulement une détection candidate partielle et des
motifs synthétiques. Il obtient **0 %** en attribution d'actif, mécanisme physique, pronostic et
capacité complète. Voir [`docs/SIGNAL_INTELLIGENCE_BENCHMARK_V2.md`](docs/SIGNAL_INTELLIGENCE_BENCHMARK_V2.md)
et [`reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_COMPLETION_AUDIT.md`](reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_COMPLETION_AUDIT.md).

## Attribution sous preuves minimales (R&D)

La couche `MinimalEvidenceAttribution` transforme une signature déjà reproductible en
compatibilités explicables avec un registre incomplet. Elle conserve toujours `unknown`,
distingue l'équivalence observationnelle de l'historique insuffisant et choisit une
micro-question à forte valeur informationnelle. La politique gardée ne nomme un actif
qu'après une ancre discriminante vérifiée.

```sh
python run_minimal_attribution_benchmark.py --help
```

La validation actuelle est exclusivement synthétique : 20 scénarios, dix seeds et un
protocole de réponse verrouillée avant lecture de la vérité. Elle démontre les garde-fous
logiciels, pas une précision d'attribution terrain. Le moteur ne produit ni mécanisme
physique, ni pronostic, ni probabilité postérieure. Voir
[`docs/MINIMAL_EVIDENCE_ATTRIBUTION.md`](docs/MINIMAL_EVIDENCE_ATTRIBUTION.md) et
[`reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_REPORT.md`](reports/MINIMAL_EVIDENCE_ATTRIBUTION_RND_REPORT.md).

## Tests

```sh
python -m pytest -q
```

La suite couvre notamment unites, integration kW/kWh, index cumulatif, timestamps, doublons,
cout partiel, production partielle, division par zero, baselines passe-vers-futur, residuals,
evenements, double comptage, PNG, ground truth et cas sans anomalie.

## Architecture

```text
analyze.py                   CLI de signaux initiaux
generate_demo.py             generateur 15 minutes reproductible
create_workspace.py          isolation locale d'un nouveau dossier client
energy_mvp/privacy.py        gate Codex-first, post-check, manifest, rétention et purge
energy_mvp/io.py             lecture, normalisation et qualite
energy_mvp/units.py          conversions physiques
energy_mvp/analysis.py       indicateurs et signaux candidats simples
energy_mvp/toolbox.py        outils quantitatifs composables pour Codex
energy_mvp/signals.py        detecteur generique de candidats
energy_mvp/case_lifecycle.py cycle questions/reponses et verrou de livraison
energy_mvp/positioning.py    positionnement canonique exposé aux dossiers client
energy_mvp/tariffs.py        plages tarifaires et puissance mensuelle
energy_mvp/validation.py     appariement d'evenements temporels
energy_mvp/minimal_attribution.py compatibilité, identifiabilité, preuves et micro-questions
energy_mvp/charts.py         PNG standard-library
benchmarking/signal_intelligence.py protocole, verrouillage, scoring et agrégation V2
benchmarking/signal_deterministic_baseline.py contrôles et ablations sans attribution
benchmarking/signal_intelligence_generator.py corpus synthétique privé multi-réalisations
benchmarking/minimal_attribution_benchmark.py benchmark aveugle, falsifications et robustesse
docs/ANALYSIS_TOOLS.md       catalogue des outils
docs/CLIENT_WORKFLOW.md      procédure nouveau client et contrats JSON
docs/PRIVACY_ARCHITECTURE.md architecture et invariants privacy-by-design
docs/PRIVACY_THREAT_MODEL.md menaces, contrôles et limites fail-closed
docs/PRIVACY_VALIDATION_REPORT.md tests et benchmarks réellement exécutés
docs/POSITIONING.md          proposition de valeur et frontière réglementaire
docs/MEGA_GOAL_AUDIT.md      preuves, limites et notes critiques actuelles
workspace/                   experiences agentiques ad hoc
tests/                       non-regressions deterministes
```

## Positionnement et limites

Energy Analyzer est un service d'**analyse et d'investigation de performance énergétique sur
données**. Il peut constituer un livrable autonome : comportements mesurés, anomalies retenues ou
rejetées, coût observé, vérifications ciblées et protocole de mesure après correction.

Il ne constitue pas un audit énergétique réglementaire, une certification, un diagnostic
mécanique définitif ni une garantie contractuelle d'économie. Une surconsommation mesurée n'est
pas automatiquement récupérable. Les causes physiques et actions doivent être validées avec
l'exploitation et, lorsque nécessaire, un professionnel qualifié.

Les pilotes initiaux peuvent bénéficier d'un prix réduit afin d'obtenir des preuves réelles. Le
modèle cible n'est toutefois pas un « petit diagnostic à bas prix » : le prix doit refléter le
périmètre, la difficulté de l'investigation, le suivi humain et la valeur décisionnelle créée,
sans dépendre artificiellement du nombre d'anomalies trouvé.
