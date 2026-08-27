#!/usr/bin/env python3
"""Tests quantitatifs adaptes a la fixture mensuelle, sans analyse infra-mensuelle."""

from __future__ import annotations

import json
from pathlib import Path
from statistics import median

from energy_mvp.analysis import analyze
from energy_mvp.io import load_data


def build_quantitative(source: str = "examples/sample_energy.csv") -> dict[str, object]:
    data = load_data(source)
    automatic = analyze(data, source=source)
    active = [item for item in data.readings if item.production is not None and item.production > 0]
    inactive = [item for item in data.readings if item.production == 0]
    intensities = {
        item.timestamp.strftime("%Y-%m"): item.energy_kwh / float(item.production)
        for item in active
        if item.production
    }
    intensity_values = list(intensities.values())
    median_intensity = median(intensity_values)
    absolute_deviations = [abs(value - median_intensity) for value in intensity_values]
    october_intensity = intensities["2026-10"]
    declared_powers = {
        item.timestamp.strftime("%Y-%m"): item.power_kw
        for item in data.readings
        if item.power_kw is not None
    }
    maximum_power_month = max(declared_powers, key=lambda month: float(declared_powers[month]))
    return {
        "schema_version": 1,
        "source": source,
        "ground_truth_read": False,
        "dataset": {
            "rows": len(data.readings),
            "coverage_start": data.coverage_start.isoformat() if data.coverage_start else None,
            "coverage_end": data.coverage_end.isoformat() if data.coverage_end else None,
            "frequency_minutes": data.quality.inferred_frequency_minutes,
            "intraday_analysis_allowed": automatic.metadata["capabilities"]["intraday_analysis"],
        },
        "tests": {
            "M01_zero_production_months": {
                "months": [item.timestamp.strftime("%Y-%m") for item in inactive],
                "count": len(inactive),
                "observed_energy_kwh": sum(item.energy_kwh for item in inactive),
                "associated_cost": sum(
                    item.energy_kwh * item.tariff_per_kwh
                    for item in inactive if item.tariff_per_kwh is not None
                ),
                "recoverable_saving_kwh": None,
                "missing_context": [
                    "heures reellement actives dans chaque mois",
                    "charge incompressible",
                    "arrets planifies et jours couverts",
                ],
            },
            "M02_declared_power": {
                "maximum_month": maximum_power_month,
                "maximum_power_kw": declared_powers[maximum_power_month],
                "median_other_months_kw": median(
                    value for month, value in declared_powers.items()
                    if month != maximum_power_month and value is not None
                ),
                "duration_available": False,
                "timestamp_granularity_supports_startup_test": False,
            },
            "M03_intensity": {
                "months_with_positive_production": len(intensities),
                "median_kwh_per_unit": median_intensity,
                "mad_kwh_per_unit": median(absolute_deviations),
                "october_kwh_per_unit": october_intensity,
                "october_delta_percent_vs_median": (
                    100 * (october_intensity - median_intensity) / median_intensity
                ),
                "minimum_kwh_per_unit": min(intensity_values),
                "maximum_kwh_per_unit": max(intensity_values),
                "validated_baseline_available": False,
                "reason": "neuf points actifs seulement; aucune validation temporelle robuste",
            },
        },
        "forbidden_tests": [
            "profil nocturne",
            "demarrage d'equipement",
            "recurrence journaliere",
            "duree du pic de puissance",
            "integration d'un exces infra-mensuel",
        ],
    }


def main() -> int:
    result = build_quantitative()
    Path("reports/monthly_quantitative_results.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print("Resultats mensuels ecrits: reports/monthly_quantitative_results.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
