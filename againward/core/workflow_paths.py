"""Portable directory discovery for INDICIA client investigations.

This module only inspects paths.  It never creates, moves, or rewrites client data.
It lets commands accept either a standard workspace root, a Goal A case root, or
an already-resolved analysis directory without duplicating lifecycle logic.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CANONICAL_ARTIFACTS = (
    "privacy_manifest.json",
    "investigation_state.json",
    "questions.json",
    "analysis_inventory.json",
    "prepared_analysis.json",
    "candidate_signals.json",
    "evidence_card.json",
    "investigation.json",
    "review.json",
    "report.md",
    "human_review.json",
)


def _is_goal_a_root(path: Path) -> bool:
    return (path / "case_manifest.json").is_file() or (
        (path / "derived").is_dir()
        and (path / "evidence").is_dir()
        and (path / "investigation").is_dir()
    )


def _is_workspace_root(path: Path) -> bool:
    return (path / "workspace.json").is_file()


def resolve_case_layout(case_directory: str | Path) -> dict[str, Any]:
    """Resolve a user-facing case path to its canonical analysis directory.

    The result contains only paths and layout metadata, so it is safe to use
    before a case has been initialized.
    """

    supplied = Path(case_directory).expanduser()
    path = supplied.resolve(strict=False)

    if _is_workspace_root(path):
        case_root = path
        analysis_root = path / "processed"
        layout = "STANDARD_WORKSPACE"
    elif path.name == "processed" and _is_workspace_root(path.parent):
        case_root = path.parent
        analysis_root = path
        layout = "STANDARD_WORKSPACE"
    elif _is_goal_a_root(path):
        case_root = path
        analysis_root = path / "investigation"
        layout = "GOAL_A_CASE"
    elif path.name == "investigation" and _is_goal_a_root(path.parent):
        case_root = path.parent
        analysis_root = path
        layout = "GOAL_A_CASE"
    else:
        case_root = path
        analysis_root = path
        layout = "DIRECT_ANALYSIS_DIRECTORY"

    if layout == "STANDARD_WORKSPACE":
        directories = {
            "incoming": case_root / "incoming",
            "privacy": case_root / "privacy",
            "sanitized": case_root / "sanitized",
            "processed": case_root / "processed",
            "scratch": case_root / "scratch",
            "outputs": case_root / "outputs",
        }
    elif layout == "GOAL_A_CASE":
        directories = {
            "incoming": case_root / "incoming",
            "privacy": case_root / "privacy",
            "sanitized": case_root / "sanitized",
            "legacy_raw": case_root / "raw",
            "processed": case_root / "normalized",
            "derived": case_root / "derived",
            "evidence": case_root / "evidence",
            "investigation": case_root / "investigation",
            "outputs": case_root / "outputs",
            "logs": case_root / "logs",
        }
    else:
        directories = {"analysis": analysis_root}

    return {
        "layout": layout,
        "supplied_path": supplied,
        "case_root": case_root,
        "analysis_root": analysis_root,
        "directories": directories,
    }


def resolve_analysis_directory(case_directory: str | Path) -> Path:
    """Return the single directory owning canonical lifecycle artifacts."""

    return resolve_case_layout(case_directory)["analysis_root"]


def _read_json_object(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not path.is_file():
        return None, None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, str(exc)
    if not isinstance(value, dict):
        return None, "objet JSON attendu"
    return value, None


def _next_action(lifecycle: dict[str, Any] | None, privacy_state: str = "NOT_REQUIRED") -> str:
    if privacy_state == "PRIVACY_MIGRATION_REQUIRED":
        return "MIGRATE_LEGACY_WORKSPACE_BEFORE_ANALYSIS"
    if privacy_state == "AWAITING_PRIVACY_REVIEW":
        return "CODEX_PRIVACY_GATE_THEN_VALIDATE"
    if privacy_state == "PRIVACY_BLOCKED":
        return "STOP_PRIVACY_BLOCKED"
    if privacy_state == "PURGED":
        return "MISSION_PURGED_NO_FURTHER_ANALYSIS"
    if lifecycle is not None and lifecycle.get("state") == "PRIVACY_CLEARED":
        return "RUN_INTAKE_FROM_SANITIZED_SOURCE"
    if lifecycle is None:
        return "INITIALIZE_LIFECYCLE"
    state = lifecycle.get("state")
    if state == "WAITING_FOR_REQUIRED_INFORMATION":
        return "WAIT_OR_RECORD_RECEIVED_ANSWERS_AND_STOP"
    if state == "RESUMING":
        return "RECALCULATE_REVIEW_AND_COMPLETE_RESUME"
    if state == "FINALIZABLE":
        return "GENERATE_REVIEW_AND_REQUEST_HUMAN_APPROVAL"
    if state == "DELIVERABLE":
        return "DELIVER_APPROVED_REPORT"
    if state == "ANALYZING" and not lifecycle.get("existing_data_exhausted"):
        return "EXHAUST_AND_INVENTORY_EXISTING_DATA"
    if state == "ANALYZING":
        return "INVESTIGATE_THEN_SELECT_REQUESTS_OR_FINALIZE"
    return "REPAIR_INVALID_LIFECYCLE_STATE"


def inspect_case_status(case_directory: str | Path) -> dict[str, Any]:
    """Return a deterministic, read-only navigation and lifecycle summary."""

    layout = resolve_case_layout(case_directory)
    analysis_root: Path = layout["analysis_root"]
    from .artifact_store import JOURNAL
    recovery_required = (analysis_root / JOURNAL).exists()
    state_path = analysis_root / "investigation_state.json"
    state_payload, state_error = _read_json_object(state_path)
    lifecycle = None if state_payload is None else state_payload.get("client_lifecycle")
    if lifecycle is not None and not isinstance(lifecycle, dict):
        lifecycle = None
        state_error = "client_lifecycle doit être un objet"

    questions_payload, questions_error = _read_json_object(
        analysis_root / "questions.json"
    )
    questions = [] if questions_payload is None else questions_payload.get("questions", [])
    responses = [] if questions_payload is None else questions_payload.get("responses", [])
    if not isinstance(questions, list):
        questions = []
        questions_error = "questions doit être une liste"
    if not isinstance(responses, list):
        responses = []
        questions_error = "responses doit être une liste"

    artifacts = {
        name: {
            "path": str(analysis_root / name),
            "exists": (analysis_root / name).is_file(),
        }
        for name in CANONICAL_ARTIFACTS
    }
    # Local import avoids making path resolution depend on the privacy module.
    from .privacy import inspect_privacy_status, privacy_manifest_path
    privacy = inspect_privacy_status(layout["case_root"])
    from .contract_policy import inspect_contract_status
    contract = inspect_contract_status(layout["case_root"])
    if lifecycle is not None and not recovery_required:
        from .client_lifecycle import validate_client_lifecycle_artifacts
        try:
            lifecycle = validate_client_lifecycle_artifacts(analysis_root)
        except (OSError, ValueError) as exc:
            state_error = str(exc)
    privacy_path = privacy_manifest_path(layout["case_root"])
    artifacts["privacy_manifest.json"] = {
        "path": str(privacy_path),
        "exists": privacy_path.is_file(),
    }
    return {
        "schema_version": "indicia-case-status-v1",
        "layout": layout["layout"],
        "case_root": str(layout["case_root"]),
        "analysis_root": str(analysis_root),
        "directories": {
            name: str(path) for name, path in layout["directories"].items()
        },
        "lifecycle": lifecycle,
        "lifecycle_error": state_error,
        "questions_error": questions_error,
        "contract": contract,
        "privacy": {key: value for key, value in privacy.items() if key != "case_root"},
        "open_question_count": sum(
            1 for item in questions if isinstance(item, dict) and item.get("status") == "open"
        ),
        "response_count": len(responses),
        "next_action": ("RESOLVE_CONTRACT_POLICY_BEFORE_REAL_DATA" if not contract["allowed"] and privacy["state"] != "PURGED"
                        else "REPAIR_INVALID_LIFECYCLE_STATE" if state_error or questions_error
                        else _next_action(lifecycle, privacy["state"])),
        "artifacts": artifacts,
        "read_only": True,
        **({"next_action":"RECOVER_ARTIFACT_TRANSACTION", "lifecycle_error":"ARTIFACT_RECOVERY_REQUIRED"}
           if recovery_required else {}),
    }
