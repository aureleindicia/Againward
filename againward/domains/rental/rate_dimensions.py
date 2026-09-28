"""Lossless decomposition of a bounded, explicit rate denominator vocabulary.

No rate, quantity, authority or charge classification is inferred here. Unknown
units stay unknown. Calendar and quantity dimensions are never discarded.
"""
from __future__ import annotations

import re
from typing import Any

QUANTITY_BASES = frozenset({"PER_ITEM", "PER_SCOPE"})


def rate_dimensions(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, str):
        return None
    words = re.sub(r"[_-]+", " ", value.strip().lower())
    words = re.sub(r"\s+", " ", words)
    # Both ordering variants explicitly state the same multiplicative basis.
    item = r"(?:asset|item|unit|equipment item)"
    duration = r"(?P<calendar>calendar )?(?P<unit>day|week|month)s?"
    match = re.fullmatch(r"per " + item + r" per " + duration, words)
    if match is None:
        match = re.fullmatch(r"per " + duration + r" (?:and )?per " + item, words)
    if match is None:
        match = re.fullmatch(item + r" " + duration, words)
    if match:
        if match['calendar'] and match['unit'] != 'day':
            return None  # Do not erase a calendar convention we have not modeled.
        result: dict[str, Any] = {"billing_unit": match['unit'].upper(), "quantity_basis": "PER_ITEM"}
        if match['calendar'] and match['unit'] == 'day':
            result['weekends_billable'] = True
        return result
    match = re.fullmatch(r"per (?:whole )?(?:fleet|scope|lot) per " + duration, words)
    if match:
        if match['calendar'] and match['unit'] != 'day':
            return None
        result = {"billing_unit": match['unit'].upper(), "quantity_basis": "PER_SCOPE"}
        if match['calendar'] and match['unit'] == 'day':
            result['weekends_billable'] = True
        return result
    if words in {"calendar day", "calendar days"}:
        return {"billing_unit": "DAY", "weekends_billable": True}
    return None
