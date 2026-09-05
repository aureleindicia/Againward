from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from energy_mvp.models import Reading
from energy_mvp.tariffs import (
    TariffPlan,
    TimeOfUsePeriod,
    calculate_tariff_cost,
    tariff_plan_from_dict,
)


class TariffTests(unittest.TestCase):
    def test_time_of_use_and_monthly_peak_are_calculated_separately(self) -> None:
        readings = [
            Reading(
                timestamp=datetime(2026, 1, 5, hour),
                local_timestamp=datetime(2026, 1, 5, hour),
                energy_kwh=10.0,
                power_kw=40.0 if hour == 18 else 20.0,
                interval_hours=1.0,
            )
            for hour in (17, 18)
        ]
        plan = TariffPlan(
            default_price_per_kwh=0.10,
            time_of_use=(TimeOfUsePeriod(
                name="pointe", weekdays=(0, 1, 2, 3, 4),
                start="18:00", end="20:00", price_per_kwh=0.30,
            ),),
            demand_charge_per_kw_month=5.0,
        )

        result = calculate_tariff_cost(readings, plan)

        self.assertAlmostEqual(result["energy_charge"], 4.0)
        self.assertAlmostEqual(result["demand_charge"], 200.0)
        self.assertAlmostEqual(result["total_cost"], 204.0)
        self.assertIsNone(result["recoverable_saving"])

    def test_cross_midnight_period_uses_previous_service_day(self) -> None:
        period = TimeOfUsePeriod(
            name="nuit", weekdays=(0,), start="22:00", end="06:00", price_per_kwh=0.08
        )
        self.assertTrue(period.matches(0, 23 * 60))
        self.assertTrue(period.matches(1, 2 * 60))
        self.assertFalse(period.matches(1, 7 * 60))

    def test_uncovered_energy_prevents_publishing_a_total(self) -> None:
        reading = Reading(
            timestamp=datetime(2026, 1, 4, 12), energy_kwh=10.0, interval_hours=1.0
        )
        plan = TariffPlan(time_of_use=(TimeOfUsePeriod(
            name="semaine", weekdays=(0, 1, 2, 3, 4), start="08:00", end="18:00",
            price_per_kwh=0.20,
        ),))

        result = calculate_tariff_cost([reading], plan)

        self.assertEqual(result["unpriced_energy_kwh"], 10.0)
        self.assertIsNone(result["total_cost"])

    def test_overlapping_periods_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "chevauchantes"):
            tariff_plan_from_dict({
                "time_of_use_periods": [
                    {"name": "A", "weekdays": [0], "start": "08:00", "end": "12:00", "price_per_kwh": 0.1},
                    {"name": "B", "weekdays": [0], "start": "10:00", "end": "14:00", "price_per_kwh": 0.2},
                ]
            })


if __name__ == "__main__":
    unittest.main()
