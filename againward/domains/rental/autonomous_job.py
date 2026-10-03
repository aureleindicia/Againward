"""Resumable reviewed-package → client-report job; privacy/source gates stay upstream.

This is deliberately not described as raw-file intake: document inventory,
privacy, extraction, QA, links and any required visual attestation must have
produced the approved package first. No automatic delivery approval occurs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from againward.core.artifact_store import read_json, write_json
from againward.core.workflow import fingerprint, prepare_investigation
from againward.documents.contracts import DocumentError
from againward.entrypoints import get_domain
from againward.evidence.hashing import stable_hash

from .autonomous_report import current_report_versions, run_autonomous_report
from .autonomous_review import run_autonomous_finding_review
from .review_policy import validate_current_review


VERSION = "againward-rental-reviewed-package-job-v1"


def _event(root: Path, state: str, **details: Any) -> dict:
    path = root / "autonomous_job_state.json"
    previous = read_json(path) if path.exists() else None
    events = list(previous["events"]) if previous is not None else []
    events.append({"at_utc": datetime.now(timezone.utc).isoformat(),
                   "state": state, **details})
    body = {"schema_version": VERSION, "state": state, "events": events,
            "human_approval": False, "approved_for_delivery": False}
    write_json(path, body)
    return body


def _completed_report(root: Path, job: dict) -> dict | None:
    if job.get("state") not in {"READY_FOR_APPROVAL", "EVALUATION_ONLY_QA_PASSED"}:
        return None
    last = job["events"][-1]
    receipt_path = Path(last["receipt"]).resolve()
    if not receipt_path.is_relative_to((root / "autonomous_report").resolve()):
        raise ValueError("Completed autonomous report receipt escaped its case directory")
    receipt = read_json(receipt_path)
    if receipt.get("binding", {}).get("versions") != current_report_versions():
        raise ValueError("Completed report policy or renderer changed; recomputation required")
    if (receipt.get("receipt_sha256") != stable_hash({key: value for key, value in receipt.items()
                                                      if key != "receipt_sha256"})
            or receipt.get("status") != job["state"]):
        raise ValueError("Completed autonomous report receipt changed")
    recorded = receipt["attempts"][-1]
    pdf = root / "rental_client_report.pdf"
    if (not pdf.is_file() or fingerprint(pdf) != recorded["pdf_sha256"]
            or fingerprint(root / "rental_evidence_pack.json") != recorded["evidence_pack_sha256"]
            or fingerprint(root / "report.md") != recorded["report_md_sha256"]):
        raise ValueError("Completed autonomous report artifacts changed; no silent replay")
    return {"status": job["state"], "receipt": str(receipt_path),
            "pdf": str(pdf), "pdf_sha256": recorded["pdf_sha256"],
            "job_state": str(root / "autonomous_job_state.json"),
            "human_approval": False, "approved_for_delivery": False}


def run_reviewed_package_job(package_path: str | Path, output_directory: str | Path, *,
                             model: str, timeout_seconds: int = 240,
                             evaluation_only: bool = False) -> dict:
    """Start or resume from a reviewed, privacy-approved document package."""
    package = Path(package_path).resolve()
    root = Path(output_directory).resolve()
    if not package.is_file():
        raise ValueError("Reviewed Rental document package is absent")
    if not (root / "investigation_state.json").exists():
        if root.exists() and any(root.iterdir()):
            raise ValueError("Nonempty job directory without a case state cannot be resumed")
        prepare_investigation(package, root, domain=get_domain("rental"))
        _event(root, "PREPARED", source_sha256=fingerprint(package))
    source = read_json(root / "investigation_state.json")["source"]
    if source["sha256"] != fingerprint(package):
        raise ValueError("Reviewed package changed; do not resume against a stale source")
    review_files = ("rental_assessments.json", "rental_findings.json", "agent_findings.json",
                    "investigation.json", "review.json")
    if all((root / name).exists() for name in review_files):
        # An existing but stale review is not permission to regenerate over it.
        validate_current_review(root)
    else:
        try:
            result = run_autonomous_finding_review(root, model=model,
                                                   timeout_seconds=timeout_seconds)
        except DocumentError as exc:
            _event(root, "WAITING_MODEL_RETRY", stage="FINDING_QA", reason_code=exc.code)
            return {"status": "WAITING_MODEL_RETRY", "stage": "FINDING_QA",
                    "reason_code": exc.code, "job_state": str(root / "autonomous_job_state.json"),
                    "approved_for_delivery": False}
        if result["status"] != "FINDINGS_QA_PASSED":
            _event(root, result["status"], stage="FINDING_QA", receipt=result.get("receipt"))
            return {**result, "job_state": str(root / "autonomous_job_state.json")}
        _event(root, "FINDINGS_QA_PASSED", receipt=result["receipt"])
    job_path = root / "autonomous_job_state.json"
    if job_path.exists():
        completed = _completed_report(root, read_json(job_path))
        if completed is not None:
            return completed
    try:
        report = run_autonomous_report(root, model=model, timeout_seconds=timeout_seconds,
                                       evaluation_only=evaluation_only)
    except DocumentError as exc:
        _event(root, "WAITING_MODEL_RETRY", stage="REPORT_QA", reason_code=exc.code)
        return {"status": "WAITING_MODEL_RETRY", "stage": "REPORT_QA",
                "reason_code": exc.code, "job_state": str(root / "autonomous_job_state.json"),
                "approved_for_delivery": False}
    _event(root, report["status"], stage="REPORT_QA", receipt=report.get("receipt"),
           pdf_sha256=report.get("pdf_sha256"))
    return {**report, "job_state": str(root / "autonomous_job_state.json")}
