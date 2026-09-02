from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from energy_mvp.minimal_attribution import (
    UNKNOWN_ASSET_ID,
    AnonymousElectricalComponent,
    ComponentOccurrence,
    EquipmentRecord,
    EvidenceItem,
    EvidenceLedger,
    EvidenceLevel,
    IdentifiabilityStatus,
    MicroQuestion,
    NaturalOperationalEvent,
    assess_attribution,
    build_anonymous_component,
    build_evidence_finding,
    evidence_from_natural_event,
    plan_temporary_measurement,
    rank_micro_questions,
    reuse_historical_anchor,
    validate_evidence_finding,
)


def component(**overrides):
    values = {
        "component_id": "PX-C01",
        "amplitude_kw": 5.1,
        "typical_start_hour": 6.0,
        "typical_stop_hour": 18.0,
        "duration_hours": 12.0,
        "frequency_per_day": 1.0,
        "operating_days": (0, 1, 2, 3, 4),
        "stability": 0.9,
        "repeatability": 0.9,
        "occurrence_count": 20,
        "production_relation": "dependent",
        "source_refs": ("signal-run.json#/C01",),
    }
    values.update(overrides)
    return AnonymousElectricalComponent(**values)


def asset(asset_id="pump_1", **overrides):
    values = {
        "asset_id": asset_id,
        "name": None,
        "family": "pump",
        "nominal_power_kw": 5.0,
        "usual_start_hour": 6.0,
        "usual_stop_hour": 18.0,
        "operating_days": (0, 1, 2, 3, 4),
        "operation_mode": "continuous",
        "production_dependency": "dependent",
    }
    values.update(overrides)
    return EquipmentRecord(**values)


def evidence(evidence_id, direction, candidates, reliability=0.9, **overrides):
    values = {
        "evidence_id": evidence_id,
        "kind": "operator_check",
        "direction": direction,
        "candidate_ids": tuple(candidates),
        "reliability": reliability,
        "observed_at": "2026-03-10T08:00:00+01:00",
        "provenance": "field-note.json#/checks/0",
        "statement": "Observation locale datée.",
    }
    values.update(overrides)
    return EvidenceItem(**values)


def test_partial_inventory_preserves_unknown_fields():
    record = EquipmentRecord(asset_id="A")
    payload = record.to_dict()
    assert payload["nominal_power_kw"] is None
    assert "nominal_power_kw" in payload["unknown_fields"]
    assert payload["name"] is None


def test_occurrences_build_anonymous_signature_with_provenance_not_submetering():
    start = datetime(2026, 3, 2, 6, tzinfo=timezone.utc)
    occurrences = [
        ComponentOccurrence(
            start + timedelta(days=index),
            start + timedelta(days=index, hours=12),
            5.0 + 0.05 * index,
            True,
            f"events.json#/{index}",
        )
        for index in range(5)
    ]
    result = build_anonymous_component("C01", occurrences)
    assert result.occurrence_count == 5
    assert result.amplitude_kw == pytest.approx(5.1)
    assert result.production_relation == "dependent"
    assert result.repeatability > 0.9
    assert result.separation_status == "aggregate_signature_not_submetering"
    assert result.to_dict()["claim_boundary"].startswith("signature électrique agrégée")


def test_empty_occurrences_and_invalid_occurrence_are_rejected():
    with pytest.raises(ValueError, match="Au moins une"):
        build_anonymous_component("C", [])
    point = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="durée"):
        ComponentOccurrence(point, point, 2.0, None, "x")


def test_component_hour_summary_is_circular_across_midnight():
    occurrences = [
        ComponentOccurrence(
            datetime(2026, 1, 1 + index, 23, 50 if index == 0 else 55, tzinfo=timezone.utc),
            datetime(2026, 1, 2 + index, 1, tzinfo=timezone.utc),
            3.0,
            False,
            f"x#/{index}",
        )
        for index in range(2)
    ]
    result = build_anonymous_component("C-midnight", occurrences)
    assert result.typical_start_hour is not None
    assert result.typical_start_hour > 23.5 or result.typical_start_hour < 0.5


def test_unknown_candidate_is_always_present_and_score_is_not_probability():
    assessment = assess_attribution(component(), [asset()], method="contextual")
    assert UNKNOWN_ASSET_ID in {item.asset_id for item in assessment.candidates}
    assert assessment.posterior_probability is None
    assert assessment.posterior_status.startswith("not_computed")


def test_context_can_disambiguate_same_power_assets():
    inventory = [
        asset("pump_day"),
        asset(
            "pump_night",
            usual_start_hour=20.0,
            usual_stop_hour=4.0,
            operating_days=(5, 6),
            production_dependency="independent",
        ),
    ]
    amplitude = assess_attribution(component(), inventory, method="amplitude_only")
    contextual = assess_attribution(component(), inventory, method="contextual")
    assert amplitude.selected_asset_id is None
    assert amplitude.identifiability == IdentifiabilityStatus.OBSERVATIONALLY_EQUIVALENT
    assert contextual.selected_asset_id == "pump_day"
    assert contextual.evidence_level == EvidenceLevel.PROBABLE_ASSET


def test_observational_equivalence_says_more_same_data_will_not_help():
    inventory = [asset("pump_1"), asset("pump_2")]
    assessment = assess_attribution(component(), inventory)
    assert assessment.selected_asset_id is None
    assert assessment.identifiability == IdentifiabilityStatus.OBSERVATIONALLY_EQUIVALENT
    assert assessment.more_same_type_data_will_help is False


def test_overlap_ambiguity_blocks_apparent_large_asset_without_anchor():
    aggregate = component(amplitude_kw=10.0, separation_status="overlap_ambiguous")
    assessment = assess_attribution(
        aggregate,
        [asset("large", nominal_power_kw=10.0)],
    )
    assert assessment.selected_asset_id is None
    assert assessment.identifiability == IdentifiabilityStatus.INSUFFICIENT_EVIDENCE
    assert assessment.more_same_type_data_will_help is False


def test_declared_unreliable_registry_field_is_neutralized():
    uncertain = asset(
        "A",
        usual_start_hour=20.0,
        metadata={"field_reliability": {"start_hour": 0.0}},
    )
    assessment = assess_attribution(component(), [uncertain])
    candidate = next(item for item in assessment.candidates if item.asset_id == "A")
    assert candidate.feature_scores["start_hour"] == 0.5


def test_absent_asset_does_not_force_least_bad_candidate():
    inventory = [asset("oven", family="oven", nominal_power_kw=50.0)]
    assessment = assess_attribution(component(amplitude_kw=2.0), inventory)
    assert assessment.selected_asset_id is None
    assert assessment.identifiability == IdentifiabilityStatus.LIKELY_ABSENT_FROM_INVENTORY
    assert assessment.candidates[0].asset_id == UNKNOWN_ASSET_ID


def test_insufficient_signature_prevents_naming_even_with_perfect_registry_match():
    assessment = assess_attribution(
        component(occurrence_count=1, repeatability=0.2, stability=0.4), [asset()]
    )
    assert assessment.selected_asset_id is None
    assert assessment.identifiability == IdentifiabilityStatus.INSUFFICIENT_EVIDENCE
    assert assessment.evidence_level == EvidenceLevel.DETECTABLE_CHANGE


def test_direct_anchor_can_reach_robust_attribution_but_never_mechanism():
    anchor = evidence(
        "E-anchor",
        "supports",
        ["pump_1"],
        source_class="temporary_measurement",
        anchor_verified=True,
    )
    assessment = assess_attribution(component(), [asset()], evidence=[anchor], method="evidence_aware")
    assert assessment.selected_asset_id == "pump_1"
    assert assessment.evidence_level == EvidenceLevel.ROBUST_ATTRIBUTION
    assert assessment.evidence_level < EvidenceLevel.PHYSICAL_MECHANISM
    finding = build_evidence_finding(component(), assessment)
    assert "physical_mechanism" in finding["forbidden_claims"]
    assert finding["posterior_probability"] is None


def test_high_reliability_contradiction_eliminates_candidate():
    contradiction = evidence(
        "E-no", "contradicts", ["pump_1"], reliability=0.95, anchor_verified=True
    )
    assessment = assess_attribution(
        component(), [asset()], evidence=[contradiction], method="evidence_aware"
    )
    candidate = next(item for item in assessment.candidates if item.asset_id == "pump_1")
    assert candidate.eliminated
    assert assessment.selected_asset_id is None


def test_unverified_high_confidence_statement_cannot_hard_eliminate():
    contradiction = evidence("E-rumour", "contradicts", ["pump_1"], reliability=0.95)
    assessment = assess_attribution(
        component(), [asset()], evidence=[contradiction], method="evidence_aware"
    )
    candidate = next(item for item in assessment.candidates if item.asset_id == "pump_1")
    assert candidate.eliminated is False


def test_ledger_is_append_only_and_preserves_contradictions():
    ledger = EvidenceLedger("PX-C01")
    ledger.append(evidence("E1", "supports", ["pump_1"]))
    ledger.append(evidence("E2", "contradicts", ["pump_1"]))
    with pytest.raises(ValueError, match="déjà présent"):
        ledger.append(evidence("E1", "supports", ["pump_1"]))
    payload = ledger.to_dict()
    assert payload["append_only"] is True
    assert [item["direction"] for item in payload["items"]] == ["supports", "contradicts"]


def test_ledger_revision_supersedes_but_does_not_erase_prior_evidence():
    ledger = EvidenceLedger("PX-C01")
    ledger.append(evidence("E-old", "supports", ["pump_1"]))
    ledger.append(
        evidence(
            "E-revision",
            "contradicts",
            ["pump_1"],
            supersedes_evidence_id="E-old",
            statement="L'opérateur corrige l'observation initiale.",
        )
    )
    assert [item.evidence_id for item in ledger.active_items()] == ["E-revision"]
    assert [item.evidence_id for item in ledger.items] == ["E-old", "E-revision"]
    with pytest.raises(ValueError, match="preuve antérieure"):
        EvidenceLedger("C").append(
            evidence("E-bad", "supports", ["pump_1"], supersedes_evidence_id="missing")
        )


def test_information_gain_and_adjusted_voi_rank_differently():
    hypotheses = ["A", "B", "C", "D"]
    perfect_but_impossible = MicroQuestion(
        "Q-perfect",
        "Question parfaite mais document indisponible ?",
        {"A": "a", "B": "b", "C": "c", "D": "d"},
        effort=5.0,
        availability=0.1,
        reliability=0.9,
    )
    easy = MicroQuestion(
        "Q-easy",
        "L'actif fonctionnait-il le week-end ?",
        {"A": "yes", "B": "yes", "C": "no", "D": "no"},
        effort=1.0,
        availability=1.0,
        reliability=0.95,
    )
    ig = rank_micro_questions(hypotheses, [perfect_but_impossible, easy], strategy="information_gain")
    voi = rank_micro_questions(
        hypotheses, [perfect_but_impossible, easy], strategy="reliability_adjusted_voi"
    )
    assert ig[0]["question_id"] == "Q-perfect"
    assert voi[0]["question_id"] == "Q-easy"
    assert voi[0]["information_gain_bits"] == 1.0


def test_useless_question_has_zero_information_gain():
    ranked = rank_micro_questions(
        ["A", "B"],
        [MicroQuestion("Q0", "Même réponse ?", {"A": "yes", "B": "yes"}, 1, 1, 1)],
    )
    assert ranked[0]["information_gain_bits"] == 0
    assert ranked[0]["discriminating"] is False


def test_natural_event_must_be_unconfounded():
    event = NaturalOperationalEvent(
        "N1", "shutdown", "2026-02-01", None, ("pump_1",), (), "disappeared", 0.9,
        "ops.csv#/0", confounder_audit_status="verified_scope"
    )
    items, audit = evidence_from_natural_event(event, component_id="PX-C01", candidate_ids=["pump_1", "pump_2"])
    assert audit["discriminating"] is True
    assert items[0].candidate_ids == ("pump_1",)
    confounded = NaturalOperationalEvent(
        "N2", "shutdown", "2026-02-02", None, ("pump_1",), ("N-other",), "disappeared", 0.9, "ops.csv#/1"
    )
    items, audit = evidence_from_natural_event(confounded, component_id="PX-C01", candidate_ids=["pump_1"])
    assert items == []
    assert audit["reason"] == "confounded_or_non_discriminating_event"


def test_measurement_is_last_resort_and_duration_is_traceable_heuristic():
    assessment = assess_attribution(component(), [asset("A"), asset("B")])
    plan = plan_temporary_measurement(
        assessment, ranked_questions=[], component=component(), decision="départager A et B"
    )
    assert plan["status"] == "last_resort_targeted_measurement"
    assert plan["minimum_repeated_cycles"] == 3
    assert plan["approximate_duration_days"] == 3
    useful = [{"utility": 0.8, "discriminating": True}]
    assert plan_temporary_measurement(
        assessment, ranked_questions=useful, component=component(), decision="x"
    ) is None


def test_historical_anchor_reuse_accepts_stable_and_refuses_drift():
    reference = component(component_id="C-old")
    stable = component(component_id="C-new", amplitude_kw=5.2, typical_start_hour=6.2)
    drifted = component(
        component_id="C-drift", amplitude_kw=9.0, typical_start_hour=13.0,
        operating_days=(5, 6), production_relation="independent"
    )
    assert reuse_historical_anchor(reference, stable, anchored_asset_id="pump_1")["status"] == "compatible_historical_signature"
    refused = reuse_historical_anchor(reference, drifted, anchored_asset_id="pump_1")
    assert refused["status"] == "reuse_refused"
    assert refused["anchored_asset_id"] is None


def test_claim_guard_rejects_llm_style_promotion():
    assessment = assess_attribution(component(), [asset()])
    finding = build_evidence_finding(component(), assessment)
    validate_evidence_finding(finding, assessment)
    finding["evidence_level"] = {"code": "PHYSICAL_MECHANISM", "ordinal": 7}
    finding["forbidden_claims"] = []
    with pytest.raises(ValueError, match="niveau de preuve"):
        validate_evidence_finding(finding, assessment)


def test_invalid_values_are_rejected_without_imputation():
    with pytest.raises(ValueError):
        EquipmentRecord(asset_id="A", nominal_power_kw=-1)
    with pytest.raises(ValueError):
        AnonymousElectricalComponent("C", 2, repeatability=1.1)
    with pytest.raises(ValueError):
        evidence("E", "supports", ["A"], reliability=1.1)
