"""Compatibility alias; implementation lives in againward.core.artifact_store."""
import sys
from againward.core import artifact_store as _implementation
sys.modules[__name__] = _implementation
