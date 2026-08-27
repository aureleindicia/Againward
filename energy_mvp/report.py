from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from .models import AnalysisBundle, AnalysisResult
from .positioning import REGULATORY_DISCLAIMER


def _number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "non disponible"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")


def render_markdown(result: AnalysisResult, currency: str = "EUR") -> str:
    lines = [
        "# Rapport d'analyse energetique",
        "",
        f"Source : `{result.source}`",
        "",
        "## Synthese",
        "",
        f"- Periode couverte (fin exclue) : {result.start:%d/%m/%Y} -> {result.end:%d/%m/%Y}",
        f"- Consommation totale : {_number(result.total_energy_kwh)} kWh",
        f"- Cout energetique estime : {_number(result.total_cost, 2)} {currency}",
    ]
    if result.off_production_kwh is not None:
        lines.append(
            f"- Consommation hors production : {_number(result.off_production_kwh)} kWh "
            f"({_number((result.off_production_share or 0) * 100, 1)} %)"
        )
    if result.total_production is not None:
        lines.append(f"- Production totale : {_number(result.total_production, 2)} unites")
    if result.energy_intensity is not None:
        lines.append(f"- Intensite energetique : {_number(result.energy_intensity, 3)} kWh/unite")
    if result.peak_power_kw is not None:
        lines.append(f"- Pointe de puissance : {_number(result.peak_power_kw, 1)} kW")
    covered_cost = result.metadata.get("covered_cost")
    if result.total_cost is None and covered_cost is not None:
        coverage = result.metadata.get("tariff_coverage_ratio", 0.0)
        lines.append(
            f"- Cout partiel sur {coverage:.1%} des lignes : "
            f"{_number(covered_cost, 2)} {currency} (non presente comme total)"
        )

    lines.extend(["", "## Signaux a examiner", ""])
    for finding in result.findings:
        status = "CANDIDAT" if finding.status == "candidate_signal" else finding.status.upper()
        lines.extend([
            f"### [{status} — {finding.level.upper()}] {finding.title}",
            "",
            finding.detail,
        ])
        if finding.basis:
            lines.extend(["", "Elements quantitatifs :"])
            lines.extend(f"- `{item}`" for item in finding.basis)
        if finding.limitations:
            lines.extend(["", "Limites avant confirmation :"])
            lines.extend(f"- {item}" for item in finding.limitations)
        if finding.estimated_saving_kwh is not None:
            saving = f"Surconsommation quantifiee : {_number(finding.estimated_saving_kwh)} kWh"
            if finding.estimated_saving_cost is not None:
                saving += f", soit {_number(finding.estimated_saving_cost, 2)} {currency}"
            lines.extend(["", saving + "."])
        lines.append("")

    lines.extend([
        "## Detail mensuel",
        "",
        "| Mois | Energie (kWh) | Cout | Production | Intensite |",
        "|---|---:|---:|---:|---:|",
    ])
    for item in result.monthly:
        cost = "-" if item["cost"] is None else f"{_number(item['cost'], 2)} {currency}"
        production = "-" if item["production"] is None else _number(item["production"], 2)
        intensity = "-" if item["intensity"] is None else _number(item["intensity"], 3)
        lines.append(
            f"| {item['month']} | {_number(item['energy_kwh'])} | {cost} | {production} | {intensity} |"
        )

    lines.extend([
        "",
        "## Qualite des donnees",
        "",
        f"- Lignes lues : {result.input_rows}",
        f"- Lignes analysees : {result.valid_rows}",
        f"- Lignes ecartees : {result.discarded_rows}",
        f"- Mode energie : {result.metadata['energy_mode']}",
        f"- Nature de mesure : {result.metadata.get('measurement_kind', 'non renseignee')}",
    ])
    quality = result.metadata.get("data_quality", {})
    bounds_method = result.metadata.get("coverage_bounds_method")
    if bounds_method == "inferred_nominal_interval":
        lines.append(
            "- Bornes de periode estimees avec l'intervalle nominal detecte; "
            "utiliser --interval-minutes si la derniere borne doit etre contractuelle."
        )
    frequency = quality.get("inferred_frequency_minutes")
    if frequency is not None:
        lines.append(f"- Frequence nominale : {_number(frequency, 3)} minutes")
    coverage = quality.get("coverage_ratio")
    if coverage is not None:
        lines.append(f"- Couverture temporelle estimee : {_number(coverage * 100, 1)} %")
    processing_log = quality.get("processing_log", [])
    if processing_log:
        lines.append("- Transformations tracees :")
        lines.extend(f"  - {item}" for item in processing_log)
    capabilities = result.metadata.get("capabilities", {})
    if not capabilities.get("intraday_analysis", False):
        lines.append("- Resolution insuffisante pour une analyse horaire, nocturne ou de demarrage.")
    if result.warnings:
        lines.extend("- Attention : " + warning for warning in result.warnings)
    else:
        lines.append("- Aucun avertissement de qualite detecte.")

    lines.extend([
        "",
        "## Limites",
        "",
        "Ce rapport ouvre une investigation énergétique sur données. Les signaux automatiques "
        "sont des pistes à tester avec le contexte d'exploitation, les factures, les courbes de "
        "charge et, lorsque nécessaire, un professionnel qualifié. L'investigation peut produire "
        "une conclusion autonome sur les comportements mesurés, sans prétendre identifier une cause "
        "physique que les preuves ne permettent pas d'établir.",
        "",
        REGULATORY_DISCLAIMER,
        "",
    ])
    return "\n".join(lines)


def write_json(result: AnalysisResult, path: str | Path) -> None:
    payload = asdict(result)
    payload["start"] = result.start.isoformat()
    payload["end"] = result.end.isoformat()
    Path(path).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def write_bundle_json(bundle: AnalysisBundle, path: str | Path) -> None:
    """Serialise les preuves et formats communs sans recalculer une metrique."""

    Path(path).write_text(
        json.dumps(asdict(bundle), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
