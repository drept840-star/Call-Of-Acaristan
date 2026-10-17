"""Cell-block map static world (floors, exterior ground, background dressing, corridor / guard
room / armory / service-wing details, the three neighbour cells) baked from
``missions.m3.draw._bake_m3_static`` - the callback the runtime chunk cache used; it stays the
live fallback.

Variants follow the two STATE-driven switches the callback reads: bit 0 = ``k9_unlocked`` (K9 SMG
taken off the armory wall stand), bit 1 = the Vostral dossier in the remains cell
(``_vostral_present_in_timeline``: archives-onward stages or ``m3_vostral_acquired``).
Per-frame bits (corridor LEDs, cabinet blink, cell tubes, flies) are drawn live by
``_draw_m3_static_live`` / ``_draw_neighbor_cells_live``.
"""
from game.art._layers import render_callback_layer, map_world_size, scaled

VARIANTS = 4
VARIANT_NAMES = ("k9_racked", "k9_unlocked", "k9_racked_vostral", "k9_unlocked_vostral")
ORIGIN = (0, 0)
BAKE_DEPS = ("missions.m3.draw",)
BAKED_ONLY = True


def variant_for_state():
    from core.state import STATE
    from missions.m3 import draw as D                            # lazy
    return (1 if getattr(STATE, "k9_unlocked", False) else 0) + (2 if D._vostral_present_in_timeline() else 0)


def bake_setup(variant=0):
    """Tools only: start the cell-block checkpoint and set the flags this variant depicts."""
    from core import game_core as gc
    from core.state import STATE
    gc.start_mission3_breakout_checkpoint(preserve_timer=True)
    STATE.k9_unlocked = bool(variant & 1)
    STATE.m3_vostral_acquired = bool(variant & 2)


def render(variant=0, scale=1):
    from missions.m3 import draw as D, maps as M       # lazy
    from core.config import TILE_SIZE
    return scaled(render_callback_layer(D._bake_m3_static, map_world_size(M.MISSION3_MAP, TILE_SIZE)), scale)


def runtime_callback():
    """The runtime chunk-cache callback this layer replaces (parity tooling)."""
    from missions.m3 import draw as D                            # lazy
    return D._bake_m3_static
