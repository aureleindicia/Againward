from __future__ import annotations

import hashlib
import json
import time
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .analysis import analyze
from .evidence_card import build_evidence_card
from .evidence_plane import EvidenceDataset
from .evidence_protocol import EvidenceQuerySession, query_contract
from .intake import assess_intake, intake_template
from .io import load_data
from .positioning import positioning_payload
from .physical_diagnostics import physical_differential_template, physical_reasoning_contract
from .signals import detect_candidate_events
from .shadow import build_shadow_comparison
from .tariffs import calculate_tariff_cost, tariff_plan_from_dict
from .toolbox import inspect_dataset


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _fingerprint(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _analysis_payload(result: Any) -> dict[str, Any]:
    payload = asdict(result)
    payload["start"] = result.start.isoformat()
    payload["end"] = result.end.isoformat()
    return payload


def _brief(state: dict[str, Any]) -> str:
    candidates = state["candidate_detection"]
    missing = state["intake_assessment"]["missing_critical"]
    lines = [
        "# Dossier d'exploration Codex — nouveau client", "",
        "Ce document ne contient aucune conclusion confirmée. Il prépare une investigation "
        "sur un dataset inconnu sans accès à une vérité terrain.", "",
        "L'objectif n'est pas de préparer un autre audit : l'investigation doit détecter et "
        "quantifier les dérives, éliminer les fausses pistes, cibler les contrôles terrain puis "
        "mesurer l'effet d'une correction. Elle peut aussi guider un intervenant technique.", "",
        "## Garde-fous", "",
        "- Ne jamais ouvrir ni demander de fichier de ground truth.",
        "- Les événements automatiques sont uniquement des signaux candidats.",
        "- Python ne choisit jamais une cause, une question, une intervention ou une décision.",
        "- Les fiches knowledge/physical_diagnostics sont des références non exhaustives.",
        "- Python calcule; Codex choisit les tests, interprète, critique et conclut.",
        "- Ne pas quantifier une économie récupérable sans preuve opérationnelle.", "",
        "## État initial", "",
        f"- Source empreinte SHA-256 : `{state['source']['sha256']}`.",
        f"- Lignes valides : {state['dataset']['rows']}.",
        f"- Détection générique : {candidates['status']}.",
        f"- Signaux candidats : {len(candidates.get('events', []))}.",
        f"- Informations critiques manquantes : {len(missing)}.", "",
        "## Travail attendu de Codex", "",
        "1. Lire l'inspection, le contexte client et les limites de capacité.",
        "2. Examiner les signaux sans supposer qu'ils sont anormaux ou évitables.",
        "3. Formuler plusieurs hypothèses concurrentes par piste retenue.",
        "4. Choisir des périodes comparables et plusieurs baselines lorsque pertinent.",
        "5. Demander les calculs déterministes nécessaires dans `scratch/`.",
        "6. Chercher au moins une contre-explication matérielle.",
        "7. Rejeter, réserver ou confirmer le comportement observé.",
        "8. Si la preuve manque, demander l'information minimale précise.",
        "9. Soumettre toute conclusion à une review contradictoire et humaine.", "",
    ]
    evidence = state.get("evidence_plane")
    if evidence and evidence.get("enabled"):
        lines.extend([
            "## Evidence Plane interactif", "",
            "La carte initiale est volontairement compacte et ne préserve pas toutes les relations. "
            "Utiliser le protocole borné pour tester les hypothèses choisies par Codex.", "",
            f"- Dataset probatoire : `{evidence['dataset_id']}`.",
            f"- Mode de migration : `{evidence['mode']}`.",
            "- Commande : `python query_evidence.py DOSSIER REQUEST.json`.",
            "- Les répétitions et dépassements de budget sont refusés et audités.",
            "- Chaque conclusion conservée doit citer des query IDs et des handles de récupération.",
            "- Si la preuve reste insuffisante, enregistrer une abstention explicite.", "",
        ])
    lines.extend([
        "Les fichiers `prepared_analysis.json`, `candidate_signals.json`, `intake_assessment.json` "
        "et `investigation_state.json` restent des sources quantitatives initiales. `evidence_card.json` "
        "et le protocole exécutable les augmentent lorsqu’ils sont activés. Les templates vides "
        "documentent le contrat mais ne constituent pas une investigation.", "",
    ])
    return "\n".join(lines)


def prepare_investigation(
    source: str | Path,
    output_directory: str | Path,
    *,
    intake: dict[str, Any] | None = None,
    default_tariff: float | None = None,
    load_options: dict[str, Any] | None = None,
    evidence_plane_mode: str = "preferred",
) -> dict[str, Any]:
    """Prépare un dossier générique; ne formule ni hypothèse ni décision à la place de Codex."""

    source_path = Path(source)
    output = Path(output_directory)
    output.mkdir(parents=True, exist_ok=True)
    if evidence_plane_mode not in {"preferred", "shadow", "legacy"}:
        raise ValueError("evidence_plane_mode doit valoir preferred, shadow ou legacy.")
    protected_outputs = (
        "investigation_state.json", "trace.json", "questions.json", "human_review.json",
        "prepared_analysis.json", "candidate_signals.json", "physical_differential_template.json",
        "evidence_dataset.json", "evidence_query_session.json", "evidence_card.json",
    )
    existing_outputs = [name for name in protected_outputs if (output / name).exists()]
    if existing_outputs:
        raise FileExistsError(
            "Le dossier contient déjà une investigation et ne sera pas réinitialisé: "
            + ", ".join(existing_outputs)
            + ". Utilisez un nouveau dossier ou archivez explicitement le cycle existant."
        )
    context = deepcopy(intake) if intake is not None else intake_template()
    resolved_load_options = dict(load_options or {})
    if evidence_plane_mode == "legacy" and "preserve_auxiliary_fields" not in resolved_load_options:
        resolved_load_options["preserve_auxiliary_fields"] = False
    declared_timezone = (context.get("site") or {}).get("timezone")
    if declared_timezone and "site_timezone" not in resolved_load_options:
        resolved_load_options["site_timezone"] = declared_timezone
    loaded = load_data(source_path, **resolved_load_options)
    source_sha256 = _fingerprint(source_path)
    source_unit = (
        loaded.source_units.get("power")
        if loaded.measurement_kind.value == "power"
        else loaded.source_units.get("energy")
    )
    requested_timestamp_position = resolved_load_options.get("timestamp_position")
    intake_assessment = assess_intake(context, evidence={
        "measurement_kind": loaded.measurement_kind.value,
        "unit": source_unit,
        "timestamp_position": loaded.timestamp_position,
        "timestamp_position_is_authoritative": (
            loaded.measurement_kind.value == "cumulative_energy"
            or requested_timestamp_position in {"start", "end"}
        ),
        "production_available_in_dataset": (
            "production" in loaded.columns or "production_active" in loaded.columns
        ),
        "temperature_available_in_dataset": "temperature" in loaded.columns,
    })
    cost_context = context.get("cost") or {}
    effective_default_tariff = (
        default_tariff
        if default_tariff is not None
        else cost_context.get("flat_price_per_kwh")
    )
    automatic = analyze(
        loaded, source=str(source_path), default_tariff=effective_default_tariff
    )
    tariff_cost = None
    if cost_context.get("time_of_use_periods") or cost_context.get(
        "demand_charge_per_kw_month"
    ) is not None:
        tariff_cost = calculate_tariff_cost(
            loaded.readings, tariff_plan_from_dict(cost_context)
        )
    legacy_started = time.perf_counter()
    try:
        candidates = detect_candidate_events(loaded)
    except ValueError as exc:
        candidates = {
            "status": "unavailable",
            "reason": str(exc),
            "events": [],
            "disabled_signal_families": ["generic_multi_event_detection"],
        }
    legacy_elapsed = time.perf_counter() - legacy_started
    evidence_dataset = None
    evidence_session = None
    evidence_card = None
    evidence_elapsed = 0.0
    shadow_comparison = None
    if evidence_plane_mode != "legacy":
        evidence_started = time.perf_counter()
        evidence_dataset = EvidenceDataset.from_loaded_data(
            loaded, source_sha256=source_sha256
        )
        evidence_session = EvidenceQuerySession.create(evidence_dataset)
        evidence_card = build_evidence_card(
            evidence_dataset,
            inspection=inspect_dataset(loaded),
            candidates=candidates,
            session=evidence_session,
        )
        evidence_elapsed = time.perf_counter() - evidence_started
        if evidence_plane_mode == "shadow":
            shadow_comparison = build_shadow_comparison(
                evidence_dataset,
                candidates=candidates,
                evidence_card=evidence_card,
                session=evidence_session,
                timings_seconds={
                    "legacy_candidate_detection": round(legacy_elapsed, 6),
                    "evidence_snapshot_and_card": round(evidence_elapsed, 6),
                },
            )
    prepared_at = datetime.now(timezone.utc).isoformat()
    state = {
        "schema_version": 1,
        "status": "awaiting_codex_exploration",
        "service_positioning": positioning_payload(),
        "prepared_at_utc": prepared_at,
        "source": {
            "name": source_path.name,
            "sha256": source_sha256,
            "ground_truth_available_to_investigation": False,
        },
        "dataset": inspect_dataset(loaded),
        "intake_assessment": intake_assessment.to_dict(),
        "candidate_detection": candidates,
        "evidence_plane": {
            "enabled": evidence_dataset is not None,
            "mode": evidence_plane_mode,
            "authoritative_for_agent_queries": evidence_dataset is not None,
            "legacy_candidate_path_retained": True,
            "dataset_id": evidence_dataset.dataset_id if evidence_dataset else None,
            "dataset_sha256": evidence_dataset.dataset_sha256 if evidence_dataset else None,
            "query_session": "evidence_query_session.json" if evidence_dataset else None,
            "evidence_card": "evidence_card.json" if evidence_dataset else None,
            "rollback": "rerun a new case directory with evidence_plane_mode=legacy",
            "shadow_comparison": "shadow_comparison.json" if shadow_comparison else None,
        },
        "costing": {
            "method": "time_of_use_and_demand" if tariff_cost is not None else "flat_or_source",
            "structured_artifact": "tariff_cost.json" if tariff_cost is not None else None,
            "recoverable_saving_calculated": False,
        },
        "separation_of_responsibilities": {
            "python": "normalisation, calculs, signaux candidats et preuves numériques",
            "codex": "choix des analyses, hypothèses, falsification, décisions et synthèse",
            "knowledge": "référence non exhaustive de mécanismes, variables, tests, limites et risques",
        },
        "agentic_investigation_loop": {
            "enabled": evidence_dataset is not None,
            "initial_overview": "evidence_card.json" if evidence_dataset else "prepared_analysis.json",
            "steps": [
                "form_competing_hypotheses",
                "request_bounded_evidence",
                "inspect_result_and_source_handles",
                "test_best_alternative_explanation",
                "request_new_evidence_only_if_decision_relevant",
                "record_evidence_linked_finding_or_abstain",
                "adversarial_review",
            ],
            "termination": [
                "hypothesis_falsified",
                "sufficient_evidence_for_calibrated_finding",
                "explicit_abstention_due_to_evidence_gap",
                "query_budget_exhausted",
                "human_or_field_information_required",
            ],
            "deterministic_engine_makes_final_decisions": False,
        },
        "physical_reasoning_contract": physical_reasoning_contract(),
        "required_artifacts_before_delivery": [
            "investigation.json",
            "review.json",
            "report.md",
            "human_review.json",
        ] + (["agent_findings.json"] if evidence_dataset is not None else []),
        "prohibited_shortcuts": [
            "candidate_signal_as_confirmed_opportunity",
            "causal_claim_without_evidence",
            "recoverable_saving_without_assumption",
            "ground_truth_access_during_investigation",
        ],
    }
    _write_json(output / "intake.json", context)
    _write_json(output / "intake_assessment.json", intake_assessment.to_dict())
    _write_json(output / "prepared_analysis.json", _analysis_payload(automatic))
    _write_json(output / "candidate_signals.json", candidates)
    if evidence_dataset is not None and evidence_session is not None and evidence_card is not None:
        _write_json(output / "evidence_dataset.json", evidence_dataset.to_dict())
        _write_json(output / "evidence_query_session.json", evidence_session.to_dict())
        _write_json(output / "evidence_query_contract.json", query_contract())
        _write_json(output / "evidence_card.json", evidence_card)
        _write_json(output / "agent_findings_template.json", {
            "schema_version": "indicia-agent-findings-v1",
            "ground_truth_used": False,
            "findings": [],
            "instructions": {
                "conserved_findings_require": [
                    "evidence_query_ids", "evidence_handles", "alternative_explanations_tested",
                ],
                "abstention_requires": ["claim_or_abstention", "evidence_gap"],
            },
        })
        if shadow_comparison is not None:
            _write_json(output / "shadow_comparison.json", shadow_comparison)
    if tariff_cost is not None:
        _write_json(output / "tariff_cost.json", tariff_cost)
    _write_json(output / "investigation_state.json", state)
    _write_json(output / "questions.json", {
        "schema_version": 1,
        "investigation_sha256": None,
        "published_at_utc": None,
        "questions": [],
        "responses": [],
    })
    _write_json(output / "human_review.json", {
        "schema_version": 1,
        "status": "not_reviewed",
        "reviewer_role": None,
        "reviewed_at_utc": None,
        "approved_for_delivery": False,
        "reservations": [],
    })
    _write_json(output / "investigation_template.json", {
        "schema_version": 1,
        "ground_truth_used": False,
        "evidence_plane_session": evidence_session.session_id if evidence_session else None,
        "hypotheses": [],
        "recommendations": [],
        "evidence_requirements": {
            "each_retained_hypothesis": [
                "evidence_query_ids", "evidence_handles", "best_reason_false",
            ],
            "insufficient_evidence": "abstain or request the minimum decision-relevant information",
        } if evidence_session else None,
    })
    _write_json(output / "physical_differential_template.json", physical_differential_template())
    _write_json(output / "review_template.json", {
        "schema_version": 1,
        "ground_truth_used": False,
        "required_checks": [
            "calculations", "data_quality", "baseline_robustness",
            "alternative_explanations", "causality", "annualization",
            "recoverable_saving", "double_counting",
        ],
        "reviewed_hypotheses": [],
    })
    _write_json(output / "answers_template.json", {
        "answers": [{
            "request_id": "REMPLACER",
            "answer": "REMPLACER",
            "provided_by_role": "REMPLACER",
            "source_or_evidence": "REMPLACER",
        }],
    })
    (output / "ANALYST_BRIEF.md").write_text(_brief(state), encoding="utf-8")
    _write_json(output / "trace.json", {
        "schema_version": 1,
        "entries": [{
            "at_utc": prepared_at,
            "action": "prepare_investigation",
            "source_sha256": state["source"]["sha256"],
            "load_options": resolved_load_options,
            "default_tariff_supplied": effective_default_tariff is not None,
            "output_files": [
                "intake.json", "intake_assessment.json", "prepared_analysis.json",
                "candidate_signals.json", "investigation_state.json", "questions.json",
                "human_review.json", "investigation_template.json", "physical_differential_template.json", "review_template.json",
                "answers_template.json", "ANALYST_BRIEF.md",
            ]
            + (["tariff_cost.json"] if tariff_cost is not None else [])
            + ([
                "evidence_dataset.json", "evidence_query_session.json",
                "evidence_query_contract.json", "evidence_card.json",
                "agent_findings_template.json",
            ] + (["shadow_comparison.json"] if shadow_comparison is not None else [])
            if evidence_dataset is not None else []),
            "evidence_plane_mode": evidence_plane_mode,
        }],
    })
    return state
