"""Compatibility alias; implementation lives in againward.core.contract_policy."""
import sys
from againward.core import contract_policy as _implementation
sys.modules[__name__] = _implementation
