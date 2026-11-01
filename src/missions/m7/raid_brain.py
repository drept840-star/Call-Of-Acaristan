"""Mission 7 raid AI: the Guard sweep (riflemen, a dog, a truck gunner), the trucks,
and the two allies, Bodi and Alex.

Deliberately plain: each raider is a dict walked by a small state machine, with no
behaviour tree.  The scene (``raid3d``) owns the player and hands itself in as ``s``.
"""
import math
import random

from . import raid_world as W

KINDS = {
    "rifle": dict(hp=70, speed=3.1, burst=3, gap=1.7, dmg=5, rng=38.0, acc=0.58, hold=15.0),
    "gunner": dict(hp=110, speed=0.0, burst=6, gap=1.5, dmg=4, rng=52.0, acc=0.52, hold=0.0),
    "dog": dict(hp=34, speed=6.4, burst=0, gap=0.9, dmg=9, rng=0.0, acc=1.0, hold=0.0),
}
ROUND_GAP = 0.12
TELEGRAPH = 0.38
FLINCH_S = 0.22
BITE_R = 1.25
BITE_PLAY = 1.2 / 0.9             # the 1.2 s Bite clip plays inside the dog's 0.9 s gap
BITE_HIT = 0.55 / BITE_PLAY       # the jaws close 0.55 s into the clip; the bite lands then
TRUCK_SPEED = 12.0
TRUCK_START_Z = -80.0
ALEX_HP, BODI_HP = 80, 100
ALEX_UP_S, BODI_DOWN_S = 8.0, 20.0
ALLY_RAISE = 0.25                 # an ally shoulders the rifle this long before a first shot
ALLY_HOLD = 1.8                   # and keeps it up through the gaps between bursts
ALEX_LEASH = 13.0                 # Alex fights within this many metres of Biribel
ALEX_RISE_S = 1.3                 # freed from the well, Alex gets up this long before moving
ALEX_CRAWL = 1.1                  # metres Alex drags himself out from under the roof

# kind, x, z, route, delay (s)
ORCHARD = [
    ("rifle", 45.5, 1.0, [(30.0, 1.0), (23.0, 1.2), (17.0, 1.2)], 0.0),
    ("rifle", 45.5, 7.5, [(33.0, 7.5), (24.0, 2.0), (17.0, 2.2)], 2.0),
    ("rifle", 45.5, -4.5, [(33.0, -5.0), (24.0, -1.5), (17.0, -1.0)], 3.5),
    ("rifle", 45.5, 4.0, [(34.0, 4.5), (26.0, 1.0), (16.0, 0.0)], 6.5),
    ("dog", 45.5, 4.0, [], 7.5),
]
NORTH = [
    ("rifle", -3.0, 40.0, [(-2.0, 26.0), (-1.0, 16.0), (-1.0, 9.0)], 0.0),
    ("rifle", 2.0, 42.0, [(2.0, 26.0), (2.5, 16.0), (3.0, 9.5)], 1.2),
    ("rifle", 6.0, 38.0, [(5.0, 26.0), (4.0, 16.0), (4.5, 10.0)], 2.4),
    ("rifle", -7.0, 38.0, [(-6.0, 26.0), (-5.0, 16.0), (-4.0, 9.0)], 3.6),
    ("rifle", 0.0, 44.0, [(0.0, 26.0), (0.0, 16.0), (0.5, 9.5)], 5.0),
    ("rifle", 28.0, 30.0, [(24.0, 22.0), (22.5, 8.0), (22.0, 1.5), (14.0, 1.5)], 3.0),
    ("rifle", 31.0, 33.0, [(25.0, 23.0), (23.0, 9.0), (22.0, 1.0), (15.0, 1.0)], 5.5),
]


def _ray_sphere(o, d, c, r):
    ox, oy, oz = o[0] - c[0], o[1] - c[1], o[2] - c[2]
    b = ox * d[0] + oy * d[1] + oz * d[2]
    cc = ox * ox + oy * oy + oz * oz - r * r
    disc = b * b - cc
    if disc < 0.0:
        return None
    t = -b - math.sqrt(disc)
    return t if t > 0.0 else None


def _yaw(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v




def _fall_from(e, src):
    """Push direction away from the shooter, and whether he was shot from the front."""
    yaw = math.radians(e["yaw"])
    fx, fz = math.sin(yaw), math.cos(yaw)
    if src is None:
        return -fx, -fz, True
    dx, dz = e["x"] - src[0], e["z"] - src[1]
    d = math.hypot(dx, dz) or 1.0
    return dx / d, dz / d, fx * -dx + fz * -dz > 0.0


class Brain:
    def __init__(self, scene):
        self.s = scene
        self.rng = random.Random(77)
        self.enemies = []
        self.trucks = []
        self.wave = 0
        self.slot = 0
        f = scene.flags
        loft = f["loft"]
        x, z = (W.LOFT_AT[0], W.LOFT_AT[2]) if loft else W.BODI_GROUND
        self.bodi = dict(x=x, z=z, y=W.LOFT_AT[1] if loft else 0.0, yaw=180.0, hp=BODI_HP,
                         state="up", down_at=0.0, loft=loft, moving=False, next=2.0, aim=-9.0, raised=-9.0, slope=0.0,
                         goal=None, revive=0.0)
        self.alex = dict(x=-3.4, z=-1.0, y=0.0, yaw=0.0, hp=ALEX_HP, state="up", up_at=0.0,
                         pinned=False, moving=False, next=2.5, aim=-9.0, raised=-9.0, slope=0.0, pull=0.0, burst=0,
                         spot=None, replan=0.0, target_slot=None, follow_goal=None, follow_at=0.0)

    # --- waves -----------------------------------------------------------------

    def add(self, kind, x, z, route, delay, wave, **kw):
        k = KINDS[kind]
        self.slot += 1
        e = dict(kind=kind, x=x, z=z, y=0.0, yaw=0.0, hp=k["hp"], alive=True, live=False,
                 wave=wave, route=list(route), wp=0, spawn_at=self.s.t + delay,
                 next_burst=0.0, tele=0.0, left=0, round_at=0.0, hit_t=-9.0, dead_t=-9.0,
                 moving=False, slot=self.slot, bite_at=0.0, bite_hit=0.0, mags=1, aim=-9.0, tgt=None,
                 truck=None, gait=0.0, phase=self.rng.random() * 6.0, held=0.0)
        e.update(kw)
        self.enemies.append(e)
        return e

    def start_wave(self, n):
        s = self.s
        self.wave = n
        if n == 1:
            for kind, x, z, route, delay in ORCHARD:
                self.add(kind, x, z, route, delay, 1)
        elif n == 2:
            block = s.flags["tractor"]
            late = 20.0 if block else 0.0
            self._truck(-1.5, 1.0, -26.0 if block else -9.5, not block, 3, True, block)
            self._truck(1.6, 1.0 + 13.0 + late, -31.5 if block else -11.5, False, 3, False, block)
        elif n == 3:
            for kind, x, z, route, delay in NORTH:
                self.add(kind, x, z, route, delay, 3)

    def _truck(self, x, delay, stop_z, gunner, riflemen, dog, block):
        t = dict(x=x, z=TRUCK_START_Z, stop_z=stop_z, at=self.s.t + delay, state="wait",
                 gun=None, riflemen=riflemen, dog=dog, block=block, t_stop=0.0, dumped=False)
        if gunner:
            t["gun"] = self.add("gunner", x, TRUCK_START_Z - 1.2, [], delay, 2, y=1.3, truck=t)
        self.trucks.append(t)

    def _dismount(self, t):
        t["dumped"] = True
        zx = t["z"] - 3.6
        for i in range(t["riflemen"]):
            if t["block"]:
                route = [(2.6, -17.5), (2.2, -9.0), (-1.5, -2.5)]
            else:
                route = [(-3.5 + i * 3.0, -4.0), (-2.0 + i * 2.0, 0.0)]
            self.add("rifle", t["x"] + (i - 1) * 0.9, zx, route, 0.5 + i * 0.7, 2)
        if t["dog"]:
            self.add("dog", t["x"], zx, [], 2.6, 2)

    def pending(self, wave):
        if wave == 2 and any(not t["dumped"] for t in self.trucks):
            return True
        return any(e["alive"] and e["wave"] == wave for e in self.enemies)

    def alive_count(self):
        return sum(1 for e in self.enemies if e["alive"])

    def clear_for_checkpoint(self):
        self.enemies = []
        self.trucks = []
        W_ = self.s.world
        W_.dyn[:] = []

    # --- targets and damage ----------------------------------------------------

    def _cands(self, dog=False):
        s = self.s
        out = []
        if not s.dying:
            out.append(("player", s.px, s.pz, 1.0, s.pmoving, 1.2))
        a = self.alex
        if a["state"] == "up":
            out.append(("alex", a["x"], a["z"], 0.55 if a["pinned"] else 1.15, a["moving"], 1.2))
        b = self.bodi
        if b["state"] == "up" and not (dog and b["loft"]):
            out.append(("bodi", b["x"], b["z"], 1.3, b["moving"], b["y"] + 1.2))
        return out

    def _pick(self, e, ex, ez):
        best, bd = None, 1e9
        for c in self._cands(e["kind"] == "dog"):
            d = math.hypot(c[1] - ex, c[2] - ez) * c[3]
            if d < bd:
                best, bd = c, d
        return best

    def _damage(self, name, dmg, src):
        s = self.s
        if name == "player":
            s.hurt_player(dmg, src)
        elif name == "alex":
            a = self.alex
            if a["pinned"]:
                a["flinch"] = s.t
                return
            a["hp"] -= dmg
            if a["hp"] <= 0:
                a["state"] = "down"
                a["up_at"] = s.t + ALEX_UP_S
                s.say("ALEX", "I'm fine! I'm fine. I'm on the floor, but I'm fine.", 3.0)
        else:
            b = self.bodi
            if b["state"] != "up":     # downed, or walking off the yard
                return
            b["hp"] -= dmg * (0.6 if b["loft"] else 1.0)
            if b["hp"] <= 0:
                b["state"] = "down"
                b["down_at"] = s.t
                s.say("ALEX", "Bodi's down! Biribel, Bodi's down!", 3.2)

    def hurt_enemy(self, e, dmg, src=None):
        if not e["alive"]:
            return False
        e["hp"] -= dmg
        e["hit_t"] = self.s.t
        if e["hp"] <= 0:
            e["alive"] = False
            e["dead_t"] = self.s.t
            e["mags"] = 1
            ux, uz, front = _fall_from(e, src)
            e["fall_dir"] = (ux, uz)
            e["dead_pose"] = "dead_back" if front else "dead_front"
            self.s.kills += 1
            return True
        return False

    def spheres(self, e):
        x, y, z = e["x"], e["y"], e["z"]
        if e["kind"] == "dog":
            return [((x, y + 0.6, z), 0.5, False)]
        return [((x, y + 1.1, z), 0.5, False), ((x, y + 1.62, z), 0.25, True)]

    def _shoot(self, e, tgt, now):
        s = self.s
        k = KINDS[e["kind"]]
        name, tx, tz, _w, moving, ty = tgt
        d = math.hypot(tx - e["x"], tz - e["z"])
        yaw = math.radians(e["yaw"])
        muzzle = (e["x"] + math.sin(yaw) * 0.55, e["y"] + 1.35, e["z"] + math.cos(yaw) * 0.55)
        p = _clamp(k["acc"] - d * 0.012 - (0.14 if moving else 0.0), 0.12, 0.85)
        if name == "bodi" and self.bodi["loft"]:
            p *= 0.45
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

    # --- movement helpers ------------------------------------------------------

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
        self._alex_update(dt, now)
        for a in (self.alex, self.bodi):    # eased walk weight: the draw blends run and stance
            k = a.get("walk_k", 0.0)
            a["walk_k"] = min(1.0, k + dt * 5.0) if a["moving"] else max(0.0, k - dt * 4.0)
        fire = self.s.fire
        if fire.lit:
            for a in (self.alex, self.bodi):
                if a["state"] == "up" and fire.burning(a["x"], a["z"]):
                    self._damage("alex" if a is self.alex else "bodi", W.FIRE_DPS * dt, None)

    def _truck_update(self, t, dt, now):
        if t["state"] == "wait":
            if now >= t["at"]:
                t["state"] = "drive"
                t["box"] = len(self.s.world.dyn)
                self.s.world.dyn.append(None)
                self._truck_box(t)
            return
        if t["state"] == "drive":
            left = t["stop_z"] - t["z"]
            v = min(TRUCK_SPEED, 1.0 + left * 0.9)
            t["z"] += max(0.0, v) * dt
            if left < 0.15:
                t["z"] = t["stop_z"]
                t["state"] = "stopped"
                t["t_stop"] = now
                self.s.on_truck_stop(t)
            self._truck_box(t)
        elif not t["dumped"] and now - t["t_stop"] > 0.8:
            self._dismount(t)

    def _truck_box(self, t):
        """Keep the truck's collider on it while it drives, and shove anyone
        standing in its path ahead of the bumper so nobody ends up inside it."""
        truck = W.truck_at(t["x"], t["z"])
        self.s.world.dyn[t["box"]] = truck
        r = W.BODY_R
        front = truck.world_box()[5] + r
        for a in (self.alex, self.bodi):
            if truck.body_hits(a["x"], a["z"], r, 0.0, W.BODY_TOP):
                a["z"] = front
        if truck.body_hits(self.s.px, self.s.pz, r, 0.0, W.BODY_TOP):
            self.s.pz = front

    def _enemy(self, e, dt, now):
        if now < e["spawn_at"]:
            e["live"] = False
            return
        e["live"] = True
        k = KINDS[e["kind"]]
        if e["kind"] == "dog":
            self._dog(e, dt, now, k)
            return
        t = e["truck"]
        if t is not None:
            e["x"], e["z"] = t["x"], t["z"] - 1.1
            if t["state"] != "stopped":
                e["moving"] = False
                return
        tgt = self._pick(e, e["x"], e["z"])
        if tgt is None:
            e["moving"] = False
            return
        d = math.hypot(tgt[1] - e["x"], tgt[2] - e["z"])
        los = d < k["rng"] and self.s.world.los((e["x"], e["z"]), (tgt[1], tgt[2]), dyn=t is None)
        e["moving"] = False
        if now - e["hit_t"] < FLINCH_S and t is None:
            return
        on_route = e["wp"] < len(e["route"])
        if on_route and los and d < 20.0:
            e["wp"] = len(e["route"])
            on_route = False
        if on_route:
            wx, wz = e["route"][e["wp"]]
            if math.hypot(wx - e["x"], wz - e["z"]) < 1.0:
                e["wp"] += 1
            elif self._steer(e, wx, wz, k["speed"] * 1.35, dt):
                e["moving"] = True
                e["yaw"] = _yaw(wx - e["x"], wz - e["z"])
        elif los:
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            busy = e["left"] > 0 or e["tele"] > 0.0
            if t is None and k["speed"] > 0.0 and not busy:
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
        elif t is None:
            e["held"] = 0.0
            if self._steer(e, tgt[1], tgt[2], k["speed"], dt):
                e["moving"] = True
                e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])

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

    def _dog(self, e, dt, now, k):
        e["moving"] = False
        if now - e["hit_t"] < 0.12:
            return
        tgt = self._pick(e, e["x"], e["z"])
        if tgt is None:
            return
        d = math.hypot(tgt[1] - e["x"], tgt[2] - e["z"])
        e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
        if e["bite_hit"] and now >= e["bite_hit"]:
            e["bite_hit"] = 0.0
            if d <= BITE_R * 1.3:
                self._damage(tgt[0], k["dmg"], (e["x"], e["z"]))
        if now - e["aim"] < BITE_HIT:
            return
        if d > BITE_R:
            e["moving"] = self._steer(e, tgt[1], tgt[2], k["speed"], dt)
        elif now >= e["bite_at"]:
            e["bite_at"] = now + k["gap"]
            e["aim"] = now
            e["bite_hit"] = now + BITE_HIT

    # --- allies ----------------------------------------------------------------

    def _target_for_ally(self, x, z, rng):
        best, bd = None, rng
        for e in self.enemies:
            if not e["alive"] or not e["live"]:
                continue
            d = math.hypot(e["x"] - x, e["z"] - z)
            if d < bd and self.s.world.los((x, z), (e["x"], e["z"]), dyn=e["truck"] is None):
                best, bd = e, d
        return best, bd

    def _raise(self, a, e, now):
        """Face ``e`` and shoulder the rifle at it; True once it is up to fire."""
        a["yaw"] = _yaw(e["x"] - a["x"], e["z"] - a["z"])
        d = max(1.0, math.hypot(e["x"] - a["x"], e["z"] - a["z"]))
        a["slope"] = _clamp(round((e["y"] - a["y"] - 0.3) / d, 1), -0.4, 0.4)
        if now - a["aim"] > ALLY_HOLD:
            a["raised"] = now
        a["aim"] = now
        return now - a["raised"] >= ALLY_RAISE

    def _ally_shot(self, a, e, d, dmg, acc, now, y):
        muzzle = a.get("muzzle") or (a["x"], a["y"] + 1.35, a["z"])
        ty = e["y"] + 1.1
        if self.rng.random() < _clamp(acc - d * 0.008, 0.2, 0.9):
            end = (e["x"], ty, e["z"])
            self.hurt_enemy(e, dmg, (a["x"], a["z"]))
        else:
            end = (e["x"] + (self.rng.random() - 0.5) * 2.0, ty, e["z"] + (self.rng.random() - 0.5) * 2.0)
        self.s.tracer(muzzle, end)
        self.s.flash(muzzle)

    def _alex_update(self, dt, now):
        a = self.alex
        a["moving"] = False
        if a["state"] == "down":
            if now >= a["up_at"]:
                a["state"] = "up"
                a["hp"] = ALEX_HP * 0.5
            return
        if a["pinned"] or a.get("cover_t") is not None:
            return
        if a.get("to_well") is not None:
            gx, gz = W.WELL_PIN
            d = math.hypot(gx - a["x"], gz - a["z"])
            if d < 0.12 or now - a["to_well"] > 8.0:
                # in cover at the well; the frame comes down on him there
                a["x"], a["z"] = gx, gz
                a["to_well"], a["cover_t"] = None, now
            else:
                self._walk(a, gx, gz, 4.0, dt, 0.3)
            return
        if now - a.get("freed", -9.0) < ALEX_RISE_S:
            return
        e, ed = self._target_for_ally(a["x"], a["z"], 32.0)
        if e is None:
            a["target_slot"], a["spot"] = None, None
            self._alex_near_player(a, dt)
            return
        # Pick a firing position once per target.  Re-solving every 2.5 seconds
        # made Alex chase a moving optimum around the player instead of holding
        # a useful lane.  Keep the chosen position until the target changes.
        if a["spot"] is None or a["target_slot"] != e["slot"]:
            a["target_slot"] = e["slot"]
            a["spot"] = self._alex_spot(a, e)
        if a["spot"] is None:
            self._alex_near_player(a, dt)
            return
        sx, sz = a["spot"]
        if math.hypot(sx - a["x"], sz - a["z"]) > 0.55:
            self._walk(a, sx, sz, 3.8, dt, 0.32)
        if a["moving"]:
            return
        if not self._raise(a, e, now) or now < a["next"]:
            return
        if a["burst"] <= 0:
            a["burst"] = 3
        self._ally_shot(a, e, ed, 12, 0.66, now, 1.2)
        a["burst"] -= 1
        a["next"] = now + (0.42 if a["burst"] else 1.1 + 0.4 * self.rng.random())

    def _alex_near_player(self, a, dt):
        """Hold a calm trailing position; only close distance when genuinely left behind."""
        s = self.s
        d_player = math.hypot(s.px - a["x"], s.pz - a["z"])
        # Do not orbit around Biribel to maintain an exact moving formation point.
        # Refresh the trailing point occasionally, and only pursue outside a wide leash.
        # Start past 6 m but keep going until 3.5 m or the goal: one threshold made
        # Alex flip between walking and standing every frame at the leash edge.
        if d_player < (3.5 if a["follow_goal"] is not None else 6.0):
            a["follow_goal"] = None
            return
        if a["follow_goal"] is None or s.t >= a["follow_at"]:
            sy = math.radians(s.yaw)
            fx, fz = math.sin(sy), math.cos(sy)
            rx, rz = math.cos(sy), -math.sin(sy)
            a["follow_goal"] = (s.px - fx * 2.0 - rx * 2.0,
                                s.pz - fz * 2.0 - rz * 2.0)
            a["follow_at"] = s.t + 1.6
        gx, gz = a["follow_goal"]
        if math.hypot(gx - a["x"], gz - a["z"]) > 1.2:
            self._walk(a, gx, gz, 4.0, dt, 0.32)
        else:
            a["follow_goal"] = None

    def _alex_spot(self, a, e):
        """A spot Alex can shoot from: a few metres off, inside the leash on Biribel, next to
        cover when it can be, and off Biribel's line to the target when it can be (a flank)."""
        s = self.s
        bearing = _yaw(e["x"] - s.px, e["z"] - s.pz)
        best, best_score = None, None
        for k in range(16):
            ang = math.tau * k / 16.0
            for r in (3.0, 5.5, 8.0):
                x, z = a["x"] + math.cos(ang) * r, a["z"] + math.sin(ang) * r
                if math.hypot(x - s.px, z - s.pz) > ALEX_LEASH:
                    continue
                if math.hypot(x - e["x"], z - e["z"]) < 6.0 or s.world.blocked(x, z):
                    continue
                if any(s.world.blocked(a["x"] + (x - a["x"]) * k / 6.0, a["z"] + (z - a["z"]) * k / 6.0)
                       for k in range(1, 6)):
                    continue
                if not s.world.los((x, z), (e["x"], e["z"]), dyn=e["truck"] is None):
                    continue
                off = abs((_yaw(x - s.px, z - s.pz) - bearing + 180.0) % 360.0 - 180.0)
                near = any(s.world.blocked(x + ox, z + oz, 0.2)
                           for ox, oz in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0)))
                score = -r + (4.0 if off > 35.0 else 0.0) + (2.0 if near else 0.0)
                if best_score is None or score > best_score:
                    best, best_score = (x, z), score
        return best

    def _bodi_update(self, dt, now):
        b = self.bodi
        b["moving"] = False
        if b["state"] == "turned":
            return          # he is not fighting the Guards any more: the scene drives him
        if b["state"] == "down":
            if now - b["down_at"] > BODI_DOWN_S:
                self.s.bodi_lost()
            return
        if b["goal"] is not None:
            gx, gz = b["goal"]
            if math.hypot(gx - b["x"], gz - b["z"]) < 0.3:
                b["goal"] = None
            else:
                self._walk(b, gx, gz, 2.8, dt, 0.32)
                return
        e, ed = self._target_for_ally(b["x"], b["z"], 46.0)
        if e is not None and self._raise(b, e, now) and now >= b["next"]:
            loft = b["loft"]
            self._ally_shot(b, e, ed, 40 if loft else 30, 0.85, now, 1.2)
            b["next"] = now + (1.15 if loft else 1.0) + 0.3 * self.rng.random()

    def bodi_climb_down(self):
        """The barn is burning: Bodi drops from the ledge and walks to cover."""
        b = self.bodi
        b["loft"] = False
        b["x"], b["z"], b["y"] = 10.0, 5.2, 0.0
        b["goal"] = W.BODI_GROUND

    def bodi_turn(self):
        """The pig is dead: Bodi stops fighting the Guards and comes for you.

        He is off the target list and off the revive list from this frame on,
        and the raid's own script (``raid3d._turn_update``) walks him into
        range and puts the round through you. There is no state in which the
        player wins this one.
        """
        b = self.bodi
        if b["state"] in ("turned", "down"):
            return False
        if b["loft"]:
            b["loft"] = False
            b["x"], b["z"], b["y"] = 10.0, 5.2, 0.0
        b["state"] = "turned"
        b["goal"] = None
        b["aim"] = -9.0
        b["raised"] = -9.0
        b["moving"] = False
        return True

    def _walk(self, a, gx, gz, speed, dt, r):
        dx, dz = gx - a["x"], gz - a["z"]
        d = math.hypot(dx, dz)
        if d < 0.05:
            return
        step = min(d, speed * dt)
        nx, nz = self.s.world.move(a["x"], a["z"], dx / d * step, dz / d * step, r)
        if math.hypot(nx - a["x"], nz - a["z"]) > step * 0.3:
            a["moving"] = True
            a["yaw"] = _yaw(dx, dz)
            a["gait"] = a.get("gait", 0.0) + math.hypot(nx - a["x"], nz - a["z"])
        else:
            nx, nz = self.s.world.move(a["x"], a["z"], -dz / d * step, dx / d * step, r)
        a["x"], a["z"] = nx, nz

    # --- revive ----------------------------------------------------------------

    def near_revive(self):
        """The ally the player can help right now, with the held-key action name."""
        s = self.s
        a, b = self.alex, self.bodi
        if a["pinned"] and math.hypot(a["x"] - s.px, a["z"] - s.pz) < 2.6:
            return "alex"
        if b["state"] == "down" and math.hypot(b["x"] - s.px, b["z"] - s.pz) < 3.0:
            return "bodi"
        return None

    def help_done(self, who):
        s = self.s
        if who == "alex":
            self.alex["pinned"] = False
            self.alex["freed"] = s.t
            self.alex["z"] -= ALEX_CRAWL
            s.say("ALEX", "Okay. Okay! I owe you. Twice.", 3.2)
        else:
            self.bodi["state"] = "up"
            self.bodi["hp"] = BODI_HP * 0.5
            s.say("BODI", "Don't make a thing of it.", 2.8)
