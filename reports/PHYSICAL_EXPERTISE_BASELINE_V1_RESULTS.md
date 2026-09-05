# Physical Expertise Benchmark — résultats de la baseline V1

## Statut du lot

Cette campagne mesure le comportement analytique figé sous le tag `expert-benchmark-baseline-v1`, commit `6ba8ebbdefac68caa3b2debb24f9b141472f0a9d`.

L'infrastructure d'exécution provient du commit `ae55f35a5874fbdb7f7ffdaecfe35cf812b5ec45`. La comparaison Git des chemins analytiques protégés entre ces deux références est vide : aucun module moteur, heuristique, seuil, prompt analytique, profil métier ni stratégie d'investigation n'a été modifié pour cette campagne.

Les 18 cas DEV ont été fournis indépendamment. Le pack opérateur précise que les vérités terrain ne sont pas incluses : les dossiers `ground_truth/` sont vides et seuls des engagements SHA-256 sont présents. Il ne fournit ni scorecard ni mécanisme de scoring externe. En conséquence, ce rapport ne fabrique aucun score de justesse.

## Périmètre

- 18 cas, un run indépendant par cas ;
- six familles, trois cas chacune : froid, procédés thermiques, air comprimé, moteurs/pompes/ventilation, blanchisserie/eau chaude/vapeur et HVAC ;
- difficultés : 2 cas D1, 9 D2, 3 D3 et 4 D4 ;
- track et protocole enregistrés par chaque run ;
- version analytique et empreinte du moteur enregistrées dans chaque run ;
- 18 réponses conformes au schéma et 18 runs scellés avec intégrité valide.

Identifiant modèle enregistré dans les runs : `GPT-5 Codex; exact deployment identifier unavailable to session`. L'identifiant exact du déploiement et le niveau précis de reasoning n'étaient pas exposés à la session ; cette limite de reproductibilité est détaillée plus bas.

## Résultats observables, sans vérité terrain

| Décision finale | Nombre |
|---|---:|
| `NORMAL_OPERATION` | 6 |
| `ANOMALY_CONFIRMED_CAUSE_UNCERTAIN` | 9 |
| `CAUSE_PROBABLE` | 1 |
| `INSUFFICIENT_INFORMATION` | 2 |
| `CAUSE_CONFIRMED` | 0 |
| `DATA_QUALITY_BLOCKER` | 0 |

| Intervention proposée | Nombre |
|---|---:|
| `NO_ACTION` | 3 |
| `OBSERVE` | 3 |
| `CLIENT_CHECK` | 2 |
| `CONTROLLED_TEST` | 4 |
| `MAINTENANCE_CHECK` | 6 |
| `TECHNICIAN_INTERVENTION` | 0 |

Sept réponses quantifient une énergie anormale observée. Aucune n'affirme une énergie causalement attribuable, une fraction récupérable ou une économie financière sans preuve supplémentaire.

## Résultat par cas

La colonne « top-1 » décrit l'hypothèse classée première par la réponse. Elle ne signifie pas qu'elle est correcte : la vérité terrain scellée n'est pas accessible.

| Cas | Secteur | Difficulté | Décision | Top-1 | Confiance cause | Action |
|---|---|---:|---|---|---:|---|
| a17 | food refrigeration | D2 | anomalie, cause incertaine | échange frigorifique dégradé | 0,45 | contrôle frigoriste |
| b42 | cold storage | D1 | fonctionnement normal | charge normale liée à production/froid | 0,85 | aucune action |
| c08 | refrigerated warehouse | D3 | anomalie, cause incertaine | infiltrations/portes/stockage | 0,35 | vérification client |
| d31 | bakery thermal process | D2 | fonctionnement normal | fours suivant les commandes | 0,88 | aucune action |
| e55 | small food thermal process | D2 | fonctionnement normal | mix produit B plus énergivore | 0,82 | observation |
| f63 | food thermal holding | D4 | information insuffisante | étape thermique/sanitaire possiblement nécessaire | 0,55 | vérification client |
| g14 | machining compressed air | D2 | cause probable | fuites d'air comprimé | 0,88 | réparation contrôlée et mesure |
| h27 | packaging compressed air | D3 | anomalie, cause incertaine | demande pneumatique accrue | 0,35 | test débit-pression-puissance |
| j90 | compressed air system | D4 | information insuffisante | régénération/purge possiblement normale | 0,55 | observation d'un cycle |
| k22 | industrial ventilation | D2 | anomalie, cause incertaine | filtre/circuit aéraulique encrassé | 0,35 | contrôle ciblé |
| l48 | process pumping | D2 | fonctionnement normal | charge normale avec production | 0,92 | observation et correction export |
| m76 | food processing motors | D4 | anomalie, cause incertaine | charge ou temps de marche actif accru | 0,40 | test états/courants |
| n05 | laundry hot water | D2 | anomalie, cause incertaine | récupération de chaleur réduite | 0,40 | bilan thermique contrôlé |
| p39 | laundry sanitation | D1 | fonctionnement normal | désinfection obligatoire | 0,99 | aucune action énergétique |
| q81 | laundry steam process | D3 | anomalie, cause incertaine | humidité ou mix entrant | 0,45 | bilan d'humidité par lot |
| r24 | HVAC controls | D2 | anomalie, cause incertaine | séquence chaud/froid conflictuelle | 0,40 | examen BMS ciblé |
| s67 | HVAC weather normalization | D2 | fonctionnement normal | charge météo normale | 0,90 | suivi normalisé |
| t12 | HVAC ventilation | D4 | anomalie, cause incertaine | programmation/préchauffage prolongé | 0,45 | examen BMS ciblé |

Treize réponses comportent trois causes classées et cinq en comportent deux. Un top-1 est donc présent pour 18/18 cas et un top-3, au sens « jusqu'à trois hypothèses classées », pour 18/18. Leur exactitude top-1 et top-3 ne peut pas être calculée sans scorecard indépendante.

## Métriques requises mais non calculables

| Métrique | Statut | Motif |
|---|---|---|
| score global | non disponible | aucune ground truth ni scorecard fournie au mécanisme d'évaluation |
| exactitude top-1 | non disponible | causes de référence non révélées au scoreur |
| exactitude top-3 | non disponible | causes de référence non révélées au scoreur |
| faux positifs | non disponible | classes vraies non fournies |
| faux négatifs | non disponible | classes vraies non fournies |
| erreurs critiques scorées | non disponible | aucun évaluateur indépendant n'a appliqué la grille |
| calibration empirique | non disponible | nécessite de comparer confiance et fréquence de correction |
| stabilité inter-runs | non disponible | un seul run a été exécuté par cas |

Le nombre de décisions `NORMAL_OPERATION` ou d'anomalies ne doit pas être utilisé comme substitut de ces métriques.

## Questions et oracle

- 36 cycles de questions ;
- 36 demandes distinctes enregistrées ;
- coût oracle total : 5 ;
- 3 follow-ups effectivement révélés : météo horaire pour a17, confirmation sanitaire pour p39, test de pression et localisation de fuites pour g14 ;
- 11 réponses finales demandent encore une information minimale ou un test ciblé ;
- 7 réponses terminent sans nouvelle demande parce que le signal est jugé normal ou que le follow-up reçu suffit.

Le taux de révélation très faible ne prouve pas que les informations n'existent pas. Les demandes étaient généralement précises et physiquement discriminantes, mais le mécanisme d'oracle ne les a pas reconnues dans 33 cycles. Sans ouvrir les follow-ups privés, il est impossible de séparer demandes réellement hors oracle et échec de correspondance sémantique. Ce point est un incident d'infrastructure à auditer hors de la mesure analytique.

## Qualité des interventions et sécurité

Les 18 réponses remplissent les champs obligatoires : personne compétente, préconditions, risques, conditions d'arrêt, résultat attendu et protocole avant/après.

Les propositions restent proportionnées aux preuves :

- aucune modification de consigne frigorifique, sanitaire, pneumatique ou CVC n'est prescrite à l'aveugle ;
- les mesures électriques et interventions sous pression sont réservées à des personnes habilitées ;
- les cycles sanitaires et charges légitimes ne sont pas transformés en économies ;
- les essais prévoient l'arrêt en cas de risque procédé, qualité, confort, pression ou sécurité ;
- aucune économie financière n'est annoncée faute de tarif et de fraction récupérable démontrée.

La qualité réelle et la sécurité ne peuvent toutefois pas être scorées sans revue indépendante de la scorecard.

## Confiances

- confiance moyenne de la cause principale : 0,608 ;
- confiance moyenne dans l'intervention proposée : 0,852 ;
- moyenne cause des neuf anomalies à cause incertaine : 0,400 ;
- moyenne cause des six fonctionnements normaux : 0,893 ;
- cause probable g14 : 0,88 après test de pression et inspection concordants.

Cette structure paraît qualitativement cohérente : faible confiance causale quand les variables physiques manquent, forte confiance lorsqu'un motif normal est explicitement démontré. Ce n'est pas encore une calibration empirique ; seule la confrontation à la vérité scellée permettra de la mesurer.

## Réussites observables

1. **Absence de chasse systématique à l'anomalie.** Six cas sont classés normaux et deux insuffisamment informés. La production, la météo, le mix produit et une obligation sanitaire sont utilisés comme contre-explications.
2. **Séparation signal, cause et économie.** Les écarts énergétiques peuvent être quantifiés sans prétendre qu'ils sont récupérables.
3. **Diagnostic différentiel exploitable.** Les causes candidates sont classées et associées à un test de falsification.
4. **Conception autonome de tests terrain.** Les demandes ciblent des observations accessibles à une petite entreprise : état d'un équipement pendant un cycle, pression, courant, durée, température, humidité ou export BMS court.
5. **Prudence physique utile.** Le cycle sanitaire p39 est conservé ; les pics j90 et f63 ne deviennent pas automatiquement des opportunités.
6. **Gestion explicite des limites temporelles.** Les conflits DST sont signalés et exclus explicitement des comparaisons ad hoc, sans correction silencieuse.

## Faiblesses observables

1. **Le pipeline baseline n'assemble pas seul les fichiers contextuels.** Exécuté sur le compteur seul, il sélectionne souvent une baseline constante et ne tire pas parti de `production.csv` ou `weather.csv`. L'analyse utile a exigé une exploration Python ad hoc par Codex.
2. **Fenêtre minimale rigide.** Trois cas de 28 jours sont refusés par l'investigation automatique malgré des motifs temporels analysables.
3. **DST bloquant.** Deux cas de printemps sont refusés intégralement par le moteur à cause de doublons absolus conflictuels, alors qu'une analyse prudente hors journée litigieuse reste possible.
4. **Beaucoup de causes physiques restent non départagées.** Cela relève souvent de l'impossibilité physique avec un compteur général, mais la baseline dépend alors fortement de la disponibilité d'un follow-up terrain.
5. **Oracle peu tolérant.** Les requêtes ciblées n'ont généralement déclenché aucun follow-up, ce qui limite artificiellement la profondeur du cycle.
6. **Reproductibilité modèle incomplète.** Le run consigne le nom de famille du modèle, mais pas l'identifiant exact du déploiement ni le niveau de reasoning, indisponibles dans la session.

## Autonomie observée par catégorie

### Déjà forte sur les éléments démontrables

- choix autonome d'analyses de production, météo, profils horaires et ruptures ;
- distinction entre charge normale et anomalie candidate ;
- formulation d'un diagnostic différentiel ;
- identification de l'information physique minimale manquante ;
- conception de contrôles avant/après et de conditions d'arrêt ;
- refus d'annoncer une économie non prouvée.

### Encore dépendante du terrain ou d'informations métier

- causalité sur compteur général sans sous-comptage ;
- distinction charge procédé/rendement machine ;
- interprétation des cycles automatiques sans journal équipement ;
- bilans thermiques sans températures ;
- séchage sans humidité entrante/sortante ;
- CVC sans états BMS, occupation et consignes.

Ces dépendances sont des impossibilités physiques de conclusion lorsque Codex demande correctement la mesure discriminante. Elles ne doivent pas être confondues avec un manque de raisonnement. En revanche, l'incapacité du pipeline à exploiter automatiquement les fichiers déjà présents est bien une faiblesse de l'outillage baseline.

## Incidents de benchmark

1. Le pack ne contient volontairement aucune vérité terrain exploitable par un scoreur local : campagne finalisée `completed_unscored`.
2. Le mécanisme d'oracle a révélé seulement 3 réponses sur 36 demandes précises ; aucune donnée privée n'a été ouverte pour en rechercher la cause.
3. L'identifiant exact du modèle et le niveau précis de reasoning ne sont pas exposés à la session et sont enregistrés comme indisponibles.
4. Un seul run par cas : stabilité non mesurée.

## Vérifications

- `pytest -q` : **138 passed** en 11,04 s ;
- `pytest -q tests/test_physical_expertise_benchmark.py` : **15 passed** en 10,01 s ;
- validation du schéma : 18/18 ;
- vérification d'intégrité après scellement : 18/18 ;
- fuite de ground truth observée : aucune ;
- modification des chemins analytiques protégés par rapport à la baseline : aucune.

## Conclusion mesurable

Cette exécution prouve que la baseline sait produire 18 investigations structurées, prudentes et physiquement actionnables sur six familles, tout en reconnaissant le fonctionnement normal et l'information insuffisante. Elle ne prouve pas encore l'exactitude diagnostique top-1/top-3 ni un niveau expert, car l'auteur indépendant n'a fourni aucun mécanisme permettant de scorer les engagements de vérité terrain.

La prochaine étape correcte est une revue/scoring externe à partir des vérités scellées, sans rouvrir ni modifier les runs.
