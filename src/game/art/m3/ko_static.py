"""Kill Order ground-floor static world (floors, exterior ground, set dressing: stairwell, dock
crane, crates, mezzanine nosing, Volkov's van or the exfil cage) baked from
``missions.m3.draw._bake_m3_ko`` - the same painters the per-frame path draws; they stay the
live fallback.

Variants follow the one STATE flag the dressing reads: 0 = Volkov's van parked at the exfil,
1 = ``m3_volkov_bailed`` (van gone, roof-line cage instead). Per-frame bits (van beacon, garage
shutter cycle, exfil pulse) are drawn live by ``missions.m3.draw._draw_ko_dressing_live``.
"""
from game.art._layers import render_callback_layer, map_world_size, state_flags_variant, scaled

VARIANTS = 2
VARIANT_NAMES = ("van", "bailed")
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m3.draw",)
BAKED_ONLY = True
_FLAGS = ((False,), (True,))
_NAMES = ("m3_volkov_bailed",)


def variant_for_state():
    return state_flags_variant(_FLAGS, _NAMES)


def bake_setup(variant=0):
    """Tools only: start the Kill Order checkpoint and set the flags this variant depicts."""
    from core import game_core as gc
    from core.state import STATE
    gc.start_mission3_kill_order_checkpoint(preserve_timer=True)
    STATE.m3_volkov_bailed = _FLAGS[variant][0]


def render(variant=0, scale=1):
    from missions.m3 import draw as D, maps as M       # lazy
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m3_ko, map_world_size(M.MISSION3_MAP, TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m3 import draw as D                            # lazy
    return D._bake_m3_ko
