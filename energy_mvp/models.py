from __future__ import annotations

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
