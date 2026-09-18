"""Compatibility entrypoint for Energy workspace creation."""
from againward.core.workspace import WORKSPACE_DIRECTORIES
from againward.core.workspace import create_client_workspace as _create
from .intake import intake_template


def create_client_workspace(identifier, *, root="workspaces", synthetic=False):
    return _create(identifier, root=root, synthetic=synthetic,
                   domain_name="energy", intake_payload=intake_template())
