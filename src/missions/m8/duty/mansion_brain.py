"""Mission 8 Duty - Mansion 3D AI: Retardovici's guard across the estate, Bodi,
Alex, and Andrei M.'s animated death."""
import math
import random

from engine3d import POSES
from missions.m7 import raid_brain as RB

from . import mansion_set as MS
from . import mansion_world as W

KINDS = {
    "rifle": dict(hp=70, speed=3.2, burst=3, gap=1.6, dmg=5, rng=34.0, acc=0.56, hold=11.0),
    "breacher": dict(hp=105, speed=3.8, burst=2, gap=1.3, dmg=6, rng=18.0, acc=0.62, hold=5.0),
    "officer": dict(hp=95, speed=3.0, burst=4, gap=1.4, dmg=6, rng=36.0, acc=0.64, hold=12.0),
    "gunner": dict(hp=240, speed=2.2, burst=8, gap=2.2, dmg=5, rng=34.0, acc=0.5, hold=14.0),
}
ROUND_GAP = 0.12
TELEGRAPH = 0.36
FLINCH_S = 0.22
ALLY_HP = 110
ALLY_UP_S = 9.0
ALLY_HOLD = 1.6
ALLY_RAISE = 0.22
GF, FF = MS.GF, MS.FF
ROOF = 6.45

# (kind, x, z, route, delay[, y, perch])
WAVES = {
    1: (  # the gates and the drive
        ("rifle", -1.8, -30.0, [(-1.5, -32.0)], 0.0),
        ("rifle", 1.8, -27.0, [(1.5, -30.0)], 0.0),
        ("rifle", -6.0, -24.0, [(-5.5, -28.0)], 0.3),
        ("rifle", 6.0, -22.0, [(5.5, -26.0)], 0.6),
        ("breacher", 0.0, -18.0, [(0.0, -26.0)], 2.0),
        ("rifle", -11.0, -30.0, [(-9.5, -33.0)], 3.0),
        ("rifle", 11.0, -28.0, [(9.5, -32.0)], 3.5),
    ),
    2: (  # the forecourt: cars, the balconies, the portico roof, then the front doors
        ("rifle", -3.6, -12.0, [], 0.0),
        ("rifle", 3.6, -12.0, [], 0.0),
        ("rifle", -8.6, -8.0, [(-7.0, -12.0)], 0.4),
        ("rifle", 8.6, -8.5, [(7.0, -12.5)], 0.6),
        ("officer", 0.0, -4.0, [(0.0, -5.5)], 1.0),
        ("rifle", -8.4, -1.3, [], 0.0, FF, True),
        ("rifle", 8.4, -1.3, [], 0.2, FF, True),
        ("gunner", 0.0, -1.5, [], 1.5, ROOF, True),
        ("breacher", -0.6, 2.0, [(-0.6, -3.0), (-3.0, -7.0)], 9.0, GF),
        ("breacher", 0.6, 2.0, [(0.6, -3.0), (3.0, -7.0)], 9.4, GF),
        ("officer", 0.0, 4.0, [(0.0, -2.6), (0.0, -5.0)], 10.2, GF),
    ),
    3: (  # the grand hall, its galleries, the landing
        ("rifle", -5.5, 7.0, [], 0.0, GF),
        ("rifle", 5.5, 9.5, [], 0.0, GF),
        ("breacher", -4.0, 14.0, [(-3.0, 8.0)], 0.5, GF),
        ("breacher", 4.0, 15.0, [(3.0, 9.0)], 0.8, GF),
        ("officer", 0.0, 16.6, [], 1.2, GF),
        ("rifle", -10.4, 8.0, [(-10.4, 5.0)], 0.0, FF),
        ("rifle", 10.4, 12.0, [(10.4, 8.0)], 0.6, FF),
        ("rifle", -10.4, 18.0, [(-10.4, 13.0)], 1.4, FF),
        ("officer", 10.4, 22.0, [(10.4, 17.0)], 2.0, FF),
        ("rifle", 6.0, 30.0, [(6.0, 24.0), (5.0, 19.0)], 4.5, GF),
        ("gunner", 0.0, 27.3, [], 6.0, FF, True),
    ),
    4: (  # down the stairs, along the galleries, out of the rooms
        ("breacher", -1.5, 27.2, [(-1.5, 22.0), (-1.5, 17.5)], 0.0, FF),
        ("breacher", 1.5, 27.2, [(1.5, 22.0), (1.5, 17.5)], 0.5, FF),
        ("rifle", -10.4, 24.0, [(-10.4, 14.0)], 0.8, FF),
        ("rifle", 10.4, 24.0, [(10.4, 14.0)], 1.2, FF),
        ("officer", -6.0, 27.2, [], 1.5, FF),
        ("officer", 6.0, 27.2, [], 1.8, FF),
        ("gunner", -8.2, 27.3, [(-10.4, 22.0)], 3.0, FF),
        ("rifle", 8.2, 27.3, [(10.4, 22.0)], 3.5, FF),
    ),
    5: (  # the study: his personal guard, then the rooms either side
        ("officer", -2.4, 31.0, [], 0.0, FF),
        ("officer", 2.4, 31.0, [], 0.2, FF),
        ("gunner", 0.0, 34.6, [], 0.4, FF),
        ("breacher", 8.2, 33.0, [(8.2, 27.2), (4.0, 27.2)], 2.5, FF),
        ("breacher", -8.2, 33.0, [(-8.2, 27.2), (-4.0, 27.2)], 3.0, FF),
    ),
    6: (  # the helipad: the last of his might
        ("gunner", -6.6, 49.6, [], 0.0, FF),
        ("gunner", 6.6, 49.6, [], 0.5, FF),
        ("officer", -4.6, 41.0, [(-5.0, 40.0)], 0.2, FF),
        ("officer", 4.6, 41.0, [(5.0, 40.0)], 0.4, FF),
        ("rifle", -7.5, 51.0, [(-6.0, 49.0)], 6.0, FF),
        ("rifle", 7.5, 51.0, [(6.0, 48.6)], 9.0, FF),
        ("breacher", -2.0, 51.2, [(-7.6, 49.0), (-7.6, 41.0)], 13.0, FF),
        ("breacher", 2.0, 51.2, [(7.6, 49.0), (7.6, 41.0)], 14.0, FF),
        ("officer", 0.0, 51.4, [(0.0, 49.0)], 18.0, FF),
    ),
}
ALLY_AT = {0: (-40.5, 0.0), 1: (3.0, GF), 2: (15.0, GF)}
HOLD_Z = 15.0


# Andrei M.'s death beats (s after the trigger); mansion3d keys his fall to them
ANDREI_SHOT_S = 0.25      # the pistol goes off into the ceiling
ANDREI_HIT_S = 1.15       # his back meets the server rack
ANDREI_ZAP_S = 2.6        # the rack lets go of him


def andrei_timings(cause="misfire"):
    if cause == "player":
        return (0.65, 2.10, 2.70, 3.30)
    return (ANDREI_HIT_S, ANDREI_ZAP_S, 3.20, 3.80)


def _yaw(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def _clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v


def in_security_room(x, y, z):
    return -12.5 <= x <= -3.75 and 26.25 <= z <= 35.5 and abs(y - GF) < 0.6


class Brain:
    def __init__(self, scene, cp=0):
        self.s = scene
        self.rng = random.Random(808)
        self.enemies = []
        self.wave = 0
        self.slot = 0
        az_, ay_ = ALLY_AT[min(cp, 2)]
        b_at, a_at = (-1.8 if cp < 2 else -2.6, az_), (1.8 if cp < 2 else 2.6, az_)
        self.bodi = dict(x=b_at[0], z=b_at[1], y=ay_, yaw=0.0, hp=ALLY_HP, state="up",
                         up_at=0.0, moving=False, next=1.5, aim=-9.0, raised=-9.0,
                         slope=0.0, goal=None, gait=0.0, walk_k=0.0, burst=0)
        self.alex = dict(x=a_at[0], z=a_at[1], y=ay_, yaw=0.0, hp=ALLY_HP, state="up",
                         up_at=0.0, moving=False, next=1.5, aim=-9.0, raised=-9.0,
                         slope=0.0, goal=None, gait=0.0, walk_k=0.0, burst=0)
        ax, ay, az = MS.ANDREI_AT
        done_init = (cp >= 2)
        self.andrei = dict(
            x=ax, y=ay, z=az, yaw=90.0, hp=0.0 if done_init else 1.0,
            state="done" if done_init else "idle",
            intro_t=0.0, dead_t=-99.0 if done_init else 0.0,
            rack_hit=done_init, shot_fired=done_init,
            breaker_popped=done_init, collapse_snd=done_init,
            smoke_at=9e9 if done_init else -9.0, banter=3 if done_init else 0,
            cause="misfire", hit_zone="chest", hit_pos=None, hit_ray=None,
        )

    def add(self, kind, x, z, route, delay, wave, y=0.0, perch=False):
        k = KINDS[kind]
        self.slot += 1
        y = y if perch else self.s.world.surface_y(x, z, y)
        e = dict(kind=kind, x=x, z=z, y=y, perch=perch, yaw=180.0, hp=k["hp"], alive=True, live=False,
                 wave=wave, route=list(route), wp=0, spawn_at=self.s.t + delay,
                 next_burst=0.0, tele=0.0, left=0, round_at=0.0, hit_t=-9.0, dead_t=-9.0,
                 moving=False, slot=self.slot, mags=1, aim=-9.0, gait=0.0, held=0.0,
                 truck=None)
        self.enemies.append(e)
        return e

    def start_wave(self, n):
        self.wave = n
        for row in WAVES[n]:
            self.add(*row[:5], n, *row[5:])

    def pending(self, wave):
        return any(e["alive"] and e["wave"] == wave for e in self.enemies)

    def alive_count(self):
        return sum(1 for e in self.enemies if e["alive"])

    def revive_allies(self):
        for name, a in (("bodi", self.bodi), ("alex", self.alex)):
            if a["state"] == "down":
                a["state"] = "up"
                a["hp"] = ALLY_HP * 0.65

    def near_revive(self):
        s = self.s
        for name, a in (("bodi", self.bodi), ("alex", self.alex)):
            # same floor only: a body under the gallery must not block the landing's prompts
            if (a["state"] == "down" and abs(a["y"] - s.py) < 1.2
                    and math.hypot(a["x"] - s.px, a["z"] - s.pz) < 2.8):
                return name
        return None

    def help_done(self, who):
        a = self.bodi if who == "bodi" else self.alex
        a["state"] = "up"
        a["hp"] = ALLY_HP * 0.75
        self.s.say(who.upper(), "I'm up. Keep pushing." if who == "bodi" else "Back in it!", 2.4)

    def spheres(self, e):
        x, y, z = e["x"], e["y"], e["z"]
        return [
            ((x, y + 1.14, z), 0.46, False),
            ((x, y + 1.62, z), 0.25, True),
            ((x, y + 0.72, z), 0.35, False),
            ((x, y + 0.30, z), 0.32, False),
        ]

    def hurt_enemy(self, e, dmg, src=None, hit_ctx=None):
        if not e["alive"]:
            return False
        prev_hp = e["hp"]
        e["hp"] -= dmg
        e["hit_t"] = self.s.t
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

    def trigger_andrei_death(self, cause="misfire", hit_zone="chest", hit_pos=None, hit_ray=None):
        a = self.andrei
        if a["state"] in ("dying", "done"):
            return False
        a["state"] = "dying"
        a["hp"] = 0.0
        a["dead_t"] = self.s.t
        a["cause"] = cause
        a["hit_zone"] = hit_zone
        a["hit_pos"] = hit_pos
        a["hit_ray"] = hit_ray
        if cause == "player":
            a["shot_fired"] = True
            self.s.on_andrei_shot(a)
        self.s.kills += 1
        return True

    def _cands(self):
        out = []
        s = self.s
        if not s.dying:
            out.append(("player", s.px, s.pz, 1.0, s.pmoving, s.py + 1.25))
        for name, a in (("bodi", self.bodi), ("alex", self.alex)):
            if a["state"] == "up":
                out.append((name, a["x"], a["z"], 1.25, a["moving"], a["y"] + 1.2))
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
        a = self.bodi if name == "bodi" else self.alex
        if a["state"] != "up":
            return
        a["hp"] -= dmg
        if a["hp"] <= 0:
            a["state"] = "down"
            a["up_at"] = s.t + ALLY_UP_S
            s.say(name.upper(), "Down for a second - cover me!", 2.8)

    def _shoot(self, e, tgt, now):
        s = self.s
        k = KINDS[e["kind"]]
        name, tx, tz, _w, moving, ty = tgt
        d = math.hypot(tx - e["x"], tz - e["z"])
        yaw = math.radians(e["yaw"])
        muzzle = (e["x"] + math.sin(yaw) * 0.55, e["y"] + 1.35, e["z"] + math.cos(yaw) * 0.55)
        p = _clamp(k["acc"] - d * 0.012 - (0.12 if moving else 0.0), 0.14, 0.82)
        if self.rng.random() < p:
            end = (tx, ty, tz)
            self._damage(name, k["dmg"], (e["x"], e["z"]))
        else:
            end = (tx + (self.rng.random() - 0.5) * 2.0, ty + (self.rng.random() - 0.5) * 1.0,
                   tz + (self.rng.random() - 0.5) * 2.0)
        s.tracer(muzzle, end)
        s.flash(muzzle)
        e["aim"] = now

    def _steer(self, e, tx, tz, speed, dt, ty=None):
        goal_y = e["y"] if ty is None else ty
        wx, wz = tx, tz
        w = self.s.world
        door_locked = ((not w.front_open and (e["z"] > 0.0) != (tz > 0.0))
                       or (not w.terrace_open and e["y"] >= FF - 0.5 and (e["z"] > MS.HZ) != (tz > MS.HZ)))
        if not door_locked and (abs(goal_y - e["y"]) > 1.0 or not w.los3d(
            (e["x"], e["y"] + 1.0, e["z"]), (tx, goal_y + 1.0, tz)
        )):
            now = self.s.t
            path = e.get("nav_path")
            prev_g = e.get("nav_goal")
            if (path is None or now >= e.get("nav_at", 0.0)
                    or prev_g is None or math.hypot(prev_g[0] - tx, prev_g[2] - tz) > 1.2):
                path = w.nav().path((e["x"], e["y"], e["z"]), (tx, goal_y, tz))
                e["nav_path"] = path
                e["nav_goal"] = (tx, goal_y, tz)
                e["nav_at"] = now + (0.90 if not path else 0.45 + 0.05 * (e["slot"] % 5))
            while path and math.hypot(path[0][0] - e["x"], path[0][2] - e["z"]) < 0.55 and abs(path[0][1] - e["y"]) < 1.0:
                path.pop(0)
            if path:
                wx, wz = path[0][0], path[0][2]
        dx, dz = wx - e["x"], wz - e["z"]
        d = math.hypot(dx, dz)
        if d < 1e-4:
            return False
        ux, uz = dx / d, dz / d
        step = speed * dt
        for ang in (0, 35, -35, 75, -75, 120, -120):
            c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            vx, vz = ux * c - uz * sn, ux * sn + uz * c
            nx, nz = self.s.world.move(e["x"], e["z"], vx * step, vz * step, 0.34, False, e["y"])
            if math.hypot(nx - e["x"], nz - e["z"]) > step * 0.35:
                e["x"], e["z"] = nx, nz
                e["y"] = self.s.world.surface_y(nx, nz, e["y"])
                e["gait"] += step
                return True
        return False

    def _enemy(self, e, dt, now):
        if now < e["spawn_at"]:
            e["live"] = False
            return
        e["live"] = True
        k = KINDS[e["kind"]]
        tgt = self._pick(e)
        e["moving"] = False
        if tgt is None or now - e["hit_t"] < FLINCH_S:
            return
        d = math.hypot(tgt[1] - e["x"], tgt[2] - e["z"])
        los = d < k["rng"] and self.s.world.los3d(
            (e["x"], e["y"] + 1.35, e["z"]), (tgt[1], tgt[5], tgt[2]))
        if e["perch"]:
            if los:
                e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
                self._fire_ctl(e, tgt, now, k)
            return
        on_route = e["wp"] < len(e["route"])
        if on_route and los and d < 14.0:
            e["wp"] = len(e["route"])
            on_route = False
        if on_route:
            wx, wz = e["route"][e["wp"]]
            if math.hypot(wx - e["x"], wz - e["z"]) < 0.9:
                e["wp"] += 1
            elif self._steer(e, wx, wz, k["speed"] * 1.25, dt):
                e["moving"] = True
                e["yaw"] = _yaw(wx - e["x"], wz - e["z"])
        elif los:
            e["yaw"] = _yaw(tgt[1] - e["x"], tgt[2] - e["z"])
            busy = e["left"] > 0 or e["tele"] > 0.0
            if not busy:
                if d > k["hold"] + 2.5:
                    e["moving"] = self._steer(e, tgt[1], tgt[2], k["speed"], dt)
                elif d < 4.5:
                    away = (e["x"] - (tgt[1] - e["x"]), e["z"] - (tgt[2] - e["z"]))
                    e["moving"] = self._steer(e, away[0], away[1], k["speed"] * 0.7, dt)
            self._fire_ctl(e, tgt, now, k)
        else:
            tx, tz = self._around_heli(e, tgt[1], tgt[2])
            if self._steer(e, tx, tz, k["speed"], dt, ty=tgt[5] - 1.25):
                e["moving"] = True
                e["yaw"] = _yaw(tx - e["x"], tz - e["z"])

    def _around_heli(self, e, tx, tz):
        """Greedy steering jams on the parked helicopter: go round its nose or tail."""
        hx, hy, hz = MS.HELIPAD_AT
        if not self.s.world.heli_parked or e["y"] < hy - 1.0 or (e["z"] - hz) * (tz - hz) >= 0.0:
            return tx, tz
        if abs(e["x"] - hx) > 7.0 and abs(tx - hx) > 7.0:
            return tx, tz
        side = 1.0 if e["x"] + tx >= 2.0 * hx else -1.0
        return hx + side * 7.6, hz

    def _fire_ctl(self, e, tgt, now, k):
        if e["left"] > 0:
            if now >= e["round_at"]:
                self._shoot(e, tgt, now)
                e["left"] -= 1
                e["round_at"] = now + ROUND_GAP
                if e["left"] == 0:
                    e["next_burst"] = now + k["gap"] * (0.8 + 0.4 * self.rng.random())
        elif e["tele"] > 0.0:
            if now >= e["tele"]:
                e["tele"] = 0.0
                e["left"] = k["burst"]
                e["round_at"] = now
        elif now >= e["next_burst"]:
            if e["next_burst"] == 0.0:
                e["next_burst"] = now + 0.5 + self.rng.random()
            else:
                e["tele"] = now + TELEGRAPH
                e["moving"] = False

    def _aim_track(self, a, e, dt=1.0 / 60.0):
        want = _yaw(e["x"] - a["x"], e["z"] - a["z"])
        a["yaw"] = RB._yaw_mix(a.get("yaw", want), want, min(1.0, max(0.0, dt) * 11.0))
        d = max(1.0, math.hypot(e["x"] - a["x"], e["z"] - a["z"]))
        a["slope"] = _clamp(round((e["y"] - a["y"] - 0.2) / d, 1), -0.4, 0.4)
        return abs(RB._wrap(want - a["yaw"]))

    def _raise(self, a, e, now, dt=1.0 / 60.0):
        err = self._aim_track(a, e, dt)
        if now - a["aim"] > ALLY_HOLD:
            a["raised"] = now
        a["aim"] = now
        return now - a["raised"] >= ALLY_RAISE and err < 14.0

    def _ally_update(self, name, a, side_x, dt, now):
        a["moving"] = False
        if a["state"] == "down":
            if now >= a["up_at"]:
                a["state"] = "up"
                a["hp"] = ALLY_HP * 0.55
            return
        best, bd = None, 32.0
        for e in self.enemies:
            if not e["alive"] or not e["live"]:
                continue
            d = math.hypot(e["x"] - a["x"], e["z"] - a["z"])
            if d < bd and self.s.world.los3d((a["x"], a["y"] + 1.3, a["z"]), (e["x"], e["y"] + 1.2, e["z"])):
                best, bd = e, d
        if a["goal"] is not None:
            gx, gz = a["goal"]
            if math.hypot(gx - a["x"], gz - a["z"]) < 0.45:
                a["goal"] = None
            else:
                self._walk_ally(a, gx, gz, 4.2, dt, face=(best is None))
                if best is not None:
                    self._raise(a, best, now, dt)
                return
        hold = self.s.cp >= 2
        if best is None:
            if hold:
                # Bodi and Alex hold the grand hall below the stairs
                gx, gz = side_x * 2.6, HOLD_Z
                if math.hypot(gx - a["x"], gz - a["z"]) > 0.6:
                    self._walk_ally(a, gx, gz, 3.8, dt)
                else:
                    a["yaw"] = RB._yaw_mix(a.get("yaw", 0.0), 0.0, min(1.0, max(0.0, dt) * 6.0))
            elif self.s.py < 3.0:
                follow_z = max(MS.GATE_Z + 1.2, min(17.0, self.s.pz - 2.4))
                if follow_z < -36.0:
                    follow_x = _clamp(self.s.px + side_x * 1.4, -2.0, 2.0)
                else:
                    follow_x = _clamp(self.s.px + side_x * 2.1, -14.0, 14.0)
                if math.hypot(follow_x - a["x"], follow_z - a["z"]) > 3.2:
                    self._walk_ally(a, follow_x, follow_z, 4.0, dt)
            return
        if self._raise(a, best, now, dt) and now >= a["next"]:
            muzzle = a.get("muzzle") or (a["x"], a["y"] + 1.35, a["z"])
            dmg = 28.0 if name == "bodi" else 16.0
            if self.rng.random() < _clamp(0.76 - bd * 0.008, 0.25, 0.88):
                end = (best["x"], best["y"] + 1.1, best["z"])
                ray = (end[0] - muzzle[0], end[1] - muzzle[1], end[2] - muzzle[2])
                self.hurt_enemy(best, dmg, (a["x"], a["z"]), hit_ctx=dict(
                    is_head=False, hit_zone="chest", hit_pos=end, hit_ray=ray,
                    weapon="rifle", dmg=dmg, hit_dist=bd,
                ))
            else:
                end = (best["x"] + (self.rng.random() - 0.5) * 1.8, best["y"] + 1.1,
                       best["z"] + (self.rng.random() - 0.5) * 1.8)
            self.s.tracer(muzzle, end)
            self.s.flash(muzzle)
            a["next"] = now + (0.95 if name == "bodi" else 0.45)

    def _walk_ally(self, a, gx, gz, speed, dt, face=True):
        w = self.s.world
        if not w.los3d((a["x"], a["y"] + 1.0, a["z"]), (gx, a["y"] + 1.0, gz)):
            now = self.s.t
            path = a.get("nav_path")
            prev_g = a.get("nav_goal")
            if (path is None or now >= a.get("nav_at", 0.0)
                    or prev_g is None or math.hypot(prev_g[0] - gx, prev_g[1] - gz) > 1.2):
                path = w.nav().path((a["x"], a["y"], a["z"]), (gx, a["y"], gz))
                a["nav_path"] = path
                a["nav_goal"] = (gx, gz)
                a["nav_at"] = now + (0.90 if not path else 0.45)
            while path and math.hypot(path[0][0] - a["x"], path[0][2] - a["z"]) < 0.5:
                path.pop(0)
            if path:
                gx, gz = path[0][0], path[0][2]
        dx, dz = gx - a["x"], gz - a["z"]
        d = math.hypot(dx, dz)
        if d < 0.05:
            return
        step = min(d, speed * dt)
        ux, uz = dx / d, dz / d
        for ang in (0, 35, -35, 75, -75):
            c, sn = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            vx, vz = ux * c - uz * sn, ux * sn + uz * c
            nx, nz = self.s.world.move(a["x"], a["z"], vx * step, vz * step, 0.32, True, a["y"])
            if math.hypot(nx - a["x"], nz - a["z"]) > step * 0.35:
                a["x"], a["z"] = nx, nz
                a["y"] = self.s.world.surface_y(nx, nz, a["y"])
                a["moving"] = True
                if face:
                    a["yaw"] = RB._yaw_mix(a.get("yaw", 0.0), _yaw(dx, dz), min(1.0, max(0.0, dt) * 9.0))
                a["gait"] += step
                return

    def _andrei_update(self, now):
        a = self.andrei
        if a["state"] == "idle":
            if (in_security_room(self.s.px, self.s.py, self.s.pz)
                    and self.s.world.los3d(
                        (self.s.px, self.s.py + 1.45, self.s.pz),
                        (a["x"], a["y"] + 1.4, a["z"]),
                    )):
                a["state"] = "intro"
                a["intro_t"] = now
                self.s.say("ANDREI M.", "Stop! Nobody touches the President's servers - I have admin privileges!", 2.2)
        elif a["state"] == "intro":
            a["yaw"] = _yaw(self.s.px - a["x"], self.s.pz - a["z"])
            if now - a["intro_t"] >= 2.2 and a["banter"] == 0:
                a["banter"] = -1
                self.s.say("ANDREI M.", "And a gun! I have a gun! I have never fired it, but -", 1.9)
            if now - a["intro_t"] >= 3.9:
                self.trigger_andrei_death(cause="misfire")
        elif a["state"] in ("dying", "done"):
            age = now - a["dead_t"]
            hit_s, zap_s, _sit_s, down_s = andrei_timings(a.get("cause", "misfire"))
            if a["state"] == "dying":
                if a.get("cause") != "player" and age >= ANDREI_SHOT_S and not a["shot_fired"]:
                    a["shot_fired"] = True
                    m = (a["x"] + 0.15, a["y"] + 1.55, a["z"])
                    self.s.tracer(m, (a["x"] + 0.3, a["y"] + 4.05, a["z"] - 0.2))
                    self.s.flash(m)
                    self.s._snd("pistol_shot", self.s._pan(m[0], m[2]))
                    self.s.on_andrei_ceiling_shot(a)
                    self.s.slowmo_until = self.s.t + 0.9
                if age >= hit_s and not a["rack_hit"]:
                    a["rack_hit"] = True
                    a["zap"] = now
                    self.s.on_andrei_rack_hit()
                # the rack arcs into him until the breaker blows
                if a["rack_hit"] and age < zap_s and now - a.get("zap", 0.0) > 0.11:
                    a["zap"] = now
                    rx, ry, rz = MS.ANDREI_RACK_AT
                    p = (rx + 0.2, ry + 0.6 + self.rng.random() * 1.4, rz + (self.rng.random() - 0.5) * 1.0)
                    self.s.sparks.append((now, p))
                    self.s._snd("elec_arc", self.s._pan(rx, rz))
                    if self.rng.random() < 0.45:
                        self.s.flashes.append((now, p))
                if age >= zap_s and not a.get("breaker_popped"):
                    a["breaker_popped"] = True
                    self.s.on_andrei_breaker_pop()
                if age >= down_s - 0.15 and not a.get("collapse_snd"):
                    a["collapse_snd"] = True
                    self.s._snd("body_fall", self.s._pan(a["x"], a["z"]),
                                math.hypot(a["x"] - self.s.px, a["z"] - self.s.pz))
                if age >= zap_s + 0.6 and a["banter"] <= 0:
                    a["banter"] = 1
                    self.s.say("BODI", "Should we have waited for him to finish?", 2.4)
                if age >= zap_s + 1.6 and a["banter"] == 1:
                    a["banter"] = 2
                    self.s.say("ALEX", "No.", 1.6)
                if age >= zap_s + 2.6 and a["banter"] == 2:
                    a["banter"] = 3
                    self.s.say("BIRIBEL", "Payroll's closed. Stairs - move.", 2.4)
                    a["state"] = "done"
            if a["rack_hit"] and age <= down_s + 6.0:
                gap = 0.14 if age < zap_s else 0.34
                if now - a.get("smoke_at", -9.0) >= gap:
                    a["smoke_at"] = now
                    self.s.on_andrei_smoke(a, hot=(age < zap_s + 1.0))

    def update(self, dt):
        now = self.s.t
        for e in self.enemies:
            if e["alive"]:
                self._enemy(e, dt, now)
        self._ally_update("bodi", self.bodi, -1.0, dt, now)
        self._ally_update("alex", self.alex, 1.0, dt, now)
        for a in (self.bodi, self.alex):
            k = a["walk_k"]
            a["walk_k"] = min(1.0, k + dt * 5.0) if a["moving"] else max(0.0, k - dt * 4.0)
        self._andrei_update(now)