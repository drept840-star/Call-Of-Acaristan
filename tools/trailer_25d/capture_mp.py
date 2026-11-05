"""Multiplayer arena clip (2.5D) for the announcement trailer.

    python tools/trailer_25d/capture_mp.py

Runs tools/mp_trailer_capture.py into trailers/announce_25d/mp/. Its bots
aim with 2D screen coordinates (mouse + 2D camera), so the 3D view's aim is
pointed back at the 2D maths; the world still draws in 2.5D. Hosting is
forced to LAN mode.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.environ["MP_ANNOUNCE_DIR"] = os.path.join(ROOT, "trailers", "announce_25d", "mp")
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "src"))

from ui import arena_view, arena_view3d  # noqa: E402

arena_view3d.ArenaView3D.aim_angle = arena_view.ArenaView.aim_angle

# LAN only: no public tunnel, and share_port stays the loopback port the
# capture's headless bots dial.
from ui import match_screen as _ms  # noqa: E402
_init = _ms.MatchScreen.__init__


def _lan_init(self, *a, **k):
    _init(self, *a, **k)
    self.net_mode = _ms.NET_LAN


_ms.MatchScreen.__init__ = _lan_init

# The host now requires the room's join token; the capture's bots predate
# it. Pin the token (dev hook) and have every join packet carry it.
TOKEN = "A5" * _ms.JOIN_TOKEN_BYTES
os.environ["ACA_MP_DEV_TOKEN"] = TOKEN
from net import protocol as _P  # noqa: E402
_join = _P.make_join_match


def _join_tok(*a, **k):
    k["token"] = k.get("token") or TOKEN
    return _join(*a, **k)


_P.make_join_match = _join_tok
import mp_trailer_capture as m  # noqa: E402

sys.argv = [sys.argv[0], "--no-browser", "--combat-seconds", "30"]
sys.exit(m.main())
