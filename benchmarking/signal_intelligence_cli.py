from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from .physical_expertise import BenchmarkError
from .signal_deterministic_baseline import (
    deterministic_baseline_response,
    run_deterministic_baseline_suite,
)
from .signal_intelligence import (
    SignalBenchmarkError,
    aggregate_scorecards,
    audit_private_suite,
    finalize_signal_run,
    null_baseline_response,
    prepare_signal_run,
    reveal_signal_followups,
    run_null_baseline_suite,
    score_signal_run,
    validate_signal_case,
    validate_signal_response,
    verify_signal_run,
)
from .signal_intelligence_generator import generate_suite


def _read_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SignalBenchmarkError(f"{path} doit contenir un objet JSON")
    return payload


def _print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="INDICIA Signal Intelligence Benchmark V2."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    generate = commands.add_parser("generate-suite", help="Générer un corpus privé reproductible.")
    generate.add_argument("output_directory")
    generate.add_argument("--seed", type=int, default=260902)
    generate.add_argument("--profile", choices=("smoke", "full"), default="full")
    generate.add_argument("--replicates", type=int, default=1)

    validate_case = commands.add_parser("validate-case", help="Valider un cas sans lire sa vérité.")
    validate_case.add_argument("case_directory")

    audit = commands.add_parser("audit-suite", help="Auditer en privé toute la suite, vérité incluse.")
    audit.add_argument("suite_directory")
    audit.add_argument("--output")

    prepare = commands.add_parser("prepare", help="Préparer un run aveugle V2.")
    prepare.add_argument("case_directory")
    prepare.add_argument("runs_directory")
    prepare.add_argument("--repository", default=".")
    prepare.add_argument("--system-ref", default="HEAD")
    prepare.add_argument("--run-id")
    prepare.add_argument("--run-index", type=int, default=1)
    prepare.add_argument("--model", required=True)
    prepare.add_argument("--reasoning-effort", required=True)
    prepare.add_argument(
        "--variant",
        choices=("NULL_BASELINE", "DETERMINISTIC", "AGENTIC", "HUMAN"),
        required=True,
    )

    ask = commands.add_parser("ask", help="Soumettre une demande à l'oracle privé.")
    ask.add_argument("run_directory")
    ask.add_argument("case_directory")
    ask.add_argument("requests_json")

    validate_response = commands.add_parser("validate-response", help="Valider une réponse V2.")
    validate_response.add_argument("response_json")
    validate_response.add_argument("--case-id")

    finalize = commands.add_parser("finalize", help="Verrouiller une réponse sans lire la vérité.")
    finalize.add_argument("run_directory")
    finalize.add_argument("response_json")
    finalize.add_argument("--repository")

    verify = commands.add_parser("verify", help="Vérifier l'intégrité d'un run V2.")
    verify.add_argument("run_directory")
    verify.add_argument("--repository")

    score = commands.add_parser("score", help="Scorer un run finalisé avec la vérité privée.")
    score.add_argument("run_directory")
    score.add_argument("case_directory")

    aggregate = commands.add_parser("aggregate", help="Agréger des scorecards privées.")
    aggregate.add_argument("score_directory")
    aggregate.add_argument("--output")

    baseline = commands.add_parser("null-baseline", help="Produire la réponse nulle pré-enregistrée.")
    baseline.add_argument("case_directory")
    baseline.add_argument("output_json")
    run_baseline = commands.add_parser(
        "run-null-suite", help="Exécuter la baseline nulle sur une suite privée complète."
    )
    run_baseline.add_argument("suite_directory")
    run_baseline.add_argument("runs_directory")
    run_baseline.add_argument("--repository", default=".")
    run_baseline.add_argument("--system-ref", default="HEAD")
    run_baseline.add_argument(
        "--stage", action="append", choices=("DEV", "HOLDOUT"), dest="stages"
    )
    deterministic = commands.add_parser(
        "deterministic-baseline",
        help="Produire le contrôle déterministe borné à la détection et aux motifs.",
    )
    deterministic.add_argument("case_directory")
    deterministic.add_argument("output_json")
    deterministic.add_argument(
        "--detection-method",
        choices=("unconditional", "production", "production_temperature"),
        default="production_temperature",
    )
    deterministic.add_argument(
        "--energy-method",
        choices=("unconditional", "production", "production_temperature"),
        default="production",
    )
    deterministic.add_argument(
        "--signature-method",
        choices=("magnitude", "pq", "morphology"),
        default="morphology",
    )
    run_deterministic = commands.add_parser(
        "run-deterministic-suite",
        help="Exécuter le contrôle déterministe sur une suite privée complète.",
    )
    run_deterministic.add_argument("suite_directory")
    run_deterministic.add_argument("runs_directory")
    run_deterministic.add_argument("--repository", default=".")
    run_deterministic.add_argument("--system-ref", default="HEAD")
    run_deterministic.add_argument(
        "--detection-method",
        choices=("unconditional", "production", "production_temperature"),
        default="production_temperature",
    )
    run_deterministic.add_argument(
        "--energy-method",
        choices=("unconditional", "production", "production_temperature"),
        default="production",
    )
    run_deterministic.add_argument(
        "--signature-method",
        choices=("magnitude", "pq", "morphology"),
        default="morphology",
    )
    run_deterministic.add_argument(
        "--stage", action="append", choices=("DEV", "HOLDOUT"), dest="stages"
    )
    run_deterministic.add_argument(
        "--tier", action="append", choices=("L0_E15", "L1_PQ1", "L2_EDGE"), dest="tiers"
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "generate-suite":
            suite = generate_suite(
                args.output_directory,
                seed=args.seed,
                profile=args.profile,
                replicates=args.replicates,
            )
            _print({
                "status": "generated",
                "output_directory": str(Path(args.output_directory).resolve()),
                "profile": suite["profile"],
                "case_count": suite["case_count"],
                "replicates": suite["replicates"],
                "measurement_tiers": suite["measurement_tiers"],
            })
        elif args.command == "validate-case":
            validated = validate_signal_case(args.case_directory)
            manifest = validated["manifest"]
            _print({
                "status": "valid",
                "case_id": manifest["case_id"],
                "stage": manifest["stage"],
                "sector": manifest["sector"],
                "measurement_tier": manifest["measurement_tier"],
                "ground_truth_read": False,
            })
        elif args.command == "audit-suite":
            report = audit_private_suite(args.suite_directory)
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print(report)
        elif args.command == "prepare":
            run = prepare_signal_run(
                args.case_directory,
                args.runs_directory,
                repository=args.repository,
                system_ref=args.system_ref,
                model=args.model,
                reasoning_effort=args.reasoning_effort,
                variant=args.variant,
                run_id=args.run_id,
                run_index=args.run_index,
            )
            _print({"status": "prepared", "run_directory": str(run)})
        elif args.command == "ask":
            _print(reveal_signal_followups(args.run_directory, args.case_directory, args.requests_json))
        elif args.command == "validate-response":
            validate_signal_response(_read_json(args.response_json), expected_case_id=args.case_id)
            _print({"status": "valid"})
        elif args.command == "finalize":
            _print(finalize_signal_run(args.run_directory, args.response_json, repository=args.repository))
        elif args.command == "verify":
            _print(verify_signal_run(args.run_directory, repository=args.repository))
        elif args.command == "score":
            _print(score_signal_run(args.run_directory, args.case_directory))
        elif args.command == "aggregate":
            report = aggregate_scorecards(args.score_directory)
            if args.output:
                output = Path(args.output)
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print(report)
        elif args.command == "null-baseline":
            response = null_baseline_response(args.case_directory)
            output = Path(args.output_json)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print({"status": "written", "output": str(output.resolve())})
        elif args.command == "run-null-suite":
            result = run_null_baseline_suite(
                args.suite_directory,
                args.runs_directory,
                repository=args.repository,
                system_ref=args.system_ref,
                stages=tuple(args.stages or ("DEV", "HOLDOUT")),
            )
            _print({
                "status": "completed",
                "baseline": result["baseline"],
                "case_count": result["case_count"],
                "mean_score": result["aggregate"]["overall"]["mean_score"],
                "results": str((Path(args.runs_directory).resolve() / "NULL_BASELINE_RESULTS.json")),
            })
        elif args.command == "deterministic-baseline":
            response = deterministic_baseline_response(
                args.case_directory,
                detection_method=args.detection_method,
                energy_method=args.energy_method,
                signature_method=args.signature_method,
            )
            output = Path(args.output_json)
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(response, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            _print({"status": "written", "output": str(output.resolve())})
        elif args.command == "run-deterministic-suite":
            result = run_deterministic_baseline_suite(
                args.suite_directory,
                args.runs_directory,
                repository=args.repository,
                system_ref=args.system_ref,
                stages=tuple(args.stages or ("DEV", "HOLDOUT")),
                measurement_tiers=tuple(args.tiers or ("L0_E15", "L1_PQ1", "L2_EDGE")),
                detection_method=args.detection_method,
                energy_method=args.energy_method,
                signature_method=args.signature_method,
            )
            _print({
                "status": "completed",
                "baseline": result["baseline"],
                "case_count": result["case_count"],
                "mean_score": result["aggregate"]["overall"]["mean_score"],
                "results": str(
                    Path(args.runs_directory).resolve() / "DETERMINISTIC_BASELINE_RESULTS.json"
                ),
            })
    except (SignalBenchmarkError, BenchmarkError, FileExistsError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
