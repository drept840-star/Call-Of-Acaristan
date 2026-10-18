"""Mission 6: Black Notebook - re-export facade (load order = parts order).

Parts: meta.py, maps.py, decor.py, stealth.py, world.py, flow.py, systems.py,
draw.py (train3d/m6_audio are lazy mission-owned modules loaded on demand).
"""
from .meta import *  # noqa: F401,F403
from .maps import *  # noqa: F401,F403
from .decor import *  # noqa: F401,F403
from .stealth import *  # noqa: F401,F403
from .world import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403

from .maps import (  # noqa: F401
    M6_CUSTOMS_MAP, M6_NOMAN_MAP, M6_RAIL_MAP,
    MISSION6_MAP, M6_STRUCTURE_MAP, _live_map_dims, _last_keys, _objective,
    _radio_marks, _validate, bind_stage, grid_for, structure_for,
)
from .flow import (  # noqa: F401
    start_m6, start_mission6_customs_checkpoint,
    start_mission6_noman_checkpoint, start_mission6_rail_checkpoint,
    start_mission6_train_checkpoint, handle_interact,
    update_stage, on_m6_cutscene_done, on_train_done,
    interaction_prompt,
)
from .systems import game_update  # noqa: F401
from .draw import game_draw, M6_TILE_BASE  # noqa: F401

# Rebound at runtime - serve live views from the owner module.
del MISSION6_MAP, M6_STRUCTURE_MAP, _last_keys, _objective, _radio_marks

_LIVE_STATE = frozenset(["MISSION6_MAP", "M6_STRUCTURE_MAP", "_last_keys",
                         "_objective", "_radio_marks"])
_LIVE_MODULES = (
    "missions.m6.draw",
    "missions.m6.systems",
    "missions.m6.flow",
    "missions.m6.world",
    "missions.m6.decor",
    "missions.m6.stealth",
    "missions.m6.maps",
    "missions.m6.meta",
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
