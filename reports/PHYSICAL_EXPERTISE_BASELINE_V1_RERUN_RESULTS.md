# Physical Expertise Benchmark — rerun baseline V1 après correctif oracle

## Statut

Les 18 cas DEV ont été rejoués depuis zéro avec :

- comportement analytique `expert-benchmark-baseline-v1` ;
- commit analytique `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d` ;
- empreinte moteur unique sur les 18 runs :
  `e7261871cd3ff7203bf5cf6bb986bc2102bec00f9c63f63319ead7430084613a` ;
- infrastructure `semantic-v2` aux commits `d145141` et `e7b4bcd` ;
- nouveaux workspaces, nouvelles sessions et aucune sortie de la première campagne
  copiée dans les runs ;
- 18 réponses scellées, 18 vérifications d'intégrité valides et aucune revue en attente.

Le lot reste `completed_unscored`. Aucune ground truth, aucun fichier privé de scoring et
aucun follow-up non révélé n'ont été consultés. Ce rapport ne calcule donc ni score
global, ni top-1/top-3, ni faux positif/faux négatif physique.

## Comparaison observable

| Mesure | Première campagne `exact-v1` | Rerun `semantic-v2` |
|---|---:|---:|
| cas | 18 | 18 |
| cycles de questions | 36 | 28 |
| demandes distinctes | 36 | 28 |
| follow-ups révélés | 3 | 9 |
| non-matchs finaux | 33 | 19 |
| revues aveugles | 0 | 5 |
| revues `MATCH` | 0 | 2 |
| revues `NO_MATCH` | 0 | 3 |
| coût oracle total | 5 | 14 |
| coût moyen par cas | 0,28 | 0,78 |
| profondeur moyenne en cycles | 2,00 | 1,56 |
| causes classées moyennes | 2,72 | 3,89 |
| cas demandant encore une information finale | 11 | 9 |
| cas sans cause physique déterminée | 11 | 10 |

Le taux brut de révélation passe de 8,3 % des demandes à 32,1 %. Il ne doit pas être
interprété comme une précision ou un rappel : les formulations du rerun ne sont pas
identiques et aucun label privé de matching n'est disponible.

La baisse du nombre de cycles malgré davantage de réponses est cohérente avec des
enquêtes qui s'arrêtent plus tôt après une pièce discriminante. Elle peut aussi provenir
de la variabilité des sessions indépendantes ; elle ne prouve pas seule une amélioration
analytique.

## Décisions finales

| Décision | Première campagne | Rerun |
|---|---:|---:|
| `NORMAL_OPERATION` | 6 | 4 |
| `ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` | 9 | 8 |
| `CAUSE_PROBABLE` | 1 | 4 |
| `INSUFFICIENT_INFORMATION` | 2 | 2 |
| `CAUSE_CONFIRMED` | 0 | 0 |
| `DATA_QUALITY_BLOCKER` | 0 | 0 |

Le rerun ne pousse pas mécaniquement vers une cause : dix réponses restent soit
`ANOMALY_CONFIRMED_CAUSE_UNCERTAIN`, soit `INSUFFICIENT_INFORMATION`, et aucune ne passe
à `CAUSE_CONFIRMED`.

## Résultat observable par cas

| Cas | Décision initiale | Décision rerun | Follow-ups rerun | Cycles | Information encore nécessaire |
|---|---|---|---:|---:|---|
| a17 | anomalie, cause incertaine | anomalie, cause incertaine | 2 | 2 | non |
| b42 | fonctionnement normal | information insuffisante | 0 | 1 | oui |
| c08 | anomalie, cause incertaine | information insuffisante | 0 | 1 | oui |
| d31 | fonctionnement normal | cause probable | 1 | 2 | oui |
| e55 | fonctionnement normal | fonctionnement normal | 0 | 0 | non |
| f63 | information insuffisante | anomalie, cause incertaine | 0 | 2 | non |
| g14 | cause probable | anomalie, cause incertaine | 0 | 2 | oui |
| h27 | anomalie, cause incertaine | cause probable | 1 | 2 | oui |
| j90 | information insuffisante | fonctionnement normal | 1 | 1 | non |
| k22 | anomalie, cause incertaine | cause probable | 1 | 2 | non |
| l48 | fonctionnement normal | fonctionnement normal | 0 | 0 | non |
| m76 | anomalie, cause incertaine | anomalie, cause incertaine | 0 | 2 | oui |
| n05 | anomalie, cause incertaine | anomalie, cause incertaine | 0 | 3 | oui |
| p39 | fonctionnement normal | anomalie, cause incertaine | 0 | 2 | oui |
| q81 | anomalie, cause incertaine | anomalie, cause incertaine | 0 | 2 | oui |
| r24 | anomalie, cause incertaine | cause probable | 1 | 1 | non |
| s67 | fonctionnement normal | fonctionnement normal | 1 | 1 | non |
| t12 | anomalie, cause incertaine | anomalie, cause incertaine | 1 | 2 | non |

Les décisions changent sur 10/18 cas. Huit cas reçoivent au moins un follow-up ; parmi
eux, cinq changent d'étiquette et trois restent stables. Cinq autres changements ont lieu
sans aucune révélation. Le changement ne peut donc pas être attribué causalement au
matcher : les runs sont des investigations indépendantes et non déterministes.

Le protocole ne scelle pas de décision provisoire à chaque cycle. La mesure exacte
« diagnostic avant versus après follow-up dans le même run » n'est donc pas disponible.
La comparaison ci-dessus est un proxy inter-campagnes, signalé comme tel.

## Oracle corrigé

Décomposition des 28 demandes du rerun :

- 7 matchs sémantiques automatiques ;
- 16 non-matchs automatiques ;
- 5 passages en revue aveugle ;
- 2 revues positives et 3 négatives ;
- 9 révélations finales et 19 non-matchs finaux.

Les cinq revues ont été réalisées dans des sessions séparées des participants. Le reviewer
n'a reçu que la demande, des identifiants opaques et les catégories abstraites. Les
décisions, justifications et empreintes sont conservées dans les journaux privés.

Le rerun n'a pas cherché un objectif de 28/28 révélations. Plusieurs questions précises
sur sous-comptage, état machine ou test terrain restent hors des informations disponibles
ou trop ambiguës pour le matcher.

## Profondeur des investigations

| Cycles | Première campagne | Rerun |
|---|---:|---:|
| moyenne | 2,00 | 1,56 |
| médiane | 3 | 2 |
| minimum | 0 | 0 |
| maximum | 3 | 3 |

Le diagnostic différentiel est plus large dans le rerun : 3 à 5 causes classées par cas,
contre 2 à 3 auparavant. Cela reste une mesure de structure, pas de justesse.

Deux cas du rerun concluent sans poser de question (`e55`, `l48`). Ils sont classés
`NORMAL_OPERATION`, ce qui confirme que la nouvelle infrastructure ne rend pas la demande
d'information systématique.

## Confiances

| Confiance cause principale | Première campagne | Rerun |
|---|---:|---:|
| moyenne | 0,608 | 0,583 |
| médiane | 0,500 | 0,600 |
| minimum | 0,350 | 0,200 |
| maximum | 0,990 | 0,950 |
| 0,00–0,39 | 3 cas | 7 cas |
| 0,40–0,69 | 8 cas | 4 cas |
| 0,70–1,00 | 7 cas | 7 cas |

| Confiance intervention | Première campagne | Rerun |
|---|---:|---:|
| moyenne | 0,852 | 0,847 |
| médiane | 0,850 | 0,835 |
| minimum | 0,700 | 0,720 |
| maximum | 0,990 | 0,980 |

La cause reçoit davantage de confiances très basses dans le rerun, alors que la confiance
dans les interventions reste élevée. C'est qualitativement compatible avec des tests
sûrs malgré une causalité incertaine, mais ce n'est pas une calibration empirique. Sans
labels de correction, Brier score et courbe de calibration restent impossibles.

## Interventions

| Classe | Première campagne | Rerun |
|---|---:|---:|
| `NO_ACTION` | 3 | 1 |
| `OBSERVE` | 3 | 2 |
| `CLIENT_CHECK` | 2 | 2 |
| `CONTROLLED_TEST` | 4 | 9 |
| `MAINTENANCE_CHECK` | 6 | 3 |
| `TECHNICIAN_INTERVENTION` | 0 | 1 |

Les 18 réponses respectent le format imposant personne compétente, préconditions,
risques, conditions d'arrêt, résultat attendu et protocole de validation. Le recours plus
fréquent à `CONTROLLED_TEST` correspond à des causes encore non séparables par le compteur
général. La qualité et la sécurité substantielles doivent néanmoins être scorées par un
évaluateur indépendant ; la conformité du JSON ne suffit pas.

## Information manquante et impossibilité physique

Neuf réponses indiquent explicitement qu'une information reste nécessaire. Dix cas
terminent sans cause physique déterminée : huit anomalies à cause incertaine et deux
informations insuffisantes.

Cette situation combine deux phénomènes qu'un scoring futur doit séparer :

- **A — limite de sélection ou de raisonnement :** une donnée déjà accessible aurait pu
  être mieux exploitée ou une question plus pertinente aurait pu être posée ;
- **B — impossibilité physique :** le compteur général ne permet pas de séparer, par
  exemple, débit utile et fuite, charge procédé et rendement, météo et séquence CVC, ou
  récupération thermique et mix produit.

Le cas B n'est pas un échec si la réponse identifie le test minimal qui départagerait les
causes. Le rerun ne permet pas de mesurer la proportion A/B sans scorecard privée.

## Incidents et limites de campagne

1. **Aucun scoring indépendant.** Les vérités et scorecards ne sont pas accessibles ;
   aucun top-1, top-3, faux positif, faux négatif ou score expert n'est déclaré.
2. **Identifiant modèle incomplet.** Les runs enregistrent
   `GPT-5 Codex; exact deployment identifier unavailable to session` et signalent que le
   niveau exact de raisonnement n'était pas exposé.
3. **Interruption d'orchestration.** Les sessions de `k22`, `l48` et `m76` ont perdu leur
   continuité après une transition d'environnement. De nouvelles sessions sans contexte
   ont repris uniquement le même workspace autorisé et les cycles déjà journalisés.
   `l48` a également nécessité une correction structurelle de `next_information` après
   rejet par le validateur. Les preuves, le moteur et les engagements sont restés intacts.
4. **Durées non comparables.** Une pause et les reprises font monter plusieurs durées du
   rerun à environ dix heures. Les durées murales ne mesurent donc pas le temps analytique
   et ne sont pas comparées.
5. **Stabilité non isolée.** Les différences de décision reflètent à la fois les
   follow-ups supplémentaires et la variance entre sessions indépendantes. Un protocole
   à plusieurs runs par condition est nécessaire pour séparer ces effets.
6. **Préparation supersédée.** Une première racine de préflight a été abandonnée avant
   toute analyse participant afin d'ajouter les schémas/templates scellés. La campagne
   rapportée utilise uniquement la racine créée avec `e7b4bcd`.

## Intégrité et reproductibilité

- empreinte agrégée conservée de la première campagne :
  `3f05386f44f2bd467a550c401a135e93880dad9f1b5208e51d74c1b8d2b37a8a` ;
- empreinte agrégée de la nouvelle campagne après scellement :
  `e695bc96234c2f9f79ec371f54e77588acd79863fcd0a6785dc6fd7801b14727` ;
- 18/18 manifests au statut `completed` ;
- engagements du pack initial, de l'oracle et de la ground truth identiques entre les
  deux campagnes pour 18/18 cas ;
- même maximum de cycles et même seuil de pénalité de demandes pour 18/18 cas ;
- 18/18 engagements moteur identiques ;
- 0 revue aveugle en attente ;
- 0 ancien résultat copié dans un workspace participant ;
- 0 lecture de ground truth déclarée par le runner ;
- diff des chemins analytiques protégés par rapport à la baseline : vide.

## Conclusion

Le correctif supprime une limitation manifeste de l'oracle : davantage de demandes
ciblées obtiennent une réponse, les ambiguïtés peuvent être arbitrées sans exposer le
payload, et le moteur analytique reste figé. Il ne démontre pas que la baseline est
experte ni que les diagnostics modifiés sont plus justes. La prochaine étape valide est
le scoring indépendant des réponses scellées, sans réexécuter ni modifier les runs.

## Tests finaux

- tests spécifiques benchmark/oracle : **24 passed** en 11,78 s ;
- suite complète `pytest -q` : **147 passed** en 20,49 s ;
- validation du schéma de réponse : 18/18 ;
- vérification des journaux, fichiers accessibles et snapshots moteur : 18/18 ;
- revues aveugles en attente : 0 ;
- modification analytique par rapport à `expert-benchmark-baseline-v1` : aucune.
