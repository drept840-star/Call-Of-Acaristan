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
FADE_W = 140                 # right edge eases out to clear

# The wrapped panel (backdrop + rendered lines) for the text last drawn: the
# banner is redrawn every frame with the same words, and measuring them and
# rebuilding the surfaces each time cost ~0.4 ms.  The surfaces are blitted in
# the original order, so the pixels are unchanged.
_PANELS: dict = {}


def draw(surface: pygame.Surface, text: object, theme: Theme, x: int = 20,
         y: int | None = None, *, label: str | None = None) -> None:
    """Draw the OBJECTIVE banner at the top of the screen (label: ``hud.objective``)."""
    font_prompt = theme.font_prompt
    if y is None:
        y = theme.letter_h + 10

    compact = bool(theme.extra.get("compact_objective", False))
    tactical = bool(theme.extra.get("tactical_hud", False))
    max_panel_w = min(theme.width - x - 200, 440) if compact else min(theme.width - x - 20, max(DEFAULT_PANEL_WIDTH, 620))
    pad_x = 9 if compact else 10
    top_pad = 5 if compact else 7
    line_gap = 2 if compact else 3
    fade_w = 24 if compact else FADE_W
    max_text_w = max(120, max_panel_w - pad_x * 2 - (12 if compact else 0))

    full = (label if label is not None else T("hud.objective")) + str(text)
    key = (full, max_panel_w, compact, tactical, id(font_prompt), font_prompt.get_height(),
           tuple(theme.c_amber), tuple(theme.c_white), tuple(theme.c_panel))
    cached = _PANELS.get(key)
    if cached is not None:
        bg, line_surfs = cached
        surface.blit(bg, (x, y))
        for obj_surf, dy in line_surfs:
            surface.blit(obj_surf, (x + pad_x, y + dy))
        return
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
    if compact:
        widest = max((font_prompt.size(line)[0] for line in lines), default=100)
        panel_w = max(210, min(max_panel_w, widest + pad_x * 2 + 24))
        panel_h = max(24, top_pad * 2 + len(lines) * line_h + (len(lines) - 1) * line_gap)
    else:
        panel_w = max_panel_w
        panel_h = max(DEFAULT_PANEL_HEIGHT, 14 + len(lines) * line_h + (len(lines) - 1) * line_gap)
    bg = theme.panel(panel_w, panel_h, fade=fade_w, stripe=theme.c_amber)
    if tactical:
        bg = bg.copy()
        c_hi = (118, 142, 166, 255)
        pygame.draw.line(bg, c_hi, (0, 0), (8, 0), 2)
        pygame.draw.line(bg, c_hi, (0, 0), (0, 7), 2)
        pygame.draw.line(bg, c_hi, (0, panel_h - 1), (8, panel_h - 1), 2)
        pygame.draw.line(bg, c_hi, (0, panel_h - 1), (0, panel_h - 8), 2)
    surface.blit(bg, (x, y))

    line_surfs = []
    for i, line in enumerate(lines):
        obj_surf = font_prompt.render(line, True, theme.c_white)
        dy = top_pad + i * (line_h + line_gap)
        surface.blit(obj_surf, (x + pad_x, y + dy))
        line_surfs.append((obj_surf, dy))
    if len(_PANELS) >= 16:
        _PANELS.clear()
    _PANELS[key] = (bg, line_surfs)
