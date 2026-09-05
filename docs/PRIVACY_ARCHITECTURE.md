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
réception
  └─ stage_incoming_drop()              copie sans inspection sémantique
       └─ incoming/                     zone temporaire ignorée par Git
            └─ CODEX PRIVACY GATE       première lecture substantielle
                 ├─ PASS                copie fidèle requise
                 ├─ SANITIZED           candidat dans privacy/candidate/
                 └─ BLOCKED             STOP
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
ne contient ni hash ni contenu. Après succès, la review et ce reçu de staging sont supprimés pour
éviter qu’un nom de fichier ou un champ de travail recrée une donnée retirée.

## Contrat de revue Codex

Schéma : `indicia-codex-privacy-review-v1`. Chaque fichier reçu apparaît exactement une fois avec
un `file_id` non sémantique, une action et, le cas échéant, un candidat. Les transformations ne
contiennent que : catégorie, action, compte, attestation de préservation et code de raison.

Les valeurs personnelles ne sont jamais écrites dans la review ni dans le manifest. Une relation
utile est pseudonymisée de façon stable sans table de correspondance :

```text
OPERATOR_001 → PRESS_07 → shift_nuit → timestamps
```

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
- pseudonymes stables, injectifs et présents lorsque la relation est conservée ;
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

Le brut n’est pas conservé après succès. Le lineage repose sur les hashes et `file_id`, puis la
provenance d’intake référence `sanitized/`. Les erreurs durables ne reprennent ni en-tête, ni chemin,
ni valeur source ; le détail reste dans l’exception opérateur éphémère.

## Verrous d’exécution

`assert_case_privacy_cleared()` et `assert_source_approved_for_analysis()` sont appelés par les
entrées d’investigation, intake Goal A, requêtes de preuve, findings, attribution, économie,
rapport et livraison. Une source `sanitized/` doit avoir un hash présent dans le manifest.

Les états sont `AWAITING_PRIVACY_REVIEW`, `PRIVACY_CLEARED`, `PRIVACY_BLOCKED`, puis `PURGED` en fin
de mission. Tout état différent de `PRIVACY_CLEARED` refuse les actions analytiques. Les dossiers
synthétiques sont exemptés seulement par un flag explicite dans leur manifest.

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
