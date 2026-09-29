"""Lossless decomposition of a bounded, explicit rate denominator vocabulary.

No rate, quantity, authority or charge classification is inferred here. Unknown
units stay unknown. Calendar and quantity dimensions are never discarded.
"""
from __future__ import annotations

import re
from typing import Any

QUANTITY_BASES = frozenset({"PER_ITEM", "PER_SCOPE"})
_UNSUPPORTED_CALENDAR_RATE = re.compile(
    r"\bper\s+(?:(?:whole\s+)?(?:asset|item|unit|equipment item|fleet|scope|lot)\s+per\s+)?"
    r"calendar\s+(?:week|month)s?\b")


def has_unsupported_calendar_rate_convention(value: Any) -> bool:
    """Detect explicit calendar-week/month pricing outside the supported model."""
    if not isinstance(value, str):
        return False
    words = re.sub(r"[_-]+", " ", value.strip().lower())
    words = re.sub(r"\s+", " ", words)
    return _UNSUPPORTED_CALENDAR_RATE.search(words) is not None


def has_ambiguous_rate_dimensions(value: Any) -> bool:
    """Return true when source wording contains multiple competing rate bases."""
    if not isinstance(value, str):
        return False
    words = re.sub(r"[_-]+", " ", value.strip().lower())
    words = re.sub(r"\s+", " ", words)
    item = r"(?:asset|item|unit|equipment item)"
    duration = r"(?P<calendar>calendar )?(?P<unit>day|week|month)s?"
    expressions = (
        re.compile(r"\bper " + item + r" per " + duration + r"\b"),
        re.compile(r"\bper " + duration + r" (?:and )?per " + item + r"\b"),
        re.compile(r"\b" + item + r" " + duration + r"\b"),
        re.compile(r"\bper (?:whole )?(?:fleet|scope|lot) per " + duration + r"\b"),
    )
    spans = {(match.start(), match.end()) for pattern in expressions for match in pattern.finditer(words)}
    return len(spans) > 1


def rate_dimensions(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    words = re.sub(r"[_-]+", " ", value.strip().lower())
    words = re.sub(r"\s+", " ", words)
    # Search for one complete denominator phrase inside longer source quotes.
    # A citation commonly includes the amount and currency before its unit.
    # Multiple matches are deliberately ambiguous: callers must not choose one.
    item = r"(?:asset|item|unit|equipment item)"
    duration = r"(?P<calendar>calendar )?(?P<unit>day|week|month)s?"
    expressions = (
        (re.compile(r"\bper " + item + r" per " + duration + r"\b"), "PER_ITEM"),
        (re.compile(r"\bper " + duration + r" (?:and )?per " + item + r"\b"), "PER_ITEM"),
        (re.compile(r"\b" + item + r" " + duration + r"\b"), "PER_ITEM"),
        (re.compile(r"\bper (?:whole )?(?:fleet|scope|lot) per " + duration + r"\b"), "PER_SCOPE"),
    )
    matches: list[tuple[re.Match[str], str]] = []
    for pattern, basis in expressions:
        matches.extend((match, basis) for match in pattern.finditer(words))
    # Do not double-count nested patterns that identify the same substring.
    unique = {(match.start(), match.end(), basis): (match, basis) for match, basis in matches}
    matches = list(unique.values())
    if len(matches) > 1:
        return None
    if matches:
        match, basis = matches[0]
        if match['calendar'] and match['unit'] != 'day':
            return None  # Do not erase a calendar convention we have not modeled.
        result: dict[str, Any] = {"billing_unit": match['unit'].upper(), "quantity_basis": basis}
        if match['calendar'] and match['unit'] == 'day':
            result['weekends_billable'] = True
        return result
    if words in {"calendar day", "calendar days"}:
        return {"billing_unit": "DAY", "weekends_billable": True}
    return None
