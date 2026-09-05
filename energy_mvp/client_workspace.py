from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .intake import intake_template
from .privacy import POLICY_VERSION, RETENTION_SCHEMA, REVIEW_SCHEMA


WORKSPACE_DIRECTORIES = (
    "incoming", "privacy", "sanitized", "processed", "scratch", "outputs",
    "contracts", "billing", "retained_derived",
)


def create_client_workspace(
    identifier: str, *, root: str | Path = "workspaces", synthetic: bool = False
) -> dict[str, Any]:
    """Create an isolated workspace without inspecting any client content."""

    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", identifier):
        raise ValueError(
            "L'identifiant doit contenir 1 a 64 caracteres ASCII: lettres, chiffres, _ ou -."
        )
    root_path = Path(root)
    target = root_path / identifier
    if target.exists():
        raise FileExistsError(
            f"Le workspace existe deja et ne sera pas modifie: {target}"
        )
    target.mkdir(parents=True)
    for directory in WORKSPACE_DIRECTORIES:
        (target / directory).mkdir()
    (target / "privacy" / "candidate").mkdir()

    manifest = {
        "schema_version": 3,
        "workspace_id": identifier,
        "case_kind": "SYNTHETIC" if synthetic else "REAL_CLIENT",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_input" if synthetic else "awaiting_privacy_review",
        "paths": {
            "incoming": "incoming/",
            "privacy": "privacy/",
            "privacy_candidate": "privacy/candidate/",
            "sanitized": "sanitized/",
            "processed": "processed/",
            "scratch": "scratch/",
            "outputs": "outputs/",
            "retained_derived": "retained_derived/",
            "privacy_manifest": "privacy/privacy_manifest.json",
            "lifecycle": "processed/investigation_state.json",
            "client_questions": "processed/questions.json",
            "human_review": "processed/human_review.json",
        },
        "privacy": {
            "required": not synthetic,
            "policy_version": POLICY_VERSION,
            "codex_first_semantic_reader": True,
            "approved_for_analysis": bool(synthetic),
        },
        "retention": {
            "configured": False,
            "derived_retention_authorized": False,
            "policy": "privacy/retention_policy.json",
        },
        "investigation_rules": {
            "ground_truth_available": False,
            "automatic_signals_are_candidates": True,
            "human_review_required": True,
        },
    }
    (target / "workspace.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (target / "intake.json").write_text(
        json.dumps(intake_template(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    review_template = {
        "schema_version": REVIEW_SCHEMA,
        "policy_version": POLICY_VERSION,
        "workspace_id": identifier,
        "received_at_utc": None,
        "status": "PASS_OR_SANITIZED_OR_BLOCKED",
        "codex_semantic_review": {
            "completed": False,
            "first_substantive_reader_attested": False,
        },
        "detected_categories": [],
        "files": [],
        "blocked_reasons": [],
    }
    (target / "privacy" / "CODEX_PRIVACY_REVIEW_TEMPLATE.json").write_text(
        json.dumps(review_template, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (target / "privacy" / "RETENTION_POLICY_TEMPLATE.json").write_text(
        json.dumps({
            "schema_version": RETENTION_SCHEMA,
            "configured": False,
            "purge_after_utc": None,
            "mission_closed": False,
            "derived_retention_authorized": False,
            "retained_paths": [],
            "retained_derived_paths": [],
        }, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (target / "README.md").write_text(
        "# Workspace d'analyse\n\n"
        "1. Completer `intake.json` avec le client.\n"
        "2. Placer le depot recu dans `incoming/` sans l'analyser.\n"
        "3. Codex lit le brut en premier et produit la privacy review/candidat.\n"
        "4. Valider avec `python manage_investigation.py privacy-validate . privacy/review.json`.\n"
        "5. Lancer l'intake uniquement depuis `sanitized/` apres `PRIVACY_CLEARED`.\n"
        "6. Piloter le dossier avec `python manage_investigation.py status .`.\n"
        "7. Conserver l'etat, les questions et la revue humaine dans `processed/`.\n"
        "8. Utiliser `scratch/` pour les tests ad hoc de Codex.\n"
        "9. Ecrire les livrables finaux et graphiques dans `outputs/`.\n"
        "10. Faire completer `processed/human_review.json` avant toute livraison.\n"
        "11. Configurer puis executer la purge contractuelle de fin de mission.\n\n"
        "Aucun signal automatique n'est une opportunite confirmee. Les donnees brutes "
        "ne deviennent jamais une source analytique avant clearance privacy.\n",
        encoding="utf-8",
    )
    return manifest
