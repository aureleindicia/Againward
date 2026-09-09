from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"

WEIGHTS = {
    "energy_potential": 19,
    "optimization_potential": 17,
    "probable_data_quality": 11,
    "economic_value_potential": 14,
    "commercial_accessibility": 11,
    "absence_internal_energy_expertise": 7,
    "energy_analyzer_fit": 13,
    "async_compatibility": 8,
}


def _load(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def _dump(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _priority(score: int, eligibility_gate: str | None) -> str:
    if eligibility_gate:
        return "REJECTED"
    if score >= 72:
        return "PRIORITY_A"
    if score >= 65:
        return "PRIORITY_B"
    return "PRIORITY_C"


def calculate_score(dimensions: dict[str, dict[str, Any]]) -> tuple[float, int]:
    if set(dimensions) != set(WEIGHTS):
        missing = set(WEIGHTS) - set(dimensions)
        extra = set(dimensions) - set(WEIGHTS)
        raise ValueError(f"Dimensions invalides (manquantes={missing}, en trop={extra})")

    weighted = 0.0
    for key, weight in WEIGHTS.items():
        item = dimensions[key]
        rating = item.get("rating")
        if not isinstance(rating, int) or isinstance(rating, bool) or not 0 <= rating <= 5:
            raise ValueError(f"La note {key} doit être un entier de 0 à 5")
        if not isinstance(item.get("rationale"), str) or not item["rationale"].strip():
            raise ValueError(f"La justification de {key} est obligatoire")
        weighted += rating * weight / 5
    return round(weighted, 1), round(weighted)


def score(
    raw_path: Path = DATA / "prospects_raw.json",
    assessments_path: Path = DATA / "scoring_assessments.json",
    output_path: Path = DATA / "scoring_results.json",
) -> dict[str, Any]:
    raw = _load(raw_path)
    assessments = _load(assessments_path)
    raw_by_id = {item["prospect_id"]: item for item in raw["prospects"]}
    assessment_by_id = {item["prospect_id"]: item for item in assessments["prospects"]}

    if len(raw_by_id) != len(raw["prospects"]):
        raise ValueError("Identifiants en doublon dans les prospects bruts")
    if set(raw_by_id) != set(assessment_by_id):
        raise ValueError("Chaque prospect brut doit avoir exactement une évaluation")
    if sum(WEIGHTS.values()) != 100:
        raise ValueError("Les pondérations doivent totaliser 100")

    results: list[dict[str, Any]] = []
    for prospect_id, raw_item in raw_by_id.items():
        assessment = assessment_by_id[prospect_id]
        exact_score, display_score = calculate_score(assessment["dimensions"])
        gate = assessment.get("eligibility_gate")
        if gate is not None and raw_item["prequalification_status"] != "REJECTED":
            raise ValueError(f"Exclusion incohérente avec la préqualification pour {prospect_id}")
        priority = _priority(display_score, gate)
        expected = assessment.get("expected_priority")
        if expected != priority:
            raise ValueError(
                f"Priorité incohérente pour {prospect_id}: {expected!r} au lieu de {priority!r}"
            )

        results.append({
            "prospect_id": prospect_id,
            "name": raw_item["name"],
            "sector": raw_item["sector"],
            "prequalification_status": raw_item["prequalification_status"],
            "score_exact": exact_score,
            "score_display": display_score,
            "priority": priority,
            "score_confidence": assessment["score_confidence"],
            "eligibility_gate": gate,
            "dimensions": assessment["dimensions"],
            "positive_signals": assessment["positive_signals"],
            "negative_signals": assessment["negative_signals"],
            "uncertainties": assessment["uncertainties"],
            "minimal_qualification": assessment.get("minimal_qualification"),
            "judgment": assessment["judgment"],
            "source_ids_used": assessment["source_ids_used"],
        })

    results.sort(key=lambda item: (-item["score_display"], item["prospect_id"]))
    counts = {
        priority: sum(item["priority"] == priority for item in results)
        for priority in ("PRIORITY_A", "PRIORITY_B", "PRIORITY_C", "REJECTED")
    }
    payload = {
        "schema_version": 1,
        "scored_at": assessments["scored_at"],
        "method": {
            "scale": "0 à 5 par dimension, puis somme pondérée sur 100",
            "weights": WEIGHTS,
            "display_rule": "arrondi à l'entier ; des écarts de 1 à 3 points ne sont pas significatifs",
            "priority_rules": {
                "PRIORITY_A": "72 à 100 sans critère d'exclusion",
                "PRIORITY_B": "65 à 71 sans critère d'exclusion",
                "PRIORITY_C": "0 à 64 sans critère d'exclusion ; enrichir avant contact",
                "REJECTED": "critère d'exclusion factuel, quel que soit le score brut",
            },
        },
        "counts": counts,
        "prospects": results,
        "contacting_performed": False,
    }
    _dump(output_path, payload)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Calcule et valide le scoring commercial sourcé.")
    parser.add_argument("--raw", type=Path, default=DATA / "prospects_raw.json")
    parser.add_argument("--assessments", type=Path, default=DATA / "scoring_assessments.json")
    parser.add_argument("--output", type=Path, default=DATA / "scoring_results.json")
    args = parser.parse_args()
    payload = score(args.raw, args.assessments, args.output)
    print(json.dumps(payload["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
