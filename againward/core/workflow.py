"""Shared case preparation; domain packs supply intelligence, never lifecycle."""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

from .artifact_store import transaction, write_json, read_json
from .client_lifecycle import initialize_client_lifecycle, begin_privacy_cleared_analysis
from .domain import DomainPack
from .privacy import assert_source_approved_for_analysis, case_root_for_path, privacy_requirement
from againward.evidence.protocol import EvidenceQuerySession, query_contract


def fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def prepare_investigation(source: str | Path, output_directory: str | Path, *,
                          domain: DomainPack, intake: dict[str, Any] | None = None,
                          options: dict[str, Any] | None = None,
                          evidence_plane_mode: str = "preferred") -> dict[str, Any]:
    source = Path(source)
    output = Path(output_directory)
    if evidence_plane_mode not in {"preferred", "shadow", "legacy"}:
        raise ValueError("evidence_plane_mode doit valoir preferred, shadow ou legacy.")
    owner = case_root_for_path(source) or case_root_for_path(output)
    requirement = privacy_requirement(owner or output)
    if requirement["legacy"]:
        raise ValueError("Workspace historique: migration privacy explicite requise avant analyse.")
    if requirement["required"]:
        assert_source_approved_for_analysis(source, output_directory=output)
    if owner and (owner / "workspace.json").is_file():
        declared = read_json(owner / "workspace.json").get("domain")
        if declared and declared != domain.name:
            raise ValueError("Selected domain differs from the workspace domain.")
    output.mkdir(parents=True, exist_ok=True)
    with transaction(output):
        protected = ("trace.json", "human_review.json", "prepared_analysis.json",
                     "candidate_signals.json", "evidence_dataset.json", "evidence_query_session.json")
        existing = [name for name in protected if (output / name).exists()]
        if existing:
            raise FileExistsError("Le dossier contient déjà une investigation et ne sera pas réinitialisé: "
                                  + ", ".join(existing))
        previous = initialize_client_lifecycle(output)["client_lifecycle"]
        if requirement["required"]:
            previous = begin_privacy_cleared_analysis(owner or output)["client_lifecycle"]
        context = deepcopy(intake) if intake is not None else domain.intake_template()
        source_sha256 = fingerprint(source)
        prepared = domain.prepare(source, source_sha256=source_sha256, intake=context,
                                  options=dict(options or {}), evidence_plane_mode=evidence_plane_mode)
        dataset = prepared.evidence_dataset
        session = EvidenceQuerySession.create(dataset) if dataset is not None else None
        artifacts = dict(prepared.artifacts)
        prepared_at = datetime.now(timezone.utc).isoformat()
        state = {
            "schema_version": 1, "domain": domain.name,
            "status": "awaiting_codex_exploration", "prepared_at_utc": prepared_at,
            "source": {"name": source.name, "sha256": source_sha256,
                       "ground_truth_available_to_investigation": False},
            **prepared.state,
            "evidence_plane": {
                "enabled": dataset is not None, "mode": evidence_plane_mode,
                "authoritative_for_agent_queries": dataset is not None,
                "legacy_candidate_path_retained": True,
                "dataset_id": dataset.dataset_id if dataset else None,
                "dataset_sha256": dataset.dataset_sha256 if dataset else None,
                "query_session": "evidence_query_session.json" if dataset else None,
                "evidence_card": "evidence_card.json" if dataset else None,
                "rollback": "rerun a new case directory with evidence_plane_mode=legacy",
                "shadow_comparison": None,
            },
            "separation_of_responsibilities": {
                "python": "normalisation, calculs, signaux candidats et preuves numériques",
                "codex": "choix des analyses, hypothèses, falsification, décisions et synthèse",
                "knowledge": "référence non exhaustive de mécanismes, variables, tests, limites et risques",
            },
            "agentic_investigation_loop": {
                "enabled": dataset is not None,
                "initial_overview": "evidence_card.json" if dataset else "prepared_analysis.json",
                "steps": ["form_competing_hypotheses", "request_bounded_evidence",
                          "inspect_result_and_source_handles", "test_best_alternative_explanation",
                          "request_new_evidence_only_if_decision_relevant",
                          "record_evidence_linked_finding_or_abstain", "adversarial_review"],
                "termination": ["hypothesis_falsified", "sufficient_evidence_for_calibrated_finding",
                                "explicit_abstention_due_to_evidence_gap", "query_budget_exhausted",
                                "human_or_field_information_required"],
                "deterministic_engine_makes_final_decisions": False,
            },
            "required_artifacts_before_delivery": ["investigation.json", "review.json", "report.md",
                                                  "human_review.json"] + (["agent_findings.json"] if dataset else []),
        }
        if previous is not None:
            state["client_lifecycle"] = previous
        artifacts["intake.json"] = context
        if dataset is not None and session is not None:
            artifacts.update({"evidence_dataset.json": dataset.to_dict(),
                              "evidence_query_session.json": session.to_dict(),
                              "evidence_query_contract.json": query_contract(),
                              "evidence_card.json": domain.evidence_card(prepared, session),
                              "agent_findings_template.json": {
                                  "schema_version": "indicia-agent-findings-v1", "ground_truth_used": False,
                                  "findings": [], "instructions": {"conserved_findings_require": [
                                      "evidence_query_ids", "evidence_handles", "alternative_explanations_tested"],
                                      "abstention_requires": ["claim_or_abstention", "evidence_gap"]}}})
            # Optional comparative artifacts are produced by the domain's card builder.
            artifacts.update(prepared.artifacts)
            if "shadow_comparison.json" in artifacts:
                state["evidence_plane"]["shadow_comparison"] = "shadow_comparison.json"
        artifacts["investigation_state.json"] = state
        if not (output / "questions.json").exists():
            artifacts["questions.json"] = {"schema_version": "indicia-client-questions-v2",
                                           "questions": [], "responses": [], "cycle_history": []}
        artifacts.update({
            "human_review.json": {"schema_version": 1, "status": "not_reviewed", "reviewer_role": None,
                                  "reviewed_at_utc": None, "approved_for_delivery": False, "reservations": []},
            "investigation_template.json": {
                "schema_version": 1, "ground_truth_used": False,
                "evidence_plane_session": session.session_id if session else None,
                "hypotheses": [], "recommendations": [],
                "evidence_requirements": {"each_retained_hypothesis": ["evidence_query_ids", "evidence_handles", "best_reason_false"],
                                          "insufficient_evidence": "abstain or request the minimum decision-relevant information"} if session else None},
            "review_template.json": {"schema_version": 1, "ground_truth_used": False,
                                     "required_checks": list(domain.review_checks), "reviewed_hypotheses": []},
            "answers_template.json": {"answers": [{"request_id": "REMPLACER", "answer": "REMPLACER",
                "provided_by_role": "REMPLACER", "source_or_evidence": "REMPLACER",
                "source_type": "CLIENT_DECLARATION", "provided_at_utc": "REMPLACER", "reliability": 0.6}]},
        })
        artifacts["trace.json"] = {"schema_version": 1, "entries": [{
            "at_utc": prepared_at, "action": "prepare_investigation", "domain": domain.name,
            "source_sha256": source_sha256, **prepared.trace_details,
            "output_files": [*artifacts, "ANALYST_BRIEF.md"], "evidence_plane_mode": evidence_plane_mode}]}
        for name, payload in artifacts.items():
            if Path(name).is_absolute() or ".." in Path(name).parts:
                raise ValueError("Domain output must be local to the investigation.")
            write_json(output / name, payload)
        # Brief is non-authoritative; all canonical JSON commits through the redo journal.
        (output / "ANALYST_BRIEF.md").write_text(domain.analyst_brief(state), encoding="utf-8")
        return state
