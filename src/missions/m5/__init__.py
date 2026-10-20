"""Mission 5: Martial Law - the capital under emergency rule.

Four days after the Vostral (Day ~8), Retardovici dissolves parliament and
folds KRAP into the Presidential Guard under Commander Vasile. Vasile orders
Biribel to bring Maru in; Biribel gets Maru out - through the Guard's raid on the
MAG print works and down the tunnel to the river, where Ucilev Nadgob
Ierdna has him in his sights and lowers the rifle.

Build plan: docs/MISSION5_BUILD_PLAN.md. Package layout: re-export facade.
Parts (load order): meta.py, maps.py, world.py, flow.py, systems.py,
draw.py.
"""
from .meta import *  # noqa: F401,F403
from .maps import *  # noqa: F401,F403
from .world import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403

from .maps import (  # noqa: F401
    MISSION5_HQ_MAP, MISSION5_QUARTER_MAP, MISSION5_PRINT_MAP, MISSION5_TUNNEL_MAP,
    MISSION5_MAP, _live_map_dims, _last_keys, _objective, _radio_marks,
    _validate,
)
from .world import (  # noqa: F401
    _dist, _player_pos, _near, _tile_world, _solid_walls, _set_objective,
    _movement_locked, _radio, _spawn_m5_guard, _register_guard_kill,
    _build_hq_world, _update_hq_barks, _vasile_desk_pos, _vasile_pos,
    _build_quarter_world, _build_print_world, _build_tunnel_world,
    _printworks_door_pos, _maru_office_pos, _stair_pos, _river_gate_pos,
    _init_maru, _update_maru, _hit_maru, friendly_npcs,
    _spawn_raid_squad, _spawn_pursuit_squad, _squad_alive_count,
)
from .flow import (  # noqa: F401
    start_m5, start_mission5_hq_checkpoint,
    start_mission5_quarter_checkpoint, start_mission5_printworks_checkpoint,
    start_mission5_tunnel_checkpoint, _update_stage, _complete_m5,
    handle_interact, handle_dialogue_event, inspect_active, handle_inspect_event,
    _enter_printworks, _enter_tunnel,
    _begin_raid, _open_stair, _m5_dlg, M5_FAIL_HOLD_FRAMES,
    _enter_hq, _enter_quarter, _start_vasile_dialogue, _vasile_beats,
)
from .systems import (  # noqa: F401
    game_update, _update_bullets, _update_m5_enemies, _m5_guards_active,
    _on_enemy_death,
)
from .draw import game_draw, _draw_m5_guard, _maru_pose, M5_TILE_BASE  # noqa: F401

# Rebound at runtime - serve live views from the owner module.
del MISSION5_MAP, _last_keys, _objective, _radio_marks

_LIVE_STATE = frozenset(["MISSION5_MAP", "_last_keys", "_objective",
                         "_radio_marks"])
_LIVE_MODULES = (
    "missions.m5.draw",
    "missions.m5.systems",
    "missions.m5.flow",
    "missions.m5.world",
    "missions.m5.maps",
    "missions.m5.meta",
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
