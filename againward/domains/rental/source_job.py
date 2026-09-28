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
from againward.documents.codex_provider import (VISUAL_RENDER_VERSION, CodexCliProvider,
    prompt_version_for_guidance)
from againward.documents.contracts import DocumentError, SourceBatch, error_category
from againward.documents.extraction import (append_adjudicator_visual_observations, append_adjudicator_native_observations, persist_extraction,
    promote_facts, replay_extraction, validate_proposal)
from againward.documents.independent_qa import (QA_GUIDANCE_VERSION, QA_INSTRUCTIONS,
    RETRY_INSTRUCTIONS, VISUAL_RETRY_INSTRUCTIONS, compare_extractions)
from againward.documents.readers import read_document
from againward.documents.sources import inventory_sources, safe_file, verify_batch
from againward.documents.visual_fact_review import MODEL_VISUAL_VERSION, record_model_visual_review, verify_visual_attestations
from againward.domains.rental.document_adapter import DOCUMENT_CASE_SCHEMA, load_document_case
from againward.domains.rental.extraction_validation import package_source_gaps, validate_rental_extraction, proposal_issues
from againward.domains.rental.entity_contract import (ANALYTICAL_FIELDS,
    NON_ENTITY_OBSERVATION_FIELDS, unique_pixel_entity_for_required_field)
from againward.domains.rental.semantic_guidance import (STRUCTURE_RETRY_INSTRUCTIONS as RENTAL_STRUCTURE_RETRY,
    guidance, visual_guidance)
from againward.evidence.hashing import stable_hash

from .autonomous_job import run_reviewed_package_job
from .autonomous_report import current_report_versions


VERSION = "againward-rental-approved-sources-job-v5-package-scope"
VISUAL_LIMITATION_ROUTING_VERSION = "againward-rental-visual-reading-v2"
RETRYABLE_MODEL_CODES = {"MODEL_TIMEOUT", "MODEL_UNAVAILABLE", "MODEL_AUTH_REQUIRED",
                         "MODEL_RATE_LIMITED", "MODEL_TRANSPORT_FAILURE", "MODEL_EMPTY_RESPONSE"}
def _visual_review_stop(visual: dict[str, Any]) -> dict[str, Any] | None:
    """Interpret final visual-review states; the native review handoff is not final."""
    status = visual.get("status")
    if status == "WAITING_FOR_VISUAL_ATTESTATION":
        return None
    if status == "REPAIR_REQUIRED":
        return {"status": status, "structural_gaps": visual.get("visual_structural_gaps", [])}
    if status == "WAITING_FOR_REQUIRED_INFORMATION":
        return {"status": status}
    raise DocumentError("REVIEW_STALE", "Unexpected final visual-review lifecycle status")


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


def _safe_failure_diagnostic(exc: DocumentError, *, stage: str,
                             source_id: str | None) -> dict[str, Any]:
    """Keep only bounded structural failure metadata in ordinary job receipts."""
    diagnostic = exc.diagnostic if isinstance(exc.diagnostic, dict) else {}
    safe_keys = {"schema_path", "validation_code", "error_category", "expected_type",
                 "received_shape", "decision_index", "retry_count", "model",
                 "prompt_version", "schema_sha256", "prompt_sha256", "response_sha256",
                 "invocation_id", "cli_version", "conflicting_field_count",
                 "limitation_count", "pixel_observation_count", "structural_gap_count",
                 "invalid_structural_field_count", "source_sha256", "extractor_version",
                 "current_prompt_version_count", "phase", "provider", "exit_code", "timeout",
                 "http_status", "technical_retries", "duration_seconds", "stdout_bytes",
                 "stdout_present", "stdout_shape", "stdout_sha256", "stderr_bytes",
                 "stderr_present", "stderr_shape", "stderr_sha256", "stage", "rejection_code",
                 "total_duration_seconds", "model_invoked"}
    safe = {key: value for key, value in diagnostic.items()
            if key in safe_keys and (value is None or type(value) in {str, int, bool})}
    semantic_types = diagnostic.get("conflicting_semantic_types")
    if (isinstance(semantic_types, list) and len(semantic_types) <= 12
            and all(isinstance(item, str) and item.replace("_", "").isalnum()
                    for item in semantic_types)):
        safe["conflicting_semantic_types"] = semantic_types
    retry_history = diagnostic.get("transient_failure_history")
    if (isinstance(retry_history, list) and len(retry_history) <= 1
            and all(isinstance(item, dict) and set(item) <= {
                "error_category", "http_status", "exit_code", "duration_seconds",
                "stdout_bytes", "stdout_shape", "stdout_sha256", "stderr_bytes",
                "stderr_shape", "stderr_sha256"}
                and all(value is None or type(value) in {str, int, float, bool}
                        for value in item.values()) for item in retry_history)):
        safe["transient_failure_history"] = retry_history
    missing_fields = diagnostic.get("missing_structural_fields")
    if (isinstance(missing_fields, list) and len(missing_fields) <= 3
            and all(item in {"entity_kind", "document_role", "document_status"}
                    for item in missing_fields)):
        safe["missing_structural_fields"] = sorted(set(missing_fields))
    missing_semantic = diagnostic.get("missing_semantic_fields")
    if (isinstance(missing_semantic, list) and len(missing_semantic) <= 20
            and all(item in ANALYTICAL_FIELDS for item in missing_semantic)):
        safe["missing_semantic_fields"] = sorted(set(missing_semantic))
    safe.update({"stage": diagnostic.get("stage", stage),
                 "source_id": diagnostic.get("source_id", source_id),
                 "reason_code": exc.code,
                 "error_category": diagnostic.get("error_category", error_category(exc.code))})
    return safe


def _bind_extraction_attempt(exc: DocumentError, *, attempt: int, model: str,
                             semantic_guidance: str) -> None:
    """Add safe attempt bindings before a proposal validation error is recorded."""
    diagnostic = dict(exc.diagnostic) if isinstance(exc.diagnostic, dict) else {}
    diagnostic.update({"retry_count": max(0, attempt - 1), "model": model,
                       "prompt_version": prompt_version_for_guidance(semantic_guidance)})
    exc.diagnostic = diagnostic


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


def _only_downstream_policy_changed(previous: dict, current: dict) -> bool:
    old_versions, new_versions = previous.get("versions", []), current.get("versions", [])
    # Source passes are unchanged by adjudication/fact/visual-review policy.
    return (len(old_versions) == len(new_versions) and len(old_versions) >= 5
            and old_versions[2:5] != new_versions[2:5]
            and old_versions[:2] + old_versions[5:] == new_versions[:2] + new_versions[5:]
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
                            REVIEW_VERSION, VISUAL_REVIEW_VERSION + "+" + MODEL_VISUAL_VERSION +
                            "+" + VISUAL_LIMITATION_ROUTING_VERSION + "+" + VISUAL_RENDER_VERSION,
                            *current_report_versions()]}
    analysis = case / "processed"
    documents = analysis / "documents"
    path = analysis / "source_job_state.json"
    _finish_revision(case, binding)
    if path.exists():
        state = _load_state(path)
        if ("package" not in state and not (analysis / "evidence_query_session.json").exists()
                and _only_downstream_policy_changed(state["binding"], binding)):
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

    active_stage = "SOURCE_INTAKE"
    active_source_id: str | None = None
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
        provider = CodexCliProvider(documents, model=model, timeout_seconds=timeout_seconds,
                                   evaluation_only=evaluation_only)
        active_stage = "PRIMARY_EXTRACTION"
        for document in batch.documents:
            active_source_id = document.source_id
            if document.source_id not in state["primary"]:
                parsed = read_document(document, documents)
                is_visual = any(unit.route != "NATIVE" for unit in parsed.units)
                base_guidance = visual_guidance() if is_visual else guidance()
                started = perf_counter()
                repair_note = ""
                deferred_structure = None
                for attempt in (1, 2):
                    attempt_guidance = (base_guidance +
                        ((VISUAL_RETRY_INSTRUCTIONS if is_visual else RETRY_INSTRUCTIONS)
                         if attempt == 2 else "") + repair_note)
                    extraction = None
                    try:
                        proposal = provider.propose(document, parsed,
                            {"batch": batch, "semantic_guidance": attempt_guidance,
                             "invocation_phase": "PRIMARY_EXTRACTION"})
                        extraction = validate_proposal(proposal, batch, documents)
                        validate_rental_extraction(extraction, provisional=True, allow_incomplete=True)
                        deferred_structure = proposal_issues(extraction) or None
                        break
                    except DocumentError as exc:
                        _bind_extraction_attempt(exc, attempt=attempt, model=model,
                                                 semantic_guidance=attempt_guidance)
                        if attempt == 2 and exc.code == "STRUCTURAL_INCOMPLETE" and extraction is not None:
                            # Keep the cited, unapproved reread for independent QA.
                            # The selected extraction is checked strictly before review.
                            validate_rental_extraction(extraction, allow_incomplete=True, provisional=True)
                            deferred_structure = _safe_failure_diagnostic(
                                exc, stage="PRIMARY_EXTRACTION", source_id=document.source_id)
                            break
                        if attempt == 2 or exc.code not in {"SOURCE_LOCATION_INVALID", "EXTRACTION_SCHEMA_INVALID",
                                                             "STRUCTURAL_INCOMPLETE"}:
                            raise
                        if (exc.code == "STRUCTURAL_INCOMPLETE" or
                                (exc.code == "EXTRACTION_SCHEMA_INVALID" and
                                 (exc.diagnostic or {}).get("validation_code") == "STRUCTURAL_ENUM_INVALID")):
                            repair_note = RENTAL_STRUCTURE_RETRY
                            missing = (exc.diagnostic or {}).get("missing_semantic_fields")
                            if isinstance(missing, list):
                                repair_note += " Check source support for: " + ", ".join(missing)[:55] + "."
                if extraction is None:
                    raise DocumentError("EXTRACTION_INCOMPLETE", "No validated primary extraction")
                stored = persist_extraction(extraction, documents)
                state["primary"][document.source_id] = str(stored)
                _save(path, state, "DOCUMENT_PARSED", source_id=document.source_id,
                      model_attempts=attempt, model_wall_seconds=round(perf_counter() - started, 3),
                      deferred_structure=deferred_structure)
        primary = _extractions(state["primary"], batch, documents)
        active_stage = "INDEPENDENT_REREAD"
        for document in batch.documents:
            active_source_id = document.source_id
            if document.source_id not in state["challenger"]:
                parsed = read_document(document, documents)
                is_visual = any(unit.route != "NATIVE" for unit in parsed.units)
                base_guidance = visual_guidance() if is_visual else guidance()
                started = perf_counter()
                repair_note = ""
                deferred_structure = None
                for attempt in (1, 2):
                    attempt_guidance = (base_guidance + QA_INSTRUCTIONS +
                        ((VISUAL_RETRY_INSTRUCTIONS if is_visual else RETRY_INSTRUCTIONS)
                         if attempt == 2 else "") + repair_note)
                    extraction = None
                    try:
                        proposal = provider.propose(document, parsed,
                            {"batch": batch, "semantic_guidance": attempt_guidance,
                             "invocation_phase": "INDEPENDENT_REREAD"})
                        extraction = validate_proposal(proposal, batch, documents)
                        validate_rental_extraction(extraction, provisional=True, allow_incomplete=True)
                        deferred_structure = proposal_issues(extraction) or None
                        break
                    except DocumentError as exc:
                        _bind_extraction_attempt(exc, attempt=attempt, model=model,
                                                 semantic_guidance=attempt_guidance)
                        if attempt == 2 and exc.code == "STRUCTURAL_INCOMPLETE" and extraction is not None:
                            validate_rental_extraction(extraction, allow_incomplete=True, provisional=True)
                            deferred_structure = _safe_failure_diagnostic(
                                exc, stage="INDEPENDENT_REREAD", source_id=document.source_id)
                            break
                        if attempt == 2 or exc.code not in {"SOURCE_LOCATION_INVALID", "EXTRACTION_SCHEMA_INVALID",
                                                             "STRUCTURAL_INCOMPLETE"}:
                            raise
                        if (exc.code == "STRUCTURAL_INCOMPLETE" or
                                (exc.code == "EXTRACTION_SCHEMA_INVALID" and
                                 (exc.diagnostic or {}).get("validation_code") == "STRUCTURAL_ENUM_INVALID")):
                            repair_note = RENTAL_STRUCTURE_RETRY
                            missing = (exc.diagnostic or {}).get("missing_semantic_fields")
                            if isinstance(missing, list):
                                repair_note += " Check source support for: " + ", ".join(missing)[:55] + "."
                if extraction is None:
                    raise DocumentError("EXTRACTION_INCOMPLETE", "No validated independent reread")
                stored = persist_extraction(extraction, documents)
                state["challenger"][document.source_id] = str(stored)
                _save(path, state, "QA_SOURCE_REREAD", source_id=document.source_id,
                      model_attempts=attempt, model_wall_seconds=round(perf_counter() - started, 3),
                      deferred_structure=deferred_structure)
        challenger = _extractions(state["challenger"], batch, documents)
        if "assembly_plan_receipt" in state:
            from againward.documents.reconciliation import assemble_observations
            plan = _receipt(state["assembly_plan_receipt"], documents, "adjudications", "adjudication_sha256")
            original = {item.source_id: item for item in _extractions(state["original_primary"], batch, documents)}
            peers = {item.source_id: item for item in challenger}
            effective = {item.source_id: item for item in primary}
            for decision in plan["decisions"]:
                source_id = decision["source_id"]
                if decision["selection"] == "ASSEMBLE":
                    rebuilt = assemble_observations(original[source_id], peers[source_id],
                        decision["candidate_selections"], batch, documents,
                        native_observations=decision.get("native_observations", []),
                        pixel_observations=decision.get("pixel_observations", []))
                    if rebuilt.to_dict() != effective[source_id].to_dict():
                        raise DocumentError("REVIEW_STALE", "Assembly lineage no longer matches current proposals")
        active_stage = "SOURCE_QA"
        active_source_id = None
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
            active_stage = "SOURCE_ADJUDICATION"
            started = perf_counter()
            adjudication = adjudicate_with_codex(batch, primary, challenger, qa, documents, semantic_guidance=guidance(),
                                                 model=model, timeout_seconds=timeout_seconds,
                                                 evaluation_only=evaluation_only,
                                                 validate_pixel_observations=lambda extraction:
                                                     validate_rental_extraction(extraction, require_package_facts=True),
                                                 unique_required_entity=unique_pixel_entity_for_required_field,
                                                 required_source_facts=package_source_gaps,
                                                 allow_assembly="assembly_plan_receipt" not in state,
                                                 assembly_context=({"plan": read_json(Path(state["assembly_plan_receipt"])),
                                                     "original_primary": [item.to_dict() for item in
                                                         _extractions(state["original_primary"], batch, documents)]}
                                                     if "assembly_plan_receipt" in state else None))
            if adjudication.get("assembly_proposals"):
                if "assembly_plan_receipt" in state or any(key in state for key in (
                        "native_review_receipt", "visual_review_receipt", "package")):
                    raise DocumentError("REVIEW_STALE", "Assembly requires fresh dependent reviews and one bounded round")
                assembly_path = documents / "adjudications" / (adjudication["adjudication_sha256"] + ".json")
                write_json(assembly_path, adjudication)
                state["assembly_plan_receipt"] = str(assembly_path)
                state["original_primary"] = dict(state["primary"])
                state["preassembly_qa_receipt"] = state["qa_receipt"]
                for source_id, payload in adjudication["assembly_proposals"].items():
                    assembled = replay_extraction(payload, batch, documents)
                    state["primary"][source_id] = str(persist_extraction(assembled, documents))
                primary = _extractions(state["primary"], batch, documents)
                qa = compare_extractions(batch, primary, challenger, documents)
                qa_path = documents / "independent_qa" / (qa["qa_sha256"] + ".json")
                write_json(qa_path, qa)
                state["qa_receipt"] = str(qa_path)
                _save(path, state, "ASSEMBLY_PROPOSED", facts_approved=0)
                adjudication = adjudicate_with_codex(batch, primary, challenger, qa, documents, semantic_guidance=guidance(),
                    model=model, timeout_seconds=timeout_seconds, evaluation_only=evaluation_only,
                    validate_pixel_observations=lambda extraction:
                        validate_rental_extraction(extraction, require_package_facts=True),
                    unique_required_entity=unique_pixel_entity_for_required_field,
                    required_source_facts=package_source_gaps, allow_assembly=False,
                    assembly_context={"plan": read_json(assembly_path),
                        "original_primary": [item.to_dict() for item in
                            _extractions(state["original_primary"], batch, documents)]})
            base_by_hash = {item.to_dict()["extraction_sha256"]: item for item in (*primary, *challenger)}
            added: dict[str, dict[str, Any]] = {}
            for decision in adjudication["decisions"]:
                observations = decision.get("pixel_observations", [])
                source_id = decision["source_id"]
                if (not observations and not decision.get("native_observations")) or source_id not in adjudication["selected_extractions"]:
                    continue
                base = base_by_hash[adjudication["selected_extractions"][source_id]]
                revised = append_adjudicator_visual_observations(
                    base, observations, batch, documents, adjudication["adjudication_sha256"],
                    unique_required_entity=unique_pixel_entity_for_required_field)
                if decision.get("native_observations"):
                    revised = append_adjudicator_native_observations(revised, decision["native_observations"],
                        batch, documents, adjudication["adjudication_sha256"],
                        unique_required_entity=unique_pixel_entity_for_required_field)
                stored = persist_extraction(revised, documents)
                augmented = revised.to_dict()["extraction_sha256"]
                base_sha = base.to_dict()["extraction_sha256"]
                candidate_hashes = sorted(stable_hash(candidate.to_dict()) for candidate in revised.candidates
                                          if {"ADJUDICATOR_PIXEL_OBSERVATION", "ADJUDICATOR_NATIVE_OBSERVATION"} & set(candidate.ambiguity_flags))
                added[source_id] = {"base_extraction_sha256": base_sha,
                    "extraction_sha256": augmented, "candidate_hashes": candidate_hashes,
                    "path": str(stored)}
                adjudication["selected_extractions"][source_id] = augmented
            if added:
                adjudication["adjudicator_extractions"] = {
                    source_id: {key: value for key, value in row.items() if key != "path"}
                    for source_id, row in added.items()}
                adjudication["adjudication_sha256"] = stable_hash({k: v for k, v in adjudication.items()
                                                                  if k != "adjudication_sha256"})
                state["adjudicator_extractions"] = {source_id: row["path"]
                                                     for source_id, row in added.items()}
            saved = documents / "adjudications" / (adjudication["adjudication_sha256"] + ".json")
            write_json(saved, adjudication)
            state["adjudication_receipt"] = str(saved)
            _save(path, state, "QA_DISAGREEMENT_RESOLVED", unresolved=len(
                adjudication["material_unresolved_source_ids"]),
                model_wall_seconds=round(perf_counter() - started, 3))
        adjudication = _receipt(state["adjudication_receipt"], documents,
                                "adjudications", "adjudication_sha256")
        active_stage = "SOURCE_ADJUDICATION_REPLAY"
        if adjudication.get("batch_id") != batch.batch_id or adjudication.get("qa_sha256") != qa["qa_sha256"]:
            raise DocumentError("REVIEW_STALE", "Adjudication no longer binds the current source QA")
        verify_adjudication_pixels(batch, adjudication, documents)
        if adjudication["material_unresolved_source_ids"]:
            _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", stage="SOURCE_ADJUDICATION",
                  source_ids=adjudication["material_unresolved_source_ids"])
            return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "stage": "SOURCE_ADJUDICATION",
                    "source_ids": adjudication["material_unresolved_source_ids"],
                    "job_state": str(path), "approved_for_delivery": False}
        augmented_rows = []
        for source_id, saved_path in state.get("adjudicator_extractions", {}).items():
            stored_path = Path(saved_path).resolve()
            if (source_id not in {doc.source_id for doc in batch.documents}
                    or not stored_path.is_relative_to((documents / "extractions").resolve())):
                raise DocumentError("SOURCE_UNSAFE_PATH", "Adjudicator extraction escaped its case")
            augmented_rows.append(replay_extraction(read_json(stored_path), batch, documents))
        augmented = tuple(augmented_rows)
        by_hash = {item.to_dict()["extraction_sha256"]: item
                   for item in (*primary, *challenger, *augmented)}
        selections = adjudication.get("selected_extractions", {})
        expected_sources = {document.source_id for document in batch.documents}
        if (not isinstance(selections, dict) or set(selections) != expected_sources
                or any(not isinstance(value, str) or value not in by_hash
                       or by_hash[value].source_id != source_id for source_id, value in selections.items())):
            raise DocumentError("REVIEW_STALE", "Selection does not cover the current source proposals", diagnostic={
                "schema_path": "$.selected_extractions", "validation_code": "SELECTED_PROPOSAL_BINDING_INVALID",
                "error_category": "SOURCE_BINDING"})
        selected = tuple(by_hash[selections[document.source_id]] for document in batch.documents)
        for extraction in selected:
            validate_rental_extraction(extraction, require_package_facts=True)
        if "native_review_receipt" not in state:
            active_stage = "FACT_REVIEW"
            started = perf_counter()
            native = review_with_codex(batch, selected, documents, model=model, semantic_guidance=guidance(),
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
        if native["status"] in {"REPAIR_REQUIRED", "WAITING_FOR_REQUIRED_INFORMATION"}:
            _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", stage="FACT_REVIEW",
                  review_status=native["status"])
            return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "stage": "FACT_REVIEW",
                    "job_state": str(path), "approved_for_delivery": False}
        review = native["review"]
        if native["visual_candidates_deferred"]:
            if "visual_review_receipt" not in state:
                active_stage = "VISUAL_FACT_REVIEW"
                started = perf_counter()
                visual = review_visual_with_codex(batch, selected, native, documents, semantic_guidance=guidance(),
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
            visual_stop = _visual_review_stop(visual)
            if visual_stop is not None:
                stop_status = visual_stop["status"]
                _save(path, state, stop_status, stage="VISUAL_FACT_REVIEW",
                      visual_review_status=stop_status,
                      **({"visual_structural_gaps": visual_stop["structural_gaps"]}
                         if "structural_gaps" in visual_stop else {}))
                return {**visual_stop, "stage": "VISUAL_FACT_REVIEW", "job_state": str(path),
                        "approved_for_delivery": False}
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
                        "extractions": [
                            state.get("adjudicator_extractions", {}).get(document.source_id)
                            if document.source_id in state.get("adjudicator_extractions", {}) else
                            (state["primary"][document.source_id]
                             if selected_item.to_dict()["extraction_sha256"] == primary_item.to_dict()["extraction_sha256"]
                             else state["challenger"][document.source_id])
                            for document, selected_item, primary_item in
                            zip(batch.documents, selected, primary, strict=True)],
                        "job_state": str(path), "approved_for_delivery": False}
            if attested is not None:
                review, review_path = attested
                state["fact_review_file"] = review_path
                _save(path, state, "VISUAL_ATTESTATION_REPLAYED")
        active_stage = "PACKAGE_SCOPE_REVIEW"
        from .scope_review import classification_plan, review_package_scope
        from againward.documents.resolution import entities_from_facts
        reviewed_entities = entities_from_facts(
            promote_facts(selected, review, batch, documents),
            non_entity_fields=NON_ENTITY_OBSERVATION_FIELDS)
        if classification_plan(reviewed_entities, selected) and "scope_review_receipt" not in state:
            scoped = review_package_scope(batch, selected, review, documents,
                                          model=model, timeout_seconds=timeout_seconds)
            saved = documents / "scope_reviews" / (scoped["receipt_sha256"] + ".json")
            write_json(saved, scoped)
            state["scope_review_receipt"] = str(saved)
            _save(path, state, "PACKAGE_SCOPE_REVIEWED", model_calls=scoped["model_calls"])
        scoped = (_receipt(state["scope_review_receipt"], documents, "scope_reviews", "receipt_sha256")
                  if "scope_review_receipt" in state else None)
        active_stage = "DOCUMENT_PACKAGE_VALIDATION"
        body = {"schema_version": DOCUMENT_CASE_SCHEMA, "batch": batch.to_dict(),
                "extractions": [item.to_dict() for item in selected], "fact_review": review,
                "rental_relationship_review": None, "credit_relationship_review": None}
        if scoped is not None:
            body["scope_review"] = scoped
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
        safe_diagnostic = _safe_failure_diagnostic(exc, stage=active_stage,
                                                   source_id=active_source_id)
        protocol_error = safe_diagnostic.get("error_category") in {
            "DECISION_COVERAGE", "SCHEMA_ERROR", "SCHEMA_SHAPE", "SCHEMA_TYPE", "SCHEMA_ENUM",
            "SCHEMA_REQUIRED", "SCHEMA_CLOSED_OBJECT", "SOURCE_BINDING", "SOURCE_DECISION_BINDING"}
        if (exc.code in {"EXTRACTION_INCOMPLETE", "STRUCTURAL_INCOMPLETE", "EXTRACTION_CONTRADICTION", "ENTITY_AMBIGUOUS"}
                and not protocol_error):
            _save(path, state, "WAITING_FOR_REQUIRED_INFORMATION", reason_code=exc.code,
                  failure_diagnostic=safe_diagnostic)
            return {"status": "WAITING_FOR_REQUIRED_INFORMATION", "reason_code": exc.code,
                    "stage": active_stage, "diagnostic": safe_diagnostic,
                    "job_state": str(path), "approved_for_delivery": False}
        if exc.code in RETRYABLE_MODEL_CODES:
            _save(path, state, "WAITING_MODEL_RETRY", reason_code=exc.code,
                  failure_diagnostic=safe_diagnostic)
            return {"status": "WAITING_MODEL_RETRY", "reason_code": exc.code,
                    "job_state": str(path), "approved_for_delivery": False}
        _save(path, state, "FAILED", reason_code=exc.code,
              failure_diagnostic=safe_diagnostic)
        return {"status": "FAILED", "reason_code": exc.code,
                "job_state": str(path), "approved_for_delivery": False}

    except ValueError as exc:
        diagnostic = {"stage": active_stage, "source_id": active_source_id,
            "validation_code": "INTERNAL_VALUE_ERROR", "error_category": "SCHEMA_ERROR",
            "schema_path": "$", "exception_type": type(exc).__name__}
        _save(path, state, "FAILED", reason_code="EXTRACTION_SCHEMA_INVALID", failure_diagnostic=diagnostic)
        return {"status": "FAILED", "reason_code": "EXTRACTION_SCHEMA_INVALID", "stage": active_stage,
                "diagnostic": diagnostic, "job_state": str(path), "approved_for_delivery": False}


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
