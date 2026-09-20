# AGAINWARD Rental — 100 prospects documentés

Recherche et revue finalisées le **20 septembre 2026**. **Aucune entreprise contactée, aucun email envoyé, aucun formulaire soumis.** Le fichier prépare une recherche commerciale; il ne démontre ni erreurs de facturation ni gains récupérables.

## Livrables

- **50 entreprises françaises** : [master Markdown](rental_france_50/PROSPECTS_50.md) · [dataset JSON](rental_france_50/PROSPECTS_50.json).
- **50 entreprises hors France**, dont 35 britanniques et 15 belges : [master Markdown](rental_international_50/PROSPECTS_50.md) · [dataset JSON](rental_international_50/PROSPECTS_50.json).
- [Méthodologie de sélection et de scoring](rental_france_50/METHODOLOGY.md), également reproduite au début des deux masters.
- [Comparaison juridique et pratique des pays](rental_international_50/JURISDICTIONS.md).
- [Rejets motivés](REJECTED.json), [revues individuelles](RENTAL_FINAL_REVIEW.json), [comptages JSON](RENTAL_SUMMARY.json) et [validation finale](RENTAL_VALIDATION.md).

## Bilan de sélection

| Indicateur | France | Hors France | Total |
|---|---:|---:|---:|
| Dossiers documentés examinés | 76 | 58 | 134 |
| Rejetés | 26 | 8 | 34 |
| Sélectionnés | 50 | 50 | 100 |
| Tier A — qualifier d’abord | 6 | 11 | 17 |
| Tier B — bons prospects avec réserves | 44 | 39 | 83 |
| Tier C | 0 | 0 | 0 |
| Email professionnel nominatif publié | 3 | 1 | 4 |
| Email de fonction | 2 | 4 | 6 |
| Email générique | 38 | 40 | 78 |
| Formulaire uniquement | 7 | 5 | 12 |
| Modèle d’email inféré | 0 | 0 | 0 |
| Confiance HIGH | 2 | 0 | 2 |
| Confiance MEDIUM | 48 | 50 | 98 |

Ces nombres comptent les dossiers conservés, pas tous les résultats de recherche aperçus. Les 84 adresses de fonction ou génériques sont distinctes des quatre adresses nominatives. « Publié/confirmé » décrit une preuve publique de l’adresse, sans test de délivrabilité. Le champ JSON `confirmed_email` peut contenir une adresse générique; `contact_status` distingue les catégories. Une priorité A est un jugement commercial, pas une preuve d’anomalie ni une garantie de dépense locative.

## Dix premières entreprises à qualifier

Ordre global : tier, score décroissant, nom pour départager les égalités. Les deux masters proposent aussi leur propre top 10. Chaque fiche contient la route publique, les sources et le champ `EMAIL_CONTEXT`; les faits ci-dessous renvoient à ces fiches.

| Priorité | Entreprise | Pays | Score | Fait utile / première réserve |
|---:|---|---|---:|---|
| 1 | Launet Construction | France | 88.0/100 · A | Launet réalise charpentes, clos-couvert et surélévation dans les Hauts-de-France, en Île-de-France et Normandie. À qualifier : Annonce portée par Launet mais poste chez Beuvain Montage : entité payeuse à confirmer. |
| 2 | Jackson Civil Engineering Limited | United Kingdom | 86.0/100 · A | Les conditions d'achat publiées en février 2026 prévoient expressément la location d'engins à des fournisseurs. À qualifier : Contrôles formels existants : ne pas présenter l'offre comme leur remplacement. |
| 3 | Cruard Charpente et Construction Bois | France | 84.0/100 · A | Montages en Normandie, Bretagne, Pays de la Loire, Centre et région parisienne. À qualifier : Ateliers possédés; location de moyens sur chantier inférée. |
| 4 | Dubrulle-Faignot TP | France | 84.0/100 · A | Construction de réseaux pour fluides; entreprise active selon le registre. À qualifier : Le partenariat de 2023 ne prouve ni volume actuel ni facturation directe à Dubrulle. |
| 5 | Stepnell Limited | United Kingdom | 84.0/100 · A | La nomination d'un responsable matériel en 2024 vise explicitement à limiter les locations externes inutiles. À qualifier : Parc propre et responsable dédié : contrôles déjà structurés. |
| 6 | Ashe Construction Limited | United Kingdom | 83.0/100 · A | L’entreprise publie l’avancement de la charpente du centre de recyclage de Wolverton, Milton Keynes. À qualifier : Matériels propres mentionnés dans le plan carbone; compléments externes inférés. |
| 7 | Conamar Building Services Limited | United Kingdom | 83.0/100 · A | Réhabilitation Centre:MK sur 56 semaines, en majorité la nuit dans un centre ouvert le jour. À qualifier : La durée du projet n'est pas la durée de location; vérifier si les sous-traitants paient le matériel. |
| 8 | Entreprises Mignone SA | Belgium | 83.0/100 · A | Deux métiers: construction et électricité, dont moyenne tension et réseaux industriels. À qualifier : Ne pas assimiler les 150 références à 150 chantiers simultanés: formulations différentes selon les pages. |
| 9 | Groupe Remove / REMOVE | France | 83.0/100 · A | Interventions en Île-de-France et sur le territoire français. À qualifier : Parc géré en interne; part louée inconnue. |
| 10 | E.G. Carter & Company Limited | United Kingdom | 82.0/100 · A | Entreprise familiale intervenant dans les Midlands et le Sud-Ouest. À qualifier : Effectif du holding, non équivalent à l'unité opérationnelle. |

## Signaux qui ont réellement guidé la sélection

Les meilleurs dossiers combinent une activité exécutante et des opérations temporaires répétées : montage mobile, terrassement/réseaux, plusieurs implantations, travaux par phases ou en site occupé. Les indices de location publiés dans des recrutements, documents fournisseurs ou conditions d’achat renforcent ces signaux. Taille intermédiaire et routage finance/achats accessible améliorent l’adéquation. La facilité à trouver un email ne représente que cinq points sur cent.

La cible centrale est une PME ou entreprise intermédiaire d’environ 50–500 personnes, avec exceptions motivées selon les opérations et le périmètre réel. Ce seuil est une hypothèse commerciale documentée, pas un seuil de rentabilité démontré. Un groupe structuré peut rester pertinent pour une vérification ponctuelle; il ne faut pas lui attribuer des contrôles faibles. Parc propre, sous-traitance et achats intragroupe sont les principales contre-explications au besoin présumé.

## Utilisation proposée, entièrement asynchrone

Commencer par les dix premières qualifications, puis élargir en fonction des réponses pertinentes, des locations externes effectivement payées et des pièces disponibles. Distinguer absence de réponse, absence de besoin et refus; ne pas prétendre valider le marché sur dix dossiers. Les contacts et exclusions devront être revérifiés lors d’une future campagne, laquelle n’est pas exécutée ici.

Présenter une **vérification documentée des factures de location**. « Audit » peut suggérer un contrôle réglementaire; « récupération de coûts » présuppose un gain encore inconnu. Pour finance, insister sur rapprochement, justification et avoirs; pour achats, tarifs et frais convenus; pour travaux/matériel, dates, mouvements et retours. Utiliser deux faits précis de la fiche, sans affirmer un problème chez le destinataire.

Le premier objectif écrit est de confirmer l’intérêt et l’entité qui paie réellement les locations. Après accord, proposer trois à cinq factures d’un même loueur/chantier avec contrat ou tarif accepté, bons de mise à disposition, traces d’arrêt/retour et avoirs éventuels. Convenir du canal sécurisé, du périmètre et des données à masquer. Aucun appel, démo ou réunion obligatoire; aucun email commercial n’est rédigé dans ces livrables.

Objections principales : parc possédé, contrôle ERP déjà présent, échantillon trop petit, pièces manquantes, confidentialité et relation avec le loueur. Répondre par un périmètre limité et une vérification contradictoire; arrêter si la valeur paraît disproportionnée ou les pièces insuffisantes. Le livrable envisagé est un dossier factuel d’écarts éventuels, pas une promesse de recouvrement.

## Pays, langues et limites

Le Royaume-Uni et la Belgique ont été retenus pour la qualité des preuves accessibles, le tissu d’entreprises et des règles de prospection officielles identifiables. Le [rapport juridique](rental_international_50/JURISDICTIONS.md) distingue sociétés britanniques, personnes morales belges et adresses nominatives/impersonnelles. Il ne valide pas une activité réglementée de conseil juridique ou de recouvrement pour compte de tiers. Aucun autre pays n’est déclaré défavorable faute d’avoir été étudié.

Préparer les échanges en français ou anglais selon les fiches. Pour certains prospects flamands, confirmer la langue de travail; ne pas supposer que l’anglais est accepté. Conserver la langue des contrats et des conditions originales pendant toute investigation.

La dépense locative demeure généralement inférée et aucun montant annuel n’est extrapolé. Un fournisseur visible sur chantier peut facturer un sous-traitant. Les effectifs peuvent concerner une unité légale, un groupe ou des ETP et être historiques; leur périmètre est explicité. Les références anciennes prouvent une capacité, pas une activité simultanée actuelle. Les chiffres d’affaires non comparables sont laissés vides. Les registres consultés ne constituent pas une enquête exhaustive de solvabilité. Les 98 dossiers MEDIUM reflètent ces limites, et non 98 locations confirmées.

## Reproduction locale

Depuis la racine du dépôt : `python prospecting/build_rental_prospects.py`. Le script lit les dossiers OSINT conservés, calcule les scores et rend les deux masters, JSON, statistiques et revues. Bibliothèque standard uniquement, aucun réseau ni envoi. La recherche et les arbitrages restent humains/agentiques; le script ne découvre ni ne vérifie de nouveaux prospects.
