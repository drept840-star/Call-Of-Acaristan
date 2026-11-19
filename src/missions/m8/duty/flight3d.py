"""Mission 8 Duty - Phase 4: Last Flight (3D door-gunner chase).

Maru flies, Biribel works the starboard door LMG.  Five checkpointed
sections: the mansion lawn (an orbit over the estate set), then three legs up
the chase set's road after Retardovici's helicopter, and Ucilev's gunship,
whose duel always ends in the scripted shootdown.

Controls: mouse aims the mount (yaw/pitch limits), hold LMB to fire (the barrel
overheats), F pops flares (limited, refilled per section).
Fails: hull at zero, or Retardovici out of range too long.  Either restarts
the section (``STATE.m8_flight_cp``).
"""
import math
import random

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette, font_terminal, font_terminal_small
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import POSES, clamp
from engine3d.core import m_apply, m_mul, rot_x, rot_y, v_add
from missions.m6 import hud3d as H
from missions.m7 import raid3d as R
from missions.m7 import raid_brain as RB
from missions.m7 import raid_hud as RH
from missions.m8.revenge import chase_set as CS
from missions.m8.revenge import trap3d as T

from . import mansion_set as MS
from . import mansion_world as MW

SENS = 0.11
YAW_LIM = 72.0
PITCH_LIM = (-58.0, 14.0)
FIRE_GAP = 1.0 / 11.0
HEAT_SHOT = 0.034
HEAT_COOL = 0.42
FLARES = 3
FLARE_S = 1.7
ROCKET_V = 34.0
ROCKET_DMG = 18.0
HULL = 100.0
HELI_V = 12.0
ALT = 26.0
ESCAPE_R = 230.0
ESCAPE_S = 8.0
LAWN_C = (0.0, 0.0, 12.0)
LAWN_R = 48.0

# (title, set, z0, z1, seconds); road sections run z0 -> z1 at HELI_V.
SECTIONS = (
    ("MANSION LAWN", "estate", 0.0, 0.0, 0.0),
    ("CURFEW ROAD", "road", 80.0, 740.0, 55.0),
    ("THE RADIO MAST", "road", 740.0, 1340.0, 50.0),
    ("ROUTE 12", "road", 1340.0, 2060.0, 60.0),
    ("UCILEV", "road", 2060.0, 2540.0, 40.0),
)
LAWN_SPAWNS = (
    ("guard", -3.0, -11.0), ("guard", 3.0, -11.0), ("guard", -9.5, -14.0),
    ("guard", 9.5, -14.0), ("guard", 16.0, -2.0), ("guard", -14.0, -4.0),
    ("aa", -13.0, -19.0), ("aa", 13.0, -19.0),
)
# (kind, z, x offset from the road); spawned as the heli closes in.
ROAD_SPAWNS = {
    1: (("rpg", 200, 14), ("guard", 220, -9), ("guard", 260, 8), ("aa", 330, -18),
        ("rpg", 420, -16), ("guard", 470, 10), ("rpg", 560, 20), ("aa", 640, 16)),
    2: (("gunship", 820, 0), ("rpg", 900, -14), ("guard", 980, 9), ("gunship", 1080, 0),
        ("rpg", 1190, 18), ("aa", 1260, -15)),
    3: (("jeep", 1420, 0), ("jeep", 1450, 0), ("rpg", 1520, 12), ("jeep", 1620, 0),
        ("aa", 1700, -16), ("jeep", 1790, 0), ("rpg", 1880, -14), ("jeep", 1950, 0)),
    4: (),
}
HP = {"guard": 28.0, "rpg": 28.0, "aa": 160.0, "jeep": 110.0, "gunship": 240.0}
SPHERE = {"guard": ((1.1, 0.85),), "rpg": ((1.1, 0.85),), "aa": ((0.9, 2.1),),
          "jeep": ((0.9, 2.1),), "gunship": ((1.0, 3.2),)}
CALLOUTS = {
    "rocket_l": "Rocket, left!", "rocket_r": "Rocket, right!", "hit": "I'm hit, I'm fine, keep shooting!",
    "light": "Searchlight - kill it!", "hold": "Hold on!",
}


def _road_pt(z, xo=0.0, y=0.0):
    return (CS.road_x(z) + xo, y, z)


class FlightScene:
    set_paused = R.RaidScene.set_paused
    _grab = R.RaidScene._grab
    _snd = R.RaidScene._snd
    say = R.RaidScene.say
    _draw_fx = T.TrapScene._draw_fx

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.t = 0.0
        self._setup(0)

    # --- lifecycle -------------------------------------------------------------

    def begin(self):
        self.t = 0.0
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_flight_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m8_flight_cp", 0) or 0))
        self._grab(True)

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_flight_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_flight_done(result)

    def _setup(self, cp):
        self.cp = cp = max(0, min(len(SECTIONS) - 1, cp))
        STATE.m8_flight_cp = cp
        self.sec_t = 0.0
        self.hull = HULL
        self.heat = 0.0
        self.overheat = False
        self.flares = FLARES
        self.flare_at = -9.0
        self.firing = False
        self.last_fire = -9.0
        self.gy, self.gp = 0.0, -18.0
        self.shake = 0.0
        self.hit_mark = -9.0
        self.hurt = 0.0
        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.targets = []
        self.rockets = []
        self.booms = []
        self.world = None
        if SECTIONS[cp][1] == "estate":
            # the house blocks shots and rockets both ways over the lawn
            self.world = MW.World()
            self.world.front_open = self.world.study_open = self.world.terrace_open = True
            self.world.heli_parked = False
        self.tracers, self.sparks, self.impacts, self.flashes = [], [], [], []
        self.lines = []
        self.dmg_marks = []
        self.spawned = set()
        self.rdist = 95.0
        self.escape = 0.0
        self.tail_hp = 320.0
        self.r_down = -1.0
        self.ucilev = None
        self.shootdown = -1.0
        self.kill_shot = False
        self.kills = 0
        self.rng = random.Random(4100 + cp)
        self._said = set()
        title = SECTIONS[cp][0]
        self.cp_toast = self.t
        if cp == 0:
            for i, (kind, x, z) in enumerate(LAWN_SPAWNS):
                self._spawn(kind, (x, 0.0, z), i)
            self.say("MARU", "Hold on! Lawn's crawling - two AA trucks by the gate!", 3.4)
        elif cp == 1:
            self.say("MARU", "There he is. Don't lose him, Biribel.", 3.0)
        elif cp == 2:
            self.say("MARU", "Guard birds coming off the mast!", 3.0)
        elif cp == 3:
            self.say("MARU", "Route 12. Take his tail rotor - put him down!", 3.4)
        else:
            self.ucilev = self._spawn("gunship", self._heli_pos(), 99)
            self.ucilev.update(hp=900.0, ucilev=True, ang=0.0)
            self.say("MARU", "Gunship out of the fog - UCILEV. Brace!", 3.4)
        self._title = title

    # --- geometry --------------------------------------------------------------

    def _heli_pos(self, t=None):
        t = self.sec_t if t is None else t
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        if kind == "estate":
            a = math.radians(200.0 + t * 7.5)
            lift = clamp(t / 6.0, 0.0, 1.0)
            return (LAWN_C[0] + math.sin(a) * LAWN_R, 2.0 + (ALT - 8.0) * lift,
                    LAWN_C[2] + math.cos(a) * LAWN_R)
        z = min(z1, z0 + t * HELI_V)
        return (CS.road_x(z) - 9.0 + 6.0 * math.sin(t * 0.21), ALT + 3.0 * math.sin(t * 0.33), z)

    def _heli_yaw(self):
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        if kind == "estate":
            return (200.0 + self.sec_t * 7.5 + 90.0) % 360.0     # tangent of the orbit
        return CS.road_yaw(self._heli_pos()[2])

    def mount_yaw(self):
        """World yaw the door mount points along (the gun swings +-YAW_LIM)."""
        if SECTIONS[self.cp][1] == "estate":
            hx, _, hz = self._heli_pos()
            return R._yaw(LAWN_C[0] - hx, LAWN_C[2] - hz)
        return self._heli_yaw() + 38.0                         # crabbed: door faces forward-right

    def eye(self):
        hx, hy, hz = self._heli_pos()
        my = math.radians(self.mount_yaw())
        s = self.shake
        jit = (math.sin(self.t * 41.0) * 0.05 * s, math.sin(self.t * 37.0 + 1.0) * 0.05 * s)
        return (hx - math.sin(my) * 0.4 + jit[0], hy + 0.9 + jit[1], hz - math.cos(my) * 0.4)

    def aim_dir(self):
        return R._fwd(self.mount_yaw() + self.gy, self.gp)

    def retardovici_pos(self):
        if SECTIONS[self.cp][1] != "road" or self.cp >= 4:
            return None
        hx, hy, hz = self._heli_pos()
        z = hz + self.rdist
        y = ALT + 4.0
        if self.r_down >= 0.0:
            k = self.t - self.r_down
            y = max(4.0, y - k * 3.2)
            z += k * 6.0
        return (CS.road_x(z) + 4.0 * math.sin(self.t * 0.4), y, z)

    def retardovici_yaw(self):
        p = self.retardovici_pos()
        return CS.road_yaw(p[2]) + (self.t - self.r_down) * 140.0 if (p and self.r_down >= 0.0) \
            else (CS.road_yaw(p[2]) if p else 0.0)

    def tail_point(self):
        p = self.retardovici_pos()
        if p is None:
            return None
        _b, _m, _t, info = CS.helicopter_parts()
        return CS._xf(info["tail_hub"], p, self.retardovici_yaw(), 0.0, 0.0)

    # --- targets ---------------------------------------------------------------

    def _spawn(self, kind, pos, key):
        e = dict(kind=kind, x=pos[0], y=pos[1], z=pos[2], hp=HP[kind], alive=True, dead_t=-9.0,
                 next=self.t + 1.2 + self.rng.random() * 2.0, yaw=0.0, key=key, ang=0.0,
                 ucilev=False, light=kind == "aa")
        if kind == "gunship":
            e["off"] = (self.rng.choice((-1.0, 1.0)) * 34.0, 8.0, 46.0)
        self.targets.append(e)
        self.spawned.add(key)
        return e

    def _road_spawns(self):
        hz = self._heli_pos()[2]
        for i, (kind, z, xo) in enumerate(ROAD_SPAWNS.get(self.cp, ())):
            key = (self.cp, i)
            if key in self.spawned or z - hz > 170.0:
                continue
            if kind == "gunship":
                self._spawn(kind, self._heli_pos(), key)
                self.say("MARU", "Guard bird, right side!", 2.6)
            elif kind == "jeep":
                e = self._spawn(kind, _road_pt(z), key)
                e["v"] = 9.0
            else:
                self._spawn(kind, _road_pt(z, xo), key)

    def spheres(self, e):
        if e["kind"] in ("guard", "rpg"):
            return [((e["x"], e["y"] + 1.1, e["z"]), 0.85)]
        if e["kind"] == "gunship":
            return [((e["x"], e["y"] + 1.0, e["z"]), 3.2)]
        return [((e["x"], e["y"] + 0.9, e["z"]), 2.1)]

    def _threats(self):
        hp = self._heli_pos()
        return sum(1 for e in self.targets if e["alive"] and e["kind"] in ("aa", "gunship", "rpg")
                   and math.dist((e["x"], e["y"], e["z"]), hp) < 200.0)

    def hurt_target(self, e, dmg):
        if not e["alive"]:
            return
        e["hp"] -= dmg
        if e["ucilev"]:
            e["hp"] = max(e["hp"], 300.0)       # the story needs him in the air
            return
        if e["hp"] <= 0.0:
            e["alive"] = False
            e["dead_t"] = self.t
            self.kills += 1
            if e["kind"] != "guard" and e["kind"] != "rpg":
                self.booms.append((self.t, (e["x"], e["y"] + 1.0, e["z"]), 6.0 if e["kind"] == "gunship" else 4.0))
                self._snd("barrel_boom", 0.0, math.dist((e["x"], e["y"], e["z"]), self._heli_pos()))
            else:
                self._snd("enemy_down", 30.0)

    def hurt_hull(self, dmg, src=None):
        if self.dying or self.shootdown >= 0.0:
            return
        self.hull -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 30.0)
        self.shake = min(1.6, self.shake + dmg / 18.0)
        self._snd("hull_hit")
        if src is not None:
            ex, _, ez = self.eye()
            bearing = R._wrap(R._yaw(src[0] - ex, src[2] - ez) - (self.mount_yaw() + self.gy))
            self.dmg_marks.append((self.t, -bearing))
        if self.hull <= 30.0 and "hit" not in self._said:
            self._said.add("hit")
            self.say("MARU", CALLOUTS["hit"], 2.8)
        if self.hull <= 0.0:
            self.dying = True
            self.death_t = 0.0
            self.death_msg = "MARU'S BIRD IS DOWN  -  AGAIN FROM THE SECTION"
            self.firing = False
            self._snd("crash")

    def _fire_rocket(self, src):
        self.rockets.append(dict(p=src, t0=self.t, alive=True, unstoppable=False, trail=[]))
        self._snd("rocket")
        mx = self.mount_yaw() + self.gy
        side = R._wrap(R._yaw(src[0] - self._heli_pos()[0], src[2] - self._heli_pos()[2]) - mx)
        if self.t - getattr(self, "_rocket_call", -9.0) > 3.0:
            self._rocket_call = self.t
            self.say("MARU", CALLOUTS["rocket_l" if side < 0 else "rocket_r"], 2.0)

    # --- update ----------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        self.t += dt
        self._snd("bed", "flight")
        self._snd("update", dt)
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.6:
                self._setup(self.cp)
            return
        self.sec_t += dt
        self.shake = max(0.0, self.shake - dt * 1.8)
        self.hurt = max(0.0, self.hurt - dt * 1.2)
        if self.overheat:
            self.heat = max(0.0, self.heat - dt * HEAT_COOL)
            self.overheat = self.heat > 0.3
        elif not self.firing:
            self.heat = max(0.0, self.heat - dt * HEAT_COOL)
        if self.firing and not self.overheat and self.shootdown < 0.0:
            self._fire()
        if SECTIONS[self.cp][1] == "road":
            self._road_spawns()
        self._targets_update(dt)
        self._rockets_update(dt)
        self._chase_update(dt)
        self._section_update()
        now = self.t
        if self.tracers:
            self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        if self.sparks:
            self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        if self.impacts:
            self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        if self.flashes:
            self.flashes = [x for x in self.flashes if now - x[0] < 0.2]
        if self.booms:
            self.booms = [x for x in self.booms if now - x[0] < 1.4]
        if self.dmg_marks:
            self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return
        self.last_fire = self.t
        self.heat = min(1.0, self.heat + HEAT_SHOT)
        if self.heat >= 1.0:
            self.overheat = True
            self.say("MARU", "Barrel's cooking - let it breathe!", 2.0)
        self.shake = min(1.0, self.shake + 0.12)
        self._snd("lmg_shot")
        o = self.eye()
        spread = 0.5 + 1.4 * self.heat
        d = R._fwd(self.mount_yaw() + self.gy + self.rng.uniform(-spread, spread),
                   self.gp + self.rng.uniform(-spread, spread))
        best = 400.0
        if d[1] < -1e-6:
            best = min(best, -o[1] / d[1])
        if self.world is not None:
            best = min(best, self.world.ray_hit(o, d, best))
        hit = None
        for e in self.targets:
            if not e["alive"]:
                continue
            for c, rad in self.spheres(e):
                h = RB._ray_sphere(o, d, c, rad)
                if h is not None and h < best:
                    best, hit = h, ("t", e)
        for rk in self.rockets:
            if rk["alive"] and not rk["unstoppable"]:
                h = RB._ray_sphere(o, d, rk["p"], 1.6)
                if h is not None and h < best:
                    best, hit = h, ("r", rk)
        tail = self.tail_point() if self.cp == 3 and self.r_down < 0.0 else None
        if tail is not None:
            h = RB._ray_sphere(o, d, tail, 2.2)
            if h is not None and h < best:
                best, hit = h, ("tail", None)
        end = (o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best)
        mz = (o[0] + d[0] * 1.2, o[1] - 0.25 + d[1] * 1.2, o[2] + d[2] * 1.2)
        self.tracers.append((self.t, mz, end, (255, 226, 160)))
        if hit is None:
            if best < 399.0:
                self.impacts.append((self.t, end, "dust"))
            return
        self.hit_mark = self.t
        self.sparks.append((self.t, end))
        if hit[0] == "t":
            self.hurt_target(hit[1], 14.0)
        elif hit[0] == "r":
            hit[1]["alive"] = False
            self.booms.append((self.t, hit[1]["p"], 2.5))
        else:
            self.tail_hp -= 14.0
            if self.tail_hp <= 0.0:
                self.r_down = self.t
                self._snd("crash")
                self.say("MARU", "He's going down! He's going -", 3.0)

    def _targets_update(self, dt):
        hp = self._heli_pos()
        hz = hp[2]
        for e in self.targets:
            if not e["alive"]:
                continue
            kind = e["kind"]
            if kind == "jeep":
                e["z"] += e["v"] * dt
                e["x"] = CS.road_x(e["z"])
                e["yaw"] = CS.road_yaw(e["z"])
            elif kind == "gunship":
                if e["ucilev"]:
                    e["ang"] += dt * 0.55
                    rad = 38.0
                    e["x"] = hp[0] + 30.0 + math.sin(e["ang"]) * rad * 0.6
                    e["y"] = hp[1] + 4.0 + math.sin(e["ang"] * 1.7) * 3.0
                    e["z"] = hp[2] + 34.0 + math.cos(e["ang"]) * rad * 0.4
                else:
                    ox, oy, oz = e["off"]
                    e["x"] += (hp[0] + ox + math.sin(self.t * 0.6 + e["key"][1]) * 8.0 - e["x"]) * min(1.0, dt * 0.8)
                    e["y"] += (hp[1] + oy - e["y"]) * min(1.0, dt * 0.8)
                    e["z"] += (hp[2] + oz - e["z"]) * min(1.0, dt * 0.8)
                e["yaw"] = R._yaw(hp[0] - e["x"], hp[2] - e["z"])
            else:
                e["yaw"] = R._yaw(hp[0] - e["x"], hp[2] - e["z"])
            if SECTIONS[self.cp][1] == "road" and e["z"] < hz - 60.0 and not e["ucilev"]:
                e["alive"] = False                          # left behind
                continue
            if self.t < e["next"] or self.shootdown >= 0.0:
                continue
            d = math.dist((e["x"], e["y"], e["z"]), hp)
            if d > 190.0:
                e["next"] = self.t + 1.0
                continue
            src = (e["x"], e["y"] + (1.4 if kind in ("guard", "rpg") else 1.6), e["z"])
            if self.world is not None and not self.world.los3d(src, (hp[0], hp[1] + 1.0, hp[2])):
                e["next"] = self.t + 0.4
                continue
            if kind in ("rpg", "aa") or (kind == "gunship" and self.rng.random() < 0.35):
                self._fire_rocket(src)
                e["next"] = self.t + (5.5 if kind == "rpg" else 4.2) + self.rng.random() * 2.0
                continue
            dmg = {"guard": 2.0, "jeep": 3.0, "gunship": 4.5}.get(kind, 2.0)
            acc = clamp(0.6 - d * 0.0025, 0.15, 0.6)
            for i in range(3):
                miss = self.rng.random() > acc
                end = (hp[0] + (self.rng.uniform(-4, 4) if miss else 0.0), hp[1] + 1.0,
                       hp[2] + (self.rng.uniform(-4, 4) if miss else 0.0))
                self.tracers.append((self.t + i * 0.05, src, end, (255, 200, 130)))
                if not miss:
                    self.hurt_hull(dmg, src)
            self.flashes.append((self.t, src))
            self._snd("guard_shot", 0.0, d)
            e["next"] = self.t + 1.6 + self.rng.random() * 1.4

    def _rockets_update(self, dt):
        hp = self._heli_pos()
        tgt = (hp[0], hp[1] + 1.0, hp[2])
        flare_on = self.t - self.flare_at < FLARE_S
        for rk in self.rockets:
            if not rk["alive"]:
                continue
            p = rk["p"]
            dx, dy, dz = tgt[0] - p[0], tgt[1] - p[1], tgt[2] - p[2]
            d = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            if flare_on and not rk["unstoppable"] and d < 160.0:
                rk["alive"] = False
                self.booms.append((self.t, p, 2.0))
                continue
            step = min(d, ROCKET_V * (2.2 if rk["unstoppable"] else 1.0) * dt)
            rk["dir"] = (dx / d, dy / d, dz / d)
            rk["p"] = (p[0] + dx / d * step, p[1] + dy / d * step, p[2] + dz / d * step)
            if not rk["trail"] or math.dist(rk["trail"][-1], p) > 1.4:
                rk["trail"] = (rk["trail"] + [p])[-9:]
            if self.world is not None and not self.world.los3d(p, rk["p"]):
                rk["alive"] = False
                self.booms.append((self.t, p, 3.0))
                continue
            if d < 2.5 or self.t - rk["t0"] > 9.0:
                rk["alive"] = False
                if rk["unstoppable"]:
                    self.booms.append((self.t, rk["p"], 3.0))
                    self._begin_crash()
                elif d < 2.5:
                    self.booms.append((self.t, rk["p"], 3.0))
                    self.hurt_hull(ROCKET_DMG, p)
        self.rockets = [rk for rk in self.rockets if rk["alive"]]

    def _chase_update(self, dt):
        if SECTIONS[self.cp][1] != "road" or self.cp >= 4 or self.r_down >= 0.0:
            self.escape = 0.0
            return
        if self._threats() > 0:
            self.rdist = min(320.0, self.rdist + 1.7 * dt)
        else:
            self.rdist = max(70.0, self.rdist - 3.0 * dt)
        if self.rdist > ESCAPE_R:
            self.escape += dt
            if self.escape >= ESCAPE_S:
                self.dying = True
                self.death_t = 0.0
                self.death_msg = "RETARDOVICI GOT AWAY  -  AGAIN FROM THE SECTION"
                self.firing = False
        else:
            self.escape = max(0.0, self.escape - dt * 2.0)

    def _section_update(self):
        name, kind, z0, z1, dur = SECTIONS[self.cp]
        nxt = False
        if self.cp == 0:
            aa_left = any(e["alive"] and e["kind"] == "aa" for e in self.targets)
            nxt = self.sec_t > 18.0 and not aa_left
        elif self.cp == 3:
            if self.r_down >= 0.0 and self.t - self.r_down > 3.4:
                nxt = True
            elif self.sec_t >= dur and self.r_down < 0.0:
                self.dying = True
                self.death_t = 0.0
                self.death_msg = "HE CROSSED THE RIDGE  -  AGAIN FROM ROUTE 12"
                return
            if self.sec_t > 26.0 and "where" not in self._said:
                self._said.add("where")
                self.say("MARU", "This is where they died, isn't it?", 3.2)
        elif self.cp == 4:
            if self.shootdown < 0.0 and not self.kill_shot and (self.sec_t > 30.0 or (self.ucilev and self.ucilev["hp"] <= 300.0
                                                                and self.sec_t > 14.0)):
                self._ucilev_kill_shot()
            if self.shootdown >= 0.0 and self.t - self.shootdown > 2.8:
                self.finish("win")
            return
        elif self.sec_t >= dur:
            nxt = True
        if nxt:
            self._setup(self.cp + 1)

    def _ucilev_kill_shot(self):
        self.kill_shot = True
        u = self.ucilev
        src = (u["x"], u["y"] + 1.2, u["z"]) if u else self._heli_pos()
        self.rockets.append(dict(p=src, t0=self.t, alive=True, unstoppable=True, trail=[]))
        self.flares = 0
        self._snd("rocket")
        self.say("MARU", "No flares - hold on, HOLD ON!", 2.6)

    def _begin_crash(self):
        self.shootdown = self.t
        self.firing = False
        self.shake = 2.0
        self._snd("crash")

    # --- input -----------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused or self.dying:
            return
        if event.type == pygame.MOUSEMOTION:
            dx, dy = event.rel
            self.gy = clamp(self.gy + dx * SENS, -YAW_LIM, YAW_LIM)
            self.gp = clamp(self.gp - dy * SENS, *PITCH_LIM)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.firing = True
        elif event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.firing = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_f:
            self.pop_flares()

    def pop_flares(self):
        if self.flares <= 0 or self.t - self.flare_at < 1.5 or self.shootdown >= 0.0:
            return False
        self.flares -= 1
        self.flare_at = self.t
        self._snd("smoke_hiss")
        return True

    # --- draw ------------------------------------------------------------------

    def _frame(self, eye, tgt, fov, tm):
        if SECTIONS[self.cp][1] == "estate":
            r = MS.frame(eye, tgt, fov, t=int(tm))
            del _w.LAST[:]
            MS.draw_dynamic_props(r, tm, cams_alive=False, front_open=True, study_open=True)
            return r
        r = CS.frame(eye, tgt, fov, t=int(tm), look="night")
        del _w.LAST[:]
        return r

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        eye = self.eye()
        d = self.aim_dir()
        if self.shootdown >= 0.0:
            k = self.t - self.shootdown
            yaw = self.mount_yaw() + self.gy + k * k * 120.0
            d = R._fwd(yaw, self.gp - 12.0 * k)
        elif self.dying:
            d = R._fwd(self.mount_yaw() + self.gy + self.death_t * 160.0, self.gp - 10.0 * self.death_t)
        tgt = (eye[0] + d[0] * 10.0, eye[1] + d[1] * 10.0, eye[2] + d[2] * 10.0)
        r = self._frame(eye, tgt, 60.0, tm)
        self._draw_targets(r, tm)
        rp = self.retardovici_pos()
        if rp is not None:
            CS.put_helicopter(r, rp, self.retardovici_yaw(), -6.0, 0.0, (tm * 1.4) % 360.0,
                              (tm * 2.2) % 360.0 if self.r_down < 0.0 else 0.0, burned=self.r_down >= 0.0)
            if self.cp == 3 and self.r_down < 0.0:
                tp = self.tail_point()
                r.add_sprite(tp, _fx.glow((255, 120, 90), 0.9, int(tm), pulse=0.5), layer=_fx.FX_LAYER)
        for rk in self.rockets:
            self._draw_rocket(r, rk, tm)
        for t0, p, rad in self.booms:
            r.add_sprite(p, _fx.flash((self.t - t0) * 1000.0, radius_m=rad, dur_ms=1400),
                         layer=_fx.FX_LAYER)
        if self.t - self.flare_at < FLARE_S:
            hp = self._heli_pos()
            age = self.t - self.flare_at
            for i in range(6):
                fp = (hp[0] + (i - 2.5) * 2.2 * age, hp[1] - 6.0 * age, hp[2] - 3.0 * age * (i % 3))
                r.add_sprite(fp, _fx.glow((255, 236, 200), 0.8, int(tm), flicker=0.6, seed=i),
                             layer=_fx.FX_LAYER)
        self._draw_fx(r, tm)
        self._draw_gun(r, eye, tm)
        pr = r
        CS.present(pr, surface) if SECTIONS[self.cp][1] == "road" else MS.present(pr, surface)
        draw_vignette(surface)
        self._hud(surface)

    def _draw_rocket(self, r, rk, tm):
        """The chase missile mesh nosed along its flight, exhaust and a smoke trail."""
        p = rk["p"]
        dx, dy, dz = rk.get("dir", (0.0, 0.0, 1.0))
        yaw = math.degrees(math.atan2(dx, dz))
        pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
        CS.put(r, "rocket", CS.rocket, p, yaw, pitch)
        tail = CS._xf((0.0, 0.0, -CS.ROCKET_LEN * 0.5), p, yaw, pitch)
        r.add_sprite(tail, _fx.glow((255, 150, 70), 0.45, int(tm), flicker=0.45, core=(255, 236, 180),
                                    intensity=1.1, max_px=24), layer=_fx.FX_LAYER)
        n = len(rk["trail"])
        for i, q in enumerate(rk["trail"]):
            k = (i + 1) / n
            r.add_sprite(q, _fx.haze((200, 196, 188), 0.8 + 1.4 * (1.0 - k), int(tm), seed=i,
                                     intensity=0.95 * k), layer=_fx.FX_LAYER)

    def _draw_targets(self, r, tm):
        for e in self.targets:
            dead = not e["alive"]
            if dead and self.t - e["dead_t"] > 6.0:
                continue
            kind = e["kind"]
            pos = (e["x"], e["y"], e["z"])
            if kind in ("guard", "rpg"):
                pose = dict(POSES["dead_back"]) if dead else dict(POSES["ready"])
                if kind == "rpg" and not dead:
                    pose.update(rsh_p=150.0, rel=60.0, lsh_p=120.0, lel=40.0)
                _w.actor(r, ("guard", "heavy" if kind == "rpg" else "rifle"), pose, pos, e["yaw"],
                         int(tm), seed=200 + hash(str(e["key"])) % 50, amp=0.3,
                         rifle_on=not dead and kind == "guard", flags=("os12",))
            elif kind in ("aa", "jeep"):
                CS.put(r, ("m8d_jeep", dead), lambda dd=dead: _charred_jeep() if dd else CS.jeep(),
                       pos, e["yaw"])
                if kind == "aa" and not dead:
                    r.add_sprite((e["x"], e["y"] + 2.2, e["z"]),
                                 _fx.glow((230, 236, 255), 0.7, int(tm), pulse=0.2), layer=_fx.FX_LAYER)
                if dead:
                    r.add_sprite((e["x"], e["y"] + 1.4, e["z"]),
                                 _fx.glow((255, 130, 60), 1.6, int(tm), flicker=0.7, seed=3),
                                 layer=_fx.FX_LAYER)
            else:
                if dead:
                    continue
                CS.put_helicopter(r, pos, e["yaw"], -4.0, 8.0 * math.sin(self.t), (tm * 1.5) % 360.0,
                                  (tm * 2.4) % 360.0)
                if e["ucilev"]:
                    r.add_sprite((e["x"], e["y"] + 0.4, e["z"]),
                                 _fx.glow((240, 244, 255), 1.4, int(tm), pulse=0.3), layer=_fx.FX_LAYER)

    def _draw_gun(self, r, eye, tm):
        """The door LMG in front of the camera, swung with the mount."""
        lmg = _lmg()
        yaw = self.mount_yaw() + self.gy
        f = R._fwd(yaw, self.gp)
        rg = R._right(yaw)
        at = (eye[0] + f[0] * 0.35 + rg[0] * 0.16, eye[1] - 0.24 + f[1] * 0.35,
              eye[2] + f[2] * 0.35 + rg[2] * 0.16)
        basis = m_mul(rot_y(yaw), rot_x(-self.gp))
        kick = 0.03 if self.t - self.last_fire < 0.05 else 0.0
        if hasattr(r, "add_packed"):
            key = (id(r), id(lmg))
            rows = _GUN_PACK.get(key)
            if rows is None:
                faces = [(fc[0], fc[1], fc[2], fc[3], None, fc[4]) for fc in lmg.faces]
                rows = _GUN_PACK[key] = r.pack(lmg.verts, faces)
            if rows is not None:
                import numpy as np
                rt = np.asarray(basis, dtype=rows.dtype).reshape(3, 3).T
                out = rows.copy()
                if kick:
                    out[:, 0:3] = (rows[:, 0:3] - np.array((0.0, 0.0, kick), dtype=rows.dtype)) @ rt
                else:
                    out[:, 0:3] = rows[:, 0:3] @ rt
                out[:, 0:3] += np.asarray(at, dtype=rows.dtype)
                out[:, 6:9] = rows[:, 6:9] @ rt
                r.add_packed(out)
        else:
            faces = _GUN_FACES.get(id(lmg))
            if faces is None:
                faces = _GUN_FACES[id(lmg)] = [(fc[0], fc[1], fc[2], fc[3], None, fc[4]) for fc in lmg.faces]
            verts = [v_add(at, m_apply(basis, (v[0], v[1], v[2] - kick))) for v in lmg.verts]
            r.add_dynamic(verts, faces)
        if self.t - self.last_fire < 0.04:
            tip = v_add(at, m_apply(basis, (0.0, 0.03, 0.78)))
            r.add_sprite(tip, _fx.glow((255, 220, 150), 0.25, int(tm), flicker=0.8), layer=_fx.FX_LAYER)

    def _hud(self, surface):
        if self.hurt > 0.02:
            surface.fill((int(70 * self.hurt), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.dying:
            k = clamp(self.death_t / 2.0, 0.0, 1.0)
            surface.blit(_get_veil(int(255 * k)), (0, 0))
            img = font_terminal.render(self.death_msg, True, (220, 200, 190))
            surface.blit(img, img.get_rect(center=(cx, cy)))
            return
        if self.shootdown >= 0.0:
            k = clamp((self.t - self.shootdown - 1.4) / 1.4, 0.0, 1.0)
            if k > 0.0:
                surface.blit(_get_veil(int(255 * k)), (0, 0))
            RH.callouts(surface, self)
            return
        H.objective(surface, self._title, self.objective_text())
        H.crosshair(surface, int(6 + 14 * self.heat), hit_age=self.t - self.hit_mark)
        H.damage_arcs(surface, self.dmg_marks, self.t, life=0.9)
        x, y = 28, HEIGHT - 96
        H._text(surface, font_terminal_small, "HULL", H.TEXT, (x, y))
        H._bar(surface, x + 70, y + 7, 180, self.hull / HULL, H.DANGER if self.hull < 35 else H.ACCENT, h=6)
        H._text(surface, font_terminal_small, "BARREL" + ("  OVERHEAT" if self.overheat else ""),
                H.DANGER if self.overheat else H.TEXT, (x, y + 24))
        H._bar(surface, x + 70, y + 31, 180, self.heat, H.DANGER if self.heat > 0.75 else H.TEXT, h=6)
        H._text(surface, font_terminal_small, "FLARES [F]  " + "I " * self.flares, H.TEXT, (x, y + 48))
        if SECTIONS[self.cp][1] == "road" and self.cp < 4 and self.r_down < 0.0:
            frac = clamp(1.0 - (self.rdist - 60.0) / (ESCAPE_R - 60.0), 0.0, 1.0)
            col = H.DANGER if self.rdist > ESCAPE_R * 0.8 else H.ACCENT
            H._text(surface, font_terminal_small, "RETARDOVICI  %d M" % int(self.rdist), col,
                    (WIDTH - 28, HEIGHT - 96), "topright")
            H._bar(surface, WIDTH - 208, HEIGHT - 74, 180, frac, col, h=6)
            if self.escape > 0.0:
                H._text(surface, font_terminal_small, "HE'S PULLING AWAY - CLEAR THE GUNS",
                        H.DANGER, (cx, 96), "midtop")
            if self.cp == 3:
                H._text(surface, font_terminal_small, "TAIL ROTOR", H.TEXT, (WIDTH - 28, HEIGHT - 60), "topright")
                H._bar(surface, WIDTH - 208, HEIGHT - 40, 180, max(0.0, self.tail_hp) / 320.0, H.DANGER, h=6)
        if any(not rk["unstoppable"] for rk in self.rockets):
            H._text(surface, font_terminal_small, "ROCKET INBOUND  -  SHOOT IT OR [F]", H.DANGER,
                    (cx, cy + 70), "midtop")
        RH.callouts(surface, self)

    def objective_text(self):
        if self.cp == 0:
            return "Kill the AA trucks on the lawn"
        if self.cp == 3:
            return "Shred his tail rotor" if self.r_down < 0.0 else "He's going down"
        if self.cp == 4:
            return "Survive Ucilev"
        return "Keep Retardovici in range"


_LMG = []


def _lmg():
    if not _LMG:
        from cutscenes.m8dutyfilms import _tactical_lmg
        _LMG.append(_tactical_lmg())
    return _LMG[0]


def _charred_jeep():
    return CS._charred(CS.jeep(), 0.8)


_SCENE = None
_GUN_PACK = {}
_GUN_FACES = {}
_VEIL = [None]


def _get_veil(alpha):
    v = _VEIL[0]
    if v is None:
        v = _VEIL[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    v.fill((0, 0, 0, alpha))
    return v


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = FlightScene()
    return _SCENE


def begin():
    return scene().begin()


def active():
    return _SCENE is not None and _SCENE.active()


def update(keys=None):
    return scene().update(keys)


def draw(surface):
    return scene().draw(surface)


def handle_event(event):
    return scene().handle_event(event)


def set_paused(paused):
    if _SCENE is not None:
        _SCENE.set_paused(paused)


def abort():
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m8_flight_active = False
        _SCENE._grab(False)
        if _SCENE.audio is not None:
            try:
                _SCENE.audio.stop_loops()
            except Exception:
                pass


def force_finish(reason="fallback"):
    if _SCENE is not None:
        return _SCENE.finish(reason)
    return False
