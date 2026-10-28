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
import time
from collections import deque

from net import protocol as P
from net import udp_transport as UDP
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
# A held movement/fire state must not survive a dead or silent datagram path.
INPUT_STALE_SECONDS = 0.25

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
        # Control messages remain ordered and reliable on each peer's TCP link.
        sent = 0
        for peer in list(self._peers()):
            wire = getattr(peer, "wire", None)
            if wire is None:
                continue
            try:
                wire._send(obj)
                sent += 1
            except OSError:
                # A peer that died mid-send is handled on the next read;
                # dropping it here would race with the roster update.
                pass
        return sent > 0

    def _send_snapshot(self, obj):
        """Prefer disposable UDP snapshots; retain TCP for unreachable peers."""
        sent = 0
        fallback = 0
        for peer in list(self._peers()):
            sock = getattr(peer, "udp_sock", None)
            address = getattr(peer, "udp_addr", None)
            token = getattr(peer, "udp_token", "")
            if (getattr(peer, "udp_ready", False) and sock is not None
                    and address is not None and token):
                packet = dict(obj)
                packet["u"] = token
                data = UDP.encode_datagram(packet)
                try:
                    if data is not None:
                        sock.sendto(data, address)
                        sent += 1
                        continue
                except OSError:
                    # If the datagram route breaks, immediately put the
                    # snapshot on the reliable channel while the peer probes
                    # for a new route.
                    peer.udp_ready = False
                    peer.udp_addr = None
            wire = getattr(peer, "wire", None)
            if wire is not None:
                wire._send(obj)
                fallback += 1
        return bool(sent or fallback)


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
        self._latest_input_seq = {}
        self._input_received_at = {}
        self._input_locks = {}
        # Switching is an edge-triggered action, not a held input. TCP can
        # batch a switch and the next (neutral) frame in one read; taking
        # only the newest movement input would erase the switch. Conversely,
        # if a frame advances multiple sim ticks, reusing that input would
        # cycle more than once and end up on the original gun.
        self._pending_switches = {}
        self._switch_seen = {}
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

    @staticmethod
    def _seq_after(seq, previous):
        """Wrap-safe ordering for 32-bit input sequence numbers."""
        delta = (int(seq) - int(previous)) & 0xFFFFFFFF
        return 0 < delta < 0x80000000

    def _queue_switch_locked(self, peer_id, seq, parsed):
        """Record one weapon switch at most once per input sequence."""
        if "w" not in parsed and not parsed.get("wcycle"):
            return
        seen = self._switch_seen.setdefault(peer_id, deque(maxlen=64))
        if seq in seen:
            return
        seen.append(seq)
        pending = self._pending_switches.setdefault(peer_id, [])
        pending.append((parsed.get("w"), bool(parsed.get("wcycle"))))
        if len(pending) > INPUT_HISTORY_TICKS:
            del pending[:-INPUT_HISTORY_TICKS]

    def _accept_input(self, msg, peer_id=0):
        """Validate and store the newest input state from a peer.

        Inputs are latest-state updates, not a queue of actions. UDP can
        reorder them, so an older datagram must never replace a newer one.
        One-shot switches are retained separately and deduplicated by their
        sequence number, which lets a delayed action arrive after newer motion.
        """
        parsed = P.parse_input(msg)
        if parsed is None:
            return False
        lock = self._input_locks.setdefault(peer_id, threading.Lock())
        with lock:
            seq = parsed["q"]
            self._queue_switch_locked(peer_id, seq, parsed)
            latest = self._latest_input_seq.get(peer_id)
            if latest is not None and seq == latest:
                # A replay of the same datagram must not keep a held key alive
                # past the input freshness window.
                return True
            if latest is not None and not self._seq_after(seq, latest):
                # The action (if any) above is still honored once, but stale
                # movement/fire state cannot roll the player backwards.
                return True
            hist = self._inputs.setdefault(peer_id, {})
            hist[seq] = parsed
            self._latest_input_seq[peer_id] = seq
            self._input_received_at[peer_id] = time.monotonic()
            for old_seq in list(hist):
                age = (seq - old_seq) & 0xFFFFFFFF
                if age >= 0x80000000 or age > INPUT_HISTORY_TICKS:
                    hist.pop(old_seq, None)
        return True

    def _accept_action(self, msg, peer_id=0):
        """Accept a reliable one-shot action from the control connection."""
        parsed = P.parse_action(msg)
        if parsed is None:
            return False
        lock = self._input_locks.setdefault(peer_id, threading.Lock())
        with lock:
            self._queue_switch_locked(peer_id, parsed["q"], parsed)
        return True

    # ── per-tick driver ─────────────────────────────────────────────────

    def tick_once(self):
        """Advance one sim tick. Host broadcasts on the snapshot cadence."""
        self.tick += 1
        if self.is_host and (self.tick % SNAPSHOT_EVERY == 0):
            self.broadcast()
        return self.tick

    def broadcast(self, entities=None):
        """Host only: publish a numbered world snapshot to every client.

        Fanout uses authenticated UDP where available so a lost packet never
        stalls later snapshots. Clients without a working datagram route keep
        receiving the same snapshot over reliable TCP.
        """
        if not self.is_host:
            return False
        ents = entities if entities is not None else self.world
        msg = P.make_snapshot(self.tick, ents)
        send_snapshot = getattr(self._client, "_send_snapshot", None)
        if send_snapshot is not None:
            try:
                return bool(send_snapshot(msg))
            except Exception:
                return False
        return self._send(msg)

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
        """Return the newest fresh state; one-shot actions survive packet loss."""
        lock = self._input_locks.get(peer_id)
        if lock is None:
            return None
        with lock:
            hist = self._inputs.get(peer_id) or {}
            newest = self._latest_input_seq.get(peer_id)
            inp = dict(hist[newest]) if newest in hist else None
            received_at = self._input_received_at.get(peer_id, 0.0)
            if received_at and time.monotonic() - received_at > INPUT_STALE_SECONDS:
                # A lost route must not leave a player walking or firing on a
                # stale held key. The next valid packet immediately resumes.
                inp = None
            pending = self._pending_switches.get(peer_id)
            if inp is None and not pending:
                return None
            if inp is None:
                inp = {"q": newest if newest is not None else 0,
                       "mx": 0, "my": 0, "a": 0.0, "b": 0}
            self._peer_ticks[peer_id] = inp.get("q", 0)
            inp.pop("w", None)
            inp.pop("wcycle", None)
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
                self._latest_input_seq.pop(peer_id, None)
                self._input_received_at.pop(peer_id, None)
                self._switch_seen.pop(peer_id, None)
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
