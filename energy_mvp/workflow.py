"""Compatibility entrypoint; Energy runs through the shared domain orchestrator."""
from againward.core.workflow import prepare_investigation as _prepare
from againward.domains.energy.domain_pack import EnergyDomainPack


def prepare_investigation(source, output_directory, *, intake=None, default_tariff=None,
                          load_options=None, evidence_plane_mode="preferred"):
    return _prepare(source, output_directory, domain=EnergyDomainPack(), intake=intake,
                    options={"default_tariff":default_tariff, "load_options":load_options},
                    evidence_plane_mode=evidence_plane_mode)
