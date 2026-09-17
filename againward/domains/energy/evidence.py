"""Energy Reading -> neutral evidence records; lossless legacy snapshot adapter."""
from __future__ import annotations
from typing import Any
from energy_mvp.models import LoadedData, Reading
from againward.evidence.dataset import EvidenceDataset, LEGACY_SCHEMA
from againward.evidence.hashing import stable_hash
from againward.evidence.plane import _round

def _power_kw(reading: Reading) -> float | None:
    if reading.power_kw is not None:
        return reading.power_kw
    if reading.interval_hours is not None and reading.interval_hours > 0:
        return reading.energy_kwh / reading.interval_hours
    return None


class EnergyEvidenceDataset(EvidenceDataset):
    @property
    def measurement_kind(self): return self.metadata.get("measurement_kind")
    @property
    def timestamp_position(self): return self.metadata.get("timestamp_position")
    @property
    def site_timezone(self): return self.metadata.get("site_timezone")

    @classmethod
    def from_loaded_data(
        cls, loaded: LoadedData, *, source_sha256: str
    ) -> EnergyEvidenceDataset:
        rows: list[dict[str, Any]] = []
        for reading in loaded.readings:
            row = {
                "source_row": reading.source_row,
                "timestamp": reading.timestamp.isoformat(),
                "operational_timestamp": reading.operational_timestamp.isoformat(),
                "energy_kwh": reading.energy_kwh,
                "power_kw": _power_kw(reading),
                "interval_hours": reading.interval_hours,
            }
            optional_values = {
                "production": reading.production,
                "production_active": reading.production_active,
                "outside_temperature_c": reading.outside_temperature_c,
                "shift": reading.shift,
                "product_type": reading.product_type,
                "tariff_per_kwh": reading.tariff_per_kwh,
            }
            row.update({key: value for key, value in optional_values.items() if value is not None})
            row.update(loaded.auxiliary.values_for_row(reading.source_row))
            rows.append(row)
        raw_source_rows = list(loaded.auxiliary.source_rows)
        raw_auxiliary_columns = {
            key: list(values) for key, values in loaded.auxiliary.raw_columns.items()
        }
        canonical = [
            ("source_row", "source_row", "integer", None),
            ("timestamp", loaded.columns.get("date", "timestamp"), "datetime", None),
            ("operational_timestamp", "operational_timestamp", "datetime", None),
            ("energy_kwh", loaded.columns.get("energy", "energy_kwh"), "number", "kWh"),
            ("power_kw", loaded.columns.get("power", "power_kw"), "number", "kW"),
            ("production", loaded.columns.get("production", "production"), "number", None),
            (
                "production_active",
                loaded.columns.get("production_active", "production_active"),
                "boolean",
                None,
            ),
            (
                "outside_temperature_c",
                loaded.columns.get("temperature", "outside_temperature_c"),
                "number",
                "°C",
            ),
            ("shift", loaded.columns.get("shift", "shift"), "string", None),
            (
                "product_type",
                loaded.columns.get("product_type", "product_type"),
                "string",
                None,
            ),
            (
                "tariff_per_kwh",
                loaded.columns.get("tariff", "tariff_per_kwh"),
                "number",
                "currency/kWh",
            ),
            ("interval_hours", "interval_hours", "number", "h"),
        ]
        fields: list[dict[str, Any]] = []
        for key, original_name, data_type, unit in canonical:
            present = sum(row.get(key) is not None for row in rows)
            fields.append(
                {
                    "key": key,
                    "original_name": original_name,
                    "origin": "canonical",
                    "data_type": data_type,
                    "unit": unit,
                    "present_count": present,
                    "missing_count": len(rows) - present,
                    "completeness": _round(present / len(rows), 6) if rows else 0.0,
                    "source_column_index": None,
                    "high_cardinality": key in {"source_row", "timestamp"},
                }
            )
        for item in loaded.auxiliary.fields:
            fields.append(
                {
                    "key": item.key,
                    "original_name": item.original_name,
                    "normalized_name": item.normalized_name,
                    "origin": "auxiliary",
                    "data_type": item.inferred_type,
                    "unit": None,
                    "present_count": item.present_count,
                    "missing_count": item.missing_count,
                    "completeness": _round(
                        item.present_count / len(rows), 6
                    ) if rows else 0.0,
                    "distinct_count": item.distinct_count,
                    "source_column_index": item.source_column_index,
                    "high_cardinality": item.high_cardinality,
                    "truncated_value_count": item.truncated_value_count,
                }
            )
        body = {
            "source_sha256": source_sha256,
            "rows": rows,
            "fields": fields,
            "raw_auxiliary_source_rows": raw_source_rows,
            "raw_auxiliary_columns": raw_auxiliary_columns,
            "measurement_kind": loaded.measurement_kind.value,
            "timestamp_position": loaded.timestamp_position,
            "site_timezone": loaded.site_timezone,
        }
        dataset_sha256 = stable_hash(body)
        return cls.from_dict({
            "schema_version": LEGACY_SCHEMA,
            "dataset_id": f"dataset-{source_sha256[:16]}",
            "dataset_sha256": dataset_sha256,
            **body,
        })

