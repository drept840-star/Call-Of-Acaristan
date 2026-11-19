"""Shared tactical HUD styling & layout metrics (M1–M6)."""
from __future__ import annotations

import pygame

from core.config import (
    C_GREY, C_KRAP_BLUE, C_ORANGE, C_WHITE, SPEAKER_COLORS, TILE_SIZE,
    WIDTH, HEIGHT, font_btn, font_dialogue, font_prompt, font_speaker,
    font_terminal, font_terminal_small, font_title,
)
from engine.ui import Theme

HUD_MARGIN = 18
PANEL_GAP = 6

TACTICAL_THEME = Theme(
    size=(WIDTH, HEIGHT),
    letter_h=80,
    tile_size=TILE_SIZE,
    font_prompt=font_prompt,
    font_terminal=font_terminal,
    font_terminal_small=font_terminal_small,
    font_dialogue=font_dialogue,
    font_speaker=font_speaker,
    font_title=font_title,
    font_btn=font_btn,
    c_white=C_WHITE,
    c_grey=C_GREY,
    c_orange=C_ORANGE,
    c_terminal=(75, 227, 122),
    c_krap_blue=C_KRAP_BLUE,
    c_amber=(230, 159, 58),
    c_panel=(12, 16, 22),
    c_panel_alpha=224,
    c_edge=(52, 64, 78),
    speaker_colors=SPEAKER_COLORS,
    extra={"tactical_hud": True, "compact_objective": True},
)

_PANELS: dict = {}


def _safe_convert_alpha(surf: pygame.Surface) -> pygame.Surface:
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert_alpha()
    return surf


def draw_tactical_corners(surface: pygame.Surface, rect: pygame.Rect,
                          col: tuple[int, int, int] = (118, 142, 166),
                          length: int = 7, thickness: int = 2) -> None:
    """Clean 2px L-shaped tactical corner brackets around ``rect``."""
    x0, y0, x1, y1 = rect.left, rect.top, rect.right - 1, rect.bottom - 1
    l = max(3, min(length, rect.w // 3, rect.h // 3))
    pygame.draw.line(surface, col, (x0, y0), (x0 + l, y0), thickness)
    pygame.draw.line(surface, col, (x0, y0), (x0, y0 + l), thickness)
    pygame.draw.line(surface, col, (x1, y0), (x1 - l, y0), thickness)
    pygame.draw.line(surface, col, (x1, y0), (x1, y0 + l), thickness)
    pygame.draw.line(surface, col, (x0, y1), (x0 + l, y1), thickness)
    pygame.draw.line(surface, col, (x0, y1), (x0, y1 - l), thickness)
    pygame.draw.line(surface, col, (x1, y1), (x1 - l, y1), thickness)
    pygame.draw.line(surface, col, (x1, y1), (x1, y1 - l), thickness)


def tactical_panel_bg(w: int, h: int, alpha: int = 224,
                      border_radius: int = 2,
                      border_col: tuple[int, int, int] = (52, 64, 78)) -> pygame.Surface:
    """Cached dark-tinted tactical backing panel with crisp corner brackets."""
    key = (int(w), int(h), int(alpha), int(border_radius), tuple(border_col))
    surf = _PANELS.get(key)
    if surf is None:
        if len(_PANELS) > 96:
            _PANELS.clear()
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        surf.fill((12, 16, 22, alpha))
        pygame.draw.rect(surf, (*border_col, 255), (0, 0, w, h), 1)
        pygame.draw.line(surf, (82, 98, 118, 120), (1, 1), (w - 2, 1), 1)
        draw_tactical_corners(surf, pygame.Rect(0, 0, w, h))
        _PANELS[key] = _safe_convert_alpha(surf)
    return surf


def place_minimap(minimap) -> None:
    """Align an existing MiniMap instance to TACTICAL_THEME and 18px top-right margin."""
    if minimap is None:
        return
    minimap._theme = TACTICAL_THEME
    minimap.x = WIDTH - minimap.minimap_w - HUD_MARGIN
    minimap.y = HUD_MARGIN
