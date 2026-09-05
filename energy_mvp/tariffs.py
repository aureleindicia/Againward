from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from typing import Any, Sequence

from .models import Reading


def _minute(value: str) -> int:
    try:
        parsed = time.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Heure tarifaire invalide: {value!r}.") from exc
    if parsed.second or parsed.microsecond:
        raise ValueError("Une plage tarifaire s'exprime à la minute, sans secondes.")
    return parsed.hour * 60 + parsed.minute


@dataclass(frozen=True, slots=True)
class TimeOfUsePeriod:
    name: str
    weekdays: tuple[int, ...]
    start: str
    end: str
    price_per_kwh: float

    def __post_init__(self) -> None:
        if not self.name.strip():
            raise ValueError("Une plage tarifaire exige un nom.")
        if not self.weekdays or any(day not in range(7) for day in self.weekdays):
            raise ValueError("weekdays doit contenir des jours 0=lundi à 6=dimanche.")
        if len(set(self.weekdays)) != len(self.weekdays):
            raise ValueError("Une plage tarifaire contient un jour dupliqué.")
        if self.price_per_kwh < 0:
            raise ValueError("Un prix par kWh ne peut pas être négatif.")
        if _minute(self.start) == _minute(self.end):
            raise ValueError("Une plage tarifaire ne peut pas couvrir zéro heure.")

    def matches(self, weekday: int, minute: int) -> bool:
        start, end = _minute(self.start), _minute(self.end)
        if start < end:
            return weekday in self.weekdays and start <= minute < end
        if minute >= start:
            return weekday in self.weekdays
        previous_day = (weekday - 1) % 7
        return minute < end and previous_day in self.weekdays


@dataclass(frozen=True, slots=True)
class TariffPlan:
    currency: str = "EUR"
    default_price_per_kwh: float | None = None
    time_of_use: tuple[TimeOfUsePeriod, ...] = ()
    demand_charge_per_kw_month: float | None = None

    def __post_init__(self) -> None:
        if not self.currency.strip():
            raise ValueError("La devise tarifaire est requise.")
        if self.default_price_per_kwh is not None and self.default_price_per_kwh < 0:
            raise ValueError("Le prix par défaut ne peut pas être négatif.")
        if self.demand_charge_per_kw_month is not None and self.demand_charge_per_kw_month < 0:
            raise ValueError("La facturation de puissance ne peut pas être négative.")
        if (
            self.default_price_per_kwh is None
            and not self.time_of_use
            and self.demand_charge_per_kw_month is None
        ):
            raise ValueError("Le plan tarifaire ne contient aucun prix.")
        for weekday in range(7):
            for minute in range(1440):
                matching = [period.name for period in self.time_of_use if period.matches(weekday, minute)]
                if len(matching) > 1:
                    raise ValueError(
                        "Plages tarifaires chevauchantes: " + ", ".join(matching) + "."
                    )


def tariff_plan_from_dict(payload: dict[str, Any]) -> TariffPlan:
    periods = tuple(
        TimeOfUsePeriod(
            name=item["name"],
            weekdays=tuple(item["weekdays"]),
            start=item["start"],
            end=item["end"],
            price_per_kwh=float(item["price_per_kwh"]),
        )
        for item in payload.get("time_of_use_periods", [])
    )
    demand = payload.get("demand_charge_per_kw_month")
    default = payload.get("flat_price_per_kwh")
    return TariffPlan(
        currency=str(payload.get("currency") or "EUR"),
        default_price_per_kwh=float(default) if default is not None else None,
        time_of_use=periods,
        demand_charge_per_kw_month=float(demand) if demand is not None else None,
    )


def calculate_tariff_cost(
    readings: Sequence[Reading], plan: TariffPlan
) -> dict[str, Any]:
    """Calcule énergie et pointe sans supposer que le coût est récupérable."""

    months: dict[str, dict[str, Any]] = {}
    for reading in readings:
        local = reading.operational_timestamp
        month = local.strftime("%Y-%m")
        bucket = months.setdefault(month, {
            "energy_kwh": 0.0,
            "priced_energy_kwh": 0.0,
            "unpriced_energy_kwh": 0.0,
            "energy_charge": 0.0,
            "peak_kw": None,
            "demand_charge": None,
            "total_cost": None,
        })
        bucket["energy_kwh"] += reading.energy_kwh
        minute = local.hour * 60 + local.minute
        matches = [
            period for period in plan.time_of_use
            if period.matches(local.weekday(), minute)
        ]
        price = matches[0].price_per_kwh if matches else plan.default_price_per_kwh
        if price is None:
            bucket["unpriced_energy_kwh"] += reading.energy_kwh
        else:
            bucket["priced_energy_kwh"] += reading.energy_kwh
            bucket["energy_charge"] += reading.energy_kwh * price
        power = reading.power_kw
        if power is None and reading.interval_hours:
            power = reading.energy_kwh / reading.interval_hours
        if power is not None:
            bucket["peak_kw"] = max(float(bucket["peak_kw"] or 0.0), power)
    for bucket in months.values():
        if plan.demand_charge_per_kw_month is not None and bucket["peak_kw"] is not None:
            bucket["demand_charge"] = (
                bucket["peak_kw"] * plan.demand_charge_per_kw_month
            )
        complete_energy = bucket["unpriced_energy_kwh"] <= 1e-9
        if complete_energy:
            bucket["total_cost"] = bucket["energy_charge"] + (bucket["demand_charge"] or 0.0)
    total_energy_charge = sum(item["energy_charge"] for item in months.values())
    total_demand_charge = sum(item["demand_charge"] or 0.0 for item in months.values())
    unpriced = sum(item["unpriced_energy_kwh"] for item in months.values())
    return {
        "currency": plan.currency,
        "months": months,
        "energy_charge": total_energy_charge,
        "demand_charge": total_demand_charge if plan.demand_charge_per_kw_month is not None else None,
        "total_cost": total_energy_charge + total_demand_charge if unpriced <= 1e-9 else None,
        "unpriced_energy_kwh": unpriced,
        "complete_energy_cost_coverage": unpriced <= 1e-9,
        "recoverable_saving": None,
    }
