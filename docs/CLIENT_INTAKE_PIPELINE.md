# Pipeline d’entrée client

Le chemin réel est fail-closed :

```text
dépôt reçu → incoming/ temporaire → revue sémantique Codex
→ PASS | SANITIZED | BLOCKED → post-check Python
→ privacy_manifest.json → sanitized/ canonique → intake déterministe
```

Codex est la première étape qui lit et comprend le contenu. Le staging Python ne fait qu’une copie
octet-pour-octet et un inventaire de chemins ; il ne parse, ne classe, ne normalise et ne hashe pas
le contenu. Après la revue Codex, Python vérifie le contrat et la préservation analytique.

## Démarrage Goal A

```sh
python intake_client_case.py stage atelier_01 /chemin/vers/dossier_recu \
  --root client_cases
python manage_investigation.py status client_cases/atelier_01
```

Structure d’un nouveau cas réel :

```text
client_cases/atelier_01/
  incoming/          brut temporaire, jamais source analytique
  privacy/
    candidate/       sorties de sanitation de travail
    privacy_manifest.json
  sanitized/         sources approuvées et hashées
  normalized/        normalisation de qualité, après clearance
  derived/           cas canonique et résumés
  evidence/          provenance depuis sanitized/
  investigation/     lifecycle, questions, réponses, findings
  scratch/
  outputs/
  contracts/
  billing/
  retained_derived/
```

`client_cases/` est entièrement exclu de Git.

## Séparation privacy / qualité de données

Le privacy cleanup retire ou pseudonymise exclusivement les données personnelles inutiles et les
secrets hors périmètre. Il préserve les machines, compteurs, lignes, sites, dates, mesures, unités,
production, lots, campagnes, états, maintenance et relations nécessaires à l’attribution. Il ne
corrige jamais une unité, un timestamp, une valeur impossible ou un doublon.

Après `PRIVACY_CLEARED` seulement :

```sh
python intake_client_case.py intake client_cases/atelier_01
```

L’intake parcourt CSV/XLSX et les documents supportés, trace les transformations de qualité et
produit les artefacts canoniques. Sa provenance référence les identifiants, hashes originaux du
privacy manifest et hashes des fichiers `sanitized/`, sans conserver une seconde copie du brut.

## États et refus

- `AWAITING_PRIVACY_REVIEW` : seul le privacy gate peut lire le brut.
- `PRIVACY_CLEARED` : intake autorisé depuis `sanitized/` uniquement.
- `PRIVACY_BLOCKED` : STOP ; aucune investigation énergétique.
- `PURGED` : mission purgée ; aucune reprise analytique.

Un ancien cas contenant `raw/` ou `input/` sans contrat privacy renvoie
`PRIVACY_MIGRATION_REQUIRED`. Il n’est jamais migré automatiquement. Voir
[CLIENT_WORKFLOW_MIGRATION.md](CLIENT_WORKFLOW_MIGRATION.md).

Ce pipeline n’est pas un diagnostic automatique. Codex conserve la responsabilité des hypothèses,
de la falsification, de l’abstention et des demandes à forte valeur ; une revue humaine reste
obligatoire avant livraison.
