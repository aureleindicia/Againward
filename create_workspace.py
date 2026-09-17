#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from againward.core.workspace import create_client_workspace
from againward.core.privacy import stage_incoming_drop
from againward.entrypoints import get_domain


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cree un workspace client local et isole, sans toucher aux donnees."
    )
    parser.add_argument("identifier", help="Identifiant local court, par exemple usine_demo")
    parser.add_argument("--root", default="workspaces", help="Racine des workspaces")
    parser.add_argument("--domain", default="energy", help="energy ou rental")
    parser.add_argument("--profile", help="Profil optionnel du domaine")
    parser.add_argument(
        "--incoming",
        help="Dossier reçu à copier sans lecture dans incoming/ immédiatement après création",
    )
    args = parser.parse_args()
    try:
        domain = get_domain(args.domain, profile=args.profile)
        manifest = create_client_workspace(args.identifier, root=args.root,
                                           domain_name=domain.name, intake_payload=domain.intake_template())
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
        print("Enregistrez d’abord la contract policy et sa revue humaine, puis utilisez manage_investigation.py stage-incoming.")
    print("Aucune donnée réelle avant accord validé ; ensuite privacy gate Codex et validation Python.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
