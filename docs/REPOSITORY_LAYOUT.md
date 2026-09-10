# Organisation du dépôt et des dossiers clients

Cette convention garde le dépôt publiable sur GitHub tout en isolant les cas réels. Le moteur ne
dépend d’aucun chemin Android ; `/storage/emulated/0/Download` peut servir de source de réception,
jamais de dépendance codée en dur.

## Dépôt versionné

```text
energy-analyzer/
├── energy_mvp/       outils, contrats, privacy gate et lifecycle
├── tests/            unités, intégration, adversarial et falsification
├── benchmarks/       protocoles et résultats reproductibles
├── docs/             architecture, méthodes et migrations
├── examples/         données synthétiques uniquement
├── reports/          rapports R&D sans données client
├── workspace/        générateurs/expériences réutilisables
├── workspaces/       guide seulement ; cas ignorés par Git
└── .codex/skills/    procédure agentique Againward
```

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
