from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable


UNCERTAIN_DECISIONS = {"INSUFFISAMMENT_ETAYE", "A_CONSERVER_AVEC_RESERVES"}
REQUEST_TYPES = {"question_metier", "donnee_complementaire", "test_terrain_simple"}
EFFORT_LEVELS = {"tres_faible", "faible", "modere"}


@dataclass(frozen=True, slots=True)
class InformationRequest:
    """Prochaine verification minimale, formulee pour le client et non comme une collecte vague."""

    request_id: str
    request_type: str
    ask_client: str
    why_useful: str
    information_value: str
    hypotheses_distinguished: tuple[str, ...]
    responsible_role: str
    client_effort: str
    effort_level: str
    expected_if_true: str
    priority: int = 1

    def __post_init__(self) -> None:
        text_fields = {
            "request_id": self.request_id,
            "ask_client": self.ask_client,
            "why_useful": self.why_useful,
            "information_value": self.information_value,
            "responsible_role": self.responsible_role,
            "client_effort": self.client_effort,
            "expected_if_true": self.expected_if_true,
        }
        if any(not value.strip() for value in text_fields.values()):
            raise ValueError("Une demande de poursuite doit renseigner tous ses champs.")
        if self.request_type not in REQUEST_TYPES:
            raise ValueError(f"Type de demande inconnu: {self.request_type}.")
        if self.effort_level not in EFFORT_LEVELS:
            raise ValueError(f"Niveau d'effort inconnu: {self.effort_level}.")
        if len(self.hypotheses_distinguished) < 2:
            raise ValueError("La demande doit departager au moins deux hypotheses explicites.")
        if self.priority < 1:
            raise ValueError("La priorite doit etre un entier positif.")
        vague = self.ask_client.casefold().strip(" .")
        if vague in {"plus de donnees", "davantage de donnees", "des donnees complementaires"}:
            raise ValueError("La demande au client est trop vague.")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["hypotheses_distinguished"] = list(self.hypotheses_distinguished)
        return payload


def information_request(**values: Any) -> dict[str, Any]:
    """Construit et valide une demande serialisable pour investigation.json."""

    return InformationRequest(**values).to_dict()


def validate_follow_up_logic(hypotheses: Iterable[dict[str, Any]]) -> None:
    """Refuse qu'une hypothese incertaine se termine sans prochaine verification actionnable."""

    for hypothesis in hypotheses:
        decision = hypothesis.get("decision")
        requests = hypothesis.get("follow_up_requests", [])
        if decision in UNCERTAIN_DECISIONS and not requests:
            raise ValueError(
                f"{hypothesis.get('hypothesis_id', '?')}: une decision incertaine exige "
                "une demande de poursuite minimale."
            )
        if decision not in UNCERTAIN_DECISIONS and requests:
            raise ValueError(
                f"{hypothesis.get('hypothesis_id', '?')}: aucune demande automatique n'est "
                "justifiee apres une decision tranchee."
            )
        priorities: set[int] = set()
        for payload in requests:
            request = InformationRequest(
                request_id=payload["request_id"],
                request_type=payload["request_type"],
                ask_client=payload["ask_client"],
                why_useful=payload["why_useful"],
                information_value=payload["information_value"],
                hypotheses_distinguished=tuple(payload["hypotheses_distinguished"]),
                responsible_role=payload["responsible_role"],
                client_effort=payload["client_effort"],
                effort_level=payload["effort_level"],
                expected_if_true=payload["expected_if_true"],
                priority=payload.get("priority", 1),
            )
            if request.priority in priorities:
                raise ValueError(
                    f"{hypothesis.get('hypothesis_id', '?')}: priorites de poursuite dupliquees."
                )
            priorities.add(request.priority)


def next_information_request(hypothesis: dict[str, Any]) -> dict[str, Any] | None:
    """Retourne la demande minimale a effectuer en premier, sans lancer de collecte."""

    requests = hypothesis.get("follow_up_requests", [])
    return min(requests, key=lambda item: item.get("priority", 1), default=None)
