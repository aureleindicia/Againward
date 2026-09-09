# Prospection internationale avec compatibilité asynchrone

Date de recherche : 10 septembre 2026. Ce lot applique l’ICP et le pipeline existants à des
entreprises hors de France. Il ne constitue ni une analyse énergétique de ces entreprises, ni une
autorisation de contact, ni une preuve que leurs données sont disponibles.

Les données structurées et reproductibles sont dans
[`data/international_async_20260910/`](data/international_async_20260910/). La phase de
préqualification a été exécutée avant le scoring ; aucune prise de contact, message ou adresse
personnelle n’a été créée.

## Méthode réutilisée et extension async

La méthodologie reste : faits publics sourcés → préqualification `CANDIDATE` / `UNCERTAIN` /
`REJECTED` → jugement Codex par dimension → somme déterministe sur 100 → gate factuel prioritaire.
Les dimensions fondamentales restent énergie, optimisation, données, valeur économique,
accessibilité commerciale, expertise énergie interne et fit Againward.

`async_compatibility` est ajoutée avec un poids de 8/100. Elle évalue la compatibilité probable
d’un **premier parcours commercial et de data scoping principalement écrit** ; elle n’évalue pas la
possibilité de supprimer une vérification terrain. Les notes s’appuient seulement sur signaux
publics identifiables : remote/distributed, documentation, portails/formulaires ou canaux écrits.
Sans preuve, la note est neutre ou basse avec confiance explicitement limitée ; elle n’est jamais
déduite du pays. Une très bonne note async ne compense ni absence de site industriel, ni faible
valeur, ni absence de donnée temporelle.

Les seuils inchangés sont : A `>=72`, B `65–71`, C `<65`, avec rejet si gate factuel. Les écarts de
un à trois points ne sont pas significatifs. Le classement ci-dessous sert donc aussi de guide de
recherche et non d’automate de vente.

## Liste priorisée

| Rang pratique | Entreprise | Pays | Activité / taille publique | Score / priorité | Async : signal et confiance | Fonction cible |
|---:|---|---|---|---:|---|---|
| 1 | Mackie’s of Scotland | Royaume-Uni | Glace, chocolat, emballage, froid et renouvelable intégrés ; ~80 employés | 75 / A | Documentation technique et canal email, mais aucune culture remote démontrée — **faible** | direction d’exploitation ; ingénierie/réfrigération |
| 2 | Vestre | Norvège / Suède | Mobilier urbain métal/bois ; 133 employés, deux usines | 71 / B | 27 marchés et postes commerciaux 100 % remote publiés — **moyenne** | Director of Operations / directeur d’usine ; production-maintenance |
| 3 | PaperShell AB | Suède | Composants bio-composites, production automatisée ; 24 collaborateurs | 68 / B | Remote lorsque possible, « digital approach », formulaire structuré — **élevée** | CEO/fondateur ou opérations ; production-maintenance |
| 4 | Notpla Limited | Royaume-Uni | Matériaux d’emballage, coating/extrusion ; 56 membres affichés | 62 / C | portail, formulaire et newsletter seulement — **faible à moyenne** | Technology & Operations / Process Engineering |
| 5 | Epishine | Suède | Cellules photovoltaïques organiques imprimées ; taille non publiée dans la source retenue | 60 / C | Hybrid Remote et contact email — **moyenne** | Manufacturing / Production Process Development |
| — | KTC BV | Pays-Bas | Ingrédients alimentaires et négoce ; taille non publique | 39 / **rejeté** | Fully remote/distributed explicite — **élevée** | aucune : hors ICP tant qu’un site propre n’est pas démontré |

Le rang pratique donne priorité aux combinaisons fit + signal async. Mackie’s reste la meilleure
opportunité analytique, mais pas la meilleure preuve d’une relation très asynchrone : une approche
écrite courte est défendable, sans éviter un appel de cadrage si nécessaire. PaperShell est le
meilleur compromis pour tester une approche écrite de bout en bout, mais le volume d’énergie et la
donnée doivent être confirmés avant de vendre un pilote.

## Dossiers à qualifier, dans l’ordre

### 1. Mackie’s of Scotland — Royaume-Uni — 75, priorité A

**Pourquoi le score est élevé.** Le site décrit une chaîne intégrée : production de glace et de
chocolat, fabrication d’emballages, éolien, solaire, biomasse et réfrigération ammoniaque. Le
procédé et les enjeux de mesure sont très clairement documentés. C’est également son principal
risque : la production, l’autoconsommation et la génération doivent être séparées avant de parler
d’un écart ou d’une économie.

**Signal async.** Le site public est riche en documentation et les candidatures passent par email,
mais ce n’est pas une preuve de remote-first ni de fonctionnement asynchrone opérationnel. Niveau
de confiance **faible**. Ce prospect ne doit pas être sélectionné seulement pour l’async.

**Sources.** [Environnement et procédés](https://www.mackies.co.uk/about-mackies/environment/),
[organisation et personnes](https://www.mackies.co.uk/about-mackies/people/),
[profil public et ordre de grandeur](https://uk.linkedin.com/company/mackie%27s-of-scotland).

**Question minimale.** « Un export horodaté du compteur de production/froid, distinct de la
génération renouvelable si possible, et un planning de fabrication peuvent-ils être partagés par
écrit ? »

### 2. Vestre — Norvège / Suède — 71, priorité B

**Pourquoi le score est élevé.** Vestre annonce 133 employés, 27 marchés et deux usines dont elle
contrôle plus de 90 % de la production. Le site indique une visibilité sur l’énergie et les déchets.
La fabrication interne et les process métal/bois sont une base crédible, mais la première mission
doit impérativement être ramenée à une seule usine autonome.

**Signal async.** L’activité internationale et des postes commerciaux publiés en 100 % remote sont
un signal raisonnable que collaboration à distance et anglais ne sont pas inhabituels. Il ne prouve
pas que la production fonctionne de façon asynchrone. Confiance **moyenne**.

**Sources.** [Entreprise, taille et marchés](https://www.vestre.com/about-us/company),
[usines, contrôle interne et vue énergie](https://vestre.com/no/faq/produksjon/hvor-produserer-dere-moblene),
[annonces remote publiques](https://www.linkedin.com/company/vestre).

**Question minimale.** « Une seule usine peut-elle exporter huit semaines d’énergie horodatée,
indiquer le périmètre du compteur et joindre un calendrier simple de production ? »

### 3. PaperShell AB — Suède — 68, priorité B

**Pourquoi le score est élevé.** PaperShell annonce 24 collaborateurs et une fabrication B2B
hautement automatisée en Suède. C’est une petite équipe, donc le budget et l’intensité énergétique
restent à établir ; en revanche, l’automatisation et la production sur mesure donnent une question
analytique plausible si une cadence existe.

**Signal async.** Sa page carrière mentionne explicitement le travail à distance lorsque possible,
une approche numérique et un formulaire de contact structuré. Confiance **élevée** pour une entrée
commerciale écrite, pas pour une prestation sans aucun échange synchrone.

**Sources.** [Production automatisée et effectif](https://careers.papershell.se/jobs),
[politique de flexibilité numérique et formulaire](https://papershell.se/careers/).

**Question minimale.** « Le site de Tibro peut-il fournir huit semaines de puissance ou énergie,
plus un indicateur simple de cadence ou d’ordres de fabrication ? »

### 4. Notpla — Royaume-Uni — 62, priorité C

**Pourquoi le score reste limité.** L’entreprise affiche 56 membres et recrute pour coating et
extrusion. Le signal de procédé est réel, mais le niveau de production stabilisée, le compteur et
l’autonomie opérationnelle ne sont pas publics. Cela justifie l’enrichissement avant contact, non
une proposition directe.

**Signal async.** Portail de recrutement, formulaire et newsletter : c’est une ouverture digitale,
pas une preuve de culture async. Confiance **faible à moyenne**.

**Sources.** [Entreprise et équipe](https://www.notpla.com/company),
[postes coating/extrusion](https://notpla.jobs.personio.com/).

### 5. Epishine — Suède — 60, priorité C

**Pourquoi le score reste limité.** Le site confirme siège et fabrication à Linköping, et associe
ses recrutements à l’impression/coating. La question peut être bonne si le procédé est devenu
répétitif ; la taille, l’échelle énergétique, le compteur et le planning ne sont pas documentés.

**Signal async.** Les candidatures Hybrid Remote et le contact écrit sont un signal de flexibilité
numérique, mais pas d’async-first. Confiance **moyenne**.

**Source.** [Carrières, Hybrid Remote et fabrication](https://www.epishine.com/career).

### Rejet contrôlé : KTC BV — Pays-Bas — 39, rejeté

KTC BV est l’anti-exemple utile : sa page carrière dit explicitement fully remote/distributed,
avec des collègues sur plusieurs continents et une grande autonomie. Le signal async est donc
**élevé**, mais la source retenue ne démontre ni usine propre ni procédé industriel correspondant à
l’ICP. Le gate factuel l’emporte sur son score async.

**Source.** [KTC BV careers](https://www.ktcingredients.com/careers/).

## Limites et prochaine action légitime

Aucun des cinq candidats retenus ne satisfait publiquement le gate de proposition de pilote :
compteur/site connu, huit semaines horodatées, contexte opérationnel et personne capable de
transmettre les données. Une prise de contact ne doit donc jamais supposer le problème, l’économie
ni la disponibilité des données. Pour les trois premiers, la seule action autorisée par ce dossier
est une qualification écrite courte autour de cette question de faisabilité ; l’envoi lui-même reste
soumis au contrôle d’opposition et aux règles applicables.
