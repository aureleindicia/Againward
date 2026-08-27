from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


WORKSPACE_DIRECTORIES = ("input", "processed", "scratch", "outputs")


def create_client_workspace(
    identifier: str, *, root: str | Path = "workspaces"
) -> dict[str, Any]:
    """Cree un espace local vide sans analyser, copier ou televerser de donnees."""

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

    manifest = {
        "schema_version": 1,
        "workspace_id": identifier,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "awaiting_input",
        "paths": {
            "input": "input/",
            "processed": "processed/",
            "scratch": "scratch/",
            "outputs": "outputs/",
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
    (target / "README.md").write_text(
        "# Workspace d'analyse\n\n"
        "1. Placer une copie locale des donnees brutes dans `input/`.\n"
        "2. Conserver toute transformation tracee dans `processed/`.\n"
        "3. Utiliser `scratch/` pour les tests ad hoc de Codex.\n"
        "4. Ecrire les JSON, graphiques et rapports dans `outputs/`.\n\n"
        "Aucun signal automatique n'est une opportunite confirmee. Les donnees brutes "
        "ne doivent jamais etre modifiees en place.\n",
        encoding="utf-8",
    )
    return manifest
