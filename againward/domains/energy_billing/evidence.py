"""Native atomic evidence binding and replay. Source binding is not approval."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from againward.documents.readers import ParsedDocument
from againward.evidence.hashing import stable_hash

from .protocol import ATOM_SCHEMA, BillingFailure, validate, validate_read_envelope


@dataclass(frozen=True)
class Observation:
    source_id: str
    location: str
    unit_sha256: str
    reader_version: str
    field: str
    value: str
    quote: str
    start: int
    end: int

    @property
    def evidence_id(self) -> str:
        # Model group labels and read role are not evidence identity.
        return "eb-e-" + stable_hash(asdict(self))


@dataclass(frozen=True)
class Reading:
    observations: tuple[Observation, ...]
    quarantine: tuple[dict[str, Any], ...]
    limitations: tuple[str, ...]
    groups: dict[str, tuple[str, ...]]


def bind_atom(row: Any, parsed: ParsedDocument) -> Observation:
    validate(row, ATOM_SCHEMA, stage="OBSERVATION")
    unit = next((u for u in parsed.units if u.location == row["location"]), None)
    if unit is None or unit.route != "NATIVE":
        raise BillingFailure("EVIDENCE_BINDING_INVALID", stage="OBSERVATION", path="$.location",
                             expected="known native unit", actual=row["location"], source_id=parsed.source_id)
    if unit.text.count(row["quote"]) != 1:
        raise BillingFailure("EVIDENCE_BINDING_INVALID", stage="OBSERVATION", path="$.quote",
                             expected="unique exact contiguous quote", actual=row["quote"], source_id=parsed.source_id)
    start = unit.text.index(row["quote"])
    return Observation(parsed.source_id, unit.location, unit.unit_sha256, parsed.reader_version,
                       row["field"], row["value"], row["quote"], start, start + len(row["quote"]))


def bind_reading(payload: dict[str, Any], parsed: ParsedDocument) -> Reading:
    validate_read_envelope(payload)
    accepted: dict[str, Observation] = {}
    groups: dict[str, list[str]] = {}
    quarantine = []
    for index, row in enumerate(payload["observations"]):
        try:
            atom = bind_atom(row, parsed)
        except BillingFailure as exc:
            # Known decorative field alone may be nonmaterial. Unknown/missing
            # field/type remains potentially material, never silently irrelevant.
            material = not (isinstance(row, dict) and row.get("field") == "note")
            quarantine.append({"root_issue_id": "eb-i-" + stable_hash({
                "source": parsed.source_id, "row": row, "diagnostic": exc.diagnostic}),
                "source_id": parsed.source_id, "row_index": index,
                "row_sha256": stable_hash(row), "potentially_material": material,
                "diagnostic": exc.diagnostic})
            continue
        accepted[atom.evidence_id] = atom
        group_ids = groups.setdefault(row["group"], [])
        if atom.evidence_id not in group_ids:
            group_ids.append(atom.evidence_id)
    return Reading(tuple(accepted[key] for key in sorted(accepted)), tuple(quarantine),
                   tuple(payload["limitations"]), {key: tuple(sorted(ids)) for key, ids in groups.items()})


def replay_atom(atom: Observation, parsed: ParsedDocument) -> None:
    if atom.source_id != parsed.source_id or atom.reader_version != parsed.reader_version:
        raise BillingFailure("SOURCE_CHANGED", stage="REPLAY", expected="original reader/source")
    row = {"group": "replay", "field": atom.field, "value": atom.value,
           "location": atom.location, "quote": atom.quote}
    if bind_atom(row, parsed) != atom:
        raise BillingFailure("EVIDENCE_BINDING_INVALID", stage="REPLAY", expected="original unit/hash/span")
