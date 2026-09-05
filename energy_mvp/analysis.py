from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from statistics import median
from typing import Any

from .models import AnalysisResult, Finding, LoadedData


def validate_analysis_invariants(result: AnalysisResult) -> None:
    """Refuse un resultat structure numeriquement impossible avant publication."""

    if result.total_energy_kwh < 0:
        raise AssertionError("Invariant viole: energie totale negative.")
    if result.off_production_kwh is not None:
        if not 0 <= result.off_production_kwh <= result.total_energy_kwh + 1e-9:
            raise AssertionError(
                "Invariant viole: energie hors production hors des bornes du total."
            )
    if result.total_cost is not None and result.total_cost < 0:
        raise AssertionError("Invariant viole: cout total negatif.")
    announced_energy = 0.0
    announced_cost = 0.0
    for finding in result.findings:
        saving_energy = finding.estimated_saving_kwh
        saving_cost = finding.estimated_saving_cost
        if saving_energy is not None:
            announced_energy += saving_energy
            if not 0 <= saving_energy <= result.total_energy_kwh + 1e-9:
                raise AssertionError(
                    "Invariant viole: economie annoncee superieure a l'energie totale."
                )
        if saving_cost is not None:
            announced_cost += saving_cost
            if saving_cost < 0:
                raise AssertionError("Invariant viole: economie financiere negative.")
            if saving_energy is None:
                raise AssertionError(
                    "Invariant viole: economie financiere sans energie associee."
                )
            if result.total_cost is None:
                raise AssertionError(
                    "Invariant viole: economie financiere sans cout total couvert."
                )
            if saving_cost > result.total_cost + 1e-9:
                raise AssertionError(
                    "Invariant viole: economie annoncee superieure au cout total."
                )

    if announced_energy > result.total_energy_kwh + 1e-9:
        raise AssertionError(
            "Invariant viole: somme des economies superieure a l'energie totale."
        )
    if result.total_cost is not None and announced_cost > result.total_cost + 1e-9:
        raise AssertionError(
            "Invariant viole: somme des economies superieure au cout total."
        )


def _anomaly_indices(values: list[float]) -> set[int]:
    if len(values) < 5:
        return set()
    centre = median(values)
    mad = median(abs(value - centre) for value in values)
    if mad == 0:
        return {index for index, value in enumerate(values) if value > centre}
    robust_sigma = 1.4826 * mad
    threshold = centre + 3 * robust_sigma
    return {index for index, value in enumerate(values) if value > threshold}


def analyze(
    data: LoadedData,
    *,
    source: str,
    default_tariff: float | None = None,
    production_threshold: float = 0.0,
) -> AnalysisResult:
    readings = data.readings
    if default_tariff is not None and default_tariff < 0:
        raise ValueError("Le tarif par kWh ne peut pas etre negatif.")
    if not readings:
        raise ValueError("Aucune mesure a analyser.")
    if any(reading.energy_kwh < 0 for reading in readings):
        raise ValueError("L'energie normalisee ne peut pas etre negative.")
    total_energy = sum(reading.energy_kwh for reading in readings)

    production_values = [
        reading.production for reading in readings if reading.production is not None
    ]
    production_coverage = len(production_values)
    has_production = production_coverage > 0
    production_complete = production_coverage == len(readings)
    total_production = sum(production_values) if production_complete else None
    intensity = (
        total_energy / total_production
        if total_production is not None and total_production > 0
        else None
    )
    off_production = None
    off_share = None
    if has_production:
        energy_with_production = sum(
            reading.energy_kwh
            for reading in readings
            if reading.production is not None
        )
        off_production = sum(
            reading.energy_kwh
            for reading in readings
            if reading.production is not None and reading.production <= production_threshold
        )
        off_share = off_production / energy_with_production if energy_with_production else 0.0

    effective_tariffs = [
        reading.tariff_per_kwh
        if reading.tariff_per_kwh is not None
        else default_tariff
        for reading in readings
    ]
    if any(tariff is not None and tariff < 0 for tariff in effective_tariffs):
        raise ValueError("Le tarif par kWh ne peut pas etre negatif.")
    tariff_coverage = sum(tariff is not None for tariff in effective_tariffs)
    covered_cost = None
    if tariff_coverage:
        covered_cost = sum(
            reading.energy_kwh * tariff
            for reading, tariff in zip(readings, effective_tariffs)
            if tariff is not None
        )
    total_cost = covered_cost if tariff_coverage == len(readings) else None

    power_readings = [reading for reading in readings if reading.power_kw is not None]
    power_values = [reading.power_kw for reading in power_readings]
    peak_power = max(power_values) if power_values else None
    weighted_power = [
        (reading.power_kw, reading.interval_hours)
        for reading in power_readings
        if reading.interval_hours is not None and reading.interval_hours > 0
    ]
    if (
        data.measurement_kind.value == "power"
        and power_values
        and len(weighted_power) == len(power_values)
    ):
        weighted_hours = sum(hours for _, hours in weighted_power)
        average_power = (
            sum(power * hours for power, hours in weighted_power) / weighted_hours
            if weighted_hours else None
        )
        power_average_method = "time_weighted"
    else:
        average_power = sum(power_values) / len(power_values) if power_values else None
        power_average_method = "sample_mean" if power_values else None
    anomaly_indices = _anomaly_indices([reading.energy_kwh for reading in readings])
    frequency_minutes = data.quality.inferred_frequency_minutes
    supports_intraday_analysis = (
        frequency_minutes is not None and frequency_minutes <= 60
        and data.quality.frequency_change_count == 0
    )

    month_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"energy_kwh": 0.0, "cost": 0.0, "cost_known": False,
                 "tariff_count": 0, "production": 0.0,
                 "production_count": 0, "row_count": 0}
    )
    for reading, tariff in zip(readings, effective_tariffs):
        month = reading.operational_timestamp.strftime("%Y-%m")
        bucket = month_buckets[month]
        bucket["row_count"] += 1
        bucket["energy_kwh"] += reading.energy_kwh
        if tariff is not None:
            bucket["cost"] += reading.energy_kwh * tariff
            bucket["cost_known"] = True
            bucket["tariff_count"] += 1
        if reading.production is not None:
            bucket["production"] += reading.production
            bucket["production_count"] += 1
    monthly = []
    for month, bucket in sorted(month_buckets.items()):
        production = (
            bucket["production"]
            if bucket["production_count"] == bucket["row_count"]
            else None
        )
        monthly.append(
            {
                "month": month,
                "energy_kwh": bucket["energy_kwh"],
                "cost": (
                    bucket["cost"]
                    if bucket["tariff_count"] == bucket["row_count"]
                    else None
                ),
                "production": production,
                "intensity": (
                    bucket["energy_kwh"] / production
                    if production is not None and production > 0 else None
                ),
            }
        )

    findings: list[Finding] = []
    if off_share is not None and off_production is not None:
        if off_share >= 0.20:
            level, title = "eleve", "Consommation importante hors production"
        elif off_share >= 0.10:
            level, title = "moyen", "Consommation hors production a examiner"
        else:
            level, title = "faible", "Consommation hors production limitee"
        findings.append(
            Finding(
                level=level,
                title=title,
                detail=(
                    f"{off_share:.1%} de l'energie est consommee sur des lignes ou "
                    f"la production renseignee est <= {production_threshold:g}. Ce volume "
                    "est une consommation observee, pas une economie recuperable."
                ),
                basis=[
                    f"energie_hors_production_kwh={off_production:.6g}",
                    f"part_sur_couverture_production={off_share:.6g}",
                ],
                limitations=[
                    "La charge incompressible n'est pas encore estimee.",
                    "La cause physique et la part evitable exigent une investigation.",
                ],
            )
        )
    if anomaly_indices:
        findings.append(
            Finding(
                level="moyen",
                title="Pics de consommation atypiques",
                detail=(
                    f"{len(anomaly_indices)} point(s) depassent le seuil robuste "
                    "mediane + 3 x ecart absolu median. Ce sont des candidats a regrouper "
                    "et comparer a des periodes equivalentes."
                ),
                basis=[f"points_candidats={len(anomaly_indices)}"],
                limitations=[
                    "Le seuil ne controle pas encore la production, l'heure ou la temperature."
                ],
            )
        )
    valid_intensities = [item["intensity"] for item in monthly if item["intensity"] is not None]
    if len(valid_intensities) >= 3:
        min_intensity = min(valid_intensities)
        max_intensity = max(valid_intensities)
        if min_intensity > 0 and max_intensity / min_intensity >= 1.25:
            findings.append(
                Finding(
                    level="moyen",
                    title="Intensite energetique variable",
                    detail=(
                        "L'intensite mensuelle la plus haute depasse d'au moins 25 % la plus basse. "
                        "Comparer le mix produit, les cadences, les arrets et les conditions meteo."
                    ),
                    basis=[
                        f"intensite_min={min_intensity:.6g}",
                        f"intensite_max={max_intensity:.6g}",
                    ],
                    limitations=[
                        "Un ratio kWh/unite se degrade mecaniquement a faible production."
                    ],
                )
            )
    if (
        supports_intraday_analysis
        and peak_power is not None
        and average_power
        and peak_power >= 1.5 * average_power
    ):
        findings.append(
            Finding(
                level="moyen",
                title="Pointe de puissance notable",
                    detail=(
                        f"La pointe ({peak_power:.1f} kW) atteint au moins 150 % de la puissance "
                        "moyenne mesuree. Examiner sa duree, la production et les demarrages "
                        "avant toute interpretation."
                    ),
                    basis=[
                        f"pointe_kw={peak_power:.6g}",
                        f"moyenne_kw={average_power:.6g}",
                    ],
                    limitations=[
                        "Une pointe peut etre normale et n'implique pas automatiquement un surcout."
                    ],
                )
            )
    if not findings:
        findings.append(
            Finding(
                level="information",
                title="Aucun signal simple detecte",
                detail="Les regles du MVP ne montrent pas d'inefficacite evidente; cela ne prouve pas l'absence de potentiel.",
                status="information",
            )
        )

    warnings = list(data.warnings)
    if tariff_coverage and tariff_coverage < len(readings):
        warnings.append(
            f"Tarif disponible pour {tariff_coverage}/{len(readings)} ligne(s): le cout est partiel."
        )
    if has_production and len(production_values) < len(readings):
        warnings.append(
            f"Production disponible pour {len(production_values)}/{len(readings)} ligne(s): "
            "production totale et intensite globale non calculees."
        )

    result = AnalysisResult(
        source=source,
        start=data.coverage_start or min(reading.timestamp for reading in readings),
        end=data.coverage_end or max(reading.timestamp for reading in readings),
        input_rows=data.input_rows,
        valid_rows=len(readings),
        discarded_rows=data.discarded_rows,
        total_energy_kwh=total_energy,
        total_cost=total_cost,
        total_production=total_production,
        energy_intensity=intensity,
        off_production_kwh=off_production,
        off_production_share=off_share,
        peak_power_kw=peak_power,
        average_power_kw=average_power,
        anomaly_count=len(anomaly_indices),
        monthly=monthly,
        findings=findings,
        warnings=warnings,
        metadata={
            "energy_mode": data.energy_mode,
            "measurement_kind": data.measurement_kind.value,
            "timestamp_position": data.timestamp_position,
            "site_timezone": data.site_timezone,
            "coverage_bounds_available": (
                data.coverage_start is not None and data.coverage_end is not None
            ),
            "coverage_bounds_method": data.coverage_bounds_method,
            "columns": data.columns,
            "source_units": data.source_units,
            "tariff_coverage": tariff_coverage,
            "tariff_coverage_ratio": tariff_coverage / len(readings),
            "covered_cost": covered_cost,
            "production_coverage": production_coverage,
            "production_coverage_ratio": production_coverage / len(readings),
            "power_average_method": power_average_method,
            "capabilities": {
                "intraday_analysis": supports_intraday_analysis,
                "night_analysis": supports_intraday_analysis,
                "startup_analysis": supports_intraday_analysis,
            },
            "data_quality": asdict(data.quality),
        },
    )
    validate_analysis_invariants(result)
    return result
