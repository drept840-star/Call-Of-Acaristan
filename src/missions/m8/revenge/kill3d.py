"""Mission 8: Vasile's last moment on the Route 12 gantry.

Vasile talks, a word at a time: "Son.", the price (Maru's team walks in blind
without him), then something warm. Biribel aims; once the price has landed the
player can pull the trigger, once, and the line is cut off mid-word. If the
player never does, Bodi shoots from the foot of the gantry instead. The score
cuts with the shot and only wind is left. One round. Vasile's knees give way and he slumps on the
catwalk where the camera can see him; no last line, no fall out of frame. A few
seconds of quiet, then fade into the chase. The existing rig supplies ground
poses; short accelerating falls and delayed, damped limb motion give the
collapse weight. The witness camera stays planted.

Uses existing assets and rig poses. Lifecycle API and flow results remain:
begin / active / update / draw / handle_event / set_paused / abort /
force_finish; on_kill_done("shot") exactly once.
"""

import bisect
import math
import random

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette, font_terminal, font_terminal_small
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import Mesh, POSES, blend, box, clamp
from engine3d.core import m_apply, m_mul, rot_x, rot_y
from missions.m6 import yard_hud as U
from missions.m7 import raid3d as R

from . import chase3d as C
from . import set3d as S3

VX, VY, VZ = S3.VASILE_AT
# Same mark as beats.BIRIBEL_POS: no teleport after Old Friends.
BX, BZ, BYAW = 6.2, S3.CATWALK_Z, 270.0
# Biribel faces -X at BYAW=270, so +X is behind him and +Z is over his
# left shoulder. The old EYE sat 1.2m back / 0.52m aside: a detached
# full-back view with Biribel looming in the middle distance. This is a
# tight over-the-shoulder: 0.55m back / 0.34m aside, just above shoulder
# height, so he is cropped to the frame edge and Vasile/reticle stay clear.
EYE = (BX + 0.55, VY + 1.74, BZ + 0.34)
# Intro starts a little wider/higher on the same side, then pushes in to
# EYE (previously it pulled backwards, ending even farther behind him).
INTRO_EYE = (BX + 0.97, VY + 1.80, BZ + 0.56)
FOV = 46.0
AIM_YAW, AIM_PITCH, SENS = 16.0, 24.0, 0.10
INTRO_S, RAISE_S = 1.1, 0.55
# His line types out at CPS from LINE_AT seconds into the aim, with PAUSE after
# each full stop. It stops on a half-word and waits. The player can fire once
# the price has landed (FIRE_N characters); the shot cuts the line off wherever
# it has got to. If nobody fires, Bodi does, BODI_S after the line stalls.
LINE = ("Son. Maru's team goes in tonight. I'm the one who cuts the cameras. "
        "Kill me, and they walk in blind. I'm still proud of you. "
        "I'm so proud of what you've becom")
LINE_AT, CPS, PAUSE, BODI_S = 0.45, 15.5, 0.35, 6.0
FIRE_N = LINE.index("blind.") + len("blind.")
_T = [0.0]
for _c in LINE:
    _T.append(_T[-1] + 1.0 / CPS + (PAUSE if _c == "." else 0.0))
DEATH_S, QUIET_S, FADE_S = 4.6, 3.4, 1.2
LOWER_S, HITSTOP_S = 0.85, 0.055
KNEE_AT, COLLAPSE_AT, GROUND_AT, SETTLED_AT = 0.68, 2.5, 3.06, 4.1
CAP_HOLD_S, CAP_OUT_S = 1.8, 0.7
BLOOD = ((118, 12, 16), (82, 8, 12), (148, 22, 24), (56, 5, 8))


def _pool_mesh(cx, cz, rad, col, y, seed=0):
    m = Mesh()
    pts = []
    for i in range(10):
        a = math.tau * i / 10.0
        wob = 0.78 + 0.32 * math.sin(i * 2.7 + seed)
        px = cx + math.cos(a) * rad * wob * 1.18
        pz = clamp(cz + math.sin(a) * rad * wob, S3.CATWALK_Z - 0.65, S3.CATWALK_Z + 0.65)
        pts.append((px, y, pz))
    m.face(pts, col, 1, True)
    return m

_CIG_MESH = None


def _cig_mesh():
    global _CIG_MESH
    if _CIG_MESH is None:
        m = Mesh()
        m.add(box(0.015, 0.015, 0.016, (196, 140, 80), center=(0.0, 0.0, -0.032)))
        m.add(box(0.012, 0.012, 0.056, (236, 232, 222), center=(0.0, 0.0, 0.004)))
        m.add(box(0.014, 0.014, 0.006, (120, 114, 108), center=(0.0, 0.0, 0.035)))
        m.add(box(0.0145, 0.0145, 0.006, (255, 120, 40), center=(0.0, 0.0, 0.041), emissive=True))
        _CIG_MESH = m
    return _CIG_MESH


def _ease(k):
    k = clamp(k, 0.0, 1.0)
    return k * k * (3.0 - 2.0 * k)


def _point(a, b, k):
    return tuple(x + (y - x) * k for x, y in zip(a, b))


def _unit(v):
    length = math.sqrt(sum(x * x for x in v))
    return tuple(x / length for x in v) if length > 1e-9 else (0.0, 0.0, 1.0)


def _yaw_to(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360.0


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _mix(a, b, k):
    keys = set(a) | set(b)
    return {n: a.get(n, 0.0) + (b.get(n, 0.0) - a.get(n, 0.0)) * k for n in keys}


def _full(p):
    """A pose dict with every joint (blend fills NEUTRAL defaults)."""
    return blend(POSES["stand"], p, 1.0)


_KNEEL = dict(POSES["kneel"], spine=18, head_p=-8, head_y=-6,
              lsh_p=-24, lsh_r=-5, lel=76, rsh_p=-12, rsh_r=8, rel=28)
# Preserve the rig's own root height and body pitch for floor contact. Keep the
# body aligned along the catwalk (X); do not roll it through either railing.
_GROUND = dict(POSES["dead_back"], body_r=0, spine=0, twist=0,
               head_p=0, head_y=-8, lhip_p=0, lhip_r=0, lkn=0,
               rhip_p=0, rhip_r=0, rkn=0,
               lsh_p=0, lsh_r=-6, lel=12, rsh_p=0, rsh_r=9, rel=5)
# After the shot the camera rises and slides clear of Biribel's head and the
# lowered gun, so the body on the grating is in plain view.
BODY_EYE, BODY_LOOK, BODY_FOV, BODY_CAM_S = (BX + 0.9, VY + 2.0, BZ - 0.45), (VX - 0.3, VY + 0.3, VZ), 42.0, 1.8
# Seconds, pose, Z offset, yaw, hit-volume height, incoming interpolation.
# The two unsupported drops accelerate into contact instead of easing to a
# halt in mid-air. Supported pauses preserve the existing line/choice timing.
PERFORMANCE = (
    (0.0, _full({}), 0.0, 90.0, 1.8, "ease"),
    (0.10, _full(dict(spine=-10, head_p=-12, twist=-10,
                      lsh_p=8, lsh_r=-8, lel=24, rsh_p=-34, rsh_r=12, rel=42)),
     0.0, 94.0, 1.8, "ease"),
    (0.24, _full(dict(spine=16, head_p=3, twist=-6,
                      lsh_p=-18, lsh_r=-8, lel=66, rsh_p=-28, rsh_r=10, rel=32)),
     0.0, 94.0, 1.72, "ease"),
    (KNEE_AT, _full(dict(_KNEEL, spine=27, head_p=7, rel=18)),
     -0.03, 92.0, 1.15, "fall"),
    (0.9, _full(_KNEEL), -0.03, 92.0, 1.18, "ease"),
    (COLLAPSE_AT, _full(dict(_KNEEL, spine=23, head_p=-3, lel=65, rel=20)),
     -0.03, 92.0, 1.12, "ease"),
    (GROUND_AT, _full(_GROUND), -0.03, 90.0, 0.42, "fall"),
    (DEATH_S, _full(_GROUND), -0.03, 90.0, 0.42, "ease"),
)

# Only these angular joints trail the torso. Root transforms always arrive at
# the ground pose on impact; delaying them would make the whole body hover.
_LIMB_LAG = {"head_p": 0.055, "head_y": 0.07,
             "lsh_p": 0.08, "lsh_r": 0.06, "lel": 0.10,
             "rsh_p": 0.12, "rsh_r": 0.08, "rel": 0.14}


def _performance(age):
    """Pure, time-based sampling: independent of draw calls and frame rate."""
    if age <= PERFORMANCE[0][0]:
        return PERFORMANCE[0][1:5]
    for a, b in zip(PERFORMANCE, PERFORMANCE[1:]):
        if age <= b[0]:
            k = clamp((age - a[0]) / (b[0] - a[0]), 0.0, 1.0)
            k = k * k if b[5] == "fall" else _ease(k)
            return (_mix(a[1], b[1], k), a[2] + (b[2] - a[2]) * k,
                    a[3] + _wrap(b[3] - a[3]) * k, a[4] + (b[4] - a[4]) * k)
    return PERFORMANCE[-1][1:5]


def _settle(age, start, duration, strength, frequency=11.0):
    """Small angular follow-through, exactly zero at both ends; no root bounce."""
    t = age - start
    if t <= 0.0 or t >= duration:
        return 0.0
    envelope = math.exp(-5.0 * t) * (1.0 - _ease(t / duration))
    return strength * math.sin(frequency * t) * envelope


class KillScene:
    _snd = R.RaidScene._snd
    _grab = R.RaidScene._grab
    _project = R.RaidScene._project

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self._reset()

    def _reset(self):
        self.t = self.real = 0.0
        self.phase = "intro"
        dx, dy, dz = VX - EYE[0], VY + 1.25 - EYE[1], VZ - EYE[2]
        self.base_yaw = _yaw_to(dx, dz)
        self.base_pitch = math.degrees(math.atan2(dy, math.hypot(dx, dz)))
        self.yaw_off = self.pitch_off = 0.0
        self.hits = self.shots = 0
        self.nutshot = self.headshot = False
        self.blood_burst = None
        self.floor_stains = []
        self._exit_mesh = None
        self._drip_at = 0.0
        self.hit_t = self.fire_t = -9.0
        self.kick = self.fade = 0.0
        self.firing = False
        self.aim_t = None
        self.cut = self.cut_real = None
        self.death_t = self.closing_t = None
        self.lowered_t = self.end_t = None
        self._witness_from = None
        self.choice = None
        self.lines = []
        self._cue = "unset"
        self._muzzle = self.flash_at = None
        self._flash_basis = None
        self.stop_until = -9.0
        self.blood = []
        self.cig = None
        self.lb = 0.8

    # --- lifecycle -------------------------------------------------------------

    def begin(self):
        self._reset()
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_kill_active = True
        self.audio = None
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._grab(True)
        try:
            hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun",))
            for mode in ("ready", "aim"):
                R._held(hum, POSES["ready"], "shotgun", mode, ("m7player", mode))
            _w.hum("vasile")
            _w.hum("vasile", flags=("cig_dropped",))
            for w in range(4):
                _w.hum("vasile", hd=True, wound=w, bloody=w > 0,
                       flags=("cig_dropped",) if w else ())
            _w.hum("vasile", hd=True, wound=3, bloody=True, flags=("cig_dropped", "head_wound"))
            _w.hum("vasile", hd=True, wound=3, bloody=True, flags=("cig_dropped", "groin_wound"))
            S3.renderer()
        except Exception:
            pass

    def active(self):
        return self._active

    def set_paused(self, paused):
        self.paused = bool(paused)
        self.firing = False
        self._grab(self._active and not self.paused)

    def _release(self):
        self._active = self.paused = False
        self.firing = False
        STATE.m8_kill_active = False
        self._grab(False)
        self._stop_score()
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass

    def finish(self, result="done"):
        if self.done:
            return False
        self.done, self.result = True, result
        self._release()
        from .. import flow as _flow
        return _flow.on_kill_done(result)

    def _stop_score(self):
        self._cue = None
        try:
            audio.fade_out_music(700)
        except Exception:
            pass

    def _score(self):
        # Old Friends runs on from the film through the warm line. The shot cuts
        # it dead: from then on only the wind bed plays, up to the chase.
        # Called every frame: a cue change fades out first, then starts.
        cue = "kill" if self.death_t is None else None
        try:
            if cue is None:
                if self._cue is not None:
                    audio.fade_out_music(40)
            else:
                from .. import m8_audio as _m8_audio
                _m8_audio.music(audio, cue)
        except Exception:
            pass
        self._cue = cue

    def typed(self):
        """How many characters of his line are on screen."""
        if self.cut is not None:
            return self.cut
        if self.aim_t is None:
            return 0
        return min(len(LINE), max(0, bisect.bisect_right(_T, self.t - self.aim_t - LINE_AT) - 1))

    def can_fire(self):
        return self.phase == "aim" and self.death_t is None and self.typed() >= FIRE_N

    def say(self, who, text, dur=3.0):
        self.lines.append((self.real, who, text, dur))
        del self.lines[:-4]

    # --- input / performance clock -------------------------------------------

    def wound_age(self):
        return 0.0 if self.death_t is None else max(0.0, self.t - self.death_t)

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if event.type == pygame.MOUSEMOTION and self.phase == "aim":
            dx, dy = event.rel
            self.yaw_off = clamp(self.yaw_off + dx * SENS, -AIM_YAW, AIM_YAW)
            self.pitch_off = clamp(self.pitch_off - dy * SENS, -AIM_PITCH, AIM_PITCH)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.can_fire():
            self._fire()

    def _choose(self, result):
        if self.choice is not None:
            return
        # Capture once. Recoil decay must not keep moving the starting frame.
        self._witness_from = self.aim_dir()
        self.choice = result
        self.lowered_t = self.t
        self.end_t = self.real if result == "shot" else None
        self.firing = False

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        previous_real = self.real
        self.real += dt
        self._snd("update", dt)
        # Only the non-frozen fraction of this frame advances the performance.
        sdt = max(0.0, self.real - max(previous_real, self.stop_until))
        self.t += sdt
        self.kick = max(0.0, self.kick - dt * 5.0)
        self.lb += (1.0 - self.lb) * min(1.0, dt * 1.5)
        if self.phase == "intro" and self.t >= INTRO_S + RAISE_S:
            self.phase, self.aim_t = "aim", self.t
        if self.phase in ("aim", "wounded", "closing"):
            self._snd("bed", "kill_wind")
        if self.phase == "aim" and self.t - self.aim_t - LINE_AT >= _T[-1] + BODI_S:
            self._fire("bodi")
        keep = []
        for b in self.blood:
            b[4] *= max(0.0, 1.0 - 1.4 * sdt)
            b[6] *= max(0.0, 1.0 - 1.4 * sdt)
            b[5] -= 9.2 * sdt
            b[1] += b[4] * sdt
            b[2] += b[5] * sdt
            b[3] += b[6] * sdt
            if b[2] <= VY + 0.012:
                if (S3.CATWALK_Z - 0.66 <= b[3] <= S3.CATWALK_Z + 0.66
                        and len(self.floor_stains) < 95):
                    self.floor_stains.append((b[1], b[3], b[7] * 1.9, b[8]))
            elif self.t - b[0] < 1.4:
                keep.append(b)
        self.blood = keep
        if self.cig is not None and not self.cig["rest"]:
            c = self.cig
            c["vy"] -= 9.8 * sdt
            c["x"] += c["vx"] * sdt
            c["y"] += c["vy"] * sdt
            c["z"] += c["vz"] * sdt
            c["yaw"] = (c["yaw"] + c["vyaw"] * sdt) % 360.0
            c["pitch"] += c["vpitch"] * sdt
            floor_y = VY + 0.012
            if c["y"] <= floor_y:
                c["y"] = floor_y
                if abs(c["vy"]) > 0.45:
                    c["vy"] = -c["vy"] * 0.25
                    c["vx"] *= 0.42
                    c["vz"] *= 0.42
                    c["vpitch"] *= 0.45
                    c["vyaw"] *= 0.55
                else:
                    c["vy"] = 0.0
                    c["vx"] *= max(0.0, 1.0 - 10.0 * sdt)
                    c["vz"] *= max(0.0, 1.0 - 10.0 * sdt)
                    c["vyaw"] *= max(0.0, 1.0 - 10.0 * sdt)
                    c["vpitch"] *= max(0.0, 1.0 - 10.0 * sdt)
                    c["pitch"] += (0.0 - c["pitch"]) * min(1.0, 18.0 * sdt)
                    if abs(c["vx"]) < 0.02 and abs(c["vz"]) < 0.02 and abs(c["pitch"]) < 1.0:
                        c["vx"] = c["vz"] = c["vyaw"] = c["vpitch"] = c["pitch"] = 0.0
                        c["rest"] = True
        if self.phase == "wounded":
            age = self.wound_age()
            if 0.18 < age < 2.60 and age >= self._drip_at:
                self._drip_at = age + 0.09
                dy = 0.56 if self.nutshot else 1.02 if self.headshot else 0.78
                self.blood.append([self.t, VX - 0.05 + (age * 17 % 1.0 - 0.5) * 0.14,
                                   VY + dy, VZ - 0.03,
                                   0.0, -0.4, 0.0, 0.028, BLOOD[1]])
            if age >= DEATH_S:
                self.phase = "closing"
                self.closing_t = self.death_t + DEATH_S
        if self.phase == "closing":
            elapsed = self.t - self.closing_t
            end = QUIET_S
            self.fade = clamp((elapsed - end) / FADE_S, 0.0, 1.0)
            if elapsed >= end + FADE_S:
                self.finish(self.choice or "lowered")
        if self._active:
            self._score()

    def aim_dir(self):
        y = math.radians(self.base_yaw + self.yaw_off)
        p = math.radians(self.base_pitch + self.pitch_off)
        return (
            math.sin(y) * math.cos(p),
            math.sin(p),
            math.cos(y) * math.cos(p),
        )

    def vasile_spot(self):
        """(x, deck Y, z, yaw, hit height) at the same mark used for drawing."""
        _pose, dz, yaw, h = self._react()
        return VX, VY, VZ + dz, yaw, h

    def _hit_capsule(self):
        """A torso/head volume that folds down with the actual collapse.

        Local forward is +Z. At yaw 90 a backward fall lies along -X, safely
        inside the narrow catwalk. This replaces the old upright-only volume.
        """
        x, y, z, yaw, h = self.vasile_spot()
        k = clamp((self.wound_age() - COLLAPSE_AT) / (GROUND_AT - COLLAPSE_AT), 0.0, 1.0)
        k = k * k if self.death_t is not None else 0.0
        angle = math.radians(yaw)
        forward = (math.sin(angle), 0.0, math.cos(angle))
        a = (x + forward[0] * 0.45 * k, y + 0.26, z + forward[2] * 0.45 * k)
        b = (x - forward[0] * 0.8 * k, y + max(0.26, h - 0.24),
             z - forward[2] * 0.8 * k)
        return a, b, 0.30

    def aim_offsets_at(self, x, y, z):
        """Offsets that put the reticle on a world point."""
        dx, dy, dz = x - EYE[0], y - EYE[1], z - EYE[2]
        return (_wrap(_yaw_to(dx, dz) - self.base_yaw),
                math.degrees(math.atan2(dy, math.hypot(dx, dz))) - self.base_pitch)

    def _fire(self, by="biribel"):
        """The one round, from Biribel or (if he hesitates) Bodi below: it lands
        on the torso and cuts his line off."""
        if self.phase != "aim" or self.death_t is not None:
            return
        self.cut = self.typed()
        self.cut_real = self.real
        d = self.aim_dir()
        self.nutshot = (
            by == "biribel"
            and _capsule_distance(EYE, d, (VX, VY + 0.92, VZ), (VX, VY + 0.95, VZ), 0.13) is not None
        )
        self.headshot = (
            by == "biribel"
            and not self.nutshot
            and _capsule_distance(EYE, d, (VX, VY + 1.62, VZ), (VX, VY + 1.82, VZ), 0.16) is not None
        )
        if self.nutshot:
            hit = (VX, VY + 0.94, VZ)
        elif self.headshot:
            hit = (VX, VY + 1.76, VZ)
        else:
            a, b, _radius = self._hit_capsule()
            hit = tuple((a[i] + b[i]) * 0.5 for i in range(3))
        self.shots += 1
        if by == "bodi":
            self._snd("guard_shot", 0.0, 14.0)      # a hunting rifle, from below
        else:
            self.fire_t = self.t
            self.kick = 1.0
            self._snd("shot")
        self.hits += 1
        self.hit_t = self.t
        self.stop_until = self.real + HITSTOP_S
        self._snd("body_hit", self.hits, self.headshot, True, GROUND_AT - 0.1)
        self._spray(d, hit)
        self.blood_burst = (self.t, (hit[0] - 0.28, hit[1], hit[2]))
        self._exit_mesh = self._build_exit_splat()
        self._drip_at = 0.18
        try:
            places, _joints, root = _w.hum("vasile").pose_world(
                dict(PERFORMANCE[0][1]), (VX, VY, VZ), 90.0, rifle_on=False)
            _, _, head_m, head_org, _, _ = next(pl for pl in places if pl[1] == "head")
            off = m_apply(head_m, (0.0473, 0.0488, 0.1589))
            cx, cy, cz = (off[i] + head_org[i] + root[i] for i in range(3))
        except Exception:
            cx, cy, cz = VX + 0.16, VY + 1.72, VZ - 0.05
        self.cig = dict(x=cx, y=cy, z=cz, vx=0.45, vy=0.35, vz=-0.35,
                        yaw=108.0, pitch=12.0, vyaw=240.0, vpitch=520.0, rest=False)
        self.death_t = self.t
        self.phase = "wounded"
        self._choose("shot" if by == "biribel" else "bodi")

    def _spray(self, d, at):
        hx, hy, hz = at
        rng = random.Random(self.shots * 31 + (7 if self.headshot else 3 if self.nutshot else 0))
        # High-velocity 12-gauge exit cone blasting out behind him (-x)
        for _ in range(38):
            speed = rng.uniform(2.6, 7.6)
            self.blood.append([self.t, hx - 0.12, hy, hz,
                               d[0] * speed + rng.uniform(-0.8, 0.3),
                               rng.uniform(-0.5, 1.4), d[2] * speed + rng.uniform(-1.3, 1.3),
                               rng.uniform(0.025, 0.060), rng.choice(BLOOD)])
        # Front/side splash & dark clots
        for _ in range(18):
            speed = rng.uniform(0.9, 2.8)
            self.blood.append([self.t, hx, hy, hz,
                               rng.uniform(-1.2, 1.4), rng.uniform(0.1, 1.3),
                               rng.uniform(-1.2, 1.2),
                               rng.uniform(0.022, 0.055), rng.choice(BLOOD)])

    def _build_exit_splat(self):
        rng = random.Random(901 + (2 if self.headshot else 1 if self.nutshot else 0))
        m = Mesh()
        for i in range(28):
            x = VX - 0.15 - rng.random() ** 0.75 * 2.1
            z = clamp(VZ + rng.uniform(-0.58, 0.58), S3.CATWALK_Z - 0.62, S3.CATWALK_Z + 0.62)
            rw, rd = rng.uniform(0.05, 0.22), rng.uniform(0.03, 0.12)
            col = rng.choice(((64, 7, 10), (96, 12, 16), (48, 5, 8)))
            m.face([(x - rw, VY + 0.008, z - rd), (x + rw, VY + 0.008, z - rd * 0.7),
                    (x + rw * 0.8, VY + 0.008, z + rd), (x - rw * 0.7, VY + 0.008, z + rd * 0.8)],
                   col, 1, True)
        # Splatters across the back catwalk railing behind him
        for _ in range(7):
            x = VX - rng.uniform(0.4, 2.0)
            y = VY + rng.uniform(0.25, 1.05)
            z = S3.CATWALK_Z + 0.68
            r = rng.uniform(0.04, 0.11)
            m.face([(x - r, y - r, z), (x + r, y - r, z), (x + r, y + r, z), (x - r, y + r, z)],
                   (72, 8, 12), 2, True)
        return m

    # --- staging --------------------------------------------------------------

    def _death_progress(self):
        return clamp(self.wound_age() / DEATH_S, 0.0, 1.0)

    def _react(self):
        age = self.wound_age()
        if self.death_t is None:
            return PERFORMANCE[0][1:5]
        if age >= DEATH_S:
            pose, dz, yaw, height = PERFORMANCE[-1][1:5]
            return pose, dz, yaw, height
        base, dz, yaw, height = _performance(age)
        pose = dict(base)
        for joint, lag in _LIMB_LAG.items():
            delayed, _, _, _ = _performance(max(0.0, age - lag))
            pose[joint] = delayed.get(joint, 0.0)
        # Knees arrest the first drop; head and shoulders continue briefly.
        pose["head_p"] += _settle(age, KNEE_AT, 0.5, 13.0)
        pose["spine"] += _settle(age, KNEE_AT, 0.42, 6.0)
        # Torso is already grounded. Only the limbs lose their residual motion.
        duration = SETTLED_AT - GROUND_AT
        pose["head_p"] += _settle(age, GROUND_AT + 0.04, duration - 0.04, -8.0)
        pose["lel"] += _settle(age, GROUND_AT + 0.09, duration - 0.09, 20.0, 12.0)
        pose["rel"] += _settle(age, GROUND_AT + 0.14, duration - 0.14, 28.0, 10.0)
        # A second hit adds local follow-through, never lifts or restarts him.
        if self.hits == 2:
            impulse = _settle(self.t, self.hit_t, 0.4, 9.0, 14.0)
            pose["head_y"] += impulse
            pose["rel"] += impulse * 0.5
        if self.nutshot and age < GROUND_AT:
            k = _ease(age / 0.35) * (1.0 - _ease((age - COLLAPSE_AT) / (GROUND_AT - COLLAPSE_AT)))
            clutch = dict(pose, spine=pose["spine"] + 18.0, head_p=pose["head_p"] + 16.0,
                          lsh_p=32.0, lsh_r=2.0, lsh_y=35.0, lel=72.0,
                          rsh_p=32.0, rsh_r=2.0, rsh_y=-35.0, rel=72.0)
            pose = _mix(pose, clutch, k)
        return pose, dz, yaw, height

    def cine(self):
        if self.death_t is None:
            return ("intro", self.t) if self.phase == "intro" else (None, 0.0)
        return "witness", self.wound_age()

    def camera(self):
        shot, elapsed = self.cine()
        if shot == "intro":
            # Match the final Old Friends shot's side and eyeline, then push
            # in to the planted shoulder position rather than pulling back.
            k = _ease(self.t / INTRO_S)
            eye = _point(INTRO_EYE, EYE, k)
            target = _point((VX, VY + 1.5, VZ), (VX, VY + 1.0, VZ), k)
            return eye, target, 32.0 + (FOV - 32.0) * k
        # Fixed shoulder position. Mouse controls framing until a choice;
        # afterward, preserve the exact direction captured by _choose().
        # Lowering the weapon must not reframe the camera.
        d = self._witness_from or self.aim_dir()
        target = tuple(EYE[i] + d[i] * 10.0 for i in range(3))
        if self.death_t is None:
            return EYE, target, FOV
        k = _ease((self.t - self.death_t - 0.4) / BODY_CAM_S)
        return (_point(EYE, BODY_EYE, k), _point(target, BODY_LOOK, k),
                FOV + (BODY_FOV - FOV) * k)

    def draw(self, surface):
        if not self._active:
            return
        tm = int(self.t * 1000.0)
        eye, tgt, fov = self.camera()
        r = S3.frame(eye, tgt, fov)
        del _w.LAST[:]
        self._draw_gore(r, tm)
        self._draw_vasile(r, tm)
        self._draw_cig(r, tm)
        self._draw_player(r, tm)
        from . import trap3d as T3
        f_age = self.t - self.fire_t
        if self._flash_basis is not None and 0.0 <= f_age < T3.FLASH_S:
            tip, fvec, rx, ry = self._flash_basis
            T3.handheld_flash(r, tm, tip, fvec, rx, ry, f_age, 93, "shotgun")
        if self.flash_at is not None and self.t - self.flash_at[0] < 0.08:
            r.add_sprite(self.flash_at[1], _fx.glow((255, 220, 170), 0.2, tm, intensity=0.9,
                                                    max_px=16), layer=_fx.FX_LAYER)
        S3.present(r, surface)
        self._draw_blood(r, surface)
        draw_vignette(surface, 125)
        self._letterbox(surface)
        self._hud(surface)

    def _draw_blood(self, r, surface):
        for t0, x, y, z, _vx, _vy, _vz, size, col in self.blood:
            sx, sy, ok = self._project(r, (x, y, z))
            if not ok:
                continue
            try:
                depth = r.to_cam((x, y, z))[2]
            except Exception:
                continue
            age = (self.t - t0) / 1.1
            px = int(clamp(size * (1.0 - 0.5 * age) * r.focal / max(depth, 0.1)
                           * WIDTH / float(r.w), 1.0, 9.0))
            surface.fill(col, (int(sx) - px // 2, int(sy) - px // 2, px, px))

    def _letterbox(self, surface):
        h = int(HEIGHT * 0.115 * R._ease(clamp(self.lb, 0.0, 1.0)))
        if h > 0:
            surface.fill((0, 0, 0), (0, 0, WIDTH, h))
            surface.fill((0, 0, 0), (0, HEIGHT - h, WIDTH, h))

    def _face(self):
        if self.death_t is None:
            return "sad" if self.typed() else "stern"
        age = self.wound_age()
        if self.nutshot:
            if age < 0.7:
                return "surprised"
            if age < 2.8:
                return "angry"
            return "neutral" if age >= DEATH_S else "worried"
        if age < 0.8:
            return "surprised"
        if age < 2.8:
            return "worried"
        return "neutral" if age >= DEATH_S else "sad"

    def _draw_vasile(self, r, tm):
        pose, dz, yaw, _height = self._react()
        speaking = (self.death_t is None and 0 < self.typed() < len(LINE)) or (
            self.nutshot and 0.72 <= self.wound_age() <= 1.35
        )
        mouth = abs(math.sin(self.t * 10.0)) * 0.25 if speaking else 0.0
        wound = 0
        flags = ()
        if self.death_t is not None:
            age = self.wound_age()
            wound = 1 if age < 0.9 else 2 if age < 2.6 else 3
            flags = ["cig_dropped"]
            if self.headshot:
                flags.append("head_wound")
            elif self.nutshot:
                flags.append("groin_wound")
            flags = tuple(flags)
        _w.actor(r, "vasile", pose, (VX, VY, VZ + dz), yaw, tm, seed=71,
                 amp=0.0 if self.death_t is not None else 0.15, rifle_on=False,
                 expression=self._face(), mouth=mouth, hd=True, wound=wound,
                 bloody=self.hits > 0, flags=flags)

    def _draw_gore(self, r, tm):
        if self.death_t is None:
            return
        age = self.wound_age()
        if self._exit_mesh is not None:
            _w.add(r, self._exit_mesh)
        if self.floor_stains:
            m = Mesh()
            for x, z, rad, col in self.floor_stains:
                m.face([(x - rad, VY + 0.010, z - rad), (x + rad, VY + 0.010, z - rad),
                        (x + rad, VY + 0.010, z + rad), (x - rad, VY + 0.010, z + rad)],
                       col, 1, True)
            _w.add(r, m)
        if age > 0.25:
            k1 = clamp((age - 0.25) / 2.4, 0.0, 1.0)
            r1 = 0.08 + 0.36 * k1
            _w.add(r, _pool_mesh(VX - 0.06, VZ - 0.03, r1, (54, 5, 9), VY + 0.007, 1.1))
            _w.add(r, _pool_mesh(VX - 0.06, VZ - 0.03, r1 * 0.68, (92, 10, 15), VY + 0.009, 2.3))
        if age > 2.85:
            k2 = clamp((age - 2.85) / 4.2, 0.0, 1.0)
            r2 = 0.10 + 0.54 * k2
            px = VX - (0.76 if self.headshot else 0.45)
            _w.add(r, _pool_mesh(px, VZ - 0.03, r2, (52, 5, 9), VY + 0.007, 3.7))
            _w.add(r, _pool_mesh(px, VZ - 0.03, r2 * 0.65, (88, 10, 14), VY + 0.009, 4.9))
        if self.blood_burst is not None:
            el = self.t - self.blood_burst[0]
            if el < 0.36:
                f = 1.0 - el / 0.36
                r.add_sprite(self.blood_burst[1],
                             _fx.glow((168, 12, 16), 0.25 + 0.55 * (1.0 - f), tm,
                                      core=(210, 26, 28), intensity=1.15 * f, max_px=56),
                             layer=_fx.FX_LAYER)

    def _draw_cig(self, r, tm):
        c = self.cig
        if c is None:
            return
        m = Mesh()
        rot = m_mul(rot_y(c["yaw"]), rot_x(c["pitch"]))
        m.add(_cig_mesh(), rot, (c["x"], c["y"], c["z"]))
        _w.add(r, m)
        eb = m_apply(rot, (0.0, 0.0, 0.041))
        r.add_sprite((c["x"] + eb[0], c["y"] + eb[1], c["z"] + eb[2]),
                     _fx.glow((255, 118, 38), 0.12, tm, flicker=0.25,
                              core=(255, 220, 150), intensity=0.65, max_px=10),
                     layer=_fx.FX_LAYER)

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        hum = _w.hum(key, flags=("shotgun",))
        ready = R._held(hum, POSES["ready"], "shotgun", "ready", ("m7player", "ready"))
        aimed = R._held(hum, POSES["ready"], "shotgun", "aim", ("m7player", "aim"))
        amount = _ease((self.t - INTRO_S) / RAISE_S)
        if self.lowered_t is not None:
            amount *= 1.0 - _ease((self.t - self.lowered_t) / LOWER_S)
        pose = _mix(ready, aimed, amount)
        yaw = BYAW + _wrap(self.base_yaw + self.yaw_off - BYAW) * amount
        joints = _w.actor(r, key, pose, (BX, VY, BZ), yaw, tm, seed=93,
                          amp=0.06, rifle_on=True, flags=("shotgun",),
                          expression="stern", mouth=0.0)
        rm = joints.get("rifle_m") if joints else None
        hand = joints.get("rhand") if joints else None
        if rm is not None and hand is not None:
            from . import trap3d as T3
            off = m_apply(rm, T3.BORE_LOCAL["shotgun"])
            tip = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
            self._muzzle = tip
            self._flash_basis = (
                tip,
                C._f_unit(m_apply(rm, (0.0, 0.0, 1.0))),
                C._f_unit(m_apply(rm, (1.0, 0.0, 0.0))),
                C._f_unit(m_apply(rm, (0.0, 1.0, 0.0))),
            )
        else:
            self._muzzle = joints.get("muzzle") if joints else None
            self._flash_basis = None

    def _text(self, surface, text, y, small=False, alpha=1.0):
        font = font_terminal_small if small else font_terminal
        image = font.render(text, True, (222, 216, 202))
        image.set_alpha(int(255 * clamp(alpha, 0.0, 1.0)))
        surface.blit(image, (WIDTH // 2 - image.get_width() // 2, y - image.get_height() // 2))

    def _hud(self, surface):
        if self.phase == "aim":
            U.reticle(surface, int(2 * self.kick))
            if self.can_fire():
                self._text(surface, "Click to fire", HEIGHT - 150, small=True, alpha=0.7)
        for t0, who, text, duration in self.lines:
            if self.real - t0 < duration:
                self._text(surface, (who + ":  " if who else "") + text, HEIGHT - 105)
        self._caption(surface)
        if self.fade > 0.0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * self.fade))
            surface.blit(veil, (0, 0))

    def _caption(self, surface):
        """His warm line on the letterbox band; the shot leaves it cut mid-word."""
        n = self.typed()
        if n <= 0:
            return
        start = LINE.rfind(". ", 0, max(n - 1, 0)) + 2 if n > 1 else 0
        text = LINE[start:n] + ("-" if self.cut is not None else "")
        a = 1.0
        if self.cut_real is not None:
            el = self.real - self.cut_real
            if self.nutshot:
                if el >= 3.50:
                    return
                if el < 0.75:
                    a = clamp(1.0 - (el - 0.45) / 0.23, 0.0, 1.0)
                else:
                    text = "Coward."
                    a = min(clamp((el - 0.75) / 0.12, 0.0, 1.0),
                            clamp(1.0 - (el - 2.85) / 0.65, 0.0, 1.0))
            else:
                out = el - CAP_HOLD_S
                if out >= CAP_OUT_S:
                    return
                a = clamp(1.0 - out / CAP_OUT_S, 0.0, 1.0)
        if a <= 0.0:
            return
        # Same speaker tab + caption as the Old Friends film, faded as one layer.
        from ui import speechbox
        layer = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        speechbox.draw_caption(layer, "VASILE", text)
        layer.set_alpha(int(255 * a))
        surface.blit(layer, (0, 0))


def _ray_segment_capsule(o, d, a, b, rad):
    """Forward ray against a capsule with arbitrary endpoints, including caps."""
    return _capsule_distance(o, d, a, b, rad) is not None


def _capsule_distance(o, d, a, b, rad):
    """First contact distance in world units, or None if the ray misses."""
    if rad < 0.0 or sum(v * v for v in d) <= 1e-18:
        return None
    axis = tuple(b[i] - a[i] for i in range(3))
    height = math.sqrt(sum(v * v for v in axis))
    if height <= 1e-9:
        # The existing helper handles a zero-height capsule as a sphere.
        return _vertical_capsule_distance(o, d, a, 0.0, rad)
    up = tuple(v / height for v in axis)
    reference = (1.0, 0.0, 0.0) if abs(up[0]) < 0.9 else (0.0, 0.0, 1.0)
    side = _unit((up[1] * reference[2] - up[2] * reference[1],
                  up[2] * reference[0] - up[0] * reference[2],
                  up[0] * reference[1] - up[1] * reference[0]))
    forward = (side[1] * up[2] - side[2] * up[1],
               side[2] * up[0] - side[0] * up[2],
               side[0] * up[1] - side[1] * up[0])
    offset = tuple(o[i] - a[i] for i in range(3))
    local_o = tuple(sum(offset[i] * v[i] for i in range(3)) for v in (side, up, forward))
    local_d = tuple(sum(d[i] * v[i] for i in range(3)) for v in (side, up, forward))
    return _vertical_capsule_distance(local_o, local_d, (0.0, 0.0, 0.0), height, rad)


def _ray_capsule(o, d, base, h, rad):
    """Exact forward ray / vertical capsule intersection, including end caps."""
    return _vertical_capsule_distance(o, d, base, h, rad) is not None


def _vertical_capsule_distance(o, d, base, h, rad):
    length = math.sqrt(sum(v * v for v in d))
    if length <= 1e-9 or rad < 0.0 or h < 0.0:
        return None
    dx, dy, dz = (v / length for v in d)
    ox, oy, oz = (o[i] - base[i] for i in range(3))
    if ox * ox + oz * oz <= rad * rad and 0.0 <= oy <= h:
        return 0.0
    distances = []
    a = dx * dx + dz * dz
    if a > 1e-12:
        b = 2.0 * (ox * dx + oz * dz)
        c = ox * ox + oz * oz - rad * rad
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            root = math.sqrt(disc)
            for distance in ((-b - root) / (2.0 * a), (-b + root) / (2.0 * a)):
                if distance >= 0.0 and 0.0 <= oy + distance * dy <= h:
                    distances.append(distance)
    for end in (0.0, h):
        ey = oy - end
        b = ox * dx + ey * dy + oz * dz
        c = ox * ox + ey * ey + oz * oz - rad * rad
        disc = b * b - c
        if c <= 0.0:
            return 0.0
        if disc >= 0.0:
            distance = -b - math.sqrt(disc)
            if distance >= 0.0:
                distances.append(distance)
    return min(distances) if distances else None

_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = KillScene()
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
    """Release input and audio without advancing the mission."""
    if _SCENE is not None and _SCENE.active():
        _SCENE.done = True
        _SCENE.result = "aborted"
        _SCENE._release()

def force_finish(reason="fallback"):
    if _SCENE is not None:
        return _SCENE.finish(reason)
    return False