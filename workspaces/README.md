# Workspaces clients locaux

Ce dossier est le point d'entrée recommandé pour les dossiers réels. Créer un espace isolé avec :

```sh
python create_workspace.py identifiant_client
```

Chaque workspace généré contient :

```text
identifiant_client/
├── input/       copies immuables reçues du client
├── processed/   données préparées, preuves et état canonique de l'investigation
├── scratch/     expériences ad hoc reproductibles, non promues par défaut
└── outputs/     graphiques et livrables finaux
```

L'état, les questions/réponses et la revue humaine ont un seul propriétaire : `processed/`.
La commande suivante accepte le dossier racine et indique les chemins résolus et l'action permise :

```sh
python manage_investigation.py status workspaces/identifiant_client
```

Les contenus clients sont ignorés par Git. Seul ce guide est versionné. Les exemples publiables
doivent être synthétiques et placés dans `examples/`.
