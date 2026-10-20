"""Mission 6 - the interactive 3D train scene (``docs/MISSION6_PLOT.md``).

A short shoulder-cam set piece on the rail platform: Biribel covers Volkov's
run to the waiting train, fires the K9 (K93D) over its holo sight, reloads,
and watches the single shot come out of the dark.  Hold RMB to aim down the
sights.  The scene owns its own engine3d Renderer, clock, camera, guards and audio; the top-down mission is frozen
while it runs and hands off to the ending film through ``flow.on_train_done``.

Design rules
    * Deterministic: the clock is a dt accumulator (``STATE.dt``), all
      animation is sin-driven, no wall clock or unseeded RNG.
    * Never strand the mission: ``force_finish`` is idempotent and hands off
      exactly once on success/skip/exception.  A failed run goes to the
      death/failure terminal instead and retries the train checkpoint.
    * Story-safe: Guard return fire is lethal (no 1-HP floor).  Volkov dies at
      25.85 s in every successful run; the player's job is to get him to the
      train, not to save him.  If two or more Guards are still up he is cut
      down in the open and the run fails.
    * Headless: with no input the failure branch runs on its own.
"""
import math
import os

import pygame

from core.config import (
    HEIGHT, WIDTH, audio, draw_scanlines, draw_vignette, font_dialogue,
    font_prompt, font_speaker, font_terminal, font_terminal_small,
    get_scaled_mouse, resource_path,
)
from core.state import STATE
from core.outfits import OUTFIT_GUARD
from cutscenes import m5fx3d as _fx
from cutscenes import m6world3d as _w
from engine.assets import load_image
from engine3d import (
    POSES, Renderer, blend, box, clamp, disc_xz, m_apply, pose_run, rot_x,
    rot_y, v_add,
)

RES = 0.80                       # internal render scale, smooth upscale
RW, RH = int(WIDTH * RES), int(HEIGHT * RES)

CONTROL_AT = 2.0
SHOT_AT = 23.0
CUT_AT = SHOT_AT                  # the dedicated cinematic starts on the shot
HIT_AT = SHOT_AT + 2.85           # Ucilev's round lands after the tower beat
FALL_AT = HIT_AT + 0.30
DOWN_AT = HIT_AT + 1.45
DOORS_AT = SHOT_AT + 11.0         # doors start after the wordless vigil
DEPART_AT = SHOT_AT + 13.6        # train moves at the departure cut
FADE_AT = DEPART_AT + 3.2
# The round lands in slow motion: animation time runs at SLOW_MIN x and eases
# back to real time over SLOW_SPAN seconds, then stays SLOW_LAG behind the
# clock for the rest of the cinematic (the scene is just that much longer).
SLOW_MIN = 0.22
SLOW_SPAN = 0.90
SLOW_LAG = (1.0 - SLOW_MIN) * SLOW_SPAN * 0.5
DURATION = FADE_AT + 1.4 + SLOW_LAG
PLAYER_HP_FLOOR = 0            # Biribel is not immortal: the train can kill him

# Cinematic beats, relative to SHOT_AT.
CINE_TOWER_END = 1.7
CINE_SCOPE_END = 3.30
CINE_IMPACT_END = 5.60
CINE_CATCH_END = 11.0
# Vigil cut points (cine seconds): cigarette, faces, hand, pull-back.
VIG_CIG_AT = 6.4
VIG_FACES_AT = 7.9
VIG_HAND_AT = 9.2
VIG_BACK_AT = 10.0
BIRI_RUN_AT = 1.9      # Biribel breaks cover (off-screen) before the round lands
BIRI_ARRIVE = 3.35     # ...and reaches the body

# The signal tower.  Ucilev kneels on the cabin roof; the SCOPE shot is taken
# from the cabin window.  The eye MUST stay clear of TOWER_CABIN_BOX (the box
# m6world3d.rail_platform builds for the cabin): every box
# face is painter layer 2, so one that comes within a metre of the lens wins
# the sort against the whole scene and paints the frame flat.  With the eye
# inside the cabin that is exactly what the beat rendered - a featureless
# grey disc with no Volkov, no track, nothing.
TOWER_CABIN_BOX = (16.9, 19.1, 7.0, 8.6, 7.5, 9.5)   # x0 x1 y0 y1 z0 z1
TOWER_KNEE = (18.0, 8.62, 8.50)   # where the rig stands (matches _draw_ucilev)
TOWER_EYE = (17.95, 8.05, 7.16)   # at the window: in front of the cabin (-z)

# Local lights per frame.  The GL shader holds eight slots (``u_pl_pos[8]``)
# but uploads only ``Renderer.light_cap`` of them, default four; the train opts
# in to all eight in ``_renderer``.  Every rig in ``_light`` stays inside this
# budget so both backends render the same frame.
LIGHT_CAP = 8

# ── background / horizon ─────────────────────────────────────────────────
# The distance fog (11,15,24) and the night backdrop are the SAME colour at
# the horizon, so far geometry is lerped toward the sky it is supposed to
# stand against.  The old yard albedo (21,24,31) came out of the bake light
# at (11,12,16) - the fog colour exactly - and the background sat on screen
# at 0.3-1.2 luma of contrast: drawn every frame, visible in none of them.
# (tools/m6_bg_contrast.py prints the numbers for both cameras.)
#
# Three knobs, in order of effect:
SKY_HORIZON = (24, 31, 50)     # night() bot: light pollution under the stars
BG_FOG_END = 220.0             # was 120: at 120 a 55 m mass is 44% sky colour
YARD_DARK = (4, 6, 10)         # albedo of the NEAREST far-yard mass
YARD_HAZY = (13, 17, 26)       # ...and of the farthest: aerial perspective
                               # lives in the albedo, not in the fog.

# x, z, w, h, d, window rows, window columns.  Authored inside the yaw the
# player can actually reach - BASE_YAW +- YAW_LIMIT behind a 100 deg
# horizontal lens is yaw -17..153 - because four of the seven old masses sat
# at yaw -21..-42, i.e. behind his left shoulder, and could never be seen.
# The three west masses are kept for the post-shot cinematic, whose impact
# and catch beats look back across the track.
_YARD_MASSES = (
    (-20.0, -31.0, 11.0, 9.0, 7.0, 2, 4),
    (-6.0, -35.0, 9.0, 12.5, 6.0, 3, 3),
    (7.5, -32.0, 13.0, 8.0, 7.0, 2, 5),
    (20.0, -29.5, 9.5, 10.5, 6.0, 3, 3),
    (31.0, -24.0, 10.0, 7.5, 6.0, 2, 4),
    (41.0, -17.0, 8.5, 11.0, 5.5, 3, 3),
    (47.0, -5.0, 7.0, 8.0, 5.0, 2, 3),
    (50.0, 3.0, 9.0, 9.5, 6.0, 2, 3),
    (42.0, 13.0, 8.0, 9.0, 6.0, 2, 3),
    (-33.0, -22.0, 12.0, 7.0, 7.0, 2, 4),
    (-43.0, -28.0, 9.0, 10.0, 6.0, 3, 3),
)
_YARD_STACKS = ((-29.0, -20.0, 15.0), (36.0, -26.0, 13.0), (3.0, -40.0, 17.0))
_YARD_HAZE = ((-14.0, 5.0, -30.0), (10.0, 5.0, -30.0), (34.0, 5.0, -22.0))
_YARD_RIDGE_R = 70.0           # radius of the horizon ridge, around the eye

PLAYER_POS = (-13.0, 0.58, 6.8)
PLAYER_EYE = 1.66
BASE_YAW = 68.0
BASE_PITCH = -3.0
YAW_LIMIT = 35.0
PITCH_LIMIT = 25.0

FIRE_INTERVAL = 0.095
RELOAD_TIME = 2.0
RELOAD_TACTICAL = 1.45
RELOAD_EMPTY = 1.90
RELOADTACTICAL = RELOAD_TACTICAL
RELOADEMPTY = RELOAD_EMPTY
RMAG_OUT = 0.22
RMAG_IN = 0.58
RMAGOUT = RMAG_OUT
RMAGIN = RMAG_IN
HIT_DAMAGE = 34
GUARD_HP = 60
TRAIN_DOOR_X = 10.9

# Volkov's run: (seconds, x, z).  He leaves cover, moves along the platform,
# drops off the edge toward the carriage and is hit before the step.
_V_KEYS = (
    (0.0, -9.9, 6.9),
    (2.0, -9.9, 6.9),
    (2.7, -9.3, 6.9),
    (5.6, -4.6, 6.9),
    (6.3, -4.6, 6.9),
    (7.8, -3.6, 6.9),
    (11.5, 1.6, 6.9),
    (12.2, 1.6, 6.9),
    (13.8, 3.8, 6.9),
    (16.7, 8.0, 6.9),
    (17.4, 8.0, 6.9),
    (18.5, 10.0, 6.9),
    (19.6, 11.4, 6.9),
    (21.2, 11.4, 4.5),
    (22.2, 11.4, 3.1),
    (SHOT_AT, 11.2, 1.05),
    (SHOT_AT + 1.5, 11.18, 0.88),   # approaching the step
    (HIT_AT, 11.15, 0.75),
    (FALL_AT, 11.05, 0.62),
    (DOWN_AT, 11.0, 0.55),
)

# The platform attack: five archetypes with different silhouettes, weapons,
# fire discipline and movement.  A Guard walks his ``advance`` waypoints once
# the listed time arrives (front lane behind the crates, or the back wall
# lane), so a player who ignores them ends up with the squad on top of the
# train step.  ``reserve`` slots only come in when the player has already
# cleared the platform, so the last run is never six seconds of empty snow.
_GUARD_KINDS = {
    "rifle": dict(hp=60, rifle="rifle", burst=3, gap=0.10, damage=4,
                  speed=0.90, telegraph=0.30, flinch=1.0,
                  idle="cover", move="crouch", label="LINE",
                  lamp=(190, 54, 42)),
    "rusher": dict(hp=46, rifle="os12", burst=4, gap=0.07, damage=3,
                   speed=2.10, telegraph=0.18, flinch=1.2,
                   idle="crouch", move="run", label="BREACHER",
                   lamp=(226, 142, 48)),
    "marksman": dict(hp=54, rifle="sniper", burst=1, gap=0.0, damage=11,
                     speed=0.0, telegraph=0.85, flinch=0.8,
                     idle="kneel", move="kneel", label="MARKSMAN",
                     lamp=(160, 200, 226)),
    "heavy": dict(hp=155, rifle="rifle", burst=2, gap=0.15, damage=9,
                  speed=0.55, telegraph=0.48, flinch=0.45,
                  idle="stand", move="stand", label="HEAVY",
                  lamp=(220, 50, 38)),
    "officer": dict(hp=68, rifle="os12", burst=3, gap=0.09, damage=5,
                    speed=1.00, telegraph=0.28, flinch=1.0,
                    idle="cover", move="run", label="OFFICER",
                    lamp=(224, 190, 96)),
}
_GUARD_SLOTS = (
    {"kind": "rifle", "pos": (3.5, 0.58, 3.2), "spawn": 3.6,
     "fire": (5.6, 9.4, 14.6, 20.0),
     "advance": ((9.0, 2.4, 3.25),)},
    {"kind": "marksman", "pos": (9.8, 1.46, 4.1), "spawn": 5.5,
     "fire": (7.9, 15.9, 21.8)},
    {"kind": "rusher", "pos": (14.5, 0.58, 3.3), "spawn": 7.5,
     "fire": (8.8, 12.0, 15.4, 20.0),
     "advance": ((8.4, 11.0, 3.3), (10.0, 7.4, 3.5), (11.6, 3.2, 3.4))},
    {"kind": "heavy", "pos": (17.5, 0.58, 4.2), "spawn": 9.5,
     "fire": (10.9, 14.1, 20.5),
     "advance": ((10.2, 13.2, 4.0), (12.8, 9.2, 5.1))},
    # Left flank stays, but out at ~12 m instead of appearing in the player's
    # lap: the old -10/3.2 and -2/6.8 spawns were 4-11 m away.
    {"kind": "officer", "pos": (-2.0, 0.58, 2.2), "spawn": 11.8,
     "fire": (13.2, 16.0, 19.4),
     "advance": ((13.8, -1.6, 4.4),)},
    {"kind": "rifle", "pos": (-1.0, 0.58, 2.4), "spawn": 14.2,
     "fire": (16.0, 19.6, 21.6),
     "advance": ((16.0, -7.0, 3.4),)},
    {"kind": "rusher", "pos": (16.0, 0.58, 6.6), "spawn": 16.6,
     "fire": (19.0, 21.9),
     "advance": ((18.4, 12.0, 4.6), (20.0, 8.0, 4.2))},
    {"kind": "officer", "pos": (6.5, 0.58, 7.4), "spawn": 18.8,
     "fire": (20.6, 22.4)},
)
MAX_LIVING = 4

# Suppression: two or more living Guards on the platform pin Volkov.  Every
# pinned second costs him up to VOLKOV_DELAY_MAX of his run; if the squad is
# still up when the signal shot comes, the wound is theirs, not Ucilev's.
VOLKOV_PIN_THREAT = 2
VOLKOV_DELAY_MAX = 0.70
VOLKOV_DELAY_RATE = 0.55
RESERVE_CUTOFF = 14.0       # no "last push" once the run is nearly over
_GUARD_DAMAGE = 6


def _guard_profile(kind):
    return _GUARD_KINDS.get(kind, _GUARD_KINDS["rifle"])


def _make_guard(slot, spec):
    kind = spec.get("kind", "rifle")
    prof = _guard_profile(kind)
    return {
        "slot": slot, "kind": kind,
        "pos": tuple(spec["pos"]), "home": tuple(spec["pos"]),
        "spawn": float(spec["spawn"]), "hp": prof["hp"], "max_hp": prof["hp"],
        "alive": False, "active": False, "dead_t": -9.0, "flinch": 0.0,
        "yaw": 0.0, "spawn_t": -9.0,
        "fire": tuple(spec.get("fire", ())), "next_fire": 0,
        "path": tuple(spec.get("advance", ())), "wp": 0,
        "reserve": bool(spec.get("reserve", False)),
        "burst_left": 0, "burst_next": 0.0, "last_shot_t": -9.0,
        "burst_damage": prof["damage"], "moving": False,
    }

# Crates/cover: (cx, cz, half_w, half_d, top).  Used for drawing and for the
# hitscan blocker test (a shot that hits a crate never reaches a Guard).
_CRATES = (
    (-8.6, 5.9, 0.85, 0.55, 1.52),
    (-3.4, 5.1, 0.75, 0.50, 1.46),
    (1.2, 4.9, 0.80, 0.50, 1.50),
    (6.2, 4.6, 0.80, 0.50, 1.54),
    (9.8, 4.1, 0.55, 0.50, 1.42),
)
_SLOT_GROUND = 0.58
_BALLAST_Y = 0.06          # top of the track bed (m6world3d.rail_platform)
_ROOF_TOP = 2.40


def _ground_at(z):
    """Floor height for an actor at track depth ``z``.

    The platform lip is a real 0.52 m drop at z=2.7; the old ramp returned 0
    on the ballast, which buried every body 6 cm into the track bed.
    """
    return _BALLAST_Y + (_SLOT_GROUND - _BALLAST_Y) * _smooth(1.2, 2.95, z)

# Volkov only, and only his two coffee lines: no callouts and no pin line in
# this run by design.  Vasile is off the net as well - his only M6 dialogue is
# the confession call in the ending film (mission6_ending_shots).
_LINES = (
    (2.6, 5.6, "VOLKOV", "Kim Kim has terrible coffee, I hear."),
    (5.8, 9.4, "VOLKOV", "I'm going to drink all of it."),
)

_cache = {"r": None, "hum": {}, "err": None}
_radio_ui = None


def _radio_widget():
    """Local RadioTransmission so the train scene never pollutes the global log."""
    global _radio_ui
    if _radio_ui is None:
        from ui.radio import RadioTransmission
        _radio_ui = RadioTransmission()
    return _radio_ui


def _anim_t(t):
    """Cinematic animation time for clock ``t``: real time up to the hit, then
    a C1 slow-motion ramp (see SLOW_MIN) that ends SLOW_LAG behind the clock."""
    d = t - HIT_AT
    if d <= 0.0:
        return t
    if d >= SLOW_SPAN:
        return t - SLOW_LAG
    x = d / SLOW_SPAN
    return HIT_AT + SLOW_MIN * d + (1.0 - SLOW_MIN) * SLOW_SPAN * (x ** 3 - 0.5 * x ** 4)


def _smooth(a, b, x):
    x = clamp((x - a) / float(b - a), 0.0, 1.0)
    return x * x * (3 - 2 * x)


def _ease(u):
    u = clamp(u, 0.0, 1.0)
    return 1 - (1 - u) ** 3


def _grade_cine(surface):
    """Cinematic contrast/saturation grade on the internal render buffer.

    The old held rig + scanlines read grey because four warm-white sources
    met a 0.5 ambient; this puts the colour back without lifting shadows the
    way m6world3d.grade's gamma does.  Numpy is optional: skip cleanly.
    """
    try:
        import numpy as np
    except Exception:
        return
    lut = _cache.get("grade_lut")
    if lut is None:
        x = np.arange(256, dtype=np.float32) / 255.0
        # open the mids a little (the albedo-modulated rigs are dark by design),
        # crush the toe (true blacks), then an S of contrast around the mids
        x = x ** 0.74
        x = np.clip((x - 0.05) / 0.95, 0.0, 1.0)
        x = np.clip(0.42 + (x - 0.42) * 1.12, 0.0, 1.0)
        sh, hi = (1.0 - x) ** 2, x ** 2
        # split tone: shadows go blue-black, only the highlights stay warm
        chan = (x - 0.010 * sh + 0.030 * hi,
                x + 0.004 * sh + 0.004 * hi,
                x + 0.026 * sh - 0.026 * hi)
        lut = np.empty((3, 256), dtype=np.uint8)
        for i, v in enumerate(chan):
            v = v - 0.10 * np.maximum(0.0, v - 0.86) ** 2
            lut[i] = np.clip(v * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
        _cache["grade_lut"] = lut
    arr = pygame.surfarray.pixels3d(surface)
    # Three vectorised channel lookups: contrast + warm/cool split tone.  The
    # float luma/saturation pass cost ~40 ms on the 800x560 buffer; this keeps
    # the grade cheap enough for the live scene on both backends.
    for i in range(3):
        arr[..., i] = lut[i][arr[..., i]]
    del arr


def _grade_play(surface, wounded=False):
    """Gameplay grade on the internal buffer: a deeper toe, cool shadows and a
    sodium-warm highlight, as a per-channel LUT like ``_grade_cine`` (never a
    float pass).  Wounded desaturates a little through the same table."""
    try:
        import numpy as np
    except Exception:
        return
    key = "grade_play_lut_w" if wounded else "grade_play_lut"
    lut = _cache.get(key)
    if lut is None:
        x = np.arange(256, dtype=np.float32) / 255.0
        x = np.clip((x - 0.018) / 0.982, 0.0, 1.0)
        x = np.clip(0.45 + (x - 0.45) * 1.07, 0.0, 1.0)
        sh, hi = (1.0 - x) ** 2, x ** 2
        chan = [x - 0.008 * sh + 0.022 * hi,
                x + 0.003 * sh + 0.004 * hi,
                x + 0.024 * sh - 0.020 * hi]
        if wounded:
            mean = (chan[0] + chan[1] + chan[2]) / 3.0
            chan = [c * 0.72 + mean * 0.28 for c in chan]
        lut = np.empty((3, 256), dtype=np.uint8)
        for i, v in enumerate(chan):
            lut[i] = np.clip(v * 255.0 + 0.5, 0.0, 255.0).astype(np.uint8)
        _cache[key] = lut
    arr = pygame.surfarray.pixels3d(surface)
    for i in range(3):
        arr[..., i] = lut[i][arr[..., i]]
    del arr


def _dist2(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def _vdist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


# ── 3D plumbing ──────────────────────────────────────────────────────────
def _renderer():
    if _cache["r"] is None:
        _cache["r"] = Renderer(RW, RH, fog=(11, 15, 24), fog_start=16.0,
                               fog_end=BG_FOG_END)
        _cache["r"].light_cap = LIGHT_CAP
    return _cache["r"]


def _hum(key, wound=0, bloody=False, flags=()):
    """The train's HD rig for ``key`` (optionally a wound stage / bloody gloves).

    Same skeleton as the film rigs, so joints and ground contact agree with
    what is drawn; the detailed geometry is train-only."""
    ck = (key, int(wound), bool(bloody), tuple(flags))
    h = _cache["hum"].get(ck)
    if h is None:
        h = _w.hum(key, True, wound, bloody, flags)
        _cache["hum"][ck] = h
    return h


# Contact shadows for actors standing on the platform slab (painter layer 2):
# the default layer-0 disc is hidden by the slab, so queue it on the slab's own
# layer, nudged behind the actor's feet.
_PLAT_SHADOW = (2, -0.30)


def _shadow_for(z):
    return _PLAT_SHADOW if z >= 2.7 else None


def _volkov_flags(d):
    """Rig variants over the vigil: the cigarette drops, then the print."""
    if d >= _PRINT_D:
        return ("cig_dropped", "handprint")
    if d >= _CIG_D:
        return ("cig_dropped",)
    return ()


def _wound_stage(d):
    """Volkov's chest wound ``d`` seconds after the hit: 0 none, 1-3 spreading."""
    if d < 0.0:
        return 0
    if d < _DEATH_D:
        return 1
    return 2 if d < 3.6 else 3


def _blood_spray(seed, age_ms, ang=math.pi * 0.92, n=38, dur_ms=950):
    """Exit spray: ballistic droplets thrown from the anchor, a few long fast
    streaks and many short ones, fading as they fall.  Screen space like
    ``_fx.sparks`` (depth-scaled), deterministic per seed."""
    parts = []
    for i in range(n):
        h = math.sin(seed * 12.9898 + i * 78.233) * 43758.5453
        u = h - math.floor(h)
        h2 = math.sin(seed * 4.1414 + i * 39.346) * 24634.6345
        v = h2 - math.floor(h2)
        parts.append((ang + (u - 0.5) * 1.15, 1.2 + 4.6 * v * v, 1 + int(v * 2.4)))

    def draw(s, sx, sy, scale, z):
        if age_ms < 0 or age_ms > dur_ms:
            return
        a = age_ms / 1000.0
        fade = 1.0 - age_ms / dur_ms
        for an, sp, w in parts:
            vx, vy = math.cos(an) * sp, math.sin(an) * sp - 0.8
            x = sx + vx * a * scale
            y = sy + (vy * a + 4.9 * a * a) * scale
            tx, ty = x - vx * 0.035 * scale, y - (vy + 9.8 * a) * 0.035 * scale
            col = (int(150 * fade + 40), int(14 * fade), int(18 * fade))
            pygame.draw.line(s, col, (tx, ty), (x, y), w)
    return draw


def _drip(i, k):
    """Deterministic 0..1 hash for the spatter layout."""
    h = math.sin(i * 12.9898 + k * 78.233) * 43758.5453
    return h - math.floor(h)


def _trail_points(delay):
    """Where the chest-drag smear lands: the root path while he is lowered."""
    key = ("trail", round(delay, 3))
    pts = _cache.get(key)
    if pts is None:
        pts = []
        d = 0.35
        while d <= _DEATH_D + 1e-6:
            pos, _pose, _yaw, j = _volkov_death_state(HIT_AT + d, delay)
            pts.append((d, j["chest"][0], j["chest"][2]))
            d += 0.12
        _cache[key] = pts
    return pts


# ── world impacts, brass, guard death tracks ─────────────────────────────
_TRAIN_FACE_Z = -2.83      # the carriage side plane the platform fire lands on
_DECAL_CAP = 48
_BRASS_CAP = 40
_BRASS = (200, 160, 72)
_DECAL_COL = {"wood": (22, 15, 10), "snow": (30, 33, 40),
              "metal": (10, 10, 12), "flesh": (70, 8, 12)}


def _world_hit(eye, fwd, tmax=90.0):
    """First world surface along the ray -> (t, kind, normal) or None.

    Crates (wood), the platform top and the ballast bed (snow), and the carriage
    side (metal).  Misses used to spark 40 m out in mid-air; now they land."""
    best = [None]

    def take(t, kind, n):
        if 0.05 < t < tmax and (best[0] is None or t < best[0][0]):
            best[0] = (t, kind, n)

    for cx, cz, hw, hd, top in _CRATES:
        lo = (cx - hw, _SLOT_GROUND, cz - hd)
        hi = (cx + hw, top, cz + hd)
        t = _ray_aabb(eye, fwd, lo, hi)
        if t is None:
            continue
        p = (eye[0] + fwd[0] * t, eye[1] + fwd[1] * t, eye[2] + fwd[2] * t)
        c = ((lo[0] + hi[0]) * 0.5, (lo[1] + hi[1]) * 0.5, (lo[2] + hi[2]) * 0.5)
        h = ((hi[0] - lo[0]) * 0.5, (hi[1] - lo[1]) * 0.5, (hi[2] - lo[2]) * 0.5)
        off = [(p[i] - c[i]) / max(h[i], 1e-6) for i in range(3)]
        ax = max(range(3), key=lambda i: abs(off[i]))
        n = [0.0, 0.0, 0.0]
        n[ax] = 1.0 if off[ax] > 0 else -1.0
        take(t, "wood", tuple(n))
    if fwd[1] < -1e-4:
        t = (_SLOT_GROUND - eye[1]) / fwd[1]
        if eye[2] + fwd[2] * t >= 2.7:
            take(t, "snow", (0.0, 1.0, 0.0))
        else:
            take((_BALLAST_Y - eye[1]) / fwd[1], "snow", (0.0, 1.0, 0.0))
    if fwd[2] < -1e-4:
        t = (_TRAIN_FACE_Z - eye[2]) / fwd[2]
        if 0.05 < eye[1] + fwd[1] * t < 3.4:
            take(t, "metal", (0.0, 0.0, 1.0))
    return best[0]


def _decal_mesh(pos, n, kind, size=0.05):
    """A bullet scar: a thin dark quad 3 mm off the surface it hit."""
    col = _DECAL_COL.get(kind, (14, 14, 16))
    off = 0.004
    if n[1] > 0.5:
        return disc_xz(pos[0], pos[2], size, pos[1] + off, col, n=7,
                       layer=3 if pos[1] > 0.3 else 1)
    if abs(n[2]) >= abs(n[0]):
        return box(size * 1.6, size * 1.6, 0.004, col,
                   center=(pos[0], pos[1], pos[2] + n[2] * off))
    return box(0.004, size * 1.6, size * 1.6, col,
               center=(pos[0] + n[0] * off, pos[1], pos[2]))


def _brass_pos(b, t):
    """Ballistic casing with one bounce on the platform -> (pos, airborne)."""
    t0, p0, v, seed = b
    a = max(0.0, t - t0)
    g0 = _SLOT_GROUND + 0.012
    a1 = (v[1] + math.sqrt(max(0.0, v[1] * v[1] + 19.6 * (p0[1] - g0)))) / 9.8
    if a < a1:
        return ((p0[0] + v[0] * a, p0[1] + v[1] * a - 4.9 * a * a,
                 p0[2] + v[2] * a), True)
    vy1 = (9.8 * a1 - v[1]) * 0.30
    a2 = 2.0 * vy1 / 9.8
    bt = a - a1
    y = g0 + (vy1 * bt - 4.9 * bt * bt if bt < a2 else 0.0)
    roll = min(bt, a2 + 0.35) * 0.35
    return ((p0[0] + v[0] * (a1 + roll), y, p0[2] + v[2] * (a1 + roll)),
            bt < a2)


# Guard death tracks: continuous keyed falls on the same footing as the
# Volkov death.  0 crumple, 1 backward fall (headshots), 2 spin-twist fall.
_G_STAGGER = dict(POSES["aim"], spine=-14, head_p=-12, lsh_p=96, lsh_r=26, lel=18,
                  rsh_p=90, rsh_r=40, rel=24, lhip_p=-4, lkn=14, rhip_p=6, rkn=22)
_G_BUCKLE = dict(POSES["slump"], spine=44, head_p=26, lsh_p=40, lsh_r=18, rsh_p=34,
                 rsh_r=16, rifle_p=60)


def _guard_death_pose(track, a):
    """Pose ``a`` seconds after a guard's last hit, for death track ``track``."""
    aim = POSES["aim"]
    if track == 1:
        if a < 0.22:
            return blend(aim, _G_STAGGER, _smooth(0.0, 0.22, a))
        return blend(_G_STAGGER, POSES["dead_back"], _smooth(0.22, 0.85, a))
    if track == 2:
        if a < 0.30:
            return blend(aim, POSES["slump"], _smooth(0.0, 0.30, a) * 0.5)
        return blend(blend(aim, POSES["slump"], 0.5), POSES["dead_side"],
                     _smooth(0.30, 0.95, a))
    if a < 0.38:
        return blend(aim, _G_BUCKLE, _smooth(0.0, 0.38, a))
    return blend(_G_BUCKLE, POSES["dead_front"], _smooth(0.38, 0.95, a))


def _floor_at(x, z):
    """Height a body lands on at (x, z): a crate top, else platform/ballast."""
    for cx, cz, hw, hd, top in _CRATES:
        if abs(x - cx) <= hw and abs(z - cz) <= hd:
            return top + 0.04
    return _ground_at(z)


def _ankles_xz(hum, pose, yaw):
    """Mid-ankle (x, z) relative to the root; skeleton only, no vertex scan."""
    places = hum.placements(pose, rifle_on=False)[0]
    feet = [org for _s, k, _M, org, _g, _fb in places if k == "foot"]
    w = m_apply(rot_y(yaw), (sum(f[0] for f in feet) / len(feet), 0.0,
                             sum(f[2] for f in feet) / len(feet)))
    return (w[0], w[2])


def _guard_landing(hum, track, pos, yaw0):
    """Floor height under the chest once the body has finished falling."""
    fp = _guard_death_pose(track, 1.2)
    fyaw = yaw0 + (75.0 if track == 2 else 0.0)
    ax0, az0 = _ankles_xz(hum, POSES["aim"], yaw0)
    fx, fz = _ankles_xz(hum, fp, fyaw)
    _pl, fj, _r = hum.pose_world(fp, (pos[0] + ax0 - fx, 0.0, pos[2] + az0 - fz),
                                 fyaw, rifle_on=False)
    return _floor_at(fj["chest"][0], fj["chest"][2])


def _guard_body(hum, track, a, pos, yaw0, land=None):
    """(pose, root, yaw, floor) for a guard ``a`` seconds after the kill.

    The rig pitches about the pelvis, so a plain pose blend slides the feet
    back while the body tips: the root is moved to keep the feet where he
    stood.  ``land`` (see _guard_landing) is the floor under the chest at
    rest, so a guard shot off a crate or the platform lip drops instead of
    lying on air.
    """
    pose = _guard_death_pose(track, a)
    yaw = yaw0
    if track == 2:
        yaw = _w.yaw_mix(yaw0, yaw0 + 75.0, _smooth(0.30, 0.95, a))
    ax0, az0 = _ankles_xz(hum, POSES["aim"], yaw0)
    ax, az = _ankles_xz(hum, pose, yaw)
    floor = pos[1]
    if land is not None and abs(land - pos[1]) > 0.05:
        # off the edge once he has tipped past it, accelerating
        k = _smooth(0.30, 0.85, a)
        floor = pos[1] + (land - pos[1]) * k * k
    return pose, (pos[0] + ax0 - ax, floor, pos[2] + az0 - az), yaw, floor


def _spot(pos, target, color, intensity, range_, cone):
    """Aimable local spot: dir points from the lamp toward the target."""
    dx, dy, dz = (target[i] - pos[i] for i in range(3))
    ln = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
    return {"pos": pos, "color": color, "intensity": intensity,
            "range": range_, "kind": "spot",
            "dir": (dx / ln, dy / ln, dz / ln), "cone": cone}


def _light(r, eye=None, fwd=None, t=None, flashes=()):
    """Light rig for the frame.

    Every rig here is authored to exactly ``LIGHT_CAP`` local lights.  The GL
    backend uploads four (``u_pl_pos[4]``) and silently drops the rest, while
    the software painter keeps eight - an over-budget rig looks right in the
    CPU preview and wrong on the player's GPU, which is how the old rig lost
    the viewmodel fill entirely on GL.
    """
    from engine3d import Light
    final = t is not None and t >= CUT_AT
    # The cinematic lights multiply the surface colour instead of adding their
    # own: a near-black coat under a warm spot stays a dark coat that is warm on
    # the lit side, instead of turning the same tan as the skin and the ballast.
    r.light_albedo = bool(final)
    r.light_gain = 2.2 if final else 1.0
    if final:
        # Post-shot cinematic: one rig per beat, each lit by something the
        # audience can already see in frame (the cabin window, the gantry work
        # lamp, the carriage windows) plus a hard cold rim that outlines the
        # silhouettes against the carriage.
        c = t - SHOT_AT
        if c < CINE_TOWER_END:
            # Tower establishing: the cabin window throws warm light up onto
            # the roof, a cold sky fill separates the tower from the night
            # instead of leaving it a black slab.
            r.light = Light(direction=(-0.34, 0.76, -0.38), ambient=0.24,
                            diffuse=0.58, sky=0.16, tint=(0.88, 0.93, 1.10))
            lights = [
                {"pos": (18.0, 7.55, 6.30), "color": (255, 196, 122),
                 "intensity": 1.45, "range": 6.5},
                {"pos": (12.0, 12.5, -1.5), "color": (142, 172, 222),
                 "intensity": 1.1, "range": 26.0},
                {"pos": (15.4, 3.2, 3.4), "color": (120, 150, 200),
                 "intensity": 0.8, "range": 12.0},
                {"pos": (10.9, 1.8, -2.1), "color": (255, 176, 96),
                 "intensity": 0.8, "range": 6.0},
                # beacon red kisses the roof and the sniper's shoulder
                {"pos": (19.0, 8.9, 7.7), "color": (255, 70, 52),
                 "intensity": 0.6, "range": 3.6},
                # cold moon rim from behind the tower
                {"pos": (21.0, 11.0, 12.5), "color": (150, 182, 255),
                 "intensity": 0.9, "range": 12.0},
            ]
        elif c < CINE_SCOPE_END:
            # Down the scope: the gantry work lamp is a real spot on the
            # target, not a 12 m flood that turned the platform floor neutral.
            r.light = Light(direction=(-0.30, 0.75, -0.35), ambient=0.18,
                            diffuse=0.60, sky=0.10, tint=(0.94, 0.96, 1.05))
            lights = [
                _spot((13.0, 5.80, 1.80), (11.25, 1.40, 0.90),
                      (255, 206, 150), 3.1, 10.0, 0.96),
                {"pos": (13.0, 3.20, 5.20), "color": (60, 105, 215),
                 "intensity": 1.0, "range": 9.0},
                {"pos": (10.8, 2.10, -3.30), "color": (255, 190, 120),
                 "intensity": 1.0, "range": 9.5},
                {"pos": (9.0, 5.40, -2.20), "color": (128, 158, 210),
                 "intensity": 1.0, "range": 15.0},
            ]
        else:
            # Impact, catch, lower and the held side vigil.  A less saturated,
            # more frontal warm key models the faces and the coat; two hard
            # cold rims behind the pair draw both silhouettes against the
            # carriage; the open door bounces warm light up from the ballast and
            # the windows spill onto the track.  The shadow side stays blue.
            r.light = Light(direction=(-0.30, 0.75, -0.34), ambient=0.31,
                            diffuse=0.58, sky=0.10, tint=(0.96, 0.98, 1.04))
            key = 1.10 + 0.40 * _smooth(CINE_SCOPE_END, CINE_SCOPE_END + 3.0, c)
            # The rims sit low (about chest height, 2-3 m behind the pair): they
            # catch the bodies from behind and barely graze the ballast, so the
            # floor stays dark and the silhouettes carry the cold edge.
            lights = [
                _spot((9.40, 2.10, 1.90), (11.40, 0.50, 0.60),
                      (255, 214, 172), key, 7.0, 0.82),
                {"pos": (13.80, 1.10, -1.30), "color": (140, 178, 255),
                 "intensity": 1.30, "range": 6.0},
                {"pos": (9.20, 1.10, -1.50), "color": (122, 160, 244),
                 "intensity": 0.95, "range": 5.5},
                {"pos": (10.90, 0.95, -1.70), "color": (255, 170, 105),
                 "intensity": 0.80, "range": 4.6},
                {"pos": (11.40, 0.50, 3.60), "color": (98, 130, 192),
                 "intensity": 0.25, "range": 4.0},
                {"pos": (14.50, 1.50, -2.20), "color": (255, 196, 140),
                 "intensity": 0.45, "range": 4.5},
                {"pos": (7.50, 1.50, -2.20), "color": (255, 196, 140),
                 "intensity": 0.35, "range": 4.5},
            ]
    else:
        # Action: deep night base, warm sodium pools, one cool rim.
        r.light = Light(direction=(-0.46, 0.64, -0.36), ambient=0.36,
                        diffuse=0.62, sky=0.21, tint=(0.90, 0.93, 1.04))
        lights = [
            # Two sodium keys, not three: the third pool landed on top of the
            # other two and the platform lost its shape.
            {"pos": (0.0, 4.2, 7.2), "color": (255, 195, 125),
             "intensity": 1.25, "range": 13.5},
            {"pos": (9.6, 4.2, 7.2), "color": (255, 208, 148),
             "intensity": 1.20, "range": 13.0},
            # Snow-side cold rim: the only thing that gives the Guard a lit
            # edge against a warm platform.
            {"pos": (4.0, 6.8, -5.6), "color": (118, 152, 214),
             "intensity": 0.52, "range": 18.0},
        ]
        if eye is not None and fwd is not None:
            # Weapon fill: the viewmodel sits ~0.8 m from the lens, and with
            # only the scene practicals behind it the receiver went to
            # near-black.  A cool key just over the barrel keeps the metal
            # readable without making it look polished.  The key sits above
            # and slightly left of the aim line (not coaxial): coaxial light
            # hits every face of the gun at the same angle and the viewmodel
            # reads as one flat grey slab.
            rgt = (-fwd[2], 0.0, fwd[0])
            lr = math.sqrt(rgt[0] * rgt[0] + rgt[2] * rgt[2]) or 1.0
            rgt = (rgt[0] / lr, rgt[1] / lr, rgt[2] / lr)
            lights.append({
                "pos": (eye[0] + fwd[0] * 0.34 + rgt[0] * 0.10 + 0.55,
                        eye[1] + 0.72, eye[2] + fwd[2] * 0.34 + rgt[2] * 0.10),
                "color": (204, 212, 226), "intensity": 0.60, "range": 2.2})
    lights.extend(flashes)
    r.set_lights(lights)


# ── first-person K9 ──────────────────────────────────────────────────────
# Built in gun space: +z is the muzzle, +y up, +x to the shooter's right,
# origin at the trigger.  Every part is a box - the point is proportions and
# contrast, not polygon count.  Materials are deliberately lifted off true
# black: the scene light multiplies them down, and a real anodised receiver
# (40,44,50) came out as mud.
VM_MUZZLE_Z = 0.84
_VM = {
    "receiver": (90, 96, 108),
    "upper": (76, 82, 94),
    "rail": (44, 48, 56),
    "guard": (60, 64, 70),
    "slot": (24, 26, 30),
    "barrel": (58, 62, 72),
    "steel": (114, 118, 126),
    "optic": (38, 42, 50),
    "lens": (20, 46, 58),
    "mag": (80, 84, 94),
    "grip": (58, 48, 38),
    "stock": (108, 72, 44),
    "glove": (46, 42, 38),
    "sleeve": (30, 30, 34),
    "mark": (156, 158, 154),
    "brass": (148, 122, 64),
    "dot": (255, 78, 64),
}


def _vm_speckle(x, y, z):
    """Anodised receiver: fine grain plus scattered worn chips."""
    n1 = _vm_noise(x, y, z, 700)
    n2 = _vm_noise(x, y, z, 70)
    k = 0.88 + 0.20 * (n2 - 0.5) + 0.18 * (n1 - 0.5)
    if n1 > 0.94:
        k += 0.30
    return k


def _vm_polymer(x, y, z):
    """Moulded handguard: coarser pebble grain, a touch darker at the ends."""
    n1 = _vm_noise(x, y, z, 420)
    n2 = _vm_noise(x, y, z, 55)
    return 0.78 + 0.26 * (n1 - 0.5) + 0.22 * (n2 - 0.5)


def _vm_grain(x, y, z):
    """Stock grain: long bands down the length, broken by plank variation."""
    band = math.sin(y * 170.0 + x * 40.0 + 1.2 * math.sin(z * 35.0))
    plank = _vm_noise(x * 0.2, y, 0.0, 45)
    fine = _vm_noise(x, y, z, 900)
    return 0.80 + 0.28 * band + 0.22 * (plank - 0.5) + 0.14 * (fine - 0.5)


def _vm_stipple(x, y, z):
    """Pebbled grip texture."""
    return 0.52 + 0.90 * _vm_noise(x, y, z, 900)


def _vm_ribs(x, y, z):
    """Vertical magazine ribs."""
    return 0.55 if int(math.floor((x * 3.0 + z) / 0.013)) % 2 else 1.02


def _vm_bluing(z0, z1):
    """Barrel and brake: darker towards the muzzle, as blued steel reads."""
    def tex(x, y, z):
        t = clamp((z - z0) / (z1 - z0), 0.0, 1.0)
        return 1.0 - 0.55 * t + 0.18 * (_vm_noise(x, y, z, 500) - 0.5)
    return tex


def _vm_noise(x, y, z, s):
    """Deterministic 0..1 hash of a point quantised to 1/s metres."""
    h = (round(x * s) * 374761393 + round(y * s) * 668265263
         + round(z * s) * 2147483647) & 0xFFFFFFFF
    h = ((h ^ (h >> 13)) * 1274126177) & 0xFFFFFFFF
    return ((h ^ (h >> 16)) & 0xFFFF) / 65535.0


def _vm_part(m, w, h, d, col, center, rx=0.0, em=False, seg=None, tex=None,
             skip=(), cols=None):
    """One box in gun space, optionally pitched about the trigger.

    ``tex(x, y, z)`` returns a brightness multiplier for each face, sampled at
    the face centre in gun space; ``seg`` subdivides the box so the pattern
    has cells to vary across.  ``cols`` overrides sides (top/bottom/...).
    The GL path has no UVs, so texture is per-face colour.
    """
    part = box(w, h, d, col, center=(0.0, 0.0, 0.0), cols=cols, emissive=em,
               seg=seg, skip=skip)
    if tex is not None:
        faces = []
        for idx, c, layer, ds, e in part.faces:
            n = len(idx)
            x = sum(part.verts[i][0] for i in idx) / n
            y = sum(part.verts[i][1] for i in idx) / n
            z = sum(part.verts[i][2] for i in idx) / n
            k = tex(x, y, z)
            faces.append((idx, tuple(min(255, int(v * k)) for v in c),
                          layer, ds, e))
        part.faces = faces
    if rx:
        m.add(part, rot_x(rx), center)
    else:
        m.add(part, t=center)


def _vm_asset_hands(m):
    """Glove/sleeve blocks that hold the imported K93D (gun-space)."""
    P, C = _vm_part, _VM
    # right hand on the pistol grip, wrist behind it
    P(m, 0.075, 0.065, 0.080, C["glove"], (0.012, -0.100, -0.105))
    for i in range(3):
        P(m, 0.064, 0.014, 0.020, C["glove"],
          (0.008, -0.078 - i * 0.022, -0.145))
    P(m, 0.020, 0.015, 0.050, C["glove"], (0.035, -0.070, -0.115))
    P(m, 0.090, 0.090, 0.14, C["sleeve"], (0.035, -0.180, -0.245))
    # left hand on the angled foregrip: the palm must sit on the AFG above the
    # magazine.  The old placement put it (and the sleeve) on the mag body,
    # where it read as a square block stuck to the magazine.
    P(m, 0.070, 0.055, 0.080, C["glove"], (-0.006, 0.035, 0.195))
    for i in range(3):
        P(m, 0.014, 0.026, 0.016, C["glove"],
          (-0.036, 0.052, 0.172 + i * 0.028))
    P(m, 0.018, 0.014, 0.050, C["glove"], (0.020, 0.055, 0.195))
    P(m, 0.080, 0.080, 0.13, C["sleeve"], (-0.050, -0.075, 0.020))


_VM_ASSET = None
_RETICLE = None


def _reticle_image():
    """The K93D's projected holographic reticle (assets/3D, keyed to alpha).

    Falls back to a drawn ring/dot so a missing derived PNG still leaves the
    optic usable instead of showing an empty housing.
    """
    global _RETICLE
    if _RETICLE is not None:
        return _RETICLE
    path = resource_path(os.path.join("assets", "3D", "K93D_reticle.png"))
    try:
        img = load_image(path)   # D5: the single raw-load chokepoint (engine.assets)
        try:
            img = img.convert_alpha()
        except Exception:
            pass
    except Exception:
        img = pygame.Surface((128, 128), pygame.SRCALPHA)
        pygame.draw.circle(img, (70, 240, 200), (64, 64), 34, 3)
        pygame.draw.circle(img, (170, 255, 230), (64, 64), 4)
        for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
            pygame.draw.line(img, (70, 240, 200),
                             (64 + dx * 30, 64 + dy * 30),
                             (64 + dx * 40, 64 + dy * 40), 3)
    _RETICLE = img
    return img


def _viewmodel_asset():
    """First authored 3D weapon asset (tools/ae_import_k93d.py).

    Returns (mesh, sight, muzzle, mag_shift) in gun space, or None when the
    content is missing (the procedural K9 stays the fallback).  The sight and
    muzzle points come from the GLB nodes, not hand-tuned offsets.
    """
    global _VM_ASSET
    if _VM_ASSET is False:
        return None
    if _VM_ASSET is not None:
        return _VM_ASSET
    import json

    from engine3d.core import Mesh
    from game.render3d_bridge import MESHES_DIR

    path = os.path.join(MESHES_DIR, "k93d.mesh.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError:
        _VM_ASSET = False
        return None
    if data.get("schema") != "ae.mesh/1":
        raise ValueError("%s: schema must be ae.mesh/1" % path)
    raw_faces = data["faces"]
    m = Mesh()
    m.verts = [tuple(float(c) for c in v) for v in data["verts"]]
    m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in raw_faces]
    meta = data.get("meta", {})
    sight = tuple(float(c) for c in meta.get("sight", (0.0, 0.181, 0.001)))
    muzzle = tuple(float(c) for c in meta.get("muzzle", (0.0, 0.083, 0.595)))
    glass_size = tuple(float(c) for c in meta.get("glass_size", (0.035, 0.041)))
    _vm_asset_hands(m)
    mag_shift = [0.0] * len(m.verts)
    for fi in meta.get("mag_faces", ()):
        if 0 <= fi < len(raw_faces):
            for vi in raw_faces[fi][0]:
                if 0 <= vi < len(mag_shift):
                    mag_shift[vi] = 1.0
    _VM_ASSET = (m, sight, muzzle, mag_shift, glass_size, _reticle_image())
    return _VM_ASSET


_VM_CACHE = {}


def _vm_mesh(reloading=False, p=1.0):
    """The K9 as it is held: receiver, optic, handguard, mag, hands, sleeves.

    Face-level patterns are static, so the built mesh is cached: normal play
    reuses one mesh, and only reload frames (mag drop) rebuild it.
    """
    key = (bool(reloading), round(p, 2) if reloading else 1.0)
    cached = _VM_CACHE.get(key)
    if cached is not None:
        return cached
    from engine3d.core import Mesh
    m = Mesh()
    P = _vm_part
    C = _VM
    # Side/top overrides give each slab a readable form: dust-cover and rail
    # tops catch the fill light, undersides stay dark.
    metal_sides = {"top": (108, 114, 124), "bottom": (62, 66, 74)}
    poly_sides = {"top": (78, 82, 88), "bottom": (48, 50, 54)}
    wood_sides = {"top": (112, 78, 50), "bottom": (64, 44, 30)}
    # ── receiver ──
    P(m, 0.070, 0.095, 0.30, C["receiver"], (0.0, -0.010, 0.10),
      seg=0.025, tex=_vm_speckle, cols=metal_sides, skip=("bottom",))
    # side plate seam + panel screws (both sides, the camera sees the left)
    for sy in (-1.0, 1.0):
        P(m, 0.003, 0.006, 0.24, C["slot"], (sy * 0.037, -0.045, 0.08))
        for zz in (0.015, 0.19):
            P(m, 0.004, 0.009, 0.009, C["steel"], (sy * 0.037, 0.005, zz))
    # stamped marking on the near side
    for i in range(3):
        P(m, 0.002, 0.007, 0.005, C["mark"],
          (-0.037, -0.012, 0.055 + i * 0.011))
    P(m, 0.064, 0.055, 0.32, C["upper"], (0.0, 0.055, 0.11),
      seg=0.035, tex=_vm_speckle, cols=metal_sides, skip=("bottom",))
    P(m, 0.040, 0.016, 0.34, C["rail"], (0.0, 0.090, 0.11))
    for i in range(7):
        P(m, 0.036, 0.010, 0.008, C["steel"], (0.0, 0.101, -0.045 + i * 0.052))
    # dust-cover ribs (short cross ribs down both flanks)
    for i in range(4):
        for sy in (-1.0, 1.0):
            P(m, 0.003, 0.008, 0.010, C["slot"],
              (sy * 0.0325, 0.055, -0.01 + i * 0.058))
    P(m, 0.006, 0.028, 0.075, C["slot"], (0.036, 0.045, 0.10))     # ejection port
    P(m, 0.010, 0.012, 0.055, C["rail"], (0.040, 0.075, 0.02))     # charging handle
    # ── handguard ──
    P(m, 0.062, 0.078, 0.30, C["guard"], (0.0, 0.030, 0.40),
      seg=0.025, tex=_vm_polymer, cols=poly_sides,
      skip=("bottom", "back"))
    P(m, 0.066, 0.082, 0.010, C["steel"], (0.0, 0.030, 0.252))     # end cap
    P(m, 0.066, 0.082, 0.010, C["steel"], (0.0, 0.030, 0.548))     # end cap
    for i in range(4):
        for sx in (-0.033, 0.033):
            P(m, 0.003, 0.018, 0.040, C["slot"], (sx, 0.030, 0.285 + i * 0.075))
    P(m, 0.030, 0.012, 0.20, C["rail"], (0.0, -0.012, 0.40))
    # ── barrel / muzzle ──
    P(m, 0.026, 0.026, 0.24, C["barrel"], (0.0, 0.035, 0.63),
      seg=0.04, tex=_vm_bluing(0.51, 0.75), skip=("front", "back"))
    P(m, 0.032, 0.032, 0.006, C["steel"], (0.0, 0.035, 0.585))
    P(m, 0.032, 0.032, 0.006, C["steel"], (0.0, 0.035, 0.665))
    P(m, 0.036, 0.046, 0.050, C["steel"], (0.0, 0.045, 0.53))      # gas block
    P(m, 0.038, 0.038, 0.075, C["steel"], (0.0, 0.035, 0.795))     # brake
    P(m, 0.008, 0.030, 0.008, C["rail"], (0.0, 0.075, 0.775))      # front post
    # ── optic ──
    P(m, 0.030, 0.020, 0.090, C["rail"], (0.0, 0.105, 0.13))
    P(m, 0.046, 0.050, 0.105, C["optic"], (0.0, 0.135, 0.13))
    P(m, 0.040, 0.044, 0.008, C["lens"], (0.0, 0.135, 0.076))
    P(m, 0.006, 0.006, 0.004, C["dot"], (0.0, 0.135, 0.070), em=True)
    P(m, 0.014, 0.014, 0.020, C["rail"], (0.030, 0.135, 0.13))
    # ── magazine (drops out during a reload) ──
    drop = 0.0
    if reloading:
        drop = 0.22 * _smooth(0.30, 0.62, p) * (1.0 - _smooth(0.62, 0.72, p))
    P(m, 0.048, 0.135, 0.075, C["mag"], (0.0, -0.115 - drop, 0.045), rx=-10.0,
      seg=0.02, tex=_vm_ribs, skip=("top",))
    P(m, 0.052, 0.014, 0.080, C["rail"], (0.0, -0.185 - drop, 0.030))
    # ── grip / trigger ──
    P(m, 0.044, 0.115, 0.070, C["grip"], (0.0, -0.115, -0.115), rx=14.0,
      seg=0.02, tex=_vm_stipple, skip=("top",))
    P(m, 0.048, 0.020, 0.075, C["rail"], (0.0, -0.170, -0.135))
    P(m, 0.026, 0.008, 0.070, C["rail"], (0.0, -0.062, -0.045))
    P(m, 0.008, 0.022, 0.008, C["steel"], (0.0, -0.052, -0.045))
    # ── stock ──
    P(m, 0.040, 0.040, 0.14, C["rail"], (0.0, 0.030, -0.10))
    P(m, 0.048, 0.080, 0.20, C["stock"], (0.0, 0.020, -0.26),
      seg=0.024, tex=_vm_grain, cols=wood_sides, skip=("back",))
    P(m, 0.046, 0.024, 0.13, C["stock"], (0.0, 0.070, -0.27),
      seg=0.03, tex=_vm_grain, cols=wood_sides)
    P(m, 0.050, 0.095, 0.028, C["rail"], (0.0, 0.015, -0.375))     # butt pad
    P(m, 0.012, 0.026, 0.026, C["steel"], (0.0, -0.045, -0.31))    # sling loop
    # ── right hand on the grip ──
    P(m, 0.078, 0.070, 0.080, C["glove"], (0.006, -0.135, -0.115))
    for i in range(3):
        P(m, 0.070, 0.015, 0.020, C["glove"], (0.002, -0.112 - i * 0.024, -0.152))
    P(m, 0.020, 0.016, 0.055, C["glove"], (0.030, -0.098, -0.125))
    P(m, 0.090, 0.090, 0.14, C["sleeve"], (0.030, -0.185, -0.235))
    # ── left hand under the handguard ──
    P(m, 0.080, 0.062, 0.095, C["glove"], (-0.004, -0.022, 0.40))
    for i in range(3):
        P(m, 0.016, 0.045, 0.018, C["glove"], (-0.030, 0.038, 0.36 + i * 0.040))
    P(m, 0.018, 0.014, 0.055, C["glove"], (-0.030, -0.032, 0.36))
    P(m, 0.085, 0.085, 0.16, C["sleeve"], (-0.030, -0.085, 0.30))
    # the viewmodel is always drawn from inside the near plane
    m.faces = [(idx, col, layer, True, em)
               for (idx, col, layer, _ds, em) in m.faces]
    if len(_VM_CACHE) > 48:
        _VM_CACHE.clear()
    _VM_CACHE[key] = m
    return m


def _volkov_at(t, delay=0.0):
    """(pos, mode, running_phase) for the scripted run.

    ``delay`` is the suppression lag: the animation clock stays on the wall
    clock, but his body is at where the run was ``delay`` seconds ago.  A
    pinned player therefore sees him lose the race to the carriage without
    losing the shot timing that the story depends on.
    """
    delay = clamp(float(delay), 0.0, VOLKOV_DELAY_MAX)
    pt = max(0.0, t - delay)
    keys = _V_KEYS
    x0 = x1 = keys[0][1]
    z0 = z1 = keys[0][2]
    u = 0.0
    at_end = True
    if pt <= keys[0][0]:
        x, z = keys[0][1], keys[0][2]
    elif pt >= keys[-1][0]:
        x, z = keys[-1][1], keys[-1][2]
    else:
        at_end = False
        idx = 0
        for i in range(len(keys) - 1):
            if keys[i][0] <= pt <= keys[i + 1][0]:
                idx = i
                break
        t0, x0, z0 = keys[idx]
        t1, x1, z1 = keys[idx + 1]
        u = _smooth(0, 1, (pt - t0) / max(1e-6, t1 - t0))
        x = x0 + (x1 - x0) * u
        z = z0 + (z1 - z0) * u
    ground = _ground_at(z)
    moving = (not at_end) and abs(x1 - x0) + abs(z1 - z0) > 0.4
    if t < 2.0:
        mode = "cover"
    elif t < HIT_AT:
        # brief pauses are authored as duplicate keyframes; a real stop in the
        # path reads as a crouch-and-check rather than a frozen run cycle.
        if at_end:
            stationary, was_move = True, False
        else:
            stationary = (t1 - t0) < 0.65
            was_move = abs(x1 - x0) + abs(z1 - z0) > 0.4
        mode = "run" if (moving and not stationary or was_move and u < 0.92) else "cover"
        if t > SHOT_AT - 0.55:
            mode = "run"
    else:
        mode = "hit"
    if t >= FALL_AT:
        mode = "fall"
    if t >= DOWN_AT:
        mode = "down"
    phase = t * 8.4
    return (x, ground, z), mode, phase


# ── death choreography ───────────────────────────────────────────────────
# One continuous track: recoil -> knees go -> sits back -> supine settle.
# The body only ever tips backward and only ever goes down: the earlier keys
# pitched him forward onto his knees and then back up and over, which read as
# falling one way, then the other.  Everything below is absolute-time driven
# so the camera, Biribel's hands and the probe all read the same body.
_VK_RECOIL = dict(spine=10, spine_r=-4, twist=4, head_p=-14, head_y=-4,
                  lsh_p=6, lsh_r=18, lel=28, rsh_p=18, rsh_r=12, rel=42,
                  lhip_p=20, lkn=40, rhip_p=13, rkn=34, body_p=-3, body_r=-2)
_VK_BUCKLE = dict(spine=30, spine_r=-6, twist=8, head_p=20, head_y=-8,
                  lsh_p=24, lsh_r=26, lel=52, rsh_p=38, rsh_r=20, rel=78,
                  lhip_p=54, lkn=96, rhip_p=32, rkn=76, body_p=-8, body_r=2)
_VK_CONTACT = dict(spine=30, spine_r=4, twist=10, head_p=10, head_y=10,
                   lsh_p=40, lsh_r=36, lel=48, rsh_p=44, rsh_r=24, rel=64,
                   lhip_p=68, lkn=112, rhip_p=44, rkn=96, body_p=-24, body_r=6)
_VK_LOWER = dict(spine=6, head_p=-4, head_y=55,
                 lsh_p=26, lsh_r=50, lel=28, rsh_p=20, rsh_r=44, rel=24,
                 lhip_p=56, lhip_r=12, lkn=96, rhip_p=40, rkn=76,
                 body_p=-52, body_r=6)
# Solved so his back is on the ballast (a bent knee used to prop him 13 cm up).
_VK_SETTLED = dict(body_p=-84, body_r=4, spine=-6, head_p=-14, head_y=85,
                   lsh_p=18, lsh_r=58, lel=18, rsh_p=6, rsh_r=62, rel=12,
                   lhip_p=12, lhip_r=12, lkn=16, rhip_p=10, rhip_r=8, rkn=12)
# The overrun death falls toward the train: a forward drop, not the catch.
_VK_FAIL_LOWER = dict(body_p=58, spine=10, head_p=-6, head_y=-10,
                      lsh_p=60, lsh_r=30, lel=30, rsh_p=50, rsh_r=24,
                      rel=34, lhip_p=30, lkn=60, rhip_p=20, rkn=44)
# Face turned aside and arms out of the way so the chest is on the ballast.
_VK_FAILED = dict(body_p=84, body_r=-8, spine=11, head_p=-20, head_y=70,
                  lsh_p=-6, lsh_r=44, lel=36, rsh_p=-2, rsh_r=32, rel=26,
                  lhip_p=-4, lhip_r=6, lkn=8, rhip_p=-2, rhip_r=10, rkn=12)

_DEATH_D = DOWN_AT - HIT_AT
# (seconds after the hit, relative size): the last breath is barely a breath
_BREATHS = ((2.30, 1.0), (3.95, 0.6), (5.60, 0.3))
_CIG_D = 3.10               # the cigarette slips from his lips after breath one
_SPRAY_O = (11.3, 0.8)    # x/z where the exit spray starts on the ballast
_PRINT_D = 6.30             # Biribel lifts his hand: the print stays on the coat
_VSUP_START = 0.55          # hands take the weight
_VSUP_FULL = _DEATH_D       # body is on the ballast


def _keyed_pose(d, t):
    """Canon death pose at ``d`` seconds after the hit."""
    # Freeze the run exactly where the round lands: letting the run cycle keep
    # ticking through the hit threw a 12 deg/frame knee pop on top of the
    # reaction blend.
    run = pose_run(HIT_AT * 8.4, lean=20)
    if d <= 0.0:
        return run
    if d < 0.14:
        return blend(run, _VK_RECOIL, _smooth(0.0, 0.14, d))
    if d < 0.45:
        return blend(_VK_RECOIL, _VK_BUCKLE, _smooth(0.14, 0.45, d))
    if d < 0.70:
        return blend(_VK_BUCKLE, _VK_CONTACT, _smooth(0.45, 0.70, d))
    if d < 1.15:
        return blend(_VK_CONTACT, _VK_LOWER, _smooth(0.70, 1.15, d))
    if d < _DEATH_D:
        return blend(_VK_LOWER, _VK_SETTLED, _smooth(1.15, _DEATH_D, d))
    p = dict(_VK_SETTLED)
    # Wordless: three breaths, each smaller than the last, then nothing.
    for d0, amp in _BREATHS:
        if d0 <= d <= d0 + 0.60:
            k = math.sin((d - d0) / 0.60 * math.pi) * amp
            p["spine"] = p.get("spine", 0.0) + 1.2 * k
            p["head_p"] = p.get("head_p", 0.0) - 1.5 * k
    return p


def _fail_pose(d, t):
    """Overrun death: same recoil/buckle, then a forward fall."""
    # The overrun starts at the signal shot (SHOT_AT), not HIT_AT: freeze the
    # run exactly where the last live frame left it.
    run = pose_run(SHOT_AT * 8.4, lean=20)
    if d <= 0.0:
        return run
    if d < 0.14:
        return blend(run, _VK_RECOIL, _smooth(0.0, 0.14, d))
    if d < 0.45:
        return blend(_VK_RECOIL, _VK_BUCKLE, _smooth(0.14, 0.45, d))
    if d < 0.90:
        return blend(_VK_BUCKLE, _VK_FAIL_LOWER, _smooth(0.45, 0.90, d))
    if d < _DEATH_D:
        return blend(_VK_FAIL_LOWER, _VK_FAILED, _smooth(0.90, _DEATH_D, d))
    return dict(_VK_FAILED)


def _volkov_death_state(t, delay=0.0):
    """(pos, pose, yaw, joints) for the canon death at absolute time ``t``.

    The root drifts onto the ballast and the pose is continuous.  There is
    no support lift: it held the whole body, feet included, off the ground
    while it fell, and Biribel's hands already follow the chest joint.
    """
    d = max(0.0, t - HIT_AT)
    hit, _mode, phase = _volkov_at(HIT_AT, delay)
    ahead, _m, _p = _volkov_at(min(HIT_AT + 0.25, DURATION), delay)
    yaw0 = _w.yaw_to(hit, ahead)
    catch_yaw = _w.yaw_to(hit, (12.0, 0.0, 1.25))
    sup = _smooth(_VSUP_START, _VSUP_FULL, d)
    yaw = _w.yaw_mix(yaw0, catch_yaw, 0.12 * sup)
    x = hit[0] + 0.10 * sup
    z = hit[2] + (0.20 - hit[2]) * sup
    pos = (x, _ground_at(z), z)
    pose = _keyed_pose(d, t)
    _pl, joints, _root = _hum("volkov").pose_world(pose, pos, yaw, rifle_on=False)
    return pos, pose, yaw, joints


def _volkov_fail_state(d, t, fail_pos, fail_yaw, delay=0.0):
    """(pos, pose, yaw, joints) for the overrun death, frozen at fail_pos."""
    ahead, _m, _p = _volkov_at(min(SHOT_AT + 0.25, DURATION), delay)
    run_yaw = _w.yaw_to(fail_pos, ahead)
    yaw = _w.yaw_mix(run_yaw, fail_yaw, _smooth(0.0, 0.35, d))
    pos = (fail_pos[0], _ground_at(fail_pos[2]), fail_pos[2])
    pose = _fail_pose(d, t)
    pose["lift"] = 0.0
    hum = _hum("volkov")
    _pl, joints, _root = hum.pose_world(pose, pos, yaw, rifle_on=False)
    return pos, pose, yaw, joints


def _volkov_pose(mode, phase, t):
    if mode == "cover":
        return dict(POSES["cover"])
    if mode == "run":
        return pose_run(phase, lean=20)
    return _keyed_pose(max(0.0, t - HIT_AT), t)


# ── Biribel's catch ──────────────────────────────────────────────────────
_BIRI_BRACE = dict(POSES["kneel"], spine=34, head_p=18,
                   lsh_p=52, lel=48, rsh_p=44, rel=52)
# Leans well over him: he lies flat on the ballast, not propped up.
_BIRI_HOLD = dict(POSES["kneel"], spine=48, head_p=-30,
                  lhip_p=96, lkn=112, rhip_p=-10, rkn=108,
                  lsh_p=40, lel=45, rsh_p=36, rel=50)


def _look_angles(pos, yaw, target, twist_max=24.0, head_max=46.0, share=0.35):
    rel = (_w.yaw_to(pos, target) - yaw + 180.0) % 360.0 - 180.0
    tw = clamp(rel * share, -twist_max, twist_max)
    return tw, clamp(rel - tw, -head_max, head_max)


def catch_right_target(chest, c):
    """World target of Biribel's right hand ``c`` cine-seconds in: the
    shoulder/chest grip, then pressed on the wound, then lifted away."""
    r_target = (chest[0] + 0.22, chest[1] + 0.08, chest[2] + 0.12)
    press = _smooth(5.2, 5.9, c) * (1.0 - _smooth(_PRINT_D + 2.55 - 0.4,
                                                   _PRINT_D + 2.55 + 0.3, c))
    if press > 0.0:
        wound = (chest[0] + 0.12, chest[1] + 0.13, chest[2] + 0.07)
        r_target = tuple(r_target[i] + (wound[i] - r_target[i]) * press
                         for i in range(3))
    lift = _smooth(_PRINT_D + 2.55 + 0.3, _PRINT_D + 2.55 + 0.9, c)
    if lift > 0.0:
        up = (chest[0] + 0.16, chest[1] + 0.40, chest[2] + 0.14)
        r_target = tuple(r_target[i] + (up[i] - r_target[i]) * lift
                         for i in range(3))
    return r_target


def _biribel_catch_state(t, vstate):
    """Grounded approach, then a side vigil: beside the chest, not the head."""
    c = t - SHOT_AT
    if c < BIRI_RUN_AT:
        return None
    vpos, _vpose, _vyaw, vj = vstate
    hum = _hum(("biribel", OUTFIT_GUARD))
    route = _cache.get("biri_route")
    if route is None:
        # From the carriage side of the lamp, along the platform lip: he is
        # already running when the round lands, not standing beside the body.
        route = _w.path([(16.4, 1.45), (14.7, 1.28), (13.85, 1.18),
                         (12.95, 0.85), (12.45, 0.62)], smooth=0.10)
        _cache["biri_route"] = route
    # A sprint that eases into the kneel: speed falls to zero at the body.
    u = clamp((c - BIRI_RUN_AT) / (BIRI_ARRIVE - BIRI_RUN_AT), 0.0, 1.0)
    dist = route.length * (1.0 - (1.0 - u) ** 1.6)
    (rx, _ry, rz), yaw = route(dist)
    pos = (rx, _ground_at(rz), rz)
    pose = pose_run(dist / 2.1 * 2.0 * math.pi, lean=24 + 10 * u)
    pose["rifle_p"] = 0.0
    if c >= 3.20:
        # settle at his chest, on the near side of the body
        ks = _smooth(3.20, 3.65, c)
        x = pos[0] + (12.20 - pos[0]) * ks
        z = pos[2] + (0.55 - pos[2]) * ks
        pos = (x, _ground_at(z), z)
    if c >= 3.10:
        k = _smooth(3.10, 3.45, c)
        chest_t = (vj["chest"][0], 0.0, vj["chest"][2])
        pose = blend(pose, _BIRI_BRACE, k)
        yaw = _w.yaw_mix(yaw, _w.yaw_to(pos, chest_t), k)
    if c >= 3.55:
        pose = blend(pose, _BIRI_HOLD, _smooth(3.55, 4.35, c))
    pos = (pos[0], _ground_at(pos[2]), pos[2])
    if c >= 3.10:
        k = _smooth(3.10, 3.50, c)
        tw, hy = _look_angles(pos, yaw, vj["head"])
        pose["twist"] = pose.get("twist", 0.0) + tw * k
        pose["head_y"] = pose.get("head_y", 0.0) + hy * k
        # head_p is authored in _BIRI_HOLD; do not pitch from the root
    kr_r = _smooth(3.75, 4.25, c)
    if kr_r > 0.0:
        r_target = catch_right_target(vj["chest"], c)
        pr = _w.reach(hum, pose, "r", r_target, pos, yaw)
        pose = blend(pose, pr, kr_r)
    kr_l = _smooth(4.05, 4.55, c)
    if kr_l > 0.0:
        hand = vj["lhand"]
        l_target = (hand[0] + 0.02, hand[1] + 0.02, hand[2] + 0.04)
        pl = _w.reach(hum, pose, "l", l_target, pos, yaw)
        pose = blend(pose, pl, kr_l)
    look = _smooth(VIG_BACK_AT, VIG_BACK_AT + 0.7, c)
    if look > 0.0:
        # Eyes up to the signal tower: the one thing he does with the silence.
        tw, hy = _look_angles(pos, yaw, TOWER_KNEE, twist_max=20.0,
                              head_max=60.0, share=0.45)
        pose["twist"] = pose.get("twist", 0.0) + tw * look
        pose["head_y"] = pose.get("head_y", 0.0) + (hy - pose.get("head_y", 0.0) * 0.0) * look
        pose["head_p"] = pose.get("head_p", 0.0) - 10.0 * look
    return pos, yaw, pose


def _ray_sphere(origin, d, centre, radius):
    ox, oy, oz = origin[0] - centre[0], origin[1] - centre[1], origin[2] - centre[2]
    b = ox * d[0] + oy * d[1] + oz * d[2]
    c = ox * ox + oy * oy + oz * oz - radius * radius
    disc = b * b - c
    if disc < 0:
        return None
    s = math.sqrt(disc)
    hit = -b - s
    if hit < 0:
        hit = -b + s
    return hit if hit > 0 else None


def _ray_aabb(origin, d, lo, hi):
    tmin, tmax = 0.0, 1e9
    for i in range(3):
        if abs(d[i]) < 1e-9:
            if origin[i] < lo[i] or origin[i] > hi[i]:
                return None
        else:
            inv = 1.0 / d[i]
            t1 = (lo[i] - origin[i]) * inv
            t2 = (hi[i] - origin[i]) * inv
            if t1 > t2:
                t1, t2 = t2, t1
            tmin = max(tmin, t1)
            tmax = min(tmax, t2)
            if tmin > tmax:
                return None
    return tmin if tmax > 0 else None


def _forward(yaw_deg, pitch_deg):
    y = math.radians(yaw_deg)
    p = math.radians(pitch_deg)
    cp = math.cos(p)
    return (math.sin(y) * cp, math.sin(p), -math.cos(y) * cp)


def _right(yaw_deg):
    y = math.radians(yaw_deg)
    return (math.cos(y), 0.0, math.sin(y))


PANEL = (6, 9, 14, 200)
EDGE = (96, 106, 122)
ACCENT = (198, 156, 74)
hudcache = {}

def panel(w, h, accent=None):
    surf = pygame.Surface((w, h), pygame.SRCALPHA)
    surf.fill(PANEL)
    c, L = EDGE, 10
    for x, y, dx, dy in ((0, 0, 1, 1), (w - 1, 0, -1, 1),
                          (0, h - 1, 1, -1), (w - 1, h - 1, -1, -1)):
        pygame.draw.line(surf, c, (x, y), (x + dx * L, y))
        pygame.draw.line(surf, c, (x, y), (x, y + dy * L))
    if accent:
        pygame.draw.rect(surf, accent, (0, 6, 3, h - 12))
    return surf

def hurtvignette():
    """Pre-rendered radial red-black vignette (one gradient, cached)."""
    v = hudcache.get("hurt")
    if v is None:
        v = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        try:
            import numpy as np
            ys, xs = np.mgrid[0:HEIGHT, 0:WIDTH].astype(np.float32)
            nx = (xs - WIDTH * 0.5) / (WIDTH * 0.5)
            ny = (ys - HEIGHT * 0.5) / (HEIGHT * 0.5)
            rr = np.sqrt(nx * nx * 0.80 + ny * ny * 1.05)
            a = np.clip((rr - 0.42) / 0.78, 0.0, 1.0) ** 1.7
            rgb = pygame.surfarray.pixels3d(v)
            rgb[..., 0] = 128
            rgb[..., 1] = 10
            rgb[..., 2] = 12
            del rgb
            al = pygame.surfarray.pixels_alpha(v)
            al[:] = (a.T * 205.0).astype(np.uint8)
            del al
        except Exception:
            steps = 24
            for i in range(steps):
                al = int(110 * (1 - i / float(steps)))
                pygame.draw.rect(v, (150, 18, 18, al),
                                 (i * 4, i * 4, WIDTH - i * 8, HEIGHT - i * 8), 4)
        hudcache["hurt"] = v
    return v


class TrainScene:
    """Singleton scene state (one process-wide instance, see module API)."""

    def __init__(self):
        self.started = False
        self.done = False
        self.t = 0.0
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.reloading = False
        self.reload_t = 0.0
        self.reload_empty = False
        self.reload_total = RELOAD_EMPTY
        self.reload_mag_in = False
        self.firing_held_during_reload = False
        self.last_fire = -9.0
        self.yaw = BASE_YAW
        self.pitch = BASE_PITCH
        self.kick = 0.0
        self.shake = 0.0
        self.hurt = 0.0
        self.hit_mark = -9.0
        self.flash_t = -9.0
        self.tracers = []
        self.sparks = []
        self.last_hit_head = False
        self.recoil_p = 0.0         # view climb (deg) that recovers when firing stops
        self.recoil_y = 0.0
        self.spread = 0.0           # bloom (deg) over a sustained burst
        self.hit_kind = "hit"       # hit-marker flavour: hit / kill / head
        self.brass = []
        self.decals = []
        self.impacts = []
        self.dmg_marks = []         # (t, bearing deg) of rounds that hurt
        self.tinks = []             # clock times a casing first hits the deck
        self.spawn_puffs = []
        self.guards = []
        self.audio = None
        self._ev = set()
        self._fired_events = set()
        self._frame = 0
        # Platform pressure / consequences.
        self.volkov_delay = 0.0
        self.volkov_pinned = False
        self.volkov_threats = 0
        self.overrun = False
        self.kills = 0
        self.dying = False
        self.death_t = 0.0
        self.death_requested = False
        self.death_yaw = BASE_YAW
        self.death_pitch = BASE_PITCH
        self.death_eye0 = None
        self.cleared_t = -9.0
        self.fall_shift = 0.0
        self.volkov_failed = False
        self.fail_t = 0.0
        self.fail_requested = False
        self.fail_pos = None
        self.fail_yaw = BASE_YAW
        self.cine_pending_shot = False
        self.ucilev_fired = False
        self.ucilev_fire_t = -9.0
        self._clear_warned = False
        self._overrun_warned = False
        self._vstate = None
        self._bstate = None
        self._fstate = None

    # ── lifecycle ──────────────────────────────────────────────────────
    def begin(self, stage_resume=False):
        if self.started and not self.done:
            return False
        self.reset()
        self.started = True
        self.done = False
        self.t = 0.0
        STATE.m6_train_active = True
        STATE.m6_train_time = 0.0
        STATE.m6_train_result = None
        STATE.m6_train_overrun = False
        STATE.m6_train_guards_left = 0
        STATE.m6_train_death = False
        STATE.m6_volkov_dead = False
        self.guards = [_make_guard(i, s) for i, s in enumerate(_GUARD_SLOTS)]
        if STATE.player is not None:
            self.yaw = BASE_YAW
            self.pitch = BASE_PITCH
        try:
            from .m6_audio import M6TrainAudio  # lazy: audio is mission-owned
            self.audio = M6TrainAudio(audio)
            self.audio.start()
        except Exception:
            self.audio = None
        try:
            if pygame.display.get_init():
                pygame.mouse.set_pos((WIDTH // 2, HEIGHT // 2))
        except Exception:
            pass
        try:
            self.prepare()
        except Exception:
            pass
        return True

    def prepare(self):
        _renderer()
        _hum(("biribel", OUTFIT_GUARD))
        _hum("volkov")
        _hum("ucilev")
        for kind in _GUARD_KINDS:
            _hum(("guard", kind))
        try:
            for name in ("m6_train_idle", "m6_wind_bed", "gunshot",
                         "bullet_impact", "bullet_impact_enemy", "empty_click",
                         "reload", "m6_rifle_crack", "m6_doors_close",
                         "m6_train_depart", "m6_breath"):
                audio.get_sound(name)
        except Exception:
            pass

    def reset(self):
        if self.audio is not None:
            try:
                self.audio.stop()
            except Exception:
                pass
        self.audio = None
        self.started = False
        self.done = False
        self.t = 0.0
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.reloading = False
        self.reload_t = 0.0
        self.reload_empty = False
        self.reload_total = RELOAD_EMPTY
        self.reload_mag_in = False
        self.firing_held_during_reload = False
        # Combat clocks are absolute in scene time.  Leaving last_fire at the
        # dead run's timestamp makes every shot after a redeploy "too soon"
        # for the whole next run - the gun simply never fires.
        self.last_fire = -9.0
        self.flash_t = -9.0
        self.hit_mark = -9.0
        self.kick = 0.0
        self.shake = 0.0
        self.hurt = 0.0
        self.yaw = BASE_YAW
        self.pitch = BASE_PITCH
        self.tracers = []
        self.sparks = []
        self.last_hit_head = False
        self.recoil_p = 0.0         # view climb (deg) that recovers when firing stops
        self.recoil_y = 0.0
        self.spread = 0.0           # bloom (deg) over a sustained burst
        self.hit_kind = "hit"       # hit-marker flavour: hit / kill / head
        self.brass = []
        self.decals = []
        self.impacts = []
        self.dmg_marks = []         # (t, bearing deg) of rounds that hurt
        self.tinks = []             # clock times a casing first hits the deck
        self.spawn_puffs = []
        self._frame = 0
        self._ev = set()
        self._fired_events = set()
        self.guards = []
        self.volkov_delay = 0.0
        self.volkov_pinned = False
        self.volkov_threats = 0
        self.overrun = False
        self.kills = 0
        self.dying = False
        self.death_t = 0.0
        self.death_requested = False
        self.death_yaw = BASE_YAW
        self.death_pitch = BASE_PITCH
        self.death_eye0 = None
        self.cleared_t = -9.0
        self.fall_shift = 0.0
        self.volkov_failed = False
        self.fail_t = 0.0
        self.fail_requested = False
        self.fail_pos = None
        self.fail_yaw = BASE_YAW
        self.cine_pending_shot = False
        self.ucilev_fired = False
        self.ucilev_fire_t = -9.0
        self._clear_warned = False
        self._overrun_warned = False
        self._vstate = None
        self._bstate = None
        self._fstate = None
        # The subtitle widget is module-owned and driven by THIS scene's clock
        # (int(t * 1000)).  A redeploy rewinds t to 0, so any line left in the
        # widget's history is stamped in the dead run's timebase - a future
        # timestamp the widget would draw with an out-of-range alpha.  A fresh
        # run starts with a clean log.
        try:
            _radio_widget().reset()
        except Exception:
            pass
        # Drop the baked static set + renderer cache so a redeploy cannot
        # inherit a stale/empty cache from the previous (possibly failed) run.
        try:
            _cache["r"] = None
        except Exception:
            pass
        try:
            _w._STATIC_SIG = None
            _w._STATIC_BUILD["active"] = False
            _w._STATIC_BUILD["rebuild"] = False
        except Exception:
            pass

    def active(self):
        return bool(self.started and not self.done)

    def result(self):
        return getattr(STATE, "m6_train_result", None) or ("win" if self.done else None)

    def skip(self):
        return self.force_finish("skip")

    def force_finish(self, result="win"):
        if self.done:
            return False
        if (self.dying or self.volkov_failed
                or getattr(STATE, "player_dead", False)):
            # A failed train run never hands off to the ending film.
            return False
        self.done = True
        self.started = False
        STATE.m6_train_active = False
        STATE.m6_train_result = result
        STATE.m6_train_guards_left = self._living()
        if self.audio is not None:
            try:
                self.audio.stop()
            except Exception:
                pass
        self.firing = False
        try:
            from . import flow as _flow
            _flow.on_train_done(result)
        except Exception:
            pass
        return True

    def set_paused(self, paused):
        if self.audio is not None:
            try:
                self.audio.pause() if paused else self.audio.resume()
            except Exception:
                pass
        if paused:
            self.firing = False
            self.aiming = False

    # ── input ──────────────────────────────────────────────────────────
    def handle_event(self, event):
        if not self.active() or self.dying or self.volkov_failed:
            return False
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.firing = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self.firing = False
            return True
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 3:
            self.aiming = True
            return True
        if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
            self.aiming = False
            return True
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_r:
                self._begin_reload()
                return True
            if event.key == pygame.K_e and self.t >= 2.0:
                self.force_finish("skip")
                return True
            if event.key in (pygame.K_SPACE, pygame.K_RETURN) and self.t >= 2.0:
                self.force_finish("skip")
                return True
            if event.key == pygame.K_h:
                self.force_finish("skip")
                return True
        return False

    def fire_once(self):
        """Test/tool hook: one aimed shot with the current camera."""
        if not self.active() or self.t < CONTROL_AT:
            return False
        self._fire()
        return True

    # ── simulation ─────────────────────────────────────────────────────
    def update(self, keys=None, mouse=None):
        if not self.active():
            return
        dt = clamp(float(getattr(STATE, "dt", 1.0 / 60.0)), 0.0, 0.05)
        if self.dying:
            # The world freezes on the last fight frame while the 3D death
            # camera and body play out.  Only the death clock advances.
            self.death_t += dt
            self.hurt = max(self.hurt, 1.0 - _smooth(0.0, 1.2, self.death_t))
            self.shake = max(self.shake * 0.96, 0.20 * (1.0 - _smooth(0.0, 0.8, self.death_t)))
            if self.death_t >= 2.2 and not self.death_requested:
                self.death_requested = True
                # Hand the frozen frame to the death screen explicitly; the
                # train no longer owns the GAME update once the terminal is up.
                STATE.m6_train_active = False
                STATE.m6_train_death = True
                STATE.request_death_screen = True
            self._prune_fx()
            return
        if self.volkov_failed:
            # Volkov was cut down in the open.  Freeze the fight on that
            # frame, let the last tracers fade, then go to the failure
            # terminal - never to the ending film.
            self.fail_t += dt
            self.shake = max(self.shake * 0.96, 0.25 * (1.0 - _smooth(0.0, 0.9, self.fail_t)))
            self.hurt = max(self.hurt, 0.9 * (1.0 - _smooth(0.0, 1.4, self.fail_t)))
            if self.fail_t > 0.20:
                self.tracers = []
                self.sparks = []
            if self.fail_t >= 1.8 and not self.fail_requested:
                self.fail_requested = True
                STATE.m6_train_active = False
                STATE.m6_train_death = True
                STATE.m6_train_result = "failed"
                STATE.request_death_screen = True
                if self.audio is not None:
                    try:
                        self.audio.stop()
                    except Exception:
                        pass
            return
        self.t += dt
        self._frame += 1
        STATE.m6_train_time = self.t

        # Sight blend: raise fast, lower a touch slower (ADS = RMB).
        want_ads = 1.0 if (self.aiming and not self.reloading) else 0.0
        rate = 11.0 if want_ads > self.ads else 7.0
        self.ads = clamp(self.ads + (want_ads - self.ads) * min(1.0, dt * rate),
                         0.0, 1.0)

        if self.t >= CONTROL_AT:
            mx, my = mouse if mouse is not None else get_scaled_mouse()
            # Zoomed aim needs a tighter mouse gain, or ADS overshoots.
            sens = 1.0 - 0.22 * self.ads
            # engine3d's screen-right is -x at yaw 0 (right = up x fwd), so
            # add to yaw to look left.  Negate x to keep mouse-right = look-right.
            want_yaw = BASE_YAW - (mx - WIDTH / 2) / (WIDTH * 0.5) * YAW_LIMIT * sens
            want_pitch = BASE_PITCH + (HEIGHT / 2 - my) / (HEIGHT * 0.5) * PITCH_LIMIT * sens
            self.yaw = clamp(want_yaw, BASE_YAW - YAW_LIMIT, BASE_YAW + YAW_LIMIT)
            self.pitch = clamp(want_pitch, BASE_PITCH - PITCH_LIMIT,
                               BASE_PITCH + PITCH_LIMIT)
            if self.firing:
                self._fire()

        self.kick = max(0.0, self.kick - dt * 5.5)
        # Recoil recovers once the trigger lets go: fast at first, then easing
        # (a burst climbs, then settles back toward the aim point).
        idle = self.t - self.last_fire
        if idle > 0.06:
            rec = 9.0 * dt + self.recoil_p * 4.0 * dt
            self.recoil_p = max(0.0, self.recoil_p - rec)
            self.recoil_y -= self.recoil_y * min(1.0, 7.0 * dt)
            self.spread = max(0.0, self.spread - 2.4 * dt)
        self.shake = max(0.0, self.shake - dt * 3.2)
        self.hurt = max(0.0, self.hurt - dt)
        self._update_reload(dt)

        self._spawn_guards()
        self._update_guards(dt)
        self._update_suppression(dt)

        if self.t >= SHOT_AT and "shot" not in self._ev:
            self._ev.add("shot")
            self._volkov_shot()
        if (self.cine_pending_shot and not self.ucilev_fired
                and self.t >= HIT_AT):
            self._ucilev_fire()
        # The shot's aftermath: ringing ears, the distant report, the body.
        for ev, at, call in (("tinnitus", HIT_AT + 0.12, "tinnitus"),
                             ("report", HIT_AT + 0.95, "report"),
                             ("thud", DOWN_AT + SLOW_LAG - 0.05, "thud")):
            if (self.ucilev_fired and self.t >= at and ev not in self._ev):
                self._ev.add(ev)
                if self.audio:
                    getattr(self.audio, call)()
        if self.t >= DOORS_AT + SLOW_LAG and "doors" not in self._ev:
            self._ev.add("doors")
            if self.audio:
                self.audio.doors()
        if self.t >= DEPART_AT + SLOW_LAG and "depart" not in self._ev:
            self._ev.add("depart")
            if self.audio:
                self.audio.depart()
        if self.t >= DOWN_AT + SLOW_LAG + 1.15 and "breath" not in self._ev:
            self._ev.add("breath")
            if self.audio:
                self.audio.breath()
        self._update_guard_fire(dt)
        self._prune_fx()
        if self.t >= DURATION:
            self.force_finish("win")

    def _prune_fx(self):
        now = self.t
        self.tracers = [x for x in self.tracers if now - x[0] < 0.12]
        self.sparks = [x for x in self.sparks if now - x[0] < 0.5]
        self.impacts = [x for x in self.impacts if now - x[0] < 0.55]
        self.brass = [b for b in self.brass if now - b[0] < 7.0]
        if self.tinks:
            due = [x for x in self.tinks if x <= now]
            if due:
                self.tinks = [x for x in self.tinks if x > now]
                if self.audio:
                    self.audio.tink()
        self.dmg_marks = [m for m in self.dmg_marks if now - m[0] < 0.85]
        self.spawn_puffs = [x for x in self.spawn_puffs if now - x[0] < 0.6]

    def _living(self):
        return sum(1 for g in self.guards
                   if g.get("active") and g.get("alive"))

    def _spawn_guards(self):
        now = self.t
        living = self._living()
        for g in self.guards:
            if g.get("active"):
                continue
            spawn = float(g.get("spawn", 99.0))
            if now < spawn:
                continue
            # Reserves are the answer to a clean sweep: if the player has the
            # platform under control, the Guard commits its last two bodies so
            # the final run still has a fight.
            if g.get("reserve") and (living > 1 or now > RESERVE_CUTOFF):
                continue
            if not g.get("reserve") and living >= MAX_LIVING:
                continue
            prof = _guard_profile(g.get("kind"))
            g["active"] = True
            g["alive"] = True
            g["hp"] = prof["hp"]
            g["max_hp"] = prof["hp"]
            g["spawn_t"] = now
            g["flinch"] = 0.0
            g["wp"] = 0
            g["next_fire"] = 0
            g["burst_left"] = 0
            living += 1
            self.spawn_puffs.append((now, g["pos"]))

    def _update_guards(self, dt):
        for g in self.guards:
            g["flinch"] = max(0.0, float(g.get("flinch", 0.0)) - dt)
            if not (g.get("active") and g.get("alive")):
                continue
            prof = _guard_profile(g.get("kind"))
            path = g.get("path") or ()
            wp = int(g.get("wp", 0))
            moving = False
            if wp < len(path):
                when, tx, tz = path[wp]
                if self.t >= when:
                    px, py, pz = g["pos"]
                    dx, dz = tx - px, tz - pz
                    dist = math.hypot(dx, dz)
                    speed = float(prof.get("speed", 0.0))
                    if dist > 0.06 and speed > 0.0:
                        step = min(dist, speed * dt)
                        px += dx / dist * step
                        pz += dz / dist * step
                        g["pos"] = (px, py, pz)
                        g["yaw"] = _w.yaw_to((px, 0.0, pz), (tx, 0.0, tz))
                        moving = True
                    else:
                        g["pos"] = (tx, py, tz)
                        g["wp"] = wp + 1
            g["moving"] = moving
            if not moving:
                eye = self._eye()[0]
                g["yaw"] = _w.yaw_to((g["pos"][0], 0.0, g["pos"][2]),
                                     (eye[0], 0.0, eye[2]))

    def _cover_blocks(self, src, dst):
        """True when one of the platform crates stands between two points."""
        dx, dy, dz = dst[0] - src[0], dst[1] - src[1], dst[2] - src[2]
        dist = math.sqrt(dx * dx + dy * dy + dz * dz)
        if dist <= 1e-6:
            return False
        d = (dx / dist, dy / dist, dz / dist)
        for cx, cz, hw, hd, top in _CRATES:
            block = _ray_aabb(src, d, (cx - hw, _SLOT_GROUND, cz - hd),
                              (cx + hw, top, cz + hd))
            if block is not None and block < dist - 0.18:
                return True
        return False

    def _update_guard_fire(self, dt):
        if self.t >= SHOT_AT:
            return
        for g in self.guards:
            if not (g.get("active") and g.get("alive")):
                continue
            prof = _guard_profile(g.get("kind"))
            fire = g.get("fire")
            if fire is None:
                slot = int(g.get("slot", -1))
                spec = _GUARD_SLOTS[slot] if 0 <= slot < len(_GUARD_SLOTS) else {}
                fire = spec.get("fire", ())
            nf = int(g.get("next_fire", 0))
            if nf < len(fire) and self.t >= fire[nf]:
                g["next_fire"] = nf + 1
                g["burst_left"] = int(prof["burst"])
                g["burst_damage"] = int(prof["damage"])
                g["burst_next"] = self.t
            if int(g.get("burst_left", 0)) > 0 and self.t >= g.get("burst_next", 0.0):
                self._guard_shot(g, prof)

    def _guard_shot(self, g, prof):
        if self.done or getattr(STATE, "player_dead", False):
            return
        src = (g["pos"][0], g["pos"][1] + 1.38, g["pos"][2])
        eye, _yaw, _pitch = self._eye()
        # Fire at the head and shoulders: a tracer that lands beside the player
        # still reads as a near miss, but cover is respected.
        dst = (eye[0] + math.sin(self.t * 8.3 + g["slot"] * 1.7) * 0.75,
               eye[1] - 0.18,
               eye[2] + math.cos(self.t * 6.1 + g["slot"] * 2.3) * 0.75)
        if self._cover_blocks(src, dst):
            g["burst_next"] = self.t + 0.30
            return
        g["burst_left"] = max(0, int(g.get("burst_left", 0)) - 1)
        g["last_shot_t"] = self.t
        gap = float(prof.get("gap", 0.1))
        g["burst_next"] = self.t + (gap if g["burst_left"] else 0.45)
        if self.audio:
            self.audio.guard_shot()
            if _drip(self.t * 60.0, g["slot"]) < 0.45:
                self.audio.whiz()
        col = (255, 208, 150) if g.get("kind") != "marksman" else (222, 236, 255)
        self.tracers.append((self.t, src, dst, col))
        p = STATE.player
        if p is not None:
            damage = int(g.get("burst_damage", _GUARD_DAMAGE))
            p.hp = max(PLAYER_HP_FLOOR, p.hp - damage)
            self.hurt = max(self.hurt, 0.20 + damage * 0.022)
            _e, yaw_v, _pv = self._eye()
            bearing = (_w.yaw_to(eye, g["pos"]) - yaw_v + 180.0) % 360.0 - 180.0
            self.dmg_marks.append((self.t, bearing))
            self.shake = max(self.shake, 0.35 + damage * 0.035)
            if p.hp <= 0:
                self._player_down()

    def _player_down(self):
        """Biribel is hit for the last time - play the death in 3D.

        The scene stays active and freezes the fight while a third-person
        camera follows the body down.  After the beat, the normal death screen
        takes over (it still draws this frozen 3D frame behind its terminal)
        and its restart button respawns at the train checkpoint.
        """
        if self.done or self.dying:
            return
        p = STATE.player
        if p is not None:
            p.hp = 0
        STATE.player_dead = True
        STATE.m6_train_result = "dead"
        STATE.m6_train_guards_left = self._living()
        STATE.m6_train_death = False
        eye0, yaw0, pitch0 = self._eye()
        self.death_eye0 = eye0
        self.dying = True
        self.death_t = 0.0
        self.death_requested = False
        self.death_yaw = yaw0
        self.death_pitch = pitch0
        self.firing = False
        self.reloading = False
        self.hurt = 1.0
        self.shake = 1.0
        if self.audio is not None:
            try:
                self.audio.stop()
            except Exception:
                pass

    def _update_suppression(self, dt):
        if self.t < CONTROL_AT or self.t >= SHOT_AT:
            self.volkov_pinned = False
            self.volkov_threats = 0
            return
        living = self._living()
        self.volkov_threats = living
        self.volkov_pinned = living >= VOLKOV_PIN_THREAT
        if self.volkov_pinned:
            self.volkov_delay = min(VOLKOV_DELAY_MAX,
                                    self.volkov_delay + dt * VOLKOV_DELAY_RATE)
        if (living == 0 and self.t > CONTROL_AT and self.cleared_t < 0.0
                and any(g.get("active") for g in self.guards)):
            self.cleared_t = self.t

    @property
    def wounded(self):
        p = STATE.player
        return bool(p is not None and getattr(p, "hp", 999) <= 35)

    def _eye(self):
        sway = 1.65 if self.wounded else 1.0
        yaw = (self.yaw + self.recoil_y
               + 0.35 * math.sin(self.t * 1.3) * self._motion() * sway)
        pitch = (self.pitch + self.recoil_p + self.kick * (0.9 - 0.32 * self.ads)
                 + 0.2 * math.sin(self.t * 1.7) * self._motion() * sway)
        eye = (PLAYER_POS[0], PLAYER_POS[1] + PLAYER_EYE, PLAYER_POS[2])
        shk = self.shake * 0.05
        if shk:
            eye = (eye[0] + math.sin(self.t * 61.0) * shk,
                   eye[1] + math.sin(self.t * 47.0 + 2.0) * shk,
                   eye[2])
        return eye, yaw, pitch

    def _motion(self):
        return 0.0 if getattr(STATE, "reduced_motion", False) else 1.0

    def _begin_reload(self):
        if self.reloading:
            return
        if getattr(STATE, "k9_ammo_in_mag", 0) >= getattr(STATE, "k9_mag_size", 30):
            return
        if getattr(STATE, "k9_spare_mags", 0) <= 0:
            if self.audio:
                self.audio.dry()
            return
        self.reload_empty = getattr(STATE, "k9_ammo_in_mag", 0) <= 0
        self.reload_total = RELOAD_EMPTY if self.reload_empty else RELOAD_TACTICAL
        if self.wounded:
            self.reload_total *= 1.18
        self.reload_t = self.reload_total
        self.reload_mag_in = False
        self.reloading = True
        self.aiming = False
        self.firing_held_during_reload = self.firing
        if self.audio:
            self.audio.reload()

    def begin_reload(self):
        return self._begin_reload()

    def beginreload(self):
        return self._begin_reload()

    def _update_reload(self, dt):
        if not self.reloading:
            return
        self.reload_t -= dt
        p = self.reload_progress()
        if not self.reload_mag_in and p >= RMAG_IN:
            self.reload_mag_in = True
            if getattr(STATE, "k9_spare_mags", 0) > 0:
                STATE.k9_spare_mags -= 1
                # The K9 counter is magazine capacity, not capacity + chamber:
                # a tactical reload refills to mag_size and the HUD stays 24/24.
                STATE.k9_ammo_in_mag = getattr(STATE, "k9_mag_size", 30)
        if self.reload_t <= 0:
            self.reloading = False

    def reload_progress(self):
        if not self.reloading:
            return 1.0
        return 1.0 - clamp(self.reload_t / self.reload_total, 0.0, 1.0)

    def reloadprogress(self):
        return self.reload_progress()

    def update_reload(self, dt):
        return self._update_reload(dt)

    def updatereload(self, dt):
        return self._update_reload(dt)

    def _fire(self):
        if self.dying or self.reloading or self.t < CONTROL_AT:
            return
        now = self.t
        if now - self.last_fire < FIRE_INTERVAL:
            return
        if getattr(STATE, "k9_ammo_in_mag", 0) <= 0:
            if now - self.last_fire > 0.25:
                self.last_fire = now
                if self.audio:
                    self.audio.dry()
                self._begin_reload()
            return
        self.last_fire = now
        STATE.k9_ammo_in_mag -= 1
        STATE.shots_fired = getattr(STATE, "shots_fired", 0) + 1
        self.flash_t = now
        if self.audio:
            self.audio.shot()

        seq = int(getattr(STATE, "shots_fired", 0))
        ads_k = 1.0 - 0.45 * self.ads
        # The round leaves along the aim the player held, not the one the
        # muzzle climbs to a frame later: kick after the ray is cast.
        eye, aim_yaw, aim_pitch = self._eye()
        self.kick = 1.0 - 0.25 * self.ads
        # Bloom over a burst, tighter down the sights; deterministic per round.
        sp = self.spread * (0.35 if self.ads > 0.5 else 1.0)
        fwd = _forward(aim_yaw + (_drip(seq, 5) - 0.5) * 2.0 * sp,
                       aim_pitch + (_drip(seq, 6) - 0.5) * 2.0 * sp)
        # This round kicks the NEXT one: the muzzle climbs and zigs.
        self.recoil_p = min(5.0, self.recoil_p + 0.55 * ads_k)
        self.recoil_y += (_drip(seq, 7) - 0.5) * 0.36 * ads_k
        self.spread = min(0.9, self.spread + 0.15)
        self._eject_brass(now, eye, aim_yaw, seq)
        hit = self._hitscan(eye, fwd)
        world = _world_hit(eye, fwd)
        muzzle = self._muzzle_world()
        if hit is not None and (world is None or hit[1] <= world[0] + 0.05):
            g, t_hit = hit
            head = bool(self.last_hit_head)
            point = (eye[0] + fwd[0] * t_hit, eye[1] + fwd[1] * t_hit,
                     eye[2] + fwd[2] * t_hit)
            self.sparks.append((now, point, (176, 44, 44)))
            self.impacts.append((now, point, "flesh", (-fwd[0], -fwd[1], -fwd[2])))
            # Spatter on whatever stands behind him.
            behind = _world_hit((point[0] + fwd[0] * 0.4, point[1] + fwd[1] * 0.4,
                                 point[2] + fwd[2] * 0.4), fwd, tmax=7.0)
            if behind is not None:
                bp = tuple(point[i] + fwd[i] * (0.4 + behind[0]) for i in range(3))
                self._add_decal(bp, behind[2], "flesh", 0.07 + 0.05 * _drip(seq, 9))
            self.hit_mark = now
            self.hit_kind = "head" if head else "hit"
            g["hp"] -= HIT_DAMAGE * (2.5 if head else 1.0)
            g["hit_t"] = now
            fn = math.hypot(fwd[0], fwd[2]) or 1.0
            g["hit_dir"] = (fwd[0] / fn, fwd[2] / fn)
            g["flinch"] = 0.24 * float(_guard_profile(g.get("kind")).get("flinch", 1.0))
            STATE.shots_hit = getattr(STATE, "shots_hit", 0) + 1
            if self.audio:
                self.audio.impact(True)
                if head:
                    self.audio.headshot()
            if g["hp"] <= 0:
                g["alive"] = False
                g["dead_t"] = now
                g["dead_land"] = None
                g["burst_left"] = 0
                g["moving"] = False
                g["track"] = 1 if head else (0 if _drip(g.get("slot", 0), seq) < 0.55 else 2)
                g["dead_yaw"] = _w.yaw_to((g["pos"][0], 0.0, g["pos"][2]),
                                          (eye[0], 0.0, eye[2]))
                self.hit_kind = "head" if head else "kill"
                self.kills += 1
                STATE.hostiles_killed = getattr(STATE, "hostiles_killed", 0) + 1
                if self._living() == 0:
                    self.cleared_t = now
            end = point
        elif world is not None:
            tw, kind, n = world
            end = (eye[0] + fwd[0] * tw, eye[1] + fwd[1] * tw, eye[2] + fwd[2] * tw)
            self.impacts.append((now, end, kind, n))
            self._add_decal(end, n, kind)
            if self.audio:
                self.audio.impact(False)
        else:
            end = (eye[0] + fwd[0] * 90.0, eye[1] + fwd[1] * 90.0,
                   eye[2] + fwd[2] * 90.0)
        self.tracers.append((now, muzzle, end, (255, 226, 170)))

    def _add_decal(self, pos, n, kind, size=0.05):
        self.decals.append((pos, n, kind, size))
        if len(self.decals) > _DECAL_CAP:
            del self.decals[0]

    def _eject_brass(self, now, eye, aim_yaw, seq):
        """Throw a casing out of the ejection port: right, up and a little back."""
        rgt = _right(aim_yaw)
        fw = _forward(aim_yaw, 0.0)
        o = (eye[0] + rgt[0] * 0.20 + fw[0] * 0.50,
             eye[1] - 0.13,
             eye[2] + rgt[2] * 0.20 + fw[2] * 0.50)
        h1, h2, h3 = _drip(seq, 11), _drip(seq, 12), _drip(seq, 13)
        v = (rgt[0] * (1.5 + 0.7 * h1) - fw[0] * 0.3,
             1.5 + 0.7 * h2,
             rgt[2] * (1.5 + 0.7 * h1) - fw[2] * 0.3 + (h3 - 0.5) * 0.4)
        self.brass.append((now, o, v, seq))
        a1 = (v[1] + math.sqrt(max(0.0, v[1] * v[1] + 19.6 * (o[1] - _SLOT_GROUND - 0.012)))) / 9.8
        self.tinks.append(now + a1)
        if len(self.brass) > _BRASS_CAP:
            del self.brass[0]

    def _hitscan(self, eye, fwd):
        best = None
        zone = 0
        for g in self.guards:
            if not (g.get("active") and g.get("alive")):
                continue
            base = g["pos"]
            big = g.get("kind") == "heavy"
            radii = ((1.30, 0.42), (1.56, 0.36)) if big else ((1.32, 0.38), (1.60, 0.32))
            for zi, (dy, rad) in enumerate(radii):
                hit = _ray_sphere(eye, fwd, (base[0], base[1] + dy, base[2]), rad)
                if hit is not None and hit < 45.0 and (best is None or hit < best[1]):
                    best = (g, hit)
                    zone = zi
        if best is None:
            return None
        # The two spheres overlap: call it a headshot when the round arrives
        # nearer the head's centre than the chest's, not by which sphere it
        # entered first.
        gb = best[0]["pos"]
        big = best[0].get("kind") == "heavy"
        py = eye[1] + fwd[1] * best[1] - gb[1]
        self.last_hit_head = abs(py - (1.56 if big else 1.60)) < abs(py - (1.30 if big else 1.32))             and py > 1.42
        for cx, cz, hw, hd, top in _CRATES:
            lo = (cx - hw, _SLOT_GROUND, cz - hd)
            hi = (cx + hw, top, cz + hd)
            block = _ray_aabb(eye, fwd, lo, hi)
            if block is not None and block < best[1]:
                return None
        return best

    def _volkov_shot(self):
        threats = [g for g in self.guards
                   if g.get("active") and g.get("alive")]
        STATE.m6_train_guards_left = len(threats)
        if len(threats) >= 2:
            # The lane was never cleared.  Volkov does not reach the train;
            # the squad cuts him down in the open and the run is a failure.
            self.overrun = True
            self.volkov_failed = True
            self.fail_t = 0.0
            self.fail_requested = False
            STATE.m6_train_overrun = True
            STATE.m6_train_result = "failed"
            STATE.m6_volkov_dead = True
            fail_pos, _mode, _phase = _volkov_at(SHOT_AT, self.volkov_delay)
            self.fail_pos = tuple(fail_pos)
            threats.sort(key=lambda g: _dist2(g["pos"], fail_pos))
            self.fail_yaw = _w.yaw_to(fail_pos, threats[0]["pos"])
            for i, g in enumerate(threats[:3]):
                src = (g["pos"][0], g["pos"][1] + 1.38, g["pos"][2])
                dst = (fail_pos[0] + 0.10 * (i - 1),
                       fail_pos[1] + 1.00,
                       fail_pos[2] + 0.06 * (i - 1))
                self.tracers.append((self.t, src, dst, (255, 198, 138)))
            if self.audio:
                self.audio.guard_shot()
                self.audio.guard_shot()
            self.shake = max(self.shake, 1.0)
            return
        # The lane is clear enough.  Ucilev's shot from the signal tower is
        # the one thing the player cannot take off the board.  Volkov dies
        # at the train; the mission continues to the ending film.
        self.overrun = False
        STATE.m6_train_overrun = False
        self.shake = max(self.shake, 0.45)
        self.cine_pending_shot = True
        self.ucilev_fired = False
        fall_pos, _mode, _phase = _volkov_at(DOWN_AT, self.volkov_delay)
        self.fall_shift = clamp(fall_pos[2] - 0.55, 0.0, 1.8)

    def _ucilev_fire(self):
        self.ucilev_fired = True
        self.ucilev_fire_t = self.t
        STATE.m6_volkov_dead = True
        if self.audio:
            self.audio.crack()
        self.shake = max(self.shake, 1.0)
        vpos, _mode, _phase = _volkov_at(HIT_AT, self.volkov_delay)
        src = (TOWER_KNEE[0], TOWER_KNEE[1] + 0.24, TOWER_KNEE[2])
        dst = (vpos[0], vpos[1] + 1.05, vpos[2])
        self.tracers.append((self.t, src, dst, (236, 242, 255)))
        self.sparks.append((self.t, (vpos[0], vpos[1] + 1.05, vpos[2]),
                            (176, 44, 44)))

    # ── draw ───────────────────────────────────────────────────────────
    def draw(self, surface):
        if not self.active():
            return False
        r = _renderer()
        t = self.t
        if t > HIT_AT and not self.volkov_failed and not self.dying:
            t = _anim_t(t)
        # Solve the death once: the camera, both actors and the death FX used
        # to re-run the same pose/IK 3-4 times a frame and could drift apart.
        self._vstate = None
        self._bstate = None
        self._fstate = None
        if self.volkov_failed:
            if self.fail_pos is not None:
                self._fstate = _volkov_fail_state(
                    self.fail_t, t, self.fail_pos, self.fail_yaw,
                    self.volkov_delay)
        elif t >= HIT_AT:
            self._vstate = _volkov_death_state(t, self.volkov_delay)
            if t - SHOT_AT >= 3.05:
                self._bstate = _biribel_catch_state(t, self._vstate)
        eye, yaw, pitch = self._eye()
        live_eye = None if self.dying else eye
        live_fwd = None if self.dying else _forward(yaw, pitch)
        _light(r, live_eye if t < CUT_AT else None,
               live_fwd if t < CUT_AT else None, t=t,
               flashes=self._flash_lights(t))
        self._draw_camera(r, t)
        r.surface.fill((6, 8, 14))
        _w.night(r, r.surface, t * 1000.0, top=(4, 6, 13), bot=SKY_HORIZON,
                 stars=90, moon=(112.0, 13.0), sodium=(42, 28, 18), seed=71,
                 star_cut=0.62)
        r.begin()
        del _w.LAST[:]          # probe reads only this frame's actors
        # The platform, station shell and dressing never move before the
        # catch cut, so bake them once: the old per-frame Python packing was
        # most of the frame budget, and the fight needs that budget for the
        # eight-actor roster.
        static = t < CUT_AT
        normal_light = r.light
        rebuild = True
        bake_ok = False
        if static:
            # Bake the shell with a little more ambient than the live action
            # light: the point-light pools are baked out of the static pass
            # (they are replaced by floor sprites), so the wall/platform need
            # the lift to match the actors.  Kept close to the action rig -
            # a brighter, warmer bake used to leave the set reading warmer
            # than the people standing in it.
            from engine3d import Light as _Light
            r.light = _Light(direction=(-0.46, 0.64, -0.36), ambient=0.41,
                             diffuse=0.64, sky=0.22, tint=(0.94, 0.95, 1.00))
            rebuild = _w.static_scene(r, "m6_train_static")
        try:
            if rebuild or not static:
                _w.rail_platform(r, t * 1000.0, train=True, snow=1.0,
                                 train_offset=self._train_offset(t))
                self._draw_station(r, t)
            else:
                # Set geometry is cached in the renderer; only the animated light
                # and snow sprites need to be re-queued each frame.
                self._draw_static_lights(r, t)
            bake_ok = True
        finally:
            if static:
                _w.static_end(r, ok=bake_ok)
                r.light = normal_light
        self._draw_train_door(r, t)
        self._draw_volkov(r, t)
        self._draw_guards(r, t)
        self._draw_ucilev(r, t)
        self._draw_biribel(r, t)
        self._draw_fx(r, t)
        self._draw_death_fx(r, t)
        _w.snow3d(r, t * 1000.0, seed=72, n=55, spread=20, height=14, speed=1.4)
        r.flush(r.surface)

        if t < CUT_AT and not self.dying and not self.volkov_failed:
            # second pass: viewmodel only, always on top of the world
            r.begin()
            self._draw_viewmodel(r)
            r.flush(r.surface)

        if t >= CUT_AT:
            _grade_cine(r.surface)
        elif not self.dying:
            _grade_play(r.surface, self.wounded)
        pygame.transform.smoothscale(r.surface, (WIDTH, HEIGHT), surface)
        draw_vignette(surface)
        if t < CUT_AT:
            draw_scanlines(surface)
        if self.dying:
            self._draw_death_overlay(surface)
        elif self.volkov_failed:
            self._draw_fail_overlay(surface)
        elif t >= SHOT_AT:
            self._draw_cine_overlay(surface, t)
            self._draw_subtitle(surface, t)
        else:
            self._draw_hud(surface, t)

        fade = 0.0
        if t < 0.8:
            fade = 1.0 - t / 0.8
        elif t > FADE_AT:
            fade = clamp((t - FADE_AT) / (DURATION - SLOW_LAG - FADE_AT), 0.0, 1.0) ** 0.8
        if fade > 0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * fade))
            surface.blit(veil, (0, 0))
        return True

    def _flash_lights(self, t):
        """Transient point lights for muzzle flashes: the player's round warms
        the gun, hands and the crate in front of it; the freshest guard shot
        shares one more slot.  Gameplay only (the cinematic rigs are authored)."""
        if t >= CUT_AT or self.dying:
            return ()
        out = []
        age = t - self.flash_t
        if 0.0 <= age < 0.055:
            k = 1.0 - age / 0.055
            out.append({"pos": self._muzzle_world(), "color": (255, 198, 128),
                        "intensity": 2.4 * k, "range": 4.2})
        best = None
        for g in self.guards:
            if g.get("active") and g.get("alive"):
                ga = t - g.get("last_shot_t", -9.0)
                if 0.0 <= ga < 0.06 and (best is None or ga < best[0]):
                    best = (ga, g)
        if best is not None:
            ga, g = best
            x, y, z = g["pos"]
            out.append({"pos": (x, y + 1.4, z + 0.3), "color": (255, 206, 150),
                        "intensity": 1.8 * (1.0 - ga / 0.06), "range": 5.0})
        return tuple(out)

    def _draw_camera(self, r, t):
        if self.dying:
            # Continuous first-person collapse: no cut out to a third-person
            # camera.  The eye drops, rolls and tips up exactly where Biribel
            # was standing; the failure terminal follows the dark.
            d = self.death_t
            fall = _smooth(0.0, 1.55, d)
            eye0 = self.death_eye0 or (
                PLAYER_POS[0], PLAYER_POS[1] + PLAYER_EYE, PLAYER_POS[2])
            eye = (eye0[0] + 0.12 * fall,
                   eye0[1] - 1.55 * fall,
                   eye0[2] - 0.20 * fall)
            yaw = self.death_yaw + 22.0 * fall
            pitch = self.death_pitch + 24.0 * fall
            fwd = _forward(yaw, pitch)
            tgt = v_add(eye, fwd)
            roll = 40.0 * fall + math.sin(d * 7.0) * 1.6 * (1.0 - fall)
            r.set_camera(eye, tgt, 68.0, roll=roll)
            return
        if self.volkov_failed:
            eye, yaw, pitch = self._eye()
            fwd = _forward(yaw, pitch)
            roll = 4.0 * (1.0 - _smooth(0.0, 1.2, self.fail_t))
            r.set_camera(eye, v_add(eye, fwd), 68, roll=roll)
            return
        if t < CUT_AT:
            eye, yaw, pitch = self._eye()
            fwd = _forward(yaw, pitch)
            tgt = v_add(eye, fwd)
            r.set_camera(eye, tgt, 68.0 - 14.0 * self.ads)
            return
        self._draw_cine_camera(r, t)

    def _cam(self, r, t, eye, tgt, fov, roll=0.0):
        """set_camera + the cinematic's impact jolt and breathing.  Both are
        deterministic sines of the dt clock and scale with reduced motion."""
        c = t - SHOT_AT
        tms = c * 1000.0
        hit_ms = (HIT_AT - SHOT_AT) * 1000.0
        dx, dy, sroll, _px = _fx.shake(tms, hit_ms, 520.0, 0.075)
        hh = 0.0
        if c >= CINE_SCOPE_END:
            hh = 0.010
        _fx.set_cam(r, tms, eye, tgt, fov, hh=hh, seed=7, roll=roll,
                    shk=(dx, dy, sroll, 0))

    def _draw_cine_camera(self, r, t):
        """Dedicated post-shot cinematic: tower, scope, impact, catch, doors."""
        c = t - SHOT_AT
        if c < CINE_TOWER_END:
            # Establish the signal tower and the sniper on it.  Framed on the
            # roof line, not the cabin: at 38 deg he was a speck on a black
            # slab, and the shot has to say who is holding the rifle.
            k = _smooth(0.0, CINE_TOWER_END, c)
            # Low and from the platform, looking UP at the cabin: the sniper
            # reads against the sky with the lit window behind him, and the
            # slow push-up-and-in makes the angle feel like a threat.
            eye = (10.4 + 0.9 * k, 2.55 + 0.25 * k, 4.6)
            self._cam(r, t, eye, (TOWER_KNEE[0] - 0.2 * k, TOWER_KNEE[1] + 0.40,
                               TOWER_KNEE[2]), 26 - 3 * k)
            return
        if c < CINE_SCOPE_END:
            # Down the scope: track Volkov's upper body.  Clamp tracking at
            # HIT_AT so the scope freezes on the impact.  The eye sits at the
            # cabin window: from inside the cabin, a cabin face wins the sort
            # and the shot is a grey disc.
            vt = min(SHOT_AT + c, HIT_AT)
            vpos_live = _volkov_at(vt, self.volkov_delay)[0]
            # Chest height - and the same height the round arrives at, so the
            # reticle sits on the point the story hits.
            tgt = (vpos_live[0], vpos_live[1] + 1.12, vpos_live[2])
            dh = t - HIT_AT
            if dh > 0.0:
                # The rifle kicks the glass up and the body buckles under it:
                # the view jumps, then drifts down after the falling chest
                # instead of freezing on an empty point.
                _p, _q, _y, vj = _volkov_death_state(t, self.volkov_delay)
                ch = vj["chest"]
                follow = _smooth(0.05, 0.30, dh)
                kick = 0.34 * math.exp(-dh / 0.07) * (1.0 - math.exp(-dh / 0.012))
                tgt = (tgt[0] + (ch[0] - tgt[0]) * follow,
                       tgt[1] + (ch[1] - tgt[1]) * follow + kick,
                       tgt[2] + (ch[2] - tgt[2]) * follow)
            # A slow breath on the eye: the same man is holding the shot, not
            # a locked-off tripod.
            sway = (0.03 * math.sin((t - SHOT_AT) * 1.7),
                    0.02 * math.sin((t - SHOT_AT) * 2.3 + 1.1))
            eye = (TOWER_EYE[0] + sway[0], TOWER_EYE[1],
                   TOWER_EYE[2] + sway[1])
            # 16 deg is a real spotter's lens: at 22 the subject was a
            # hand-sized figure on an empty bed of ballast.
            self._cam(r, t, eye, tgt, 16)
            return
        # From here the camera stands on the track side of the platform lip,
        # in front of the safety chain and clear of the gantry mast at
        # (13, 1.8).  The old platform-side eye looked THROUGH that chain:
        # a 3.9 m bar and a post crossed the body for the whole beat.
        if t >= HIT_AT:
            _vp, _vq, _vy, vj = _volkov_death_state(t, self.volkov_delay)
            chest, head = vj["chest"], vj["head"]
        else:
            vp = _volkov_at(min(t, HIT_AT - 0.01), self.volkov_delay)[0]
            chest = (vp[0], vp[1] + 1.0, vp[2])
            head = (vp[0], vp[1] + 1.65, vp[2])
        if c < CINE_CATCH_END:
            self._vigil_camera(r, t, c, chest, head)
            return
        # Reveal: cut wide on the door close so the carriage, its detail and
        # the window row are visible, then let it slide out behind the pair.
        k = _smooth(CINE_CATCH_END, DURATION - SHOT_AT, c)
        eye = (9.00 - 0.30 * k, 2.25 + 0.05 * k, 2.72 + 0.12 * k)
        tgt = (12.30, 1.05, -0.20)
        self._cam(r, t, eye, tgt, 60.0 + 4.0 * k)

    def _vigil_camera(self, r, t, c, chest, head):
        """The wordless vigil as a short cut sequence: a push-in on the pair,
        the cigarette in the snow, both faces, the bloody hand, then back out
        as Biribel looks up toward the tower."""
        if c < VIG_CIG_AT:
            # One continuous push-in from the track side.
            k = _smooth(CINE_SCOPE_END, VIG_CIG_AT, c)
            eye = (9.60 - 0.40 * k, 1.95 - 0.17 * k, 2.66 + 0.14 * k)
            live = (0.5 * (chest[0] + head[0]),
                    0.55 * chest[1] + 0.45 * head[1],
                    0.5 * (chest[2] + head[2]))
            k2 = _smooth(0.40, 5.00, c)
            rest = (11.65, 0.75, 0.64)
            tgt = tuple(live[i] * (1.0 - k2) + rest[i] * k2 for i in range(3))
            roll = 1.2 * (1.0 - _smooth(0.0, 0.45, t - HIT_AT))                 if t >= HIT_AT else 0.0
            self._cam(r, t, eye, tgt, 44.0 + 3.0 * k, roll=roll)
            return
        j = 0.5 * math.sin(c * 0.9)      # a hand-held breath on every insert
        if c < VIG_FACES_AT:
            # Insert: the cigarette smouldering in the snow beside his head.
            k = _smooth(VIG_CIG_AT, VIG_FACES_AT, c)
            cp = (head[0] - 0.28, _BALLAST_Y + 0.05, head[2] + 0.02)
            self._cam(r, t, (cp[0] - 0.75 + 0.12 * k, 0.36, cp[2] + 0.95),
                         (cp[0] + 0.04, cp[1] + 0.06, cp[2]), 30.0,
                         roll=0.8 * j)
            return
        if c < VIG_HAND_AT:
            # Both faces, close: the side key models them, the rim cuts them.
            k = _smooth(VIG_FACES_AT, VIG_HAND_AT, c)
            self._cam(r, t, (9.60 + 0.25 * k, 1.05 - 0.04 * k, 2.62 - 0.12 * k),
                         (11.72, 0.70, 0.78), 41.0 - 3.0 * k, roll=0.5 * j)
            return
        if c < VIG_BACK_AT:
            # Insert: the hand on the wound, then lifted, the print left behind.
            k = _smooth(VIG_HAND_AT, VIG_BACK_AT, c)
            self._cam(r, t, (10.95 + 0.1 * k, 1.18 - 0.04 * k, 1.30 + 0.05 * k),
                         (11.46, 0.50, 0.52), 34.0 - 2.0 * k, roll=0.6 * j)
            return
        # Out and wide as he looks up toward the tower.
        k = _smooth(VIG_BACK_AT, CINE_CATCH_END, c)
        self._cam(r, t, (9.20 - 0.2 * k, 1.90 + 0.10 * k, 2.72),
                     (11.90, 0.95, 0.50), 44.0 + 2.0 * k)

    def _train_offset(self, t=None):
        t = self.t if t is None else t
        if t <= DEPART_AT:
            return 0.0
        return _ease(clamp((t - DEPART_AT) / 4.6, 0.0, 1.0)) * 72.0

    def _draw_station(self, r, t):
        # Main depot building with recessed dark brickwork, roof trim, and pillars
        _w.add(r, box(19.0, 2.4, 3.2, (24, 27, 33), center=(7.0, 1.2, 10.6), seg=5))
        _w.add(r, box(19.2, 0.35, 3.3, (18, 20, 25), center=(7.0, 0.2, 10.6), seg=4))
        _w.add(r, box(19.8, 0.22, 3.9, (38, 42, 50), center=(7.0, 2.48, 10.4), seg=5))

        # Structural steel columns along the platform wall
        for px in (-1.5, 3.0, 7.5, 12.0, 15.5):
            _w.add(r, box(0.24, 2.4, 0.28, (32, 35, 42), center=(px, 1.2, 8.98)))

        # Illuminated departure board with frame
        _w.add(r, box(4.4, 1.12, 0.14, (36, 40, 48), center=(-4.8, 2.0, 9.04)))
        _w.add(r, box(4.1, 0.92, 0.10, (14, 18, 24), center=(-4.8, 2.0, 8.98), emissive=True))
        _w.add(r, box(3.6, 0.08, 0.08, (255, 190, 115), center=(-4.8, 2.28, 8.93), emissive=True))
        _w.add(r, box(2.4, 0.05, 0.08, (190, 210, 230), center=(-5.2, 1.95, 8.93), emissive=True))

        # Yellow tactile safety strip along the platform edge
        _w.add(r, box(34.0, 0.02, 0.16, (168, 134, 52), center=(2.0, _SLOT_GROUND + 0.01, 3.15), seg=6))

        # Platform bollards and a bench to break the long empty edge
        for px in (-7.5, -4.5, -1.5, 5.5, 8.5, 12.5):
            _w.add(r, box(0.16, 0.72, 0.16, (34, 36, 42), center=(px, _SLOT_GROUND + 0.36, 3.9)))
            _w.add(r, box(0.22, 0.08, 0.22, (58, 60, 66), center=(px, _SLOT_GROUND + 0.74, 3.9)))
        _w.add(r, box(1.8, 0.08, 0.45, (62, 54, 42), center=(-5.8, _SLOT_GROUND + 0.42, 6.6)))
        _w.add(r, box(0.12, 0.40, 0.12, (40, 42, 46), center=(-6.6, _SLOT_GROUND + 0.20, 6.6)))
        _w.add(r, box(0.12, 0.40, 0.12, (40, 42, 46), center=(-5.0, _SLOT_GROUND + 0.20, 6.6)))

        # A few suitcases waiting on the platform
        for sx, sz, sc in ((-7.1, 6.6, (58, 46, 38)), (-4.4, 6.2, (44, 52, 44)),
                           (2.2, 6.5, (52, 44, 40))):
            _w.add(r, box(0.42, 0.28, 0.24, sc, center=(sx, _SLOT_GROUND + 0.14, sz)))
            _w.add(r, box(0.30, 0.05, 0.06, (26, 26, 28), center=(sx, _SLOT_GROUND + 0.30, sz)))

        # Streetlamps with base post, overhang arm, and warm sodium fixture
        for x in (-10.0, 0.0, 10.0):
            _w.add(r, box(0.22, 0.45, 0.22, (28, 30, 36), center=(x, 0.22 + _SLOT_GROUND, 7.5)))
            _w.add(r, box(0.10, 3.6, 0.10, (36, 40, 46), center=(x, 1.8 + _SLOT_GROUND, 7.5)))
            _w.add(r, box(0.12, 0.08, 0.70, (36, 40, 46), center=(x, 3.62 + _SLOT_GROUND, 7.20)))
            _w.add(r, box(0.46, 0.14, 0.34, (255, 220, 165), center=(x, 3.56 + _SLOT_GROUND, 6.95), emissive=True))
            r.add_sprite((x, 3.50 + _SLOT_GROUND, 6.95),
                         _fx.sodium_lamp(t * 1000.0, seed=80 + int(x),
                                         radius_m=3.1, intensity=0.65),
                         layer=_fx.FX_LAYER)

        # Detailed cargo crates: wooden pallet base, main body, slat trim, and snow cap
        for idx, (cx, cz, hw, hd, top) in enumerate(_CRATES):
            h = top - _SLOT_GROUND
            # Dark pallet base
            _w.add(r, box(hw * 2 + 0.08, 0.10, hd * 2 + 0.08, (34, 28, 22),
                          center=(cx, _SLOT_GROUND + 0.05, cz)))
            # Crate body (alternating olive-drab military cases and dark wood)
            body_col = (48, 52, 44) if idx % 2 == 0 else (56, 44, 34)
            trim_col = (68, 72, 62) if idx % 2 == 0 else (76, 60, 46)
            _w.add(r, box(hw * 1.94, h - 0.14, hd * 1.94, body_col,
                          center=(cx, _SLOT_GROUND + 0.10 + (h - 0.14) * 0.5, cz), seg=2))
            # Reinforcing horizontal band & top lid
            _w.add(r, box(hw * 2.02, 0.10, hd * 2.02, trim_col,
                          center=(cx, _SLOT_GROUND + h * 0.55, cz)))
            _w.add(r, box(hw * 2.04, 0.08, hd * 2.04, trim_col,
                          center=(cx, top - 0.03, cz)))
            # Thin snow dusting on top of the crate
            _w.add(r, box(hw * 1.85, 0.03, hd * 1.85, (185, 195, 210),
                          center=(cx, top + 0.02, cz)))

        self._draw_platform_dressing(r, t)

    def _draw_platform_dressing(self, r, t):
        """The platform is a real station, not a corridor: a service catwalk
        for the marksman, a lit station wall, luggage and barriers in the
        foreground, and a freight yard beyond the carriage.  Everything here
        is authored cover/dressing - the fight paths stay in the open lanes.
        """
        from engine3d import Mesh
        m = Mesh()
        add = m.add
        G = _SLOT_GROUND

        # ── roof parapet along the station wall ────────────────────────
        for x in range(-14, 18, 2):
            add(box(0.06, 0.72, 0.06, (58, 62, 70), center=(x, 2.76, 9.00)))
        add(box(31.0, 0.06, 0.06, (72, 76, 84), center=(1.5, 3.12, 9.00)))
        add(box(31.0, 0.04, 0.04, (48, 52, 60), center=(1.5, 2.72, 9.00)))

        # ── canopy over the wall side, with hanging work lamps ─────────
        add(box(33.0, 0.20, 2.55, (28, 31, 38), center=(0.5, 4.05, 9.30), seg=8))
        add(box(33.0, 0.04, 2.35, (168, 178, 194), center=(0.5, 4.16, 9.30), seg=8))
        for x in (-15.0, -8.0, 0.0, 8.0, 16.0):
            add(box(0.14, 3.4, 0.14, (34, 38, 44), center=(x, 2.1, 10.35)))
            add(box(0.34, 0.10, 0.34, (46, 50, 58), center=(x, 3.52, 8.55)))
            add(box(0.20, 0.06, 0.20, (255, 220, 165), center=(x, 3.45, 8.55),
                    emissive=True))
            r.add_sprite((x, 3.42, 8.55),
                         _fx.sodium_lamp(t * 1000.0, seed=120 + int(x),
                                         radius_m=2.25, intensity=0.48),
                         layer=_fx.FX_LAYER)

        # ── left wing of the station: the dark behind the player ───────
        add(box(15.0, 2.0, 1.8, (22, 24, 30), center=(-9.6, 1.0, 10.7), seg=6))
        add(box(15.5, 0.16, 2.0, (42, 46, 54), center=(-9.6, 2.06, 10.7), seg=6))
        for wx in (-14.0, -10.5, -6.5):
            add(box(1.45, 0.64, 0.05, (255, 205, 145), center=(wx, 1.48, 9.78),
                    emissive=True))
            add(box(1.62, 0.80, 0.04, (38, 40, 46), center=(wx, 1.48, 9.81)))
            r.add_sprite((wx, 1.48, 9.74),
                         _fx.window_glow((255, 190, 122), 0.95, 0.60, 0.20),
                         layer=_fx.FX_LAYER)

        # ── station wall detail: windows, door, clock, posters, pipes ──
        for wx in (0.4, 4.0, 7.6, 11.2):
            add(box(1.55, 0.82, 0.05, (38, 40, 46), center=(wx, 1.55, 8.98)))
            add(box(1.38, 0.66, 0.03, (255, 212, 158), center=(wx, 1.55, 8.94),
                    emissive=True))
            add(box(1.46, 0.06, 0.04, (20, 22, 26), center=(wx, 1.90, 8.93)))
            add(box(1.46, 0.06, 0.04, (20, 22, 26), center=(wx, 1.20, 8.93)))
            r.add_sprite((wx, 1.55, 8.90),
                         _fx.window_glow((255, 192, 128), 1.05, 0.82, 0.18),
                         layer=_fx.FX_LAYER)
        # the Guard door and its gooseneck lamp
        add(box(1.25, 2.05, 0.10, (30, 34, 40), center=(14.6, 1.03, 8.96)))
        add(box(1.02, 1.76, 0.05, (44, 48, 56), center=(14.6, 0.98, 8.91)))
        add(box(0.72, 1.40, 0.03, (255, 205, 140), center=(14.6, 1.02, 8.88),
                emissive=True))
        add(box(0.10, 0.10, 0.34, (36, 40, 48), center=(14.6, 2.26, 8.72)))
        add(box(0.30, 0.08, 0.26, (255, 222, 168), center=(14.6, 2.18, 8.58),
                emissive=True))
        r.add_sprite((14.6, 2.15, 8.55),
                     _fx.sodium_lamp(t * 1000.0, seed=133, radius_m=1.5,
                                     intensity=0.55),
                     layer=_fx.FX_LAYER)
        # station clock
        add(box(0.58, 0.58, 0.06, (18, 20, 24), center=(6.4, 2.06, 8.96)))
        add(box(0.46, 0.46, 0.03, (238, 230, 202), center=(6.4, 2.06, 8.92),
                emissive=True))
        add(box(0.035, 0.17, 0.02, (20, 22, 26), center=(6.4, 2.12, 8.90)))
        add(box(0.13, 0.035, 0.02, (20, 22, 26), center=(6.46, 2.06, 8.90)))
        # faded printed notices
        for px, pc in ((2.0, (122, 54, 46)), (10.8, (44, 72, 98))):
            add(box(0.96, 0.66, 0.04, (36, 38, 44), center=(px, 1.28, 8.96)))
            add(box(0.82, 0.54, 0.02, pc, center=(px, 1.28, 8.93)))
        # conduits and wall pipes
        for px in (1.2, 9.4, 13.2):
            add(box(0.07, 1.78, 0.07, (48, 52, 60), center=(px, 1.32, 8.92)))
        add(box(18.0, 0.07, 0.07, (44, 48, 56), center=(7.0, 2.26, 8.92)))
        add(box(18.0, 0.14, 0.16, (156, 166, 182), center=(7.0, 0.66, 8.86)))

        # ── foreground furniture: luggage, bench, bins, ticket machine ─
        # luggage trolley, right where the player is standing at the start
        add(box(1.92, 0.10, 0.92, (52, 48, 42), center=(-8.8, 0.86, 6.45)))
        for wx, wz in ((-9.62, 6.10), (-9.62, 6.80), (-7.98, 6.10), (-7.98, 6.80)):
            add(box(0.10, 0.52, 0.10, (34, 36, 40), center=(wx, 0.55, wz)))
        add(box(0.08, 1.12, 0.08, (34, 36, 40), center=(-7.92, 1.06, 6.45)))
        add(box(0.08, 0.08, 0.74, (34, 36, 40), center=(-7.92, 1.60, 6.45)))
        add(box(0.66, 0.38, 0.42, (58, 46, 38), center=(-8.92, 1.12, 6.45)))
        add(box(0.55, 0.27, 0.36, (44, 52, 44), center=(-8.78, 1.44, 6.45)))
        add(box(0.62, 0.03, 0.40, (184, 192, 206), center=(-8.78, 1.58, 6.45)))
        # bench against the wall
        add(box(2.25, 0.10, 0.55, (62, 54, 42), center=(2.6, 1.05, 6.85)))
        add(box(2.25, 0.52, 0.08, (62, 54, 42), center=(2.6, 1.39, 7.10)))
        for bx in (1.65, 3.55):
            add(box(0.09, 0.55, 0.42, (40, 42, 46), center=(bx, 0.82, 6.85)))
        add(box(2.25, 0.03, 0.50, (178, 188, 204), center=(2.6, 1.11, 6.85)))
        # bin and newspaper box
        add(box(0.46, 0.78, 0.46, (38, 48, 42), center=(7.4, 0.97, 6.82)))
        add(box(0.54, 0.08, 0.54, (30, 36, 32), center=(7.4, 1.38, 6.82)))
        add(box(0.48, 0.03, 0.48, (176, 186, 202), center=(7.4, 1.43, 6.82)))
        add(box(0.52, 1.12, 0.44, (40, 58, 84), center=(10.3, 1.14, 6.88)))
        add(box(0.40, 0.34, 0.02, (228, 232, 226), center=(10.3, 1.26, 6.65),
                emissive=True))
        # ticket machine by the Guard door
        add(box(0.96, 1.78, 0.56, (46, 52, 60), center=(12.6, 1.47, 8.42)))
        add(box(0.62, 0.38, 0.04, (120, 190, 176), center=(12.6, 1.66, 8.12),
                emissive=True))
        add(box(0.52, 0.10, 0.05, (228, 190, 116), center=(12.6, 1.20, 8.12),
                emissive=True))
        add(box(0.42, 0.03, 0.42, (174, 184, 200), center=(12.6, 2.37, 8.42)))

        # ── platform edge: safety posts and chains, snow drifts ───────
        for x in (-16.0, -12.0, -8.0, -4.0, 0.0, 4.0, 8.0, 12.0, 16.0):
            add(box(0.09, 0.94, 0.09, (44, 46, 52), center=(x, G + 0.47, 3.0)))
            add(box(0.17, 0.05, 0.17, (64, 66, 72), center=(x, G + 0.96, 3.0)))
        for x in range(-14, 16, 4):
            add(box(3.88, 0.035, 0.035, (70, 72, 78), center=(x, G + 0.70, 3.0)))
        for i, x in enumerate((-19.0, -15.0, -11.0, -7.0, -3.0, 1.0, 5.0, 9.0, 13.0, 17.0)):
            add(box(2.6, 0.14 + 0.03 * (i % 3), 0.52, (158, 168, 184),
                    center=(x, G + 0.07 + 0.015 * (i % 3), 2.92), seg=2))
        # stacked pallets / sleepers at the east end
        for i in range(4):
            add(box(1.9, 0.10, 0.62, (44, 36, 28) if i % 2 else (54, 46, 34),
                    center=(18.2 - i * 0.10, G + 0.05 + i * 0.11, 5.9 + i * 0.06)))
        add(box(1.94, 0.03, 0.64, (174, 184, 200),
                center=(17.9, G + 0.48, 6.1)))

        # ── the yard beyond the carriage: silhouettes, gantries, wires ─
        add(box(2.0, 3.4, 1.6, (24, 27, 33), center=(26.0, 1.7, -9.2)))
        add(box(0.12, 5.2, 0.12, (30, 34, 40), center=(28.0, 2.6, -7.2)))
        add(box(0.52, 0.20, 0.52, (235, 60, 40), center=(28.0, 5.24, -7.2),
                emissive=True))
        r.add_sprite((28.0, 5.24, -7.2), _fx.glow((240, 70, 50), 1.4,
                                                 t * 1000.0, intensity=0.75),
                     layer=_fx.FX_LAYER)
        for gx in (-7.0, 13.0):
            add(box(0.18, 6.3, 0.18, (36, 40, 48), center=(gx, 3.15, 1.8)))
            add(box(0.18, 6.3, 0.18, (36, 40, 48), center=(gx, 3.15, -7.2)))
            add(box(0.16, 0.16, 9.2, (36, 40, 48), center=(gx, 6.25, -2.7)))
            add(box(0.50, 0.34, 0.30, (255, 228, 178), center=(gx, 6.02, -2.7),
                    emissive=True))
        # layer 2, not 0: every box face in this scene is painter layer 2, so
        # a layer-0 wire sorts behind the whole world - including the sky-side
        # carriage it is strung over - and the gantry run read as bare masts.
        for wz in (-1.5, 1.5):
            r.add_line3d((-30.0, 6.02, wz), (-7.0, 6.02, wz), (44, 48, 58), 1, layer=2)
            r.add_line3d((-7.0, 6.02, wz), (13.0, 6.02, wz), (44, 48, 58), 1, layer=2)
            r.add_line3d((13.0, 6.02, wz), (30.0, 6.02, wz), (44, 48, 58), 1, layer=2)

        # ── far yard silhouette ──────────────────────────────────────
        # Read the SKY_HORIZON / YARD_DARK note at the top of the module
        # before changing a colour down here.  Everything in this block is
        # authored DARKER than the sky and lifts with distance: the fog
        # colour is the sky colour, so a mass that is lighter than the
        # backdrop can only converge to it.
        def far_col(d):
            k = clamp((d - 26.0) / 44.0, 0.0, 1.0)
            return tuple(int(YARD_DARK[i] + (YARD_HAZY[i] - YARD_DARK[i]) * k)
                         for i in range(3))

        def far_dist(px, pz):
            return math.hypot(px - PLAYER_POS[0], pz - PLAYER_POS[2])

        # A ridge seals the horizon: between the masses the sky used to meet
        # the ballast on a ruled, empty edge.  Axis-aligned blocks on a ring
        # around the eye - no rotation, so no handedness to get wrong.
        ridge_col = far_col(_YARD_RIDGE_R)
        for i in range(0, 17, 2):  # every other ridge for performance
            a = math.radians(-56.0 + i * 12.0)
            rx = PLAYER_POS[0] + _YARD_RIDGE_R * math.sin(a)
            rz = PLAYER_POS[2] - _YARD_RIDGE_R * math.cos(a)
            rh = 3.0 + 1.1 * _vm_noise(rx, 0.0, rz, 3)
            add(box(19.0, rh, 14.0, ridge_col,
                    center=(rx, rh * 0.5 - 0.6, rz), skip=("bottom", "back")))

        # Warehouses, sheds and silos across the yard.
        # View cull: skip masses outside the player's reachable yaw range
        base_yaw = BASE_YAW
        yaw_limit = YAW_LIMIT + 10  # extra margin for safety
        for sx, sz, sw, sh, sd, rows, cols in _YARD_MASSES:
            # Check if mass is within view frustum
            dx = sx - PLAYER_POS[0]
            dz = sz - PLAYER_POS[2]
            if abs(dx) + abs(dz) < 1e-6:
                continue
            mass_yaw = math.degrees(math.atan2(dx, -dz))
            # Normalize yaw difference
            dyaw = (mass_yaw - base_yaw + 180) % 360 - 180
            if abs(dyaw) > yaw_limit:
                continue  # mass is behind the player
            add(box(sw, sh, sd, far_col(far_dist(sx, sz)),
                    center=(sx, sh * 0.5, sz), skip=("bottom", "back")))
            # Lit windows are the only thing out here allowed to be bright:
            # emissive, so the distance fog is all that dims them, and large
            # enough (0.66 m) to survive RES=0.80 plus the smoothscale.
            face = sz + sd * 0.5 + 0.04
            for ry in range(rows):
                wy = sh * (0.30 + 0.22 * ry)
                for ci in range(cols):
                    wx = sx + sw * (-0.34 + 0.68 * ci / max(1, cols - 1))
                    n = _vm_noise(wx, wy, sz, 5)
                    if n < 0.58:  # higher threshold = fewer windows
                        continue
                    add(box(0.66, 0.46, 0.06,
                            (236, 190, 124) if n > 0.62 else (150, 128, 96),
                            center=(wx, wy, face), emissive=True))
            if sh >= 9.0:
                add(box(0.26, 0.26, 0.26, (228, 56, 42),
                        center=(sx + sw * 0.34, sh + 0.18, sz), emissive=True))

        # Chimney stacks: vertical breaks in a horizon of flat-topped boxes.
        for cx_s, cz_s, ch in _YARD_STACKS:
            add(box(0.9, ch, 0.9, far_col(far_dist(cx_s, cz_s)),
                    center=(cx_s, ch * 0.5, cz_s), skip=("bottom", "back")))
            add(box(0.30, 0.30, 0.30, (228, 56, 42),
                    center=(cx_s, ch + 0.2, cz_s), emissive=True))

        for fx, fz in ((-22.0, -14.0), (30.0, -13.0)):
            add(box(0.14, 6.4, 0.14, (32, 36, 44), center=(fx, 3.2, fz)))
            add(box(0.55, 0.24, 0.35, (255, 226, 176), center=(fx, 6.45, fz),
                    emissive=True))

        self._yard_sprites(r, t * 1000.0)

        # ── atmosphere: window spill, steam, a warming barrel ─────────
        r.add_sprite((5.6, G + 0.25, 6.15),
                     _fx.haze((190, 200, 214), 1.9, t * 1000.0, seed=137,
                              intensity=0.10),
                     layer=_fx.FX_LAYER)
        add(box(0.62, 0.03, 0.62, (28, 30, 34), center=(5.6, G + 0.015, 6.15)))
        add(box(0.50, 0.06, 0.50, (34, 36, 40), center=(-18.2, G + 0.10, 8.55)))
        add(box(0.58, 0.78, 0.58, (42, 38, 34), center=(-18.2, G + 0.48, 8.55)))
        add(box(0.44, 0.08, 0.44, (255, 120, 54), center=(-18.2, G + 0.90, 8.55),
                emissive=True))
        r.add_sprite((-18.2, G + 1.05, 8.55),
                     _fx.glow((255, 140, 66), 1.7, t * 1000.0, flicker=0.16,
                              seed=139, intensity=0.55),
                     layer=_fx.FX_LAYER)
        r.add_sprite((-18.2, G + 1.32, 8.55),
                     _fx.cig_smoke(t * 1000.0, seed=139, drift=(0.10, -0.42),
                                   intensity=0.16, life_ms=3200),
                     layer=_fx.FX_LAYER)

        # Baked geometry loses the per-frame point-light pools, so put the
        # warm spill back as depth-masked floor sprites under each lamp.
        # These are ADDITIVE: the old rig stacked eleven overlapping pools and
        # the platform came out one flat beige sheet with no dark between the
        # lamps.  Fewer, tighter, dimmer - the pools have to read as pools.
        for lx in (-13.0, -9.0, 0.0, 9.0):
            r.add_sprite((lx, G + 0.055, 6.10),
                         _fx.window_glow((255, 184, 116), 3.0, 0.92, 0.36,
                                         t * 1000.0, seed=151 + int(lx)),
                         layer=_fx.FX_LAYER)
            r.add_sprite((lx, G + 0.05, 3.55),
                         _fx.window_glow((255, 176, 108), 1.8, 0.54, 0.17,
                                         t * 1000.0, seed=181 + int(lx)),
                         layer=_fx.FX_LAYER)
        for lx in (-6.0, 8.0):
            r.add_sprite((lx, G + 0.05, 7.0),
                         _fx.window_glow((255, 190, 126), 1.7, 0.55, 0.20,
                                         t * 1000.0, seed=160 + int(lx)),
                         layer=_fx.FX_LAYER)
        r.add_sprite((10.9, G + 0.06, 3.2),
                     _fx.window_glow((255, 172, 102), 2.0, 0.66, 0.26,
                                     t * 1000.0, seed=171),
                     layer=_fx.FX_LAYER)

        _w.add(r, m)

    def _yard_sprites(self, r, tm):
        """Beacons and light pollution for the far yard.

        Called from BOTH ``_draw_platform_dressing`` (the bake frame) and
        ``_draw_static_lights`` (every other frame).  Geometry is cached by
        ``static_scene``; sprites are not, so a sprite queued only in the
        dressing pass exists on exactly one frame of the whole scene.
        """
        for sx, sz, sw, sh, _sd, _rows, _cols in _YARD_MASSES:
            if sh < 9.0:
                continue
            r.add_sprite((sx + sw * 0.34, sh + 0.18, sz),
                         _fx.glow((236, 64, 48), 0.9, tm, flicker=0.14,
                                  seed=400 + int(sx), intensity=0.85),
                         layer=_fx.FX_LAYER)
        for cx_s, cz_s, ch in _YARD_STACKS:
            r.add_sprite((cx_s, ch + 0.2, cz_s),
                         _fx.glow((236, 64, 48), 1.0, tm, flicker=0.18,
                                  seed=430 + int(cx_s), intensity=0.9),
                         layer=_fx.FX_LAYER)
        # A cold band over the yard.  It separates the silhouettes from the
        # sky without lighting them - the masses must stay darker than it.
        for hx, hy, hz in _YARD_HAZE:
            r.add_sprite((hx, hy, hz),
                         _fx.haze((104, 132, 182), 15.0, tm,
                                  seed=460 + int(hx), intensity=0.085),
                         layer=_fx.FX_LAYER)

    def _draw_static_lights(self, r, t):
        """Animated sprites for the baked set (lamps, window spill, snow).

        Geometry is cached by ``static_scene``; these callbacks change with
        the clock, so they are queued every frame.
        """
        tm = t * 1000.0
        G = _SLOT_GROUND
        # waiting-train windows: cluster glows, door spill, rear marker
        for x in (-12.0, 0.0, 9.0, 15.0, 21.0):
            r.add_sprite((x, 2.45, -2.80),
                         _fx.window_glow((255, 198, 128), 4.2, 1.2, 0.20),
                         layer=_fx.FX_LAYER)
        for x in (6.0, 11.0, 16.0):
            r.add_sprite((x, 0.10, -2.45),
                         _fx.window_glow((255, 180, 110), 2.4, 0.6, 0.16),
                         layer=_fx.FX_LAYER)
        r.add_sprite((TRAIN_DOOR_X, 1.85, -2.80),
                     _fx.window_glow((255, 196, 130), 1.2, 1.4, 0.22),
                     layer=_fx.FX_LAYER)
        r.add_sprite((-23.02, 2.0, -2.80),
                     _fx.glow((228, 56, 42), 0.35, tm, intensity=0.55),
                     layer=_fx.FX_LAYER)
        # floodlight masts
        for i, x in enumerate((-18.0, -6.0, 6.0, 18.0)):
            r.add_sprite((x, 8.0, 11.3),
                         _fx.sodium_lamp(tm, seed=50 + i, radius_m=3.6,
                                         intensity=0.55),
                         layer=_fx.FX_LAYER)
            r.add_sprite((x, 0.6, 8.0),
                         _fx.haze((220, 210, 190), 4.0, tm, seed=50 + i,
                                  intensity=0.10),
                         layer=_fx.FX_LAYER)
        # street lamps
        for x in (-10.0, 0.0, 10.0):
            r.add_sprite((x, 3.50 + G, 6.95),
                         _fx.sodium_lamp(tm, seed=80 + int(x), radius_m=3.1,
                                         intensity=0.65),
                         layer=_fx.FX_LAYER)
        # canopy work lamps
        for x in (-15.0, -8.0, 0.0, 8.0, 16.0):
            r.add_sprite((x, 3.42, 8.55),
                         _fx.sodium_lamp(tm, seed=120 + int(x),
                                         radius_m=2.25, intensity=0.48),
                         layer=_fx.FX_LAYER)
        # station windows + left-wing windows
        for wx in (0.4, 4.0, 7.6, 11.2):
            r.add_sprite((wx, 1.55, 8.90),
                         _fx.window_glow((255, 192, 128), 1.05, 0.82, 0.18),
                         layer=_fx.FX_LAYER)
        for wx in (-14.0, -10.5, -6.5):
            r.add_sprite((wx, 1.48, 9.74),
                         _fx.window_glow((255, 190, 122), 0.95, 0.60, 0.20),
                         layer=_fx.FX_LAYER)
        r.add_sprite((14.6, 2.15, 8.55),
                     _fx.sodium_lamp(tm, seed=133, radius_m=1.5, intensity=0.55),
                     layer=_fx.FX_LAYER)
        r.add_sprite((28.0, 5.24, -7.2),
                     _fx.glow((240, 70, 50), 1.4, tm, intensity=0.75),
                     layer=_fx.FX_LAYER)
        r.add_sprite((5.6, G + 0.25, 6.15),
                     _fx.haze((190, 200, 214), 1.9, tm, seed=137,
                              intensity=0.10),
                     layer=_fx.FX_LAYER)
        r.add_sprite((-18.2, G + 1.05, 8.55),
                     _fx.glow((255, 140, 66), 1.7, tm, flicker=0.16,
                              seed=139, intensity=0.55),
                     layer=_fx.FX_LAYER)
        r.add_sprite((-18.2, G + 1.32, 8.55),
                     _fx.cig_smoke(tm, seed=139, drift=(0.10, -0.42),
                                   intensity=0.16, life_ms=3200),
                     layer=_fx.FX_LAYER)
        # floor spill (replaces the point lights lost to the static bake) -
        # must stay in step with _draw_platform_dressing
        for lx in (-13.0, -9.0, 0.0, 9.0):
            r.add_sprite((lx, G + 0.055, 6.10),
                         _fx.window_glow((255, 184, 116), 3.0, 0.92, 0.36,
                                         tm, seed=151 + int(lx)),
                         layer=_fx.FX_LAYER)
            r.add_sprite((lx, G + 0.05, 3.55),
                         _fx.window_glow((255, 176, 108), 1.8, 0.54, 0.17,
                                         tm, seed=181 + int(lx)),
                         layer=_fx.FX_LAYER)
        for lx in (-6.0, 8.0):
            r.add_sprite((lx, G + 0.05, 7.0),
                         _fx.window_glow((255, 190, 126), 1.7, 0.55, 0.20,
                                         tm, seed=160 + int(lx)),
                         layer=_fx.FX_LAYER)
        r.add_sprite((10.9, G + 0.06, 3.2),
                     _fx.window_glow((255, 172, 102), 2.0, 0.66, 0.26, tm,
                                     seed=171),
                     layer=_fx.FX_LAYER)
        self._yard_sprites(r, tm)
        _w.snow3d(r, tm, seed=61, n=60, spread=22, height=16, speed=1.3)

    def _draw_train_door(self, r, t):
        tx = self._train_offset(t)
        closed = _smooth(DOORS_AT, DOORS_AT + 1.0, t)
        dx = TRAIN_DOOR_X + tx
        z = -2.83
        if closed < 0.98:
            # The warm vestibule is real now; this is only the doorway spill.
            r.add_sprite((dx, 1.9, z + 0.02),
                         _fx.window_glow((255, 196, 130), 1.15, 1.4, 0.24),
                         layer=_fx.FX_LAYER)
        if closed > 0.02:
            # two leaves meet at the seam; the last 20 cm lands with the clunk
            off = 0.72 * (1.0 - closed)
            for side in (-1, 1):
                cx = dx + side * (0.36 + off)
                _w.add(r, box(0.78, 1.62, 0.06, (46, 48, 54),
                              center=(cx, 1.85, z + 0.01)))
                _w.add(r, box(0.26, 0.32, 0.03, (255, 214, 158),
                              center=(cx, 2.32, z + 0.045), emissive=True))
                _w.add(r, box(0.04, 0.88, 0.05, (28, 30, 34),
                              center=(cx - side * 0.30, 1.62, z + 0.05)))
                _w.add(r, box(0.03, 0.30, 0.05, (130, 130, 134),
                              center=(cx - side * 0.31, 1.50, z + 0.06)))
        # grab rails either side of the opening
        for side in (-1, 1):
            _w.add(r, box(0.035, 0.90, 0.035, (150, 150, 150),
                          center=(dx + side * 0.86, 1.55, z + 0.04)))
        # the step Volkov never reaches
        _w.add(r, box(1.1, 0.16, 0.55, (72, 70, 66),
                      center=(dx, 0.30, z + 0.42)))
        _w.add(r, box(1.1, 0.42, 0.12, (44, 44, 48),
                      center=(dx, 0.12, z + 0.68)))

    def _draw_volkov(self, r, t):
        if self.volkov_failed:
            pos = self.fail_pos or _volkov_at(SHOT_AT, self.volkov_delay)[0]
            fstate = self._fstate or _volkov_fail_state(
                self.fail_t, t, pos, self.fail_yaw, self.volkov_delay)
            pos, pose, yaw, _j = fstate
            _w.actor(r, "volkov", pose, pos, yaw, int(t * 1000),
                     seed=91, amp=0.0, rifle_on=False, expression="sad",
                     hd=True, wound=2 if self.fail_t >= 0.5 else 0)
            return
        if t >= HIT_AT:
            vstate = self._vstate or _volkov_death_state(t, self.volkov_delay)
            pos, pose, yaw, _j = vstate
            expr = "surprised" if t - HIT_AT < 0.45 else "sad"
            _w.actor(r, "volkov", pose, pos, yaw, int(t * 1000),
                     seed=91, amp=0.0, rifle_on=False, expression=expr,
                     hd=True, wound=_wound_stage(t - HIT_AT),
                     flags=_volkov_flags(t - HIT_AT))
            return
        vt = t
        (x, y, z), mode, phase = _volkov_at(vt, self.volkov_delay)
        pose = _volkov_pose(mode, phase, vt)
        if self.volkov_pinned and mode == "cover":
            pose = dict(POSES["cover_tight"])
        (nx, _ny, nz), _m2, _p2 = _volkov_at(
            min(vt + 0.25, DURATION), self.volkov_delay)
        yaw = _w.yaw_to((x, 0.0, z), (nx, 0.0, nz)) if mode == "run" else \
            _w.yaw_to((x, 0.0, z), (TRAIN_DOOR_X, 0.0, -2.0))
        _w.actor(r, "volkov", pose, (x, y, z), yaw, int(vt * 1000),
                 seed=91, amp=0.5, hd=True, shadow=_shadow_for(z))
        if t > 8.0:
            r.add_sprite((x, y + 1.58, z),
                         _w.breath((x, y, z), t * 1000, seed=92, intensity=0.18),
                         layer=_fx.FX_LAYER)

    def _draw_guards(self, r, t):
        if t >= CUT_AT:
            return
        eye = self._eye()[0]
        for g in self.guards:
            if not g.get("active"):
                continue
            x, y, z = g["pos"]
            yaw = _w.yaw_to((x, 0.0, z), (eye[0], 0.0, eye[2]))
            kind = g.get("kind", "rifle")
            key = ("guard", kind)
            prof = _guard_profile(kind)
            if g.get("alive"):
                rise = _smooth(g.get("spawn_t", -9.0),
                               g.get("spawn_t", -9.0) + 0.45, t)
                if g.get("moving"):
                    # The heavy is a trudge; the breacher/officer sprint.
                    rate = 4.2 if kind == "heavy" else (
                        9.0 if kind in ("rusher", "officer") else 7.0)
                    lean = 6 if kind == "heavy" else (
                        22 if kind in ("rusher", "officer") else 14)
                    pose = pose_run(t * rate + g["slot"] * 1.7, lean=lean)
                else:
                    pose = dict(POSES.get(prof.get("idle", "cover"),
                                          POSES["cover"]))
                    if int(g.get("burst_left", 0)) > 0:
                        pose = blend(pose, "aim", 0.72)
                    if rise < 1.0:
                        pose = blend("crouch", pose, rise)
                if g.get("flinch", 0.0) > 0 and kind != "marksman":
                    amp = 1.0 if kind != "heavy" else 0.45
                    pose = dict(pose, spine=pose.get("spine", 8) + 14 * amp,
                                head_p=pose.get("head_p", 6) + 10 * amp)
                # Face where he is going while he runs, at the player while he
                # holds or fires; the heading eases instead of snapping.
                face = yaw
                if g.get("moving") and int(g.get("burst_left", 0)) <= 0:
                    px, pz = g.get("_dp", (x, z))
                    if math.hypot(x - px, z - pz) > 1e-4:
                        g["_mv"] = _w.yaw_to((px, 0.0, pz), (x, 0.0, z))
                    face = g.get("_mv", yaw)
                g["_dp"] = (x, z)
                yaw = _w.yaw_mix(g.get("_yaw", face), face, 0.22)
                g["_yaw"] = yaw
                stag = max(0.0, 1.0 - (t - g.get("hit_t", -9.0)) / 0.32)
                if stag > 0.0 and g.get("hit_dir"):
                    amp = (0.5 if kind == "heavy" else 1.0) * stag
                    pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * amp,
                                head_p=pose.get("head_p", 6) - 8.0 * amp)
                    bump = 0.10 * amp * math.sin(math.pi * (1.0 - stag))
                    x += g["hit_dir"][0] * bump
                    z += g["hit_dir"][1] * bump
                joints = _w.actor(r, key, pose, (x, y, z), yaw,
                                  int(t * 1000), seed=100 + g["slot"],
                                  amp=0.4, rifle_on=True, hd=True,
                                  shadow=_shadow_for(z))
                # IFF strobe on the shoulder: the roster reads at distance
                # even when every silhouette is a dark shape in the snow.
                lamp = prof.get("lamp")
                if lamp:
                    r.add_sprite((x + 0.16, y + 1.52, z + 0.03),
                                 _fx.glow(lamp, 0.19, t * 1000.0,
                                          flicker=0.08, seed=210 + g["slot"],
                                          intensity=0.95),
                                 layer=_fx.FX_LAYER)
                if 0.0 <= t - g.get("spawn_t", -9.0) < 0.5:
                    r.add_sprite((x, y + 0.18, z),
                                 _fx.dust_motes(int((t - g["spawn_t"]) * 1000.0),
                                                seed=300 + g["slot"], count=14,
                                                spread_m=(0.9, 0.7),
                                                col=(178, 190, 208)),
                                 layer=_fx.FX_LAYER)
                muzzle = joints.get("muzzle")
                if muzzle is not None:
                    # Telegraph: a brief glow before each scheduled burst and
                    # between the rounds of one, so the heavy/marksman read
                    # before they hit.
                    fire = g.get("fire") or ()
                    nf = int(g.get("next_fire", 0))
                    next_t = fire[nf] if nf < len(fire) else 1e9
                    telegraph = float(prof.get("telegraph", 0.25))
                    burst_due = (int(g.get("burst_left", 0)) > 0
                                 and g.get("burst_next", 1e9) - t <= 0.10)
                    if (0.0 <= next_t - t <= telegraph) or burst_due:
                        r.add_sprite(muzzle,
                                     _fx.glow((255, 210, 150),
                                              0.38 if kind != "marksman" else 0.30,
                                              t * 1000, intensity=0.9),
                                     layer=_fx.FX_LAYER)
                    if t - g.get("last_shot_t", -9.0) < 0.055:
                        r.add_sprite(muzzle,
                                     _fx.flash(0, col=(255, 224, 166),
                                               radius_m=0.30, dur_ms=60),
                                     layer=_fx.FX_LAYER)
            else:
                a = t - g.get("dead_t", -9.0)
                track = int(g.get("track", 0))
                # He falls where he stood, facing the way he was facing when
                # the round landed: the yaw no longer tracks the player.
                hum = _hum(key)
                dyaw0 = g.get("dead_yaw", yaw)
                if g.get("dead_land") is None:
                    g["dead_land"] = _guard_landing(hum, track, (x, y, z), dyaw0)
                pose, root, dyaw, floor = _guard_body(
                    hum, track, a, (x, y, z), dyaw0, g["dead_land"])
                try:
                    r.add_humanoid(hum, pose, root, dyaw,
                                   rifle_on=False, shadow=_shadow_for(root[2]))
                except Exception:
                    pass
                pool = _smooth(0.40, 2.60, a)
                if pool > 0.0:
                    # under the chest, not the pelvis: that is where he bleeds
                    _pl, dj, _r = hum.pose_world(pose, root, dyaw, rifle_on=False)
                    cx, cz = dj["chest"][0], dj["chest"][2]
                    wob = (1.0, 0.85, 1.12, 0.92, 1.15, 0.88, 1.06, 0.95)
                    _w.add(r, disc_xz(cx, cz, 0.08 + 0.26 * pool, floor + 0.010,
                                      (58, 8, 12), n=8,
                                      layer=3 if floor > 0.3 else 1, wobble=wob))

    def _draw_ucilev(self, r, t):
        """The signal-tower sniper, visible for the establishing shot."""
        c = t - SHOT_AT
        if c < 0.0 or c >= CINE_TOWER_END:
            return
        pos = TOWER_KNEE
        yaw = _w.yaw_to(pos, (11.2, 1.0, 1.0))
        pose = dict(POSES["kneel"])
        _w.actor(r, "ucilev", pose, pos, yaw, int(t * 1000), seed=95,
                 amp=0.20, rifle_on=True, hd=True)

    def _draw_biribel(self, r, t):
        if self.dying or self.volkov_failed or t < SHOT_AT:
            return
        c = t - SHOT_AT
        if c < 3.05:
            return
        vstate = self._vstate or _volkov_death_state(t, self.volkov_delay)
        state = self._bstate or _biribel_catch_state(t, vstate)
        if state is None:
            return
        pos, yaw, pose = state
        expr = "worried" if c < 3.60 else "sad"
        # Biribel's gloves go red once his hand is on the wound.
        _w.actor(r, ("biribel", OUTFIT_GUARD), pose, pos, yaw,
                 int(t * 1000), seed=93, amp=0.0, expression=expr,
                 hd=True, bloody=c >= 4.3)

    def _vm_setup(self):
        """Resolve the held-weapon frame (GL: K93D asset, software: K9).

        ADS blends the low-ready hold onto the sight axis: the gun's own
        sight point (from the GLB nodes) is placed on the eye ray, the mouse
        gain tightens with the zoom, and recoil is damped.
        """
        asset = None
        if getattr(_renderer(), "backend", "") == "gl":
            asset = _viewmodel_asset()
        p = self.reload_progress() if self.reloading else 1.0
        if asset is not None:
            mesh, sight, muzzle, mag_shift, glass_size, reticle = asset
            k = 1.0
        else:
            mesh = _vm_mesh(self.reloading, p)
            sight = (0.0, 0.135, 0.070)
            muzzle = (0.0, 0.035, VM_MUZZLE_Z)
            mag_shift = None
            glass_size = None
            reticle = None
            k = 0.92

        eye, yaw, pitch = self._eye()
        fwd = _forward(yaw, pitch)
        # NOTE: the renderer's camera right is the NEGATIVE of ``_right(yaw)``.
        # The viewmodel used ``_right`` directly, which put a right-handed
        # low-ready hold on the left of the screen with the muzzle converging
        # back across the crosshair - the biggest reason the gun read wrong.
        rgt = _right(yaw)
        rgt = (-rgt[0], -rgt[1], -rgt[2])
        up = (fwd[1] * rgt[2] - fwd[2] * rgt[1],
              fwd[2] * rgt[0] - fwd[0] * rgt[2],
              fwd[0] * rgt[1] - fwd[1] * rgt[0])

        a = 0.0 if self.reloading else self.ads
        # Breathing and recoil settle as the sight comes up.
        motion = self._motion() * (1.0 - 0.70 * a)
        breath_y = 0.008 * math.sin(self.t * 2.4) * motion
        breath_x = 0.005 * math.cos(self.t * 1.2) * motion
        kick_back = 0.085 * self.kick * (1.0 - 0.45 * a)
        kick_up = 0.030 * self.kick * (1.0 - 0.45 * a)

        down = _smooth(0.0, 0.18, p) * (1.0 - _smooth(0.78, 1.0, p))
        jolt = math.sin(clamp((p - RMAG_IN) / 0.08, 0, 1) * math.pi) * 0.04
        bolt = 0.0
        if self.reloading and self.reload_empty:
            bolt = math.sin(clamp((p - 0.72) / 0.12, 0, 1) * math.pi) * 0.05
        dip = 0.15 * down + jolt
        roll = 26.0 * down

        fwd_dist = 0.55 + (0.50 - 0.55) * a - kick_back - 0.06 * down - bolt
        right_off = 0.165 * (1.0 - a) + breath_x - 0.05 * down
        sight_y = sight[1] * k
        up_off = 0.240 + (sight_y - 0.240) * a + dip - kick_up + breath_y

        origin = (
            eye[0] + fwd[0] * fwd_dist + rgt[0] * right_off - up[0] * up_off,
            eye[1] + fwd[1] * fwd_dist + rgt[1] * right_off - up[1] * up_off,
            eye[2] + fwd[2] * fwd_dist + rgt[2] * right_off - up[2] * up_off,
        )

        yaw_vm = math.radians(10.0 * (1.0 - a))
        cant = math.radians((roll - 8.0) * (1.0 - a))
        cw, sw = math.cos(yaw_vm), math.sin(yaw_vm)
        ca, sa = math.cos(cant), math.sin(cant)

        drop = 0.0
        if mag_shift is not None and self.reloading:
            drop = 0.22 * _smooth(0.30, 0.62, p) * (1.0 - _smooth(0.62, 0.72, p))

        mx, my, mz = muzzle[0] * k, muzzle[1] * k, muzzle[2] * k
        mx, mz = mx * cw - mz * sw, mx * sw + mz * cw
        lx = mx * ca - my * sa
        ly = mx * sa + my * ca
        muzzle_world = (origin[0] + rgt[0] * lx + up[0] * ly + fwd[0] * mz,
                        origin[1] + rgt[1] * lx + up[1] * ly + fwd[1] * mz,
                        origin[2] + rgt[2] * lx + up[2] * ly + fwd[2] * mz)
        sx, sy, sz = sight[0] * k, sight[1] * k, sight[2] * k
        sx, sz = sx * cw - sz * sw, sx * sw + sz * cw
        slx = sx * ca - sy * sa
        sly = sx * sa + sy * ca
        sight_world = (origin[0] + rgt[0] * slx + up[0] * sly + fwd[0] * sz,
                       origin[1] + rgt[1] * slx + up[1] * sly + fwd[1] * sz,
                       origin[2] + rgt[2] * slx + up[2] * sly + fwd[2] * sz)
        return dict(mesh=mesh, k=k, mag_shift=mag_shift, mag_drop=drop,
                    origin=origin, rgt=rgt, up=up, fwd=fwd,
                    yaw_vm=yaw_vm, cant=cant, muzzle_world=muzzle_world,
                    sight_world=sight_world, reticle=reticle,
                    glass_size=glass_size)

    def _muzzle_world(self):
        """World-space muzzle tip for the current held pose (tracers/flash)."""
        return self._vm_setup()["muzzle_world"]

    def _draw_viewmodel(self, r):
        s = self._vm_setup()
        mesh, k = s["mesh"], s["k"]
        origin, rgt, up, fwd = s["origin"], s["rgt"], s["up"], s["fwd"]
        cw, sw = math.cos(s["yaw_vm"]), math.sin(s["yaw_vm"])
        ca, sa = math.cos(s["cant"]), math.sin(s["cant"])
        shift, drop = s["mag_shift"], s["mag_drop"]

        verts = []
        for i, (vx, vy, vz) in enumerate(mesh.verts):
            if shift is not None and drop:
                vy -= drop * shift[i]
            vx, vy, vz = vx * k, vy * k, vz * k
            vx, vz = vx * cw - vz * sw, vx * sw + vz * cw
            lx = vx * ca - vy * sa
            ly = vx * sa + vy * ca
            verts.append((origin[0] + rgt[0] * lx + up[0] * ly + fwd[0] * vz,
                          origin[1] + rgt[1] * lx + up[1] * ly + fwd[1] * vz,
                          origin[2] + rgt[2] * lx + up[2] * ly + fwd[2] * vz))
        faces = [(i, c, l, d, None, e) for i, c, l, d, e in mesh.faces]
        # A touch of cool lift so the black-anodised parts still separate from
        # the night behind them.
        r.add_dynamic(verts, faces, bias=0.0, tint=((128, 142, 164), 0.12))

        # Holographic reticle: the imported optic has no glass pane (an opaque
        # teal slab read as a fake lens), so the asset's own projected ring is
        # drawn through the open housing and fades in with the sight picture.
        img, gsize = s["reticle"], s["glass_size"]
        alpha = int(255 * clamp((self.ads - 0.05) / 0.45, 0.0, 1.0))
        if img is not None and gsize is not None and alpha > 0:
            size_m = max(gsize) * 1.15

            def _reticle(surface, sx, sy, scale, z):
                px = max(3, int(size_m * scale))
                tile = pygame.transform.scale(img, (px, px))
                tile.set_alpha(alpha)
                surface.blit(tile, (int(sx - px * 0.5), int(sy - px * 0.5)))

            r.add_sprite(s["sight_world"], _reticle, layer=3)

        if self.t - self.flash_t < 0.055:
            r.add_sprite(s["muzzle_world"],
                         _fx.flash(int((self.t - self.flash_t) * 1000),
                                   col=(255, 224, 166), radius_m=0.34,
                                   dur_ms=65),
                         layer=_fx.FX_LAYER)

    def _draw_fx(self, r, t):
        # Draw tracers as fast-moving projectile bolts instead of static full-length lines
        for t0, a, b, col in self.tracers:
            age = t - t0
            if age < 0.10:
                u0 = clamp(age / 0.10, 0.0, 0.85)
                u1 = clamp(u0 + 0.28, 0.0, 1.0)
                p0 = (a[0] + (b[0] - a[0]) * u0,
                      a[1] + (b[1] - a[1]) * u0,
                      a[2] + (b[2] - a[2]) * u0)
                p1 = (a[0] + (b[0] - a[0]) * u1,
                      a[1] + (b[1] - a[1]) * u1,
                      a[2] + (b[2] - a[2]) * u1)
                r.add_line3d(p0, p1, col, 2, layer=5)
        for t0, pos, col in self.sparks:
            age = t - t0
            if age < 0.45:
                r.add_sprite(pos, _fx.sparks(17, int(age * 1000), col=col),
                             layer=_fx.FX_LAYER)
        for t0, pos, kind, _n in self.impacts:
            ms = int((t - t0) * 1000)
            seed = int(t0 * 97) & 0xFFF
            if kind == "flesh":
                r.add_sprite(pos, _blood_spray(seed, ms, ang=-1.57, n=16,
                                               dur_ms=520), layer=_fx.FX_LAYER)
                continue
            if kind == "metal":
                r.add_sprite(pos, _fx.sparks(seed, ms, col=(255, 206, 128), n=16,
                                             speed_m=3.4, dur_ms=480),
                             layer=_fx.FX_LAYER)
                if ms < 70:
                    r.add_sprite(pos, _fx.flash(ms, col=(255, 214, 150),
                                                radius_m=0.18, dur_ms=70),
                                 layer=_fx.FX_LAYER)
                continue
            col = (150, 112, 74) if kind == "wood" else (206, 214, 228)
            if kind == "wood":
                r.add_sprite(pos, _fx.sparks(seed, ms, col=(176, 136, 88), n=9,
                                             speed_m=2.2, dur_ms=420),
                             layer=_fx.FX_LAYER)
            r.add_sprite(pos, _fx.dust_motes(ms, seed=seed, count=10,
                                             spread_m=(0.30, 0.26), col=col),
                         layer=_fx.FX_LAYER)
        for pos, n, kind, size in self.decals:
            _w.add(r, _decal_mesh(pos, n, kind, size))
        for b in self.brass:
            bp, air = _brass_pos(b, t)
            ph = int((t - b[0]) * 16.0) + b[3]
            if air:
                dims = ((0.014, 0.014, 0.045), (0.045, 0.014, 0.014),
                        (0.014, 0.045, 0.014))[ph % 3]
            else:
                dims = (0.045, 0.013, 0.014) if b[3] % 2 else (0.014, 0.013, 0.045)
            _w.add(r, box(dims[0], dims[1], dims[2], _BRASS, center=bp))

    def _draw_death_fx(self, r, t):
        """Contact shadow, ground puffs, stain and the last breath."""
        if self.volkov_failed:
            if not self.fail_pos:
                return
            d = self.fail_t
            fstate = self._fstate or _volkov_fail_state(
                d, t, self.fail_pos, self.fail_yaw, self.volkov_delay)
            pos, pose, yaw, joints = fstate
            failed = True
        elif t >= HIT_AT:
            vstate = self._vstate or _volkov_death_state(
                t, self.volkov_delay)
            pos, pose, yaw, joints = vstate
            d = t - HIT_AT
            failed = False
        else:
            return
        head, pelvis = joints["head"], joints["pelvis"]
        if d >= 0.45:
            for i, k in enumerate((0.20, 0.50, 0.80)):
                cx = head[0] + (pelvis[0] - head[0]) * k
                cz = head[2] + (pelvis[2] - head[2]) * k
                rad = 0.34 - 0.04 * abs(i - 1)
                _w.add(r, disc_xz(cx, cz, rad, _BALLAST_Y + 0.003,
                                  (32, 34, 40), n=10, layer=1))
        if not failed:
            self._draw_exit_gore(r, t, d, joints)
        if failed:
            if _DEATH_D <= d <= _DEATH_D + 0.40:
                r.add_sprite((pos[0], _BALLAST_Y + 0.10, pos[2]),
                             _fx.dust_motes(t * 1000.0, seed=78, count=14,
                                            spread_m=(0.7, 0.6),
                                            col=(198, 208, 224)),
                             layer=_fx.FX_LAYER)
            return
        if 0.42 <= d <= 0.90:
            for knee in _w.knees(_hum("volkov"), pose, pos, yaw).values():
                r.add_sprite((knee[0], knee[1] + 0.05, knee[2]),
                             _fx.dust_motes(t * 1000.0, seed=77, count=10,
                                            spread_m=(0.5, 0.4),
                                            col=(190, 200, 214)),
                             layer=_fx.FX_LAYER)
        if _DEATH_D <= d <= _DEATH_D + 0.45:
            r.add_sprite((pos[0], _BALLAST_Y + 0.10, pos[2]),
                         _fx.dust_motes(t * 1000.0, seed=78, count=14,
                                        spread_m=(0.7, 0.6),
                                        col=(198, 208, 224)),
                         layer=_fx.FX_LAYER)
        if d >= _DEATH_D:
            # The pool never stops widening, slowly, across the whole vigil.
            grow = _smooth(_DEATH_D, _DEATH_D + 0.60, d) +                 0.9 * _smooth(_DEATH_D, _DEATH_D + 7.0, d)
            rad = 0.14 + 0.16 * grow
            wob = (1.0, 0.82, 1.12, 0.9, 1.18, 0.86, 1.05, 0.94, 1.14, 0.88)
            _w.add(r, disc_xz(pos[0] + 0.05, pos[2] - 0.04, rad,
                              _BALLAST_Y + 0.012, (62, 10, 12), n=10,
                              layer=1, wobble=wob))
            _w.add(r, disc_xz(pos[0] + 0.03, pos[2] - 0.02, rad * 0.58,
                              _BALLAST_Y + 0.016, (38, 6, 9), n=10,
                              layer=1, wobble=wob[::-1]))
            self._draw_cigarette(r, t, d, head, pos)
        for (t0, _a), inten in zip(_BREATHS, (0.24, 0.14, 0.06)):
            if t0 + 0.1 <= d <= t0 + 1.2:
                r.add_sprite((head[0], head[1] + 0.05, head[2]),
                             _w.breath(head, t * 1000.0, seed=93,
                                       intensity=inten),
                             layer=_fx.FX_LAYER)
        if t >= SHOT_AT + 4.4:
            bstate = self._bstate or _biribel_catch_state(
                t, (pos, pose, yaw, joints))
            if bstate is not None:
                bpos, byaw, bpose = bstate
                bj = _hum(("biribel", OUTFIT_GUARD)).pose_world(
                    bpose, bpos, byaw)[1]
                bh = bj["head"]
                r.add_sprite((bh[0], bh[1] + 0.04, bh[2]),
                             _w.breath(bh, t * 1000.0, seed=94,
                                       intensity=0.10),
                             layer=_fx.FX_LAYER)

    def _draw_exit_gore(self, r, t, d, joints):
        """The round's exit: spray and mist at the hit, spatter on the
        ballast ahead of him, a smear where he is lowered."""
        chest = joints["chest"]
        if 0.0 <= d < 1.0:
            r.add_sprite((chest[0], chest[1] + 0.06, chest[2]),
                         _blood_spray(5, d * 1000.0), layer=_fx.FX_LAYER)
            fade = 1.0 - _smooth(0.05, 0.42, d)
            if fade > 0.01:
                r.add_sprite((chest[0], chest[1] + 0.04, chest[2]),
                             _fx.glow((150, 20, 26), 0.55, t * 1000.0,
                                      intensity=0.5 * fade),
                             layer=_fx.FX_LAYER)
        # spatter: throw direction is tower -> chest, i.e. away from the tower
        for i in range(11):
            land = 0.12 + 0.30 * _drip(i, 3)
            if d < land:
                continue
            reach = 0.5 + 2.3 * _drip(i, 1)
            ang = math.atan2(-7.6, -6.7) + (_drip(i, 2) - 0.5) * 0.9
            sx = _SPRAY_O[0] + math.cos(ang) * reach
            sz = _SPRAY_O[1] + math.sin(ang) * reach * 0.55
            rad = (0.03 + 0.07 * _drip(i, 4)) * _smooth(land, land + 0.4, d)
            if rad > 0.006:
                wob = tuple(0.8 + 0.4 * _drip(i, 10 + k) for k in range(7))
                _w.add(r, disc_xz(sx, sz, rad, _BALLAST_Y + 0.006 + 0.0004 * i,
                                  (70, 8, 12), n=7, layer=1, wobble=wob))
        # the drag: a smear that follows the chest down
        if d >= 0.35:
            for k, (ds, px, pz) in enumerate(_trail_points(self.volkov_delay)):
                if ds > d:
                    break
                _w.add(r, disc_xz(px, pz, 0.07 + 0.015 * (k % 3),
                                  _BALLAST_Y + 0.005 + 0.0003 * k,
                                  (60, 8, 12), n=8, layer=1))

    def _draw_cigarette(self, r, t, d, head, pos):
        """The cigarette that left his lips: a short fall, then a thread of
        smoke from the ember in the bloody snow."""
        if d < _CIG_D:
            return
        lip = (head[0] + 0.07, head[1] + 0.01, head[2] + 0.10)
        rest = (head[0] - 0.28, _BALLAST_Y + 0.012, head[2] + 0.02)
        k = clamp((d - _CIG_D) / 0.34, 0.0, 1.0)
        fall = k * k
        cp = (lip[0] + (rest[0] - lip[0]) * k,
              lip[1] + (rest[1] - lip[1]) * fall,
              lip[2] + (rest[2] - lip[2]) * k)
        m = box(0.012, 0.012, 0.075, (232, 228, 216), center=cp)
        m.add(box(0.0125, 0.0125, 0.014, (196, 140, 80),
                  center=(cp[0], cp[1], cp[2] - 0.040)))
        ember = box(0.0125, 0.0125, 0.012, (255, 120, 48),
                    center=(cp[0], cp[1], cp[2] + 0.040), emissive=True)
        m.add(ember)
        _w.add(r, m)
        if k >= 1.0:
            tip = (rest[0], rest[1] + 0.02, rest[2] + 0.04)
            r.add_sprite(tip, _fx.glow((255, 130, 56), 0.5, t * 1000.0,
                                       flicker=0.25, seed=141, intensity=0.55),
                         layer=_fx.FX_LAYER)
            r.add_sprite((tip[0], tip[1] + 0.05, tip[2]),
                         _fx.cig_smoke(t * 1000.0, seed=141,
                                       drift=(0.10, -0.42), intensity=0.20,
                                       life_ms=3600),
                         layer=_fx.FX_LAYER)

    # ── HUD ────────────────────────────────────────────────────────────
    def _draw_hud(self, surface, t):
        self._draw_objective(surface, t)
        self._draw_volkov_status(surface, t)
        self._draw_crosshair(surface, t)
        self._draw_vitals(surface)
        self._draw_damage_arcs(surface, t)
        self._draw_subtitle(surface, t)
        if t < 6.0:
            font = font_prompt
            hint = "AIM: MOUSE   ADS: RMB   FIRE: LMB   RELOAD: R"
            img = font.render(hint, True, (176, 184, 196))
            alpha = int(255 * (1.0 - _smooth(4.4, 6.0, t)))
            img.set_alpha(alpha)
            surface.blit(img, ((WIDTH - img.get_width()) // 2, HEIGHT - 34))
        if t >= 2.0:
            img = font_terminal_small.render("[E] SKIP", True, (110, 116, 128))
            surface.blit(img, (WIDTH - img.get_width() - 30, HEIGHT - 140))
        base = 0.0
        if self.wounded:
            # a slow heartbeat: two beats, a rest
            ph = (t * 1.25) % 1.0
            beat = (math.exp(-((ph - 0.10) / 0.05) ** 2)
                    + 0.6 * math.exp(-((ph - 0.30) / 0.06) ** 2))
            base = 0.30 + 0.22 * beat
        hv = max(base, clamp(self.hurt / 0.34, 0.0, 1.0))
        if hv > 0.0:
            v = hurtvignette()
            v.set_alpha(int(255 * hv))
            surface.blit(v, (0, 0))

    def _draw_cine_overlay(self, surface, t):
        c = t - SHOT_AT
        bar = 54
        pygame.draw.rect(surface, (0, 0, 0), (0, 0, WIDTH, bar))
        pygame.draw.rect(surface, (0, 0, 0), (0, HEIGHT - bar, WIDTH, bar))
        tag = font_terminal_small
        if c < CINE_TOWER_END:
            eyebrow = tag.render("SIGNAL TOWER  /  UCILEV", True,
                                 (198, 168, 104))
            surface.blit(eyebrow, (34, bar + 14))
            sub = tag.render("ONE ROUND", True, (150, 156, 166))
            surface.blit(sub, (34, bar + 32))
            return
        if c < CINE_SCOPE_END:
            scope = hudcache.get("scope")
            if scope is None:
                scope = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                scope.fill((0, 0, 0, 255))
                cx, cy, rad = WIDTH // 2, HEIGHT // 2, 238
                pygame.draw.circle(scope, (0, 0, 0, 0), (cx, cy), rad)
                pygame.draw.circle(scope, (16, 16, 18, 235), (cx, cy),
                                   rad + 10, 20)
                for rr in (36, 120, rad):
                    pygame.draw.circle(scope, (168, 176, 188, 105),
                                       (cx, cy), rr, 1)
                # Brighter than the old grey: the lit platform behind the
                # target was swallowing the cross.
                pygame.draw.line(scope, (226, 232, 240, 165),
                                 (cx - rad, cy), (cx + rad, cy), 1)
                pygame.draw.line(scope, (226, 232, 240, 165),
                                 (cx, cy - rad), (cx, cy + rad), 1)
                for d in (10, 24, 44, 68):
                    pygame.draw.line(scope, (214, 220, 228, 150),
                                     (cx - d, cy - 2), (cx - 8, cy - 2), 2)
                    pygame.draw.line(scope, (214, 220, 228, 150),
                                     (cx + 8, cy - 2), (cx + d, cy - 2), 2)
                hudcache["scope"] = scope
            hit_rel = HIT_AT - SHOT_AT
            dh = c - hit_rel
            if self.ucilev_fired and 0.0 <= dh < 0.45:
                # Everything below is drawn UNDER the lens mask: a full-screen
                # flash used to wash the black mask grey and read as a veil.
                bloom = hudcache.get("scope_bloom")
                if bloom is None:
                    bloom = pygame.Surface((WIDTH, HEIGHT))
                    cx, cy = WIDTH // 2, HEIGHT // 2
                    for rr in range(238, 0, -6):
                        v = int(150 * (1.0 - rr / 238.0) ** 1.6)
                        pygame.draw.circle(bloom, (v, v - 6 if v > 6 else 0,
                                                   v - 18 if v > 18 else 0),
                                           (cx, cy), rr)
                    hudcache["scope_bloom"] = bloom
                # muzzle bloom: hot, instant, gone in ~0.12 s
                k = math.exp(-dh / 0.045)
                if k > 0.02:
                    tmp = bloom.copy()
                    tmp.fill((int(255 * k),) * 3, special_flags=pygame.BLEND_MULT)
                    surface.blit(tmp, (0, 0), special_flags=pygame.BLEND_ADD)
                # impact mist: a pink-red cloud blooming out of the chest
                mist = _smooth(0.0, 0.12, dh) * (1.0 - _smooth(0.12, 0.45, dh))
                if mist > 0.01:
                    sp = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
                    cx, cy = WIDTH // 2, HEIGHT // 2
                    for i in range(11):
                        a = i * 2.399
                        rr = 16 + 150 * _smooth(0.0, 0.45, dh) * (0.45 + 0.1 * (i % 4))
                        px = cx + int(math.cos(a) * rr * 0.9)
                        py = cy + int(math.sin(a) * rr * 0.7) + int(10 * dh * 30 * (i % 3) / 3)
                        pygame.draw.circle(sp, (150, 22, 28, int(70 * mist)),
                                           (px, py), 14 + 9 * (i % 3))
                    surface.blit(sp, (0, 0))
            surface.blit(scope, (0, 0))
            eyebrow = tag.render("UCILEV  /  SIGNAL TOWER", True,
                                 (198, 168, 104))
            surface.blit(eyebrow, (34, bar + 14))
            sub = tag.render("SCOPE  /  LEADING", True, (152, 158, 168))
            surface.blit(sub, (WIDTH - sub.get_width() - 34, bar + 14))
            return
        if c < CINE_IMPACT_END:
            eyebrow = tag.render("ONE SHOT", True, (204, 82, 64))
            surface.blit(eyebrow, (34, bar + 14))
            return
        if c < CINE_CATCH_END:
            eyebrow = tag.render("BIRIBEL  /  PLATFORM", True,
                                 (166, 158, 142))
            surface.blit(eyebrow, (34, bar + 14))
            return

    def _draw_death_overlay(self, surface):
        d = self.death_t
        if d < 0.38:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((118, 10, 10))
            veil.set_alpha(int(150 * (1.0 - d / 0.38)))
            surface.blit(veil, (0, 0))
        red = hurtvignette()
        red.set_alpha(int(255 * clamp(1.0 - d / 1.4, 0.0, 1.0)))
        surface.blit(red, (0, 0))
        fade = clamp((d - 1.75) / 0.45, 0.0, 1.0) * 0.62
        if fade > 0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((4, 3, 4))
            veil.set_alpha(int(255 * fade))
            surface.blit(veil, (0, 0))
        if d > 1.15:
            a = int(255 * clamp((d - 1.15) / 0.45, 0.0, 1.0))
            img = font_terminal_small.render("BIRIBEL DOWN", True, (196, 78, 62))
            img.set_alpha(a)
            surface.blit(img, ((WIDTH - img.get_width()) // 2, HEIGHT - 118))

    def _draw_fail_overlay(self, surface):
        d = self.fail_t
        if d < 0.42:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((96, 12, 12))
            veil.set_alpha(int(170 * (1.0 - d / 0.42)))
            surface.blit(veil, (0, 0))
        red = hurtvignette()
        red.set_alpha(int(235 * clamp(1.0 - d / 1.5, 0.0, 1.0)))
        surface.blit(red, (0, 0))
        fade = clamp((d - 1.10) / 0.70, 0.0, 1.0) * 0.55
        if fade > 0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((5, 3, 3))
            veil.set_alpha(int(255 * fade))
            surface.blit(veil, (0, 0))
        if d > 0.30:
            a = int(255 * clamp((d - 0.30) / 0.35, 0.0, 1.0))
            img = font_terminal_small.render("VOLKOV IS DOWN", True,
                                             (204, 82, 64))
            img.set_alpha(a)
            surface.blit(img, ((WIDTH - img.get_width()) // 2, HEIGHT - 118))

    def _draw_objective(self, surface, t):
        done = t >= SHOT_AT
        cleared = self.cleared_t >= 0.0 and self._living() == 0
        if done:
            head = "VOLKOV IS DOWN"
            sub = ("He never reached the train. The Guard cut him down."
                   if self.volkov_failed else
                   "Ucilev's shot. The train is leaving.")
            accent = (176, 72, 58)
        elif self.volkov_pinned:
            head = "COVER VOLKOV"
            sub = "He is pinned. Clear the platform."
            accent = (196, 112, 64)
        elif cleared:
            head = "COVER VOLKOV"
            sub = "Platform clear. Keep him moving."
            accent = (112, 168, 118)
        else:
            head = "COVER VOLKOV"
            sub = "Clear the lane. Get him to the train."
            accent = ACCENT
        head_img = font_terminal.render(head, True, (232, 226, 210))
        sub_img = font_terminal_small.render(sub, True, (154, 162, 176))
        w = max(head_img.get_width(), sub_img.get_width()) + 34
        pnl = panel(w, 58, accent)
        pnl.blit(head_img, (16, 8))
        pnl.blit(sub_img, (16, 34))
        surface.blit(pnl, (26, 24))

    def _draw_volkov_status(self, surface, t):
        """Live read on the two things that decide the ending: how far Volkov
        has left to run and how many Guards are still on the platform."""
        if t < 1.0:
            return
        living = self._living()
        pos, _mode, _phase = _volkov_at(t, self.volkov_delay)
        prog = clamp((pos[0] + 9.9) / (11.4 + 9.9), 0.0, 1.0)
        if t >= SHOT_AT:
            state = "DOWN"
            scol = (204, 78, 64)
        elif self.volkov_pinned:
            state = "PINNED"
            scol = (226, 120, 74)
        elif living == 0:
            state = "CLEAR"
            scol = (118, 184, 128)
        else:
            state = "RUNNING"
            scol = (198, 176, 120)
        w, h = 244, 72
        accent = (176, 72, 58) if self.overrun else ACCENT
        pnl = panel(w, h, accent)
        pnl.blit(font_terminal_small.render("VOLKOV", True, (198, 190, 172)), (12, 7))
        st = font_terminal_small.render(state, True, scol)
        pnl.blit(st, (w - st.get_width() - 12, 7))
        pygame.draw.rect(pnl, (28, 30, 36), (12, 28, 188, 7))
        pygame.draw.rect(pnl, (214, 176, 96) if not self.volkov_pinned else (196, 96, 60),
                         (12, 28, int(188 * prog), 7))
        # Guard pips: one per authored slot, red while alive, grey when down.
        pnl.blit(font_terminal_small.render(f"GUARD {living}", True,
                                            (158, 164, 178)), (12, 44))
        x0 = 92
        for i, g in enumerate(self.guards):
            alive = bool(g.get("active") and g.get("alive"))
            pending = not g.get("active")
            c = (196, 74, 60) if alive else ((38, 42, 50) if pending else (58, 62, 68))
            pygame.draw.rect(pnl, c, (x0 + i * 12, 46, 8, 8))
        surface.blit(pnl, (WIDTH - w - 26, 24))

    def _draw_crosshair(self, surface, t):
        if t < CONTROL_AT or t >= CUT_AT:
            return
        cx, cy = WIDTH // 2, HEIGHT // 2
        if self.ads < 0.55:
            gap = 7 + int(8 * self.kick)
            col = (226, 228, 220)
            pygame.draw.line(surface, col, (cx - gap - 10, cy), (cx - gap, cy), 2)
            pygame.draw.line(surface, col, (cx + gap, cy), (cx + gap + 10, cy), 2)
            pygame.draw.line(surface, col, (cx, cy - gap - 10), (cx, cy - gap), 2)
            pygame.draw.line(surface, col, (cx, cy + gap), (cx, cy + gap + 10), 2)
            if self.reloading:
                p = self.reload_progress()
                rect = pygame.Rect(cx - 22, cy - 22, 44, 44)
                pygame.draw.circle(surface, (50, 52, 58), (cx, cy), 22, 2)
                pygame.draw.arc(surface, (214, 176, 96), rect,
                                math.pi / 2, math.pi / 2 + p * 2 * math.pi, 3)
        if t - self.hit_mark < 0.20:
            k = 1.0 - (t - self.hit_mark) / 0.20
            r = int(10 + 4 * (1 - k))
            mc = {"head": (246, 196, 84), "kill": (236, 70, 58)}.get(
                self.hit_kind, (226, 228, 220))
            if self.hit_kind in ("kill", "head"):
                r = int(r * (1.0 + 0.55 * k))     # a scale pop on a kill
            for sx in (-1, 1):
                for sy in (-1, 1):
                    pygame.draw.line(surface, mc, (cx + sx * r, cy + sy * r),
                                     (cx + sx * (r + 7), cy + sy * (r + 7)), 2)

    def _draw_damage_arcs(self, surface, t):
        """Where the last hits came from: arcs around the crosshair."""
        cx, cy = WIDTH // 2, HEIGHT // 2
        for t0, bearing in self.dmg_marks:
            k = 1.0 - (t - t0) / 0.85
            if k <= 0.0:
                continue
            rad = 118
            rect = pygame.Rect(cx - rad, cy - rad, rad * 2, rad * 2)
            # bearing 0 = straight ahead, + = to the player's left
            a = math.radians(90.0 + bearing)
            w = 0.34
            col = (int(210 * k + 30), int(36 * k), int(32 * k))
            pygame.draw.arc(surface, col, rect, a - w, a + w, 5)

    def _draw_vitals(self, surface):
        p = STATE.player
        hp = p.hp if p is not None else 0
        mx = p.max_hp if p is not None else 100
        frac = clamp(hp / float(max(1, mx)), 0.0, 1.0)

        pnl = panel(250, 44)
        name = "BIRIBEL  WOUNDED" if self.wounded else "BIRIBEL"
        pnl.blit(font_terminal_small.render(name, True,
                                            (214, 118, 94) if self.wounded
                                            else (190, 196, 208)), (12, 5))
        col = (188, 64, 54) if frac < 0.35 else (86, 168, 112)
        pygame.draw.rect(pnl, (30, 32, 38), (12, 26, 180, 8))
        pygame.draw.rect(pnl, col, (12, 26, int(180 * frac), 8))
        num = font_terminal_small.render(str(int(hp)), True, (208, 210, 204))
        pnl.blit(num, (204, 21))
        surface.blit(pnl, (26, HEIGHT - 70))

        ammo = getattr(STATE, "k9_ammo_in_mag", 0)
        size = getattr(STATE, "k9_mag_size", 30)
        mags = getattr(STATE, "k9_spare_mags", 0)
        low = ammo <= size // 4
        pnl = panel(220, 70)
        pnl.blit(font_terminal_small.render("K9 SMG", True, (160, 166, 178)), (12, 6))
        big = font_terminal.render(f"{ammo:02d}", True,
                                   (188, 74, 64) if low else (232, 214, 170))
        pnl.blit(big, (12, 24))
        pnl.blit(font_terminal_small.render(f"/ {size}   x{mags}", True,
                                            (148, 154, 166)),
                   (16 + big.get_width(), 30))
        pipw = max(2, (196 - size) // size) if size > 0 else 2
        for i in range(size):
            c = (214, 176, 96) if i < ammo else (44, 46, 52)
            pygame.draw.rect(pnl, c, (12 + i * (pipw + 1), 56, pipw, 6))
        surface.blit(pnl, (WIDTH - 246, HEIGHT - 96))
        if low and not self.reloading and mags > 0 and ammo > 0:
            hint = font_terminal_small.render("R  RELOAD", True, (228, 216, 178))
            surface.blit(hint, (WIDTH - 246, HEIGHT - 118))

    def _draw_subtitle(self, surface, t):
        start = end = who = text = None
        best = -1.0
        for s0, s1, spk, body in _LINES:
            if s0 <= t <= s1 and s0 >= best:
                start, end, who, text = s0, s1, spk, body
                best = s0
        live = None
        if text is not None:
            clock = int(t * 1000.0)
            live = {
                "start": int(start * 1000.0),
                "end": int(end * 1000.0),
                "text": text,
                "speaker": who,
                "body": text,
                "color": (212, 186, 140),
                "vo_ms": max(500, len(text) * 40),
                "priority": 0,
            }
        _radio_widget().draw(surface, live=live, allowed=True,
                             clock=int(t * 1000.0), anchor="hud")


_scene = TrainScene()


# Module API ---------------------------------------------------------------
def begin(stage_resume=False):
    return _scene.begin(stage_resume)


def active():
    return _scene.active()


def update(keys=None, mouse=None):
    return _scene.update(keys, mouse)


def draw(surface):
    return _scene.draw(surface)


def handle_event(event):
    return _scene.handle_event(event)


def skip():
    return _scene.skip()


def force_finish(result="win"):
    return _scene.force_finish(result)


def result():
    return _scene.result()


def reset():
    return _scene.reset()


def prepare():
    return _scene.prepare()


def set_paused(paused):
    return _scene.set_paused(paused)


def fire_once():
    return _scene.fire_once()


def scene():
    return _scene
