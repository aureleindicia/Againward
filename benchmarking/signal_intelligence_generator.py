from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import shutil
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable
from zoneinfo import ZoneInfo

from .physical_expertise import tree_commitment
from .physical_expertise import sha256_file


BENCHMARK_VERSION = "2.3"
TIERS = ("L0_E15", "L1_PQ1", "L2_EDGE")
START_LOCAL = datetime(2026, 3, 2, 0, 0, tzinfo=ZoneInfo("Europe/Paris"))
OBSERVED_DAYS = 42
FUTURE_DAYS = 14

PROTOCOL_RELATIVE_FILES = (
    "benchmarking/signal_intelligence.py",
    "benchmarking/signal_deterministic_baseline.py",
    "benchmarking/signal_intelligence_cli.py",
    "benchmarking/signal_intelligence_generator.py",
    "run_signal_intelligence_benchmark.py",
    "benchmarks/signal_intelligence_v2/schemas/response.schema.json",
    "benchmarks/signal_intelligence_v2/templates/response.template.json",
)


@dataclass(frozen=True)
class Asset:
    asset_id: str
    asset_type: str
    nominal_kw: float
    q_ratio: float
    ramp_seconds: float
    inrush_ratio: float
    harmonic_pct: float
    installation_year: int


@dataclass(frozen=True)
class Scenario:
    family_id: str
    sector: str
    site_kind: str
    stage: str
    event_class: str
    mechanism: str
    target_asset_id: str | None
    onset_day: int | None
    outcome_day: int | None
    outcome_code: str
    acceptable_actions: tuple[str, ...]
    dangerous_actions: tuple[str, ...]
    description_private: str


ASSETS: dict[str, tuple[Asset, ...]] = {
    "plasturgie": (
        Asset("BASE-01", "services_site", 4.0, 0.18, 2.0, 1.0, 4.0, 2019),
        Asset("PR-01", "presse_injection", 42.0, 0.35, 3.0, 2.6, 11.0, 2017),
        Asset("PR-02", "presse_injection", 36.0, 0.34, 3.4, 2.5, 10.0, 2020),
        Asset("PR-03", "presse_injection", 30.0, 0.32, 4.0, 2.2, 9.0, 2015),
        Asset("DR-01", "secheur_matiere", 12.0, 0.08, 18.0, 1.1, 6.0, 2021),
        Asset("CH-01", "groupe_froid", 15.0, 0.42, 8.0, 2.1, 12.0, 2018),
        Asset("CA-01", "compresseur_air", 18.0, 0.48, 2.5, 3.0, 13.0, 2016),
    ),
    "froid_industriel": (
        Asset("BASE-01", "services_site", 6.0, 0.20, 2.0, 1.0, 4.0, 2020),
        Asset("RF-01", "compresseur_froid", 28.0, 0.46, 4.0, 2.8, 14.0, 2017),
        Asset("RF-02", "compresseur_froid", 24.0, 0.45, 4.5, 2.7, 13.0, 2019),
        Asset("EV-01", "ventilateurs_evaporateur", 7.0, 0.38, 5.0, 1.8, 10.0, 2018),
        Asset("DF-01", "degivrage_electrique", 20.0, 0.02, 1.0, 1.0, 3.0, 2018),
        Asset("CV-01", "convoyeur", 8.0, 0.39, 2.5, 2.4, 9.0, 2022),
    ),
    "blanchisserie": (
        Asset("BASE-01", "services_site", 3.0, 0.16, 2.0, 1.0, 4.0, 2021),
        Asset("WS-01", "laveuse_essoreuse", 16.0, 0.34, 3.5, 2.4, 10.0, 2018),
        Asset("WS-02", "laveuse_essoreuse", 14.0, 0.33, 3.8, 2.3, 10.0, 2020),
        Asset("DR-01", "sechoir", 26.0, 0.25, 7.0, 1.8, 8.0, 2017),
        Asset("DR-02", "sechoir", 23.0, 0.24, 7.5, 1.8, 8.0, 2016),
        Asset("VT-01", "ventilation", 7.0, 0.40, 5.0, 2.0, 11.0, 2019),
        Asset("ST-01", "auxiliaire_thermique", 9.0, 0.12, 12.0, 1.2, 5.0, 2015),
    ),
}


SCENARIOS: tuple[Scenario, ...] = (
    Scenario(
        "P_CHILLER_FOULING", "plasturgie", "atelier_injection", "DEV",
        "PROGRESSIVE_DEGRADATION", "HEAT_EXCHANGE_DEGRADATION", "CH-01", 12, 49,
        "MAINTENANCE_INTERVENTION",
        ("INSPECT_HEAT_EXCHANGE", "MEASURE_TEMPERATURE_DIFFERENTIAL", "REVIEW_COOLING_CONTROL"),
        ("STOP_COOLING_UNSUPERVISED", "CHANGE_SETPOINT_WITHOUT_PROCESS_APPROVAL"),
        "Encrassement progressif du groupe froid, puissance conditionnelle en hausse avant intervention.",
    ),
    Scenario(
        "P_DRYER_EARLY", "plasturgie", "atelier_injection", "DEV",
        "ENERGY_WASTE", "EXCESS_PRESTART_RUNTIME", "DR-01", 14, None, "NONE",
        ("REVIEW_DRYER_SCHEDULE", "CONTROLLED_TIMER_TEST", "VERIFY_PROCESS_PRECONDITIONS"),
        ("DISABLE_MATERIAL_DRYING_UNSUPERVISED",),
        "Séchage matière démarré deux heures trop tôt sans changement de besoin produit.",
    ),
    Scenario(
        "P_AIR_LEAK", "plasturgie", "atelier_injection", "DEV",
        "ENERGY_WASTE", "COMPRESSED_AIR_LEAK", "CA-01", 18, None, "NONE",
        ("LEAK_SURVEY", "REVIEW_COMPRESSOR_CYCLES", "MEASURE_PRESSURE_DECAY"),
        ("ISOLATE_AIR_WITHOUT_PRODUCTION_APPROVAL",),
        "Fuite d'air augmentant la fréquence de cycles, surtout hors production.",
    ),
    Scenario(
        "P_MIX_NORMAL", "plasturgie", "atelier_injection", "HOLDOUT",
        "NO_ABNORMALITY", "NORMAL_PRODUCT_MIX", None, 17, None, "NONE",
        ("NO_ACTION", "VERIFY_PRODUCT_MIX"), (),
        "Famille produit plus énergivore, entièrement expliquée par les données de production.",
    ),
    Scenario(
        "C_SHORT_CYCLE", "froid_industriel", "entrepot_froid", "DEV",
        "PROGRESSIVE_DEGRADATION", "REFRIGERATION_SHORT_CYCLING", "RF-02", 11, 48,
        "MAINTENANCE_INTERVENTION",
        ("REVIEW_REFRIGERATION_CYCLES", "CHECK_PRESSURE_TEMPERATURE_LOGS", "TECHNICIAN_INSPECTION"),
        ("BYPASS_REFRIGERATION_SAFETY", "CHANGE_PRESSURE_SETPOINT_UNSUPERVISED"),
        "Cycles de plus en plus courts sur un compresseur avant intervention frigoriste.",
    ),
    Scenario(
        "C_INVENTORY_NORMAL", "froid_industriel", "entrepot_froid", "DEV",
        "NO_ABNORMALITY", "NORMAL_THROUGHPUT_DEMAND", None, 16, None, "NONE",
        ("NO_ACTION", "VERIFY_THROUGHPUT_NORMALIZATION"), (),
        "Hausse légitime liée à davantage de palettes et d'ouvertures, visible dans l'activité.",
    ),
    Scenario(
        "C_DEFROST_OVERLAP", "froid_industriel", "entrepot_froid", "HOLDOUT",
        "ENERGY_WASTE", "EXCESS_DEFROST_RUNTIME", "DF-01", 15, None, "NONE",
        ("REVIEW_DEFROST_SCHEDULE", "VERIFY_COIL_CONDITION", "CONTROLLED_SCHEDULE_TEST"),
        ("DISABLE_DEFROST_UNSUPERVISED",),
        "Dégivrages additionnels et mal synchronisés, sans panne future.",
    ),
    Scenario(
        "C_HEATWAVE_NORMAL", "froid_industriel", "entrepot_froid", "HOLDOUT",
        "NO_ABNORMALITY", "NORMAL_WEATHER_DEMAND", None, 19, None, "NONE",
        ("NO_ACTION", "VERIFY_WEATHER_NORMALIZATION"), (),
        "Hausse légitime de charge frigorifique expliquée par une période chaude visible.",
    ),
    Scenario(
        "C_EVAP_FAN_FAULT", "froid_industriel", "entrepot_froid", "HOLDOUT",
        "ABRUPT_FAULT", "EVAPORATOR_FAN_CONTROL_FAULT", "EV-01", 24, 47, "FAILURE",
        ("INSPECT_EVAPORATOR_FANS", "REVIEW_FAN_CONTROL_STATES", "TECHNICIAN_INSPECTION"),
        ("BYPASS_FAN_SAFETY", "ENTER_COLD_ZONE_WITHOUT_PROCEDURE"),
        "Comportement de commande abrupt et irrégulier avant défaillance future des ventilateurs.",
    ),
    Scenario(
        "L_DRYER_FOULING", "blanchisserie", "blanchisserie_industrielle", "HOLDOUT",
        "PROGRESSIVE_DEGRADATION", "AIRFLOW_RESTRICTION", "DR-02", 10, 50,
        "MAINTENANCE_INTERVENTION",
        ("INSPECT_FILTER_AIRFLOW", "COMPARE_DRYING_CYCLE_DURATION", "TECHNICIAN_INSPECTION"),
        ("BYPASS_THERMAL_SAFETY", "RUN_UNATTENDED_TEST"),
        "Restriction progressive d'air augmentant durée et énergie des cycles avant intervention.",
    ),
    Scenario(
        "L_METER_STEP_DEV", "blanchisserie", "blanchisserie_industrielle", "DEV",
        "METER_ARTIFACT", "METER_SCALE_SHIFT", None, 18, None, "NONE",
        ("VERIFY_METER_CONFIGURATION", "RECONCILE_WITH_BILLING_METER"),
        ("ALTER_METER_CONFIGURATION_WITHOUT_AUTHORIZATION",),
        "Décalage de facteur compteur sans changement physique des actifs, cas DEV.",
    ),
    Scenario(
        "L_STANDBY_WASTE", "blanchisserie", "blanchisserie_industrielle", "HOLDOUT",
        "ENERGY_WASTE", "EXCESS_IDLE_RUNTIME", "ST-01", 16, None, "NONE",
        ("REVIEW_SHUTDOWN_SEQUENCE", "CONTROLLED_TIMER_TEST", "VERIFY_PROCESS_PRECONDITIONS"),
        ("CUT_THERMAL_AUXILIARY_UNSUPERVISED",),
        "Auxiliaire thermique restant en service plusieurs heures après la fin des cycles.",
    ),
    Scenario(
        "L_HEAVY_MIX_NORMAL", "blanchisserie", "blanchisserie_industrielle", "HOLDOUT",
        "NO_ABNORMALITY", "NORMAL_PRODUCT_MIX", None, 20, None, "NONE",
        ("NO_ACTION", "VERIFY_LINEN_MIX"), (),
        "Période de linge lourd avec cycles plus longs, renseignée dans le suivi d'activité.",
    ),
    Scenario(
        "X_METER_STEP", "plasturgie", "atelier_injection", "HOLDOUT",
        "METER_ARTIFACT", "METER_SCALE_SHIFT", None, 20, None, "NONE",
        ("VERIFY_METER_CONFIGURATION", "RECONCILE_WITH_BILLING_METER"),
        ("ALTER_METER_CONFIGURATION_WITHOUT_AUTHORIZATION",),
        "Décalage de facteur compteur sans changement physique des actifs.",
    ),
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def _stable_seed(seed: int, value: str) -> int:
    digest = hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()
    return int(digest[:16], 16)


def _case_id(seed: int, family_id: str, tier: str) -> str:
    digest = hashlib.sha256(f"signal-v2:{seed}:{family_id}:{tier}".encode()).hexdigest()
    return f"SI2-{digest[:10].upper()}"


def _assets_for(sector: str) -> dict[str, Asset]:
    return {asset.asset_id: asset for asset in ASSETS[sector]}


def _ambient_temperature(day: int, sector: str, scenario: Scenario, rng: random.Random) -> float:
    base = 10.0 + 4.5 * math.sin(2 * math.pi * day / 28.0)
    if sector == "froid_industriel":
        base += 1.5
    if scenario.family_id == "C_HEATWAVE_NORMAL" and 19 <= day <= 31:
        base += 11.0
    return base + rng.gauss(0.0, 0.6)


def _daily_context(scenario: Scenario, rng: random.Random) -> dict[int, dict[str, Any]]:
    result: dict[int, dict[str, Any]] = {}
    for day in range(OBSERVED_DAYS + FUTURE_DAYS + 1):
        date = (START_LOCAL + timedelta(days=day)).date()
        weekday = date.weekday()
        operating = weekday < (6 if scenario.sector == "blanchisserie" else 5)
        temperature = _ambient_temperature(day, scenario.sector, scenario, rng)
        if scenario.sector == "plasturgie":
            family = "F01" if day % 3 else "F02"
            if scenario.family_id == "P_MIX_NORMAL" and 17 <= day <= 30:
                family = "F03"
            output = (920 if operating else 0) * (1 + rng.gauss(0, 0.045))
            if family == "F03":
                output *= 0.88
        elif scenario.sector == "froid_industriel":
            family = "STORAGE"
            output = (48 if operating else 22) * (1 + rng.gauss(0, 0.07))
            if scenario.family_id == "C_INVENTORY_NORMAL" and 16 <= day <= 30:
                output *= 1.45
        else:
            family = "STANDARD"
            if scenario.family_id == "L_HEAVY_MIX_NORMAL" and 20 <= day <= 33:
                family = "HEAVY"
            output = (6200 if operating else 0) * (1 + rng.gauss(0, 0.055))
            if family == "HEAVY":
                output *= 0.82
        result[day] = {
            "date": date.isoformat(),
            "operating_day": operating,
            "product_family": family,
            "output_units": round(max(0.0, output), 2),
            "outside_temperature_c": round(temperature, 2),
            "planned_shift": (
                "06:00-22:00" if scenario.sector == "plasturgie" else
                "24/7" if scenario.sector == "froid_industriel" else
                "06:00-18:00"
            ),
        }
    return result


def _progress(day_fraction: float, onset_day: int, cutoff_day: int = OBSERVED_DAYS) -> float:
    if day_fraction < onset_day:
        return 0.0
    return min(1.0, (day_fraction - onset_day) / max(1.0, cutoff_day - onset_day))


def _base_asset_powers(
    scenario: Scenario,
    local: datetime,
    context: dict[str, Any],
) -> dict[str, float]:
    hour = local.hour + local.minute / 60.0
    minute = local.hour * 60 + local.minute
    weekday = local.weekday()
    operating = bool(context["operating_day"])
    family = str(context["product_family"])
    temp = float(context["outside_temperature_c"])
    powers: dict[str, float] = {asset_id: 0.0 for asset_id in _assets_for(scenario.sector)}

    if scenario.sector == "plasturgie":
        powers["BASE-01"] = 4.0
        active = operating and 6 <= hour < 22
        if active:
            powers["PR-01"] = 42.0 if minute % 52 < 39 else 7.0
            powers["PR-02"] = 36.0 if (minute + 17) % 61 < 43 else 6.0
            powers["PR-03"] = 30.0 if (minute + 31) % 73 < 49 else 5.0
            if family == "F03":
                powers["PR-01"] *= 1.13
                powers["PR-02"] *= 1.09
        if operating and 4.5 <= hour < 21:
            powers["DR-01"] = 12.0
        if active:
            powers["CH-01"] = 8.0 + max(0.0, temp - 8.0) * 0.28
        compressor_period = 25 if active else 125
        if minute % compressor_period < 8:
            powers["CA-01"] = 18.0

    elif scenario.sector == "froid_industriel":
        powers["BASE-01"] = 6.0
        throughput = float(context["output_units"])
        load = max(0.0, temp + 2.0) + max(0.0, throughput - 30.0) * 0.08
        period_1 = 34
        on_1 = min(27, 12 + int(load * 0.42))
        powers["RF-01"] = 28.0 if minute % period_1 < on_1 else 2.0
        period_2 = 39
        on_2 = min(30, 10 + int(load * 0.36))
        powers["RF-02"] = 24.0 if (minute + 11) % period_2 < on_2 else 1.5
        powers["EV-01"] = 7.0 if minute % 30 < 24 else 3.0
        powers["DF-01"] = 20.0 if minute % 360 < 20 else 0.0
        powers["CV-01"] = 8.0 if weekday < 5 and 7 <= hour < 18 and minute % 45 < 26 else 0.0

    else:
        powers["BASE-01"] = 3.0
        active = operating and 6 <= hour < 18
        if active:
            powers["WS-01"] = 16.0 if (minute - 360) % 58 < 39 else 2.0
            powers["WS-02"] = 14.0 if (minute - 343) % 64 < 43 else 2.0
            heavy_extra = 10 if family == "HEAVY" else 0
            powers["DR-01"] = 26.0 if (minute + 10) % (66 + heavy_extra) < (47 + heavy_extra) else 2.5
            powers["DR-02"] = 23.0 if (minute + 37) % (71 + heavy_extra) < (51 + heavy_extra) else 2.0
            powers["VT-01"] = 7.0
            powers["ST-01"] = 9.0
        elif operating and 5 <= hour < 6:
            powers["ST-01"] = 9.0
    return powers


def _apply_scenario(
    scenario: Scenario,
    local: datetime,
    context: dict[str, Any],
    powers: dict[str, float],
) -> tuple[dict[str, float], float]:
    modified = dict(powers)
    day_fraction = (local.date() - START_LOCAL.date()).days + (local.hour * 60 + local.minute) / 1440.0
    onset = scenario.onset_day
    if onset is None or day_fraction < onset:
        return modified, 0.0

    if scenario.family_id == "P_CHILLER_FOULING":
        factor = 1.0 + 0.42 * _progress(day_fraction, onset)
        modified["CH-01"] *= factor
    elif scenario.family_id == "P_DRYER_EARLY":
        if bool(context["operating_day"]) and 2.5 <= local.hour + local.minute / 60.0 < 4.5:
            modified["DR-01"] = 12.0
    elif scenario.family_id == "P_AIR_LEAK":
        minute = local.hour * 60 + local.minute
        active = bool(context["operating_day"]) and 6 <= local.hour < 22
        if (not active and minute % 38 < 8) or (active and minute % 18 < 8):
            modified["CA-01"] = 18.0
    elif scenario.family_id == "C_SHORT_CYCLE":
        minute = local.hour * 60 + local.minute
        progress = _progress(day_fraction, onset)
        period = max(12, int(39 - 27 * progress))
        duty = max(5, int(period * 0.50))
        modified["RF-02"] = 24.0 if (minute + 11) % period < duty else 1.5
    elif scenario.family_id == "C_DEFROST_OVERLAP":
        minute = local.hour * 60 + local.minute
        if minute % 180 < 22:
            modified["DF-01"] = 20.0
    elif scenario.family_id == "C_EVAP_FAN_FAULT":
        minute = local.hour * 60 + local.minute
        modified["EV-01"] = 10.5 if minute % 11 < 8 else 0.8
    elif scenario.family_id == "L_DRYER_FOULING":
        if modified["DR-02"] > 3:
            modified["DR-02"] *= 1.0 + 0.30 * _progress(day_fraction, onset)
        minute = local.hour * 60 + local.minute
        if bool(context["operating_day"]) and 6 <= local.hour < 18:
            extension = int(13 * _progress(day_fraction, onset))
            if (minute + 37) % 71 < 51 + extension:
                modified["DR-02"] = max(modified["DR-02"], 23.0)
    elif scenario.family_id == "L_STANDBY_WASTE":
        if bool(context["operating_day"]) and 18 <= local.hour < 22:
            modified["ST-01"] = 9.0
    # Normal product/weather scenarios change only their visible business context and base load.
    physical_delta = sum(modified.values()) - sum(powers.values())
    return modified, physical_delta


def _simulate(scenario: Scenario, seed: int) -> dict[str, Any]:
    rng = random.Random(_stable_seed(seed, scenario.family_id))
    context = _daily_context(scenario, rng)
    assets = _assets_for(scenario.sector)
    start_utc = START_LOCAL.astimezone(timezone.utc)
    # The declared periods are local operating-calendar days, not fixed UTC
    # durations.  Computing the endpoints in local time avoids silently adding
    # an hour and an unrepresented calendar date across the spring DST change.
    cutoff_local = START_LOCAL + timedelta(days=OBSERVED_DAYS)
    end_local = START_LOCAL + timedelta(days=OBSERVED_DAYS + FUTURE_DAYS)
    cutoff_utc = cutoff_local.astimezone(timezone.utc)
    end_utc = end_local.astimezone(timezone.utc)
    total_minutes = int((end_utc - start_utc).total_seconds() // 60)
    aggregate_rows: list[dict[str, Any]] = []
    event_rows: list[dict[str, Any]] = []
    event_truth_rows: list[dict[str, Any]] = []
    weak_label_rows: list[dict[str, Any]] = []
    hidden_buckets: dict[str, dict[str, float]] = {}
    public_buckets: dict[str, dict[str, float]] = {}
    previous_asset_p: dict[str, float] | None = None
    expected_excess_kwh = 0.0

    for index in range(total_minutes):
        instant_utc = start_utc + timedelta(minutes=index)
        local = instant_utc.astimezone(ZoneInfo("Europe/Paris"))
        day = (local.date() - START_LOCAL.date()).days
        daily = context[day]
        base = _base_asset_powers(scenario, local, daily)
        modified, physical_delta = _apply_scenario(scenario, local, daily, base)
        if instant_utc < cutoff_utc and scenario.event_class not in {"NO_ABNORMALITY", "METER_ARTIFACT"}:
            expected_excess_kwh += max(0.0, physical_delta) / 60.0

        asset_p: dict[str, float] = {}
        q_total = 0.0
        for asset_id, value in modified.items():
            noise = rng.gauss(0.0, max(0.015, value * 0.008)) if value > 0 else 0.0
            observed = max(0.0, value + noise)
            asset_p[asset_id] = observed
            q_total += observed * assets[asset_id].q_ratio
        p_total_physical = sum(asset_p.values())
        p_total = p_total_physical + rng.gauss(0.0, 0.18)
        q_total += rng.gauss(0.0, 0.08)
        if scenario.mechanism == "METER_SCALE_SHIFT" and day >= int(scenario.onset_day or 0):
            p_total *= 1.085
            q_total *= 1.085
            if instant_utc < cutoff_utc:
                expected_excess_kwh += max(0.0, p_total - p_total_physical) / 60.0

        row = {
            "timestamp": local.isoformat(),
            "active_power_kw": round(max(0.0, p_total), 5),
            "reactive_power_kvar": round(max(0.0, q_total), 5),
        }
        if instant_utc < cutoff_utc:
            aggregate_rows.append(row)

        bucket = local.replace(minute=(local.minute // 15) * 15, second=0, microsecond=0).isoformat()
        hidden = hidden_buckets.setdefault(bucket, {asset_id: 0.0 for asset_id in assets})
        for asset_id, value in asset_p.items():
            hidden[asset_id] += value / 60.0
        if instant_utc < cutoff_utc:
            public = public_buckets.setdefault(bucket, {"energy_kwh": 0.0})
            public["energy_kwh"] += max(0.0, p_total) / 60.0

        if instant_utc < cutoff_utc and previous_asset_p is not None:
            changes = {
                asset_id: asset_p[asset_id] - previous_asset_p[asset_id]
                for asset_id in assets
                if abs(asset_p[asset_id] - previous_asset_p[asset_id]) >= 3.0
            }
            if changes:
                delta_p = sum(changes.values())
                if abs(delta_p) >= 3.0:
                    weight = sum(abs(value) for value in changes.values())
                    ramp = sum(abs(value) * assets[key].ramp_seconds for key, value in changes.items()) / weight
                    inrush = sum(abs(value) * assets[key].inrush_ratio for key, value in changes.items()) / weight
                    harmonic = sum(abs(value) * assets[key].harmonic_pct for key, value in changes.items()) / weight
                    delta_q = sum(changes[key] * assets[key].q_ratio for key in changes)
                    event_id = f"EV-{len(event_rows) + 1:06d}"
                    event_rows.append({
                        "event_id": event_id,
                        "timestamp": local.isoformat(),
                        "delta_active_power_kw": round(delta_p, 4),
                        "delta_reactive_power_kvar": round(delta_q, 4),
                        "ramp_seconds_proxy": round(ramp, 3),
                        "inrush_ratio_proxy": round(inrush, 3),
                        "harmonic_distortion_pct_proxy": round(harmonic, 3),
                        "simultaneous_change_count_proxy": len(changes),
                    })
                    dominant_asset = max(changes, key=lambda key: abs(changes[key]))
                    event_truth_rows.append({
                        "event_id": event_id,
                        "timestamp": local.isoformat(),
                        "dominant_asset_id": dominant_asset,
                        "source_asset_ids": "|".join(sorted(changes)),
                        "source_count": len(changes),
                    })
                    if len(event_rows) % 41 == 0:
                        weak_label_rows.append({
                            "timestamp": local.isoformat(),
                            "observed_asset_id": dominant_asset,
                            "label_source": "operator_walkthrough",
                        })
        previous_asset_p = asset_p

    # Small, deterministic logger defects force quality checks without creating the
    # operational event. The 15-minute and minute exports remain independent exports.
    if len(aggregate_rows) > 25000:
        for position in sorted((23117, 10007, 3201), reverse=True):
            del aggregate_rows[position]
        aggregate_rows.insert(8124, dict(aggregate_rows[8123]))
    public_energy_rows = [
        {"timestamp": timestamp, "energy_kwh": round(values["energy_kwh"], 6)}
        for timestamp, values in sorted(public_buckets.items())
    ]
    if len(public_energy_rows) > 2500:
        del public_energy_rows[1777]
        public_energy_rows.insert(912, dict(public_energy_rows[911]))

    return {
        "context": context,
        "aggregate_rows": aggregate_rows,
        "event_rows": event_rows,
        "event_truth_rows": event_truth_rows,
        "weak_label_rows": weak_label_rows,
        "public_buckets": public_buckets,
        "public_energy_rows": public_energy_rows,
        "hidden_buckets": hidden_buckets,
        "expected_excess_kwh": round(expected_excess_kwh, 3),
        "analysis_cutoff": cutoff_utc.astimezone(ZoneInfo("Europe/Paris")).isoformat(),
        "assets": assets,
    }


def _write_initial_pack(root: Path, scenario: Scenario, tier: str, simulation: dict[str, Any]) -> None:
    cutoff = simulation["analysis_cutoff"]
    (root / "00_mission.md").write_text(
        "# Mission\n\n"
        "Analyser les données disponibles jusqu'à la date de coupure sans utiliser d'information future. "
        "Rechercher les signatures électriques reproductibles, les anomalies, les optimisations et les "
        "indices de dégradation. Une attribution ou une prévision n'est admise que si elle est étayée.\n",
        encoding="utf-8",
    )
    (root / "01_site_context.md").write_text(
        f"# Contexte du site\n\nSecteur : {scenario.sector}\n"
        f"Type de site : {scenario.site_kind}\nFuseau : Europe/Paris\n"
        f"Date de coupure de l'analyse : {cutoff}\n"
        f"Horizon pronostique imposé : {FUTURE_DAYS} jours après la coupure\n"
        "Le point de mesure couvre l'intégralité du site. L'inventaire est fourni, mais aucune "
        "correspondance entre événement électrique et actif n'est donnée.\n",
        encoding="utf-8",
    )
    _write_csv(
        root / "02_asset_inventory.csv",
        ("asset_id", "asset_type", "nominal_power_kw", "installation_year"),
        (
            {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "nominal_power_kw": asset.nominal_kw,
                "installation_year": asset.installation_year,
            }
            for asset in simulation["assets"].values()
        ),
    )
    (root / "03_measurement_context.md").write_text(
        "# Mesure\n\n"
        f"Niveau disponible : {tier}\n"
        "Un seul point de mesure central est utilisé. Les timestamps sont ISO 8601 avec offset. "
        "Les fichiers ne contiennent aucun identifiant d'actif mesuré. `L2_EDGE` contient des "
        "caractéristiques extraites au même point central, pas des sous-compteurs.\n",
        encoding="utf-8",
    )
    context_rows = [
        simulation["context"][day]
        for day in range(OBSERVED_DAYS)
    ]
    _write_csv(
        root / "04_daily_operations.csv",
        ("date", "operating_day", "product_family", "output_units", "outside_temperature_c", "planned_shift"),
        context_rows,
    )
    _write_csv(
        root / "05_aggregate_energy_15min.csv",
        ("timestamp", "energy_kwh"),
        simulation["public_energy_rows"],
    )
    if tier in {"L1_PQ1", "L2_EDGE"}:
        _write_csv(
            root / "06_aggregate_power_1min.csv",
            ("timestamp", "active_power_kw", "reactive_power_kvar"),
            simulation["aggregate_rows"],
        )
    if tier == "L2_EDGE":
        _write_csv(
            root / "07_central_electrical_events.csv",
            (
                "event_id", "timestamp", "delta_active_power_kw", "delta_reactive_power_kvar",
                "ramp_seconds_proxy", "inrush_ratio_proxy", "harmonic_distortion_pct_proxy",
                "simultaneous_change_count_proxy",
            ),
            simulation["event_rows"],
        )


def _write_oracle(root: Path, case_id: str, scenario: Scenario, simulation: dict[str, Any]) -> None:
    payloads = root / "payloads"
    payloads.mkdir(parents=True, exist_ok=True)
    assets = simulation["assets"]
    # Runtime totals are deliberately useful but not a direct answer.
    runtime_rows = []
    for day in range(OBSERVED_DAYS):
        row: dict[str, Any] = {"date": simulation["context"][day]["date"]}
        for asset_id in assets:
            row[f"{asset_id}_runtime_h"] = "not_logged"
        if scenario.target_asset_id:
            base_runtime = 14.0 if scenario.sector != "froid_industriel" else 18.0
            if scenario.event_class == "PROGRESSIVE_DEGRADATION" and day >= int(scenario.onset_day or 0):
                base_runtime += min(3.0, (day - int(scenario.onset_day or 0)) * 0.08)
            row[f"{scenario.target_asset_id}_runtime_h"] = round(base_runtime, 2)
        runtime_rows.append(row)
    _write_csv(payloads / "payload_001.csv", ["date", *(f"{key}_runtime_h" for key in assets)], runtime_rows)

    maintenance_lines = [
        "# Historique disponible avant la date de coupure",
        "",
        "Aucune conclusion de panne n'est enregistrée dans la période visible.",
        "Les interventions futures et leur résultat ne sont pas disponibles pendant l'analyse.",
    ]
    if scenario.event_class == "PROGRESSIVE_DEGRADATION" and scenario.target_asset_id:
        maintenance_lines.append(
            f"Une remarque non diagnostique signale des cycles ou durées à surveiller sur {scenario.target_asset_id} durant la dernière semaine."
        )
    (payloads / "payload_002.md").write_text("\n".join(maintenance_lines) + "\n", encoding="utf-8")

    process_rows = []
    for day in range(OBSERVED_DAYS):
        context = simulation["context"][day]
        process_rows.append({
            "date": context["date"],
            "change_recorded": (
                "product_family_change" if (
                    scenario.event_class == "NO_ABNORMALITY" and day == int(scenario.onset_day or -1)
                ) else "none"
            ),
            "product_family": context["product_family"],
            "comment": "routine production record",
        })
    _write_csv(payloads / "payload_003.csv", ("date", "change_recorded", "product_family", "comment"), process_rows)

    _write_csv(
        payloads / "payload_004.csv",
        ("timestamp", "observed_asset_id", "label_source"),
        simulation["weak_label_rows"],
    )

    oracle = {
        "schema_version": 1,
        "case_id": case_id,
        "entries": [
            {
                "oracle_id": "item_001",
                "accepted_concepts": ["equipment runtime status logs"],
                "question_terms": ["equipment", "runtime", "status"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 2,
                "response": "Les durées de marche disponibles sont jointes ; plusieurs actifs ne sont pas historisés.",
                "responder_role": "responsable maintenance",
                "payload_files": ["payloads/payload_001.csv"],
            },
            {
                "oracle_id": "item_002",
                "accepted_concepts": ["maintenance alarm history"],
                "question_terms": ["maintenance", "alarm", "history"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 1,
                "response": "L'historique maintenance disponible avant la coupure est joint.",
                "responder_role": "responsable maintenance",
                "payload_files": ["payloads/payload_002.md"],
            },
            {
                "oracle_id": "item_003",
                "accepted_concepts": ["production recipe change log"],
                "question_terms": ["production", "recipe", "change", "record"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 1,
                "response": "Le journal quotidien des changements produit disponibles est joint.",
                "responder_role": "responsable production",
                "payload_files": ["payloads/payload_003.csv"],
            },
            {
                "oracle_id": "item_004",
                "accepted_concepts": ["operator walkthrough event equipment labels"],
                "question_terms": ["operator", "event", "equipment", "label"],
                "minimum_term_matches": 2,
                "availability": "available",
                "cost": 3,
                "response": "Quelques correspondances événement-actif issues d'une observation opérateur sont jointes.",
                "responder_role": "chef d'équipe",
                "payload_files": ["payloads/payload_004.csv"],
            },
        ],
    }
    _write_json(root / "oracle.json", oracle)


def _write_truth(
    root: Path,
    scenario: Scenario,
    tier: str,
    simulation: dict[str, Any],
    *,
    scenario_instance_id: str,
) -> None:
    assets = simulation["assets"]
    onset = (
        (START_LOCAL + timedelta(days=scenario.onset_day)).isoformat()
        if scenario.onset_day is not None else None
    )
    outcome_at = (
        (START_LOCAL + timedelta(days=scenario.outcome_day, hours=10)).isoformat()
        if scenario.outcome_day is not None else None
    )
    truth = {
        "schema_version": 2,
        "benchmark_version": BENCHMARK_VERSION,
        "scenario_family_id": scenario_instance_id,
        "sector": scenario.sector,
        "site_kind": scenario.site_kind,
        "measurement_tier": tier,
        "analysis_cutoff": simulation["analysis_cutoff"],
        "primary_event": {
            "event_class": scenario.event_class,
            "mechanism": scenario.mechanism,
            "target_asset_id": scenario.target_asset_id,
            "onset": onset,
            "expected_excess_energy_kwh": simulation["expected_excess_kwh"],
            "outcome_within_horizon": scenario.outcome_day is not None,
            "outcome_at": outcome_at,
            "outcome_code": scenario.outcome_code,
            "acceptable_actions": list(scenario.acceptable_actions),
            "dangerous_actions": list(scenario.dangerous_actions),
            "private_description": scenario.description_private,
        },
        "asset_signature_registry": [
            {
                "asset_id": asset.asset_id,
                "asset_type": asset.asset_type,
                "nominal_kw": asset.nominal_kw,
                "q_ratio": asset.q_ratio,
                "ramp_seconds": asset.ramp_seconds,
                "inrush_ratio": asset.inrush_ratio,
                "harmonic_pct": asset.harmonic_pct,
            }
            for asset in assets.values()
        ],
    }
    _write_json(root / "truth.json", truth)
    _write_csv(
        root / "asset_energy_15min.csv",
        ("timestamp", *assets.keys()),
        (
            {"timestamp": timestamp, **{key: round(values[key], 6) for key in assets}}
            for timestamp, values in sorted(simulation["hidden_buckets"].items())
        ),
    )
    _write_csv(
        root / "event_sources.csv",
        ("event_id", "timestamp", "dominant_asset_id", "source_asset_ids", "source_count"),
        simulation["event_truth_rows"],
    )


def generate_case(
    root: Path,
    scenario: Scenario,
    tier: str,
    *,
    seed: int,
    simulation: dict[str, Any] | None = None,
    scenario_instance_id: str | None = None,
) -> dict[str, Any]:
    if tier not in TIERS:
        raise ValueError(f"Niveau de mesure inconnu: {tier}")
    instance_id = scenario_instance_id or scenario.family_id
    case_id = _case_id(seed, instance_id, tier)
    case_root = root / scenario.stage / case_id
    if case_root.exists():
        raise FileExistsError(f"Le cas existe déjà: {case_root}")
    initial = case_root / "initial_client_pack"
    oracle = case_root / "followup_oracle"
    truth = case_root / "ground_truth"
    for directory in (initial, oracle, truth):
        directory.mkdir(parents=True)
    simulation = simulation or _simulate(scenario, seed)
    _write_initial_pack(initial, scenario, tier, simulation)
    _write_oracle(oracle, case_id, scenario, simulation)
    _write_truth(truth, scenario, tier, simulation, scenario_instance_id=instance_id)
    manifest = {
        "schema_version": 1,
        "case_id": case_id,
        "case_revision": 1,
        "stage": scenario.stage,
        "track": "CONTROLLED_OPEN_BOOK",
        "difficulty": "D4" if tier == "L0_E15" else "D3",
        "truth_level": "SYNTHETIC",
        "sector": scenario.sector,
        "initial_pack_commitment_sha256": tree_commitment(initial),
        "oracle_commitment_sha256": tree_commitment(oracle),
        "ground_truth_commitment_sha256": tree_commitment(truth),
        "max_question_cycles": 3,
        "efficiency_penalty_after_requests": 3,
        "allowed_references": [],
        "benchmark_profile": "SIGNAL_INTELLIGENCE_V2",
        "benchmark_version": BENCHMARK_VERSION,
        "measurement_tier": tier,
        "analysis_cutoff": simulation["analysis_cutoff"],
        "forecast_horizon_days": FUTURE_DAYS,
        "scenario_family_commitment": hashlib.sha256(
            f"{seed}:{instance_id}".encode()
        ).hexdigest(),
        "generator_sha256": sha256_file(Path(__file__)),
    }
    _write_json(case_root / "case_manifest.json", manifest)
    return {
        "case_id": case_id,
        "stage": scenario.stage,
        "sector": scenario.sector,
        "measurement_tier": tier,
        "scenario_family_id": instance_id,
        "case_path": str(case_root),
    }


def generate_suite(
    output_directory: str | Path,
    *,
    seed: int,
    profile: str = "full",
    replicates: int = 1,
) -> dict[str, Any]:
    root = Path(output_directory).resolve()
    if profile not in {"smoke", "full"}:
        raise ValueError("profile doit être 'smoke' ou 'full'")
    if root.exists() and any(root.iterdir()):
        raise FileExistsError(f"Le dossier de suite doit être neuf ou vide: {root}")
    root.mkdir(parents=True, exist_ok=True)
    if not isinstance(replicates, int) or isinstance(replicates, bool) or not 1 <= replicates <= 20:
        raise ValueError("replicates doit être compris entre 1 et 20")
    cases_root = root / "cases"
    selected = SCENARIOS if profile == "full" else tuple(
        next(scenario for scenario in SCENARIOS if scenario.family_id == family_id)
        for family_id in ("P_CHILLER_FOULING", "C_DEFROST_OVERLAP", "L_HEAVY_MIX_NORMAL")
    )
    tiers = TIERS if profile in {"full", "smoke"} else ("L0_E15",)
    records: list[dict[str, Any]] = []
    try:
        for replicate in range(1, replicates + 1):
            replicate_seed = seed + (replicate - 1) * 100_003
            for scenario in selected:
                # The physical realization is generated once, then exposed through each
                # measurement tier. This is a true information ablation, not three nearby cases.
                simulation = _simulate(scenario, replicate_seed)
                instance_id = f"{scenario.family_id}__R{replicate:02d}"
                for tier in tiers:
                    record = generate_case(
                        cases_root,
                        scenario,
                        tier,
                        seed=replicate_seed,
                        simulation=simulation,
                        scenario_instance_id=instance_id,
                    )
                    record["case_path"] = Path(record["case_path"]).relative_to(root).as_posix()
                    records.append(record)
    except Exception:
        # A partially generated private suite is misleading. Preserve it under an explicit name.
        incomplete = root.with_name(root.name + ".incomplete")
        if not incomplete.exists():
            shutil.move(str(root), str(incomplete))
        raise
    repository = Path(__file__).resolve().parents[1]
    protocol_snapshot = root / "protocol_snapshot"
    protocol_records = []
    for relative_name in PROTOCOL_RELATIVE_FILES:
        source = repository / relative_name
        destination = protocol_snapshot / relative_name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        protocol_records.append({
            "path": relative_name,
            "size": source.stat().st_size,
            "sha256": sha256_file(source),
        })
    suite = {
        "schema_version": 2,
        "benchmark_version": BENCHMARK_VERSION,
        "seed": seed,
        "profile": profile,
        "replicates": replicates,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "observed_days": OBSERVED_DAYS,
        "future_horizon_days": FUTURE_DAYS,
        "measurement_tiers": list(tiers),
        "generator_sha256": sha256_file(Path(__file__)),
        "protocol_files": protocol_records,
        "protocol_snapshot_commitment_sha256": tree_commitment(protocol_snapshot),
        "case_count": len(records),
        "cases": records,
    }
    _write_json(root / "suite_manifest.json", suite)
    (root / "OPERATOR_README.md").write_text(
        "# INDICIA Signal Intelligence V2 — opérateur privé\n\n"
        "Ce dossier contient les packs visibles, les oracles et les vérités de scoring. "
        "Il ne doit jamais être accessible à la session participant.\n\n"
        "## Règles\n\n"
        "- Utiliser une session neuve pour chaque run HOLDOUT.\n"
        "- Ne jamais donner suite_manifest.json, followup_oracle/, ground_truth/ ou ce chemin au participant.\n"
        "- Remettre uniquement RUN/participant_workspace/.\n"
        "- Conserver le générateur, la présente conversation et les anciens runs hors de son accès.\n"
        "- Commencer par DEV. Ne modifier ni prompt ni moteur après avoir vu un résultat HOLDOUT.\n"
        "- Les niveaux d'une même famille doivent être exécutés dans des sessions indépendantes.\n\n"
        "## Préparer\n\n"
        "```bash\n"
        "python run_signal_intelligence_benchmark.py prepare CASE_DIR RUNS_DIR \\\n"
        "  --repository . --system-ref COMMIT_FIGE \\\n"
        "  --model MODELE --reasoning-effort high --variant AGENTIC\n"
        "```\n\n"
        "Prompt participant court :\n\n"
        "```text\n"
        "/goal\n\n"
        "Travaille comme analyste indépendant uniquement dans [CHEMIN]/participant_workspace. "
        "Lis d'abord SIGNAL_INTELLIGENCE_INSTRUCTIONS.md puis exécute intégralement le protocole. "
        "N'accède à aucun fichier extérieur et n'utilise aucune information postérieure à analysis_cutoff.\n"
        "```\n\n"
        "## Demande, finalisation et score\n\n"
        "```bash\n"
        "python run_signal_intelligence_benchmark.py ask RUN CASE REQUESTS_JSON\n"
        "python run_signal_intelligence_benchmark.py finalize RUN RUN/participant_workspace/output/response.json --repository .\n"
        "python run_signal_intelligence_benchmark.py verify RUN --repository .\n"
        "python run_signal_intelligence_benchmark.py score RUN CASE\n"
        "python run_signal_intelligence_benchmark.py aggregate RUNS_DIR --output aggregate_report.json\n"
        "```\n\n"
        "Le scoring ne lit la vérité qu'après verrouillage. Un résultat synthétique sélectionne une "
        "hypothèse R&D ; il ne constitue pas une preuve terrain ou une promesse client.\n",
        encoding="utf-8",
    )
    return suite
