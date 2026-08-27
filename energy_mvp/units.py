from __future__ import annotations


ENERGY_TO_KWH = {
    "wh": 0.001,
    "kwh": 1.0,
    "mwh": 1000.0,
}

POWER_TO_KW = {
    "w": 0.001,
    "kw": 1.0,
    "mw": 1000.0,
}


def convert_energy_to_kwh(value: float, unit: str) -> float:
    """Convertit une energie source vers l'unite interne kWh."""

    try:
        factor = ENERGY_TO_KWH[unit.lower()]
    except KeyError as exc:
        raise ValueError(f"Unite d'energie non prise en charge: {unit}") from exc
    return value * factor


def convert_power_to_kw(value: float, unit: str) -> float:
    """Convertit une puissance source vers l'unite interne kW."""

    try:
        factor = POWER_TO_KW[unit.lower()]
    except KeyError as exc:
        raise ValueError(f"Unite de puissance non prise en charge: {unit}") from exc
    return value * factor
