"""Mission 2 clue / evidence prop icons at world scale (PROP_WORLD_SCALE), baked from
``missions.m2.draw._paint_prop_icon`` (live fallback, also the only path for card-preview scales).
19 variants = ``missions.m2.draw._PROP_ICON_VARIANTS`` (kind, active, colour index); the pulsing
LEDs / cursor are drawn live on top. 64 x 64 canvas with the icon centre at (32, 32) -> blit at
(cx - 32, cy - 32).
"""
import pygame

VARIANTS = 19
VARIANT_NAMES = ("radio", "mag_paint", "mag_paint_off", "timer_fragment", "bootprints", "range_card",
                 "manifest", "decree", "packet", "document", "terminal", "terminal_amber",
                 "terminal_orange", "generic", "generic_off", "generic_amber", "generic_amber_off",
                 "generic_orange", "generic_orange_off")
SIZE = (64, 64)
BAKE_DEPS = ("missions.m2.draw",)


def render(variant=0, scale=1):
    from missions.m2 import draw as D   # lazy: game modules only at bake / fallback time
    kind, active, ci = D._PROP_ICON_VARIANTS[variant]
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_prop_icon(surf, kind, 32, 32, D.PROP_WORLD_SCALE, active, D._PROP_ICON_COLOURS[ci])
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
