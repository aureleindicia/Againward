# Rapport de validation privacy

Date d’exécution : 2026-09-05

Environnement : Android/Termux, Python 3.14.6
Nature des données : fixtures exclusivement synthétiques

## Portée validée

La validation couvre la réception sans lecture, le gate Codex-first, les trois décisions,
le post-check déterministe, la préservation analytique, les verrous lifecycle, la reprise,
l’attribution minimale, la revue humaine, Git, la rétention et la purge.

## Tests exécutés avant commit

| Commande | Résultat |
| --- | ---: |
| `python -m pytest -q tests/test_client_workflow_unification.py tests/test_workflow_paths.py` | 39 passed |
| `python -m pytest -q tests/test_privacy_gate.py` | 36 passed |
| privacy + intake + workspace + lifecycle + économie + workflow | 119 passed |
| `python -m compileall -q ...` | succès |
| `git diff --check` | succès |

La première exécution globale a produit `380 passed, 3 failed`. Un échec documentaire réel
(chemin Download requis par le contrat) a été corrigé. Les deux autres étaient les protections
d’intégrité HOLDOUT qui refusent volontairement un moteur modifié par rapport à `HEAD`. La suite
globale doit donc être relancée après création du commit local propre ; son résultat final est
enregistré plus bas avant publication.

## Scénarios privacy/adversarial

Les tests vérifient notamment :

- CSV propre → PASS et suppression de l’original temporaire ;
- noms, emails, téléphones et matricules retirés/pseudonymisés ;
- stabilité/injectivité des pseudonymes et conservation des jointures machine/shift ;
- machine ou produit appelé `Jean`, et identifiant machine ressemblant à un téléphone, conservés ;
- email en note libre et marqueurs machine/cycle en texte préservés ;
- secrets résiduels, RH/médical, mutation énergétique, perte de ligne ou relation → BLOCKED ;
- classeurs XLSX multi-feuilles, texte, doublons et nettoyage interrompu ;
- review invalide, symlink/artefact auxiliaire ou table de correspondance durable → BLOCKED ;
- aucun contenu retiré dans le manifest ou le reçu de purge ;
- intake/finding/attribution impossible avant clearance, possible après ;
- hash sanitized vérifié et sortie hors workspace refusée ;
- reprise après réponse typée et approbation humaine inchangées ;
- purge complète, purge partielle honnête et rétention dérivée refusée par défaut ;
- patterns Git réels vérifiés avec `git check-ignore`.

## Benchmarks exécutés

### Workflow client

Commande : `python benchmarks/client_workflow/benchmark.py`

| Candidats | Médiane | Sélection | Rejets |
| ---: | ---: | ---: | ---: |
| 10 | 3.781 ms | 3 | 7 |
| 100 | 40.804 ms | 3 | 97 |
| 1 000 | 433.268 ms | 3 | 997 |

Les assertions `bounded_selection` et `semantic_deduplication_exercised` passent.

### Post-check privacy

Commande : `python benchmarks/privacy_gate/benchmark.py`

| Lignes | Taille | Temps | Débit | RSS max processus |
| ---: | ---: | ---: | ---: | ---: |
| 10 000 | 325 691 octets | 0.131 s | 76 152 lignes/s | 75 300 KiB |
| 100 000 | 3 256 561 octets | 0.408 s | 245 353 lignes/s | 75 300 KiB |
| 500 000 | 16 282 648 octets | 2.342 s | 213 514 lignes/s | 242 972 KiB |

Les trois cas produisent PASS avec `approved_for_analysis=true`. Le RSS est celui du processus
entier et dépend de l’ordre des tailles ; il ne constitue pas une limite garantie.

## Résultat global sur commit propre

Commande : `python -m pytest -q`

Résultat final confirmé : **386 passed in 81.01s** (première passe propre : 83.12s). Les protections
HOLDOUT qui échouaient volontairement sur le worktree modifié passent une fois le moteur fixé dans
`HEAD` ; aucune exigence de test n'a été diminuée ou contournée.

## Ce que ces preuves démontrent

- Les entrées officielles de dossiers réels échouent fermées avant clearance.
- Le post-check détecte les catégories/patterns explicitement testés et refuse les mutations
  industrielles observables.
- Le workflow existant de questions, reprise, attribution et revue humaine reste opérationnel.
- La purge exécute réellement des suppressions et ne transforme pas une erreur en succès.

## Risques résiduels

- La compréhension sémantique dépend de la qualité de la revue Codex ; aucun détecteur universel de
  noms ou secrets propriétaires n’est démontré.
- Les textes libres ne permettent qu’un contrôle déterministe de marqueurs industriels, pas une
  preuve sémantique complète de non-altération.
- L’effacement physique, les backups Android/éditeur et les politiques d’OpenAI sont hors contrôle
  du dépôt.
- La désidentification de long terme reste exposée aux singularités industrielles ; elle est donc
  refusée par défaut et n’est jamais présentée comme anonymisation parfaite.
- Les chiffres ci-dessus sont synthétiques et ne démontrent pas une performance privacy sur un
  corpus client réel.
