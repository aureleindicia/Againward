from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class MeasurementKind(str, Enum):
    """Nature physique de la mesure source, avant normalisation en kWh."""

    POWER = "power"
    ENERGY_PER_INTERVAL = "energy_per_interval"
    CUMULATIVE_ENERGY = "cumulative_energy"


@dataclass(slots=True)
class Reading:
    timestamp: datetime
    energy_kwh: float
    production: float | None = None
    production_active: bool | None = None
    outside_temperature_c: float | None = None
    shift: str | None = None
    product_type: str | None = None
    tariff_per_kwh: float | None = None
    power_kw: float | None = None
    source_row: int = 0
    interval_hours: float | None = None
    local_timestamp: datetime | None = None

    @property
    def operational_timestamp(self) -> datetime:
        """Horloge locale du site pour les profils; UTC interne à défaut."""

        return self.local_timestamp or self.timestamp


@dataclass(slots=True)
class DataQuality:
    """Constats et transformations tracables effectues pendant le chargement."""

    blank_rows: int = 0
    invalid_timestamp_rows: int = 0
    missing_measurement_rows: int = 0
    impossible_value_rows: int = 0
    identical_duplicates_removed: int = 0
    conflicting_duplicates: int = 0
    out_of_order_rows: int = 0
    timezone_normalized_rows: int = 0
    naive_timezone_localized_rows: int = 0
    missing_values_by_column: dict[str, int] = field(default_factory=dict)
    invalid_values_by_column: dict[str, int] = field(default_factory=dict)
    inferred_frequency_minutes: float | None = None
    detected_frequencies_minutes: list[float] = field(default_factory=list)
    frequency_change_count: int = 0
    irregular_interval_count: int = 0
    gap_count: int = 0
    coverage_ratio: float | None = None
    processing_log: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class AuxiliaryFieldDefinition:
    """Décrit une colonne non canonique sans lui attribuer de sens métier."""

    key: str
    original_name: str
    normalized_name: str
    source_column_index: int
    inferred_type: str
    present_count: int
    missing_count: int
    distinct_count: int
    high_cardinality: bool
    truncated_value_count: int = 0


@dataclass(slots=True)
class ContextualFieldStore:
    """Magasin auxiliaire séparé du noyau physique et lié aux lignes sources."""

    fields: list[AuxiliaryFieldDefinition] = field(default_factory=list)
    source_rows: list[int] = field(default_factory=list)
    raw_columns: dict[str, list[Any]] = field(default_factory=dict)
    typed_columns: dict[str, list[Any]] = field(default_factory=dict)
    maximum_fields: int = 128
    maximum_value_characters: int = 4096

    def field_keys(self) -> list[str]:
        return [item.key for item in self.fields]

    def field(self, key: str) -> AuxiliaryFieldDefinition:
        for item in self.fields:
            if item.key == key:
                return item
        raise KeyError(key)

    def values_for_row(self, source_row: int, *, raw: bool = False) -> dict[str, Any]:
        index = bisect_left(self.source_rows, source_row)
        if index >= len(self.source_rows) or self.source_rows[index] != source_row:
            return {}
        columns = self.raw_columns if raw else self.typed_columns
        return {key: values[index] for key, values in columns.items()}

    def signature(self, source_row: int) -> tuple[tuple[str, str], ...]:
        """Signature brute stable utilisée pour éviter une déduplication destructive."""

        values = self.values_for_row(source_row, raw=True)
        return tuple((key, repr(value)) for key, value in sorted(values.items()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 2,
            "maximum_fields": self.maximum_fields,
            "maximum_value_characters": self.maximum_value_characters,
            "fields": [
                {
                    "key": item.key,
                    "original_name": item.original_name,
                    "normalized_name": item.normalized_name,
                    "source_column_index": item.source_column_index,
                    "inferred_type": item.inferred_type,
                    "present_count": item.present_count,
                    "missing_count": item.missing_count,
                    "distinct_count": item.distinct_count,
                    "high_cardinality": item.high_cardinality,
                    "truncated_value_count": item.truncated_value_count,
                }
                for item in self.fields
            ],
            "source_rows": self.source_rows,
            "raw_columns": self.raw_columns,
            "typed_columns": self.typed_columns,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ContextualFieldStore:
        if payload.get("schema_version") not in {1, 2}:
            raise ValueError("Version de magasin contextuel inconnue.")
        fields_payload = payload.get("fields")
        if not isinstance(fields_payload, list):
            raise ValueError("Magasin contextuel invalide: fields est requis.")
        fields = [AuxiliaryFieldDefinition(**item) for item in fields_payload]
        known = {item.key for item in fields}
        if payload.get("schema_version") == 1:
            rows_payload = payload.get("rows")
            if not isinstance(rows_payload, list):
                raise ValueError("Magasin contextuel v1 invalide: rows est requis.")
            source_rows: list[int] = []
            raw_columns = {key: [] for key in known}
            typed_columns = {key: [] for key in known}
            for row in sorted(rows_payload, key=lambda item: item.get("source_row", -1)):
                source_row = row.get("source_row")
                values = row.get("values")
                if not isinstance(source_row, int) or not isinstance(values, dict):
                    raise ValueError("Ligne contextuelle invalide.")
                if set(values) - known:
                    raise ValueError("Clé contextuelle inconnue dans le magasin v1.")
                source_rows.append(source_row)
                for key in known:
                    cell = values.get(key, {"raw": None, "value": None})
                    if not isinstance(cell, dict) or set(cell) != {"raw", "value"}:
                        raise ValueError("Cellule contextuelle invalide.")
                    raw_columns[key].append(cell["raw"])
                    typed_columns[key].append(cell["value"])
        else:
            source_rows = payload.get("source_rows")
            raw_columns = payload.get("raw_columns")
            typed_columns = payload.get("typed_columns")
            if (
                not isinstance(source_rows, list)
                or any(not isinstance(item, int) for item in source_rows)
                or source_rows != sorted(set(source_rows))
                or not isinstance(raw_columns, dict)
                or not isinstance(typed_columns, dict)
            ):
                raise ValueError("Magasin contextuel colonnaire invalide.")
            if set(raw_columns) != known or set(typed_columns) != known:
                raise ValueError("Colonnes contextuelles incohérentes avec leur schéma.")
            if any(
                not isinstance(values, list) or len(values) != len(source_rows)
                for values in [*raw_columns.values(), *typed_columns.values()]
            ):
                raise ValueError("Longueur de colonne contextuelle invalide.")
        return cls(
            fields=fields,
            source_rows=source_rows,
            raw_columns=raw_columns,
            typed_columns=typed_columns,
            maximum_fields=int(payload.get("maximum_fields", 128)),
            maximum_value_characters=int(
                payload.get("maximum_value_characters", 4096)
            ),
        )


@dataclass(slots=True)
class LoadedData:
    readings: list[Reading]
    input_rows: int
    discarded_rows: int
    warnings: list[str] = field(default_factory=list)
    columns: dict[str, str] = field(default_factory=dict)
    source_units: dict[str, str] = field(default_factory=dict)
    energy_mode: str = "interval"
    measurement_kind: MeasurementKind = MeasurementKind.ENERGY_PER_INTERVAL
    quality: DataQuality = field(default_factory=DataQuality)
    timestamp_position: str = "start"
    coverage_start: datetime | None = None
    coverage_end: datetime | None = None
    coverage_bounds_method: str = "unavailable"
    site_timezone: str | None = None
    auxiliary: ContextualFieldStore = field(default_factory=ContextualFieldStore)


@dataclass(slots=True)
class Finding:
    level: str
    title: str
    detail: str
    status: str = "candidate_signal"
    basis: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    estimated_saving_kwh: float | None = None
    estimated_saving_cost: float | None = None


@dataclass(slots=True)
class AnalysisResult:
    source: str
    start: datetime
    end: datetime
    input_rows: int
    valid_rows: int
    discarded_rows: int
    total_energy_kwh: float
    total_cost: float | None
    total_production: float | None
    energy_intensity: float | None
    off_production_kwh: float | None
    off_production_share: float | None
    peak_power_kw: float | None
    average_power_kw: float | None
    anomaly_count: int
    monthly: list[dict[str, Any]]
    findings: list[Finding]
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisEvent:
    """Evenement final quantifie, distinct d'un simple signal candidat."""

    event_id: str
    type: str
    start: str
    end: str
    duration_hours: float
    evaluated_hours: float
    observed_energy_kwh: float
    expected_energy_kwh: float
    excess_energy_kwh: float
    cost: float | None
    potential_saving_kwh: float | None
    recoverability: str
    severity: str
    confidence: dict[str, str]
    decision: str
    supporting_methods: list[str]
    related_hypotheses: list[str]

    def __post_init__(self) -> None:
        try:
            start = datetime.fromisoformat(self.start)
            end = datetime.fromisoformat(self.end)
        except ValueError as exc:
            raise ValueError("Les timestamps d'evenement doivent etre au format ISO.") from exc
        calendar_hours = (end - start).total_seconds() / 3600.0
        if calendar_hours <= 0:
            raise ValueError("La fin d'un evenement doit suivre son debut.")
        if abs(self.duration_hours - calendar_hours) > 1e-6:
            raise ValueError("La duree d'evenement ne correspond pas a sa periode.")
        if not 0 <= self.evaluated_hours <= self.duration_hours + 1e-9:
            raise ValueError("Les heures evaluees doivent appartenir a la periode.")
        energy_values = (
            self.observed_energy_kwh,
            self.expected_energy_kwh,
            self.excess_energy_kwh,
        )
        if any(value < 0 for value in energy_values):
            raise ValueError("Les energies d'un evenement doivent etre non negatives.")
        if self.excess_energy_kwh > self.observed_energy_kwh + 1e-9:
            raise ValueError("La surconsommation ne peut pas depasser l'energie observee.")
        if self.cost is not None and self.cost < 0:
            raise ValueError("Le cout d'un evenement ne peut pas etre negatif.")
        if self.potential_saving_kwh is not None:
            if not 0 <= self.potential_saving_kwh <= self.excess_energy_kwh + 1e-9:
                raise ValueError(
                    "L'economie potentielle ne peut pas depasser la surconsommation."
                )


@dataclass(slots=True)
class AnalysisBundle:
    """Representation commune d'une investigation agentique terminee."""

    automatic_analysis: dict[str, Any]
    quantitative_results: dict[str, Any]
    investigation: dict[str, Any]
    events: list[AnalysisEvent]
    artifacts: dict[str, Any]
