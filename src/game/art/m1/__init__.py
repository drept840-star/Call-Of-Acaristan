"""Mission 1 asset pack: baked world layers (and props) of the mission dressing.

Each module ``game.art.m1.<name>`` is a bake adapter around a painter that still lives in
``missions.m1`` (the painter is the live fallback). See ``engine.assets.layerbake`` and
``docs/engine/adr/ADR-015``.
"""
from game.art._pack import Pack as _Pack

_PACK = _Pack("m1")
PACK = "m1"
get = _PACK.get
variants = _PACK.variants
module = _PACK.module
baked_path = _PACK.baked_path
sprite_dir = _PACK.sprite_dir
registry = _PACK.registry
invalidate = _PACK.invalidate
origin = _PACK.origin
blit_layer = _PACK.blit_layer
layer_variant = _PACK.layer_variant

__all__ = ["PACK", "get", "variants", "module", "baked_path", "sprite_dir", "registry", "invalidate",
           "origin", "blit_layer", "layer_variant"]
