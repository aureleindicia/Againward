from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from statistics import mean, pstdev
from typing import Any, Sequence

from .models import LoadedData, Reading
from .toolbox import calculate_residuals, extract_period, fit_linear_baseline, group_residual_events


def _trend(values: Sequence[float]) -> tuple[float, float | None]:
    if len(values) < 2:
        return 0.0, None
    x_mean = (len(values) - 1) / 2
    y_mean = mean(values)
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    slope = sum(
        (index - x_mean) * (value - y_mean) for index, value in enumerate(values)
    ) / denominator
    predicted = [y_mean + slope * (index - x_mean) for index in range(len(values))]
    residual_sum = sum((value - expected) ** 2 for value, expected in zip(values, predicted))
    total_sum = sum((value - y_mean) ** 2 for value in values)
    return slope, 1 - residual_sum / total_sum if total_sum > 0 else None


def _group_dates(days: Sequence[date], *, maximum_gap_days: int) -> list[list[date]]:
    groups: list[list[date]] = []
    for day in sorted(set(days)):
        if not groups or (day - groups[-1][-1]).days > maximum_gap_days:
            groups.append([day])
        else:
            groups[-1].append(day)
    return groups


def _date_event(
    event_id: str, event_type: str, days: Sequence[date], score: float
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "type": event_type,
        "start": datetime.combine(days[0], datetime.min.time()).isoformat(),
        "end": datetime.combine(days[-1] + timedelta(days=1), datetime.min.time()).isoformat(),
        "score_kw": score,
        "status": "candidate_signal",
    }


def detect_candidate_events(data: LoadedData) -> dict[str, Any]:
    """Produit des signaux de depart generiques ; aucune opportunite n'est confirmee ici."""

    readings = data.readings
    if not readings or readings[-1].timestamp - readings[0].timestamp < timedelta(days=29):
        raise ValueError("La detection multi-evenements exige au moins trente jours de donnees.")
    frequency = data.quality.inferred_frequency_minutes
    if frequency is None or frequency > 60:
        raise ValueError(
            "La detection multi-evenements exige une frequence connue d'au plus 60 minutes."
        )
    if data.quality.frequency_change_count:
        raise ValueError(
            "La detection multi-evenements est desactivee en presence de changements "
            "durables de frequence. Segmentez d'abord les regimes temporels."
        )
    first_day = readings[0].timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    last_day = readings[-1].timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
    total_days = (last_day - first_day).days + 1
    reference_days = max(14, min(30, total_days // 6))
    reference_end = first_day + timedelta(days=reference_days)
    reference = extract_period(readings, first_day, reference_end)
    completeness = {
        "production": sum(item.production is not None for item in readings) / len(readings),
        "outside_temperature_c": sum(
            item.outside_temperature_c is not None for item in readings
        ) / len(readings),
        "production_active": sum(
            item.production_active is not None for item in readings
        ) / len(readings),
        "product_type": sum(item.product_type is not None for item in readings) / len(readings),
    }
    predictors: list[str] = []
    if completeness["production"] >= 0.90:
        predictors.append("production")
    if completeness["outside_temperature_c"] >= 0.90:
        predictors.append("outside_temperature_c")
    if completeness["production_active"] >= 0.90:
        predictors.append("production_active")
    if completeness["product_type"] >= 0.90:
        predictors.append("product_type_b")
        if completeness["production"] >= 0.90:
            predictors.append("production_product_b")
    model = fit_linear_baseline(
        reference, predictors=tuple(predictors), calibration_fraction=0.7
    )
    residuals = calculate_residuals(readings, model)
    by_timestamp = {item.timestamp.isoformat(): item for item in readings}
    daily_inactive: dict[date, list[float]] = defaultdict(list)
    daily_active: dict[date, list[float]] = defaultdict(list)
    daily_night: dict[date, list[float]] = defaultdict(list)
    daily_weekend_day: dict[date, list[float]] = defaultdict(list)
    for residual in residuals:
        reading = by_timestamp[residual["timestamp"]]
        value = residual["residual_kw"]
        day = reading.timestamp.date()
        activity = reading.production_active
        if activity is None and reading.production is not None:
            activity = reading.production > 0
        if activity is True:
            daily_active[day].append(value)
        elif activity is False:
            daily_inactive[day].append(value)
        if reading.timestamp.hour >= 22 or reading.timestamp.hour < 6:
            daily_night[day].append(value)
        if reading.timestamp.weekday() >= 5 and 8 <= reading.timestamp.hour < 18:
            daily_weekend_day[day].append(value)
    inactive_mean = {day: mean(values) for day, values in daily_inactive.items()}
    active_mean = {day: mean(values) for day, values in daily_active.items()}
    night_mean = {day: mean(values) for day, values in daily_night.items()}
    weekend_mean = {day: mean(values) for day, values in daily_weekend_day.items()}
    reference_dates = [day for day in inactive_mean if day < reference_end.date()]
    reference_inactive_values = [inactive_mean[day] for day in reference_dates]
    reference_inactive = (
        mean(reference_inactive_values) if reference_inactive_values else None
    )
    reference_night_values = [
        value for day, value in night_mean.items() if day < reference_end.date()
    ]
    reference_night = mean(reference_night_values) if reference_night_values else None
    reference_weekend_values = [
        value for day, value in weekend_mean.items() if day < reference_end.date()
    ]
    reference_weekend = (
        mean(reference_weekend_values) if reference_weekend_values else None
    )
    validation_mae = model["validation_metrics"]["mae"]
    structured_threshold = max(4.0, 2.0 * validation_mae)
    events: list[dict[str, Any]] = []
    counter = 1

    # Signal nocturne borne : une hausse qui revient au niveau de reference avant la fin.
    high_nights = (
        [
            day for day, value in night_mean.items()
            if value > reference_night + structured_threshold
        ]
        if reference_night is not None
        else []
    )
    for group in _group_dates(high_nights, maximum_gap_days=1):
        if len(group) < 3 or (last_day.date() - group[-1]).days < 10:
            continue
        following = [
            night_mean[day]
            for day in night_mean
            if group[-1] < day <= group[-1] + timedelta(days=7)
        ]
        if following and mean(following) < reference_night + structured_threshold:
            events.append(
                _date_event(
                    f"C{counter:03d}", "night_anomaly", group,
                    mean(night_mean[day] for day in group) - reference_night,
                )
            )
            counter += 1

    high_weekends = (
        [
            day for day, value in weekend_mean.items()
            if value > reference_weekend + structured_threshold
        ]
        if reference_weekend is not None
        else []
    )
    for group in _group_dates(high_weekends, maximum_gap_days=8):
        if len(group) < 2 or (last_day.date() - group[-1]).days < 10:
            continue
        following = [
            weekend_mean[day]
            for day in weekend_mean
            if group[-1] < day <= group[-1] + timedelta(days=14)
        ]
        if following and mean(following) < reference_weekend + structured_threshold:
            events.append(
                _date_event(
                    f"C{counter:03d}", "weekend_anomaly", group,
                    mean(weekend_mean[day] for day in group) - reference_weekend,
                )
            )
            counter += 1

    active_adjusted = {
        day: active_mean[day] - inactive_mean[day]
        for day in active_mean
        if day in inactive_mean
    }
    reference_adjusted_values = [
        value for day, value in active_adjusted.items() if day < reference_end.date()
    ]
    reference_adjusted = (
        mean(reference_adjusted_values) if reference_adjusted_values else None
    )
    high_efficiency = [
        day for day, value in active_adjusted.items()
        if reference_adjusted is not None
        and value > reference_adjusted + structured_threshold
    ]
    for group in _group_dates(high_efficiency, maximum_gap_days=3):
        if len(group) < 4 or (last_day.date() - group[-1]).days < 7:
            continue
        following = [
            active_adjusted[day]
            for day in active_adjusted
            if group[-1] < day <= group[-1] + timedelta(days=10)
        ]
        if following and mean(following) < reference_adjusted + structured_threshold:
            events.append(
                _date_event(
                    f"C{counter:03d}", "efficiency_drop", group,
                    mean(active_adjusted[day] for day in group) - float(reference_adjusted),
                )
            )
            counter += 1

    spike_threshold = max(30.0, 6.0 * model["validation_metrics"]["rmse"])
    for point_event in group_residual_events(
        residuals, threshold_kw=spike_threshold, max_gap_minutes=frequency
    ):
        if point_event["points"] < 2:
            continue
        end = datetime.fromisoformat(point_event["end"]) + timedelta(
            minutes=frequency
        )
        events.append(
            {
                "event_id": f"C{counter:03d}",
                "type": "point_spike",
                "start": point_event["start"],
                "end": end.isoformat(),
                "score_kw": point_event["peak_residual_kw"],
                "status": "candidate_signal",
            }
        )
        counter += 1

    ordered_days = sorted(inactive_mean)
    window = min(30, max(14, total_days // 4))
    drift_candidates = []
    for start_index in range(0, len(ordered_days) - window + 1):
        dates = ordered_days[start_index:start_index + window]
        values = [inactive_mean[day] for day in dates]
        slope, r_squared = _trend(values)
        if slope > 0.15 and r_squared is not None and r_squared >= 0.7:
            drift_candidates.append((slope * r_squared, slope, r_squared, dates))
    if drift_candidates:
        _, slope, r_squared, dates = max(drift_candidates, key=lambda item: item[0])
        event = _date_event(f"C{counter:03d}", "progressive_drift", dates, slope)
        event["r_squared"] = r_squared
        events.append(event)
        counter += 1

    tail_candidates = []
    minimum_tail = max(14, total_days // 6)
    first_tail_index = max(reference_days, len(ordered_days) - 45)
    for start_index in range(first_tail_index, len(ordered_days) - minimum_tail + 1):
        dates = ordered_days[start_index:]
        values = [inactive_mean[day] for day in dates]
        slope, _ = _trend(values)
        if reference_inactive is None:
            continue
        level = mean(values) - reference_inactive
        deviation = pstdev(values)
        if level > structured_threshold and abs(slope) < 0.05 and deviation < 2.0:
            tail_candidates.append((deviation + abs(slope), dates, level, slope))
    if tail_candidates:
        _, dates, level, slope = min(tail_candidates, key=lambda item: item[0])
        event = _date_event(f"C{counter:03d}", "permanent_baseline_shift", dates, level)
        event["slope_kw_per_day"] = slope
        events.append(event)

    return {
        "status": "candidate_signals_only",
        "reference_days": reference_days,
        "structured_threshold_kw": structured_threshold,
        "spike_threshold_kw": spike_threshold,
        "predictors_used": predictors,
        "context_completeness": completeness,
        "disabled_signal_families": [
            name
            for name, enabled in {
                "inactive_drift": bool(inactive_mean),
                "efficiency": bool(active_adjusted),
                "night": reference_night is not None,
                "weekend": reference_weekend is not None,
            }.items()
            if not enabled
        ],
        "baseline": model,
        "events": sorted(events, key=lambda item: (item["start"], item["type"])),
    }
