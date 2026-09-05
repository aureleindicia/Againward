# Modèle de menaces privacy INDICIA

## Périmètre

Ce modèle couvre les futurs workspaces `REAL_CLIENT`, depuis la réception jusqu’à la purge. Il
traite la minimisation de données, les secrets accidentels, la contamination des dérivés, Git et la
traçabilité. Il ne remplace pas l’analyse contractuelle ou juridique applicable au pilote.

## Actifs à protéger

- identités, coordonnées, matricules, commentaires RH/médicaux et texte libre personnel ;
- mots de passe, clés, tokens, credentials et URL d’accès ;
- données industrielles confidentielles nécessaires à la prestation ;
- relations temporelles et structurelles nécessaires à l’attribution ;
- exactitude du lineage, du manifest et du reçu de purge.

## Frontières de confiance

1. Le dépôt externe devient temporairement local dans `incoming/`.
2. Codex lit le contenu en premier et porte la décision sémantique.
3. Python ne fait confiance ni à la review ni au candidat : il post-vérifie et bloque.
4. `sanitized/` est la seule source initiale autorisée après clearance.
5. L’humain reste requis avant livraison.
6. La purge ferme définitivement le workspace analytique.

## Menaces, contrôles et résiduels

| Menace | Contrôle | Risque résiduel |
| --- | --- | --- |
| Analyse avant minimisation | lifecycle privacy + asserts sur les commandes ; reconnaissance des dossiers sans manifest sous `workspaces/` et `client_cases/` | du code ad hoc hors workflow ou un fichier client mal placé hors des racines gérées peut être lu ; la discipline de staging et la revue opérateur restent nécessaires |
| Codex manque une identité en texte libre | revue exhaustive puis patterns Python | aucun détecteur de noms n’est parfait ; ambiguïté ⇒ `BLOCKED` |
| Faux positif supprimant un actif | colonnes industrielles exemptées des patterns naïfs et comparées exactement | une colonne mal nommée peut être mal classée ; Codex doit expliciter son sens |
| Pseudonyme instable ou collision | format borné et mapping injectif éphémère vérifié sur toutes les colonnes relationnelles de tous les fichiers du dépôt | des alias textuels distincts d’une même personne ne peuvent pas être rapprochés déterministement ; ambiguïté ⇒ `BLOCKED` |
| Secret restant | patterns credentials/clé/token + colonnes explicites | formats propriétaires inconnus possibles ; doute ⇒ `BLOCKED` |
| Mutation énergétique pendant sanitation | comparaison lignes/feuilles/valeurs industrielles | texte libre ne peut être comparé sémantiquement par Python |
| PII recréée dans l’audit | schémas bornés, codes/comptes, erreurs génériques, review supprimée après succès | workspace/case id doit lui-même être non personnel |
| Copie cachée | zones bornées, promotion staging nettoyée, pré-dérivés refusés, purge deny-by-default | backups OS, historique d’éditeur ou stockage externe ne sont pas inspectés |
| Commit accidentel | patterns `.gitignore` et tests `git check-ignore` | `git add -f` ou copie hors zones ignorées reste possible ; review humaine de `git diff/status` |
| Suppression partielle | purge immédiate de `incoming/` même après `BLOCKED`, vérification du nombre restant, statut et codes d’échec sans contenu | support de stockage/backup hors workspace non contrôlé ; une erreur laisse le dossier bloqué et peut laisser une partie du brut sur place |
| Réidentification d’un dérivé | rétention refusée par défaut et revue de désidentification stricte | rareté industrielle et sources externes peuvent encore réidentifier ; aucune anonymisation parfaite promise |
| Surconfiance après réponse client | provenance typée et plafonds EvidenceLedger | erreur déclarative humaine toujours possible |
| Exposition via Codex/OpenAI | transparence documentaire sur le traitement nécessaire | dépend des paramètres, politiques et conditions du service utilisé |

## Cas fail-closed

Le gate doit produire ou converger vers `PRIVACY_BLOCKED` si :

- le format ne peut pas être inspecté avec confiance ;
- des données RH/médicales sont présentes ;
- un secret ne peut pas être retiré sûrement ;
- un motif personnel/secret reste dans le candidat ;
- une colonne industrielle, une ligne, une feuille, un timestamp ou une valeur utile change ;
- une relation personnelle utile n’a pas un pseudonyme stable ;
- une même identité textuelle reçoit plusieurs pseudonymes entre fichiers ou plusieurs identités
  textuelles partagent le même pseudonyme ;
- la review ne couvre pas exactement le dépôt ou contient des champs libres ;
- un symlink, un chemin extérieur, un candidat manquant ou une collision de destination apparaît ;
- un dérivé analytique existe déjà avant clearance ;
- la promotion ou la suppression du brut temporaire échoue.

En `PRIVACY_BLOCKED`, il ne faut ni analyser, ni extrapoler depuis ce qui a été vu, ni générer de
finding. Le système tente immédiatement de supprimer le brut temporaire et ses auxiliaires, puis
enregistre uniquement hashes, `file_id`, catégories/codes, timestamps et résultat de suppression.
La résolution consiste à produire un nouvel export minimal sûr ou à revoir manuellement le
protocole ; elle ne consiste pas à diminuer les contrôles.

## Hors périmètre volontaire

- chiffrement disque, gestion de clés, DLP système et effacement physique garanti du support ;
- sauvegardes Android, synchronisation cloud configurée par l’utilisateur et caches de fournisseurs ;
- contrôle des politiques de conservation d’OpenAI ou d’autres services ;
- reconnaissance universelle des personnes et secrets propriétaires ;
- preuve mathématique d’anonymat ou conformité juridique définitive ;
- données temps réel, multi-tenant, SaaS ou API externe ajoutée avant Codex.
- interception du langage Python arbitraire ou identification par contenu d’un fichier client placé
  hors des racines et commandes officielles INDICIA.

Ces limites doivent être examinées avant chaque pilote et communiquées sans transformer une mesure
technique en promesse juridique.
