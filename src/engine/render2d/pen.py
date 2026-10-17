"""render2d.pen - a drawing sink for procedural painters (RPE6 Phase 6, B-033).

Legacy painters that draw a *character* (the player avatar, weapon rigs, head
adornments) issue ~150 primitive calls through several modules. A ``Pen`` gives
them one sink with the exact call shape of the ``pygame.draw`` calls they used to
make:

- ``SurfacePen(surface)`` paints immediately - pixel-identical to the old code,
  because it *is* the old code (same ``pygame.draw`` calls, same arguments).
- ``RecordingPen()`` appends screen-space drawables to ``.items`` instead, so the
  painter's output can be submitted to the ``RenderQueue``.

Both pens pass numbers through untouched (ADR-017 truncation rule): each legacy
call site's own float→int conversion is preserved by pygame / the drawables.
"""
from __future__ import annotations

import pygame

from .drawables import SCREEN, ArcDraw, CircleDraw, EllipseDraw, LineDraw, PolyDraw, RectDraw, SurfaceDraw

__all__ = ["SurfacePen", "RecordingPen", "pen_or_surface"]


class SurfacePen:
    """Immediate pen: every call is the legacy ``pygame.draw`` call on ``surface``."""

    __slots__ = ("surface",)

    def __init__(self, surface) -> None:
        self.surface = surface

    def polygon(self, color, points, width=0):
        pygame.draw.polygon(self.surface, color, points, width)
        return 1

    def line(self, color, a, b, width=1):
        pygame.draw.line(self.surface, color, a, b, width)
        return 1

    def lines(self, color, closed, points, width=1):
        pygame.draw.lines(self.surface, color, closed, points, width)
        return 1

    def circle(self, color, center, radius, width=0):
        pygame.draw.circle(self.surface, color, center, radius, width)
        return 1

    def ellipse(self, color, rect, width=0):
        pygame.draw.ellipse(self.surface, color, rect, width)
        return 1

    def arc(self, color, rect, start, stop, width=1):
        pygame.draw.arc(self.surface, color, rect, start, stop, width)
        return 1

    def rect(self, color, rect, width=0, border_radius=0):
        pygame.draw.rect(self.surface, color, rect, width, border_radius=border_radius)
        return 1

    def blit(self, img, pos):
        self.surface.blit(img, pos)
        return 1


class RecordingPen:
    """Recording pen: appends screen-space drawables to ``items`` in call order."""

    __slots__ = ("items",)

    def __init__(self) -> None:
        self.items: list = []

    def polygon(self, color, points, width=0):
        self.items.append(PolyDraw(points, color, width, space=SCREEN))
        return 1

    def line(self, color, a, b, width=1):
        self.items.append(LineDraw([a, b], color, width, space=SCREEN))
        return 1

    def lines(self, color, closed, points, width=1):
        self.items.append(LineDraw(points, color, width, closed=closed, space=SCREEN))
        return 1

    def circle(self, color, center, radius, width=0):
        self.items.append(CircleDraw(center, radius, color, width, space=SCREEN))
        return 1

    def ellipse(self, color, rect, width=0):
        self.items.append(EllipseDraw(rect, color, width, space=SCREEN))
        return 1

    def arc(self, color, rect, start, stop, width=1):
        self.items.append(ArcDraw(rect, color, start, stop, width, space=SCREEN))
        return 1

    def rect(self, color, rect, width=0, border_radius=0):
        self.items.append(RectDraw(rect, color, width, border_radius=border_radius, space=SCREEN))
        return 1

    def blit(self, img, pos):
        self.items.append(SurfaceDraw(img, pos, space=SCREEN))
        return 1


def pen_or_surface(pen, surface):
    """``pen`` if given, else an immediate pen over ``surface`` (the legacy default)."""
    return pen if pen is not None else SurfacePen(surface)
