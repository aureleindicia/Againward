"""Compatibility alias; implementation lives in againward.core.investigation."""
import sys
from againward.core import investigation as _implementation
sys.modules[__name__] = _implementation
