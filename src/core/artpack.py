"""core.artpack - deprecated path (RPE6 Phase 2, A-006).

The implementation is ``engine.assets.artpack``; this module binds it to the
game's resource root and re-exports the public API for ``from core import artpack``.
"""
import warnings as _warnings

from engine.assets import artpack as _impl
from core.config import resource_path as _resource_path

_warnings.warn("core.artpack moved to engine.assets.artpack (RPE6 A-006)", DeprecationWarning, stacklevel=2)
_impl.configure(_resource_path)

enabled = _impl.enabled
path = _impl.path
get = _impl.get
tile = _impl.tile
wall = _impl.wall
icon = _impl.icon
light = _impl.light
blit = _impl.blit
blit9slice = _impl.blit9slice
pose = _impl.pose
sheet = _impl.sheet
frame = _impl.frame
frame_anchor = _impl.frame_anchor
blit_frame = _impl.blit_frame
vehicle = _impl.vehicle
prop = _impl.prop
fx = _impl.fx
rebuild = _impl.rebuild
