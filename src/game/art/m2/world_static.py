"""Mission 2 static world (road / terrain tiles, static dressing, structure walls, control
facade, gantry, shelter, garden) baked from ``missions.m2.draw._bake_m2_static`` - the callback
the runtime chunk cache used; it stays the live fallback.

One variant: the callback's only STATE inputs are the structure walls (authored map), the tanker
tile (proved pixel-identical with and without the tanker) and the shelter run caption, which is
now drawn per frame (``_draw_shelter_live``).
"""
from game.art._layers import render_callback_layer, scaled

VARIANTS = 1
VARIANT_NAMES = ("default",)
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m2.draw",)
BAKED_ONLY = True


def bake_setup(variant=0):
    from core import game_core as gc
    gc.start_mission2(preserve_timer=True)


def render(variant=0, scale=1):
    from missions.m2 import draw as D                       # lazy
    from missions.m2.meta import MAP_W, MAP_H
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m2_static, (MAP_W * TILE_SIZE, MAP_H * TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m2 import draw as D                       # lazy
    return D._bake_m2_static
