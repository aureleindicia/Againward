from __future__ import annotations

import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from energy_mvp.io import DataError, load_data, parse_date
from energy_mvp.models import MeasurementKind


class LoadDataTests(unittest.TestCase):
    def csv_file(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        )
        with handle:
            handle.write(content)
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_power_is_integrated_using_explicit_interval(self) -> None:
        path = self.csv_file("timestamp,power_kw\n2026-01-01 00:00,100\n")

        loaded = load_data(path, interval_minutes=15)

        self.assertEqual(loaded.measurement_kind, MeasurementKind.POWER)
        self.assertEqual(loaded.energy_mode, "power")
        self.assertAlmostEqual(loaded.readings[0].energy_kwh, 25.0)
        self.assertAlmostEqual(loaded.readings[0].interval_hours or 0.0, 0.25)

    def test_watts_are_converted_before_integration(self) -> None:
        path = self.csv_file("timestamp,power_w\n2026-01-01 00:00,100000\n")

        loaded = load_data(path, interval_minutes=15)

        self.assertAlmostEqual(loaded.readings[0].power_kw or 0.0, 100.0)
        self.assertAlmostEqual(loaded.readings[0].energy_kwh, 25.0)
        self.assertEqual(loaded.source_units["power"], "w")

    def test_mwh_are_converted_to_internal_kwh(self) -> None:
        path = self.csv_file("timestamp,energy_mwh\n2026-01-01,0.1\n")

        loaded = load_data(path)

        self.assertAlmostEqual(loaded.readings[0].energy_kwh, 100.0)
        self.assertEqual(loaded.source_units["energy"], "mwh")

    def test_ambiguous_energy_unit_is_rejected(self) -> None:
        path = self.csv_file("timestamp,energie\n2026-01-01,100\n")

        with self.assertRaisesRegex(DataError, "Unite absente ou ambigue"):
            load_data(path)

    def test_explicit_energy_unit_resolves_ambiguous_header(self) -> None:
        path = self.csv_file("timestamp,energie\n2026-01-01,100000\n")

        loaded = load_data(path, energy_unit="wh")

        self.assertAlmostEqual(loaded.readings[0].energy_kwh, 100.0)

    def test_regular_power_frequency_is_inferred(self) -> None:
        path = self.csv_file(
            "timestamp,power_kw\n"
            "2026-01-01 00:00,100\n"
            "2026-01-01 00:15,100\n"
        )

        loaded = load_data(path)

        self.assertEqual([item.energy_kwh for item in loaded.readings], [25.0, 25.0])
        self.assertEqual(loaded.quality.inferred_frequency_minutes, 15.0)

    def test_irregular_power_requires_explicit_duration(self) -> None:
        path = self.csv_file(
            "timestamp,power_kw\n"
            "2026-01-01 00:00,100\n"
            "2026-01-01 00:15,100\n"
            "2026-01-01 00:45,100\n"
        )

        with self.assertRaisesRegex(DataError, "timestamps de puissance sont irreguliers"):
            load_data(path)

    def test_energy_before_a_gap_keeps_nominal_interval_duration(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01 00:00,25\n"
            "2026-01-01 00:15,25\n"
            "2026-01-01 00:45,25\n"
            "2026-01-01 01:00,25\n"
        )

        loaded = load_data(path)

        self.assertEqual([item.interval_hours for item in loaded.readings], [0.25] * 4)
        self.assertEqual(loaded.quality.gap_count, 1)

    def test_interval_start_position_extends_coverage_to_exclusive_end(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01 00:00,5\n"
            "2026-01-01 00:15,5\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.coverage_start, datetime(2026, 1, 1, 0, 0))
        self.assertEqual(loaded.coverage_end, datetime(2026, 1, 1, 0, 30))
        self.assertEqual(loaded.timestamp_position, "start")
        self.assertEqual(loaded.coverage_bounds_method, "inferred_nominal_interval")

    def test_interval_end_position_moves_coverage_start_backward(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01 00:00,5\n"
            "2026-01-01 00:15,5\n"
        )

        loaded = load_data(path, timestamp_position="end")

        self.assertEqual(loaded.coverage_start, datetime(2025, 12, 31, 23, 45))
        self.assertEqual(loaded.coverage_end, datetime(2026, 1, 1, 0, 15))

    def test_monotonic_interval_energy_is_not_misclassified_as_counter(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01,10\n2026-01-02,20\n"
            "2026-01-03,30\n2026-01-04,40\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.energy_mode, "interval")
        self.assertEqual([item.energy_kwh for item in loaded.readings], [10, 20, 30, 40])

    def test_cumulative_index_is_differenced_once(self) -> None:
        path = self.csv_file(
            "timestamp,index_kwh\n"
            "2026-01-01,100\n2026-01-02,125\n2026-01-03,150\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.measurement_kind, MeasurementKind.CUMULATIVE_ENERGY)
        self.assertEqual([item.energy_kwh for item in loaded.readings], [25, 25])
        self.assertEqual(loaded.discarded_rows, 1)
        self.assertEqual(loaded.coverage_start, datetime(2026, 1, 1))
        self.assertEqual(loaded.coverage_end, datetime(2026, 1, 3))
        self.assertEqual(loaded.timestamp_position, "end")
        self.assertEqual(loaded.coverage_bounds_method, "cumulative_reading_differences")

    def test_cumulative_index_rejects_start_timestamp_semantics(self) -> None:
        path = self.csv_file(
            "timestamp,index_kwh\n"
            "2026-01-01,100\n2026-01-02,125\n"
        )

        with self.assertRaisesRegex(DataError, "incompatible"):
            load_data(path, timestamp_position="start")

    def test_identical_duplicate_is_removed_and_traced(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01,10\n2026-01-01,10\n"
        )

        loaded = load_data(path)

        self.assertEqual(len(loaded.readings), 1)
        self.assertEqual(loaded.discarded_rows, 1)
        self.assertEqual(loaded.quality.identical_duplicates_removed, 1)
        self.assertTrue(loaded.quality.processing_log)

    def test_conflicting_duplicate_is_rejected(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01,10\n2026-01-01,11\n"
        )

        with self.assertRaisesRegex(DataError, "Doublon conflictuel"):
            load_data(path)

    def test_impossible_negative_values_are_discarded_and_traced(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,production\n"
            "2026-01-01,10,2\n2026-01-02,-5,2\n"
        )

        loaded = load_data(path)

        self.assertEqual(len(loaded.readings), 1)
        self.assertEqual(loaded.quality.impossible_value_rows, 1)
        self.assertEqual(loaded.discarded_rows, 1)

    def test_aware_timestamp_is_normalized_to_utc(self) -> None:
        parsed = parse_date("2026-01-01T00:00:00+02:00")

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2025-12-31T22:00:00")

    def test_aware_datetime_object_is_normalized_to_utc(self) -> None:
        parsed = parse_date(
            datetime(2026, 1, 1, tzinfo=timezone(timedelta(hours=2)))
        )

        self.assertIsNotNone(parsed)
        self.assertEqual(parsed.isoformat(), "2025-12-31T22:00:00")

    def test_source_reordering_is_never_silent(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01 00:15,5\n"
            "2026-01-01 00:00,5\n"
            "2026-01-01 00:30,5\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.quality.out_of_order_rows, 1)
        self.assertEqual(loaded.readings[0].timestamp.minute, 0)
        self.assertTrue(any("triees" in item for item in loaded.quality.processing_log))

    def test_sustained_frequency_change_limits_duration_dependent_analysis(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01 00:00,5\n"
            "2026-01-01 00:15,5\n"
            "2026-01-01 00:30,5\n"
            "2026-01-01 00:45,5\n"
            "2026-01-01 01:15,5\n"
            "2026-01-01 01:45,5\n"
            "2026-01-01 02:15,5\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.quality.detected_frequencies_minutes, [15.0, 30.0])
        self.assertEqual(loaded.quality.frequency_change_count, 1)
        self.assertIsNone(loaded.quality.coverage_ratio)
        self.assertTrue(all(item.interval_hours is None for item in loaded.readings))

    def test_timezone_normalization_is_traced_during_loading(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh\n"
            "2026-01-01T00:00:00+02:00,5\n"
            "2026-01-01T00:15:00+02:00,5\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.quality.timezone_normalized_rows, 2)
        self.assertEqual(loaded.readings[0].timestamp.hour, 22)
        self.assertTrue(any("converti" in item for item in loaded.quality.processing_log))

    def test_missing_and_invalid_context_values_are_counted_without_losing_energy(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,production,outside_temperature_c\n"
            "2026-01-01 00:00,5,,12\n"
            "2026-01-01 00:15,5,erreur,200\n"
        )

        loaded = load_data(path)

        self.assertEqual(len(loaded.readings), 2)
        self.assertEqual(loaded.quality.missing_values_by_column, {"production": 1})
        self.assertEqual(
            loaded.quality.invalid_values_by_column,
            {"outside_temperature_c": 1, "production": 1},
        )
        self.assertIsNone(loaded.readings[1].outside_temperature_c)

    def test_empty_file_has_clean_error(self) -> None:
        path = self.csv_file("")

        with self.assertRaisesRegex(DataError, "fichier est vide"):
            load_data(path)


if __name__ == "__main__":
    unittest.main()
