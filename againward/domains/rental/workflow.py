"""Rental recalculation and review persist through the shared case lifecycle."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from againward.core.artifact_store import read_json, write_json, transaction
from againward.core.client_lifecycle import assert_workflow_action_allowed, validate_client_lifecycle_artifacts
from againward.core.workflow_paths import resolve_analysis_directory
from againward.core.workflow import fingerprint
from againward.evidence.cli import validate_session_artifacts
from againward.evidence.dataset import EvidenceDataset
from againward.evidence.hashing import stable_hash
from againward.evidence.protocol import EvidenceQuerySession, QueryBudget, validate_finding_provenance
from .domain_pack import RentalDomainPack
from .findings import review_findings
from .ingestion import load_rental_case
from .models import RentalCase
from .reconciliation import reconcile


def _trace(root, action, **details):
    trace = read_json(root / "trace.json")
    trace["entries"].append({"at_utc": datetime.now(timezone.utc).isoformat(), "action": action, **details})
    write_json(root / "trace.json", trace)


def current_calculations(case_directory):
    root = resolve_analysis_directory(case_directory)
    assert_workflow_action_allowed(root, "rental_calculation_validation")
    state = read_json(root / "investigation_state.json")
    if state.get("domain") != "rental":
        raise ValueError("Rental tool requires a Rental investigation.")
    inventory = read_json(root / "artifact_inventory.json")
    extraction = inventory["extraction"]
    case, fresh_inventory = load_rental_case(extraction["path"], output_directory=root)
    if fresh_inventory["extraction"]["sha256"] != extraction["sha256"]:
        raise ValueError("Rental extraction changed; explicit recalculation required.")
    if case.to_dict() != read_json(root / "rental_case.json"):
        raise ValueError("Normalized Rental case no longer matches its source extraction.")
    result = reconcile(case)
    if result != read_json(root / "prepared_analysis.json"):
        raise ValueError("Rental calculations are stale or altered; explicit recalculation required.")
    return case, result


def record_assessments(case_directory, assessments):
    root = resolve_analysis_directory(case_directory)
    with transaction(root):
        assert_workflow_action_allowed(root, "rental_finding_review")
        life = validate_client_lifecycle_artifacts(root)
        if life["state"] not in {"ANALYZING", "RESUMING"}:
            raise ValueError("Review requires an active investigation or an answer-driven resume.")
        case, calculations = current_calculations(root)
        reviewed = review_findings(case, calculations, assessments)
        agent_findings = {"schema_version": "indicia-agent-findings-v1", "ground_truth_used": False,
                          "findings": []}
        for finding in reviewed["findings"]:
            record = {key: finding[key] for key in ("finding_id", "status", "claim_or_abstention", "evidence_query_ids", "evidence_handles")}
            record["alternative_explanations_tested"] = [test["description"] + ": " + test["result"] for test in finding["alternative_tests"]]
            if finding["status"] in {"ABSTAIN", "INSUFFISAMMENT_ETAYE"}:
                record["evidence_gap"] = "; ".join([*finding["limitations"], *finding["unresolved_questions"]])
            agent_findings["findings"].append(record)
        session = EvidenceQuerySession.from_dict(read_json(root / "evidence_query_session.json"))
        validate_session_artifacts(root, session)
        validate_finding_provenance(agent_findings, session)
        write_json(root / "rental_assessments.json", {"schema_version": "againward-rental-assessments-v1", "assessments": assessments})
        write_json(root / "rental_findings.json", reviewed)
        write_json(root / "agent_findings.json", agent_findings)
        _trace(root, "rental_assessments_recorded", reconciliation_sha256=reviewed["reconciliation_sha256"],
               finding_ids=[f["finding_id"] for f in reviewed["findings"]])
        return reviewed


def _remaining_budget(session):
    remaining = asdict(session.budget)
    remaining["maximum_calls"] -= len(session.successful_query_ids)
    remaining["maximum_returned_rows"] -= session.returned_rows_used
    remaining["maximum_context_bytes"] -= session.context_bytes_used
    remaining["maximum_pair_comparisons"] -= session.pair_comparisons_used
    remaining["maximum_handles"] -= len(session.handles)
    remaining["maximum_rejected_calls"] -= sum(call.get("status") == "rejected" for call in session.calls)
    try:
        return QueryBudget(**remaining)
    except ValueError as exc:
        raise ValueError("Evidence budget insufficient for a new source revision; record a justified continuation before recalculation.") from exc


def recalculate(case_directory, source):
    """Replace current calculations, retaining old evidence and consuming remaining budgets.

    This does not complete RESUME, decide findings, erase old responses or approve a
    report. Existing reviews become stale through content hashes until re-reviewed.
    """
    root = resolve_analysis_directory(case_directory)
    with transaction(root):
        assert_workflow_action_allowed(root, "rental_recalculation")
        life = validate_client_lifecycle_artifacts(root)
        state = read_json(root / "investigation_state.json")
        if state.get("domain") != "rental" or life["state"] not in {"ANALYZING", "RESUMING"}:
            raise ValueError("Recalculation requires an active Rental investigation, never WAIT or finalized state.")
        source = Path(source)
        # Validate every new source through the same privacy gate before semantic parsing.
        from againward.core.privacy import assert_source_approved_for_analysis
        assert_source_approved_for_analysis(source, output_directory=root)
        pack = RentalDomainPack(profile=state.get("profile"))
        prepared = pack.prepare(source, source_sha256=fingerprint(source), intake=read_json(root / "intake.json"),
                                options={}, evidence_plane_mode="preferred")
        previous = EvidenceDataset.from_dict(read_json(root / "evidence_dataset.json"))
        session = EvidenceQuerySession.from_dict(read_json(root / "evidence_query_session.json"))
        validate_session_artifacts(root, session, dataset=previous)
        if previous.dataset_sha256 == prepared.evidence_dataset.dataset_sha256:
            raise ValueError("Unchanged evidence revision; do not reset a session or its budget.")
        if session.status in {"closed", "failure_budget_exhausted"}:
            raise ValueError("Closed or failure-exhausted evidence sessions cannot be reset through recalculation.")
        new_session = EvidenceQuerySession.create(prepared.evidence_dataset, budget=_remaining_budget(session))
        archive = root / "evidence_revisions" / previous.dataset_sha256
        if archive.exists():
            raise ValueError("Evidence revision already archived; source replay refused.")
        for name in ("evidence_dataset.json", "evidence_query_session.json", "prepared_analysis.json", "rental_case.json",
                     "artifact_inventory.json", "rental_findings.json", "rental_assessments.json", "agent_findings.json",
                     "human_review.json", "investigation.json", "review.json"):
            if (root / name).is_file():
                write_json(archive / name, read_json(root / name))
        for name, payload in prepared.artifacts.items():
            write_json(root / name, payload)
        write_json(root / "evidence_dataset.json", prepared.evidence_dataset.to_dict())
        write_json(root / "evidence_query_session.json", new_session.to_dict())
        write_json(root / "evidence_card.json", pack.evidence_card(prepared, new_session))
        state.update(prepared.state)
        state["source"] = {"name": source.name, "sha256": fingerprint(source), "ground_truth_available_to_investigation": False}
        state["evidence_plane"].update(dataset_id=prepared.evidence_dataset.dataset_id, dataset_sha256=prepared.evidence_dataset.dataset_sha256)
        state.setdefault("evidence_revisions", []).append({"archive": str(archive.relative_to(root)),
            "previous_dataset_sha256": previous.dataset_sha256, "new_dataset_sha256": prepared.evidence_dataset.dataset_sha256,
            "previous_usage": session.to_dict()["usage"], "budget_reset": False})
        write_json(root / "investigation_state.json", state)
        write_json(root / "human_review.json", {"schema_version": 1, "status": "not_reviewed", "approved_for_delivery": False,
            "reviewer_role": None, "reviewed_at_utc": None, "reservations": ["Source revision requires fresh review."]})
        _trace(root, "rental_recalculated", dataset_sha256=prepared.evidence_dataset.dataset_sha256,
               source_sha256=state["source"]["sha256"], lifecycle_state=life["state"])
        return {"state": life["state"], "candidate_count": len(prepared.state["candidate_detection"]["events"]),
                "reconciliation_sha256": stable_hash(prepared.artifacts["prepared_analysis.json"]),
                "review_required": True}
