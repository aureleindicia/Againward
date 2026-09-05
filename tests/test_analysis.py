from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from energy_mvp.analysis import analyze, validate_analysis_invariants
from energy_mvp.models import Finding, LoadedData, Reading


def reading(
    day: int,
    energy: float,
    *,
    production: float | None = None,
    tariff: float | None = None,
    power: float | None = None,
) -> Reading:
    return Reading(
        timestamp=datetime(2026, 1, 1) + timedelta(days=day),
        energy_kwh=energy,
        production=production,
        tariff_per_kwh=tariff,
        power_kw=power,
        interval_hours=24.0,
    )


def loaded(*items: Reading) -> LoadedData:
    return LoadedData(
        readings=list(items),
        input_rows=len(items),
        discarded_rows=0,
    )


class AnalysisTests(unittest.TestCase):
    def test_single_energy_measurement_does_not_invent_temporal_analysis(self) -> None:
        result = analyze(loaded(reading(0, 25)), source="single.csv")

        self.assertEqual(result.total_energy_kwh, 25)
        self.assertEqual(result.anomaly_count, 0)
        self.assertFalse(result.metadata["capabilities"]["intraday_analysis"])
        self.assertFalse(any("Pointe" in item.title for item in result.findings))

    def test_absent_tariff_never_creates_currency_value(self) -> None:
        result = analyze(
            loaded(reading(0, 25), reading(1, 75)), source="without_tariff.csv"
        )

        self.assertIsNone(result.total_cost)
        self.assertIsNone(result.metadata["covered_cost"])
        self.assertTrue(all(item["cost"] is None for item in result.monthly))

    def test_massive_anomaly_is_retained_as_candidate_not_confirmed_opportunity(self) -> None:
        result = analyze(
            loaded(*(reading(day, 1000 if day == 9 else 10) for day in range(10))),
            source="massive.csv",
        )

        self.assertEqual(result.anomaly_count, 1)
        candidate = next(item for item in result.findings if "Pics" in item.title)
        self.assertEqual(candidate.status, "candidate_signal")
        self.assertIsNone(candidate.estimated_saving_kwh)

    def test_monthly_aggregation_preserves_energy_cost_and_production(self) -> None:
        result = analyze(
            loaded(
                reading(0, 25, production=5, tariff=0.2),
                reading(31, 75, production=15, tariff=0.2),
            ),
            source="two_months.csv",
        )

        self.assertEqual([item["month"] for item in result.monthly], ["2026-01", "2026-02"])
        self.assertEqual([item["energy_kwh"] for item in result.monthly], [25, 75])
        self.assertEqual([item["cost"] for item in result.monthly], [5, 15])
        self.assertEqual([item["intensity"] for item in result.monthly], [5, 5])

    def test_total_energy_cost_and_intensity_are_deterministic(self) -> None:
        data = loaded(
            reading(0, 25, production=5, tariff=0.2),
            reading(1, 75, production=15, tariff=0.2),
        )

        result = analyze(data, source="test.csv")

        self.assertEqual(result.total_energy_kwh, 100)
        self.assertEqual(result.total_cost, 20)
        self.assertEqual(result.total_production, 20)
        self.assertEqual(result.energy_intensity, 5)

    def test_partial_tariff_is_never_published_as_total_cost(self) -> None:
        data = loaded(
            reading(0, 25, tariff=0.2),
            reading(1, 75, tariff=None),
        )

        result = analyze(data, source="test.csv")

        self.assertIsNone(result.total_cost)
        self.assertEqual(result.metadata["covered_cost"], 5)
        self.assertEqual(result.metadata["tariff_coverage_ratio"], 0.5)
        self.assertIsNone(result.monthly[0]["cost"])

    def test_default_tariff_completes_cost_coverage(self) -> None:
        data = loaded(reading(0, 25), reading(1, 75))

        result = analyze(data, source="test.csv", default_tariff=0.2)

        self.assertEqual(result.total_cost, 20)

    def test_negative_default_tariff_is_rejected(self) -> None:
        data = loaded(reading(0, 25))

        with self.assertRaisesRegex(ValueError, "tarif par kWh ne peut pas etre negatif"):
            analyze(data, source="test.csv", default_tariff=-0.2)

    def test_partial_production_does_not_create_global_intensity(self) -> None:
        data = loaded(
            reading(0, 10, production=0),
            reading(1, 90, production=None),
        )

        result = analyze(data, source="test.csv")

        self.assertIsNone(result.total_production)
        self.assertIsNone(result.energy_intensity)
        self.assertEqual(result.off_production_kwh, 10)
        self.assertEqual(result.off_production_share, 1.0)
        self.assertIsNone(result.monthly[0]["production"])

    def test_zero_production_never_divides_by_zero(self) -> None:
        data = loaded(reading(0, 10, production=0), reading(1, 10, production=0))

        result = analyze(data, source="test.csv")

        self.assertEqual(result.total_production, 0)
        self.assertIsNone(result.energy_intensity)
        self.assertEqual(result.off_production_kwh, result.total_energy_kwh)

    def test_constant_consumption_does_not_create_outliers(self) -> None:
        data = loaded(*(reading(day, 10) for day in range(10)))

        result = analyze(data, source="test.csv")

        self.assertEqual(result.anomaly_count, 0)
        self.assertEqual(result.findings[0].status, "information")

    def test_off_production_signal_does_not_invent_savings(self) -> None:
        data = loaded(
            reading(0, 30, production=0, tariff=0.2),
            reading(1, 70, production=10, tariff=0.2),
        )

        result = analyze(data, source="test.csv")
        signal = result.findings[0]

        self.assertEqual(signal.status, "candidate_signal")
        self.assertIsNone(signal.estimated_saving_kwh)
        self.assertIsNone(signal.estimated_saving_cost)
        self.assertIn("pas une economie recuperable", signal.detail)

    def test_negative_normalized_energy_violates_invariant(self) -> None:
        data = loaded(reading(0, -1))

        with self.assertRaisesRegex(ValueError, "ne peut pas etre negative"):
            analyze(data, source="test.csv")

    def test_announced_savings_cannot_exceed_energy_or_covered_cost(self) -> None:
        result = analyze(
            loaded(
                reading(0, 30, production=0, tariff=0.2),
                reading(1, 70, production=10, tariff=0.2),
            ),
            source="test.csv",
        )
        finding = result.findings[0]
        finding.estimated_saving_kwh = 101
        with self.assertRaisesRegex(AssertionError, "energie totale"):
            validate_analysis_invariants(result)

        finding.estimated_saving_kwh = 50
        finding.estimated_saving_cost = 21
        with self.assertRaisesRegex(AssertionError, "cout total"):
            validate_analysis_invariants(result)

    def test_sum_of_announced_savings_cannot_hide_double_counting(self) -> None:
        result = analyze(
            loaded(
                reading(0, 30, production=0, tariff=0.2),
                reading(1, 70, production=10, tariff=0.2),
            ),
            source="test.csv",
        )
        result.findings[0].estimated_saving_kwh = 60
        result.findings[0].estimated_saving_cost = 10
        result.findings.append(
            Finding(
                level="moyen",
                title="Signal chevauchant",
                detail="Test d'invariant",
                estimated_saving_kwh=60,
                estimated_saving_cost=10,
            )
        )

        with self.assertRaisesRegex(AssertionError, "somme des economies"):
            validate_analysis_invariants(result)

    def test_empty_dataset_has_clean_error(self) -> None:
        data = loaded()

        with self.assertRaisesRegex(ValueError, "Aucune mesure"):
            analyze(data, source="test.csv")

    def test_coarse_data_does_not_invent_startup_analysis(self) -> None:
        data = loaded(
            reading(0, 10, power=10),
            reading(31, 10, power=10),
            reading(59, 10, power=10),
            reading(90, 10, power=100),
            reading(120, 10, power=10),
        )
        data.quality.inferred_frequency_minutes = 30 * 24 * 60

        result = analyze(data, source="monthly.csv")

        self.assertFalse(result.metadata["capabilities"]["intraday_analysis"])
        self.assertFalse(any("Pointe de puissance" in item.title for item in result.findings))

    def test_frequency_change_disables_intraday_conclusions(self) -> None:
        data = loaded(
            reading(0, 10, power=10),
            reading(1, 10, power=100),
            reading(2, 10, power=10),
        )
        data.quality.inferred_frequency_minutes = 15
        data.quality.frequency_change_count = 1

        result = analyze(data, source="mixed_frequency.csv")

        self.assertFalse(result.metadata["capabilities"]["intraday_analysis"])
        self.assertFalse(any("Pointe de puissance" in item.title for item in result.findings))


if __name__ == "__main__":
    unittest.main()
