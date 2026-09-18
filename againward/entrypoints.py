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


def get_case_domain(case_directory):
    """Read explicit case metadata; the absent-domain fallback is legacy Energy only."""
    from againward.core.workflow_paths import resolve_case_layout
    from againward.core.artifact_store import read_json
    layout = resolve_case_layout(case_directory)
    state_path = layout["analysis_root"] / "investigation_state.json"
    state = read_json(state_path) if state_path.exists() else {}
    manifest = {}
    for name in ("workspace.json", "case_manifest.json"):
        path = layout["case_root"] / name
        if path.exists():
            manifest = read_json(path)
            break
    declared = manifest.get("domain")
    selected = state.get("domain", declared or "energy")
    if declared and declared != selected:
        raise ValueError("Case domain metadata is inconsistent.")
    profile = state.get("profile", manifest.get("domain_profile"))
    return get_domain(selected, profile=profile)
