"""Mission 8 Duty - Phase 6: The Ridge (first-person scope finale).

Biribel lies on the frozen ridge above the evacuation pad: Retardovici's
downed helicopter, a few Guards, a rescue bird on its way in.

1. Ucilev steps in front of the President; he has to go first.  One round,
   visible bullet flight and visceral impact: he drops to his knees in the
   snow and gets his line before pitching forward.
2. Retardovici takes a Guard radio, on Biribel's channel, crouched behind the
   wreck: four lines.  Then he stands.  The game waits for the shot.
3. The shot: flying round, hitstop, gore spray & snow pool, scope recoil.
   The scene hands off to the epilogue.

Scope: mouse aims, wheel / RMB cycles zoom, hold SHIFT to hold breath
(limited, then the sway comes back worse), wind and drop are real.  If the
rescue bird lands and lifts with him, the ridge restarts.
"""
import math
import random

import pygame

from core.config import HEIGHT, WIDTH, audio, draw_vignette, font_terminal, font_terminal_small
from core.state import STATE
from cutscenes import fire3d as _f3d
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m8duty_sets as DS
from engine3d import Mesh, POSES, blend, clamp
from engine3d.core import m_apply, m_mul, rot_x, rot_y, rot_z, v_add
from engine3d.hold import hold_frame
from engine3d.rig import rifle_mesh
from missions.m6 import hud3d as H
from missions.m7 import raid3d as R
from missions.m7 import raid_brain as RB
from missions.m8.revenge import chase_set as CS

PAD = (CS.road_x(2300.0) + 70.0, 0.0, 2300.0)
EYE = (PAD[0] - 95.0, 30.0, PAD[2] - 60.0)
ZOOMS = (18.0, 8.0, 3.8)
PERIPH_FOV = 54.0
INTRO_S = 1.3
_INTRO_RIFLE = []
_RADIO_PROP = []
_PERCH_GUN = []
_SCOPE_SURFS = {}


def _recolor_sniper_face(col):
    if not (isinstance(col, (tuple, list)) and len(col) >= 3):
        return col
    r, g, b = col[0], col[1], col[2]
    # Amber GLB lens -> dark coated optic glass
    if r > 180 and g > 120 and b < 60:
        return (24, 36, 54)
    # Khaki/sand stock -> dark walnut so it contrasts against Ucilev's uniform
    if r > 140 and g > 115 and b > 80:
        return (int(r * 0.36), int(g * 0.28), int(b * 0.24))
    return col


def _intro_rifle_mesh():
    if not _INTRO_RIFLE:
        m = None
        try:
            from cutscenes.cast3d import weapon_asset
            raw, _ = weapon_asset("sniper_rifle")
            if raw is not None:
                m = Mesh()
                m.verts = list(raw.verts)
                m.faces = [(f[0], _recolor_sniper_face(f[1])) + tuple(f[2:]) for f in raw.faces]
        except Exception:
            m = None
        if m is None:
            m = rifle_mesh(scope=True)
        _INTRO_RIFLE.append(m)
    return _INTRO_RIFLE[0]


def _radio_prop_mesh():
    if not _RADIO_PROP:
        from engine3d import box
        m = Mesh()
        m.add(box(0.08, 0.16, 0.05, (28, 30, 34), center=(0.0, 0.0, 0.0)))
        m.add(box(0.018, 0.14, 0.018, (18, 18, 22), center=(0.025, 0.14, 0.0)))
        m.add(box(0.022, 0.022, 0.015, (220, 48, 38), center=(0.0, 0.04, 0.028), emissive=True))
        _RADIO_PROP.append(m)
    return _RADIO_PROP[0]


def _perch_gun_mesh():
    """Forward sniper barrel, suppressor, wooden fore-end & planted bipod legs
    positioned cleanly in the lower 1x peripheral view resting on the spruce log."""
    if not _PERCH_GUN:
        from engine3d import box
        m = Mesh()
        wood = (62, 44, 30)
        steel = (30, 34, 40)
        dark = (16, 18, 22)
        glove = (22, 24, 28)
        # Stock fore-end, receiver & cheek rest angled from lower-right toward the log
        m.add(box(0.072, 0.062, 0.52, wood, center=(0.0, -0.34, 0.68)))
        m.add(box(0.036, 0.036, 0.58, steel, center=(0.0, -0.30, 0.98)))
        m.add(box(0.048, 0.048, 0.34, dark, center=(0.0, -0.30, 1.38)))
        # Left gloved support hand gripping the fore-end / sandbag
        m.add(box(0.11, 0.075, 0.16, glove, center=(-0.05, -0.37, 0.82)))
        m.add(box(0.10, 0.09, 0.32, (34, 40, 34)), m=rot_y(24.0), t=(-0.22, -0.44, 0.64))
        # Planted bipod legs resting cleanly onto the granite/spruce parapet
        for sx in (-1.0, 1.0):
            m.add(box(0.026, 0.52, 0.026, steel), m=rot_z(sx * 26.0), t=(sx * 0.12, -0.54, 1.06))
        _PERCH_GUN.append(m)
    return _PERCH_GUN[0]


MUZZLE_V = 820.0
G = 9.81
BOLT_S = 1.3
BREATH_S = 4.0
RESCUE_S = 48.0
SLOWMO = 0.45
FLIGHT_S = 0.22
FLIGHT_KILL_S = 0.26
LINE_S = 4.2
RADIO_LINES = (
    "He always gets someone else to pull the trigger.",
    "Your friends on Route 12, now me. And he's sitting somewhere warm waiting for morning.",
    "Go on, soldier. Make him President.",
)
UCILEV_LINE = "Good shot, Biribel."
BLOOD_COLS = ((132, 12, 16), (92, 8, 12), (168, 20, 24), (62, 5, 8))
SNOW_COLS = ((232, 240, 250), (168, 182, 206), (118, 132, 156), (64, 58, 54))


def _off(dx, dz):
    return (PAD[0] + dx, 0.0, PAD[2] + dz)


def _yaw_to(a, b):
    return R._yaw(b[0] - a[0], b[2] - a[2])


def _ease(k):
    k = clamp(k, 0.0, 1.0)
    return k * k * (3.0 - 2.0 * k)


def _mix_pose(a, b, k):
    a_full = POSES[a] if isinstance(a, str) else a
    b_full = POSES[b] if isinstance(b, str) else b
    return blend(a_full, b_full, clamp(k, 0.0, 1.0))


def _settle(age, start, dur, strength, freq=12.0):
    t = age - start
    if t <= 0.0 or t >= dur:
        return 0.0
    env = math.exp(-5.0 * t) * (1.0 - _ease(t / dur))
    return strength * math.sin(freq * t) * env


def _pool_mesh(cx, cz, rad, col, y, seed=0):
    m = Mesh()
    pts = []
    for i in range(10):
        a = math.tau * i / 10.0
        wob = 0.78 + 0.30 * math.sin(i * 2.7 + seed)
        pts.append((cx + math.cos(a) * rad * wob * 1.15, y, cz + math.sin(a) * rad * wob))
    m.face(pts, col, 1, True)
    return m


PRES_AT = _off(2.6, -1.0)
_U_DIR = (EYE[0] - PRES_AT[0], EYE[2] - PRES_AT[2])
_U_LEN = math.hypot(*_U_DIR)
UCILEV_AT = (PRES_AT[0] + _U_DIR[0] / _U_LEN * 1.1, 0.0, PRES_AT[2] + _U_DIR[1] / _U_LEN * 1.1)
GUARDS = (_off(-4.0, 3.0), _off(6.5, 2.0), _off(1.0, 6.5))
RESCUE_FROM = _off(160.0, 260.0)
RESCUE_PAD = _off(9.0, 9.0)

# Retardovici's downed VIP helicopter: cleanly right of PRES_AT with tail away NE (zero overlap)
HELI_CRASH_AT = _off(9.4, -3.6)
HELI_CRASH_YAW = 225.0

# Guard escort truck parked on the left edge of the pad, headlights sweeping the clearing
TRUCK_AT = _off(-12.5, 6.5)
TRUCK_YAW = _yaw_to(TRUCK_AT, PRES_AT)

# Distant flank crash site (tying back to Maru's crash clearing across the ridge spur)
_EYE_LEN = math.hypot(PAD[0] - EYE[0], PAD[2] - EYE[2]) or 1.0
_FWD_XZ = ((PAD[0] - EYE[0]) / _EYE_LEN, (PAD[2] - EYE[2]) / _EYE_LEN)
_RIGHT_XZ = (_FWD_XZ[1], -_FWD_XZ[0])
MARU_GLOW_AT = (EYE[0] + _FWD_XZ[0] * 70.0 - _RIGHT_XZ[0] * 46.0, 0.7,
                EYE[2] + _FWD_XZ[1] * 70.0 - _RIGHT_XZ[1] * 46.0)

# Shot-away unit vector from EYE -> PAD in XZ
_SHOT_FWD = (-_U_DIR[0] / _U_LEN, -_U_DIR[1] / _U_LEN)

_U_IMPACT = dict(POSES["stand"], spine=-22, twist=20, head_p=-26, lsh_p=46, lsh_r=42, lel=28,
                 rsh_p=64, rsh_r=48, rel=22, lkn=14, rkn=10)
_U_BUCKLE = dict(POSES["slump"], spine=28, twist=10, head_p=20, lsh_p=54, lsh_r=-14, lel=88,
                 rsh_p=20, rsh_r=28, rel=38, lhip_p=44, lkn=78, rhip_p=36, rkn=68)
_U_KNEEL = dict(POSES["kneel"], spine=22, head_p=12, lsh_p=48, lsh_r=-12, lel=86,
                rsh_p=16, rsh_r=18, rel=34)
_U_DEAD = dict(POSES["dead_front"], body_r=6, head_y=-14, lsh_p=142, lsh_r=28, lel=22,
               rsh_p=128, rsh_r=36, rel=18, lank=16, rank=16)

_P_IMPACT = dict(POSES["stand"], spine=-24, twist=-22, head_p=-30, lsh_p=44, lsh_r=52, lel=24,
                 rsh_p=86, rsh_r=64, rel=14, lhip_p=-8, rkn=12)
_P_BUCKLE = dict(POSES["slump"], spine=20, twist=-10, head_p=-10, lsh_p=52, lsh_r=-10, lel=82,
                 rsh_p=34, rsh_r=44, rel=32, lhip_p=34, lkn=62, rhip_p=42, rkn=74)
_P_DEAD = dict(POSES["dead_back"], body_r=-10, twist=-12, head_p=6, head_y=20,
               lhip_p=2, lhip_r=10, lkn=4, rhip_p=2, rhip_r=14, rkn=6,
               lank=18, rank=18, lsh_p=24, lsh_r=38, lel=34, rsh_p=14, rsh_r=52, rel=24)


def _blood_mist_sprite(age_s, is_head=False):
    """Organic multi-puff crimson blood spray cloud against bright snow."""
    dur = 0.55 if is_head else 0.45
    u = clamp(age_s / dur, 0.0, 1.0)
    rad_m = (0.78 if is_head else 0.62) * (0.42 + 0.78 * u)
    fade = clamp(1.0 - u, 0.0, 1.0) ** 1.3

    def draw(s, sx, sy, scale, z):
        if fade <= 0.03 or scale < 0.2:
            return
        px = max(6, min(96, int(rad_m * scale)))
        key = ("bmist2", px // 2, int(round(fade * 10)), bool(is_head))
        img = _FX_CACHE.get(key)
        if img is None:
            d = px * 2 + 6
            img = pygame.Surface((d, d), pygame.SRCALPHA)
            c = px + 3
            rng = random.Random(4109 if is_head else 2083)
            # Scattered asymmetric spray droplets + ragged aerosol puffs
            for i in range(18):
                ang = rng.uniform(-0.85, 0.85) + (0.0 if i % 3 else rng.uniform(0.0, math.tau))
                dist = rng.uniform(0.05, 0.88) * px
                bx = int(c + math.cos(ang) * dist)
                by = int(c + math.sin(ang) * dist * 0.72 - rng.uniform(0.0, 0.18 * px))
                br = max(2, int(px * rng.uniform(0.10, 0.30) * (1.0 - 0.3 * (dist / max(1, px)))))
                col = rng.choice(((118, 10, 14), (168, 16, 22), (82, 6, 10)))
                a = int(rng.uniform(115, 195) * fade)
                pygame.draw.circle(img, (*col, a), (bx, by), br)
            for _ in range(8):
                ang = rng.uniform(-0.9, 0.9)
                r0 = rng.uniform(0.1, 0.4) * px
                r1 = rng.uniform(0.6, 1.0) * px
                pygame.draw.line(img, (150, 14, 18, int(175 * fade)),
                                 (int(c + math.cos(ang) * r0), int(c + math.sin(ang) * r0 * 0.7)),
                                 (int(c + math.cos(ang) * r1), int(c + math.sin(ang) * r1 * 0.7)),
                                 max(1, px // 14))
            if len(_FX_CACHE) > 256:
                _FX_CACHE.clear()
            _FX_CACHE[key] = img
        s.blit(img, (int(sx - img.get_width() * 0.5), int(sy - img.get_height() * 0.5)))

    draw.bounds_m = (rad_m * 1.15, rad_m * 1.15)
    draw.bounds_cap_px = (100, 100)
    return draw


def _snow_geyser_sprite(age_s, seed=0):
    """Crisp rifle-caliber snow & frozen-earth kickup at the ground strike point."""
    dur = 0.62
    u = clamp(age_s / dur, 0.0, 1.0)
    fade = clamp(1.0 - u, 0.0, 1.0) ** 1.15
    h_m = 0.18 + 0.52 * (1.0 - (1.0 - u) ** 2.2)
    w_m = 0.22 + 0.42 * u

    def draw(s, sx, sy, scale, z):
        if fade <= 0.03 or scale < 0.2:
            return
        pw = max(6, min(88, int(w_m * scale)))
        ph = max(8, min(120, int(h_m * scale)))
        key = ("sgeyser2", pw // 2, ph // 2, int(round(fade * 10)))
        img = _FX_CACHE.get(key)
        if img is None:
            iw, ih = pw * 2 + 8, ph + 12
            img = pygame.Surface((iw, ih), pygame.SRCALPHA)
            cx = iw // 2
            base_y = ih - 5
            rng = random.Random(7331)
            # Base churned earth/shadow skirt
            for i in range(6):
                ox = int(rng.uniform(-0.55, 0.55) * pw)
                oy = int(rng.uniform(-0.14, 0.02) * ph)
                rx = max(3, int(pw * rng.uniform(0.28, 0.48)))
                ry = max(2, int(ph * rng.uniform(0.08, 0.16)))
                pygame.draw.ellipse(img, (68, 76, 90, int(165 * fade)),
                                    (cx + ox - rx, base_y + oy - ry, rx * 2, ry * 2))
            # Irregular rising fan of powder snow puffs
            for i in range(16):
                t_h = rng.uniform(0.12, 0.95)
                spread = (0.15 + 0.72 * t_h) * pw
                px = int(cx + rng.uniform(-spread, spread))
                py = int(base_y - t_h * ph)
                pr = max(2, int(pw * rng.uniform(0.16, 0.34) * (1.0 - 0.35 * t_h)))
                col = rng.choice(((166, 180, 202), (210, 222, 238), (238, 244, 252)))
                a = int(rng.uniform(130, 210) * fade * (1.0 - 0.25 * t_h))
                pygame.draw.circle(img, (*col, a), (px, py), pr)
            # Crisp upward spray streaks
            for _ in range(9):
                ang = rng.uniform(-0.48, 0.48) - math.pi * 0.5
                ln0 = rng.uniform(0.08, 0.25) * ph
                ln1 = rng.uniform(0.55, 0.98) * ph
                pygame.draw.line(img, (236, 242, 252, int(180 * fade)),
                                 (int(cx + math.cos(ang) * ln0), int(base_y + math.sin(ang) * ln0)),
                                 (int(cx + math.cos(ang) * ln1), int(base_y + math.sin(ang) * ln1)), 1)
            if len(_FX_CACHE) > 256:
                _FX_CACHE.clear()
            _FX_CACHE[key] = img
        s.blit(img, (int(sx - img.get_width() * 0.5), int(sy - img.get_height() + 5)))

    draw.bounds_m = (w_m * 1.25, h_m * 1.25)
    draw.bounds_cap_px = (96, 132)
    return draw


_FX_CACHE = {}


class RidgeScene:
    set_paused = R.RaidScene.set_paused
    _grab = R.RaidScene._grab
    _snd = R.RaidScene._snd
    say = R.RaidScene.say
    _project = R.RaidScene._project

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self.t = 0.0
        self._setup()

    def begin(self):
        self.t = 0.0
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_ridge_active = True
        try:
            from .. import m8_audio as _m8_audio
            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None
        self._setup()
        self._grab(True)

    def active(self):
        return self._active

    def finish(self, result="win"):
        if self.done:
            return False
        self.done = True
        self.result = result
        self._active = False
        STATE.m8_ridge_active = False
        self._grab(False)
        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass
        from .. import flow as _flow
        return _flow.on_ridge_done(result)

    def _setup(self):
        self.rng = random.Random()
        self.yaw = _yaw_to(EYE, UCILEV_AT) + 0.6
        self.pitch = math.degrees(math.atan2(-(EYE[1] - 1.24), math.hypot(UCILEV_AT[0] - EYE[0],
                                                                           UCILEV_AT[2] - EYE[2])))
        self.zoom_i = 0
        self.breath = BREATH_S
        self.holding = False
        self.winded = 0.0
        self.last_shot = -9.0
        self.kick = 0.0
        self.kick_yaw = 0.0
        self.phase = "ucilev"
        self.phase_start = 0.0
        self.u_down_t = 0.0
        self.impact_t = None
        self.phase_t = 0.0
        self.line_i = 0
        self.rescue = RESCUE_S
        self.fail_t = -1.0
        self.wind = self.rng.choice((-1.0, 1.0)) * self.rng.uniform(2.0, 5.5)
        self.guards = [dict(x=g[0], y=0.0, z=g[2], alive=True, dead_t=-9.0, head=False,
                            flinch_t=-9.0, yaw=_yaw_to(g, EYE))
                       for g in GUARDS]
        self.lines = []
        self.impacts = []
        self.craters = []
        self.snow_chunks = []
        self.snow_plumes = []
        self.blood = []
        self.blood_bursts = []
        self.snow_stains = []
        self.dropped_props = []
        self.bullet = None
        self.trails = []
        self.hit_mark = -9.0
        self.hit_head = False
        self.u_headshot = False
        self.p_headshot = False
        self.slow_until = -1.0
        self.stop_until_real = -1.0
        self.shake_until = -1.0
        self.muzzle_flash_t = -9.0
        self._cap = None   # (t0, who, text, dur, typewriter)
        self._cap_real = 0.0
        self._lb = 0.0
        self.intro_u = 0.0
        self._intro_clicked = False
        self._intro_mist = 0.0
        self._was_holding = False
        self._hold_time = 0.0
        self.hold_frost = 0.0
        self._eye_rx = 0.0
        self._eye_ry = 0.0
        self._bolt_t = -9.0
        self._bolt_played = False
        self._brass = []
        self._hud_alpha = 1.0
        self._abort_t = -1.0
        self._breath_next = 0.4
        self._breath_puffs = []
        self._silence_until = -1.0
        self._wind_only_at = -1.0
        self._periph_state = None
        self._u_gun_xform = None

    # --- the world -------------------------------------------------------------

    @staticmethod
    def _reduced_motion():
        try:
            from core.user_settings import SETTINGS
            return bool(SETTINGS.reduced_motion)
        except Exception:
            return False

    @staticmethod
    def _flash_reduction():
        try:
            from core.user_settings import SETTINGS
            return bool(SETTINGS.flash_reduction)
        except Exception:
            return False

    def fov(self):
        return ZOOMS[self.zoom_i]

    def sway(self):
        """Scope drift in degrees (yaw, pitch); breath-hold steadies it."""
        rm = 0.45 if self._reduced_motion() else 1.0
        amp = (0.10 + 0.05 * self.zoom_i) * rm * (0.15 if self.holding else 1.0) * (1.0 + 1.6 * self.winded)
        t = self.t
        return (amp * (math.sin(t * 0.9) + 0.5 * math.sin(t * 2.3 + 1.0)),
                amp * 0.8 * (math.sin(t * 1.3 + 2.0) + 0.4 * math.sin(t * 3.1)))

    def _optic_ease(self):
        ie = R._ease(clamp(getattr(self, "intro_u", 1.0), 0.0, 1.0))
        if self.phase == "pres_down" and self.impact_t is not None:
            outro = _ease((self._p_impact_age() - 1.6) / 1.4)
            ie *= 1.0 - 0.62 * outro
        return ie

    def view_dir(self):
        sy, sp = self.sway()
        trem_y, trem_p = 0.0, 0.0
        if self._cap_real < self.shake_until:
            u = (self.shake_until - self._cap_real) / 0.22
            trem_y = math.sin(self._cap_real * 75.0) * 0.09 * u
            trem_p = math.cos(self._cap_real * 63.0) * 0.09 * u
        outro_p = 0.0
        if self.phase == "pres_down" and self.impact_t is not None:
            outro_p = -2.8 * _ease((self._p_impact_age() - 1.6) / 1.4)
        return R._fwd(self.yaw + sy + self.kick_yaw + trem_y,
                      self.pitch + sp + self.kick + trem_p + outro_p)

    def rescue_pos(self):
        k = clamp(1.0 - self.rescue / RESCUE_S, 0.0, 1.0)
        e = R._ease(k)
        p = tuple(RESCUE_FROM[i] + (RESCUE_PAD[i] - RESCUE_FROM[i]) * e for i in range(3))
        alt = 60.0 * (1.0 - e) ** 1.4
        if self.fail_t >= 0.0:
            alt = (self.t - self.fail_t) * 4.0
        elif self._abort_t >= 0.0:
            da = max(0.0, self.t - self._abort_t)
            return (p[0] + da * 12.0, p[1] + alt + da * 7.5, p[2] + da * 20.0)
        return (p[0], p[1] + alt, p[2])

    def _u_impact_age(self):
        if self.phase == "ucilev" or self.u_down_t <= 0.0:
            return 0.0
        if self.phase == "u_down" and self.impact_t is None:
            return 0.0
        return max(0.0, self.t - self.u_down_t)

    def _p_impact_age(self):
        if self.phase != "pres_down" or self.impact_t is None:
            return 0.0
        return max(0.0, self.t - self.impact_t)

    def pres_spot(self):
        """(pos, yaw, pose) for Retardovici including stand-up, step into lights, and collapse."""
        yaw = _yaw_to(PRES_AT, EYE)
        if self.phase in ("ucilev", "u_down", "radio"):
            wave = 0.0
            if self.phase == "radio" and self.line_i >= len(RADIO_LINES):
                wave = 26.0 + 18.0 * math.sin(self.phase_t * 5.0)
            return PRES_AT, yaw, dict(POSES["kneel"], rsh_p=105.0, rel=95.0, lsh_r=wave, head_p=-8.0)
        if self.phase == "wait" or (self.phase == "pres_down" and self.impact_t is None):
            stand_pose = dict(POSES["stand"], rsh_p=105.0, rel=95.0, lsh_r=12.0, head_p=-14.0)
            k = _ease(self.phase_t / 0.55) if self.phase == "wait" else 1.0
            step = _ease((self.phase_t - 0.35) / 0.85) if self.phase == "wait" else 1.0
            pos = (PRES_AT[0] + _SHOT_FWD[0] * 1.15 * step, 0.0, PRES_AT[2] + _SHOT_FWD[1] * 1.15 * step)
            return pos, yaw, _mix_pose(dict(POSES["kneel"], rsh_p=105.0, rel=95.0), stand_pose, k)

        age = self._p_impact_age()
        stand_pose = dict(POSES["stand"], rsh_p=105.0, rel=95.0, lsh_r=12.0, head_p=-14.0)
        base_pos = (PRES_AT[0] + _SHOT_FWD[0] * 1.15, 0.0, PRES_AT[2] + _SHOT_FWD[1] * 1.15)
        if age < 0.13:
            k = _ease(age / 0.13)
            imp = dict(_P_IMPACT, head_p=-38.0 if self.p_headshot else -26.0)
            pose = _mix_pose(stand_pose, imp, k)
            back = 0.14 * k
        elif age < 0.44:
            k = _ease((age - 0.13) / 0.31)
            imp = dict(_P_IMPACT, head_p=-38.0 if self.p_headshot else -26.0)
            pose = _mix_pose(imp, _P_BUCKLE, k)
            back = 0.14 + 0.30 * k
        elif age < 0.90:
            u = clamp((age - 0.44) / 0.46, 0.0, 1.0)
            pose = _mix_pose(_P_BUCKLE, _P_DEAD, u * u)
            back = 0.44 + 0.36 * (u * u)
        else:
            pose = dict(_P_DEAD)
            pose["head_p"] += _settle(age, 0.90, 0.45, -10.0)
            pose["lsh_p"] += _settle(age, 0.94, 0.42, 16.0)
            pose["rsh_p"] += _settle(age, 0.96, 0.44, 18.0)
            back = 0.80
        pos = (base_pos[0] + _SHOT_FWD[0] * back, 0.0, base_pos[2] + _SHOT_FWD[1] * back)
        return pos, yaw + clamp(age / 0.45, 0.0, 1.0) * 14.0, pose

    def pres_pose(self):
        return self.pres_spot()[2]

    def ucilev_spot(self):
        """(pos, yaw, pose) for Ucilev: impact snap, knee drop, dying words, forward slump."""
        yaw = _yaw_to(UCILEV_AT, EYE)
        stand_u = dict(POSES["stand"], spine=3.0, head_p=-14.0)
        if self.phase == "ucilev" or (self.phase == "u_down" and self.impact_t is None):
            return UCILEV_AT, yaw, stand_u
        age = self._u_impact_age()
        if age < 0.14:
            k = _ease(age / 0.14)
            imp = dict(_U_IMPACT, head_p=-36.0 if self.u_headshot else -24.0)
            pose = _mix_pose(stand_u, imp, k)
            back = 0.15 * k
        elif age < 0.46:
            k = _ease((age - 0.14) / 0.32)
            imp = dict(_U_IMPACT, head_p=-36.0 if self.u_headshot else -24.0)
            pose = _mix_pose(imp, _U_BUCKLE, k)
            back = 0.15 + 0.18 * k
        elif age < 0.82:
            u = clamp((age - 0.46) / 0.36, 0.0, 1.0)
            pose = _mix_pose(_U_BUCKLE, _U_KNEEL, u * u)
            back = 0.33
        elif age < 4.15:
            look = _ease((age - 0.90) / 0.50)
            pose = dict(_U_KNEEL)
            pose["spine"] = 22.0 + 3.0 * math.sin(age * 3.5)
            pose["head_p"] = 12.0 - 24.0 * look + 2.5 * math.sin(age * 3.5)
            pose["head_p"] += _settle(age, 0.82, 0.38, 12.0)
            back = 0.33
        elif age < 4.95:
            u = clamp((age - 4.15) / 0.80, 0.0, 1.0)
            up_kneel = dict(_U_KNEEL, spine=24.0, head_p=-10.0)
            pose = _mix_pose(up_kneel, _U_DEAD, u * u)
            back = 0.33 - 0.18 * (u * u)
        else:
            pose = dict(_U_DEAD)
            pose["head_p"] += _settle(age, 4.95, 0.40, -8.0)
            back = 0.15
        pos = (UCILEV_AT[0] + _SHOT_FWD[0] * back, 0.0, UCILEV_AT[2] + _SHOT_FWD[1] * back)
        return pos, yaw, pose

    def ucilev_pose(self):
        return self.ucilev_spot()[2]

    def targets(self):
        """(name, centre, radius, is_head) the round can hit (full head/chest/pelvis/leg stack)."""
        out = []
        if self.phase == "ucilev":
            u = UCILEV_AT
            out += [
                ("ucilev", (u[0], 1.62, u[2]), 0.19, True),
                ("ucilev", (u[0], 1.18, u[2]), 0.35, False),
                ("ucilev", (u[0], 0.76, u[2]), 0.31, False),
                ("ucilev", (u[0], 0.38, u[2]), 0.27, False),
            ]
        if self.phase == "wait":
            p = self.pres_spot()[0]
            out += [
                ("pres", (p[0], 1.62, p[2]), 0.19, True),
                ("pres", (p[0], 1.16, p[2]), 0.35, False),
                ("pres", (p[0], 0.75, p[2]), 0.31, False),
                ("pres", (p[0], 0.38, p[2]), 0.27, False),
            ]
        for i, g in enumerate(self.guards):
            if g["alive"]:
                nm = "g%d" % i
                out += [
                    (nm, (g["x"], 1.60, g["z"]), 0.19, True),
                    (nm, (g["x"], 1.15, g["z"]), 0.35, False),
                    (nm, (g["x"], 0.74, g["z"]), 0.30, False),
                    (nm, (g["x"], 0.36, g["z"]), 0.26, False),
                ]
        return out

    # --- update ----------------------------------------------------------------

    def _set_phase(self, name):
        self.phase = name
        self.phase_start = self.t
        self.phase_t = 0.0

    def _set_caption(self, who, text, dur, typewriter=False):
        self._cap = (self._cap_real, who, text, dur, typewriter)
        self.say(who, text, dur)

    def _bullet_pos(self, b, u):
        p0, p1 = b["p0"], b["p1"]
        u = clamp(u, 0.0, 1.0)
        p_aim = b.get("p_aim", p1)
        # Follow the bore line (p0 -> p_aim) linearly in u and accumulate gravity drop
        # & wind drift quadratically (u^2) so perspective projection (dividing by Z ~ u)
        # starts right at the crosshair and curves smoothly into p1.
        bx = p0[0] + (p_aim[0] - p0[0]) * u
        by = p0[1] + (p_aim[1] - p0[1]) * u
        bz = p0[2] + (p_aim[2] - p0[2]) * u
        u2 = u * u
        return (
            bx + (p1[0] - p_aim[0]) * u2,
            by + (p1[1] - p_aim[1]) * u2,
            bz + (p1[2] - p_aim[2]) * u2,
        )

    def _spawn_gore(self, hit_pos, d, is_head, kind):
        hx, hy, hz = hit_pos
        rng = random.Random(int(self._cap_real * 1000.0) + (77 if is_head else 19))
        self.blood_bursts.append((self._cap_real, (hx + d[0] * 0.22, hy, hz + d[2] * 0.22), is_head))
        # High-velocity exit spray blasting out the back along the shot vector
        n_exit = 48 if is_head else 36
        for _ in range(n_exit):
            spd = rng.uniform(3.4, 9.8 if is_head else 7.6)
            self.blood.append([
                self.t, hx + d[0] * 0.14, hy, hz + d[2] * 0.14,
                d[0] * spd + rng.uniform(-1.1, 1.1),
                rng.uniform(-0.3, 2.2 if is_head else 1.5),
                d[2] * spd + rng.uniform(-1.1, 1.1),
                rng.uniform(0.032, 0.072),
                rng.choice(BLOOD_COLS),
            ])
        # Entry spatter & dark clots
        for _ in range(16):
            spd = rng.uniform(1.0, 3.0)
            self.blood.append([
                self.t, hx - d[0] * 0.08, hy, hz - d[2] * 0.08,
                -d[0] * spd * 0.5 + rng.uniform(-1.2, 1.2),
                rng.uniform(0.4, 1.8),
                -d[2] * spd * 0.5 + rng.uniform(-1.2, 1.2),
                rng.uniform(0.026, 0.058),
                rng.choice(BLOOD_COLS),
            ])
        # Knock held gear loose into the snow
        if kind == "ucilev":
            gx, gy, gz = self._u_gun_xform[0] if self._u_gun_xform else (UCILEV_AT[0] + 0.18, 1.10, UCILEV_AT[2] - 0.10)
            self.dropped_props.append({
                "kind": "rifle",
                "x": gx, "y": gy, "z": gz,
                "vx": d[0] * 1.4 + 0.6, "vy": 2.4, "vz": d[2] * 1.4 - 0.5,
                "yaw": _yaw_to(UCILEV_AT, EYE), "pitch": 0.0, "roll": 0.0,
                "vyaw": 240.0, "vpitch": 380.0, "rest": False,
            })
        elif kind == "pres":
            self.dropped_props.append({
                "kind": "radio",
                "x": PRES_AT[0] + 0.22, "y": 1.35, "z": PRES_AT[2] - 0.05,
                "vx": d[0] * 1.8 + 1.1, "vy": 3.1, "vz": d[2] * 1.8 - 0.4,
                "yaw": 40.0, "pitch": 0.0, "roll": 0.0,
                "vyaw": 420.0, "vpitch": 620.0, "rest": False,
            })

    def _spawn_snow_impact(self, end, near_feet=False):
        ex, _, ez = end
        self.impacts.append((self.t, end))
        self.snow_plumes.append((self._cap_real, (ex, 0.05, ez)))
        if len(self.craters) < 24:
            self.craters.append((ex, ez, 0.24 if near_feet else 0.22))
        rng = random.Random(int(self._cap_real * 1000.0) + 303)
        for _ in range(18):
            ang = rng.uniform(0.0, math.tau)
            spd_h = rng.uniform(0.4, 2.1)
            self.snow_chunks.append([
                self.t, ex, 0.08, ez,
                math.cos(ang) * spd_h - _SHOT_FWD[0] * 0.5,
                rng.uniform(0.9, 2.4),
                math.sin(ang) * spd_h - _SHOT_FWD[1] * 0.5,
                rng.uniform(0.018, 0.044),
                rng.choice(SNOW_COLS),
            ])

    def _resolve_bullet(self):
        b = self.bullet
        if b is None or b["resolved"]:
            return
        b["resolved"] = True
        self.trails.append((self._cap_real, [self._bullet_pos(b, i / 4.0) for i in range(5)]))
        name = b["kind"]
        head = b["head"]
        hit_pos = b["p1"]
        d = b["dir"]
        if name == "miss":
            self._spawn_snow_impact(hit_pos, near_feet=b.get("near_feet", False))
            dist = math.dist(EYE, hit_pos)
            self._snd("impact", False, dist, 0.0)
            if self.phase == "ucilev":
                for g in self.guards:
                    if g["alive"]:
                        g["flinch_t"] = self.t
            return

        self.stop_until_real = self._cap_real + 0.055
        self.shake_until = self._cap_real + 0.14
        self._spawn_gore(hit_pos, d, head, name)
        if name == "ucilev":
            self.u_headshot = bool(head)
            self.impact_t = self.t
            self.u_down_t = self.t
            self.slow_until = self.t + 0.38
            self._snd("body_hit", 1, bool(head), False, 0.5)
            self._snd("enemy_down", 112.0, 0.0)
        elif name == "pres":
            self.p_headshot = bool(head)
            self.impact_t = self.t
            self.slow_until = self.t + 0.42
            self._abort_t = self.t
            self._snd("dead_carrier")
            self._snd("body_hit", 6, bool(head), True, 0.92)
            self._snd("ridge_kill_silence")
            self._silence_until = self._cap_real + 1.45
            self._wind_only_at = self._cap_real + 1.45
            try:
                audio.fade_out_music(30)
            except Exception:
                pass
        else:
            self.hit_mark = self._cap_real
            self.hit_head = bool(head)
            g = self.guards[int(name[1:])]
            g["alive"] = False
            g["dead_t"] = self.t
            g["head"] = bool(head)
            self._snd("body_hit", 1, bool(head), True, 0.72)

    def update(self, keys=None):
        if not self._active or self.paused:
            return
        raw = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        prev_real = self._cap_real
        self._cap_real += raw
        if self.bullet is not None and not self.bullet["resolved"] and self._cap_real >= self.bullet["t_end"]:
            self._resolve_bullet()
        sdt = max(0.0, self._cap_real - max(prev_real, self.stop_until_real))
        dt = sdt * (SLOWMO if self.t < self.slow_until else 1.0)
        self.t += dt
        self.phase_t += dt
        if self.intro_u < 1.0:
            self.intro_u = clamp(self.t / INTRO_S, 0.0, 1.0)
        if self.intro_u >= 0.65 and not self._intro_clicked:
            self._intro_clicked = True
            self._intro_mist = 1.0
            self._snd("safety_click")
            self._snd("exhale")
        self._intro_mist = max(0.0, self._intro_mist - raw * 0.85)
        want_lb = 1.0 if self.phase in ("u_down", "radio", "pres_down") else 0.0
        self._lb += (want_lb - self._lb) * min(1.0, raw * 4.5)
        want_hud = 1.0 if self.phase in ("ucilev", "u_down") else 0.0
        self._hud_alpha += (want_hud - self._hud_alpha) * min(1.0, raw * 1.4)
        if self._cap_real >= self._silence_until:
            if self.phase == "pres_down" and self._wind_only_at >= 0.0 and self._cap_real >= self._wind_only_at:
                self._snd("bed", "ridge_wind_only")
            elif self.phase == "radio":
                self._snd("bed", "ridge_radio")
            elif self.phase == "wait":
                self._snd("bed", "ridge_standoff")
            else:
                self._snd("bed", "ridge")
        self._snd("update", raw)
        k = keys if keys is not None else pygame.key.get_pressed()
        try:
            want = bool(k[pygame.K_LSHIFT] or k[pygame.K_RSHIFT])
        except Exception:
            want = False
        self.holding = want and self.breath > 0.0 and self.winded <= 0.0
        if self.holding:
            self.breath = max(0.0, self.breath - raw)
            self._hold_time += raw
            self.hold_frost = min(1.0, self.hold_frost + raw * 0.45)
            self._snd("duck", 0.28, 0.10)
            self._snd("heartbeat")
            if self.breath <= 0.0:
                self.winded = 3.0
        else:
            if self._was_holding and self._hold_time > 0.4:
                self._snd("exhale")
            self._hold_time = 0.0
            self.hold_frost = max(0.0, self.hold_frost - raw * 0.90)
            self.winded = max(0.0, self.winded - raw)
            self.breath = min(BREATH_S, self.breath + raw * 0.8)
        self._was_holding = self.holding
        self.kick = max(0.0, self.kick - raw * 3.6)
        self.kick_yaw *= max(0.0, 1.0 - raw * 8.0)
        self._eye_rx *= max(0.0, 1.0 - raw * 7.5)
        self._eye_ry *= max(0.0, 1.0 - raw * 7.5)

        if self._bolt_t >= 0.0:
            b_age = self._cap_real - self._bolt_t
            if b_age >= 0.24 and not self._bolt_played:
                self._bolt_played = True
                self._snd("bolt_cycle")
                self._brass.append([self._cap_real, 0.0, 0.0, 0.85, -0.55, 0.0, 14.0])
            if b_age >= 1.15:
                self._bolt_t = -9.0
        if self._brass:
            keep_br = []
            for br in self._brass:
                if self._cap_real - br[0] < 0.75:
                    br[1] += br[3] * raw
                    br[2] += br[4] * raw
                    br[4] += 2.6 * raw
                    br[5] += br[6] * raw
                    keep_br.append(br)
            self._brass = keep_br

        if self.t >= self._breath_next:
            self._breath_next = self.t + 1.85
            if self.phase == "ucilev":
                self._breath_puffs.append((self._cap_real, UCILEV_AT[0], 1.56, UCILEV_AT[2]))
            if self.phase in ("ucilev", "u_down", "radio", "wait"):
                p_pos = self.pres_spot()[0]
                py = 1.05 if self.phase in ("ucilev", "u_down", "radio") else 1.56
                self._breath_puffs.append((self._cap_real, p_pos[0], py, p_pos[2]))
        if self._breath_puffs:
            self._breath_puffs = [bp for bp in self._breath_puffs if self._cap_real - bp[0] < 1.35]

        # Update ballistic blood droplets -> crimson snow stains
        keep_blood = []
        for b in self.blood:
            b[4] *= max(0.0, 1.0 - 1.5 * dt)
            b[6] *= max(0.0, 1.0 - 1.5 * dt)
            b[5] -= G * dt
            b[1] += b[4] * dt
            b[2] += b[5] * dt
            b[3] += b[6] * dt
            if b[2] <= 0.03:
                if len(self.snow_stains) < 120:
                    self.snow_stains.append((b[1], b[3], b[7] * 2.4, b[8]))
            elif self.t - b[0] < 1.8:
                keep_blood.append(b)
        self.blood = keep_blood

        # Update ballistic snow clods
        keep_snow = []
        for sc in self.snow_chunks:
            sc[4] *= max(0.0, 1.0 - 1.1 * dt)
            sc[6] *= max(0.0, 1.0 - 1.1 * dt)
            sc[5] -= G * dt
            sc[1] += sc[4] * dt
            sc[2] += sc[5] * dt
            sc[3] += sc[6] * dt
            if sc[2] > 0.02 and self.t - sc[0] < 1.4:
                keep_snow.append(sc)
        self.snow_chunks = keep_snow

        # Update dropped props (Ucilev's rifle / Retardovici's radio)
        for pr in self.dropped_props:
            if pr["rest"]:
                continue
            pr["vy"] -= G * dt
            pr["x"] += pr["vx"] * dt
            pr["y"] += pr["vy"] * dt
            pr["z"] += pr["vz"] * dt
            pr["yaw"] = (pr["yaw"] + pr["vyaw"] * dt) % 360.0
            pr["pitch"] += pr["vpitch"] * dt
            if pr["y"] <= 0.04:
                pr["y"] = 0.04
                if abs(pr["vy"]) > 0.6:
                    pr["vy"] = -pr["vy"] * 0.25
                    pr["vx"] *= 0.45
                    pr["vz"] *= 0.45
                    pr["vpitch"] *= 0.4
                else:
                    pr["vy"] = pr["vx"] = pr["vz"] = pr["vyaw"] = pr["vpitch"] = 0.0
                    pr["pitch"] = 0.0
                    pr["roll"] = 90.0
                    pr["rest"] = True

        if self.fail_t >= 0.0:
            if self.t - self.fail_t > 4.0:
                self._setup()
            return
        if self.phase in ("ucilev", "wait"):
            self.rescue -= raw
            if self.rescue <= 0.0:
                self.fail_t = self.t
                self.say("", "The rescue bird is down and up again - with him aboard.", 3.6)
                return
        if self.phase == "u_down":
            if self.impact_t is not None:
                imp_age = self._u_impact_age()
                if imp_age > 1.05 and self.line_i == 0:
                    self.line_i = 1
                    self._set_caption("UCILEV", UCILEV_LINE, 2.9, typewriter=True)
                if self.t >= self.slow_until and imp_age > 4.0:
                    self._set_phase("radio")
                    self.line_i = 0
        elif self.phase == "radio":
            n = int(self.phase_t / LINE_S)
            while self.line_i <= n and self.line_i < len(RADIO_LINES):
                self._set_caption("RETARDOVICI", RADIO_LINES[self.line_i], LINE_S, typewriter=True)
                self._snd("pa_squelch")
                self.line_i += 1
            if self.phase_t >= LINE_S * len(RADIO_LINES):
                self._set_phase("wait")
        elif self.phase == "pres_down":
            if self.impact_t is not None and self.t >= self.slow_until and self._p_impact_age() > 4.0:
                self.finish("win")

        if self.impacts:
            self.impacts = [x for x in self.impacts if self.t - x[0] < 1.0]
        if self.blood_bursts:
            self.blood_bursts = [x for x in self.blood_bursts if self._cap_real - x[0] < 0.7]
        if self.snow_plumes:
            self.snow_plumes = [x for x in self.snow_plumes if self._cap_real - x[0] < 0.9]
        if self.trails:
            self.trails = [x for x in self.trails if self._cap_real - x[0] < 0.65]

    def _ground_impact(self, o, d):
        """Ballistic ground intersection with gravity drop and wind drift."""
        # Solve o[1] + d[1]*MUZZLE_V*t - 0.5*G*t^2 = 0.05
        a = -0.5 * G
        b = d[1] * MUZZLE_V
        c = o[1] - 0.05
        disc = b * b - 4.0 * a * c
        if disc >= 0.0:
            sq = math.sqrt(disc)
            t1 = (-b - sq) / (2.0 * a)
            t2 = (-b + sq) / (2.0 * a)
            cands = [t for t in (t1, t2) if t > 0.0]
            tof = min(cands) if cands else 0.45
        else:
            tof = 0.45
        tof = clamp(tof, 0.02, 0.65)
        yr = math.radians(self.yaw)
        return (
            o[0] + d[0] * MUZZLE_V * tof + self.wind * tof * 0.9 * math.cos(yr),
            0.05,
            o[2] + d[2] * MUZZLE_V * tof - self.wind * tof * 0.9 * math.sin(yr),
        ), tof

    def fire(self):
        if self.t - self.last_shot < BOLT_S or self.phase in ("u_down", "pres_down") or self.fail_t >= 0.0:
            return None
        if self.bullet is not None and not self.bullet["resolved"]:
            self._resolve_bullet()
        self.intro_u = 1.0
        self.last_shot = self.t
        self.muzzle_flash_t = self._cap_real
        o = EYE
        d = self.view_dir()
        self.kick = 0.32                          # crisp muzzle jump that keeps target in scope
        self.kick_yaw = self.rng.uniform(-0.08, 0.08)
        self._eye_ry = clamp(self._eye_ry - 0.45, -1.0, 1.0)
        self._eye_rx = clamp(self._eye_rx + self.rng.uniform(-0.22, 0.22), -1.0, 1.0)
        self._snd("sniper_shot", 0.0, 10.0)
        best, hit = 1e9, None
        for name, c, rad, head in self.targets():
            dist = math.dist(o, c)
            tof = dist / MUZZLE_V
            # the round falls and drifts on the way: test against where the aim must have been
            aim_c = (c[0] - self.wind * tof * 0.9 * math.cos(math.radians(self.yaw)),
                     c[1] + 0.5 * G * tof * tof,
                     c[2] + self.wind * tof * 0.9 * math.sin(math.radians(self.yaw)))
            h = RB._ray_sphere(o, d, aim_c, rad)
            if h is not None and h < best:
                best, hit = h, (name, head, c, tof)

        sy, sp = self.sway()
        basis = m_mul(rot_y(self.yaw + sy), rot_x(-(self.pitch + sp)))
        p0 = v_add(EYE, m_apply(basis, (0.02, -0.06, 0.65)))

        if hit is None:
            self._bolt_t = self._cap_real
            self._bolt_played = False
            end, tof = self._ground_impact(o, d)
            dist_end = math.dist(o, end)
            p_aim = (o[0] + d[0] * dist_end, o[1] + d[1] * dist_end, o[2] + d[2] * dist_end)
            dx_u, dz_u = end[0] - UCILEV_AT[0], end[2] - UCILEV_AT[2]
            dist_u = math.hypot(dx_u, dz_u)
            # True near-boot hit: lands within 1.8 m of his boots and not far behind him
            fwd_dot = dx_u * _SHOT_FWD[0] + dz_u * _SHOT_FWD[1]
            near_feet = (self.phase == "ucilev" and dist_u <= 1.85 and fwd_dot <= 0.65)
            past_body = (self.phase == "ucilev" and not near_feet and dist_u <= 6.5
                         and abs(dx_u * (-_SHOT_FWD[1]) + dz_u * _SHOT_FWD[0]) <= 1.45)
            b_dur = FLIGHT_S * clamp(tof / 0.14, 0.65, 1.35)
            self.bullet = {
                "p0": p0, "p1": end, "p_aim": p_aim, "dir": d, "kind": "miss", "head": False,
                "near_feet": near_feet, "past_body": past_body,
                "t0": self._cap_real, "t_end": self._cap_real + b_dur,
                "dur": b_dur, "apex": 0.5 * G * tof * tof,
                "wind_bow": self.wind * tof * 0.9, "yaw": self.yaw, "resolved": False,
            }
            return "miss"

        name, head, tgt_c, tof = hit
        # Exact 3D point along the ballistic path at target distance (preserves leg/waist/chest/head height)
        dist_t = math.dist(o, tgt_c)
        p_aim = (o[0] + d[0] * dist_t, o[1] + d[1] * dist_t, o[2] + d[2] * dist_t)
        yr = math.radians(self.yaw)
        hit_pos = (
            p_aim[0] + self.wind * tof * 0.9 * math.cos(yr),
            clamp(p_aim[1] - 0.5 * G * tof * tof, 0.22, 1.74),
            p_aim[2] - self.wind * tof * 0.9 * math.sin(yr),
        )
        is_boss = name in ("ucilev", "pres")
        b_dur = FLIGHT_KILL_S if is_boss else FLIGHT_S
        self.bullet = {
            "p0": p0, "p1": hit_pos, "p_aim": p_aim, "dir": d, "kind": name, "head": bool(head),
            "near_feet": False, "t0": self._cap_real, "t_end": self._cap_real + b_dur,
            "dur": b_dur, "apex": 0.5 * G * tof * tof,
            "wind_bow": self.wind * tof * 0.9, "yaw": self.yaw, "resolved": False,
        }
        if name == "ucilev":
            self._bolt_t = self._cap_real
            self._bolt_played = False
            self.impact_t = None
            self.u_down_t = self.t
            self._set_phase("u_down")
            self.line_i = 0
        elif name == "pres":
            self._bolt_t = -9.0
            self.impact_t = None
            self._set_phase("pres_down")
        else:
            self._bolt_t = self._cap_real
            self._bolt_played = False
        return name

    # --- input -----------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if event.type == pygame.MOUSEMOTION:
            dx, dy = event.rel
            s = 0.02 * self.fov() / ZOOMS[0] * 4.0
            self.yaw = (self.yaw + dx * s) % 360.0
            self.pitch = clamp(self.pitch - dy * s, -40.0, 10.0)
            self._eye_rx = clamp(self._eye_rx - dx * 0.008, -0.85, 0.85)
            self._eye_ry = clamp(self._eye_ry - dy * 0.008, -0.85, 0.85)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:
                self.fire()
            elif event.button == 3:
                self.zoom_i = (self.zoom_i + 1) % len(ZOOMS)
        elif event.type == pygame.MOUSEWHEEL and event.y:
            self.zoom_i = int(clamp(self.zoom_i + (1 if event.y > 0 else -1), 0, len(ZOOMS) - 1))

    # --- draw ------------------------------------------------------------------

    def _draw_gore_world(self, r, tm):
        if self.craters:
            m = Mesh()
            for x, z, rad in self.craters:
                m.face([(x - rad, 0.036, z - rad), (x + rad, 0.036, z - rad),
                        (x + rad, 0.036, z + rad), (x - rad, 0.036, z + rad)],
                       (112, 122, 140), 1, True)
                ir = rad * 0.52
                m.face([(x - ir, 0.040, z - ir), (x + ir, 0.040, z - ir),
                        (x + ir, 0.040, z + ir), (x - ir, 0.040, z + ir)],
                       (56, 52, 50), 1, True)
            _w.add(r, m)
        if self.snow_stains:
            m = Mesh()
            for x, z, rad, col in self.snow_stains:
                m.face([(x - rad, 0.042, z - rad), (x + rad, 0.042, z - rad),
                        (x + rad, 0.042, z + rad), (x - rad, 0.042, z + rad)],
                       col, 1, True)
            _w.add(r, m)
        u_age = self._u_impact_age()
        if self.phase != "ucilev" and self.u_down_t > 0.0 and u_age > 0.45:
            k = clamp((u_age - 0.45) / 2.2, 0.0, 1.0)
            rad = 0.12 + 0.48 * k
            _w.add(r, _pool_mesh(UCILEV_AT[0] + _SHOT_FWD[0] * 0.35,
                                 UCILEV_AT[2] + _SHOT_FWD[1] * 0.35,
                                 rad, (64, 6, 10), 0.038, 1.4))
            _w.add(r, _pool_mesh(UCILEV_AT[0] + _SHOT_FWD[0] * 0.35,
                                 UCILEV_AT[2] + _SHOT_FWD[1] * 0.35,
                                 rad * 0.68, (108, 12, 16), 0.041, 2.2))
        p_age = self._p_impact_age()
        if self.phase == "pres_down" and self.impact_t is not None and p_age > 0.30:
            k = clamp((p_age - 0.30) / 2.2, 0.0, 1.0)
            rad = 0.16 + 0.74 * k
            _w.add(r, _pool_mesh(PRES_AT[0] + _SHOT_FWD[0] * 0.65,
                                 PRES_AT[2] + _SHOT_FWD[1] * 0.65,
                                 rad, (58, 5, 9), 0.038, 3.7))
            _w.add(r, _pool_mesh(PRES_AT[0] + _SHOT_FWD[0] * 0.65,
                                 PRES_AT[2] + _SHOT_FWD[1] * 0.65,
                                 rad * 0.66, (102, 11, 15), 0.041, 4.5))
        for t0, pos, is_head in self.blood_bursts:
            r.add_sprite(pos, _blood_mist_sprite(self._cap_real - t0, is_head), layer=_fx.FX_LAYER)
        for t0, pos in self.snow_plumes:
            r.add_sprite(pos, _snow_geyser_sprite(self._cap_real - t0), layer=2)

    def _draw_dropped_props(self, r, tm):
        for pr in self.dropped_props:
            mesh = _intro_rifle_mesh() if pr["kind"] == "rifle" else _radio_prop_mesh()
            rot = m_mul(rot_y(pr["yaw"]), m_mul(rot_x(pr["pitch"]), rot_z(pr["roll"])))
            m = Mesh()
            m.verts = [v_add((pr["x"], pr["y"], pr["z"]), m_apply(rot, v)) for v in mesh.verts]
            m.faces = list(mesh.faces)
            _w.add(r, m)
            if pr["kind"] == "radio":
                r.add_sprite((pr["x"], pr["y"] + 0.08, pr["z"]),
                             _fx.beacon((255, 52, 42), 0.16, int(tm), period_ms=700.0),
                             layer=_fx.FX_LAYER)

    def _draw_bullet(self, r, tm):
        b = self.bullet
        if b is not None and not b["resolved"]:
            u = clamp((self._cap_real - b["t0"]) / max(0.01, b["dur"]), 0.0, 1.0)
            head = self._bullet_pos(b, u)
            tail = self._bullet_pos(b, max(0.0, u - 0.14))
            wake = self._bullet_pos(b, max(0.0, u - 0.42))
            r.add_line3d(wake, tail, (186, 204, 232), 1, layer=3)
            r.add_line3d(tail, head, (255, 236, 176), 2, layer=4)
            r.add_sprite(head, _fx.glow((255, 224, 150), 0.22, int(tm),
                                        core=(255, 250, 220), intensity=1.1, max_px=12),
                         layer=_fx.FX_LAYER)
        for t0, pts in self.trails:
            el = self._cap_real - t0
            if el >= 0.55:
                continue
            fade = (1.0 - el / 0.55) ** 1.6
            col = (int(110 + 95 * fade), int(124 + 95 * fade), int(146 + 98 * fade))
            for pa, pb in zip(pts, pts[1:]):
                r.add_line3d(pa, pb, col, 1, layer=3)

    def _draw_particles_2d(self, r, surface):
        for _t0, x, y, z, vx, vy, vz, size, col in self.blood:
            proj = self._project(r, (x, y, z))
            if not proj[2]:
                continue
            sx, sy, _ = proj
            try:
                depth = r.to_cam((x, y, z))[2]
            except Exception:
                continue
            px = int(clamp(size * r.focal / max(depth, 0.2) * WIDTH / float(r.w), 2.0, 11.0))
            tail = self._project(r, (x - vx * 0.018, y - vy * 0.018, z - vz * 0.018))
            if tail[2]:
                pygame.draw.line(surface, col, (int(tail[0]), int(tail[1])), (int(sx), int(sy)), max(1, px // 2))
            pygame.draw.circle(surface, col, (int(sx), int(sy)), max(1, px // 2))

        for _t0, x, y, z, vx, vy, vz, size, col in self.snow_chunks:
            proj = self._project(r, (x, y, z))
            if not proj[2]:
                continue
            sx, sy, _ = proj
            try:
                depth = r.to_cam((x, y, z))[2]
            except Exception:
                continue
            px = int(clamp(size * r.focal / max(depth, 0.2) * WIDTH / float(r.w), 2.0, 9.0))
            surface.fill(col, (int(sx) - px // 2, int(sy) - px // 2, px, px))

    def _draw_ridge_snow(self, r, tm):
        """Wind-driven high-altitude Carpathian snow streaks across the ridge and clearing."""
        if self._reduced_motion():
            return
        yr = math.radians(self.yaw)
        fx, fz = math.sin(yr), math.cos(yr)
        rx, rz = math.cos(yr), -math.sin(yr)
        wind_v = self.wind * 1.2
        col = (118, 134, 164)
        for i in range(24):
            df = 6.0 + ((i * 3.3) % 36.0)
            ox = ((i * 53 + self.t * wind_v * 3.2) % 32.0) - 16.0
            oy = (((i * 29) % 15 - 6) - (self.t * 3.0 + i * 0.7) % 12.0) * 0.65
            p0 = (
                EYE[0] + fx * df + rx * ox,
                EYE[1] + oy,
                EYE[2] + fz * df + rz * ox,
            )
            p1 = (p0[0] + rx * (self.wind * 0.045), p0[1] - 0.14, p0[2] + rz * (self.wind * 0.045))
            r.add_line3d(p0, p1, col, 1, layer=2)

    def _populate_world(self, r, tm, ie, peripheral=False):
        del _w.LAST[:]
        CS.put_helicopter(r, HELI_CRASH_AT, HELI_CRASH_YAW, 5.0, 14.0, 0.0, 0.0, burned=True)
        _f3d.emit_fire(r, (HELI_CRASH_AT[0] - 0.8, 0.65, HELI_CRASH_AT[2] + 0.5), tm, seed=19,
                       size=1.50, heat=1.30, smoky=True, embers=True, bed=True, layer=2)
        _f3d.emit_fire(r, (HELI_CRASH_AT[0] + 1.4, 0.95, HELI_CRASH_AT[2] + 1.2), tm, seed=27,
                       size=0.95, heat=1.05, smoky=True, embers=False, bed=False, layer=2)
        for sk in range(4):
            r.add_sprite((HELI_CRASH_AT[0] + 0.4 + math.sin(self.t * 0.6 + sk) * 0.8,
                          2.2 + sk * 1.6, HELI_CRASH_AT[2] + 0.8),
                         _f3d.emit_smoke(tm, seed=310 + sk, size_m=1.4 + sk * 0.45, heat=0.55 - sk * 0.12),
                         layer=2)
        # Parked Guard escort truck on the west edge of the apron with glowing headlights
        CS.put_wheeled(r, "gun_truck", TRUCK_AT, TRUCK_YAW, 0.0, 0.0, 0.0)
        for sx in (-0.68, 0.68):
            hl = CS._xf((sx, 1.05, 2.95), TRUCK_AT, TRUCK_YAW, 0.0, 0.0)
            r.add_sprite(hl, _fx.glow((255, 224, 168), 0.75, int(tm), core=(255, 248, 226),
                                      intensity=1.05, max_px=22), layer=_fx.FX_LAYER)
        for bi, dist_m in enumerate((4.5, 9.5, 15.0)):
            bp = CS._xf((0.0, 0.95, 2.95 + dist_m), TRUCK_AT, TRUCK_YAW, 0.0, 0.0)
            r.add_sprite(bp, _fx.haze((255, 224, 174), 1.1 + dist_m * 0.16, int(tm),
                                      seed=520 + bi, intensity=0.16 * (1.0 - bi * 0.25)), layer=_fx.FX_LAYER)
        # Distant crash glow & drifting valley mist tying back to Maru's clearing and Last Flight
        _f3d.emit_fire(r, MARU_GLOW_AT, tm, seed=47, size=1.45, heat=1.15,
                       smoky=True, embers=False, bed=False, layer=2)
        for mi, (mx, _my, mz) in enumerate((_off(-22.0, -18.0), _off(24.0, 18.0), _off(-4.0, 26.0))):
            drift = math.sin(self.t * 0.35 + mi * 1.9) * 3.5
            r.add_sprite((mx + drift, 2.6, mz),
                         _fx.haze((138, 158, 192), 5.6, int(tm), seed=610 + mi, intensity=0.14),
                         layer=2)
        for lx, lz in ((-7.8, -2.0), (10.4, -9.2), (-8.0, 9.6), (9.8, 9.2)):
            r.add_sprite((PAD[0] + lx, 1.88, PAD[2] + lz),
                         _fx.glow((255, 200, 128), 1.25, int(tm), intensity=0.72, max_px=22),
                         layer=_fx.FX_LAYER)
        for fx_o, fz_o in ((-4.2, -4.8), (4.6, 5.0)):
            r.add_sprite((PAD[0] + fx_o, 0.26, PAD[2] + fz_o),
                         _fx.glow((255, 84, 46), 0.65, int(tm), flicker=0.14, intensity=0.9, max_px=18),
                         layer=_fx.FX_LAYER)

        self._draw_gore_world(r, tm)

        p_pos, p_yaw, p_pose = self.pres_spot()
        p_hit = (self.phase == "pres_down" and self.impact_t is not None)
        p_flags = ("head_wound",) if (p_hit and self.p_headshot) else ()
        p_joints = _w.actor(r, "president", p_pose, p_pos, p_yaw, int(tm),
                            seed=12, amp=0.0 if p_hit else 0.18,
                            expression="surprised" if (p_hit and self._p_impact_age() < 0.6) else "angry",
                            hd=p_hit, wound=3 if p_hit else 0, bloody=p_hit, flags=p_flags)
        if not p_hit and p_joints and "rhand" in p_joints:
            rh = p_joints["rhand"]
            rm = _radio_prop_mesh()
            rot_r = rot_y(p_yaw)
            m_rad = Mesh()
            m_rad.verts = [v_add(rh, m_apply(rot_r, (v[0], v[1] + 0.05, v[2] + 0.02))) for v in rm.verts]
            m_rad.faces = list(rm.faces)
            _w.add(r, m_rad)

        u_pos, u_yaw, u_pose = self.ucilev_spot()
        u_hit = (self.phase != "ucilev" and self.u_down_t > 0.0
                 and not (self.phase == "u_down" and self.impact_t is None))
        if not u_hit:
            u_hum = _w.hum("ucilev")
            u_pose = _w.life_pose(u_pose, int(tm), 0.08, 34)
            u_pose, r_orig, r_basis = hold_frame(u_hum, u_pose, u_pos, u_yaw,
                                                 weapon="sniper_rifle", mode="port")
            self._u_gun_xform = (r_orig, r_basis)
        u_flags = ("head_wound",) if (u_hit and self.u_headshot) else ()
        _w.actor(r, "ucilev", u_pose, u_pos, u_yaw, int(tm),
                 seed=34, amp=0.0, rifle_on=False,
                 expression="worried" if u_hit else "stern",
                 hd=u_hit, wound=3 if u_hit else 0, bloody=u_hit, flags=u_flags)
        if not u_hit and self._u_gun_xform is not None:
            ro, rb = self._u_gun_xform
            rm = _intro_rifle_mesh()
            m_gun = Mesh()
            m_gun.verts = [v_add(ro, m_apply(rb, v)) for v in rm.verts]
            m_gun.faces = list(rm.faces)
            _w.add(r, m_gun)

        for i, g in enumerate(self.guards):
            flinching = g["alive"] and 0.0 <= self.t - g["flinch_t"] < 3.5
            pose = dict(POSES["kneel"] if flinching else POSES["ready"]) if g["alive"] else dict(POSES["dead_back"])
            g_hit = not g["alive"]
            g_amp = 0.0 if g_hit else (0.06 if self.phase == "pres_down" else 0.25)
            _w.actor(r, ("guard", "rifle"), pose, (g["x"], 0.0, g["z"]), g["yaw"], int(tm),
                     seed=300 + i, amp=g_amp, rifle_on=g["alive"],
                     hd=g_hit, wound=3 if g_hit else 0, bloody=g_hit,
                     flags=("os12", "head_wound") if (g_hit and g.get("head")) else ("os12",))

        for bi, (bt0, bx, by, bz) in enumerate(self._breath_puffs):
            bu = clamp((self._cap_real - bt0) / 1.35, 0.0, 1.0)
            bpos = (bx + self.wind * 0.08 * bu, by + 0.24 * bu, bz)
            r.add_sprite(bpos, _fx.haze((212, 224, 242), 0.14 + 0.22 * bu, int(tm),
                                        seed=700 + bi, intensity=0.22 * (1.0 - bu)),
                         layer=_fx.FX_LAYER)

        self._draw_dropped_props(r, tm)

        rp = self.rescue_pos()
        r_yaw = 135.0 if self._abort_t >= 0.0 else (_yaw_to(rp, PAD) if self.fail_t < 0.0 else 30.0)
        r_pitch = -12.0 if self._abort_t >= 0.0 else -4.0
        r_roll = 18.0 if self._abort_t >= 0.0 else 0.0
        CS.put_helicopter(r, rp, r_yaw, r_pitch, r_roll,
                          (tm * 1.5) % 360.0, (tm * 2.4) % 360.0)
        r.add_sprite((rp[0], rp[1] - 0.4, rp[2]), _fx.glow((240, 244, 255), 1.2, int(tm), pulse=0.3),
                     layer=_fx.FX_LAYER)

        if not peripheral:
            self._draw_bullet(r, tm)
        self._draw_ridge_snow(r, tm)

        mf_age = self._cap_real - self.muzzle_flash_t
        if 0.0 <= mf_age < 0.08:
            basis = m_mul(rot_y(self.yaw), rot_x(-self.pitch))
            fp = v_add(EYE, m_apply(basis, (0.06, -0.07, 0.85)))
            rad_f = 0.48 if self._flash_reduction() else 0.85
            r.add_sprite(fp, _fx.flash(int(mf_age * 1000.0), (255, 224, 165), rad_f, 80), layer=_fx.FX_LAYER)

        if peripheral and ie >= 0.85:
            sy, sp = self.sway()
            ryaw = self.yaw + sy + self.kick_yaw
            rpitch = self.pitch + sp + self.kick
            CS.put(r, "m8d_ridge_perch_gun", _perch_gun_mesh, EYE, ryaw, rpitch, 0.0)
        elif ie < 0.92:
            sy, sp = self.sway()
            ryaw = self.yaw + sy - 10.0 * (1.0 - ie)
            rpitch = self.pitch + sp - 14.0 * (1.0 - ie)
            basis = m_mul(rot_y(ryaw), rot_x(-rpitch))
            off_l = (0.14 * (1.0 - ie), -0.14 * (1.0 - ie) - 0.04, 0.42 - 0.14 * ie)
            r_pos = v_add(EYE, m_apply(basis, off_l))
            CS.put(r, "m8d_ridge_intro_rifle", _intro_rifle_mesh, r_pos, ryaw, rpitch, 0.0)

    def draw(self, surface):
        if not self._active:
            return
        tm = self.t * 1000.0
        d = self.view_dir()
        tgt = (EYE[0] + d[0] * 50.0, EYE[1] + d[1] * 50.0, EYE[2] + d[2] * 50.0)
        ie = self._optic_ease()
        cur_fov = PERIPH_FOV + (self.fov() - PERIPH_FOV) * ie
        lights = _pad_lights()
        pools = _pad_pools()

        # 1. Peripheral 1x ridge-perch render (always live on GL; throttled on software backend)
        periph_surf = _get_surf("periph", WIDTH, HEIGHT)
        r_probe = DS.ridge_renderer(PAD, EYE)
        is_gl = getattr(r_probe, "backend", "") == "gl"
        need_periph = is_gl or self._periph_state is None or (
            abs(self.yaw - self._periph_state[0]) > 0.25
            or abs(self.pitch - self._periph_state[1]) > 0.25
            or (self.t - self._periph_state[2]) > 0.18
        )
        if need_periph:
            r = DS.ridge_frame(PAD, EYE, tgt, PERIPH_FOV, t=int(tm), lights=lights, pools=pools)
            self._populate_world(r, tm, ie, peripheral=True)
            CS.present(r, periph_surf)
            self._periph_state = (self.yaw, self.pitch, self.t)

        # Creamy 2-stage optical defocus & smooth vignette dimming outside the optic
        blur_m = _get_surf("blur_m", WIDTH // 3, HEIGHT // 3)
        blur_q = _get_surf("blur_q", WIDTH // 6, HEIGHT // 6)
        blur_out = _get_surf("blur_out", WIDTH, HEIGHT)
        pygame.transform.smoothscale(periph_surf, (WIDTH // 3, HEIGHT // 3), blur_m)
        pygame.transform.smoothscale(blur_m, (WIDTH // 6, HEIGHT // 6), blur_q)
        pygame.transform.smoothscale(blur_q, (WIDTH, HEIGHT), blur_out)
        surface.blit(blur_out, (0, 0))
        periph_dim = _get_periph_tint()
        surface.blit(periph_dim, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if self.hold_frost > 0.02:
            veil = _get_veil(int(68 * self.hold_frost))
            surface.blit(veil, (0, 0))

        # Ejected brass casing arcing across the blurred right periphery
        for _bt0, bx, by, _vx, _vy, bang, _va in self._brass:
            px = int(WIDTH * 0.56 + bx * HEIGHT * 0.45)
            py = int(HEIGHT * 0.56 + by * HEIGHT * 0.45)
            dx_b = math.cos(bang) * 10.0
            dy_b = math.sin(bang) * 10.0
            pygame.draw.line(surface, (214, 176, 86), (px - dx_b, py - dy_b), (px + dx_b, py + dy_b), 4)
            pygame.draw.line(surface, (255, 232, 162), (px - dx_b * 0.4, py - dy_b * 0.4), (px + dx_b * 0.4, py + dy_b * 0.4), 2)

        # 2. Magnified optic lens render (must run second so ``r`` holds scope camera for 2D particles)
        bolt_roll = 0.0
        if self._bolt_t >= 0.0:
            b_age = self._cap_real - self._bolt_t
            if 0.20 <= b_age <= 1.08:
                bu = clamp((b_age - 0.20) / 0.88, 0.0, 1.0)
                rm_scale = 0.35 if self._reduced_motion() else 1.0
                bolt_roll = 7.5 * math.sin(math.pi * bu) * rm_scale
        scope_surf = _get_surf("scope", WIDTH, HEIGHT)
        r = DS.ridge_frame(PAD, EYE, tgt, cur_fov, t=int(tm), lights=lights, pools=pools, roll=bolt_roll)
        self._populate_world(r, tm, ie, peripheral=False)
        CS.present(r, scope_surf)
        self._draw_particles_2d(r, scope_surf)

        frost = clamp(self._intro_mist * 0.75 + self.hold_frost * 0.65, 0.0, 1.0)
        eye_off = (self._eye_rx, self._eye_ry)
        target_rad = int(HEIGHT * 0.42)
        if ie < 1.0:
            full_rad = int(math.hypot(WIDTH, HEIGHT) * 0.56)
            raw_rad = int(round(full_rad + (target_rad - full_rad) * ie))
            rad = target_rad if raw_rad <= target_rad + 4 else (raw_rad // 8 * 8)
            if ie < 0.35:
                surface.blit(scope_surf, (0, 0))
            else:
                _blit_circular_lens(surface, scope_surf, rad, frost=frost, eye_off=eye_off)
        else:
            _blit_circular_lens(surface, scope_surf, target_rad, frost=frost, eye_off=eye_off)

        self._scope(surface)
        if self.phase == "pres_down" and self.impact_t is not None:
            fade_k = _ease((self._p_impact_age() - 2.1) / 1.5)
            if fade_k > 0.01:
                surface.blit(_get_veil(int(255 * fade_k)), (0, 0))
        self._letterbox(surface)
        self._hud(surface)

    def _scope(self, surface):
        cx, cy = WIDTH // 2, HEIGHT // 2
        ie = self._optic_ease()
        target_rad = int(HEIGHT * 0.42)
        if ie < 1.0:
            full_rad = int(math.hypot(WIDTH, HEIGHT) * 0.56)
            raw_rad = int(round(full_rad + (target_rad - full_rad) * ie))
            rad = target_rad if raw_rad <= target_rad + 4 else (raw_rad // 8 * 8)
            if ie < 0.38:
                return
        else:
            rad = target_rad

        # Outer scope tube housing, elevation/windage turrets, and coated glass bevel
        surface.blit(_housing(rad), (0, 0))

        # Authentic Eastern-bloc PSO-1 sniper reticle: fine black stadia, illuminated amber-red
        # center chevron, ballistic drop chevrons, and lower-left stadiametric rangefinder arc
        col = (14, 16, 20)
        thick = int(rad * 0.44)
        pygame.draw.line(surface, col, (cx - rad, cy), (cx - thick, cy), 3)
        pygame.draw.line(surface, col, (cx + thick, cy), (cx + rad, cy), 3)
        pygame.draw.line(surface, col, (cx, cy + int(rad * 0.38)), (cx, cy + rad), 3)
        pygame.draw.line(surface, col, (cx - thick, cy), (cx - 12, cy), 1)
        pygame.draw.line(surface, col, (cx + 12, cy), (cx + thick, cy), 1)
        pygame.draw.line(surface, col, (cx, cy - rad), (cx, cy - 12), 1)
        pygame.draw.line(surface, col, (cx, cy + 14), (cx, cy + int(rad * 0.38)), 1)
        for i in range(1, 6):
            step = int(rad * 0.075 * i)
            tick = 6 if i % 2 == 0 else 4
            pygame.draw.line(surface, col, (cx - step, cy - tick), (cx - step, cy + tick), 1)
            pygame.draw.line(surface, col, (cx + step, cy - tick), (cx + step, cy + tick), 1)
        # Ballistic drop chevrons below center
        for ci, dy in enumerate((18, 36, 56)):
            w = 5 - ci
            pygame.draw.line(surface, col, (cx - w, cy + dy + w), (cx, cy + dy), 1)
            pygame.draw.line(surface, col, (cx + w, cy + dy + w), (cx, cy + dy), 1)
        # Lower-left stadiametric rangefinder bracket (signature PSO-1 detail)
        rf_x0, rf_y0 = cx - int(rad * 0.46), cy + int(rad * 0.36)
        pygame.draw.line(surface, col, (rf_x0, rf_y0), (rf_x0 + 62, rf_y0), 1)
        pts_rf = [(rf_x0 + k * 10, rf_y0 - int(28.0 / (1.0 + k * 0.42))) for k in range(7)]
        pygame.draw.lines(surface, col, False, pts_rf, 1)
        # Illuminated PSO amber-red aiming chevron
        chev_c = (238, 62, 42)
        pygame.draw.line(surface, chev_c, (cx - 6, cy + 6), (cx, cy), 2)
        pygame.draw.line(surface, chev_c, (cx + 6, cy + 6), (cx, cy), 2)
        surface.set_at((cx, cy), (255, 198, 128))

    def _letterbox(self, surface):
        h = int(HEIGHT * 0.095 * R._ease(clamp(self._lb, 0.0, 1.0)))
        if h > 0:
            surface.fill((0, 0, 0), (0, 0, WIDTH, h))
            surface.fill((0, 0, 0), (0, HEIGHT - h, WIDTH, h))

    def _draw_caption(self, surface):
        cap = self._cap
        if cap is None:
            if self.lines:
                t0, who, text, dur = self.lines[-1]
                age = self.t - t0
                if age < dur:
                    cap = (self._cap_real - age, who, text, dur, False)
            if cap is None:
                return
        t0, who, text, dur, use_tw = cap
        el = self._cap_real - t0
        if el < 0.0 or el >= dur:
            return
        if use_tw:
            n = max(1, min(len(text), int(el * 22.0)))
        else:
            n = len(text)
        a = min(clamp(el / 0.14, 0.0, 1.0), clamp((dur - el) / 0.45, 0.0, 1.0))
        if a <= 0.02:
            return
        from ui import speechbox
        layer = _cap_surface()
        layer.fill((0, 0, 0, 0))
        speechbox.draw_caption(layer, who, text, shown=n, band=(HEIGHT - 74, HEIGHT - 10))
        layer.set_alpha(int(255 * a))
        surface.blit(layer, (0, 0))

    def _hud(self, surface):
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.fail_t >= 0.0:
            k = clamp((self.t - self.fail_t - 1.5) / 2.0, 0.0, 1.0)
            surface.blit(_get_veil(int(255 * k)), (0, 0))
            img = font_terminal.render("HE GOT AWAY  -  AGAIN FROM THE RIDGE", True, (220, 200, 190))
            surface.blit(img, img.get_rect(center=(cx, cy)))
            self._draw_caption(surface)
            return
        if self.phase == "pres_down":
            self._draw_caption(surface)
            return
        if self.phase == "wait" and self.phase_t < 2.2:
            H.objective(surface, "Shoot anyway")
        elif self._hud_alpha > 0.02:
            head = {"ucilev": "Take Ucilev", "u_down": "", "radio": "Listen"}.get(self.phase, "")
            if head:
                H.objective(surface, head)
        if self._hud_alpha > 0.03:
            hud_surf = _get_hud_surf()
            hud_surf.fill((0, 0, 0, 0))
            x, y = 28, HEIGHT - 154
            rng = math.dist(EYE, PRES_AT)
            H._text(hud_surf, font_terminal_small, "RANGE %d M   ZOOM x%d" % (rng, int(round(72.0 / self.fov()))),
                    H.TEXT, (x, y))
            arrow = ">" * int(abs(self.wind)) if self.wind > 0 else "<" * int(abs(self.wind))
            H._text(hud_surf, font_terminal_small, "WIND %.1f M/S %s" % (abs(self.wind), arrow), H.TEXT, (x, y + 22))
            H._text(hud_surf, font_terminal_small, "BREATH [SHIFT]", H.DANGER if self.winded > 0 else H.TEXT,
                    (x, y + 44))
            H._bar(hud_surf, x + 150, y + 51, 140, self.breath / BREATH_S, H.ACCENT, h=6)
            if self.phase in ("ucilev", "wait"):
                H._text(hud_surf, font_terminal_small, "RESCUE BIRD  %d S" % int(math.ceil(self.rescue)),
                        H.DANGER if self.rescue < 12 else H.TEXT, (WIDTH - 28, 22), "topright")
            if self.t < 9.0 and self.phase == "ucilev":
                H._text(hud_surf, font_terminal_small, "[RMB / WHEEL] ZOOM   [SHIFT] BREATH   [LMB] FIRE",
                        H.DIM, (x, y + 68))
            if self.t - self.last_shot < BOLT_S and self.phase in ("ucilev", "u_down"):
                H._text(hud_surf, font_terminal_small, "BOLT", H.TEXT, (cx, cy + 40), "midtop")
            hud_surf.set_alpha(int(255 * clamp(self._hud_alpha, 0.0, 1.0)))
            surface.blit(hud_surf, (0, 0))
        self._draw_caption(surface)


_MASKS = {}
_HOUSINGS = {}
_LENS_ALPHA = {}
_LENS_WORK = {}
_VEIL = [None]
_CAP_SURF = [None]
_HUD_SURF = [None]
_PERIPH_TINT = [None]
_PAD_LIGHTS = tuple(
    {"pos": (PAD[0] + x, 4.0, PAD[2] + z), "color": (255, 206, 146), "intensity": 0.90, "range": 19.0}
    for x, z in ((-7.8, -2.0), (10.4, -9.2), (-8.0, 9.6), (9.8, 9.2))
) + (
    {"pos": (HELI_CRASH_AT[0] - 0.8, 1.9, HELI_CRASH_AT[2] + 0.5),
     "color": (255, 128, 44), "intensity": 1.45, "range": 16.0},
    {"pos": (TRUCK_AT[0] + 2.5, 1.4, TRUCK_AT[2] - 2.0), "color": (255, 216, 152), "intensity": 1.05, "range": 20.0},
    {"pos": (MARU_GLOW_AT[0], 2.2, MARU_GLOW_AT[2]), "color": (255, 118, 44), "intensity": 1.40, "range": 22.0},
    {"pos": (EYE[0] + _FWD_XZ[0] * 2.6, EYE[1] + 0.9, EYE[2] + _FWD_XZ[1] * 2.6),
     "color": (152, 186, 244), "intensity": 1.25, "range": 14.0},
)
_PAD_POOLS = (
    {"pos": (HELI_CRASH_AT[0] - 0.8, 0.4, HELI_CRASH_AT[2] + 0.5),
     "range": 10.5, "color": (255, 126, 44), "intensity": 1.55},
    {"pos": (PAD[0] + 1.0, 0.4, PAD[2] - 0.8),
     "range": 12.5, "color": (255, 206, 140), "intensity": 1.10},
    {"pos": (TRUCK_AT[0] + 5.5, 0.4, TRUCK_AT[2] - 3.5),
     "range": 10.0, "color": (255, 214, 152), "intensity": 0.95},
    {"pos": (MARU_GLOW_AT[0], 0.4, MARU_GLOW_AT[2]),
     "range": 9.5, "color": (255, 118, 42), "intensity": 1.35},
)


def _get_veil(alpha):
    v = _VEIL[0]
    if v is None:
        v = _VEIL[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    v.fill((0, 0, 0, alpha))
    return v


def _get_surf(key, w, h):
    s = _SCOPE_SURFS.get((key, w, h))
    if s is None:
        s = _SCOPE_SURFS[(key, w, h)] = pygame.Surface((w, h))
    return s


def _get_periph_tint():
    """Silky pixel-exact nocturnal peripheral vignette (zero concentric banding)."""
    t = _PERIPH_TINT[0]
    if t is None:
        t = _PERIPH_TINT[0] = pygame.Surface((WIDTH, HEIGHT))
        try:
            import numpy as np
            ys, xs = np.ogrid[:HEIGHT, :WIDTH]
            cx, cy = WIDTH * 0.5, HEIGHT * 0.5
            dist = np.hypot((xs - cx) / (HEIGHT * 0.42), (ys - cy) / (HEIGHT * 0.42))
            # Smoothly fall from ~0.78 near scope edge to ~0.42 in far corners (readable night ridge)
            u = np.clip((dist - 1.0) / 0.95, 0.0, 1.0)
            k = 0.78 - 0.36 * (u * u * (3.0 - 2.0 * u))
            arr = pygame.surfarray.pixels3d(t)
            arr[:, :, 0] = np.clip(k.T * 214.0, 0, 255).astype(np.uint8)
            arr[:, :, 1] = np.clip(k.T * 228.0, 0, 255).astype(np.uint8)
            arr[:, :, 2] = np.clip(k.T * 252.0, 0, 255).astype(np.uint8)
            del arr
        except Exception:
            t.fill((96, 108, 132))
    return t


def _cap_surface():
    v = _CAP_SURF[0]
    if v is None:
        v = _CAP_SURF[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    return v


def _get_hud_surf():
    v = _HUD_SURF[0]
    if v is None:
        v = _HUD_SURF[0] = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
    return v


def _lens_alpha(rad):
    """Silky circular glass-cutout & optical edge vignette mask (zero stepping)."""
    m = _LENS_ALPHA.get(rad)
    if m is None:
        if len(_LENS_ALPHA) > 20:
            _LENS_ALPHA.clear()
            _LENS_WORK.clear()
        d = rad * 2
        m = pygame.Surface((d, d), pygame.SRCALPHA)
        try:
            import numpy as np
            ys, xs = np.ogrid[:d, :d]
            dist = np.hypot(xs - rad + 0.5, ys - rad + 0.5)
            alpha = np.clip((rad - dist) * 1.5, 0.0, 1.0)
            edge = np.clip((dist / float(max(1, rad)) - 0.72) / 0.28, 0.0, 1.0)
            vig = 1.0 - 0.42 * (edge * edge)
            rgb = pygame.surfarray.pixels3d(m)
            alp = pygame.surfarray.pixels_alpha(m)
            rgb[:, :, 0] = np.clip(vig.T * 248.0, 0, 255).astype(np.uint8)
            rgb[:, :, 1] = np.clip(vig.T * 252.0, 0, 255).astype(np.uint8)
            rgb[:, :, 2] = np.clip(vig.T * 255.0, 0, 255).astype(np.uint8)
            alp[:, :] = np.clip(alpha.T * 255.0, 0, 255).astype(np.uint8)
            del rgb, alp
        except Exception:
            m.fill((0, 0, 0, 0))
            pygame.draw.circle(m, (255, 255, 255, 255), (rad, rad), rad)
        _LENS_ALPHA[rad] = m
    return m


def _blit_circular_lens(surface, scope_surf, rad, frost=0.0, eye_off=(0.0, 0.0)):
    cx, cy = WIDTH // 2, HEIGHT // 2
    rad = max(16, int(rad))
    d = rad * 2
    work = _LENS_WORK.get(rad)
    if work is None:
        work = _LENS_WORK[rad] = pygame.Surface((d, d), pygame.SRCALPHA)
    work.blit(scope_surf, (0, 0), (cx - rad, cy - rad, d, d))
    if frost > 0.02:
        w = max(8, int(rad * 0.16))
        pygame.draw.circle(work, (214, 228, 248, int(46 * frost)), (rad, rad), rad, w)
        pygame.draw.circle(work, (226, 238, 255, int(24 * frost)), (rad, rad), rad - int(w * 0.5), int(w * 0.9))
    ex, ey = eye_off
    emag = math.hypot(ex, ey)
    if emag > 0.04:
        ox = int(ex * rad * 0.28)
        oy = int(ey * rad * 0.28)
        a_sh = int(clamp(emag * 165.0, 0.0, 175.0))
        pygame.draw.circle(work, (4, 6, 10, a_sh), (rad + ox, rad + oy), rad + int(rad * 0.16), int(rad * 0.28))
    work.blit(_lens_alpha(rad), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surface.blit(work, (cx - rad, cy - rad))


def _housing(rad):
    """Cached metallic PSO-style scope tube bezel, turrets, soft eyecup shadow, and glass sheen."""
    h = _HOUSINGS.get(rad)
    if h is None:
        if len(_HOUSINGS) > 20:
            _HOUSINGS.clear()
        cx, cy = WIDTH // 2, HEIGHT // 2
        h = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        # Top elevation drum turret (12 o'clock) & right windage turret (3 o'clock)
        tw, th = max(24, int(rad * 0.14)), max(14, int(rad * 0.075))
        pygame.draw.rect(h, (22, 24, 28, 245), (cx - tw, cy - rad - th - 6, tw * 2, th + 10), border_radius=3)
        pygame.draw.rect(h, (58, 64, 74, 220), (cx - tw + 2, cy - rad - th - 4, tw * 2 - 4, 3))
        for kx in range(-tw + 6, tw - 4, 7):
            pygame.draw.line(h, (44, 48, 56, 220),
                             (cx + kx, cy - rad - th - 2), (cx + kx, cy - rad - 3), 1)
        pygame.draw.rect(h, (22, 24, 28, 245), (cx + rad - 4, cy - tw, th + 10, tw * 2), border_radius=3)
        pygame.draw.rect(h, (58, 64, 74, 220), (cx + rad + th + 1, cy - tw + 2, 3, tw * 2 - 4))
        for ky in range(-tw + 6, tw - 4, 7):
            pygame.draw.line(h, (44, 48, 56, 220),
                             (cx + rad + 2, cy + ky), (cx + rad + th + 2, cy + ky), 1)
        # Soft drop shadow outside the matte-black ocular tube
        for dr, a in ((16, 45), (13, 95)):
            pygame.draw.circle(h, (4, 6, 10, a), (cx, cy), rad + dr, 4)
        # Matte gunmetal outer tube + cool moonlight top-left rim + inner rubber eyecup
        pygame.draw.circle(h, (12, 14, 18, 250), (cx, cy), rad + 9, 12)
        pygame.draw.arc(h, (76, 86, 102, 190), (cx - rad - 14, cy - rad - 14, (rad + 14) * 2, (rad + 14) * 2),
                        math.radians(105), math.radians(205), 2)
        pygame.draw.circle(h, (34, 38, 46, 240), (cx, cy), rad + 2, 3)
        pygame.draw.circle(h, (6, 8, 11, 252), (cx, cy), rad, 5)
        # Faint anti-reflective upper-left lens arc sheen
        pygame.draw.arc(h, (150, 182, 224, 18),
                        (cx - int(rad * 0.88), cy - int(rad * 0.88), int(rad * 1.76), int(rad * 1.76)),
                        math.radians(110), math.radians(158), 4)
        _HOUSINGS[rad] = h
    return h


def _mask(rad):
    """Compatibility wrapper returning the scope housing overlay."""
    m = _MASKS.get(rad)
    if m is None:
        m = _MASKS[rad] = _housing(rad)
    return m


def _pad_lights():
    return _PAD_LIGHTS


def _pad_pools():
    return _PAD_POOLS


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = RidgeScene()
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
        STATE.m8_ridge_active = False
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
