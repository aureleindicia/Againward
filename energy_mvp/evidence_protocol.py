"""Compatibility alias for the shared evidence protocol."""
import sys
from againward.evidence import protocol as _implementation
sys.modules[__name__] = _implementation
