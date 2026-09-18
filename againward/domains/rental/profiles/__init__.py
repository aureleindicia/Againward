"""Profiles enrich vocabulary; they never redefine rental lifecycle or pricing."""
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class RentalProfile:
    name: str
    item_vocabulary: tuple[tuple[str, tuple[str, ...]], ...] = ()
    likely_charge_types: tuple[str, ...] = ()
    operational_checks: tuple[str, ...] = ()

    def suggest_category(self, description: str):
        text = " " + re.sub(r"[^\w]+", " ", description.casefold()) + " "
        matches = [category for category, terms in self.item_vocabulary
                   if any(" " + term + " " in text for term in terms)]
        return {"suggested_categories": matches, "status": "VOCABULARY_HINT_ONLY", "decision": None}


def get_profile(name: str | None) -> RentalProfile:
    if name in {None, "generic"}:
        return RentalProfile("generic")
    if name == "construction":
        from .construction import CONSTRUCTION
        return CONSTRUCTION
    raise ValueError(f"Unknown Rental profile: {name}.")
