# Pre-diagnostic energetique agentique — donnees mensuelles

## 1. Resume executif

Aucune opportunite energetique n'est confirmee. Les totaux sont calculables, mais la granularite mensuelle interdit les conclusions nocturnes, horaires et de demarrage.

## 2. Donnees analysees

- 12 mesures couvrant 2026-01-01T00:00:00 -> 2027-01-01T00:00:00.
- Energie, production, tarif et une valeur de puissance par mois.

## 3. Qualite des donnees

Les douze lignes sont exploitables pour les totaux. La resolution, et non la proprete du fichier, constitue la limitation dominante.

## 4. Profil energetique

Les trois mois a production nulle totalisent 41 100,0 kWh, soit 7 192,50 EUR de cout associe observe.

## 5. Baseline

Aucune baseline validee n'est retenue : neuf mois actifs ne suffisent pas pour une calibration passe-vers-futur robuste avec variables contextuelles.

## 6. Investigations realisees

M01 consommation sans production, M02 puissance d'octobre, M03 intensite d'octobre.

## 7. Opportunites confirmees

Aucune.

## 8. Efficacite energetique

Octobre atteint 5,817 kWh/unite, soit 4,0 % au-dessus de la mediane. Ce signal reste insuffisamment etaye sans mix produit, jours ouvres et temperature.

## 9. Impact economique

Le cout des mois sans production est un cout observe, pas une economie. Aucun potentiel recuperable ni projection annuelle n'est publie.

## 10. Opportunites necessitant verification

Les questions ci-dessous ne sont posees que parce que M01 et M03 restent indeterminees; M02, deja rejetee, ne declenche aucune demande.

### M01 — prochaine verification minimale

- A demander : Pour chacun des trois mois a production nulle, confirmer en une ligne si le site etait ferme et quelles utilites devaient obligatoirement rester actives.
- Pourquoi : Cette reponse indique si l'energie correspond a un arret reel, a une activite non renseignee ou a des besoins incompressibles connus.
- Hypotheses departagees : charge potentiellement evitable pendant fermeture / charge legitime ou production manquante dans le fichier.
- Effort client : Environ 10 minutes avec le calendrier d'exploitation. (tres_faible).
- Attendu si l'hypothese est vraie : Si une charge evitable existe, le client confirmera une fermeture complete sans procede ni exigence de securite expliquant tout ou partie de la consommation.
- Cause physique : non etablie avec les donnees disponibles.

### M03 — prochaine verification minimale

- A demander : Indiquer si octobre avait un mix produit, un nombre de jours ouvres ou des horaires sensiblement differents d'un mois actif habituel, et lequel.
- Pourquoi : Ces trois facteurs simples peuvent expliquer le ratio mensuel sans degradation energetique et evitent une collecte instrumentee prematuree.
- Hypotheses departagees : degradation reelle de l'efficacite en octobre / effet normal du mix produit, des jours ouvres ou des horaires.
- Effort client : Environ 10 a 15 minutes avec le responsable de production. (tres_faible).
- Attendu si l'hypothese est vraie : Si la degradation est reelle, aucun changement operationnel important ne sera signale alors que l'intensite restera anormalement haute.
- Cause physique : non etablie avec les donnees disponibles.

## 11. Hypotheses rejetees importantes

M02 est rejetee : 198,0 kW en octobre ne permet pas d'affirmer un demarrage simultane sans heure ni duree.

## 12. Recommandations

1. Poser d'abord les deux questions minimales M01 et M03 ci-dessus.
2. Ne demander une courbe 15 minutes que si leurs reponses laissent une incertitude materielle et que l'enjeu justifie cet effort supplementaire.
3. Ne rien demander pour M02 : l'hypothese de demarrage est deja rejetee.
Aucune cause physique n'est etablie avec ces douze agregats mensuels.

## 13. Limites

Douze agregats mensuels, aucune temperature, aucun horaire, aucune mesure machine et aucune preuve de causalite.

## 14. Methodologie

Normalisation deterministe, controles de resolution, quantification Python, formulation d'hypotheses, recherche de contre-explications et review contradictoire Codex.
