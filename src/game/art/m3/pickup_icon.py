"""Mission 3 ground-pickup markers (0 looted sidearm, 1 bandage), baked from
``missions.m3.draw._paint_m3_pickup_icon`` (live fallback). Opaque primitives on a transparent
18 x 18 canvas; the marker centre sits at (8, 8) -> blit at (px - 8, py - 8). The pulsing halo under
the marker stays live.
"""
import pygame

VARIANTS = 2
VARIANT_NAMES = ("sidearm", "bandage")
SIZE = (18, 18)
BAKE_DEPS = ("missions.m3.draw",)


def render(variant=0, scale=1):
    from missions.m3 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_m3_pickup_icon(surf, 8, 8, VARIANT_NAMES[variant])
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
