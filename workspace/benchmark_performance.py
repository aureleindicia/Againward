#!/usr/bin/env python3
"""Benchmark progressif du chargeur standard-library dans l'environnement Termux."""

from __future__ import annotations

import argparse
import csv
import json
import resource
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from energy_mvp.analysis import analyze
from energy_mvp.io import load_data


def run_case(rows: int) -> dict[str, float | int]:
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / f"benchmark-{rows}.csv"
        started = time.perf_counter()
        timestamp = datetime(2026, 1, 1)
        with source.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(("timestamp", "energy_kwh", "production"))
            for index in range(rows):
                writer.writerow(
                    (
                        timestamp.isoformat(timespec="minutes"),
                        "0.25",
                        "1" if index % 3 else "0",
                    )
                )
                timestamp += timedelta(minutes=1)
        generation_seconds = time.perf_counter() - started
        file_size = source.stat().st_size

        started = time.perf_counter()
        data = load_data(source)
        load_seconds = time.perf_counter() - started
        started = time.perf_counter()
        result = analyze(data, source=str(source), default_tariff=0.175)
        analysis_seconds = time.perf_counter() - started
        if result.valid_rows != rows or result.total_energy_kwh != rows * 0.25:
            raise AssertionError("Le benchmark a produit un total numeriquement incorrect.")
        peak_rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
        return {
            "rows": rows,
            "file_size_bytes": file_size,
            "generation_seconds": generation_seconds,
            "load_seconds": load_seconds,
            "analysis_seconds": analysis_seconds,
            "rows_per_second_loading": rows / load_seconds,
            "peak_process_rss_mb": peak_rss_mb,
            "verified_total_energy_kwh": result.total_energy_kwh,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("sizes", nargs="*", type=int, default=[10_000, 100_000, 500_000])
    args = parser.parse_args()
    cases = []
    for size in args.sizes:
        if size <= 0:
            raise ValueError("Les tailles doivent etre positives.")
        result = run_case(size)
        cases.append(result)
        print(json.dumps(result, indent=2))
    payload = {
        "environment": "Android/Termux/Python standard library",
        "cases": cases,
        "interpretation": (
            "Conserver la stack standard-library tant que temps et memoire restent acceptables ; "
            "ne migrer vers Polars ou DuckDB qu'apres un besoin observe."
        ),
    }
    Path("reports/performance.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Benchmark ecrit: reports/performance.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
