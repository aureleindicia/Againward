"""Frozen actual-PDF thin path. No financial oracle is passed to the pipeline."""
from __future__ import annotations

import argparse
from pathlib import Path
import platform
import subprocess
import time
from typing import Any

from againward.core.artifact_store import write_json
from againward.documents.contracts import DocumentError
from againward.documents.sources import inventory_sources
from againward.domains.energy_billing.calculation import calculate, readiness
from againward.domains.energy_billing.investigator import propose_action, semantic_hash
from againward.domains.energy_billing.protocol import BillingFailure
from againward.domains.energy_billing.provider import CodexTransport, ModelBoundary
from againward.domains.energy_billing.reader import read_source
from againward.domains.energy_billing.reporting import render_report
from againward.domains.energy_billing.review import request_review
from againward.domains.energy_billing.state import commit_event, initialize

from .native_gate import make_sources


def run(model: str, output: Path) -> dict:
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], text=True).strip():
        raise ValueError("Frozen vertical run requires a clean worktree.")
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    make_sources(output / "input")
    started = time.perf_counter()
    root = output / "snapshot"
    batch = inventory_sources(output / "input", root)
    state = initialize(batch, root)
    transport = CodexTransport(model, evaluation_root=output / "raw")
    calls = 0

    def bounded(prompt, schema):
        nonlocal calls
        if calls >= 16 or time.perf_counter() - started > 600:
            raise BillingFailure("RESOURCE_LIMIT", stage="RUNTIME", expected="16 calls and 600 seconds")
        calls += 1
        return transport(prompt, schema)

    boundary = ModelBoundary(bounded)
    turns: list[dict[str, Any]] = []
    calculation = None
    report = None
    decision: dict[str, Any] = {"ready": False, "support_state": "UNRESOLVED", "root_issues": []}
    terminal = None
    stage_times: dict[str, float] = {}
    stage = "READ"

    def mutate(event):
        nonlocal state
        before = semantic_hash(state)
        state = commit_event(state, event, root)
        turns.append({"event_type": event["type"], "before_semantic_sha256": before,
                      "after_semantic_sha256": semantic_hash(state), "progress": before != semantic_hash(state)})
        write_json(output / "progress.json", {"turns": turns, "model_calls": calls,
                    "occurrences": len(state["occurrences"]), "relations": len(state["relations"]),
                    "observations": len(state["observations"]), "reviews": len(state["reviews"])})

    try:
        for document in batch.documents:
            at = time.perf_counter()
            stage = "READ"
            digest = read_source(batch, document.source_id, root, model=model, boundary=boundary, role="PRIMARY")
            mutate({"type": "READ", "receipt_sha256": digest})
            stage_times["reading"] = stage_times.get("reading", 0) + time.perf_counter() - at
            stage = "ACTION"
            issue: dict[str, Any] = {"issue_id": "missing-occurrence-" + document.source_id, "source_id": document.source_id,
                     "description": "Bind the scoped invoice line or tariff term; declare neither if materially ambiguous."}
            at = time.perf_counter()
            response = propose_action(state, issue, boundary)
            if response["action"]["type"] not in {"DECLARE_INVOICE", "DECLARE_TARIFF"}:
                terminal = {"code": "BUSINESS_AMBIGUITY", "stage": stage, "action": response}
                break
            mutate({"type": "ACTION", "focus": issue["issue_id"], "response": response})
            stage_times["actions"] = stage_times.get("actions", 0) + time.perf_counter() - at
        if terminal is None:
            for target in list(state["occurrences"]):
                stage = "REVIEW"
                at = time.perf_counter()
                digest = request_review(state, target, root, model=model, boundary=boundary)
                mutate({"type": "REVIEW", "receipt_sha256": digest})
                stage_times["reviews"] = stage_times.get("reviews", 0) + time.perf_counter() - at
            decision = readiness(state, root)
            if decision["support_state"] == "UNSUPPORTED":
                terminal = {"code": "UNSUPPORTED_DOMAIN_RULE", "stage": "ENVELOPE", "root_issues": decision["root_issues"]}
        if terminal is None:
            stage = "ACTION"
            issue = {"issue_id": "missing-contract-authority", "targets": list(state["occurrences"]),
                     "description": "Establish a candidate GOVERNS relation for the line's contractual expected price."}
            response = propose_action(state, issue, boundary)
            if response["action"]["type"] != "LINK_TARIFF":
                terminal = {"code": "AUTHORITY_UNRESOLVED", "stage": stage, "action": response}
            else:
                mutate({"type": "ACTION", "focus": issue["issue_id"], "response": response})
                target = next(iter(state["relations"]))
                stage = "REVIEW"
                digest = request_review(state, target, root, model=model, boundary=boundary)
                mutate({"type": "REVIEW", "receipt_sha256": digest})
                stage = "READINESS"
                decision = readiness(state, root)
                if decision["ready"]:
                    stage = "CALCULATION"
                    at = time.perf_counter()
                    calculation = calculate(state, root)
                    stage_times["calculation"] = time.perf_counter() - at
                    stage = "REPORT"
                    at = time.perf_counter()
                    report = render_report(root, calculation["calculation_sha256"])
                    stage_times["report"] = time.perf_counter() - at
                else:
                    terminal = {"code": decision["root_issues"][0]["code"], "stage": stage,
                                "root_issues": decision["root_issues"]}
    except (BillingFailure, DocumentError) as exc:
        terminal = exc.diagnostic if isinstance(exc, BillingFailure) else {"code": exc.code, "stage": stage, "cause": str(exc)}
    result = {"schema_version": "energy-billing-vertical-v1", "engine_sha": sha, "engine_dirty": False,
              "model": model, "python_version": platform.python_version(), "platform": platform.system(),
              "cli_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
              "batch": batch.to_dict(), "source_rejects": 0, "observations": len(state["observations"]),
              "invalid_observations": len(state["quarantine"]), "occurrences": len(state["occurrences"]),
              "relations": len(state["relations"]), "claims": 0, "reviews": len(state["reviews"]),
              "readiness": decision, "root_issues": decision.get("root_issues", []),
              "derived_blockers": decision.get("derived_blockers", []), "turns": turns,
              "investigator_turns": sum(row["event_type"] == "ACTION" for row in turns),
              "model_calls": calls,
              "protocol_retries": sum(row["code"] == "MODEL_PROTOCOL_INVALID" and row["retry_count"] == 0
                                      for row in boundary.diagnostics),
              "diagnostics": boundary.diagnostics, "provider_calls": transport.calls,
              "provider_failures": sum(row["code"] == "MODEL_PROVIDER_FAILURE" for row in boundary.diagnostics),
              "calculation_reached": calculation is not None, "calculation": calculation, "qa_objections": [],
              "qa_performed": False, "report_reached": report is not None, "report": report,
              "terminal_reason": terminal or {"code": "INTERNAL_SCOPED_REPORT_CREATED", "stage": "REPORT"},
              "stage_seconds": stage_times, "wall_seconds": time.perf_counter() - started,
              "qualification": "Frozen synthetic thin vertical path; not DEV corpus, HOLDOUT, post-calculation QA or approved delivery."}
    write_json(output / "result.json", result)
    print({"observations": result["observations"], "occurrences": result["occurrences"], "relations": result["relations"],
           "calculation_reached": result["calculation_reached"], "report_reached": result["report_reached"],
           "terminal_reason": result["terminal_reason"], "model_calls": calls}, flush=True)
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
