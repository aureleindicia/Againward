# Goal C — Client Decision Delivery

## Livré

Goal C ajoute `client_delivery.py`, une couche de livraison qui consomme les
états Goal A/B sans les modifier :

```text
narratif Codex + états Goal A/B
→ CLIENT_REPORT_MODEL.json validé
→ graphique explicitement choisi
→ PDF client
```

Le PDF léger produit par la bibliothèque standard est autonome, partageable et
lisible sans UI. Les deux E2E synthétiques sont :

- `examples/goal_c_e2e_case/boulangerie_centre/` : réparation recommandée,
  alternative de remplacement non cumulative, contrainte d'ouverture, calcul
  économique et graphique utile ;
- `examples/goal_c_no_finding_case/atelier_reference/` : no-finding Goal A et
  `DO_NOTHING` Goal B sans action ni économie inventée.

## Contrats principaux

- Toute carte référence une action sélectionnée, décision, finding et calcul
  Goal A/B réels.
- La décision, le niveau de preuve, les économies, CAPEX, fourchettes et
  contraintes dures sont résolus depuis Goal B, pas réécrits par le rapport.
- Le narratif Codex est requis pour expliquer le contexte mais les nombres
  libres y sont interdits : les claims quantitatifs sont rendus depuis Python.
- Les alternatives restent non additives; le total économique n'est affiché
  que lorsqu'il est agrégable selon Goal B.
- Une économie est `POTENTIAL`, jamais `VERIFIED` avant validation post-action.
- Les réponses Goal B déjà reçues sont référencées dans le modèle et ne sont
  pas redemandées au client.

## PDF et fixtures

Le rapport E2E principal fait cinq pages et le no-finding quatre pages; tous
deux restent dans la cible de trois à huit pages. Les vérifications binaires
contrôlent le format PDF, les pages, l'absence d'IDs internes, de chemins locaux
et l'existence du graphique.

`examples/goal_c_fixtures.json` couvre C-A à C-J : action forte,
investigation, non-rentabilité, contrainte opérationnelle, no-finding,
alternatives, précision, incertitude, réalisme PME et réponse Goal B.

## Auto-revue finale

- Le client peut comprendre la conclusion principale en quelques minutes : **YES**.
- Toute recommandation importante explique pourquoi elle compte : **YES**.
- Les chiffres précis justifiés restent précis : **YES**.
- Les incertitudes réelles restent des fourchettes : **YES**.
- Une économie théorique opérationnellement absurde peut être recommandée : **NO**.
- Goal C peut renforcer une décision ou un claim Goal B : **NO**.
- Un vrai no-finding peut produire un rapport utile : **YES**.
- Un rapport normal reste entre trois et huit pages : **YES**.
- Le rapport simplifie la décision au lieu de créer une charge opérationnelle : **YES**.
