"""Compatibility alias; implementation lives in againward.core.client_requests."""
import sys
from againward.core import client_requests as _implementation
sys.modules[__name__] = _implementation
