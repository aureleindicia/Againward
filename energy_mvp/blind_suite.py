from __future__ import annotations

import csv
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from .intake import intake_template


CASE_NAMES = (
    "normal_scheduled",
    "progressive_drift",
    "permanent_level_shift",
    "intermittent_unknown",
    "legitimate_point_maintenance",
    "weather_variation",
    "production_variation",
    "product_mix_change",
    "legitimate_night_shift",
    "maintenance_shutdown",
    "missing_and_misleading",
    "overlapping_changes",
    "short_cycling_unknown",
    "normal_24_7_multi_regime",
)


def _event(
    identifier: str,
    event_type: str,
    start: datetime,
    end: datetime,
    expected_energy_impact: float,
) -> dict[str, Any]:
    return {
        "anomaly_id": identifier,
        "type": event_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "expected_energy_impact": expected_energy_impact,
    }


def generate_blind_case(
    case_name: str,
    input_path: str | Path,
    intake_path: str | Path,
    truth_path: str | Path,
    *,
    seed: int,
) -> None:
    """Générateur distinct de demo.py; la vérité est écrite dans un fichier séparé."""

    if case_name not in CASE_NAMES:
        raise ValueError(f"Cas aveugle inconnu: {case_name}.")
    rng = random.Random(seed)
    zone = ZoneInfo("Europe/Paris")
    origin = datetime(2025, 9, 1, tzinfo=zone)
    origin_utc = origin.astimezone(timezone.utc)
    total_hours = 90 * 24
    anomalies: list[dict[str, Any]] = []
    legitimate_events: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    impacts: dict[str, float] = {}
    intake = intake_template()
    intake["site"].update({
        "name": f"blind-{case_name}",
        "activity": "fabrication légère",
        "timezone": "Europe/Paris",
        "meter_scope": "atelier principal",
        "operations_contact_role": "responsable de production",
    })
    intake["metering"].update({
        "measurement_kind": "power",
        "unit": "kW",
        "timestamp_position": "start",
        "nominal_interval_minutes": 60,
    })
    intake["operations"].update({
        "operating_mode": "scheduled",
        "weekly_schedule": {
            "monday_friday": ["07:00", "18:00"],
            "saturday_sunday": None,
        },
        "legitimate_night_activity": False,
        "legitimate_weekend_activity": False,
    })
    intake["production"].update({
        "available": True, "unit": "unités/heure", "product_families_available": True,
    })
    intake["weather"]["material_for_site"] = True
    intake["cost"].update({
        "flat_price_per_kwh": 0.20,
        "has_time_of_use_or_demand_charges": False,
    })

    if case_name == "normal_24_7_multi_regime":
        intake["operations"].update({
            "operating_mode": "24_7", "weekly_schedule": {},
            "legitimate_night_activity": True, "legitimate_weekend_activity": True,
        })

    drift_start = origin + timedelta(days=38)
    drift_end = origin + timedelta(days=68)
    level_start = origin + timedelta(days=58)
    maintenance_start = origin + timedelta(days=44, hours=9)
    maintenance_end = maintenance_start + timedelta(hours=3)
    shutdown_start = origin + timedelta(days=50)
    shutdown_end = shutdown_start + timedelta(days=2)
    night_start = origin + timedelta(days=35)
    night_end = origin + timedelta(days=50)
    unknown_start = origin + timedelta(days=45)
    unknown_end = unknown_start + timedelta(days=10)

    for index in range(total_hours):
        timestamp = (origin_utc + timedelta(hours=index)).astimezone(zone)
        day_index = (timestamp.date() - origin.date()).days
        hour = timestamp.hour
        weekday = timestamp.weekday()
        temperature = 14 + 9 * math.sin(2 * math.pi * day_index / 90) + 3 * math.sin(
            2 * math.pi * (hour - 8) / 24
        )
        active = weekday < 5 and 7 <= hour < 18
        product = "B" if (day_index // 7) % 3 == 2 else "A"
        production = (18 + 4 * math.sin(index * 0.19) + rng.uniform(-1.5, 1.5)) if active else 0.0

        if case_name == "normal_24_7_multi_regime":
            active = True
            shift = hour // 8
            production = 10 + shift * 7 + 3 * math.sin(index * 0.11) + rng.uniform(-1, 1)
            product = "B" if shift == 2 else "A"
        if case_name == "production_variation" and day_index >= 45 and active:
            production *= 1.75
        if case_name == "product_mix_change" and day_index >= 45 and active:
            product = "B"
        if case_name == "legitimate_night_shift" and night_start <= timestamp < night_end:
            if weekday < 5 and (hour >= 22 or hour < 5):
                active = True
                production = 12 + rng.uniform(-1, 1)
                product = "A"
        if case_name == "maintenance_shutdown" and shutdown_start <= timestamp < shutdown_end:
            active = False
            production = 0.0

        weather_coefficient = 0.45
        if case_name == "weather_variation":
            weather_coefficient = 2.1
        base = 16.0 + weather_coefficient * max(temperature - 18, 0)
        production_coefficient = 1.8 if product == "A" else 2.25
        power = base + production_coefficient * production + rng.gauss(0, 1.1)

        added = 0.0
        if case_name == "progressive_drift" and drift_start <= timestamp < drift_end:
            added = 0.5 * ((timestamp - drift_start).total_seconds() / 86400)
            impacts["B01"] = impacts.get("B01", 0.0) + added
        elif case_name == "permanent_level_shift" and timestamp >= level_start:
            added = 13.0
            impacts["B01"] = impacts.get("B01", 0.0) + added
        elif case_name == "overlapping_changes":
            if drift_start <= timestamp < drift_end:
                component = 0.35 * ((timestamp - drift_start).total_seconds() / 86400)
                added += component
                impacts["B01"] = impacts.get("B01", 0.0) + component
            if timestamp >= level_start:
                added += 9.0
                impacts["B02"] = impacts.get("B02", 0.0) + 9.0
        elif case_name == "intermittent_unknown":
            if day_index in {34, 41, 53, 67} and 1 <= hour < 5:
                added = 22.0
                identifier = f"B{(34, 41, 53, 67).index(day_index) + 1:02d}"
                impacts[identifier] = impacts.get(identifier, 0.0) + added
        elif case_name == "legitimate_point_maintenance" and maintenance_start <= timestamp < maintenance_end:
            added = 85.0
            impacts["L01"] = impacts.get("L01", 0.0) + added
        elif case_name == "maintenance_shutdown" and shutdown_start <= timestamp < shutdown_end:
            added = 28.0
            impacts["L01"] = impacts.get("L01", 0.0) + added
        elif case_name == "short_cycling_unknown" and unknown_start <= timestamp < unknown_end:
            if not active and hour % 2 == 0:
                added = 26.0
                impacts["B01"] = impacts.get("B01", 0.0) + added

        power = max(power + added, 0.1)
        rows.append({
            "timestamp": timestamp.isoformat(),
            "power_kw": f"{power:.6f}",
            "production": f"{production:.6f}",
            "production_active": str(int(active)),
            "outside_temperature_c": f"{temperature:.4f}",
            "product_type": product,
            "shift": "night" if hour < 7 or hour >= 18 else "day",
        })

    if case_name == "progressive_drift":
        anomalies.append(_event(
            "B01", "progressive_drift", drift_start, drift_end, impacts["B01"]
        ))
    elif case_name == "permanent_level_shift":
        anomalies.append(_event(
            "B01", "permanent_baseline_shift", level_start,
            (origin_utc + timedelta(hours=total_hours)).astimezone(zone), impacts["B01"],
        ))
    elif case_name == "overlapping_changes":
        anomalies.extend([
            _event("B01", "progressive_drift", drift_start, drift_end, impacts["B01"]),
            _event(
                "B02", "permanent_baseline_shift", level_start,
                (origin_utc + timedelta(hours=total_hours)).astimezone(zone), impacts["B02"],
            ),
        ])
    elif case_name == "intermittent_unknown":
        for number, day in enumerate((34, 41, 53, 67), start=1):
            start = origin + timedelta(days=day, hours=1)
            identifier = f"B{number:02d}"
            anomalies.append(_event(
                identifier, "intermittent_unknown", start, start + timedelta(hours=4),
                impacts[identifier],
            ))
    elif case_name == "short_cycling_unknown":
        anomalies.append(_event(
            "B01", "short_cycling_unknown", unknown_start, unknown_end, impacts["B01"],
        ))
    elif case_name == "legitimate_point_maintenance":
        legitimate_events.append(_event(
            "L01", "planned_maintenance", maintenance_start, maintenance_end, impacts["L01"]
        ))
        intake["operations"]["known_maintenance_periods"] = [{
            "start": maintenance_start.isoformat(), "end": maintenance_end.isoformat(),
            "reason": "essai de réception planifié",
        }]
    elif case_name == "maintenance_shutdown":
        legitimate_events.append(_event(
            "L01", "planned_maintenance", shutdown_start, shutdown_end, impacts["L01"]
        ))
        intake["operations"]["known_maintenance_periods"] = [{
            "start": shutdown_start.isoformat(), "end": shutdown_end.isoformat(),
            "reason": "maintenance annuelle avec utilités maintenues",
        }]

    if case_name == "legitimate_night_shift":
        intake["known_changes"].append({
            "start": night_start.isoformat(), "end": night_end.isoformat(),
            "change": "équipe de nuit temporaire autorisée",
        })
    if case_name == "product_mix_change":
        intake["known_changes"].append({
            "start": (origin + timedelta(days=45)).isoformat(),
            "change": "passage temporaire à la famille produit B",
        })

    if case_name == "missing_and_misleading":
        # Les suppressions sont postérieures à la simulation et ne créent aucune vérité d'anomalie.
        rows = [row for i, row in enumerate(rows) if not (1000 <= i < 1008 or i in {1300, 1301})]
        for row in rows[1200:1220]:
            row["production"] = ""

    input_target = Path(input_path)
    input_target.parent.mkdir(parents=True, exist_ok=True)
    with input_target.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    Path(intake_path).write_text(
        json.dumps(intake, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path(truth_path).write_text(json.dumps({
        "schema_version": 1,
        "case_name": case_name,
        "seed": seed,
        "anomalies": anomalies,
        "legitimate_events": legitimate_events,
        "investigation_access": "forbidden",
        "generator_family": "independent_hourly_operational",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
