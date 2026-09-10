# Architecture privacy-by-design

## Invariant principal

Pour un dossier `REAL_CLIENT`, Codex est la première étape capable de lire et comprendre le contenu
brut. Aucun parseur métier, détecteur de colonnes, normaliseur, modèle externe supplémentaire ou
outil d’analyse énergétique ne précède cette revue. Python peut uniquement créer le workspace et
copier le dépôt dans `incoming/` sans lire son contenu.

Cette frontière est intentionnelle : Codex décide ce qui est personnel, inutile, industriellement
nécessaire ou ambigu ; Python vérifie ensuite que la décision respecte un contrat borné.

## Flux et responsabilités

```text
accord contractuel extrait et revu
  └─ stage_incoming_drop()              copie sans inspection sémantique
       └─ incoming/                     zone temporaire ignorée par Git
            └─ CODEX PRIVACY GATE       première lecture substantielle
                 ├─ PASS                copie fidèle requise
                 ├─ SANITIZED           candidat dans privacy/candidate/
                 └─ BLOCKED             purge immédiate du temporaire puis STOP
                      ↓
validate_codex_privacy_review()         post-check Python fail-closed
  ├─ scan déterministe résiduel
  ├─ comparaison de préservation
  ├─ promotion atomique vers sanitized/
  ├─ suppression incoming/candidate/review de travail
  └─ privacy/privacy_manifest.json
       ↓
PRIVACY_CLEARED
  └─ intake / calculs / investigation / attribution / rapport
       └─ revue humaine / livraison
            └─ politique de rétention / purge / PURGE_RECEIPT.json
```

Le staging conserve temporairement les noms de fichiers nécessaires au traitement, mais son reçu
ne contient ni hash ni contenu. Après `PASS`, `SANITIZED` ou `BLOCKED`, la review, le candidat et ce
reçu de staging sont supprimés lorsque cela est techniquement sûr. En `BLOCKED`, `incoming/` est
également supprimé immédiatement. Un échec ou une suppression partielle reste
`PRIVACY_BLOCKED` et le manifest indique `attempted`, `succeeded`, `partial`, les nombres supprimés
et restants, l’horodatage et des codes d’erreur sans chemin ni contenu client.
Un nouveau dépôt minimal peut ensuite être restagé explicitement : la commande recrée `incoming/`,
mais le dossier reste bloqué jusqu’à la réussite complète d’un nouveau gate.

## Contrat de revue Codex

Schéma : `indicia-codex-privacy-review-v1`. Chaque fichier reçu apparaît exactement une fois avec
un `file_id` non sémantique, une action et, le cas échéant, un candidat. Les transformations ne
contiennent que : catégorie, action, compte, attestation de préservation et code de raison.
Le hardening décrit ici est tracé par `policy_version: indicia-privacy-policy-v1.1`.

Les valeurs personnelles ne sont jamais écrites dans la review ni dans le manifest. Une relation
utile est pseudonymisée de façon stable sans table de correspondance :

```text
OPERATOR_001 → PRESS_07 → shift_nuit → timestamps
```

Pendant un unique post-check, Python maintient seulement en mémoire une correspondance injective
entre chaque identité brute normalisée et son pseudonyme. Une même identité textuelle présente
dans plusieurs fichiers doit donc recevoir le même pseudonyme, et deux identités textuelles
différentes ne peuvent partager un pseudonyme. Cette correspondance est abandonnée à la fin du
processus et n’est jamais sérialisée dans la review, le manifest ou un log. Les alias distincts
d’une même personne ne pouvant pas être établis par un contrôle déterministe restent une décision
sémantique Codex ; en cas de doute, le dossier doit être bloqué.

Les noms/types de machines, compteurs, lignes, ateliers, sites, références produits, lots et
campagnes ne sont pas assimilés à des personnes sur la seule base de leur orthographe.

## Post-check déterministe

`energy_mvp.privacy.validate_codex_privacy_review()` impose :

- attestation que Codex fut le premier lecteur sémantique ;
- couverture exacte de `incoming/`, chemins internes et absence de symlinks ;
- identifiants/codes bornés pour empêcher les valeurs libres dans l’audit ;
- recherche des colonnes personnelles explicites, emails, téléphones, credentials, clés/tokens et
  motifs RH/médicaux évidents ;
- absence de motif résiduel dans un candidat sanitized ;
- même type tabulaire, mêmes feuilles, même nombre et ordre de lignes ;
- en-têtes et valeurs industrielles/contextuelles inchangés ;
- marqueurs industriels textuels (machine, compteur, lot, cycle, timestamp, valeur/unité) conservés ;
- pseudonymes stables et injectifs dans tout le dépôt multi-fichiers, présents lorsque la relation
  est conservée ;
- absence de dérivé pré-gate dans les zones d’analyse ;
- promotion sans écrasement et suppression réussie du brut temporaire.

Les patterns génériques ne sont pas appliqués aveuglément aux colonnes explicitement industrielles
afin de préserver, par exemple, une machine appelée `Jean` ou un identifiant compteur ressemblant à
un téléphone. Cette exception dépend de la première revue sémantique Codex.

Le post-check ne fait aucune correction métier : pas d’interpolation, d’unité convertie, de
timestamp réparé, de ligne dédupliquée ou de valeur énergétique ajustée.

## Manifest et lineage

`privacy_manifest.json` enregistre version de schéma/policy, workspace, réception/validation,
statut, catégories et comptes, transformations sans valeurs, SHA-256 original et sanitized,
résultat du post-check, suppression et `approved_for_analysis`.

Le brut n’est conservé ni après clearance réussie ni après blocage lorsque sa suppression est sûre.
Le lineage repose sur les hashes et `file_id`, puis la provenance d’intake référence `sanitized/`.
Un manifest bloqué conserve aussi les catégories et codes de raison structurés ainsi que l’état
vérifié de suppression. Les erreurs durables ne reprennent ni en-tête, ni chemin, ni valeur source ;
le détail reste dans l’exception opérateur éphémère.

## Verrous d’exécution

`assert_case_privacy_cleared()` et `assert_source_approved_for_analysis()` sont appelés par les
entrées d’investigation, intake Goal A, requêtes de preuve, findings, attribution, économie,
rapport et livraison. Une source `sanitized/` doit avoir un hash présent dans le manifest.
Le booléen `approved_for_analysis` ne suffit pas seul : policy et schéma courants, statut
`PASS`/`SANITIZED`, post-check réussi et suppression originale réussie sont tous requis.

Les états sont `AWAITING_PRIVACY_REVIEW`, `PRIVACY_CLEARED`, `PRIVACY_BLOCKED`, puis `PURGED` en fin
de mission. Tout état différent de `PRIVACY_CLEARED` refuse les actions analytiques. Les dossiers
réels ou historiques placés sous les racines officielles `workspaces/` et `client_cases/` sont
reconnus même si un appel leur fournit directement un sous-dossier auparavant classé
`DIRECT_ANALYSIS_DIRECTORY`; un manifest absent ou ancien impose alors une migration explicite.
Même l’initialisation du lifecycle est refusée dans cet état, avant la création d’un artefact
analytique.
Les dossiers synthétiques gérés sont exemptés seulement par `case_kind: SYNTHETIC` et
`privacy.required: false` dans leur manifest.

## Rétention et purge

`configure_retention()` exige une date avec fuseau, une clôture explicite de mission et une liste
sûre des livrables à retenir. Les contrats et éléments de facturation restent isolés. La rétention
de dérivés vaut `false` par défaut ; si elle est autorisée, une revue séparée doit confirmer la
suppression de l’identité site, la généralisation des combinaisons d’actifs, volumes et timestamps,
et un risque de réidentification bas.

`purge_client_case()` parcourt le workspace en deny-by-default. Il efface sources, normalisés,
dérivés reconstructibles, preuves, investigations, scratch, caches et auxiliaires privacy. Son reçu
ne contient que catégories, identifiants logiques opaques, hashes et statuts. Une erreur produit
`partial_failure`, bloque l’analyse et ne prétend jamais à une purge complète.

## Limite de la garantie

Le workspace et l’orchestration sont locaux et aucune télémétrie ou upload arbitraire n’est ajouté
au moteur. Codex/OpenAI doit néanmoins traiter les données nécessaires au service selon la
configuration employée. Cette architecture est un contrôle technique, pas une certification, un
avis juridique ou une preuve d’anonymisation parfaite.

Les assertions couvrent les entrées officielles Againward, pas la capacité générale de Python ou d’un
outil externe à ouvrir arbitrairement un fichier. Un chemin autonome hors des racines de dossiers
gérés ne peut pas être identifié comme client par son seul contenu sans violer la règle Codex-first :
les données client réelles doivent donc toujours être créées dans un workspace officiel. Les cas
synthétiques sous racines gérées utilisent un manifest explicite ; les fixtures versionnées et les
répertoires temporaires des harnesses de benchmark restent hors des racines client et sont déclarés
comme synthétiques par ces harnesses. Les scripts de développement autonomes hors workflow restent
hors de cette garantie.

## Fermeture de mission

Le gate contractuel, l’autorisation historique du traitement et les projections retenables sont
décrits dans [FINAL_CLIENT_MISSION.md](FINAL_CLIENT_MISSION.md). Aucune exemption implicite de
conservation des contrats/factures ne subsiste : policy explicite, finalité et revue requises.
Le post-mortem complet est temporaire ; seule la whitelist revue peut survivre à la purge.
