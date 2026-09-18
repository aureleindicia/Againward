"""Small explicit domain contract; implementations are composed at entrypoints."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from againward.evidence.dataset import EvidenceDataset
from againward.evidence.protocol import EvidenceQuerySession


@dataclass
class DomainPreparation:
    state: dict[str, Any]
    artifacts: dict[str, dict[str, Any]]
    evidence_dataset: EvidenceDataset | None
    trace_details: dict[str, Any] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)


class DomainPack(Protocol):
    name: str
    review_checks: tuple[str, ...]

    def intake_template(self) -> dict[str, Any]: ...

    def prepare(self, source: Path, *, source_sha256: str,
                intake: dict[str, Any], options: dict[str, Any],
                evidence_plane_mode: str) -> DomainPreparation: ...

    def evidence_card(self, preparation: DomainPreparation,
                      session: EvidenceQuerySession) -> dict[str, Any]: ...

    def analyst_brief(self, state: dict[str, Any]) -> str: ...

    @property
    def privacy_preservation(self): ...

    def delivery_policy(self): ...


class DomainRegistry:
    """Registration is explicit; core never imports or guesses an implementation."""
    def __init__(self):
        self._packs: dict[str, DomainPack] = {}

    def register(self, pack: DomainPack) -> None:
        if not pack.name or pack.name in self._packs:
            raise ValueError("Domain name missing or already registered.")
        self._packs[pack.name] = pack

    def get(self, name: str) -> DomainPack:
        try:
            return self._packs[name]
        except KeyError as exc:
            raise ValueError(f"Unknown domain: {name}. Explicit selection is required.") from exc
