#!/usr/bin/env python3
"""CLI légère pour préparer un dossier client sans lancer de diagnostic."""
from __future__ import annotations

import argparse
import json
import sys

from client_intake_pipeline import create_client_case, ingest_client_drop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventorie et normalise un dossier client hétérogène, sans diagnostic automatique."
    )
    parser.add_argument("case_id", help="Identifiant local sûr du cas client")
    parser.add_argument("raw_drop", help="Dossier source fourni par le client (inchangé)")
    parser.add_argument("--root", default="client_cases", help="Racine locale des cas isolés")
    args = parser.parse_args(argv)
    try:
        manifest = create_client_case(args.case_id, root=args.root)
        canonical = ingest_client_drop(args.raw_drop, f"{args.root}/{args.case_id}")
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "case_id": manifest["case_id"],
        "status": "ready_for_codex_first_pass",
        "datasets": len(canonical["available_datasets"]),
        "material_ambiguities": len(canonical["unresolved_material_ambiguities"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
