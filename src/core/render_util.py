"""core.render_util - deprecated path (RPE6 Phase 2, A-006).

The helpers live in ``engine.render2d``; this module re-exports them so the
legacy ``from core import render_util`` call sites keep working. ``screen_visible``
keeps its old signature by binding the window size from ``core.config``.
"""
import warnings as _warnings

from engine.render2d import add_radial, doors_anim_sig, push_lamps, soft_shadow, swap_screen  # noqa: F401
from engine.render2d import screen_visible as _screen_visible
from core.config import WIDTH as _WIDTH, HEIGHT as _HEIGHT

_warnings.warn("core.render_util moved to engine.render2d (RPE6 A-006)", DeprecationWarning, stacklevel=2)


def screen_visible(sx, sy, w, h, margin=80):
    return _screen_visible(sx, sy, w, h, margin, (_WIDTH, _HEIGHT))
