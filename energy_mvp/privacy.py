"""Compatibility alias; implementation lives in againward.core.privacy."""
import sys
from againward.core import privacy as _implementation
sys.modules[__name__] = _implementation
