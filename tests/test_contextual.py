from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from energy_mvp.io import DataError, load_data
from energy_mvp.models import ContextualFieldStore


class ContextualFieldStoreTests(unittest.TestCase):
    def csv_file(self, content: str) -> Path:
        handle = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", encoding="utf-8", delete=False
        )
        with handle:
            handle.write(content)
        path = Path(handle.name)
        self.addCleanup(path.unlink, missing_ok=True)
        return path

    def test_unknown_columns_survive_with_types_missingness_and_provenance(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,Machine state,Batch code,operator_score\n"
            "2026-01-01 00:00,5,RUN,0012,10.5\n"
            "2026-01-01 00:15,6,,0013,11.0\n"
        )

        loaded = load_data(path)

        definitions = {item.original_name: item for item in loaded.auxiliary.fields}
        self.assertEqual(definitions["Machine state"].inferred_type, "string")
        self.assertEqual(definitions["Machine state"].missing_count, 1)
        self.assertEqual(definitions["Batch code"].inferred_type, "string")
        self.assertEqual(definitions["operator_score"].inferred_type, "number")
        key = definitions["operator_score"].key
        self.assertEqual(loaded.auxiliary.values_for_row(2, raw=True)[key], "10.5")
        self.assertEqual(loaded.auxiliary.values_for_row(2)[key], 10.5)
        self.assertEqual(definitions["operator_score"].source_column_index, 4)

    def test_context_store_round_trip_preserves_raw_and_typed_values(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,is_cleaning,event_time\n"
            "2026-01-01 00:00,5,true,2026-01-01T03:00:00\n"
            "2026-01-01 00:15,6,false,2026-01-01T04:00:00\n"
        )
        loaded = load_data(path)

        restored = ContextualFieldStore.from_dict(loaded.auxiliary.to_dict())

        self.assertEqual(restored.to_dict(), loaded.auxiliary.to_dict())
        kinds = {item.original_name: item.inferred_type for item in restored.fields}
        self.assertEqual(kinds, {"is_cleaning": "boolean", "event_time": "datetime"})

    def test_auxiliary_change_makes_a_duplicate_conflicting(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,machine_mode\n"
            "2026-01-01,10,A\n"
            "2026-01-01,10,B\n"
        )

        with self.assertRaisesRegex(DataError, "Doublon conflictuel"):
            load_data(path)

    def test_explicit_legacy_ingestion_rollback_restores_old_duplicate_semantics(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,machine_mode\n"
            "2026-01-01,10,A\n"
            "2026-01-01,10,B\n"
        )

        loaded = load_data(path, preserve_auxiliary_fields=False)

        self.assertEqual(len(loaded.readings), 1)
        self.assertEqual(loaded.quality.identical_duplicates_removed, 1)
        self.assertEqual(loaded.auxiliary.fields, [])

    def test_duplicate_header_collision_has_distinct_stable_keys(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,zone,zone\n"
            "2026-01-01,10,north,packaging\n"
            "2026-01-02,11,south,utilities\n"
        )

        loaded = load_data(path)

        keys = [item.key for item in loaded.auxiliary.fields]
        self.assertEqual(len(keys), 2)
        self.assertEqual(len(set(keys)), 2)
        self.assertTrue(all(item.original_name == "zone" for item in loaded.auxiliary.fields))

    def test_malformed_numeric_context_is_conservatively_mixed(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,sensor_reading\n"
            "2026-01-01,10,12.5\n"
            "2026-01-02,11,broken\n"
        )

        loaded = load_data(path)

        self.assertEqual(loaded.auxiliary.fields[0].inferred_type, "mixed")
        values = [
            loaded.auxiliary.values_for_row(reading.source_row)[
                loaded.auxiliary.fields[0].key
            ]
            for reading in loaded.readings
        ]
        self.assertEqual(values, ["12.5", "broken"])

    def test_high_cardinality_is_retained_and_disclosed(self) -> None:
        rows = ["timestamp,energy_kwh,batch_id"]
        rows.extend(
            f"2026-01-{1 + index // 24:02d} {index % 24:02d}:00,1,B-{index:03d}"
            for index in range(60)
        )
        path = self.csv_file("\n".join(rows) + "\n")

        loaded = load_data(path)

        field = loaded.auxiliary.fields[0]
        self.assertTrue(field.high_cardinality)
        self.assertEqual(field.distinct_count, 60)
        self.assertEqual(len(loaded.auxiliary.source_rows), 60)

    def test_excess_auxiliary_width_is_rejected_instead_of_silently_dropped(self) -> None:
        path = self.csv_file(
            "timestamp,energy_kwh,a,b\n"
            "2026-01-01,10,one,two\n"
        )

        with self.assertRaisesRegex(DataError, "dépassent la limite"):
            load_data(path, maximum_auxiliary_fields=1)


if __name__ == "__main__":
    unittest.main()
