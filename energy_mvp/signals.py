from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from statistics import mean, median, pstdev
import math
from typing import Any, Sequence
from zoneinfo import ZoneInfo

from .models import LoadedData, Reading
from .toolbox import calculate_residuals, extract_period, fit_linear_baseline, fit_time_baseline, group_residual_events


def _trend(values: Sequence[float], days: Sequence[date] | None = None) -> tuple[float, float | None]:
    if len(values) < 2:
        return 0.0, None
    xs = [(day - days[0]).days for day in days] if days else list(range(len(values)))
    x_mean = mean(xs)
    y_mean = mean(values)
    denominator = sum((index - x_mean) ** 2 for index in xs)
    slope = sum(
        (index - x_mean) * (value - y_mean) for index, value in zip(xs, values)
    ) / denominator
    predicted = [y_mean + slope * (index - x_mean) for index in xs]
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


def _past_only_transient_groups(
    values_by_day: dict[date, float],
    *,
    threshold: float,
    minimum_history_points: int,
    minimum_event_points: int,
    maximum_gap_days: int,
) -> list[tuple[list[date], float]]:
    """Détecte un palier temporaire avec une référence figée composée du seul passé."""

    ordered = sorted(values_by_day)
    groups: list[tuple[list[date], float]] = []
    index = minimum_history_points
    while index < len(ordered):
        history = ordered[max(0, index - minimum_history_points):index]
        baseline = median(values_by_day[day] for day in history)
        if values_by_day[ordered[index]] <= baseline + threshold:
            index += 1
            continue
        group = [ordered[index]]
        cursor = index + 1
        while cursor < len(ordered):
            day = ordered[cursor]
            if (day - group[-1]).days > maximum_gap_days:
                break
            if values_by_day[day] <= baseline + threshold:
                break
            group.append(day)
            cursor += 1
        following = ordered[cursor:cursor + max(2, minimum_event_points)]
        recovered = bool(following) and median(
            values_by_day[day] for day in following
        ) <= baseline + threshold
        if len(group) >= minimum_event_points and recovered:
            groups.append((group, baseline))
            index = cursor + len(following)
        else:
            index += 1
    return groups


def _date_event(
    event_id: str,
    event_type: str,
    days: Sequence[date],
    score: float,
    *,
    site_timezone: str | None = None,
) -> dict[str, Any]:
    start = datetime.combine(days[0], datetime.min.time())
    end = datetime.combine(days[-1] + timedelta(days=1), datetime.min.time())
    if site_timezone:
        zone = ZoneInfo(site_timezone)
        start = start.replace(tzinfo=zone)
        end = end.replace(tzinfo=zone)
    return {
        "event_id": event_id,
        "type": event_type,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "score_kw": score,
        "status": "candidate_signal",
    }


def _internal_event_timestamp(value: datetime, site_timezone: str | None) -> str:
    if not site_timezone:
        return value.isoformat()
    return (
        value.replace(tzinfo=timezone.utc)
        .astimezone(ZoneInfo(site_timezone))
        .isoformat()
    )


def _fit_robust_reference(
    reference: Sequence[Reading], predictors: tuple[str, ...]
) -> dict[str, Any]:
    """Réajuste après retrait tracé d'une petite minorité de résidus extrêmes."""

    initial = fit_linear_baseline(reference, predictors=predictors, calibration_fraction=0.7)
    calibration_end = datetime.fromisoformat(initial["calibration_end"])
    training = [item for item in reference if item.timestamp <= calibration_end]
    residuals = calculate_residuals(training, initial)
    values = [float(item["residual_kw"]) for item in residuals]
    center = median(values)
    mad = median(abs(value - center) for value in values)
    robust_sigma = 1.4826 * mad
    cutoff = max(4.0, 4.0 * robust_sigma)
    retained_timestamps = {
        item["timestamp"] for item in residuals
        if abs(float(item["residual_kw"]) - center) <= cutoff
    }
    cleaned = [
        reading for reading in reference
        if reading.timestamp > calibration_end or reading.timestamp.isoformat() in retained_timestamps
    ]
    removed = len(reference) - len(cleaned)
    # Ne pas laisser un mauvais modèle supprimer une fraction importante du procédé.
    if removed <= 0 or removed > 0.20 * len(training):
        initial["robust_refit"] = False
        initial["robust_trimmed_rows"] = 0
        initial["initial_validation_metrics"] = initial["validation_metrics"]
        return initial
    refitted = fit_linear_baseline(cleaned, predictors=predictors, calibration_fraction=0.7,
                                   calibration_end=calibration_end)
    refitted["robust_refit"] = True
    refitted["validation_rows_never_trimmed"] = True
    refitted["robust_trimmed_rows"] = removed
    refitted["robust_cutoff_kw"] = cutoff
    refitted["initial_validation_metrics"] = initial["validation_metrics"]
    return refitted


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
    first_local_date = readings[0].operational_timestamp.date()
    last_local_date = readings[-1].operational_timestamp.date()
    total_days = (last_local_date - first_local_date).days + 1
    # Trente jours couvrent plusieurs semaines et davantage de régimes produit qu'une
    # courte référence. La période reste strictement antérieure aux détections.
    reference_days = min(total_days - 1, max(30, min(45, total_days // 3)))
    reference_start = readings[0].timestamp
    reference_end = reference_start + timedelta(days=reference_days)
    if data.site_timezone:
        local_end = datetime.combine(first_local_date + timedelta(days=reference_days), datetime.min.time(), tzinfo=ZoneInfo(data.site_timezone))
        reference_end = local_end.astimezone(timezone.utc).replace(tzinfo=None)
    reference_end_local_date = first_local_date + timedelta(days=reference_days)
    reference = extract_period(readings, reference_start, reference_end)
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
    base_predictors: list[str] = []
    if completeness["production"] >= 0.90:
        base_predictors.append("production")
    if completeness["production_active"] >= 0.90:
        base_predictors.append("production_active")
    if completeness["product_type"] >= 0.90:
        base_predictors.append("product_type")
        if completeness["production"] >= 0.90:
            base_predictors.append("production_by_product")
    temperature_options: dict[str, tuple[str, ...]] = {"none": ()}
    if completeness["outside_temperature_c"] >= 0.90:
        temperature_options.update({
            "linear": ("outside_temperature_c",),
            "degree_18": ("heating_degree_c", "cooling_degree_c"),
            "degree_10_20": ("heating_degree_10_c", "cooling_degree_20_c"),
        })
    baseline_candidates = {}
    for name, temperature_predictors in temperature_options.items():
        candidate_predictors = tuple(base_predictors) + temperature_predictors
        try:
            baseline_candidates[name] = _fit_robust_reference(
                reference, candidate_predictors
            )
        except ValueError:
            continue
    # A meter-only baseline must compare recurring clock/day regimes, not flatten them.
    if not base_predictors:
        try:
            temporal = fit_time_baseline(reference)
            temporal["predictors"] = []
            baseline_candidates["time_slot"] = temporal
        except ValueError:
            pass
    baseline_candidates = {name: candidate for name, candidate in baseline_candidates.items()
        if candidate.get("validation_coverage_ratio", 1.0) >= .9}
    if not baseline_candidates:
        raise ValueError("Aucune baseline candidate n'a pu être ajustée.")
    best_rmse = min(
        float(candidate["validation_metrics"]["rmse"])
        for candidate in baseline_candidates.values()
    )
    near_best = [
        (name, candidate)
        for name, candidate in baseline_candidates.items()
        if float(candidate["validation_metrics"]["rmse"]) <= best_rmse * 1.02
    ]
    # Une amélioration marginale ne justifie pas un modèle plus complexe et plus
    # extrapolant. Cette règle de parcimonie limite les corrélations météo fortuites.
    selected_baseline_name, model = min(
        near_best,
        key=lambda item: (len(item[1]["predictors"]), float(item[1]["validation_metrics"]["rmse"])),
    )
    predictors = list(model["predictors"])
    residuals = calculate_residuals(readings, model)
    reference_residuals = calculate_residuals(reference, model)
    reference_values = [float(item["residual_kw"]) for item in reference_residuals]
    residual_center = median(reference_values)
    residual_mad = median(abs(value - residual_center) for value in reference_values)
    robust_residual_sigma = 1.4826 * residual_mad
    by_timestamp = {item.timestamp.isoformat(): item for item in readings}
    daily_all: dict[date, list[tuple[float, float]]] = defaultdict(list)
    daily_inactive: dict[date, list[float]] = defaultdict(list)
    daily_active: dict[date, list[float]] = defaultdict(list)
    daily_night: dict[date, list[float]] = defaultdict(list)
    daily_weekend_day: dict[date, list[float]] = defaultdict(list)
    for residual in residuals:
        reading = by_timestamp[residual["timestamp"]]
        value = residual["residual_kw"]
        operational = reading.operational_timestamp
        day = operational.date()
        daily_all[day].append((value, reading.interval_hours or 0.0))
        activity = reading.production_active
        if activity is None and reading.production is not None:
            activity = reading.production > 0
        if activity is True:
            daily_active[day].append(value)
        elif activity is False:
            daily_inactive[day].append(value)
        if operational.hour >= 22 or operational.hour < 6:
            daily_night[day].append(value)
        if operational.weekday() >= 5 and 8 <= operational.hour < 18:
            daily_weekend_day[day].append(value)
    inactive_mean = {day: mean(values) for day, values in daily_inactive.items()}
    active_mean = {day: mean(values) for day, values in daily_active.items()}
    night_mean = {day: mean(values) for day, values in daily_night.items()}
    weekend_mean = {day: mean(values) for day, values in daily_weekend_day.items()}
    reference_dates = [day for day in inactive_mean if day < reference_end_local_date]
    reference_inactive_values = [inactive_mean[day] for day in reference_dates]
    reference_inactive = (
        median(reference_inactive_values) if reference_inactive_values else None
    )
    reference_night_values = [
        value for day, value in night_mean.items() if day < reference_end_local_date
    ]
    reference_night = median(reference_night_values) if reference_night_values else None
    reference_weekend_values = [
        value for day, value in weekend_mean.items() if day < reference_end_local_date
    ]
    reference_weekend = (
        median(reference_weekend_values) if reference_weekend_values else None
    )
    validation_mae = model["validation_metrics"]["mae"]
    structured_threshold = max(4.0, 2.5 * robust_residual_sigma)
    events: list[dict[str, Any]] = []
    counter = 1

    # Signal nocturne borne : une hausse qui revient au niveau de reference avant la fin.
    night_groups = _past_only_transient_groups(
        night_mean,
        threshold=structured_threshold,
        minimum_history_points=14,
        minimum_event_points=3,
        maximum_gap_days=1,
    ) if reference_night is not None else []
    for group, frozen_baseline in night_groups:
        if (last_local_date - group[-1]).days < 10:
            continue
        events.append(
            _date_event(
                f"C{counter:03d}", "night_anomaly", group,
                mean(night_mean[day] for day in group) - frozen_baseline,
                site_timezone=data.site_timezone,
            )
        )
        counter += 1

    high_weekends = (
        [
            day for day, value in weekend_mean.items()
            if day >= reference_end_local_date
            and value > reference_weekend + structured_threshold
        ]
        if reference_weekend is not None
        else []
    )
    for group in _group_dates(high_weekends, maximum_gap_days=8):
        if len(group) < 2 or (last_local_date - group[-1]).days < 10:
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
                    site_timezone=data.site_timezone,
                )
            )
            counter += 1

    active_adjusted = {
        day: active_mean[day] - inactive_mean[day]
        for day in active_mean
        if day in inactive_mean
    }
    reference_adjusted_values = [
        value for day, value in active_adjusted.items() if day < reference_end_local_date
    ]
    reference_adjusted = (
        median(reference_adjusted_values) if reference_adjusted_values else None
    )
    high_efficiency = [
        day for day, value in active_adjusted.items()
        if day >= reference_end_local_date
        and reference_adjusted is not None
        and value > reference_adjusted + structured_threshold
    ]
    for group in _group_dates(high_efficiency, maximum_gap_days=3):
        if len(group) < 4 or (last_local_date - group[-1]).days < 7:
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
                    site_timezone=data.site_timezone,
                )
            )
            counter += 1

    spike_threshold = max(30.0, 8.0 * robust_residual_sigma)
    point_events = group_residual_events(
        residuals, threshold_kw=spike_threshold, max_gap_minutes=frequency
    )
    point_dates = {
        datetime.fromisoformat(item["start"]).date() for item in point_events
        if item["points"] >= 2
    }
    isolated_peak_threshold = spike_threshold
    if len(point_dates) >= 3:
        # Une pluie de dépassements sur plusieurs jours décrit généralement un nouveau
        # régime, pas des dizaines de pics ponctuels indépendants. Ne conserver alors
        # que les événements réellement extrêmes pour éviter cette fragmentation.
        peaks = [float(item["peak_residual_kw"]) for item in point_events]
        peak_median = median(peaks)
        peak_mad = median(abs(value - peak_median) for value in peaks)
        isolated_peak_threshold = max(
            2.0 * spike_threshold,
            peak_median + 6.0 * 1.4826 * peak_mad,
        )
    for point_event in point_events:
        if point_event["points"] < 2:
            continue
        if point_event["peak_residual_kw"] < isolated_peak_threshold:
            continue
        internal_start = datetime.fromisoformat(point_event["start"])
        internal_end = datetime.fromisoformat(point_event["end"]) + timedelta(
            minutes=frequency
        )
        events.append(
            {
                "event_id": f"C{counter:03d}",
                "type": "point_spike",
                "start": _internal_event_timestamp(internal_start, data.site_timezone),
                "end": _internal_event_timestamp(internal_end, data.site_timezone),
                "score_kw": point_event["peak_residual_kw"],
                "status": "candidate_signal",
            }
        )
        counter += 1

    # Exclude incomplete calendar days (including unsupported categorical predictions).
    def expected_day_hours(day: date) -> float:
        if not data.site_timezone:
            return 24.0
        zone = ZoneInfo(data.site_timezone)
        start = datetime.combine(day, datetime.min.time(), tzinfo=zone)
        end = datetime.combine(day + timedelta(days=1), datetime.min.time(), tzinfo=zone)
        return (end.astimezone(timezone.utc) - start.astimezone(timezone.utc)).total_seconds() / 3600
    complete_days = {day for day, points in daily_all.items()
        if sum(hours for _, hours in points) >= .9 * expected_day_hours(day)}
    aggregate_mean = {day: sum(value * hours for value, hours in points) / sum(hours for _, hours in points)
        for day, points in daily_all.items() if day in complete_days}
    regime_series = {day: value for day, value in (inactive_mean or aggregate_mean).items()
                     if day in complete_days}
    regime_scope = "inactive" if inactive_mean else "aggregate"
    reference_daily = [value for day, value in regime_series.items() if day < reference_end_local_date]
    regime_events = []
    if len(reference_daily) >= 7:
        baseline_daily = median(reference_daily)
        daily_sigma = 1.4826 * median(abs(value - baseline_daily) for value in reference_daily)
        reference_power = median(item.power_kw if item.power_kw is not None else
                                 item.energy_kwh / item.interval_hours for item in reference)
        regime_threshold = max(.5, .05 * reference_power, 3 * daily_sigma)
        ordered_days = sorted(day for day in regime_series if day >= reference_end_local_date)
        window = min(30, max(14, total_days // 4))
        drift_candidates = []
        for start_index in range(0, len(ordered_days) - window + 1):
            dates = ordered_days[start_index:start_index + window]
            if (dates[-1] - dates[0]).days > len(dates) * 1.2:
                continue
            values = [regime_series[day] for day in dates]
            slope, r_squared = _trend(values, dates)
            linear_error = (1 - (r_squared or 0)) * sum((v - mean(values)) ** 2 for v in values)
            step_error = min(sum((v - mean(values[:cut])) ** 2 for v in values[:cut]) +
                             sum((v - mean(values[cut:])) ** 2 for v in values[cut:])
                             for cut in range(3, len(values)-2))
            # A step is not a drift simply because a fitted line has a large R².
            if (slope > max(.02, regime_threshold / window) and r_squared is not None
                    and r_squared >= .7 and linear_error < .8 * max(step_error, 1e-12)):
                drift_candidates.append((slope * r_squared, slope, r_squared, dates))
        if drift_candidates:
            _, slope, r_squared, dates = max(drift_candidates, key=lambda item: item[0])
            event = _date_event(f"C{counter:03d}", "progressive_drift", dates, slope,
                                site_timezone=data.site_timezone)
            event.update({"r_squared": r_squared, "scope": regime_scope,
                          "shape_evidence": "linear_fits_better_than_single_step",
                          "score_unit": "kW/day"})
            regime_events.append(event)
            counter += 1
        # A stable elevated tail is observable without declaring any machine inactive.
        # Index zero already means the end of the reference; never skip reference_days twice.
        minimum_tail = 14
        for start_index in range(0, len(ordered_days) - minimum_tail + 1):
            dates = ordered_days[start_index:]
            if (dates[-1] - dates[0]).days > len(dates) * 1.2:
                continue
            values = [regime_series[day] for day in dates]
            slope, _ = _trend(values, dates)
            level = mean(values) - baseline_daily
            spread_limit = max(.25, 2.5 * daily_sigma)
            slope_limit = max(.01, 2 * daily_sigma / max(1, (dates[-1] - dates[0]).days))
            stable_halves = abs(median(values[:7]) - median(values[-7:])) <= max(.5, 2 * daily_sigma)
            if abs(level) > regime_threshold and abs(slope) < slope_limit and pstdev(values) < spread_limit and stable_halves:
                event = _date_event(f"C{counter:03d}", "permanent_baseline_shift", dates, level,
                                    site_timezone=data.site_timezone)
                event.update({"scope": regime_scope, "direction": "increase" if level > 0 else "decrease",
                              "slope_kw_per_day": slope,
                              "persistence": "observed_until_dataset_end_not_a_forecast"})
                regime_events.append(event)
                counter += 1
                break
        # Meter-only temporary changes need a channel distinct from the fixed night clock.
        if not inactive_mean:
            for dates, frozen in _past_only_transient_groups(
                aggregate_mean, threshold=regime_threshold, minimum_history_points=14,
                minimum_event_points=3, maximum_gap_days=1):
                if dates[0] < reference_end_local_date:
                    continue
                prior = sorted(day for day in aggregate_mean if day < dates[0])[-14:]
                prior_slope, _ = _trend([aggregate_mean[day] for day in prior], prior)
                group_slope, _ = _trend([aggregate_mean[day] for day in dates], dates)
                if abs(prior_slope) * len(prior) > regime_threshold or abs(group_slope) * len(dates) > regime_threshold:
                    continue
                event = _date_event(f"C{counter:03d}", "temporary_level_shift", dates,
                                    mean(aggregate_mean[day] for day in dates)-frozen,
                                    site_timezone=data.site_timezone)
                event["scope"] = "aggregate"
                regime_events.append(event)
                counter += 1
    else:
        regime_threshold = None

    # Preserve overlapping observations as evidence, but don't count the same common-mode
    # change as a new night/weekend event. Distinct inactive-only changes remain separate.
    consolidated = []
    for event in events:
        related = None
        if event["type"] in {"night_anomaly", "weekend_anomaly"}:
            start = datetime.fromisoformat(event["start"]).date()
            end = datetime.fromisoformat(event["end"]).date()
            for regime in regime_events:
                rs = datetime.fromisoformat(regime["start"]).date()
                re = datetime.fromisoformat(regime["end"]).date()
                overlap = max(0, (min(end,re)-max(start,rs)).days)
                if overlap / max(1,(end-start).days) < .8:
                    continue
                if regime_scope == "aggregate":
                    related = regime
                else:
                    active_ref = [v for d,v in active_mean.items() if d < reference_end_local_date]
                    active_event = [v for d,v in active_mean.items() if start <= d < end]
                    inactive_event = [v for d,v in inactive_mean.items() if start <= d < end]
                    if active_ref and active_event and inactive_event:
                        a = mean(active_event)-median(active_ref)
                        i = mean(inactive_event)-baseline_daily
                        if abs(a-i) <= max(1., .25*abs(i)):
                            related = regime
                if related is not None:
                    break
        if related is None:
            consolidated.append(event)
        else:
            related.setdefault("related_candidate_evidence", []).append(event)
    events = consolidated + regime_events
    unsupported_rows = len(readings) - len(residuals)

    return {
        "status": "candidate_signals_only",
        "regime_threshold_kw": regime_threshold,
        "regime_scope": regime_scope,
        "prediction_coverage": {"supported_rows": len(residuals), "unsupported_rows": unsupported_rows,
            "ratio": len(residuals)/len(readings),
            "policy": "unsupported_rows_are_not_zero_residuals; investigate_missing_or_new_categories"},
        "excluded_incomplete_days": sorted(day.isoformat() for day in daily_all if day not in complete_days),
        "claim_boundary": "aggregate observations only; no cause or recoverable saving",
        "reference_days": reference_days,
        "structured_threshold_kw": structured_threshold,
        "spike_threshold_kw": spike_threshold,
        "isolated_peak_threshold_kw": isolated_peak_threshold,
        "threshold_method": "reference_residual_median_absolute_deviation",
        "reference_robust_residual_sigma_kw": robust_residual_sigma,
        "predictors_used": predictors,
        "selected_baseline": selected_baseline_name,
        "baseline_candidate_metrics": {
            name: candidate["validation_metrics"]
            for name, candidate in baseline_candidates.items()
        },
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
