"""Prison kitchen / utility room of the cell block (floor tiles, backsplash, shelves, fixtures,
grime) as a baked world layer. Bake source: ``missions.m3.draw._draw_kitchen_details`` (still the
live fallback). Fully static: the painter clips to the room rect (tiles 2..6 x 20..24), which is
exactly this layer. Probe: ``tools/ae_layer_probe.py missions.m3.draw _draw_kitchen_details`` = EXACT.
"""
from engine.assets import bake_camera_layer

VARIANTS = 1
VARIANT_NAMES = ("default",)
ORIGIN = (128, 1280)          # world px: 2 * 64, 20 * 64
SIZE = (320, 320)             # 5 x 5 tiles
BAKE_DEPS = ("missions.m3.draw",)


def bake_setup(variant=0):
    """Tools only: start the cell-block checkpoint (the painter reads no state)."""
    from core import game_core as gc
    gc.start_mission3_breakout_checkpoint(preserve_timer=True)


def render(variant=0, scale=1):
    from missions.m3 import draw as D   # lazy: boots the game modules only at bake / fallback time
    from core import config as C
    layer = bake_camera_layer(
        lambda cx, cy: D._draw_kitchen_details(cx, cy),
        size=SIZE, origin=ORIGIN, tile=(C.WIDTH, C.HEIGHT), redirect=[(D, "screen")])
    if scale != 1:
        import pygame
        layer = pygame.transform.scale(layer, (int(SIZE[0] * scale), int(SIZE[1] * scale)))
    return layer
