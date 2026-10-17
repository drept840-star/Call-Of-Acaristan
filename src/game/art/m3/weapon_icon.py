"""Mission 3 HUD weapon icons (shiv, chair leg, K-9 SMG, looted sidearm, generic), baked from
``missions.m3.systems._paint_m3_weapon_icon`` (live fallback). Opaque primitives on a transparent
56 x 36 canvas; the icon origin sits at (8, 4) -> blit at (x - 8, y - 4).
"""
import pygame

VARIANTS = 5
VARIANT_NAMES = ("shiv", "chair_leg", "k9_smg", "sidearm", "generic")
SIZE = (56, 36)
BAKE_DEPS = ("missions.m3.systems",)
_WEAPONS = ("shiv", "chair_leg", "k9_smg", "sidearm", "")


def render(variant=0, scale=1):
    from missions.m3 import systems as S   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    S._paint_m3_weapon_icon(surf, 8, 4, _WEAPONS[variant])
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
