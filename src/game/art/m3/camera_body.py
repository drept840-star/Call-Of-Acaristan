"""Mission 3 security-camera mount + smoked dome (0 idle, 1 alerted = opaque dome), baked from
``missions.m3.systems._paint_security_camera_body`` (live fallback). 14 x 14 centred at (7, 7) ->
blit at (body_cx - 7, body_cy - 7). The detection cone, lens glint and alarm light stay live.
"""
import pygame

VARIANTS = 2
VARIANT_NAMES = ("idle", "alerted")
SIZE = (14, 14)
BAKE_DEPS = ("missions.m3.systems",)


def render(variant=0, scale=1):
    from missions.m3 import systems as S   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    S._paint_security_camera_body(surf, 7, 7, variant == 1)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
