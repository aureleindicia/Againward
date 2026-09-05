#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gc
import json
import tempfile
import time
import tracemalloc
from datetime import datetime, timedelta
from pathlib import Path

from energy_mvp.evidence_plane import EvidenceDataset
from energy_mvp.evidence_protocol import EvidenceQuerySession
from energy_mvp.io import load_data


ROOT = Path(__file__).resolve().parent


def _generate(path: Path, rows: int) -> float:
    started = time.perf_counter()
    origin = datetime(2025, 1, 1)
    with path.open("w", encoding="utf-8") as handle:
        handle.write(
            "timestamp,power_kw,production,production_active,machine_mode,batch_id\n"
        )
        for index in range(rows):
            timestamp = origin + timedelta(minutes=15 * index)
            active = timestamp.weekday() < 5 and 7 <= timestamp.hour < 18
            handle.write(
                f"{timestamp.isoformat()},{60 if active else 18},"
                f"{10 if active else 0},{str(active).lower()},"
                f"{'run' if active else 'idle'},B-{index // 96:05d}\n"
            )
    return time.perf_counter() - started


def _request(dataset: EvidenceDataset, query_id: str, operation: str, arguments: dict) -> dict:
    return {
        "schema_version": "indicia-evidence-query-v1",
        "query_id": query_id,
        "dataset_id": dataset.dataset_id,
        "operation": operation,
        "arguments": arguments,
        "purpose": "Sonde de performance déterministe sans interprétation métier.",
    }


def probe(rows: int, directory: Path) -> dict:
    source = directory / f"probe_{rows}.csv"
    snapshot = directory / f"probe_{rows}_evidence.json"
    generation_seconds = _generate(source, rows)
    tracemalloc.start()
    started = time.perf_counter()
    loaded = load_data(source)
    load_seconds = time.perf_counter() - started
    started = time.perf_counter()
    dataset = EvidenceDataset.from_loaded_data(loaded, source_sha256="b" * 64)
    snapshot_build_seconds = time.perf_counter() - started
    started = time.perf_counter()
    snapshot.write_text(
        json.dumps(dataset.to_dict(), ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    serialization_seconds = time.perf_counter() - started
    session = EvidenceQuerySession.create(dataset)
    started = time.perf_counter()
    session.execute(dataset, _request(dataset, "describe", "describe_schema", {}))
    describe_seconds = time.perf_counter() - started
    auxiliary_key = next(item["key"] for item in dataset.fields if item["origin"] == "auxiliary" and item["original_name"] == "machine_mode")
    started = time.perf_counter()
    session.execute(
        dataset,
        _request(
            dataset,
            "contrast",
            "contrast_surface",
            {
                "group_field": "production_active",
                "left_value": False,
                "right_value": True,
                "fields": ["energy_kwh", "production", auxiliary_key],
            },
        ),
    )
    contrast_seconds = time.perf_counter() - started
    started = time.perf_counter()
    session.execute(
        dataset,
        _request(
            dataset,
            "boundary",
            "boundary_ledger",
            {
                "order_field": "timestamp",
                "fields": ["energy_kwh", "production", auxiliary_key],
                "minimum_segment_rows": 20,
                "candidate_stride": max(1, rows // 20_000),
                "maximum_coarse_boundaries": 128,
                "maximum_candidates": 5,
            },
        ),
    )
    boundary_seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    record = {
        "rows": rows,
        "source_bytes": source.stat().st_size,
        "snapshot_bytes": snapshot.stat().st_size,
        "peak_python_allocated_bytes": peak,
        "timings_seconds": {
            "generation": round(generation_seconds, 6),
            "load": round(load_seconds, 6),
            "snapshot_build": round(snapshot_build_seconds, 6),
            "snapshot_serialization": round(serialization_seconds, 6),
            "describe_query": round(describe_seconds, 6),
            "contrast_query": round(contrast_seconds, 6),
            "boundary_query": round(boundary_seconds, 6),
        },
        "query_calls": len(session.calls),
        "pairwise_support_not_run": "bounded protocol refuses unscoped quadratic work",
    }
    del session, dataset, loaded
    gc.collect()
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description="Sonde locale de performance Stage 4.")
    parser.add_argument("--sizes", type=int, nargs="+", default=[10_000, 100_000])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "docs" / "stage4_evidence_plane" / "PERFORMANCE_PROBE.json",
    )
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="indicia_stage4_perf_") as directory:
        records = [probe(size, Path(directory)) for size in args.sizes]
    payload = {
        "schema_version": "indicia-stage4-performance-probe-v1",
        "environment": "local Termux/Python; tracemalloc measures Python allocations only",
        "evidence_classification": "engineering performance probe, not analytical validation",
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
