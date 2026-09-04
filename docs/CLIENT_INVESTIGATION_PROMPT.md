# Prompt standard de production — dossier client INDICIA

Copier le bloc et remplacer `<CHEMIN_DOSSIER_CLIENT>` si connu. Ce n'est pas un `/goal`.

```text
Utilise la skill $indicia-client-workflow et travaille dans le dépôt courant INDICIA / Energy Analyzer.

Dossier client : <CHEMIN_DOSSIER_CLIENT>. Si le placeholder subsiste, localise le dossier pertinent dans le dépôt et Download; ne demande le chemin que si le mauvais choix reste un risque réel.
MODE : <AUTO | INITIAL | REPRISE>
Nouvelles réponses : <CHEMIN_JSON | AUCUNE>

Repars sans contexte conversationnel. Lis intégralement le skill et suis les sources de vérité qu'il
indique. Reconstruis le contexte depuis le dépôt courant et tout `/storage/emulated/0/Download` :
les objectifs, handoffs, R&D, benchmarks et pièces client peuvent être répartis. Le dépôt est
autoritatif pour le code; Download est seulement contexte/entrée locale et ses données client ne
doivent jamais être versionnées.

Commence par `python manage_investigation.py status <CHEMIN_DOSSIER_CLIENT>`. En `AUTO`, déduis le
mode des artefacts : `REPRISE` si `investigation_state.json.client_lifecycle.state == RESUMING`,
sinon `INITIAL`. Refuse un MODE explicite incompatible avec l'état. N'invente pas de workflow ou
de copie parallèle de `questions.json`.

En INITIAL, analyse exhaustivement les sources existantes, conduis l'investigation et ses calculs
Python, puis utilise le sélecteur canonique seulement si une information peut changer une décision
matérielle. En REPRISE, enregistre uniquement le fichier de réponses réellement reçu, avec sa
provenance, réintègre les preuves/EvidenceLedger, recalcule, réévalue et refais la review selon le
skill. Une absence de réponse n'est jamais une confirmation.

Respecte les frontières de claims et tous les invariants imposés par le code. Si le lifecycle passe
à `WAITING_FOR_REQUIRED_INFORMATION`, transmets les demandes minimales et leur utilité, indique que
tu attends une réponse, puis ARRÊTE COMPLÈTEMENT cette session. Sinon, finalise honnêtement avec les
limites atteintes; ne livre qu'après `FINALIZABLE` et validation humaine vers `DELIVERABLE`.
```
