"""Frozen actual-model local Investigator gate on original synthetic PDFs.

No scripted action order, financial oracle, post-calculation QA or delivery approval.
"""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import subprocess
import time

from againward.core.artifact_store import write_json
from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.loop import investigate
from againward.domains.energy_billing.protocol import BillingFailure
from againward.domains.energy_billing.provider import CodexTransport
from againward.domains.energy_billing.reporting import render_report
from againward.domains.energy_billing.state import initialize, load_state

from .native_gate import make_sources


def frozen_sha() -> str:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Investigator gate requires a clean frozen worktree")
    return sha


def run(model: str, output: Path) -> dict:
    sha = frozen_sha()
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.perf_counter()
    make_sources(output / "input")
    root = output / "snapshot"
    batch = inventory_sources(output / "input", root)
    initialize(batch, root)
    transport = CodexTransport(model, evaluation_root=output / "raw")
    runtime = investigate(root, model=model, transport=transport)
    state = load_state(root)
    calculation = runtime["calculation"]
    report, report_seconds = None, None
    terminal = runtime["terminal_reason"]
    if calculation is not None:
        at = time.perf_counter()
        try:
            report = render_report(root, calculation["calculation_sha256"])
            terminal = {"code": "INTERNAL_SCOPED_REPORT_CREATED", "stage": "REPORT"}
        except BillingFailure as exc:
            terminal = exc.diagnostic
        report_seconds = time.perf_counter() - at
    if frozen_sha() != sha:
        raise ValueError("Frozen engine changed during campaign")
    result = {"schema_version": "energy-billing-investigator-gate-v1", "engine_sha": sha, "engine_dirty": False,
              "model": model, "python_version": platform.python_version(), "platform": platform.system(),
              "cli_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
              "batch": batch.to_dict(), "source_rejects": 0, "observations": len(state["observations"]),
              "invalid_observations": len(state["quarantine"]), "occurrences": len(state["occurrences"]),
              "relations": len(state["relations"]), "claims": 0, "reviews": len(state["reviews"]),
              "readiness": runtime["readiness"], "root_issues": runtime["readiness"].get("root_issues", []),
              "derived_blockers": runtime["readiness"].get("derived_blockers", []), "runtime": runtime,
              "investigator_turns": runtime["turns"], "model_calls": runtime["model_calls"],
              "protocol_retries": runtime["protocol_repairs"], "diagnostics": runtime["diagnostics"],
              "provider_calls": transport.calls,
              "provider_failures": sum(row["code"] == "MODEL_PROVIDER_FAILURE" for row in runtime["diagnostics"]),
              "calculation_reached": calculation is not None, "calculation": calculation,
              "qa_objections": [], "qa_performed": False, "report_reached": report is not None, "report": report,
              "terminal_reason": terminal, "report_seconds": report_seconds, "wall_seconds": time.perf_counter() - started,
              "qualification": "Known synthetic local Investigator development gate; not DEV corpus, sealed HOLDOUT, post-calculation QA or human delivery approval."}
    write_json(output / "result.json", result)
    print({k: result[k] for k in ("observations", "occurrences", "relations", "calculation_reached", "report_reached",
                                 "terminal_reason", "model_calls", "investigator_turns")}, flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = run(args.model, args.output)
    raise SystemExit(0 if result["report_reached"] else 1)


if __name__ == "__main__":
    main()
