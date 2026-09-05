# Prompt standard de production — dossier client INDICIA

Copier ce bloc dans une nouvelle instance Codex et remplacer les placeholders connus. Ce n’est pas
un `/goal`.

```text
Utilise la skill $indicia-client-workflow et travaille uniquement dans le dépôt courant INDICIA / Energy Analyzer.

DOSSIER/WORKSPACE CLIENT : <CHEMIN_OU_A_CREER>
DEPOT BRUT A RECEVOIR : <CHEMIN_DU_DEPOT_OU_AUCUN>
MODE : <AUTO | INITIAL | REPRISE>
NOUVELLES REPONSES : <CHEMIN_JSON_OU_AUCUNE>

Considère cette session comme sans contexte préalable. Lis intégralement la skill, AGENTS.md et les
documents qu’elle rend obligatoires. Reconstruis le contexte depuis le dépôt ; consulte
`/storage/emulated/0/Download` seulement si nécessaire pour localiser des instructions ou le dépôt
explicitement placé en entrée.
Le dépôt courant est autoritatif pour le code. Ne versionne jamais de donnée client.

PRIVACY GATE OBLIGATOIRE

Pour tout dossier réel, Codex doit être la première étape qui lit et comprend le contenu brut. Si
le dossier n’existe pas, crée-le et stage le dépôt sans lecture avec la commande canonique. Si le
dossier existe, commence par :

python manage_investigation.py status <DOSSIER/WORKSPACE CLIENT>

Ne lance aucun intake, parseur métier, normalisation, calcul énergétique, recherche de finding ou
attribution avant PRIVACY_CLEARED. Même si tu penses connaître le contenu, inspecte d’abord tous les
fichiers incoming/ en tant que privacy gate.

Recherche personnes, emails, téléphones, matricules/identifiants individuels, texte libre personnel,
données RH/médicales et secrets. Supprime l’identité inutile. Si sa relation est utile, remplace-la
par un pseudonyme stable sans table de correspondance. Préserve exactement machines, compteurs,
lignes, sites, timestamps, unités, énergie, puissance, production, cycles, shifts, lots, références,
températures, maintenance et relations utiles à l’attribution. Ne fais aucune correction métier,
interpolation ou déduplication pendant ce gate.

Produis privacy/review.json et, pour SANITIZED, les candidats dans privacy/candidate/, sans recopier
une valeur retirée dans la review. Exécute ensuite :

python manage_investigation.py privacy-validate <DOSSIER> <DOSSIER>/privacy/review.json

Continue uniquement si privacy_manifest.json indique approved_for_analysis=true et si l’état est
PRIVACY_CLEARED. En PRIVACY_BLOCKED ou PRIVACY_MIGRATION_REQUIRED, explique la résolution minimale
nécessaire puis ARRÊTE COMPLÈTEMENT : n’exploite pas ce que tu as vu pour poursuivre l’analyse.

INVESTIGATION

Après clearance, lance l’intake exclusivement depuis sanitized/. En AUTO, utilise REPRISE seulement
si investigation_state.json.client_lifecycle.state == RESUMING, sinon INITIAL. Refuse un mode
explicite incompatible et n’invente aucune copie parallèle de questions.json.

En INITIAL, analyse exhaustivement toutes les sources déjà disponibles. Formule des observations et
hypothèses concurrentes, fais calculer chaque chiffre par Python, cherche à falsifier les pistes,
préserve la provenance et distingue strictement détection, signature, composant, attribution,
mécanisme et pronostic. Ne demande une information que si elle peut modifier matériellement preuve,
attribution, alternative, importance économique, priorité, action ou risque de fausse conclusion.
Demande le minimum ; préfère une micro-question ou observation ponctuelle à un export lourd de
valeur équivalente. Explique simplement ce que chaque demande confirmerait, infirmerait ou
départagerait.

En REPRISE, enregistre uniquement les réponses réellement reçues avec auteur/date/source/type.
Une déclaration opérateur n’est pas une validation terrain. Mets à jour les preuves, recalcule avec
Python, réévalue les huit dimensions du contrat, cherche les contradictions et refais la review.
Deux cycles maximum ; après épuisement, finalise honnêtement avec unknown, non identifiable ou
information insuffisante.

STOP ET FINALISATION

Si le lifecycle passe à WAITING_FOR_REQUIRED_INFORMATION, transmets les demandes minimales et leur
utilité, indique que tu attends une réponse, puis ARRÊTE COMPLÈTEMENT la session. N’invente aucune
réponse et ne continue pas à promouvoir les hypothèses suspendues.

Si aucune information supplémentaire ne justifie l’effort client, finalise normalement avec les
limites atteintes. Fais toujours la review adversariale, exige la revue humaine avant livraison et
ne présente ni surconsommation comme économie garantie, ni attribution comme mécanisme prouvé.

FIN DE MISSION

Applique la politique de rétention configurée. derived_retention_authorized=false par défaut.
Après clôture et échéance, exécute la purge canonique, vérifie PURGE_RECEIPT.json et ne qualifie
jamais partial_failure de succès. Ne reprends jamais analytiquement un dossier PURGED.
```
