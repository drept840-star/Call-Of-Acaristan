"""HUD Molotov icon (0 active = lit bottle, 1 spent = grey bottle), baked from
``missions.m1.draw._paint_molotov_icon`` (live fallback; the M2 and M3 HUDs reuse the same
painter). Opaque primitives on a transparent 12 x 36 canvas; the painter's (cx, cy) sits at
(6, 26) -> blit at (cx - 6, cy - 26).
"""
import pygame

VARIANTS = 2
VARIANT_NAMES = ("active", "spent")
SIZE = (12, 36)
BAKE_DEPS = ("missions.m1.draw",)


def render(variant=0, scale=1):
    from missions.m1 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_molotov_icon(surf, 6, 26, variant == 0)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
