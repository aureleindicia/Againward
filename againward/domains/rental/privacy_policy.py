"""Rental business identifiers and monetary/date markers protected during cleanup."""
import re
from againward.core.privacy_rules import PreservationPolicy, PrivacyRiskPolicy

RENTAL_RISK = PrivacyRiskPolicy(
    "rental-b2b-risk-v1",
    frozenset({"EMAIL", "PHONE", "PROFESSIONAL_NAME", "PROFESSIONAL_SIGNATURE"}),
    visual_human_review=True,
)

RENTAL_PRESERVATION = PreservationPolicy(
    "rental-preservation-v1",
    frozenset({"agreement", "invoice", "credit", "item", "asset", "period", "event", "site",
               "cost", "center", "charge", "quantity", "amount", "rate", "currency", "discount",
               "date", "start", "end", "status", "serial", "fleet", "document", "supplier"}),
    (
        re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"),
        re.compile(r"(?i)\b(?:EUR|USD|GBP|CHF|CAD|AUD|NZD)\s*\d+(?:[.,]\d+)?\b"),
        re.compile(r"(?i)\b\d+(?:[.,]\d+)?\s*(?:EUR|USD|GBP|CHF|CAD|AUD|NZD|%|days?|weeks?|months?|jours?|semaines?|mois)\b"),
        re.compile(r"(?i)\b(?:agreement|invoice|credit|item|asset|period|event|site|contract|contrat|facture)\s*[:=#-]?\s*([A-Za-z0-9_.-]+)"),
    ),
    RENTAL_RISK,
)
