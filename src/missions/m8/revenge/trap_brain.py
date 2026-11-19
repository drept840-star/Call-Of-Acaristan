"""Mission 8 Revenge - trap AI: Guard riflemen, breachers, elevated overwatch
snipers, the interactive Guard truck and Bodi.

Keeps Bodi's cover-seeking A* wingman loop from M7/M8 while giving the Guard
real tactical roles so the player cannot sit at spawn clicking identical troops:
- ``rifle``: standard cover/flank Guard.
- ``breacher``: armored heavy shotgunner who pushes inside 6.5 m to flush campers.
- ``overwatch``: sniper perched high on the gantry/watchtower with a long-range
  laser lock that charges faster when Biribel stands inside plaza floodlights.
- ``officer``: gantry-foot squad lead anchoring the final push.
- ``gunner``: suppressive rifleman riding the Wave 2 Guard truck bed.

Wave 2's Guard truck now carries real hull HP: shooting the engine/cab or
blowing the north-lane drum as it passes crashes it early and decimates its
dismount crew.
"""
import heapq
import math
import random

from missions.m7 import raid_brain as RB

from . import set3d as S3
from . import trap_world as W

KINDS = {
    "rifle": dict(hp=68, speed=3.15, burst=3, gap=1.70, dmg=5, rng=42.0, acc=0.56, hold=15.0),
    "breacher": dict(hp=115, speed=3.85, burst=2, gap=1.35, dmg=9, rng=26.0, acc=0.72, hold=5.5),
    "overwatch": dict(hp=54, speed=0.0, burst=1, gap=2.55, dmg=18, rng=95.0, acc=0.76, hold=0.0),
    "officer": dict(hp=110, speed=2.90, burst=4, gap=1.40, dmg=6, rng=44.0, acc=0.64, hold=11.0),
    "gunner": dict(hp=110, speed=0.0, burst=5, gap=1.35, dmg=4, rng=60.0, acc=0.48, hold=0.0),
}
ROUND_GAP, TELEGRAPH, FLINCH_S = RB.ROUND_GAP, RB.TELEGRAPH, RB.FLINCH_S
OVERWATCH_TELE = 1.25
ALLY_RAISE, ALLY_HOLD = RB.ALLY_RAISE, RB.ALLY_HOLD
BODI_HP, BODI_DOWN_S = RB.BODI_HP, RB.BODI_DOWN_S
BODI_DMG, BODI_ACC, BODI_GAP = 22, 0.72, 2.15       # tactical wingman, not a solo carry
TRUCK_SPEED = 11.5
TRUCK_HP = 580.0
TRUCK_X, TRUCK_START_Z, TRUCK_STOP_Z = -29.6, 108.0, 38.0

BODI_POSTS = {1: (-63.0, -3.5), 2: (-48.0, 10.5), 3: (-32.0, 29.0)}
BODI_FOOT = (11.0, 54.0)

# Wave 1: wrecks ambush + heavy flanker + gantry-west overwatch (M2 sniper perch)
WRECKS = [
    ("rifle", -40.0, 14.5, [(-43.5, 12.0), (-46.0, 6.0)], 0.0),
    ("rifle", -30.0, 26.0, [(-34.0, 23.0), (-37.0, 15.0)], 0.8),
    ("breacher", -46.0, 23.5, [(-50.5, 16.0), (-54.0, 6.0)], 1.6),
    ("rifle", -40.0, 35.0, [(-43.5, 32.0), (-46.0, 26.0)], 2.4),
    ("rifle", -42.0, 6.0, [(-42.0, -1.0), (-50.0, -4.5)], 3.4),
    ("overwatch", -0.8, 57.1, [], 2.0),
]

# Wave 2 flanking pair supporting the convoy truck roll-in + watchtower overwatch
PLAZA_SUPPORT = [
    ("rifle", -60.0, 20.0, [(-54.0, 18.0), (-48.0, 21.0)], 0.4),
    ("rifle", -14.0, 34.0, [(-20.0, 31.0), (-24.0, 27.0)], 1.6),
    ("overwatch", W.TOWER_AT[0], W.TOWER_AT[1], [], 2.5),
]

# Wave 3: final holdout anchored around the gantry base, control yard and east catwalk
FLANK = [
    ("officer", 2.0, 48.0, [(2.5, 46.0)], 0.0),
    ("breacher", -10.0, 46.0, [(-12.0, 42.0), (-16.0, 38.0)], 0.8),
    ("rifle", -6.0, 54.0, [(-8.0, 48.0), (-5.0, 44.0)], 1.6),
    ("rifle", -38.0, 56.0, [(-34.0, 48.0), (-26.0, 44.0)], 2.4),
    ("rifle", 8.0, 44.0, [(6.0, 45.0), (2.0, 44.0)], 3.2),
    ("overwatch", -0.6, 57.1, [], 1.2),
]


NAV_CELL = 1.0
NAV_PAD = W.BODY_R + 0.12
COVER_REACH = 1.3
PLAN_S = 1.1
PLAN_SAMPLES = 18
CALL_GAP = 3.5
DUCK_RATE = 6.0
_NAV = {}


def _nav():
    if _NAV:
        return _NAV
    x0, x1, z0, z1 = W.BOUNDS
    nx, nz = int((x1 - x0) / NAV_CELL), int((z1 - z0) / NAV_CELL)
    free = [[True] * nz for _ in range(nx)]
    near = [[False] * nz for _ in range(nx)]
    reach = max(NAV_PAD, COVER_REACH)
    for bx0, bz0, bx1, bz1, h in W.STATIC + [W.TOWER_BOX]:
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
        self._sniper_warned = -9.0
        self._breacher_warned = -9.0
        self._grenade_cd = 5.5
        self._camp_pos = (scene.px, scene.pz)
        self._camp_t = 0.0

    # --- waves -----------------------------------------------------------------

    def add(self, kind, x, z, route, delay, wave, **kw):
        k = KINDS[kind]
        self.slot += 1
        y = 0.0
        if kind == "overwatch":
            y = S3.CATWALK_Y if abs(z - S3.CATWALK_Z) < 1.2 else W.TOWER_H
        e = dict(kind=kind, x=x, z=z, y=y, yaw=180.0, hp=k["hp"], alive=True, live=False,
                 wave=wave, route=list(route), wp=0, spawn_at=self.s.t + delay,
                 next_burst=0.0, tele=0.0, tele_dur=OVERWATCH_TELE if kind == "overwatch" else TELEGRAPH,
                 left=0, round_at=0.0, hit_t=-9.0, dead_t=-9.0,
                 moving=False, slot=self.slot, mags=1, aim=-9.0, truck=None, gait=0.0,
                 held=0.0, throw_t=-9.0, throw_at=0.0, throw_dst=None)
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
            t = dict(x=TRUCK_X, z=TRUCK_START_Z, at=self.s.t + 0.8, state="wait",
                     riflemen=4, t_stop=0.0, dumped=False, box=None,
                     hp=TRUCK_HP, max_hp=TRUCK_HP, crashed=False, gun=None, smoke_t=0.0)
            t["gun"] = self.add("gunner", TRUCK_X, TRUCK_START_Z + 1.1, [], 0.8, 2, y=1.3, truck=t)
            self.trucks.append(t)
            for kind, x, z, route, delay in PLAZA_SUPPORT:
                self.add(kind, x, z, route, delay, 2)
        elif n == 3:
            for kind, x, z, route, delay in FLANK:
                self.add(kind, x, z, route, delay, 3)

    def damage_truck(self, t, dmg):
        """Damage the Wave 2 Guard truck; disabling it early crashes it on the lane."""
        if t["crashed"] or t["state"] == "wait":
            return False
        t["hp"] = max(0.0, t["hp"] - dmg)
        if t["hp"] <= 0.0:
            t["crashed"] = True
            t["state"] = "crashed"
            t["t_stop"] = self.s.t
            gun = t.get("gun")
            if gun is not None and gun["alive"]:
                self.hurt_enemy(gun, 999.0, (self.s.px, self.s.pz))
            self.s.on_truck_crash(t)
            return True
        return False

    def _dismount(self, t):
        t["dumped"] = True
        zr = min(W.BOUNDS[3] - 1.5, t["z"] + 3.6)     # tailgate on the north end
        lanes = ((-37.5, 24.0), (-37.0, 18.0), (-23.0, 27.0), (-22.0, 31.0))
        if t["crashed"]:
            # Disrupted crash: only two battered riflemen stumble out late
            for i in range(2):
                sx = t["x"] + (-1.2 if i == 0 else 1.2)
                gx, gz = lanes[i * 2]
                route = [(sx + (-3.2 if i == 0 else 3.2), zr - 2.5), (gx, gz)]
                self.add("rifle", sx, zr, route, 1.3 + i * 0.8, 2, hp=44)
        else:
            for i in range(t["riflemen"]):
                sx = t["x"] + (i - 1.5) * 0.9
                gx, gz = lanes[i]
                kind = "breacher" if i == 1 else "rifle"
                route = [(sx + (2.8 if i >= 2 else -6.5), zr - 1.0), (gx, gz + 9.0), (gx, gz)]
                self.add(kind, sx, zr, route, 0.5 + i * 0.6, 2)

    def pending(self, wave):
        if wave == 2 and any(
            not t["dumped"] or (t["state"] in ("wait", "drive", "stopped") and not t["crashed"])
            for t in self.trucks
        ):
            return True
        return any(e["alive"] and e["wave"] == wave for e in self.enemies)

    def pending_count(self):
        out = 0
        for t in self.trucks:
            if not t["dumped"]:
                out += 2 if t["crashed"] else t["riflemen"]
        return out

    def alive_in_wave(self, wave):
        return sum(1 for e in self.enemies if e["alive"] and e["wave"] == wave)

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
        if e["kind"] == "overwatch" and not self.s.dying and self.s.py < 1.0:
            return ("player", self.s.px, self.s.pz, 1.0, self.s.pmoving, 1.2)
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
        b["replan"] = 0.0
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

    def hurt_enemy(self, e, dmg, src=None, hit_ctx=None):
        if not e["alive"]:
            return False
        prev_hp = e["hp"]
        e["hp"] -= dmg
        e["hit_t"] = self.s.t
        if e["kind"] == "overwatch" and e["tele"] > 0.0:
            e["tele"] = 0.0
            e["next_burst"] = self.s.t + 1.2      # stagger resets sniper lock
        if e["hp"] <= 0:
            e["alive"] = False
            e["dead_t"] = self.s.t
            ux, uz, front = RB._fall_from(e, src)
            e["fall_dir"] = (ux, uz)
            e["dead_pose"] = "dead_back" if front else "dead_front"
            ctx = dict(hit_ctx or {})
            ctx.setdefault("dmg", dmg)
            ctx["overkill"] = max(0.0, dmg - prev_hp)
            e["death_ctx"] = ctx
            self.s.kills += 1
            self.s._snd("enemy_down", math.hypot(e["x"] - self.s.px, e["z"] - self.s.pz))
            return True
        return False

    def spheres(self, e):
        x, y, z = e["x"], e["y"], e["z"]
        if e.get("truck") is not None:
            return [((x, y + 1.1, z), 0.5, False), ((x, y + 1.62, z), 0.25, True)]
        return [
            ((x, y + 1.14, z), 0.46, False),
            ((x, y + 1.62, z), 0.25, True),
            ((x, y + 0.72, z), 0.35, False),
            ((x, y + 0.30, z), 0.32, False),
        ]

    def _shoot(self, e, tgt, now):
        s = self.s
        k = KINDS[e["kind"]]
        name, tx, tz, _w, moving, ty = tgt
        d = math.hypot(tx - e["x"], tz - e["z"])
        yaw = math.radians(e["yaw"])
        muzzle = (e["x"] + math.sin(yaw) * 0.55, e["y"] + 1.35, e["z"] + math.cos(yaw) * 0.55)
        lit = (name == "player" and s.in_floodlight(tx, tz))
        if e["kind"] == "overwatch":
            # Overwatch uses 3D sight check; standing in a floodlight boosts hit odds
            los_ok = s.world.los3d((e["x"], e["y"] + 1.4, e["z"]), (tx, ty + 0.1, tz), dyn=True)
            if not los_ok:
                return
            p = _clamp(k["acc"] + (0.16 if lit else -0.10) - d * 0.004 - (0.18 if moving else 0.0),
                       0.18, 0.90)
        else:
            p = _clamp(k["acc"] - d * 0.012 - (0.14 if moving else 0.0), 0.12, 0.85)
        if s.world.low_cover((tx, tz), (e["x"], e["z"])):
            p *= W.LOW_COVER_K
            if name == "bodi" and self.bodi["duck_k"] > 0.5:
                p *= 0.3
        if self.rng.random() < p:
            end = (tx, ty, tz)
            self._damage(name, k["dmg"], (e["x"], e["z"]))
        else:
            r = self.rng
            end = (tx + (r.random() - 0.5) * 2.2, ty + (r.random() - 0.5) * 1.2,
                   tz + (r.random() - 0.5) * 2.2)
        s.tracer(muzzle, end)
        s.flash(muzzle, sniper=(e["kind"] == "overwatch"))
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
                if e.get("throw_at") and now >= e["throw_at"]:
                    dst = e["throw_dst"] or (self.s.px, self.s.pz)
                    e["throw_at"] = 0.0
                    self.s.throw_grenade((e["x"], e["y"] + 1.55, e["z"]), dst)
                self._enemy(e, dt, now)
        self._bodi_update(dt, now)
        b = self.bodi
        k = b.get("walk_k", 0.0)
        b["walk_k"] = min(1.0, k + dt * 5.0) if b["moving"] else max(0.0, k - dt * 4.0)
        # The Guard flushes entrenched/camping players with live frag grenades.
        if self.s.phase in ("w1", "w2", "w3") and not self.s.dying and self.s.py < 1.0:
            if math.hypot(self.s.px - self._camp_pos[0], self.s.pz - self._camp_pos[1]) < 2.4:
                self._camp_t += dt
            else:
                self._camp_pos = (self.s.px, self.s.pz)
                self._camp_t = 0.0
            pressure = (self._camp_t >= 4.2 and now >= self._grenade_cd) or (now >= self._grenade_cd + 6.5)
            if pressure:
                thrower = next((e for e in self.enemies
                                if e["alive"] and e["live"] and e["kind"] in ("rifle", "officer", "breacher")
                                and not e["left"] and e["tele"] == 0.0
                                and 8.5 < math.hypot(e["x"] - self.s.px, e["z"] - self.s.pz) < 32.0), None)
                if thrower is not None:
                    self._grenade_cd = now + 13.0
                    self._camp_t = 0.0
                    thrower["throw_t"] = now
                    thrower["throw_at"] = now + 0.28
                    thrower["throw_dst"] = (self.s.px, self.s.pz)
                    thrower["yaw"] = _yaw(self.s.px - thrower["x"], self.s.pz - thrower["z"])
                    self._call("Grenade! Get out of there!", force=True)

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
        elif not t["dumped"] and now - t["t_stop"] > (0.6 if t["crashed"] else 0.8):
            self._dismount(t)

    def _truck_box(self, t):
        truck = W.guard_truck_at(t["x"], t["z"])
        self.s.world.dyn[t["box"]] = truck
        r = W.BODY_R
        front = truck.world_box()[2] - r
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
        t = e["truck"]
        if t is not None:
            e["x"], e["z"] = t["x"], t["z"] + 1.15
        tgt = self._pick(e)
        e["moving"] = False
        if e["y"] < 0.5 and t is None:
            self._spread(e, dt)
        if tgt is None:
            return
        d = math.hypot(tgt[1] - e["x"], tgt[2] - e["z"])
        if e["y"] > 0.5 and t is None:
            los = d < k["rng"] and self.s.world.los3d((e["x"], e["y"] + 1.4, e["z"]),
                                                      (tgt[1], tgt[5] + 0.1, tgt[2]), dyn=True)
        else:
            los = d < k["rng"] and self.s.world.los((e["x"], e["z"]), (tgt[1], tgt[2]), dyn=t is None)
        if now - e["hit_t"] < FLINCH_S and t is None:
            return
        if now - e.get("throw_t", -9.0) < 0.55 and t is None:
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            return
        if e["kind"] == "overwatch":
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            if los:
                if e["tele"] > 0.0 and now - self._sniper_warned > 9.0:
                    self._sniper_warned = now
                    where = "Gantry" if abs(e["z"] - S3.CATWALK_Z) < 1.2 else "Tower"
                    self._call("%s sniper - stay behind concrete!" % where, force=True)
                self._fire_ctl(e, tgt, now, k)
            else:
                e["tele"] = 0.0
            return
        if t is not None:
            if los and t["state"] in ("drive", "stopped"):
                e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
                self._fire_ctl(e, tgt, now, k)
            return
        on_route = e["wp"] < len(e["route"])
        if on_route and los and d < (14.0 if e["kind"] == "breacher" else 20.0):
            e["wp"] = len(e["route"])
            on_route = False
        if on_route:
            wx, wz = e["route"][e["wp"]]
            if math.hypot(wx - e["x"], wz - e["z"]) < 1.0:
                e["wp"] += 1
            else:
                self._go(e, wx, wz, k["speed"] * 1.30, dt, now)
        elif los:
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            busy = e["left"] > 0 or e["tele"] > 0.0
            if e["kind"] == "breacher" and d < 16.0 and now - self._breacher_warned > 11.0:
                self._breacher_warned = now
                self._call("Heavy pushing in - don't stay pinned!", force=True)
            if not busy:
                e["held"] += dt
                if d > k["hold"] + 2.5:
                    e["moving"] = self._steer(e, tgt[1], tgt[2], k["speed"], dt)
                elif d < (4.2 if e["kind"] == "breacher" else 7.0):
                    away = e["x"] - (tgt[1] - e["x"]), e["z"] - (tgt[2] - e["z"])
                    e["moving"] = self._steer(e, away[0], away[1], k["speed"] * 0.7, dt)
                elif e["held"] > 3.2 and e["left"] == 0:
                    side = 1.0 if e["slot"] % 2 else -1.0
                    px, pz = tgt[2] - e["z"], -(tgt[1] - e["x"])
                    n = math.hypot(px, pz) or 1.0
                    e["moving"] = self._steer(e, e["x"] + side * px / n * 4.0,
                                              e["z"] + side * pz / n * 4.0, k["speed"] * 0.85, dt)
                    if e["held"] > 5.0:
                        e["held"] = 0.0
            self._fire_ctl(e, tgt, now, k)
        else:
            e["held"] = 0.0
            self._go(e, tgt[1], tgt[2], k["speed"], dt, now)

    def _spread(self, e, dt):
        px = pz = 0.0
        for o in self.enemies:
            if o is e or not o["alive"] or not o.get("live") or o["y"] > 0.5 or o["truck"] is not None:
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
                dur = TELEGRAPH
                if e["kind"] == "overwatch":
                    lit = tgt[0] == "player" and self.s.in_floodlight(tgt[1], tgt[2])
                    dur = OVERWATCH_TELE * (0.72 if lit else 1.18)
                e["tele_dur"] = dur
                e["tele"] = now + dur
                e["moving"] = False

    # --- Bodi ------------------------------------------------------------------

    def _call(self, text, force=False):
        b = self.bodi
        now = self.s.t
        if force or now - b["said"] >= CALL_GAP:
            b["said"] = now
            self.s.say("BODI", text, 2.4)

    def _aim_track(self, a, e, dt=1.0 / 60.0):
        want = _yaw(e["x"] - a["x"], e["z"] - a["z"])
        a["yaw"] = RB._yaw_mix(a.get("yaw", want), want, min(1.0, max(0.0, dt) * 11.0))
        d = max(1.0, math.hypot(e["x"] - a["x"], e["z"] - a["z"]))
        a["slope"] = _clamp(round((e["y"] - a["y"] - 0.3) / d, 1), -0.4, 0.4)
        return abs(RB._wrap(want - a["yaw"]))

    def _raise(self, a, e, now, dt=1.0 / 60.0):
        err = self._aim_track(a, e, dt)
        if now - a["aim"] > ALLY_HOLD:
            a["raised"] = now
        a["aim"] = now
        return now - a["raised"] >= ALLY_RAISE and err < 14.0

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
        threats = [e for e in self.enemies if e["alive"] and e["live"]]
        if b["goal"] is not None:
            b["cover_t"] = None
            gx, gz = b["goal"]
            if math.hypot(gx - b["x"], gz - b["z"]) < 0.35:
                b["goal"] = None
                b["path"] = []
            else:
                if not b["path"]:
                    b["path"] = self._path(b["x"], b["z"], gx, gz) or [(gx, gz)]
                e, _ed = self._bodi_target(threats)
                self._follow(b, dt, 3.6, face=(e is None))
                if e is not None:
                    self._raise(b, e, now, dt)
                return
        if self.s.phase in ("clear", "climb", "catwalk"):
            b["cover_t"] = None
            return
        if now >= b["replan"]:
            self._plan(threats, now)
            self._warn(threats)
        e, ed = self._bodi_target(threats)
        if b["path"]:
            b["cover_t"] = None
            self._follow(b, dt, 4.4 if threats else 3.4, face=(e is None))
            if e is not None:
                self._raise(b, e, now, dt)
            if b["path"]:
                return
        if e is None:
            b["cover_t"] = now if (threats and b["covered"]) else None
            if not threats and math.hypot(self.s.px - b["x"], self.s.pz - b["z"]) > 1.5:
                want = _yaw(self.s.px - b["x"], self.s.pz + 6.0 - b["z"])
                b["yaw"] = RB._yaw_mix(b.get("yaw", want), want, min(1.0, max(0.0, dt) * 6.0))
            return
        b["tgt"] = e
        b["shot_t"] = now
        if b["cover_t"] is not None and now < b["next"] - ALLY_RAISE - 0.25:
            self._aim_track(b, e, dt)
            return
        b["cover_t"] = None
        if self._raise(b, e, now, dt) and now >= b["next"]:
            muzzle = b.get("muzzle") or (b["x"], 1.35, b["z"])
            ty = e["y"] + 1.1
            p = _clamp(BODI_ACC - ed * 0.008, 0.2, 0.85)
            if e["y"] < 0.5 and self.s.world.low_cover((e["x"], e["z"]), (b["x"], b["z"])):
                p *= 0.6
            if e["moving"]:
                p -= 0.1
            if self.rng.random() < p:
                end = (e["x"], ty, e["z"])
                if self.hurt_enemy(e, BODI_DMG, (b["x"], b["z"])) and self.rng.random() < 0.35:
                    self._call(self.rng.choice(("Got him.", "One less.", "He's down.")))
            else:
                end = (e["x"] + (self.rng.random() - 0.5) * 2.0, ty,
                       e["z"] + (self.rng.random() - 0.5) * 2.0)
            self.s.tracer(muzzle, end)
            self.s.flash(muzzle)
            b["next"] = now + BODI_GAP + 0.5 * self.rng.random()
            b["duck_at"] = now + 0.65
        elif b["duck_at"] is not None and now >= b["duck_at"]:
            b["duck_at"] = None
            if b["covered"]:
                b["cover_t"] = now

    def _bodi_target(self, threats):
        b = self.bodi
        s = self.s
        best, bs, bd = None, 1e9, 0.0
        for e in threats:
            d = math.hypot(e["x"] - b["x"], e["z"] - b["z"])
            if d > 56.0:
                continue
            if e["y"] > 0.5:
                if not s.world.los3d((b["x"], 1.4, b["z"]), (e["x"], e["y"] + 1.2, e["z"]),
                                     dyn=(e["truck"] is None)):
                    continue
            elif not s.world.los((b["x"], b["z"]), (e["x"], e["z"])):
                continue
            sc = d
            if e["tele"] > 0.0 or e["left"] > 0:
                sc -= 8.0
            dp = math.hypot(e["x"] - s.px, e["z"] - s.pz)
            if dp < 10.0:
                sc -= 10.0 - dp
            if e["kind"] == "breacher" and dp < 14.0:
                sc -= 6.0
            if e is b["tgt"]:
                sc -= 4.0
            if e["y"] < 0.5 and s.world.low_cover((e["x"], e["z"]), (b["x"], b["z"])):
                sc += 6.0
            if sc < bs:
                best, bs, bd = e, sc, d
        return best, bd

    def _spot_score(self, x, z, threats):
        s = self.s
        b = self.bodi
        dpl = math.hypot(x - s.px, z - s.pz)
        sc = -0.12 * math.hypot(x - b["x"], z - b["z"])
        if dpl < 1.8:
            sc -= 3.0
        if not threats:
            return sc - 0.35 * abs(dpl - 4.5) - 0.6 * max(0.0, z - s.pz + 1.0), False
        bold = 6.0 if s.t - b["shot_t"] > 4.0 else 0.0
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
        threats = sorted([e for e in threats if e["y"] < 0.5],
                         key=lambda e: math.hypot(e["x"] - b["x"], e["z"] - b["z"]))[:4]
        here, here_cov = self._spot_score(b["x"], b["z"], threats)
        here += 0.8
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
        s = self.s
        a = math.radians(s.yaw)
        f = (math.sin(a), math.cos(a))
        rt = (math.cos(a), -math.sin(a))
        for e in threats:
            if e.get("called") or e["y"] > 0.5:
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

    def _follow(self, a, dt, speed, face=True):
        path = a["path"]
        if len(path) > 1 and self._clear_line(a["x"], a["z"], path[1][0], path[1][1]):
            path.pop(0)
        gx, gz = path[0]
        if math.hypot(gx - a["x"], gz - a["z"]) < 0.35:
            path.pop(0)
            if not path:
                return
            gx, gz = path[0]
        if self._walk(a, gx, gz, speed, dt, 0.32, face=face):
            a["stuck"] = 0.0
        else:
            a["stuck"] += dt
            if a["stuck"] > 0.8:
                a["path"] = []
                a["replan"] = 0.0

    def _walk(self, a, gx, gz, speed, dt, r, face=True):
        dx, dz = gx - a["x"], gz - a["z"]
        d = math.hypot(dx, dz)
        if d < 0.05:
            return True
        step = min(d, speed * dt)
        nx, nz = self.s.world.move(a["x"], a["z"], dx / d * step, dz / d * step, r)
        if math.hypot(nx - a["x"], nz - a["z"]) > step * 0.3:
            a["moving"] = True
            if face:
                a["yaw"] = RB._yaw_mix(a.get("yaw", 0.0), _yaw(dx, dz), min(1.0, max(0.0, dt) * 9.0))
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
