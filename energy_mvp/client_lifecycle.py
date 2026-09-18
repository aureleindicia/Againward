"""Compatibility alias; implementation lives in againward.core.client_lifecycle."""
import sys
from againward.core import client_lifecycle as _implementation
sys.modules[__name__] = _implementation
