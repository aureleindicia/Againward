"""First commercial profile, optional for every canonical Rental structure."""
from . import RentalProfile

CONSTRUCTION = RentalProfile(
    name="construction",
    item_vocabulary=(
        ("excavator", ("excavator", "pelle", "pelleteuse", "mini excavator", "mini pelle")),
        ("telehandler", ("telehandler", "chariot télescopique")),
        ("forklift", ("forklift", "chariot élévateur")),
        ("boom_lift", ("boom lift", "nacelle articulée")),
        ("scissor_lift", ("scissor lift", "nacelle ciseaux")),
        ("generator", ("generator", "groupe électrogène")),
        ("compressor", ("compressor", "compresseur")),
        ("site_cabin", ("site cabin", "bungalow de chantier")),
        ("compactor", ("compactor", "compacteur")),
        ("dumper", ("dumper", "tombereau")),
        ("tool", ("tool hire", "outillage")),
    ),
    likely_charge_types=("TRANSPORT", "DELIVERY", "COLLECTION", "FUEL", "CLEANING", "DAMAGE_WAIVER"),
    operational_checks=(
        "Distinguish off-hire notification, collection request and documented supplier possession.",
        "Verify asset/fleet identity and quantity on delivery and signed return notes.",
        "Check whether fuel, cleaning and waiver terms were accepted for this rental period.",
    ),
)
