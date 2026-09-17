"""Application composition root. Only this layer selects built-in domain packs."""
from againward.core.domain import DomainRegistry


def get_domain(name: str, *, profile: str | None = None):
    registry = DomainRegistry()
    if name == "energy":
        if profile is not None:
            raise ValueError("Energy has no Rental profile.")
        from againward.domains.energy.domain_pack import EnergyDomainPack
        registry.register(EnergyDomainPack())
    elif name == "rental":
        from againward.domains.rental.domain_pack import RentalDomainPack
        registry.register(RentalDomainPack(profile=profile))
    return registry.get(name)
