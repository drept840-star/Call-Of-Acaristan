"""HealthBar - the HP strip (panel + "HP" label + ratio bar).

Body moved verbatim from the M4 ``_draw_m4_hud`` / M5 ``_draw_hud`` HP blocks,
which were identical: the mission keeps only the data (hp / max_hp) and the
panel background factory (``entities.art_cache.get_panel_bg``).
"""
from __future__ import annotations

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["draw"]

PANEL_W = 246
PANEL_H = 30


def draw(surface: pygame.Surface, theme: Theme, hp: float, max_hp: float, *,
         panel_bg, x: int = 24, y: int | None = None,
         bb: tuple[int, int, int, int] = (6, 4, 234, 14), inset: int = 20,
         panel: tuple[int, int] = (PANEL_W, PANEL_H),
         panel_off: tuple[int, int] = (0, 0), label_dy: int = 2) -> None:
    """Draw the HP strip; ``y`` defaults to the classic bottom-left anchor.

    Defaults are the M2-M5 look (246x30 panel, inline "HP" label, bar inset 20
    px to the right of it). M1's compact strip passes its own geometry: a
    full-width bar (``inset=0``), a plain backdrop (``panel_bg`` builds it),
    the label above the bar (``label_dy``) and the offset backdrop
    (``panel`` / ``panel_off``).
    """
    if y is None:
        y = theme.height - 40
    bx, by, bw, bh = x + bb[0], y + bb[1], bb[2], bb[3]
    ratio = max(0.0, min(1.0, hp / max(1, max_hp)))
    surface.blit(panel_bg(*panel), (x + panel_off[0], y + panel_off[1]))
    surface.blit(theme.font_terminal_small.render(T("hud.hp"), True, theme.c_terminal),
                 (x + bb[0], y + label_dy))
    pygame.draw.rect(surface, (30, 30, 30), (bx + inset, by, bw - inset, bh))
    col = ((int(200 * ratio), int(220 * ratio), 40) if ratio > 0.5 else
           (220, int(200 * ratio * 2), 40) if ratio > 0.25 else (220, 40, 40))
    pygame.draw.rect(surface, col, (bx + inset, by, int((bw - inset) * ratio), bh))
    pygame.draw.rect(surface, theme.c_terminal, (bx + inset, by, bw - inset, bh), 1)
