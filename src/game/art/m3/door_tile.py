"""Reinforced prison door tile of Mission 3 (frame + leaf / open inner + padlock / LED) in its two
rest states, baked from ``missions.m3.systems._paint_m3_door_tile`` (still the live fallback, and the
only path while a door swings or carries bullet damage). 68 x 68: the 64 px tile plus the 2 px frame
the painter draws around it; blit at (tile_x - 2, tile_y - 2). Fully opaque.

Variants: 0 closed + locked, 1 closed + unlocked, 2 fully open (green LED), 3 fully open during the
scripted breach (LED suppressed).
"""
import pygame

VARIANTS = 4
VARIANT_NAMES = ("closed_locked", "closed_unlocked", "open_led", "open_dark")
SIZE = (68, 68)
BAKE_DEPS = ("missions.m3.systems",)
_STATES = ((True, 0.0, False), (False, 0.0, False), (True, 1.0, False), (True, 1.0, True))


def render(variant=0, scale=1):
    from missions.m3 import systems as S   # lazy: boots the game modules only at bake / fallback time
    locked, open_p, breach = _STATES[variant]
    surf = pygame.Surface(SIZE)
    S._paint_m3_door_tile(surf, 2, 2, -1, -1, None, locked, open_p, breach, 0)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
