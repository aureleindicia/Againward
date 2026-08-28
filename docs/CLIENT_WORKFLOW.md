# Workflow d'un nouveau client

Ce workflow est local-first et conçu pour une petite entreprise. Python prépare et vérifie les
preuves quantitatives ; Codex choisit les investigations et rédige ; un humain autorise la
livraison. Aucun stade automatique ne transforme un signal candidat en économie.

La prestation est une investigation de performance énergétique autonome sur données : elle doit
détecter et quantifier les dérives, éliminer les fausses pistes, cibler les vérifications terrain
et mesurer l'effet après correction. Elle n'est pas limitée à la préparation d'un autre audit.
Elle peut néanmoins fournir à un auditeur, frigoriste, électricien ou mainteneur les périodes,
preuves et hypothèses qui indiquent précisément où chercher.

Cette prestation ne constitue pas un audit énergétique réglementaire.

## 1. Créer et renseigner le dossier

Avant de créer un espace client ou de demander un fichier, envoyer la fiche
[`CLIENT_DATA_FEASIBILITY_REQUEST.md`](CLIENT_DATA_FEASIBILITY_REQUEST.md). Elle permet au client
de confirmer l'existence d'un export et son périmètre sans fabriquer de données manuellement. Les
critères de cette fiche correspondent aux contrôles d'intake ci-dessous.

```sh
python create_workspace.py usine_01
```

Compléter `workspaces/usine_01/intake.json`, puis déposer une copie du fichier dans `input/`.
Les informations réellement critiques sont le périmètre du compteur, la nature et l'unité de la
mesure, la convention début/fin d'intervalle et le fuseau du site. Les horaires, fermetures,
maintenance, production, météo et tarif augmentent les analyses possibles mais une absence est
conservée comme limite, jamais inventée.

Si le contrat contient des plages ou une puissance facturée, renseigner
`cost.time_of_use_periods` et `cost.demand_charge_per_kw_month`. Le paquet produit alors
`tariff_cost.json`. Ce coût contractuel reste distinct d'une économie récupérable.

## 2. Préparer l'investigation générique

```sh
python investigate.py workspaces/usine_01/input/mesures.csv \
  --intake workspaces/usine_01/intake.json \
  --output-dir workspaces/usine_01/processed
```

Le paquet contient notamment `prepared_analysis.json`, `candidate_signals.json`,
`intake_assessment.json`, `investigation_state.json`, `questions.json`, `human_review.json`,
`trace.json` et `ANALYST_BRIEF.md`. Les événements automatiques restent `candidate_signal`.

## 3. Investigation Codex

Codex écrit `investigation.json`. Chaque piste doit contenir : observation, hypothèse, test(s),
résultat provenant de Python, contre-explication, meilleure raison d'être fausse, décision,
confiance, statut explicite de la cause physique et éventuelle demande minimale. Une décision
incertaine exige une demande précise ; une décision tranchée ne déclenche pas de question par
réflexe. Les recommandations sont validées séparément et ne peuvent annoncer une économie
récupérable lorsque la cause n'est pas prouvée. Elles définissent toujours une mesure après
intervention. Si le comportement mérite un suivi durable, elles peuvent aussi définir un bloc
`continuous_monitoring` avec condition d'activation, cadence, règle d'alerte et responsable.

## 4. Questions et réponses

```sh
python manage_investigation.py questions workspaces/usine_01/processed
```

Le fichier `questions.json` ne publie que la prochaine demande prioritaire de chaque piste. Pour
enregistrer les réponses, créer par exemple :

```json
{
  "answers": [
    {
      "request_id": "H01-Q1",
      "answer": "Le site était fermé et aucun nettoyage n'était planifié.",
      "provided_by_role": "responsable de production",
      "source_or_evidence": "Planning signé de la semaine 12"
    }
  ]
}
```

Puis :

```sh
python manage_investigation.py answers workspaces/usine_01/processed answers.json
```

Une réponse déjà consignée ne peut pas être réécrite. Codex peut alors demander un nouveau calcul,
réviser `investigation.json` et archiver le cycle entièrement répondu avant d'en publier un autre :

```sh
python manage_investigation.py next-cycle workspaces/usine_01/processed
python manage_investigation.py questions workspaces/usine_01/processed
```

Les archives numérotées restent dans `question_cycles/` avec leur empreinte dans `trace.json`.

## 5. Review contradictoire

Codex écrit `review.json` avec `ground_truth_used: false` et une entrée pour chaque hypothèse non
rejetée. Chaque entrée répond à la question « quelle est la meilleure raison de penser que cette
conclusion pourrait être fausse ? » et contrôle exactement :

- calculs ;
- qualité des données ;
- robustesse de la baseline ;
- explications alternatives ;
- causalité ;
- annualisation ;
- économie récupérable ;
- double comptage.

Chaque contrôle porte un statut `passed`, `failed` ou `not_applicable` et une preuve. Une conclusion
avec un contrôle échoué ne peut pas rester `CONFIRME`.

## 6. Rapport et validation humaine

Après rédaction de `report.md`, le relecteur complète `human_review.json` :

```json
{
  "schema_version": 1,
  "status": "approved",
  "reviewer_role": "ingénieur énergie",
  "reviewed_at_utc": "2026-08-27T13:00:00+00:00",
  "approved_for_delivery": true,
  "reservations": ["La cause physique H01 reste à vérifier sur site."]
}
```

Le logiciel ne remplit jamais cette approbation lui-même. Le contrôle final est :

```sh
python manage_investigation.py check workspaces/usine_01/processed
```

`delivery_gate.json` contient le statut, les blocages et l'empreinte des quatre livrables. Un code
de sortie `3` signifie que le dossier n'est pas livrable ; ce n'est pas une erreur de calcul.
