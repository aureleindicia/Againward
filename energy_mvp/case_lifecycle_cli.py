from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .case_lifecycle import (
    archive_answered_question_cycle,
    evaluate_delivery_gate,
    publish_minimum_questions,
    record_client_answers,
)
from .client_lifecycle import (initialize_client_lifecycle,record_existing_data_exhaustion,publish_client_requests,
    record_canonical_answers,complete_resume,close_clarification_budget,mark_finalizable)


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
    for name,help_text in (("init","Initialiser/migrer le cycle canonique"),("data-exhausted","Tracer les sources examinées"),
        ("publish-candidates","Classer et publier les candidats"),("record-answers","Enregistrer les réponses typées"),
        ("complete-resume","Clore une reprise"),("close-budget","Clore le budget"),("finalizable","Marquer finalisable")):
        command=subparsers.add_parser(name,help=help_text); command.add_argument("case_directory")
        if name=="data-exhausted": command.add_argument("analysis_inventory_ref"); command.add_argument("reviewed_sources",nargs="+")
        elif name in {"publish-candidates","record-answers","complete-resume","close-budget"}: command.add_argument("payload_json")
        elif name=="finalizable": command.add_argument("conclusion_ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "init": result=initialize_client_lifecycle(args.case_directory)["client_lifecycle"]
        elif args.command == "data-exhausted": result=record_existing_data_exhaustion(args.case_directory,analysis_inventory_ref=args.analysis_inventory_ref,reviewed_sources=args.reviewed_sources)["client_lifecycle"]
        elif args.command in {"publish-candidates","record-answers","complete-resume","close-budget"}:
            source=json.loads(Path(args.payload_json).read_text(encoding="utf-8"))
            if args.command=="publish-candidates": result=publish_client_requests(args.case_directory,source.get("candidates",source if isinstance(source,list) else []),new_material_branch=source.get("new_material_branch") if isinstance(source,dict) else None)
            elif args.command=="record-answers": result=record_canonical_answers(args.case_directory,source.get("answers",source if isinstance(source,list) else []))
            elif args.command=="complete-resume": result=complete_resume(args.case_directory,recalculation_refs=source.get("recalculation_refs",[]),adversarial_review_ref=source.get("adversarial_review_ref",""),before_after=source.get("before_after",[]),terminal_limitations=source.get("terminal_limitations"))["client_lifecycle"]
            else: result=close_clarification_budget(args.case_directory,terminal_limitations=source.get("terminal_limitations",source if isinstance(source,list) else []))["client_lifecycle"]
        elif args.command == "finalizable": result=mark_finalizable(args.case_directory,conclusion_ref=args.conclusion_ref)["client_lifecycle"]
        elif args.command == "questions":
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
