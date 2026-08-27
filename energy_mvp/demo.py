from __future__ import annotations

import csv
import json
import math
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


INTERVAL_MINUTES = 15
INTERVAL_HOURS = INTERVAL_MINUTES / 60.0


@dataclass(frozen=True, slots=True)
class Scenario:
    production_mean: float
    production_sd: float
    noise_sd_kw: float
    temperature_coefficient: float
    fixed_load_kw: float


SCENARIOS = {
    "factory_simple": Scenario(26.0, 1.5, 0.8, 0.5, 22.0),
    "factory_variable": Scenario(26.0, 5.0, 1.6, 0.7, 22.0),
    "factory_temperature_sensitive": Scenario(26.0, 3.0, 1.2, 2.0, 22.0),
    "factory_noisy": Scenario(26.0, 4.0, 4.5, 0.8, 22.0),
    "factory_low_production": Scenario(11.0, 3.0, 1.5, 0.7, 24.0),
}


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="minutes")


def _event(
    anomaly_id: str,
    event_type: str,
    start: datetime,
    end: datetime,
    magnitude_kw: float | str,
    expected_energy_impact: float | None,
    description: str,
) -> dict[str, Any]:
    return {
        "anomaly_id": anomaly_id,
        "type": event_type,
        "start": _iso(start),
        "end": _iso(end),
        "magnitude": magnitude_kw,
        "expected_energy_impact": (
            round(expected_energy_impact, 6)
            if expected_energy_impact is not None
            else None
        ),
        "description": description,
    }


def generate_demo(
    csv_path: str | Path,
    truth_path: str | Path,
    *,
    days: int = 120,
    seed: int = 42,
    scenario_name: str = "factory_variable",
    include_data_issues: bool = True,
    include_anomalies: bool = True,
) -> dict[str, Any]:
    """Genere une courbe industrielle 15 min et sa verite terrain separee."""

    if not 30 <= days <= 365:
        raise ValueError("days doit etre compris entre 30 et 365.")
    try:
        scenario = SCENARIOS[scenario_name]
    except KeyError as exc:
        raise ValueError(f"Scenario inconnu: {scenario_name}") from exc

    rng = random.Random(seed)
    start = datetime(2026, 1, 5)  # lundi, pour rendre les horaires reproductibles
    interval_count = days * 24 * 4
    impacts = {f"A{index:02d}": 0.0 for index in range(1, 7)}
    rows: list[dict[str, Any]] = []

    for index in range(interval_count):
        timestamp = start + timedelta(minutes=INTERVAL_MINUTES * index)
        day_index = index // (24 * 4)
        hour = timestamp.hour + timestamp.minute / 60.0
        weekday = timestamp.weekday()
        production_active = weekday < 5 and 6 <= hour < 22
        shift = "shift_1" if 6 <= hour < 14 else "shift_2" if 14 <= hour < 22 else "off"
        product_type = "B" if day_index % 3 == 0 else "A"

        seasonal = 6.0 * math.sin(2 * math.pi * (day_index - 20) / 365.0)
        daily = 2.5 * math.sin(2 * math.pi * (hour - 14) / 24.0)
        temperature = 14.0 + seasonal + daily + rng.gauss(0.0, 0.5)

        if production_active:
            cadence = 1.0 + 0.08 * math.sin(2 * math.pi * hour / 8.0)
            production = max(
                0.0,
                rng.gauss(scenario.production_mean * cadence, scenario.production_sd),
            )
        else:
            production = 0.0

        product_effect = 0.18 * production if product_type == "B" else 0.0
        temperature_effect = scenario.temperature_coefficient * max(temperature - 20.0, 0.0)
        temperature_effect += 0.45 * max(10.0 - temperature, 0.0)
        power = scenario.fixed_load_kw + (12.0 if production_active else 0.0)
        power += 1.55 * production + product_effect + temperature_effect

        components: dict[str, float] = {}
        if include_anomalies:
            if 20 <= day_index < 35 and not production_active and (hour >= 22 or hour < 6):
                components["A01"] = 18.0
            if 45 <= day_index < 60 and weekday >= 5 and 8 <= hour < 18:
                components["A02"] = 22.0
            if 60 <= day_index < 90:
                components["A03"] = 12.0 * (day_index - 60 + hour / 24.0) / 30.0
            if day_index == 50 and 10 <= hour < 12:
                components["A04"] = 120.0
            if 70 <= day_index < 85 and production_active:
                components["A05"] = 0.45 * production
            if day_index >= 90:
                components["A06"] = 8.0

        for anomaly_id, extra_kw in components.items():
            power += extra_kw
            impacts[anomaly_id] += extra_kw * INTERVAL_HOURS
        power = max(0.0, power + rng.gauss(0.0, scenario.noise_sd_kw))
        energy = power * INTERVAL_HOURS
        rows.append(
            {
                "timestamp": _iso(timestamp),
                "energy_kwh": round(energy, 6),
                "power_kw": round(power, 6),
                "production": round(production, 6),
                "production_active": "true" if production_active else "false",
                "outside_temperature_c": round(temperature, 3),
                "shift": shift,
                "product_type": product_type,
            }
        )

    anomalies = [
        _event(
            "A01", "night_anomaly", start + timedelta(days=20),
            start + timedelta(days=35), 18.0, impacts["A01"],
            "Charge additionnelle recurrente pendant les nuits de la fenetre.",
        ),
        _event(
            "A02", "weekend_anomaly", start + timedelta(days=45),
            start + timedelta(days=60), 22.0, impacts["A02"],
            "Charge additionnelle le week-end entre 08:00 et 18:00.",
        ),
        _event(
            "A03", "progressive_drift", start + timedelta(days=60),
            start + timedelta(days=90), "0->12 kW", impacts["A03"],
            "Derive lineaire de la charge sur trente jours.",
        ),
        _event(
            "A04", "point_spike", start + timedelta(days=50, hours=10),
            start + timedelta(days=50, hours=12), 120.0, impacts["A04"],
            "Pic ponctuel de deux heures.",
        ),
        _event(
            "A05", "efficiency_drop", start + timedelta(days=70),
            start + timedelta(days=85), "+0.45 kW/unite_intervalle", impacts["A05"],
            "Production comparable mais coefficient energie-production degrade.",
        ),
        _event(
            "A06", "permanent_baseline_shift", start + timedelta(days=90),
            start + timedelta(days=days), 8.0, impacts["A06"],
            "Changement permanent de charge fixe.",
        ),
    ] if include_anomalies else []

    data_quality_issues: list[dict[str, Any]] = []
    if include_data_issues:
        issue_specs = [
            (5, 12, 0),
            (5, 12, 15),
        ]
        missing_timestamps = {
            _iso(start + timedelta(days=day, hours=hour, minutes=minute))
            for day, hour, minute in issue_specs
        }
        rows = [row for row in rows if row["timestamp"] not in missing_timestamps]
        data_quality_issues.append(
            _event(
                "DQ01", "missing_intervals", start + timedelta(days=5, hours=12),
                start + timedelta(days=5, hours=12, minutes=30), 2, None,
                "Deux intervalles consecutifs retires.",
            )
        )

        def row_at(day: int, hour: int) -> dict[str, Any]:
            wanted = _iso(start + timedelta(days=day, hours=hour))
            return next(row for row in rows if row["timestamp"] == wanted)

        duplicate = dict(row_at(10, 9))
        rows.append(duplicate)
        data_quality_issues.append(
            _event(
                "DQ02", "identical_duplicate", start + timedelta(days=10, hours=9),
                start + timedelta(days=10, hours=9, minutes=15), 1, None,
                "Une ligne strictement identique dupliquee.",
            )
        )

        missing_energy = row_at(12, 11)
        missing_energy["energy_kwh"] = ""
        data_quality_issues.append(
            _event(
                "DQ03", "missing_value", start + timedelta(days=12, hours=11),
                start + timedelta(days=12, hours=11, minutes=15), 1, None,
                "Valeur energy_kwh manquante.",
            )
        )

        invalid_timestamp = row_at(13, 11)
        original_invalid_time = invalid_timestamp["timestamp"]
        invalid_timestamp["timestamp"] = "timestamp_invalide"
        data_quality_issues.append(
            _event(
                "DQ04", "invalid_timestamp", start + timedelta(days=13, hours=11),
                start + timedelta(days=13, hours=11, minutes=15), 1, None,
                f"Timestamp remplace ({original_invalid_time}).",
            )
        )

        impossible = row_at(14, 11)
        impossible["energy_kwh"] = -5.0
        data_quality_issues.append(
            _event(
                "DQ05", "impossible_value", start + timedelta(days=14, hours=11),
                start + timedelta(days=14, hours=11, minutes=15), -5.0, None,
                "Energie negative impossible injectee.",
            )
        )
        rows.sort(key=lambda row: str(row["timestamp"]))

    csv_target = Path(csv_path)
    truth_target = Path(truth_path)
    csv_target.parent.mkdir(parents=True, exist_ok=True)
    truth_target.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "timestamp", "energy_kwh", "power_kw", "production", "production_active",
        "outside_temperature_c", "shift", "product_type",
    ]
    with csv_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    truth = {
        "schema_version": 1,
        "scenario": scenario_name,
        "seed": seed,
        "start": _iso(start),
        "end": _iso(start + timedelta(days=days)),
        "days": days,
        "interval_minutes": INTERVAL_MINUTES,
        "nominal_rows": interval_count,
        "written_rows": len(rows),
        "scenario_parameters": asdict(scenario),
        "anomalies_enabled": include_anomalies,
        "anomalies": anomalies,
        "data_quality_issues": data_quality_issues,
        "investigation_access": "forbidden",
    }
    truth_target.write_text(
        json.dumps(truth, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return truth
