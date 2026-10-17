
"""Package missions/m1 - re-export facade. Parts: map.py, main.py, hotwire.py, update.py, draw.py."""
"""Mission 1B gameplay: warehouse infiltrate/firefight/escape."""
from .map import *  # noqa: F401,F403
from .main import *  # noqa: F401,F403
from .hotwire import *  # noqa: F401,F403
from .update import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403
from .map import _tc, _lerp  # noqa: F401
from .main import _walk_footstep_timer, _init_mission_specials, _trigger_civilian_payoff  # noqa: F401
from .hotwire import _hotwire_wire_nodes, _reset_hotwire_minigame  # noqa: F401
from .update import _last_keys  # noqa: F401
from .draw import _draw_molotov_icon, _escape_subtitle, _draw_biribel_soldier_closeup, _draw_escape_truck  # noqa: F401
from .map import _spawn_molotov_fire, _wall_blocks_line  # noqa: F401  (imported names, skipped by star imports)

del _last_keys


_LIVE_STATE = frozenset([
    "_last_keys",
])

_LIVE_MODULES = (
    "missions.m1.update",
    "missions.m1.draw",
    "missions.m1.hotwire",
    "missions.m1.main",
    "missions.m1.map",
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
