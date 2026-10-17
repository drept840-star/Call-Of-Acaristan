"""core.lighting - deprecated path (RPE6 Phase 2, A-006).

``LightBuffer`` lives in ``engine.lighting``; the window-sized singleton that
the missions share (``buffer()``) stays here because it needs ``core.config``.
"""
import warnings as _warnings

from engine.lighting import LightBuffer, enabled, frozen  # noqa: F401
from core.config import WIDTH as _WIDTH, HEIGHT as _HEIGHT

_warnings.warn("core.lighting moved to engine.lighting (RPE6 A-006)", DeprecationWarning, stacklevel=2)

_BUFFER = None


def buffer():
    global _BUFFER
    if _BUFFER is None:
        _BUFFER = LightBuffer((_WIDTH, _HEIGHT))
    return _BUFFER
