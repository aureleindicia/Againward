# Organisation du dépôt et des dossiers clients

État actif et limites : [CURRENT_STATE.md](CURRENT_STATE.md). Index des documents :
[README.md](README.md). Les audits `stage4_*`, `*_202609*` et rapports Goal
restent des preuves historiques, pas des points d'entrée actuels.

Cette convention garde le dépôt publiable sur GitHub tout en isolant les cas réels. Le moteur ne
dépend d’aucun chemin Android ; `/storage/emulated/0/Download` peut servir de source de réception,
jamais de dépendance codée en dur.

## Dépôt versionné

```text
energy-analyzer/
├── againward/
│   ├── core/         autorités privacy, lifecycle, requêtes et stockage durable
│   ├── documents/    sources immuables, propositions, provenance et rapprochements
│   ├── evidence/     snapshots et requêtes bornées
│   └── domains/      outils métier Energy et Rental
├── energy_mvp/       imports de compatibilité historiques (ne pas dupliquer les autorités)
├── benchmarking/    générateurs/scorers synthétiques, hors moteur d'investigation
├── tests/            unités, intégration, adversarial et falsification
├── benchmarks/       protocoles et résultats reproductibles
├── docs/             architecture, méthodes et migrations
├── examples/         données synthétiques uniquement
├── reports/          rapports R&D sans données client
├── workspace/        générateurs/expériences réutilisables
├── workspaces/       guide seulement ; cas ignorés par Git
└── .codex/skills/    procédure agentique Againward
```

Pour la branche documentaire active, commencer par
`docs/REAL_WORLD_DOCUMENT_ARCHITECTURE.md`, `docs/ENTITY_RESOLUTION.md` et
`docs/DOCUMENT_INTELLIGENCE_RND.md`. Le dernier distingue preuves obtenues et
travail encore nécessaire ; l'existence d'un module n'est pas une validation client.

## Scripts racine — statut vérifié

| Catégorie | Scripts | Usage |
|---|---|---|
| Point d'entrée canonique | `investigate.py` (alias de `againward.cli`), `create_workspace.py`, `intake_client_case.py` | Investigation et dossiers réels ; respecter contrat et privacy avant lecture métier. `investigate.py documents` est l'entrée des sources approuvées. |
| Compatibilité | `analyze.py`, `manage_investigation.py`, `query_evidence.py`, `generate_demo.py` | Interfaces Energy/legacy encore testées ; ne pas en faire de nouveaux propriétaires Rental. |
| Runners de benchmark | `run_rental_privacy_benchmark.py`, `run_rental_benchmark.py`, `run_document_benchmark.py`, `run_physical_benchmark.py`, `run_signal_intelligence_benchmark.py`, `run_minimal_attribution_benchmark.py`, `run_stage4_performance.py`, `run_stage4_shadow.py`, `prepare_stage4_model_benchmark.py` | Données synthétiques et preuves R&D ; résultats distincts des analyses client. |
| Utilitaires spécialisés/historiques | `client_intake_pipeline.py`, `client_delivery.py`, `deliver_client_report.py`, `operational_economics.py`, `pilot_learning.py`, `report_design.py`, `value_map.py` | Modules/CLI de workflows antérieurs ; inspecter le cycle applicable avant usage et ne pas supposer un point d'entrée Rental canonique. |

Ce classement indique l'usage actuel, pas une autorisation d'utiliser une
commande avant clearance. Le package `againward/` reste propriétaire des
frontières communes ; les calculs et rapports historiques ne sont pas supprimés.

## Workspace standard réel

```text
workspaces/<id>/
├── workspace.json
├── intake.json
├── incoming/             brut temporaire, avant privacy
├── privacy/
│   ├── candidate/        sanitation de travail
│   └── privacy_manifest.json
├── sanitized/            source autorisée après clearance
├── processed/            analyses et lifecycle canonique
├── scratch/              expériences ad hoc après clearance
├── outputs/              livrables
├── contracts/            conservation administrative séparée
├── billing/              conservation administrative séparée
└── retained_derived/     vide par défaut, autorisation explicite requise
```

Créer/stager et inspecter :

```sh
python create_workspace.py usine_01
python manage_investigation.py contract-record workspaces/usine_01 contracts_packet.json
python manage_investigation.py stage-incoming workspaces/usine_01 /chemin/du/depot
python manage_investigation.py status workspaces/usine_01
```

`processed/investigation_state.json` et `processed/questions.json` sont les autorités du cycle.
`processed/human_review.json` porte l’approbation. `privacy/privacy_manifest.json` est l’autorité de
clearance. Les commandes acceptent la racine ou `processed/`.

## Cas Goal A réel

```text
client_cases/<id>/
├── incoming/ et privacy/candidate/
├── sanitized/
├── normalized/ et derived/
├── evidence/
├── investigation/        lifecycle canonique
├── scratch/ et outputs/
├── contracts/ et billing/
└── retained_derived/
```

`raw/` n’existe plus dans un nouveau cas réel. La provenance relie les données normalisées aux
hashes original/sanitized du manifest, sans conserver l’original personnel.

## Compatibilité et migration

Les fixtures créées explicitement avec `synthetic=True` peuvent conserver l’ancien `raw/` ou un
chemin direct, car elles ne contiennent aucune donnée client. Un ancien workspace réel avec
`input/`/`raw/` et sans contrat privacy est détecté comme `PRIVACY_MIGRATION_REQUIRED` et bloqué. Il
doit être migré manuellement vers un nouveau workspace ; aucun fichier n’est déplacé ou supprimé
automatiquement.

## Git et confidentialité

- `client_cases/` et `workspaces/*` sont ignorés intégralement ; les sous-zones sont aussi listées
  explicitement pour rendre l’intention vérifiable.
- Les répertoires `incoming/`, `privacy/`, `sanitized/`, `processed/`, `scratch/`, `outputs/` et
  `retained_derived/` de cas sont ignorés.
- Seules des fixtures synthétiques identifiées peuvent entrer dans `examples/` ou `workspace/`.
- Avant commit : examiner `git diff`, `git status` et ne jamais utiliser `git add -f` sur un cas.
- Aucune télémétrie ou transmission arbitraire n’est ajoutée au moteur.

La CI GitHub exécute la suite Python sans service cloud applicatif. Le workspace et l’orchestration
sont local-first, mais Codex/OpenAI traite les données nécessaires selon sa configuration ; cette
architecture ne justifie pas la promesse « aucune donnée ne quitte l’appareil ».
