"""Mission 3 asset pack: baked world layers of the prison dressing (and later props).

Each module ``game.art.m3.<name>`` is a bake adapter around a painter that
still lives in ``missions.m3`` (the painter is the live fallback). See
``engine.assets.layerbake`` and ``docs/engine/adr/ADR-015``.
"""
from game.art._pack import Pack as _Pack

_PACK = _Pack("m3")
PACK = "m3"
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
