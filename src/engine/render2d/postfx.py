"""render2d.postfx - full-screen post effects as cached surfaces + parameters (RPE6 §6.6).

Each effect is a pure function of its parameters, so the cache key is the parameter
tuple and a surface is built once per (size, params). The algorithms reproduce the
legacy overlays exactly (``core.config._make_vignette`` / ``_make_scanlines``) so a
mission can swap its module-level surface for ``postfx.vignette(...)`` with pixel
parity (unit-tested against the legacy builders).

    fx = PostFX()
    screen.blit(fx.vignette((W, H), 130, band=(top, bottom)), (0, 0))
    q.submit(OverlayDraw(fx.flash((W, H), (255, 255, 255)), alpha=120), Layer.UI)
"""
from __future__ import annotations

import math
import random
from typing import Any

import pygame

from .drawables import SCREEN, Drawable

__all__ = ["PostFX", "OverlayDraw", "vignette", "scanlines", "flash", "letterbox", "grain", "color_grade"]


def vignette(size: tuple[int, int], strength: int = 130, band: tuple[int, int] | None = None,
             step: int = 6) -> pygame.Surface:
    """Elliptical darkening toward the edges, centred on the scene band (legacy algorithm)."""
    w, h = int(size[0]), int(size[1])
    top, bot = band if band is not None else (0, h)
    vig = pygame.Surface((w, h), pygame.SRCALPHA)
    cx, cy = w // 2, (top + bot) // 2
    scene_h = bot - top
    max_r = int(math.hypot(w // 2, scene_h // 2)) + 10
    for r in range(max_r, 0, -step):
        t = 1.0 - (r / max_r)
        alpha = int(strength * t * t)
        alpha = min(alpha, strength)
        rw = int(r * 2)
        rh = int(r * 1.15)
        pygame.draw.ellipse(vig, (0, 0, 0, alpha), (cx - r, cy - rh // 2, rw, rh))
    return vig


def scanlines(size: tuple[int, int], band: tuple[int, int] | None = None, spacing: int = 4,
              alpha: int = 18) -> pygame.Surface:
    w, h = int(size[0]), int(size[1])
    top, bot = band if band is not None else (0, h)
    sl = pygame.Surface((w, h), pygame.SRCALPHA)
    for y in range(top, bot, spacing):
        pygame.draw.line(sl, (0, 0, 0, alpha), (0, y), (w, y))
    return sl


def flash(size: tuple[int, int], color: Any = (255, 255, 255)) -> pygame.Surface:
    """Opaque colour plate; fade it with ``OverlayDraw(alpha=...)`` / ``set_alpha``."""
    s = pygame.Surface((int(size[0]), int(size[1])))
    s.fill(color)
    return s


def letterbox(size: tuple[int, int], bar_h: int, line_color: Any = (40, 40, 40)) -> pygame.Surface:
    w, h = int(size[0]), int(size[1])
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.rect(s, (0, 0, 0, 255), (0, 0, w, bar_h))
    pygame.draw.rect(s, (0, 0, 0, 255), (0, h - bar_h, w, bar_h))
    pygame.draw.line(s, (*line_color, 255), (0, bar_h), (w, bar_h), 1)
    pygame.draw.line(s, (*line_color, 255), (0, h - bar_h), (w, h - bar_h), 1)
    return s


def grain(size: tuple[int, int], seed: int, amount: int = 18, density: float = 0.5) -> pygame.Surface:
    """Deterministic monochrome noise plate (seeded ``random.Random``, never the global rng)."""
    w, h = int(size[0]), int(size[1])
    rnd = random.Random(seed)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    px = pygame.PixelArray(s)
    try:
        for y in range(h):
            for x in range(w):
                if rnd.random() < density:
                    v = rnd.randint(0, amount)
                    px[x, y] = (v, v, v, amount)
    finally:
        px.close()
    return s


def color_grade(size: tuple[int, int], tint: tuple[int, int, int], alpha: int) -> pygame.Surface:
    s = pygame.Surface((int(size[0]), int(size[1])), pygame.SRCALPHA)
    s.fill((*tint, int(alpha)))
    return s


_BUILDERS = {"vignette": vignette, "scanlines": scanlines, "flash": flash, "letterbox": letterbox, "grain": grain,
             "color_grade": color_grade}


class PostFX:
    """Parameter-keyed cache over the builders above."""

    def __init__(self) -> None:
        self._cache: dict[tuple, pygame.Surface] = {}

    def get(self, kind: str, *args: Any, **kw: Any) -> pygame.Surface:
        key = (kind, args, tuple(sorted(kw.items())))
        s = self._cache.get(key)
        if s is None:
            s = _BUILDERS[kind](*args, **kw)
            self._cache[key] = s
        return s

    def vignette(self, size, strength=130, band=None):
        return self.get("vignette", tuple(size), int(strength), None if band is None else tuple(band))

    def scanlines(self, size, band=None, spacing=4, alpha=18):
        return self.get("scanlines", tuple(size), None if band is None else tuple(band), int(spacing), int(alpha))

    def flash(self, size, color=(255, 255, 255)):
        return self.get("flash", tuple(size), tuple(color))

    def letterbox(self, size, bar_h, line_color=(40, 40, 40)):
        return self.get("letterbox", tuple(size), int(bar_h), tuple(line_color))

    def grain(self, size, seed, amount=18, density=0.5):
        return self.get("grain", tuple(size), int(seed), int(amount), float(density))

    def color_grade(self, size, tint, alpha):
        return self.get("color_grade", tuple(size), tuple(tint), int(alpha))

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


class OverlayDraw(Drawable):
    """Full-screen (or positioned) screen-space blit of a post-FX plate with an optional alpha."""

    __slots__ = ("surface", "alpha")
    kind = "overlay"

    def __init__(self, surface: pygame.Surface, *, alpha: int | None = None, pos: tuple[float, float] = (0.0, 0.0)) -> None:
        super().__init__(pos, SCREEN)
        self.surface = surface
        self.alpha = alpha

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        img = self.surface
        if self.alpha is not None:
            img.set_alpha(max(0, min(255, int(self.alpha))))
        surface.blit(img, (int(self.pos[0]), int(self.pos[1])))
        return 1
