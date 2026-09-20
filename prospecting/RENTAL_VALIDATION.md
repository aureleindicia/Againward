# Validation Rental - 20 septembre 2026

Perimetre : 50 entreprises francaises plus 50 hors France. Les controles structurels ne prouvent pas les affirmations publiques : celles-ci restent rattachees aux sources et limites de chaque fiche.

## Audit des exigences

| Exigence | Preuve conservee et resultat |
|---|---|
| 1. Methode avant collecte | METHODOLOGY.md, commit a0caea0; methode sourcee reproduite au debut des masters. |
| 2. Geographie | 50 France, 35 United Kingdom, 15 Belgium; aucun quota regional. |
| 3. Profil operationnel | Secteur executant, taille et operations decrits pour chaque cible. |
| 4. Location plausible | equipment, rental_evidence, rental_spend_hypothesis et sources; 95 inferences operationnelles, aucune depense inventee. |
| 5. Taille | Hypothese centrale 50-500 personnes; exceptions et perimetres groupe/unite/ETP explicites, sans seuil de rentabilite pretendu. |
| 6. Exclusions | 34 rejets motives dans REJECTED.json; aucun dans les selections. |
| 7. OSINT | Sources publiques, claim/URL/date dans source_references; aucune base privee ou donnee client. |
| 8. Contact | Fonction cible, personne lorsqu'identifiee, route et source; aucun titulaire invente. |
| 9. Emails | confirmed_email distinct de inferred_email_pattern; zero modele devine. |
| 10. Verification | 4 CONFIRMED, 6 ROLE_ADDRESS, 78 GENERIC, 12 CONTACT_FORM_ONLY, tous sources. Publication seulement, pas de test de delivrabilite. |
| 11. Personnalisation | Deux a quatre faits par fiche; references anciennes signalees comme telles. |
| 12. Difficultes | likely_pain_angle distingue hypothese commerciale et anomalie; aucune erreur alleguee. |
| 13. Score | Huit notes et justifications, poids total 100; recalcul independant identique. |
| 14. Tiers | 17 A et 83 B; zero C de remplissage; retrogradations motivees. |
| 15. Profondeur | Activite, materiel, interet documentaire, contact, fait reutilisable et sources dans chaque fiche. |
| 16. Formats | Deux masters Markdown et deux JSON contenant chacun exactement 50 fiches. |
| 17. EMAIL_CONTEXT | Champ non vide dans les 100 fiches; aucun email commercial redige. |
| 18. Strategie | Methode et RENTAL_100.md : dix premiers, variantes par role, petit echantillon apres accord, objections et parcours ecrit sans rendez-vous impose. |
| 19. Fit avant email | Contact limite a 5/100; un formulaire peut rester A, dont Le Batiment Associe. |
| 20. Confiance | 2 HIGH et 98 MEDIUM avec arbitrages; confiance de ciblage, pas preuve d'erreur. |
| 21. Groupes | 100 cles distinctes; contre-indices consignes et autonomie a qualifier. |
| 22. Actualite | Recherche des 19-20 septembre 2026; dates historiques visibles, contacts a revalider avant toute campagne. |
| 23. Review | 100 revues individuelles dans RENTAL_FINAL_REVIEW.json; contre-arguments, reductions de notes et remplacements de Komorniczak, Chapron et Breheny. |
| 24. Bilan | RENTAL_100.md et RENTAL_SUMMARY.json : 134 examines, 34 rejetes, 100 retenus; top 10 global et par marche. Aucun contact effectue. |
| Extension internationale | JURISDICTIONS.md : sources CNIL/ICO/SPF/Commission, formes sociales, routes, contrats, langues et donnees; aucune autorisation generale de recouvrement pretendue. |

## Controles executes

- python prospecting/build_rental_prospects.py : reussite; six artefacts generes identiques octet pour octet apres regeneration, verification SHA-256.
- Verification independante : deux fois 50 fiches; rangs 1-50; 100 noms et cles de groupe distincts; zero selection parmi les 34 rejets; champs requis; provenance des contacts; recalcul des scores; poids 100; 100 revues; parite du nombre de fiches Markdown/JSON; outreach_authorized=false.
- python -m pytest prospecting/tests -q : **19 tests reussis**. Tests des outils existants, pas verification automatique de la veracite OSINT.
- git diff --check : reussite; controle repete apres staging avant commit.
- Relecture des 17 A : parc propre, sous-traitance, payeur, sophistication des controles, pertinence et actualite du contact. Aucun taux d'erreur ni gain presume ajoute.

Ce lot modifie documentation, donnees publiques et renderer. Les moteurs Energy/Rental ne sont pas modifies; la suite analytique complete n'a pas ete relancee pour ce lot documentaire. Le renderer n'effectue aucun reseau ni envoi.

## Limites conservees

Les categories locatives comprennent 95 inferences operationnelles, deux mentions explicites, un deploiement fournisseur explicite, des conditions d'achat prevoyant la location et un deploiement fournisseur dont le payeur reste inconnu. Les cinq derniers dossiers ne prouvent pas tous une facture actuelle adressee au prospect. Aucun budget locatif ou remboursement attendu n'est chiffre.

Les routes publiques ne constituent pas des accords pour recevoir une offre. Ni emails ni formulaires n'ont ete testes par envoi. Certains roles et effectifs reposent sur une publication historique explicitement datee. Les registres et l'activite publique ne garantissent pas la solvabilite. MEDIUM et A peuvent coexister sans signifier location confirmee.

Les cles de groupe verifient le dedoublonnage documente, pas toutes les participations possibles. Entite facturee et autonomie restent a qualifier par ecrit. Les listes d'opposition existantes consultees etaient vides; toute campagne future devra refaire ce controle.

Le choix Royaume-Uni/Belgique porte sur l'offre documentaire. Il ne constitue ni un classement mondial des legislations ni une autorisation de conseil juridique, representation ou recouvrement. Les regles des adresses nominatives et impersonnelles restent distinctes.
