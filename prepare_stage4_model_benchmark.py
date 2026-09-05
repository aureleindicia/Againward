#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys

from benchmarking.stage4_model_harness import prepare_model_benchmark


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prépare la matrice fort/petit/raw/Evidence Plane sans appeler de modèle."
    )
    parser.add_argument("case_directory")
    parser.add_argument("output_directory")
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--raw-source", required=True)
    args = parser.parse_args()
    try:
        result = prepare_model_benchmark(
            args.case_directory,
            args.output_directory,
            case_id=args.case_id,
            randomization_seed=args.seed,
            raw_source=args.raw_source,
        )
    except (OSError, ValueError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": result["status"], "condition_order": result["condition_order"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
