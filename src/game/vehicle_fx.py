"""Game-side FX adapter for ``engine.render3d.VehicleDestructionManager``.

Bridges ``cutscenes.fire3d`` (turbulent fire, warm-underlit smoke, ember plumes)
and optional caller-supplied ``m6fx3d`` (bloom glows & ignition flashes) into the
pure-engine vehicle destruction system without adding W1 boundary edges.
"""
from __future__ import annotations

from types import SimpleNamespace


_CACHED_FIRE = None
_CACHED_FX: dict[int, SimpleNamespace] = {}


def default_vehicle_fx(fx=None):
    """Return a shared FX adapter wrapping ``fire3d`` and optional ``m6fx3d``."""
    global _CACHED_FIRE
    if _CACHED_FIRE is None:
        from cutscenes import fire3d as F3D

        _CACHED_FIRE = F3D
    key = id(fx) if fx is not None else 0
    cached = _CACHED_FX.get(key)
    if cached is not None:
        return cached
    ns = SimpleNamespace(
        emit_fire=_CACHED_FIRE.emit_fire,
        smoke_puff=_CACHED_FIRE.smoke_puff_surface,
        embers=_CACHED_FIRE.embers_sprite,
        flash=getattr(fx, "flash", None) if fx is not None else None,
        glow=getattr(fx, "glow", None) if fx is not None else None,
        fx_layer=getattr(fx, "FX_LAYER", 6) if fx is not None else 6,
    )
    if len(_CACHED_FX) > 8:
        _CACHED_FX.clear()
    _CACHED_FX[key] = ns
    return ns
