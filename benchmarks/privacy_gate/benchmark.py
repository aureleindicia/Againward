#!/usr/bin/env python3
"""Bounded synthetic benchmark for the deterministic privacy post-check."""
from __future__ import annotations

import argparse
import json
import platform
import resource
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from energy_mvp.client_workspace import create_client_workspace
from tests.contract_fixtures import authorize_test_case
from energy_mvp.privacy import POLICY_VERSION, REVIEW_SCHEMA, validate_codex_privacy_review


def _run(size: int, root: Path) -> dict[str, object]:
    identifier = f"privacy_{size}"
    create_client_workspace(identifier, root=root)
    case = root / identifier
    # The privacy benchmark still exercises REAL_CLIENT gates; only setup gains an explicit fictional agreement.
    authorize_test_case(case)
    source = case / "incoming" / "energy.csv"
    with source.open("w", encoding="utf-8", newline="") as handle:
        handle.write("timestamp,machine_id,power_kw,production\n")
        for index in range(size):
            handle.write(
                f"2026-01-{1 + (index // 96) % 28:02d}T{(index // 4) % 24:02d}:{(index % 4) * 15:02d}:00,"
                f"M{index % 37:03d},{10 + index % 11}.{index % 10},{index % 23}\n"
            )
    review = {
        "schema_version": REVIEW_SCHEMA,
        "policy_version": POLICY_VERSION,
        "workspace_id": identifier,
        "received_at_utc": "2026-09-05T08:00:00+00:00",
        "status": "PASS",
        "codex_semantic_review": {
            "completed": True,
            "first_substantive_reader_attested": True,
        },
        "detected_categories": [],
        "files": [{
            "file_id": "FILE-001",
            "source": "incoming/energy.csv",
            "action": "PASS",
            "sanitized": None,
            "categories": [],
            "transformations": [],
        }],
        "blocked_reasons": [],
    }
    review_path = case / "privacy" / "review.json"
    review_path.write_text(json.dumps(review), encoding="utf-8")
    started = time.perf_counter()
    manifest = validate_codex_privacy_review(case, review_path)
    elapsed = time.perf_counter() - started
    return {
        "rows": size,
        "input_bytes": source.stat().st_size if source.exists() else (case / "sanitized/energy.csv").stat().st_size,
        "elapsed_seconds": round(elapsed, 3),
        "rows_per_second": round(size / elapsed),
        "max_rss_kib_process": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
        "status": manifest["status"],
        "approved_for_analysis": manifest["approved_for_analysis"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sizes", nargs="+", type=int, default=[10_000, 100_000, 500_000])
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("RESULTS.json"))
    args = parser.parse_args(argv)
    if any(size < 1 for size in args.sizes):
        parser.error("Chaque taille doit être positive.")
    with tempfile.TemporaryDirectory(prefix="indicia-privacy-benchmark-") as temporary:
        measurements = [_run(size, Path(temporary)) for size in args.sizes]
    payload = {
        "schema_version": "indicia-privacy-benchmark-v1",
        "synthetic_only": True,
        "python": platform.python_version(),
        "measurements": measurements,
        "assertions": {
            "all_approved": all(item["approved_for_analysis"] is True for item in measurements),
            "largest_size_exercised": max(args.sizes) >= 500_000,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if all(payload["assertions"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
