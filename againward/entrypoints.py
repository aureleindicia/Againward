"""Application composition root. Only this layer selects built-in domain packs."""
from againward.core.domain import DomainRegistry


def get_domain(name: str):
    registry = DomainRegistry()
    if name == "energy":
        from againward.domains.energy.domain_pack import EnergyDomainPack
        registry.register(EnergyDomainPack())
    return registry.get(name)
