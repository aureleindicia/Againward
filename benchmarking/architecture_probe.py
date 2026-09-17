"""Synthetic behavioral probes; no model, client data, or ground truth access."""
from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from energy_mvp.client_lifecycle import (
    initialize_client_lifecycle, record_existing_data_exhaustion, publish_client_requests,
    record_canonical_answers, close_clarification_budget, mark_finalizable,
)
from energy_mvp.client_requests import select_minimum_requests
from energy_mvp.evidence_protocol import EvidenceQuerySession, QueryBudget
from energy_mvp.evidence_plane import EvidenceDataset
from energy_mvp.io import load_data


def request(identifier="Q1", *, blocking=True, partition=None):
    return {
        "request_id": identifier, "request_type": "MICRO_QUESTION",
        "client_question": f"Which operating condition was observed for {identifier}?",
        "internal_reason": "Distinguish remaining operating explanations.",
        "target_role": "site manager", "related_hypothesis_ids": ["H1"],
        "hypotheses_distinguished": ["A", "B", "C", "D"],
        "answer_by_hypothesis": partition or {"A":"yes","B":"yes","C":"no","D":"no"},
        "plausible_answers": [
            {"answer_id":"yes","label":"yes","decision_effects":["retain explanation"]},
            {"answer_id":"no","label":"no","decision_effects":["reject explanation"]}],
        "decision_impact_dimensions":["alternatives"], "effort":1,
        "availability":1, "reliability":1, "source_cost":0,
        "importance":"BLOCKING" if blocking else "NON_BLOCKING",
    }


def answer():
    return {"answer_id":"A1", "request_id":"Q1", "answer":"yes",
            "provided_by_role":"site manager", "source_or_evidence":"synthetic response",
            "source_type":"CLIENT_DECLARATION", "provided_at_utc":"2026-01-01T00:00:00Z"}


def ready(root):
    initialize_client_lifecycle(root)
    record_existing_data_exhaustion(root, analysis_inventory_ref="synthetic_inventory.json",
                                    reviewed_sources=["synthetic.csv"])


def run():
    result = {"scope":"deterministic synthetic counterexamples; not model quality evaluation"}
    with tempfile.TemporaryDirectory(prefix="againward-rnd-") as tmp:
        root = Path(tmp)
        waiting = root / "waiting"
        ready(waiting)
        publish_client_requests(waiting, [request()])
        try:
            close_clarification_budget(waiting, terminal_limitations=["unknown cause"])
            mark_finalizable(waiting, conclusion_ref="missing.json")
            result["pending_blocking_can_be_finalized"] = True
        except ValueError:
            result["pending_blocking_can_be_finalized"] = False
        optional = root / "optional"
        ready(optional)
        publish_client_requests(optional, [request(blocking=False)])
        result["nonblocking_answer_requires_resume"] = record_canonical_answers(optional,[answer()])["state"] == "RESUMING"
        orthogonal = request("Q2", partition={"A":"yes","B":"no","C":"yes","D":"no"})
        result["independent_questions_preserved"] = len(select_minimum_requests([request(),orthogonal])["selected"])
        source = root / "source.csv"
        source.write_text("timestamp,power_kw\n2026-01-01T00:00:00,100\n2026-01-01T00:15:00,100\n")
        data = load_data(source)
        result["two_quarter_hours_at_100kw_kwh"] = sum(r.energy_kwh for r in data.readings)
        dataset = EvidenceDataset.from_loaded_data(data,source_sha256="synthetic")
        session = EvidenceQuerySession.create(dataset, budget=QueryBudget(maximum_calls=1))
        query = {"query_id":"q1","dataset_id":dataset.dataset_id,"operation":"describe_schema",
                 "arguments":{},"purpose":"inspect synthetic evidence"}
        session.execute(dataset,query)
        try:
            session.execute(dataset,{**query,"query_id":"q2"})
        except ValueError:
            session._audit_failure(query,"rejected by CLI after exhaustion")
        try:
            EvidenceQuerySession.from_dict(session.to_dict())
            result["exhausted_session_remains_readable"] = True
        except ValueError:
            result["exhausted_session_remains_readable"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = json.dumps(run(),indent=2)+"\n"
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(output)
    print(output,end="")


if __name__ == "__main__":
    main()
