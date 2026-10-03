"""Run genuine source-unit model participant, then score frozen observations."""
import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    run = commands.add_parser("run")
    run.add_argument("public", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("--split", required=True, choices=("DEV", "ADVERSARIAL", "HOLDOUT"))
    run.add_argument("--model", required=True)
    run.add_argument("--timeout-seconds", type=int, default=180)
    score = commands.add_parser("score")
    score.add_argument("corpus", type=Path)
    score.add_argument("run", type=Path)
    audit = commands.add_parser("audit")
    audit.add_argument("run", type=Path)
    args = parser.parse_args()
    if args.action == "run":
        from benchmarking.semantic_participant import run_semantic_participant
        result = run_semantic_participant(args.public, args.output, split=args.split,
                                          model=args.model, timeout_seconds=args.timeout_seconds)
        view = {"split": result["split"], "cases": len(result["cases"]),
                "model": result["model"], "engine": result["engine"]}
    elif args.action == "score":
        from benchmarking.semantic_scoring import score_semantic_candidates
        result = score_semantic_candidates(args.corpus, args.run)
        view = result["metrics"]
    else:
        from benchmarking.semantic_preflight import audit_semantic_preflight
        result = audit_semantic_preflight(args.run)
        view = result["metrics"]
    print(json.dumps(view, indent=2))


if __name__ == "__main__":
    main()
