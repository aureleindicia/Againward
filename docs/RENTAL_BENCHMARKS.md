# Benchmarks Rental

```sh
python run_rental_benchmark.py --output scratch/rental_run --performance
python -m pytest -q tests/test_rental*.py
```

Un dossier de sortie non vide est refusé. Le générateur écrit uniquement les sources
et extractions dans chaque dossier participant. La vérité attendue reste dans le
scorer et n'est lue qu'après exécution ; le moteur n'importe aucun module benchmark.
`validation.json` contient les sorties et les assertions, `performance.json` les
mesures locales, les dossiers `cases/` conservent requêtes et traces.

Résultat au checkpoint `9496e15` : **13/13 cas**. Les montants ci-dessous proviennent
de `validation.json`, pas d'une estimation de l'agent.

| Cas | Résultat attendu et obtenu |
|---|---|
| R01 facture correcte | Aucun écart positif ni réclamation automatique |
| R02 mauvais tarif | Écart contractuel 150,00 EUR |
| R03 facturation après retour | Écart contractuel 300,00 EUR |
| R04 doublon | Écart commun 700,00 EUR, non multiplié par les familles |
| R05 frais sans base | Signal L1, montant récupérable inconnu |
| R06 retour ambigu | L1 → une demande BLOCKING → WAIT → réponse simulée → RESUMING → recalcul de 300,00 EUR → review → FINALIZABLE |
| A01 mêmes descriptions, actifs/sites différents | Aucun écart positif |
| A02 prolongation ultérieure autorisée | Contradiction exposée, abstention monétaire |
| A03 supplément week-end autorisé | Aucun écart positif |
| A04 avoir correct | Écart net nul |
| A05 avenant tarifaire accepté | Écart nul |
| A06 contrat manquant | Base inconnue, aucune réclamation inventée |
| A07 deux lignes pour deux unités autorisées | Aucun faux doublon monétaire |

Métrique **par cas avec écart positif étayé avant réponse**, distincte de la détection
de tous les signaux : TP=3, FP=0, FN=0, TN=10, précision=1, rappel=1, F1=1.
Les cas d'ambiguïté restent négatifs pour cette métrique malgré leurs signaux L1.
Il s'agit d'une petite suite contractuelle explicite, pas d'une estimation de
performance sur de nouveaux fournisseurs. La revue et la réponse R06 sont des
fixtures scénarisées : aucune métrique de raisonnement autonome n'est revendiquée.

Premier relevé Termux, validation canonique + ledgers + rapprochement : 1 000 lignes
en 0,333 s ; 10 000 lignes en 3,291 s. Ce relevé exclut extraction documentaire,
requêtes et I/O de rapport. Les timings dépendent de l'appareil et ne sont pas des
seuils de réussite des tests. Les comparaisons utilisent des index par clé, pas une
recherche de toutes les paires de factures.

Tests complémentaires : arithmétique décimale indépendante du contexte, mois
calendaires, prorata/minimum/week-ends, retour partiel, faux document opérationnel,
tarif sans autorité contractuelle, quantité, FX refusé, crédits, cycles de dépendance,
provenance/altération, XLSX, privacy, limites L3 et invalidation de la revue humaine.
