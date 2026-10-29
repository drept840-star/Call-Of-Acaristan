"""Mission 7 beat 5 - the raid: a third-person fight for Bodi's yard at night.

Over-the-shoulder camera, WASD + relative mouse look, RMB tightens the aim, LMB
fires the Fallow 12, R reloads, Shift sprints, hold E to free Alex or pull Bodi
up.

Three waves: riflemen and a dog through the orchard gate, two trucks up the
track, then the north sweep while the barn burns and Alex lies pinned at the
well.  Bodi and Alex fight on the AI in ``raid_brain``.  Dying, or leaving Bodi
down for twenty seconds, reloads the last checkpoint inside the scene.

The farm itself is ``cutscenes.m7world3d`` (the same builder the films use).
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import death3d as D
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F
from engine3d import POSES, blend, box, clamp, pose_run
from engine3d.hold import hold_cached as _hold_cached

from . import raid_brain as B
from . import raid_hud as HUD
from . import raid_world as W

RES = (640, 448)                       # internal buffer; x1.5625 to the 1000x700 canvas
WALK, SPRINT, AIM_WALK = 3.3, 5.3, 1.9
EYE_H = 1.55
BOOM = (3.1, 0.85, 0.18)               # back, right, up (hip)
BOOM_ADS = (2.1, 0.62, 0.14)
FOV, FOV_ADS = 62.0, 48.0
SENS = 0.12
PITCH_LIM = (-38.0, 32.0)
MAG, RESERVE0, RESERVE_CAP = 6, 24, 36
FIRE_GAP = 0.95
RELOAD_S = 2.2
PELLETS = 8
# (yaw, pitch) offsets in degrees around the crosshair: a centre lane and a ring of seven.
PELLET_FAN = ((0.0, 0.0), (2.5, 0.0), (1.6, 1.9), (-0.5, 2.4), (-2.2, 1.1), (-2.2, -1.1),
              (-0.5, -2.4), (1.6, -1.9))
PELLET_BODY, PELLET_HEAD = 10, 24
# Impact flecks and the muzzle flash: short hard lines from the point, in metres.
FLECK_ARMS = ((0.10, 0.06, 0.02), (-0.08, 0.09, -0.03), (0.02, -0.07, 0.09))
FLASH_ARMS = ((0.22, 0.05, 0.0), (-0.12, 0.20, 0.05), (0.0, -0.10, -0.22))
PUMP_S = 0.32
SHELL_AT = (0.35, 1.0, 1.65)
HP_REGEN_DELAY, HP_REGEN = 5.0, 7.0
LOOT_R = 1.5
HOLD_S = {"alex": 1.6, "bodi": 2.4}
CP_STATE = {1: (4.0, 2.0, 180.0), 2: (0.0, -2.0, 0.0)}
TANK_BLAST_R = 8.0
GUARD_VIEW = ("rifle", "rusher", "rifle", "officer")
GUARD_PUSH_M = 0.35
BED_TOP = 1.3
DOG_FALL_S, DOG_PUSH_M = 1.0, 0.35      # the Death clip drops over its first second


def _wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def _yaw(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def _fwd(yaw, pitch):
    y, p = math.radians(yaw), math.radians(pitch)
    cp = math.cos(p)
    return (math.sin(y) * cp, math.sin(p), math.cos(y) * cp)


def _right(yaw):
    y = math.radians(yaw)
    return (math.cos(y), 0.0, -math.sin(y))


def _lerp(a, b, k):
    return a + (b - a) * k


def _ease(k):
    return k * k * (3.0 - 2.0 * k)


class RaidScene:
    MAG = MAG
    RELOAD_S = RELOAD_S

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.cp_state = None
        self.t = 0.0
        self._truck = None
        self._ledge = None
        self._last_snd = -9.0
        self._setup(0)

    # --- lifecycle -------------------------------------------------------------

    def begin(self):
        self.t = 0.0
        self.cp_state = None
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m7_raid_active = True
        try:
            from . import m7_audio as _m7_audio
            self.audio = _m7_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m7_raid_cp", 0) or 0))
        self._grab(True)
        try:
            hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
            for mode in ("ready", "aim"):
                _hold_cached(hum, dict(POSES["ready"]), "shotgun", mode,
                             key=("m7player", mode))
        except Exception:
            pass
        try:
            scratch = pygame.Surface((WIDTH, HEIGHT))
            self.draw(scratch)
        except Exception:
            pass

    def active(self):
        return self._active

    def _grab(self, on):
        try:
            pygame.event.set_grab(bool(on))
            pygame.mouse.set_visible(not on)
            pygame.mouse.get_rel()
        except Exception:
            pass

    def set_paused(self, paused):
        self.paused = bool(paused)
        self._grab(self._active and not self.paused)
        if self.audio is not None:
            try:
                if self.paused:
                    self.audio.pause()
                else:
                    self.audio.resume()
            except Exception:
                pass

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m7_raid_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from . import flow as _flow
        return _flow.on_raid_done(result)

    def _setup(self, cp):
        """(Re)build the fight at checkpoint ``cp``; the clock keeps running."""
        self.cp = cp
        p = STATE.player
        preps = list(getattr(STATE, "m7_preps", None) or [])
        self.flags = {k: k in preps for k in ("tractor", "shed", "loft")}
        self.world = W.World(self.flags["tractor"])
        self.fire = W.Fire()
        st = self.cp_state if cp and self.cp_state else None
        if cp == 0:
            self.px, self.pz, self.yaw = 5.0, -1.0, 90.0
            self.mag, self.reserve = MAG, RESERVE0
        else:
            x, z, yaw = CP_STATE[cp]
            self.px, self.pz, self.yaw = (st["px"], st["pz"], st["yaw"]) if st else (x, z, yaw)
            self.mag, self.reserve = (st["mag"], st["reserve"]) if st else (MAG, RESERVE0)
        self.pitch = -4.0
        self.body_yaw = self.yaw
        self.vel = (0.0, 0.0)
        self.stride = 0.0
        self.pmoving = False
        self.sprint = False
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.gun_up = 0.0
        self.reloading = 0.0
        self._shell_i = 0
        self.pump_at = -9.0
        self.pump_snd_at = 1e9
        self.last_fire = -9.0
        self.recoil = 0.0
        self.cam_kick = 0.0
        self.hurt = 0.0
        self.last_hurt = -9.0
        self.hit_mark = -9.0
        self.dmg_marks = []
        self.tracers = []
        self.sparks = []
        self.impacts = []
        self.flashes = []
        self.lines = []
        self.toast = None
        self.cp_toast = 0.0
        self.kills = 0
        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.hold = 0.0
        self.tank_blown = None
        self.marker_screen = None
        self._muzzle = None
        self.phase = "intro" if cp == 0 else "gap"
        self.next_wave = (cp + 1, self.t + (6.0 if cp == 0 else 3.5))
        self.brain = B.Brain(self)
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115
        if cp == 0:
            self.say("BODI", "Yard's ours until it isn't. Keep them off the house.", 3.6)
            self.say("ALEX", "I'll stay on your left.", 2.6)

    def _fail(self, msg):
        if self.dying:
            return
        self.dying = True
        self.death_t = 0.0
        self.death_msg = msg
        self.firing = False

    def _load(self, cp):
        self._setup(cp)

    # --- scene contract used by raid_brain -------------------------------------

    def say(self, who, text, dur=3.0):
        self.lines.append((self.t, who, text, dur))
        del self.lines[:-6]

    def tracer(self, a, b):
        self.tracers.append((self.t, a, b, (255, 214, 150)))

    def flash(self, pos):
        self.flashes.append((self.t, pos))
        del self.flashes[:-6]
        d = math.hypot(pos[0] - self.px, pos[2] - self.pz)
        if d < 50.0 and self.t - self._last_snd > 0.07:
            self._last_snd = self.t
            self._snd("guard_shot")

    def on_truck_stop(self, t):
        self._snd("tailgate")

    def bodi_lost(self):
        self._fail("BODI WENT DOWN  -  AGAIN FROM THE CHECKPOINT")

    def hurt_player(self, dmg, src=None):
        p = STATE.player
        if p is None or self.dying:
            return
        p.hp -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 28.0)
        self.last_hurt = self.t
        if src is not None:
            bearing = _wrap(_yaw(src[0] - self.px, src[1] - self.pz) - self.yaw)
            self.dmg_marks.append((self.t, -bearing))
        if p.hp <= 0:
            self._fail("BIRIBEL DOWN  -  AGAIN FROM THE CHECKPOINT")

    def hp(self):
        p = STATE.player
        return p.hp if p else 0

    def hp_max(self):
        p = STATE.player
        return (getattr(p, "max_hp", 115) or 115) if p else 115

    def _snd(self, name, *a):
        try:
            if self.audio is not None:
                getattr(self.audio, name)(*a)
        except Exception:
            pass

    # --- input -----------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if event.type == pygame.MOUSEMOTION and not self.dying:
            dx, dy = event.rel
            sens = SENS * (1.0 - 0.35 * self.ads)
            self.yaw = (self.yaw + dx * sens) % 360.0
            self.pitch = clamp(self.pitch - dy * sens, *PITCH_LIM)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.firing = True
            elif event.button == 3:
                self.aiming = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.firing = False
            elif event.button == 3:
                self.aiming = False
        elif event.type == pygame.KEYDOWN and event.key == pygame.K_r:
            self._begin_reload()

    # --- update ----------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        self.t += dt
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.4:
                self._load(self.cp)
            return
        k = keys if keys is not None else pygame.key.get_pressed()
        self.ads += ((1.0 if self.aiming and not self.reloading else 0.0) - self.ads) \
            * min(1.0, dt * 12.0)
        up = self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6
        up = 0.0 if (self.sprint or self.reloading or not up) else 1.0
        self.gun_up += (up - self.gun_up) * min(1.0, dt * 14.0)
        self._move(k, dt)
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            elapsed = RELOAD_S - self.reloading
            while self._shell_i < len(SHELL_AT) and elapsed >= SHELL_AT[self._shell_i]:
                self._shell_i += 1
                self._snd("shell_in")
            if not self.reloading:
                n = min(MAG - self.mag, self.reserve)
                self.mag += n
                self.reserve -= n
                if n:
                    self._snd("pump")
        if self.t >= self.pump_snd_at:
            self.pump_snd_at = 1e9
            self._snd("pump")
        if self.firing and not self.reloading:
            self._fire()
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self._hold(k, dt)
        self.fire.update(self.t)
        self.brain.update(dt)
        if self.fire.lit and self.fire.burning(self.px, self.pz):
            self.hurt_player(W.FIRE_DPS * dt)
        self._waves()
        self.hurt = max(0.0, self.hurt - dt * 1.4)
        p = STATE.player
        if p is not None and self.t - self.last_hurt > HP_REGEN_DELAY and p.hp < self.hp_max():
            p.hp = min(self.hp_max(), p.hp + HP_REGEN * dt)
        now = self.t
        self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]
        self.flashes = [x for x in self.flashes if now - x[0] < 0.2]

    def _move(self, k, dt):
        def down(*codes):
            try:
                return any(k[c] for c in codes)
            except Exception:
                return False

        fwd_in = (1 if down(pygame.K_w, pygame.K_UP) else 0) - (1 if down(pygame.K_s, pygame.K_DOWN) else 0)
        side_in = (1 if down(pygame.K_d, pygame.K_RIGHT) else 0) - (1 if down(pygame.K_a, pygame.K_LEFT) else 0)
        self.sprint = (down(pygame.K_LSHIFT, pygame.K_RSHIFT) and fwd_in > 0
                       and self.ads < 0.3 and not self.firing)
        f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
        mx = f[0] * fwd_in + rg[0] * side_in
        mz = f[2] * fwd_in + rg[2] * side_in
        n = math.hypot(mx, mz)
        speed = SPRINT if self.sprint else (AIM_WALK if self.ads > 0.5 else WALK)
        want = (mx / n * speed, mz / n * speed) if n > 1e-6 else (0.0, 0.0)
        a = min(1.0, dt * 10.0)
        self.vel = (self.vel[0] + (want[0] - self.vel[0]) * a, self.vel[1] + (want[1] - self.vel[1]) * a)
        nx, nz = self.world.move(self.px, self.pz, self.vel[0] * dt, self.vel[1] * dt)
        if abs(nx - self.px) < abs(self.vel[0] * dt) * 0.3:
            self.vel = (0.0, self.vel[1])
        if abs(nz - self.pz) < abs(self.vel[1] * dt) * 0.3:
            self.vel = (self.vel[0], 0.0)
        self.px, self.pz = nx, nz
        sp = math.hypot(*self.vel)
        self.pmoving = sp > 0.6
        self.stride += sp * dt
        self.body_yaw = _w.yaw_mix(self.body_yaw, self.yaw, min(1.0, dt * 10.0))

    # --- camera and aim ----------------------------------------------------------

    def camera(self):
        back, right, up = (BOOM[i] + (BOOM_ADS[i] - BOOM[i]) * self.ads for i in range(3))
        pivot = (self.px, EYE_H + up, self.pz)
        f = _fwd(self.yaw, self.pitch)
        rg = _right(self.yaw)
        right = min(right, max(0.0, self.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), right + 0.3) - 0.3))
        shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = max(0.45, min(back, self.world.ray_hit(shoulder, d, back + 0.35) - 0.35))
        eye = (shoulder[0] + d[0] * dist, max(0.35, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        fv = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)
        tgt = (eye[0] + fv[0] * 10.0, eye[1] + fv[1] * 10.0, eye[2] + fv[2] * 10.0)
        if self.dying:
            kk = clamp(self.death_t / 1.2, 0.0, 1.0)
            eye = (eye[0], eye[1] + 1.4 * kk, eye[2])
            tgt = (self.px, 0.3, self.pz)
        fov = FOV + (FOV_ADS - FOV) * self.ads - 1.4 * self.cam_kick
        return eye, tgt, fov, dist

    def _aim_ray(self):
        eye, _tgt, _fov, dist = self.camera()
        f = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)   # the crosshair ray, as the camera looks
        return (eye[0] + f[0] * dist, eye[1] + f[1] * dist, eye[2] + f[2] * dist), f

    def _begin_reload(self):
        if self.reloading or self.mag >= MAG or self.reserve <= 0:
            return
        self.reloading = RELOAD_S
        self._shell_i = 0
        self._snd("reload")

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return
        if self.mag <= 0:
            if self.t - self.last_fire > 0.3:
                self.last_fire = self.t
                self._snd("dry")
                self._begin_reload()
            return
        self.mag -= 1
        self.last_fire = self.t
        self.pump_at = self.t
        self.pump_snd_at = self.t + PUMP_S
        o, d = self._aim_ray()      # the shot leaves along the sight as it was, before the kick
        look_pitch = self.pitch + 1.6 * self.cam_kick
        self.recoil = min(3.0, self.recoil + 1.4)
        self.cam_kick = min(2.6, self.cam_kick + 2.0)
        self.pitch = clamp(self.pitch + 0.55, *PITCH_LIM)
        self._snd("shot", True)
        if self.flags["shed"] and self.tank_blown is None:
            tank = W._ray_box(o, d, W.STATIC[3])
            if tank is not None and tank < self.world.ray_hit(o, d, 70.0) + 1e-3:
                self._blow_tank()
                return
        cone = 0.65 if self.ads > 0.5 else 1.0
        src = self._muzzle or o
        hits = {}
        impact_pts = []
        lanes = []
        farthest = 0.0
        any_enemy = False
        any_head = False
        for dy, dp in PELLET_FAN:
            dd = _fwd(self.yaw + dy * cone, look_pitch + dp * cone)
            best = self.world.ray_hit(o, dd, 70.0)
            hit_e, head = None, False
            for e in self.brain.enemies:
                if not e["alive"] or not e["live"]:
                    continue
                for c, rad, is_head in self.brain.spheres(e):
                    h = B._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_e, head = h, e, is_head
            end = (o[0] + dd[0] * best, o[1] + dd[1] * best, o[2] + dd[2] * best)
            lanes.append(end)
            farthest = max(farthest, best)
            if hit_e is None:
                impact_pts.append((end, "dust"))
            else:
                any_enemy = True
                any_head = any_head or head
                rec = hits.get(id(hit_e))
                if rec is None:
                    hits[id(hit_e)] = [hit_e, 0.0]
                    rec = hits[id(hit_e)]
                rec[1] += PELLET_HEAD if head else PELLET_BODY
                impact_pts.append((end, "blood"))
        for end in lanes:
            self.tracers.append((self.t, src, end, (255, 226, 160)))
        self.flashes.append((self.t, src))
        for end, kind in impact_pts:
            self.impacts.append((self.t, end, kind))
        ld = _fwd(self.yaw, look_pitch)
        self.sparks.append((self.t, (o[0] + ld[0] * farthest, o[1] + ld[1] * farthest,
                                     o[2] + ld[2] * farthest)))
        for e, dmg in hits.values():
            self.brain.hurt_enemy(e, dmg, (o[0], o[2]))
        if any_enemy:
            self.hit_mark = self.t
            self._snd("headshot" if any_head else "impact", True)
        else:
            self._snd("impact", False)

    def _blow_tank(self):
        self.tank_blown = self.t
        cx, cy, cz = W.TANK_AT
        self._snd("report")
        for e in self.brain.enemies:
            if e["alive"] and e["live"]:
                d = math.hypot(e["x"] - cx, e["z"] - cz)
                if d < TANK_BLAST_R:
                    self.brain.hurt_enemy(e, 150.0 * (1.0 - 0.55 * d / TANK_BLAST_R))
        d = math.hypot(self.px - cx, self.pz - cz)
        if d < 6.0:
            self.hurt_player(55.0 * (1.0 - d / 6.0), (cx, cz))
        self.say("BODI", "That's the tank! They're all over the track!", 3.0)

    def _loot(self):
        for e in self.brain.enemies:
            room = RESERVE_CAP - self.reserve
            if room <= 0:
                return
            if e["alive"] or not e["mags"] or e["kind"] == "dog":
                continue
            bx, bz = e.get("rest", (e["x"], e["z"]))
            if math.hypot(bx - self.px, bz - self.pz) > LOOT_R:
                continue
            got = min(MAG, room)
            e["mags"] = 0
            self.reserve += got
            self.toast = (self.t, "+%d SHELLS" % got)
            self._snd("reload")
            if self.mag <= 0:
                self._begin_reload()

    def _hold(self, k, dt):
        who = self.brain.near_revive()
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        if who is None or not held:
            self.hold = 0.0
            return
        self.hold += dt
        if self.hold >= HOLD_S[who]:
            self.hold = 0.0
            self.brain.help_done(who)

    # --- waves -------------------------------------------------------------------

    def _waves(self):
        b = self.brain
        if self.next_wave and self.t >= self.next_wave[1]:
            n = self.next_wave[0]
            self.next_wave = None
            self._begin_wave(n)
        if self.phase == "w1" and not b.pending(1):
            self._clear(1)
        elif self.phase == "w2" and not b.pending(2):
            self._clear(2)
        elif self.phase == "w3" and not b.pending(3) and not b.alex["pinned"]:
            self.say("BODI", "North's clear. Go. I'll hold the yard.", 3.0)
            self.finish("win")

    def _begin_wave(self, n):
        b = self.brain
        self.phase = "w%d" % n
        if n == 1:
            self.say("BODI", "Orchard gate! Riflemen in the trees.", 3.2)
        elif n == 2:
            self.say("ALEX", "Trucks! Two of them - no, three!", 3.6)
            self._snd("truck_arrive")
        else:
            self.fire.ignite(self.t)
            if b.bodi["loft"]:
                b.bodi_climb_down()
            a = b.alex
            a["pinned"] = True
            a["x"], a["z"] = W.WELL_PIN
            self.say("BODI", "That's my barn.", 2.6)
            self.say("ALEX", "I'm pinned! Biribel, I'm pinned!", 3.4)
        b.start_wave(n)

    def _clear(self, n):
        self.phase = "gap"
        self.cp = n
        self.cp_state = dict(px=self.px, pz=self.pz, yaw=self.yaw, mag=self.mag,
                             reserve=max(self.reserve, RESERVE0))
        STATE.m7_raid_cp = n
        self.cp_toast = self.t
        p = STATE.player
        if p is not None:
            p.hp = self.hp_max()
        self.next_wave = (n + 1, self.t + 6.0)
        if n == 1:
            self.say("BODI", "That's the first knock. They'll come up the track next.", 3.4)
        else:
            self.say("BODI", "Quiet. Too quiet. Check your mag.", 2.8)
            self.say("ALEX", "Smoke... Biribel, that's the barn!", 2.8)

    def pending_count(self):
        return sum(t["riflemen"] + (1 if t["dog"] else 0)
                   for t in self.brain.trucks if not t["dumped"])

    # --- guidance ------------------------------------------------------------------

    def objective_point(self):
        b = self.brain
        if b.bodi["state"] == "down":
            return b.bodi["x"], b.bodi["z"]
        if b.alex["pinned"]:
            return W.WELL_PIN
        return None, None

    def objective_text(self):
        b = self.brain
        tx, tz = self.objective_point()
        if tx is not None:
            who = "Get to Bodi - he is down" if b.bodi["state"] == "down" else "Free Alex at the well"
            return who, math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "w3":
            return "Clear the north road - the barn is burning", None
        if self.phase == "w2":
            return "Stop the trucks coming up the track", None
        if self.phase == "w1":
            return "Hold the orchard gate", None
        return "Hold the yard - they are coming", None

    def prompt(self):
        who = self.brain.near_revive()
        if who is not None:
            label = "Free Alex" if who == "alex" else "Pull Bodi up"
            return label, "E", (self.hold / HOLD_S[who]) if self.hold > 0.0 else None
        if self.toast and self.t - self.toast[0] < 1.6:
            return self.toast[1], None, None
        if self.mag <= 0 and self.reserve <= 0:
            return "Dry - take mags off the bodies", None, None
        return None

    # --- draw ----------------------------------------------------------------------

    def _lights(self, tm):
        now = self.t
        out = [{"pos": pos, "color": (255, 196, 120), "intensity": 1.3, "range": 5.0}
               for t0, pos in self.flashes[-2:] if now - t0 < 0.07]
        if self.tank_blown is not None and now - self.tank_blown < 2.5:
            k = 1.0 - (now - self.tank_blown) / 2.5
            out.append({"pos": W.TANK_AT, "color": (255, 150, 60), "intensity": 1.8 * k,
                        "range": 16.0})
        out += self.fire.lights(tm, now)
        # Headlights add no local light: point lights are additive and wash the
        # Guard's dark uniforms grey.  The beam is the road pools (``_beam_pools``)
        # and the lamp glows, which leave the men and the truck moonlit.
        out.append({"pos": F.PORCH_LAMP, "color": (255, 190, 110), "intensity": 1.15,
                    "range": 13.0})
        out.append({"pos": F.BARN_LAMP, "color": (255, 180, 100), "intensity": 1.05,
                    "range": 12.0})
        return out[:8]

    def _beam_pools(self):
        """The headlight beams on the baked road: two pools ahead of each
        moving truck, the far one wider and dimmer."""
        out = []
        for t in self.brain.trucks:
            if t["state"] != "wait":
                x, z = t["x"], t["z"]
                out.append({"pos": (x, 1.3, z + 6.0), "range": 3.8, "color": (255, 226, 178),
                            "hot": (255, 244, 214), "intensity": 3.0})
                out.append({"pos": (x, 1.3, z + 11.0), "range": 5.0, "color": (216, 194, 158),
                            "hot": (255, 236, 208), "intensity": 1.8})
        return out

    def _project(self, r, p):
        try:
            x, y, z = r.to_cam(p)
        except Exception:
            return (WIDTH / 2.0, 0.0, False)
        k = WIDTH / float(r.w)
        if z <= 0.05:
            return (WIDTH / 2.0 + x * 1000.0, HEIGHT / 2.0 - y * 1000.0, False)
        return ((r.w / 2 + x / z * r.focal) * k, (r.h / 2 - y / z * r.focal) * k, True)

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        eye, tgt, fov, _dist = self.camera()
        park = W.TRACTOR_BLOCK if self.flags["tractor"] else None
        r, buf = F.stage("raid", tm, eye, tgt, fov, self._lights(tm), hh=0.0, seed=7,
                         size=RES, park=park)
        del _w.LAST[:]
        r.set_pools(F.raid_pools(self.fire.lights(tm, self.t) + self._beam_pools()))
        F.raid_fx(r, tm)
        if self._truck is None:
            self._truck = W.truck()
            self._ledge = W.ledge()
        if self.flags["loft"]:
            _w.add(r, self._ledge)
        for t in self.brain.trucks:
            if t["state"] != "wait":
                _w.add(r, W.placed(self._truck, t["x"], 0.0, t["z"], 0.0))
                for sx in (-0.68, 0.68):
                    r.add_sprite((t["x"] + sx, 1.46, t["z"] + 2.95),
                                 _fx.glow((255, 236, 200), 0.55, tm, core=(255, 250, 236),
                                          intensity=1.15, max_px=34), layer=_fx.FX_LAYER)
                # Two warm pools on the road and a low glare between them: the
                # beam has to land on the track, not just sit in the lamps.
                seed = int(t["x"] * 7.0) + 11
                for dz, rad, k in ((6.0, 3.6, 0.26), (11.0, 4.8, 0.14)):
                    r.add_sprite((t["x"], 0.05, t["z"] + dz),
                                 F.pool((255, 228, 184), rad, intensity=k, squash=0.5),
                                 layer=_fx.FX_LAYER)
                r.add_sprite((t["x"], 1.05, t["z"] + 4.4),
                             _fx.haze((255, 232, 196), 2.1, tm, seed=seed, intensity=0.12),
                             layer=_fx.FX_LAYER)
        self._draw_player(r, tm)
        self._draw_allies(r, tm)
        self._draw_enemies(r, tm)
        self.fire.draw(r, tm, self.t)
        self._draw_tank(r, tm)
        self._draw_fx(r, tm)
        tx, tz = self.objective_point()
        self.marker_screen = self._project(r, (tx, 1.6, tz)) if tx is not None else None
        r.flush(buf)
        F.grade_raid(buf)
        _fx.present_crisp(buf, surface)
        draw_vignette(surface)
        HUD.draw(surface, self)

    def _draw_tank(self, r, tm):
        cx, cy, cz = W.TANK_AT
        if self.flags["shed"] and self.tank_blown is None:
            r.add_sprite((cx, cy + 0.9, cz), W.tank_glow(tm, True), layer=_fx.FX_LAYER)
        elif self.tank_blown is not None and self.t - self.tank_blown < 7.0:
            age = self.t - self.tank_blown
            F.fire(r, (cx, 0.3, cz), tm, seed=91, size=1.5 * max(0.3, 1.0 - age / 7.0))
            if age < 2.6:
                r.add_sprite((cx, 1.5, cz), F.sparks(tm, self.tank_blown * 1000.0, seed=5, n=60,
                                                     speed=9.0, life=2.4), layer=_fx.FX_LAYER)

    def _player_pose(self):
        if math.hypot(*self.vel) > 0.5:
            base = pose_run(self.stride * 1.9, lean=12 if self.sprint else 5)
        else:
            base = POSES["ready"]
        pose = dict(blend(base, "aim", self.gun_up))
        pose["spine"] = pose.get("spine", 0.0) - 0.35 * self.pitch
        pose["head_p"] = pose.get("head_p", 0.0) - 0.55 * self.pitch
        return pose

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        at = (self.px, 0.0, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 0.6, 0.0, 1.0)
            _w.actor(r, key, blend("kneel", "dead_back", kk), at, self.body_yaw, int(tm), seed=93,
                     amp=0.0, rifle_on=False, flags=("shotgun",), expression="angry")
            self._muzzle = None
            return
        hum = _w.hum(key, flags=("shotgun",))
        pose = self._player_pose()
        pump = 0.0
        if 0.0 <= self.t - self.pump_at < 0.45:
            pump = math.sin(math.pi * clamp((self.t - self.pump_at) / 0.45, 0.0, 1.0))
        mode = "aim" if (self.ads > 0.5 or self.t - self.last_fire < 0.4) else "ready"
        pose = _hold_cached(hum, pose, "shotgun", mode, key=("m7player", mode))
        if pump > 0.0:
            pose = dict(pose, lel=pose.get("lel", 12) + 16.0 * pump,
                        lsh_p=pose.get("lsh_p", 8) - 5.0 * pump)
        joints = _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93,
                          amp=0.12, rifle_on=True, flags=("shotgun",), expression="angry")
        m = joints.get("muzzle") if joints else None
        if m is None:
            f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
            m = (self.px + f[0] * 0.7 + rg[0] * 0.25, 1.38, self.pz + f[2] * 0.7 + rg[2] * 0.25)
        self._muzzle = m

    def _ally_pose(self, a, held=None):
        if a["state"] == "down":
            return dict(POSES["slump"])
        if a.get("pinned"):
            return dict(POSES["kneel"])
        if a["moving"]:
            return pose_run(self.t * 7.0 + a["x"], lean=6)
        if self.t - a["aim"] < 0.4:
            return blend(POSES["stand"], "aim", 0.85)
        return dict(POSES["ready"])

    def _draw_allies(self, r, tm):
        b = self.brain
        for name, a in (("bodi", b.bodi), ("alex", b.alex)):
            key = ("ally", name)
            pose = self._ally_pose(a)
            if not a["moving"] and a["state"] != "down":
                pose = _hold_cached(_w.hum(key), pose, "rifle", "ready", key=key)
            joints = _w.actor(r, key, pose, (a["x"], a["y"], a["z"]), a["yaw"], int(tm),
                              seed=61 if name == "bodi" else 62, amp=0.3, rifle_on=True, mouth=0.0)
            a["muzzle"] = joints.get("muzzle") if joints else None
            if a["state"] == "down" and name == "bodi":
                r.add_sprite((a["x"], 1.6, a["z"]), _fx.glow((255, 90, 70), 0.3, tm, intensity=0.8,
                                                              core=(255, 160, 140), flicker=0.3),
                             layer=_fx.FX_LAYER)

    def _guard_pose(self, e):
        if e["moving"]:
            return pose_run(self.t * 8.0 + e["slot"], lean=14)
        if e["tele"] > 0.0 or e["left"] > 0 or self.t - e["aim"] < 0.4:
            return blend(POSES["stand"], "aim", 0.85)
        return dict(POSES["ready"])

    def _floor(self, x, z):
        """Height a body lands on: a truck bed, else the ground."""
        for t in self.brain.trucks:
            if t["state"] != "wait" and abs(x - t["x"]) <= 1.2 and abs(z - t["z"]) <= 3.0:
                return BED_TOP
        return 0.0

    def _draw_enemies(self, r, tm):
        for e in self.brain.enemies:
            if not e["live"] and e["alive"]:
                continue
            x, y, z = e["x"], e["y"], e["z"]
            if e["kind"] == "dog":
                if not e["alive"]:
                    k = _ease(clamp((self.t - e["dead_t"]) / DOG_FALL_S, 0.0, 1.0))
                    ux, uz = e.get("fall_dir", (0.0, 0.0))
                    _w.add(r, W.placed(W.dog("Death", self.t - e["dead_t"]), x + ux * DOG_PUSH_M * k,
                                       0.0, z + uz * DOG_PUSH_M * k, e["yaw"]))
                    continue
                bite = (self.t - e["aim"]) * B.BITE_PLAY
                if bite < W.dog_clip_s("Bite"):
                    clip, ct = "Bite", bite
                elif e["moving"]:
                    clip, ct = "Run", e["gait"] / W.DOG_RUN_M * W.dog_clip_s("Run")
                else:
                    clip, ct = "Idle", self.t + e["phase"]
                _w.add(r, W.placed(W.dog(clip, ct), x, 0.0, z, e["yaw"]))
                continue
            kind = "heavy" if e["kind"] == "gunner" else GUARD_VIEW[e["slot"] % len(GUARD_VIEW)]
            gk = ("guard", kind)
            if not e["alive"]:
                fall = e.get("fall")
                if fall is None:
                    ux, uz = e.get("fall_dir", (0.0, 0.0))
                    track = D.track_for(e.get("dead_pose") == "dead_back", e["slot"])
                    fall = e["fall"] = D.Fall(_w.hum(gk, True), e.get("pose") or POSES["stand"],
                                              track, (x, y, z), e["yaw"],
                                              (ux * GUARD_PUSH_M, uz * GUARD_PUSH_M), e["slot"])
                pose, root, yaw = fall.at(self.t - e["dead_t"], self._floor)
                _w.actor(r, gk, pose, root, yaw, int(tm), seed=100 + e["slot"], amp=0.0,
                         rifle_on=False, hd=True)
                e["rest"] = fall.chest
                if e["mags"] and fall.rest is not None:
                    r.add_sprite((fall.chest[0], root[1] + 0.2, fall.chest[1]),
                                 _fx.glow((255, 214, 140), 0.28, tm,
                                          intensity=0.35 + 0.35 * math.sin(self.t * 4.0 + e["slot"]) ** 2),
                                 layer=_fx.FX_LAYER)
                continue
            pose = self._guard_pose(e)
            stag = max(0.0, 1.0 - (self.t - e["hit_t"]) / 0.3)
            if stag > 0.0:
                pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
            if not e["moving"]:
                pose = _hold_cached(_w.hum(gk, True), pose, "rifle", "ready", key=gk)
            e["pose"] = pose
            joints = _w.actor(r, gk, pose, (x, y, z), e["yaw"], int(tm), seed=100 + e["slot"],
                              amp=0.4, rifle_on=True, hd=True)
            m = joints.get("muzzle") if joints else None
            if m is not None and e["tele"] > 0.0:
                r.add_sprite(m, _fx.glow((255, 70, 50), 0.14, tm, seed=e["slot"], core=(255, 120, 90),
                                         intensity=0.8), layer=_fx.FX_LAYER)

    def _draw_fx(self, r, tm):
        now = self.t
        for t0, a, b, col in self.tracers:
            k = (now - t0) / 0.06
            head, tail = min(1.0, k), max(0.0, k - 0.35)
            if tail < 1.0:
                pa = tuple(a[i] + (b[i] - a[i]) * tail for i in range(3))
                pb = tuple(a[i] + (b[i] - a[i]) * head for i in range(3))
                r.add_line3d(pa, pb, col, 2, layer=3)
        for t0, p in self.sparks:
            r.add_sprite(p, _fx.sparks(7, (now - t0) * 1000.0, n=10, speed_m=2.0, dur_ms=420),
                         layer=_fx.FX_LAYER)
        for t0, p, kind in self.impacts:
            if now - t0 < 0.22:
                col = (176, 26, 22) if kind == "blood" else (238, 226, 176)
                for ax, ay, az in FLECK_ARMS:
                    r.add_line3d(p, (p[0] + ax, p[1] + ay, p[2] + az), col, 1, layer=3)
        for t0, pos in self.flashes:
            if now - t0 < 0.06:
                for ax, ay, az in FLASH_ARMS:
                    r.add_line3d(pos, (pos[0] + ax, pos[1] + ay, pos[2] + az), (255, 238, 190), 2,
                                 layer=3)


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = RaidScene()
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
    """Drop the scene without finishing (mission restart, quit to menu)."""
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m7_raid_active = False
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
