from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DIRECTIONS = {"increase", "decrease", "no_material_change"}


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _read_value(payload: Any, dotted_path: str) -> Any:
    value = payload
    for part in dotted_path.split("."):
        if isinstance(value, list):
            value = value[int(part)]
        else:
            value = value[part]
    return value


def validate_field_test_plan(plan: dict[str, Any], *, base_directory: str | Path) -> None:
    required_text = (
        "test_id", "hypothesis_id", "action", "owner_role", "client_effort",
        "decision_if_confirmed", "decision_if_refuted",
    )
    if any(not str(plan.get(name, "")).strip() for name in required_text):
        raise ValueError("Le test terrain doit renseigner identité, action, responsable et décisions.")
    if not plan.get("safety_preconditions") or not plan.get("stop_conditions"):
        raise ValueError("Le test terrain exige des préconditions de sécurité et des conditions d'arrêt.")
    prediction = plan.get("prediction") or {}
    if prediction.get("expected_direction") not in DIRECTIONS:
        raise ValueError("La direction attendue du test terrain est absente ou invalide.")
    for name in ("metric", "unit", "quantitative_source", "value_path", "comparison_method"):
        if not str(prediction.get(name, "")).strip():
            raise ValueError(f"Prédiction terrain incomplète: {name} est requis.")
    expected = prediction.get("expected_effect")
    if not isinstance(expected, (int, float)):
        raise ValueError("L'effet attendu doit être un nombre calculé par Python.")
    source = Path(base_directory) / prediction["quantitative_source"]
    if not source.is_file():
        raise ValueError(f"Source quantitative introuvable: {source}.")
    evidence = json.loads(source.read_text(encoding="utf-8"))
    source_value = _read_value(evidence, prediction["value_path"])
    if not isinstance(source_value, (int, float)) or abs(float(source_value) - float(expected)) > 1e-9:
        raise ValueError(
            "L'effet attendu ne correspond pas exactement à la source quantitative déclarée."
        )


def preregister_field_test(
    plan: dict[str, Any], target: str | Path, *, base_directory: str | Path
) -> dict[str, Any]:
    """Verrouille une prédiction avant test; refuse tout écrasement ultérieur."""

    target_path = Path(target)
    if target_path.exists():
        raise FileExistsError(f"La prédiction pré-enregistrée existe déjà: {target_path}.")
    validate_field_test_plan(plan, base_directory=base_directory)
    locked_hash = hashlib.sha256(_canonical(plan)).hexdigest()
    registration = {
        "schema_version": 1,
        "status": "preregistered_before_field_test",
        "registered_at_utc": datetime.now(timezone.utc).isoformat(),
        "locked_plan_sha256": locked_hash,
        "plan": plan,
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(registration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return registration


def verify_registration(registration: dict[str, Any]) -> None:
    expected = hashlib.sha256(_canonical(registration["plan"])).hexdigest()
    if expected != registration.get("locked_plan_sha256"):
        raise ValueError("La prédiction pré-enregistrée a été modifiée après verrouillage.")


def record_field_test_outcome(
    registration_path: str | Path,
    outcome: dict[str, Any],
    target: str | Path,
) -> dict[str, Any]:
    """Compare après test les moyennes mesurées à la prédiction verrouillée."""

    target_path = Path(target)
    if target_path.exists():
        raise FileExistsError(f"Le résultat terrain existe déjà: {target_path}.")
    registration = json.loads(Path(registration_path).read_text(encoding="utf-8"))
    verify_registration(registration)
    baseline = outcome.get("baseline_mean")
    observed = outcome.get("test_mean")
    if not isinstance(baseline, (int, float)) or not isinstance(observed, (int, float)):
        raise ValueError("Le résultat exige baseline_mean et test_mean numériques.")
    prediction = registration["plan"]["prediction"]
    if outcome.get("metric") != prediction["metric"] or outcome.get("unit") != prediction["unit"]:
        raise ValueError("La métrique observée ne correspond pas à la prédiction verrouillée.")
    delta = float(observed) - float(baseline)
    expected_direction = prediction["expected_direction"]
    direction_observed = (
        "increase" if delta > 0 else "decrease" if delta < 0 else "no_material_change"
    )
    comparison = {
        "schema_version": 1,
        "status": "field_test_compared_to_preregistration",
        "registration_sha256": registration["locked_plan_sha256"],
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "outcome": outcome,
        "computed": {
            "observed_delta": delta,
            "direction_observed": direction_observed,
            "direction_matches_prediction": direction_observed == expected_direction,
            "expected_effect": prediction["expected_effect"],
            "effect_error": delta - float(prediction["expected_effect"]),
        },
    }
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_text(
        json.dumps(comparison, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return comparison
