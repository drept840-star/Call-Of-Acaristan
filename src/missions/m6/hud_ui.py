"""Mission 6 tactical HUD styling & unified top-left combat cluster."""
from __future__ import annotations

import pygame

from core.config import font_terminal_small
from engine.text import T
from ui.tactical_hud import (
    HUD_MARGIN, PANEL_GAP, TACTICAL_THEME as M6_THEME,
    draw_tactical_corners, tactical_panel_bg as m6_panel_bg,
)

CLUSTER_W = 246
CLUSTER_H = 42
STEALTH_W = 232
_TEXT_CACHE: dict = {}


def _safe_convert_alpha(surf: pygame.Surface) -> pygame.Surface:
    if pygame.display.get_init() and pygame.display.get_surface() is not None:
        return surf.convert_alpha()
    return surf


def draw_combat_cluster(surface: pygame.Surface, remaining: int,
                        waves_done: int, waves_total: int,
                        loud: bool, peak: int) -> None:
    """Single top-left tactical panel combining wave state & hostiles count."""
    x, y, w, h = HUD_MARGIN, HUD_MARGIN, CLUSTER_W, CLUSTER_H
    surface.blit(m6_panel_bg(w, h), (x, y))
    pygame.draw.rect(surface, M6_THEME.c_amber, (x, y, 3, h))

    left_count = max(0, int(remaining))
    if left_count <= 0:
        status_txt, status_col, fill_col, frac = (
            "AREA CLEAR  -  MOVE OUT", (142, 222, 152), (96, 198, 126), 1.0
        )
    else:
        if waves_done == 0 and not loud:
            status_txt, status_col = f"SQUAD DUG IN  ·  W0/{waves_total}", (216, 198, 152)
        else:
            status_txt, status_col = f"WAVE {waves_done}/{waves_total}", (236, 154, 78)
        fill_col = (224, 162, 46)
        frac = 1.0 - left_count / float(max(1, peak))

    h_col = M6_THEME.c_terminal if left_count > 0 else (142, 222, 152)
    sk = ("s", status_txt, status_col)
    hk = ("h", left_count, h_col)
    s_surf = _TEXT_CACHE.get(sk)
    if s_surf is None:
        if len(_TEXT_CACHE) > 64:
            _TEXT_CACHE.clear()
        s_surf = _TEXT_CACHE[sk] = _safe_convert_alpha(
            font_terminal_small.render(status_txt, True, status_col))
    h_surf = _TEXT_CACHE.get(hk)
    if h_surf is None:
        h_surf = _TEXT_CACHE[hk] = _safe_convert_alpha(
            font_terminal_small.render(T("hud.hostiles", n=left_count), True, h_col))
    surface.blit(s_surf, (x + 10, y + 6))
    surface.blit(h_surf, (x + w - 10 - h_surf.get_width(), y + 6))

    bx, by, bw, bh = x + 10, y + 27, w - 20, 7
    pygame.draw.rect(surface, (6, 8, 12), (bx, by, bw, bh))
    fw = int((bw - 2) * max(0.0, min(1.0, frac)))
    if fw > 0:
        pygame.draw.rect(surface, fill_col, (bx + 1, by + 1, fw, bh - 2))
    pygame.draw.rect(surface, (46, 58, 72), (bx, by, bw, bh), 1)


def draw_stealth_cluster(surface: pygame.Surface, exp_frac: float,
                         alarmed: bool, visible: bool) -> None:
    """Exposure / searchlight alert panel aligned cleanly next to the combat cluster."""
    x = HUD_MARGIN + CLUSTER_W + 12
    y, w, h = HUD_MARGIN, STEALTH_W, CLUSTER_H
    surface.blit(m6_panel_bg(w, h), (x, y))
    col = (240, 96, 78) if alarmed else (236, 154, 78)
    pygame.draw.rect(surface, col, (x, y, 3, h))
    label = "SEARCHLIGHT - GUNNER" if (alarmed and visible) else "IN THE LIGHT"
    txt = font_terminal_small.render(label, True, col)
    surface.blit(txt, (x + 10, y + 6))
    bx, by, bw, bh = x + 10, y + 27, w - 20, 7
    pygame.draw.rect(surface, (6, 8, 12), (bx, by, bw, bh))
    frac = 1.0 if alarmed else max(0.0, min(1.0, exp_frac))
    fw = int((bw - 2) * frac)
    if fw > 0:
        pygame.draw.rect(surface, col, (bx + 1, by + 1, fw, bh - 2))
    pygame.draw.rect(surface, (46, 58, 72), (bx, by, bw, bh), 1)
