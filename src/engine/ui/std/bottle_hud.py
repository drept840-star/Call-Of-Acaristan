"""BottleHud - the molotov counter strip (M1 + M2; the bodies were identical).

Both missions drew the same 246x36 strip: four bottle icons at 26px steps, the
"MOLOTOVS  [G]" label and the "{n} / {cap}" readout (M2 even borrowed M1's icon
painter through a mission import). The strip moved here; the mission passes its
own ``panel_bg`` (each HUD stack uses its own alpha) and its bottle icon
painter, so the pixels stay exactly where they were.
"""
from __future__ import annotations

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["PANEL_H", "PANEL_W", "draw"]

PANEL_W = 246
PANEL_H = 36
ICON_STEP = 26
ICON_X0 = 18
ICON_Y = 23
COL_LABEL_ON = (255, 150, 60)
COL_LABEL_OFF = (130, 80, 80)
COL_COUNT_OFF = (180, 60, 60)


def draw(surface: pygame.Surface, theme: Theme, bottles: int, *, panel_bg, icon,
         x: int, y: int, width: int = PANEL_W, cap: int = 4) -> None:
    """Draw the bottle strip at (x, y).

    ``icon(surface, x, y, filled)`` paints one bottle; ``cap`` is the strip's
    capacity (the readout renders as ``{bottles} / {cap}``).
    """
    surface.blit(panel_bg(width, PANEL_H), (x, y))
    for i in range(cap):
        icon(surface, x + ICON_X0 + i * ICON_STEP, y + ICON_Y, i < bottles)
    label_col = COL_LABEL_ON if bottles > 0 else COL_LABEL_OFF
    surface.blit(theme.font_terminal_small.render(T("hud.molotovs"), True, label_col),
                 (x + 120, y + 4))
    count_col = theme.c_terminal if bottles > 0 else COL_COUNT_OFF
    surface.blit(theme.font_terminal_small.render(
        T("hud.bottles", n=int(bottles), cap=cap), True, count_col), (x + 120, y + 18))
