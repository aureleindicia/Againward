# Validation du lot — 10 septembre 2026

## Résultats exécutés

| Vérification | Résultat |
|---|---|
| Tests prospection existants avant extension | 11 passent, 0,07 s |
| Suite globale configurée par `pytest.ini` (`tests/`) | 514 passent, 143,16 s |
| Tests prospection après ajout des contrôles du lot | 19 passent, 0,18 s |
| Total des deux suites complémentaires après extension | 533 tests passent |
| Reproduction via `build_artifacts.py` | 50 sociétés, 104 références de sources, aucun contact |
| Préparation / déduplication / opposition locale | 50 entités distinctes, aucun rejet d'opposition |
| Références des accroches email | 50 accroches référencées à leur propre entreprise |

Commandes depuis la racine :

```sh
python -m pytest -q
python -m pytest prospecting/tests -q
python prospecting/data/international_async_50_20260910/build_artifacts.py
```

La suite globale ne collecte pas `prospecting/tests` automatiquement : les deux commandes sont nécessaires. Les huit nouveaux tests contrôlent unicité/pays, réutilisation des contrats, reproduction des scores, priorité du filtre métier, absence de bonus pour async inconnu, provenance des accroches, absence de qualification inventée, distinction score/rang et accès aux sources échoués.

## Revue des claims

- Score existant conservé ; aucune modification du détecteur, de l'Evidence Plane ou du workflow client.
- P1 : 5 ; P2 : 31 ; P3 : 14. P3 inclut réserves métier, contraintes de partage et signaux async insuffisants. Les réserves ne sont pas présentées comme bonnes cibles prêtes au pilote.
- Ni compteur, ni sponsor, ni facture, ni gisement, ni acceptation du mode écrit obtenus. Aucune probabilité chiffrée de succès.
- 104 références distinctes : 30 pages/documents ouverts, 68 extraits indexés, 5 ouvertures échouées et 1 challenge conservés explicitement. Les six derniers restent des preuves indexées, pas des lectures intégrales. Une ouverture ne signifie pas audit exhaustif du site.
- Pas de comptes privés LinkedIn/Indeed ; pas d'adresses personnelles, d'emails devinés ou d'envois. Plusieurs reprises d'une annonce ne sont pas plusieurs confirmations indépendantes.
- Anciennes données préservées. Les deux fichiers locaux préexistants sans lien avec ce travail ne sont pas intégrés.

## Limites de la validation

Les tests prouvent la cohérence des artefacts et des calculs, pas la vérité d'un site commercial ni la valeur économique d'un pilote. Les pratiques anciennes doivent être reconfirmées ; les portails de vente ne prouvent pas la pratique des achats. Les informations de personnalisation sont des notes de rédaction, pas des emails déjà approuvés pour envoi.
