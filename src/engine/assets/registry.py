"""AssetRegistry (§6.5): stable ids, the fallback chain, caching, ref-counts, reload.

``get(id, variant=0, scale=1)`` resolves **baked file → live render → declared
fallback → placeholder**. The placeholder is a magenta checker with a one-time
warning in dev, a transparent surface in release; callers that keep a
procedural fallback (R: never delete them) pass ``default=None`` and get
``None`` instead, exactly as the old ``art.m5.get`` did.

Loading a baked PNG mirrors the legacy loader to the pixel: ``image.load`` →
``convert_alpha()`` only when a display exists → nearest ``transform.scale``
for ``scale != 1``. Live renders call ``module.render(variant, scale)``.

Ref-counting: ``acquire(pack, owner)`` / ``release(owner)`` let a loading
scene preload a pack and drop it when the scene exits; ``unload_pack`` evicts
the pack's cache entries once no owner holds it.
"""
from __future__ import annotations

import importlib
import os
import sys
from typing import Any, Callable

from engine.core import AssetError

from .manifest import AssetDef, Manifest, load_manifest

__all__ = ["AssetRegistry", "PLACEHOLDER", "AssetReloaded"]

class _Placeholder:
    """Sentinel for ``get(default=PLACEHOLDER)``: "give me the dev checker / release blank"."""
    __slots__ = ()

    def __repr__(self) -> str:
        return "PLACEHOLDER"


PLACEHOLDER = _Placeholder()


class AssetReloaded:
    """Event: an asset's module or file changed and its cache entries were dropped."""
    __slots__ = ("id", "reason")

    def __init__(self, id: str, reason: str = "") -> None:
        self.id = id
        self.reason = reason

    def __repr__(self) -> str:
        return f"AssetReloaded({self.id!r}, {self.reason!r})"


def _reexec(mod) -> None:
    """Re-run a module from its source in place (same module object).

    ``importlib.reload`` trusts the ``.pyc`` mtime/size stamp, which misses an
    edit saved within the same second as the previous one - exactly the
    hot-reload case - so compile straight from the file when there is one.
    """
    path = getattr(mod, "__file__", None)
    if path and path.endswith(".py") and os.path.exists(path):
        with open(path, "rb") as fh:
            code = compile(fh.read(), path, "exec", dont_inherit=True)
        exec(code, mod.__dict__)
    else:
        importlib.reload(mod)


def _checker(size=(32, 32)):
    import pygame
    s = pygame.Surface(size, pygame.SRCALPHA)
    w, h = size
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            col = (255, 0, 255, 255) if ((x // 8 + y // 8) % 2 == 0) else (20, 20, 20, 255)
            s.fill(col, (x, y, 8, 8))
    return s


class AssetRegistry:
    def __init__(self, root: str, *, dev: bool = True, log: Any = None, bus: Any = None) -> None:
        self.root = str(root)
        self.dev = bool(dev)
        self.log = log
        self.bus = bus
        self.packs: dict[str, Manifest] = {}
        self.assets: dict[str, AssetDef] = {}
        self._cache: dict[tuple, Any] = {}
        self._modules: dict[str, Any] = {}
        self._owners: dict[str, set] = {}
        self._warned: set = set()
        self.stats = {"hits": 0, "baked": 0, "rendered": 0, "fallback": 0, "placeholder": 0, "evicted": 0}
        # World layers are big (a 4608x5120 opaque layer is 70 MB). Only the ones in use stay
        # resident: least-recently-used layer surfaces are dropped past this budget.
        self.layer_budget_bytes = 160 * 1024 * 1024
        self._layer_lru: dict[tuple, int] = {}
        self._tick = 0

    # -- packs -------------------------------------------------------------------
    def load_pack(self, manifest_path: str) -> Manifest:
        m = load_manifest(manifest_path)
        if m.pack in self.packs:
            self.unload_pack(m.pack, force=True)
        self.packs[m.pack] = m
        for a in m:
            self.assets[a.id] = a
        return m

    def unload_pack(self, pack: str, force: bool = False) -> bool:
        if self._owners.get(pack) and not force:
            return False
        m = self.packs.pop(pack, None)
        if m is None:
            return False
        for a in m:
            self.assets.pop(a.id, None)
            self.invalidate(a.id)
            self._modules.pop(a.id, None)
        self._owners.pop(pack, None)
        return True

    def acquire(self, pack: str, owner: object) -> None:
        if pack not in self.packs:
            raise AssetError(f"pack {pack!r} is not loaded")
        self._owners.setdefault(pack, set()).add(id(owner))

    def release(self, owner: object) -> list[str]:
        """Drop ``owner``'s holds; returns the packs that became unreferenced."""
        freed = []
        for pack, owners in list(self._owners.items()):
            owners.discard(id(owner))
            if not owners:
                freed.append(pack)
                del self._owners[pack]
        return freed

    def holders(self, pack: str) -> int:
        return len(self._owners.get(pack, ()))

    # -- lookup ------------------------------------------------------------------
    def define(self, asset_id: str) -> AssetDef:
        try:
            return self.assets[asset_id]
        except KeyError:
            raise AssetError(f"unknown asset id {asset_id!r}") from None

    def ids(self, pack: str | None = None, kind: str | None = None) -> list[str]:
        return sorted(a.id for a in self.assets.values()
                      if (pack is None or a.pack == pack) and (kind is None or a.kind == kind))

    def variant_index(self, asset_id: str, variant: Any) -> int:
        """``"m5/mag_icon:stick.active"`` style names resolve through the module's VARIANT_NAMES."""
        if isinstance(variant, int):
            return variant
        a = self.define(asset_id)
        names = a.extra.get("variant_names")
        if names is None and a.module:
            names = getattr(self.module(asset_id), "VARIANT_NAMES", None)
        if names is None or variant not in names:
            raise AssetError(f"{asset_id}: unknown variant name {variant!r}")
        return int(names[variant]) if isinstance(names, dict) else list(names).index(variant)

    def module(self, asset_id: str):
        a = self.define(asset_id)
        if not a.module:
            raise AssetError(f"{asset_id} ({a.kind}) has no module")
        mod = self._modules.get(asset_id)
        if mod is None:
            mod = importlib.import_module(a.module)
            self._modules[asset_id] = mod
        return mod

    def variants(self, asset_id: str) -> int:
        a = self.define(asset_id)
        if a.rendered:
            try:
                return int(getattr(self.module(asset_id), "VARIANTS", a.variants))
            except Exception:
                return a.variants
        return a.variants

    def baked_path(self, asset_id: str, variant: int = 0) -> str | None:
        a = self.define(asset_id)
        # normpath: manifest paths use "/", callers compare against native paths
        # (tools/smoke_test.py, game/art shims); neutral on POSIX.
        if a.rendered:
            f = a.baked_file(variant)
            return os.path.normpath(os.path.join(self.root, f)) if f else None
        return os.path.normpath(os.path.join(self.root, a.path)) if a.path else None

    def get(self, asset_id: str, variant: Any = 0, scale: float = 1, *, baked: bool = True, default: Any = PLACEHOLDER):
        """Resolve an asset surface (see module docstring for the chain)."""
        if ":" in asset_id and asset_id.split(":", 1)[0] in self.assets:   # "id:variant_name"
            asset_id, variant = asset_id.split(":", 1)
        a = self.define(asset_id)
        if not isinstance(variant, int):
            variant = self.variant_index(asset_id, variant)
        key = (asset_id, variant, scale, baked)
        if key in self._cache:
            self.stats["hits"] += 1
            if key in self._layer_lru:
                self._tick += 1
                self._layer_lru[key] = self._tick
            return self._cache[key]
        surf = None
        if baked:
            surf = self._load_baked(a, variant, scale)
            if surf is not None:
                self.stats["baked"] += 1
        if surf is None and a.rendered:
            surf = self._render(a, variant, scale)
            if surf is not None:
                self.stats["rendered"] += 1
        if surf is None and a.fallback:
            surf = self.get(a.fallback, 0, scale, baked=baked, default=None)
            if surf is not None:
                self.stats["fallback"] += 1
        if surf is None:
            self._warn(asset_id, f"asset {asset_id!r} v{variant} did not resolve (baked, render, fallback all failed)")
            if default is PLACEHOLDER:
                self.stats["placeholder"] += 1
                surf = self._placeholder(a)
            else:
                surf = default
        self._cache[key] = surf
        if a.kind == "layer" and surf is not None and hasattr(surf, "get_size"):
            self._tick += 1
            self._layer_lru[key] = self._tick
            self._evict_layers(keep=key)
        return surf

    @staticmethod
    def _surface_bytes(surf) -> int:
        try:
            w, h = surf.get_size()
            return int(w) * int(h) * int(surf.get_bytesize())
        except Exception:   # noqa: BLE001
            return 0

    def _evict_layers(self, keep=None) -> int:
        """Drop least-recently-used layer surfaces until resident layers fit the budget."""
        total = sum(self._surface_bytes(self._cache[k]) for k in self._layer_lru if k in self._cache)
        n = 0
        for k in sorted(self._layer_lru, key=self._layer_lru.get):
            if total <= self.layer_budget_bytes:
                break
            if k == keep or k not in self._cache:
                continue
            total -= self._surface_bytes(self._cache[k])
            del self._cache[k]
            del self._layer_lru[k]
            n += 1
        self.stats["evicted"] += n
        return n

    def _load_baked(self, a: AssetDef, variant: int, scale: float):
        import pygame
        p = self.baked_path(a.id, variant)
        if not p or not os.path.exists(p):
            return None
        try:
            surf = pygame.image.load(p)
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                if surf.get_flags() & pygame.SRCALPHA:
                    surf = surf.convert_alpha()
                # else: opaque PNGs (world layers) stay 24-bit as loaded - 25 % less memory than
                # convert(); the 24->32 copy blit is within 0.05 ms of the converted one.
            if scale != 1:
                w, h = surf.get_size()
                surf = pygame.transform.scale(surf, (int(w * scale), int(h * scale)))
            return surf
        except Exception as e:   # noqa: BLE001 - a broken file falls through the chain
            self._warn(a.id + "#load", f"{a.id}: baked file {p} failed to load: {e!r}")
            return None

    def _render(self, a: AssetDef, variant: int, scale: float):
        try:
            return self.module(a.id).render(variant, scale)
        except Exception as e:   # noqa: BLE001
            self._warn(a.id + "#render", f"{a.id}: live render failed: {e!r}")
            return None

    def _placeholder(self, a: AssetDef):
        import pygame
        size = a.size or (32, 32)
        if self.dev:
            return _checker(size)
        return pygame.Surface(size, pygame.SRCALPHA)

    def _warn(self, key: str, msg: str) -> None:
        if key in self._warned:
            return
        self._warned.add(key)
        if self.log is not None:
            try:
                self.log.warn("assets", msg)
            except Exception:
                pass

    # -- invalidation / hot reload ----------------------------------------------
    def invalidate(self, asset_id: str | None = None) -> int:
        """Drop cache entries for one asset (or all). Returns how many."""
        if asset_id is None:
            n = len(self._cache)
            self._cache.clear()
            self._layer_lru.clear()
            return n
        keys = [k for k in self._cache if k[0] == asset_id]
        for k in keys:
            del self._cache[k]
            self._layer_lru.pop(k, None)
        self._warned.discard(asset_id)
        return len(keys)

    def reload(self, asset_id: str, reason: str = "") -> int:
        """Re-import the asset's module, drop its cache, emit AssetReloaded."""
        a = self.define(asset_id)
        if a.module:
            mod = self._modules.get(asset_id) or sys.modules.get(a.module)
            if mod is not None:
                _reexec(mod)
                self._modules[asset_id] = mod
        n = self.invalidate(asset_id)
        if self.bus is not None:
            self.bus.emit(AssetReloaded(asset_id, reason))
        if self.log is not None:
            try:
                self.log.info("assets", f"reloaded {asset_id} ({reason or 'manual'}), {n} cache entries dropped")
            except Exception:
                pass
        return n

    def watched_files(self) -> dict[str, list[str]]:
        """asset id -> files whose change should trigger a reload (module file + baked files)."""
        out: dict[str, list[str]] = {}
        for a in self.assets.values():
            files = []
            if a.module:
                try:
                    f = getattr(self.module(a.id), "__file__", None)
                except Exception:
                    f = None
                if f:
                    files.append(f)
            if a.rendered:
                for v in range(self.variants(a.id)):
                    p = self.baked_path(a.id, v)
                    if p:
                        files.append(p)
            elif a.path:
                files.append(os.path.join(self.root, a.path))
            out[a.id] = files
        return out

    def cache_size(self) -> int:
        return len(self._cache)
