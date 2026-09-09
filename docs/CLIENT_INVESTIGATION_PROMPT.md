# Prompt de lancement — dossier client INDICIA

Remplacer les chemins avant envoi. `AUTO` suffit normalement : les artefacts déterminent l'étape.
Ce prompt lance une investigation ; pour seulement l'auditer, demander explicitement une revue.
Utiliser une session normale, sans `/goal`, pour respecter l'arrêt après une demande bloquante.

```text
Utilise $indicia-client-workflow dans le dépôt courant INDICIA / Energy Analyzer.
Si le skill n'est pas proposé, lis .codex/skills/indicia-client-workflow/SKILL.md.

DOSSIER CLIENT : <CHEMIN_DOSSIER>
MODE : AUTO
NOUVELLES RÉPONSES : <CHEMIN_JSON | AUCUNE>
DÉPÔT BRUT SI NOUVEAU DOSSIER : <CHEMIN | AUCUN>

Lis le skill et les instructions applicables. Reconstruis le contexte depuis les
artefacts persistés du dossier et le dépôt, sans supposer de mémoire conversationnelle.
Le dépôt est autoritatif pour le code et le workflow. Consulte Download uniquement
pour les fichiers désignés ou nécessaires à ce dossier, en respectant le privacy gate.

Pour un dossier existant, commence par :
python manage_investigation.py status "<CHEMIN_DOSSIER>"

Suis le chemin canonique, l'état réel et la prochaine action. Pour un nouveau dossier,
applique d'abord le préalable contractuel puis le staging et le privacy gate du skill.
Ne réinitialise pas un dossier existant et ne crée aucune architecture parallèle.

Si des réponses sont fournies, enregistre seulement les réponses réellement nouvelles
selon le workflow, puis relis le statut avant de choisir REPRISE ou de t'arrêter.
Si WAITING_FOR_REQUIRED_INFORMATION subsiste ou survient ensuite, transmets les demandes
bloquantes restantes et leur utilité, écris « J'attends votre réponse », puis termine
immédiatement la session. Ne poursuis aucun calcul, rapport ou attente automatique.

Sinon, mène l'investigation, la falsification et les calculs traçables prévus par le skill.
Distingue observations, attribution, mécanisme, quantification et économies récupérables.
Finalise avec les limites réellement atteintes. Ne livre qu'après FINALIZABLE,
approbation humaine réelle et gate réussi conduisant à DELIVERABLE.
Si l'approbation humaine manque, présente les artefacts à relire puis arrête la session.
```

Les détails maintenus du workflow restent dans le skill et dans [CLIENT_WORKFLOW.md](CLIENT_WORKFLOW.md).
Le préalable contractuel provient de
[business/pilot_gtm/DATA_INTAKE_FOR_PILOTS.md](../business/pilot_gtm/DATA_INTAKE_FOR_PILOTS.md) ;
`status` expose désormais le gate de la policy extraite et revue ; la validation technique ne
constitue jamais un avis juridique. Voir [FINAL_CLIENT_MISSION.md](FINAL_CLIENT_MISSION.md).

Repères canoniques : les demandes et réponses sont dans `questions.json` ; la reprise analytique
suit l'état `RESUMING`. Le contexte externe ciblé est `/storage/emulated/0/Download`.
