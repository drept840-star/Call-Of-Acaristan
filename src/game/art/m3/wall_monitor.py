"""Interrogation-cell wall monitor (Mission 3), baked from
``missions.m3.draw._paint_wall_monitor_part`` (live fallback). 200 x 67, blit at (rect.x - 4,
rect.y - 4) where rect is the 192 x 57 screen rectangle. The pulsing additive glow and the blinking
REC dot are drawn live between / after the parts.

Variants: 0 monitor off (bezel, dead screen, NO SIGNAL), 1 lit bezel + screen (under the glow),
2 lit foreground (silhouette, scanlines, BALACEANU / REC labels).
"""
import pygame

VARIANTS = 3
VARIANT_NAMES = ("off", "lit_base", "lit_fg")
SIZE = (200, 67)
BAKE_DEPS = ("missions.m3.draw",)


def render(variant=0, scale=1):
    from missions.m3 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    rect = pygame.Rect(4, 4, 64 * 3, int(64 * 0.9))
    D._paint_wall_monitor_part(surf, rect, VARIANT_NAMES[variant])
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
