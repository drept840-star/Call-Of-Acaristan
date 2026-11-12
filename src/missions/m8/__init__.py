"""Mission 8: The Call - re-export facade (load order = parts order).

Parts: meta.py, flow.py, systems.py, draw.py.  Route packages: revenge/
(slice 1: the trap and gantry fight plus placeholder beats), duty/ (reserved).
"""
from .meta import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403
