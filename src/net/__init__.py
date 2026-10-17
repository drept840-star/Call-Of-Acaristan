
"""net - multiplayer relay client. Parts: protocol.py, client.py.

Load order (top-down) is the import order. ``protocol`` must precede
``client`` because the client imports it at module scope.

``net`` deliberately has NO dependency on ``ui``, ``core``, or pygame: it is
the one layer in this game that must be importable by a headless tool with
no display. The chat callback crosses back into the UI via an explicit
``register_chat_sink()`` hook rather than an import, which keeps the
dependency graph acyclic in both directions.
"""
from .protocol import *  # noqa: F401,F403
from .client import *  # noqa: F401,F403
from .discovery import *  # noqa: F401,F403
from .client import MPRelayClient, register_chat_sink, friendly_error  # noqa: F401
from .discovery import discover_master  # noqa: F401
from .protocol import (  # noqa: F401
    PROTO_VERSION, DEFAULT_MASTER_HOST, DEFAULT_MASTER_PORT,
    DISCOVERY_PORT, encode, decode, normalize_row, normalize_rows,
    color_for, checksum,
)
