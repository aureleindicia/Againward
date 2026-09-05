#!/usr/bin/env python3
"""Calculs quantitatifs de l'investigation demo, sans acces a la ground truth."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, pstdev
from typing import Any, Callable

from energy_mvp.io import load_data
from energy_mvp.models import Reading
from energy_mvp.toolbox import (
    calculate_cost,
    calculate_residuals,
    estimate_baseload,
    extract_period,
    fit_linear_baseline,
    group_residual_events,
    inspect_dataset,
    union_excess_energy,
)


PRICE_PER_KWH = 0.175


def dt(value: str) -> datetime:
    return datetime.fromisoformat(value)


def avg(values: list[float]) -> float | None:
    return mean(values) if values else None


def linear_trend(values: list[float]) -> dict[str, float | None]:
    if len(values) < 2:
        return {"slope_per_day": None, "r_squared": None}
    x_mean = (len(values) - 1) / 2
    y_mean = mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    slope = sum(
        (index - x_mean) * (value - y_mean) for index, value in enumerate(values)
    ) / denominator
    predictions = [y_mean + slope * (index - x_mean) for index in range(len(values))]
    residual_sum = sum((value - predicted) ** 2 for value, predicted in zip(values, predictions))
    total_sum = sum((value - y_mean) ** 2 for value in values)
    return {
        "slope_per_day": slope,
        "r_squared": 1 - residual_sum / total_sum if total_sum > 0 else None,
    }


def main() -> int:
    data = load_data("examples/demo_15min.csv")
    readings = data.readings
    reference_start = dt("2026-01-05")
    reference_end = dt("2026-01-25")
    reference = extract_period(readings, reference_start, reference_end)
    predictor_sets = {
        "production": ("production",),
        "production_temperature": ("production", "outside_temperature_c"),
        "production_temperature_activity": (
            "production", "outside_temperature_c", "production_active"
        ),
        "production_temperature_activity_product": (
            "production", "outside_temperature_c", "production_active", "product_type_b"
        ),
        "production_temperature_activity_product_interaction": (
            "production", "outside_temperature_c", "production_active",
            "product_type_b", "production_product_b",
        ),
    }
    models = {
        name: fit_linear_baseline(reference, predictors=predictors, calibration_fraction=0.7)
        for name, predictors in predictor_sets.items()
    }
    model = models["production_temperature_activity_product_interaction"]
    residual_rows = calculate_residuals(readings, model)
    residual_by_timestamp = {item["timestamp"]: item for item in residual_rows}

    def select(
        start: str,
        end: str,
        predicate: Callable[[Reading], bool] | None = None,
    ) -> list[Reading]:
        selected = extract_period(readings, dt(start), dt(end))
        return [item for item in selected if predicate is None or predicate(item)]

    def metrics(items: list[Reading]) -> dict[str, Any]:
        residuals = [residual_by_timestamp[item.timestamp.isoformat()]["residual_kw"] for item in items]
        powers = [item.power_kw for item in items if item.power_kw is not None]
        productions = [item.production for item in items if item.production is not None]
        temperatures = [
            item.outside_temperature_c
            for item in items
            if item.outside_temperature_c is not None
        ]
        return {
            "rows": len(items),
            "days": len({item.timestamp.date() for item in items}),
            "evaluated_hours": sum(item.interval_hours or 0.0 for item in items),
            "energy_kwh": sum(item.energy_kwh for item in items),
            "mean_power_kw": avg([float(value) for value in powers]),
            "mean_residual_kw": avg(residuals),
            "mean_production_per_interval": avg([float(value) for value in productions]),
            "total_production": sum(productions),
            "production_zero_share": (
                sum(value == 0 for value in productions) / len(productions)
                if productions else None
            ),
            "mean_temperature_c": avg([float(value) for value in temperatures]),
            "product_b_share": (
                sum(item.product_type == "B" for item in items) / len(items)
                if items else None
            ),
            "mean_production_product_b": (
                mean((item.production or 0.0) * float(item.product_type == "B") for item in items)
                if items else None
            ),
        }

    def excess_map(items: list[Reading], baseline_residual_kw: float) -> dict[str, float]:
        result = {}
        for item in items:
            residual = residual_by_timestamp[item.timestamp.isoformat()]["residual_kw"]
            hours = item.interval_hours or 0.0
            result[item.timestamp.isoformat()] = max(residual - baseline_residual_kw, 0.0) * hours
        return result

    def recurrence(
        items: list[Reading], baseline_residual_kw: float, margin_kw: float
    ) -> dict[str, int | float]:
        daily: dict[str, list[float]] = defaultdict(list)
        for item in items:
            daily[item.timestamp.date().isoformat()].append(
                residual_by_timestamp[item.timestamp.isoformat()]["residual_kw"]
            )
        detected = sum(mean(values) > baseline_residual_kw + margin_kw for values in daily.values())
        return {
            "days_tested": len(daily),
            "days_detected": detected,
            "recurrence_ratio": detected / len(daily) if daily else 0.0,
        }

    inactive = lambda item: item.production_active is False
    active = lambda item: item.production_active is True
    night = lambda item: inactive(item) and (item.timestamp.hour >= 22 or item.timestamp.hour < 6)
    weekend_day = lambda item: (
        inactive(item) and item.timestamp.weekday() >= 5 and 8 <= item.timestamp.hour < 18
    )

    reference_night = select("2026-01-05", "2026-01-25", night)
    candidate_night = select("2026-01-25", "2026-02-09", night)
    post_night = select("2026-02-09", "2026-02-19", night)
    reference_night_residual = float(metrics(reference_night)["mean_residual_kw"])
    night_energy = excess_map(candidate_night, reference_night_residual)

    reference_weekend = select("2026-01-05", "2026-02-19", weekend_day)
    candidate_weekend = select("2026-02-19", "2026-03-06", weekend_day)
    post_weekend = select("2026-03-06", "2026-03-16", weekend_day)
    reference_weekend_residual = float(metrics(reference_weekend)["mean_residual_kw"])
    weekend_energy = excess_map(candidate_weekend, reference_weekend_residual)

    spike_items = select("2026-02-24T10:00", "2026-02-24T12:00")
    similar_spike_periods = [
        item
        for item in readings
        if item.timestamp.weekday() == 1
        and 10 <= item.timestamp.hour < 12
        and not (dt("2026-02-24T10:00") <= item.timestamp < dt("2026-02-24T12:00"))
    ]
    spike_energy = excess_map(spike_items, 0.0)
    point_events = group_residual_events(
        residual_rows, threshold_kw=80.0, max_gap_minutes=15.0
    )

    daily_inactive: dict[str, list[float]] = defaultdict(list)
    daily_active: dict[str, list[float]] = defaultdict(list)
    daily_temperature: dict[str, list[float]] = defaultdict(list)
    for item in readings:
        timestamp = item.timestamp.isoformat()
        residual = residual_by_timestamp[timestamp]["residual_kw"]
        key = item.timestamp.date().isoformat()
        if item.production_active:
            daily_active[key].append(residual)
        else:
            daily_inactive[key].append(residual)
        if item.outside_temperature_c is not None:
            daily_temperature[key].append(item.outside_temperature_c)
    inactive_mean = {key: mean(values) for key, values in daily_inactive.items()}
    active_mean = {key: mean(values) for key, values in daily_active.items()}
    temperature_mean = {key: mean(values) for key, values in daily_temperature.items()}

    prior_efficiency = select("2026-03-01", "2026-03-16", active)
    candidate_efficiency = select("2026-03-16", "2026-03-31", active)

    def adjusted_active_residual(item: Reading) -> float:
        return (
            residual_by_timestamp[item.timestamp.isoformat()]["residual_kw"]
            - inactive_mean[item.timestamp.date().isoformat()]
        )

    prior_adjusted = [adjusted_active_residual(item) for item in prior_efficiency]
    prior_adjusted_mean = mean(prior_adjusted)
    efficiency_energy = {
        item.timestamp.isoformat(): max(
            adjusted_active_residual(item) - prior_adjusted_mean, 0.0
        ) * (item.interval_hours or 0.0)
        for item in candidate_efficiency
    }
    efficiency_daily: dict[str, list[float]] = defaultdict(list)
    for item in candidate_efficiency:
        efficiency_daily[item.timestamp.date().isoformat()].append(adjusted_active_residual(item))
    efficiency_detected = sum(
        mean(values) > prior_adjusted_mean + 5.0 for values in efficiency_daily.values()
    )

    reference_inactive_items = select("2026-01-05", "2026-01-25", inactive)
    reference_inactive_residual = float(metrics(reference_inactive_items)["mean_residual_kw"])
    drift_start, drift_end = "2026-03-06", "2026-04-05"
    drift_dates = sorted(
        key for key in inactive_mean if drift_start <= key < drift_end
    )
    drift_inactive_values = [inactive_mean[key] for key in drift_dates]
    drift_active_values = [active_mean[key] for key in drift_dates if key in active_mean]
    drift_temperature_values = [temperature_mean[key] for key in drift_dates]
    drift_items = select(drift_start, drift_end)
    drift_energy = {
        item.timestamp.isoformat(): max(
            inactive_mean[item.timestamp.date().isoformat()] - reference_inactive_residual,
            0.0,
        ) * (item.interval_hours or 0.0)
        for item in drift_items
    }

    level_items = select("2026-04-05", "2026-05-05")
    level_inactive_items = select("2026-04-05", "2026-05-05", inactive)
    level_dates = sorted(key for key in inactive_mean if "2026-04-05" <= key < "2026-05-05")
    level_inactive_values = [inactive_mean[key] for key in level_dates]
    level_energy = {
        item.timestamp.isoformat(): max(
            inactive_mean[item.timestamp.date().isoformat()] - reference_inactive_residual,
            0.0,
        ) * (item.interval_hours or 0.0)
        for item in level_items
    }

    night_kwh = sum(night_energy.values())
    weekend_kwh = sum(weekend_energy.values())
    spike_kwh = sum(spike_energy.values())
    efficiency_kwh = sum(efficiency_energy.values())
    drift_kwh = sum(drift_energy.values())
    level_kwh = sum(level_energy.values())
    temperature_coefficient = model["coefficients"]["outside_temperature_c"]
    prior_efficiency_metrics = metrics(prior_efficiency)
    candidate_efficiency_metrics = metrics(candidate_efficiency)
    controlled_context_delta_kw = sum(
        model["coefficients"][name] * (
            float(candidate_efficiency_metrics[metric])
            - float(prior_efficiency_metrics[metric])
        )
        for name, metric in (
            ("production", "mean_production_per_interval"),
            ("outside_temperature_c", "mean_temperature_c"),
            ("product_type_b", "product_b_share"),
            ("production_product_b", "mean_production_product_b"),
        )
    )
    reference_inactive_metrics = metrics(reference_inactive_items)
    level_inactive_metrics = metrics(level_inactive_items)

    result = {
        "method": {
            "ground_truth_read": False,
            "price_per_kwh": PRICE_PER_KWH,
            "reference_period": [reference_start.isoformat(), reference_end.isoformat()],
            "selected_baseline": "production_temperature_activity_product_interaction",
            "baseline_selection_reason": (
                "Lowest validation RMSE among tested interpretable models, with production, "
                "temperature, activity and product mix controlled."
            ),
        },
        "dataset": inspect_dataset(data),
        "baseload": estimate_baseload(readings),
        "baseline_candidates": models,
        "hypotheses": {
            "H01": {
                "signal": "night_load_window",
                "period": ["2026-01-25", "2026-02-09"],
                "window_duration_hours": 15 * 24,
                "reference": metrics(reference_night),
                "candidate": metrics(candidate_night),
                "post_window": metrics(post_night),
                "recurrence": recurrence(candidate_night, reference_night_residual, 5.0),
                "temperature_explained_delta_kw": temperature_coefficient
                * (
                    float(metrics(candidate_night)["mean_temperature_c"])
                    - float(metrics(reference_night)["mean_temperature_c"])
                ),
                "excess_energy_kwh": night_kwh,
                "cost": calculate_cost(night_kwh, PRICE_PER_KWH),
            },
            "H02": {
                "signal": "weekend_day_load_window",
                "period": ["2026-02-19", "2026-03-06"],
                "window_duration_hours": 15 * 24,
                "reference": metrics(reference_weekend),
                "candidate": metrics(candidate_weekend),
                "post_window": metrics(post_weekend),
                "recurrence": recurrence(candidate_weekend, reference_weekend_residual, 5.0),
                "temperature_explained_delta_kw": temperature_coefficient
                * (
                    float(metrics(candidate_weekend)["mean_temperature_c"])
                    - float(metrics(reference_weekend)["mean_temperature_c"])
                ),
                "excess_energy_kwh": weekend_kwh,
                "cost": calculate_cost(weekend_kwh, PRICE_PER_KWH),
            },
            "H03": {
                "signal": "two_hour_point_spike",
                "period": ["2026-02-24T10:00", "2026-02-24T12:00"],
                "window_duration_hours": 2,
                "candidate": metrics(spike_items),
                "comparable_tuesdays": metrics(similar_spike_periods),
                "events_over_80_kw_residual": point_events,
                "excess_energy_kwh": spike_kwh,
                "cost": calculate_cost(spike_kwh, PRICE_PER_KWH),
            },
            "H04": {
                "signal": "active_efficiency_drop",
                "period": ["2026-03-16", "2026-03-31"],
                "window_duration_hours": 15 * 24,
                "prior": prior_efficiency_metrics,
                "candidate": candidate_efficiency_metrics,
                "modelled_context_delta_kw": controlled_context_delta_kw,
                "prior_active_minus_inactive_residual_kw": prior_adjusted_mean,
                "candidate_active_minus_inactive_residual_kw": mean(
                    adjusted_active_residual(item) for item in candidate_efficiency
                ),
                "days_tested": len(efficiency_daily),
                "days_detected": efficiency_detected,
                "excess_after_fixed_drift_removal_kwh": efficiency_kwh,
                "cost": calculate_cost(efficiency_kwh, PRICE_PER_KWH),
            },
            "H05": {
                "signal": "progressive_fixed_load_drift",
                "period": [drift_start, drift_end],
                "window_duration_hours": 30 * 24,
                "candidate": metrics(drift_items),
                "inactive_residual_start_kw": drift_inactive_values[0],
                "inactive_residual_end_kw": drift_inactive_values[-1],
                "inactive_trend": linear_trend(drift_inactive_values),
                "active_trend": linear_trend(drift_active_values),
                "temperature_trend": linear_trend(drift_temperature_values),
                "baseline_temperature_coefficient_kw_per_c": temperature_coefficient,
                "temperature_implied_residual_slope_kw_per_day": (
                    temperature_coefficient
                    * float(linear_trend(drift_temperature_values)["slope_per_day"])
                ),
                "excess_energy_kwh": drift_kwh,
                "cost": calculate_cost(drift_kwh, PRICE_PER_KWH),
            },
            "H06": {
                "signal": "persistent_fixed_load_level",
                "period": ["2026-04-05", "2026-05-05"],
                "window_duration_hours": 30 * 24,
                "reference_inactive_residual_kw": reference_inactive_residual,
                "post_inactive_residual_mean_kw": mean(level_inactive_values),
                "post_inactive_residual_sd_kw": pstdev(level_inactive_values),
                "days_tested": len(level_dates),
                "days_over_reference_plus_5kw": sum(
                    value > reference_inactive_residual + 5 for value in level_inactive_values
                ),
                "reference": reference_inactive_metrics,
                "candidate": metrics(level_items),
                "candidate_inactive": level_inactive_metrics,
                "temperature_explained_delta_kw": temperature_coefficient
                * (
                    float(level_inactive_metrics["mean_temperature_c"])
                    - float(reference_inactive_metrics["mean_temperature_c"])
                ),
                "excess_energy_kwh": level_kwh,
                "cost": calculate_cost(level_kwh, PRICE_PER_KWH),
            },
        },
        "double_counting": {
            "automatic_spike_and_peak_signal_same_event": union_excess_energy(
                [spike_energy, spike_energy]
            ),
            "confirmed_temporal_overlap_audit": union_excess_energy(
                [
                    night_energy, weekend_energy, spike_energy, efficiency_energy,
                    drift_energy, level_energy,
                ]
            ),
            "note": (
                "H04 retranche deja le residu inactif journalier de H05. "
                "Aucun total portefeuille n'est publie sans allocation causale."
            ),
        },
    }
    target = Path("reports/demo_quantitative_results.json")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Resultats quantitatifs ecrits: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
