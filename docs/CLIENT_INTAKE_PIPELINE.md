# Pipeline d’entrée client

Energy Analyzer accepte un dossier tel qu’il existe chez une petite entreprise. Le flux est local :

`dossier brut → inventaire → extraction/normalisation traçable → cas canonique → investigation Codex`.

Il ne transforme pas les sources en diagnostic automatique. Codex reste responsable du périmètre, des hypothèses, des calculs à demander, de la falsification, de l’abstention et des demandes au client. Python ne fait que lire, convertir, conserver les transformations et produire des mesures reproductibles.

## Démarrage

```sh
python intake_client_case.py atelier_01 /chemin/vers/dossier_recu --root client_cases
```

Le dossier créé est :

```text
client_cases/atelier_01/
  raw/             # copie immuable des originaux, jamais modifiée
  normalized/      # tables exploitables ou contexte normalisé
  derived/         # canonical_case.json, résumé qualité
  evidence/        # inventaire et provenance
  investigation/  # état persistant, brief Codex, questions, findings
  outputs/
  logs/
```

`client_cases/` est exclu de Git. Une copie est effectuée afin que le dossier envoyé par le client reste inchangé.

## Ce qui est déterministe

CSV, XLSX, XLS (conservé et signalé si la lecture legacy n’est pas disponible), TXT, Markdown et PDF sont inventoriés. Les classeurs XLSX sont parcourus feuille par feuille : le pipeline recherche les régions tabulaires, l’en-tête le plus plausible, les dates et les colonnes de mesure. Il n’assume jamais que la première feuille contient la donnée.

Les corrections sûres sont explicites : virgule décimale, ligne TOTAL explicitement identifiée, doublon strictement identique. Un doublon contradictoire, une unité pouvant changer une décision, une valeur suspecte ou une transition DST ambiguë restent visibles et ne sont pas « réparés ».

## Passage à Codex

Lire dans cet ordre :

1. `derived/canonical_case.json`;
2. `derived/data_quality_summary.json`;
3. `evidence/dataset_provenance.json`;
4. `investigation/CODEX_FIRST_PASS_BRIEF.md`;
5. `investigation/engine_handoff.json`.

Le handoff liste les entrées normalisées que Codex peut choisir d’analyser avec les outils existants. Il ne sélectionne pas le compteur à sa place et ne déclenche pas une investigation fixe. Une conclusion « aucun finding matériel » est valide.

## État persistant

`investigation/case_state.json` conserve l’état d’entrée, les sources, les transformations, les conclusions structurées que Codex a choisies, les demandes et les réponses. Il contient des résumés auditables, pas de chaîne de pensée détaillée. Le cas est donc reprenable sans reparcourir le dépôt brut.

Le pipeline ne constitue pas un audit énergétique réglementaire, ni un diagnostic mécanique définitif. Une revue humaine reste requise avant livraison à un client.
