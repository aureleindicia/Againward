# Migration du workflow client

## Changement privacy

Ancien comportement : les workspaces standard lisaient `input/` et les cas Goal A copiaient les
originaux durablement dans `raw/` avant normalisation.

Nouveau comportement pour tout futur dossier réel :

```text
incoming/ temporaire → revue sémantique Codex → validation Python
→ sanitized/ canonique → intake/investigation
```

Le manifest de workspace porte désormais `case_kind`, `privacy.required`, la version de policy et
`approved_for_analysis`. Les anciens manifests sans ces champs sont classés
`PRIVACY_MIGRATION_REQUIRED`. Les commandes d’intake, investigation, findings, attribution,
économie, rapport et livraison les refusent ; aucune migration automatique n’est tentée.

## Procédure sûre pour un ancien dossier réel

1. Ne pas reprendre directement `input/` ou `raw/`.
2. Identifier les originaux et toutes les copies/dérivés déjà créés dans le workspace historique.
3. Créer un nouveau workspace v3 ou cas Goal A v2 avec un identifiant non personnel.
4. Replacer les sources nécessaires dans son `incoming/` par la commande de staging.
5. Exécuter le privacy gate complet et obtenir `PRIVACY_CLEARED`.
6. Relancer l’intake depuis `sanitized/`.
7. Réimporter uniquement les décisions, réponses et preuves dont la provenance peut être reliée à
   la source nettoyée, sans copier d’anciennes données personnelles.
8. Purger séparément l’ancien workspace selon l’autorisation et la politique applicables.

Cette migration reste manuelle parce qu’un programme ne peut pas déterminer de façon sûre si des
dérivés historiques contiennent encore une identité ou un secret.

## Compatibilité synthétique

Les fixtures, démos et benchmarks publics créés avec `synthetic=True` conservent le chemin
historique nécessaire à la reproductibilité et portent explicitement `case_kind: SYNTHETIC` et
`privacy.required: false`. Cet opt-out n’est pas disponible implicitement pour un dossier réel.

## Lifecycle questions/réponses

Les autorités restent `investigation_state.json.client_lifecycle` et `questions.json`.
Le chemin complet devient :

```text
AWAITING_PRIVACY_REVIEW → PRIVACY_CLEARED → ANALYZING
→ WAITING_FOR_REQUIRED_INFORMATION → RESUMING → ANALYZING
→ FINALIZABLE → DELIVERABLE → PURGED
```

`PRIVACY_BLOCKED` est fail-closed. Deux cycles de clarification maximum restent appliqués. Les
adaptateurs historiques Goal A/Goal B et MinimalEvidenceAttribution continuent de déléguer au
lifecycle canonique après clearance.

Vérifier un dossier sans l’écrire avec :

```sh
python manage_investigation.py status <dossier>
```
