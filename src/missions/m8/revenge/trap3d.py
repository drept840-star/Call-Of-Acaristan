"""Mission 8 Revenge - phases 2 and 3: the Trap and the Gantry, one third-person scene.

Dawn on the Route 12 toll plaza (the M2 kill box, rebuilt).  The Guard is
waiting: riflemen out from behind the wrecks, a Guard truck down from the
north, then flankers out of the ditches and from behind the gantry pillars.
Biribel fights north up the M2 route in reverse with the Fallow 12; Bodi
covers from post to post with his hunting rifle and can go down (hold E).
With the road clear Bodi stops at the gantry foot ("This part's yours.") and
Biribel climbs the ladder to the catwalk, where Vasile is waiting.

The fight plays exactly like the Mission 7 raid: camera, movement, input,
reload, looting and the effect/actor drawing are the raid scene's own methods,
borrowed below, run against this scene's world and brain.

Contract (as ``missions.m7.raid3d``): ``begin`` / ``active`` / ``update`` /
``draw`` / ``handle_event`` / ``set_paused`` / ``abort`` / ``force_finish``.
Checkpoints: 0 start, 1 and 2 after the first two waves, 3 the gantry.
"""
import math

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import POSES, blend, clamp
from engine3d.hold import hold_cached as _hold_cached
from missions.m7 import raid3d as R
from missions.m7 import raid_world as RW

from . import set3d as S3
from . import trap_brain as B
from . import trap_hud as HUD
from . import trap_world as W

RES = S3.RES
MAG, RESERVE0, RELOAD_S = R.MAG, R.RESERVE0, R.RELOAD_S
CP_STATE = {1: (-60.0, -2.0, 40.0), 2: (-46.0, 8.0, 40.0), 3: (6.0, 50.0, 20.0)}
CLIMB_HOLD_S = 0.6
CLIMB_S = 3.2
STEP_M = 0.8                    # stride metres per footstep
RUNGS = 9                       # ladder rungs heard on the climb
CLIMB_UP = 0.82                 # share of the climb on the rungs; the rest steps onto the deck
LADDER_FOOT = (S3.LADDER_X, S3.LADDER_Z - 0.45)
CATWALK_X = (-1.6, 8.8)
CATWALK_HALF = 0.5
VASILE_REACH = 2.3
GAP_S = 6.0

_fwd, _right, _wrap, _yaw, _ease = R._fwd, R._right, R._wrap, R._yaw, R._ease


class TrapScene:
    MAG = MAG
    RELOAD_S = RELOAD_S

    # The raid's own feel: these read only state this scene keeps too.
    handle_event = R.RaidScene.handle_event
    _grab = R.RaidScene._grab
    set_paused = R.RaidScene.set_paused
    _snd = R.RaidScene._snd
    say = R.RaidScene.say
    tracer = R.RaidScene.tracer
    hp = R.RaidScene.hp
    hp_max = R.RaidScene.hp_max
    _begin_reload = R.RaidScene._begin_reload
    _aim_ray = R.RaidScene._aim_ray
    _loot = R.RaidScene._loot
    _player_pose = R.RaidScene._player_pose
    _guard_pose = R.RaidScene._guard_pose
    _ally_pose = R.RaidScene._ally_pose
    _cover_pose = R.RaidScene._cover_pose
    _draw_enemies = R.RaidScene._draw_enemies
    _draw_fx = R.RaidScene._draw_fx
    _project = R.RaidScene._project
    _ground_move = R.RaidScene._move

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.cp_state = None
        self.t = 0.0
        self._truck = None
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
        STATE.m8_trap_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup(int(getattr(STATE, "m8_trap_cp", 0) or 0))
        self._grab(True)
        try:
            self._warm()
        except Exception:
            pass

    def _warm(self):
        """Arm solves and the truck pack behind the cut, not mid-fight."""
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
        for mode in ("ready", "aim"):
            R._held(hum, POSES["ready"], "shotgun", mode, ("m7player", mode))
        stances = (dict(POSES["ready"]), blend(POSES["stand"], "aim", 0.85))
        for kind in set(R.GUARD_VIEW):
            gk = ("guard", kind)
            for pose in stances:
                _hold_cached(_w.hum(gk, True), pose, "rifle", "ready", key=gk)
        key = ("ally", "bodi")
        for pose in stances:
            _hold_cached(_w.hum(key), pose, R._ally_gun(key), "ready", key=key)
        for i in range(-4, 5):
            R._ally_aim(key, i / 10.0)
        if self._truck is None:
            self._truck = RW.truck()
        S3.renderer()

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_trap_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_trap_done(result)

    def _setup(self, cp):
        """(Re)build the fight at checkpoint ``cp``; the clock keeps running."""
        self.cp = cp
        p = STATE.player
        self.world = W.World()
        st = self.cp_state if cp and self.cp_state else None
        if cp == 0:
            self.px, self.pz, self.yaw = -73.4, -16.6, 40.0
            self.mag, self.reserve = MAG, RESERVE0
        else:
            x, z, yaw = CP_STATE[cp]
            self.px, self.pz, self.yaw = (st["px"], st["pz"], st["yaw"]) if st else (x, z, yaw)
            self.mag, self.reserve = (st["mag"], st["reserve"]) if st else (MAG, RESERVE0)
        self.py = 0.0
        self.pitch = -4.0
        self.body_yaw = self.yaw
        self.vel = (0.0, 0.0)
        self.stride = 0.0
        self._step_i = 0
        self._rung = -1
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
        self.climb_t = None
        self.marker_screen = None
        self._muzzle = None
        self.turn = None                     # the raid's borrowed methods read it
        post = B.BODI_FOOT if cp == 3 else (B.BODI_POSTS.get(cp) if cp else (-74.8, -17.0))
        self.brain = B.Brain(self, post)
        if cp == 3:
            self.phase = "clear"
            self.next_wave = None
            self.say("BODI", "This part's yours.", 3.0)
        else:
            self.phase = "intro" if cp == 0 else "gap"
            self.next_wave = (cp + 1, self.t + (5.0 if cp == 0 else 3.5))
        if p is not None:
            p.hp = getattr(p, "max_hp", 115) or 115
        if cp == 0:
            self.say("BODI", "Quiet. Too quiet for a man who picked the place.", 3.4)

    def _fail(self, msg):
        if self.dying:
            return
        self.dying = True
        self.death_t = 0.0
        self.death_msg = msg
        self.firing = False
        self._snd("down")

    # --- scene contract used by trap_brain -------------------------------------

    def flash(self, pos):
        self.flashes.append((self.t, pos))
        del self.flashes[:-6]
        d = math.hypot(pos[0] - self.px, pos[2] - self.pz)
        if d < 50.0 and self.t - self._last_snd > 0.07:
            self._last_snd = self.t
            rg = _right(self.yaw)           # which side of the camera it came from
            pan = ((pos[0] - self.px) * rg[0] + (pos[2] - self.pz) * rg[2]) / max(d, 1.0)
            self._snd("guard_shot", 0.8 * pan, d)

    def on_truck_start(self, t):
        self._snd("truck_arrive")

    def on_truck_stop(self, t):
        self._snd("tailgate")

    def bodi_lost(self):
        self._fail("BODI BLED OUT  -  AGAIN FROM THE CHECKPOINT")

    def hurt_player(self, dmg, src=None, forced=False):
        p = STATE.player
        if p is None or self.dying:
            return
        p.hp -= dmg
        self.hurt = min(1.0, self.hurt + dmg / 28.0)
        self.last_hurt = self.t
        self._snd("hurt", dmg)
        if src is not None:
            bearing = _wrap(_yaw(src[0] - self.px, src[1] - self.pz) - self.yaw)
            self.dmg_marks.append((self.t, -bearing))
        if p.hp <= 0:
            self._fail("BIRIBEL DOWN  -  AGAIN FROM THE CHECKPOINT")

    def _floor(self, x, z):
        return 0.0

    # --- update ----------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        self.t += dt
        self._snd("bed", "gantry" if self.phase in ("clear", "climb", "catwalk") else "trap")
        self._snd("update", dt)
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.4:
                self._setup(self.cp)
            return
        k = keys if keys is not None else pygame.key.get_pressed()
        self.ads += ((1.0 if self.aiming and not self.reloading else 0.0) - self.ads) \
            * min(1.0, dt * 12.0)
        up = self.ads > 0.3 or self.firing or self.t - self.last_fire < 0.6
        up = 0.0 if (self.sprint or self.reloading or not up or self.climb_t is not None) else 1.0
        self.gun_up += (up - self.gun_up) * min(1.0, dt * 14.0)
        if self.phase == "climb":
            self._climb(dt)
        elif self.phase == "catwalk":
            self._catwalk_move(k, dt)
        else:
            self._ground_move(k, dt)
        step = int(self.stride / STEP_M)
        if step != self._step_i:
            self._step_i = step
            self._snd("step", step, self.phase == "catwalk")
        if self.reloading:
            self.reloading = max(0.0, self.reloading - dt)
            elapsed = RELOAD_S - self.reloading
            while self._shell_i < len(R.SHELL_AT) and elapsed >= R.SHELL_AT[self._shell_i]:
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
        if self.firing and not self.reloading and self.phase not in ("climb",):
            self._fire()
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self._hold(k, dt)
        self.brain.update(dt)
        self._waves()
        self.hurt = max(0.0, self.hurt - dt * 1.4)
        p = STATE.player
        if p is not None and self.t - self.last_hurt > R.HP_REGEN_DELAY and p.hp < self.hp_max():
            p.hp = min(self.hp_max(), p.hp + R.HP_REGEN * dt)
        now = self.t
        self.tracers = [x for x in self.tracers if now - x[0] < 0.10]
        self.sparks = [x for x in self.sparks if now - x[0] < 0.45]
        self.impacts = [x for x in self.impacts if now - x[0] < 0.6]
        self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.9]
        self.flashes = [x for x in self.flashes if now - x[0] < 0.2]

    def _catwalk_move(self, k, dt):
        def down(*codes):
            try:
                return any(k[c] for c in codes)
            except Exception:
                return False

        fwd_in = (1 if down(pygame.K_w, pygame.K_UP) else 0) - (1 if down(pygame.K_s, pygame.K_DOWN) else 0)
        side_in = (1 if down(pygame.K_d, pygame.K_RIGHT) else 0) - (1 if down(pygame.K_a, pygame.K_LEFT) else 0)
        self.sprint = False
        f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
        mx = f[0] * fwd_in + rg[0] * side_in
        mz = f[2] * fwd_in + rg[2] * side_in
        n = math.hypot(mx, mz)
        speed = R.AIM_WALK if self.ads > 0.5 else R.WALK * 0.8
        want = (mx / n * speed, mz / n * speed) if n > 1e-6 else (0.0, 0.0)
        a = min(1.0, dt * 10.0)
        self.vel = (self.vel[0] + (want[0] - self.vel[0]) * a, self.vel[1] + (want[1] - self.vel[1]) * a)
        self.px = clamp(self.px + self.vel[0] * dt, *CATWALK_X)
        self.pz = clamp(self.pz + self.vel[1] * dt, S3.CATWALK_Z - CATWALK_HALF, S3.CATWALK_Z + CATWALK_HALF)
        vx, vy, vz = S3.VASILE_AT
        if math.hypot(self.px - vx, self.pz - vz) < 0.8:     # he does not get walked through
            dx, dz = self.px - vx, self.pz - vz
            n = math.hypot(dx, dz) or 1.0
            self.px, self.pz = vx + dx / n * 0.8, vz + dz / n * 0.8
        sp = math.hypot(*self.vel)
        self.pmoving = sp > 0.6
        self.stride += sp * dt
        self.body_yaw = _w.yaw_mix(self.body_yaw, self.yaw, min(1.0, dt * 10.0))

    def _climb(self, dt):
        self.climb_t += dt
        k = clamp(self.climb_t / CLIMB_S, 0.0, 1.0)
        self.vel = (0.0, 0.0)
        self.pmoving = False
        self.px, self.body_yaw = S3.LADDER_X, 0.0
        z0 = S3.LADDER_Z - 0.38
        if k < CLIMB_UP:
            self.pz = z0
            u = k / CLIMB_UP
            rung = int(u * RUNGS)
            if rung != self._rung:
                self._rung = rung
                self._snd("rung")
            self.py = S3.CATWALK_Y * (u * u * (3.0 - 2.0 * u) * 0.25 + u * 0.75)
        else:
            # over the lip and through the gap in the rail
            self.py = S3.CATWALK_Y
            self.pz = z0 + (S3.CATWALK_Z - 0.15 - z0) * _ease((k - CLIMB_UP) / (1.0 - CLIMB_UP))
        if k >= 1.0:
            self.phase = "catwalk"
            self.climb_t = None
            self.yaw = self.body_yaw = 270.0       # along the catwalk, toward him
            self.say("VASILE", "Took your time.", 2.6)

    def _hold(self, k, dt):
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        action = self._hold_action()
        if action is None or not held:
            self.hold = 0.0
            return
        self.hold += dt
        if action == "bodi" and self.hold >= R.HOLD_S["bodi"]:
            self.hold = 0.0
            self.brain.help_done("bodi")
        elif action == "climb" and self.hold >= CLIMB_HOLD_S:
            self.hold = 0.0
            self.phase = "climb"
            self.climb_t = 0.0
            self._rung = -1
            self.aiming = self.firing = False

    def _hold_action(self):
        if self.brain.near_revive() is not None:
            return "bodi"
        if self.phase == "clear" and math.hypot(self.px - LADDER_FOOT[0], self.pz - LADDER_FOOT[1]) < 1.3:
            return "climb"
        return None

    # --- camera and fire ---------------------------------------------------------

    def camera(self):
        back, right, up = (R.BOOM[i] + (R.BOOM_ADS[i] - R.BOOM[i]) * self.ads for i in range(3))
        pivot = (self.px, self.py + R.EYE_H + up, self.pz)
        f = _fwd(self.yaw, self.pitch)
        rg = _right(self.yaw)
        right = min(right, max(0.0, self.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), right + 0.3) - 0.3))
        shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = max(0.45, min(back, self.world.ray_hit(shoulder, d, back + 0.35) - 0.35))
        eye = (shoulder[0] + d[0] * dist, max(self.py + 0.35, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        fv = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)
        tgt = (eye[0] + fv[0] * 10.0, eye[1] + fv[1] * 10.0, eye[2] + fv[2] * 10.0)
        if self.phase == "climb":
            # a rear quarter off the open east side, the ladder in profile
            eye = (self.px + 2.6, self.py + 1.5, self.pz - 2.3)
            tgt = (self.px - 0.2, self.py + 1.1, self.pz + 0.3)
        elif self.phase == "catwalk":
            # No fight up here, and the boom would hit the pillar behind him:
            # a rear quarter off the catwalk's south side, along it toward Vasile.
            eye = (self.px + 2.6, self.py + 2.0, self.pz - 2.4)
            tgt = (self.px - 3.0, self.py + 1.2, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 1.2, 0.0, 1.0)
            eye = (eye[0], eye[1] + 1.4 * kk, eye[2])
            tgt = (self.px, self.py + 0.3, self.pz)
        fov = R.FOV + (R.FOV_ADS - R.FOV) * self.ads - 1.4 * self.cam_kick
        return eye, tgt, fov, dist

    def _fire(self):
        if self.t - self.last_fire < R.FIRE_GAP:
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
        self.pump_snd_at = self.t + R.PUMP_S
        o, d = self._aim_ray()
        look_pitch = self.pitch + 1.6 * self.cam_kick
        self.recoil = min(3.0, self.recoil + 1.4)
        self.cam_kick = min(2.6, self.cam_kick + 2.0)
        self.pitch = clamp(self.pitch + 0.55, *R.PITCH_LIM)
        self._snd("shot", True)
        cone = 0.65 if self.ads > 0.5 else 1.0
        src = self._muzzle or o
        hits, impact_pts, lanes = {}, [], []
        farthest, any_enemy, any_head = 0.0, False, False
        for dy, dp in R.PELLET_FAN:
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
                rec = hits.setdefault(id(hit_e), [hit_e, 0.0])
                rec[1] += R.PELLET_HEAD if head else R.PELLET_BODY
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
            if any_head:
                self._snd("headshot", farthest)
            else:
                self._snd("impact", True, farthest)
        else:
            self._snd("impact", False, farthest)

    # --- waves -------------------------------------------------------------------

    def _waves(self):
        b = self.brain
        if self.next_wave and self.t >= self.next_wave[1]:
            n = self.next_wave[0]
            self.next_wave = None
            self.phase = "w%d" % n
            if n == 1:
                self.say("BODI", "Wrecks! They were waiting in the wrecks!", 3.0)
            elif n == 2:
                self.say("BODI", "Truck, north lane. Stay low behind the concrete.", 3.4)
            else:
                self.say("BODI", "Ditches, both sides - and the pillars!", 3.2)
            b.start_wave(n)
        if self.phase in ("w1", "w2") and not b.pending(int(self.phase[1])):
            self._clear(int(self.phase[1]))
        elif self.phase == "w3" and not b.pending(3):
            self._road_clear()
        elif self.phase == "catwalk":
            vx, _vy, vz = S3.VASILE_AT
            if math.hypot(self.px - vx, self.pz - vz) < VASILE_REACH:
                self.finish("win")

    def _clear(self, n):
        self.phase = "gap"
        self.cp = n
        self.cp_state = dict(px=self.px, pz=self.pz, yaw=self.yaw, mag=self.mag,
                             reserve=max(self.reserve, RESERVE0))
        STATE.m8_trap_cp = n
        self.cp_toast = self.t
        p = STATE.player
        if p is not None:
            p.hp = self.hp_max()
        self.next_wave = (n + 1, self.t + GAP_S)
        if n == 1:
            self.say("BODI", "Move up. Booth by booth, like last time - the other way.", 3.4)
        else:
            self.say("BIRIBEL", "He knew we'd come up the road.", 2.6)
            self.say("BODI", "He taught you the road.", 2.4)

    def _road_clear(self):
        self.phase = "clear"
        self.cp = 3
        self.cp_state = None
        STATE.m8_trap_cp = 3
        self.cp_toast = self.t
        p = STATE.player
        if p is not None:
            p.hp = self.hp_max()
        b = self.brain.bodi
        if b["state"] == "up":
            b["goal"] = B.BODI_FOOT
        self.say("BODI", "Road's clear. He's up there.", 2.6)
        self.say("BODI", "This part's yours.", 3.0)
        from .. import flow as _flow
        _flow.on_gantry_reached()

    # --- guidance ------------------------------------------------------------------

    def pending_count(self):
        return self.brain.pending_count()

    def objective_point(self):
        b = self.brain.bodi
        if b["state"] == "down":
            return b["x"], b["z"]
        if self.phase == "clear":
            return LADDER_FOOT
        if self.phase == "catwalk":
            return S3.VASILE_AT[0], S3.VASILE_AT[2]
        return None, None

    def objective_text(self):
        tx, tz = self.objective_point()
        if self.brain.bodi["state"] == "down":
            return "Get to Bodi - he is down", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "clear":
            return "Climb the gantry ladder", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "catwalk":
            return "Walk to Vasile", math.hypot(tx - self.px, tz - self.pz)
        if self.phase == "climb":
            return "Climb", None
        if self.phase == "w3":
            return "Clear the ditches and the gantry pillars", None
        if self.phase == "w2":
            return "Stop the Guard truck in the north lane", None
        if self.phase == "w1":
            return "Fight up the road - the wrecks are full", None
        return "Push north to the gantry", None

    def prompt(self):
        action = self._hold_action()
        if action is not None:
            label = "Pull Bodi up" if action == "bodi" else "Climb"
            need = R.HOLD_S["bodi"] if action == "bodi" else CLIMB_HOLD_S
            return label, "E", (self.hold / need) if self.hold > 0.0 else None
        if self.toast and self.t - self.toast[0] < 1.6:
            return self.toast[1], None, None
        if self.mag <= 0 and self.reserve <= 0:
            return "Dry - take shells off the bodies", None, None
        return None

    # --- draw ----------------------------------------------------------------------

    def _lights(self):
        now = self.t
        return [{"pos": pos, "color": (255, 196, 120), "intensity": 1.3, "range": 5.0}
                for t0, pos in self.flashes[-2:] if now - t0 < 0.07]

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        eye, tgt, fov, _dist = self.camera()
        r = S3.frame(eye, tgt, fov, self._lights())
        del _w.LAST[:]
        if self._truck is None:
            self._truck = RW.truck()
        for t in self.brain.trucks:
            if t["state"] != "wait":
                RW.put(r, self._truck, t["x"], 0.0, t["z"], 180.0)
        self._draw_player(r, tm)
        self._draw_bodi(r, tm)
        self._draw_vasile(r, tm)
        self._draw_enemies(r, tm)
        self._draw_fx(r, tm)
        tx, tz = self.objective_point()
        ty = S3.CATWALK_Y + 1.6 if self.phase == "catwalk" else 1.6
        self.marker_screen = self._project(r, (tx, ty, tz)) if tx is not None else None
        S3.present(r, surface)
        draw_vignette(surface)
        HUD.draw(surface, self)

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        at = (self.px, self.py, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 0.6, 0.0, 1.0)
            _w.actor(r, key, blend("kneel", "dead_back", kk), at, self.body_yaw, int(tm), seed=93,
                     amp=0.0, rifle_on=False, flags=("shotgun",), expression="angry")
            self._muzzle = None
            return
        if self.phase == "climb":
            pose = self._climb_pose()
            _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93, amp=0.0,
                     rifle_on=False, flags=("shotgun",), expression="angry")
            self._muzzle = None
            return
        hum = _w.hum(key, flags=("shotgun",))
        pose = self._player_pose()
        pump = 0.0
        if 0.0 <= self.t - self.pump_at < 0.45:
            pump = math.sin(math.pi * clamp((self.t - self.pump_at) / 0.45, 0.0, 1.0))
        mode = "aim" if (self.ads > 0.5 or self.t - self.last_fire < 0.4) else "ready"
        pose = R._held(hum, pose, "shotgun", mode, ("m7player", mode))
        if pump > 0.0:
            pose = dict(pose, lel=pose.get("lel", 12) + 16.0 * pump,
                        lsh_p=pose.get("lsh_p", 8) - 5.0 * pump)
        joints = _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93,
                          amp=0.12, rifle_on=True, flags=("shotgun",), expression="angry")
        m = joints.get("muzzle") if joints else None
        if m is None:
            f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
            m = (self.px + f[0] * 0.7 + rg[0] * 0.25, self.py + 1.38, self.pz + f[2] * 0.7 + rg[2] * 0.25)
        self._muzzle = m

    def _climb_pose(self):
        """Hand over hand on the rungs, one rung per step, knees up; eased back
        to standing as he steps off onto the deck."""
        k = clamp((self.climb_t or 0.0) / CLIMB_S, 0.0, 1.0)
        sw = math.sin(self.py / 0.64 * 2.0 * math.pi)
        up = dict(spine=6, head_p=-18,
                  lsh_p=158 + 14 * sw, lsh_r=10, lel=36 - 22 * sw,
                  rsh_p=158 - 14 * sw, rsh_r=10, rel=36 + 22 * sw,
                  lhip_p=44 + 30 * sw, lkn=70 + 40 * sw, rhip_p=44 - 30 * sw, rkn=70 - 40 * sw,
                  lank=-10, rank=-10)
        if k < CLIMB_UP:
            return dict(POSES["stand"], **up)
        u = _ease((k - CLIMB_UP) / (1.0 - CLIMB_UP))
        step = math.sin(u * math.pi)
        over = dict(up, lhip_p=up["lhip_p"] + 30 * step, lkn=up["lkn"] + 20 * step)
        return blend(over, POSES["stand"], u)

    def _draw_bodi(self, r, tm):
        a = self.brain.bodi
        key = ("ally", "bodi")
        yaw = a["yaw"]
        if self.phase in ("clear", "climb", "catwalk") and a["state"] == "up" and not a["moving"]:
            yaw = _yaw(S3.LADDER_X - a["x"], S3.LADDER_Z - a["z"])   # he watches the ladder
        joints = _w.actor(r, key, self._bodi_pose(a, key), (a["x"], a["y"], a["z"]), yaw, int(tm),
                          seed=61, amp=0.3, rifle_on=True, mouth=0.0)
        a["muzzle"] = joints.get("muzzle") if joints else None
        if a["state"] == "down":
            r.add_sprite((a["x"], 1.6, a["z"]), _fx.glow((255, 90, 70), 0.3, tm, intensity=0.8,
                                                          core=(255, 160, 140), flicker=0.3),
                         layer=_fx.FX_LAYER)

    def _bodi_pose(self, a, key):
        """The raid's ally pose, eased down into the crouch while he is ducked."""
        ct = a.get("cover_t")
        a["cover_t"] = None
        pose = self._ally_pose(a, key)
        a["cover_t"] = ct
        k = a.get("duck_k", 0.0)
        if k > 0.0 and a["state"] == "up":
            pose = blend(pose, self._cover_pose(key), _ease(k))
        return pose

    def _draw_vasile(self, r, tm):
        x, y, z = S3.VASILE_AT
        yaw = 90.0
        if self.phase == "catwalk":
            yaw = _yaw(self.px - x, self.pz - z)
        _w.actor(r, "vasile", dict(POSES["stand"]), (x, y, z), yaw, int(tm), seed=71, amp=0.5,
                 rifle_on=False, mouth=0.0)


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = TrapScene()
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
        STATE.m8_trap_active = False
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
