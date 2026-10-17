"""render2d.queue - the sorted render queue and its layer table (RPE6 §6.6, Phase 6).

    q = RenderQueue()
    q.begin(cam_x, cam_y, clear=(12, 12, 14))
    q.submit(SurfaceDraw(img, (wx, wy), anchor="midbottom"), Layer.ENTITIES)
    stats = q.flush(screen)

Draw order is fixed by the layer table; inside a layer items are ordered by
``sort_key`` (y-sorted layers default to the drawable's ``world_y()``, the other
layers to insertion order) and ties keep insertion order. Explicit keys are how a
mission keeps an authored order inside a y-sorted layer (ADR-017): pass the same key
convention for every item of that layer.

``flush`` never swallows exceptions: a failing drawable aborts the frame loudly
(R1 - an exception is easier to fix than a silently missing layer).
"""
from __future__ import annotations

import time
from enum import IntEnum
from typing import Any, Callable, Iterable

import pygame

from .drawables import CustomDraw, DrawContext, Drawable, FillDraw, RotationCache, UiPassDraw

__all__ = ["Layer", "LAYER_NAMES", "Y_SORTED", "RenderStats", "RenderQueue"]


class Layer(IntEnum):
    FLOOR = 0
    DECOR_STATIC = 1
    DECALS_DYNAMIC = 2
    SHADOWS = 3
    ENTITIES = 4
    FX_WORLD = 5
    LIGHTING = 6
    OVERLAY_WORLD = 7
    UI = 8
    DEBUG = 9


LAYER_NAMES = tuple(l.name.lower() for l in Layer)
Y_SORTED = frozenset({Layer.SHADOWS, Layer.ENTITIES, Layer.FX_WORLD, Layer.OVERLAY_WORLD})


class RenderStats:
    """Per-flush counters: draws and blits per layer, custom draws (named), cache hits, ms per layer."""

    __slots__ = ("draws", "blits", "ms", "custom", "custom_names", "ui_passes", "ui_names", "cache_hits",
                 "cache_misses", "frame")

    def __init__(self) -> None:
        self.draws = [0] * len(Layer)
        self.blits = [0] * len(Layer)
        self.ms = [0.0] * len(Layer)
        self.custom = 0
        self.custom_names: list[str] = []
        self.ui_passes = 0
        self.ui_names: list[str] = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.frame = 0

    @property
    def total_draws(self) -> int:
        return sum(self.draws)

    def as_dict(self) -> dict[str, Any]:
        return {"frame": self.frame, "draws": dict(zip(LAYER_NAMES, self.draws)),
                "blits": dict(zip(LAYER_NAMES, self.blits)),
                "ms": {n: round(v, 3) for n, v in zip(LAYER_NAMES, self.ms)},
                "custom": self.custom, "custom_names": list(self.custom_names),
                "ui_passes": self.ui_passes, "ui_names": list(self.ui_names),
                "cache_hits": self.cache_hits, "cache_misses": self.cache_misses}

    def lines(self) -> list[str]:
        out = [f"frame {self.frame}: {self.total_draws} draws, {sum(self.blits)} blits, custom={self.custom}, "
               f"ui_passes={self.ui_passes}, rot-cache {self.cache_hits}/{self.cache_hits + self.cache_misses}"]
        for i, name in enumerate(LAYER_NAMES):
            if self.draws[i]:
                out.append(f"  {i} {name:<14} draws={self.draws[i]:<5} blits={self.blits[i]:<5} {self.ms[i]:.2f} ms")
        if self.custom_names:
            out.append("  custom: " + ", ".join(self.custom_names))
        return out


class RenderQueue:
    def __init__(self, resolver: Callable[..., Any] | None = None, rotations: RotationCache | None = None) -> None:
        self._items: list[list[Drawable]] = [[] for _ in Layer]
        self._seq = 0
        self.cam_x = 0
        self.cam_y = 0
        self.viewport = (0, 0)                  # target size of the frame being built (set by begin)
        self.ctx = DrawContext(resolver, rotations)
        self.stats = RenderStats()
        self.frames = 0
        self.warn_custom: Callable[[str], None] | None = None
        self.sorted_layers: frozenset = Y_SORTED

    # ── frame protocol ─────────────────────────────────────────────────────
    def begin(self, cam_x: int = 0, cam_y: int = 0, *, clear: Any = None, viewport: Any = None) -> None:
        for lst in self._items:
            lst.clear()
        self._seq = 0
        self.cam_x, self.cam_y = int(cam_x), int(cam_y)
        if viewport is not None:
            self.viewport = (int(viewport[0]), int(viewport[1]))
        if clear is not None:
            self.submit(FillDraw(clear), Layer.FLOOR, sort_key=float("-inf"))

    def submit(self, drawable: Drawable, layer: int | Layer = Layer.ENTITIES, sort_key: Any = None) -> Drawable:
        li = int(layer)
        if not 0 <= li < len(Layer):
            raise ValueError(f"render2d: unknown layer {layer!r}")
        drawable.layer = li
        drawable.sort_key = sort_key
        drawable.seq = self._seq
        self._seq += 1
        self._items[li].append(drawable)
        return drawable

    def submit_many(self, drawables: Iterable[Drawable], layer: int | Layer, sort_key: Any = None) -> int:
        n = 0
        for d in drawables:
            self.submit(d, layer, sort_key)
            n += 1
        return n

    def items(self, layer: int | Layer | None = None) -> list[Drawable]:
        if layer is None:
            return [d for lst in self._items for d in lst]
        return list(self._items[int(layer)])

    def pending(self) -> int:
        return sum(len(lst) for lst in self._items)

    def _order(self, layer: int, items: list[Drawable]) -> list[Drawable]:
        if len(items) < 2:
            return items
        if layer in self.sorted_layers:
            def key(d: Drawable):
                k = d.sort_key if d.sort_key is not None else d.world_y()
                return (k, d.seq)
        else:
            def key(d: Drawable):
                k = d.sort_key if d.sort_key is not None else 0
                return (k, d.seq)
        return sorted(items, key=key)

    def flush(self, surface: pygame.Surface) -> RenderStats:
        st = RenderStats()
        st.frame = self.frames
        ctx = self.ctx
        h0, m0 = ctx.rotations.hits, ctx.rotations.misses
        for li, items in enumerate(self._items):
            if not items:
                continue
            t0 = time.perf_counter()
            for d in self._order(li, items):
                st.blits[li] += int(d.draw(surface, self.cam_x, self.cam_y, ctx) or 0)
                st.draws[li] += 1
                if isinstance(d, CustomDraw):
                    st.custom += 1
                    st.custom_names.append(d.name)
                    if self.warn_custom is not None:
                        self.warn_custom(d.name)
                elif isinstance(d, UiPassDraw):
                    st.ui_passes += 1
                    st.ui_names.append(d.name)
            st.ms[li] = (time.perf_counter() - t0) * 1000.0
            items.clear()
        st.cache_hits = ctx.rotations.hits - h0
        st.cache_misses = ctx.rotations.misses - m0
        self.stats = st
        self.frames += 1
        return st

    def describe(self) -> list[dict[str, Any]]:
        """Submitted-but-not-flushed items in draw order (inspector / tests)."""
        out = []
        for li, items in enumerate(self._items):
            for d in self._order(li, items):
                out.append(d.describe())
        return out
