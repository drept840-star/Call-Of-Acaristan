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
SEG_W = 12        # HP segment pitch, px


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
    tx, tw = bx + inset, bw - inset
    # Recessed track: near-black well, a darker lip along its top edge.
    pygame.draw.rect(surface, (8, 10, 12), (tx, by, tw, bh))
    pygame.draw.line(surface, (2, 3, 4), (tx, by), (tx + tw - 1, by))
    col = (theme.c_terminal if ratio > 0.5 else theme.c_amber if ratio > 0.25
           else (214, 58, 46))
    fill_w = int(tw * ratio)
    if fill_w > 0:
        # Vertical gradient (lit top, darker base) cut into segments.
        for j in range(1, bh - 1):
            k = 1.08 - 0.42 * (j - 1) / max(1, bh - 3)
            c = tuple(min(255, int(v * k)) for v in col)
            pygame.draw.line(surface, c, (tx + 1, by + j), (tx + fill_w - 2, by + j))
        for sx in range(tx + SEG_W, tx + fill_w - 1, SEG_W):
            pygame.draw.line(surface, (8, 10, 12), (sx, by + 1), (sx, by + bh - 2))
    pygame.draw.rect(surface, theme.c_edge, (tx - 1, by - 1, tw + 2, bh + 2), 1)
