# Audit final — fermeture de la mission client

Spécification : `AGAINWARD_FINAL_CLIENT_MISSION_GOAL.md`, lue intégralement.
Référence avant modification : `82dcb54`. Implémentation : `c514a72`, puis
`e489292` pour la révocation d’un reçu de livraison périmé.
La preuve détaillée par section A–AI et par test AE est dans
[REQUIREMENTS_TRACEABILITY.md](REQUIREMENTS_TRACEABILITY.md).

## 1. Gaps identifiés avant modification

- La règle commerciale « accord avant données réelles » ne bloquait pas le staging.
- Aucun contrat technique canonique ne séparait clairement traitement, conservation
  et finalités secondaires, avec UNKNOWN et ambiguïtés bloquantes.
- Le renderer imposait l’essentiel de la composition ; le modèle de claims existant
  était utile mais ne donnait pas à l’agent la maîtrise des pages.
- La revue humaine n’était pas liée à tout le contenu sémantique du PDF ; sa simple
  existence ne prouvait ni les octets livrés ni leur inspection visuelle.
- Le learning existant manquait du post-mortem scientifique complet et d’une
  projection de rétention à whitelist liée aux droits contractuels.
- Les contrats et factures survivaient implicitement à la purge, et certains
  manifests pouvaient conserver des informations plus riches que le reçu minimal.

Ces gaps et les autorités à conserver sont consignés dans l’audit préalable.

## 2. Capacités existantes conservées

Privacy Codex-first, lineage, sanitized, requests et STOP, lifecycle et gate de
livraison existants ; Evidence Plane et frontières d’attribution ; findings et
review contradictoire ; Operational Economics, tarifs, provenance numérique,
LOW/BASE/HIGH et décisions agentiques ; Value Map non additive, contrefactuels et
résultats post-action distincts ; métriques pilote et purge existante.
Les détecteurs et leur logique ne sont pas modifiés.

## 3. Ajouts réels

- `energy_mvp/contract_policy.py` : contrat fermé, extraction, review liée au digest,
  sources vérifiées, période d’application, permissions distinctes, snapshots
  d’autorisation historique et refus des opérations inconnues.
- Entrées CLI `contract-record`, `stage-incoming`, `mission-close`, création d’un
  dossier vide et template de policy ; status expose le gate contractuel.
- `report_design.py` : catalogue de références autorisées, composition libre par
  blocs, contrôle de marges/débordement, hash sémantique, PDF local reproductible,
  revue visuelle liée aux bytes et vérification de la reproduction à la livraison.
- Extension de `pilot_learning.py` : vingt sections, questions obligatoires,
  typologie des énoncés, verdict sourcé, statut confidentiel, projection CSV fermée
  en plages et approbation humaine de rétention liée aux bytes et à la finalité.
- Tests, quatre compositions/PDF synthétiques inspectés, documentation et skill
  mis à jour pour le chemin nominal réel.

## 4. Refactors effectués

Le sérialiseur PDF existant est partagé par les deux chemins de rendu. Le modèle
client continue à porter les claims ; le nouveau plan ne porte que la composition.
Les courbes conservent désormais les extrema lors de la réduction au pixel et
exposent méthode, source, finding, unités et période reproductibles.

Les gates existants appellent la policy et le validateur du rapport. Une retouche
esthétique exige une nouvelle inspection visuelle ; une modification substantielle
exige une nouvelle approbation humaine. La dernière attaque de test a montré qu’un
modèle modifié directement pouvait laisser l’ancien reçu marqué approuvé, bien
que le gate refusât la livraison. Le test a échoué avant correction ; `e489292`
révoque maintenant aussi ce reçu et conserve l’échec du gate.

La purge utilise toujours son parcours existant, avec rétention contractuelle
explicite, dérivés whitelistés et tombstones minimaux. Aucun nouveau système de
suppression ou de lifecycle n’a été introduit.

## 5. Absence d’architecture parallèle

Une seule autorité pour chaque objet : `client_lifecycle` pour l’état,
`privacy_manifest` pour la privacy, `retention_policy` pour la clôture/purge,
`economic_decision_state` et Value Map pour les valeurs, findings pour les preuves,
`CLIENT_REPORT_MODEL` pour les claims et `REPORT_DESIGN_MODEL` pour leur composition.
La policy est une précondition technique, pas un nouvel automate. Le post-mortem
étend le module pilote existant. Python ne choisit ni les décisions économiques,
ni les hypothèses éliminées, ni le verdict du pilote, ni l’ordre des pages.

## 6. Détecteurs, benchmarks et fichiers devenus secondaires

Aucun détecteur, aucune vérité terrain ni aucun seuil de scoring n’a changé.
Le seul benchmark modifié est `benchmarks/privacy_gate/benchmark.py` : il fournit
un accord **synthétique** à sa fixture REAL_CLIENT, nouvelle précondition obligatoire.
Ses tailles, lignes générées, boucle de mesure et assertions sont conservées.
Sans cette adaptation, il testerait seulement l’absence d’accord, pas le coût du
post-check privacy. Les résultats historiques suivis ne sont pas écrasés.

L’ancien renderer reste nécessaire à des fixtures et régressions historiques :
il n’est donc pas supprimé arbitrairement. Il n’est plus autoritatif pour une
livraison réelle, qui exige `--design` et le nouveau reçu. Les instructions
actives contradictoires ont été actualisées. Aucune donnée locale de prospection,
aucun stash ni fichier non suivi préexistant n’est ajouté ou supprimé.

## 7. Tests ciblés

Les résultats et commandes exacts sont dans [VALIDATION_RESULTS.json](VALIDATION_RESULTS.json).
Les nouveaux tests couvrent absence/UNKNOWN/ambiguïté d’autorisation, période et
clôture, références et nombres interdits, reproduction du graphique/PDF,
esthétique vs sémantique, reçu périmé, revue scientifique, droits de R&D,
réidentification et purge réelle de la revue complète.
La validation structurelle du skill réussit. Les tests workflow imposés par ce
skill et son benchmark de sélection des demandes ont été exécutés.

## 8. Suite globale

La suite avant modification comportait 491 tests réussis, prospection incluse.
La suite globale après modification, y compris la correction finale du reçu,
réussit : **523 tests en 107,48 secondes**, prospection incluse. Le résultat
est consigné dans VALIDATION_RESULTS.json. Les suites économiques, Value Map,
pilote, privacy, lifecycle, Evidence Plane et client delivery y sont incluses.
Les logs complets de validation sont conservés dans ce dossier d’audit.

## 9. PDF synthétiques réellement générés

[Exemples et manifeste](../../examples/final_client_mission_reports/README.md) :
clear_energy, false_lead, multiple_priorities, useful_abstention.
Les quatre PDF contiennent respectivement trois, deux, cinq et deux pages.
Ils ne portent aucune approbation humaine fictive de livraison réelle. Le
générateur réutilise les contrats de fixtures, sans modifier un benchmark pour
faire croire à une meilleure détection.

## 10. Revue visuelle

[VISUAL_REVIEW.md](VISUAL_REVIEW.md) détaille génération, rasterisation, inspection,
corrections et réponse à la question de qualité AG. Les attestations sont liées
aux SHA exacts des quatre PDF. Les images inchangées ont été comparées octet pour
octet aux pages déjà inspectées ; toutes les pages modifiées ont été revues.
Le verdict visuel est favorable pour ces compositions sobres et lisibles.

## 11. Limitations restantes

- L’agent et l’humain restent responsables de la vérité sémantique du récit : un
  validateur de références ne peut pas démontrer toute proposition en français.
  Il bloque les incohérences structurées ; il ne transforme pas le texte en preuve.
- Le code ne certifie ni conformité juridique, ni anonymisation parfaite. Les
  droits, contraintes de traitement externe et attestations doivent être réels.
- Un opérateur ayant accès au disque peut contourner les entrées supportées ou
  copier ailleurs ; backups externes et effacement physique du stockage ne sont
  pas couverts par la purge du workspace.
- La rétention whitelistée est volontairement très pauvre et en larges plages.
  Une combinaison de métriques peut encore être singulière ; revue humaine LOW
  et droit contractuel restent obligatoires. Aucun Markdown libre n’est conservé.
- Le chemin complet de rapport économique utilise les contrats Goal A/B du layout
  `client_cases`. Un workspace standard incomplet ne peut pas être livré en
  contournant ces contrats ; il faut l’adapter explicitement avant restitution.
- Le moteur graphique actuel offre les visualisations locales existantes et la
  composition libre. Un nouveau type analytique exige un adaptateur déterministe
  validé ; aucune image arbitraire n’est acceptée comme preuve.
- Les exemples de restitution ont une matière technique synthétique courte. Ils
  ne prouvent ni la qualité d’une investigation réelle, ni un taux d’insights
  utiles, ni des économies récupérées, ni la valeur commerciale d’AGAINWARD.
- Chaque mission réelle doit encore obtenir son accord applicable, sa revue
  privacy, ses preuves, ses approbations humaines et sa propre inspection PDF.
  La présente validation ne remplit aucune de ces conditions pour un futur client.

## Verdict

**READY_FOR_SUPERVISED_REAL_PILOT**, sur le chemin nominal `client_cases` et sous
les gates décrits ci-dessus. L’architecture sait refuser l’entrée non autorisée,
préserver les autorités analytiques et économiques, composer un PDF sourcé et
inspecté, bloquer une livraison non approuvée et purger le learning confidentiel
en ne conservant que les éléments explicitement autorisés.

Ce verdict porte sur la cohérence logicielle d’un **pilote supervisé**. Il ne
constitue ni un avis juridique, ni une autorisation de traiter un dossier absent,
ni une preuve de valeur commerciale. Les tests et exemples synthétiques ne
remplacent pas le premier pilote terrain.
