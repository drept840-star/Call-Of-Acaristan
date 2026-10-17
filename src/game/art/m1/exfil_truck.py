"""Mission 1 parked KRAP exfil flatbed (shadow, bed, crates, cab, headlights, wheels, KRAP
label), baked from ``missions.m1.draw._paint_m1_exfil_truck`` (live fallback). 136 x 70 with the
painter's (ex, ey) at (60, 34) -> blit at (ex - 60, ey - 34). The headlight glows + lenses, the pulsing exfil
ring and the EXFIL label stay live.
"""
import pygame

VARIANTS = 1
VARIANT_NAMES = ("parked",)
SIZE = (136, 70)
BAKE_DEPS = ("missions.m1.draw",)


def render(variant=0, scale=1):
    from missions.m1 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_m1_exfil_truck(surf, 60, 34, headlights=False)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
