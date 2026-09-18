"""Compatibility alias for the application CLI."""
import sys
from againward import cli as _implementation
sys.modules[__name__] = _implementation
