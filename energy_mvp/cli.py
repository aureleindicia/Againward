from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .analysis import analyze
from .io import DataError, load_data
from .positioning import SERVICE_TITLE
from .privacy import assert_source_approved_for_analysis, case_root_for_path, privacy_requirement
from .report import render_markdown, write_json


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=f"{SERVICE_TITLE}, locale, à partir de données industrielles CSV/XLSX."
    )
    parser.add_argument("source", help="Fichier .csv ou .xlsx a analyser")
    parser.add_argument("--output", "-o", help="Rapport Markdown (defaut: reports/<fichier>-rapport.md)")
    parser.add_argument("--json-output", help="Export JSON structure optionnel")
    parser.add_argument("--date-column", help="Nom exact de la colonne date/heure")
    parser.add_argument("--energy-column", help="Nom exact de la colonne energie")
    parser.add_argument("--production-column", help="Nom exact de la colonne production")
    parser.add_argument("--production-active-column", help="Colonne indiquant l'activite de production")
    parser.add_argument("--temperature-column", help="Colonne de temperature exterieure")
    parser.add_argument("--shift-column", help="Colonne de poste/equipe")
    parser.add_argument("--product-type-column", help="Colonne de type de produit")
    parser.add_argument("--tariff-column", help="Nom exact de la colonne tarif")
    parser.add_argument("--power-column", help="Nom exact de la colonne puissance")
    parser.add_argument(
        "--energy-unit", choices=("wh", "kwh", "mwh"),
        help="Unite de la colonne energie si elle n'apparait pas dans son nom",
    )
    parser.add_argument(
        "--power-unit", choices=("w", "kw", "mw"),
        help="Unite de la colonne puissance si elle n'apparait pas dans son nom",
    )
    parser.add_argument(
        "--energy-mode", choices=("auto", "interval", "cumulative"), default="auto",
        help="Nature de la colonne energie (defaut: detection automatique)",
    )
    parser.add_argument(
        "--interval-minutes", type=float,
        help=(
            "Duree explicite d'une mesure de puissance en minutes. Requise pour une "
            "mesure isolee ou des timestamps de puissance irreguliers."
        ),
    )
    parser.add_argument(
        "--timestamp-position",
        choices=("auto", "start", "end"),
        default="auto",
        help=(
            "Position du timestamp dans l'intervalle. Auto utilise debut pour energie/puissance "
            "et fin pour un index cumulatif."
        ),
    )
    parser.add_argument(
        "--site-timezone",
        help="Fuseau IANA des heures locales sans décalage (exemple: Europe/Paris)",
    )
    parser.add_argument(
        "--price-per-kwh", "--default-tariff", dest="default_tariff", type=float,
        help="Tarif par kWh si absent des donnees",
    )
    parser.add_argument("--currency", default="EUR", help="Devise affichee (defaut: EUR)")
    parser.add_argument(
        "--production-threshold", type=float, default=0.0,
        help="Production sous laquelle une periode est consideree a l'arret",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        case_root = case_root_for_path(args.source)
        real_case = bool(
            case_root is not None and privacy_requirement(case_root).get("required")
        )
        output = Path(args.output) if args.output else (
            case_root / "outputs" / f"{Path(args.source).stem}-rapport.md"
            if real_case and case_root is not None
            else Path("reports") / f"{Path(args.source).stem}-rapport.md"
        )
        json_path = Path(args.json_output) if args.json_output else None
        assert_source_approved_for_analysis(args.source, output_directory=output)
        if json_path is not None:
            assert_source_approved_for_analysis(args.source, output_directory=json_path)
        loaded = load_data(
            args.source,
            date_column=args.date_column,
            energy_column=args.energy_column,
            production_column=args.production_column,
            production_active_column=args.production_active_column,
            temperature_column=args.temperature_column,
            shift_column=args.shift_column,
            product_type_column=args.product_type_column,
            tariff_column=args.tariff_column,
            power_column=args.power_column,
            energy_mode=args.energy_mode,
            interval_minutes=args.interval_minutes,
            energy_unit=args.energy_unit,
            power_unit=args.power_unit,
            timestamp_position=args.timestamp_position,
            site_timezone=args.site_timezone,
        )
        result = analyze(
            loaded,
            source=args.source,
            default_tariff=args.default_tariff,
            production_threshold=args.production_threshold,
        )
        report = render_markdown(result, currency=args.currency)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(report, encoding="utf-8")
        if json_path is not None:
            json_path.parent.mkdir(parents=True, exist_ok=True)
            write_json(result, json_path)
    except (DataError, ValueError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Erreur de fichier: {exc}", file=sys.stderr)
        return 2

    print(report)
    print(f"\nRapport enregistre: {output}", file=sys.stderr)
    if args.json_output:
        print(f"Export JSON enregistre: {args.json_output}", file=sys.stderr)
    return 0
