"""Mission 1 static world (office floor grid, container / warehouse walls, desk bodies, bay
label, dressing) baked from ``missions.m1.draw._bake_m1_static`` - the callback the runtime
chunk cache used; it stays the live fallback. One variant: the layout is authored, not random.
"""
from game.art._layers import render_callback_layer, scaled

VARIANTS = 1
VARIANT_NAMES = ("default",)
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m1.draw",)
BAKED_ONLY = True


def bake_setup(variant=0):
    from core import game_core as gc
    gc.start_mission(preserve_timer=True)


def render(variant=0, scale=1):
    from missions.m1 import draw as D                      # lazy
    from missions.m1.map import MAP_W, MAP_H
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m1_static, (MAP_W * TILE_SIZE, MAP_H * TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m1 import draw as D                            # lazy
    return D._bake_m1_static
