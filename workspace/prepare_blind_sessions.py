#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from energy_mvp.blind_suite import generate_blind_case
from energy_mvp.workflow import prepare_investigation


SESSION_CASES = (
    "normal_scheduled",
    "progressive_drift",
    "legitimate_point_maintenance",
    "weather_variation",
    "legitimate_night_shift",
    "short_cycling_unknown",
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root")
    args = parser.parse_args(argv)
    root = Path(args.root)
    if root.exists():
        raise FileExistsError(f"Le dossier aveugle existe déjà: {root}")
    public = root / "public"
    private = root / "private_truth"
    public.mkdir(parents=True)
    private.mkdir()
    for index, case_name in enumerate(SESSION_CASES):
        case_public = public / case_name
        case_public.mkdir()
        source = case_public / "input.csv"
        intake_path = case_public / "intake.json"
        truth_path = private / f"{case_name}.json"
        generate_blind_case(case_name, source, intake_path, truth_path, seed=9100 + index)
        intake = json.loads(intake_path.read_text(encoding="utf-8"))
        prepare_investigation(
            source,
            case_public,
            intake=intake,
            default_tariff=0.20,
            load_options={"interval_minutes": 60},
        )
    (public / "SESSION_INSTRUCTIONS.md").write_text(
        """# Investigation Codex aveugle indépendante

Interdiction absolue : ne pas chercher, ouvrir ou mentionner un fichier de vérité terrain,
le générateur `blind_suite.py` ou tout dossier frère de `public/`.

Pour chaque sous-dossier, lire `ANALYST_BRIEF.md`, `intake.json`, les JSON préparés et, si
nécessaire, analyser `input.csv` avec des scripts créés uniquement dans votre dossier de sortie.
Les signaux automatiques ne sont pas des opportunités confirmées.

Produire un unique `review.json` avec :

- `schema_version: 1`, `session_id`, `ground_truth_accessed: false` ;
- `cases`, une entrée par cas ;
- chaque cas contient `case_name`, `hypotheses`, `questions_to_client`, `summary` ;
- chaque hypothèse contient au minimum `hypothesis_id`, `candidate_event_id` (ou null pour une
  découverte ad hoc), `type`, `start`, `end`, `observation`, `alternative_explanations`,
  `best_reason_false`, `decision`, `confidence`, `follow_up_requests` ;
- décisions autorisées : CONFIRME, A_CONSERVER_AVEC_RESERVES, INSUFFISAMMENT_ETAYE, REJETE ;
- une décision incertaine exige une demande complète avec tous les champs du schéma
  `InformationRequest`, notamment `information_value` et `responsible_role` ;
- une décision confirmée ou rejetée ne doit avoir aucune demande.

Ne jamais inventer de kWh ou de coût. Une observation peut être confirmée sans affirmer sa cause
physique ni son caractère récupérable.
""",
        encoding="utf-8",
    )
    print(public)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
