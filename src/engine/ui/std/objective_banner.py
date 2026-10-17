"""ObjectiveBanner - the OBJECTIVE panel.

Body moved verbatim from ``src/ui/hud.py:draw_objective_panel`` (shim keeps the
old name, A-009). Long objectives are wrapped inside the panel instead of
overflowing across the map; short ones stay the same one-line banner, clamped to
two readable lines maximum.
"""
from __future__ import annotations

import pygame

from engine.text import T

from ..theme import Theme

__all__ = ["DEFAULT_PANEL_HEIGHT", "DEFAULT_PANEL_WIDTH", "draw"]

DEFAULT_PANEL_WIDTH = 520    # was OBJECTIVE_PANEL_WIDTH in src/ui/hud.py
DEFAULT_PANEL_HEIGHT = 30    # was OBJECTIVE_PANEL_HEIGHT in src/ui/hud.py


def draw(surface: pygame.Surface, text: object, theme: Theme, x: int = 20,
         y: int | None = None, *, label: str | None = None) -> None:
    """Draw the OBJECTIVE banner at the top of the screen (label: ``hud.objective``)."""
    font_prompt = theme.font_prompt
    if y is None:
        y = theme.letter_h + 10

    panel_w = min(theme.width - x - 20, max(DEFAULT_PANEL_WIDTH, 620))
    pad_x = 10
    line_gap = 3
    max_text_w = panel_w - pad_x * 2

    full = (label if label is not None else T("hud.objective")) + str(text)
    words = full.split(" ")
    lines = []
    cur = ""
    for word in words:
        test = word if not cur else cur + " " + word
        if font_prompt.size(test)[0] <= max_text_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
                cur = word
            else:
                # Extremely long single token: trim defensively.
                trimmed = word
                while trimmed and font_prompt.size(trimmed + "\u2026")[0] > max_text_w:
                    trimmed = trimmed[:-1]
                lines.append(trimmed + "\u2026")
                cur = ""
    if cur:
        lines.append(cur)

    # Don't let an objective panel become a paragraph. Mission code should keep
    # text concise; this clamps the UI to two readable lines.
    if len(lines) > 2:
        second = lines[1]
        while second and font_prompt.size(second + "\u2026")[0] > max_text_w:
            second = second[:-1]
        lines = [lines[0], second + "\u2026"]

    line_h = font_prompt.get_height()
    panel_h = max(DEFAULT_PANEL_HEIGHT, 14 + len(lines) * line_h + (len(lines) - 1) * line_gap)
    bg = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(bg, (0, 0, 0, 150), (0, 0, panel_w, panel_h))
    pygame.draw.line(bg, theme.c_krap_blue, (0, 0), (0, panel_h), 3)
    surface.blit(bg, (x, y))

    for i, line in enumerate(lines):
        obj_surf = font_prompt.render(line, True, theme.c_white)
        surface.blit(obj_surf, (x + pad_x, y + 7 + i * (line_h + line_gap)))
