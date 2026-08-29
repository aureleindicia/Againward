from __future__ import annotations

import pytest

from energy_mvp.physical_tools import (
    command_feedback_comparison,
    compare_specific_energy,
    degree_hours,
    fan_pump_affinity_scenario,
    heat_recovery_balance,
    matched_operating_regime_comparison,
    normalized_before_after,
    pressure_decay,
    sensible_heat_energy,
)


def test_legitimate_service_increase_does_not_create_efficiency_change() -> None:
    result = compare_specific_energy(
        before_energy_kwh=100,
        before_service_output=10,
        after_energy_kwh=150,
        after_service_output=15,
        service_unit="batch",
    )
    assert result["delta_specific_energy"] == pytest.approx(0)
    assert result["decision"] is None


def test_same_service_with_more_energy_is_measured_not_diagnosed() -> None:
    result = compare_specific_energy(
        before_energy_kwh=100,
        before_service_output=10,
        after_energy_kwh=120,
        after_service_output=10,
        service_unit="m3",
    )
    assert result["delta_percent"] == pytest.approx(20)
    assert result["decision"] is None


def test_matched_regimes_exclude_different_service() -> None:
    result = matched_operating_regime_comparison(
        before_energy_kwh=[100, 100, 100],
        before_service=[10, 10, 10],
        after_energy_kwh=[110, 200, 108],
        after_service=[10.2, 20, 9.8],
        service_tolerance_fraction=0.05,
    )
    assert result["matched_pairs"] == 2
    assert result["decision"] is None


def test_command_off_with_feedback_on_is_quantified() -> None:
    result = command_feedback_comparison(
        command_active=[False, False, True, True],
        feedback_active=[True, False, True, False],
        interval_hours=[0.25, 0.25, 0.25, 0.25],
    )
    assert result["command_off_feedback_on_hours"] == pytest.approx(0.25)
    assert result["command_on_feedback_off_hours"] == pytest.approx(0.25)
    assert result["mismatch_share"] == pytest.approx(0.5)
    assert result["decision"] is None


def test_before_after_drop_remains_non_causal() -> None:
    result = normalized_before_after(
        observed_after_kw=[8, 9],
        expected_after_kw=[10, 10],
        interval_hours=[1, 1],
    )
    assert result["signed_residual_energy_kwh"] == pytest.approx(-3)
    assert result["decision"] is None
    assert "ne prouve pas seule" in result["limitations"][1]


def test_degree_hours_are_integrated_with_explicit_base() -> None:
    result = degree_hours(
        [15, 20, 10], [1, 1, 0.5], base_temperature_c=18, mode="heating"
    )
    assert result["degree_hours_c_h"] == pytest.approx(7)
    assert result["decision"] is None


def test_pressure_decay_requires_known_volume_for_flow_estimate() -> None:
    without_volume = pressure_decay(
        start_pressure_gauge_bar=7,
        end_pressure_gauge_bar=6,
        duration_minutes=10,
    )
    assert without_volume["decay_rate_bar_per_min"] == pytest.approx(0.1)
    assert without_volume["estimated_free_air_loss_m3_per_min"] is None

    with_volume = pressure_decay(
        start_pressure_gauge_bar=7,
        end_pressure_gauge_bar=6,
        duration_minutes=10,
        isolated_volume_m3=2,
    )
    assert with_volume["estimated_free_air_loss_m3_per_min"] > 0
    assert with_volume["decision"] is None


def test_heat_calculations_are_deterministic_and_limited() -> None:
    sensible = sensible_heat_energy(
        mass_kg=1000,
        temperature_change_c=10,
        specific_heat_kj_per_kg_k=4.186,
        conversion_efficiency=0.9,
    )
    assert sensible["useful_sensible_heat_kwh"] == pytest.approx(11.6277777778)
    assert sensible["input_energy_kwh"] == pytest.approx(12.9197530864)

    recovery = heat_recovery_balance(
        cold_side_mass_kg=1000,
        cold_inlet_c=10,
        cold_outlet_c=20,
        hot_side_mass_kg=1000,
        hot_inlet_c=40,
        hot_outlet_c=31,
    )
    assert recovery["cold_side_recovered_heat_kwh"] > recovery["hot_side_released_heat_kwh"]
    assert recovery["decision"] is None


def test_affinity_law_is_only_an_idealized_scenario() -> None:
    result = fan_pump_affinity_scenario(
        reference_speed=50,
        scenario_speed=40,
        reference_power_kw=100,
    )
    assert result["idealized_scenario_power_kw"] == pytest.approx(51.2)
    assert result["decision"] is None
    assert len(result["warnings"]) == 3




def test_sensible_heat_rejects_signed_energy_ambiguity() -> None:
    with pytest.raises(ValueError, match="variation de température"):
        sensible_heat_energy(
            mass_kg=100,
            temperature_change_c=-5,
            specific_heat_kj_per_kg_k=4.186,
        )
