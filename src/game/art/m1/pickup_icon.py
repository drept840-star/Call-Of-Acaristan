"""Mission 1 ground-pickup icons (0 magazine, 1 keycard, 2 bandage, 3 bottle), baked from
``missions.m1.draw._paint_m1_pickup_icon`` (live fallback). Opaque primitives on a transparent
32 x 32 canvas centred at (16, 16) -> blit at (int(px) - 16, int(py) - 16). The bobbing offset and
the glow under the icon stay live.
"""
import pygame

VARIANTS = 4
VARIANT_NAMES = ("mag", "keycard", "bandage", "bottle")
SIZE = (32, 32)
BAKE_DEPS = ("missions.m1.draw",)


def render(variant=0, scale=1):
    from missions.m1 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_m1_pickup_icon(surf, VARIANT_NAMES[variant], 16, 16)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
