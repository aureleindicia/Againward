"""Explainable, bounded resolution of source-local entity occurrences.

No entity attributes are copied across a relationship. Business packs provide
keys, cardinality and relationship vocabulary; confidence is not an authority.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, replace
from enum import Enum
from itertools import combinations
import json
import re
from typing import Any

from againward.evidence.hashing import stable_hash
from .contracts import DocumentError, closed, identifier, text, timestamp
from .extraction import CanonicalFact

RESOLVER_VERSION = "againward-entity-resolution-v1"


class RelationshipState(str, Enum):
    CONFIRMED = "CONFIRMED"
    CANDIDATE = "CANDIDATE"
    AMBIGUOUS = "AMBIGUOUS"
    REJECTED = "REJECTED"
    CONTRADICTED = "CONTRADICTED"


@dataclass(frozen=True)
class Entity:
    entity_id: str
    local_id: str
    source_id: str
    kind: str
    facts: tuple[CanonicalFact, ...]

    @property
    def values(self) -> dict[str, str | bool | int | None]:
        return {f.candidate.semantic_type: f.candidate.value for f in self.facts}

    @property
    def evidence_hash(self) -> str:
        return stable_hash([f.to_dict() for f in self.facts])


def entities_from_facts(facts: tuple[CanonicalFact, ...], *,
                        non_entity_fields: frozenset[str] = frozenset(),
                        reference_fields_by_kind: dict[str, frozenset[str]] | None = None,
                        ) -> tuple[Entity, ...]:
    """Build typed entities without promoting metadata/reference fragments.

    Local labels never join documents, even if a model reuses the same label.
    Source metadata and identifier-only references stay as reviewed facts in
    lineage. A typed credit may use a unique, non-excluded target reference for
    deterministic linking; ambiguous references never enter its value map.
    """
    grouped: dict[tuple[str, str], list[CanonicalFact]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.candidate.source_id, fact.candidate.entity_id)].append(fact)
    entities = []
    reference_fields_by_kind = reference_fields_by_kind or {}
    for (source, local), group in sorted(grouped.items()):
        kinds = {fact.candidate.value for fact in group
                 if fact.candidate.semantic_type == "entity_kind"}
        kind_value = next(iter(kinds)) if len(kinds) == 1 else None
        kind = kind_value if isinstance(kind_value, str) else None
        reference_fields = (reference_fields_by_kind.get(kind, frozenset())
                            if kind is not None else frozenset())
        reference_facts = [fact for fact in group
                           if fact.candidate.semantic_type in reference_fields]
        entity_facts = [fact for fact in group
                        if fact.candidate.semantic_type not in reference_fields]
        # A unique source-bound target can support an explicit relationship.
        # Reused model labels, multiple positive values, and explicitly
        # excluded targets do not select one value by order or convenience.
        if kind is not None and reference_fields:
            by_reference: dict[str, list[CanonicalFact]] = defaultdict(list)
            for fact in reference_facts:
                flags = {flag.casefold() for flag in fact.candidate.ambiguity_flags}
                if "excluded_target" not in flags:
                    by_reference[fact.candidate.semantic_type].append(fact)
            for field, candidates in by_reference.items():
                values_for_field = {candidate.candidate.value for candidate in candidates}
                if len(values_for_field) == 1:
                    entity_facts.extend(candidates)
        values: dict[str, Any] = {}
        for fact in entity_facts:
            key, value = fact.candidate.semantic_type, fact.candidate.value
            if key in values and values[key] != value:
                raise DocumentError("ENTITY_AMBIGUOUS", "Conflicting values on the same source-local entity")
            values[key] = value
        kind = values.get("entity_kind")
        if not isinstance(kind, str):
            fields = {fact.candidate.semantic_type for fact in group}
            metadata_only = is_source_metadata_fragment(fields, non_entity_fields)
            if metadata_only or is_reference_fragment(fields, non_entity_fields):
                continue
            raise DocumentError("ENTITY_AMBIGUOUS", "Reviewed entity_kind required")
        entities.append(Entity("entity-" + stable_hash({"source": source, "local": local}),
                               local, source, kind,
                               tuple(sorted(entity_facts, key=lambda f: f.fact_id))))
    return tuple(entities)


def non_entity_reference_groups(facts: tuple[CanonicalFact, ...], *,
                                non_entity_fields: frozenset[str] = frozenset(),
                                reference_fields_by_kind: dict[str, frozenset[str]] | None = None
                                ) -> list[dict[str, Any]]:
    """Return separately bound references, without treating model labels as IDs."""
    grouped: dict[tuple[str, str], list[CanonicalFact]] = defaultdict(list)
    for fact in facts:
        grouped[(fact.candidate.source_id, fact.candidate.entity_id)].append(fact)
    rows = []
    reference_fields_by_kind = reference_fields_by_kind or {}
    for (source_id, local_id), group in sorted(grouped.items()):
        fields = {fact.candidate.semantic_type for fact in group}
        kinds = {fact.candidate.value for fact in group
                 if fact.candidate.semantic_type == "entity_kind"}
        kind_value = next(iter(kinds)) if len(kinds) == 1 else None
        kind = kind_value if isinstance(kind_value, str) else None
        reference_fields = (reference_fields_by_kind.get(kind, frozenset())
                            if kind is not None else frozenset())
        for fact in sorted(group, key=lambda item: item.fact_id):
            field = fact.candidate.semantic_type
            if field in reference_fields:
                rows.append({"source_id": source_id,
                             "local_id": "reference-" + stable_hash(fact.fact_id)[:20],
                             "record_type": "SOURCE_REFERENCE_FRAGMENT",
                             "semantic_type": field, "fact_ids": [fact.fact_id]})
        metadata_only = is_source_metadata_fragment(fields, non_entity_fields)
        if "entity_kind" not in fields and (metadata_only or is_reference_fragment(fields, non_entity_fields)):
            rows.append({"source_id": source_id, "local_id": local_id,
                         "record_type": "SOURCE_METADATA_OR_REFERENCE_FRAGMENT",
                         "fact_ids": sorted(fact.fact_id for fact in group)})
    return rows


def is_source_metadata_fragment(fields: set[str], non_entity_fields: frozenset[str]) -> bool:
    """Recognize narrowly scoped source metadata without creating an entity.

    Supplier identity may be emitted as its own source-envelope observation,
    just like document role/status. A date is source metadata only when tied to
    an explicit role or status. Commercial facts and bare agreement identifiers
    still require a typed occurrence.
    """
    if not fields or not fields <= non_entity_fields:
        return False
    envelope = {"document_role", "document_status", "supplier_id", "agreement_id"}
    if fields <= envelope and (fields == {"supplier_id"}
                               or bool(fields & {"document_role", "document_status"})):
        return True
    return ("date" in fields
            and bool(fields & {"document_role", "document_status"})
            and fields <= envelope | {"date"})


def is_reference_fragment(fields: set[str], non_entity_fields: frozenset[str]) -> bool:
    """Recognize only anchored invoice-reference groups as non-entities."""
    references = fields & non_entity_fields
    return (bool(references) and references <= non_entity_fields
            and bool(references & {"invoice_id", "invoice_line_id"})
            and fields <= non_entity_fields)


@dataclass(frozen=True)
class MatchPolicy:
    relationship_type: str
    kind_pairs: tuple[tuple[str, str], ...]
    blocking_keys: tuple[str, ...]
    anchor_keys: tuple[tuple[str, ...], ...]
    contradiction_keys: tuple[str, ...]
    required_scope_keys: tuple[str, ...]
    exclusive_left_kinds: tuple[str, ...]
    prefix_blocking_keys: tuple[str, ...] = ()
    scope_optional_left_kinds: tuple[str, ...] = ()
    maximum_pairs: int = 20_000

    def __post_init__(self) -> None:
        identifier(self.relationship_type)
        if type(self.maximum_pairs) is not int or self.maximum_pairs < 1:
            raise DocumentError("RESOURCE_LIMIT", "Positive pair budget required")
        if not self.kind_pairs or not self.anchor_keys or any(not k for k in self.anchor_keys):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Explicit kinds and match anchors required")
        if any(not set(anchor) <= set(self.blocking_keys) for anchor in self.anchor_keys):
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Exact anchor must be retrievable by blocking")


@dataclass(frozen=True)
class Relationship:
    relationship_id: str
    left: str
    right: str
    relationship_type: str
    state: RelationshipState
    support: tuple[str, ...]
    contradictions: tuple[str, ...]
    supporting_fact_ids: tuple[str, ...]
    contradicting_fact_ids: tuple[str, ...]
    authority: str
    entity_evidence_hashes: tuple[str, str]
    history: tuple[dict[str, Any], ...]

    def to_dict(self) -> dict[str, Any]:
        return json.loads(json.dumps(asdict(self)))


@dataclass(frozen=True)
class ResolutionResult:
    entities: tuple[Entity, ...]
    relationships: tuple[Relationship, ...]
    considered_pairs: int
    theoretical_pairs: int
    policy: MatchPolicy

    def to_dict(self) -> dict[str, Any]:
        body = {
            "schema_version": RESOLVER_VERSION,
            "policy": asdict(self.policy),
            "entities": [asdict(e) for e in self.entities],
            "relationships": [r.to_dict() for r in self.relationships],
            "considered_pairs": self.considered_pairs, "theoretical_pairs": self.theoretical_pairs,
        }
        return json.loads(json.dumps({**body, "resolution_sha256": stable_hash(body)}))


def _prefix(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    tokens = re.split(r"[- /]", value)
    return tokens[0] if tokens and len(tokens[0]) >= 3 else None


def candidate_pairs(entities: tuple[Entity, ...], policy: MatchPolicy) -> tuple[tuple[int, int], ...]:
    index: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, entity in enumerate(entities):
        values = entity.values
        for key in policy.blocking_keys:
            value = values.get(key)
            if value is not None:
                index[(key, json.dumps(value))].append(i)
        for key in policy.prefix_blocking_keys:
            prefix = _prefix(values.get(key))
            if prefix is not None:
                index[("prefix:" + key, prefix)].append(i)
    pairs = set()
    allowed = set(policy.kind_pairs)
    for members in index.values():
        # Group kinds before enumeration: identical supplier values across a
        # thousand unrelated invoice lines must not generate invoice/invoice pairs.
        by_kind: dict[str, list[int]] = defaultdict(list)
        for i in members:
            by_kind[entities[i].kind].append(i)
        for left_kind, right_kind in allowed:
            lefts, rights = by_kind[left_kind], by_kind[right_kind]
            possible = combinations(lefts, 2) if left_kind == right_kind else (
                (a, b) for a in lefts for b in rights)
            for a, b in possible:
                if a != b:
                    pairs.add((min(a, b), max(a, b)))
                    if len(pairs) > policy.maximum_pairs:
                        raise DocumentError("RESOURCE_LIMIT", "Entity pair budget exceeded; narrow reviewed scope")
    return tuple(sorted(pairs))


def resolve_entities(entities: tuple[Entity, ...], policy: MatchPolicy) -> ResolutionResult:
    ids = [e.entity_id for e in entities]
    if len(ids) != len(set(ids)):
        raise DocumentError("ENTITY_AMBIGUOUS", "Duplicate entity occurrence ID")
    entities = tuple(sorted(entities, key=lambda e: e.entity_id))
    pairs = candidate_pairs(entities, policy)
    relationships = []
    for a, b in pairs:
        left, right = entities[a], entities[b]
        if (left.kind, right.kind) not in policy.kind_pairs:
            left, right = right, left
        lv, rv = left.values, right.values
        support = tuple(sorted(key for key in set(lv) & set(rv)
                               if key != "entity_kind" and lv[key] is not None and lv[key] == rv[key]))
        contradictions = tuple(sorted(key for key in policy.contradiction_keys
                                      if lv.get(key) is not None and rv.get(key) is not None and lv[key] != rv[key]))
        anchors = any(set(keys) <= set(support) for keys in policy.anchor_keys)
        scope = (set(policy.required_scope_keys) <= set(support)
                 or left.kind in policy.scope_optional_left_kinds)
        state = RelationshipState.CONTRADICTED if contradictions else (
            RelationshipState.CONFIRMED if anchors and scope else RelationshipState.CANDIDATE)
        all_facts = (*left.facts, *right.facts)
        sid = tuple(sorted(f.fact_id for f in all_facts if f.candidate.semantic_type in support))
        cid = tuple(sorted(f.fact_id for f in all_facts if f.candidate.semantic_type in contradictions))
        rid = "rel-" + stable_hash({"left": left.entity_id, "right": right.entity_id, "policy": asdict(policy)})
        relationships.append(Relationship(rid, left.entity_id, right.entity_id,
            policy.relationship_type, state, support, contradictions, sid, cid,
            "EXACT_REVIEWED_IDENTIFIERS" if state == RelationshipState.CONFIRMED else "UNRESOLVED",
            (left.evidence_hash, right.evidence_hash),
            ({"resolver": RESOLVER_VERSION, "state": state.value, "reason": "Deterministic reviewed-fact features"},)))
    # A strong pair is not unique if a second non-contradicted candidate exists.
    # Counting candidates as well as exact matches avoids convenient auto-links.
    options: dict[str, list[int]] = defaultdict(list)
    lookup = {e.entity_id: e for e in entities}
    for i, relationship in enumerate(relationships):
        if (lookup[relationship.left].kind in policy.exclusive_left_kinds
                and relationship.state in {RelationshipState.CONFIRMED, RelationshipState.CANDIDATE}):
            options[relationship.left].append(i)
    for alternatives in options.values():
        if len(alternatives) > 1:
            for index in alternatives:
                r = relationships[index]
                relationships[index] = replace(r, state=RelationshipState.AMBIGUOUS, authority="UNRESOLVED",
                    history=(*r.history, {"state": "AMBIGUOUS", "reason": "Multiple plausible target occurrences"}))
    return ResolutionResult(entities, tuple(relationships), len(pairs),
                            len(entities) * (len(entities) - 1) // 2, policy)


def review_relationships(result: ResolutionResult, review: Any) -> ResolutionResult:
    """A supplied human source review may resolve ambiguity, never erase history.

    Conflicting identifiers cannot be hand-waved away: correct the extracted facts
    with a new source/revision and run resolution again.
    """
    p = closed(review, {"schema_version", "resolution_sha256", "reviewer_role", "reviewed_at", "decisions"})
    if p["schema_version"] != "againward-resolution-review-v1" or p["reviewer_role"] != "HUMAN":
        raise DocumentError("UNSUPPORTED_PROMOTION", "Ambiguous links require a human source review")
    if p["resolution_sha256"] != result.to_dict()["resolution_sha256"]:
        raise DocumentError("REVIEW_STALE")
    timestamp(p["reviewed_at"])
    if not isinstance(p["decisions"], list):
        raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Decision array required")
    by_id = {r.relationship_id: r for r in result.relationships}
    decisions = {}
    for decision in p["decisions"]:
        d = closed(decision, {"relationship_id", "state", "reason", "supporting_fact_ids"})
        rid = identifier(d["relationship_id"])
        if rid not in by_id or rid in decisions:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Unknown or duplicate relationship review")
        r = by_id[rid]
        if d["state"] not in {"CONFIRMED", "REJECTED"}:
            raise DocumentError("EXTRACTION_SCHEMA_INVALID", "Explicit confirm or reject required")
        text(d["reason"])
        if (not isinstance(d["supporting_fact_ids"], list) or not d["supporting_fact_ids"]
                or set(d["supporting_fact_ids"]) - set(r.supporting_fact_ids)):
            raise DocumentError("UNSUPPORTED_PROMOTION", "Review must cite actual matching source facts")
        if d["state"] == "CONFIRMED" and r.contradictions:
            raise DocumentError("UNSUPPORTED_PROMOTION", "Contradicted IDs need corrected evidence")
        decisions[rid] = replace(r, state=RelationshipState(d["state"]), authority="HUMAN_REVIEWED",
            history=(*r.history, {"state": d["state"], "reason": d["reason"],
                                 "review_sha256": stable_hash(p), "reviewed_at": p["reviewed_at"]}))
    revised = tuple(decisions.get(r.relationship_id, r) for r in result.relationships)
    confirmed_left: dict[str, int] = defaultdict(int)
    entities = {e.entity_id: e for e in result.entities}
    for r in revised:
        if r.state == RelationshipState.CONFIRMED and entities[r.left].kind in result.policy.exclusive_left_kinds:
            confirmed_left[r.left] += 1
    if any(n > 1 for n in confirmed_left.values()):
        raise DocumentError("ENTITY_AMBIGUOUS", "Exclusive source occurrence cannot have two confirmed targets")
    return replace(result, relationships=revised)
