"""Injected preservation vocabulary; the privacy engine owns no domain ontology."""
from contextvars import ContextVar
from dataclasses import dataclass
from functools import wraps
from typing import Pattern

from againward.compat.privacy_v1 import HEADER_PARTS, TEXT_PATTERNS


@dataclass(frozen=True)
class PreservationPolicy:
    policy_id: str
    header_parts: frozenset[str]
    text_patterns: tuple[Pattern, ...]


LEGACY_PRESERVATION = PreservationPolicy("legacy-energy-v1", frozenset(HEADER_PARTS), TEXT_PATTERNS)
_current = ContextVar("privacy_preservation_policy", default=LEGACY_PRESERVATION)


def current_preservation_policy():
    return _current.get()


def with_preservation_policy(function):
    @wraps(function)
    def wrapped(*args, preservation_policy=None, **kwargs):
        policy = preservation_policy or current_preservation_policy()
        if not isinstance(policy, PreservationPolicy):
            raise ValueError("Explicit code-defined preservation policy required.")
        token = _current.set(policy)
        try:
            return function(*args, **kwargs)
        finally:
            _current.reset(token)
    return wrapped
