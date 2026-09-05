#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path

from energy_mvp.workflow import prepare_investigation


ROOT = Path(__file__).resolve().parent


def _context_fixture(path: Path) -> None:
    rows = [
        "timestamp,power_kw,production,production_active,machine_mode,batch_id,cleaning_active"
    ]
    origin = datetime(2026, 1, 1)
    for index in range(60 * 24):
        day = index // 24
        hour = index % 24
        active = day % 7 < 5 and 7 <= hour < 18
        cleaning = day >= 35 and 4 <= hour < 6
        power = 18 + (42 if active else 0) + (8 if cleaning else 0)
        timestamp = origin + timedelta(hours=index)
        rows.append(
            f"{timestamp.isoformat(sep=' ')},{power},{10 if active else 0},"
            f"{str(active).lower()},{'run' if active else 'idle'},B-{day:03d},"
            f"{str(cleaning).lower()}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def run(output: Path) -> dict:
    records = []
    with tempfile.TemporaryDirectory(prefix="indicia_stage4_shadow_") as directory:
        temporary = Path(directory)
        contextual = temporary / "contextual.csv"
        _context_fixture(contextual)
        cases = [
            ("monthly_legacy_fixture", ROOT / "examples" / "sample_energy.csv", {}),
            ("demo_15min_regression", ROOT / "examples" / "demo_15min.csv", {}),
            (
                "unknown_context_fixture",
                contextual,
                {"interval_minutes": 60},
            ),
        ]
        for case_id, source, load_options in cases:
            target = temporary / case_id
            started = time.perf_counter()
            prepare_investigation(
                source,
                target,
                evidence_plane_mode="shadow",
                load_options=load_options,
            )
            comparison = json.loads(
                (target / "shadow_comparison.json").read_text(encoding="utf-8")
            )
            records.append(
                {
                    "case_id": case_id,
                    "source_kind": "repository synthetic fixture",
                    "wall_time_seconds": round(time.perf_counter() - started, 6),
                    "comparison": comparison,
                }
            )
    payload = {
        "schema_version": "indicia-stage4-shadow-suite-v1",
        "status": "STRUCTURAL_SHADOW_COMPLETE_MODEL_COMPARISON_NOT_RUN",
        "evidence_classification": "development/regression; not genuinely unseen",
        "cases": records,
        "summary": {
            "cases": len(records),
            "legacy_candidate_preservation_failures": sum(
                not item["comparison"]["agreement"]["legacy_candidates_preserved"]
                for item in records
            ),
            "new_automatic_findings": sum(
                item["comparison"]["evidence_plane_path"]["automatic_findings"]
                for item in records
            ),
            "model_finding_disagreements_measured": 0,
            "reason": "No external model investigation was available; structural evidence must not be scored as agent quality.",
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Exécute le shadow structurel Stage 4.")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "stage4_evidence_plane" / "SHADOW_COMPARISON.json",
    )
    args = parser.parse_args()
    payload = run(args.output)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
