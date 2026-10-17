"""render2d.static - StaticLayers: chunked bakes of floor/decor painters (RPE6 §6.6).

A static layer is a painter plus a signature:

    layers.define("floor", painter=paint_tiles, world_size=(w_px, h_px),
                  signature=("quarter", rows_hash), fill=(12, 12, 14))
    layers.blit(screen, "floor", cam_x, cam_y, (WIDTH, HEIGHT))

``painter(target, ox, oy, w, h)`` paints the world rectangle ``(ox, oy, w, h)`` into
``target`` at (0, 0) - the decor-painter contract: it reads no game state beyond
what the signature captures and adds no solids. Chunks (default 1024²) are painted
lazily the first time they are visible and dropped when the signature changes
(level edit, hot reload, stage change). ``fill`` is painted under the chunk so a
chunk composes exactly like painting the same tiles on a cleared screen.
"""
from __future__ import annotations

from typing import Any, Callable

import pygame

from .drawables import SCREEN, Drawable

__all__ = ["StaticLayers", "StaticLayer", "StaticLayerDraw"]

Painter = Callable[[pygame.Surface, int, int, int, int], None]


class StaticLayer:
    __slots__ = ("name", "painter", "world_w", "world_h", "signature", "fill", "chunk", "chunks", "built")

    def __init__(self, name: str, painter: Painter, world_size: tuple[int, int], signature: Any, fill: Any,
                 chunk: int) -> None:
        self.name = name
        self.painter = painter
        self.world_w, self.world_h = int(world_size[0]), int(world_size[1])
        self.signature = signature
        self.fill = fill
        self.chunk = int(chunk)
        self.chunks: dict[tuple[int, int], pygame.Surface] = {}
        self.built = 0

    def chunk_surface(self, cx: int, cy: int) -> pygame.Surface | None:
        ox, oy = cx * self.chunk, cy * self.chunk
        if ox >= self.world_w or oy >= self.world_h or ox < 0 or oy < 0:
            return None
        surf = self.chunks.get((cx, cy))
        if surf is None:
            w = min(self.chunk, self.world_w - ox)
            h = min(self.chunk, self.world_h - oy)
            surf = pygame.Surface((w, h))
            if self.fill is not None:
                surf.fill(self.fill)
            self.painter(surf, ox, oy, w, h)
            self.chunks[(cx, cy)] = surf
            self.built += 1
        return surf


class StaticLayers:
    def __init__(self, chunk: int = 1024) -> None:
        self.chunk = int(chunk)
        self._layers: dict[str, StaticLayer] = {}
        self.blits = 0

    def define(self, name: str, *, painter: Painter, world_size: tuple[int, int], signature: Any = None,
               fill: Any = None, chunk: int | None = None) -> StaticLayer:
        """(Re)declare a layer; chunks survive while ``signature`` and world size are unchanged."""
        cur = self._layers.get(name)
        chunk = int(chunk or self.chunk)
        if (cur is not None and cur.signature == signature and (cur.world_w, cur.world_h) == tuple(map(int, world_size))
                and cur.chunk == chunk):
            cur.painter = painter
            cur.fill = fill
            return cur
        layer = StaticLayer(name, painter, world_size, signature, fill, chunk)
        self._layers[name] = layer
        return layer

    def has(self, name: str) -> bool:
        return name in self._layers

    def layer(self, name: str) -> StaticLayer:
        return self._layers[name]

    def invalidate(self, name: str | None = None) -> None:
        if name is None:
            for l in self._layers.values():
                l.chunks.clear()
        elif name in self._layers:
            self._layers[name].chunks.clear()

    def drop(self, name: str) -> None:
        self._layers.pop(name, None)

    def visible_chunks(self, name: str, cam_x: int, cam_y: int, viewport: tuple[int, int]) -> list[tuple[int, int]]:
        l = self._layers[name]
        vw, vh = viewport
        x0 = max(0, cam_x) // l.chunk
        y0 = max(0, cam_y) // l.chunk
        x1 = min(l.world_w - 1, cam_x + vw - 1) // l.chunk
        y1 = min(l.world_h - 1, cam_y + vh - 1) // l.chunk
        if cam_x + vw <= 0 or cam_y + vh <= 0 or cam_x >= l.world_w or cam_y >= l.world_h:
            return []
        return [(cx, cy) for cy in range(y0, y1 + 1) for cx in range(x0, x1 + 1)]

    def blit(self, surface: pygame.Surface, name: str, cam_x: int, cam_y: int, viewport: tuple[int, int]) -> int:
        """Blit the visible chunks of ``name`` (painting them on first sight); returns the blit count."""
        l = self._layers[name]
        n = 0
        for cx, cy in self.visible_chunks(name, cam_x, cam_y, viewport):
            surf = l.chunk_surface(cx, cy)
            if surf is not None:
                surface.blit(surf, (cx * l.chunk - cam_x, cy * l.chunk - cam_y))
                n += 1
        self.blits += n
        return n

    def stats(self) -> dict[str, Any]:
        return {name: {"chunks": len(l.chunks), "built": l.built, "chunk": l.chunk,
                       "world": (l.world_w, l.world_h), "signature": repr(l.signature)[:60]}
                for name, l in self._layers.items()}


class StaticLayerDraw(Drawable):
    """Queue item that blits the visible chunks of a static layer for the frame's camera."""

    __slots__ = ("layers", "name", "viewport")
    kind = "static"

    def __init__(self, layers: StaticLayers, name: str, viewport: tuple[int, int]) -> None:
        super().__init__((0.0, 0.0), SCREEN)
        self.layers, self.name, self.viewport = layers, name, (int(viewport[0]), int(viewport[1]))

    def draw(self, surface, cam_x, cam_y, ctx=None) -> int:
        return self.layers.blit(surface, self.name, cam_x, cam_y, self.viewport)

    def describe(self):
        d = super().describe()
        d.update(name=self.name)
        return d
