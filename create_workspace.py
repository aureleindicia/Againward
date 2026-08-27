#!/usr/bin/env python3
from __future__ import annotations

import argparse

from energy_mvp.client_workspace import create_client_workspace


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cree un workspace client local et isole, sans toucher aux donnees."
    )
    parser.add_argument("identifier", help="Identifiant local court, par exemple usine_demo")
    parser.add_argument("--root", default="workspaces", help="Racine des workspaces")
    args = parser.parse_args()
    try:
        manifest = create_client_workspace(args.identifier, root=args.root)
    except (ValueError, FileExistsError, OSError) as exc:
        parser.error(str(exc))
    print(f"Workspace cree: {args.root}/{manifest['workspace_id']}")
    print("Placez une copie des donnees dans input/; Codex commencera par les inspecter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
