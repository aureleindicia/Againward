from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .physical_expertise import (
    DEFAULT_BASELINE_TAG,
    BenchmarkError,
    finalize_run,
    prepare_run,
    reveal_followups,
    validate_case_directory,
    validate_response,
    validate_scorecard,
    verify_run_integrity,
)


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkError(f"{path} doit contenir un objet JSON.")
    return payload


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Runner isolé du Physical Expertise Benchmark."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    validate_case = commands.add_parser("validate-case", help="Valider un cas privé.")
    validate_case.add_argument("case_directory")

    prepare = commands.add_parser("prepare", help="Préparer un run aveugle neuf.")
    prepare.add_argument("case_directory")
    prepare.add_argument("runs_directory")
    prepare.add_argument("--repository", default=".")
    prepare.add_argument("--system-ref", default=DEFAULT_BASELINE_TAG)
    prepare.add_argument("--run-id")
    prepare.add_argument("--run-index", type=int, default=1)
    prepare.add_argument("--model", required=True)
    prepare.add_argument("--reasoning-effort", required=True)

    ask = commands.add_parser("ask", help="Soumettre un cycle de demandes à l'oracle.")
    ask.add_argument("run_directory")
    ask.add_argument("case_directory")
    ask.add_argument("requests_json")

    validate_answer = commands.add_parser("validate-response", help="Valider une réponse.")
    validate_answer.add_argument("response_json")
    validate_answer.add_argument("--case-id")

    finalize = commands.add_parser("finalize", help="Sceller un run sans le scorer.")
    finalize.add_argument("run_directory")
    finalize.add_argument("response_json")
    finalize.add_argument("--repository")

    verify = commands.add_parser("verify", help="Vérifier l'intégrité d'un run.")
    verify.add_argument("run_directory")
    verify.add_argument("--repository")

    scorecard = commands.add_parser("validate-scorecard", help="Valider une scorecard externe.")
    scorecard.add_argument("scorecard_json")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    arguments = build_parser().parse_args(argv)
    try:
        if arguments.command == "validate-case":
            validated = validate_case_directory(arguments.case_directory)
            _print({
                "status": "valid",
                "case_id": validated["manifest"]["case_id"],
                "stage": validated["manifest"]["stage"],
                "initial_files": len(validated["initial_manifest"]),
                "ground_truth_read": False,
            })
        elif arguments.command == "prepare":
            run = prepare_run(
                arguments.case_directory,
                arguments.runs_directory,
                run_id=arguments.run_id,
                repository=arguments.repository,
                system_ref=arguments.system_ref,
                model=arguments.model,
                reasoning_effort=arguments.reasoning_effort,
                run_index=arguments.run_index,
            )
            _print({"status": "prepared", "run_directory": str(run)})
        elif arguments.command == "ask":
            _print(reveal_followups(
                arguments.run_directory,
                arguments.case_directory,
                arguments.requests_json,
            ))
        elif arguments.command == "validate-response":
            validate_response(_read_json(arguments.response_json), expected_case_id=arguments.case_id)
            _print({"status": "valid"})
        elif arguments.command == "finalize":
            _print(finalize_run(
                arguments.run_directory,
                arguments.response_json,
                repository=arguments.repository,
            ))
        elif arguments.command == "verify":
            _print(verify_run_integrity(
                arguments.run_directory,
                repository=arguments.repository,
            ))
        elif arguments.command == "validate-scorecard":
            validate_scorecard(_read_json(arguments.scorecard_json))
            _print({"status": "valid"})
    except (BenchmarkError, FileExistsError, json.JSONDecodeError, OSError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
