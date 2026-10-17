"""Mission 3 interrogation-cell door after the C4 breach has settled: jambs, the two door tiles,
blast hole, scorch, cracks and hinge stub - baked from ``missions.m3.draw._paint_cell_door_blown``
(the live ``_draw_cell_door`` stays the fallback and still animates the first 20 frames).
138 x 68, blit at (door_x - 4, door_y - 2). Variant 0: door tiles in their open rest state (the
normal post-breach state), 1: closed + locked tiles (defensive).
"""
import pygame

VARIANTS = 2
VARIANT_NAMES = ("open_tiles", "closed_tiles")
SIZE = (138, 68)
BAKE_DEPS = ("missions.m3.draw", "missions.m3.systems")


def render(variant=0, scale=1):
    from missions.m3 import draw as D   # lazy: game modules only at bake / fallback time
    surf = pygame.Surface(SIZE, pygame.SRCALPHA)
    D._paint_cell_door_blown(surf, 4, 2, open_tiles=(variant == 0))
    if scale != 1:
        surf = pygame.transform.scale(surf, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return surf
