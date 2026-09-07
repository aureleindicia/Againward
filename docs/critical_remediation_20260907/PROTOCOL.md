# Protocole gelé avant correction

Référence moteur : 55eaaf30224a66cfec22aa701e05a2ebbad2f1ad.
Suite avant : 410 tests, sources tests/ et prospecting/tests/.

Aucun générateur historique, vérité ou critère historique ne sera modifié.
Les 14 cas aveugles conservent seeds 700+i, IoU >=0,25, type exact ; un tableau
sans contrainte de type est publié séparément (jamais substitué au score historique).
Les 20 scénarios démo conservent seeds 1/7/42 et 101 sans anomalies, IoU >=0,30.

Les contre-exemples nouveaux (capture.py, figé par SHA-256 dans results.json)
utilisent 90 jours, 15 minutes, seeds 103/211/307. Acceptation :
- hausses 10→20 et 10→12, baisse : candidat de niveau persistant ;
- rampe : pente, sans marche fictive au même instant ;
- hausse temporaire : retour identifié, pas permanence inventée ;
- production/météo expliquées, bruit et semaine normale : pas de faux finding ;
- cycle historique régulier : ne pas présenter comme changement nouveau ;
- trou de huit jours : pas d'imputation ou de changement inventé.
On publie les événements et dates même lorsque la typologie historique les pénalise.

Priorité quantification : bilan signé et aire positive sont deux estimands différents.
Pas d'intervalle de confiance à partir de l'écart entre modèles. Refus d'une estimation
lorsque le support ou les hypothèses manquent ; fourchette de sensibilité seulement
sur les mêmes mesures et baselines déclarées défendables par l'analyste.

End-to-end : distinguer candidats, hypothèses rejetées, constats retenus, abstentions,
quantifications et gate humain. Les décisions écrites dans des tests par le développeur
ne sont pas une performance agentique. Toute exécution par cette session est non aveugle.
Sans sessions modèle indépendantes exécutées, qualité agentique comparative = NOT_MEASURED,
jamais un score simulé. Le harnais doit néanmoins scorer des sorties réellement fournies,
refuser les omissions et préserver les engagements avant accès à la vérité.
