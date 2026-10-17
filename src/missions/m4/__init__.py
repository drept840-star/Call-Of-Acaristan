
"""Mission 4: The Aftermath - the world after the broadcast.

Picks up hours after Mission 3's Vostral transmission. The regime is
reeling: Balaceanu's career is public record, Retardovici's puppet
strings are cut, and KRAP is left without clear direction. Volkov has
vanished across the border to Regatul Kim Kim. Vasile and Biribel are
the only ones left trying to figure out what comes next - KRAP doesn't
fully dissolve but "kind of dissolves," its remnants allied with MAG,
while Maru steps into physical presence for the first time.

The spine of the mission (per the approved arc): ~48h of curfew chaos
in the capital, the KRAP-MAG liaison meet at the state radio station,
and a siege hold on the transmitter while President Retardovici orders
Balaceanu's arrest live on air. Biribel never kills Balaceanu - the
vendetta ends by being made irrelevant. The nation cheers the wrong
man; Biribel chooses to stay and fight.

Integration contract (all wired in Slice 0):
    - game_core.start_mission4() / station / tower checkpoint wrappers
    - game_core.game_update()/game_draw()/handle_interact() routing
      (MISSION4 is checked BEFORE MISSION3 - see game_core.game_update)
    - app.py intro/ending cutscene chains + --dev-mission4* flags
    - save as MISSION_4
Package layout: re-export facade. Parts (load order): meta.py, maps.py,
world.py, flow.py, systems.py, draw.py.
"""
from .meta import *  # noqa: F401,F403
from .maps import *  # noqa: F401,F403
from .world import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403

# Explicit re-exports (star imports skip leading-underscore names).
from .meta import (  # noqa: F401
    MAP_W, MAP_H, TILE, M4_SOLID_CHARS,
    PLAYER_START_TILE, VASILE_CACHE_TILE, STATION_DOOR_TILE,
    STATION_START_TILE, TRANSMITTER_TILE, M4_HOLD_SECONDS,
    M4_ROLE_TUNING, MISSION_PHASES,
)
from .maps import (  # noqa: F401
    MISSION4_STREET_MAP, MISSION4_STATION_MAP, MISSION4_MAP,
    _generate_m4_map, _generate_station_map, _live_map_dims,
    _last_keys, _objective, _radio_marks,
)
from .world import (  # noqa: F401
    _dist, _player_pos, _near, _tile_world, _street_door_pos,
    _vasile_cache_pos, _solid_walls, _set_objective, _movement_locked,
    _radio, _spawn_m4_guard, _build_m4_world, _build_station_world,
    _liaison_pos, _jammer_pos, friendly_npcs, M4_ALLY_POSTS,
    M4_INSERTION_TILES, M4_MAX_CONCURRENT, M4_SIEGE_RELIEF_FRAMES,
    _siege_reset, _siege_alive_count, _add_sniper_laser, _run_siege_director,
    _init_m4_allies, _arm_m4_allies, _update_m4_allies, _hit_m4_ally,
)
from .flow import (  # noqa: F401
    start_m4, start_mission4_station_checkpoint,
    start_mission4_tower_checkpoint, _enter_station, _update_stage,
    _complete_m4, handle_interact, handle_dialogue_event, _install_jammer,
)

# These names are REBOUND at runtime (map swaps, per-frame key capture,
# objective sets). The star-import copies above go stale on the first
# rebinding, so delete them and let __getattr__ serve a live view from
# the owner module (m3 facade contract).
del MISSION4_MAP, _last_keys, _objective, _radio_marks


_LIVE_STATE = frozenset([
    "MISSION4_MAP",
    "_last_keys",
    "_objective",
    "_radio_marks",
])

_LIVE_MODULES = (
    "missions.m4.draw",
    "missions.m4.systems",
    "missions.m4.flow",
    "missions.m4.world",
    "missions.m4.maps",
    "missions.m4.meta",
)


def __getattr__(name):
    """PEP 562 live view for rebound shared state (see _LIVE_STATE)."""
    if name in _LIVE_STATE:
        import sys as _sys2
        for _mod in _LIVE_MODULES:
            _m = _sys2.modules.get(_mod)
            if _m is not None and name in vars(_m):
                return vars(_m)[name]
    raise AttributeError(
        "module " + repr(__name__) + " has no attribute " + repr(name))
