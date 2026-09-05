#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from energy_mvp.client_workspace import create_client_workspace
from energy_mvp.privacy import stage_incoming_drop


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cree un workspace client local et isole, sans toucher aux donnees."
    )
    parser.add_argument("identifier", help="Identifiant local court, par exemple usine_demo")
    parser.add_argument("--root", default="workspaces", help="Racine des workspaces")
    parser.add_argument(
        "--incoming",
        help="Dossier reçu à copier sans lecture dans incoming/ immédiatement après création",
    )
    args = parser.parse_args()
    try:
        manifest = create_client_workspace(args.identifier, root=args.root)
        receipt = None
        if args.incoming:
            receipt = stage_incoming_drop(
                args.incoming, Path(args.root) / args.identifier
            )
    except (ValueError, FileExistsError, OSError) as exc:
        parser.error(str(exc))
    print(f"Workspace cree: {args.root}/{manifest['workspace_id']}")
    if receipt is not None:
        print(f"Depot temporaire place dans incoming/: {receipt['file_count']} fichier(s).")
    else:
        print("Placez le dépôt reçu dans incoming/ sans en lire le contenu.")
    print("Prochaine étape obligatoire: privacy gate sémantique par Codex, puis validation Python.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
