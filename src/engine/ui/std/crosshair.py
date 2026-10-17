"""Crosshair - the aim reticle shapes (four-arm reticle; combat ring + arms).

The combat shape was copied verbatim into M1, M2 and walking_sim (each copy
carries the comment "same logic as the shared ui_hud.draw_gameplay_crosshair()")
and lived a fourth time in ``ui.hud.draw_combat_reticle``; the four-arm variant
lived in ``ui.hud.draw_crosshair``. The geometry moved here.

Every *policy* stays with the caller: whether the reticle draws at all
(SETTINGS.show_crosshair, dead player, OS-pointer visibility, overlays, scene
name) and the ``STATE.crosshair_kick`` decay are game-side. The colour comes
from the caller's settings (colour-blind modes), so - unlike the other widgets -
these functions take no ``Theme``.
"""
from __future__ import annotations

import pygame

__all__ = ["COLORBLIND_COLORS", "color_for", "draw", "draw_combat"]

# The accessibility palette. The four copies of this table (ui.hud twice, M1,
# M2, walking_sim) agreed byte-for-byte; the arms reticle's default is white and
# the combat reticle's is the game's orange, so the caller passes ``default``.
COLORBLIND_COLORS = {
    "protanopia": (90, 180, 255),    # blue reads well for red-deficient vision
    "deuteranopia": (255, 220, 80),  # yellow
    "tritanopia": (255, 120, 120),   # pinkish-red
}


def color_for(mode, *, default):
    """Reticle colour for a colour-blind ``mode`` (``default`` when unset)."""
    return COLORBLIND_COLORS.get(mode, default)


def draw(surface: pygame.Surface, cx: int, cy: int, *, size: int = 6,
         color, kick: int = 0) -> None:
    """Four-arm reticle + centre dot; ``kick`` spreads the arms for this frame."""
    size = max(3, int(size))
    gap = max(2, size // 2)
    arm = size + gap + 2
    if kick > 0:
        spread = min(int(kick), 9)
        gap += spread
        arm += spread
    pygame.draw.rect(surface, color, (cx - 1, cy - 1, 2, 2))
    pygame.draw.line(surface, color, (cx - arm, cy), (cx - gap, cy), 1)
    pygame.draw.line(surface, color, (cx + gap, cy), (cx + arm, cy), 1)
    pygame.draw.line(surface, color, (cx, cy - arm), (cx, cy - gap), 1)
    pygame.draw.line(surface, color, (cx, cy + gap), (cx, cy + arm), 1)


def draw_combat(surface: pygame.Surface, cx: int, cy: int, *, size: int = 6,
                color) -> None:
    """Combat reticle: ring + centre dot + four arms."""
    size = max(3, int(size))
    ring_r = size + 8
    arm = size + 6
    gap = max(2, size // 2)
    pygame.draw.circle(surface, color, (cx, cy), ring_r, 1)
    pygame.draw.circle(surface, color, (cx, cy), max(1, size // 3))
    for x1, y1, x2, y2 in [
        (cx - arm, cy, cx - gap, cy),
        (cx + gap, cy, cx + arm, cy),
        (cx, cy - arm, cx, cy - gap),
        (cx, cy + gap, cx, cy + arm),
    ]:
        pygame.draw.line(surface, color, (x1, y1), (x2, y2), 1)
