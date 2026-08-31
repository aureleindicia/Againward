# Notes de migration Stage 4

## Ce qui change par défaut

`investigate.py` utilise `--evidence-plane-mode preferred`. Le dossier préparé contient toujours
les artefacts historiques et ajoute :

- `evidence_dataset.json` ;
- `evidence_card.json` ;
- `evidence_query_contract.json` ;
- `evidence_query_session.json` ;
- `agent_findings_template.json` ;
- `evidence_queries/` après le premier appel.

Les colonnes inconnues ne sont plus perdues. Elles restent séparées du modèle physique et sont
visibles uniquement si Codex les sélectionne dans une requête.

## Compatibilité conservée

- Les classes `Reading`, `AnalysisResult`, `Finding` et les unités internes gardent leurs contrats.
- `LoadedData` reçoit un champ `auxiliary` avec défaut vide ; les constructions existantes restent
  valides.
- `prepared_analysis.json`, `candidate_signals.json`, `intake_assessment.json`, `questions.json`,
  `review.json`, le rapport et les calculateurs legacy restent présents.
- `detect_candidate_events` n’est ni supprimé ni transformé en décision.
- Les rapports client ne lisent pas directement le snapshot et restent simples.
- Les tests et preuves historiques Stage 1/2/3 ne sont pas réécrits.

## Comportements volontairement renforcés

- Un doublon physiquement identique mais contextuellement différent est désormais conflictuel en
  mode nominal, afin de ne pas supprimer une information opérationnelle.
- Une source contenant plus de 128 colonnes auxiliaires est refusée par défaut. La limite peut être
  augmentée explicitement jusqu’à 512.
- Une valeur auxiliaire au-delà de 4096 caractères est tronquée avec compteur et avertissement ; la
  limite explicite peut monter jusqu’à 65536.
- Le verrou de livraison exige `agent_findings.json` et valide ses références si le dossier contient
  une session Evidence Plane.

## Classification legacy

- Détecteur multi-événements : **retenu** comme génération de candidats, régression et fallback.
- H01 intervention effect : **recherche/régression**, non promu comme conclusion fixe.
- H02 temporal coupling : **recherche/régression**, remplaçable par contrastes temporels choisis.
- H03 flexibility envelope : candidate Stage 2 **rejetée**, préservée comme résultat négatif.
- H05 natural experiment : **recherche/régression**, aucun claim de récupérabilité automatique.

Les surfaces Stage 4 ne sont pas des remplacements un-à-un de H01/H02/H03/H05. Elles offrent des
questions plus générales que Codex compose selon le dataset.

## Shadow

Le mode `shadow` construit les deux représentations dans un même nouveau dossier et écrit
`shadow_comparison.json`. Il compare conservation des candidats, disponibilité des colonnes,
provenance, interface dynamique, taille de contexte, erreurs et temps. En l’absence de vraie
investigation modèle, le désaccord de conclusions reste explicitement `NOT_MEASURED`.

La suite reproductible est :

```sh
python run_stage4_shadow.py
```

Elle utilise trois fixtures synthétiques/de régression du dépôt et ne constitue pas une validation
aveugle nouvelle.

## Rollback

Le rollback immédiat est un nouveau dossier préparé en mode legacy :

```sh
python investigate.py SOURCE --output-dir NOUVEAU_DOSSIER \
  --evidence-plane-mode legacy
```

Ce mode désactive Evidence Plane et la conservation auxiliaire, ce qui restaure aussi l’ancienne
sémantique de déduplication. Il n’écrase jamais un dossier existant. Aucun downgrade de schéma ni
suppression de snapshot n’est nécessaire, et aucune migration destructive de données n’a eu lieu.

Pour diagnostiquer seulement l’interface nouvelle tout en gardant les deux chemins :

```sh
python investigate.py SOURCE --output-dir DOSSIER_SHADOW \
  --evidence-plane-mode shadow
```

## Limites connues

- Le snapshot JSON est local et inspectable, mais volumineux à 500 000 lignes.
- Les champs physiques bruts avant normalisation ne sont pas dupliqués dans le snapshot.
- Les types auxiliaires sont prudents mais ne remplacent pas une déclaration métier d’unité.
- Support Atlas est volontairement refusé si les cohortes dépassent le budget quadratique.
- Boundary Ledger est exploratoire et sensible aux saisons, changements d’export et autocorrélation.
- Aucun benchmark de qualité agent avec un vrai petit modèle n’a été exécuté dans cet environnement.
