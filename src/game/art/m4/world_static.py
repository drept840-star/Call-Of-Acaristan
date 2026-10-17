"""Mission 4 static world (floor + walls, buildings, roofs, window grids, storefronts, ground
dressing) baked from ``missions.m4.draw._bake_m4_static`` (live fallback).

Variants = the map bound at draw time: 0 = street map, 1 = station map (different sizes).
"""
from game.art._layers import render_callback_layer, map_world_size, scaled

VARIANTS = 2
VARIANT_NAMES = ("street", "station")
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m4.draw",)
BAKED_ONLY = True


def variant_for_state():
    from missions.m4 import maps as M                      # lazy
    g = M.MISSION4_MAP
    if g is M.MISSION4_STATION_MAP:
        return 1
    if g is M.MISSION4_STREET_MAP:
        return 0
    return None


def bake_setup(variant=0):
    from core import game_core as gc
    if variant == 1:
        gc.start_mission4_station_checkpoint(preserve_timer=True)
    else:
        gc.start_mission4(preserve_timer=True)


def render(variant=0, scale=1):
    from missions.m4 import draw as D, maps as M           # lazy
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m4_static, map_world_size(M.MISSION4_MAP, TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m4 import draw as D                            # lazy
    return D._bake_m4_static
