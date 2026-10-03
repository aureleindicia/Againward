"""Frozen actual-model local Investigator gate on original synthetic PDFs.

No scripted action order, financial oracle, post-calculation QA or delivery approval.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import platform
import shutil
import subprocess
import time

from againward.core.artifact_store import read_json, write_json
from againward.documents.sources import inventory_sources, verify_batch
from againward.documents.contracts import SourceBatch
from againward.evidence.hashing import stable_hash
from againward.domains.energy_billing.loop import investigate, runtime_lease
from againward.domains.energy_billing.protocol import BillingFailure
from againward.domains.energy_billing.provider import CodexTransport
from againward.domains.energy_billing.reporting import render_report
from againward.domains.energy_billing.state import initialize, load_state

from .frontier_cases import SCENARIOS, make_sources


def frozen_sha() -> str:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Investigator gate requires a clean frozen worktree")
    return sha


def snapshot_manifest(root: Path) -> dict[str, str]:
    """Private bytes manifest; lock contents are not analytical artifacts."""
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("Unlinked private snapshot required")
    result = {}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():
            raise ValueError("Snapshot symlink refused")
        if path.is_file() and path.name not in {'.artifact.lock', 'investigator.lock'}:
            result[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def continue_snapshot(previous: Path, output: Path, model: str) -> tuple[SourceBatch, dict]:
    """Copy a stopped synthetic gate; never reset or overwrite its proof."""
    original_root = previous / 'snapshot'
    if ((previous / 'result.json').is_symlink()
            or any(p.is_symlink() for p in (output, *output.parents))):
        raise ValueError("Unlinked evaluation paths required")
    if output.resolve().is_relative_to(previous.resolve()):
        raise ValueError("Continuation output must be separate from its original run")
    with runtime_lease(original_root):
        original = read_json(previous / 'result.json')
        runtime = read_json(original_root / 'energy_billing/investigator.json')
        state = load_state(original_root)
        if (original.get('schema_version') != 'energy-billing-investigator-gate-v1'
                or original.get('model') != model or original.get('engine_dirty') is not False
                or original.get('calculation_reached') is not False or original.get('report_reached') is not False
                or original.get('runtime') != {k: v for k, v in runtime.items() if k != 'receipt_sha256'}
                or runtime['receipt_sha256'] != stable_hash(original['runtime'])
                or runtime['pending'] or runtime['terminal_reason']['code'] != 'MODEL_PROVIDER_FAILURE'
                or runtime['state_sha256'] != stable_hash(state) or original['batch'] != state['batch']):
            raise ValueError("Verified terminal provider failure from a frozen synthetic gate required")
        batch = SourceBatch.from_dict(state['batch'])
        if batch.privacy_manifest_sha256 is not None:
            raise ValueError("Real privacy-bound cases must use their original authorized workspace")
        verify_batch(batch, original_root)
        before = snapshot_manifest(original_root)
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        shutil.copytree(original_root, output / 'snapshot')
        if snapshot_manifest(output / 'snapshot') != before or snapshot_manifest(original_root) != before:
            raise ValueError("Snapshot changed during continuation copy")
        for path in (output / 'snapshot', *(output / 'snapshot').rglob('*')):
            path.chmod(0o700 if path.is_dir() else 0o600)
        return batch, {'kind': 'PRESERVED_RUNTIME_CONTINUATION', 'origin_engine_sha': original['engine_sha'],
                       'origin_result_sha256': hashlib.sha256((previous / 'result.json').read_bytes()).hexdigest(),
                       'origin_snapshot_manifest_sha256': stable_hash(before),
                       'origin_runtime_receipt_sha256': runtime['receipt_sha256'],
                       'origin_model_calls': runtime['model_calls'], 'origin_turns': runtime['turns'],
                       'origin_active_wall_seconds': runtime['wall_seconds']}


def run(model: str, output: Path, *, continue_from: Path | None = None, scenario: str = 'thin') -> dict:
    if scenario not in SCENARIOS or (continue_from is not None and scenario != 'thin'):
        raise ValueError('Known fresh scenario or preserved continuation required')
    sha = frozen_sha()
    started = time.perf_counter()
    root = output / "snapshot"
    continuation = None
    if continue_from is None:
        output.mkdir(parents=True, exist_ok=False, mode=0o700)
        make_sources(output / "input", scenario)
        batch = inventory_sources(output / "input", root)
        initialize(batch, root)
    else:
        batch, continuation = continue_snapshot(continue_from, output, model)
    transport = CodexTransport(model, evaluation_root=output / "raw")
    runtime = investigate(root, model=model, transport=transport, resume_provider_failure=continuation is not None)
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
              "continuation": continuation,
              "scenario": scenario if continuation is None else None,
              "dispositions": {key: {'disposition': row['proposal']['disposition'], 'verdict': row['response']['verdict'],
                                     'basis': row['response']['basis'], 'receipt_sha256': row['receipt_sha256']}
                               for key, row in state.get('dispositions', {}).items()},
              "new_model_calls": runtime['model_calls'] - (continuation['origin_model_calls'] if continuation else 0),
              "new_turns": runtime['turns'] - (continuation['origin_turns'] if continuation else 0),
              "provider_failures": sum(row["code"] == "MODEL_PROVIDER_FAILURE" for row in runtime["diagnostics"]),
              "calculation_reached": calculation is not None, "calculation": calculation,
              "qa_objections": [], "qa_performed": False, "report_reached": report is not None, "report": report,
              "terminal_reason": terminal, "report_seconds": report_seconds, "wall_seconds": time.perf_counter() - started,
              "qualification": ("Preserved synthetic runtime continuation; potentially mixed engines, not a fresh frozen E2E. "
                                if continuation else "Known synthetic local Investigator development gate. ") +
                               "Not DEV corpus, sealed HOLDOUT, post-calculation QA or human delivery approval."}
    write_json(output / "result.json", result)
    print({k: result[k] for k in ("observations", "occurrences", "relations", "calculation_reached", "report_reached",
                                 "terminal_reason", "model_calls", "investigator_turns")}, flush=True)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--continue-from", type=Path, help="Preserve a failed synthetic gate in a separate new output")
    parser.add_argument('--scenario', choices=SCENARIOS, default='thin', help='Fresh synthetic original document variation')
    args = parser.parse_args()
    result = run(args.model, args.output, continue_from=args.continue_from, scenario=args.scenario)
    raise SystemExit(0 if result["report_reached"] else 1)


if __name__ == "__main__":
    main()
