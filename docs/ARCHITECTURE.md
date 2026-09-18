# Architecture AGAINWARD : noyau, preuves et domaines

## Frontières effectives

| Couche | Responsabilité | Dépendances métier |
|---|---|---|
| `againward/core` | Lifecycle, requests/VOI, privacy, contrats d'autorisation, workspace, transactions, orchestration, review et gate de livraison | Aucune importation Energy/Rental |
| `againward/evidence` | Tables typées, empreintes, provenance, requêtes bornées, sessions, handles, comparaisons | Aucune unité ou classe métier obligatoire |
| `againward/domains/energy` | DomainPack, adaptateur Evidence v1, préparation quantitative, politique physique et économique | Moteur existant `energy_mvp`, outils Energy éprouvés |
| `againward/domains/rental` | Modèle commercial, extraction canonique, calendrier, ledgers, rapprochement, niveaux de preuve, reprise et rapport | Core et Evidence |
| `againward/domains/rental/profiles` | Suggestions de catégories et questions métier | Aucun changement de prix, de preuve ou de lifecycle |
| `againward/entrypoints.py` | Sélection explicite des domaines et profils | Seul point de composition des implémentations |
| `againward/compat` | Schémas/politiques historiques figés pour les API existantes | Données de compatibilité, pas d'import du moteur Energy |

Le choix évite de déplacer mécaniquement tout le moteur énergétique. Les calculs
existants restent dans `energy_mvp`, mais **la préparation d'une investigation passe
réellement par `EnergyDomainPack` et l'orchestrateur partagé**. `analyze.py` conserve
son rôle de pipeline quantitatif Energy ; il n'est pas l'orchestrateur d'investigation.

Les anciens modules lifecycle/privacy/workspace/evidence sont des aliases ou des
adaptateurs minces, pas une seconde implémentation. Les aliases de modules conservent
les mêmes verrous et points de monkeypatch. Ils seront retirables après migration
des consommateurs externes, sans date de suppression arbitraire. Les wrappers
Energy conservent les signatures, les schémas v1 et les comportements caractérisés.

## Contrat DomainPack

`core/domain.py` définit un `Protocol` et une registry explicite. Un pack fournit
son intake, sa préparation quantitative (`DomainPreparation`), sa carte de preuves,
son brief analyste, ses contrôles de review, sa politique de préservation privacy et
sa politique de livraison. La préparation retourne des artefacts et un dataset ;
le noyau les persiste et crée le lifecycle et les templates communs.

Le noyau ne choisit pas de baseline, ne connaît pas de retour de matériel et ne
transforme pas les signaux en décisions. Il ne devine pas le domaine. Un conflit
entre le workspace et le domaine demandé est refusé. Un dossier historique sans
champ `domain` conserve son interprétation Energy.

Pour ajouter un domaine : implémenter ces méthodes utiles, fournir ses tests métier,
son adaptateur de records et ses politiques, puis l'enregistrer dans le point de
composition. Aucun changement au noyau n'est nécessaire. Un pack documentaire de
test vérifie ce découplage sans données Energy ni Rental.

## Evidence Plane

`EvidenceDataset.from_records()` accepte des records typés et une provenance
`sources` + `rows` : identifiant source, SHA-256, emplacement et champ facultatif.
Le `source_row` est un ordinal du snapshot, pas nécessairement une ligne physique.
Le schéma `againward-evidence-dataset-v2` lie par hash l'identité, les types, les
valeurs, les sources et les métadonnées. Les floats non finis et références invalides
sont refusés. Les montants Rental sont aussi exposés en unités monétaires mineures
entières, sans conversion de devises.

Les snapshots Energy v1 restent lisibles par l'infrastructure neutre. Seul leur
constructeur historique dépend de `LoadedData`; l'adaptateur Energy reproduit les
octets de la fixture initiale. Requêtes, budget, replay, handles et validation des
réponses matérialisées sont communs. Les sorties restent décisionnellement neutres.

Une révision Rental archive le snapshot, la session et les reviews précédents. Elle
crée une session liée aux nouvelles sources avec **le budget restant**, jamais un
budget gratuit. Les réponses antérieures restent conservées, les anciens handles
ne justifient pas les nouvelles conclusions. Les ID de requêtes doivent être nouveaux.

## Review, confidentialité et livraison

Core valide la méthode et les contrôles injectés. Energy conserve les exigences
de causalité physique, baseline, annualisation et économie. Rental exige contrat,
chronologie, monnaie, récupérabilité et absence de double comptage. Les politiques
ne sont pas choisies par un argument libre dans un dossier déjà identifié.

La privacy review sémantique Codex précède le parsing des sources réelles. Le
post-check Python reçoit une politique métier de préservation : dates, unités,
relations ou montants ne peuvent être effacés avec les données personnelles. Les
JSON Rental conservent strictement leurs valeurs commerciales et leur structure.
Les sources et les sorties restent dans le même workspace ; les liens symboliques
et chemins sortants sont refusés. Il n'y a ni serveur ni nouvelle API externe.
Codex/OpenAI traite toutefois le contenu selon sa configuration, ce qui n'est pas
un traitement exclusivement local.

La livraison exige le lifecycle finalisable, les permissions contractuelles,
les preuves matérialisées, les conclusions revues et une approbation humaine.
Rental recalcule depuis les sources encore disponibles et vérifie les décisions
contre les montants déterministes. L'approbation humaine lie les hashes du rapport,
du dossier de preuves et des reviews ; un changement invalide la livraison.

## Invariants testés

- Core n'importe aucun domaine, même transitivement pour ses primitives.
- Evidence peut lire v1 et v2 sans importer Energy.
- Construction enrichit le contexte sans modifier les ledgers ni le dataset.
- Les tests de caractérisation figent les rapports Energy et le snapshot v1.
- WAIT bloque l'analyse ; les réponses déclenchent RESUME et une nouvelle review.
- L1/L2 ne deviennent pas L3 par simple soustraction de deux montants.
- Plusieurs familles sur le même groupe ne multiplient pas son montant.
- Les échecs de preuve restent des abstentions ou des limites explicites.

Le détail des étapes et résultats de migration figure dans
[DOMAIN_KERNEL_MIGRATION.md](DOMAIN_KERNEL_MIGRATION.md).
