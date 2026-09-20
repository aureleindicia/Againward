# Veille et prospection sourcée

Ce dossier conserve une veille publique, locale et traçable. Il sépare la préparation des faits,
le jugement qualitatif de Codex et le calcul déterministe du score. Il ne lance aucun email et ne
prétend jamais avoir analysé les consommations d'une organisation avant réception de ses données.

## Exécution

```sh
python prospecting/prepare.py
python prospecting/score.py
```

La commande lit `data/prospects_raw.json`, valide les faits, inférences, sources, oppositions et
statuts de préqualification, puis écrit :

- `data/candidates_pre_scoring.json` : candidats et dossiers `UNCERTAIN` compacts ;
- `data/rejected_prequalification.json` : dossiers écartés avec leur justification ;
- `data/deduplication_audit.json` : doublons, relations marque/société et contradictions ;
- `data/preparation_summary.json` : compte rendu de la phase, sans score.

Les valeurs possibles de `prequalification_status` sont uniquement `CANDIDATE`, `UNCERTAIN` et
`REJECTED`. Un champ de score, priorité, rang ou recommandation de contact fait échouer la
préparation : cette phase doit rester exploitable par le modèle chargé du scoring ultérieur.

Les sources publiques sont conservées avec URL, date de récupération et niveau de confiance. Une
inférence ne doit jamais être rangée parmi les faits observés. Les adresses électroniques et noms
de personnes ne sont pas collectés dans ce premier lot.

`score.py` lit ensuite les appréciations argumentées de `data/scoring_assessments.json`. Codex
attribue les notes par dimension et Python vérifie les dimensions, applique les pondérations puis
écrit `data/scoring_results.json`. Un critère d'exclusion factuel reste prioritaire sur le score
brut. Un écart de quelques points ne doit pas être interprété comme une différence certaine.

La compatibilité asynchrone est un critère complémentaire : elle repose sur des signaux publics
traçables (organisation distribuée, canaux écrits, documentation ou portails), ne se déduit pas du
pays, et ne peut pas compenser un mauvais ajustement industriel ou de données.

Pour la priorité commerciale principalement écrite, voir [ASYNC_QUALIFICATION.md](ASYNC_QUALIFICATION.md).
Le [lot international de 50 entreprises du 10 septembre 2026](data/international_async_50_20260910/PROSPECTS_50.md)
conserve le score existant et distingue premières cibles, qualification complémentaire et réserves.
L'[audit du lot précédent](data/international_async_50_20260910/RESEARCH_REVIEW.md) expose les limites des preuves.
Les [notes de personnalisation](data/international_async_50_20260910/EMAIL_PERSONALIZATION.md)
contiennent une accroche sourcée, une fonction cible et une question métier pour chaque entreprise.
Elles n'autorisent aucun envoi. Reproduction du lot, sans modifier les anciennes données :

```sh
python prospecting/data/international_async_50_20260910/build_artifacts.py
```

`SCORING_REPORT.md` donne le jugement lisible, `data/outreach_preparation.json` prépare uniquement
les angles des candidats retenus, et `data/commercial_tracking.json` conserve leur état. Aucun de
ces fichiers ne constitue une autorisation d'envoi.

`data/opposition.json` est la liste locale des organisations ou personnes à ne plus contacter. Elle
doit être contrôlée avant toute préparation puis de nouveau juste avant tout contact.

## Rental — France et international, septembre 2026

Le [lot Rental de 100 prospects](RENTAL_100.md) contient 50 entreprises françaises et 50 hors France, avec sources, contacts publics, scores et `EMAIL_CONTEXT`. Il possède son propre schéma JSON, adapté aux factures de location, et ne modifie pas les anciens jeux Energy. Aucun envoi n’est autorisé ou effectué.

Reproduction locale des classements et exports :

```sh
python prospecting/build_rental_prospects.py
```

Les lots `batch_*.json` sont les notes de recherche, y compris les candidats rejetés en revue finale. Utiliser uniquement les exports `PROSPECTS_50.json` pour les 100 sélectionnés. Consulter [RENTAL_FINAL_REVIEW.json](RENTAL_FINAL_REVIEW.json) et [REJECTED.json](REJECTED.json) avant une préparation ultérieure.
