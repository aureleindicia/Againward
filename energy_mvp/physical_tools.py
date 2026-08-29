from __future__ import annotations

import math
from statistics import median
from typing import Any, Sequence


WATER_SPECIFIC_HEAT_KJ_PER_KG_K = 4.186


def _finite(value: float, *, field: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field} doit être fini.")
    return number


def _same_length(*series: Sequence[Any]) -> int:
    lengths = {len(values) for values in series}
    if len(lengths) != 1:
        raise ValueError("Les séries doivent avoir la même longueur.")
    return next(iter(lengths), 0)


def compare_specific_energy(
    *,
    before_energy_kwh: float,
    before_service_output: float,
    after_energy_kwh: float,
    after_service_output: float,
    service_unit: str,
) -> dict[str, Any]:
    """Compare l'énergie par unité de service sans décider si l'écart est un défaut."""

    values = [
        _finite(before_energy_kwh, field="before_energy_kwh"),
        _finite(before_service_output, field="before_service_output"),
        _finite(after_energy_kwh, field="after_energy_kwh"),
        _finite(after_service_output, field="after_service_output"),
    ]
    if values[0] < 0 or values[2] < 0 or values[1] <= 0 or values[3] <= 0:
        raise ValueError("L'énergie doit être positive ou nulle et le service strictement positif.")
    if not isinstance(service_unit, str) or not service_unit.strip():
        raise ValueError("L'unité de service est requise.")
    before = values[0] / values[1]
    after = values[2] / values[3]
    delta = after - before
    return {
        "before_specific_energy": before,
        "after_specific_energy": after,
        "specific_energy_unit": f"kWh/{service_unit.strip()}",
        "delta_specific_energy": delta,
        "delta_percent": 100 * delta / before if before else None,
        "decision": None,
        "limitations": [
            "Le service déclaré doit représenter la demande physique utile.",
            "Un écart d'énergie spécifique ne localise pas la cause.",
        ],
    }


def matched_operating_regime_comparison(
    *,
    before_energy_kwh: Sequence[float],
    before_service: Sequence[float],
    after_energy_kwh: Sequence[float],
    after_service: Sequence[float],
    service_tolerance_fraction: float = 0.05,
) -> dict[str, Any]:
    """Compare uniquement des paires dont le service est suffisamment proche."""

    count = _same_length(before_energy_kwh, before_service, after_energy_kwh, after_service)
    if count < 2:
        raise ValueError("Au moins deux paires de régimes sont requises.")
    if not 0 <= service_tolerance_fraction <= 1:
        raise ValueError("La tolérance de service doit être comprise entre 0 et 1.")
    pairs = []
    for index, values in enumerate(zip(before_energy_kwh, before_service, after_energy_kwh, after_service)):
        b_energy, b_service, a_energy, a_service = (
            _finite(value, field=f"pair_{index}") for value in values
        )
        if b_energy < 0 or a_energy < 0 or b_service <= 0 or a_service <= 0:
            raise ValueError("Énergies non négatives et services strictement positifs requis.")
        relative_service_gap = abs(a_service - b_service) / max(a_service, b_service)
        if relative_service_gap <= service_tolerance_fraction:
            pairs.append({
                "index": index,
                "before_specific_energy": b_energy / b_service,
                "after_specific_energy": a_energy / a_service,
                "relative_service_gap": relative_service_gap,
            })
    if not pairs:
        raise ValueError("Aucune paire ne respecte la tolérance de service.")
    deltas = [item["after_specific_energy"] - item["before_specific_energy"] for item in pairs]
    baseline = median(item["before_specific_energy"] for item in pairs)
    delta = median(deltas)
    return {
        "input_pairs": count,
        "matched_pairs": len(pairs),
        "service_tolerance_fraction": service_tolerance_fraction,
        "median_before_specific_energy": baseline,
        "median_after_specific_energy": median(item["after_specific_energy"] for item in pairs),
        "median_delta_specific_energy": delta,
        "median_delta_percent": 100 * delta / baseline if baseline else None,
        "pairs": pairs,
        "decision": None,
        "limitations": [
            "L'appariement par une seule grandeur de service ne contrôle pas le mix, l'environnement ou les consignes.",
            "Codex doit justifier la comparabilité physique des paires.",
        ],
    }


def normalized_before_after(
    *,
    observed_after_kw: Sequence[float],
    expected_after_kw: Sequence[float],
    interval_hours: Sequence[float],
) -> dict[str, Any]:
    """Mesure l'écart postérieur à une baseline préalablement figée."""

    count = _same_length(observed_after_kw, expected_after_kw, interval_hours)
    if count == 0:
        raise ValueError("La comparaison avant/après exige au moins un intervalle.")
    residual_kwh = []
    for observed, expected, hours in zip(observed_after_kw, expected_after_kw, interval_hours):
        observed_value = _finite(observed, field="observed_after_kw")
        expected_value = _finite(expected, field="expected_after_kw")
        duration = _finite(hours, field="interval_hours")
        if observed_value < 0 or expected_value < 0 or duration <= 0:
            raise ValueError("Puissances non négatives et intervalles positifs requis.")
        residual_kwh.append((observed_value - expected_value) * duration)
    return {
        "intervals": count,
        "signed_residual_energy_kwh": sum(residual_kwh),
        "positive_residual_energy_kwh": sum(max(value, 0.0) for value in residual_kwh),
        "negative_residual_energy_kwh": sum(min(value, 0.0) for value in residual_kwh),
        "median_interval_residual_kwh": median(residual_kwh),
        "decision": None,
        "limitations": [
            "La baseline doit avoir été figée avant l'intervention et validée temporellement.",
            "Une baisse après intervention renforce une hypothèse mais ne prouve pas seule son mécanisme causal.",
        ],
    }


def command_feedback_comparison(
    *,
    command_active: Sequence[bool],
    feedback_active: Sequence[bool],
    interval_hours: Sequence[float],
) -> dict[str, Any]:
    """Quantifie les quatre états commande/feedback, sans interpréter leur cause."""

    count = _same_length(command_active, feedback_active, interval_hours)
    if count == 0:
        raise ValueError("Commande/feedback exige au moins un intervalle.")
    states = {
        "command_on_feedback_on_hours": 0.0,
        "command_on_feedback_off_hours": 0.0,
        "command_off_feedback_on_hours": 0.0,
        "command_off_feedback_off_hours": 0.0,
    }
    for command, feedback, hours in zip(command_active, feedback_active, interval_hours):
        if not isinstance(command, bool) or not isinstance(feedback, bool):
            raise ValueError("Les états de commande et feedback doivent être booléens.")
        duration = _finite(hours, field="interval_hours")
        if duration <= 0:
            raise ValueError("Les intervalles doivent être positifs.")
        key = (
            "command_on_feedback_on_hours" if command and feedback
            else "command_on_feedback_off_hours" if command
            else "command_off_feedback_on_hours" if feedback
            else "command_off_feedback_off_hours"
        )
        states[key] += duration
    mismatch = states["command_on_feedback_off_hours"] + states["command_off_feedback_on_hours"]
    total = sum(states.values())
    return {
        "intervals": count,
        **states,
        "mismatch_hours": mismatch,
        "mismatch_share": mismatch / total if total else None,
        "decision": None,
        "limitations": [
            "Le feedback doit mesurer l'état physique réel, pas une copie de la commande.",
            "Une discordance peut venir d'un délai, d'une sécurité, d'un capteur ou d'un actionneur.",
        ],
    }


def duty_cycle(
    *, active: Sequence[bool], interval_hours: Sequence[float]
) -> dict[str, Any]:
    count = _same_length(active, interval_hours)
    if count == 0:
        raise ValueError("Le duty cycle exige au moins un intervalle.")
    active_hours = 0.0
    total_hours = 0.0
    starts = 0
    previous = False
    for state, hours in zip(active, interval_hours):
        if not isinstance(state, bool):
            raise ValueError("Les états doivent être booléens.")
        duration = _finite(hours, field="interval_hours")
        if duration <= 0:
            raise ValueError("Les intervalles doivent être positifs.")
        total_hours += duration
        active_hours += duration if state else 0.0
        if state and not previous:
            starts += 1
        previous = state
    return {
        "intervals": count,
        "active_hours": active_hours,
        "total_hours": total_hours,
        "duty_cycle_fraction": active_hours / total_hours,
        "observed_starts": starts,
        "decision": None,
    }


def degree_hours(
    temperatures_c: Sequence[float],
    interval_hours: Sequence[float],
    *,
    base_temperature_c: float,
    mode: str,
) -> dict[str, Any]:
    count = _same_length(temperatures_c, interval_hours)
    if count == 0:
        raise ValueError("Le calcul de degré-heures exige des mesures.")
    if mode not in {"heating", "cooling"}:
        raise ValueError("mode doit valoir heating ou cooling.")
    base = _finite(base_temperature_c, field="base_temperature_c")
    contributions = []
    for temperature, hours in zip(temperatures_c, interval_hours):
        temp = _finite(temperature, field="temperature_c")
        duration = _finite(hours, field="interval_hours")
        if duration <= 0:
            raise ValueError("Les intervalles doivent être positifs.")
        delta = max(base - temp, 0.0) if mode == "heating" else max(temp - base, 0.0)
        contributions.append(delta * duration)
    return {
        "mode": mode,
        "base_temperature_c": base,
        "degree_hours_c_h": sum(contributions),
        "intervals": count,
        "decision": None,
        "limitations": ["La température de base doit être justifiée pour le site et le service étudié."],
    }


def pressure_decay(
    *,
    start_pressure_gauge_bar: float,
    end_pressure_gauge_bar: float,
    duration_minutes: float,
    isolated_volume_m3: float | None = None,
    atmospheric_pressure_bar: float = 1.01325,
) -> dict[str, Any]:
    """Mesure une décroissance; l'estimation de débit exige un volume isolé connu."""

    start = _finite(start_pressure_gauge_bar, field="start_pressure_gauge_bar")
    end = _finite(end_pressure_gauge_bar, field="end_pressure_gauge_bar")
    duration = _finite(duration_minutes, field="duration_minutes")
    atmospheric = _finite(atmospheric_pressure_bar, field="atmospheric_pressure_bar")
    if start < 0 or end < 0 or end > start or duration <= 0 or atmospheric <= 0:
        raise ValueError("Pressions et durée invalides pour une décroissance.")
    drop = start - end
    estimated_free_air = None
    estimated_rate = None
    if isolated_volume_m3 is not None:
        volume = _finite(isolated_volume_m3, field="isolated_volume_m3")
        if volume <= 0:
            raise ValueError("Le volume isolé doit être strictement positif.")
        estimated_free_air = volume * drop / atmospheric
        estimated_rate = estimated_free_air / duration
    return {
        "pressure_drop_bar": drop,
        "decay_rate_bar_per_min": drop / duration,
        "estimated_free_air_loss_m3": estimated_free_air,
        "estimated_free_air_loss_m3_per_min": estimated_rate,
        "decision": None,
        "assumptions": [
            "Le tronçon est réellement isolé et aucun consommateur légitime ne fonctionne.",
            "La température et le volume gazeux restent suffisamment stables.",
            "Le volume total est connu si un débit équivalent est calculé.",
        ],
        "safety": "Le test d'isolement et toute manœuvre sur réseau pressurisé relèvent d'une personne compétente.",
    }


def sensible_heat_energy(
    *,
    mass_kg: float,
    temperature_change_c: float,
    specific_heat_kj_per_kg_k: float,
    conversion_efficiency: float | None = None,
) -> dict[str, Any]:
    mass = _finite(mass_kg, field="mass_kg")
    delta = _finite(temperature_change_c, field="temperature_change_c")
    heat_capacity = _finite(specific_heat_kj_per_kg_k, field="specific_heat_kj_per_kg_k")
    if mass < 0 or delta < 0 or heat_capacity <= 0:
        raise ValueError(
            "Masse et variation de température non négatives, capacité thermique positive requises."
        )
    useful = mass * heat_capacity * delta / 3600.0
    input_energy = None
    if conversion_efficiency is not None:
        efficiency = _finite(conversion_efficiency, field="conversion_efficiency")
        if not 0 < efficiency <= 1:
            raise ValueError("Le rendement doit être dans ]0, 1].")
        input_energy = useful / efficiency
    return {
        "useful_sensible_heat_kwh": useful,
        "input_energy_kwh": input_energy,
        "conversion_efficiency_assumption": conversion_efficiency,
        "decision": None,
        "limitations": [
            "Le calcul ne couvre ni chaleur latente, ni pertes, ni changement de phase.",
            "La masse et le delta de température doivent représenter le service réellement rendu.",
        ],
    }


def heat_recovery_balance(
    *,
    cold_side_mass_kg: float,
    cold_inlet_c: float,
    cold_outlet_c: float,
    hot_side_mass_kg: float | None = None,
    hot_inlet_c: float | None = None,
    hot_outlet_c: float | None = None,
    specific_heat_kj_per_kg_k: float = WATER_SPECIFIC_HEAT_KJ_PER_KG_K,
) -> dict[str, Any]:
    cold = sensible_heat_energy(
        mass_kg=cold_side_mass_kg,
        temperature_change_c=cold_outlet_c - cold_inlet_c,
        specific_heat_kj_per_kg_k=specific_heat_kj_per_kg_k,
    )["useful_sensible_heat_kwh"]
    hot = None
    imbalance = None
    if any(value is not None for value in (hot_side_mass_kg, hot_inlet_c, hot_outlet_c)):
        if any(value is None for value in (hot_side_mass_kg, hot_inlet_c, hot_outlet_c)):
            raise ValueError("Le bilan côté chaud exige masse, entrée et sortie ensemble.")
        hot = sensible_heat_energy(
            mass_kg=float(hot_side_mass_kg),
            temperature_change_c=float(hot_inlet_c) - float(hot_outlet_c),
            specific_heat_kj_per_kg_k=specific_heat_kj_per_kg_k,
        )["useful_sensible_heat_kwh"]
        imbalance = cold - hot
    return {
        "cold_side_recovered_heat_kwh": cold,
        "hot_side_released_heat_kwh": hot,
        "heat_balance_difference_kwh": imbalance,
        "decision": None,
        "limitations": [
            "Une performance exige des cycles comparables, des débits ou masses synchronisés et des sondes fiables.",
            "Le bilan ne prouve pas pourquoi la récupération a changé.",
        ],
    }


def fan_pump_affinity_scenario(
    *,
    reference_speed: float,
    scenario_speed: float,
    reference_power_kw: float,
) -> dict[str, Any]:
    """Calcule un scénario de lois d'affinité avec avertissements obligatoires."""

    reference = _finite(reference_speed, field="reference_speed")
    scenario = _finite(scenario_speed, field="scenario_speed")
    power = _finite(reference_power_kw, field="reference_power_kw")
    if reference <= 0 or scenario <= 0 or power < 0:
        raise ValueError("Vitesses positives et puissance non négative requises.")
    ratio = scenario / reference
    return {
        "speed_ratio": ratio,
        "idealized_flow_ratio": ratio,
        "idealized_pressure_or_head_ratio": ratio ** 2,
        "idealized_power_ratio": ratio ** 3,
        "idealized_scenario_power_kw": power * ratio ** 3,
        "decision": None,
        "warnings": [
            "Scénario valide seulement pour la même machine, le même fluide et un réseau suivant approximativement la même courbe.",
            "La loi de cube ne doit pas être appliquée aveuglément aux charges statiques, étranglements, rendements variables ou limites de variateur.",
            "Aucune réduction de vitesse n'est recommandée sans contraintes de débit, pression, qualité, sécurité et procédé.",
        ],
    }
