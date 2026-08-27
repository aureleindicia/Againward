from __future__ import annotations

from typing import Any


SERVICE_CATEGORY = "investigation énergétique sur données"
SERVICE_TITLE = "Analyse et investigation de performance énergétique"
REGULATORY_DISCLAIMER = (
    "Cette prestation ne constitue pas un audit énergétique réglementaire."
)


def positioning_payload() -> dict[str, Any]:
    """Retourne le positionnement canonique exposé dans les dossiers client."""

    return {
        "category": SERVICE_CATEGORY,
        "value_chain": [
            "détecter les dérives et anomalies invisibles dans les agrégats",
            "quantifier leur énergie et leur coût observés",
            "éliminer les fausses pistes par des tests contradictoires",
            "cibler les vérifications terrain qui réduisent réellement l'incertitude",
            "mesurer l'effet après correction et surveiller une éventuelle réapparition",
        ],
        "standalone_use": True,
        "complements": [
            "auditeur énergétique",
            "frigoriste",
            "électricien",
            "mainteneur",
        ],
        "regulatory_audit": False,
        "regulatory_disclaimer": REGULATORY_DISCLAIMER,
    }
