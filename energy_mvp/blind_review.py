from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .investigation import validate_follow_up_logic


DECISIONS = {
    "CONFIRME", "A_CONSERVER_AVEC_RESERVES", "INSUFFISAMMENT_ETAYE", "REJETE"
}


def validate_blind_session_review(payload: dict[str, Any], public_root: str | Path) -> None:
    """Valide la sortie d'une session Codex sans ouvrir ni connaître la vérité privée."""

    if payload.get("ground_truth_accessed") is not False:
        raise ValueError("La session aveugle doit déclarer explicitement ground_truth_accessed=false.")
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        raise ValueError("La session aveugle exige un identifiant.")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("La session aveugle ne contient aucun cas revu.")
    seen_cases: set[str] = set()
    root = Path(public_root)
    for case in cases:
        name = case.get("case_name")
        if not isinstance(name, str) or name in seen_cases:
            raise ValueError("Nom de cas absent ou dupliqué dans la review aveugle.")
        if not (root / name / "investigation_state.json").is_file():
            raise ValueError(f"Cas public inconnu dans la review: {name}.")
        seen_cases.add(name)
        hypotheses = case.get("hypotheses")
        if not isinstance(hypotheses, list):
            raise ValueError(f"{name}: hypotheses doit être une liste.")
        ids: set[str] = set()
        for hypothesis in hypotheses:
            identifier = hypothesis.get("hypothesis_id")
            if not isinstance(identifier, str) or identifier in ids:
                raise ValueError(f"{name}: identifiant d'hypothèse absent ou dupliqué.")
            ids.add(identifier)
            if hypothesis.get("decision") not in DECISIONS:
                raise ValueError(f"{name}/{identifier}: décision inconnue.")
            if not hypothesis.get("observation") or not hypothesis.get("best_reason_false"):
                raise ValueError(f"{name}/{identifier}: observation ou critique absente.")
            for field in ("type", "start", "end"):
                if not hypothesis.get(field):
                    raise ValueError(f"{name}/{identifier}: {field} est requis pour l'évaluation.")
        validate_follow_up_logic(hypotheses)
        if not isinstance(case.get("questions_to_client", []), list):
            raise ValueError(f"{name}: questions_to_client doit être une liste.")


def write_validated_blind_review(
    payload: dict[str, Any], target: str | Path, *, public_root: str | Path
) -> None:
    validate_blind_session_review(payload, public_root)
    Path(target).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
