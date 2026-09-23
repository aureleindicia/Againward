"""Run the synthetic Rental privacy policy and source-routing benchmark."""
import argparse
import json
from pathlib import Path

from benchmarking.rental_privacy import run_privacy_benchmark


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_privacy_benchmark(args.output), indent=2))


if __name__ == "__main__":
    main()
