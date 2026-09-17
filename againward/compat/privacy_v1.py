"""Legacy v1 preservation vocabulary, retained only for historical Energy callers."""
import re

HEADER_PARTS = {
    "timestamp", "date", "time", "heure", "energy", "energie", "kwh", "mwh", "wh",
    "power", "puissance", "kw", "mw", "production", "volume", "cadence", "cycle",
    "machine", "equipment", "equipement", "asset", "meter", "compteur", "line", "ligne",
    "workshop", "atelier", "site", "shift", "poste", "campaign", "campagne", "lot",
    "batch", "product", "produit", "reference", "temperature", "temp", "state", "etat",
    "status", "on", "off", "maintenance", "arret", "stop", "model", "modele", "type",
}
TEXT_PATTERNS = (
    re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?(?:Z|[+-]\d{2}:?\d{2})?\b"),
    re.compile(r"(?i)\b\d+(?:[.,]\d+)?\s*(?:kwh|mwh|wh|kw|mw|w|°c|degc)\b"),
    re.compile(
        r"(?i)\b(?:machine|equipement|équipement|compteur|meter|ligne|line|atelier|site|"
        r"shift|poste|lot|batch|cycle|campagne|campaign|produit|product|reference|référence)"
        r"\s*(?:[:=#-]|est|nommé|appele|appelé)?\s*([A-Za-z0-9_.-]+)"
    ),
)

