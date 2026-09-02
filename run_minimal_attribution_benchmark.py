from __future__ import annotations

import argparse
import json

from pathlib import Path

from benchmarking.minimal_attribution_benchmark import (
    compact_comparison,
    build_rnd_result,
    build_decision_examples,
    run_registry_corruption_experiment,
    scan_px201_fixture_sources,
    render_rnd_report,
    run_benchmark,
    run_falsification_suite,
    run_historical_anchor_drift_experiment,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Exécute le benchmark synthétique MinimalEvidenceAttribution."
    )
    parser.add_argument(
        "--output",
        default="workspace/minimal_attribution_benchmark",
        help="Répertoire des cas, locks, réponses et résultats.",
    )
    parser.add_argument(
        "--report-json",
        default=None,
        help="Chemin optionnel du résultat R&D consolidé machine-readable.",
    )
    parser.add_argument(
        "--report-md",
        default=None,
        help="Rapport Markdown optionnel rendu depuis le JSON consolidé.",
    )
    parser.add_argument(
        "--examples-json",
        default=None,
        help="Exemples synthétiques de décisions produits par le moteur.",
    )
    parser.add_argument(
        "--seeds",
        nargs="+",
        type=int,
        default=[101, 202, 303, 404, 505],
    )
    args = parser.parse_args()
    result = run_benchmark(args.output, seeds=args.seeds)
    falsifications = run_falsification_suite()
    Path(args.output, "falsifications.json").write_text(
        json.dumps(falsifications, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    robustness = run_registry_corruption_experiment()
    Path(args.output, "registry_corruption_experiment.json").write_text(
        json.dumps(robustness, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    anchor_drift = run_historical_anchor_drift_experiment()
    Path(args.output, "historical_anchor_drift_experiment.json").write_text(
        json.dumps(anchor_drift, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.report_json:
        consolidated = build_rnd_result(
            result,
            falsifications,
            robustness,
            anchor_drift,
            scan_px201_fixture_sources(Path.cwd()),
        )
        report_path = Path(args.report_json)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(consolidated, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        if args.report_md:
            markdown_path = Path(args.report_md)
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(render_rnd_report(consolidated), encoding="utf-8")
    if args.examples_json:
        examples_path = Path(args.examples_json)
        examples_path.parent.mkdir(parents=True, exist_ok=True)
        examples_path.write_text(
            json.dumps(build_decision_examples(), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(compact_comparison(result), ensure_ascii=False, indent=2))
    print(json.dumps({"falsification_counts": falsifications["counts"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
