
"""Game-side client for the KRAPNET master server.

Threading model
---------------
The pygame main loop runs at 60Hz and must never block. A DNS lookup or a
TCP connect to an unreachable host can stall for many seconds, so *no*
socket call is ever made from the caller's thread.

Instead this module owns exactly one daemon worker thread. The main thread
only ever touches:

  * ``state()``      -- returns an immutable snapshot (a tuple of tuples)
  * ``send_*()``     -- appends to a deque and returns immediately

Both are guarded by a ``threading.Lock`` held for microseconds, and the
worker never holds that lock across a blocking socket call. The result is
that the render thread can stall the network for as long as it likes without
ever stalling the network back.

The snapshot-is-a-tuple rule matters: the UI iterates the server list while
rendering, and handing it a live list that the worker mutates mid-iteration
would be a classic heisenbug. Copying a list of a few dozen rows once per
frame is free.
"""

import socket
import threading
import time

from collections import deque

from net import protocol as P

# How often the worker tries to (re)connect. Deliberately slow: the master
# may be down, and we must not spin a reconnect storm against it.
RECONNECT_INTERVAL = 3.0
# Query cadence while the browser is open.
QUERY_INTERVAL = 4.0
SOCKET_TIMEOUT = 4.0

# Connection states surfaced to the UI.
ST_IDLE = "idle"
ST_CONNECTING = "connecting"
ST_ONLINE = "online"
ST_ERROR = "error"


class MPRelayClient(object):
    """Background client. Create once, then poll ``state()`` once per frame."""

    def __init__(self, host=P.DEFAULT_MASTER_HOST, port=P.DEFAULT_MASTER_PORT,
                 nickname="operator", chat_enabled=True):
        self.host = host
        self.port = port
        self.nickname = nickname
        self.chat_enabled = chat_enabled

        self._lock = threading.Lock()
        self._thread = None
        self._running = False

        # Owned by the worker thread unless noted.
        self._sock = None
        self._buf = b""
        self._status = ST_IDLE
        self._error = ""
        self._servers = []          # list of (name, cur, max, ping, rules)
        self._next_query = 0.0
        self._next_connect = 0.0
        # Soft-error notes from the master ("sending too fast"). Deliberately
        # NOT folded into _error: _error is bound to the connection state, and
        # putting a transient note there would make the whole session look
        # broken to every caller of state().
        self._notes = []

        # Written by the main thread, drained by the worker.
        self._outbox = deque()
        self._want_connect = False

        # Gameplay. Set by attach_match(); None while just browsing a lobby.
        # Held as a plain attribute guarded by _lock, and never a module
        # global, so two clients in one process cannot collide.
        self._match = None

    # ── Match (gameplay) ──
    # Kept deliberately thin: MPRelayClient owns the socket and the worker
    # thread, MatchSession owns the game state. Neither imports the other
    # at module scope -- net.load-order rules require that -- so the
    # handoff goes through this attribute.

    def attach_match(self, session):
        """Route inbound snapshots/inputs to a MatchSession (or None)."""
        with self._lock:
            self._match = session
        return session

    def detach_match(self):
        with self._lock:
            self._match = None

    def match(self):
        with self._lock:
            return self._match

    def _match_snapshot(self, msg):
        m = self.match()
        if m is None:
            return False
        try:
            return m._accept_snapshot(msg)
        except Exception:
            return False

    def _match_input(self, msg):
        m = self.match()
        if m is None:
            return False
        peer = msg.get("p")
        try:
            peer_id = int(peer) if isinstance(peer, (int, float)) else 0
        except (TypeError, ValueError):
            peer_id = 0
        try:
            return m._accept_input(msg, peer_id)
        except Exception:
            return False

    # ── Public API (main thread) ────────────────────────────────────────

    def start(self):
        """Spin up the worker. Safe to call twice."""
        with self._lock:
            if self._running:
                return
            self._running = True
        self._thread = threading.Thread(
            target=self._worker, name="mprelay", daemon=True)
        self._thread.start()

    def stop(self):
        """Signal the worker to exit and close the socket. Non-blocking."""
        with self._lock:
            self._running = False
        t = self._thread
        if t is not None and t.is_alive():
            t.join(timeout=0.5)
        self._thread = None

    def flush(self, timeout=1.0):
        """Best-effort: let queued outgoing messages reach the socket.

        send_chat() only enqueues; the worker actually writes on its next
        pass. That is right for the game, where the connection lives for
        minutes, but a short-lived client (our command-line joiner, someone
        typing a last line and hitting Ctrl+C) can be stopped before the
        worker ever runs, silently dropping the message.

        Callers must flush() BEFORE stop(). Deliberately opt-in so the
        render loop never blocks on it.
        """
        deadline = time.monotonic() + max(0.0, timeout)
        while time.monotonic() < deadline:
            with self._lock:
                pending = bool(self._outbox)
            if not pending:
                return True
            t = self._thread
            if t is None or not t.is_alive():
                return False
            time.sleep(0.01)
        return False

    def state(self):
        """Snapshot for rendering. Returns (status, error, servers, nickname).

        ``servers`` is a tuple of ``(name, cur, max, ping, rules)`` where
        ``rules`` is a tuple of strings (possibly empty). Copying under the
        lock is what makes concurrent worker mutation invisible to the UI.
        """
        with self._lock:
            return (
                self._status,
                self._error,
                tuple(self._servers),
                self.nickname,
            )

    def request_connect(self):
        """Ask the worker to (re)connect on its next pass. Non-blocking."""
        self._outbox.append(("connect", None))
        with self._lock:
            self._status = ST_CONNECTING
            self._error = ""
        return True

    def refresh(self):
        """Force an immediate server-list query on the next worker pass."""
        self._outbox.append(("query", None))
        with self._lock:
            self._next_query = 0.0

    def send_chat(self, text):
        """Queue a chat line. Returns False if the text is unusable.

        Over-long input is REJECTED here rather than truncated. The master
        sanitizes too -- it has to, because its input is a hostile peer -- but
        this is the player's own line, and silently dropping the end of a
        sentence someone just typed is worse than telling them it was too
        long. The bound is the protocol's own (P.MAX_CHAT_CHARS) rather than a
        private number that can drift from what the master will accept.
        """
        if not isinstance(text, str):
            return False
        body = text.strip()
        if not body or len(body) > P.MAX_CHAT_CHARS:
            return False
        self._outbox.append(("chat", " ".join(body.split())))
        return True

    # ── Worker (background thread only) ───────────────────────────────

    def _alive(self):
        with self._lock:
            return self._running

    def _set_status(self, status, error=""):
        with self._lock:
            self._status = status
            self._error = error

    def _worker(self):
        while self._alive():
            self._drain_outbox()
            if self._sock is None:
                if not self._try_connect():
                    time.sleep(0.25)
                    continue
            self._pump()
            time.sleep(0.02)

        # Tear down outside the lock.
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
            self._sock = None

    def _drain_outbox(self):
        """Move queued main-thread intents into worker-side flags."""
        while self._outbox:
            kind, payload = self._outbox.popleft()
            if kind == "connect":
                self._want_connect = True
            elif kind == "query":
                self._next_query = 0.0
            elif kind == "chat":
                if self._sock is not None:
                    self._send({"t": P.T_CHAT, "user": self.nickname,
                                "text": payload})

    def _try_connect(self):
        """One connection attempt. Blocking, but on the worker thread only."""
        self._want_connect = False
        now = time.monotonic()
        if now < self._next_connect:
            return False
        self._next_connect = now + RECONNECT_INTERVAL

        self._set_status(ST_CONNECTING)
        try:
            sock = socket.create_connection((self.host, self.port),
                                            timeout=SOCKET_TIMEOUT)
            sock.settimeout(0.2)
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except OSError as exc:
            self._set_status(ST_ERROR, friendly_error(exc))
            return False

        self._sock = sock
        self._buf = b""
        self._set_status(ST_ONLINE)
        self._send({"t": P.T_HELLO, "user": self.nickname,
                    "proto": P.PROTO_VERSION})
        self._send({"t": P.T_QUERY})
        self._next_query = time.monotonic() + QUERY_INTERVAL
        return True

    def _send(self, obj):
        """Best-effort write. Never raises; a dead socket is just a reset."""
        if self._sock is None:
            return False
        try:
            self._sock.sendall(P.encode(obj))
            return True
        except OSError:
            self._reset()
            return False

    def _reset(self):
        """Drop the socket and clear the cached list. Worker thread only."""
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None
        self._buf = b""
        with self._lock:
            self._servers = []
        self._set_status(ST_ERROR, "connection lost")

    def _pump(self):
        """One non-blocking read + dispatch cycle."""
        if self._sock is None:
            return
        try:
            chunk = self._sock.recv(4096)
        except socket.timeout:
            # No data yet -- NOT a disconnect. This must return early:
            # recv() reports a timeout as b"", which is indistinguishable
            # from a clean close unless we branch on the exception.
            self._maybe_poll()
            return
        except OSError:
            self._reset()
            return

        if chunk == b"":
            # Clean close from the peer (recv returned no data, no error).
            self._reset()
            return

        self._buf += chunk
        if len(self._buf) > 1 << 20:
            # A peer streaming without newlines must not eat all our RAM.
            self._reset()
            return
        self._consume_lines()
        self._maybe_poll()

    def _maybe_poll(self):
        """Issue the periodic keepalive query if it is due."""
        if not self.chat_enabled:
            return
        now = time.monotonic()
        if now >= self._next_query:
            self._next_query = now + QUERY_INTERVAL
            self._send({"t": P.T_QUERY})

    def _consume_lines(self):
        """Split the read buffer on newlines and dispatch each message.

        Buffering until the newline arrives is what makes this correct for
        partial reads: a TCP segment can split a message anywhere.
        """
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            msg = P.decode(line)
            if msg:
                self._dispatch(msg)

    def _dispatch(self, msg):
        kind = msg.get("t")
        if kind == P.T_SERVERS:
            self._apply_server_list(msg)
        elif kind == P.T_CHAT:
            self._push_chat(msg)
        elif kind == P.T_SNAPSHOT:
            # Gameplay. Hand off to the match session if one is listening;
            # the lobby never needs to know what a snapshot is.
            self._match_snapshot(msg)
        elif kind == P.T_INPUT:
            self._match_input(msg)
        elif kind == P.T_WELCOME:
            # The server echoes the sanitised name back. We adopt it only if
            # it is genuinely different, so that a "welcome" sent before our
            # HELLO lands (when the server still calls us "anon") cannot
            # clobber the name we actually chose.
            name = msg.get("name")
            if isinstance(name, str) and name and name != self.nickname:
                with self._lock:
                    self.nickname = name[:32]
        elif kind == P.T_ERROR:
            # A soft error is a note -- "sending too fast", "registering too
            # often" -- and must NOT tear the session down. Treating it as a
            # fault would mean a player who typed quickly lost their server
            # list and chat until they restarted the game.
            text = str(msg.get("text", ""))[:120]
            if P.is_soft_error(msg):
                with self._lock:
                    self._notes.append(text)
                    del self._notes[:-8]
            else:
                self._set_status(ST_ERROR, text)

    def take_notes(self):
        """Drain the soft-error notes the master has sent. Never raises."""
        with self._lock:
            out = list(self._notes)
            del self._notes[:]
        return out

    def _apply_server_list(self, msg):
        """Replace the snapshot with the authoritative list."""
        rows = P.normalize_rows(msg.get("servers"))
        rules = msg.get("rules")
        if not isinstance(rules, dict):
            rules = {}

        built = []
        for name, cur, mx, ping in rows:
            lines = rules.get(name)
            if isinstance(lines, (list, tuple)):
                lines = tuple(
                    str(x)[:80] for x in lines
                    if isinstance(x, (str, int, float))
                )[:6]
            else:
                lines = ()
            built.append((name, cur, mx, ping, lines))

        with self._lock:
            self._servers = built

    def _push_chat(self, msg):
        """Deliver a chat line to the UI.

        We hand it off through a module-level hook rather than importing
        ``ui`` here: ``net`` loads before ``ui``, so importing it at module
        scope would create a load-order cycle. ``ui.mp`` registers the sink
        at import time.
        """
        sink = _CHAT_SINK
        if sink is None:
            return
        try:
            sink(msg)
        except Exception:
            # A rendering bug in the sink must not kill the network thread.
            pass


# Module-level chat sink, set by ui.mp via register_chat_sink().
_CHAT_SINK = None


def register_chat_sink(fn):
    """Install the callback that receives inbound chat lines."""
    global _CHAT_SINK
    _CHAT_SINK = fn
    return fn


def friendly_error(exc):
    """Turn an OSError into something a player can read."""
    err = getattr(exc, "errno", None)
    if err in (10061, 111):
        return "no master on that host"
    if err == 11001:
        return "host not found"
    if err in (10060, 110):
        return "master timed out"
    if err in (10051, 101):
        return "network unreachable"
    if err in (10013, 13):
        return "blocked by firewall"
    text = getattr(exc, "strerror", None) or str(exc)
    return text[:80]
