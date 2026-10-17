
"""Fixed-timestep accumulator, for making the simulation host-independent.

Why this exists
---------------
The main loop advances the game by whatever `dt` the OS hands us:

    dt = min(clock.tick(60) / 1000.0, MAX_DT)

Movement already compensates -- speeds are stored as px/frame and scaled by
``60.0 * STATE.dt`` -- so a player walks the same distance per second on
any machine. But ~60 *frame counters* (``self.fire_cooldown -= 1``,
``self.state_timer -= 1``) have no such compensation: they advance once per
rendered frame. Under a 60 FPS cap that is very nearly correct, and it is
why single-player has never visibly suffered.

It matters for multiplayer. The host simulates; every client is then shown
the host's world. If the host's counters drift with its frame pacing, then
the *rules of the match* drift with the host's hardware -- a machine that
hitches hands out measurably different fire rates. For a shooter that is
not acceptable, and it is the same class of bug that makes lockstep
replays desync.

The fix is the standard one: advance the simulation in fixed-size steps and
let rendering run free. Wall-clock time is accumulated and drained in whole
1/60 s ticks, so N seconds of play is always exactly 60*N simulation steps
no matter how the frames are spaced.

Scope
-----
Deliberately OFF by default. Single-player keeps its current timing
exactly, so this cannot regress the campaign; it is switched on for a real
multiplayer session (``set_enabled(True)``).

Spiral-of-death guard
---------------------
If a frame takes so long that a huge backlog builds (alt-tab, a long GC
pause, a breakpoint), draining every accumulated tick would take longer
than real time and fall further behind -- forever. ``max_steps`` caps the
catch-up per frame and the excess time is discarded, so the simulation
runs momentarily slow instead of locking up.
"""

# Simulation rate. 60 Hz matches the existing cap, so enabling this on a
# 60 Hz machine is a no-op; it only matters when the loop is free to run
# faster (which is where the drift would come from).
DEFAULT_HZ = 60

# Never run more than this many sim steps in one rendered frame. Five
# frames of backlog (~83 ms) is enough to ride out a normal hitch without
# inviting a death spiral.
DEFAULT_MAX_STEPS = 5


class FixedStepClock(object):
    """Accumulates real elapsed time and hands out fixed-size sim steps.

    Usage per frame::

        for _ in clock.steps(real_dt):
            simulate_one_tick()        # always exactly clock.dt seconds

    With nothing stepped (fast display, no backlog) the game still advances
    at most one step per frame, which is the point: ``alpha`` then tells the
    renderer how far between the last two sim states it is, so motion stays
    smooth instead of stepping.
    """

    def __init__(self, hz=DEFAULT_HZ, max_steps=DEFAULT_MAX_STEPS):
        if hz <= 0:
            raise ValueError("hz must be positive, got %r" % (hz,))
        if max_steps < 1:
            raise ValueError("max_steps must be >= 1, got %r" % (max_steps,))
        self.hz = float(hz)
        self.max_steps = int(max_steps)
        self.dt = 1.0 / self.hz
        self._accumulator = 0.0
        # Total simulated seconds since construction/reset. Handy for tests
        # and for asserting that two machines stayed in lockstep.
        self.sim_time = 0.0
        # Times we had to throw backlog away. Non-zero means the machine
        # cannot keep up; worth surfacing rather than hiding.
        self.dropped_steps = 0
        self.enabled = False

    def reset(self):
        """Discard any partial step. Call when a match starts/stops."""
        self._accumulator = 0.0

    def steps(self, real_dt):
        """Feed real elapsed seconds; return how many sim steps to run now.

        Returns a plain int so callers can use ``range()``. The returned
        count is at most ``max_steps``.
        """
        if real_dt is None or real_dt <= 0:
            # A zero/negative frame (possible right after a stall) must not
            # drain the accumulator, or a paused game would fast-forward.
            return 0
        self._accumulator += float(real_dt)
        count = int(self._accumulator / self.dt)
        if count <= 0:
            return 0
        if count > self.max_steps:
            # Too far behind to catch up. Drop the surplus and say so.
            self.dropped_steps += count - self.max_steps
            count = self.max_steps
            self._accumulator = 0.0
        else:
            self._accumulator -= count * self.dt
        self.sim_time += count * self.dt
        return count

    def alpha(self):
        """Interpolation factor in [0, 1) between the last two sim states.

        The renderer can lerp by this to hide the fixed step. 0 means "the
        simulation is exactly at a tick boundary", which is the common case
        when the display is slower than or equal to the sim rate.
        """
        return min(1.0, max(0.0, self._accumulator / self.dt))


# ── Process-wide clock + switch ──
# One instance, mirroring how STATE works elsewhere in this codebase. The
# main loop consults is_enabled() to decide whether to step the sim or fall
# back to the legacy variable-dt path.
_CLOCK = FixedStepClock()


def is_enabled():
    """True when the main loop should run the fixed-timestep path."""
    return _CLOCK.enabled


def set_enabled(on):
    """Turn fixed stepping on/off. Returns the previous value.

    Disabling resets the accumulator, so switching mid-frame cannot leave a
    partial step behind to be consumed by the other path.
    """
    prev = _CLOCK.enabled
    _CLOCK.enabled = bool(on)
    if not _CLOCK.enabled:
        _CLOCK.reset()
    return prev


def clock():
    """The shared FixedStepClock."""
    return _CLOCK

# inviting a death spiral.
DEFAULT_MAX_STEPS = 5



# ── Snapshot interpolation buffer (client side) ─────────────────────────
# The host sends the world 20 times a second. The client draws 60 times a
# second. Those do not line up, so drawing the newest snapshot verbatim
# makes remote players visibly stutter -- they teleport a few pixels, freeze,
# then teleport again.
#
# The standard fix is to render the world *slightly in the past* and
# interpolate between the two snapshots straddling the render time. Being
# behind by a fixed delay costs nothing visually and buys smooth motion even
# when a packet runs late.
#
# This class is pure maths over immutable tuples: no pygame, no game state,
# no sockets. That is deliberate -- it is the part of netcode most likely to
# produce subtle bugs, and keeping it free of side effects means it can be
# tested exhaustably in milliseconds.

# How far behind real time to render, in seconds. 100 ms is the usual
# recommendation: comfortably more than a typical LAN or broadband round
# trip, so there is almost always a pair of snapshots to interpolate
# between. Too small and interpolation silently degrades to "snap to the
# newest" on any real network.
DEFAULT_INTERP_DELAY = 0.100

# Snapshots older than this are dropped. Without a bound, a client that
# pauses (alt-tab, a breakpoint) would resume with a huge buffer and spend
# seconds interpolating through stale history.
MAX_BUFFERED = 32


def lerp(a, b, t):
    """Linear interpolation. t is clamped to 0..1 so callers cannot
    accidentally extrapolate by passing something outside the range."""
    if t < 0.0:
        t = 0.0
    elif t > 1.0:
        t = 1.0
    return a + (b - a) * t


def lerp_angle(a, b, t):
    """Interpolate degrees the short way round.

    Naive lerp between 350 and 10 sweeps backwards through 180 degrees, so a
    player turning across the 0/360 seam spins almost a full turn. Wrapping
    the difference into -180..180 fixes it.
    """
    d = (b - a) % 360.0
    if d > 180.0:
        d -= 360.0
    return (a + d * t) % 360.0


class SnapshotBuffer(object):
    """Ordered store of snapshots with interpolated sampling.

    Feed it snapshots as they arrive (``push``) and ask it what the world
    looked like at a given moment (``sample``). Time here is the host's tick
    count, not wall clock, so both sides agree without clock sync.
    """

    def __init__(self, tick_rate=60, interp_delay=DEFAULT_INTERP_DELAY):
        if tick_rate <= 0:
            raise ValueError("tick_rate must be positive")
        self.tick_rate = float(tick_rate)
        self.interp_delay = float(interp_delay)
        self._snaps = []          # [(tick, entities), ...] oldest first

    def clear(self):
        self._snaps = []

    def __len__(self):
        return len(self._snaps)

    def push(self, tick, entities):
        """Add a snapshot. Out-of-order and duplicate ticks are ignored.

        ``tick`` MUST be the simulation tick -- 0, 3, 6, 9 ... for a host
        sending every 3rd tick of a 60 Hz sim -- and NOT the packet count
        (0, 1, 2, 3). Both ends have to agree that "a tick" is one 1/60 s
        step of simulated time. Number packets instead and the buffer
        believes the world advanced one tick per packet, so a 3 px move is
        spread across a 1-tick span and lands as a single 3 px jump on one
        frame: the remote player teleports instead of gliding. Measured for
        identical entity motion -- max frame step 1.00 px with sim-tick
        numbering versus 3.00 px with packet-count numbering.

        Packets do arrive out of order on a real network. Accepting a stale
        one would make the world visibly jump backwards, so anything not
        strictly newer than what we already hold is dropped.
        """
        tick = int(tick)
        if self._snaps and tick <= self._snaps[-1][0]:
            return False
        self._snaps.append((tick, list(entities)))
        if len(self._snaps) > MAX_BUFFERED:
            del self._snaps[0:len(self._snaps) - MAX_BUFFERED]
        return True

    def latest_tick(self):
        return self._snaps[-1][0] if self._snaps else None

    def render_tick(self, now_tick):
        """The tick we should be drawing: real time minus the delay."""
        return now_tick - self.interp_delay * self.tick_rate

    def sample(self, now_tick):
        """Interpolated world at ``now_tick``. Returns {id: entity-tuple}.

        Returns None when there is not enough history yet (nothing buffered,
        or a single snapshot and we are asked to interpolate). Callers
        should hold the previous frame's result in that case rather than
        drawing nothing.
        """
        if not self._snaps:
            return None
        target = self.render_tick(now_tick)
        first_tick, first_ents = self._snaps[0]
        last_tick, last_ents = self._snaps[-1]

        # Before the oldest snapshot we hold, or past the newest: there is
        # nothing to interpolate towards, so show what we have. Extrapolating
        # past the newest snapshot would invent motion the host never
        # simulated, which in an authoritative shooter is a lie.
        if target <= first_tick:
            return self._index(first_ents)
        if target >= last_tick:
            return self._index(last_ents)
        if len(self._snaps) == 1:
            return None

        # Find the bracketing pair.
        older = newer = None
        for i in range(len(self._snaps) - 1):
            t0 = self._snaps[i][0]
            t1 = self._snaps[i + 1][0]
            if t0 <= target <= t1:
                older, newer = self._snaps[i], self._snaps[i + 1]
                break
        if older is None or newer is None:
            return self._index(last_ents)

        span = newer[0] - older[0]
        t = 0.0 if span <= 0 else (target - older[0]) / float(span)
        return self._blend(older[1], newer[1], t)

    @staticmethod
    def _index(entities):
        return dict((e[0], e) for e in entities
                    if isinstance(e, (list, tuple)) and e)

    @staticmethod
    def _blend(a_ents, b_ents, t):
        """Interpolate two entity lists into one.

        An entity present in only one snapshot is carried through untouched
        rather than faded. A player who just spawned or died should pop in or
        out; fading them would leave a ghost drifting across the map.
        """
        b_map = dict((e[0], e) for e in b_ents
                     if isinstance(e, (list, tuple)) and e)
        out = {}
        for ea in a_ents:
            if not (isinstance(ea, (list, tuple)) and len(ea) >= 9):
                continue
            eb = b_map.get(ea[0])
            if eb is None or len(eb) < 9:
                out[ea[0]] = tuple(ea)
                continue
            out[ea[0]] = (
                ea[0],
                eb[1],
                lerp(ea[2], eb[2], t),
                lerp(ea[3], eb[3], t),
                lerp_angle(ea[4], eb[4], t),
                # hp is an int on the wire, so round rather than hand the
                # caller a fractional hit point.
                int(round(lerp(ea[5], eb[5], t))),
                eb[6],
                eb[7],
                eb[8],
            )
        # Entities that only exist in the newer snapshot (just spawned).
        a_ids = set(e[0] for e in a_ents if isinstance(e, (list, tuple)) and e)
        for eid, eb in b_map.items():
            if eid not in a_ids:
                out[eid] = tuple(eb)
        return out


# ── Host-side snapshot producer ─────────────────────────────────────────
# Turns the live game objects into wire entities. This is the only place
# that knows what a Player or Enemy looks like, so the wire format and the
# game can drift apart without everything else noticing.
#
# The interesting decision is what NOT to send. An Enemy carries 37
# attributes; a snapshot carries 9, of which only 6 matter for drawing a
# remote copy (x, y, angle, hp, kind, plus an id). AI internals -- path
# waypoints, search timers, stuck detection -- are the host's business
# alone, and shipping them would leak the host's AI and cost bandwidth for
# no client benefit.


def _player_state(p, firing=False):
    """Derive the animation state a remote client needs to draw this player."""
    from net import protocol as P
    if getattr(p, "hp", 100) <= 0:
        return P.PS_DEAD
    if getattr(p, "is_reloading", False):
        return P.PS_RELOADING
    if getattr(p, "melee_active", False):
        return P.PS_MELEE
    if firing or getattr(p, "weapon_raised", False):
        return P.PS_SHOOTING
    if getattr(p, "was_moving", False):
        return P.PS_MOVING
    return P.PS_IDLE


def _weapon_code(name):
    from net import protocol as P
    return P.WPN_BY_NAME.get(name, P.WPN_PISTOL)


def snapshot_from_state(player, enemies=(), tick=0, remote_players=(),
                        firing_player_ids=()):
    """Build a snapshot from live game objects.

    ``remote_players`` is an iterable of (id, nickname, player-like) for
    locally-simulated stand-ins of other humans. They are sent as
    ENT_REMOTE so a client can tell a person from an NPC.
    """
    from net import protocol as P
    ents = []
    firing = set(firing_player_ids or ())

    if player is not None:
        flags = 0
        if getattr(player, "invincible_timer", 0) > 0:
            flags |= P.F_INVULNERABLE
        st = _player_state(player, firing=0 in firing)
        if st == P.PS_RELOADING:
            flags |= P.F_RELOADING
        if st == P.PS_SHOOTING:
            flags |= P.F_FIRING
        ents.append(P.make_entity(
            0, P.ENT_PLAYER,
            player.rect.centerx, player.rect.centery,
            getattr(player, "angle", 0.0),
            getattr(player, "hp", 100),
            st, _weapon_code(getattr(player, "weapon", None)),
            flags))

    for eid, _nick, rp in remote_players:
        flags = 0
        if getattr(rp, "invincible_timer", 0) > 0:
            flags |= P.F_INVULNERABLE
        st = _player_state(rp, firing=eid in firing)
        ents.append(P.make_entity(
            eid, P.ENT_REMOTE,
            rp.rect.centerx, rp.rect.centery,
            getattr(rp, "angle", 0.0),
            getattr(rp, "hp", 100),
            st, _weapon_code(getattr(rp, "weapon", None)),
            flags))

    # Enemies are numbered from 100 so their ids can never collide with a
    # player slot (0..99), which would make the client's entity map
    # ambiguous.
    for i, en in enumerate(enemies or ()):
        ents.append(P.make_entity(
            100 + i, P.ENT_ENEMY,
            en.rect.centerx, en.rect.centery,
            getattr(en, "angle", 0.0),
            getattr(en, "hp", 0)))

    return P.make_snapshot(tick, ents)
