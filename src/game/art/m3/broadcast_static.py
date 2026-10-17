"""Broadcast Wing static world baked from ``missions.m3.draw._bake_m3_broadcast`` (live fallback).
Single variant; the ON AIR pulse is drawn live by ``_draw_broadcast_wing_live``."""
from game.art._layers import render_callback_layer, map_world_size, scaled

VARIANTS = 1
VARIANT_NAMES = ("default",)
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m3.draw",)
BAKED_ONLY = True


def bake_setup(variant=0):
    from core import game_core as gc
    gc.start_mission3_broadcast_checkpoint(preserve_timer=True)


def render(variant=0, scale=1):
    from missions.m3 import draw as D, maps as M       # lazy
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m3_broadcast, map_world_size(M.MISSION3_MAP, TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m3 import draw as D                            # lazy
    return D._bake_m3_broadcast
