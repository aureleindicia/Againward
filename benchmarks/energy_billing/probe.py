"""Real CLI protocol-only probes; no money fixture, oracle or domain mutation.

Run: python -m benchmarks.energy_billing.probe --model MODEL --output scratch/eb-probe
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Any

from againward.core.artifact_store import write_json
from againward.domains.energy_billing.protocol import (
    ACTION_FIELDS,
    ACTION_SCHEMA,
    ATOM_SCHEMA,
    READ_SCHEMA,
    REVIEW_SCHEMA,
    FACT_REVIEW_SCHEMA,
    TARIFF_REVIEW_SCHEMA,
    AUTHORITY_REVIEW_SCHEMA,
    BillingFailure,
    validate,
    validate_action,
)
from againward.domains.energy_billing.provider import CodexTransport, ModelBoundary
from againward.domains.energy_billing.review import check_response
from againward.domains.energy_billing.reader import source_context
from againward.documents.readers import ParsedDocument, SourceUnit


def run(model: str, output: Path, *, authority_only: bool = False, actions_only: bool = False) -> dict:
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    transport = CodexTransport(model, evaluation_root=output / "raw")
    boundary = ModelBoundary(transport)
    started = time.perf_counter()
    probes: list[dict[str, Any]] = []
    tasks: list[tuple[str, dict[str, Any], str, Callable[[Any], None] | None]] = [("READ", READ_SCHEMA,
        "Protocol probe only. Source location line:1 contains exactly 'Reference: SAMPLE'. "
        "Return one invoice_id observation value SAMPLE group document quote 'Reference: SAMPLE', no limitations.", None),
        ("REVIEW", REVIEW_SCHEMA,
         "Protocol probe only. Return AMBIGUOUS with evidence_ids ['e-1'], reason 'No business evidence supplied.'", None)]
    for name, schema in (("FACT_REVIEW", FACT_REVIEW_SCHEMA), ("TARIFF_REVIEW", TARIFF_REVIEW_SCHEMA),
                         ("AUTHORITY_REVIEW", AUTHORITY_REVIEW_SCHEMA)):
        response = {"verdict": "AMBIGUOUS", "evidence_ids": ["e-1"], "reason": "No business evidence supplied."}
        if name == "AUTHORITY_REVIEW":
            response["evidence_ids"] = [f"e-{index}" for index in range(64)]
        for key in schema["properties"]:
            if key not in response:
                response[key] = [] if key == "nonmaterial_quarantine_ids" else "INCOMPLETE" if key == "coverage" else "UNRESOLVED"
        tasks.append((name, schema, "Protocol-only echo; no money fixture or business decision:\n" + json.dumps(response), None))
    for kind, fields in ACTION_FIELDS.items():
        action: dict[str, Any] = {"type": kind}
        for name in fields:
            action[name] = ["e-1"] if name == "evidence_ids" else "Not enough evidence." if name == "reason" else "target-1"
        proposal = {"issue_id": "issue-1", "action": action}
        tasks.append((kind, ACTION_SCHEMA,
            "Protocol-only echo of this action; do not investigate a case or calculate:\n" + json.dumps(proposal),
            partial(validate_action, issue_id="issue-1", targets={"target-1"})))
    # Deliberately wrong focus is a native schema-valid but context-invalid response.
    # Runtime diagnostic must trigger one REAL CLI repair; no scripted transport.
    tasks.append(("LIVE_REPAIR", ACTION_SCHEMA,
        "Protocol fault-injection probe only. First response: issue_id 'obsolete', action MARK_UNRESOLVED, "
        "reason 'Protocol probe'. If runtime later reports focused issue issue-1, correct the issue_id "
        "to issue-1. Never change a business decision.", partial(validate_action, issue_id="issue-1")))
    context = source_context(ParsedDocument("probe-source", "protocol-probe-v1", (
        SourceUnit("probe-source", "line:1", "Accepted agreement.", "NATIVE", {}),), ()))
    deps = {"subject": {"kind": "GOVERNS", "tariff_id": "t-1", "invoice_id": "i-1", "evidence_ids": ["e-contract"]},
            "occurrences": {"t-1": {"source_id": "probe-source"}, "i-1": {"source_id": "invoice-source"}},
            "observations": {"e-contract": {}}, "quarantine": {}}
    for name, fault in (("BOUND_AUTHORITY", False), ("BOUND_AUTHORITY_REPAIR", True)):
        response = {"verdict": "SUPPORTED", "evidence_ids": ["e-contract"], "reason": "The supplied protocol text explicitly says accepted agreement.",
                    "authority_kind": "ACCEPTED_CONTRACT", "authority_source_id": "probe-source", "authority_location": "line:1",
                    "authority_quote": "Accepted agreement."}
        prompt = "Protocol binding only, no billing case, money or domain state. Source probe-source line:1 contains exactly 'Accepted agreement.'. "
        if fault:
            response["authority_location"] = "line:999"
            prompt += "First response uses deliberately wrong line:999. When runtime rejects it, correct location to line:1; keep the same quote and verdict. "
        prompt += "Return this protocol-only object:\n" + json.dumps(response)
        tasks.append((name, AUTHORITY_REVIEW_SCHEMA, prompt, partial(check_response, deps=deps, contexts=[context])))
    if authority_only:
        tasks = [task for task in tasks if task[0].startswith("BOUND_AUTHORITY")]
    if actions_only:
        tasks = [task for task in tasks if task[0] in ACTION_FIELDS or task[0] == "LIVE_REPAIR"]
    for name, schema, prompt, checker in tasks:
        before = boundary.calls
        try:
            result = boundary.ask(prompt, schema, stage=name, checker=checker)
            if name == "READ":
                validate(result["observations"][0], ATOM_SCHEMA, stage="READ")
            probes.append({"name": name, "passed": True, "calls": boundary.calls - before,
                           "response": result})
        except BillingFailure as exc:
            probes.append({"name": name, "passed": False, "calls": boundary.calls - before,
                           "failure": exc.diagnostic})
        write_json(output / "progress.json", {"probes": probes, "calls": transport.calls})
        print(json.dumps({"probe": name, "passed": probes[-1]["passed"], "calls": probes[-1]["calls"]}), flush=True)
        # A schema/provider failure means later contracts cannot be presumed viable.
        if not probes[-1]["passed"] and probes[-1]["failure"].get("cause") in {"SCHEMA_REJECTED", "CLI_EXIT", "TIMEOUT"}:
            break
    receipt = {"schema_version": "energy-billing-probe-v1",
        "engine_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "engine_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()),
        "model": model, "cli_version": subprocess.check_output(["codex", "--version"], text=True).strip(),
        "financial_fixture": False, "oracle": False, "domain_state_mutated": False,
        "probes": probes, "planned_probes": len(tasks), "calls": transport.calls,
        "diagnostics": boundary.diagnostics, "wall_seconds": time.perf_counter() - started,
        "passed": len(probes) == len(tasks) and all(row["passed"] for row in probes)}
    write_json(output / "result.json", receipt)
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--output", required=True, type=Path)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--authority-only", action="store_true")
    modes.add_argument("--actions-only", action="store_true")
    args = parser.parse_args()
    result = run(args.model, args.output, authority_only=args.authority_only, actions_only=args.actions_only)
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
