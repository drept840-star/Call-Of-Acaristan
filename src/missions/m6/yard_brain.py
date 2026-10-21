"""Mission 6 yard - the Guard brains (engine.ai on the "Who fired?" fight).

One behaviour tree runs every Guard; his state lives on his dict (``bb`` the
tree's blackboard, ``mem`` what he knows about Biribel).  Each tick, before
the tree, he perceives: sight (a cone with a reaction delay, blocked by the
yard's boxes), noise (the K9 is suppressed but not silent; squadmates' shots
carry across the yard), radio (the squad shares sightings a second late, an
officer's at once) and being shot.  Then the tree picks what he does:

    enter        walk the scripted route to his post (rushers shoot on the way)
    fight        he has contact:
      push         rushers and heavies close in and fire on the move
      cover        the rest take a cover spot that hides them from Biribel,
                   crouch or stand behind it, then peek, telegraph and fire a
                   burst when the squad's fire token allows; under fire they
                   stay down longer; a spot that stops hiding them is left;
                   badly hurt, a Guard falls back once to cover further away
      exposed      no cover that works: stand and shoot, or close in
    investigate  a lead (a noise, a report, where he lost him): go and look
    hold         at his post, scanning

Deterministic: no random numbers, the variation comes from the Guard's slot.
The scene is reached as ``ctx.world`` (its ``brain``), never imported here.
"""
from __future__ import annotations

import math

from engine.ai import cover as C
from engine.ai.bt import (
    FAILURE, RUNNING, SUCCESS, Action, If, Selector, Tree,
)
from engine.ai.senses import NoiseBus, Sight, drop_lead, give_lead, new_memory, on_hit
from engine.ai.squad import Squad
from engine.collision import BoxWorld, GridNav

from . import train3d as T

_w = T._w

SIGHT = Sight(fov=140.0, range=45.0, near=3.0, react=(0.12, 0.9), forget=4.0)
SHOOTERS = 3                   # Guards firing at once
RADIO = 1.0                    # seconds before a sighting reaches the squad
NOISE_SHOT = 16.0              # the K9, suppressed
NOISE_GUARD_SHOT = 30.0
NOISE_SPRINT = 7.0
NOISE_WALK = 2.5
STEP_GAP = 0.3                 # footfalls, s
WALK_SPEED = {"heavy": 1.3}    # investigating; everyone else 1.7
PUSH_STOP = {"rusher": 6.5, "heavy": 13.0}
FALL_BACK_HP = 0.35
SUPPRESS_R = 1.5               # a shot passing this close keeps his head down
EYE = {"hide_low": 0.90, "hide_high": 1.50}
GUN_H = 1.38

_NAV = {}                      # yard3d module id -> (nav, boxes, spots)


def _geometry(Y):
    key = id(Y)
    if key not in _NAV:
        boxes = BoxWorld(Y.BLOCKERS)
        nav = GridNav(Y.BOUNDS, 0.5,
                      lambda x, z: not Y._blocked(x, z, Y.ground_y(x, z),
                                                  r=Y.BODY_R + 0.15),
                      height=Y.ground_y, step=Y.STEP_UP)
        spots = C.build_spots(boxes, nav.is_walkable, nav.floor)
        _NAV[key] = (nav, boxes, spots)
    return _NAV[key]


_SGN = 1.0 if _w.yaw_to((0, 0, 0), (1, 0, 0)) > 0 else -1.0


def _dir(yaw):
    """Unit XZ facing of an actor at ``yaw`` (the rig's convention, not the
    camera's ``T._forward``)."""
    a = math.radians(_SGN * yaw)
    return math.sin(a), math.cos(a)


def _d2(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _raise(p):
    return (p[0], p[1] + 1.2, p[2])      # sounds start at the waist, not the floor


def _feet(p):
    return (p[0], p[1] - 1.25, p[2])     # a chest point back to the ground


# ── per-tick helpers (the scene's brain is ctx.world) ──────────────────────
def _prof(g):
    return T._guard_profile(g["kind"])


def _threat(g):
    """Where he believes Biribel's chest is."""
    return g["mem"]["last_pos"]


def _look(g, p):
    g["look"] = (p[0], p[1], p[2])


def _go(br, g, goal, speed, dt, stop=0.12):
    """One tick along a nav path to ``goal``; True on arrival, None when no
    route exists."""
    bb = g["bb"]
    if _d2(g["pos"], goal) <= stop:
        bb["path"] = []
        g["moving"] = False
        return True
    if bb.get("goal") is None or _d2(bb["goal"], goal) > 0.75 or not bb.get("path"):
        bb["goal"] = tuple(goal)
        bb["path"] = list(br.nav.path(g["pos"], goal))
        if not bb["path"]:
            g["moving"] = False
            return None
    if br.sc.t - g["hit_t"] < 0.25:
        speed *= 0.5                      # the hit staggers him
    path = bb["path"]
    x, y, z = g["pos"]
    step = speed * dt
    while path and step > 0.0:
        tx, _ty, tz = path[0]
        dx, dz = tx - x, tz - z
        d = math.hypot(dx, dz)
        if d <= step:
            x, z = tx, tz
            step -= d
            path.pop(0)
        else:
            x, z = x + dx / d * step, z + dz / d * step
            step = 0.0
    g["pos"] = (x, br.nav.floor(x, z), z)
    g["moving"] = True
    g["heading"] = path[0] if path else goal
    if _d2(g["pos"], goal) <= stop or not path:
        bb["path"] = []
        return True
    return False


def _burst(br, g, eye, sees, hold_token=True):
    """The old cadence: telegraph, then a burst while he sees; the squad's
    fire token gates the start of each burst."""
    sc, prof, t = br.sc, _prof(g), br.sc.t
    if g["burst_left"] <= 0:
        if not sees or t < g["next_burst"]:
            return False
        hold = float(prof.get("telegraph", 0.3)) + prof["burst"] * prof.get("gap", 0.1) + 0.3
        if hold_token and not br.squad.fire_token(t, g["slot"], hold):
            return False
        g["burst_left"] = int(prof["burst"])
        g["burst_next"] = t + float(prof.get("telegraph", 0.3))
        return True
    if not sees:
        g["burst_left"] = 0                # lost the line: abort the burst
        g["next_burst"] = t + 0.4
        return False
    if t >= g["burst_next"]:
        sc._guard_shot(g, prof, eye, sc._player_chest())
        br.noise.emit(t, _raise(g["pos"]), NOISE_GUARD_SHOT, "gunfire")
    return True


# ── the tree's leaves ──────────────────────────────────────────────────────
def _entering(ctx):
    return ctx.agent["wp"] < len(ctx.agent["route"])


def _enter(ctx):
    br, g, t, dt = ctx.world, ctx.agent, ctx.t, ctx.dt
    g["stance"] = "run"
    if t < g["react"]:
        g["moving"] = False
        g["stance"] = "post"
        return RUNNING
    tx, ty, tz = g["route"][g["wp"]]
    x, y, z = g["pos"]
    dx, dz = tx - x, tz - z
    dist = math.hypot(dx, dz)
    speed = br.Y.ENTRY_SPEED.get(g["kind"], 2.8)
    if dist > 0.08:
        k = min(dist, speed * dt) / dist
        g["pos"] = (x + dx * k, y + (ty - y) * k, z + dz * k)
        g["moving"] = True
        g["heading"] = (tx, ty, tz)
    else:
        g["pos"] = (tx, ty, tz)
        g["wp"] += 1
    if g["kind"] == "rusher" and g["mem"]["sees"]:
        _look(g, br.sc._player_chest())
        _burst(br, g, br.eye(g), True)
    if g["wp"] >= len(g["route"]):
        g["posted"] = True
        g["moving"] = False
        g["stance"] = "post"
        return SUCCESS
    return RUNNING


def _contact(ctx):
    return ctx.agent["mem"]["contact"] and ctx.agent["mem"]["last_pos"] is not None


def _pusher(ctx):
    return ctx.agent["kind"] in PUSH_STOP


def _push(ctx):
    """Rushers and heavies: close to their range, firing on the move."""
    br, g, dt = ctx.world, ctx.agent, ctx.dt
    threat = _threat(g)
    sees = g["mem"]["sees"]
    _look(g, threat)
    far = _d2(g["pos"], threat) > PUSH_STOP[g["kind"]]
    if far or not sees:
        speed = br.Y.ENTRY_SPEED.get(g["kind"], 2.8) * (1.0 if far else 0.6)
        if _go(br, g, _feet(threat), speed, dt, stop=1.5) is None:
            g["moving"] = False
        g["stance"] = "run" if g["moving"] else "aim"
    else:
        g["moving"] = False
        g["stance"] = "aim"
    _burst(br, g, br.eye(g), sees)
    return RUNNING


def _cover_ok(ctx):
    """He is at a spot that still hides him (half a second of grace when it
    stops: a strafe across the line should not uproot him)."""
    br, g, t = ctx.world, ctx.agent, ctx.t
    s = g["cover"]
    if s is None or _d2(g["pos"], s.pos) > 0.3 and g["bb"].get("cphase") != "peek":
        return False
    if br.wants_fall_back(g):
        return False
    if C.hides(s, _threat(g), br.boxes):
        g["bb"]["exposed_t"] = None
        return True
    since = g["bb"].get("exposed_t")
    if since is None:
        g["bb"]["exposed_t"] = t
        return True
    return t - since < 0.55


def _take_cover(ctx):
    """Pick a spot (or keep the one he is heading for) and run to it."""
    br, g, dt = ctx.world, ctx.agent, ctx.dt
    s = g["cover"]
    threat = _threat(g)
    retreat = br.wants_fall_back(g) and not g["bb"].get("retreating")
    if ctx.fresh or s is None or retreat or not C.hides(s, threat, br.boxes):
        s = br.pick_cover(g)
        if s is None:
            return FAILURE
    g["bb"]["exposed_t"] = None
    _look(g, threat)
    got = _go(br, g, s.pos, br.Y.ENTRY_SPEED.get(g["kind"], 2.8), dt)
    if got is None:
        br.drop_cover(g)
        g["bb"].setdefault("bad_spots", set()).add(s.id)
        return FAILURE
    g["stance"] = "run"
    if got:
        g["pos"] = s.pos
        g["moving"] = False
        if g["bb"].get("retreating"):
            g["bb"]["retreating"] = False
            g["fell_back"] = True
        return SUCCESS
    return RUNNING


def _hide_secs(g, n):
    return 1.0 + 0.4 * ((g["slot"] * 3 + n) % 4)


def _cover_cycle(ctx):
    """Hide, peek, fire a burst, hide again."""
    br, g, t, dt = ctx.world, ctx.agent, ctx.t, ctx.dt
    bb, s = g["bb"], g["cover"]
    threat = _threat(g)
    _look(g, threat)
    if ctx.fresh or "cphase" not in bb:
        bb["cphase"], bb["cuntil"], bb["cn"] = "hide", t + 0.4 + 0.15 * (g["slot"] % 4), 0
        bb["cstart"] = t
    if bb["cphase"] == "hide":
        back = _go(br, g, s.pos, 2.4, dt, stop=0.05) is not False
        g["stance"] = ("hide_low" if s.low else "hide_high") if back else "walk"
        if t - g.get("suppressed_t", -9.0) < 0.6:
            bb["cuntil"] = max(bb["cuntil"], min(t + 0.6, bb["cstart"] + 4.5))
        if t < bb["cuntil"]:
            return RUNNING
        hold = 0.8 + _prof(g)["burst"] * _prof(g).get("gap", 0.1)
        if not br.squad.fire_token(t, g["slot"], hold + float(_prof(g).get("telegraph", 0.3))):
            bb["cuntil"] = t + 0.3                 # the others are shooting
            return RUNNING
        bb["cphase"], bb["cuntil"] = "peek", t + 0.9
        bb["fired"] = False
        g["next_burst"] = min(g["next_burst"], t)
    if bb["cphase"] == "peek":
        out = C.peek_point(s)
        there = _go(br, g, out, 2.6, dt, stop=0.05) is not False
        g["stance"] = "aim"
        if not there:
            g["stance"] = "walk"
            bb["cuntil"] = t + 0.9
            return RUNNING
        sees = g["mem"]["sees"]
        if g["burst_left"] > 0 or (sees and not bb["fired"]):
            bb["fired"] = _burst(br, g, br.eye(g), sees, hold_token=False) or bb["fired"]
            if g["burst_left"] > 0:
                bb["cuntil"] = t + 0.25
        if bb["fired"] and g["burst_left"] <= 0 or t >= bb["cuntil"]:
            bb["cn"] += 1
            bb["cphase"], bb["cstart"] = "hide", t
            bb["cuntil"] = t + _hide_secs(g, bb["cn"])
            br.squad.release(g["slot"])
    return RUNNING


def _cycle_halt(ctx):
    for k in ("cphase", "cuntil", "cstart", "fired"):
        ctx.agent["bb"].pop(k, None)
    ctx.agent["burst_left"] = 0
    ctx.world.squad.release(ctx.agent["slot"])


def _exposed(ctx):
    """No cover that works: shoot where he stands, or close in until he sees."""
    br, g, dt = ctx.world, ctx.agent, ctx.dt
    threat = _threat(g)
    _look(g, threat)
    sees = g["mem"]["sees"]
    if sees:
        g["moving"] = False
        g["stance"] = "aim"
        _burst(br, g, br.eye(g), True)
    else:
        _go(br, g, _feet(threat), WALK_SPEED.get(g["kind"], 1.7) * 1.4, dt, stop=6.0)
        g["stance"] = "walk" if g["moving"] else "aim"
    return RUNNING


def _has_lead(ctx):
    return ctx.agent["mem"]["lead"] is not None


def _investigate(ctx):
    br, g, t, dt = ctx.world, ctx.agent, ctx.t, ctx.dt
    mem, bb = g["mem"], g["bb"]
    lead = mem["lead"]
    if ctx.fresh or bb.get("lead_at") != mem["lead_t"]:
        bb["lead_at"] = mem["lead_t"]
        bb["scan_until"] = None
        bb["inv_until"] = t + 25.0
    if bb["scan_until"] is None:
        _look(g, (lead[0], g["pos"][1] + 1.4, lead[2]))
        got = _go(br, g, lead, WALK_SPEED.get(g["kind"], 1.7), dt, stop=2.0)
        g["stance"] = "walk"
        if got or got is None or t > bb["inv_until"]:
            bb["scan_until"] = t + 3.0
            bb["scan_yaw"] = g["yaw"]
            g["moving"] = False
        return RUNNING
    g["stance"] = "post"
    fx, fz = _dir(bb["scan_yaw"] + 50.0 * math.sin((bb["scan_until"] - t) * 1.6))
    x, y, z = g["pos"]
    _look(g, (x + fx * 5.0, y + 1.4, z + fz * 5.0))
    if t < bb["scan_until"]:
        return RUNNING
    drop_lead(mem)
    bb["watch"] = bb["scan_yaw"]
    return SUCCESS


def _hold(ctx):
    g, t = ctx.agent, ctx.t
    g["moving"] = False
    g["stance"] = "post"
    watch = g["bb"].get("watch", g["yaw"])
    fx, fz = _dir(watch + 35.0 * math.sin(t * 0.55 + g["slot"] * 1.7))
    x, y, z = g["pos"]
    _look(g, (x + fx * 5.0, y + 1.4, z + fz * 5.0))
    return RUNNING


TREE = Tree(Selector(
    If(_entering, Action(_enter), name="enter"),
    If(_contact, Selector(
        If(_pusher, Action(_push), name="push"),
        Selector(
            If(_cover_ok, Action(_cover_cycle, halt=_cycle_halt, name="cycle")),
            Action(_take_cover, name="move"),
            name="cover"),
        Action(_exposed, name="exposed"),
    ), name="fight"),
    If(_has_lead, Action(_investigate), name="investigate"),
    Action(_hold, name="hold"),
))


class Brain:
    """The yard's shared AI state: geometry, the squad, the noise bus."""

    def __init__(self, sc, Y):
        self.sc, self.Y = sc, Y
        self.nav, self.boxes, self.spots = _geometry(Y)
        self.squad = Squad(shooters=SHOOTERS, radio=RADIO)
        self.noise = NoiseBus(keep=1.5, muffle=0.5)
        self.next_step = 0.0
        self.shots_heard = 0

    # ── guards in and out ──────────────────────────────────────────────
    def adopt(self, g):
        """A Guard enters the fight."""
        g.update(bb={}, mem=new_memory(), look=None, stance="post", cover=None,
                 suppressed_t=-9.0, hp_max=g["hp"], fell_back=False, heading=None)
        last = g["route"][-1] if g["route"] else g["pos"]
        if g["wave"] == 0:
            watch = _w.yaw_to(last, self.Y.START_POS)      # torching the body
        elif len(g["route"]) >= 2:
            watch = _w.yaw_to(g["route"][-2], last)
        else:
            watch = _w.yaw_to(g["pos"], last)
        g["bb"]["watch"] = watch
        g["yaw"] = watch
        if g["wave"] and g["route"]:
            g["yaw"] = _w.yaw_to(g["pos"], g["route"][0])      # off the tailgate
        heard = self.squad.intel(self.sc.t, None)
        if heard is not None:                              # sent in after him
            give_lead(g["mem"], self.sc.t, _feet(heard[0]), "radio")

    def drop_cover(self, g):
        g["cover"] = None
        self.squad.unclaim(g["slot"])

    def wants_fall_back(self, g):
        return (not g["fell_back"] and g["kind"] not in PUSH_STOP
                and g["hp"] < g["hp_max"] * FALL_BACK_HP)

    def pick_cover(self, g):
        threat = _threat(g)
        retreat = self.wants_fall_back(g)
        td = _d2(g["pos"], threat)
        if retreat:
            band, ideal, travel = (max(10.0, td + 4.0), 40.0), td + 9.0, 22.0
        else:
            # hold about the range he is at: no running off, no charging in
            ideal = min(18.0, max(8.0, td)) + (2.0 if g["kind"] == "officer" else 0.0)
            band, travel = (5.0, 32.0), 14.0
        bad = g["bb"].get("bad_spots", ())
        mates = [m["cover"].pos if m.get("cover") is not None else m["pos"]
                 for m in self.sc.guards if m is not g and m["alive"]]

        def taken(s):
            return s.id in bad or self.squad.claimed(s.id, g["slot"])

        def reachable(s):
            if not s.low and not self.nav.walk_clear(s.pos, C.peek_point(s)):
                return False
            return bool(self.nav.path(g["pos"], s.pos)) or _d2(g["pos"], s.pos) < 0.5

        s = C.pick(self.spots, g["pos"], threat, self.boxes, band=band, ideal=ideal,
                   max_travel=travel, taken=taken, mates=mates, reachable=reachable)
        if s is None and retreat:
            g["fell_back"] = True                 # nowhere to go: fight it out
            return self.pick_cover(g)
        if s is not None:
            self.squad.claim(s.id, g["slot"])
            g["bb"]["retreating"] = retreat
        else:
            self.squad.unclaim(g["slot"])
        g["cover"] = s
        return s

    # ── perception ─────────────────────────────────────────────────────
    def eye(self, g):
        x, y, z = g["pos"]
        return (x, y + EYE.get(g["stance"], GUN_H), z)

    def spheres(self, g):
        """(height, radius) of the chest and head hit spheres for his stance."""
        big = g["kind"] == "heavy"
        if g.get("stance") == "hide_low":
            return ((0.66, 0.38 if big else 0.34), (0.92, 0.28 if big else 0.24))
        return ((1.30, 0.42 if big else 0.38), (1.58, 0.34 if big else 0.30))

    def _perceive(self, g, dt):
        sc, t, mem = self.sc, self.sc.t, g["mem"]
        chest = sc._player_chest()
        eye = self.eye(g)
        dist = math.dist(eye, chest)
        visible = (SIGHT.in_view(eye, _dir(g["yaw"]), chest)
                   and not self.boxes.segment_blocked(eye, chest))
        boost = 2.0 if self.squad.intel(t, g["slot"]) is not None else 1.0
        if sc.sprint:
            boost *= 1.5
        if g["hit_t"] > g["bb"].get("hit_seen", -9.0):
            g["bb"]["hit_seen"] = g["hit_t"]
            on_hit(mem, t, chest)
        SIGHT.update(mem, t, dt, visible, chest, dist, boost)
        if mem["sees"]:
            g["last_seen"] = t
            drop_lead(mem)
            self.squad.report(t, chest, by=g["slot"], instant=g["kind"] == "officer")
        heard = self.squad.intel(t, g["slot"])
        if heard is not None:
            pos, at = heard
            if mem["contact"]:
                if at > mem["seen_t"] and not mem["sees"]:
                    mem["seen_t"], mem["last_pos"] = at, pos     # the radio keeps him in it
            elif at > mem["lead_t"]:
                give_lead(mem, at, _feet(pos), "radio")
        if not mem["contact"]:
            ev = self.noise.listen(mem, t, eye, self.boxes.segment_blocked)
            if ev is not None and ev[0] > mem["lead_t"]:
                give_lead(mem, ev[0], ev[1], ev[3])
                mem["aware"] = max(mem["aware"], 0.35)

    # ── the tick ───────────────────────────────────────────────────────
    def update(self, dt):
        sc, t = self.sc, self.sc.t
        sp = math.hypot(*sc.vel)
        if sp > 0.5 and t >= self.next_step:
            self.next_step = t + STEP_GAP
            self.noise.emit(t, _raise(sc.pos), NOISE_SPRINT if sc.sprint else NOISE_WALK,
                            "steps")
        if sc.shots != self.shots_heard:
            self.shots_heard = sc.shots
            self.noise.emit(t, _raise(sc.pos), NOISE_SHOT, "shot")
        self.noise.prune(t)
        for g in sc.guards:
            if not g["alive"]:
                if "bb" in g and not g["bb"].get("gone"):
                    g["bb"]["gone"] = True
                    self.squad.forget(g["slot"])
                    g["cover"] = None
                continue
            if "bb" not in g:
                self.adopt(g)
            if t < g["react"] - (0.0 if g["wave"] else 1.0):
                continue
            g["moving"] = False
            if t >= g["react"]:
                self._perceive(g, dt)
            TREE.tick(g, g["bb"], t, dt, self)
            self._face(g, dt)
        self._separate()

    def _face(self, g, dt):
        x, _y, z = g["pos"]
        if g["moving"] and g.get("heading") is not None and g["stance"] in ("run", "walk"):
            tgt = g["heading"]
        elif g["look"] is not None:
            tgt = g["look"]
        else:
            return
        if abs(tgt[0] - x) + abs(tgt[2] - z) < 1e-3:
            return
        g["yaw"] = _w.yaw_mix(g["yaw"], _w.yaw_to((x, 0, z), (tgt[0], 0, tgt[2])),
                              min(1.0, dt * 12.0))

    def _separate(self):
        """Two Guards never stand in one another."""
        live = [g for g in self.sc.guards if g["alive"] and g.get("posted")]
        for i, a in enumerate(live):
            for b in live[i + 1:]:
                dx, dz = b["pos"][0] - a["pos"][0], b["pos"][2] - a["pos"][2]
                d = math.hypot(dx, dz)
                if d >= 0.7 or d < 1e-6:
                    continue
                push = (0.7 - d) * 0.5
                for g, sgn in ((a, -1.0), (b, 1.0)):
                    x, y, z = g["pos"]
                    nx, nz = x + sgn * dx / d * push, z + sgn * dz / d * push
                    if self.nav.is_walkable(nx, nz):
                        g["pos"] = (nx, self.nav.floor(nx, nz), nz)

    def suppress(self, o, end):
        """A shot from ``o`` to ``end`` cracks past every Guard near its line."""
        t = self.sc.t
        ax, ay, az = o
        bx, by, bz = end[0] - ax, end[1] - ay, end[2] - az
        ll = bx * bx + by * by + bz * bz
        if ll < 1e-9:
            return
        for g in self.sc.guards:
            if not g["alive"]:
                continue
            h = self.spheres(g)[0][0]
            px, py, pz = g["pos"][0] - ax, g["pos"][1] + h - ay, g["pos"][2] - az
            k = max(0.0, min(1.0, (px * bx + py * by + pz * bz) / ll))
            ex, ey, ez = px - bx * k, py - by * k, pz - bz * k
            if ex * ex + ey * ey + ez * ez < SUPPRESS_R * SUPPRESS_R:
                g["suppressed_t"] = t
