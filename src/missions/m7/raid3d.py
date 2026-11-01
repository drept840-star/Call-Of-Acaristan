"""Mission 7 beat 5 - the raid: a third-person fight for Bodi's yard at night.

Over-the-shoulder camera, WASD + relative mouse look, RMB tightens the aim, LMB
fires the Fallow 12, R reloads, Shift sprints, hold E to free Alex or pull Bodi
up.

Three waves: riflemen and a dog through the orchard gate, two trucks up the
track, then the north sweep while the barn burns and Alex lies pinned at the
well.  Bodi and Alex fight on the AI in ``raid_brain``.  Dying, or leaving Bodi
down for twenty seconds, reloads the last checkpoint inside the scene.

Put a barrel in the pig and the night turns: Bodi stops fighting the Guards,
crosses the yard and rifles *you* down in a scripted beat (``_turn_update``).
He cannot be killed, wounded or revived from that frame on, and the checkpoint
replays with him back at your shoulder.

The farm itself is ``cutscenes.m7world3d`` (the same builder the films use).
"""
import math
import random

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
WELL_CREAK_S = 0.8                      # Alex is in cover at the well this long before it goes
KNOCK_S = 0.3                           # the beam throws Alex flat over this long
LIFT_LOW = dict(POSES["crouch"], spine=40, head_p=-20, lsh_p=62, lsh_r=10, lel=24,
                rsh_p=62, rsh_r=10, rel=24)
LIFT_HIGH = dict(POSES["stand"], spine=18, head_p=-12, lhip_p=34, lkn=40, rhip_p=34, rkn=40,
                 lsh_p=96, lsh_r=10, lel=46, rsh_p=96, rsh_r=10, rel=46)
RISE_KNEE = 0.5                         # share of Alex's rise spent getting onto a knee
CP_STATE = {1: (4.0, 2.0, 180.0), 2: (0.0, -2.0, 0.0)}
TANK_BLAST_R = 8.0
PIG_HIDE = (-18.5, -14.5)              # the far south-west corner it bolts to
# The pig as a target: a body sphere (metres) and the shot that ends it.
PIG_HIT_Y, PIG_HIT_R = 0.36, 0.5
PIG_HIT_MAX = 2                         # pellets: one barrel at range, not a graze
# The betrayal. Timings in seconds, distances in metres.
TURN_STARE = 1.5                        # he looks at the pig, then at you
TURN_CLOSE_M = 4.6                      # he walks in to this range and stops
TURN_CLOSE_MAX = 4.2                    # ...or stops walking after this long
TURN_WALK = 2.9                         # he does not jog it: he walks you down
TURN_AIM_S = 1.8                        # shoulders the rifle: your last window
TURN_DEATH_MSG = "BODI PUT YOU DOWN  -  HIS YARD, HIS RULES"
GUARD_VIEW = ("rifle", "rusher", "rifle", "officer")
GUARD_PUSH_M = 0.35
BED_TOP = 1.3
DOG_FALL_S, DOG_PUSH_M = 1.0, 0.35      # the Death clip drops over its first second
AIM_TWIST = 30.0                         # allies blade the torso this far to aim


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


_ARMS = ("lsh_p", "lsh_r", "lsh_y", "lel", "rsh_p", "rsh_r", "rsh_y", "rel", "rifle_p", "rifle_y")


def _held(hum, pose, weapon, mode, key):
    """``pose`` with the arms of the cached hold solved at the ready stance.

    The solve's arms do not depend on the spine and its rifle_p follows the
    spine one to one, so the look-pitch spine and the hit stagger shift rifle_p
    instead of costing a fresh 20-60 ms IK solve for every new degree."""
    ref = POSES["ready"]
    arms = _hold_cached(hum, ref, weapon, mode, key=key)
    out = dict(pose)
    out.update((k, arms[k]) for k in _ARMS if k in arms)
    out["rifle_p"] = arms.get("rifle_p", 0.0) + pose.get("spine", 0.0) - ref["spine"]
    return out


def _ally_gun(key):
    """Grip set of an ally's rifle: the M7Rifle asset, or the rig rifle without it."""
    return getattr(_w.hum(key), "_weapon", "rifle")


def _ally_aim(key, slope):
    """An ally's aiming stance, rifle shouldered along ``slope`` (rise per metre).

    The torso blades 30 degrees so the left hand reaches the handguard instead
    of sliding back onto the receiver; the head turns back down the barrel."""
    stance = dict(blend(POSES["stand"], "aim", 0.85), twist=AIM_TWIST, head_y=-0.8 * AIM_TWIST)
    return _hold_cached(_w.hum(key), stance, _ally_gun(key), "aim",
                        aim=(0.0, 1.45 + 10.0 * slope, 10.0), key=key)


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
        self._pig_mesh = None
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
            self._warm()
        except Exception:
            pass
        try:
            scratch = pygame.Surface((WIDTH, HEIGHT))
            self.draw(scratch)
        except Exception:
            pass

    def _warm(self):
        """Pay the one-off costs here, behind the cut, instead of mid-fight:
        every arm solve the fight can ask for (20-60 ms each) and the truck's
        15k-face pack."""
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
        for mode in ("ready", "aim"):
            _held(hum, POSES["ready"], "shotgun", mode, ("m7player", mode))
        stances = (dict(POSES["ready"]), blend(POSES["stand"], "aim", 0.85))
        for kind in set(GUARD_VIEW) | {"heavy"}:
            gk = ("guard", kind)
            for pose in stances:
                _hold_cached(_w.hum(gk, True), pose, "rifle", "ready", key=gk)
        for name in ("bodi", "alex"):
            key = ("ally", name)
            for pose in stances + (dict(POSES["kneel"]), dict(POSES["crouch"])):
                _hold_cached(_w.hum(key), pose, _ally_gun(key), "ready", key=key)
            for i in range(-4, 5):
                _ally_aim(key, i / 10.0)
        if self._truck is None:
            self._truck = W.truck()
            self._ledge = W.ledge()
        r = _w.rend(*RES)[0]
        r.begin()
        W.put(r, self._truck, 0.0, 0.0, 0.0, 0.0)
        W.put(r, self._pig_mesh, F.PIG_HOME[0], 0.0, F.PIG_HOME[1], F.PIG_HOME[2])
        for mesh in self._pig_walk:
            W.put(r, mesh, F.PIG_HOME[0], 0.0, F.PIG_HOME[1], F.PIG_HOME[2])

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
        self.death_by_bodi = False
        self.death_t = 0.0
        self.death_msg = ""
        self.hold = 0.0
        self.wreck = W.WellWreck()
        self.tank_blown = None
        self.marker_screen = None
        self._muzzle = None
        self.phase = "intro" if cp == 0 else "gap"
        self.next_wave = (cp + 1, self.t + (6.0 if cp == 0 else 3.5))
        self.brain = B.Brain(self)
        self.pig = {"x": F.PIG_HOME[0], "z": F.PIG_HOME[1], "yaw": F.PIG_HOME[2],
                    "tx": F.PIG_HOME[0], "tz": F.PIG_HOME[1], "mode": "graze",
                    "next": 2.0, "gait": 0.0, "scared": False, "shy_t": -9.0,
                    "stuck": 0.0, "dead": False, "fell_at": 0.0}
        # A checkpoint reload replays the attempt: the pig is alive again.
        self.turn = None            # the betrayal beat, once the pig is down
        self.pig_dead = False
        STATE.m7_pig_dead = False
        STATE.m7_pig_at = None
        self._pig_dead_mesh = None
        self._pig_rng = random.Random(47)
        self.world.pig_at = (self.pig["x"], self.pig["z"])
        if self._pig_mesh is None:
            self._pig_mesh = F.pig()
            from cutscenes.m7pig3d import FRAMES, pig_pose
            self._pig_walk = tuple(pig_pose(i) for i in range(FRAMES))
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
        self._pig_scare()
        d = math.hypot(pos[0] - self.px, pos[2] - self.pz)
        if d < 50.0 and self.t - self._last_snd > 0.07:
            self._last_snd = self.t
            self._snd("guard_shot")

    def on_truck_stop(self, t):
        self._snd("tailgate")

    def bodi_lost(self):
        self._fail("BODI WENT DOWN  -  AGAIN FROM THE CHECKPOINT")

    def hurt_player(self, dmg, src=None, forced=False):
        p = STATE.player
        if p is None or self.dying:
            return
        if self.turn is not None and not forced:
            return          # the Guards are not what ends this one
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
        if self.turn is None:
            self._move(k, dt)
        else:
            self._turn_update(dt)   # he has the floor: no walking out of this
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
        self._pig_update(dt)
        self._well(dt)
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
            if getattr(self, "death_by_bodi", False):
                # His round: the camera drops back and down off the shoulder, the
                # body stays in the left of frame, and he never leaves the shot.
                b = self.brain.bodi
                dx, dz = self.px - b["x"], self.pz - b["z"]
                n = math.hypot(dx, dz) or 1.0
                dx, dz = dx / n, dz / n
                rg = _right(self.yaw)
                d = _ease(clamp((self.death_t - 0.08) / 0.7, 0.0, 1.0))
                # step back off the body, but not into the crates behind it
                pivot = (self.px, 1.45, self.pz)
                back = min(2.3, max(0.7, self.world.ray_hit(pivot, (dx, 0.0, dz), 2.65) - 0.35))
                fall = (self.px + dx * back + rg[0] * 0.62, 1.18,
                        self.pz + dz * back + rg[2] * 0.62)
                eye = tuple(eye[i] + (fall[i] - eye[i]) * d for i in range(3))
                tgt = (b["x"], b["y"] + 1.10, b["z"])
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
        self._pig_scare()
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
        # The pig is a target, not scenery: take its blocking box out of the
        # world for the pellet pass so the sphere below decides the hit.
        pig_block = self.world.pig_at
        self.world.pig_at = None
        hits = {}
        impact_pts = []
        lanes = []
        farthest = 0.0
        any_enemy = False
        any_head = False
        pig_pellets = 0
        bodi_pellets = 0
        for dy, dp in PELLET_FAN:
            dd = _fwd(self.yaw + dy * cone, look_pitch + dp * cone)
            best = self.world.ray_hit(o, dd, 70.0)
            hit_e, head, hit_pig, hit_bodi = None, False, False, False
            for e in self.brain.enemies:
                if not e["alive"] or not e["live"]:
                    continue
                for c, rad, is_head in self.brain.spheres(e):
                    h = B._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_e, head = h, e, is_head
            if self.turn is not None:
                # Bodi is unkillable once he turns: the pellets spark, they do
                # not damage. Chest sphere, then head, whichever is nearer.
                bd = self.brain.bodi
                for cy, rad in ((bd["y"] + 1.15, 0.42), (bd["y"] + 1.62, 0.22)):
                    h = B._ray_sphere(o, dd, (bd["x"], cy, bd["z"]), rad)
                    if h is not None and h < best:
                        best, hit_e, head, hit_pig, hit_bodi = h, None, False, False, True
            if not self.pig["dead"]:
                centre = (self.pig["x"], PIG_HIT_Y, self.pig["z"])
                h = B._ray_sphere(o, dd, centre, PIG_HIT_R)
                if h is not None and h < best:
                    best, hit_e, head, hit_pig = h, None, False, True
            end = (o[0] + dd[0] * best, o[1] + dd[1] * best, o[2] + dd[2] * best)
            lanes.append(end)
            farthest = max(farthest, best)
            if hit_bodi:
                bodi_pellets += 1
                impact_pts.append((end, "spark"))
            elif hit_pig:
                pig_pellets += 1
                impact_pts.append((end, "blood"))
            elif hit_e is None:
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
        self.world.pig_at = pig_block
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
        if pig_pellets:
            self.pig_shot(pig_pellets)
        if bodi_pellets:
            # He does not even flinch. One line, once, and he keeps coming.
            self.hit_mark = self.t
            self._snd("impact", True)
            if self.turn is not None and not self.turn.get("taunt"):
                self.turn["taunt"] = True
                self.say("BODI", "Not tonight, Biribel. Not over a pig.", 3.0)
        if any_enemy:
            self.hit_mark = self.t
            self._snd("headshot" if any_head else "impact", True)
        else:
            self._snd("impact", False)

    def _blow_tank(self):
        self.tank_blown = self.t
        self._pig_scare()
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
        if self.turn is not None:
            self.hold = 0.0
            return
        who = self.brain.near_revive()
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        if who is None or not held:
            self.hold = 0.0
            return
        self.hold += dt
        if who == "alex":
            # step in to the end of the fallen beam and face along it
            k = min(1.0, dt * 12.0)
            self.px += (W.WELL_LIFT_AT[0] - self.px) * k
            self.pz += (W.WELL_LIFT_AT[1] - self.pz) * k
            self.body_yaw = 270.0
        if self.hold >= HOLD_S[who]:
            self.hold = 0.0
            self.brain.help_done(who)

    # --- the pig -----------------------------------------------------------------

    def _pig_scare(self):
        """Gunfire (either side), the tank blast or the barn fire sends it off."""
        p = self.pig
        if p["scared"] or p["dead"]:
            return
        p["scared"] = True
        p["mode"] = "flee"
        p["tx"], p["tz"] = PIG_HIDE

    def pig_shot(self, pellets=1):
        """Pellets found the pig. One barrel of Fallow 12 is enough."""
        p = self.pig
        if p["dead"] or pellets < PIG_HIT_MAX:
            return False
        p["dead"] = True
        p["fell_at"] = self.t
        p["mode"] = "down"
        self.pig_dead = True
        STATE.m7_pig_dead = True
        STATE.m7_pig_at = (p["x"], p["z"])
        self.world.pig_at = (p["x"], p["z"])       # the body is still in the yard
        self.hit_mark = self.t
        self._snd("pig_squeal")
        self._snd("impact", True)
        # The night turns here. If Bodi is already down there is no betrayal to
        # play, and the checkpoint clock still owns that attempt.
        if self.brain.bodi_turn() and self.turn is None:
            self.turn = {"phase": "stare", "t": self.t, "shot": False, "taunt": False,
                         "raised_at": None, "bodi": True}
            self.say("BODI", "That pig was Maru's. She raised it by hand.", 3.4)
            self.say("ALEX", "Bodi? Bodi, what are you doing?", 3.4)
        return True

    # --- the betrayal ------------------------------------------------------------

    def _look_at(self, x, y, z, k=0.2):
        """Ease the view onto a point (yaw, then pitch, solved from the camera)."""
        yaw, pitch = self.yaw, self.pitch
        for _ in range(4):
            eye, _t, _f, _d = self.camera()
            dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
            self.yaw = _yaw(dx, dz) % 360.0
            self.pitch = clamp(math.degrees(math.atan2(dy, math.hypot(dx, dz))), *PITCH_LIM)
        ty, tp = self.yaw, self.pitch
        self.yaw = (yaw + _wrap(ty - yaw) * k) % 360.0
        self.pitch = pitch + (tp - pitch) * k

    def _turn_update(self, dt):
        """Stare, close the distance, shoulder the rifle, fire - in that order.

        Bodi is driven from here, not from ``raid_brain``: the brain leaves him
        in ``state == "turned"`` and only turns to face you. The player is rooted
        (no moving out of it), nothing else can damage them, and pellets that
        reach him spark off him for nothing.
        """
        b = self.brain.bodi
        st = self.turn
        age = self.t - st["t"]
        # he never stops looking at you, and he never runs
        b["yaw"] = _yaw(self.px - b["x"], self.pz - b["z"]) % 360.0
        b["moving"] = False
        b["goal"] = None
        self.vel = (0.0, 0.0)
        self.pmoving = False
        self.sprint = False
        self.stride += 0.0
        self.body_yaw = _w.yaw_mix(self.body_yaw, self.yaw, min(1.0, dt * 8.0))
        if st["phase"] == "stare":
            self.aiming = True          # shouldered on him: it does not help
            self._look_at(b["x"], 1.55, b["z"], 0.22)
            if age > TURN_STARE:
                st["phase"], st["t"] = "close", self.t
        elif st["phase"] == "close":
            self._look_at(b["x"], 1.55, b["z"], 0.3)
            d = math.hypot(self.px - b["x"], self.pz - b["z"])
            if d > TURN_CLOSE_M:
                self.brain._walk(b, self.px, self.pz, TURN_WALK, dt, 0.34)
                b["yaw"] = _yaw(self.px - b["x"], self.pz - b["z"]) % 360.0
            if d <= TURN_CLOSE_M or age > TURN_CLOSE_MAX:
                st["phase"], st["t"] = "raise", self.t
                self.say("BODI", "You don't walk out of this yard.", 3.2)
        elif st["phase"] == "raise":
            self.aiming = True
            self._look_at(b["x"], 1.5, b["z"], 0.4)
            b["aim"] = self.t
            b["slope"] = -0.12
            if st["raised_at"] is None:
                st["raised_at"] = self.t
            b["raised"] = st["raised_at"]
            if age > TURN_AIM_S:
                st["phase"], st["t"] = "fire", self.t
        if st["phase"] in ("fire", "done"):
            b["aim"] = self.t
            b["slope"] = -0.12
            self._look_at(b["x"], 1.4, b["z"], 0.5)
        if st["phase"] == "fire" and not st["shot"]:
            st["shot"] = True
            st["phase"] = "done"
            st["t"] = self.t
            self._turn_execute()

    def _turn_execute(self):
        """One round, point blank, in the middle of the frame."""
        b = self.brain.bodi
        muzzle = b.get("muzzle") or (b["x"], b["y"] + 1.45, b["z"])
        x, y, z = self.px, 0.72, self.pz
        self.tracer(muzzle, (x, y, z))
        self.flash(muzzle)
        self.impacts.append((self.t, (x, y, z), "blood"))
        for i in range(-1, 2):
            self.impacts.append((self.t + 0.02 * abs(i), (x + 0.22 * i, y - 0.18 + 0.12 * i, z),
                                 "blood"))
        self.cam_kick = min(2.6, self.cam_kick + 2.2)
        self.hurt = 1.0
        self.hurt_player(999.0, (b["x"], b["z"]), forced=True)
        if self.dying:
            self.death_msg = TURN_DEATH_MSG
            self.death_by_bodi = True

    def _dead_pig_mesh(self):
        """The standing pig, rolled onto its side and set down on the grass."""
        if self._pig_dead_mesh is None:
            from engine3d.core import Mesh
            src = F.pig()
            verts = [(x, 0.27 + z, -y) for (x, y, z) in src.verts]
            self._pig_dead_mesh = Mesh(verts, src.faces)
        return self._pig_dead_mesh

    def _pig_update(self, dt):
        """Grazes by the trough until spooked, then bolts for the fence corner
        and shuffles out of reach if anyone walks up to it there."""
        p = self.pig
        if p["dead"]:
            self.world.pig_at = (p["x"], p["z"])
            return
        if not p["scared"]:
            if self.fire.lit or math.hypot(self.px - p["x"], self.pz - p["z"]) < 2.3:
                self._pig_scare()
        elif p["mode"] in ("graze", "hide") and self.t - p["shy_t"] > 3.0 \
                and math.hypot(self.px - p["x"], self.pz - p["z"]) < 1.7:
            p["shy_t"] = self.t
            p["tx"] = clamp(PIG_HIDE[0] + self._pig_rng.uniform(-1.2, 1.2), -19.4, -17.4)
            p["tz"] = clamp(PIG_HIDE[1] + self._pig_rng.uniform(-1.2, 1.2), -15.7, -13.9)
            p["mode"] = "walk"
        if p["mode"] in ("graze", "hide"):
            home = PIG_HIDE if p["scared"] else (F.PIG_HOME[0], F.PIG_HOME[1])
            p["yaw"] += math.sin(self.t * 0.9) * dt * 7.0      # rooting sway
            if self.t >= p["next"]:
                a = self._pig_rng.uniform(0.0, math.tau)
                rad = self._pig_rng.uniform(0.4, 0.8 if p["scared"] else 1.7)
                p["tx"] = home[0] + math.cos(a) * rad
                p["tz"] = home[1] + math.sin(a) * rad
                if not p["scared"]:        # grazing stays by the trough
                    p["tx"] = clamp(p["tx"], 15.6, 19.2)
                    p["tz"] = clamp(p["tz"], -12.0, -7.6)
                p["mode"] = "walk"
        elif p["mode"] in ("walk", "flee"):
            dx, dz = p["tx"] - p["x"], p["tz"] - p["z"]
            d = math.hypot(dx, dz)
            step = min(d, (4.4 if p["mode"] == "flee" else 0.6) * dt)
            ox, oz = p["x"], p["z"]
            self.world.pig_at = None          # the pig does not block itself
            nx, nz = self.world.move(ox, oz, dx / d * step if d else 0.0,
                                     dz / d * step if d else 0.0, r=0.3)
            self.world.pig_at = (p["x"], p["z"])
            moved = math.hypot(nx - ox, nz - oz)
            p["x"], p["z"] = nx, nz
            p["gait"] += moved
            p["yaw"] = _yaw(dx, dz)
            if moved > step * 0.05:                 # sliding along a box is progress
                p["stuck"] = 0.0
            else:
                p["stuck"] += dt
            if d < 0.12 or p["stuck"] > 0.6:        # arrived, or truly wedged
                p["stuck"] = 0.0
                p["mode"] = "hide" if p["scared"] else "graze"
                p["next"] = self.t + (self._pig_rng.uniform(1.2, 3.2) if p["scared"]
                                      else self._pig_rng.uniform(2.5, 6.5))
        self.world.pig_at = (p["x"], p["z"])

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
        elif (self.phase == "w3" and not b.pending(3) and not b.alex["pinned"]
              and not b.alex.get("to_well") and not b.alex.get("cover_t")):
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
            # Alex runs for cover at the well; the frame comes down on him there
            b.alex["to_well"] = self.t
            self.say("BODI", "That's my barn.", 2.6)
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

    def _tank_lights(self):
        """A hard ignition flash, rolling fireball light, then burning fuel."""
        if self.tank_blown is None:
            return []

        age = self.t - self.tank_blown
        if not 0.0 <= age < 45.0:
            return []

        cx, cy, cz = W.TANK_AT
        fade = 1.0 - _ease(clamp((age - 28.0) / 17.0, 0.0, 1.0))
        flicker = (
            0.84
            + 0.10 * math.sin(self.t * 11.7)
            + 0.06 * math.sin(self.t * 19.3 + 1.2)
        )

        flash = math.exp(-age * 15.0)
        fireball = max(0.0, 1.0 - age / 2.2) ** 1.5

        return [{
            "pos": (cx, cy + 0.8, cz),
            "color": (255, 218, 155) if age < 0.12 else (255, 142, 48),
            "intensity": (
                4.0 * flash + 2.4 * fireball + 1.15 * flicker * fade
            ),
            "range": 10.0 + 16.0 * max(flash, fireball),
        }]

    def _lights(self, tm):
        now = self.t

        # Reserve room for the tank and the two fixed lamps.
        out = self._tank_lights()

        out += [
            {
                "pos": pos,
                "color": (255, 196, 120),
                "intensity": 1.3,
                "range": 5.0,
            }
            for t0, pos in self.flashes[-2:]
            if now - t0 < 0.07
        ]

        fire_lights = self.fire.lights(tm, now)
        out += fire_lights[:max(0, 6 - len(out))]

        # Headlights add no local light: point lights are additive and wash the
        # Guard's dark uniforms grey.  The beam is the road pools (``_beam_pools``)
        # and the lamp glows, which leave the men and the truck moonlit.
        out.extend([
            {
                "pos": F.PORCH_LAMP,
                "color": (255, 190, 110),
                "intensity": 1.15,
                "range": 13.0,
            },
            {
                "pos": F.BARN_LAMP,
                "color": (255, 180, 100),
                "intensity": 1.05,
                "range": 12.0,
            },
        ])
        return out

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
                         size=RES, park=park, well_roof=False)
        del _w.LAST[:]
        r.set_pools(F.raid_pools(
            self.fire.lights(tm, self.t)
            + self._tank_lights()
            + self._beam_pools()
        ))
        F.raid_fx(r, tm)
        self.wreck.draw(r)
        if self._truck is None:
            self._truck = W.truck()
            self._ledge = W.ledge()
        if self.flags["loft"]:
            _w.add(r, self._ledge)
        for t in self.brain.trucks:
            if t["state"] != "wait":
                W.put(r, self._truck, t["x"], 0.0, t["z"], 0.0)
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
        pm = self.pig
        if pm["dead"]:
            r.add_sprite(
                (pm["x"], 0.03, pm["z"]),
                F.pool((104, 16, 18), 1.05, intensity=0.62, squash=1.0),
                layer=_fx.FX_LAYER,
            )
            W.put(r, self._dead_pig_mesh(), pm["x"], 0.0, pm["z"], pm["yaw"])
        else:
            moving = pm["mode"] in ("walk", "flee")
            from cutscenes.m7pig3d import walking_frame
            pig_mesh = self._pig_walk[walking_frame(pm["gait"])] if moving else self._pig_mesh
            W.put(r, pig_mesh, pm["x"], 0.0, pm["z"], pm["yaw"])
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

        if self.tank_blown is None:
            if self.flags["shed"]:
                r.add_sprite(
                    (cx, cy + 0.9, cz),
                    W.tank_glow(tm, True),
                    layer=_fx.FX_LAYER,
                )
            return

        age = self.t - self.tank_blown
        if not 0.0 <= age < 45.0:
            return

        start_ms = self.tank_blown * 1000.0
        fade = 1.0 - _ease(clamp((age - 28.0) / 17.0, 0.0, 1.0))

        # IGNITION: a very short white-hot flash, not a sustained orange orb.
        if age < 0.32:
            flash = (1.0 - age / 0.32) ** 2
            r.add_sprite(
                (cx, cy + 0.45, cz),
                _fx.glow(
                    (255, 184, 75),
                    2.2 + age * 11.0,
                    tm,
                    core=(255, 250, 220),
                    intensity=3.0 * flash,
                    max_px=300,
                ),
                layer=_fx.FX_LAYER,
            )

        # FIREBALL: several expanding, rising lobes with staggered ignition.
        if age < 2.35:
            for i in range(7):
                delay = 0.025 * i
                a = age - delay
                if not 0.0 <= a < 2.15:
                    continue

                ang = i * 2.399963
                expansion = 1.0 - math.exp(-a * 6.0)
                collapse = 1.0 - _ease(clamp((a - 0.65) / 1.5, 0.0, 1.0))
                radius = (0.55 + 1.35 * expansion) * collapse
                spread = (0.4 + 2.4 * expansion) * (0.7 + 0.3 * (i % 2))

                if radius > 0.03:
                    F.fire(
                        r,
                        (
                            cx + math.cos(ang) * spread,
                            max(0.25, cy - 0.4) + a * (1.1 + 0.12 * i),
                            cz + math.sin(ang) * spread,
                        ),
                        tm,
                        seed=91 + i * 13,
                        size=radius,
                    )

        # PRESSURE FRONT: an expanding, low dust ring.
        if age < 1.15:
            k = age / 1.15
            radius = 0.6 + 10.5 * k
            strength = 0.30 * (1.0 - k) ** 2

            for i in range(10):
                ang = i * math.tau / 10.0
                r.add_sprite(
                    (
                        cx + math.cos(ang) * radius,
                        0.15 + 0.3 * k,
                        cz + math.sin(ang) * radius,
                    ),
                    _fx.haze(
                        (125, 108, 88),
                        0.65 + 1.4 * k,
                        tm,
                        seed=220 + i,
                        intensity=strength,
                    ),
                    layer=_fx.FX_LAYER,
                )

        # FRAGMENTS: short ballistic streaks, cooling as they travel.
        if age < 2.8:
            for i in range(20):
                ang = i * 2.399963
                speed = 3.0 + (i % 6) * 0.85
                vx = math.cos(ang) * speed
                vz = math.sin(ang) * speed
                vy = 4.0 + (i % 7) * 0.75

                y = cy + vy * age - 4.9 * age * age
                if y <= 0.08:
                    continue

                tail_age = max(0.0, age - 0.035)
                tail_y = cy + vy * tail_age - 4.9 * tail_age * tail_age
                hot = max(0.0, 1.0 - age / 2.8)
                col = (
                    int(120 + 135 * hot),
                    int(58 + 150 * hot),
                    int(28 + 70 * hot),
                )

                r.add_line3d(
                    (cx + vx * tail_age, tail_y, cz + vz * tail_age),
                    (cx + vx * age, y, cz + vz * age),
                    col,
                    2 if i % 4 == 0 else 1,
                    layer=3,
                )

        # Initial sparks and a delayed secondary shower.
        for delay, seed, count, speed in (
            (0.0, 5, 65, 11.0),
            (0.22, 17, 35, 7.0),
        ):
            a = age - delay
            if 0.0 <= a < 2.4:
                r.add_sprite(
                    (cx, cy + 0.5, cz),
                    F.sparks(
                        tm,
                        start_ms + delay * 1000.0,
                        seed=seed,
                        n=count,
                        speed=speed,
                        life=2.4,
                    ),
                    layer=_fx.FX_LAYER,
                )

        # BURNING FUEL: a broad base with independently moving flame tongues.
        fuel = _ease(clamp(age / 0.55, 0.0, 1.0)) * fade
        if fuel > 0.01:
            for i in range(6):
                ang = i * 2.399963
                spread = 0.0 if i == 0 else 0.85 + 0.23 * (i % 3)
                pulse = (
                    0.86
                    + 0.10 * math.sin(self.t * 5.7 + i * 2.1)
                    + 0.07 * math.sin(self.t * 9.3 + i)
                )
                size = 1.45 if i == 0 else 0.85 + 0.16 * (i % 3)
                size *= fuel * pulse

                F.fire(
                    r,
                    (
                        cx + math.cos(ang) * spread,
                        0.18,
                        cz + math.sin(ang) * spread,
                    ),
                    tm,
                    seed=310 + i * 19,
                    size=size,
                )

            r.add_sprite(
                (cx, 0.06, cz),
                F.pool(
                    (255, 115, 32),
                    3.8,
                    intensity=0.42 * fuel,
                    squash=0.5,
                ),
                layer=_fx.FX_LAYER,
            )

        # Rising smoke: staggered puffs with coherent upward travel and drift.
        if age > 0.3:
            for i in range(8):
                born = 0.3 + i * 0.58
                if age < born:
                    continue

                a = (age - born) % 4.64
                k = a / 4.64
                envelope = (
                    _ease(clamp(a / 0.45, 0.0, 1.0))
                    * (1.0 - _ease(clamp((k - 0.65) / 0.35, 0.0, 1.0)))
                    * fade
                )
                if envelope < 0.01:
                    continue

                r.add_sprite(
                    (
                        cx + a * 0.42 + math.sin(i * 2.3 + a) * 0.35,
                        cy + 1.1 + a * 1.65,
                        cz + a * 0.18 + math.cos(i * 1.7 + a) * 0.3,
                    ),
                    _fx.haze(
                        (62, 57, 53),
                        1.1 + a * 0.55,
                        tm,
                        seed=440 + i,
                        intensity=0.46 * envelope,
                    ),
                    layer=_fx.FX_LAYER,
                )

        # Small recurring ember showers keep the aftermath alive.
        if age > 1.0 and fade > 0.05:
            cycle = int((age - 1.0) / 1.8)
            ember_start = start_ms + (1.0 + cycle * 1.8) * 1000.0
            r.add_sprite(
                (cx, 0.65, cz),
                F.sparks(
                    tm,
                    ember_start,
                    seed=600 + cycle % 7,
                    n=max(1, int(14 * fade)),
                    speed=2.8,
                    life=1.8,
                ),
                layer=_fx.FX_LAYER,
            )

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
        lift = self._help_k()
        if lift > 0.0:
            # both hands under the roof's crossbeam: squat, then drive up with the legs
            pose = blend(LIFT_LOW, LIFT_HIGH, _ease(lift))
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
        pose = _held(hum, pose, "shotgun", mode, ("m7player", mode))
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

    def _ally_pose(self, a, key):
        if a["state"] == "down":
            return dict(POSES["slump"])
        if a.get("pinned"):
            pose = self._pinned_pose(a, key)
            k = (self.t - a.get("pinned_t", -9.0)) / KNOCK_S
            if k < 1.0:
                # thrown flat out of the crouch as the beam lands
                return blend(self._cover_pose(key), pose, _ease(k))
            return pose
        if a.get("cover_t") is not None:
            return self._cover_pose(key)
        stance = _hold_cached(_w.hum(key), dict(POSES["ready"]), _ally_gun(key), "ready", key=key)
        rise = (self.t - a.get("freed", -9.0)) / B.ALEX_RISE_S
        if rise < 1.0:
            # out from under the roof: push up onto a knee, take the rifle, stand
            rise = max(0.0, rise)
            if rise < RISE_KNEE:
                return blend(self._pinned_pose(a, key, 1.0), POSES["kneel"], _ease(rise / RISE_KNEE))
            knee = _hold_cached(_w.hum(key), dict(POSES["kneel"]), _ally_gun(key), "ready", key=key)
            return blend(knee, stance, _ease((rise - RISE_KNEE) / (1.0 - RISE_KNEE)))
        if self.t - a["aim"] < B.ALLY_HOLD:
            # shouldered at the target, raised over ALLY_RAISE from the ready hold
            aim = _ally_aim(key, a["slope"])
            up = clamp((self.t - a["raised"]) / B.ALLY_RAISE, 0.0, 1.0)
            stance = aim if up >= 1.0 else blend(stance, aim, _ease(up))
        k = a.get("walk_k", 0.0)
        if k <= 0.0:
            return stance
        # stride follows distance walked, and the eased weight fades run <-> stance
        # so a stop or a start never snaps the legs and arms in one frame; the run
        # keeps the ready hold's arms, so the rifle stays in both hands
        run = _held(_w.hum(key), pose_run(a.get("gait", 0.0) * 1.9, lean=6), _ally_gun(key), "ready", key)
        return run if k >= 1.0 else blend(stance, run, k * k * (3.0 - 2.0 * k))

    def _help_k(self):
        """How far Biribel is through freeing Alex, 0..1."""
        if self.brain.near_revive() != "alex":
            return 0.0
        return clamp(self.hold / HOLD_S["alex"], 0.0, 1.0)

    def _well(self, dt):
        """Run the well frame: it goes once Alex has been in cover a moment, the
        first landing pins him, Biribel's hold lifts it, and every hit is heard."""
        a, wk = self.brain.alex, self.wreck
        if a.get("cover_t") is not None and self.t - a["cover_t"] >= WELL_CREAK_S:
            wk.topple()
        lift = self._help_k() if a.get("pinned") else 0.0
        wk.update(dt, lift if lift > 0.0 else None)
        for kind, speed in wk.events:
            if kind == "frame" and a.get("cover_t") is not None:
                a["cover_t"] = None
                a["pinned"], a["pinned_t"], a["yaw"] = True, self.t, 180.0
                self.say("ALEX", "I'm pinned! Biribel, I'm pinned!", 3.4)
                self.world.boxes.extend(wk.boxes())
                self._unstick()
            if kind == "frame" and speed > 2.0:
                self._snd("tailgate")
            else:
                self._snd("impact", False)
        del wk.events[:]

    def _unstick(self):
        """Step Biribel clear if the frame came down where they stood."""
        if not self.world.blocked(self.px, self.pz):
            return
        for rad in (0.3, 0.6, 0.9, 1.2, 1.6):
            for i in range(12):
                ang = i * math.pi / 6.0
                x, z = self.px + rad * math.sin(ang), self.pz + rad * math.cos(ang)
                if not self.world.blocked(x, z):
                    self.px, self.pz = x, z
                    return

    def _pinned_pose(self, a, key, look=None):
        """Alex face down with the well roof across his legs: he claws at the dirt
        and heaves against it, kicks, ducks each round that lands near, and drags
        himself out hand over hand as Biribel lifts (``look`` 0..1)."""
        if look is None:
            look = self._help_k()
        t, calm = self.t, 1.0 - look
        heave = max(0.0, math.sin(t * 2.2)) ** 3 * calm
        claw = math.sin(t * 5.3) * calm
        pull = math.sin(look * math.pi * 3.0)
        duck = max(0.0, 1.0 - (t - a.get("flinch", -9.0)) / 0.35) * calm
        kick = max(0.0, math.sin(t * 3.4 + 1.0)) * calm
        p = dict(POSES["prone"])
        p.update(spine=p["spine"] - 14.0 * heave + 10.0 * duck,
                 head_p=p["head_p"] - 10.0 * heave + 30.0 * duck,
                 head_y=12.0 * math.sin(t * 0.9) * calm,
                 lsh_p=p["lsh_p"] - 50.0 * heave + 14.0 * claw + 22.0 * pull,
                 rsh_p=p["rsh_p"] - 50.0 * heave - 14.0 * claw - 22.0 * pull,
                 lel=p["lel"] + 40.0 * heave + 25.0 * max(0.0, -pull),
                 rel=p["rel"] + 40.0 * heave + 25.0 * max(0.0, pull),
                 lkn=p["lkn"] + 26.0 * kick, rkn=p["rkn"] + 26.0 * (calm - kick))
        return p

    def _cover_pose(self, key):
        return _hold_cached(_w.hum(key), dict(POSES["crouch"]), _ally_gun(key), "ready", key=key)

    def _alex_armed(self, a):
        return not a.get("pinned") and (self.t - a.get("freed", -9.0)) / B.ALEX_RISE_S >= RISE_KNEE

    def _draw_allies(self, r, tm):
        b = self.brain
        for name, a in (("bodi", b.bodi), ("alex", b.alex)):
            if a["state"] == "gone":
                continue
            key = ("ally", name)
            pose = self._ally_pose(a, key)
            z, yaw, armed = a["z"], a["yaw"], True
            if name == "alex":
                armed = self._alex_armed(a)
                if a.get("pinned"):
                    z -= B.ALEX_CRAWL * self._help_k()
                if a.get("cover_t") is not None:
                    # back to the well: turn to face the yard as he drops into cover
                    k = _ease(clamp((self.t - a["cover_t"]) / 0.3, 0.0, 1.0))
                    yaw = a["yaw"] + ((180.0 - a["yaw"] + 180.0) % 360.0 - 180.0) * k
            joints = _w.actor(r, key, pose, (a["x"], a["y"], z), yaw, int(tm),
                              seed=61 if name == "bodi" else 62, amp=0.3, rifle_on=armed, mouth=0.0)
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
                    W.put(r, W.dog("Death", self.t - e["dead_t"]), x + ux * DOG_PUSH_M * k,
                          0.0, z + uz * DOG_PUSH_M * k, e["yaw"])
                    continue
                bite = (self.t - e["aim"]) * B.BITE_PLAY
                if bite < W.dog_clip_s("Bite"):
                    clip, ct = "Bite", bite
                elif e["moving"]:
                    clip, ct = "Run", e["gait"] / W.DOG_RUN_M * W.dog_clip_s("Run")
                else:
                    clip, ct = "Idle", self.t + e["phase"]
                W.put(r, W.dog(clip, ct), x, 0.0, z, e["yaw"])
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
            if not e["moving"]:
                pose = _hold_cached(_w.hum(gk, True), pose, "rifle", "ready", key=gk)
            stag = max(0.0, 1.0 - (self.t - e["hit_t"]) / 0.3)
            if stag > 0.0:
                # after the hold: rifle_p follows the spine one to one in the
                # solve, so the flinch needs no fresh IK solve per frame
                pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
                if not e["moving"]:
                    pose["rifle_p"] = pose.get("rifle_p", 0.0) - 12.0 * stag
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
