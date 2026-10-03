"""V2 investigation/QA boundary feeding the existing report and PDF job.

A native V2 package retains the replayable graph and current calculation QA.
It is not a legacy reviewed package and conveys no human delivery approval.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from againward.core.artifact_store import read_json, write_json
from againward.documents.contracts import DocumentError, closed
from againward.evidence.hashing import stable_hash
from .case_graph import commit_transition, graph_hash, replay_evidence
from .case_graph_adapter import load_graph_case
from .case_graph_readiness import evaluate_readiness
from .case_investigator import Budget, investigate
from .case_post_calculation import MAX_REOPEN_CYCLES, invoke_qa, reduce_objections, verify_qa
from .reconciliation import reconcile

PACKAGE_VERSION = "againward-rental-graph-calculated-case-v2"


def load_calculated_package(payload: dict[str, Any], root: Path):
    closed(payload, {"schema_version", "graph", "qa_receipt_sha256", "case_sha256", "calculation_sha256"})
    if payload["schema_version"] != PACKAGE_VERSION:
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Native V2 calculated package required")
    graph = replay_evidence(payload["graph"], root)
    head = root / "case_graph_v2" / "head.json"
    if not head.is_file() or read_json(head).get("graph_sha256") != graph_hash(graph):
        raise DocumentError("REVIEW_STALE", "Calculated package does not represent current graph head")
    if evaluate_readiness(graph, root)["status"] != "SUPPORTED_DETERMINISTIC":
        raise DocumentError("EXTRACTION_INCOMPLETE", "V2 package is not ready")
    case, lineage = load_graph_case(graph, root)
    calculation = reconcile(case)
    qa = verify_qa(graph, payload["qa_receipt_sha256"], root)
    if (qa["response"]["verdict"] != "PASS" or payload["case_sha256"] != stable_hash(case.to_dict())
            or payload["calculation_sha256"] != stable_hash(calculation)):
        raise DocumentError("REVIEW_STALE", "Calculated case or successful QA binding changed")
    lineage["post_calculation_qa_sha256"] = payload["qa_receipt_sha256"]
    return case, lineage


def _investigate_to_report(graph: dict[str, Any], root: Path, output_directory: Path, *, model: str,
                          provider: Callable | None = None, qa_provider: Callable | None = None,
                          budget: Budget = Budget(), max_reopen_cycles: int = MAX_REOPEN_CYCLES,
                          evaluation_only: bool = False) -> dict[str, Any]:
    from .autonomous_job import run_reviewed_package_job
    if type(max_reopen_cycles) is not int or not 0 <= max_reopen_cycles <= MAX_REOPEN_CYCLES:
        raise ValueError("At most two post-calculation reopening cycles")
    replay_evidence(graph, root)
    rounds: list[dict[str, Any]] = []
    used_cycles = sum(event["type"] == "POST_CALC_OBJECTION" for event in graph["actions"])
    remaining_cycles = min(max_reopen_cycles, max(0, MAX_REOPEN_CYCLES - used_cycles))
    for cycle in range(remaining_cycles + 1):
        investigation = investigate(graph, root, model=model, provider=provider, budget=budget,
                                    evaluation_only=evaluation_only)
        graph = investigation["graph"]
        record = {"cycle": cycle, "graph_sha256": graph_hash(graph), "investigator_status": investigation["status"],
                  "investigator_stop_reason": investigation["stop_reason"]}
        rounds.append(record)
        if investigation["status"] != "SUPPORTED_DETERMINISTIC":
            return {"status": "UNRESOLVED", "stop_reason": investigation["stop_reason"], "graph": graph,
                    "remaining_issues": investigation["remaining_issues"], "rounds": rounds,
                    "calculation": None, "report": None}
        try:
            sha = invoke_qa(graph, root, model=model, timeout_seconds=budget.timeout_seconds, provider=qa_provider)
            qa = verify_qa(graph, sha, root)
        except Exception as exc:
            from .case_investigator_context import open_issues
            remaining = open_issues(graph)
            # A pending verified OBJECT must remain visible after provider failure
            # or an attempted fresh PASS at the identical graph state.
            qa_head = root / "case_graph_v2" / "post_calculation_qa" / (graph_hash(graph) + "-current.json")
            if qa_head.is_file() and not qa_head.is_symlink():
                try:
                    pending = verify_qa(graph, read_json(qa_head)["receipt_sha256"], root)
                    remaining.update({"qa-objection-" + stable_hash(row): {"kind": "POST_CALC_OBJECTION", **row}
                                      for row in pending["response"]["objections"]})
                except (DocumentError, ValueError, OSError, KeyError):
                    remaining["qa-unverified"] = {"kind": "POST_CALC_QA_NOT_VERIFIED", "target": "case"}
            return {"status": "UNRESOLVED", "stop_reason": "POST_CALC_QA_FAILURE", "graph": graph,
                    "remaining_issues": remaining, "rounds": rounds, "calculation": None, "report": None,
                    "error_code": getattr(exc, "code", type(exc).__name__)}
        record["qa_receipt_sha256"] = sha
        record["qa_verdict"] = qa["response"]["verdict"]
        if qa["response"]["verdict"] == "PASS":
            # Establish current head even when the starting graph was ready and
            # investigation needed no mutation. CAS refuses an obsolete graph.
            graph = commit_transition(graph, root, lambda current: current)
            case = investigation["rental_case"]
            calculation = investigation["calculation"]
            payload = {"schema_version": PACKAGE_VERSION, "graph": graph, "qa_receipt_sha256": sha,
                       "case_sha256": stable_hash(case), "calculation_sha256": stable_hash(calculation)}
            load_calculated_package(payload, root)
            package_path = root / "packages" / (stable_hash(payload) + ".json")
            write_json(package_path, payload)
            report = run_reviewed_package_job(package_path, output_directory, model=model,
                timeout_seconds=budget.timeout_seconds, evaluation_only=evaluation_only)
            return {"status": report["status"], "graph": graph, "rounds": rounds, "remaining_issues": {},
                    "calculation": calculation, "report": report, "package": str(package_path)}
        if cycle == remaining_cycles:
            # Expose the outstanding objection without exceeding the journal's
            # lifetime reopening budget. Its OBJECT receipt cannot authorize a package.
            objections = {"qa-objection-" + stable_hash(row): {"kind": "POST_CALC_OBJECTION", **row}
                          for row in qa["response"]["objections"]}
            return {"status": "UNRESOLVED", "stop_reason": "REOPEN_BUDGET_EXHAUSTED", "graph": graph,
                    "remaining_issues": objections, "rounds": rounds, "calculation": None, "report": None}
        graph = commit_transition(graph, root, lambda current: reduce_objections(current, sha, root))
    raise AssertionError("Bounded post-calculation loop exhausted")


def investigate_to_report(graph: dict[str, Any], root: Path, output_directory: Path, *, model: str,
                          provider: Callable | None = None, qa_provider: Callable | None = None,
                          budget: Budget = Budget(), max_reopen_cycles: int = MAX_REOPEN_CYCLES,
                          evaluation_only: bool = False) -> dict[str, Any]:
    """Persist the bounded run, including unresolved stops and final PDF receipt."""
    result = _investigate_to_report(graph, root, output_directory, model=model, provider=provider,
        qa_provider=qa_provider, budget=budget, max_reopen_cycles=max_reopen_cycles, evaluation_only=evaluation_only)
    body = {"schema_version": "againward-rental-graph-delivery-run-v2",
            **{key: value for key, value in result.items() if key != "graph"},
            "final_graph_sha256": graph_hash(result["graph"]), "human_approval": False, "approved_for_delivery": False}
    sha = stable_hash(body)
    path = root / "case_graph_v2" / "delivery_runs" / (sha + ".json")
    write_json(path, {**body, "receipt_sha256": sha})
    result["receipt"] = str(path)
    return result


def main() -> None:
    import argparse
    import json
    from againward.documents.contracts import SourceBatch
    from .case_graph import empty_graph
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Immutable SourceBatch or persisted V2 graph")
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--max-turns", type=int, default=64)
    parser.add_argument("--max-reopen-cycles", type=int, choices=(0, 1, 2), default=2)
    parser.add_argument("--evaluation-only", action="store_true")
    args = parser.parse_args()
    payload = read_json(args.input)
    graph = payload if payload.get("schema_version") == "againward-rental-case-graph-v2" else empty_graph(SourceBatch.from_dict(payload))
    result = investigate_to_report(graph, args.root, args.output_dir, model=args.model,
        budget=Budget(max_turns=args.max_turns), max_reopen_cycles=args.max_reopen_cycles, evaluation_only=args.evaluation_only)
    print(json.dumps({key: value for key, value in result.items() if key != "graph"}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["status"] in {"READY_FOR_APPROVAL", "EVALUATION_ONLY_QA_PASSED"} else 3)


if __name__ == "__main__":
    main()
