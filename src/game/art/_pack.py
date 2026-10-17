"""Per-pack registry wrappers for game code (``game.art.<pack>``).

``Pack("m3")`` exposes the same tiny API the Mission 5 pack had - ``get``,
``variants``, ``module``, ``baked_path``, ``sprite_dir``, ``registry``,
``invalidate`` - plus ``blit_layer`` for world layers (baked camera-space
dressing; see ``engine.assets.layerbake``). All packs share one
``engine.assets.AssetRegistry`` so caches, ref-counts and hot reload are
process-wide. No import-time I/O: the manifest loads on first use.
"""
import importlib
import os
import sys

from engine.assets import AssetRegistry

__all__ = ["Pack", "root", "shared_registry"]

_REGISTRY = None


def root():
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return base
    here = os.path.dirname(os.path.abspath(__file__))          # src/game/art
    return os.path.dirname(os.path.dirname(os.path.dirname(here)))


def shared_registry():
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = AssetRegistry(root(), dev=True)
    return _REGISTRY


class Pack:
    def __init__(self, name, module_prefix=None):
        self.name = name
        self.module_prefix = module_prefix or ("game.art." + name)
        self._loaded = False

    # -- plumbing ---------------------------------------------------------------
    def manifest_path(self):
        return os.path.join(root(), "src", "game", "content", self.name, "manifest.json")

    def registry(self):
        reg = shared_registry()
        if not self._loaded:
            if self.name not in reg.packs:
                reg.load_pack(self.manifest_path())
            self._loaded = True
        return reg

    def sprite_dir(self):
        return os.path.join(root(), "assets", "baked", self.name)

    def baked_path(self, name, variant=0):
        return os.path.join(self.sprite_dir(), "%s_%d.png" % (name, variant))

    def module(self, name):
        return importlib.import_module(self.module_prefix + "." + name)

    def variants(self, name):
        return getattr(self.module(name), "VARIANTS", 1)

    def ids(self):
        return self.registry().ids(self.name)

    # -- per-frame API ------------------------------------------------------------
    def get(self, name, variant=0, scale=1, baked=True):
        """Surface or ``None`` (callers keep their procedural fallback)."""
        return self.registry().get(self.name + "/" + name, variant, scale, baked=baked, default=None)

    def invalidate(self, name=None):
        return self.registry().invalidate(None if name is None else self.name + "/" + name)

    def origin(self, name):
        """World origin of a baked layer (module ``ORIGIN``, or manifest ``origin``)."""
        a = self.registry().define(self.name + "/" + name)
        o = a.extra.get("origin")
        if o is None:
            o = getattr(self.module(name), "ORIGIN", (0, 0))
        return (int(o[0]), int(o[1]))

    def layer_variant(self, name):
        """Runtime variant of a layer from the adapter's ``variant_for_state()`` (0 when absent,
        ``None`` when the current state has no baked representation)."""
        pick = getattr(self.module(name), "variant_for_state", None)
        return 0 if pick is None else pick()

    def blit_layer(self, surface, name, cam_x, cam_y, variant=None):
        """Blit a baked world layer at its origin minus the camera.

        ``variant=None`` asks the adapter (``variant_for_state``). Returns False - so callers run
        their procedural path - when the state is not representable, when the layer is declared
        ``BAKED_ONLY`` and no baked file exists, or when nothing resolves.
        """
        if variant is None:
            variant = self.layer_variant(name)
            if variant is None:
                return False
        if getattr(self.module(name), "BAKED_ONLY", False) and not os.path.exists(self.baked_path(name, variant)):
            return False
        s = self.get(name, variant)
        if s is None:
            return False
        ox, oy = self.origin(name)
        surface.blit(s, (ox - cam_x, oy - cam_y))
        return True
