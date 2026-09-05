"""CLI locale Goal C : rend un rapport à partir d'un cas et d'un narratif Codex."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from client_delivery import generate_client_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Rend le PDF client Goal C depuis les états Goal A/B.")
    parser.add_argument("case_directory", help="Dossier client Goal A/B")
    parser.add_argument("narrative_json", help="Narratif client Codex, sans nombres libres")
    parser.add_argument("--output-directory", help="Répertoire de livraison; défaut : outputs/client_report")
    args = parser.parse_args()
    narrative = json.loads(Path(args.narrative_json).read_text(encoding="utf-8"))
    result = generate_client_report(args.case_directory, narrative, output_directory=args.output_directory)
    print(json.dumps({"pdf": result["pdf_path"], "pages": result["page_count"], "claim_validation": "passed"}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
