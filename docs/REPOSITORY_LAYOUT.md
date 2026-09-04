# Organisation du dépôt et des dossiers clients

Cette convention garde le dépôt publiable sur GitHub tout en protégeant les dossiers réels.
Le code ne dépend d'aucun chemin Android : `/storage/emulated/0/Download` est une source locale
facultative pour Codex, jamais une dépendance du moteur Python.

## Dépôt versionné

```text
energy-analyzer/
├── energy_mvp/       bibliothèque Python et contrats déterministes
├── tests/            tests unitaires, d'intégration et de falsification
├── benchmarks/       protocoles, schémas et résultats reproductibles
├── docs/             navigation, méthodes et contrats utilisateur
├── examples/         uniquement des données et décisions synthétiques
├── reports/          rapports R&D reproductibles, sans données client
├── workspace/        scripts d'expérimentation réutilisables
├── workspaces/       guide versionné; contenus clients ignorés par Git
└── .codex/skills/    procédure Codex locale au dépôt
```

Les scripts temporaires spécifiques à un client restent dans son `scratch/`. Ils n'entrent dans
`energy_mvp/` qu'après généralisation, test et review.

## Workspace recommandé

```text
workspaces/<dossier>/
├── workspace.json
├── intake.json
├── input/       copies reçues, jamais modifiées en place
├── processed/   analyses intermédiaires et état canonique
├── scratch/     expériences ad hoc
└── outputs/     livrables finaux
```

`processed/investigation_state.json` et `processed/questions.json` sont les seules autorités du
cycle client. `processed/human_review.json` porte l'approbation. Il n'existe plus de copies
concurrentes à la racine pour les nouveaux workspaces.

Créer et inspecter un dossier :

```sh
python create_workspace.py usine_01
python manage_investigation.py status workspaces/usine_01
```

Toutes les commandes du lifecycle acceptent soit la racine `workspaces/usine_01`, soit son
`processed/`. `status` ne modifie rien et affiche le layout détecté, le chemin canonique, les
artefacts présents, l'état et la prochaine action permise.

## Compatibilité avec le pipeline d'intake historique

Un dossier Goal A conserve sa structure riche :

```text
<cas>/
├── raw/
├── normalized/
├── derived/
├── evidence/
├── investigation/   propriétaire du lifecycle canonique
├── outputs/
└── logs/
```

Le résolveur reconnaît la racine comme `investigation/`; aucun fichier n'est déplacé. Un dossier
d'analyse direct reste également supporté. Cette compatibilité évite une migration destructive.

## Règles Git et confidentialité

- Ne jamais versionner `input/`, `processed/`, `scratch/`, `outputs/` ou des données de pilote.
- Ne publier dans `examples/` que des fixtures synthétiques explicitement identifiées.
- Ne pas coder en dur un chemin Termux, Android ou personnel.
- Ne pas ajouter de télémétrie ou d'upload automatique.
- Exécuter `python -m pytest -q` avant chaque publication.

La CI GitHub exécute la suite complète sous Python sans service cloud applicatif. L'analyse client
elle-même reste locale-first.
