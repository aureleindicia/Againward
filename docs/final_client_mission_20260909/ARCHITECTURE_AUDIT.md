# Audit préalable — mission client finale

Spécification lue intégralement : `/storage/emulated/0/Download/AGAINWARD_FINAL_CLIENT_MISSION_GOAL.md`.
Référence du code avant modification : `82dcb54`. Les deux fichiers locaux non suivis et les stashes ne font pas partie de cette mission.

| Domaine | État avant modification | Autorité à conserver / gap |
|---|---|---|
| Qualification sans données réelles | PARTIAL | Documenté dans DATA_INTAKE_FOR_PILOTS et le skill ; pas de verrou logiciel au staging |
| Contract policy | MISSING | contracts/ existe, mais pas de politique structurée ni de revue liée à son contenu |
| Intake / privacy | EXISTING | privacy.py, stage_incoming_drop, post-check Codex-first, sanitized et lineage ; ajouter contrôle contractuel aux entrées |
| Lifecycle | EXISTING | client_lifecycle.py, questions.json, WAITING, FINALIZABLE / DELIVERABLE ; aucun nouvel automate à créer |
| Evidence / findings / falsification | EXISTING | contrats Evidence Plane, provenance, plafonds d’attribution et revue contradictoire conservés |
| Économie / Value Map | EXISTING | même état canonique, calculs revalidés, catégories non additives, revue humaine liée à la carte |
| Présentation PDF | PARTIAL | modèle et validation des claims utiles ; _render_pages impose une composition unique et render_client_report_pdf limite à huit pages |
| Composition éditoriale libre | MISSING | plan de composition fourni par l’agent, composants, références et contrôle du contenu après revue à ajouter |
| Pilot learning | PARTIAL | métriques et jugements sourcés existants ; manque post-mortem complet, typologie des énoncés et statut confidentiel |
| Dérivés retenus | PARTIAL | contrôle de colonnes et revue de réidentification existent ; pas de whitelist de projection liée à une finalité contractuelle |
| Purge | PARTIAL | parcours deny-by-default, reçu et blocage PURGED existent ; contracts/ et billing/ survivent actuellement sans liste contractuelle explicite |
| Ancien renderer | REDUNDANT à terme | conserver les validations et primitives utiles ; retirer le rôle nominal de la composition rigide après validation de son remplacement |

## Périmètre de correction

Étendre les gates existants, la rétention/purge existante et pilot_learning.py. Le plan de rapport sera un plan de composition de contenu autorisé, pas un second registre de findings/économie. Aucun détecteur ni critère de benchmark ne doit être ajusté. Les fixtures de confidentialité qui simulent des clients réels devront fournir le nouvel accord synthétique requis ; ne pas transformer ces cas en exceptions de production.

## Limites de garantie à maintenir

Le contrôle porte sur les entrées supportées. Un utilisateur avec accès au système de fichiers peut toujours copier un fichier hors du workflow ; aucun programme local ne peut honnêtement garantir le contraire. Une revue structurée n’est pas une qualification juridique. Aucun contrôle de désidentification ne crée un droit contractuel. La beauté du PDF ne renforce pas sa preuve.
