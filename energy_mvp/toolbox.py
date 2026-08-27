from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from statistics import median
from typing import Any, Callable, Iterable, Sequence

from .models import LoadedData, Reading


def _power_kw(reading: Reading) -> float | None:
    if reading.power_kw is not None:
        return reading.power_kw
    if reading.interval_hours is not None and reading.interval_hours > 0:
        return reading.energy_kwh / reading.interval_hours
    return None


def _quantile(values: Sequence[float], probability: float) -> float:
    if not values:
        raise ValueError("Un quantile exige au moins une valeur.")
    if not 0 <= probability <= 1:
        raise ValueError("La probabilite doit etre comprise entre 0 et 1.")
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def inspect_dataset(data: LoadedData) -> dict[str, Any]:
    readings = data.readings
    return {
        "rows": len(readings),
        "start": readings[0].timestamp.isoformat() if readings else None,
        "end": readings[-1].timestamp.isoformat() if readings else None,
        "coverage_start": data.coverage_start.isoformat() if data.coverage_start else None,
        "coverage_end": data.coverage_end.isoformat() if data.coverage_end else None,
        "timestamp_position": data.timestamp_position,
        "site_timezone": data.site_timezone,
        "coverage_bounds_method": data.coverage_bounds_method,
        "measurement_kind": data.measurement_kind.value,
        "source_units": dict(data.source_units),
        "columns": dict(data.columns),
        "frequency_minutes": data.quality.inferred_frequency_minutes,
        "coverage_ratio": data.quality.coverage_ratio,
        "quality": {
            "invalid_timestamps": data.quality.invalid_timestamp_rows,
            "missing_measurements": data.quality.missing_measurement_rows,
            "impossible_values": data.quality.impossible_value_rows,
            "identical_duplicates_removed": data.quality.identical_duplicates_removed,
            "conflicting_duplicates": data.quality.conflicting_duplicates,
            "out_of_order_rows": data.quality.out_of_order_rows,
            "timezone_normalized_rows": data.quality.timezone_normalized_rows,
            "naive_timezone_localized_rows": data.quality.naive_timezone_localized_rows,
            "missing_values_by_column": data.quality.missing_values_by_column,
            "invalid_values_by_column": data.quality.invalid_values_by_column,
            "detected_frequencies_minutes": data.quality.detected_frequencies_minutes,
            "frequency_changes": data.quality.frequency_change_count,
            "irregular_intervals": data.quality.irregular_interval_count,
            "gaps": data.quality.gap_count,
        },
    }


def extract_period(
    readings: Iterable[Reading], start: datetime, end: datetime
) -> list[Reading]:
    if end <= start:
        raise ValueError("La fin de periode doit etre posterieure au debut.")
    return [reading for reading in readings if start <= reading.timestamp < end]


def summarize_readings(readings: Sequence[Reading]) -> dict[str, float | int | None]:
    total_energy = sum(reading.energy_kwh for reading in readings)
    production_values = [
        reading.production for reading in readings if reading.production is not None
    ]
    total_hours = sum(
        reading.interval_hours or 0.0
        for reading in readings
        if reading.interval_hours is not None
    )
    powers = [value for reading in readings if (value := _power_kw(reading)) is not None]
    return {
        "rows": len(readings),
        "energy_kwh": total_energy,
        "mean_power_kw": total_energy / total_hours if total_hours > 0 else None,
        "median_power_kw": median(powers) if powers else None,
        "production": sum(production_values) if len(production_values) == len(readings) else None,
        "energy_intensity": (
            total_energy / sum(production_values)
            if len(production_values) == len(readings) and sum(production_values) > 0
            else None
        ),
    }


def _regime_value(reading: Reading, field: str) -> str:
    if field == "production_active":
        return _activity_key(reading)
    if field == "shift":
        return reading.shift or "unknown"
    if field == "product_type":
        return reading.product_type or "unknown"
    if field == "month":
        return reading.operational_timestamp.strftime("%m")
    if field == "season":
        month = reading.operational_timestamp.month
        return (
            "winter" if month in {12, 1, 2}
            else "spring" if month in {3, 4, 5}
            else "summer" if month in {6, 7, 8}
            else "autumn"
        )
    raise ValueError(f"Champ de régime inconnu: {field}.")


def summarize_operating_regimes(
    readings: Sequence[Reading],
    *,
    fields: Sequence[str] = ("production_active", "shift", "product_type"),
) -> list[dict[str, Any]]:
    """Décrit des régimes déclarés; ne décide pas lesquels sont normaux ou anormaux."""

    if not fields:
        raise ValueError("Au moins un champ de régime est requis.")
    groups: dict[tuple[str, ...], list[Reading]] = defaultdict(list)
    for reading in readings:
        groups[tuple(_regime_value(reading, field) for field in fields)].append(reading)
    output = []
    for key, items in sorted(groups.items()):
        summary = summarize_readings(items)
        output.append({
            "regime": dict(zip(fields, key)),
            **summary,
            "share_of_rows": len(items) / len(readings) if readings else 0.0,
            "decision": None,
        })
    return output


def fit_regime_baselines(
    readings: Sequence[Reading],
    *,
    regime_fields: Sequence[str],
    predictors: Sequence[str] = ("production",),
    calibration_fraction: float = 0.7,
) -> dict[str, Any]:
    """Ajuste séparément des baselines temporelles dans chaque régime observable."""

    if not regime_fields:
        raise ValueError("Au moins un champ de régime est requis.")
    groups: dict[tuple[str, ...], list[Reading]] = defaultdict(list)
    for reading in readings:
        key = tuple(_regime_value(reading, field) for field in regime_fields)
        groups[key].append(reading)
    models = []
    unavailable = []
    for key, items in sorted(groups.items()):
        regime = dict(zip(regime_fields, key))
        try:
            model = fit_linear_baseline(
                items,
                predictors=predictors,
                calibration_fraction=calibration_fraction,
            )
        except ValueError as exc:
            unavailable.append({"regime": regime, "rows": len(items), "reason": str(exc)})
            continue
        models.append({"regime": regime, "rows": len(items), "baseline": model})
    if not models:
        raise ValueError("Aucune baseline de régime n'a pu être ajustée.")
    return {
        "kind": "regime_linear_baselines",
        "regime_fields": list(regime_fields),
        "predictors": list(predictors),
        "models": models,
        "unavailable_regimes": unavailable,
        "decision": None,
    }


def compare_groups(
    readings: Sequence[Reading],
    first_filter: Callable[[Reading], bool],
    second_filter: Callable[[Reading], bool],
) -> dict[str, Any]:
    first = [reading for reading in readings if first_filter(reading)]
    second = [reading for reading in readings if second_filter(reading)]
    first_summary = summarize_readings(first)
    second_summary = summarize_readings(second)
    first_power = first_summary["mean_power_kw"]
    second_power = second_summary["mean_power_kw"]
    delta_power = (
        second_power - first_power
        if isinstance(first_power, float) and isinstance(second_power, float)
        else None
    )
    return {
        "first": first_summary,
        "second": second_summary,
        "delta_mean_power_kw": delta_power,
        "delta_mean_power_percent": (
            100 * delta_power / first_power
            if delta_power is not None and first_power
            else None
        ),
    }


def daily_profile(
    readings: Sequence[Reading], *, weekdays_only: bool | None = None
) -> list[dict[str, float | int | str | None]]:
    buckets: dict[tuple[int, int], list[Reading]] = defaultdict(list)
    for reading in readings:
        operational = reading.operational_timestamp
        is_weekday = operational.weekday() < 5
        if weekdays_only is not None and is_weekday != weekdays_only:
            continue
        buckets[(operational.hour, operational.minute)].append(reading)
    profile = []
    for (hour, minute), items in sorted(buckets.items()):
        summary = summarize_readings(items)
        profile.append(
            {
                "time": f"{hour:02d}:{minute:02d}",
                "samples": len(items),
                "mean_power_kw": summary["mean_power_kw"],
                "median_power_kw": summary["median_power_kw"],
                "mean_production": (
                    sum(item.production or 0.0 for item in items) / len(items)
                    if all(item.production is not None for item in items)
                    else None
                ),
            }
        )
    return profile


def estimate_baseload(
    readings: Sequence[Reading], *, inactive_only: bool = True
) -> dict[str, float | int]:
    eligible = [
        reading
        for reading in readings
        if not inactive_only
        or reading.production_active is False
        or (reading.production_active is None and reading.production == 0)
    ]
    powers = [value for reading in eligible if (value := _power_kw(reading)) is not None]
    if len(powers) < 20:
        raise ValueError("Au moins 20 mesures eligibles sont requises pour la charge de base.")
    low_count = max(1, math.ceil(len(powers) * 0.2))
    lowest = sorted(powers)[:low_count]
    return {
        "samples": len(powers),
        "q10_kw": _quantile(powers, 0.10),
        "q25_kw": _quantile(powers, 0.25),
        "median_lowest_20_percent_kw": median(lowest),
        "absolute_minimum_kw": min(powers),
    }


def _solve(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    augmented = [row[:] + [value] for row, value in zip(matrix, vector)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("Baseline impossible: predicteurs singuliers.")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        augmented[column] = [value / divisor for value in augmented[column]]
        for row in range(size):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [
                current - factor * reference
                for current, reference in zip(augmented[row], augmented[column])
            ]
    return [augmented[row][-1] for row in range(size)]


def _metrics(observed: Sequence[float], predicted: Sequence[float]) -> dict[str, float | None]:
    if not observed or len(observed) != len(predicted):
        raise ValueError("Les metriques exigent deux series non vides de meme longueur.")
    errors = [actual - expected for actual, expected in zip(observed, predicted)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    mean_observed = sum(observed) / len(observed)
    denominator = sum((value - mean_observed) ** 2 for value in observed)
    r_squared = (
        1 - sum(error * error for error in errors) / denominator
        if denominator > 0
        else None
    )
    mape = (
        100 * sum(abs(error / actual) for error, actual in zip(errors, observed)) / len(errors)
        if all(abs(actual) > 1e-9 for actual in observed)
        else None
    )
    return {"mae": mae, "rmse": rmse, "r_squared": r_squared, "mape": mape}


def _predictor_value(reading: Reading, name: str) -> float | None:
    if name == "production":
        return reading.production
    if name == "outside_temperature_c":
        return reading.outside_temperature_c
    if name == "heating_degree_c":
        return (
            max(18.0 - reading.outside_temperature_c, 0.0)
            if reading.outside_temperature_c is not None else None
        )
    if name == "cooling_degree_c":
        return (
            max(reading.outside_temperature_c - 18.0, 0.0)
            if reading.outside_temperature_c is not None else None
        )
    if name == "heating_degree_10_c":
        return (
            max(10.0 - reading.outside_temperature_c, 0.0)
            if reading.outside_temperature_c is not None else None
        )
    if name == "cooling_degree_20_c":
        return (
            max(reading.outside_temperature_c - 20.0, 0.0)
            if reading.outside_temperature_c is not None else None
        )
    if name == "production_active":
        return float(reading.production_active) if reading.production_active is not None else None
    if name == "product_type_b":
        return float(reading.product_type == "B") if reading.product_type is not None else None
    if name == "production_product_b":
        if reading.product_type is None or reading.production is None:
            return None
        return reading.production * float(reading.product_type == "B")
    raise ValueError(f"Predicteur inconnu: {name}")


def fit_linear_baseline(
    readings: Sequence[Reading],
    *,
    predictors: Sequence[str] = ("production",),
    calibration_fraction: float = 0.7,
) -> dict[str, Any]:
    if not 0.5 <= calibration_fraction < 1:
        raise ValueError("calibration_fraction doit etre comprise entre 0.5 et 1.")
    usable: list[tuple[Reading, float, list[float]]] = []
    for reading in sorted(readings, key=lambda item: item.timestamp):
        target = _power_kw(reading)
        values = [_predictor_value(reading, name) for name in predictors]
        if target is not None and all(value is not None for value in values):
            usable.append((reading, target, [float(value) for value in values]))
    minimum = max(20, 4 * (len(predictors) + 1))
    if len(usable) < minimum:
        raise ValueError(f"Baseline impossible: au moins {minimum} lignes completes requises.")
    split = int(len(usable) * calibration_fraction)
    split = min(max(split, len(predictors) + 2), len(usable) - 1)
    calibration = usable[:split]
    validation = usable[split:]
    design = [[1.0, *values] for _, _, values in calibration]
    targets = [target for _, target, _ in calibration]
    width = len(predictors) + 1
    xtx = [
        [sum(row[left] * row[right] for row in design) for right in range(width)]
        for left in range(width)
    ]
    # Regularisation numerique minuscule, sans effet materiel sur les coefficients.
    for index in range(width):
        xtx[index][index] += 1e-10
    xty = [sum(row[column] * target for row, target in zip(design, targets)) for column in range(width)]
    coefficients = _solve(xtx, xty)

    def predict(values: Sequence[float]) -> float:
        return coefficients[0] + sum(
            coefficient * value for coefficient, value in zip(coefficients[1:], values)
        )

    validation_observed = [target for _, target, _ in validation]
    validation_predicted = [predict(values) for _, _, values in validation]
    calibration_observed = targets
    calibration_predicted = [predict(values) for _, _, values in calibration]
    return {
        "kind": "linear",
        "target": "power_kw",
        "predictors": list(predictors),
        "coefficients": {
            "intercept": coefficients[0],
            **{name: value for name, value in zip(predictors, coefficients[1:])},
        },
        "calibration_rows": len(calibration),
        "validation_rows": len(validation),
        "calibration_start": calibration[0][0].timestamp.isoformat(),
        "calibration_end": calibration[-1][0].timestamp.isoformat(),
        "validation_start": validation[0][0].timestamp.isoformat(),
        "validation_end": validation[-1][0].timestamp.isoformat(),
        "calibration_metrics": _metrics(calibration_observed, calibration_predicted),
        "validation_metrics": _metrics(validation_observed, validation_predicted),
    }


def _activity_key(reading: Reading) -> str:
    if reading.production_active is True:
        return "active"
    if reading.production_active is False:
        return "inactive"
    return "unknown"


def fit_activity_baseline(
    readings: Sequence[Reading], *, calibration_fraction: float = 0.7
) -> dict[str, Any]:
    """Baseline robuste a deux regimes, calibree sur le passe."""

    if not 0.5 <= calibration_fraction < 1:
        raise ValueError("calibration_fraction doit etre comprise entre 0.5 et 1.")
    usable = [
        (reading, power)
        for reading in sorted(readings, key=lambda item: item.timestamp)
        if (power := _power_kw(reading)) is not None
    ]
    if len(usable) < 20:
        raise ValueError("Baseline active/inactive: au moins 20 lignes requises.")
    split = min(max(int(len(usable) * calibration_fraction), 10), len(usable) - 1)
    calibration, validation = usable[:split], usable[split:]
    buckets: dict[str, list[float]] = defaultdict(list)
    for reading, power in calibration:
        buckets[_activity_key(reading)].append(power)
    expected_by_activity = {key: median(values) for key, values in buckets.items()}
    fallback = median(power for _, power in calibration)
    observed = [power for _, power in validation]
    predicted = [
        expected_by_activity.get(_activity_key(reading), fallback)
        for reading, _ in validation
    ]
    return {
        "kind": "activity",
        "target": "power_kw",
        "expected_by_activity": expected_by_activity,
        "fallback_kw": fallback,
        "calibration_rows": len(calibration),
        "validation_rows": len(validation),
        "calibration_end": calibration[-1][0].timestamp.isoformat(),
        "validation_start": validation[0][0].timestamp.isoformat(),
        "validation_metrics": _metrics(observed, predicted),
    }


def _time_slot_key(reading: Reading, *, include_weekday: bool) -> str:
    activity = _activity_key(reading)
    operational = reading.operational_timestamp
    clock = f"{operational.hour:02d}:{operational.minute:02d}"
    return (
        f"{operational.weekday()}|{clock}|{activity}"
        if include_weekday
        else f"{clock}|{activity}"
    )


def fit_time_baseline(
    readings: Sequence[Reading], *, calibration_fraction: float = 0.7
) -> dict[str, Any]:
    """Baseline mediane par jour, heure et activite, avec fallback horaire."""

    if not 0.5 <= calibration_fraction < 1:
        raise ValueError("calibration_fraction doit etre comprise entre 0.5 et 1.")
    usable = [
        (reading, power)
        for reading in sorted(readings, key=lambda item: item.timestamp)
        if (power := _power_kw(reading)) is not None
    ]
    if len(usable) < 100:
        raise ValueError("Baseline temporelle: au moins 100 lignes requises.")
    split = min(max(int(len(usable) * calibration_fraction), 50), len(usable) - 1)
    calibration, validation = usable[:split], usable[split:]
    exact: dict[str, list[float]] = defaultdict(list)
    fallback_slots: dict[str, list[float]] = defaultdict(list)
    for reading, power in calibration:
        exact[_time_slot_key(reading, include_weekday=True)].append(power)
        fallback_slots[_time_slot_key(reading, include_weekday=False)].append(power)
    expected_by_slot = {key: median(values) for key, values in exact.items()}
    expected_by_clock = {key: median(values) for key, values in fallback_slots.items()}
    global_fallback = median(power for _, power in calibration)

    def expected(reading: Reading) -> float:
        return expected_by_slot.get(
            _time_slot_key(reading, include_weekday=True),
            expected_by_clock.get(
                _time_slot_key(reading, include_weekday=False), global_fallback
            ),
        )

    observed = [power for _, power in validation]
    predicted = [expected(reading) for reading, _ in validation]
    return {
        "kind": "time_slot",
        "target": "power_kw",
        "expected_by_slot": expected_by_slot,
        "expected_by_clock": expected_by_clock,
        "fallback_kw": global_fallback,
        "calibration_rows": len(calibration),
        "validation_rows": len(validation),
        "calibration_end": calibration[-1][0].timestamp.isoformat(),
        "validation_start": validation[0][0].timestamp.isoformat(),
        "validation_metrics": _metrics(observed, predicted),
    }


def fit_rolling_median_baseline(
    readings: Sequence[Reading], *, window_rows: int
) -> dict[str, Any]:
    """Predictions causales utilisant uniquement les `window_rows` mesures precedentes."""

    if window_rows < 3:
        raise ValueError("La fenetre glissante doit contenir au moins trois lignes.")
    usable = [
        (reading, power)
        for reading in sorted(readings, key=lambda item: item.timestamp)
        if (power := _power_kw(reading)) is not None
    ]
    if len(usable) <= window_rows:
        raise ValueError("La serie doit etre plus longue que la fenetre glissante.")
    observed: list[float] = []
    predicted: list[float] = []
    residuals = []
    for index in range(window_rows, len(usable)):
        expected = median(power for _, power in usable[index - window_rows:index])
        reading, actual = usable[index]
        observed.append(actual)
        predicted.append(expected)
        residuals.append(
            {
                "timestamp": reading.timestamp.isoformat(),
                "observed_kw": actual,
                "expected_kw": expected,
                "residual_kw": actual - expected,
                "interval_hours": reading.interval_hours,
            }
        )
    return {
        "kind": "rolling_median",
        "target": "power_kw",
        "window_rows": window_rows,
        "past_only": True,
        "validation_rows": len(observed),
        "validation_metrics": _metrics(observed, predicted),
        "residuals": residuals,
    }


def measure_linear_drift(
    points: Sequence[dict[str, Any]], *, value_key: str = "residual_kw"
) -> dict[str, Any]:
    """Mesure une pente temporelle; Codex decide si elle constitue une derive."""

    usable = sorted(
        (datetime.fromisoformat(str(item["timestamp"])), float(item[value_key]))
        for item in points
        if item.get("timestamp") is not None and item.get(value_key) is not None
    )
    if len(usable) < 3:
        raise ValueError("Une mesure de derive exige au moins trois points complets.")
    origin = usable[0][0]
    elapsed_days = [(timestamp - origin).total_seconds() / 86400.0 for timestamp, _ in usable]
    if elapsed_days[-1] <= 0:
        raise ValueError("La mesure de derive exige des timestamps distincts.")
    values = [value for _, value in usable]
    x_mean = sum(elapsed_days) / len(elapsed_days)
    y_mean = sum(values) / len(values)
    denominator = sum((value - x_mean) ** 2 for value in elapsed_days)
    slope = sum(
        (x - x_mean) * (y - y_mean) for x, y in zip(elapsed_days, values)
    ) / denominator
    intercept = y_mean - slope * x_mean
    predicted = [intercept + slope * value for value in elapsed_days]
    residual_sum = sum((actual - expected) ** 2 for actual, expected in zip(values, predicted))
    total_sum = sum((value - y_mean) ** 2 for value in values)
    return {
        "points": len(usable),
        "start": usable[0][0].isoformat(),
        "end": usable[-1][0].isoformat(),
        "slope_per_day": slope,
        "intercept": intercept,
        "r_squared": 1 - residual_sum / total_sum if total_sum > 0 else None,
        "decision": None,
    }


def compare_level_shift(
    before: Sequence[float], after: Sequence[float]
) -> dict[str, float | int | None]:
    """Compare deux regimes avec medianes et dispersions robustes."""

    if len(before) < 3 or len(after) < 3:
        raise ValueError("Un changement de niveau exige trois valeurs par regime.")
    before_values = [float(value) for value in before]
    after_values = [float(value) for value in after]
    before_median = median(before_values)
    after_median = median(after_values)
    delta = after_median - before_median
    return {
        "before_points": len(before_values),
        "after_points": len(after_values),
        "before_median": before_median,
        "after_median": after_median,
        "delta": delta,
        "delta_percent": 100 * delta / before_median if before_median else None,
        "before_mad": median(abs(value - before_median) for value in before_values),
        "after_mad": median(abs(value - after_median) for value in after_values),
        "decision": None,
    }


def calculate_residuals(
    readings: Sequence[Reading], model: dict[str, Any]
) -> list[dict[str, Any]]:
    kind = model.get("kind")
    if kind == "rolling_median":
        return list(model["residuals"])
    if kind not in {"linear", "activity", "time_slot"}:
        raise ValueError("Type de baseline non pris en charge.")
    residuals = []
    for reading in sorted(readings, key=lambda item: item.timestamp):
        observed = _power_kw(reading)
        if observed is None:
            continue
        if kind == "linear":
            predictors = model["predictors"]
            coefficients = model["coefficients"]
            values = [_predictor_value(reading, name) for name in predictors]
            if any(value is None for value in values):
                continue
            expected = coefficients["intercept"] + sum(
                coefficients[name] * float(value) for name, value in zip(predictors, values)
            )
        elif kind == "activity":
            expected = model["expected_by_activity"].get(
                _activity_key(reading), model["fallback_kw"]
            )
        else:
            expected = model["expected_by_slot"].get(
                _time_slot_key(reading, include_weekday=True),
                model["expected_by_clock"].get(
                    _time_slot_key(reading, include_weekday=False), model["fallback_kw"]
                ),
            )
        residuals.append(
            {
                "timestamp": reading.timestamp.isoformat(),
                "observed_kw": observed,
                "expected_kw": expected,
                "residual_kw": observed - expected,
                "interval_hours": reading.interval_hours,
            }
        )
    return residuals


def group_residual_events(
    residuals: Sequence[dict[str, Any]],
    *,
    threshold_kw: float,
    max_gap_minutes: float,
) -> list[dict[str, Any]]:
    if threshold_kw < 0 or max_gap_minutes <= 0:
        raise ValueError("Les seuils d'evenement doivent etre positifs.")
    candidates = [item for item in residuals if item["residual_kw"] > threshold_kw]
    groups: list[list[dict[str, Any]]] = []
    for item in candidates:
        timestamp = datetime.fromisoformat(item["timestamp"])
        if not groups:
            groups.append([item])
            continue
        previous = datetime.fromisoformat(groups[-1][-1]["timestamp"])
        if (timestamp - previous).total_seconds() <= max_gap_minutes * 60:
            groups[-1].append(item)
        else:
            groups.append([item])
    events = []
    for index, group in enumerate(groups, start=1):
        excess = sum(
            item["residual_kw"] * item["interval_hours"]
            for item in group
            if item["interval_hours"] is not None
        )
        events.append(
            {
                "event_id": f"E{index:04d}",
                "start": group[0]["timestamp"],
                "end": group[-1]["timestamp"],
                "points": len(group),
                "peak_residual_kw": max(item["residual_kw"] for item in group),
                "excess_energy_kwh": excess,
            }
        )
    return events


def calculate_excess_energy(
    observed_kw: Sequence[float], expected_kw: Sequence[float], interval_hours: Sequence[float]
) -> float:
    if not (len(observed_kw) == len(expected_kw) == len(interval_hours)):
        raise ValueError("Les series de surconsommation doivent avoir la meme longueur.")
    if any(hours <= 0 for hours in interval_hours):
        raise ValueError("Les durees d'intervalle doivent etre positives.")
    return sum(
        max(observed - expected, 0.0) * hours
        for observed, expected, hours in zip(observed_kw, expected_kw, interval_hours)
    )


def calculate_cost(energy_kwh: float, price_per_kwh: float) -> float:
    if energy_kwh < 0 or price_per_kwh < 0:
        raise ValueError("L'energie et le tarif doivent etre positifs.")
    return energy_kwh * price_per_kwh


def annualize_effect(
    *,
    observed_excess_energy_kwh: float,
    observed_occurrences: int,
    eligible_occurrences: int,
    observation_days: float,
    annual_eligible_occurrences: int,
    representative_period: bool,
    coverage_ratio: float,
    price_per_kwh: float | None = None,
    recoverable_fraction: float | None = None,
    minimum_occurrences: int = 3,
    minimum_observation_days: float = 28.0,
) -> dict[str, Any]:
    """Projette uniquement un effet recurrent suffisamment documente.

    L'energie projetee reste une surconsommation associee au signal. Elle ne
    devient pas une economie sans hypothese explicite de part recuperable.
    ``representative_period`` est un jugement documente par l'analyste, pas
    une propriete que le code peut deduire des seules mesures.
    """

    if observed_excess_energy_kwh < 0:
        raise ValueError("La surconsommation observee ne peut pas etre negative.")
    if observed_occurrences < 0 or eligible_occurrences <= 0:
        raise ValueError("Les nombres d'occurrences sont invalides.")
    if observed_occurrences > eligible_occurrences:
        raise ValueError("Les occurrences observees depassent les occasions eligibles.")
    if observed_occurrences == 0 and observed_excess_energy_kwh > 0:
        raise ValueError("Une energie positive exige au moins une occurrence observee.")
    if observation_days <= 0 or annual_eligible_occurrences <= 0:
        raise ValueError("La duree et les occasions annuelles doivent etre positives.")
    if not 0 <= coverage_ratio <= 1:
        raise ValueError("Le taux de couverture doit etre compris entre 0 et 1.")
    if minimum_occurrences < 2 or minimum_observation_days <= 0:
        raise ValueError("Les seuils minimaux d'annualisation sont invalides.")
    if price_per_kwh is not None and price_per_kwh < 0:
        raise ValueError("Le tarif ne peut pas etre negatif.")
    if recoverable_fraction is not None and not 0 <= recoverable_fraction <= 1:
        raise ValueError("La part recuperable doit etre comprise entre 0 et 1.")

    refusal_reasons = []
    if not representative_period:
        refusal_reasons.append("periode_non_documentee_comme_representative")
    if observation_days < minimum_observation_days:
        refusal_reasons.append("periode_d_observation_trop_courte")
    if observed_occurrences < minimum_occurrences:
        refusal_reasons.append("recurrence_insuffisante")
    if coverage_ratio < 0.90:
        refusal_reasons.append("couverture_des_donnees_insuffisante")
    if refusal_reasons:
        raise ValueError(
            "Annualisation refusee: " + ", ".join(refusal_reasons) + "."
        )

    recurrence_rate = observed_occurrences / eligible_occurrences
    mean_excess_per_occurrence = observed_excess_energy_kwh / observed_occurrences
    projected_occurrences = recurrence_rate * annual_eligible_occurrences
    projected_excess = mean_excess_per_occurrence * projected_occurrences
    associated_cost = (
        calculate_cost(projected_excess, price_per_kwh)
        if price_per_kwh is not None
        else None
    )
    recoverable_energy = (
        projected_excess * recoverable_fraction
        if recoverable_fraction is not None
        else None
    )
    return {
        "status": "scenario_not_guarantee",
        "recurrence_rate": recurrence_rate,
        "mean_excess_per_occurrence_kwh": mean_excess_per_occurrence,
        "projected_occurrences_per_year": projected_occurrences,
        "projected_excess_energy_kwh": projected_excess,
        "projected_associated_cost": associated_cost,
        "recoverable_fraction_assumption": recoverable_fraction,
        "projected_recoverable_energy_kwh": recoverable_energy,
        "projected_recoverable_cost": (
            calculate_cost(recoverable_energy, price_per_kwh)
            if recoverable_energy is not None and price_per_kwh is not None
            else None
        ),
        "assumptions": {
            "representative_period": representative_period,
            "observation_days": observation_days,
            "coverage_ratio": coverage_ratio,
            "observed_occurrences": observed_occurrences,
            "eligible_occurrences": eligible_occurrences,
            "annual_eligible_occurrences": annual_eligible_occurrences,
            "minimum_occurrences": minimum_occurrences,
            "minimum_observation_days": minimum_observation_days,
        },
        "limitations": [
            "La recurrence et l'impact moyen observes sont supposes stables sur l'annee.",
            "La projection ne prouve ni la causalite ni la part reellement recuperable.",
            "Aucun intervalle de confiance n'est fabrique sans modele statistique dedie.",
        ],
    }


def union_excess_energy(events: Sequence[dict[str, float]]) -> dict[str, float | int]:
    """Evite d'additionner deux estimations portant sur le meme intervalle.

    Chaque dictionnaire represente les kWh excedentaires d'un signal par timestamp.
    La valeur maximale par timestamp est retenue de maniere prudente.
    """

    naive_total = sum(sum(event.values()) for event in events)
    union: dict[str, float] = {}
    overlaps = 0
    for event in events:
        for timestamp, energy in event.items():
            if energy < 0:
                raise ValueError("Une surconsommation d'evenement ne peut pas etre negative.")
            if timestamp in union:
                overlaps += 1
                union[timestamp] = max(union[timestamp], energy)
            else:
                union[timestamp] = energy
    union_total = sum(union.values())
    return {
        "naive_total_kwh": naive_total,
        "deduplicated_total_kwh": union_total,
        "double_counted_kwh": naive_total - union_total,
        "overlapping_points": overlaps,
    }
