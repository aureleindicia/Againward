"""Run deterministic synthetic Rental cases and optionally local timing checks."""
import argparse
import json
from benchmarking.rental import run_benchmark, benchmark_performance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    parser.add_argument("--performance", action="store_true")
    args = parser.parse_args()
    result = run_benchmark(args.output)
    if args.performance:
        from pathlib import Path
        from againward.core.artifact_store import write_json
        timings = benchmark_performance()
        write_json(Path(args.output) / "performance.json", timings)
        result["performance"] = timings
    print(json.dumps(result, indent=2))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
