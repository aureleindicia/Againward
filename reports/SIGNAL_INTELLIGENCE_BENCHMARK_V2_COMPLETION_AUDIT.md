# Signal Intelligence Benchmark V2 — audit R&D contradictoire

Date : 2026-09-02
Protocole courant : `2.3`

## Verdict

L'infrastructure de benchmark, le corpus synthétique multi-réalisations et les deux
contrôles sont reproductibles. Une amélioration déterministe est conservée pour la
**détection candidate**, la **quantification partielle** et la **découverte de motifs
synthétiques**.

Le benchmark ne démontre pas l'attribution d'un actif, un mécanisme physique, un
pronostic, une capacité agentique supérieure ou une validité terrain. Ces couches ont
un taux de réussite nul lorsqu'elles sont applicables, sauf la signature latente L2.

Le détail numérique public est dans
`reports/SIGNAL_INTELLIGENCE_BENCHMARK_V2_RESULTS.json`. Les cas, vérités et runs restent
privés et exclus de Git.

## Ce qui a été réellement exécuté

- lecture et audit de l'architecture INDICIA, des handoffs R&D, benchmarks et rapports
  Stage 2 à Stage 4 ;
- reproduction du pipeline Energy Analyzer sur les fixtures 15 minutes et mensuelles ;
- suite historique explicite : 323 tests passaient avant les renforcements V2 ;
- campagne finale principale : 278 tests passent ;
- campagne historique finale explicite : 336 tests passent ;
- génération et audit privé de 126 cas (42 réalisations physiques, trois niveaux) ;
- 126 runs de contrôle nul et 126 runs déterministes, chacun préparé et verrouillé avant
  lecture de la vérité ;
- ablation de trois baselines de détection, trois méthodes de quantification et trois
  granularités de signature ;
- mutations adversariales du contrat, du scorer, des timestamps et de l'agrégation.

## Corpus final

Le corpus `2.3`, seed `260902`, contient :

- 14 familles de scénario et 3 réalisations stochastiques par famille ;
- 42 vérités physiques indépendantes par niveau ;
- 126 cas après ablation `L0_E15` / `L1_PQ1` / `L2_EDGE` ;
- 54 cas marqués DEV et 72 HOLDOUT en comptant niveaux et réalisations ;
- 36 cas avec outcome futur ; les outcomes sont présents dans les deux stages ;
- deux codes d'outcome positif : intervention maintenance et failure ;
- 263 470 599 octets de packs publics ;
- audit privé `valid`, sans issue détectée.

Engagements de reproduction :

```text
suite_manifest_sha256:
a7138c98355a03b411e127b42cc8bf487dfaf71bac1f28c4bb22c4d5a7029da0

protocol_snapshot_commitment_sha256:
5be0dceb4574a8f5b61ae27952683b0d41ce52d5c069ac317a41399c7cdcc2cc

generator_sha256:
1009bcc5f220685e949bbe4cb5467f5826917bee40c287f36b707c144fa047c4
```

## Falsifications qui ont modifié le système

### Temps et DST

Le corpus original 2.0 utilisait une durée UTC fixe autour du passage à l'heure d'été.
Python a montré que 42/42 cas finissaient à `2026-04-13T01:00:00+02:00`, avec des
mesures du 13 avril mais seulement 42 dates de contexte arrêtées au 12 avril. Le
générateur utilise maintenant 42 jours calendaires locaux complets : 4 027 timestamps
15 minutes uniques, plus un doublon injecté, et un cutoff à minuit local.

### Séparation des capacités

Les corrections suivantes empêchent une preuve de glisser d'une couche à l'autre :

- détection binaire distincte de la classification du phénomène ;
- signature reproductible jugée sans exiger le nom du bon actif ;
- attribution applicable seulement lorsque la vérité contient un actif cible ;
- mécanisme physique non crédité sur les cas normaux et artefacts de mesure ;
- quantification applicable seulement lorsqu'un excès positif existe ;
- pronostic applicable aux outcomes futurs positifs, sans crédit de classe majoritaire
  pour une abstention ;
- abstention négative non comptée comme attribution ou quantification réussie ;
- capacité complète impossible à valider sur un simple cas normal.

### Scoring et intégrité

- références d'événements uniques dans et entre signatures ;
- nombres finis obligatoires, ordre temporel et cohérence finding/assessment contrôlés ;
- énergie récupérable impossible sans énergie observée ou supérieure à celle-ci ;
- code d'outcome et actif du pronostic scorés ;
- `action_code` borné à un vocabulaire explicite, y compris les actions dangereuses ;
- fichiers publics validés sémantiquement avant analyse ;
- chemins de suite relatifs et contenus dans la racine ;
- snapshot autonome du protocole générateur et engagements SHA-256 ;
- Wilson global supprimé lorsque plusieurs cartes partagent une réalisation physique ;
- comparaison appariée conservant toutes les répétitions et identifiant modèle/effort.

### Corpus pronostique

Une première campagne 2.2 avait 27 outcomes, tous en DEV. Elle a été invalidée comme
preuve pronostique. Le protocole 2.3 place des outcomes en DEV et HOLDOUT et ajoute une
classe `FAILURE`. Ce changement ne transforme pas le contrôle déterministe en modèle de
pronostic : il échoue bien 0/36 cas applicables.

## Ablation et amélioration retenue

Sur 42 réalisations L0 indépendantes du corpus de développement multi-seed :

| Détection | Précision | Rappel | F1 | Brier |
|---|---:|---:|---:|---:|
| inconditionnelle | 0,739 | 0,567 | 0,642 | 0,310 |
| production | 0,778 | 0,700 | 0,737 | 0,291 |
| production + température | **1,000** | **0,700** | **0,824** | **0,175** |

Le modèle production+température réduisait toutefois la quantification à 0/30 dans
±25 %. Le calcul d'énergie a donc été découplé de la décision de détection :

| Méthode d'énergie, détection fixe | Réussites ±25 % | Erreur relative moyenne émise |
|---|---:|---:|
| production + température | 0/30 | 0,448 |
| production | **14/30** | 0,287 |
| inconditionnelle | 13/30 | **0,269** |

Production est retenue parce qu'elle réussit un cas supplémentaire au critère
pré-enregistré de ±25 % et avait la meilleure erreur DEV entre les deux hybrides. Le
résultat reste mitigé et n'autorise pas une promesse de quantification fiable.

Sur 42 cas L2 indépendants :

| Signature | Couverture événements | Pureté pondérée |
|---|---:|---:|
| amplitude | 0,404 | 0,969 |
| P/Q | 0,429 | 0,987 |
| morphologie complète | **0,438** | **0,995** |

La morphologie complète est conservée. Sa pureté porte sur le simulateur ; elle ne
prouve ni identité d'actif sur site, ni causalité physique.

## Résultat final du contrôle déterministe

Par niveau indépendant (42 cas) :

- 21 vrais positifs, 0 faux positif, 9 faux négatifs, 12 vrais négatifs ;
- précision 1,000, borne basse Wilson 95 % 0,845 ;
- rappel 0,700, borne basse Wilson 95 % 0,521 ;
- F1 0,824 ;
- au seuil 0,90 : 12/12 alertes vraies, borne basse Wilson 0,758, couverture 0,286.

Sur les 126 ablations :

| Couche | Réussites / applicables |
|---|---:|
| détection | 99/126 |
| classification du phénomène | 36/126 |
| signature reproductible L2 | 42/42 |
| attribution d'actif | **0/72** |
| mécanisme physique | **0/72** |
| énergie dans ±25 % | 42/90 |
| pronostic | **0/36** |
| capacité complète | **0 %** |

Le pire mécanisme est `HEAT_EXCHANGE_DEGRADATION`, score moyen 12,814 et détection
nulle. Cette faiblesse n'est pas masquée par la moyenne.

## Ce que les chiffres permettent d'affirmer

Sur les scénarios synthétiques définis :

- la baseline contextuelle détecte une partie des changements agrégés sans faux positif
  observé sur 42 réalisations indépendantes par niveau ;
- L2 permet au contrôle de former des motifs répétables très purs dans le simulateur ;
- l'hybride améliore nettement la quantification par rapport au modèle initial, mais
  reste hors tolérance dans plus de la moitié des cas applicables.

## Ce qu'ils ne permettent pas d'affirmer

- qu'un compteur central identifie une machine réelle ;
- que les candidats top-3 sont une attribution opérationnelle ;
- qu'un mécanisme de panne est démontré ;
- qu'un événement maintenance est prédit ;
- qu'une probabilité est calibrée sur le terrain ;
- que les niveaux L1/L2 n'apportent rien : le détecteur de contrôle n'utilise simplement
  pas leurs variables supplémentaires pour sa décision agrégée ;
- que HOLDOUT est cognitivement aveugle dans cette session, puisque le générateur a été
  inspecté pendant la R&D ;
- que le contrôle déterministe mesure la valeur ajoutée de Codex.

## Gates restant à franchir

1. run agentique neuf, session isolée, d'abord DEV puis moteur/prompt gelés ;
2. HOLDOUT agentique sans accès au générateur, aux vérités, anciens scores ou à cette
   conversation ;
3. comparaison appariée avec contrôle déterministe et, si possible, analystes humains ;
4. cas historiques confirmés multi-sites ;
5. validation prospective terrain avec outcomes et interventions observés.

Tant que ces gates ne sont pas franchis, le statut reste : **infrastructure et contrôles
synthétiques validés ; attribution, mécanisme et pronostic non démontrés**.
