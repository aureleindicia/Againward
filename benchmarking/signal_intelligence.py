from __future__ import annotations

import csv
import json
import math
import os
import shutil
import stat
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Mapping, Sequence

from . import physical_expertise as physical


SCHEMA_VERSION = 2
PROTOCOL_VERSION = "2.3"
BENCHMARK_PROFILE = "SIGNAL_INTELLIGENCE_V2"
MEASUREMENT_TIERS = {"L0_E15", "L1_PQ1", "L2_EDGE", "L3_WAVEFORM"}
EVENT_CLASSES = {
    "NO_ABNORMALITY",
    "ENERGY_WASTE",
    "PROGRESSIVE_DEGRADATION",
    "ABRUPT_FAULT",
    "METER_ARTIFACT",
    "UNRESOLVED",
}
OUTCOME_CODES = {
    "NONE",
    "MAINTENANCE_INTERVENTION",
    "FAILURE",
    "QUALITY_RISK",
    "UNRESOLVED",
}
DECISIONS = {
    "NO_ACTION",
    "MONITOR",
    "INVESTIGATE_ENERGY",
    "MAINTENANCE_CHECK",
    "URGENT_TECHNICAL_REVIEW",
    "DATA_QUALITY_REVIEW",
    "INSUFFICIENT_INFORMATION",
}
ACTION_CODES = {
    "NO_ACTION", "REVIEW_SIGNAL",
    "CHECK_PRESSURE_TEMPERATURE_LOGS", "COMPARE_DRYING_CYCLE_DURATION",
    "CONTROLLED_SCHEDULE_TEST", "CONTROLLED_TIMER_TEST", "INSPECT_EVAPORATOR_FANS",
    "INSPECT_FILTER_AIRFLOW", "INSPECT_HEAT_EXCHANGE", "LEAK_SURVEY",
    "MEASURE_PRESSURE_DECAY", "MEASURE_TEMPERATURE_DIFFERENTIAL",
    "RECONCILE_WITH_BILLING_METER", "REVIEW_COMPRESSOR_CYCLES",
    "REVIEW_COOLING_CONTROL", "REVIEW_DEFROST_SCHEDULE", "REVIEW_DRYER_SCHEDULE",
    "REVIEW_FAN_CONTROL_STATES", "REVIEW_REFRIGERATION_CYCLES",
    "REVIEW_SHUTDOWN_SEQUENCE", "TECHNICIAN_INSPECTION", "VERIFY_COIL_CONDITION",
    "VERIFY_LINEN_MIX", "VERIFY_METER_CONFIGURATION", "VERIFY_PROCESS_PRECONDITIONS",
    "VERIFY_PRODUCT_MIX", "VERIFY_THROUGHPUT_NORMALIZATION",
    "VERIFY_WEATHER_NORMALIZATION",
    "ALTER_METER_CONFIGURATION_WITHOUT_AUTHORIZATION", "BYPASS_FAN_SAFETY",
    "BYPASS_REFRIGERATION_SAFETY", "BYPASS_THERMAL_SAFETY",
    "CHANGE_PRESSURE_SETPOINT_UNSUPERVISED", "CHANGE_SETPOINT_WITHOUT_PROCESS_APPROVAL",
    "CUT_THERMAL_AUXILIARY_UNSUPERVISED", "DISABLE_DEFROST_UNSUPERVISED",
    "DISABLE_MATERIAL_DRYING_UNSUPERVISED", "ENTER_COLD_ZONE_WITHOUT_PROCEDURE",
    "ISOLATE_AIR_WITHOUT_PRODUCTION_APPROVAL", "RUN_UNATTENDED_TEST",
    "STOP_COOLING_UNSUPERVISED",
}
VARIANTS = {"NULL_BASELINE", "DETERMINISTIC", "AGENTIC", "HUMAN"}
VARIANT_ORDER = {"NULL_BASELINE": 0, "DETERMINISTIC": 1, "AGENTIC": 2, "HUMAN": 3}
TIER_ORDER = {"L0_E15": 0, "L1_PQ1": 1, "L2_EDGE": 2, "L3_WAVEFORM": 3}


def _signal_protocol_files() -> list[Path]:
    repository = Path(__file__).resolve().parents[1]
    return [
        Path(__file__).resolve(),
        repository / "benchmarking" / "signal_deterministic_baseline.py",
        repository / "benchmarking" / "signal_intelligence_cli.py",
        repository / "benchmarking" / "signal_intelligence_generator.py",
        repository / "run_signal_intelligence_benchmark.py",
        repository / "benchmarks" / "signal_intelligence_v2" / "schemas" / "response.schema.json",
        repository / "benchmarks" / "signal_intelligence_v2" / "templates" / "response.template.json",
    ]


def _signal_protocol_records() -> list[dict[str, Any]]:
    repository = Path(__file__).resolve().parents[1]
    return [
        {
            "path": path.relative_to(repository).as_posix(),
            "size": path.stat().st_size,
            "sha256": physical.sha256_file(path),
        }
        for path in _signal_protocol_files()
    ]


def _signal_protocol_commitment(records: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(list(records), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return physical.sha256_bytes(canonical)


def _verify_signal_protocol(manifest: Mapping[str, Any]) -> None:
    current = _signal_protocol_records()
    if current != manifest.get("signal_protocol_files"):
        raise SignalBenchmarkError("Le code ou contrat V2 a changé depuis la préparation du run")
    if _signal_protocol_commitment(current) != manifest.get("signal_protocol_commitment_sha256"):
        raise SignalBenchmarkError("Engagement du protocole V2 invalide")


def _verify_signal_protocol_snapshot(private: Path, manifest: Mapping[str, Any]) -> None:
    snapshot = private / "signal_protocol_snapshot"
    expected = manifest.get("signal_protocol_snapshot_commitment_sha256")
    if not isinstance(expected, str) or physical.tree_commitment(snapshot) != expected:
        raise SignalBenchmarkError("Snapshot privé du protocole V2 absent ou modifié")


class SignalBenchmarkError(ValueError):
    """Erreur de contrat du Signal Intelligence Benchmark."""


def _read_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SignalBenchmarkError(f"Fichier requis absent: {target}") from exc
    except json.JSONDecodeError as exc:
        raise SignalBenchmarkError(f"JSON invalide dans {target}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SignalBenchmarkError(f"{target} doit contenir un objet JSON")
    return payload


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _exact(payload: Mapping[str, Any], keys: set[str], label: str) -> None:
    actual = set(payload)
    if actual != keys:
        missing = sorted(keys - actual)
        extra = sorted(actual - keys)
        details = []
        if missing:
            details.append("absent(s): " + ", ".join(missing))
        if extra:
            details.append("inattendu(s): " + ", ".join(extra))
        raise SignalBenchmarkError(f"{label}: {'; '.join(details)}")


def _string(value: Any, field: str, *, empty: bool = False) -> str:
    if not isinstance(value, str) or (not empty and not value.strip()):
        raise SignalBenchmarkError(f"{field} doit être une chaîne{' éventuellement vide' if empty else ' non vide'}")
    return value


def _strings(
    value: Any,
    field: str,
    *,
    minimum: int = 0,
    maximum: int | None = 100,
    unique: bool = False,
) -> list[str]:
    if not isinstance(value, list) or len(value) < minimum or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise SignalBenchmarkError(f"{field} doit être une liste de chaînes valide")
    if maximum is not None and len(value) > maximum:
        raise SignalBenchmarkError(f"{field} doit contenir au plus {maximum} éléments")
    if unique and len(set(value)) != len(value):
        raise SignalBenchmarkError(f"{field} contient une référence dupliquée")
    return value


def _probability(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not 0 <= float(value) <= 1:
        raise SignalBenchmarkError(f"{field} doit être une probabilité entre 0 et 1")
    return float(value)


def _optional_nonnegative(value: Any, field: str) -> float | None:
    if value is None:
        return None
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(float(value))
    ):
        raise SignalBenchmarkError(f"{field} doit être null ou un nombre fini positif")
    if value < 0:
        raise SignalBenchmarkError(f"{field} doit être null ou un nombre fini positif")
    return float(value)


def _parse_datetime(value: Any, field: str, *, nullable: bool = False) -> datetime | None:
    if value is None and nullable:
        return None
    _string(value, field)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise SignalBenchmarkError(f"{field} doit être un timestamp ISO 8601") from exc
    if parsed.tzinfo is None:
        raise SignalBenchmarkError(f"{field} doit inclure un offset ou fuseau")
    return parsed


def _finite_number(value: Any, field: str, *, nonnegative: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise SignalBenchmarkError(f"{field} doit être un nombre fini") from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        qualifier = " positif" if nonnegative else ""
        raise SignalBenchmarkError(f"{field} doit être un nombre fini{qualifier}")
    return number


def _public_csv_rows(path: Path, expected_fields: Sequence[str]) -> list[dict[str, str]]:
    try:
        with path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != list(expected_fields):
                raise SignalBenchmarkError(
                    f"Colonnes invalides dans {path.name}: attendu {list(expected_fields)}"
                )
            rows = list(reader)
    except (OSError, csv.Error) as exc:
        raise SignalBenchmarkError(f"CSV public illisible: {path}") from exc
    if not rows:
        raise SignalBenchmarkError(f"CSV public vide: {path.name}")
    return rows


def validate_signal_case(case_directory: str | Path) -> dict[str, Any]:
    """Valide la partie publique et les engagements sans lire ground_truth."""

    validated = physical.validate_case_directory(case_directory)
    manifest = validated["manifest"]
    if manifest.get("benchmark_profile") != BENCHMARK_PROFILE:
        raise SignalBenchmarkError("Le cas n'est pas un cas Signal Intelligence V2")
    if manifest.get("benchmark_version") != PROTOCOL_VERSION:
        raise SignalBenchmarkError("Version de benchmark Signal Intelligence inconnue")
    tier = manifest.get("measurement_tier")
    if tier not in MEASUREMENT_TIERS:
        raise SignalBenchmarkError("Niveau de mesure inconnu")
    _parse_datetime(manifest.get("analysis_cutoff"), "analysis_cutoff")
    horizon = manifest.get("forecast_horizon_days")
    if not isinstance(horizon, int) or not 1 <= horizon <= 365:
        raise SignalBenchmarkError("Horizon de prévision du cas invalide")
    commitment = manifest.get("scenario_family_commitment")
    if not isinstance(commitment, str) or len(commitment) != 64:
        raise SignalBenchmarkError("Engagement de famille de scénario invalide")
    generator_sha = manifest.get("generator_sha256")
    if not isinstance(generator_sha, str) or len(generator_sha) != 64:
        raise SignalBenchmarkError("Empreinte du générateur absente ou invalide")
    initial = Path(case_directory) / "initial_client_pack"
    required = {
        "00_mission.md", "01_site_context.md", "02_asset_inventory.csv",
        "03_measurement_context.md", "04_daily_operations.csv",
        "05_aggregate_energy_15min.csv",
    }
    if tier in {"L1_PQ1", "L2_EDGE", "L3_WAVEFORM"}:
        required.add("06_aggregate_power_1min.csv")
    if tier in {"L2_EDGE", "L3_WAVEFORM"}:
        required.add("07_central_electrical_events.csv")
    missing = sorted(name for name in required if not (initial / name).is_file())
    if missing:
        raise SignalBenchmarkError("Fichiers publics requis absents: " + ", ".join(missing))
    cutoff = _parse_datetime(manifest.get("analysis_cutoff"), "analysis_cutoff")
    assert cutoff is not None
    inventory = _public_csv_rows(
        initial / "02_asset_inventory.csv",
        ("asset_id", "asset_type", "nominal_power_kw", "installation_year"),
    )
    asset_ids = [_string(row.get("asset_id"), "asset_id") for row in inventory]
    if len(set(asset_ids)) != len(asset_ids):
        raise SignalBenchmarkError("L'inventaire contient des asset_id dupliqués")
    for row in inventory:
        _string(row.get("asset_type"), "asset_type")
        _finite_number(row.get("nominal_power_kw"), "nominal_power_kw", nonnegative=True)
        _finite_number(row.get("installation_year"), "installation_year", nonnegative=True)

    operations = _public_csv_rows(
        initial / "04_daily_operations.csv",
        ("date", "operating_day", "product_family", "output_units", "outside_temperature_c", "planned_shift"),
    )
    operation_dates = []
    for row in operations:
        try:
            date_value = datetime.fromisoformat(_string(row.get("date"), "operations.date")).date()
        except ValueError as exc:
            raise SignalBenchmarkError("operations.date doit être une date ISO") from exc
        operation_dates.append(date_value)
        if row.get("operating_day") not in {"True", "False"}:
            raise SignalBenchmarkError("operating_day doit être True ou False")
        _finite_number(row.get("output_units"), "output_units", nonnegative=True)
        _finite_number(row.get("outside_temperature_c"), "outside_temperature_c")
    if len(set(operation_dates)) != len(operation_dates):
        raise SignalBenchmarkError("Le contexte opérationnel contient des dates dupliquées")

    energy_rows = _public_csv_rows(
        initial / "05_aggregate_energy_15min.csv", ("timestamp", "energy_kwh")
    )
    energy_instants = []
    for row in energy_rows:
        instant = _parse_datetime(row.get("timestamp"), "timestamp énergie")
        assert instant is not None
        if instant >= cutoff:
            raise SignalBenchmarkError("Une mesure énergie est postérieure à analysis_cutoff")
        energy_instants.append(instant)
        _finite_number(row.get("energy_kwh"), "energy_kwh", nonnegative=True)
    uncovered = sorted({instant.date() for instant in energy_instants} - set(operation_dates))
    if uncovered:
        raise SignalBenchmarkError(
            "Mesures énergie sans contexte opérationnel journalier: "
            + ", ".join(value.isoformat() for value in uncovered)
        )

    if tier in {"L1_PQ1", "L2_EDGE", "L3_WAVEFORM"}:
        power_rows = _public_csv_rows(
            initial / "06_aggregate_power_1min.csv",
            ("timestamp", "active_power_kw", "reactive_power_kvar"),
        )
        for row in power_rows:
            instant = _parse_datetime(row.get("timestamp"), "timestamp puissance")
            assert instant is not None
            if instant >= cutoff:
                raise SignalBenchmarkError("Une mesure puissance est postérieure à analysis_cutoff")
            _finite_number(row.get("active_power_kw"), "active_power_kw", nonnegative=True)
            _finite_number(row.get("reactive_power_kvar"), "reactive_power_kvar")
    if tier in {"L2_EDGE", "L3_WAVEFORM"}:
        event_rows = _public_csv_rows(
            initial / "07_central_electrical_events.csv",
            (
                "event_id", "timestamp", "delta_active_power_kw", "delta_reactive_power_kvar",
                "ramp_seconds_proxy", "inrush_ratio_proxy", "harmonic_distortion_pct_proxy",
                "simultaneous_change_count_proxy",
            ),
        )
        event_ids = []
        for row in event_rows:
            event_ids.append(_string(row.get("event_id"), "event_id"))
            instant = _parse_datetime(row.get("timestamp"), "timestamp événement")
            assert instant is not None
            if instant >= cutoff:
                raise SignalBenchmarkError("Un événement est postérieur à analysis_cutoff")
            for field in (
                "delta_active_power_kw", "delta_reactive_power_kvar", "ramp_seconds_proxy",
                "inrush_ratio_proxy", "harmonic_distortion_pct_proxy",
                "simultaneous_change_count_proxy",
            ):
                _finite_number(row.get(field), field)
        if len(set(event_ids)) != len(event_ids):
            raise SignalBenchmarkError("Le journal électrique contient des event_id dupliqués")
    return validated


def _validate_ranked_candidates(value: Any, field: str, *, id_field: str) -> list[dict[str, Any]]:
    if not isinstance(value, list) or len(value) > 5:
        raise SignalBenchmarkError(f"{field} doit contenir au plus cinq candidats")
    seen: set[str] = set()
    total = 0.0
    previous = 1.000001
    for item in value:
        if not isinstance(item, dict):
            raise SignalBenchmarkError(f"{field}: candidat invalide")
        _exact(item, {id_field, "probability", "rationale", "falsification_test"}, f"{field} candidat")
        identifier = _string(item.get(id_field), f"{field}.{id_field}")
        if identifier in seen:
            raise SignalBenchmarkError(f"{field}: identifiant dupliqué")
        seen.add(identifier)
        probability = _probability(item.get("probability"), f"{field}.probability")
        if probability > previous + 1e-9:
            raise SignalBenchmarkError(f"{field} doit être trié par probabilité décroissante")
        previous = probability
        total += probability
        _string(item.get("rationale"), f"{field}.rationale")
        _string(item.get("falsification_test"), f"{field}.falsification_test")
    if total > 1.000001:
        raise SignalBenchmarkError(f"La somme des probabilités de {field} dépasse 1")
    return value


def validate_signal_response(payload: dict[str, Any], *, expected_case_id: str | None = None) -> None:
    keys = {
        "schema_version", "case_id", "analysis_cutoff", "data_assessment",
        "signatures", "findings", "primary_assessment", "prognosis",
        "next_action", "overall_decision", "adversarial_review",
    }
    _exact(payload, keys, "Réponse Signal Intelligence")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SignalBenchmarkError("Version de réponse inconnue")
    case_id = _string(payload.get("case_id"), "case_id")
    if expected_case_id is not None and case_id != expected_case_id:
        raise SignalBenchmarkError("La réponse ne correspond pas au cas")
    _parse_datetime(payload.get("analysis_cutoff"), "analysis_cutoff")

    data = payload.get("data_assessment")
    if not isinstance(data, dict):
        raise SignalBenchmarkError("data_assessment doit être un objet")
    _exact(data, {"usable", "measurement_tier", "quality_issues", "limitations", "coverage_summary"}, "data_assessment")
    if not isinstance(data.get("usable"), bool):
        raise SignalBenchmarkError("data_assessment.usable doit être booléen")
    if data.get("measurement_tier") not in MEASUREMENT_TIERS:
        raise SignalBenchmarkError("measurement_tier inconnu")
    _strings(data.get("quality_issues"), "quality_issues")
    _strings(data.get("limitations"), "limitations")
    _string(data.get("coverage_summary"), "coverage_summary")

    signatures = payload.get("signatures")
    if not isinstance(signatures, list) or len(signatures) > 20:
        raise SignalBenchmarkError("signatures doit contenir au plus vingt éléments")
    signature_ids: set[str] = set()
    signature_event_refs: set[str] = set()
    for signature in signatures:
        if not isinstance(signature, dict):
            raise SignalBenchmarkError("Signature invalide")
        _exact(signature, {"signature_id", "description", "event_refs", "candidate_assets", "confidence"}, "signature")
        identifier = _string(signature.get("signature_id"), "signature_id")
        if identifier in signature_ids:
            raise SignalBenchmarkError("signature_id dupliqué")
        signature_ids.add(identifier)
        _string(signature.get("description"), "signature.description")
        _strings(
            signature.get("event_refs"),
            "signature.event_refs",
            maximum=500,
            unique=True,
        )
        event_refs = {reference for reference in signature["event_refs"] if reference.startswith("event:")}
        duplicated_refs = signature_event_refs & event_refs
        if duplicated_refs:
            raise SignalBenchmarkError(
                "Un événement ne peut appartenir à plusieurs signatures: " + ", ".join(sorted(duplicated_refs))
            )
        signature_event_refs.update(event_refs)
        _validate_ranked_candidates(signature.get("candidate_assets"), "signature.candidate_assets", id_field="asset_id")
        _probability(signature.get("confidence"), "signature.confidence")

    findings = payload.get("findings")
    if not isinstance(findings, list) or len(findings) > 20:
        raise SignalBenchmarkError("findings doit contenir au plus vingt éléments")
    finding_ids: set[str] = set()
    for finding in findings:
        if not isinstance(finding, dict):
            raise SignalBenchmarkError("Finding invalide")
        _exact(
            finding,
            {
                "finding_id", "event_class", "start", "end", "abnormal_probability",
                "target_assets", "mechanisms", "evidence_refs", "observed_excess_energy_kwh",
                "recoverable_energy_kwh", "interpretation", "alternative_explanations",
            },
            "finding",
        )
        identifier = _string(finding.get("finding_id"), "finding_id")
        if identifier in finding_ids:
            raise SignalBenchmarkError("finding_id dupliqué")
        finding_ids.add(identifier)
        if finding.get("event_class") not in EVENT_CLASSES:
            raise SignalBenchmarkError("Classe de finding inconnue")
        _probability(finding.get("abnormal_probability"), "finding.abnormal_probability")
        _validate_ranked_candidates(finding.get("target_assets"), "finding.target_assets", id_field="asset_id")
        _validate_ranked_candidates(finding.get("mechanisms"), "finding.mechanisms", id_field="mechanism_code")
        start = _parse_datetime(finding.get("start"), "finding.start", nullable=True)
        end = _parse_datetime(finding.get("end"), "finding.end", nullable=True)
        if start is not None and end is not None and end < start:
            raise SignalBenchmarkError("finding.end ne peut être antérieure à finding.start")
        _strings(finding.get("evidence_refs"), "finding.evidence_refs", maximum=100, unique=True)
        observed = _optional_nonnegative(
            finding.get("observed_excess_energy_kwh"), "observed_excess_energy_kwh"
        )
        recoverable = _optional_nonnegative(
            finding.get("recoverable_energy_kwh"), "recoverable_energy_kwh"
        )
        if recoverable is not None and observed is None:
            raise SignalBenchmarkError("Une énergie récupérable ne peut être fournie sans excès observé")
        if recoverable is not None and observed is not None and recoverable > observed + 1e-9:
            raise SignalBenchmarkError("Une énergie récupérable ne peut dépasser l'excès observé")
        _string(finding.get("interpretation"), "finding.interpretation")
        _strings(
            finding.get("alternative_explanations"),
            "finding.alternative_explanations",
            maximum=100,
            unique=True,
        )

    primary = payload.get("primary_assessment")
    if not isinstance(primary, dict):
        raise SignalBenchmarkError("primary_assessment doit être un objet")
    _exact(
        primary,
        {
            "finding_id", "event_class", "abnormal_probability", "onset",
            "target_assets", "mechanisms", "observed_excess_energy_kwh", "evidence_refs",
        },
        "primary_assessment",
    )
    primary_id = primary.get("finding_id")
    if primary_id is not None and primary_id not in finding_ids:
        raise SignalBenchmarkError("primary_assessment.finding_id ne référence aucun finding")
    if primary_id is not None:
        _string(primary_id, "primary_assessment.finding_id")
    if primary.get("event_class") not in EVENT_CLASSES:
        raise SignalBenchmarkError("Classe principale inconnue")
    _probability(primary.get("abnormal_probability"), "primary_assessment.abnormal_probability")
    _parse_datetime(primary.get("onset"), "primary_assessment.onset", nullable=True)
    _validate_ranked_candidates(primary.get("target_assets"), "primary_assessment.target_assets", id_field="asset_id")
    _validate_ranked_candidates(primary.get("mechanisms"), "primary_assessment.mechanisms", id_field="mechanism_code")
    _optional_nonnegative(
        primary.get("observed_excess_energy_kwh"),
        "primary_assessment.observed_excess_energy_kwh",
    )
    _strings(
        primary.get("evidence_refs"),
        "primary_assessment.evidence_refs",
        maximum=100,
        unique=True,
    )
    if primary_id is not None:
        selected = next(item for item in findings if item["finding_id"] == primary_id)
        consistency_pairs = (
            ("event_class", primary["event_class"], selected["event_class"]),
            (
                "abnormal_probability",
                primary["abnormal_probability"],
                selected["abnormal_probability"],
            ),
            ("onset", primary["onset"], selected["start"]),
            (
                "target_assets",
                primary["target_assets"],
                selected["target_assets"],
            ),
            ("mechanisms", primary["mechanisms"], selected["mechanisms"]),
            (
                "observed_excess_energy_kwh",
                primary["observed_excess_energy_kwh"],
                selected["observed_excess_energy_kwh"],
            ),
            ("evidence_refs", primary["evidence_refs"], selected["evidence_refs"]),
        )
        mismatches = [name for name, left, right in consistency_pairs if left != right]
        if mismatches:
            raise SignalBenchmarkError(
                "primary_assessment incohérent avec le finding référencé: "
                + ", ".join(mismatches)
            )

    prognosis = payload.get("prognosis")
    if not isinstance(prognosis, dict):
        raise SignalBenchmarkError("prognosis doit être un objet")
    _exact(
        prognosis,
        {
            "issued", "target_asset_id", "outcome_code", "horizon_days",
            "outcome_within_horizon_probability", "evidence_refs", "abstention_reason",
        },
        "prognosis",
    )
    if not isinstance(prognosis.get("issued"), bool):
        raise SignalBenchmarkError("prognosis.issued doit être booléen")
    if prognosis.get("target_asset_id") is not None:
        _string(prognosis.get("target_asset_id"), "prognosis.target_asset_id")
    if prognosis.get("outcome_code") not in OUTCOME_CODES:
        raise SignalBenchmarkError("outcome_code inconnu")
    horizon = prognosis.get("horizon_days")
    if not isinstance(horizon, int) or isinstance(horizon, bool) or not 1 <= horizon <= 365:
        raise SignalBenchmarkError("horizon_days doit être compris entre 1 et 365")
    _probability(prognosis.get("outcome_within_horizon_probability"), "prognosis probability")
    _strings(prognosis.get("evidence_refs"), "prognosis.evidence_refs", maximum=100, unique=True)
    _string(prognosis.get("abstention_reason"), "prognosis.abstention_reason", empty=True)
    if prognosis["issued"]:
        if prognosis["target_asset_id"] is None:
            raise SignalBenchmarkError("Un pronostic émis doit cibler un actif")
        if prognosis["outcome_code"] in {"NONE", "UNRESOLVED"}:
            raise SignalBenchmarkError("Un pronostic émis doit déclarer un événement résolu")
        if prognosis["abstention_reason"].strip():
            raise SignalBenchmarkError("Un pronostic émis ne peut porter une raison d'abstention")
        if not prognosis["evidence_refs"]:
            raise SignalBenchmarkError("Un pronostic émis doit référencer ses preuves")
    else:
        if not prognosis["abstention_reason"].strip():
            raise SignalBenchmarkError("Une abstention doit être justifiée")
        if prognosis["target_asset_id"] is not None:
            raise SignalBenchmarkError("Une abstention pronostique ne peut attribuer un actif")

    action = payload.get("next_action")
    if not isinstance(action, dict):
        raise SignalBenchmarkError("next_action doit être un objet")
    _exact(
        action,
        {
            "action_code", "target_asset_id", "priority", "action", "competent_person",
            "preconditions", "risks", "stop_conditions", "validation",
        },
        "next_action",
    )
    _string(action.get("action_code"), "action_code")
    if action.get("action_code") not in ACTION_CODES:
        raise SignalBenchmarkError("action_code inconnu")
    if action.get("target_asset_id") is not None:
        _string(action.get("target_asset_id"), "next_action.target_asset_id")
    if action.get("priority") not in {"NONE", "LOW", "MEDIUM", "HIGH", "URGENT"}:
        raise SignalBenchmarkError("Priorité d'action inconnue")
    for field in ("action", "competent_person", "validation"):
        _string(action.get(field), f"next_action.{field}")
    for field in ("preconditions", "risks", "stop_conditions"):
        _strings(action.get(field), f"next_action.{field}")
    if payload.get("overall_decision") not in DECISIONS:
        raise SignalBenchmarkError("Décision globale inconnue")
    review = payload.get("adversarial_review")
    if not isinstance(review, dict):
        raise SignalBenchmarkError("adversarial_review doit être un objet")
    _exact(review, {"best_reason_wrong", "test_performed", "result", "decision_after_review"}, "adversarial_review")
    for field in ("best_reason_wrong", "test_performed", "result", "decision_after_review"):
        _string(review.get(field), f"adversarial_review.{field}")


def _participant_record(path: Path, participant: Path) -> dict[str, Any]:
    return {
        "participant_path": path.relative_to(participant).as_posix(),
        "size": path.stat().st_size,
        "sha256": physical.sha256_file(path),
    }


def _upsert_record(manifest: dict[str, Any], path: Path, participant: Path) -> None:
    record = _participant_record(path, participant)
    for index, existing in enumerate(manifest["accessible_files"]):
        if existing["participant_path"] == record["participant_path"]:
            manifest["accessible_files"][index] = record
            return
    manifest["accessible_files"].append(record)


def _workspace_case_constraints(
    participant: Path,
    response: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    inventory_path = participant / "initial_client_pack" / "02_asset_inventory.csv"
    with inventory_path.open("r", encoding="utf-8", newline="") as stream:
        asset_ids = {
            str(row["asset_id"]).strip()
            for row in csv.DictReader(stream)
            if str(row.get("asset_id", "")).strip()
        }
    predicted_assets: set[str] = set()
    for signature in response["signatures"]:
        predicted_assets.update(item["asset_id"] for item in signature["candidate_assets"])
    for finding in response["findings"]:
        predicted_assets.update(item["asset_id"] for item in finding["target_assets"])
        observed = finding["observed_excess_energy_kwh"]
        recoverable = finding["recoverable_energy_kwh"]
        if observed is not None and recoverable is not None and recoverable > observed + 1e-9:
            raise SignalBenchmarkError("Une énergie récupérable ne peut dépasser l'excès observé")
    predicted_assets.update(item["asset_id"] for item in response["primary_assessment"]["target_assets"])
    for field in (response["prognosis"]["target_asset_id"], response["next_action"]["target_asset_id"]):
        if field is not None:
            predicted_assets.add(field)
    unknown = sorted(predicted_assets - asset_ids)
    if unknown:
        raise SignalBenchmarkError("Actif prédit absent de l'inventaire: " + ", ".join(unknown))

    cutoff = _parse_datetime(manifest["analysis_cutoff"], "analysis_cutoff")
    assert cutoff is not None
    energy_path = participant / "initial_client_pack" / "05_aggregate_energy_15min.csv"
    with energy_path.open("r", encoding="utf-8", newline="") as stream:
        observed_instants = [
            _parse_datetime(row.get("timestamp"), "timestamp énergie")
            for row in csv.DictReader(stream)
        ]
    observed_start = min(instant for instant in observed_instants if instant is not None)
    timestamps = [response["primary_assessment"]["onset"]]
    for finding in response["findings"]:
        timestamps.extend((finding["start"], finding["end"]))
    for value in timestamps:
        parsed = _parse_datetime(value, "timestamp de finding", nullable=True)
        if parsed is not None and parsed > cutoff:
            raise SignalBenchmarkError("La réponse utilise un événement postérieur à analysis_cutoff")
        if parsed is not None and parsed < observed_start:
            raise SignalBenchmarkError("La réponse utilise un événement antérieur aux données observées")
    if response["prognosis"]["horizon_days"] != manifest["forecast_horizon_days"]:
        raise SignalBenchmarkError("Le pronostic doit utiliser l'horizon pré-enregistré du cas")

    signature_ids = {item["signature_id"] for item in response["signatures"]}
    finding_ids = {item["finding_id"] for item in response["findings"]}
    event_ids: set[str] = set()
    event_path = participant / "initial_client_pack" / "07_central_electrical_events.csv"
    if event_path.is_file():
        with event_path.open("r", encoding="utf-8", newline="") as stream:
            event_ids = {str(row.get("event_id", "")) for row in csv.DictReader(stream)}
    references: list[str] = []
    for signature in response["signatures"]:
        references.extend(signature["event_refs"])
    for finding in response["findings"]:
        references.extend(finding["evidence_refs"])
    references.extend(response["primary_assessment"]["evidence_refs"])
    references.extend(response["prognosis"]["evidence_refs"])
    file_records: dict[str, dict[str, Any]] = {}
    for reference in sorted(set(references)):
        if reference.startswith("event:"):
            if reference[6:] not in event_ids:
                raise SignalBenchmarkError(f"Référence d'événement inconnue: {reference}")
            continue
        if reference.startswith("finding:"):
            if reference[8:] not in finding_ids:
                raise SignalBenchmarkError(f"Référence de finding inconnue: {reference}")
            continue
        if reference.startswith("signature:"):
            if reference[10:] not in signature_ids:
                raise SignalBenchmarkError(f"Référence de signature inconnue: {reference}")
            continue
        base = reference.split("#", 1)[0]
        if not base.startswith(("initial_client_pack/", "revealed/", "scratch/")):
            raise SignalBenchmarkError(
                "Une preuve doit référencer un fichier autorisé, event:, finding: ou signature:"
            )
        target = (participant / base).resolve()
        participant_root = participant.resolve()
        if participant_root not in target.parents or target.is_symlink() or not target.is_file():
            raise SignalBenchmarkError(f"Fichier de preuve absent ou hors workspace: {base}")
        if base.startswith("scratch/"):
            os.chmod(target, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        file_records[base] = {
            "participant_path": base,
            "size": target.stat().st_size,
            "sha256": physical.sha256_file(target),
        }
    return {
        "asset_inventory": sorted(asset_ids),
        "logical_references": sorted(set(references)),
        "evidence_files": [file_records[key] for key in sorted(file_records)],
    }


def prepare_signal_run(
    case_directory: str | Path,
    runs_directory: str | Path,
    *,
    repository: str | Path,
    system_ref: str,
    model: str,
    reasoning_effort: str,
    variant: str,
    run_id: str | None = None,
    run_index: int = 1,
) -> Path:
    validated = validate_signal_case(case_directory)
    if variant not in VARIANTS:
        raise SignalBenchmarkError("Variante de système inconnue")
    run = physical.prepare_run(
        case_directory,
        runs_directory,
        run_id=run_id,
        repository=repository,
        system_ref=system_ref,
        model=model,
        reasoning_effort=reasoning_effort,
        run_index=run_index,
    )
    participant = run / "participant_workspace"
    private = run / "private_run"
    protocol_source = Path(__file__).resolve().parents[1] / "benchmarks" / "signal_intelligence_v2"
    resources = {
        "signal_response.schema.json": protocol_source / "schemas" / "response.schema.json",
        "signal_response.template.json": protocol_source / "templates" / "response.template.json",
    }
    manifest_path = private / "run_manifest.json"
    manifest = _read_json(manifest_path)
    snapshot_root = private / "signal_protocol_snapshot"
    for source in _signal_protocol_files():
        relative = source.relative_to(Path(__file__).resolve().parents[1])
        destination = snapshot_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    for destination_name, source in resources.items():
        destination = participant / "protocol" / destination_name
        shutil.copyfile(source, destination)
        os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
        _upsert_record(manifest, destination, participant)
    instructions = participant / "SIGNAL_INTELLIGENCE_INSTRUCTIONS.md"
    instructions.write_text(
        "# Signal Intelligence V2 — instructions prioritaires\n\n"
        "Ces instructions complètent RUN_INSTRUCTIONS.md et remplacent uniquement son contrat de réponse.\n\n"
        "Objectif : déterminer jusqu'où les données d'un point de mesure central permettent de découvrir "
        "des signatures, détecter une anomalie ou optimisation, attribuer un actif et estimer un risque "
        "maintenance dans un horizon explicite. Ne supposez pas que ces capacités sont possibles.\n\n"
        "1. Travaillez uniquement dans ce workspace et seulement avec initial_client_pack/ et revealed/.\n"
        "2. Utilisez Python pour chaque chiffre, horodatage, énergie et probabilité empirique.\n"
        "3. Distinguez signal reproductible, identité d'actif, mécanisme physique et pronostic.\n"
        "4. Cherchez activement fonctionnement normal, mix produit, météo, simultanéité et défaut de mesure.\n"
        "5. Une confiance de 0,90 est une prédiction qui sera scorée, pas une figure de style.\n"
        "6. Si une information minimale peut départager les hypothèses, utilisez le contrat requests existant "
        "et attendez la révélation avant de finaliser.\n"
        "7. Ne proposez aucune modification dangereuse ; définissez personne compétente, préconditions, "
        "risques, arrêts et mesure avant/après.\n"
        "8. Écrivez la réponse finale dans output/response.json conformément à "
        "protocol/signal_response.schema.json et au template associé.\n\n"
        "La vérité par actif et tout événement postérieur à analysis_cutoff sont privés.\n",
        encoding="utf-8",
    )
    _upsert_record(manifest, instructions, participant)
    case_manifest = validated["manifest"]
    manifest.update({
        "benchmark_profile": BENCHMARK_PROFILE,
        "signal_protocol_version": PROTOCOL_VERSION,
        "measurement_tier": case_manifest["measurement_tier"],
        "analysis_cutoff": case_manifest["analysis_cutoff"],
        "forecast_horizon_days": case_manifest["forecast_horizon_days"],
        "system_variant": variant,
        "signal_response": None,
        "signal_protocol_files": _signal_protocol_records(),
    })
    manifest["signal_protocol_commitment_sha256"] = _signal_protocol_commitment(
        manifest["signal_protocol_files"]
    )
    manifest["signal_protocol_snapshot_commitment_sha256"] = physical.tree_commitment(snapshot_root)
    _write_json(manifest_path, manifest)
    physical._append_event(private, "enable_signal_intelligence_v2", {
        "protocol_version": PROTOCOL_VERSION,
        "measurement_tier": case_manifest["measurement_tier"],
        "system_variant": variant,
        "added_accessible_files": [
            "protocol/signal_response.schema.json",
            "protocol/signal_response.template.json",
            "SIGNAL_INTELLIGENCE_INSTRUCTIONS.md",
        ],
        "ground_truth_read": False,
    })
    physical._write_participant_context(participant, manifest)
    return run


def reveal_signal_followups(
    run_directory: str | Path,
    case_directory: str | Path,
    requests_json: str | Path,
) -> dict[str, Any]:
    return physical.reveal_followups(run_directory, case_directory, requests_json)


def finalize_signal_run(
    run_directory: str | Path,
    response_json: str | Path,
    *,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    run = Path(run_directory).resolve()
    participant = run / "participant_workspace"
    private = run / "private_run"
    manifest_path = private / "run_manifest.json"
    manifest = _read_json(manifest_path)
    if manifest.get("benchmark_profile") != BENCHMARK_PROFILE:
        raise SignalBenchmarkError("Run Signal Intelligence V2 invalide")
    if manifest.get("signal_response") is not None:
        raise SignalBenchmarkError("Le run est déjà finalisé")
    _verify_signal_protocol(manifest)
    _verify_signal_protocol_snapshot(private, manifest)
    if manifest.get("pending_blind_oracle_reviews"):
        raise SignalBenchmarkError("Une revue oracle aveugle est encore en attente")
    physical.verify_run_integrity(run, repository=repository)
    response = _read_json(response_json)
    validate_signal_response(response, expected_case_id=manifest["case_id"])
    if response["analysis_cutoff"] != manifest["analysis_cutoff"]:
        raise SignalBenchmarkError("La réponse modifie la date de coupure")
    if response["data_assessment"]["measurement_tier"] != manifest["measurement_tier"]:
        raise SignalBenchmarkError("La réponse modifie le niveau de mesure")
    evidence_commitment = _workspace_case_constraints(participant, response, manifest)
    destination = participant / "output" / "response.json"
    source = Path(response_json).resolve()
    if source != destination.resolve():
        shutil.copyfile(source, destination)
    os.chmod(destination, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    response_sha = physical.sha256_file(destination)
    completed = datetime.now(timezone.utc).isoformat()
    manifest["signal_response"] = {
        "participant_path": "output/response.json",
        "sha256": response_sha,
        "event_class": response["primary_assessment"]["event_class"],
        "abnormal_probability": response["primary_assessment"]["abnormal_probability"],
        "prognosis_issued": response["prognosis"]["issued"],
    }
    _write_json(private / "signal_evidence_commitment.json", evidence_commitment)
    manifest["signal_evidence_commitment"] = {
        "private_path": "signal_evidence_commitment.json",
        "sha256": physical.sha256_file(private / "signal_evidence_commitment.json"),
    }
    manifest["status"] = "completed_unscored_signal_v2"
    manifest["completed_at_utc"] = completed
    _write_json(manifest_path, manifest)
    result = {
        "schema_version": SCHEMA_VERSION,
        "status": "completed_unscored",
        "run_id": manifest["run_id"],
        "case_id": manifest["case_id"],
        "system_variant": manifest["system_variant"],
        "measurement_tier": manifest["measurement_tier"],
        "response_sha256": response_sha,
        "ground_truth_read": False,
        "completed_at_utc": completed,
    }
    _write_json(private / "signal_result_manifest.json", result)
    physical._append_event(private, "finalize_signal_intelligence_v2", {
        "response_sha256": response_sha,
        "ground_truth_read": False,
        "status": "completed_unscored",
        "evidence_commitment_sha256": manifest["signal_evidence_commitment"]["sha256"],
    })
    return result


def verify_signal_run(
    run_directory: str | Path,
    *,
    repository: str | Path | None = None,
) -> dict[str, Any]:
    run = Path(run_directory).resolve()
    base = physical.verify_run_integrity(run, repository=repository)
    participant = run / "participant_workspace"
    private = run / "private_run"
    manifest = _read_json(private / "run_manifest.json")
    if manifest.get("benchmark_profile") != BENCHMARK_PROFILE:
        raise SignalBenchmarkError("Profil de run incompatible")
    _verify_signal_protocol(manifest)
    _verify_signal_protocol_snapshot(private, manifest)
    for relative in (
        "SIGNAL_INTELLIGENCE_INSTRUCTIONS.md",
        "protocol/signal_response.schema.json",
        "protocol/signal_response.template.json",
    ):
        if not (participant / relative).is_file():
            raise SignalBenchmarkError(f"Ressource V2 absente: {relative}")
    finalized = manifest.get("signal_response")
    if finalized is not None:
        response = participant / finalized["participant_path"]
        if not response.is_file() or physical.sha256_file(response) != finalized["sha256"]:
            raise SignalBenchmarkError("Réponse V2 verrouillée absente ou modifiée")
        validate_signal_response(_read_json(response), expected_case_id=manifest["case_id"])
        commitment_meta = manifest.get("signal_evidence_commitment")
        if not isinstance(commitment_meta, dict):
            raise SignalBenchmarkError("Engagement des preuves V2 absent")
        commitment_path = private / commitment_meta["private_path"]
        if physical.sha256_file(commitment_path) != commitment_meta["sha256"]:
            raise SignalBenchmarkError("Engagement des preuves V2 modifié")
        commitment = _read_json(commitment_path)
        for record in commitment["evidence_files"]:
            target = participant / record["participant_path"]
            if not target.is_file() or target.stat().st_size != record["size"] or physical.sha256_file(target) != record["sha256"]:
                raise SignalBenchmarkError("Fichier de preuve V2 modifié après finalisation")
    return {
        **base,
        "benchmark_profile": BENCHMARK_PROFILE,
        "measurement_tier": manifest["measurement_tier"],
        "system_variant": manifest["system_variant"],
        "signal_finalized": finalized is not None,
    }


def _rank(ids: Sequence[str], expected: str | None) -> int | None:
    if expected is None:
        return 0 if not ids else None
    try:
        return list(ids).index(expected) + 1
    except ValueError:
        return None


def _brier_points(probability: float, outcome: bool, maximum: float) -> float:
    error = (probability - float(outcome)) ** 2
    return maximum * max(0.0, 1.0 - error)


def _temporal_points(predicted: datetime | None, expected: datetime | None) -> tuple[float, float | None]:
    if expected is None:
        return (10.0 if predicted is None else 0.0), None
    if predicted is None:
        return 0.0, None
    delta_days = abs((predicted - expected).total_seconds()) / 86400.0
    if delta_days <= 1:
        return 10.0, delta_days
    if delta_days <= 3:
        return 7.0, delta_days
    if delta_days <= 7:
        return 3.0, delta_days
    return 0.0, delta_days


def _energy_points(predicted: float | None, expected: float) -> tuple[float, float | None]:
    if expected <= 1e-9:
        if predicted is None or predicted <= 1.0:
            return 10.0, 0.0 if predicted is not None else None
        return max(0.0, 10.0 * (1.0 - min(1.0, predicted / 100.0))), None
    if predicted is None:
        return 0.0, None
    relative = abs(predicted - expected) / expected
    if relative <= 0.10:
        return 10.0, relative
    if relative <= 0.25:
        return 7.0, relative
    if relative <= 0.50:
        return 4.0, relative
    return max(0.0, 2.0 * (1.0 - min(1.0, relative - 0.5))), relative


def _signature_discovery_metrics(
    response: Mapping[str, Any],
    truth_directory: Path,
    measurement_tier: str,
) -> dict[str, Any]:
    if measurement_tier != "L2_EDGE":
        return {
            "applicable": False,
            "referenced_event_count": 0,
            "eligible_event_count": 0,
            "event_coverage": None,
            "event_asset_top1_accuracy": None,
            "event_asset_top3_accuracy": None,
            "weighted_cluster_purity": None,
        }
    event_truth_path = truth_directory / "event_sources.csv"
    with event_truth_path.open("r", encoding="utf-8", newline="") as stream:
        truth_rows = {row["event_id"]: row for row in csv.DictReader(stream)}
    referenced = 0
    top1_correct = 0
    top3_correct = 0
    purity_numerator = 0.0
    purity_denominator = 0
    for signature in response["signatures"]:
        event_ids = [reference[6:] for reference in signature["event_refs"] if reference.startswith("event:")]
        rows = [truth_rows[event_id] for event_id in event_ids if event_id in truth_rows]
        if not rows:
            continue
        candidate_ids = [item["asset_id"] for item in signature["candidate_assets"]]
        for row in rows:
            sources = set(row["source_asset_ids"].split("|"))
            referenced += 1
            top1_correct += int(bool(candidate_ids) and candidate_ids[0] in sources)
            top3_correct += int(bool(set(candidate_ids[:3]) & sources))
        dominant_counts = Counter(row["dominant_asset_id"] for row in rows)
        purity_numerator += max(dominant_counts.values())
        purity_denominator += len(rows)
    return {
        "applicable": True,
        "referenced_event_count": referenced,
        "eligible_event_count": len(truth_rows),
        "event_coverage": round(referenced / len(truth_rows), 6) if truth_rows else None,
        "event_asset_top1_accuracy": round(top1_correct / referenced, 6) if referenced else None,
        "event_asset_top3_accuracy": round(top3_correct / referenced, 6) if referenced else None,
        "weighted_cluster_purity": round(purity_numerator / purity_denominator, 6) if purity_denominator else None,
    }


def score_signal_run(run_directory: str | Path, case_directory: str | Path) -> dict[str, Any]:
    run = Path(run_directory).resolve()
    case = Path(case_directory).resolve()
    private = run / "private_run"
    participant = run / "participant_workspace"
    manifest = _read_json(private / "run_manifest.json")
    finalized = manifest.get("signal_response")
    if not finalized or manifest.get("status") != "completed_unscored_signal_v2":
        raise SignalBenchmarkError("Le run doit être finalisé avant tout accès à la vérité")
    _verify_signal_protocol(manifest)
    _verify_signal_protocol_snapshot(private, manifest)
    response_path = participant / finalized["participant_path"]
    if physical.sha256_file(response_path) != finalized["sha256"]:
        raise SignalBenchmarkError("La réponse verrouillée a été modifiée")
    validated = validate_signal_case(case)
    case_manifest = validated["manifest"]
    if case_manifest["case_id"] != manifest["case_id"]:
        raise SignalBenchmarkError("Le cas privé ne correspond pas au run")
    # Ground truth is first read here, after response lock.
    if physical.tree_commitment(case / "ground_truth") != case_manifest["ground_truth_commitment_sha256"]:
        raise SignalBenchmarkError("La vérité privée ne correspond pas à son engagement")
    truth = _read_json(case / "ground_truth" / "truth.json")
    response = _read_json(response_path)
    validate_signal_response(response, expected_case_id=manifest["case_id"])
    expected = truth["primary_event"]
    predicted = response["primary_assessment"]
    signature_metrics = _signature_discovery_metrics(
        response,
        case / "ground_truth",
        truth["measurement_tier"],
    )

    components: dict[str, float] = {}
    components["event_class"] = 15.0 if predicted["event_class"] == expected["event_class"] else (
        5.0 if predicted["event_class"] == "UNRESOLVED" else 0.0
    )
    abnormal_truth = expected["event_class"] != "NO_ABNORMALITY"
    abnormal_probability = float(predicted["abnormal_probability"])
    components["anomaly_probability"] = _brier_points(abnormal_probability, abnormal_truth, 10.0)

    asset_ids = [item["asset_id"] for item in predicted["target_assets"]]
    asset_rank = _rank(asset_ids, expected["target_asset_id"])
    if expected["target_asset_id"] is None:
        components["asset_attribution"] = 15.0 if not asset_ids else 0.0
    else:
        components["asset_attribution"] = 15.0 if asset_rank == 1 else 9.0 if asset_rank and asset_rank <= 3 else 0.0

    mechanisms = [item["mechanism_code"] for item in predicted["mechanisms"]]
    mechanism_rank = _rank(mechanisms, expected["mechanism"])
    components["mechanism"] = 15.0 if mechanism_rank == 1 else 9.0 if mechanism_rank and mechanism_rank <= 3 else 0.0

    predicted_onset = _parse_datetime(predicted["onset"], "onset", nullable=True)
    expected_onset = _parse_datetime(expected["onset"], "truth onset", nullable=True)
    components["temporal_localization"], onset_error_days = _temporal_points(predicted_onset, expected_onset)
    predicted_energy = _optional_nonnegative(predicted["observed_excess_energy_kwh"], "observed_excess_energy_kwh")
    expected_energy = float(expected["expected_excess_energy_kwh"])
    components["energy_quantification"], energy_relative_error = _energy_points(predicted_energy, expected_energy)

    prognosis = response["prognosis"]
    outcome_truth = bool(expected["outcome_within_horizon"])
    prognosis_probability = float(prognosis["outcome_within_horizon_probability"])
    prognosis_points = _brier_points(prognosis_probability, outcome_truth, 8.0)
    issued_correctly = bool(prognosis["issued"]) == outcome_truth
    expected_outcome_code = expected["outcome_code"] if outcome_truth else "NONE"
    outcome_code_correct = prognosis["outcome_code"] == expected_outcome_code
    expected_prognosis_asset = expected["target_asset_id"] if outcome_truth else None
    prognosis_target_correct = prognosis["target_asset_id"] == expected_prognosis_asset
    prognosis_points += 2.0 if issued_correctly else 0.0
    prognosis_points += 2.0 if outcome_code_correct else 0.0
    prognosis_points += 2.0 if prognosis_target_correct else 0.0
    if outcome_truth:
        outcome_at = _parse_datetime(expected["outcome_at"], "truth outcome_at")
        cutoff = _parse_datetime(truth["analysis_cutoff"], "truth analysis_cutoff")
        assert outcome_at is not None and cutoff is not None
        actual_horizon = math.ceil((outcome_at - cutoff).total_seconds() / 86400.0)
        prognosis_points += 1.0 if prognosis["horizon_days"] >= actual_horizon else 0.0
        lead_time_days = (outcome_at - cutoff).total_seconds() / 86400.0
    else:
        prognosis_points += 1.0 if prognosis["abstention_reason"].strip() else 0.0
        lead_time_days = None
    components["prognosis"] = min(15.0, prognosis_points)

    action_code = response["next_action"]["action_code"]
    dangerous = action_code in set(expected["dangerous_actions"])
    if dangerous:
        components["action_safety"] = 0.0
    elif action_code in set(expected["acceptable_actions"]):
        components["action_safety"] = 5.0
    else:
        components["action_safety"] = 2.0
    evidence_refs = predicted["evidence_refs"]
    has_adversarial = bool(response["adversarial_review"]["test_performed"].strip())
    components["evidence_trace"] = min(5.0, 1.5 * len(set(evidence_refs)) + (2.0 if has_adversarial else 0.0))

    total = round(sum(components.values()), 3)
    asset_applicable = expected["target_asset_id"] is not None
    asset_top1: bool | None = asset_rank == 1 if asset_applicable else None
    asset_top3: bool | None = bool(asset_rank and asset_rank <= 3) if asset_applicable else None
    physical_mechanism_applicable = expected["event_class"] in {
        "ENERGY_WASTE", "PROGRESSIVE_DEGRADATION", "ABRUPT_FAULT",
    }
    mechanism_top1: bool | None = mechanism_rank == 1 if physical_mechanism_applicable else None
    mechanism_top3: bool | None = (
        bool(mechanism_rank and mechanism_rank <= 3) if physical_mechanism_applicable else None
    )
    alert_at_90 = abnormal_probability >= 0.90
    expected_asset_probability = (
        next(
            (float(item["probability"]) for item in predicted["target_assets"]
             if item["asset_id"] == expected["target_asset_id"]),
            0.0,
        )
        if asset_applicable else None
    )
    expected_mechanism_probability = next(
        (float(item["probability"]) for item in predicted["mechanisms"]
         if item["mechanism_code"] == expected["mechanism"]),
        0.0,
    )
    detection_pass = (abnormal_probability >= 0.5) == abnormal_truth
    event_classification_pass = predicted["event_class"] == expected["event_class"]
    signature_pass: bool | None = None
    if signature_metrics["applicable"]:
        signature_pass = (
            int(signature_metrics["referenced_event_count"]) >= 3
            and float(signature_metrics["weighted_cluster_purity"] or 0.0) >= 0.8
        )
    asset_attribution_pass: bool | None = (
        bool(asset_top3 and float(expected_asset_probability or 0.0) >= 0.5)
        if asset_applicable else None
    )
    mechanism_pass: bool | None = (
        bool(mechanism_top3 and expected_mechanism_probability >= 0.5)
        if physical_mechanism_applicable else None
    )
    energy_quantification_pass: bool | None = (
        bool(energy_relative_error is not None and energy_relative_error <= 0.25)
        if expected_energy > 1e-9 else None
    )
    prognosis_pass: bool | None = (
        bool(
            issued_correctly
            and outcome_code_correct
            and prognosis_target_correct
            and prognosis_probability >= 0.5
        )
        if outcome_truth else None
    )
    capability_pass = (
        abnormal_truth
        and detection_pass
        and event_classification_pass
        and asset_attribution_pass is not False
        and mechanism_pass is not False
        and energy_quantification_pass is not False
        and prognosis_pass is not False
        and (signature_pass is not False)
        and not dangerous
    )
    scorecard = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_profile": BENCHMARK_PROFILE,
        "case_id": manifest["case_id"],
        "run_id": manifest["run_id"],
        "system_variant": manifest["system_variant"],
        "model": manifest["model"],
        "reasoning_effort": manifest["reasoning_effort"],
        "stage": manifest["stage"],
        "sector": truth["sector"],
        "site_kind": truth.get("site_kind", "unknown"),
        "measurement_tier": truth["measurement_tier"],
        "scenario_family_id": truth["scenario_family_id"],
        "response_sha256": finalized["sha256"],
        "ground_truth_commitment_sha256": case_manifest["ground_truth_commitment_sha256"],
        "components": {key: round(value, 3) for key, value in components.items()},
        "total_score": total,
        "critical_fail": dangerous,
        "critical_fail_reasons": ["dangerous_action_selected"] if dangerous else [],
        "metrics": {
            "truth_event_class": expected["event_class"],
            "predicted_event_class": predicted["event_class"],
            "abnormal_truth": abnormal_truth,
            "abnormal_probability": abnormal_probability,
            "alert_at_90": alert_at_90,
            "asset_rank": asset_rank,
            "asset_top1": asset_top1,
            "asset_top3": asset_top3,
            "expected_asset_probability": expected_asset_probability,
            "mechanism_rank": mechanism_rank,
            "mechanism_top1": mechanism_top1,
            "mechanism_top3": mechanism_top3,
            "expected_mechanism_probability": expected_mechanism_probability,
            "onset_error_days": onset_error_days,
            "energy_relative_error": energy_relative_error,
            "outcome_truth": outcome_truth,
            "prognosis_probability": prognosis_probability,
            "prognosis_issued": bool(prognosis["issued"]),
            "prognosis_issued_correct": issued_correctly,
            "truth_outcome_code": expected_outcome_code,
            "predicted_outcome_code": prognosis["outcome_code"],
            "outcome_code_correct": outcome_code_correct,
            "prognosis_target_correct": prognosis_target_correct,
            "truth_mechanism": expected["mechanism"],
            "lead_time_days": lead_time_days,
            "layer_passes": {
                "detection": detection_pass,
                "event_classification": event_classification_pass,
                "reproducible_signature": signature_pass,
                "asset_attribution": asset_attribution_pass,
                "physical_mechanism": mechanism_pass,
                "energy_quantification": energy_quantification_pass,
                "prognosis": prognosis_pass,
            },
            "capability_pass": capability_pass,
            "signature_discovery": signature_metrics,
        },
        "scored_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    output = private / "signal_scorecard.json"
    _write_json(output, scorecard)
    physical._append_event(private, "score_signal_intelligence_v2", {
        "scorecard_sha256": physical.sha256_file(output),
        "total_score": total,
        "critical_fail": dangerous,
        "ground_truth_read": True,
    })
    manifest["status"] = "scored_signal_v2"
    manifest["scorecard"] = {
        "private_path": "signal_scorecard.json",
        "sha256": physical.sha256_file(output),
    }
    _write_json(private / "run_manifest.json", manifest)
    return scorecard


def null_baseline_response(case_directory: str | Path) -> dict[str, Any]:
    validated = validate_signal_case(case_directory)
    manifest = validated["manifest"]
    return {
        "schema_version": SCHEMA_VERSION,
        "case_id": manifest["case_id"],
        "analysis_cutoff": manifest["analysis_cutoff"],
        "data_assessment": {
            "usable": True,
            "measurement_tier": manifest["measurement_tier"],
            "quality_issues": [],
            "limitations": ["Réponse nulle pré-enregistrée sans analyse."],
            "coverage_summary": "Non évaluée par la baseline nulle.",
        },
        "signatures": [],
        "findings": [],
        "primary_assessment": {
            "finding_id": None,
            "event_class": "NO_ABNORMALITY",
            "abnormal_probability": 0.1,
            "onset": None,
            "target_assets": [],
            "mechanisms": [{
                "mechanism_code": "NORMAL_OPERATION",
                "probability": 0.9,
                "rationale": "Baseline nulle pré-enregistrée.",
                "falsification_test": "Toute anomalie étayée réfute cette baseline.",
            }],
            "observed_excess_energy_kwh": None,
            "evidence_refs": [],
        },
        "prognosis": {
            "issued": False,
            "target_asset_id": None,
            "outcome_code": "NONE",
            "horizon_days": manifest["forecast_horizon_days"],
            "outcome_within_horizon_probability": 0.1,
            "evidence_refs": [],
            "abstention_reason": "Baseline nulle sans analyse.",
        },
        "next_action": {
            "action_code": "NO_ACTION",
            "target_asset_id": None,
            "priority": "NONE",
            "action": "Aucune action proposée par la baseline nulle.",
            "competent_person": "Responsable de site",
            "preconditions": [],
            "risks": [],
            "stop_conditions": [],
            "validation": "Non applicable.",
        },
        "overall_decision": "NO_ACTION",
        "adversarial_review": {
            "best_reason_wrong": "Une anomalie peut être présente.",
            "test_performed": "Aucun test.",
            "result": "Inconnu.",
            "decision_after_review": "Baseline inchangée.",
        },
    }


def run_null_baseline_suite(
    suite_directory: str | Path,
    runs_directory: str | Path,
    *,
    repository: str | Path,
    system_ref: str = "HEAD",
    stages: Sequence[str] = ("DEV", "HOLDOUT"),
) -> dict[str, Any]:
    """Exécute la baseline nulle pré-enregistrée via le cycle verrouillé complet.

    La réponse est construite et finalisée avant que ``score_signal_run`` ne lise
    la vérité privée. Cette fonction orchestre le benchmark ; elle n'ajoute
    aucune règle analytique ou attribution.
    """

    suite_root = Path(suite_directory).resolve()
    runs_root = Path(runs_directory).resolve()
    suite = _read_json(suite_root / "suite_manifest.json")
    selected_stages = set(stages)
    if not selected_stages or not selected_stages <= {"DEV", "HOLDOUT", "HUMAN_PARITY", "PROSPECTIVE"}:
        raise SignalBenchmarkError("stages contient une valeur inconnue")
    if runs_root.exists() and any(runs_root.iterdir()):
        raise FileExistsError(f"Le dossier de runs doit être neuf ou vide: {runs_root}")
    runs_root.mkdir(parents=True, exist_ok=True)
    completed = []
    for record in suite.get("cases", []):
        if not isinstance(record, dict) or record.get("stage") not in selected_stages:
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
            model="pre_registered_null_v2",
            reasoning_effort="none",
            variant="NULL_BASELINE",
            run_id=f"null-{record['case_id'].lower()}",
        )
        response_path = run / "participant_workspace" / "output" / "response.json"
        _write_json(response_path, null_baseline_response(case))
        finalized = finalize_signal_run(run, response_path, repository=repository)
        if finalized.get("ground_truth_read") is not False:
            raise SignalBenchmarkError("La baseline a lu la vérité avant verrouillage")
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
        "baseline": "PRE_REGISTERED_NULL_V2",
        "suite_seed": suite.get("seed"),
        "stages": sorted(selected_stages),
        "case_count": len(completed),
        "pre_truth_lock_enforced": True,
        "completed_runs": completed,
        "aggregate": aggregate,
        "limitations": [
            "Une baseline nulle mesure le plancher pré-enregistré, pas une capacité analytique.",
            "Les cas synthétiques ne constituent pas une validation terrain.",
        ],
    }
    _write_json(runs_root / "NULL_BASELINE_RESULTS.json", result)
    return result


def audit_private_suite(suite_directory: str | Path) -> dict[str, Any]:
    """Audit privé complet. Cette fonction lit volontairement la vérité des cas."""

    root = Path(suite_directory).resolve()
    suite = _read_json(root / "suite_manifest.json")
    records = suite.get("cases")
    if not isinstance(records, list) or not records:
        raise SignalBenchmarkError("Manifeste de suite vide ou invalide")
    issues: list[str] = []
    declared_count = suite.get("case_count")
    if declared_count != len(records):
        issues.append("case_count du manifeste incohérent")
    record_case_ids = [record.get("case_id") for record in records if isinstance(record, dict)]
    if len(record_case_ids) != len(records) or len(set(record_case_ids)) != len(record_case_ids):
        issues.append("identifiants de cas absents ou dupliqués dans la suite")
    snapshot = root / "protocol_snapshot"
    protocol_records = suite.get("protocol_files")
    snapshot_commitment = suite.get("protocol_snapshot_commitment_sha256")
    if not isinstance(protocol_records, list) or not isinstance(snapshot_commitment, str):
        issues.append("snapshot du protocole générateur absent du manifeste")
    elif not snapshot.is_dir() or physical.tree_commitment(snapshot) != snapshot_commitment:
        issues.append("snapshot du protocole générateur absent ou modifié")
    else:
        actual_protocol_records = []
        for record in protocol_records:
            if not isinstance(record, dict) or not isinstance(record.get("path"), str):
                issues.append("enregistrement de protocole invalide")
                continue
            target = snapshot / record["path"]
            if snapshot.resolve() not in target.resolve().parents or not target.is_file():
                issues.append(f"fichier de protocole absent: {record.get('path')}")
                continue
            actual_protocol_records.append({
                "path": record["path"],
                "size": target.stat().st_size,
                "sha256": physical.sha256_file(target),
            })
        if actual_protocol_records != protocol_records:
            issues.append("inventaire du snapshot de protocole incohérent")
    family_records: dict[str, list[tuple[dict[str, Any], dict[str, Any], Path]]] = defaultdict(list)
    class_counts: Counter[str] = Counter()
    sector_counts: Counter[str] = Counter()
    stage_counts: Counter[str] = Counter()
    outcome_count = 0
    expected_energies: list[float] = []
    public_bytes = 0
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("case_path"), str):
            issues.append("enregistrement de cas invalide")
            continue
        recorded_path = Path(record["case_path"])
        case = (recorded_path if recorded_path.is_absolute() else root / recorded_path).resolve()
        if root not in case.parents:
            issues.append(f"chemin de cas hors suite: {record.get('case_id', 'inconnu')}")
            continue
        try:
            validated = validate_signal_case(case)
        except (SignalBenchmarkError, physical.BenchmarkError) as exc:
            issues.append(f"cas public invalide ({record.get('case_id', 'inconnu')}): {exc}")
            continue
        manifest = validated["manifest"]
        if manifest["case_id"] != record["case_id"]:
            issues.append(f"case_id incohérent: {case}")
        if manifest.get("generator_sha256") != suite.get("generator_sha256"):
            issues.append(f"générateur de cas incohérent: {manifest['case_id']}")
        if physical.tree_commitment(case / "ground_truth") != manifest["ground_truth_commitment_sha256"]:
            issues.append(f"engagement vérité invalide: {manifest['case_id']}")
            continue
        truth = _read_json(case / "ground_truth" / "truth.json")
        event = truth["primary_event"]
        family = truth["scenario_family_id"]
        family_records[family].append((record, truth, case))
        class_counts[event["event_class"]] += 1
        sector_counts[truth["sector"]] += 1
        stage_counts[manifest["stage"]] += 1
        outcome_count += int(bool(event["outcome_within_horizon"]))
        expected_energies.append(float(event["expected_excess_energy_kwh"]))
        inventory_path = case / "initial_client_pack" / "02_asset_inventory.csv"
        with inventory_path.open("r", encoding="utf-8", newline="") as stream:
            assets = {row["asset_id"] for row in csv.DictReader(stream)}
        if event["target_asset_id"] is not None and event["target_asset_id"] not in assets:
            issues.append(f"actif vérité absent de l'inventaire: {manifest['case_id']}")
        cutoff = _parse_datetime(truth["analysis_cutoff"], "truth cutoff")
        outcome_at = _parse_datetime(event["outcome_at"], "truth outcome", nullable=True)
        if event["outcome_within_horizon"]:
            if outcome_at is None or cutoff is None or not cutoff < outcome_at <= cutoff + timedelta(days=manifest["forecast_horizon_days"]):
                issues.append(f"événement futur hors horizon: {manifest['case_id']}")
        elif outcome_at is not None:
            issues.append(f"date future présente sans outcome: {manifest['case_id']}")
        if event["event_class"] == "NO_ABNORMALITY" and float(event["expected_excess_energy_kwh"]) > 1e-6:
            issues.append(f"excès non nul sur cas normal: {manifest['case_id']}")
        operations_path = case / "initial_client_pack" / "04_daily_operations.csv"
        with operations_path.open("r", encoding="utf-8", newline="") as stream:
            operation_dates = {
                str(row.get("date", "")).strip()
                for row in csv.DictReader(stream)
                if str(row.get("date", "")).strip()
            }
        energy_path = case / "initial_client_pack" / "05_aggregate_energy_15min.csv"
        with energy_path.open("r", encoding="utf-8", newline="") as stream:
            energy_instants = [
                _parse_datetime(row.get("timestamp"), "timestamp énergie")
                for row in csv.DictReader(stream)
            ]
        energy_dates = {instant.date().isoformat() for instant in energy_instants if instant is not None}
        uncovered_dates = sorted(energy_dates - operation_dates)
        if uncovered_dates:
            issues.append(
                f"mesures sans contexte journalier ({manifest['case_id']}): "
                + ", ".join(uncovered_dates)
            )
        if cutoff is not None and any(
            instant is not None and instant >= cutoff for instant in energy_instants
        ):
            issues.append(f"mesure publique postérieure à la coupure: {manifest['case_id']}")
        public_bytes += sum(path.stat().st_size for path in (case / "initial_client_pack").rglob("*") if path.is_file())
        visible_text = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in (case / "initial_client_pack").rglob("*") if path.is_file()
        )
        if family in visible_text or event["private_description"] in visible_text:
            issues.append(f"fuite sémantique directe dans pack public: {manifest['case_id']}")

    for family, grouped in family_records.items():
        tiers = {record["measurement_tier"] for record, _, _ in grouped}
        if tiers != {"L0_E15", "L1_PQ1", "L2_EDGE"}:
            issues.append(f"ablation incomplète pour {family}: {sorted(tiers)}")
            continue
        energy_hashes = {
            physical.sha256_file(case / "initial_client_pack" / "05_aggregate_energy_15min.csv")
            for _, _, case in grouped
        }
        if len(energy_hashes) != 1:
            issues.append(f"signal 15 minutes non identique entre niveaux: {family}")
        pq_hashes = {
            physical.sha256_file(case / "initial_client_pack" / "06_aggregate_power_1min.csv")
            for record, _, case in grouped if record["measurement_tier"] in {"L1_PQ1", "L2_EDGE"}
        }
        if len(pq_hashes) != 1:
            issues.append(f"signal minute non identique entre L1/L2: {family}")
        reference_event = dict(grouped[0][1]["primary_event"])
        for _, truth, _ in grouped[1:]:
            if truth["primary_event"] != reference_event:
                issues.append(f"vérité physique différente entre niveaux: {family}")

    report = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_profile": BENCHMARK_PROFILE,
        "status": "valid" if not issues else "invalid",
        "truth_read": True,
        "case_count": len(records),
        "scenario_family_count": len(family_records),
        "class_counts_including_tier_repeats": dict(sorted(class_counts.items())),
        "sector_counts_including_tier_repeats": dict(sorted(sector_counts.items())),
        "stage_counts_including_tier_repeats": dict(sorted(stage_counts.items())),
        "future_outcome_cases_including_tier_repeats": outcome_count,
        "expected_excess_energy_kwh_range": {
            "minimum": min(expected_energies) if expected_energies else None,
            "maximum": max(expected_energies) if expected_energies else None,
        },
        "public_pack_bytes": public_bytes,
        "issues": issues,
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "limitations": [
            "Les cas sont synthétiques et ne valident pas une revendication terrain.",
            "Les trois niveaux d'une famille ne sont pas des observations indépendantes.",
            "L'isolation OS et la remise à zéro cognitive restent des responsabilités opérateur.",
        ],
    }
    return report


def _mean(values: Sequence[float]) -> float | None:
    return sum(values) / len(values) if values else None


def _wilson_lower(successes: int, total: int, z: float = 1.959963984540054) -> float | None:
    if total == 0:
        return None
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def _calibration(metrics: Sequence[dict[str, Any]], probability_field: str, truth_field: str) -> dict[str, Any]:
    bins = []
    ece = 0.0
    total = len(metrics)
    for lower in (0.0, 0.2, 0.4, 0.6, 0.8):
        upper = lower + 0.2
        members = [
            item for item in metrics
            if lower <= float(item[probability_field]) <= (upper if upper >= 1 else upper - 1e-12)
        ]
        if not members:
            bins.append({"lower": lower, "upper": upper, "count": 0, "mean_probability": None, "observed_rate": None})
            continue
        mean_p = sum(float(item[probability_field]) for item in members) / len(members)
        rate = sum(bool(item[truth_field]) for item in members) / len(members)
        ece += len(members) / max(1, total) * abs(mean_p - rate)
        bins.append({
            "lower": lower, "upper": upper, "count": len(members),
            "mean_probability": round(mean_p, 6), "observed_rate": round(rate, 6),
        })
    brier = _mean([
        (float(item[probability_field]) - float(bool(item[truth_field]))) ** 2
        for item in metrics
    ])
    return {"brier": None if brier is None else round(brier, 6), "ece": round(ece, 6), "bins": bins}


def aggregate_scorecards(score_directory: str | Path) -> dict[str, Any]:
    root = Path(score_directory)
    paths = sorted(root.rglob("signal_scorecard.json"))
    if not paths:
        paths = sorted(root.glob("*.json"))
    cards = []
    for path in paths:
        payload = _read_json(path)
        if payload.get("benchmark_profile") == BENCHMARK_PROFILE and "metrics" in payload:
            cards.append(payload)
    if not cards:
        raise SignalBenchmarkError("Aucune scorecard Signal Intelligence trouvée")
    metrics = [card["metrics"] for card in cards]
    def _applicable_rate(group_metrics: Sequence[dict[str, Any]], field: str) -> float | None:
        applicable = [item.get(field) for item in group_metrics if item.get(field) is not None]
        if not applicable:
            return None
        return round(sum(bool(value) for value in applicable) / len(applicable), 6)

    def binary_alert_metrics(
        group_metrics: Sequence[dict[str, Any]],
        *,
        threshold: float = 0.5,
        independent: bool = False,
    ) -> dict[str, Any]:
        tp = sum(float(item["abnormal_probability"]) >= threshold and bool(item["abnormal_truth"]) for item in group_metrics)
        fp = sum(float(item["abnormal_probability"]) >= threshold and not bool(item["abnormal_truth"]) for item in group_metrics)
        fn = sum(float(item["abnormal_probability"]) < threshold and bool(item["abnormal_truth"]) for item in group_metrics)
        tn = sum(float(item["abnormal_probability"]) < threshold and not bool(item["abnormal_truth"]) for item in group_metrics)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = (
            2 * precision * recall / (precision + recall)
            if precision is not None and recall is not None and precision + recall > 0 else None
        )
        return {
            "threshold": threshold,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
            "precision": None if precision is None else round(precision, 6),
            "precision_wilson_lower_95": (
                round(float(_wilson_lower(tp, tp + fp) or 0.0), 6)
                if independent and tp + fp else None
            ),
            "recall": None if recall is None else round(recall, 6),
            "recall_wilson_lower_95": (
                round(float(_wilson_lower(tp, tp + fn) or 0.0), 6)
                if independent and tp + fn else None
            ),
            "f1": None if f1 is None else round(f1, 6),
            "independence_status": (
                "ONE_CARD_PER_FAMILY" if independent else "CLUSTERED_REPEATS_PRESENT"
            ),
        }

    def threshold_summary(group: Sequence[dict[str, Any]], *, threshold: float = 0.90) -> dict[str, Any]:
        group_metrics = [item["metrics"] for item in group]
        alerts = [item for item in group_metrics if float(item["abnormal_probability"]) >= threshold]
        successes = sum(bool(item["abnormal_truth"]) for item in alerts)
        family_count = len({item["scenario_family_id"] for item in group})
        independent = family_count == len(group)
        return {
            "threshold": threshold,
            "alerts": len(alerts),
            "true_alerts": successes,
            "precision": round(successes / len(alerts), 6) if alerts else None,
            "precision_wilson_lower_95": (
                round(float(_wilson_lower(successes, len(alerts)) or 0.0), 6)
                if alerts and independent else None
            ),
            "coverage": round(len(alerts) / len(group), 6),
            "independent_scenario_families": family_count,
            "independence_status": (
                "ONE_CARD_PER_FAMILY" if independent else "CLUSTERED_REPEATS_PRESENT"
            ),
            "interval_limitation": (
                None if independent else
                "Wilson supprimé: plusieurs cartes partagent une même réalisation physique."
            ),
        }

    def summarize(group: Sequence[dict[str, Any]]) -> dict[str, Any]:
        group_metrics = [item["metrics"] for item in group]
        independent = len({item["scenario_family_id"] for item in group}) == len(group)
        signature_metrics = [
            item["signature_discovery"]
            for item in group_metrics
            if item.get("signature_discovery", {}).get("applicable")
        ]
        referenced_events = sum(int(item["referenced_event_count"]) for item in signature_metrics)
        eligible_events = sum(int(item["eligible_event_count"]) for item in signature_metrics)
        weighted_top1 = sum(
            float(item["event_asset_top1_accuracy"] or 0.0) * int(item["referenced_event_count"])
            for item in signature_metrics
        )
        weighted_top3 = sum(
            float(item["event_asset_top3_accuracy"] or 0.0) * int(item["referenced_event_count"])
            for item in signature_metrics
        )
        weighted_purity = sum(
            float(item["weighted_cluster_purity"] or 0.0) * int(item["referenced_event_count"])
            for item in signature_metrics
        )
        layer_names = sorted({
            name
            for item in group_metrics
            for name in item.get("layer_passes", {})
        })
        layer_summary = {}
        for name in layer_names:
            applicable = [
                item["layer_passes"][name]
                for item in group_metrics
                if name in item.get("layer_passes", {}) and item["layer_passes"][name] is not None
            ]
            layer_summary[name] = {
                "applicable_count": len(applicable),
                "pass_count": sum(bool(value) for value in applicable),
                "pass_rate": (
                    round(sum(bool(value) for value in applicable) / len(applicable), 6)
                    if applicable else None
                ),
            }
        return {
            "count": len(group),
            "mean_score": round(float(_mean([float(item["total_score"]) for item in group]) or 0.0), 3),
            "critical_fails": sum(bool(item["critical_fail"]) for item in group),
            "class_accuracy": round(sum(m["truth_event_class"] == m["predicted_event_class"] for m in group_metrics) / len(group), 6),
            "asset_top1": _applicable_rate(group_metrics, "asset_top1"),
            "asset_top3": _applicable_rate(group_metrics, "asset_top3"),
            "mechanism_top1": _applicable_rate(group_metrics, "mechanism_top1"),
            "mechanism_top3": _applicable_rate(group_metrics, "mechanism_top3"),
            "prognosis_issued_accuracy": round(
                sum(bool(m.get("prognosis_issued_correct")) for m in group_metrics) / len(group), 6
            ),
            "prognosis_outcome_code_accuracy": round(
                sum(bool(m.get("outcome_code_correct")) for m in group_metrics) / len(group), 6
            ),
            "prognosis_target_accuracy": round(
                sum(bool(m.get("prognosis_target_correct")) for m in group_metrics) / len(group), 6
            ),
            "mean_energy_relative_error": (
                None if not [m["energy_relative_error"] for m in group_metrics if m["energy_relative_error"] is not None]
                else round(float(_mean([
                    float(m["energy_relative_error"])
                    for m in group_metrics if m["energy_relative_error"] is not None
                ]) or 0.0), 6)
            ),
            "capability_pass_rate": round(sum(bool(m["capability_pass"]) for m in group_metrics) / len(group), 6),
            "layer_passes": layer_summary,
            "alert_detection": binary_alert_metrics(group_metrics, independent=independent),
            "threshold_0_90": threshold_summary(group),
            "signature_discovery": {
                "applicable_cases": len(signature_metrics),
                "referenced_events": referenced_events,
                "eligible_events": eligible_events,
                "event_coverage": round(referenced_events / eligible_events, 6) if eligible_events else None,
                "event_asset_top1_accuracy": round(weighted_top1 / referenced_events, 6) if referenced_events else None,
                "event_asset_top3_accuracy": round(weighted_top3 / referenced_events, 6) if referenced_events else None,
                "weighted_cluster_purity": round(weighted_purity / referenced_events, 6) if referenced_events else None,
            },
        }

    by_tier: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_sector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_variant: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_mechanism: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_event_class: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_stage: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_site_kind: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_tier_variant: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_system_family: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in cards:
        by_tier[card["measurement_tier"]].append(card)
        by_sector[card["sector"]].append(card)
        by_variant[card["system_variant"]].append(card)
        by_family[card["scenario_family_id"]].append(card)
        by_mechanism[card["metrics"].get("truth_mechanism", "unknown")].append(card)
        by_event_class[card["metrics"]["truth_event_class"]].append(card)
        by_stage[card["stage"]].append(card)
        by_site_kind[card.get("site_kind", "unknown")].append(card)
        by_tier_variant[(card["measurement_tier"], card["system_variant"])].append(card)
        by_system_family[(
            card["system_variant"], card["model"], card["reasoning_effort"], card["scenario_family_id"]
        )].append(card)
    frontier = []
    for (variant, model, effort, family), group in sorted(by_system_family.items()):
        passing = sorted(
            (card for card in group if card["metrics"]["capability_pass"]),
            key=lambda card: TIER_ORDER.get(card["measurement_tier"], 99),
        )
        layer_frontier = {}
        layer_names = sorted({
            name for card in group for name in card["metrics"].get("layer_passes", {})
        })
        for layer in layer_names:
            layer_passing = sorted(
                (
                    card for card in group
                    if card["metrics"].get("layer_passes", {}).get(layer) is True
                ),
                key=lambda card: TIER_ORDER.get(card["measurement_tier"], 99),
            )
            layer_frontier[layer] = (
                layer_passing[0]["measurement_tier"] if layer_passing else None
            )
        frontier.append({
            "system_variant": variant,
            "model": model,
            "reasoning_effort": effort,
            "scenario_family_id": family,
            "minimum_passing_tier": passing[0]["measurement_tier"] if passing else None,
            "minimum_passing_tier_by_layer": layer_frontier,
            "tested_tiers": sorted({card["measurement_tier"] for card in group}, key=lambda value: TIER_ORDER.get(value, 99)),
        })

    threshold_by_tier = {
        tier: threshold_summary(group) for tier, group in sorted(by_tier.items())
    }
    threshold_by_tier_variant = {
        f"{tier}|{variant}": threshold_summary(group)
        for (tier, variant), group in sorted(by_tier_variant.items())
    }

    paired_variants = []
    paired: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for card in cards:
        system_key = "|".join((
            card["system_variant"], card["model"], card["reasoning_effort"]
        ))
        paired[(card["scenario_family_id"], card["measurement_tier"])][system_key].append(
            float(card["total_score"])
        )
    for (family, tier), values in sorted(paired.items()):
        if len(values) < 2:
            continue
        means = {
            variant: float(_mean(scores) or 0.0)
            for variant, scores in sorted(
                values.items(), key=lambda item: VARIANT_ORDER.get(item[0].split("|", 1)[0], 99)
            )
        }
        record = {
            "scenario_family_id": family,
            "measurement_tier": tier,
            "system_mean_scores": {
                variant: round(mean, 3) for variant, mean in means.items()
            },
            "system_run_counts": {
                variant: len(scores) for variant, scores in sorted(
                    values.items(), key=lambda item: VARIANT_ORDER.get(item[0].split("|", 1)[0], 99)
                )
            },
            "pairwise_score_deltas": [
                {
                    "comparison": f"{right}_minus_{left}",
                    "delta": round(means[right] - means[left], 3),
                }
                for left, right in combinations(
                    sorted(
                        means,
                        key=lambda item: (VARIANT_ORDER.get(item.split("|", 1)[0], 99), item),
                    ),
                    2,
                )
            ],
        }
        paired_variants.append(record)

    stratum_summaries = {
        **{f"tier:{key}": summarize(value) for key, value in by_tier.items()},
        **{f"sector:{key}": summarize(value) for key, value in by_sector.items()},
        **{f"mechanism:{key}": summarize(value) for key, value in by_mechanism.items()},
        **{f"event_class:{key}": summarize(value) for key, value in by_event_class.items()},
        **{f"stage:{key}": summarize(value) for key, value in by_stage.items()},
        **{f"site_kind:{key}": summarize(value) for key, value in by_site_kind.items()},
    }
    worst_stratum_key = min(
        stratum_summaries,
        key=lambda key: float(stratum_summaries[key]["mean_score"]),
    )

    report = {
        "schema_version": SCHEMA_VERSION,
        "benchmark_profile": BENCHMARK_PROFILE,
        "scorecard_count": len(cards),
        "unique_case_ids": len({card["case_id"] for card in cards}),
        "unique_scenario_families": len(by_family),
        "independence_note": (
            "Les niveaux d'une même famille partagent une réalisation physique. "
            "Les intervalles de précision doivent être interprétés par niveau, où chaque famille ne compte qu'une fois."
        ),
        "overall": summarize(cards),
        "anomaly_calibration": {
            **_calibration(metrics, "abnormal_probability", "abnormal_truth"),
            "independence_warning": "Les répétitions, niveaux et variantes partageant une famille ne sont pas indépendants.",
        },
        "prognosis_calibration": {
            **_calibration(metrics, "prognosis_probability", "outcome_truth"),
            "independence_warning": "Les répétitions, niveaux et variantes partageant une famille ne sont pas indépendants.",
        },
        "calibration_by_tier_and_variant": {
            f"{tier}|{variant}": {
                "anomaly": _calibration(
                    [card["metrics"] for card in group], "abnormal_probability", "abnormal_truth"
                ),
                "prognosis": _calibration(
                    [card["metrics"] for card in group], "prognosis_probability", "outcome_truth"
                ),
                "independent_scenario_families": len({card["scenario_family_id"] for card in group}),
            }
            for (tier, variant), group in sorted(by_tier_variant.items())
        },
        "threshold_0_90": threshold_summary(cards),
        "threshold_0_90_by_tier": threshold_by_tier,
        "threshold_0_90_by_tier_and_variant": threshold_by_tier_variant,
        "by_measurement_tier": {key: summarize(value) for key, value in sorted(by_tier.items())},
        "by_sector": {key: summarize(value) for key, value in sorted(by_sector.items())},
        "by_mechanism": {f"mechanism:{key}": summarize(value) for key, value in sorted(by_mechanism.items())},
        "by_event_class": {key: summarize(value) for key, value in sorted(by_event_class.items())},
        "by_stage": {key: summarize(value) for key, value in sorted(by_stage.items())},
        "by_site_kind": {key: summarize(value) for key, value in sorted(by_site_kind.items())},
        "by_system_variant": {key: summarize(value) for key, value in sorted(by_variant.items())},
        "minimum_data_frontier": frontier,
        "paired_variant_comparisons": paired_variants,
        "worst_reported_stratum": {
            "stratum": worst_stratum_key,
            "summary": stratum_summaries[worst_stratum_key],
        },
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    return report
