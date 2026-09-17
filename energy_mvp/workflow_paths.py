"""Compatibility alias; implementation lives in againward.core.workflow_paths."""
import sys
from againward.core import workflow_paths as _implementation
sys.modules[__name__] = _implementation
