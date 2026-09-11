# Mission client — autorités et procédure nominale

Cette page complète le workflow existant, sans remplacer l’investigation, l’Evidence Plane,
Operational Economics ou la Value Map. Le code protège les références et les calculs ; l’agent
choisit les hypothèses, les décisions et la composition éditoriale. La revue humaine reste réelle.

## Avant les données industrielles

Créer un dossier vide. Aucun premier dépôt réel n’est admis sans politique contractuelle revue.

```sh
python intake_client_case.py create dossier --root client_cases
python manage_investigation.py status client_cases/dossier
```

Un workspace standard peut aussi être créé avec `create_workspace.py`, sans `--incoming`.
La contractualisation n’est pas un deuxième lifecycle : `status` expose le gate contractuel à côté
du gate privacy, et les entrées existantes vérifient les autorisations.

Conserver l’accord applicable dans `contracts/`. Codex lit sémantiquement le contrat et extrait
seulement les règles opérationnelles dans un packet : `policy`, `semantic_extraction` et, si elle
est réellement fournie, `human_review`. Utiliser `contract_policy_template()` ou
`contracts/CONTRACT_POLICY_TEMPLATE.json`. Les permissions sont true / false / null ; null ne vaut
ni consentement ni refus factuel. Les clauses ambiguës imposent HUMAN_LEGAL_REVIEW_REQUIRED.

La policy porte accord actif, signature si pertinente, référence et hash des sources, dates avec
fuseau, autorisation de traitement, confidentialité, rétention canonique et échéance, permissions
séparées de R&D/benchmark/portfolio/citation, codes des contraintes externes, ambiguïtés et fichiers
explicitement conservables. Les contraintes externes inconnues restent bloquantes. Le contrat brut
n’est ni joint au rapport ni recopié dans les analyses. Aucune qualification juridique n’est calculée.

L’humain doit approuver la policy exacte : `approved`, `policy_sha256` (calculé par
`contract_policy_digest`), `reviewer_role`, `reviewed_at_utc`,
`external_processing_constraints_satisfied`. `review_status=REVIEWED` seul ne suffit pas. Ne jamais
fabriquer cette approbation. Les snapshots d’autorisation sont conservés sous `contracts/authorizations/`
pour tracer l’autorisation applicable au traitement, puis soumis à la purge.

```sh
python manage_investigation.py contract-record client_cases/dossier contracts_packet.json
python manage_investigation.py retention-configure client_cases/dossier retention_policy.json
python manage_investigation.py stage-incoming client_cases/dossier /chemin/depot
```

Le packet et toute copie de travail du contrat restent dans le dossier confidentiel, jamais dans Git.
La date de purge et les fichiers à retenir doivent correspondre à la policy revue. Configurer
`mission_closed=false` tant que la mission est ouverte. Avant l’accord, seuls format, colonnes
anonymes, unités, fréquence et périmètre général sans lignes réelles sont recevables.

Le staging lit la policy, puis copie les données sans analyse. Son reçu référence la policy.
La privacy review reste Codex-first ; son manifest conserve la référence à l’autorisation historique.
Les autres couches consomment ces projections et ne réinterprètent pas le contrat.

## Analyse et économie : capacités conservées

Suivre `CLIENT_WORKFLOW.md` : privacy, intake depuis sanitized, exploration, hypothèses, tests,
falsification, demandes minimales, reprise, findings et revue contradictoire. WAITING_FOR_REQUIRED_INFORMATION
impose toujours STOP complet. Une déclaration client n’est ni une ancre terrain ni une causalité.

Les valeurs viennent d’Operational Economics et de la Value Map. Aucun calcul de ROI global n’est
ajouté au rendu. Ne jamais confondre exposition, potentiel, estimation contrefactuelle et réalisation.
Le chemin complet de rapport Goal A/B utilise le layout `client_cases/` ; les workspaces standard
conservent leur pipeline analytique et doivent être adaptés explicitement au contrat Goal A/B avant
ce rapport économique. Ne pas créer de second état économique dans processed pour contourner cela.

## Composition du rapport par Codex

Lire `REPORT_DESIGN_SYSTEM.md`. L’ancien `CLIENT_REPORT_MODEL` reste la représentation validée des
claims, actions et chiffres. `REPORT_DESIGN_MODEL` est uniquement un plan de composition : pages,
blocs, références de contenu, coordonnées, taille de police et emphase. Codex conçoit ce plan ; aucun
algorithme ne choisit les findings prioritaires ou la mise en page à sa place.

```sh
python deliver_client_report.py client_cases/dossier narrative.json --design REPORT_DESIGN_MODEL.json
```

Le résultat nominal est `outputs/client_report/client_report.pdf`. Les API de l’ancien renderer
restent disponibles pour les fixtures historiques ; leur composition automatique n’est plus le
chemin réel. `report.md` reste une synthèse textuelle/audit, sans déterminer les pages du PDF.

Le rendu est reproductible et utilise le sérialiseur PDF local existant. Il ne nécessite ni navigateur,
ni téléchargement de polices, ni service réseau. L’agent peut recomposer les pages autant que nécessaire.
Les références sont résolues à nouveau ; un nombre libre, une source inconnue, une économie renforcée,
un graphique altéré ou un bloc qui déborde sont refusés.

Inspecter toutes les pages avec `pdftoppm`, puis consigner la vraie revue via `record_visual_review`.
Les contrôles couvrent coupures, débordements, titres, légendes, graphiques, densité, espaces, contraste,
accents/unités et qualité professionnelle. La génération ne remplit pas ces attestations automatiquement.

L’approbation humaine doit porter sur `report_semantic_sha256`, en plus des conditions précédentes
et de `value_map_sha256` lorsque requis. Ce hash inclut les claims sélectionnés, leur ordre, leurs
sources et décisions ; il exclut coordonnées et taille de police. Une modification substantielle
exige une nouvelle approbation. Un changement esthétique exige une nouvelle inspection visuelle,
mais conserve l’approbation sémantique si les faits et leur sélection n’ont pas changé.

```sh
python manage_investigation.py check client_cases/dossier
python manage_investigation.py status client_cases/dossier
```

Le gate exige contrat actif, traitement historiquement autorisé, privacy, état finalisable,
questions résolues, investigation/revue, provenance, économie et carte valides, approbation humaine,
inspection visuelle et PDF reproductible depuis le plan autorisé. Un reçu édité ne suffit pas.
Après succès seulement, le dossier et le reçu deviennent DELIVERABLE. Sans approbation humaine,
présenter les artefacts à relire et arrêter la session, sans les annoncer comme livrés au client.

## Feedback, réalisation et post-mortem

Enregistrer feedback et vérifications comme preuves Goal B sourcées. Les résultats post-action
utilisent le contrat Value Map existant : action, dates, comparaison, confondants, mesures référencées,
et entrée distincte de l’estimation initiale. Une estimation passée reste intacte.

`pilot_learning.persist_pilot_learning_review(case, assessment)` étend la revue existante avec
`post_mortem`. Les vingt sections, trois questions obligatoires, contribution et verdict sont
fournis par Codex. Chaque énoncé est FAIT_OBSERVE, RESULTAT_CALCULE, RETOUR_CLIENT, INFERENCE,
HYPOTHESE, INTERPRETATION_POST_MORTEM ou INCONNU ; les chiffres référencent une métrique existante.
Python ne choisit ni verdict ni généralisation. Les cinq verdicts vont de RENFORCE_FORTEMENT à
AFFAIBLIT_FORTEMENT ; NEUTRE n’équivaut pas à une preuve générale.

Chaque post-mortem final contient aussi une **comparaison contrefactuelle de simplicité**. Elle
compare explicitement Againward à « raw data + Python + bon prompt » et exige des constats sourcés
sur la valeur des outils, les frictions du workflow, les calculs qui relèvent mieux d’un Python
simple, les briques à supprimer/fusionner/rendre optionnelles, les capacités réellement uniques,
les contournements de l’agent et le design minimal recommandé pour un dossier semblable.

Les dimensions sont séparées : découverte et investigation, fiabilité des calculs, faux positifs et
abstentions, traçabilité et reproductibilité, temps et complexité, puis valeur finale pour le client.
Chaque axe et chaque dimension reçoivent un résultat fermé (`AGAINWARD_ADVANTAGE`,
`RAW_PLUS_PYTHON_ADVANTAGE`, `ROUGHLY_EQUIVALENT` ou `INCONCLUSIVE`) et au moins une preuve issue des sources, findings,
artefacts hachés ou métriques existantes. Le verdict global est obligatoirement l’un de
`AGAINWARD_CLEARLY_BETTER`, `AGAINWARD_BETTER_ON_RELIABILITY`, `ROUGHLY_EQUIVALENT`,
`RAW_PLUS_PYTHON_LIKELY_BETTER` ou `INCONCLUSIVE`. Une formulation libre comme « Againward semble
meilleur » est rejetée. Le constat peut conclure qu’une brique est inutile ou contre-productive si
les artefacts du pilote le justifient.

`PILOT_LEARNING_REVIEW.json` et `.md` sont TEMPORARY_CONFIDENTIAL dans l’investigation. Les sources
et chemins locaux ne doivent pas sortir avec des métriques. Le système ne conserve pas ce Markdown
simplement parce qu’un modèle l’aurait « anonymisé ».

## Conservation contrôlée, clôture et purge

`create_retention_candidate(case, review, purpose=...)` produit uniquement
`retained_derived/pilot_learning.csv` depuis une whitelist. Aucun nom, source, actif, recette, lot,
timestamp, verbatim ou chiffre industriel précis n’est exporté ; les métriques numériques sont
regroupées en larges plages. Les finalités disponibles sont INTERNAL_RND et BENCHMARKING, seulement
si le contrat autorise explicitement la conservation et la finalité correspondante.

`approve_retention_candidate` exige une revue humaine réelle liée aux bytes et à la policy :
identité supprimée, combinaisons rares/volumes/timestamps généralisés, absence de données personnelles
et dimensions interdites, risque LOW, auteur/rôle/date. La revue n’est jamais calculée automatiquement.
La purge réexamine whitelist, finalité, contrat et hashes. Un CSV précis ou un Markdown libre échoue.
L’export de métriques existant reste utilisable mais exige aussi une autorisation contractuelle R&D
pour un dossier réel ; il ne constitue pas, à lui seul, un artefact RETENTION_APPROVED.

```sh
python manage_investigation.py mission-close client_cases/dossier
python manage_investigation.py purge client_cases/dossier
```

La purge ne démarre qu’à l’échéance et après clôture. Elle retire sources, analyses, preuves,
post-mortem complet, caches, fichiers de travail et contrats non explicitement retenus. Les
contrats/factures ne bénéficient plus d’une exemption de rétention implicite. Les seules sorties
retenables sont les PDF explicitement permis ; les dérivés passent par la whitelist.
Des tombstones minimaux bloquent toute réouverture, avec un reçu sans contenu analytique.
Une suppression partielle reste un échec et un blocage, pas une purge réussie.

## Limites de garantie

Ces protections couvrent les entrées et artefacts supportés. Elles ne peuvent empêcher un opérateur
ayant accès au système de fichiers de copier des données ailleurs ou de mentir dans une attestation.
Les sauvegardes externes et l’effacement physique des blocs de stockage sont hors périmètre. Les
revues humaines doivent vérifier le sens des clauses, des extractions et des claims ; aucune
conformité juridique ni anonymisation parfaite n’est annoncée. Un rapport synthétique valide les
contrats et la présentation, jamais la valeur commerciale ou la performance chez un vrai client.
