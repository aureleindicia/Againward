"""Compatibility alias for the shared evidence cli."""
import sys
from againward.evidence import cli as _implementation
sys.modules[__name__] = _implementation
