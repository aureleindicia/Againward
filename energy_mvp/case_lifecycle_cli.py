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
from .client_lifecycle import (
    close_clarification_budget,
    complete_resume,
    initialize_client_lifecycle,
    mark_finalizable,
    publish_client_requests,
    record_canonical_answers,
    record_existing_data_exhaustion,
    continue_clarification,
)
from .workflow_paths import inspect_case_status
from .privacy import configure_retention, purge_client_case, validate_codex_privacy_review


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Gère le cycle questions, réponses et validation d'une investigation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser(
        "status", help="Afficher les dossiers, artefacts et la prochaine action sans rien modifier"
    )
    status.add_argument("case_directory")
    recovery = subparsers.add_parser("recover-artifacts", help="Recover an interrupted artifact transaction")
    recovery.add_argument("case_directory")
    questions = subparsers.add_parser("questions", help="Publier les prochaines questions minimales")
    questions.add_argument("case_directory")
    questions.add_argument("--investigation-name", default="investigation.json")
    answers = subparsers.add_parser("answers", help="Enregistrer des réponses client sans réécriture")
    answers.add_argument("case_directory")
    answers.add_argument("answers_json")
    gate = subparsers.add_parser("check", help="Évaluer le verrou de livraison")
    gate.add_argument("case_directory")
    for name, argument in (("rental-recalculate", "source_json"),
                           ("rental-review", "assessments_json"), ("rental-report", "synthesis_md")):
        command = subparsers.add_parser(name, help="Rental evidence revision, analyst review or report composition")
        command.add_argument("case_directory")
        command.add_argument(argument)
    archive = subparsers.add_parser(
        "next-cycle", help="Archiver un cycle entièrement répondu"
    )
    archive.add_argument("case_directory")
    privacy_validate = subparsers.add_parser("privacy-validate", help="Valider le privacy gate Codex et promouvoir sanitized/")
    privacy_validate.add_argument("case_directory")
    privacy_validate.add_argument("review_json")
    retention = subparsers.add_parser("retention-configure", help="Configurer la rétention contractuelle")
    retention.add_argument("case_directory")
    retention.add_argument("policy_json")
    stage = subparsers.add_parser("stage-incoming", help="Copier un dépôt réel après accord contractuel validé")
    stage.add_argument("case_directory")
    stage.add_argument("source_directory")
    contract = subparsers.add_parser("contract-record", help="Enregistrer extraction contractuelle et revue humaine fournies")
    contract.add_argument("case_directory")
    contract.add_argument("packet_json")
    close = subparsers.add_parser("mission-close", help="Clore la mission dans la rétention canonique")
    close.add_argument("case_directory")
    purge = subparsers.add_parser("purge", help="Exécuter la purge de fin de mission")
    purge.add_argument("case_directory")
    commands = (
        ("init", "Initialiser/migrer le cycle canonique"),
        ("data-exhausted", "Tracer les sources examinées"),
        ("publish-candidates", "Classer et publier les candidats"),
        ("record-answers", "Enregistrer les réponses typées"),
        ("complete-resume", "Clore une reprise"),
        ("close-budget", "Clore le budget"),
        ("continue-clarification", "Prolonger un cycle sur progrès documenté"),
        ("finalizable", "Marquer finalisable"),
    )
    for name, help_text in commands:
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("case_directory")
        if name == "data-exhausted":
            command.add_argument("analysis_inventory_ref")
            command.add_argument("reviewed_sources", nargs="+")
        elif name in {
            "publish-candidates",
            "record-answers",
            "complete-resume",
            "close-budget",
            "continue-clarification",
        }:
            command.add_argument("payload_json")
        elif name == "finalizable":
            command.add_argument("conclusion_ref")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command.startswith("rental-"):
            from againward.domains.rental.workflow import recalculate, record_assessments
            from againward.domains.rental.reporting import render_report
            if args.command == "rental-recalculate":
                result = recalculate(args.case_directory, args.source_json)
            elif args.command == "rental-review":
                packet = json.loads(Path(args.assessments_json).read_text(encoding="utf-8"))
                result = record_assessments(args.case_directory, packet["assessments"])
            else:
                result = render_report(args.case_directory, Path(args.synthesis_md).read_text(encoding="utf-8"))
        elif args.command == "status":
            result = inspect_case_status(args.case_directory)
        elif args.command == "recover-artifacts":
            from .artifact_store import recover_artifacts
            result = recover_artifacts(args.case_directory)
        elif args.command == "stage-incoming":
            from .privacy import stage_incoming_drop
            result = stage_incoming_drop(args.source_directory, args.case_directory)
        elif args.command == "contract-record":
            from .contract_policy import record_contract_policy
            packet = json.loads(Path(args.packet_json).read_text(encoding="utf-8"))
            result = record_contract_policy(args.case_directory, packet["policy"],
                semantic_extraction=packet["semantic_extraction"], human_review=packet.get("human_review"))
        elif args.command == "privacy-validate":
            from againward.entrypoints import get_case_domain
            result = validate_codex_privacy_review(args.case_directory, args.review_json,
                preservation_policy=get_case_domain(args.case_directory).privacy_preservation)
        elif args.command == "retention-configure":
            policy = json.loads(Path(args.policy_json).read_text(encoding="utf-8"))
            result = configure_retention(args.case_directory, policy)
        elif args.command == "mission-close":
            from .workflow_paths import resolve_case_layout
            root = resolve_case_layout(args.case_directory)["case_root"]
            policy = json.loads((root / "privacy/retention_policy.json").read_text(encoding="utf-8"))
            policy["mission_closed"] = True
            result = configure_retention(args.case_directory, policy)
        elif args.command == "purge":
            result = purge_client_case(args.case_directory)
        elif args.command == "init":
            result = initialize_client_lifecycle(args.case_directory)["client_lifecycle"]
        elif args.command == "data-exhausted":
            result = record_existing_data_exhaustion(
                args.case_directory,
                analysis_inventory_ref=args.analysis_inventory_ref,
                reviewed_sources=args.reviewed_sources,
            )["client_lifecycle"]
        elif args.command in {
            "publish-candidates",
            "record-answers",
            "complete-resume",
            "close-budget",
            "continue-clarification",
        }:
            source = json.loads(Path(args.payload_json).read_text(encoding="utf-8"))
            if args.command == "continue-clarification":
                result = continue_clarification(args.case_directory, **source)
            elif args.command == "publish-candidates":
                candidates = source.get("candidates", []) if isinstance(source, dict) else source
                branch = source.get("new_material_branch") if isinstance(source, dict) else None
                result = publish_client_requests(
                    args.case_directory,
                    candidates,
                    new_material_branch=branch,
                )
            elif args.command == "record-answers":
                answers = source.get("answers", []) if isinstance(source, dict) else source
                result = record_canonical_answers(args.case_directory, answers)
            elif args.command == "complete-resume":
                from againward.entrypoints import get_case_domain
                if get_case_domain(args.case_directory).name == "rental":
                    from againward.domains.rental.review_policy import validate_current_review
                    validate_current_review(args.case_directory)
                result = complete_resume(
                    args.case_directory,
                    recalculation_refs=source.get("recalculation_refs", []),
                    adversarial_review_ref=source.get("adversarial_review_ref", ""),
                    before_after=source.get("before_after", []),
                    terminal_limitations=source.get("terminal_limitations"),
                )["client_lifecycle"]
            else:
                limitations = (
                    source.get("terminal_limitations", [])
                    if isinstance(source, dict)
                    else source
                )
                result = close_clarification_budget(
                    args.case_directory,
                    terminal_limitations=limitations,
                )["client_lifecycle"]
        elif args.command == "finalizable":
            from againward.entrypoints import get_case_domain
            if get_case_domain(args.case_directory).name == "rental":
                from againward.domains.rental.review_policy import validate_current_review
                validate_current_review(args.case_directory)
            result = mark_finalizable(
                args.case_directory, conclusion_ref=args.conclusion_ref
            )["client_lifecycle"]
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
            from againward.core.delivery import evaluate_delivery_gate as domain_delivery_gate
            from againward.entrypoints import get_case_domain
            payload = domain_delivery_gate(args.case_directory, policy=get_case_domain(args.case_directory).delivery_policy())
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
