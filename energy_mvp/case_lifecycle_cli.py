from __future__ import annotations

import argparse
import json
import sys

from .case_lifecycle import (
    archive_answered_question_cycle,
    evaluate_delivery_gate,
    publish_minimum_questions,
    record_client_answers,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gère le cycle questions, réponses et validation d'une investigation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    questions = subparsers.add_parser("questions", help="Publier les prochaines questions minimales")
    questions.add_argument("case_directory")
    questions.add_argument("--investigation-name", default="investigation.json")
    answers = subparsers.add_parser("answers", help="Enregistrer des réponses client sans réécriture")
    answers.add_argument("case_directory")
    answers.add_argument("answers_json")
    gate = subparsers.add_parser("check", help="Évaluer le verrou de livraison")
    gate.add_argument("case_directory")
    archive = subparsers.add_parser(
        "next-cycle", help="Archiver un cycle entièrement répondu"
    )
    archive.add_argument("case_directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "questions":
            payload = publish_minimum_questions(
                args.case_directory, investigation_name=args.investigation_name
            )
            result = {"published_questions": len(payload["questions"])}
        elif args.command == "answers":
            payload = record_client_answers(args.case_directory, args.answers_json)
            result = {"recorded_responses": len(payload["responses"])}
        elif args.command == "next-cycle":
            target = archive_answered_question_cycle(args.case_directory)
            result = {"archived_cycle": str(target)}
        else:
            payload = evaluate_delivery_gate(args.case_directory)
            result = {
                "status": payload["status"],
                "blocking_reasons": payload["blocking_reasons"],
            }
    except (OSError, ValueError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if args.command != "check" or payload["ready_for_delivery"] else 3


if __name__ == "__main__":
    raise SystemExit(main())
