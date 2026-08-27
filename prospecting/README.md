# Veille et prospection — phase pré-scoring

Ce dossier conserve une veille publique, locale et traçable. Il ne lance aucun email, aucun
scoring, aucun classement commercial ni aucune sélection de prospects à contacter.

## Exécution

```sh
python prospecting/prepare.py
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

`data/opposition.json` est la liste locale des organisations ou personnes à ne plus contacter. La
commande la contrôle avant d'inclure un prospect dans la sortie pré-scoring.
