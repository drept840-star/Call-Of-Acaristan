"""Mission 7: Fallow Ground - re-export facade (load order = parts order).

Parts: m7_audio.py, meta.py, flow.py, systems.py, draw.py.
"""
from . import m7_audio as _m7_audio  # noqa: F401  (generators registered on first use)
from .meta import *  # noqa: F401,F403
from .flow import *  # noqa: F401,F403
from .systems import *  # noqa: F401,F403
from .draw import *  # noqa: F401,F403
