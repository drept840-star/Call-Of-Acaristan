"""lighting.lightmap - multiplicative 2D light map (RPE6 Phase 6, §6.6 lighting integration).

Model (moved verbatim from the M5 night look, ``missions.m5.decor.draw_over``): the scene is
multiplied by a light map stored at *half scale* and doubled after the multiply, so lamps can
push the painted floor up to 2x its base colour while the gaps go properly dark:

    map  = ambient/2 + sum(falloff sprites, additive)
    out  = scene * map * 2        (BLEND_RGB_MULT, then scene + scene)

``falloff_sprite`` is the smooth ``(1-d)^1.7`` lamp pool, ``bloom_sprite`` the faint additive
bulb halo; both are cached per ``(radius, colour)``. ``LightMapDraw`` is the queue drawable:
the caller samples flicker/visibility at submit time and hands over screen-space ``(sprite,
pos)`` pairs; the draw applies the map to whatever is on the target at that point of the flush.
"""
from __future__ import annotations

import pygame

from engine.render2d.drawables import Drawable, SCREEN

__all__ = ["LightMap", "LightMapDraw", "falloff_sprite", "bloom_sprite"]

_falloffs: dict = {}
_blooms: dict = {}


def falloff_sprite(radius, col):
    """Smooth (1-d)^1.7 falloff in many fine steps (no visible rings); opaque, black = no light."""
    key = (radius, col)
    g = _falloffs.get(key)
    if g is None:
        g = pygame.Surface((radius * 2, radius * 2))
        g.fill((0, 0, 0))
        steps = max(24, radius // 3)
        for i in range(steps, 0, -1):
            d = i / steps
            k = 0.66 * min(1.0, 1.7 * (1.0 - d) ** 1.7)   # bright core, long soft tail (2x map)
            pygame.draw.circle(g, (int(col[0] * k), int(col[1] * k), int(col[2] * k)),
                               (radius, radius), max(1, int(radius * d)))
        _falloffs[key] = g
    return g


def bloom_sprite(radius, col):
    """Faint additive bloom around the bulb itself."""
    key = (radius, col)
    g = _blooms.get(key)
    if g is None:
        g = pygame.Surface((radius * 2, radius * 2))
        g.fill((0, 0, 0))
        steps = max(12, radius // 3)
        for i in range(steps, 0, -1):
            d = i / steps
            k = 0.22 * (1.0 - d) ** 2.2
            pygame.draw.circle(g, (int(col[0] * k), int(col[1] * k), int(col[2] * k)),
                               (radius, radius), max(1, int(radius * d)))
        _blooms[key] = g
    return g


class LightMap:
    """Owns one reusable map surface per target size."""

    __slots__ = ("_maps",)

    def __init__(self) -> None:
        self._maps: dict = {}

    def surface(self, size) -> pygame.Surface:
        lm = self._maps.get(tuple(size))
        if lm is None:
            lm = self._maps[tuple(size)] = pygame.Surface(size)
        return lm

    def apply(self, target: pygame.Surface, ambient, lamps) -> pygame.Surface:
        """``target *= (ambient/2 + lamps) * 2``; ``lamps`` are ``(sprite, (x, y))`` in screen space."""
        lm = self.surface(target.get_size())
        lm.fill(tuple(c // 2 for c in ambient))
        add = pygame.BLEND_RGB_ADD
        for sprite, pos in lamps:
            lm.blit(sprite, pos, special_flags=add)
        target.blit(lm, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        target.blit(target.copy(), (0, 0), special_flags=add)
        return lm


_shared: list = []


def _shared_map() -> LightMap:
    if not _shared:
        _shared.append(LightMap())
    return _shared[0]


class LightMapDraw(Drawable):
    """Apply a multiplicative light map, then additive blooms, at this point of the flush."""

    __slots__ = ("ambient", "lamps", "blooms", "lightmap")
    kind = "lighting"

    def __init__(self, ambient, lamps, blooms=(), *, lightmap: LightMap | None = None) -> None:
        super().__init__((0, 0), SCREEN)
        self.ambient = tuple(ambient)
        self.lamps = list(lamps)
        self.blooms = list(blooms)
        self.lightmap = lightmap

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        (self.lightmap or _shared_map()).apply(surface, self.ambient, self.lamps)
        add = pygame.BLEND_RGB_ADD
        for sprite, pos in self.blooms:
            surface.blit(sprite, pos, special_flags=add)
        return 1 + len(self.lamps) + len(self.blooms)
