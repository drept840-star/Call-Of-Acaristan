"""Mission 5 sprite pack (owner module; ``art.m5`` is the compatibility shim).

Every asset is a module ``game.art.m5.<name>`` exposing ``render(variant=0,
scale=1) -> pygame.Surface`` (pygame-only) plus ``VARIANTS``. The pack is
declared in ``game/content/m5/manifest.json`` (``ae.manifest/1``) and baked by
``tools/ae_bake.py --pack m5`` to ``assets/baked/m5/<name>_<variant>.png``.

``get(name, variant, scale)`` is the one entry point the game uses. It is a
thin call into the shared ``engine.assets.AssetRegistry``: baked PNG first,
live ``render()`` second, declared fallback third and ``None`` if everything
fails - callers keep their procedural drawing as the last fallback (never
delete those). Results are cached per key inside the registry, so the
per-frame cost is one dict lookup, exactly as before Phase 3.
"""
import importlib
import os
import sys

from engine.assets import AssetRegistry

PACK = "m5"
ASSETS = ("posters", "printworks_sign", "guard_banner", "guard_plate", "district_map",
          "portrait_frame", "presidential_crest", "calendar", "armband", "wall_posters",
          "hq_locker", "mag", "mag_icon", "plate", "press", "bale", "m5_guard",
          "maru", "tram_wreck", "inspect_art")
# Wall art that the 3D cutscenes mesh into decals (m5decal); the rest are
# gameplay / HUD sprites blitted in 2D.
DECALS = ("posters", "printworks_sign", "guard_banner", "guard_plate", "district_map",
          "portrait_frame", "presidential_crest", "calendar", "armband")

_REGISTRY = None


def _root():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    here = os.path.dirname(os.path.abspath(__file__))          # src/game/art/m5
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(here))))


def manifest_path():
    return os.path.join(_root(), "src", "game", "content", PACK, "manifest.json")


def registry():
    """The process-wide registry with the m5 pack loaded (lazy; no import-time I/O)."""
    global _REGISTRY
    if _REGISTRY is None:
        reg = AssetRegistry(_root(), dev=True)
        reg.load_pack(manifest_path())
        _REGISTRY = reg
    return _REGISTRY


def sprite_dir():
    return os.path.join(_root(), "assets", "baked", PACK)


def baked_path(name, variant=0):
    return os.path.join(sprite_dir(), "%s_%d.png" % (name, variant))


def module(name):
    return importlib.import_module(__name__ + "." + name)


def variants(name):
    return getattr(module(name), "VARIANTS", 1)


def get(name, variant=0, scale=1, baked=True):
    """Surface for ``name``/``variant`` at ``scale`` or ``None`` (keep the procedural fallback)."""
    return registry().get(PACK + "/" + name, variant, scale, baked=baked, default=None)


def invalidate(name=None):
    """Drop cached surfaces (one asset or all) - display-mode changes, hot reload."""
    return registry().invalidate(None if name is None else PACK + "/" + name)
