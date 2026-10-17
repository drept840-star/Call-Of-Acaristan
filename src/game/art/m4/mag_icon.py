"""Mission 4 HUD magazine icons, baked from ``missions.m4.draw._paint_m4_mag_icon`` (live
fallback). 56 variants = kind (stick, box) x active (no, yes) x 14 fill states (empty, then
witness-hole fill 0..12); index via ``missions.m4.draw._m4_mag_icon_variant``. 25 x 56 canvas with
the painter's (mx, my) at (0, 3) -> blit at (mx, my - 3).
"""
import pygame

VARIANTS = 56
VARIANT_NAMES = tuple("%s_%s_%s" % (k, a, ("empty" if st == 0 else "fill%d" % (st - 1)))
                      for k in ("stick", "box") for a in ("idle", "active") for st in range(14))
SIZE = (25, 56)
BAKE_DEPS = ("missions.m4.draw",)


def render(variant=0, scale=1):
    from missions.m4 import draw as D   # lazy: game modules only at bake / fallback time
    kind = "stick" if variant < 28 else "box"
    active = (variant // 14) % 2 == 1
    state = variant % 14
    rounds, cap = (0, 12) if state == 0 else (max(1, (state - 1) * 2), 24)  # fill = round(r/24*12)
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_m4_mag_icon(surf, 0, 3, kind, rounds, cap, active)
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
