"""Compatibility shim (ADAPTERS A-008): ``art.m5`` -> ``game.art.m5``.

The Mission 5 sprite pack moved to ``game.art.m5`` in RPE6 Phase 3. This shim
keeps every historical import working: ``from art import m5 as _art`` /
``art.get(...)``, ``from art.m5 import _kit as K``, ``from art.m5.bale import
variant_for``, ``art.m5.maru`` ... The sprite modules are aliased in
``sys.modules`` (same module objects, so hot reload and caches stay coherent).
Remove when the last importer is migrated (tracked in docs/engine/ADAPTERS.md).
"""
import importlib as _importlib
import sys as _sys

from game.art import m5 as _owner
from game.art.m5 import (ASSETS, DECALS, PACK, baked_path, get, invalidate, manifest_path,  # noqa: F401
                         module, registry, sprite_dir, variants)

for _name in ASSETS + ("_kit",):
    _mod = _importlib.import_module("game.art.m5." + _name)
    _sys.modules[__name__ + "." + _name] = _mod
    globals()[_name] = _mod
del _name, _mod

__all__ = ["ASSETS", "DECALS", "PACK", "baked_path", "get", "invalidate", "manifest_path",
           "module", "registry", "sprite_dir", "variants"]
