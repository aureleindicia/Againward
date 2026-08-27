from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from energy_mvp.models import Reading
from energy_mvp.toolbox import (
    annualize_effect,
    calculate_cost,
    calculate_excess_energy,
    calculate_residuals,
    estimate_baseload,
    fit_activity_baseline,
    fit_linear_baseline,
    fit_rolling_median_baseline,
    fit_time_baseline,
    group_residual_events,
    union_excess_energy,
)


class ToolboxTests(unittest.TestCase):
    def test_production_baseline_uses_past_for_calibration_and_future_for_validation(self) -> None:
        start = datetime(2026, 1, 1)
        readings = []
        for index in range(100):
            production = float(index % 17)
            power = 10 + 2 * production
            readings.append(
                Reading(
                    timestamp=start + timedelta(minutes=15 * index),
                    energy_kwh=power * 0.25,
                    power_kw=power,
                    production=production,
                    interval_hours=0.25,
                )
            )

        model = fit_linear_baseline(readings, predictors=("production",))

        self.assertLess(model["calibration_end"], model["validation_start"])
        self.assertAlmostEqual(model["coefficients"]["intercept"], 10, places=7)
        self.assertAlmostEqual(model["coefficients"]["production"], 2, places=7)
        self.assertAlmostEqual(model["validation_metrics"]["mae"], 0, places=7)
        residuals = calculate_residuals(readings, model)
        self.assertAlmostEqual(max(abs(item["residual_kw"]) for item in residuals), 0, places=7)

    def test_baseload_uses_robust_low_distributions_not_only_absolute_minimum(self) -> None:
        readings = [
            Reading(
                timestamp=datetime(2026, 1, 1) + timedelta(minutes=15 * index),
                energy_kwh=power * 0.25,
                power_kw=power,
                production=0,
                production_active=False,
                interval_hours=0.25,
            )
            for index, power in enumerate([1.0] + [20.0] * 99)
        ]

        estimate = estimate_baseload(readings)

        self.assertEqual(estimate["absolute_minimum_kw"], 1)
        self.assertEqual(estimate["q10_kw"], 20)
        self.assertEqual(estimate["median_lowest_20_percent_kw"], 20)

    def test_activity_baseline_keeps_calibration_before_validation(self) -> None:
        start = datetime(2026, 1, 1)
        readings = [
            Reading(
                timestamp=start + timedelta(minutes=15 * index),
                energy_kwh=(80 if index % 2 else 20) * 0.25,
                power_kw=80 if index % 2 else 20,
                production_active=bool(index % 2),
                interval_hours=0.25,
            )
            for index in range(100)
        ]

        model = fit_activity_baseline(readings)

        self.assertLess(model["calibration_end"], model["validation_start"])
        self.assertEqual(model["expected_by_activity"], {"inactive": 20, "active": 80})
        self.assertEqual(model["validation_metrics"]["rmse"], 0)

    def test_time_baseline_uses_repeated_historical_slots(self) -> None:
        start = datetime(2026, 1, 5)
        readings = []
        for day in range(35):
            for hour in (0, 6, 12, 18):
                timestamp = start + timedelta(days=day, hours=hour)
                power = 20 + hour + (5 if timestamp.weekday() >= 5 else 0)
                readings.append(
                    Reading(
                        timestamp=timestamp,
                        energy_kwh=power * 6,
                        power_kw=power,
                        production_active=6 <= hour < 18,
                        interval_hours=6,
                    )
                )

        model = fit_time_baseline(readings)

        self.assertLess(model["calibration_end"], model["validation_start"])
        self.assertEqual(model["validation_metrics"]["rmse"], 0)
        self.assertTrue(calculate_residuals(readings, model))

    def test_rolling_median_never_uses_future_anomaly(self) -> None:
        start = datetime(2026, 1, 1)
        readings = [
            Reading(
                timestamp=start + timedelta(minutes=15 * index),
                energy_kwh=power * 0.25,
                power_kw=power,
                interval_hours=0.25,
            )
            for index, power in enumerate([20.0] * 20 + [100.0])
        ]

        model = fit_rolling_median_baseline(readings, window_rows=10)

        self.assertTrue(model["past_only"])
        self.assertEqual(model["residuals"][-1]["expected_kw"], 20)
        self.assertEqual(model["residuals"][-1]["residual_kw"], 80)

    def test_residual_points_are_grouped_into_temporal_events(self) -> None:
        start = datetime(2026, 1, 1)
        residuals = [
            {
                "timestamp": (start + timedelta(minutes=minute)).isoformat(),
                "residual_kw": residual,
                "interval_hours": 0.25,
            }
            for minute, residual in [(0, 12), (15, 11), (30, 2), (60, 13)]
        ]

        events = group_residual_events(
            residuals, threshold_kw=10, max_gap_minutes=15
        )

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["points"], 2)
        self.assertAlmostEqual(events[0]["excess_energy_kwh"], 5.75)

    def test_excess_energy_and_cost_are_deterministic(self) -> None:
        excess = calculate_excess_energy([100], [75], [0.25])

        self.assertEqual(excess, 6.25)
        self.assertEqual(calculate_cost(excess, 0.2), 1.25)

    def test_overlapping_signals_are_not_summed_twice(self) -> None:
        result = union_excess_energy(
            [
                {"2026-01-01T00:00": 2.0, "2026-01-01T00:15": 3.0},
                {"2026-01-01T00:15": 2.5, "2026-01-01T00:30": 4.0},
            ]
        )

        self.assertEqual(result["naive_total_kwh"], 11.5)
        self.assertEqual(result["deduplicated_total_kwh"], 9.0)
        self.assertEqual(result["double_counted_kwh"], 2.5)
        self.assertEqual(result["overlapping_points"], 1)

    def test_annualization_is_a_deterministic_non_guaranteed_scenario(self) -> None:
        result = annualize_effect(
            observed_excess_energy_kwh=600,
            observed_occurrences=6,
            eligible_occurrences=8,
            observation_days=56,
            annual_eligible_occurrences=250,
            representative_period=True,
            coverage_ratio=0.98,
            price_per_kwh=0.20,
            recoverable_fraction=0.50,
        )

        self.assertEqual(result["status"], "scenario_not_guarantee")
        self.assertEqual(result["recurrence_rate"], 0.75)
        self.assertEqual(result["projected_excess_energy_kwh"], 18_750)
        self.assertEqual(result["projected_associated_cost"], 3_750)
        self.assertEqual(result["projected_recoverable_energy_kwh"], 9_375)
        self.assertEqual(result["projected_recoverable_cost"], 1_875)

    def test_annualization_rejects_isolated_event(self) -> None:
        with self.assertRaisesRegex(ValueError, "recurrence_insuffisante"):
            annualize_effect(
                observed_excess_energy_kwh=100,
                observed_occurrences=1,
                eligible_occurrences=20,
                observation_days=90,
                annual_eligible_occurrences=250,
                representative_period=True,
                coverage_ratio=1.0,
            )

    def test_annualization_rejects_weak_data_or_representativeness(self) -> None:
        with self.assertRaisesRegex(ValueError, "periode_non_documentee.*couverture"):
            annualize_effect(
                observed_excess_energy_kwh=300,
                observed_occurrences=3,
                eligible_occurrences=4,
                observation_days=35,
                annual_eligible_occurrences=52,
                representative_period=False,
                coverage_ratio=0.80,
            )


if __name__ == "__main__":
    unittest.main()
