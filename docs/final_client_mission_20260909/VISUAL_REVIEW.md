# Inspection réelle des PDF synthétiques

## Méthode et versions

Générateur : `workspace/generate_final_mission_reports.py`. Les sources sont des
fixtures Goal A/B existantes et un exemple Value Map explicitement fictionnel de
réfutation. Aucun résultat de détecteur ni feedback client réel n’est revendiqué.

Les PDF ont été rasterisés avec `pdftoppm -scale-to 1200 -png` et leur texte extrait
avec `pdftotext -layout`. Toutes les douze pages de la version initiale ont été
inspectées. Les corrections ont porté sur les libellés des prochaines étapes,
le format des euros, les périodes graphiques, les graduations, un titre trop
affirmatif et les formulations génériques des fixtures.

Les douze pages de la version v3 ont été vues individuellement. En v4, les pages
modifiées ont été réinspectées : clear_energy page deux ; multiple_priorities
pages deux, trois et quatre. Les huit autres images raster sont identiques octet
pour octet à celles déjà inspectées en v3. Les PDF v4 et leur SHA exact figurent
dans `examples/final_client_mission_reports/MANIFEST.json` ; les attestations
`REPORT_VISUAL_REVIEW.json` ont été enregistrées après cette inspection.

## Résultat par cas

| Cas | Pages | Histoire éditoriale | Contrôle visuel |
|---|---:|---|---|
| clear_energy | 3 | Écart récurrent, bénéfice net potentiel, observation et activité, alternatives, action et vérification | Montant lisible sans statut réalisé ; graphique non tronqué, unités et période lisibles ; alternatives visibles ; aucun débordement |
| false_lead | 2 | Ne pas engager une correction non justifiée ; piste éliminée et périmètre recentré | Aucun euro fictif ; Value Map séparée ; texte aéré, accents corrects, absence de tableau inutile |
| multiple_priorities | 5 | Agir, vérifier avant investissement, surveiller, préserver les horaires | Deux pistes majeures puis deux secondaires ; plages distinctes sans total ; contrainte de fraîcheur visible ; décisions hiérarchisées |
| useful_abstention | 2 | Aucune intervention suffisamment étayée ; conserver la référence et savoir quand reprendre | Pas de page vide de remplissage ni de métrique artificielle ; abstention explicitement distincte de l’absence d’anomalie |

Identité commune : blanc, encre sombre, trait discret vert industriel, typographie
sobre, marges constantes et pagination. Aucun emoji, jauge, gradient, effet de
volume, carte décorative ou marque copiée. Les pages courtes ne sont pas gonflées
pour atteindre arbitrairement quatre pages. Le document multi-priorités réserve
plus de place aux décisions majeures.

## Question obligatoire AG

« Si ce PDF était envoyé demain au directeur d’une PME industrielle ayant payé
l’analyse, aurait-il l’impression de recevoir un livrable professionnel préparé
spécialement pour son entreprise ? »

**Oui pour la présentation et la capacité de composition démontrées**, sous réserve
que le contenu du dossier réel soit effectivement personnalisé et validé. La
hiérarchie, les chiffres, les réserves et les prochaines étapes sont lisibles sans
connaître l’architecture interne. Les quatre cas ont des narrations distinctes.

La matière technique des anciennes fixtures est volontairement compacte et
abstraite : elle ne constitue pas une investigation industrielle complète. Le
petit graphique de contexte ne prouve pas à lui seul la récurrence affirmée par
le finding synthétique. Un vrai rapport devra choisir les comparaisons réellement
probantes de son dossier. Cette limitation est analytique, pas un motif pour
remplir les pages ou fabriquer des preuves.

Les PDF sont publiés comme **exemples synthétiques inspectés**, jamais comme
livraisons client approuvées. Les attestations visuelles ne remplacent aucune revue
humaine sémantique et ne peuvent pas être réutilisées pour d’autres octets PDF.
