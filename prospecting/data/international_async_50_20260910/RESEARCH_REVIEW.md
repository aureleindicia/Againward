# Le premier lot confondait trop facilement numérique, remote et collaboration asynchrone

Revue du 10 septembre 2026. Recherche publique, sans accès aux consommations, sans entretien et sans contact commercial.

## La méthode existante est conservée

L'[ICP](../../ICP.md) demande un site/procédé propre identifiable et un fonctionnement répétitif, généralement 15–150 salariés. Un fait sur le procédé et un fait sur le site, la taille, la croissance ou l'organisation sont nécessaires. Une inconnue conduit à `UNCERTAIN`, pas à un rejet factuel inventé. Le [cadrage des pilotes](../../../business/pilot_gtm/ICP_AND_SEGMENTATION.md) distingue ensuite la qualification réelle : sponsor, périmètre, données de plusieurs semaines et contexte d'exploitation. Ses critères ne sont pas remplacés par le score public.

Le calcul de [score.py](../../score.py) reste inchangé : énergie 19, optimisation 17, qualité probable des données 11, valeur économique 14, accessibilité 11, absence d'expertise énergie interne 7, adéquation 13, async 8 ; notes de 0 à 5. Les appréciations restent des jugements qualitatifs, pas des probabilités calibrées. Les notes identiques et les petits écarts n'autorisent pas une hiérarchie fine.

Avec seulement 8 points de poids, l'async ne pouvait pas être « vraiment très important » dans l'ordre final. Plutôt que réécrire l'historique ou inventer un deuxième score sur 100, la [doctrine complémentaire](../../ASYNC_QUALIFICATION.md) impose un filtre métier/périmètre puis des bandes de preuve async. Le score historique sert à ordonner à l'intérieur de ces bandes. Python valide et additionne ; l'appréciation des faits reste éditoriale.

## Jugement sur le travail précédent

Le [premier lot international](../international_async_20260910/scoring_assessments.json) a correctement séparé faits, appréciations, calcul et absence d'envoi. Il avait identifié quelques industriels intéressants, sans prétendre posséder leurs mesures. Ces éléments sont conservés.

Mais il ne suffisait pas pour la demande actuelle :

1. **Cinq entreprises conservées seulement**, avec un sixième dossier exclu : trop peu de diversité pour rechercher sérieusement le double fit industriel/async.
2. **Mackie's en priorité A, async 1/5** : logique possible pour le métier, inadaptée à un classement dominé par le besoin d'écrit. Le dossier reste intéressant industriellement mais passe en réserve commerciale.
3. **PaperShell à 4/5 async pour du remote lorsque possible** : la [page carrière](https://papershell.se/careers/) confirme une flexibilité, pas une pratique opérationnelle écrite avec les fournisseurs. Nouvelle note 2/5.
4. **Vestre à 4/5 pour des postes commerciaux remote** : extrapolation aux opérations/achats injustifiée. Sans revalidation d'une pratique pertinente, la nouvelle appréciation n'utilise pas ce signal comme preuve forte.
5. **Qualité probable des données trop généreuse chez Mackie's** : investissements et pilotage de l'énergie ne prouvent ni export ni pas de temps. La disponibilité reste `UNKNOWN`.
6. **KTC exclu pour absence de production documentée** : motif de réserve, pas preuve d'absence. Il reste hors sélection industrielle faute de périmètre établi, sans qualifier cette absence de preuve de rejet définitif.

Notpla et Epishine restent en veille, hors des 50 retenus : l'échelle industrielle répétitive et la preuve async n'ont pas été suffisamment renforcées pour les privilégier. Les anciennes fiches ne sont pas réécrites.

## Ce que les nouveaux recoupements changent réellement

- **Modist** : des fiches de production relient brassage, nettoyage, traces Ekos et communication écrite. C'est plus pertinent qu'un poste commercial remote. [Fiche brasseur](https://modistbrewing.com/wp-content/uploads/2025/05/Part-Time-Brewer_Cellarperson-Job-Description-1.pdf).
- **G&O Springs** : le MTC décrit Teams, APQP et accès aux informations en atelier. Le fait que les opérations soient documentées rend la qualification écrite crédible ; aucun compteur n'est pourtant confirmé. [Cas MTC, juin 2026](https://www.the-mtc.org/insights/go-springs-setting-standard-sme-digital-adoption).
- **Buddy Brew** : le recrutement production relie planning de torréfaction, Cropster et Slack. L'ouverture directe de l'annonce a échoué : l'extrait officiel indexé et sa reprise sont distingués d'une lecture intégrale. [Annonce officielle](https://buddybrew.hrmdirect.com/employment/job-opening.php?req=3741077&req_loc=1362112), [reprise Built In](https://builtin.com/company/buddy-brew-coffee/teams).
- **Geometric** : l'[étude historique Slack, page 8](https://bethebusiness.com/files/research-reports/ebook_slack_the_secret_of_productive_work.pdf) soutient bien des transmissions entre shifts. Mais le [site actuel](https://geometricmanufacturing.co.uk/) décrit une infrastructure air-gapped et des contraintes défense. Excellent fit industriel, partage des données non acquis : réserve commerciale explicite.
- **BACA** : le [cas Slack](https://slack.com/customer-stories/baca-systems-story) décrit réellement décisions, achats et opérations écrits. En revanche, fabriquer des robots n'est pas consommer comme les usines de pierre clientes. Note async élevée, utilité énergétique propre à qualifier : il ne passe pas devant les bonnes cibles métier.
- **Clifton Coffee** : la [présentation Teams](https://www.changingsocial.com/case-studies/clifton-coffee/) renvoie à un déploiement de 2018. L'ouverture du document a évité de présenter cette culture comme nouvellement prouvée en 2026.

Ces contradictions sont conservées dans les fiches. Les sources liées au recrutement décrivent un usage attendu dans un rôle, pas une garantie que tous les salariés travaillent ainsi aujourd'hui.

## Les entreprises écartées empêchent de remplir la liste avec de faux bons prospects

| Entreprise | Décision et preuve |
|---|---|
| Laserhub | Pas client industriel direct retenu : plateforme sans production propre selon sa [FAQ](https://laserhub.com/plattform/faq/?anchor=angebotsoptionen). |
| SendCutSend | Métier et digital solides, mais le [site actuel](https://sendcutsend.com/about-us/) annonce plus de 500 salariés. Hors premier lot PME ; des pages plus anciennes indiquent moins de sites. |
| Protocase | [Historique actuel](https://www.protocase.com/about/history/) proche de 500 salariés : hors taille première approche. |
| Eurocircuits | [Mise à jour 2024](https://www.eurocircuits.com/eurocircuits-company-update/merry-christmas-2024/) : groupe de plus de 500 personnes. Pas ramené artificiellement à une ancienne taille. |
| Komaspec / Komacut | [Komaspec](https://www.komaspec.com/) annonce plus de 350 personnes et plusieurs pays : futur site ciblé possible, pas priorité PME ici. |
| Oxwash Big Blue | Le [registre PSC](https://find-and-update.company-information.service.gov.uk/company/14561528/persons-with-significant-control) indique le contrôle par Elis UK. Écarté conservatoirement comme filiale du groupe français, sans dire que toute implantation UK est française. |
| KTC Ingredients | [Culture distribuée](https://www.ktcingredients.com/careers/) intéressante, site industriel propre non établi : réserve, pas preuve de non-pertinence définitive. |

Les sociétés et leurs marques ne sont pas comptées deux fois : Photoncut/KM, Beta LAYOUT/PCB-POOL, Newbury Electronics/PCB Train, eMachineShop/Micro Logic.

## Solidité et limites de la liste de 50

Le [rapport](PROSPECTS_50.md) distingue cinq premières cibles, des candidats à qualification complémentaire et des réserves. **Il ne démontre pas que 50 entreprises auraient une forte probabilité de rentabiliser un pilote.** Cette probabilité n'est pas estimable honnêtement sans données, budget et problème opérationnel. Les 50 dossiers ont un lien industriel documenté ou explicitement à reconfirmer ; les cas incomplets ne sont pas assimilés aux premières cibles.

Pour beaucoup, le signal est un portail commercial côté vente. Cela prouve une capacité à échanger des fichiers et suivre une opération numériquement ; cela ne prouve pas le fonctionnement des achats. Aucun prospect n'a confirmé accepter Againward en mode principalement écrit. La confiance dans ce transfert reste moyenne au mieux, et la variable de probabilité est nulle au sens JSON `null` — inconnue, pas probabilité zéro.

Le sous-lot froid a un fort potentiel technique, mais les WMS ne sont pas des compteurs énergie. Les torréfacteurs peuvent exiger du gaz horodaté : une courbe électrique ne mesure pas nécessairement le principal usage thermique. Une PME d'additive bien digitalisée peut rester trop petite économiquement. Les procédés nécessaires, préchauffages ou maintien en température ne sont pas des économies récupérables par défaut.

La recherche ouverte a couvert plusieurs continents, sans prime de pays. Elle présente toutefois un biais de visibilité : documentation anglophone, recrutement public et entreprises numériques sont plus faciles à trouver. Les implantations indiquées ne prouvent pas l'anglais de travail de chaque équipe. L'effectif actuel manque souvent ; le site/parc documenté sert de proxy de périmètre, pas de nombre inventé.

## Traçabilité et personnalisation

L'[inventaire](source_inventory.json) conserve URL, éditeur/domaine, fait résumé, date de consultation, date de publication lorsqu'identifiable, mode d'accès et limite. `SEARCH_EXTRACT` signifie contenu indexé consulté, pas page intégralement lue. Un échec d'ouverture ou un challenge reste signalé. Les reprises LinkedIn/Indeed/Built In d'une même annonce ne sont pas des corroborations indépendantes. Aucun profil privé, compte connecté ou avis anonyme n'a été utilisé pour affirmer une politique générale.

Les [notes email](EMAIL_PERSONALIZATION.md) donnent, pour chaque entreprise, un fait d'accroche, sa source, le lien à une investigation plausible, la fonction cible et une question courte. Elles évitent de transformer une offre d'emploi en prétexte intrusif et ne contiennent aucune anomalie prétendument déjà trouvée. Aucune adresse n'est devinée, aucun email n'est envoyé. La langue et le destinataire restent à valider avant rédaction finale.

## Ce qui doit faire changer le classement

Une réponse écrite suffit à qualifier le mode de relation : sponsor disponible pour des questions consolidées par écrit, exports existants et appels exceptionnels convenus. Après accord, demander un échantillon et le périmètre des mesures, unité/pas de temps, au moins plusieurs semaines, contexte de production et ordre de grandeur de facture. Refuser le pilote si le coût et le travail nécessaires sont disproportionnés ou si la donnée ne permet aucune question utile.

L'absence de réponse n'est pas une incompatibilité async démontrée. Un export défaillant est un obstacle concret. Un accord de méthode sans problème métier ne suffit pas. Le classement doit évoluer à partir de ces preuves, sans gonfler rétroactivement les scores publics.

## Reproductibilité

`research_judgments.json` conserve les appréciations de recherche ; `build_artifacts.py` ne recherche et ne décide rien de nouveau. Il réutilise `prepare.py`, la liste d'opposition et `score.py`, puis présente la bande commerciale déjà définie. Les lots précédents, le moteur analytique et le workflow client sont inchangés. Les tests vérifient contrats, calculs, références et absence de claims de qualification ; ils ne certifient pas les déclarations publiques des entreprises.
