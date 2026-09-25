"""Resume authorized Rental intake through privacy, sources and report QA.

Raw semantic review runs only after contract authority; business readers run
only after privacy clearance. No visual inspection or delivery approval is invented.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from againward.core.artifact_store import read_json, write_json
from againward.core.privacy import assert_case_privacy_cleared, inspect_privacy_status
from againward.core.workflow import fingerprint
from againward.documents.adjudication import ADJUDICATION_VERSION, adjudicate_with_codex, verify_adjudication_pixels
from againward.documents.analyst_review import REVIEW_VERSION, VISUAL_REVIEW_VERSION, review_visual_with_codex, review_with_codex
from againward.documents.codex_provider import CodexCliProvider, prompt_version_for_guidance
from againward.documents.contracts import DocumentError, SourceBatch
from againward.documents.extraction import persist_extraction, promote_facts, replay_extraction, validate_proposal
from againward.documents.independent_qa import QA_GUIDANCE_VERSION, QA_INSTRUCTIONS, RETRY_INSTRUCTIONS, compare_extractions
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources, safe_file, verify_batch
from againward.documents.visual_fact_review import MODEL_VISUAL_VERSION, record_model_visual_review, verify_visual_attestations
from againward.domains.rental.document_adapter import DOCUMENT_CASE_SCHEMA, load_document_case
from againward.domains.rental.semantic_guidance import guidance
from againward.evidence.hashing import stable_hash

from .autonomous_job import run_reviewed_package_job
from .autonomous_report import current_report_versions


VERSION = "againward-rental-approved-sources-job-v1"
RETRYABLE_MODEL_CODES = {"MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_AUTH_REQUIRED",
                         "MODEL_RATE_LIMITED", "MODEL_TRANSPORT_FAILURE", "MODEL_EMPTY_RESPONSE"}


def _save(path: Path, state: dict[str, Any], phase: str, **details: Any) -> None:
    state["phase"] = phase
    state["events"].append({"at_utc": datetime.now(timezone.utc).isoformat(),
                            "phase": phase, **details})
    state["state_sha256"] = stable_hash({key: value for key, value in state.items()
                                         if key != "state_sha256"})
    write_json(path, state)


def _load_state(path: Path) -> dict[str, Any]:
    state = read_json(path)
    if (state.get("schema_version") != VERSION or state.get("state_sha256") !=
            stable_hash({key: value for key, value in state.items() if key != "state_sha256"})):
        raise DocumentError("REVIEW_STALE", "Source job state changed")
    return state


def _remaining_revision_budget(analysis: Path) -> dict | None:
    from dataclasses import asdict
    from againward.evidence.cli import validate_session_artifacts
    from againward.evidence.protocol import EvidenceQuerySession
    from .workflow import _remaining_budget

    session_path = analysis / "evidence_query_session.json"
    if session_path.exists():
        session = EvidenceQuerySession.from_dict(read_json(session_path))
        validate_session_artifacts(analysis, session)
        if session.status in {"closed", "failure_budget_exhausted"}:
            raise ValueError("Closed evidence sessions cannot be reset by a source-job revision")
        return asdict(_remaining_budget(session))
    origin = analysis / "revision_origin.json"
    return read_json(origin).get("remaining_evidence_budget") if origin.exists() else None


def _only_adjudication_policy_changed(previous: dict, current: dict) -> bool:
    old_versions, new_versions = previous.get("versions", []), current.get("versions", [])
    # Source passes are unchanged by adjudication or visual-review policy.
    return (len(old_versions) == len(new_versions) and len(old_versions) >= 5
            and (old_versions[2], old_versions[4]) != (new_versions[2], new_versions[4])
            and [v for i, v in enumerate(old_versions) if i not in (2, 4)] ==
                [v for i, v in enumerate(new_versions) if i not in (2, 4)]
            and {k: v for k, v in previous.items() if k != "versions"} ==
                {k: v for k, v in current.items() if k != "versions"})


def _finish_revision(case: Path, binding: dict) -> None:
    """Recover an interrupted archive without discarding the previous query usage."""
    journal_path = case / ".rental-revision.json"
    if not journal_path.exists():
        return
    journal = read_json(journal_path)
    if journal.get("sha256") != stable_hash({k: v for k, v in journal.items() if k != "sha256"}):
        raise DocumentError("REVIEW_STALE", "Source revision journal changed")
    if journal["status"] == "COMPLETED":
        return
    if journal["status"] != "PENDING" or journal["origin"]["current_binding"] != binding:
        raise DocumentError("REVIEW_STALE", "Source revision changed while recovery was pending")
    archive = Path(journal["origin"]["archived_directory"])
    if archive.is_symlink() or archive.parent.resolve() != (case / "scratch/rental_revisions").resolve():
        raise DocumentError("SOURCE_UNSAFE_PATH", "Revision archive escaped its case")
    analysis = case / "processed"
    if not archive.exists():
        analysis.rename(archive)
    elif analysis.exists() and any(analysis.iterdir()):
        origin = analysis / "revision_origin.json"
        if not origin.exists() or read_json(origin) != journal["origin"]:
            raise DocumentError("REVIEW_STALE", "Interrupted revision has conflicting active artifacts")
    analysis.mkdir(exist_ok=True)
    write_json(analysis / "revision_origin.json", journal["origin"])
    journal["status"] = "COMPLETED"
    journal["sha256"] = stable_hash({k: v for k, v in journal.items() if k != "sha256"})
    write_json(journal_path, journal)


def _source_snapshot(folder: Path) -> list[dict[str, str]]:
    if folder.is_symlink() or not folder.is_dir():
        raise DocumentError("SOURCE_UNSAFE_PATH", "Approved source folder missing or linked")
    paths = sorted(path for path in folder.rglob("*") if path.is_file() or path.is_symlink())
    if not paths:
        raise DocumentError("SOURCE_UNREADABLE", "Approved source folder is empty")
    return [{"name": path.relative_to(folder).as_posix(), "sha256": fingerprint(safe_file(folder, path.relative_to(folder).as_posix()))}
            for path in paths]


def _receipt(path: str, root: Path, directory: str, hash_key: str) -> dict[str, Any]:
    file = Path(path).resolve()
    if not file.is_relative_to((root / directory).resolve()):
        raise DocumentError("SOURCE_UNSAFE_PATH", "Job receipt escaped its document directory")
    body = read_json(file)
    if body.get(hash_key) != stable_hash({key: value for key, value in body.items()
                                          if key != hash_key}):
        raise DocumentError("REVIEW_STALE", "Job receipt changed")
    return body


def _extractions(paths: dict[str, str], batch: SourceBatch, root: Path) -> tuple[Any, ...]:
    selected = []
    for document in batch.documents:
        path = paths[document.source_id]
        file = Path(path).resolve()
        if not file.is_relative_to((root / "extractions").resolve()):
            raise DocumentError("SOURCE_UNSAFE_PATH", "Extraction escaped its case")
        selected.append(replay_extraction(read_json(file), batch, root))
    return tuple(selected)


def _visual_review(root: Path, batch: SourceBatch, extractions: tuple[Any, ...],
                   proposed: dict[str, Any]) -> tuple[dict[str, Any], str] | None:
    """Select only a current component-bound operator receipt, never a template."""
    base = proposed["review"]
    matches: list[tuple[dict[str, Any], str]] = []
    for path in sorted((root / "review_templates").glob("attested-*.json")):
        if path.is_symlink():
            raise DocumentError("SOURCE_UNSAFE_PATH", "Linked visual attestation refused")
        candidate = read_json(path)
        stripped = {key: value for key, value in candidate.items()
                    if key != "visual_attestations"}
        base_decisions = {row["candidate_id"]: row for row in base["decisions"]}
        rows = stripped.get("decisions", [])
        if (stripped.get("extraction_hashes") != base.get("extraction_hashes")
                or {row.get("candidate_id") for row in rows} != set(base_decisions)):
            continue
        compatible = all(
            {key: value for key, value in row.items() if key != "resolved_flags"} ==
            {key: value for key, value in base_decisions[row["candidate_id"]].items()
             if key != "resolved_flags"}
            for row in rows)
        if not compatible:
            continue
        verify_visual_attestations(batch, extractions, candidate, root)
        promote_facts(extractions, candidate, batch, root)
        matches.append((candidate, str(path)))
    if len(matches) > 1:
        raise DocumentError("REVIEW_STALE", "Multiple current visual attestations need an explicit choice")
    return matches[0] if matches else None


def _run_approved_sources_job(workspace: str | Path, *, model: str,
                             timeout_seconds: int = 240,
                             evaluation_only: bool = False) -> dict[str, Any]:
    """One invocation drives all cleared source stages; STOPs remain explicit."""
    case = Path(workspace).resolve()
    if any((case / name).is_symlink() for name in ("processed", "scratch", "privacy", "sanitized", "incoming")):
        raise DocumentError("SOURCE_UNSAFE_PATH", "Workspace stage directory is linked")
    metadata = read_json(case / "workspace.json")
    if metadata.get("domain") != "rental":
        raise ValueError("A standard Rental workspace is required")
    evaluation_only = evaluation_only or metadata.get("case_kind") == "SYNTHETIC"
    privacy = inspect_privacy_status(case)
    if not privacy["approved_for_analysis"]:
        from .privacy_job import run_privacy_intake
        try:
            intake = run_privacy_intake(case, model=model, timeout_seconds=timeout_seconds)
        except DocumentError as exc:
            return {"status": "WAITING_MODEL_RETRY" if exc.code in RETRYABLE_MODEL_CODES else "FAILED",
                    "stage": "PRIVACY", "reason_code": exc.code, "approved_for_delivery": False}
        if not intake["approved_for_analysis"]:
            return {**intake, "approved_for_delivery": False}
        privacy = inspect_privacy_status(case)
    assert_case_privacy_cleared(case)
    # Synthetic fixtures may live in incoming; a real case only uses sanitized.
    source = case / "sanitized"
    if privacy["state"] == "NOT_REQUIRED" and not any(source.iterdir()):
        source = case / "incoming"
    snapshot = _source_snapshot(source)
    privacy_path = case / "privacy" / "privacy_manifest.json"
    binding = {"sources": snapshot,
               "privacy_manifest_sha256": fingerprint(privacy_path) if privacy_path.is_file() else None,
               "prompt_version": prompt_version_for_guidance(guidance()), "model": model,
               "evaluation_only": evaluation_only,
               "versions": [VERSION, QA_GUIDANCE_VERSION, ADJUDICATION_VERSION,
                            REVIEW_VERSION, VISUAL_REVIEW_VERSION + "+" + MODEL_VISUAL_VERSION,
                            *current_report_versions()]}
    analysis = case / "processed"
    documents = analysis / "documents"
    path = analysis / "source_job_state.json"
    _finish_revision(case, binding)
    if path.exists():
        state = _load_state(path)
        if ("package" not in state and not (analysis / "evidence_query_session.json").exists()
                and _only_adjudication_policy_changed(state["binding"], binding)):
            # No financial work exists yet. Preserve hash-verified independent
            # source reads; invalidate the changed judgment and its dependents.
            for key in ("adjudication_receipt", "native_review_receipt", "visual_review_receipt", "fact_review_file"):
                state.pop(key, None)
            previous = state["binding"]
            state["binding"] = binding
            _save(path, state, "QA_POLICY_CHANGED", previous_binding=previous,
                  reused_source_passes=len(state["primary"]) + len(state["challenger"]))
        if state["binding"] != binding:
            from againward.core.artifact_store import assert_artifacts_consistent
            assert_artifacts_consistent(analysis)
            # Retain every old artifact and approval for audit, never import an
            # old approval into the new source/policy revision. Rename is atomic.
            archive_root = case / "scratch/rental_revisions"
            if (case / "scratch").is_symlink() or archive_root.is_symlink():
                raise DocumentError("SOURCE_UNSAFE_PATH", "Revision archive is linked")
            archive_root.mkdir(parents=True, exist_ok=True)
            archive = archive_root / (state["state_sha256"][:16] + "-" +
                datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f"))
            origin = {
                "archived_directory": str(archive), "previous_binding": state["binding"],
                "current_binding": binding, "reason": "SOURCE_PRIVACY_MODEL_OR_POLICY_CHANGED",
                "remaining_evidence_budget": _remaining_revision_budget(analysis),
                "budget_reset": False,
                "historical_absolute_refs_are_not_active": True, "approved_for_delivery": False}
            journal = {"status": "PENDING", "origin": origin}
            journal["sha256"] = stable_hash(journal)
            write_json(case / ".rental-revision.json", journal)
            _finish_revision(case, binding)
    if not path.exists():
        state = {"schema_version": VERSION, "binding": binding, "phase": "INTAKE",
                 "events": [], "primary": {}, "challenger": {},
                 "human_approval": False, "approved_for_delivery": False}
        _save(path, state, "INTAKE", source_count=len(snapshot))

    try:
        if "batch_receipt" not in state:
            batch = inventory_sources(source, documents)
            receipt = documents / "batches" / batch.batch_id / (stable_hash(batch.to_dict()) + ".json")
            state["batch_receipt"] = str(receipt)
            _save(path, state, "SOURCE_ACCEPTED", document_count=len(batch.documents))
        batch = SourceBatch.from_dict(read_json(Path(state["batch_receipt"])))
        verify_batch(batch, documents)
        # Aliases may duplicate bytes; every approved byte still needs a snapshot.
        if {row["sha256"] for row in snapshot} != {doc.sha256 for doc in batch.documents}:
            raise DocumentError("SOURCE_CHANGED", "Inventory no longer matches approved folder")
        provider = CodexCliProvider(documents, model=model, timeout_seconds=timeout_seconds)
        for document in batch.documents:
            if document.source_id not in state["primary"]:
                parsed = read_document(document, documents)
                started = perf_counter()
                for attempt in (1, 2):
                    try:
                        proposal = provider.propose(document, parsed,
                            {"batch": batch, "semantic_guidance": guidance() +
                             (RETRY_INSTRUCTIONS if attempt == 2 else "")})
                        extraction = validate_proposal(proposal, batch, documents)
                        break
                    except DocumentError as exc:
                        if attempt == 2 or exc.code not in {"SOURCE_LOCATION_INVALID", "EXTRACTION_SCHEMA_INVALID"}:
                            raise
                stored = persist_extraction(extraction, documents)
                state["primary"][document.source_id] = str(stored)
                _save(path, state, "DOCUMENT_PARSED", source_id=document.source_id,
                      model_attempts=attempt, model_wall_seconds=round(perf_counter() - started, 3))
        primary = _extractions(state["primary"], batch, documents)
        for document in batch.documents:
            if document.source_id not in state["challenger"]:
                parsed = read_document(document, documents)
                started = perf_counter()
                for attempt in (1, 2):
                    try:
                        proposal = provider.propose(document, parsed,
                            {"batch": batch, "semantic_guidance": guidance() + QA_INSTRUCTIONS +
                             (RETRY_INSTRUCTIONS if attempt == 2 else "")})
                        extraction = validate_proposal(proposal, batch, documents)
                        break
                    except DocumentError as exc:
                        if attempt == 2 or exc.code not in {"SOURCE_LOCATION_INVALID", "EXTRACTION_SCHEMA_INVALID"}:
                            raise
                stored = persist_extraction(extraction, documents)
                state["challenger"][document.source_id] = str(stored)
                _save(path, state, "QA_SOURCE_REREAD", source_id=document.source_id,
                      model_attempts=attempt, model_wall_seconds=round(perf_counter() - started, 3))
        challenger = _extractions(state["challenger"], batch, documents)
        qa = compare_extractions(batch, primary, challenger, documents)
        if "qa_receipt" not in state:
            qa_path = documents / "independent_qa" / (qa["qa_sha256"] + ".json")
            write_json(qa_path, qa)
            state["qa_receipt"] = str(qa_path)
            _save(path, state, "QA_COMPLETED", material_disagreements=sum(
                row["material_needs_reconciliation"] for row in qa["source_results"]))
        else:
            saved_qa = _receipt(state["qa_receipt"], documents, "independent_qa", "qa_sha256")
            if saved_qa["source_results"] != qa["source_results"]:
                raise DocumentError("REVIEW_STALE", "QA comparison changed")
            qa = saved_qa
        if "adjudication_receipt" not in state:
            started = perf_counter()
            adjudication = adjudicate_with_codex(batch, primary, challenger, qa, documents,
                                                 model=model, timeout_seconds=timeout_seconds)
            saved = documents / "adjudications" / (adjudication["adjudication_sha256"] + ".json")
            write_json(saved, adjudication)
            state["adjudication_receipt"] = str(saved)
            _save(path, state, "QA_DISAGREEMENT_RESOLVED", unresolved=len(
                adjudication["material_unresolved_source_ids"]),
                model_wall_seconds=round(perf_counter() - started, 3))
        adjudication = _receipt(state["adjudication_receipt"], documents,
                                "adjudications", "adjudication_sha256")
        if adjudication.get("batch_id") != batch.batch_id or adjudication.get("qa_sha256") != qa["qa_sha256"]:
            raise DocumentError("REVIEW_STALE", "Adjudication no longer binds the current source QA")
        verify_adjudication_pixels(batch, adjudication, documents)
        if adjudication["material_unresolved_source_ids"]:
            _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", stage="SOURCE_ADJUDICATION",
                  source_ids=adjudication["material_unresolved_source_ids"])
            return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "stage": "SOURCE_ADJUDICATION",
                    "source_ids": adjudication["material_unresolved_source_ids"],
                    "job_state": str(path), "approved_for_delivery": False}
        by_hash = {item.to_dict()["extraction_sha256"]: item for item in (*primary, *challenger)}
        selected = tuple(by_hash[adjudication["selected_extractions"][document.source_id]]
                         for document in batch.documents)
        if "native_review_receipt" not in state:
            started = perf_counter()
            native = review_with_codex(batch, selected, documents, model=model,
                                       timeout_seconds=timeout_seconds)
            saved = documents / "analyst_reviews" / (native["receipt_sha256"] + ".json")
            write_json(saved, native)
            state["native_review_receipt"] = str(saved)
            _save(path, state, "FACT_REVIEWED", native_facts=native["native_facts_accepted"],
                  model_wall_seconds=round(perf_counter() - started, 3),
                  model_calls=native["model_calls"])
        native = _receipt(state["native_review_receipt"], documents,
                          "analyst_reviews", "receipt_sha256")
        if (native.get("batch_id") != batch.batch_id or
                native.get("review", {}).get("extraction_hashes") !=
                sorted(item.to_dict()["extraction_sha256"] for item in selected)):
            raise DocumentError("REVIEW_STALE", "Native fact review no longer binds selected extractions")
        if native["status"] == "REPAIR_REQUIRED":
            _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", stage="FACT_REVIEW")
            return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "stage": "FACT_REVIEW",
                    "job_state": str(path), "approved_for_delivery": False}
        review = native["review"]
        if native["visual_candidates_deferred"]:
            if "visual_review_receipt" not in state:
                started = perf_counter()
                visual = review_visual_with_codex(batch, selected, native, documents,
                                                  model=model, timeout_seconds=timeout_seconds)
                saved = documents / "analyst_reviews" / (visual["receipt_sha256"] + ".json")
                write_json(saved, visual)
                state["visual_review_receipt"] = str(saved)
                template = documents / "review_templates" / (visual["receipt_sha256"] + ".json")
                write_json(template, visual["review"])
                _save(path, state, "VISUAL_REVIEW_PROPOSED",
                      pending=visual["visual_candidates_pending_attestation"],
                      model_wall_seconds=round(perf_counter() - started, 3),
                      model_calls=visual["visual_analyst_model_calls"])
            visual = _receipt(state["visual_review_receipt"], documents,
                              "analyst_reviews", "receipt_sha256")
            if (visual.get("batch_id") != batch.batch_id or
                    visual.get("review", {}).get("extraction_hashes") !=
                    sorted(item.to_dict()["extraction_sha256"] for item in selected)):
                raise DocumentError("REVIEW_STALE", "Visual review no longer binds selected extractions")
            if visual["status"] != "WAITING_FOR_VISUAL_ATTESTATION":
                _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", stage="VISUAL_FACT_REVIEW")
                return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "stage": "VISUAL_FACT_REVIEW",
                        "job_state": str(path), "approved_for_delivery": False}
            model_review = None
            try:
                model_review = record_model_visual_review(batch, selected, visual, qa, adjudication,
                                                          documents, model=model)
            except DocumentError as exc:
                if exc.code != "HUMAN_REVIEW_REQUIRED":
                    raise
            if model_review is not None:
                reviewed_path = documents / "review_templates" / ("model-reviewed-" + stable_hash(model_review) + ".json")
                if reviewed_path.exists():
                    if read_json(reviewed_path) != model_review:
                        raise DocumentError("REVIEW_STALE", "Model visual review changed on replay")
                else:
                    write_json(reviewed_path, model_review)
                review = model_review
                state["fact_review_file"] = str(reviewed_path)
                _save(path, state, "VISUAL_MODEL_REVIEWED",
                      accepted=visual["visual_candidates_pending_attestation"], human_approval=False)
                attested = None
            else:
                attested = _visual_review(documents, batch, selected, visual)
            if model_review is None and attested is None:
                _save(path, state, "WAITING_FOR_VISUAL_ATTESTATION",
                      pending=visual["visual_candidates_pending_attestation"])
                return {"status": "WAITING_FOR_VISUAL_ATTESTATION", "stage": "VISUAL_FACT_REVIEW",
                        "review": str(documents / "review_templates" / (visual["receipt_sha256"] + ".json")),
                        "batch": state["batch_receipt"],
                        "extractions": [state["primary"].get(document.source_id)
                                        if selected_item.to_dict()["extraction_sha256"] ==
                                        primary_item.to_dict()["extraction_sha256"] else
                                        state["challenger"][document.source_id]
                                        for document, selected_item, primary_item in
                                        zip(batch.documents, selected, primary, strict=True)],
                        "job_state": str(path), "approved_for_delivery": False}
            if attested is not None:
                review, review_path = attested
                state["fact_review_file"] = review_path
                _save(path, state, "VISUAL_ATTESTATION_REPLAYED")
        body = {"schema_version": DOCUMENT_CASE_SCHEMA, "batch": batch.to_dict(),
                "extractions": [item.to_dict() for item in selected], "fact_review": review,
                "rental_relationship_review": None, "credit_relationship_review": None}
        if "package" not in state:
            canonical, lineage = load_document_case(body, documents)
            package = documents / "packages" / (stable_hash(body) + ".json")
            write_json(package, body)
            state["package"] = str(package)
            _save(path, state, "CALCULATION_INPUT_REVIEWED", facts=len(lineage["facts"]),
                  invoice_lines=len(canonical.actual_charges))
        package = Path(state["package"])
        if not package.resolve().is_relative_to((documents / "packages").resolve()):
            raise DocumentError("SOURCE_UNSAFE_PATH", "Package escaped its case")
        if package.name != stable_hash(body) + ".json" or read_json(package) != body:
            raise DocumentError("REVIEW_STALE", "Reviewed package changed or no longer matches source decisions")
        load_document_case(body, documents)
        from againward.core.workflow import prepare_investigation
        from againward.entrypoints import get_domain
        existing = read_json(analysis / "investigation_state.json") if (analysis / "investigation_state.json").is_file() else {}
        if "source" not in existing:
            from againward.evidence.protocol import QueryBudget
            remaining = _remaining_revision_budget(analysis)
            prepare_investigation(package, analysis, domain=get_domain("rental"),
                                  evidence_budget=QueryBudget(**remaining) if remaining is not None else None)
            _save(path, state, "CALCULATING")
        result = run_reviewed_package_job(package, analysis, model=model,
                                          timeout_seconds=timeout_seconds,
                                          evaluation_only=evaluation_only)
        _save(path, state, result["status"], pdf_sha256=result.get("pdf_sha256"))
        return {**result, "source_job_state": str(path)}
    except DocumentError as exc:
        if exc.code in RETRYABLE_MODEL_CODES:
            _save(path, state, "WAITING_MODEL_RETRY", reason_code=exc.code)
            return {"status": "WAITING_MODEL_RETRY", "reason_code": exc.code,
                    "job_state": str(path), "approved_for_delivery": False}
        _save(path, state, "FAILED", reason_code=exc.code)
        return {"status": "FAILED", "reason_code": exc.code,
                "job_state": str(path), "approved_for_delivery": False}


def run_approved_sources_job(workspace: str | Path, *, model: str,
                             timeout_seconds: int = 240,
                             evaluation_only: bool = False) -> dict[str, Any]:
    """Serialize one case across model waits and atomic revision changes."""
    import fcntl
    import os

    case = Path(workspace).resolve()
    if not (case / "workspace.json").is_file():
        raise ValueError("A standard Rental workspace is required")
    descriptor = os.open(case / ".rental-job.lock", os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "r+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {"status": "RUNNING", "reason_code": "CASE_ALREADY_RUNNING", "approved_for_delivery": False}
        try:
            return _run_approved_sources_job(case, model=model, timeout_seconds=timeout_seconds,
                                             evaluation_only=evaluation_only)
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
