from __future__ import annotations

import csv
import json
import math
import statistics
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Sequence
from zoneinfo import ZoneInfo

from .signal_intelligence import (
    BENCHMARK_PROFILE,
    SCHEMA_VERSION,
    SignalBenchmarkError,
    aggregate_scorecards,
    finalize_signal_run,
    prepare_signal_run,
    score_signal_run,
    validate_signal_case,
)


BASELINE_VERSION = "detection-and-motif-v2"
DETECTION_METHODS = ("unconditional", "production", "production_temperature")
SIGNATURE_METHODS = ("magnitude", "pq", "morphology")
METHOD_TAGS = {
    "unconditional": "u",
    "production": "p",
    "production_temperature": "pt",
    "magnitude": "mag",
    "pq": "pq",
    "morphology": "morph",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def _median(values: Iterable[float]) -> float:
    materialized = list(values)
    return statistics.median(materialized) if materialized else 0.0


def _solve_ridge(features: Sequence[Sequence[float]], values: Sequence[float]) -> list[float]:
    width = len(features[0])
    matrix = [[0.0 for _ in range(width + 1)] for _ in range(width)]
    for row, value in zip(features, values):
        for left in range(width):
            matrix[left][-1] += row[left] * value
            for right in range(width):
                matrix[left][right] += row[left] * row[right]
    for index in range(1, width):
        matrix[index][index] += 1e-6
    for pivot in range(width):
        selected = max(range(pivot, width), key=lambda row: abs(matrix[row][pivot]))
        matrix[pivot], matrix[selected] = matrix[selected], matrix[pivot]
        divisor = matrix[pivot][pivot]
        if abs(divisor) < 1e-12:
            continue
        matrix[pivot] = [value / divisor for value in matrix[pivot]]
        for row in range(width):
            if row == pivot:
                continue
            factor = matrix[row][pivot]
            matrix[row] = [
                current - factor * reference
                for current, reference in zip(matrix[row], matrix[pivot])
            ]
    return [matrix[index][-1] for index in range(width)]


def _daily_detection(pack: Path, method: str = "production_temperature") -> dict[str, Any]:
    if method not in DETECTION_METHODS:
        raise ValueError(f"Méthode de détection inconnue: {method}")
    operations = _read_csv(pack / "04_daily_operations.csv")
    operation_by_date = {row["date"]: row for row in operations}
    energy_rows = _read_csv(pack / "05_aggregate_energy_15min.csv")
    daily_energy: dict[str, float] = defaultdict(float)
    timestamps = []
    for row in energy_rows:
        instant = datetime.fromisoformat(row["timestamp"])
        timestamps.append(instant)
        daily_energy[instant.date().isoformat()] += float(row["energy_kwh"])
    dates = sorted(set(operation_by_date) & set(daily_energy))
    training_dates = dates[: min(10, max(5, len(dates) // 3))]
    output_scale = max(1.0, _median(
        float(operation_by_date[date]["output_units"])
        for date in training_dates
        if float(operation_by_date[date]["output_units"]) > 0
    ))
    temperature_scale = 10.0

    def vector(date: str) -> list[float]:
        row = operation_by_date[date]
        values = [1.0]
        if method in {"production", "production_temperature"}:
            values.extend([
                float(row["output_units"]) / output_scale,
                1.0 if row["operating_day"] == "True" else 0.0,
            ])
        if method == "production_temperature":
            values.append(float(row["outside_temperature_c"]) / temperature_scale)
        return values

    coefficients = _solve_ridge(
        [vector(date) for date in training_dates],
        [daily_energy[date] for date in training_dates],
    )
    expected = {
        date: sum(value * coefficient for value, coefficient in zip(vector(date), coefficients))
        for date in dates
    }
    residuals = {date: daily_energy[date] - expected[date] for date in dates}
    training_residuals = [residuals[date] for date in training_dates]
    centre = _median(training_residuals)
    mad = _median(abs(value - centre) for value in training_residuals)
    scale = max(1.0, 1.4826 * mad, 0.01 * _median(daily_energy[date] for date in training_dates))

    products = {operation_by_date[date]["product_family"] for date in training_dates}
    training_outputs = [float(operation_by_date[date]["output_units"]) for date in training_dates]
    training_temperatures = [float(operation_by_date[date]["outside_temperature_c"]) for date in training_dates]
    maximum_output = max(training_outputs)
    minimum_temperature = min(training_temperatures)
    maximum_temperature = max(training_temperatures)
    supported = {}
    support_reasons: dict[str, list[str]] = {}
    for date in dates:
        row = operation_by_date[date]
        reasons = []
        if method != "unconditional" and row["product_family"] not in products:
            reasons.append("unseen_product_family")
        output = float(row["output_units"])
        if method != "unconditional" and maximum_output > 0 and output > maximum_output * 1.2:
            reasons.append("output_extrapolation")
        temperature = float(row["outside_temperature_c"])
        if method == "production_temperature" and (
            temperature < minimum_temperature - 2.0 or temperature > maximum_temperature + 2.0
        ):
            reasons.append("temperature_extrapolation")
        supported[date] = not reasons
        support_reasons[date] = reasons

    best: dict[str, Any] | None = None
    for boundary in range(len(training_dates), max(len(training_dates), len(dates) - 4)):
        before_dates = [date for date in dates[max(0, boundary - 10):boundary] if supported[date]]
        after_dates = [date for date in dates[boundary:min(len(dates), boundary + 10)] if supported[date]]
        if len(before_dates) < 4 or len(after_dates) < 4:
            continue
        before = _median(residuals[date] for date in before_dates)
        after = _median(residuals[date] for date in after_dates)
        effect = after - before
        recurrence = sum(residuals[date] - before > 2.0 * scale for date in after_dates) / len(after_dates)
        score = max(0.0, effect / scale) * (0.5 + 0.5 * recurrence)
        candidate = {
            "boundary_index": boundary,
            "onset": datetime.fromisoformat(dates[boundary]).replace(
                tzinfo=ZoneInfo("Europe/Paris")
            ).isoformat(),
            "effect_kwh_per_day": effect,
            "score": score,
            "recurrence": recurrence,
            "before_residual_kwh": before,
            "after_residual_kwh": after,
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate

    if best is None:
        probability = 0.25
        onset = None
        excess = None
        recurrence = 0.0
        effect = 0.0
    else:
        probability = 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, best["score"] - 3.0))))
        onset = best["onset"]
        recurrence = float(best["recurrence"])
        effect = float(best["effect_kwh_per_day"])
        post_dates = dates[int(best["boundary_index"]):]
        unsupported_share = sum(not supported[date] for date in post_dates) / max(1, len(post_dates))
        if unsupported_share >= 0.35:
            probability = min(probability, 0.45)
        baseline_residual = float(best["before_residual_kwh"])
        excess = sum(max(0.0, residuals[date] - baseline_residual) for date in post_dates if supported[date])

    timestamp_counts: dict[str, int] = defaultdict(int)
    for instant in timestamps:
        timestamp_counts[instant.isoformat()] += 1
    duplicate_count = sum(count - 1 for count in timestamp_counts.values() if count > 1)
    sorted_unique = sorted(set(timestamps))
    gap_count = sum(
        (right - left).total_seconds() > 15 * 60 + 1
        for left, right in zip(sorted_unique, sorted_unique[1:])
    )
    quality_issues = []
    if duplicate_count:
        quality_issues.append(f"{duplicate_count} timestamp(s) dupliqué(s) dans l'export 15 minutes")
    if gap_count:
        quality_issues.append(f"{gap_count} trou(s) temporel(s) supérieur(s) à 15 minutes")
    return {
        "probability": round(probability, 6),
        "onset": onset,
        "observed_excess_energy_kwh": None if excess is None else round(max(0.0, excess), 3),
        "effect_kwh_per_day": round(effect, 3),
        "recurrence": round(recurrence, 6),
        "quality_issues": quality_issues,
        "coverage_summary": (
            f"{len(energy_rows)} intervalles, {len(dates)} jours avec contexte; "
            f"{len(training_dates)} jours de référence; baseline {BASELINE_VERSION}/{method}."
        ),
        "support_limitations": sorted({
            reason for reasons in support_reasons.values() for reason in reasons
        }),
    }


def _asset_candidates(inventory: list[dict[str, str]], magnitude: float) -> list[dict[str, Any]]:
    ranked = sorted(
        inventory,
        key=lambda row: abs(float(row["nominal_power_kw"]) - magnitude),
    )[:3]
    raw = [1.0 / (1.0 + abs(float(row["nominal_power_kw"]) - magnitude)) for row in ranked]
    total = sum(raw) or 1.0
    return [
        {
            "asset_id": row["asset_id"],
            "probability": round(0.8 * weight / total, 6),
            "rationale": (
                f"Candidat morphologique uniquement: puissance nominale {row['nominal_power_kw']} kW "
                f"comparée à un saut agrégé d'environ {magnitude:.2f} kW."
            ),
            "falsification_test": "Synchroniser l'état réel de l'actif avec plusieurs événements centraux.",
        }
        for row, weight in zip(ranked, raw)
    ]


def _event_signatures(pack: Path, method: str = "morphology") -> list[dict[str, Any]]:
    if method not in SIGNATURE_METHODS:
        raise ValueError(f"Méthode de signature inconnue: {method}")
    event_path = pack / "07_central_electrical_events.csv"
    if not event_path.is_file():
        return []
    inventory = _read_csv(pack / "02_asset_inventory.csv")
    groups: dict[tuple[int, ...], list[dict[str, str]]] = defaultdict(list)
    for row in _read_csv(event_path):
        magnitude = round(abs(float(row["delta_active_power_kw"])) / 2.0)
        reactive = round(abs(float(row["delta_reactive_power_kvar"])))
        if method == "magnitude":
            key = (magnitude,)
        elif method == "pq":
            key = (magnitude, reactive)
        else:
            key = (
                magnitude,
                reactive,
                round(float(row["ramp_seconds_proxy"]) / 2.0),
                round(float(row["inrush_ratio_proxy"]) * 2.0),
                round(float(row["harmonic_distortion_pct_proxy"]) / 2.0),
            )
        groups[key].append(row)
    selected = sorted(
        (rows for rows in groups.values() if len(rows) >= 3),
        key=lambda rows: (-len(rows), rows[0]["event_id"]),
    )[:20]
    signatures = []
    for index, rows in enumerate(selected, 1):
        magnitude = _median(abs(float(row["delta_active_power_kw"])) for row in rows)
        event_refs = [f"event:{row['event_id']}" for row in rows[:500]]
        signatures.append({
            "signature_id": f"DS-{index:03d}",
            "description": (
                f"Motif central récurrent de {len(rows)} événements, |delta P| médian "
                f"{magnitude:.2f} kW; identité non établie."
            ),
            "event_refs": event_refs,
            "candidate_assets": _asset_candidates(inventory, magnitude),
            "confidence": round(min(0.8, 0.35 + math.log10(len(rows)) / 5.0), 6),
        })
    return signatures


def deterministic_baseline_response(
    case_directory: str | Path,
    *,
    detection_method: str = "production_temperature",
    energy_method: str = "production",
    signature_method: str = "morphology",
) -> dict[str, Any]:
    validated = validate_signal_case(case_directory)
    manifest = validated["manifest"]
    pack = Path(case_directory) / "initial_client_pack"
    detection = _daily_detection(pack, detection_method)
    energy_estimate = (
        detection if energy_method == detection_method else _daily_detection(pack, energy_method)
    )
    probability = float(detection["probability"])
    detected = probability >= 0.5
    event_class = "UNRESOLVED" if detected else "NO_ABNORMALITY"
    evidence_refs = [
        "initial_client_pack/05_aggregate_energy_15min.csv",
        "initial_client_pack/04_daily_operations.csv",
    ]
    mechanisms = [{
        "mechanism_code": "UNRESOLVED_PHYSICAL_MECHANISM",
        "probability": 0.5,
        "rationale": "Une rupture agrégée ne démontre aucun mécanisme physique.",
        "falsification_test": "Tester demande de service, mesure, commande et état réel séparément.",
    }]
    finding = {
        "finding_id": "DET-001",
        "event_class": event_class,
        "start": detection["onset"],
        "end": None,
        "abnormal_probability": probability,
        "target_assets": [],
        "mechanisms": mechanisms,
        "evidence_refs": evidence_refs,
        "observed_excess_energy_kwh": energy_estimate["observed_excess_energy_kwh"],
        "recoverable_energy_kwh": None,
        "interpretation": (
            "Signal agrégé candidat; ni actif, ni mécanisme, ni récupérabilité ne sont attribués."
        ),
        "alternative_explanations": [
            "Changement de demande ou de mix produit",
            "Température ou calendrier",
            "Changement de mesure ou de qualité des données",
        ],
    }
    findings = [finding] if detected else []
    primary_finding_id = "DET-001" if detected else None
    primary_onset = detection["onset"] if detected else None
    primary_energy = energy_estimate["observed_excess_energy_kwh"] if detected else None
    primary_evidence = evidence_refs if detected else []
    primary_mechanisms = mechanisms if detected else [{
        **mechanisms[0],
        "mechanism_code": "NORMAL_OR_UNRESOLVED_OPERATION",
    }]
    return {
        "schema_version": 2,
        "case_id": manifest["case_id"],
        "analysis_cutoff": manifest["analysis_cutoff"],
        "data_assessment": {
            "usable": True,
            "measurement_tier": manifest["measurement_tier"],
            "quality_issues": detection["quality_issues"],
            "limitations": [
                "Détection agrégée sans attribution ni causalité.",
                *[f"Support limité: {item}" for item in detection["support_limitations"]],
            ],
            "coverage_summary": detection["coverage_summary"],
        },
        "signatures": _event_signatures(pack, signature_method),
        "findings": findings,
        "primary_assessment": {
            "finding_id": primary_finding_id,
            "event_class": event_class,
            "abnormal_probability": probability,
            "onset": primary_onset,
            "target_assets": [],
            "mechanisms": primary_mechanisms,
            "observed_excess_energy_kwh": primary_energy,
            "evidence_refs": primary_evidence,
        },
        "prognosis": {
            "issued": False,
            "target_asset_id": None,
            "outcome_code": "UNRESOLVED",
            "horizon_days": manifest["forecast_horizon_days"],
            "outcome_within_horizon_probability": 0.5,
            "evidence_refs": primary_evidence,
            "abstention_reason": "Une rupture historique seule ne calibre pas un événement futur.",
        },
        "next_action": {
            "action_code": "REVIEW_SIGNAL" if detected else "NO_ACTION",
            "target_asset_id": None,
            "priority": "MEDIUM" if detected else "NONE",
            "action": (
                "Vérifier le contexte et synchroniser les états d'actifs avant toute intervention."
                if detected else "Aucune action déterminée par le contrôle de détection."
            ),
            "competent_person": "Responsable de site et technicien compétent",
            "preconditions": ["Aucune modification physique sur la seule base du signal agrégé."],
            "risks": ["Fausse attribution à partir du compteur central."],
            "stop_conditions": ["Arrêter si la vérification nécessite une manœuvre non autorisée."],
            "validation": "Comparer états réels, signal central et demande de service sur une période future.",
        },
        "overall_decision": "MONITOR" if detected else "NO_ACTION",
        "adversarial_review": {
            "best_reason_wrong": "Le changement peut être une extrapolation de production, produit ou température.",
            "test_performed": "Contrôle de support sur produit, production et température visibles.",
            "result": "Les extrapolations réduisent la probabilité; elles ne sont jamais converties en cause.",
            "decision_after_review": "Conserver uniquement un signal candidat ou ne rien signaler.",
        },
    }


def run_deterministic_baseline_suite(
    suite_directory: str | Path,
    runs_directory: str | Path,
    *,
    repository: str | Path,
    system_ref: str = "HEAD",
    stages: Sequence[str] = ("DEV", "HOLDOUT"),
    measurement_tiers: Sequence[str] = ("L0_E15", "L1_PQ1", "L2_EDGE"),
    detection_method: str = "production_temperature",
    energy_method: str = "production",
    signature_method: str = "morphology",
) -> dict[str, Any]:
    """Exécute le contrôle détection/motifs via le cycle aveugle verrouillé."""

    suite_root = Path(suite_directory).resolve()
    runs_root = Path(runs_directory).resolve()
    suite = json.loads((suite_root / "suite_manifest.json").read_text(encoding="utf-8"))
    selected_stages = set(stages)
    allowed_stages = {"DEV", "HOLDOUT", "HUMAN_PARITY", "PROSPECTIVE"}
    if not selected_stages or not selected_stages <= allowed_stages:
        raise SignalBenchmarkError("stages contient une valeur inconnue")
    selected_tiers = set(measurement_tiers)
    allowed_tiers = {"L0_E15", "L1_PQ1", "L2_EDGE", "L3_WAVEFORM"}
    if not selected_tiers or not selected_tiers <= allowed_tiers:
        raise SignalBenchmarkError("measurement_tiers contient une valeur inconnue")
    if detection_method not in DETECTION_METHODS:
        raise SignalBenchmarkError("detection_method inconnu")
    if energy_method not in DETECTION_METHODS:
        raise SignalBenchmarkError("energy_method inconnu")
    if signature_method not in SIGNATURE_METHODS:
        raise SignalBenchmarkError("signature_method inconnu")
    if runs_root.exists() and any(runs_root.iterdir()):
        raise FileExistsError(f"Le dossier de runs doit être neuf ou vide: {runs_root}")
    runs_root.mkdir(parents=True, exist_ok=True)
    completed = []
    for record in suite.get("cases", []):
        if (
            not isinstance(record, dict)
            or record.get("stage") not in selected_stages
            or record.get("measurement_tier") not in selected_tiers
        ):
            continue
        recorded_path = Path(str(record.get("case_path", "")))
        case = (recorded_path if recorded_path.is_absolute() else suite_root / recorded_path).resolve()
        if suite_root not in case.parents:
            raise SignalBenchmarkError("Un chemin de cas sort du dossier de suite")
        run = prepare_signal_run(
            case,
            runs_root,
            repository=repository,
            system_ref=system_ref,
            model=f"{BASELINE_VERSION}:{detection_method}:{energy_method}:{signature_method}",
            reasoning_effort="none",
            variant="DETERMINISTIC",
            run_id=(
                f"det-{METHOD_TAGS[detection_method]}-{METHOD_TAGS[energy_method]}-"
                f"{METHOD_TAGS[signature_method]}-{str(record['case_id']).lower()}"
            ),
        )
        response_path = run / "participant_workspace" / "output" / "response.json"
        response_path.parent.mkdir(parents=True, exist_ok=True)
        response_path.write_text(
            json.dumps(
                deterministic_baseline_response(
                    case,
                    detection_method=detection_method,
                    energy_method=energy_method,
                    signature_method=signature_method,
                ),
                ensure_ascii=False,
                indent=2,
            ) + "\n",
            encoding="utf-8",
        )
        finalized = finalize_signal_run(run, response_path, repository=repository)
        if finalized.get("ground_truth_read") is not False:
            raise SignalBenchmarkError("Le contrôle déterministe a lu la vérité avant verrouillage")
        score = score_signal_run(run, case)
        completed.append({
            "case_id": record["case_id"],
            "run_id": score["run_id"],
            "stage": record["stage"],
            "score": score["total_score"],
        })
    if not completed:
        raise SignalBenchmarkError("Aucun cas de la suite ne correspond aux stages demandés")
    aggregate = aggregate_scorecards(runs_root)
    result = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_profile": BENCHMARK_PROFILE,
        "baseline": BASELINE_VERSION,
        "detection_method": detection_method,
        "energy_method": energy_method,
        "signature_method": signature_method,
        "suite_seed": suite.get("seed"),
        "stages": sorted(selected_stages),
        "measurement_tiers": sorted(selected_tiers),
        "case_count": len(completed),
        "pre_truth_lock_enforced": True,
        "scope": ["detection", "reproducible_signature"],
        "excluded_claims": ["asset_attribution", "physical_mechanism", "prognosis"],
        "completed_runs": completed,
        "aggregate": aggregate,
        "limitations": [
            "Ce contrôle n'attribue aucun actif principal ni mécanisme physique.",
            "Ses candidats morphologiques ne sont pas des attributions.",
            "Il s'abstient systématiquement de tout pronostic.",
            "Les cas synthétiques ne constituent pas une validation terrain.",
        ],
    }
    output = runs_root / "DETERMINISTIC_BASELINE_RESULTS.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result
