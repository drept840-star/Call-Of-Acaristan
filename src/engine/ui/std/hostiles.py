"""Hostiles - the HOSTILES counter box.

Body moved verbatim from the M4 ``_draw_m4_hud`` / M5 ``_draw_hud`` blocks,
which differed only in how the count is computed (M5 counts living, non-passive
enemies; M4 counts every entry) - that stays with the mission, the box does not.
"""
from __future__ import annotations

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["draw"]

BOX_W = 180
BOX_H = 26


def draw(surface: pygame.Surface, theme: Theme, count: int, *, x: int = 20, y: int = 20,
         label: str | None = None) -> None:
    """Draw the hostiles counter in the top-left corner (string: ``hud.hostiles``).

    ``label`` is the legacy override: a ``{}``-template formatted with the count.
    """
    surface.blit(theme.panel(BOX_W, BOX_H), (x, y))
    text = label.format(int(count)) if label is not None else T("hud.hostiles", n=int(count))
    surface.blit(theme.font_terminal_small.render(text, True, theme.c_terminal),
                 (x + 10, y + 5))
