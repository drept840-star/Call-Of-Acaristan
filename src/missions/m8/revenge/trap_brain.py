"""Mission 8 Revenge - trap AI: the Guard riflemen, the Guard truck and Bodi.

A trimmed copy of ``missions.m7.raid_brain`` (no dogs, no Alex, no fire): the
same dict-per-rifleman state machine, burst telegraph and ally raise, so the
two fights read alike.  Bodi carries his hunting rifle: slow, hard, accurate.
Guards firing at someone tucked behind a jersey barrier mostly hit concrete.
Bodi fights from cover: he picks a spot by the concrete or a wreck that hides
him from the live Guards, keeps near Biribel without getting ahead of him,
walks there on a 1 m grid path, ducks between shots and rises to fire, takes
the Guard about to shoot Biribel first, and calls flanks.
The scene (``trap3d``) owns the player and hands itself in as ``s``.
"""
import heapq
import math
import random

from missions.m7 import raid_brain as RB

from . import trap_world as W

KINDS = {"rifle": dict(RB.KINDS["rifle"])}
ROUND_GAP, TELEGRAPH, FLINCH_S = RB.ROUND_GAP, RB.TELEGRAPH, RB.FLINCH_S
ALLY_RAISE, ALLY_HOLD = RB.ALLY_RAISE, RB.ALLY_HOLD
BODI_HP, BODI_DOWN_S = RB.BODI_HP, RB.BODI_DOWN_S
BODI_DMG, BODI_ACC, BODI_GAP = 30, 0.85, 1.6       # bolt hunting rifle
TRUCK_SPEED = 11.0
TRUCK_X, TRUCK_START_Z, TRUCK_STOP_Z = -29.6, 112.0, 38.0   # down the Guard track from the north

# Bodi's post for each wave; the gantry foot once the road is clear.
BODI_POSTS = {1: (-63.0, -3.5), 2: (-50.0, 6.5), 3: (-34.0, 26.0)}
BODI_FOOT = (11.0, 54.0)

# kind, x, z, route, delay (s): out from behind the burned cars in the lot
WRECKS = [
    ("rifle", -40.0, 14.5, [(-43.5, 12.0), (-46.0, 6.0)], 0.0),
    ("rifle", -30.0, 26.0, [(-34.0, 23.0), (-37.0, 15.0)], 0.8),
    ("rifle", -46.0, 23.5, [(-49.5, 23.0), (-52.0, 14.0)], 1.6),
    ("rifle", -40.0, 35.0, [(-43.5, 32.0), (-46.0, 26.0)], 2.6),
    ("rifle", -42.0, 6.0, [(-42.0, -1.0), (-50.0, -4.5)], 4.0),
]
# out of the booths, the tanker and the control-building side
FLANK = [
    ("rifle", -62.0, 18.0, [(-54.0, 17.0), (-46.0, 26.5)], 0.0),
    ("rifle", -6.0, 30.0, [(-12.0, 30.0), (-18.0, 28.0)], 1.0),
    ("rifle", -40.0, 62.0, [(-36.0, 52.0), (-35.0, 44.0)], 2.0),
    ("rifle", -6.0, 54.0, [(-12.0, 48.0), (-12.0, 46.0)], 3.0),
    ("rifle", -60.0, 44.0, [(-54.0, 38.0), (-48.0, 33.0)], 4.5),
    ("rifle", 2.0, 44.0, [(-6.0, 42.0), (-11.0, 42.0)], 6.0),
]


NAV_CELL = 1.0
NAV_PAD = W.BODY_R + 0.12          # a cell is walkable when its centre clears every solid by this
COVER_REACH = 1.3                  # a cover spot sits this close to a solid of 0.5 m or more
PLAN_S = 1.1                       # Bodi re-weighs his spot this often
PLAN_SAMPLES = 18                  # cover spots scored per plan, plus where he stands
CALL_GAP = 3.5                     # seconds between two of his callouts
DUCK_RATE = 6.0                    # crouch blend per second
_NAV = {}


def _nav():
    """Walkable cells and cover spots of the static set, built once."""
    if _NAV:
        return _NAV
    x0, x1, z0, z1 = W.BOUNDS
    nx, nz = int((x1 - x0) / NAV_CELL), int((z1 - z0) / NAV_CELL)
    free = [[True] * nz for _ in range(nx)]
    near = [[False] * nz for _ in range(nx)]
    reach = max(NAV_PAD, COVER_REACH)
    for bx0, bz0, bx1, bz1, h in W.STATIC:
        i0 = max(0, int((bx0 - reach - x0) / NAV_CELL) - 1)
        i1 = min(nx, int((bx1 + reach - x0) / NAV_CELL) + 2)
        j0 = max(0, int((bz0 - reach - z0) / NAV_CELL) - 1)
        j1 = min(nz, int((bz1 + reach - z0) / NAV_CELL) + 2)
        for i in range(i0, i1):
            cx = x0 + (i + 0.5) * NAV_CELL
            for j in range(j0, j1):
                cz = z0 + (j + 0.5) * NAV_CELL
                d = math.hypot(max(bx0 - cx, 0.0, cx - bx1), max(bz0 - cz, 0.0, cz - bz1))
                if d < NAV_PAD:
                    free[i][j] = False
                elif d < COVER_REACH and h >= 0.5:
                    near[i][j] = True
    spots = [(x0 + (i + 0.5) * NAV_CELL, z0 + (j + 0.5) * NAV_CELL)
             for i in range(nx) for j in range(nz) if free[i][j] and near[i][j]]
    _NAV.update(nx=nx, nz=nz, free=free, spots=spots)
    return _NAV


_ray_sphere = RB._ray_sphere
_yaw = RB._yaw
_clamp = RB._clamp


class Brain:
    def __init__(self, scene, post=None):
        self.s = scene
        self.rng = random.Random(812)
        self.enemies = []
        self.trucks = []
        self.wave = 0
        self.slot = 0
        x, z = post or BODI_POSTS[1]
        self.bodi = dict(x=x, z=z, y=0.0, yaw=0.0, hp=BODI_HP, state="up", down_at=0.0,
                         moving=False, next=2.0, aim=-9.0, raised=-9.0, slope=0.0,
                         goal=None, gait=0.0, path=[], replan=0.0, covered=False,
                         cover_t=None, duck_k=0.0, duck_at=None, stuck=0.0, tgt=None,
                         said=-9.0, low_said=False, shot_t=0.0)
        self._dyn_boxes = []

    # --- waves -----------------------------------------------------------------

    def add(self, kind, x, z, route, delay, wave, **kw):
        k = KINDS[kind]
        self.slot += 1
        e = dict(kind=kind, x=x, z=z, y=0.0, yaw=180.0, hp=k["hp"], alive=True, live=False,
                 wave=wave, route=list(route), wp=0, spawn_at=self.s.t + delay,
                 next_burst=0.0, tele=0.0, left=0, round_at=0.0, hit_t=-9.0, dead_t=-9.0,
                 moving=False, slot=self.slot, mags=1, aim=-9.0, truck=None, gait=0.0,
                 held=0.0)
        e.update(kw)
        self.enemies.append(e)
        return e

    def start_wave(self, n):
        self.wave = n
        self.bodi["replan"] = 0.0
        if n == 1:
            for kind, x, z, route, delay in WRECKS:
                self.add(kind, x, z, route, delay, 1)
        elif n == 2:
            self.trucks.append(dict(x=TRUCK_X, z=TRUCK_START_Z, at=self.s.t + 1.0, state="wait",
                                    riflemen=4, t_stop=0.0, dumped=False, box=None))
        elif n == 3:
            for kind, x, z, route, delay in FLANK:
                self.add(kind, x, z, route, delay, 3)

    def _dismount(self, t):
        t["dumped"] = True
        zr = t["z"] + 3.6                      # out over the tailgate, north end
        lanes = ((-37.5, 24.0), (-37.0, 18.0), (-23.0, 27.0), (-22.0, 31.0))
        for i in range(t["riflemen"]):
            sx = t["x"] + (i - 1.5) * 0.9
            gx, gz = lanes[i]
            route = [(sx + (2.8 if i >= 2 else -6.5), zr - 1.0), (gx, gz + 9.0), (gx, gz)]
            self.add("rifle", sx, zr, route, 0.5 + i * 0.6, 2)

    def pending(self, wave):
        if wave == 2 and any(not t["dumped"] for t in self.trucks):
            return True
        return any(e["alive"] and e["wave"] == wave for e in self.enemies)

    def pending_count(self):
        return sum(t["riflemen"] for t in self.trucks if not t["dumped"])

    def alive_count(self):
        return sum(1 for e in self.enemies if e["alive"])

    # --- targets and damage ----------------------------------------------------

    def _cands(self):
        s = self.s
        out = []
        if not s.dying and s.py < 1.0:
            out.append(("player", s.px, s.pz, 1.0, s.pmoving, 1.2))
        b = self.bodi
        if b["state"] == "up":
            out.append(("bodi", b["x"], b["z"], 1.25, b["moving"], 1.2))
        return out

    def _pick(self, e):
        best, bd = None, 1e9
        for c in self._cands():
            d = math.hypot(c[1] - e["x"], c[2] - e["z"]) * c[3]
            if d < bd:
                best, bd = c, d
        return best

    def _damage(self, name, dmg, src):
        s = self.s
        if name == "player":
            s.hurt_player(dmg, src)
            return
        b = self.bodi
        if b["state"] != "up":
            return
        b["hp"] -= dmg
        b["replan"] = 0.0                     # hit: the spot is no good, find another
        if b["hp"] <= 0:
            b["state"] = "down"
            b["down_at"] = s.t
            b["goal"] = None
            b["path"] = []
            b["cover_t"] = None
            s.say("BIRIBEL", "Bodi!", 2.0)
        elif b["hp"] < BODI_HP * 0.4 and not b["low_said"]:
            b["low_said"] = True
            self._call("I'm hit bad. Keep them off me!", force=True)
        elif self.rng.random() < 0.35:
            self._call(self.rng.choice(("Hit - I'm fine.", "Just a graze.")))

    def hurt_enemy(self, e, dmg, src=None):
        if not e["alive"]:
            return False
        e["hp"] -= dmg
        e["hit_t"] = self.s.t
        if e["hp"] <= 0:
            e["alive"] = False
            e["dead_t"] = self.s.t
            ux, uz, front = RB._fall_from(e, src)
            e["fall_dir"] = (ux, uz)
            e["dead_pose"] = "dead_back" if front else "dead_front"
            self.s.kills += 1
            self.s._snd("enemy_down", math.hypot(e["x"] - self.s.px, e["z"] - self.s.pz))
            return True
        return False

    def spheres(self, e):
        x, y, z = e["x"], e["y"], e["z"]
        return [((x, y + 1.1, z), 0.5, False), ((x, y + 1.62, z), 0.25, True)]

    def _shoot(self, e, tgt, now):
        s = self.s
        k = KINDS[e["kind"]]
        name, tx, tz, _w, moving, ty = tgt
        d = math.hypot(tx - e["x"], tz - e["z"])
        yaw = math.radians(e["yaw"])
        muzzle = (e["x"] + math.sin(yaw) * 0.55, e["y"] + 1.35, e["z"] + math.cos(yaw) * 0.55)
        p = _clamp(k["acc"] - d * 0.012 - (0.14 if moving else 0.0), 0.12, 0.85)
        if s.world.low_cover((tx, tz), (e["x"], e["z"])):
            p *= W.LOW_COVER_K
            if name == "bodi" and self.bodi["duck_k"] > 0.5:
                p *= 0.3                       # ducked behind the concrete
        if self.rng.random() < p:
            end = (tx, ty, tz)
            self._damage(name, k["dmg"], (e["x"], e["z"]))
        else:
            r = self.rng
            end = (tx + (r.random() - 0.5) * 2.2, ty + (r.random() - 0.5) * 1.2,
                   tz + (r.random() - 0.5) * 2.2)
        s.tracer(muzzle, end)
        s.flash(muzzle)
        e["aim"] = now

    def _steer(self, e, tx, tz, speed, dt):
        dx, dz = tx - e["x"], tz - e["z"]
        d = math.hypot(dx, dz)
        if d < 1e-4:
            return False
        ux, uz = dx / d, dz / d
        step = speed * dt
        for ang in (0, 35, -35, 75, -75, 120, -120):
            c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            vx, vz = ux * c - uz * sn, ux * sn + uz * c
            nx, nz = self.s.world.move(e["x"], e["z"], vx * step, vz * step, 0.34, False)
            if math.hypot(nx - e["x"], nz - e["z"]) > step * 0.4:
                e["x"], e["z"] = nx, nz
                e["gait"] += step
                return True
        return False

    # --- per-frame -------------------------------------------------------------

    def update(self, dt):
        now = self.s.t
        for t in self.trucks:
            self._truck_update(t, dt, now)
        for e in self.enemies:
            if e["alive"]:
                self._enemy(e, dt, now)
        self._bodi_update(dt, now)
        b = self.bodi
        k = b.get("walk_k", 0.0)
        b["walk_k"] = min(1.0, k + dt * 5.0) if b["moving"] else max(0.0, k - dt * 4.0)

    def _truck_update(self, t, dt, now):
        if t["state"] == "wait":
            if now >= t["at"]:
                t["state"] = "drive"
                t["box"] = len(self.s.world.dyn)
                self.s.world.dyn.append(None)
                self._truck_box(t)
                self.s.on_truck_start(t)
            return
        if t["state"] == "drive":
            left = t["z"] - TRUCK_STOP_Z
            v = min(TRUCK_SPEED, 1.0 + left * 0.9)
            t["z"] -= max(0.0, v) * dt
            if left < 0.15:
                t["z"] = TRUCK_STOP_Z
                t["state"] = "stopped"
                t["t_stop"] = now
                self.s.on_truck_stop(t)
            self._truck_box(t)
        elif not t["dumped"] and now - t["t_stop"] > 0.8:
            self._dismount(t)

    def _truck_box(self, t):
        truck = W.guard_truck_at(t["x"], t["z"])
        self.s.world.dyn[t["box"]] = truck
        r = W.BODY_R
        front = truck.world_box()[2] - r          # the bumper is the south end
        b = self.bodi
        if truck.body_hits(b["x"], b["z"], r, 0.0, W.BODY_TOP):
            b["z"] = front
        if truck.body_hits(self.s.px, self.s.pz, r, 0.0, W.BODY_TOP):
            self.s.pz = front

    def _enemy(self, e, dt, now):
        if now < e["spawn_at"]:
            e["live"] = False
            return
        e["live"] = True
        k = KINDS[e["kind"]]
        tgt = self._pick(e)
        e["moving"] = False
        self._spread(e, dt)
        if tgt is None:
            return
        d = math.hypot(tgt[1] - e["x"], tgt[2] - e["z"])
        los = d < k["rng"] and self.s.world.los((e["x"], e["z"]), (tgt[1], tgt[2]))
        if now - e["hit_t"] < FLINCH_S:
            return
        on_route = e["wp"] < len(e["route"])
        if on_route and los and d < 20.0:
            e["wp"] = len(e["route"])
            on_route = False
        if on_route:
            wx, wz = e["route"][e["wp"]]
            if math.hypot(wx - e["x"], wz - e["z"]) < 1.0:
                e["wp"] += 1
            else:
                self._go(e, wx, wz, k["speed"] * 1.35, dt, now)
        elif los:
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            busy = e["left"] > 0 or e["tele"] > 0.0
            if not busy:
                e["held"] += dt
                if d > k["hold"] + 3.0:
                    e["moving"] = self._steer(e, tgt[1], tgt[2], k["speed"], dt)
                elif d < 7.0:
                    away = e["x"] - (tgt[1] - e["x"]), e["z"] - (tgt[2] - e["z"])
                    e["moving"] = self._steer(e, away[0], away[1], k["speed"] * 0.7, dt)
                elif e["held"] > 3.5 and e["left"] == 0:
                    side = 1.0 if e["slot"] % 2 else -1.0
                    px, pz = tgt[2] - e["z"], -(tgt[1] - e["x"])
                    n = math.hypot(px, pz) or 1.0
                    e["moving"] = self._steer(e, e["x"] + side * px / n * 4.0,
                                              e["z"] + side * pz / n * 4.0, k["speed"] * 0.8, dt)
                    if e["held"] > 5.5:
                        e["held"] = 0.0
            self._fire_ctl(e, tgt, now, k)
        else:
            e["held"] = 0.0
            self._go(e, tgt[1], tgt[2], k["speed"], dt, now)

    def _spread(self, e, dt):
        """Push a Guard off his mates so a squad never stacks on one waypoint."""
        px = pz = 0.0
        for o in self.enemies:
            if o is e or not o["alive"] or not o.get("live"):
                continue
            dx, dz = e["x"] - o["x"], e["z"] - o["z"]
            d = math.hypot(dx, dz)
            if d < 1.1:
                if d < 1e-3:
                    dx, dz, d = (1.0 if e["slot"] % 2 else -1.0), 0.0, 1.0
                k = (1.1 - d) / 1.1
                px += dx / d * k
                pz += dz / d * k
        if px or pz:
            e["x"], e["z"] = self.s.world.move(e["x"], e["z"], px * 2.2 * dt, pz * 2.2 * dt, 0.34, False)

    def _go(self, e, tx, tz, speed, dt, now):
        """Walk a Guard toward (tx, tz) round the wrecks on a grid path."""
        key = (round(tx), round(tz))
        if e.get("goal_key") != key or not e.get("path") or now >= e.get("repath", 0.0):
            e["path"] = self._path(e["x"], e["z"], tx, tz) or [(tx, tz)]
            e["goal_key"] = key
            e["repath"] = now + 1.2 + 0.6 * self.rng.random()
            e.setdefault("stuck", 0.0)
        self._follow(e, dt, speed)

    def _fire_ctl(self, e, tgt, now, k):
        if e["left"] > 0:
            if now >= e["round_at"]:
                self._shoot(e, tgt, now)
                e["left"] -= 1
                e["round_at"] = now + ROUND_GAP
                if e["left"] == 0:
                    e["next_burst"] = now + k["gap"] * (0.8 + 0.45 * self.rng.random())
        elif e["tele"] > 0.0:
            if now >= e["tele"]:
                e["tele"] = 0.0
                e["left"] = k["burst"]
                e["round_at"] = now
        elif now >= e["next_burst"]:
            if e["next_burst"] == 0.0:
                e["next_burst"] = now + 0.6 + self.rng.random()
            else:
                e["tele"] = now + TELEGRAPH
                e["moving"] = False

    # --- Bodi ------------------------------------------------------------------

    def _call(self, text, force=False):
        b = self.bodi
        now = self.s.t
        if force or now - b["said"] >= CALL_GAP:
            b["said"] = now
            self.s.say("BODI", text, 2.2)

    def _raise(self, a, e, now):
        a["yaw"] = _yaw(e["x"] - a["x"], e["z"] - a["z"])
        d = max(1.0, math.hypot(e["x"] - a["x"], e["z"] - a["z"]))
        a["slope"] = _clamp(round((e["y"] - a["y"] - 0.3) / d, 1), -0.4, 0.4)
        if now - a["aim"] > ALLY_HOLD:
            a["raised"] = now
        a["aim"] = now
        return now - a["raised"] >= ALLY_RAISE

    def _bodi_update(self, dt, now):
        b = self.bodi
        b["moving"] = False
        if b["cover_t"] is not None:
            b["duck_k"] = min(1.0, b["duck_k"] + dt * DUCK_RATE)
        else:
            b["duck_k"] = max(0.0, b["duck_k"] - dt * DUCK_RATE)
        if b["state"] == "down":
            if now - b["down_at"] > BODI_DOWN_S:
                self.s.bodi_lost()
            return
        if b["goal"] is not None:                 # scripted walk (a checkpoint, the gantry foot)
            b["cover_t"] = None
            gx, gz = b["goal"]
            if math.hypot(gx - b["x"], gz - b["z"]) < 0.3:
                b["goal"] = None
                b["path"] = []
            else:
                if not b["path"]:
                    b["path"] = self._path(b["x"], b["z"], gx, gz) or [(gx, gz)]
                self._follow(b, dt, 3.4)
                return
        if self.s.phase in ("clear", "climb", "catwalk"):
            b["cover_t"] = None
            return
        threats = [e for e in self.enemies if e["alive"] and e["live"]]
        if now >= b["replan"]:
            self._plan(threats, now)
            self._warn(threats)
        if b["path"]:
            b["cover_t"] = None
            self._follow(b, dt, 4.4 if threats else 3.2)
            if b["path"]:
                return                            # no shots on the move
        e, ed = self._bodi_target(threats)
        if e is None:
            b["cover_t"] = now if (threats and b["covered"]) else None
            if not threats and math.hypot(self.s.px - b["x"], self.s.pz - b["z"]) > 1.5:
                b["yaw"] = _yaw(self.s.px - b["x"], self.s.pz + 6.0 - b["z"])
            return
        b["tgt"] = e
        b["shot_t"] = now
        if b["cover_t"] is not None and now < b["next"] - ALLY_RAISE - 0.15:
            return                                # down between shots
        b["cover_t"] = None
        if self._raise(b, e, now) and now >= b["next"]:
            muzzle = b.get("muzzle") or (b["x"], 1.35, b["z"])
            ty = e["y"] + 1.1
            p = _clamp(BODI_ACC - ed * 0.008, 0.2, 0.9)
            if self.s.world.low_cover((e["x"], e["z"]), (b["x"], b["z"])):
                p *= 0.6
            if e["moving"]:
                p -= 0.1
            if self.rng.random() < p:
                end = (e["x"], ty, e["z"])
                if self.hurt_enemy(e, BODI_DMG, (b["x"], b["z"])) and self.rng.random() < 0.4:
                    self._call(self.rng.choice(("Got him.", "One less.", "He's down.")))
            else:
                end = (e["x"] + (self.rng.random() - 0.5) * 2.0, ty,
                       e["z"] + (self.rng.random() - 0.5) * 2.0)
            self.s.tracer(muzzle, end)
            self.s.flash(muzzle)
            b["next"] = now + BODI_GAP + 0.4 * self.rng.random()
            b["duck_at"] = now + 0.45
        elif b["duck_at"] is not None and now >= b["duck_at"]:
            b["duck_at"] = None
            if b["covered"]:
                b["cover_t"] = now

    def _bodi_target(self, threats):
        """The Guard Bodi should drop first: the one about to fire, the one near
        Biribel, the one he is already on; never one he cannot see."""
        b = self.bodi
        s = self.s
        best, bs, bd = None, 1e9, 0.0
        for e in threats:
            d = math.hypot(e["x"] - b["x"], e["z"] - b["z"])
            if d > 48.0 or not s.world.los((b["x"], b["z"]), (e["x"], e["z"])):
                continue
            sc = d
            if e["tele"] > 0.0 or e["left"] > 0:
                sc -= 10.0
            dp = math.hypot(e["x"] - s.px, e["z"] - s.pz)
            if dp < 10.0:
                sc -= 10.0 - dp
            if e is b["tgt"]:
                sc -= 4.0
            if s.world.low_cover((e["x"], e["z"]), (b["x"], b["z"])):
                sc += 6.0
            if sc < bs:
                best, bs, bd = e, sc, d
        return best, bd

    def _spot_score(self, x, z, threats):
        """(score, covered) of standing at (x, z) against ``threats``."""
        s = self.s
        b = self.bodi
        dpl = math.hypot(x - s.px, z - s.pz)
        sc = -0.12 * math.hypot(x - b["x"], z - b["z"])
        if dpl < 1.8:
            sc -= 3.0
        if not threats:                          # stay with him, a step behind
            return sc - 0.35 * abs(dpl - 4.5) - 0.6 * max(0.0, z - s.pz + 1.0), False
        bold = 6.0 if s.t - b["shot_t"] > 4.0 else 0.0   # nothing to shoot: range out
        sc -= 0.25 * max(0.0, dpl - 8.0 - bold) + 0.5 * max(0.0, z - s.pz - 2.5 - bold)
        hid = shot = 0
        for e in threats:
            ex, ez = e["x"], e["z"]
            de = math.hypot(ex - x, ez - z)
            if de < 5.0:
                sc -= 1.5 if bold else 3.0
            if not s.world.los((x, z), (ex, ez)):
                hid += 1
            elif s.world.low_cover((x, z), (ex, ez)):
                hid += 1
                shot += 1
            else:
                shot += 1
        n = float(len(threats))
        # hidden from all with no shot at any is a hole, not a firing spot; long
        # without a shot he takes the risk to get one
        if bold:
            sc += 2.5 * hid / n - 0.8 * (n - hid) / n + (1.5 if shot else -6.0)
        else:
            sc += 4.0 * hid / n - 2.5 * (n - hid) / n + (1.2 if shot else -1.0)
        return sc, hid >= n * 0.5

    def _plan(self, threats, now):
        b = self.bodi
        s = self.s
        b["replan"] = now + PLAN_S + 0.4 * self.rng.random()
        if s.py > 1.0 or s.dying:
            return
        self._dyn_boxes = [m.world_box() for m in s.world.dyn if m is not None]
        threats = sorted(threats, key=lambda e: math.hypot(e["x"] - b["x"], e["z"] - b["z"]))[:4]
        here, here_cov = self._spot_score(b["x"], b["z"], threats)
        here += 0.8                               # hold a good spot rather than shuffle
        near = [p for p in _nav()["spots"]
                if math.hypot(p[0] - s.px, p[1] - s.pz) < 13.0 + (6.0 if now - b["shot_t"] > 4.0 else 0.0)
                and not self._in_dyn(p[0], p[1])]
        if len(near) > PLAN_SAMPLES:
            near = self.rng.sample(near, PLAN_SAMPLES)
        best, bs, bcov = None, here, here_cov
        for x, z in near:
            sc, cov = self._spot_score(x, z, threats)
            if sc > bs:
                best, bs, bcov = (x, z), sc, cov
        b["covered"] = bcov
        if best is None:
            return
        path = self._path(b["x"], b["z"], best[0], best[1])
        if not path:
            return
        b["path"] = path
        b["stuck"] = 0.0
        if threats and math.hypot(best[0] - b["x"], best[1] - b["z"]) > 7.0:
            side = "Going left." if best[0] < b["x"] else "Going right."
            self._call(self.rng.choice(("Moving up.", "Shifting - cover me.", side)))

    def _warn(self, threats):
        """Call a Guard working round Biribel's side or back."""
        s = self.s
        a = math.radians(s.yaw)
        f = (math.sin(a), math.cos(a))
        rt = (math.cos(a), -math.sin(a))
        for e in threats:
            if e.get("called"):
                continue
            dx, dz = e["x"] - s.px, e["z"] - s.pz
            d = math.hypot(dx, dz)
            if d > 14.0 or d < 1e-3:
                continue
            fw = (dx * f[0] + dz * f[1]) / d
            if fw > 0.4:
                continue
            e["called"] = True
            if fw < -0.5:
                self._call("Behind you!", force=True)
            elif dx * rt[0] + dz * rt[1] > 0.0:
                self._call("Right side - close!", force=True)
            else:
                self._call("Left side - close!", force=True)
            return

    # --- Bodi's legs -------------------------------------------------------------

    def _in_dyn(self, x, z):
        pad = NAV_PAD + 0.3
        for bx in self._dyn_boxes:
            if bx[0] - pad < x < bx[3] + pad and bx[2] - pad < z < bx[5] + pad:
                return True
        return False

    def _cell(self, x, z):
        n = _nav()
        x0, _x1, z0, _z1 = W.BOUNDS
        return (min(n["nx"] - 1, max(0, int((x - x0) / NAV_CELL))),
                min(n["nz"] - 1, max(0, int((z - z0) / NAV_CELL))))

    def _free(self, i, j):
        n = _nav()
        if not (0 <= i < n["nx"] and 0 <= j < n["nz"]) or not n["free"][i][j]:
            return False
        if self._dyn_boxes:
            x0, _x1, z0, _z1 = W.BOUNDS
            return not self._in_dyn(x0 + (i + 0.5) * NAV_CELL, z0 + (j + 0.5) * NAV_CELL)
        return True

    def _path(self, ax, az, bx, bz):
        """Grid A* from (ax, az) to (bx, bz): waypoints, the goal last; [] if none.
        A goal inside a solid snaps to the nearest walkable cell."""
        n = _nav()
        nx, nz = n["nx"], n["nz"]
        x0, _x1, z0, _z1 = W.BOUNDS
        dyn = bool(self._dyn_boxes)
        grid = n["free"]

        def free(i, j):
            if not (0 <= i < nx and 0 <= j < nz) or not grid[i][j]:
                return False
            return not dyn or not self._in_dyn(x0 + (i + 0.5) * NAV_CELL, z0 + (j + 0.5) * NAV_CELL)

        st, gl = self._cell(ax, az), self._cell(bx, bz)
        if not free(*gl):
            ring = [(gl[0] + di, gl[1] + dj) for di in range(-2, 3) for dj in range(-2, 3)]
            ring = [c for c in ring if free(*c)]
            if not ring:
                return []
            gl = min(ring, key=lambda c: (c[0] - gl[0]) ** 2 + (c[1] - gl[1]) ** 2)
            bx, bz = x0 + (gl[0] + 0.5) * NAV_CELL, z0 + (gl[1] + 0.5) * NAV_CELL
        if st == gl:
            return [(bx, bz)]
        came = {st: None}
        cost = {st: 0.0}
        heap = [(0.0, st)]
        steps = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, 1.414), (1, -1, 1.414), (-1, 1, 1.414), (-1, -1, 1.414))
        gi, gj = gl
        left = 1500
        while heap and left > 0:
            _f, c = heapq.heappop(heap)
            left -= 1
            if c == gl:
                break
            ci, cj = c
            base = cost[c]
            for di, dj, w in steps:
                i, j = ci + di, cj + dj
                if not free(i, j):
                    continue
                if di and dj and not (free(ci + di, cj) and free(ci, cj + dj)):
                    continue
                nc = base + w
                if nc < cost.get((i, j), 1e9):
                    cost[(i, j)] = nc
                    came[(i, j)] = c
                    heapq.heappush(heap, (nc + math.hypot(gi - i, gj - j), (i, j)))
        if gl not in came:
            return []
        cells = []
        c = came[gl]
        while c is not None and c != st:
            cells.append(c)
            c = came[c]
        cells.reverse()
        return [(x0 + (i + 0.5) * NAV_CELL, z0 + (j + 0.5) * NAV_CELL) for i, j in cells] + [(bx, bz)]

    def _clear_line(self, ax, az, bx, bz):
        d = math.hypot(bx - ax, bz - az)
        k = int(d / 0.4) + 1
        for i in range(1, k + 1):
            t = i / float(k)
            if not self._free(*self._cell(ax + (bx - ax) * t, az + (bz - az) * t)):
                return False
        return True

    def _follow(self, a, dt, speed):
        path = a["path"]
        if len(path) > 1 and self._clear_line(a["x"], a["z"], path[1][0], path[1][1]):
            path.pop(0)                           # string-pull: cut the grid corner
        gx, gz = path[0]
        if math.hypot(gx - a["x"], gz - a["z"]) < 0.35:
            path.pop(0)
            if not path:
                return
            gx, gz = path[0]
        if self._walk(a, gx, gz, speed, dt, 0.32):
            a["stuck"] = 0.0
        else:
            a["stuck"] += dt
            if a["stuck"] > 0.8:
                a["path"] = []
                a["replan"] = 0.0

    def _walk(self, a, gx, gz, speed, dt, r):
        dx, dz = gx - a["x"], gz - a["z"]
        d = math.hypot(dx, dz)
        if d < 0.05:
            return True
        step = min(d, speed * dt)
        nx, nz = self.s.world.move(a["x"], a["z"], dx / d * step, dz / d * step, r)
        if math.hypot(nx - a["x"], nz - a["z"]) > step * 0.3:
            a["moving"] = True
            a["yaw"] = _yaw(dx, dz)
            a["gait"] = a.get("gait", 0.0) + math.hypot(nx - a["x"], nz - a["z"])
        else:
            nx, nz = self.s.world.move(a["x"], a["z"], -dz / d * step, dx / d * step, r)
        ok = math.hypot(nx - a["x"], nz - a["z"]) > step * 0.3
        a["x"], a["z"] = nx, nz
        return ok

    def near_revive(self):
        s = self.s
        b = self.bodi
        if b["state"] == "down" and s.py < 1.0 and math.hypot(b["x"] - s.px, b["z"] - s.pz) < 3.0:
            return "bodi"
        return None

    def help_done(self, who):
        self.bodi["state"] = "up"
        self.bodi["hp"] = BODI_HP * 0.5
        self.bodi["low_said"] = False
        self.bodi["replan"] = 0.0
        self.s.say("BODI", "I'm up. Keep moving.", 2.6)
