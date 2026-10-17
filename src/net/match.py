
"""A multiplayer match session: authoritative host + interpolating clients.

This is the layer that turns the snapshot codec (net/protocol.py) and the
interpolation buffer (core/fixedstep.py) into an actual playable match. It
owns the transport for gameplay traffic and nothing else -- chat and the
server list stay in MPRelayClient.

Model
-----
Host-authoritative. The host simulates the world and broadcasts snapshots;
clients send input and draw what they are told. Nobody simulates remotely,
so a client cannot disagree with the host about where a wall is, and there
is no determinism requirement anywhere. That last point is why the
fixed-timestep accumulator (step 1) had to come first: the host's
simulation rate must not depend on its framerate.

Timing contract
---------------
Everything is counted in SIM TICKS, where one tick is 1/60 s of simulated
time, and both ends must agree on that. The host broadcasts at
SNAPSHOT_HZ (every 3rd tick); the client sends input at the full tick
rate. Snapshots are numbered by sim tick, never by packet count -- see
``SnapshotBuffer.push``.

Threading
---------
The socket is driven by MPRelayClient's worker thread; this module is
called from it. It therefore does no blocking work and keeps no locks of
its own beyond a short one around the snapshot buffer, which the render
thread reads. Everything handed across that boundary is an immutable
tuple, so a reader can never see a half-written world.
"""

import threading

from net import protocol as P
from core.fixedstep import SnapshotBuffer

# Simulation rate. Must match core.fixedstep.DEFAULT_HZ.
TICK_RATE = 60
SIM_DT = 1.0 / TICK_RATE

# How often the host broadcasts. 20 Hz is the usual compromise: below that
# interpolation gets lumpy, above it you are spending bandwidth on motion
# the client will interpolate anyway.
SNAPSHOT_HZ = 20
SNAPSHOT_EVERY = max(1, TICK_RATE // SNAPSHOT_HZ)      # 3 ticks at 60Hz

# Inputs older than this many are pruned. Without a bound, a flooding or
# reconnecting peer grows the input history without limit.
INPUT_HISTORY_TICKS = 12

# Client-side event queue depth. Events are drained once per rendered frame,
# so this bounds roughly a second of a very busy firefight; beyond that the
# oldest are dropped, because a stale kill feed entry is worse than none.
MAX_QUEUED_EVENTS = 256


class Fanout(object):
    """Host-side transport that broadcasts to every connected client.

    ``MatchSession`` only knows it has a client with a ``_send`` method. That
    is a one-to-one shape, which is fine for a client and wrong for a host
    with a roster: with a single shared socket, a snapshot goes to exactly
    one player, and with ``None`` it goes to nobody and every client sees an
    empty world. This keeps the one-method contract and fans out behind it.

    ``peers`` is a callable returning the current peer list rather than a
    list, because the roster changes while the match is running.
    """

    def __init__(self, peers):
        self._peers = peers

    def _send(self, obj):
        # Encode once, send many: with 7 players this runs 7x less JSON work.
        data = P.encode(obj)
        sent = 0
        for peer in list(self._peers()):
            sock = getattr(peer, "sock", None)
            if sock is None:
                continue
            try:
                sock.sendall(data)
                sent += 1
            except OSError:
                # A peer that died mid-send is handled on the next read;
                # dropping it here would race with the roster update.
                pass
        return sent > 0


class MatchSession(object):
    """One connected match. Drive it from the game's fixed-timestep loop.

    Host side:   call ``tick_once()`` each sim tick; it broadcasts on the
                 SNAPSHOT_HZ cadence. Set ``world`` or pass entities to
                 ``broadcast()``.
    Client side: call ``tick_once()`` each sim tick and ``sample_world()``
                 to get the interpolated world to draw.
    """

    def __init__(self, client, is_host=False, local_id=0, tick_rate=TICK_RATE):
        self._client = client
        self.is_host = bool(is_host)
        self.local_id = int(local_id)
        self.tick_rate = tick_rate
        self.tick = 0
        self._next_seq = 0
        self.world = ()          # host: current authoritative entities
        # Pending remote inputs: {peer_id: {seq: input-dict}}. A short
        # history so a packet arriving a tick late still lands sensibly
        # instead of being thrown away.
        self._inputs = {}
        self._input_locks = {}
        # Switching is an edge-triggered action, not a held input. TCP can
        # batch a switch and the next (neutral) frame in one read; taking
        # only the newest movement input would erase the switch. Conversely,
        # if a frame advances multiple sim ticks, reusing that input would
        # cycle more than once and end up on the original gun.
        self._pending_switches = {}
        self._buf = SnapshotBuffer(tick_rate, 0.100)
        self._buf_lock = threading.Lock()
        # Authoritative events from the host, drained by the render loop.
        self._events = []
        self._peer_ticks = {}
        self._stopped = False

    # ── outgoing ────────────────────────────────────────────────────────

    def _send(self, obj):
        send = getattr(self._client, "_send", None)
        if send is None:
            return False
        try:
            return send(obj)
        except Exception:
            # A dead socket must not take the render loop down with it.
            return False

    def send_input(self, move_x, move_y, aim=0.0, buttons=0, weapon=None):
        """Send local intent for this tick. Call once per sim tick.

        Only axes go on the wire: the host multiplies by its own speed, so
        there is no value a peer could send to move faster than a human.
        ``weapon`` is a REQUEST to switch; the host decides whether it
        happens, so a client cannot equip something it has not picked up.
        """
        if self._stopped:
            return False
        msg = P.make_input(self._next_seq, move_x, move_y, aim, buttons,
                           weapon=weapon)
        self._next_seq = (self._next_seq + 1) & 0xFFFFFFFF
        return self._send(msg)

    def send_events(self, tick, events):
        """Host only: tell every client what just happened.

        This is what replaced the client's local re-trace. The host knows
        exactly which shots connected; a client guessing from an interpolated
        world disagreed with it constantly and showed "HIT" on wall shots.
        """
        if not self.is_host or not events:
            return False
        return self._send(P.make_events(tick, events))

    def send_host_left(self, reason="host left the match"):
        """Host only: tell every client the session is over.

        The host IS the match -- there is no host migration -- so when it
        leaves, the session ends for everybody, and every client has to be
        told rather than left to guess why the snapshots stopped. Call this
        while the sockets are still open; tearing them down first drops the
        packet along with them.
        """
        if not self.is_host:
            return False
        return self._send(P.make_host_left(reason))

    def send_match_chat(self, text, author=None):
        """Put one chat line into the current match.

        Used in both directions, which is what makes it a chat channel rather
        than a host-only broadcast: a client sends its line up to the host,
        and the host sends the relayed copy back out to everyone. On the host
        the transport is the Fanout, so the line reaches every peer at once.

        ``author`` is supplied on the host side only, and it comes from the
        HOST's roster rather than from the packet. That is the whole point of
        relaying instead of forwarding: a client cannot post a line under
        somebody else's name, because the name is not the client's to choose.
        Clients omit it; their own line comes back attributed by the host.
        """
        msg = P.make_match_chat(text)
        if msg is None:
            return False
        if author is not None:
            name = P.sanitize_name(author)
            if name:
                msg["by"] = name
        return self._send(msg)

    def send_match_state(self, state):
        """Host only: publish the rules the client cannot infer itself.

        Scores, the round clock, team assignment and pickup respawn timers all
        live on the host. A client that guesses them is guessing wrong: it
        cannot know the clock is nearly out, and it would draw health packs
        that have already been taken.
        """
        if not self.is_host:
            return False
        return self._send(P.make_match_state(state))

    # ── incoming (called from the socket worker thread) ──────────────────

    def _accept_snapshot(self, msg):
        """Validate and buffer an inbound snapshot."""
        parsed = P.parse_snapshot(msg)
        if parsed is None:
            return False
        tick, entities = parsed
        with self._buf_lock:
            return self._buf.push(tick, entities)

    def _accept_events(self, msg):
        """Validate an inbound event packet and queue it for the render loop.

        Queued rather than applied here: this runs on the socket worker
        thread, and touching the view from there would be a data race. The
        match screen drains the queue once per frame.
        """
        parsed = P.parse_events(msg)
        if parsed is None:
            return False
        tick, events = parsed
        with self._buf_lock:
            self._events.extend(events)
            # Bound the queue. A host that floods events must not be able to
            # grow this without limit in a long session.
            if len(self._events) > MAX_QUEUED_EVENTS:
                del self._events[:len(self._events) - MAX_QUEUED_EVENTS]
        return True

    def drain_events(self):
        """Take and clear the queued events. Called once per render frame."""
        with self._buf_lock:
            if not self._events:
                return []
            out = list(self._events)
            del self._events[:]
            return out

    def _accept_input(self, msg, peer_id=0):
        """Validate and store an inbound input packet.

        Takes the RAW wire dict -- the one that still carries ``"t"`` -- so
        there is exactly one place that decides what a valid input is.
        Parsing earlier in the call chain used to strip ``"t"`` before it
        got here, and the validation below then rejected every remote
        player's packet as "not an input": remote players could not move or
        shoot, while the host's own keyboard input (built with ``t``
        present) worked fine.
        """
        parsed = P.parse_input(msg)
        if parsed is None:
            return False
        lock = self._input_locks.setdefault(peer_id, threading.Lock())
        with lock:
            hist = self._inputs.setdefault(peer_id, {})
            seq = parsed["q"]
            # Queue the one-shot action BEFORE the next packet can replace
            # the latest movement sample. Ignore duplicate sequence numbers
            # (e.g. a retransmitted input); a tap must never switch twice.
            if seq not in hist and ("w" in parsed or parsed.get("wcycle")):
                pending = self._pending_switches.setdefault(peer_id, [])
                pending.append((parsed.get("w"), bool(parsed.get("wcycle"))))
                if len(pending) > INPUT_HISTORY:
                    del pending[:-INPUT_HISTORY]
            hist[seq] = parsed
            if len(hist) > INPUT_HISTORY:
                cutoff = sorted(hist)[-INPUT_HISTORY]
                for k in [k for k in hist if k < cutoff]:
                    del hist[k]
        return True

    # ── per-tick driver ─────────────────────────────────────────────────

    def tick_once(self):
        """Advance one sim tick. Host broadcasts on the snapshot cadence."""
        self.tick += 1
        if self.is_host and (self.tick % SNAPSHOT_EVERY == 0):
            self.broadcast()
        return self.tick

    def broadcast(self, entities=None):
        """Host only: send the current world to every client."""
        if not self.is_host:
            return False
        ents = entities if entities is not None else self.world
        return self._send(P.make_snapshot(self.tick, ents))

    def sample_world(self):
        """The world to draw, or None.

        Host: its own authoritative entities. Client: the interpolated
        result. None means "not enough data yet" -- keep drawing the
        previous frame rather than flashing to empty.
        """
        if self.is_host:
            return self.world if self.world else None
        with self._buf_lock:
            return self._buf.sample(self.tick)

    def consume_input(self, peer_id=0):
        """Host only: the newest input from a peer, or None.

        Returning None means "no input this tick", which the host must read
        as standing still. Re-applying the previous input would make a
        client keep walking after it let go.
        """
        lock = self._input_locks.get(peer_id)
        if lock is None:
            return None
        with lock:
            hist = self._inputs.get(peer_id) or {}
            if not hist:
                return None
            newest = max(hist)
            self._peer_ticks[peer_id] = newest
            # Motion/fire still use the latest sampled state as before, but
            # the switch is consumed from the FIFO exactly once. Copy the
            # packet so the history itself stays unchanged for diagnostics.
            inp = dict(hist[newest])
            inp.pop("w", None)
            inp.pop("wcycle", None)
            pending = self._pending_switches.get(peer_id)
            if pending:
                weapon, cycle = pending.pop(0)
                if weapon is not None:
                    inp["w"] = weapon
                elif cycle:
                    inp["wcycle"] = 1
            return inp

    def forget_peer(self, peer_id):
        """Release a departed player's input, including unspent switches.

        IDs are reused when a new player joins, so stale input/queued taps
        from the old owner must never switch the new player's weapon.
        """
        lock = self._input_locks.get(peer_id)
        if lock is not None:
            with lock:
                self._inputs.pop(peer_id, None)
                self._pending_switches.pop(peer_id, None)
                self._peer_ticks.pop(peer_id, None)
            self._input_locks.pop(peer_id, None)

    def stop(self):
        self._stopped = True
        with self._buf_lock:
            self._buf.clear()

    def stats(self):
        """Diagnostics for the dev overlay and tests."""
        with self._buf_lock:
            n = len(self._buf)
            latest = self._buf.latest_tick()
        return {
            "tick": self.tick,
            "buffered": n,
            "latest_tick": latest,
            # Positive lag means the client is ahead of the newest snapshot,
            # i.e. it is starved and holding the last frame.
            "lag_ticks": (self.tick - latest) if latest is not None else None,
            "is_host": self.is_host,
            "peers": sorted(self._peer_ticks.keys()),
        }

# long-lived peer grows the history forever.
INPUT_HISTORY = 30

# Player speed in px/frame, matching Player.speed. The host owns this
# number: clients send a direction, never a distance, so a peer cannot
# inflate its own movement.
PLAYER_SPEED = 5.0
