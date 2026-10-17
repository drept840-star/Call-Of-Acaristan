"""render2d.drawables - the things a RenderQueue draws (RPE6 §6.6, Phase 6).

A drawable is a small object with a ``draw(surface, cam_x, cam_y)`` method and a
``world_y()`` used by the y-sorted layers. World-space drawables are placed with the
camera subtracted; screen-space ones (``space="screen"``) are not. Every drawable is
plain data - resolving an asset or a rotation happens at draw time against the caches
passed in by the queue, so a submitted frame can be inspected (``describe()``) and
counted before a single pixel is touched.

``CustomDraw`` is the escape hatch of the strangler migration: it wraps a legacy
``fn(surface, cam_x, cam_y)`` painter. The queue counts them (D6 metric) and the
report names them, so they only ever go down.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Iterable, Sequence

import pygame

__all__ = [
    "Drawable", "SurfaceDraw", "SpriteDraw", "RotatedSpriteDraw", "RotationCache", "TextDraw", "LineDraw",
    "PolyDraw", "SurfaceBatchDraw", "CircleDraw", "RectDraw", "EllipseDraw", "ArcDraw", "FillDraw", "CustomDraw", "UiPassDraw", "WORLD", "SCREEN",
]

WORLD = "world"
SCREEN = "screen"

_ANCHORS = {
    "topleft": (0.0, 0.0), "midtop": (0.5, 0.0), "topright": (1.0, 0.0),
    "midleft": (0.0, 0.5), "center": (0.5, 0.5), "midright": (1.0, 0.5),
    "bottomleft": (0.0, 1.0), "midbottom": (0.5, 1.0), "bottomright": (1.0, 1.0),
}


def _anchor_offset(anchor: Any, w: int, h: int) -> tuple[int, int]:
    """Pixel offset of ``anchor`` (name or (fx, fy) fractions or (px, py) ints) inside a w×h surface."""
    if isinstance(anchor, str):
        fx, fy = _ANCHORS[anchor]
        return int(w * fx), int(h * fy)
    ax, ay = anchor
    if isinstance(ax, float) or isinstance(ay, float):
        return int(w * ax), int(h * ay)
    return int(ax), int(ay)


class Drawable:
    """Base: ``pos`` is world or screen space; ``layer``/``sort_key``/``seq`` are set by the queue."""

    __slots__ = ("pos", "space", "layer", "sort_key", "seq")
    kind = "drawable"

    def __init__(self, pos: tuple[float, float] = (0.0, 0.0), space: str = WORLD) -> None:
        self.pos = (float(pos[0]), float(pos[1]))
        self.space = space
        self.layer: int = -1
        self.sort_key: Any = None
        self.seq: int = 0

    # ── queue protocol ──────────────────────────────────────────────────────
    def world_y(self) -> float:
        """Default y-sort key: the drawable's y (feet for sprites anchored at midbottom)."""
        return self.pos[1]

    def screen_pos(self, cam_x: int, cam_y: int) -> tuple[float, float]:
        """Screen position before truncation. Each drawable applies ``int()`` once, at the end of its own
        arithmetic (``int(x - cam_x - anchor)``) - the legacy idiom - so sub-pixel positions round the
        same way the old painters did. Callers that need a different truncation order pass screen-space
        integers."""
        x, y = self.pos
        if self.space == WORLD:
            return x - cam_x, y - cam_y
        return x, y

    def draw(self, surface: pygame.Surface, cam_x: int, cam_y: int, ctx: "DrawContext | None" = None) -> int:
        """Paint onto ``surface``; return the number of blits/primitive calls made (stats)."""
        raise NotImplementedError

    def describe(self) -> dict[str, Any]:
        return {"kind": self.kind, "pos": self.pos, "space": self.space, "layer": self.layer,
                "sort_key": self.sort_key}


class DrawContext:
    """Caches the queue hands to drawables at draw time (asset resolver, rotation cache, stats)."""

    __slots__ = ("resolver", "rotations", "cache_hits", "cache_misses")

    def __init__(self, resolver: Callable[..., Any] | None = None, rotations: "RotationCache | None" = None) -> None:
        self.resolver = resolver
        self.rotations = rotations or RotationCache()
        self.cache_hits = 0
        self.cache_misses = 0


def _blit(surface: pygame.Surface, img: pygame.Surface, sx: float, sy: float, anchor: Any, alpha: int | None,
          flags: int = 0) -> int:
    ox, oy = _anchor_offset(anchor, img.get_width(), img.get_height())
    if alpha is not None and alpha < 255:
        img = img.copy()
        img.set_alpha(max(0, int(alpha)))
    surface.blit(img, (int(sx - ox), int(sy - oy)), special_flags=flags)
    return 1


class SurfaceDraw(Drawable):
    """Blit an already prepared surface (sprite caches, baked chunks, pre-rendered text)."""

    __slots__ = ("surface", "anchor", "alpha", "area", "flags")
    kind = "surface"

    def __init__(self, surface: pygame.Surface, pos: tuple[float, float], *, anchor: Any = "topleft",
                 alpha: int | None = None, space: str = WORLD, area: pygame.Rect | None = None,
                 flags: int = 0) -> None:
        super().__init__(pos, space)
        self.surface = surface
        self.anchor = anchor
        self.alpha = alpha
        self.area = area
        self.flags = flags                      # pygame special_flags (BLEND_RGB_ADD, ...)

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        if self.area is not None:
            surface.blit(self.surface, (int(sx), int(sy)), self.area, special_flags=self.flags)
            return 1
        return _blit(surface, self.surface, sx, sy, self.anchor, self.alpha, self.flags)


class SurfaceBatchDraw(Drawable):
    """Many prepared surfaces blitted in submission order (rain fields, decal sheets) - one
    queue item, so per-item queue overhead is paid once (§6.22 batching). Items are
    ``(surface, pos)`` in this drawable's space."""

    __slots__ = ("items",)
    kind = "batch"

    def __init__(self, items, *, space: str = SCREEN) -> None:
        super().__init__(items[0][1] if items else (0.0, 0.0), space)
        self.items = list(items)

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        n = 0
        if self.space == WORLD:
            for img, (x, y) in self.items:
                surface.blit(img, (int(x - cam_x), int(y - cam_y)))
                n += 1
        else:
            for img, pos in self.items:
                surface.blit(img, (int(pos[0]), int(pos[1])))
                n += 1
        return n


class SpriteDraw(Drawable):
    """Asset-resolved sprite: ``resolver(asset, variant, scale)`` -> surface (``engine.assets`` registry)."""

    __slots__ = ("asset", "variant", "anchor", "alpha", "tint", "flip", "scale")
    kind = "sprite"

    def __init__(self, asset: str, variant: Any, pos: tuple[float, float], *, anchor: Any = "center",
                 alpha: int | None = None, tint: tuple[int, int, int] | None = None,
                 flip: tuple[bool, bool] = (False, False), scale: float = 1.0, space: str = WORLD) -> None:
        super().__init__(pos, space)
        self.asset, self.variant, self.anchor = asset, variant, anchor
        self.alpha, self.tint, self.flip, self.scale = alpha, tint, flip, scale

    def resolve(self, ctx: DrawContext | None) -> pygame.Surface | None:
        if ctx is None or ctx.resolver is None:
            return None
        img = ctx.resolver(self.asset, self.variant, self.scale)
        if img is None:
            return None
        if self.flip != (False, False):
            img = pygame.transform.flip(img, bool(self.flip[0]), bool(self.flip[1]))
        if self.tint is not None:
            img = img.copy()
            img.fill(self.tint, special_flags=pygame.BLEND_RGB_MULT)
        return img

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        img = self.resolve(ctx)
        if img is None:
            return 0
        sx, sy = self.screen_pos(cam_x, cam_y)
        return _blit(surface, img, sx, sy, self.anchor, self.alpha)

    def describe(self):
        d = super().describe()
        d.update(asset=self.asset, variant=self.variant)
        return d


class RotationCache:
    """Pre-rotated surfaces per heading bucket (generalises the M5 guard cache).

    ``get(base, angle, buckets, key)``: ``key`` identifies the base image (asset id +
    variant, or ``id(base)`` when the caller holds the surface). Rotation uses
    ``pygame.transform.rotate(base, -bucket * 360 / buckets)`` exactly like the legacy
    guard path, so the pixels are the same for the same base and bucket.
    """

    def __init__(self, limit: int = 4096) -> None:
        self._cache: dict[tuple[Any, int, int], pygame.Surface] = {}
        self.limit = limit
        self.hits = 0
        self.misses = 0

    @staticmethod
    def bucket_of(angle: float, buckets: int) -> int:
        return int(round(angle / (2 * math.pi) * buckets)) % buckets

    def get(self, base: pygame.Surface, angle: float, buckets: int = 64, key: Any = None) -> pygame.Surface:
        b = self.bucket_of(angle, buckets)
        k = (key if key is not None else id(base), buckets, b)
        spr = self._cache.get(k)
        if spr is None:
            self.misses += 1
            if len(self._cache) >= self.limit:
                self._cache.clear()
            spr = pygame.transform.rotate(base, -b * 360.0 / buckets)
            self._cache[k] = spr
        else:
            self.hits += 1
        return spr

    def clear(self) -> None:
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)


class RotatedSpriteDraw(Drawable):
    """A base surface (or asset) rotated to the nearest of ``buckets`` headings, blitted centred."""

    __slots__ = ("base", "asset", "variant", "angle", "buckets", "anchor", "alpha", "key")
    kind = "rotated"

    def __init__(self, pos: tuple[float, float], angle: float, *, base: pygame.Surface | None = None,
                 asset: str | None = None, variant: Any = 0, buckets: int = 64, anchor: Any = "center",
                 alpha: int | None = None, key: Any = None, space: str = WORLD) -> None:
        super().__init__(pos, space)
        self.base, self.asset, self.variant = base, asset, variant
        self.angle, self.buckets, self.anchor, self.alpha = float(angle), int(buckets), anchor, alpha
        self.key = key

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        base = self.base
        key = self.key
        if base is None:
            if ctx is None or ctx.resolver is None or self.asset is None:
                return 0
            base = ctx.resolver(self.asset, self.variant, 1.0)
            if base is None:
                return 0
            key = key or (self.asset, self.variant)
        rot = ctx.rotations if ctx is not None else RotationCache()
        img = rot.get(base, self.angle, self.buckets, key)
        sx, sy = self.screen_pos(cam_x, cam_y)
        return _blit(surface, img, sx, sy, self.anchor, self.alpha)

    def describe(self):
        d = super().describe()
        d.update(asset=self.asset, variant=self.variant, angle=self.angle, buckets=self.buckets)
        return d


class TextDraw(Drawable):
    """``font.render(text, True, color)`` at ``pos`` (optional shadow offset / colour)."""

    __slots__ = ("text", "font", "color", "shadow", "shadow_color", "anchor", "antialias")
    kind = "text"

    def __init__(self, text: str, font: Any, pos: tuple[float, float], color: Any = (255, 255, 255), *,
                 shadow: tuple[int, int] | None = None, shadow_color: Any = (0, 0, 0), anchor: Any = "topleft",
                 antialias: bool = True, space: str = SCREEN) -> None:
        super().__init__(pos, space)
        self.text, self.font, self.color = text, font, color
        self.shadow, self.shadow_color, self.anchor, self.antialias = shadow, shadow_color, anchor, antialias

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        n = 0
        if self.shadow is not None:
            sh = self.font.render(self.text, self.antialias, self.shadow_color)
            n += _blit(surface, sh, sx + self.shadow[0], sy + self.shadow[1], self.anchor, None)
        img = self.font.render(self.text, self.antialias, self.color)
        return n + _blit(surface, img, sx, sy, self.anchor, None)

    def describe(self):
        d = super().describe()
        d.update(text=self.text)
        return d


def _shift(points: Iterable[Sequence[float]], dx: int, dy: int) -> list[tuple[float, float]]:
    # Numbers pass through untouched (minus the camera in world space): pygame applies the same
    # float->int conversion the legacy call sites relied on. Callers that truncated explicitly
    # submit screen-space ints (truncation rule, ADR-017).
    return [(p[0] - dx, p[1] - dy) for p in points]


class LineDraw(Drawable):
    """``pygame.draw.line``/``lines`` in world or screen space."""

    __slots__ = ("points", "color", "width", "closed")
    kind = "line"

    def __init__(self, points: Sequence[Sequence[float]], color: Any, width: int = 1, *, closed: bool = False,
                 space: str = WORLD) -> None:
        super().__init__(points[0] if points else (0.0, 0.0), space)
        self.points, self.color, self.width, self.closed = [tuple(p) for p in points], color, int(width), closed

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        dx, dy = (cam_x, cam_y) if self.space == WORLD else (0, 0)
        pts = _shift(self.points, dx, dy)
        if len(pts) == 2:
            pygame.draw.line(surface, self.color, pts[0], pts[1], self.width)
        elif len(pts) > 2:
            pygame.draw.lines(surface, self.color, self.closed, pts, self.width)
        return 1


class PolyDraw(Drawable):
    __slots__ = ("points", "color", "width")
    kind = "poly"

    def __init__(self, points: Sequence[Sequence[float]], color: Any, width: int = 0, *, space: str = WORLD) -> None:
        super().__init__(points[0] if points else (0.0, 0.0), space)
        self.points, self.color, self.width = [tuple(p) for p in points], color, int(width)

    def world_y(self) -> float:
        return max(p[1] for p in self.points) if self.points else 0.0

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        dx, dy = (cam_x, cam_y) if self.space == WORLD else (0, 0)
        pygame.draw.polygon(surface, self.color, _shift(self.points, dx, dy), self.width)
        return 1


class CircleDraw(Drawable):
    __slots__ = ("radius", "color", "width")
    kind = "circle"

    def __init__(self, pos: tuple[float, float], radius: float, color: Any, width: int = 0, *,
                 space: str = WORLD) -> None:
        super().__init__(pos, space)
        self.radius, self.color, self.width = radius, color, int(width)

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        pygame.draw.circle(surface, self.color, (sx, sy), self.radius, self.width)
        return 1


class RectDraw(Drawable):
    __slots__ = ("size", "color", "width", "border_radius")
    kind = "rect"

    def __init__(self, rect: Any, color: Any, width: int = 0, *, border_radius: int = 0, space: str = WORLD) -> None:
        if isinstance(rect, pygame.Rect):
            x, y, w, h = rect.x, rect.y, rect.w, rect.h
        else:                                   # (x, y, w, h) - floats pass through untouched
            x, y, w, h = rect
        super().__init__((x, y), space)
        self.size, self.color, self.width, self.border_radius = (w, h), color, int(width), int(border_radius)

    def world_y(self) -> float:
        return self.pos[1] + self.size[1]

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        pygame.draw.rect(surface, self.color, (sx, sy, self.size[0], self.size[1]), self.width,
                         border_radius=self.border_radius)
        return 1


class EllipseDraw(RectDraw):
    """``pygame.draw.ellipse`` inside ``rect`` (same pass-through numbers as ``RectDraw``)."""

    __slots__ = ()
    kind = "ellipse"

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        pygame.draw.ellipse(surface, self.color, (sx, sy, self.size[0], self.size[1]), self.width)
        return 1


class ArcDraw(RectDraw):
    """``pygame.draw.arc`` inside ``rect`` from ``start`` to ``stop`` radians."""

    __slots__ = ("start", "stop")
    kind = "arc"

    def __init__(self, rect: Any, color: Any, start: float, stop: float, width: int = 1, *,
                 space: str = WORLD) -> None:
        super().__init__(rect, color, width, space=space)
        self.start, self.stop = start, stop

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        sx, sy = self.screen_pos(cam_x, cam_y)
        pygame.draw.arc(surface, self.color, (sx, sy, self.size[0], self.size[1]), self.start, self.stop, self.width)
        return 1


class FillDraw(Drawable):
    """Fill the whole target (frame clear) - screen space by nature."""

    __slots__ = ("color",)
    kind = "fill"

    def __init__(self, color: Any) -> None:
        super().__init__((0.0, 0.0), SCREEN)
        self.color = color

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        surface.fill(self.color)
        return 1


class UiPassDraw(Drawable):
    """The UI pass (§6.6 layer 8): ``fn(surface)`` draws a widget tree (``engine.ui`` widgets composed
    with mission data). Counted as a UI pass, not as a custom draw - it is the declared place for
    HUD/dialogue/menus; world painting inside a UI pass is what the D6 census still catches."""

    __slots__ = ("fn", "name")
    kind = "ui_pass"

    def __init__(self, fn: Callable[[pygame.Surface], Any], name: str = "") -> None:
        super().__init__((0.0, 0.0), SCREEN)
        self.fn = fn
        self.name = name or getattr(fn, "__qualname__", getattr(fn, "__name__", "ui"))

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        self.fn(surface)
        return 1

    def describe(self):
        d = super().describe()
        d.update(name=self.name)
        return d


class CustomDraw(Drawable):
    """Escape hatch: ``fn(surface, cam_x, cam_y)``. Counted by the queue; named in the stats."""

    __slots__ = ("fn", "name")
    kind = "custom"

    def __init__(self, fn: Callable[[pygame.Surface, int, int], Any], name: str = "", *,
                 pos: tuple[float, float] = (0.0, 0.0), space: str = WORLD) -> None:
        super().__init__(pos, space)
        self.fn = fn
        self.name = name or getattr(fn, "__qualname__", getattr(fn, "__name__", "custom"))

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        self.fn(surface, cam_x, cam_y)
        return 1

    def describe(self):
        d = super().describe()
        d.update(name=self.name)
        return d
