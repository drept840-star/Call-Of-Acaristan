
"""staticlayer.py - chunked bake of the static world (phase 0).

Mission 3 re-executed ~1,100 procedural draw calls every frame for geometry
that never changes (floors, walls, shelves, cabinets, pipes, signage). This
module bakes that geometry once into 512x512 chunks at first sight and
blits 2-4 chunks per frame afterwards.

Contract for the bake callback ``bake_cb(surface, origin_x, origin_y)``:
draw the *static* world as seen from a camera at (origin_x, origin_y) onto
``surface`` (512x512). Deterministic only - anything animated must consult
:func:`baking` and emit its static base frame; the dynamic counterpart then
runs in the per-frame pass.

Chunks are LRU-cached (cap 24 ≈ 24 MB RGBA worst case, typically far less)
and ``invalidate_all()`` is called on mission (re)start and display-mode
change.
"""

import os

import pygame

CHUNK = 512
_CAP = 24

_BAKING = False


def enabled():
    """ACA_STATIC=off bypasses the bake (A/B benchmarking, debugging)."""
    return os.environ.get("ACA_STATIC", "") != "off"


def baking():
    """True while a static chunk is being baked (animated draws check this)."""
    return _BAKING


def set_baking(v):
    global _BAKING
    _BAKING = v


class StaticLayer:
    def __init__(self, world_w, world_h, chunk=CHUNK, cap=_CAP):
        self.world_w = world_w
        self.world_h = world_h
        self.chunk = chunk
        self._cap = cap
        self.cols = max(1, -(-world_w // chunk))
        self.rows = max(1, -(-world_h // chunk))
        self._grid = {}
        self._order = []

    def invalidate_all(self):
        self._grid.clear()
        del self._order[:]

    def _bake(self, ci, cj, bake_cb):
        surf = pygame.Surface((self.chunk, self.chunk))
        surf.fill((0, 0, 0))
        set_baking(True)
        try:
            bake_cb(surf, ci * self.chunk, cj * self.chunk)
        finally:
            set_baking(False)
        key = (ci, cj)
        self._grid[key] = surf
        self._order.append(key)
        if len(self._order) > self._cap:
            self._grid.pop(self._order.pop(0), None)
        return surf

    def blit(self, target, cam_x, cam_y, bake_cb):
        """Blit every chunk overlapping the view at (cam_x, cam_y)."""
        c = self.chunk
        ci0 = max(0, cam_x // c)
        cj0 = max(0, cam_y // c)
        ci1 = min(self.cols - 1, (cam_x + target.get_width()) // c)
        cj1 = min(self.rows - 1, (cam_y + target.get_height()) // c)
        for cj in range(cj0, cj1 + 1):
            for ci in range(ci0, ci1 + 1):
                key = (ci, cj)
                surf = self._grid.get(key)
                if surf is None:
                    surf = self._bake(ci, cj, bake_cb)
                target.blit(surf, (ci * c - cam_x, cj * c - cam_y))
        return True


# Keyed layer registry: one StaticLayer slot per owning family ("m1",
# "m2", "m3"). The owning mission composes ``key`` from everything that
# identifies the baked content (stage, map identity, wall signature, ...);
# when the key changes the old layer is dropped so a mission restart can
# never reuse stale chunks, and the registry itself stays bounded.
_LAYERS = {}


def get_layer(family, key, world_w, world_h, chunk=CHUNK, cap=_CAP):
    """Return the family's cached StaticLayer for ``key``, if any."""
    slot = _LAYERS.get(family)
    if slot is not None:
        old_key, lay = slot
        if (old_key == key and lay.world_w == world_w
                and lay.world_h == world_h and lay.chunk == chunk):
            return lay
    lay = StaticLayer(world_w, world_h, chunk, cap)
    _LAYERS[family] = (key, lay)
    return lay
