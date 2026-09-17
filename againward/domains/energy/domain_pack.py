"""Energy domain adapter: established numerical engine, shared investigation kernel."""
from __future__ import annotations
from dataclasses import asdict
from pathlib import Path
import time
from typing import Any
from againward.core.domain import DomainPreparation
from energy_mvp.analysis import analyze
from energy_mvp.evidence_card import build_evidence_card
from energy_mvp.intake import assess_intake, intake_template
from energy_mvp.io import load_data
from energy_mvp.positioning import positioning_payload
from energy_mvp.physical_diagnostics import physical_differential_template, physical_reasoning_contract
from energy_mvp.signals import detect_candidate_events
from energy_mvp.shadow import build_shadow_comparison
from energy_mvp.tariffs import calculate_tariff_cost, tariff_plan_from_dict
from energy_mvp.toolbox import inspect_dataset
from .evidence import EnergyEvidenceDataset


def _analysis_payload(result):
    payload=asdict(result)
    payload['start']=result.start.isoformat()
    payload['end']=result.end.isoformat()
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
        "- Zéro candidat ne prouve pas la normalité : examiner aussi profils, ruptures et couverture des prédictions.",
        "- Lire prediction_coverage et les catégories non supportées dans candidate_signals.json avant toute conclusion.",
        "- Pour chiffrer : distinguer bilan signé et aire positive ; utiliser quantify_baseline_sensitivity "
        "(energy_mvp.quantification) sur des références défendables et les mêmes intervalles.",
        "- Une plage entre baselines est une sensibilité, jamais un intervalle de confiance. "
        "Si les références ne sont pas comparables ou le signe change, s'abstenir de chiffrer.",
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


class EnergyDomainPack:
    name = "energy"
    review_checks = ("calculations", "data_quality", "baseline_robustness",
                     "alternative_explanations", "causality", "annualization",
                     "recoverable_saving", "double_counting")
    intake_template = staticmethod(intake_template)
    analyst_brief = staticmethod(_brief)

    def prepare(self, source: Path, *, source_sha256, intake, options, evidence_plane_mode):
        source_path = source
        default_tariff = options.get("default_tariff")
        context = intake
        resolved_load_options = dict(options.get("load_options") or {})
        if evidence_plane_mode == "legacy" and "preserve_auxiliary_fields" not in resolved_load_options:
            resolved_load_options["preserve_auxiliary_fields"] = False
        declared_timezone = (context.get("site") or {}).get("timezone")
        if declared_timezone and "site_timezone" not in resolved_load_options:
            resolved_load_options["site_timezone"] = declared_timezone
        loaded = load_data(source_path, **resolved_load_options)
        source_sha256 = source_sha256
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

        dataset = None
        evidence_started = time.perf_counter()
        if evidence_plane_mode != "legacy":
            dataset = EnergyEvidenceDataset.from_loaded_data(loaded, source_sha256=source_sha256)
        state = {
            "service_positioning": positioning_payload(),
            "dataset": inspect_dataset(loaded),
            "intake_assessment": intake_assessment.to_dict(),
            "candidate_detection": candidates,
            "costing": {
                "method": "time_of_use_and_demand" if tariff_cost is not None else "flat_or_source",
                "structured_artifact": "tariff_cost.json" if tariff_cost is not None else None,
                "recoverable_saving_calculated": False,
            },
            "physical_reasoning_contract": physical_reasoning_contract(),
            "prohibited_shortcuts": ["candidate_signal_as_confirmed_opportunity", "causal_claim_without_evidence",
                                     "recoverable_saving_without_assumption", "ground_truth_access_during_investigation"],
        }
        artifacts = {"intake_assessment.json": intake_assessment.to_dict(),
                     "prepared_analysis.json": _analysis_payload(automatic),
                     "candidate_signals.json": candidates,
                     "physical_differential_template.json": physical_differential_template()}
        if tariff_cost is not None:
            artifacts["tariff_cost.json"] = tariff_cost
        return DomainPreparation(state, artifacts, dataset,
            trace_details={"load_options": resolved_load_options,
                           "default_tariff_supplied": effective_default_tariff is not None},
            runtime={"evidence_mode": evidence_plane_mode, "legacy_elapsed": legacy_elapsed,
                     "evidence_started": evidence_started})

    def evidence_card(self, preparation, session):
        card = build_evidence_card(preparation.evidence_dataset,
            inspection=preparation.state["dataset"],
            candidates=preparation.state["candidate_detection"], session=session)
        if preparation.runtime["evidence_mode"] == "shadow":
            preparation.artifacts["shadow_comparison.json"] = build_shadow_comparison(
                preparation.evidence_dataset, candidates=preparation.state["candidate_detection"],
                evidence_card=card, session=session,
                timings_seconds={"legacy_candidate_detection": round(preparation.runtime["legacy_elapsed"], 6),
                                 "evidence_snapshot_and_card": round(time.perf_counter()-preparation.runtime["evidence_started"],6)})
        return card
