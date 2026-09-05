#!/usr/bin/env python3
"""Stage a real client drop, or run intake after privacy clearance."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from client_intake_pipeline import create_client_case, ingest_client_drop
from energy_mvp.privacy import stage_incoming_drop


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prépare un dossier client avec privacy gate obligatoire avant tout intake."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    stage = sub.add_parser("stage", help="Créer le cas et copier le dépôt dans incoming/ sans l'inspecter")
    stage.add_argument("case_id")
    stage.add_argument("raw_drop")
    stage.add_argument("--root", default="client_cases")
    intake = sub.add_parser("intake", help="Normaliser uniquement la source sanitized après clearance")
    intake.add_argument("case_directory")
    args = parser.parse_args(argv)
    try:
        if args.command == "stage":
            manifest = create_client_case(args.case_id, root=args.root)
            receipt = stage_incoming_drop(args.raw_drop, Path(args.root) / args.case_id)
            result = {
                "case_id": manifest["case_id"],
                "status": "AWAITING_PRIVACY_REVIEW",
                "files_staged": receipt["file_count"],
                "next_action": "CODEX_PRIVACY_GATE",
            }
        else:
            case = Path(args.case_directory)
            canonical = ingest_client_drop(case / "sanitized", case)
            result = {
                "case_id": case.name,
                "status": "ready_for_codex_first_pass",
                "datasets": len(canonical["available_datasets"]),
                "material_ambiguities": len(canonical["unresolved_material_ambiguities"]),
            }
    except (OSError, ValueError, FileExistsError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
