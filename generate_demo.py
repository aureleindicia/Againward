#!/usr/bin/env python3
from __future__ import annotations

import argparse

from energy_mvp.demo import SCENARIOS, generate_demo


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Genere un dataset industriel synthetique 15 minutes reproductible."
    )
    parser.add_argument("--output", default="examples/demo_15min.csv")
    parser.add_argument("--ground-truth", default="examples/demo_ground_truth.json")
    parser.add_argument("--days", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--scenario", choices=sorted(SCENARIOS), default="factory_variable")
    parser.add_argument("--without-data-issues", action="store_true")
    parser.add_argument("--without-anomalies", action="store_true")
    args = parser.parse_args()

    truth = generate_demo(
        args.output,
        args.ground_truth,
        days=args.days,
        seed=args.seed,
        scenario_name=args.scenario,
        include_data_issues=not args.without_data_issues,
        include_anomalies=not args.without_anomalies,
    )
    print(
        f"Dataset genere: {args.output} ({truth['written_rows']} lignes, "
        f"scenario={truth['scenario']}, seed={truth['seed']})"
    )
    print(f"Ground truth separee: {args.ground_truth}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
