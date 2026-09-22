from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from againward.core.workflow import prepare_investigation
from againward.entrypoints import get_domain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prépare une investigation Againward avec domaine explicite pour Codex."
    )
    parser.add_argument("--domain", default="energy", help="Domaine explicite (energy par défaut historique)")
    parser.add_argument("--profile", help="Profil Rental optionnel : generic ou construction")
    parser.add_argument("source", help="Energy: CSV/XLSX ; Rental: extraction canonique JSON")
    parser.add_argument("--output-dir", required=True, help="Dossier de travail isolé")
    parser.add_argument("--intake", help="Questionnaire intake.json complété")
    parser.add_argument("--price-per-kwh", type=float)
    parser.add_argument("--date-column")
    parser.add_argument("--energy-column")
    parser.add_argument("--power-column")
    parser.add_argument("--production-column")
    parser.add_argument("--production-active-column")
    parser.add_argument("--temperature-column")
    parser.add_argument("--shift-column")
    parser.add_argument("--product-type-column")
    parser.add_argument("--tariff-column")
    parser.add_argument("--energy-unit", choices=("wh", "kwh", "mwh"))
    parser.add_argument("--power-unit", choices=("w", "kw", "mw"))
    parser.add_argument("--energy-mode", choices=("auto", "interval", "cumulative"), default="auto")
    parser.add_argument("--interval-minutes", type=float)
    parser.add_argument("--timestamp-position", choices=("auto", "start", "end"), default="auto")
    parser.add_argument("--site-timezone", help="Fuseau IANA; remplace celui de intake.json")
    parser.add_argument(
        "--evidence-plane-mode",
        choices=("preferred", "shadow", "legacy"),
        default="preferred",
        help="Migration Stage 4; legacy constitue le rollback immédiat.",
    )
    parser.add_argument("--maximum-auxiliary-fields", type=int, default=128)
    parser.add_argument("--maximum-auxiliary-value-characters", type=int, default=4096)
    return parser


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments and arguments[0] == "documents":
        from againward.documents.cli import main as document_main
        return document_main(arguments[1:])
    args = build_parser().parse_args(argv)
    try:
        intake = (
            json.loads(Path(args.intake).read_text(encoding="utf-8"))
            if args.intake else None
        )
        load_options = {
            name: value for name, value in {
                "date_column": args.date_column,
                "energy_column": args.energy_column,
                "power_column": args.power_column,
                "production_column": args.production_column,
                "production_active_column": args.production_active_column,
                "temperature_column": args.temperature_column,
                "shift_column": args.shift_column,
                "product_type_column": args.product_type_column,
                "tariff_column": args.tariff_column,
                "energy_unit": args.energy_unit,
                "power_unit": args.power_unit,
                "energy_mode": args.energy_mode,
                "interval_minutes": args.interval_minutes,
                "timestamp_position": args.timestamp_position,
                "site_timezone": args.site_timezone,
                "maximum_auxiliary_fields": args.maximum_auxiliary_fields,
                "maximum_auxiliary_value_characters": args.maximum_auxiliary_value_characters,
            }.items() if value is not None
        }
        state = prepare_investigation(
            args.source,
            args.output_dir,
            domain=get_domain(args.domain, profile=args.profile), intake=intake,
            options={"default_tariff": args.price_per_kwh, "load_options": load_options},
            evidence_plane_mode=args.evidence_plane_mode,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"Erreur: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "status": state["status"],
        "output_dir": args.output_dir,
        "candidate_signals": len(state.get("candidate_detection", {}).get("events", [])),
        "missing_critical": len(state.get("intake_assessment", {}).get("missing_critical", [])),
    }, ensure_ascii=False, indent=2))
    return 0
