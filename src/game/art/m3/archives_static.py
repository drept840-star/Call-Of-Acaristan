"""Archives Wing static world baked from ``missions.m3.draw._bake_m3_archives`` (live fallback).

Variants = the reachable combinations of the two flags the painter reads:
0 = vault locked, 1 = ``m3_maru_contacted`` (terminal bezels green, vault unlocked),
2 = contacted + ``m3_vostral_acquired`` (dossier taken). Phosphor text / vault pulses are
already per-frame in the painter (``staticlayer.baking()`` guards).
"""
from game.art._layers import render_callback_layer, map_world_size, state_flags_variant, scaled

VARIANTS = 3
VARIANT_NAMES = ("locked", "maru_contacted", "vostral_taken")
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m3.draw",)
BAKED_ONLY = True
_FLAGS = ((False, False), (True, False), (True, True))
_NAMES = ("m3_maru_contacted", "m3_vostral_acquired")


def variant_for_state():
    return state_flags_variant(_FLAGS, _NAMES)


def bake_setup(variant=0):
    from core import game_core as gc
    from core.state import STATE
    gc.start_mission3_archives_checkpoint(preserve_timer=True)
    STATE.m3_maru_contacted, STATE.m3_vostral_acquired = _FLAGS[variant]


def render(variant=0, scale=1):
    from missions.m3 import draw as D, maps as M       # lazy
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m3_archives, map_world_size(M.MISSION3_MAP, TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m3 import draw as D                            # lazy
    return D._bake_m3_archives
