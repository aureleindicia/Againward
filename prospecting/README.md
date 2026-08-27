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

`SCORING_REPORT.md` donne le jugement lisible, `data/outreach_preparation.json` prépare uniquement
les angles des candidats retenus, et `data/commercial_tracking.json` conserve leur état. Aucun de
ces fichiers ne constitue une autorisation d'envoi.

`data/opposition.json` est la liste locale des organisations ou personnes à ne plus contacter. Elle
doit être contrôlée avant toute préparation puis de nouveau juste avant tout contact.
