"""Biribel's cell dressing (cot, chair, sink, drain, stains, tally marks, conduit) as a baked
world layer. Bake source: ``missions.m3.draw._draw_cell_details`` (still the live fallback).

Variants: 0 = interrogation chair intact, 1 = chair broken. The speaker LED is drawn live
(``_draw_cell_details_live``). ORIGIN/SIZE come from ``tools/ae_layer_probe.py``.
"""
from engine.assets import bake_camera_layer

VARIANTS = 2
VARIANT_NAMES = ("chair_intact", "chair_broken")
ORIGIN = (1913, 313)          # world px (map tile 64)
SIZE = (536, 523)
BAKE_DEPS = ("missions.m3.draw",)


def render(variant=0, scale=1):
    from missions.m3 import draw as D   # lazy: boots the game modules only at bake / fallback time
    from core import config as C
    layer = bake_camera_layer(
        lambda cx, cy: D._draw_cell_details(cx, cy, chair_broken=bool(variant), live=False),
        size=SIZE, origin=ORIGIN, tile=(C.WIDTH, C.HEIGHT), redirect=[(D, "screen")])
    if scale != 1:
        import pygame
        layer = pygame.transform.scale(layer, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return layer
