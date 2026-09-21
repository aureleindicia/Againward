"""Generate, run without truth, then score actual synthetic document folders."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    generate = commands.add_parser("generate")
    generate.add_argument("output", type=Path)
    generate.add_argument("--split", choices=("DEV", "ADVERSARIAL", "HOLDOUT"), required=True)
    generate.add_argument("--seed", type=int, required=True)
    run = commands.add_parser("run")
    run.add_argument("public", type=Path)
    run.add_argument("output", type=Path)
    run.add_argument("--split", choices=("DEV", "ADVERSARIAL", "HOLDOUT"), required=True)
    run.add_argument("--submissions", type=Path)
    score = commands.add_parser("score")
    score.add_argument("corpus", type=Path)
    score.add_argument("run", type=Path)
    args = parser.parse_args()
    if args.command == "generate":
        from benchmarking.document_corpus import generate_corpus
        result = generate_corpus(args.output, split=args.split, seed=args.seed)
    elif args.command == "run":
        from benchmarking.document_runner import run_documents
        result = run_documents(args.public, args.output, submissions=args.submissions, split=args.split)
    else:
        from benchmarking.document_scoring import score_documents
        result = score_documents(args.corpus, args.run)
    print(json.dumps(result.get("metrics", result.get("case_ids", {k: v for k, v in result.items() if k != "cases"})), indent=2))


if __name__ == "__main__":
    main()
