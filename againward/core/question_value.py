"""Deterministic question-partition utility; no posterior or domain attribution."""
from __future__ import annotations
import math
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

@dataclass(frozen=True, slots=True)
class MicroQuestion:
    question_id: str
    prompt: str
    answer_by_candidate: dict[str, str]
    effort: float
    availability: float
    reliability: float
    source_class: str = "operator_question"

    def __post_init__(self) -> None:
        if not self.question_id or not self.prompt or len(set(self.answer_by_candidate.values())) < 1:
            raise ValueError("Question incomplète.")
        if self.effort <= 0:
            raise ValueError("L'effort doit être strictement positif.")
        if not 0 <= self.availability <= 1 or not 0 <= self.reliability <= 1:
            raise ValueError("Disponibilité et fiabilité doivent être dans [0, 1].")


def _entropy(probabilities: Iterable[float]) -> float:
    return -sum(value * math.log2(value) for value in probabilities if value > 0)


def rank_micro_questions(
    candidate_ids: Sequence[str],
    questions: Sequence[MicroQuestion],
    *,
    strategy: str = "reliability_adjusted_voi",
) -> list[dict[str, Any]]:
    """Classe des partitions d'hypothèses sans inventer de posterior d'actif."""

    hypotheses = tuple(dict.fromkeys(candidate_ids))
    if len(hypotheses) < 2:
        return []
    if strategy not in {"information_gain", "expected_elimination", "reliability_adjusted_voi"}:
        raise ValueError("Stratégie de micro-question inconnue.")
    prior_entropy = math.log2(len(hypotheses))
    ranked: list[dict[str, Any]] = []
    for question in questions:
        missing = set(hypotheses) - set(question.answer_by_candidate)
        if missing:
            raise ValueError(
                f"{question.question_id}: réponses manquantes pour " + ", ".join(sorted(missing))
            )
        groups: dict[str, list[str]] = {}
        for candidate in hypotheses:
            groups.setdefault(question.answer_by_candidate[candidate], []).append(candidate)
        expected_entropy = sum(
            len(group) / len(hypotheses) * math.log2(len(group))
            for group in groups.values()
        )
        information_gain = prior_entropy - expected_entropy
        expected_remaining = sum(len(group) ** 2 for group in groups.values()) / len(hypotheses)
        expected_elimination = len(hypotheses) - expected_remaining
        if strategy == "information_gain":
            utility = information_gain
        elif strategy == "expected_elimination":
            utility = expected_elimination
        else:
            utility = information_gain * question.availability * question.reliability / question.effort
        ranked.append(
            {
                "question_id": question.question_id,
                "prompt": question.prompt,
                "strategy": strategy,
                "prior_entropy_bits": round(prior_entropy, 6),
                "expected_entropy_bits": round(expected_entropy, 6),
                "information_gain_bits": round(information_gain, 6),
                "expected_hypothesis_elimination": round(expected_elimination, 6),
                "effort": question.effort,
                "availability": question.availability,
                "reliability": question.reliability,
                "utility": round(utility, 6),
                "discriminating": len(groups) > 1,
                "answer_groups": {answer: sorted(group) for answer, group in sorted(groups.items())},
            }
        )
    return sorted(ranked, key=lambda item: (-item["utility"], item["question_id"]))


