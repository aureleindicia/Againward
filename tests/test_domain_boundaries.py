"""Dependency direction is a product invariant, not a naming convention."""
import ast
from pathlib import Path
import subprocess
import sys


def test_core_has_no_domain_or_energy_implementation_imports():
    for path in Path("againward/core").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            assert all(not name.startswith(("energy_mvp", "againward.domains"))
                       for name in names), path


def test_core_lifecycle_import_does_not_load_energy_transitively():
    subprocess.run([sys.executable, "-c", """
import sys
from againward.core.client_lifecycle import initialize_client_lifecycle
from againward.core.workspace import create_client_workspace
assert not any(n.startswith(('energy_mvp', 'againward.domains')) for n in sys.modules)
"""], check=True)


def test_legacy_lifecycle_and_store_are_same_implementation():
    from againward.core import artifact_store, client_lifecycle
    from energy_mvp import artifact_store as old_store, client_lifecycle as old_lifecycle
    assert old_store is artifact_store
    assert old_lifecycle is client_lifecycle
