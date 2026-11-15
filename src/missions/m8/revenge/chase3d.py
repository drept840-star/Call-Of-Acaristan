"""Mission 8 Revenge - phase 6: the tractor chase to the Kim Kim crossing.

Bodi drives the farm tractor on a fixed route (he steers round the wrecks);
Biribel rides the hay trailer with a belt-fed light machine gun and turns freely
on it. Armoured Guard jeeps tailgate, gun trucks cut in, guards bail out of the
Route 12 wrecks, and a last jeep blocks the tracks while the train waits to
leave. The cars carry steel for the LMG: a tyre takes a short burst, the driver
sits behind a windscreen shield, the body soaks a long one. The tractor's hull
is the life bar.

Four sections, each a checkpoint: farm track, hay bales and the ditch, the
wrecks, the crossing. Fail: the hull reaches zero (the tractor stalls), or the
train leaves first (the crossing timer). The ending is scripted: the tractor
stops on the tracks, Bodi waves him off, Biribel jumps for the last car.

Contract (as ``trap3d``): ``begin`` / ``active`` / ``update`` / ``draw`` /
``handle_event`` / ``set_paused`` / ``abort`` / ``force_finish``.
``finish`` hands off to ``flow.on_chase_done`` exactly once.
"""

import copy
import math
import random
from functools import lru_cache

import pygame

from core.config import (
    HEIGHT,
    WIDTH,
    audio,
    draw_vignette,
    font_terminal,
    font_terminal_small,
)
from core.outfits import OUTFIT_GUARD
from core.state import STATE
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from engine3d import Mesh, POSES, blend, box, clamp
from engine3d.core import m_apply, m_mul, rot_x, rot_y, rot_z
from engine3d.rig import NEUTRAL, pose_run
from engine3d.hold import GRIPS, hold_cached, solve_arm_safe
from missions.m6 import hud3d as H
from missions.m6 import yard_hud as U
from missions.m7 import raid3d as R

from . import chase_set as S
from . import epilogue3d as E


SPEED = 11.0
HITCH = 4.6
HULL = 100.0
GUN = "lmg"
MAG = 100
RELOAD_S = 4.2
RELOAD_PITCH = -4.0
PITCH_LIM = (-28.0, 16.0)
PITCH_STEP = 4.0
FEET = 0.98
BIRIBEL = ("biribel", OUTFIT_GUARD)

FIRE_GAP = 0.085
SPREAD = (0.35, 2.2)
HEAT_SHOT, HEAT_COOL = 0.07, 1.1
CLIMB = 0.12
SENS = 0.12

# ADS: both points are gun-space, with +z down the bore.
ADS_EYE = (0.0, 0.375, -0.26)
ADS_POST = (0.0, 0.172, 0.58)
ADS_FOV = 45.0
ADS_SENS = 0.30
ADS_SPREAD = 0.55
ADS_CLIMB = 0.45
ADS_UP, ADS_DOWN = 11.0, 7.0

# Muzzle flash:
# - Real geometry rooted at the barrel opening.
# - Every flame vertex is on or ahead of the muzzle plane.
# - A narrow axial discharge, not a large camera-facing fireball.
# - Small supporting bloom ahead of the opening.
# - No invented muzzle-brake jets, ember fountain or emissive "smoke".
FLASH_MS = 52
ENEMY_FLASH_MS = 72
FLASH_LEN = 0.44
FLASH_CORE_R = 0.028
FLASH_PETALS = 5
FLASH_BLOOM_R = 0.11
FLASH_BLOOM_I = 0.48
FLASH_BIAS = 0.32
FLASH_ROLL = 0.85
FLASH_LIGHT = 1.95

CROSSING_TIME = 72.0
STOP_Z = S.CROSSING_Z - 7.5

SPEAKER = {
    "BODI": (226, 170, 98),
    "BIRIBEL": (228, 230, 222),
    "GUARD": (206, 128, 112),
    "RETARDOVICI": (220, 150, 140),
}

CAPTURE_S = 9.0
SECTION_NAMES = (
    "FARM TRACK",
    "THE DITCH",
    "ROUTE 12 WRECKS",
    "THE GUNSHIP",
    "KIM KIM CROSSING",
)

# Per section: (seconds after section starts, kind, lateral offset).
SPAWNS = (
    (
        (2.0, "jeep", -1.6),
        (8.0, "jeep", 1.8),
        (15.0, "jeep", 0.0),
        (22.0, "jeep", -1.8),
        (28.0, "jeep", 1.6),
    ),
    (
        (3.0, "jeep", 1.6),
        (10.0, "jeep", -1.6),
        (16.0, "gun_truck", 2.0),
        (26.0, "jeep", 0.0),
        (34.0, "jeep", -1.8),
        (42.0, "jeep", 1.8),
    ),
    (
        (6.0, "jeep", 1.4),
        (16.0, "jeep", -1.4),
        (26.0, "gun_truck", 2.0),
        (36.0, "jeep", 1.4),
        (44.0, "jeep", -1.4),
    ),
    (
        (3.0, "jeep", -1.6),
        (24.0, "jeep", 1.8),
    ),
    (
        (2.0, "jeep", -1.6),
        (8.0, "jeep", 1.6),
        (15.0, "jeep", 0.0),
    ),
)

# --- the gunship -------------------------------------------------------------
HELI_HP = 280
HELI_GUNNER_HP = 18
HELI_LOCK_S = 1.5
ROCKET_HP = 2
ROCKET_HIT_R = 0.65
ROCKET_DMG = 40.0
DODGE_S = 1.7

REPAIR_S = 2.4
REPAIR_HEAL = 45.0
REPAIRS_MAX = 2

# The descent film plays the first PULL_S seconds using the chase simulation.
PULL_S = 4.5
PULL_DT = 1.0 / 60.0
START_Z = S.SECTIONS[0] - 10.0
PULL_Z0 = START_Z - SPEED * (PULL_S - 0.5)

RELOAD_TRACK = (
    (0.0, "grip"),
    (0.3, "grip"),
    (0.62, "cover"),
    (0.8, "cover_up"),
    (1.1, "can_old"),
    (1.4, "can_out"),
    (1.55, "toss"),
    (1.95, "rack"),
    (2.2, "rack_up"),
    (2.6, "can_on"),
    (2.9, "belt"),
    (3.05, "belt2"),
    (3.25, "shut_top"),
    (3.4, "shut"),
    (3.58, "charge_in"),
    (3.76, "charge"),
    (3.98, "grip"),
    (RELOAD_S, "grip"),
)

# Key: (left-hand target, right-hand target, stance).
RELOAD_KEYS = {
    "cover": (
        ("gun", (-0.03, 0.15, 0.0)),
        None,
        dict(head_p=8),
    ),
    "cover_up": (
        ("gun", (-0.03, 0.27, 0.05)),
        None,
        dict(head_p=6),
    ),
    "can_old": (
        ("gun", (-0.1, -0.06, 0.19)),
        None,
        dict(head_p=16, head_y=-10),
    ),
    "can_out": (
        ("gun", (-0.36, -0.12, 0.12)),
        None,
        dict(head_p=14, head_y=-24),
    ),
    "toss": (
        ("gun", (-0.56, 0.02, 0.04)),
        None,
        dict(head_p=4, head_y=-34, twist=-6),
    ),
    "rack": (
        ("rack", (0.04, 0.2, 0.0)),
        None,
        dict(spine=6, twist=-6, head_p=22, head_y=-30),
    ),
    "rack_up": (
        ("rack", (0.04, 0.36, 0.0)),
        None,
        dict(spine=4, twist=-4, head_p=18, head_y=-24),
    ),
    "can_on": (
        ("gun", (-0.1, -0.06, 0.19)),
        None,
        dict(head_p=16, head_y=-10),
    ),
    "belt": (
        ("gun", (-0.04, 0.12, 0.17)),
        None,
        dict(head_p=12),
    ),
    "belt2": (
        ("gun", (0.0, 0.12, 0.05)),
        None,
        dict(head_p=12),
    ),
    "shut_top": (
        ("gun", (-0.03, 0.27, 0.05)),
        None,
        dict(head_p=8),
    ),
    "shut": (
        ("gun", (-0.03, 0.15, 0.0)),
        None,
        dict(head_p=8),
    ),
    "charge_in": (
        None,
        ("gun", (0.1, 0.06, 0.22)),
        dict(head_y=8),
    ),
    "charge": (
        None,
        ("gun", (0.1, 0.06, 0.0)),
        dict(head_y=8),
    ),
}

RELOAD_EVENTS = (
    (0.74, "dry"),
    (1.55, "toss"),
    (2.6, "reload"),
    (3.38, "shell_in"),
    (3.72, "pump"),
)
CAN_OLD, CAN_NEW = (1.1, 1.55), (1.95, 2.6)

HP = {"jeep": 40, "gun_truck": 110, "blocker": 60, "foot": 2}
TYRE_HP = {"jeep": 7, "gun_truck": 10}
DRIVER_HP = {"jeep": 6, "gun_truck": 8, "blocker": 6}
GUNNER_HP = 4

SPAWN_BACK = S.FOG_END + 80.0
DESPAWN_BACK = SPAWN_BACK + 60.0
LAMP_RANGE = S.FOG_START + 0.5 * (S.FOG_END - S.FOG_START)
CLOSE_MAX = 16.0
REACT_S = 0.8
LAT_MAX = 5.0
CRASH_SPEED = 7.0
CRASH_RANGE = 40.0
CRASH_TRANSFER = 0.6
TRACTOR_HIT = 4.0
BRAKE = 8.0
WRECK_DECEL = 5.5

# (life seconds, initial radius, final radius, alpha, rise speed).
PUFF = {
    "dust": (1.8, 0.5, 2.4, 92, 0.5),
    "trail": (1.2, 0.3, 1.3, 36, 0.5),
    "exhaust": (1.1, 0.18, 0.95, 120, 1.7),
    "fire": (0.55, 0.7, 2.0, 220, 1.5),
    "blast": (2.6, 0.9, 3.8, 150, 1.4),
    "burn": (3.2, 0.5, 2.8, 112, 1.8),
}
PUFF_COL = {
    "dust": ((150, 124, 96), (196, 166, 128)),
    "trail": ((150, 124, 96), (196, 166, 128)),
    "exhaust": ((46, 46, 48), (78, 76, 76)),
    "fire": ((214, 92, 30), (255, 184, 80)),
    "blast": ((34, 30, 30), (92, 70, 54)),
    "burn": ((30, 29, 30), (66, 62, 60)),
}
PUFF_MAX = 260


@lru_cache(maxsize=384)
def _puff_img(kind, rad, alpha, variant):
    """A lumpy two-tone puff with a lit cap toward the low sun."""
    shade, lit = PUFF_COL[kind]
    n = 40
    small = pygame.Surface((n, n), pygame.SRCALPHA)
    rng = random.Random(variant * 31 + 7)

    for col, dy, k in ((shade, 2, 1.0), (lit, -3, 0.66)):
        for i in range(5):
            a = math.tau * i / 5 + variant * 0.9
            cx = 20 + math.cos(a) * 6 * k
            cy = 20 + dy + math.sin(a) * 4 * k
            rr = (7 + rng.randrange(4)) * k
            pts = [
                (
                    int(cx + math.cos(b) * rr),
                    int(cy + math.sin(b) * rr * 0.9),
                )
                for b in (math.tau * j / 7 for j in range(7))
            ]
            pygame.draw.polygon(small, col + (alpha,), pts)

    return pygame.transform.scale(small, (rad * 2, rad * 2))


def _puff_fn(kind, rad_m, alpha, variant):
    def draw(s, sx, sy, scale, z):
        rad = int(min(96, rad_m * scale)) // 2 * 2
        if rad < 2:
            return
        img = _puff_img(kind, rad, alpha, variant)
        s.blit(img, (int(sx) - rad, int(sy) - rad))

    draw.bounds_m = (rad_m, rad_m)
    draw.bounds_cap_px = (98, 98)
    return draw


_SEATED = dict(
    POSES["stand"],
    lhip_p=88,
    lkn=86,
    rhip_p=88,
    rkn=86,
    lsh_p=46,
    lel=40,
    rsh_p=46,
    rel=40,
    spine=6,
)
_SEATED_DEAD = dict(
    _SEATED,
    spine=40,
    head_p=40,
    lsh_p=6,
    lel=10,
    rsh_p=6,
    rel=10,
    twist=18,
)
_HANDS_UP = dict(
    POSES["stand"],
    lsh_p=168,
    lsh_r=14,
    lel=18,
    rsh_p=168,
    rsh_r=14,
    rel=18,
    head_p=8,
)
_KNEEL_HANDS = dict(
    POSES["kneel"],
    spine=8,
    lsh_p=120,
    lsh_r=62,
    lel=142,
    rsh_p=120,
    rsh_r=62,
    rel=142,
    head_p=22,
    rifle_p=0,
)


def _mix(a, b, f):
    out = dict(a)
    for k, v in b.items():
        if isinstance(v, (int, float)):
            out[k] = a.get(k, 0.0) + (v - a.get(k, 0.0)) * f
    return out


def _hold(hum, b):
    """Both hands on the mounted gun aimed b degrees up."""
    stance = dict(
        POSES["ready"],
        spine=POSES["ready"]["spine"] - 0.5 * b,
    )
    aim = (0.085, 1.45 + 60.0 * math.tan(math.radians(b)), 60.0)
    return hold_cached(
        hum, stance, "lmg", "aim", aim=aim, key="m8lmg"
    )


def _hold_at(hum, pitch):
    """Blend between the two nearest cached hold solves."""
    k = (clamp(pitch, *PITCH_LIM) - PITCH_LIM[0]) / PITCH_STEP
    i = min(
        int(k),
        int((PITCH_LIM[1] - PITCH_LIM[0]) / PITCH_STEP) - 1,
    )
    b0 = PITCH_LIM[0] + i * PITCH_STEP
    return _mix(
        _hold(hum, b0),
        _hold(hum, b0 + PITCH_STEP),
        k - i,
    )


def _frame(hum, pose):
    """Gun grip and rotation, body-local with feet at the origin."""
    j = hum.pose_world(
        pose, (0.0, 0.0, 0.0), 0.0, rifle_on=True
    )[1]
    return j["rhand"], j["rifle_m"]


def _gun_pt(hand, rm, q):
    d = m_apply(rm, q)
    return (
        hand[0] + d[0],
        hand[1] + d[1],
        hand[2] + d[2],
    )


_KEYS = {}


def _reload_keys(hum):
    """Reload poses solved against the gun levelled at RELOAD_PITCH."""
    if not _KEYS:
        base = _hold(hum, RELOAD_PITCH)
        hand, rm = _frame(hum, base)
        piv = _gun_pt(hand, rm, S.LMG_PIVOT)
        tx, ty, tz = S.RACK
        rack = (
            piv[0] + tx,
            S.POST_TOP - FEET + ty,
            piv[2] + tz[0],
        )
        grip = {
            "l": _gun_pt(hand, rm, GRIPS["lmg"]["fore"]),
            "r": hand,
        }

        for name, (lt, rt, stance) in RELOAD_KEYS.items():
            pose = dict(base, **stance)
            bent = "spine" in stance or "twist" in stance

            for side, tgt in (("l", lt), ("r", rt)):
                if tgt is None:
                    if not bent:
                        continue
                    p = grip[side]
                elif tgt[0] == "gun":
                    p = _gun_pt(hand, rm, tgt[1])
                else:
                    p = tuple(rack[i] + tgt[1][i] for i in range(3))

                pose = solve_arm_safe(
                    hum, pose, (0.0, 0.0, 0.0), 0.0, side, p
                )

            _KEYS[name] = pose

        _KEYS["grip"] = base

    return _KEYS


_REPAIR_KEYS = {}
_REPAIR_GRAB_LOCAL = (0.30, 0.99, -0.16)
_REPAIR_WORK_LOCAL = (0.16, 0.99, -0.32)


def _repair_keys(hum):
    """Crouch/toolbox/hammer poses on the trailer bed, solved once with IK."""
    if not _REPAIR_KEYS:
        base = dict(
            POSES["crouch"],
            spine=44,
            twist=-14,
            head_p=20,
            head_y=0,
            lsh_p=46,
            lsh_r=6,
            lel=42,
            rsh_p=44,
            rsh_r=2,
            rel=24,
        )
        # Reaching into the open toolbox (~0.58 m ahead of _REPAIR_GRAB_LOCAL)
        grab_base = dict(base, spine=52, twist=-12, head_p=22)
        grab = solve_arm_safe(hum, grab_base, (0.0, 0.0, 0.0), 0.0, "l", (-0.20, 0.32, 0.42))
        grab = solve_arm_safe(hum, grab, (0.0, 0.0, 0.0), 0.0, "r", (0.0, 0.24, 0.56))

        # High overhead wind-up before swinging down onto the coupling housing
        up_base = dict(
            base,
            spine=26,
            twist=18,
            head_p=8,
            head_y=-16,
            rsh_p=92,
            rsh_r=18,
            rsh_y=-14,
            rel=84,
        )
        work_up = solve_arm_safe(hum, up_base, (0.0, 0.0, 0.0), 0.0, "l", (-0.18, 0.28, 0.44))

        # Impact follow-through (left hand braced on deck/housing, hammer drives flat)
        dn_base = dict(
            base,
            spine=46,
            twist=-20,
            head_p=24,
            head_y=8,
            rsh_p=44,
            rsh_r=-8,
            rsh_y=4,
            rel=16,
        )
        work_down = solve_arm_safe(hum, dn_base, (0.0, 0.0, 0.0), 0.0, "l", (-0.18, 0.24, 0.46))

        _REPAIR_KEYS["reach"] = dict(base, spine=36, head_p=14)
        _REPAIR_KEYS["grab"] = grab
        _REPAIR_KEYS["work_up"] = work_up
        _REPAIR_KEYS["work_down"] = work_down
    return _REPAIR_KEYS


def _hammer_curve(frac):
    """Asymmetric hammer blow: 0 = struck down, 1 = cocked high."""
    if frac < 0.46:
        return R._ease(frac / 0.46)
    if frac < 0.56:
        return 1.0 - 0.02 * ((frac - 0.46) / 0.10)
    if frac < 0.72:
        u = (frac - 0.56) / 0.16
        return 0.98 * (1.0 - u ** 2.4)
    if frac < 0.88:
        u = (frac - 0.72) / 0.16
        return 0.18 * math.sin(math.pi * u)
    return 0.05 * ((frac - 0.88) / 0.12)


def _right_forearm_mat(pose, yaw):
    """Right-forearm world rotation matching Humanoid._placements()."""
    p = dict(NEUTRAL)
    p.update(pose)
    B = m_mul(rot_y(yaw), m_mul(rot_x(p["body_p"]), rot_z(p["body_r"])))
    S = m_mul(B, m_mul(rot_y(p["twist"]), m_mul(rot_x(p["spine"]), rot_z(p["spine_r"]))))
    U = m_mul(
        S,
        m_mul(
            rot_z(p["rsh_r"]),
            m_mul(rot_x(-p["rsh_p"]), rot_y(p.get("rsh_y", 0.0))),
        ),
    )
    return m_mul(U, rot_x(-p["rel"]))


def _cover_lift(el):
    if el is None:
        return 0.0
    return (
        62.0
        * R._ease(clamp((el - 0.62) / 0.18, 0.0, 1.0))
        * (
            1.0
            - R._ease(clamp((el - 3.25) / 0.15, 0.0, 1.0))
        )
    )


def _yaw_to(dx, dz):
    return math.degrees(math.atan2(dx, dz)) % 360.0


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _local(pos, yaw, off):
    c = math.cos(math.radians(yaw))
    s = math.sin(math.radians(yaw))
    x, y, z = off
    return (
        pos[0] + x * c + z * s,
        pos[1] + y,
        pos[2] + z * c - x * s,
    )


def _far_lamp(col, px):
    """A solid far lamp that rises out of the fog with its vehicle."""
    def draw(s, sx, sy, scale, z):
        if z > 58.0:
            k = clamp(
                (z - LAMP_RANGE) / (S.FOG_END + 60.0 - LAMP_RANGE),
                0.0,
                1.0,
            )
            c = tuple(
                int(a + (b - a) * k)
                for a, b in zip(col, S.FOG)
            )
            pygame.draw.circle(
                s,
                c,
                (int(sx), int(sy)),
                px if z > 150.0 else 1,
            )

    draw.bounds_m = (0.3, 0.3)
    draw.bounds_cap_px = (px + 1, px + 1)
    return draw


def _ray_sphere(o, d, c, rad):
    w = (
        c[0] - o[0],
        c[1] - o[1],
        c[2] - o[2],
    )
    s = w[0] * d[0] + w[1] * d[1] + w[2] * d[2]
    if s <= 0.0:
        return None

    q = (
        o[0] + d[0] * s - c[0],
        o[1] + d[1] * s - c[1],
        o[2] + d[2] * s - c[2],
    )
    if q[0] * q[0] + q[1] * q[1] + q[2] * q[2] > rad * rad:
        return None

    return s


# --- Bore-aligned muzzle-flash helpers --------------------------------------


def _f_unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


def _f_cross(a, b):
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _f_hash(seed, n):
    """Stable per-shot variation without consuming gameplay RNG."""
    x = math.sin(seed * 127.1 + n * 311.7) * 43758.5453
    return x - math.floor(x)


def _flash_submit(r, m, bias=-0.06):
    """Submit a flash mesh through the existing scene mesh path."""
    if hasattr(_w, "add"):
        _w.add(r, m)
        return

    faces = []
    for face in m.faces:
        idx = tuple(face[:-1])
        if len(idx) == 3:
            idx = (idx[0], idx[1], idx[2], idx[2])
        faces.append(
            (idx[0], idx[1], idx[2], idx[3], None, face[-1])
        )

    r.add_dynamic(m.verts, faces, bias=bias)


def _flash_col(c_hot, c_cool, k):
    t = 1.0 - clamp(k, 0.0, 1.0)
    return (
        int(c_hot[0] + (c_cool[0] - c_hot[0]) * t),
        int(c_hot[1] + (c_cool[1] - c_hot[1]) * t),
        int(c_hot[2] + (c_cool[2] - c_hot[2]) * t),
    )


def flash_star(tip, f, rx, ry, k, seed, scale=1.0):
    """A 3D axial flame rooted at the actual muzzle opening.

    All vertices lie on or ahead of the muzzle plane. Built from a 3D
    tapered core, a short forward expansion crown, and creased two-stage
    flame tongues so it reads cleanly from both side and ADS angles.
    """
    try:
        from engine3d import Mesh
    except ImportError:
        from engine3d.core import Mesh

    m = Mesh()
    k = clamp(k, 0.0, 1.0)
    if k <= 0.0:
        return m

    length = FLASH_LEN * scale * (0.48 + 0.52 * (k ** 0.65))
    radius = FLASH_CORE_R * scale * (0.72 + 0.28 * k)
    roll = math.radians((seed * 137.5) % 360.0) * FLASH_ROLL

    def pt(ahead, right, up):
        return (
            tip[0] + f[0] * ahead + rx[0] * right + ry[0] * up,
            tip[1] + f[1] * ahead + rx[1] * right + ry[1] * up,
            tip[2] + f[2] * ahead + rx[2] * right + ry[2] * up,
        )

    # 1. 3D incandescent inner core spindle (visible from any angle, incl. ADS).
    n_core = 5
    r0 = radius * 0.45
    r1 = radius * 0.95
    a1 = length * 0.14
    a_tip = length * 0.56
    tip_jit_a = roll + _f_hash(seed, 90) * math.tau
    apex = pt(
        a_tip,
        math.cos(tip_jit_a) * radius * 0.12,
        math.sin(tip_jit_a) * radius * 0.12,
    )

    ring0 = []
    ring1 = []
    for i in range(n_core):
        ang = roll + i * math.tau / n_core
        ca, sa = math.cos(ang), math.sin(ang)
        ring0.append(pt(0.0, ca * r0, sa * r0))
        ring1.append(pt(a1, ca * r1, sa * r1))

    col_c0 = _flash_col((255, 253, 240), (255, 195, 105), k)
    col_c1 = _flash_col((255, 238, 175), (255, 150, 52), k)
    for i in range(n_core):
        j = (i + 1) % n_core
        m.face([ring0[i], ring0[j], ring1[j]], col_c0, 2, True, True)
        m.face([ring0[i], ring1[j], ring1[i]], col_c0, 2, True, True)
        m.face([ring1[i], ring1[j], apex], col_c1, 2, True, True)

    # 2. Short forward-angled muzzle crown (3D creased fins right at the bore).
    col_crown = _flash_col((255, 224, 128), (242, 112, 32), k)
    for i in range(FLASH_PETALS):
        h1 = _f_hash(seed, 40 + i * 3)
        h2 = _f_hash(seed, 41 + i * 3)
        ang = roll + (
            i + 0.5 + 0.3 * (h1 - 0.5)
        ) * math.tau / FLASH_PETALS
        ca, sa = math.cos(ang), math.sin(ang)

        r_in = pt(0.0, ca * radius * 0.28, sa * radius * 0.28)
        r_l = pt(
            0.0,
            ca * radius * 0.45 - sa * radius * 0.45,
            sa * radius * 0.45 + ca * radius * 0.45,
        )
        r_r = pt(
            0.0,
            ca * radius * 0.45 + sa * radius * 0.45,
            sa * radius * 0.45 - ca * radius * 0.45,
        )
        flare_r = radius * (1.55 + 0.75 * h1)
        f_tip = pt(
            length * (0.14 + 0.12 * h2),
            ca * flare_r,
            sa * flare_r,
        )
        m.face([r_in, r_l, f_tip], col_crown, 2, True, True)
        m.face([r_in, f_tip, r_r], col_crown, 2, True, True)

    # 3. Uneven two-stage 3D axial flame tongues.
    col_mid = _flash_col((255, 206, 84), (240, 102, 24), k)
    col_tip = _flash_col((255, 132, 32), (205, 58, 14), k)

    for i in range(FLASH_PETALS):
        h1 = _f_hash(seed, i * 3 + 1)
        h2 = _f_hash(seed, i * 3 + 2)
        h3 = _f_hash(seed, i * 3 + 3)
        angle = roll + (
            i + 0.42 * (h2 - 0.5)
        ) * math.tau / FLASH_PETALS
        ca, sa = math.cos(angle), math.sin(angle)

        tongue_len = length * (0.58 + 0.58 * h1)
        mid_a = tongue_len * (0.32 + 0.14 * h3)

        root_in = pt(0.0, ca * radius * 0.25, sa * radius * 0.25)
        root_l = pt(
            0.0,
            ca * radius * 0.55 - sa * radius * 0.50,
            sa * radius * 0.55 + ca * radius * 0.50,
        )
        root_r = pt(
            0.0,
            ca * radius * 0.55 + sa * radius * 0.50,
            sa * radius * 0.55 - ca * radius * 0.50,
        )

        mid_r = radius * (1.05 + 0.65 * h2)
        wing_r = radius * 0.72
        wing_w = radius * (0.42 + 0.25 * h3)

        mid_ridge = pt(mid_a, ca * mid_r, sa * mid_r)
        mid_l = pt(
            mid_a,
            ca * wing_r - sa * wing_w,
            sa * wing_r + ca * wing_w,
        )
        mid_rt = pt(
            mid_a,
            ca * wing_r + sa * wing_w,
            sa * wing_r - ca * wing_w,
        )

        tip_r = radius * (0.25 + 0.45 * h1)
        end_pt = pt(tongue_len, ca * tip_r, sa * tip_r)

        m.face([root_in, root_l, mid_ridge], col_mid, 2, True, True)
        m.face([root_l, mid_l, mid_ridge], col_mid, 2, True, True)
        m.face([root_in, mid_ridge, root_r], col_mid, 2, True, True)
        m.face([root_r, mid_ridge, mid_rt], col_mid, 2, True, True)
        m.face([mid_l, end_pt, mid_ridge], col_tip, 2, True, True)
        m.face([mid_ridge, end_pt, mid_rt], col_tip, 2, True, True)

    return m


class ChaseScene:
    _snd = R.RaidScene._snd
    _grab = R.RaidScene._grab

    def __init__(self):
        self._active = False
        self.paused = False
        self.done = False
        self.result = None
        self.audio = None
        self._heli_seen = False
        self._setup(0)

    # --- lifecycle ---------------------------------------------------------

    def begin(self):
        self.done = False
        self.result = None
        self._active = True
        self.paused = False
        STATE.m8_chase_active = True

        try:
            from .. import m8_audio as _m8_audio

            self.audio = _m8_audio.instance(audio)
            self.audio.warm()
        except Exception:
            self.audio = None

        cp = int(getattr(STATE, "m8_chase_cp", 0) or 0)
        ending = bool(getattr(STATE, "m8_chase_ending", False))
        heli = bool(getattr(STATE, "m8_chase_heli", False))
        if ending:
            STATE.m8_chase_ending = False
            cp = 4
        elif heli:
            STATE.m8_chase_heli = False
            cp = 3
        if cp < 3 or heli:
            self._heli_seen = False
        if cp:
            self._setup(cp)
            if ending:
                # dev --dev-mission8-ending: the last jeep is already burning at the crossing
                self.z = S.CROSSING_Z - 0.5
                for e in self.enemies:
                    if e["kind"] == "blocker":
                        self._wreck(e)
            elif cp == 3 and not self._heli_seen:
                self._start_heli_cutscene()
        else:
            self._adopt(pullout_scene(PULL_S))

        self._grab(True)

        try:
            S.renderer()
            S.helicopter_parts()
            S.rocket()
            hum = _w.hum(BIRIBEL, flags=(GUN,))
            _w.hum(("guard", "heavy"), flags=("os12",))
            b = PITCH_LIM[0]
            while b <= PITCH_LIM[1]:
                _hold(hum, b)
                b += PITCH_STEP
            _reload_keys(hum)
            _repair_keys(hum)
        except Exception:
            pass

    def _setup(self, cp, t=0.0):
        self.cp = max(0, min(4, cp))
        self.t = t
        self.sec_t = 0.0
        self.z = S.SECTIONS[self.cp] + (
            0.0 if self.cp else -10.0
        )
        self.speed = SPEED
        self.lane = 0.0
        self.hull = HULL

        self.yaw = 180.0
        self.pitch = -3.0
        self.mag = MAG
        self.reloading = 0.0
        self.cans = []
        self._can_at = None
        self._rig_key = None

        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.last_fire = -9.0

        # Separate actual discharge time from dry-fire cooldown.
        self.last_flash = -9.0
        self.flash_seed = 0

        self.kick = 0.0
        self.heat = 0.0
        self.odo = 0.0
        self.hit_mark = -9.0
        self.enemies = []
        self.spawn_i = 0
        self.wreck_done = set()
        self.lines = []
        self.said = set()
        self.flashes = []
        self.bullets = []
        self.impacts = []
        self.sparks = []
        self.puffs = []
        self.hurt = 0.0
        self.dmg_marks = []
        self._hit_snd_t = -9.0
        self._emit = {}

        self.dying = False
        self.death_t = 0.0
        self.death_msg = ""
        self.wreck_t = None
        self.slew = 0.0
        self.captors = []
        self.heli = None
        self.rockets = []
        self.repairs = REPAIRS_MAX
        self.repair_t = None
        self._repair_heal_left = 0.0
        self._repair_spark_i = -1
        self._cutscene_wait = False
        self.dodge_t = None
        self.dodge_lane = 0.0

        self.cp_toast = self.t if self.cp else -9.0
        self.timer = CROSSING_TIME if self.cp == 4 else None
        self.end_t = None
        self._jump_start = None
        self.barrier_t = None
        self.train_t = None
        self.fade = 0.0
        self.shake = 0.0
        self._snd_t = -9.0
        self._crash_t = -9.0

        if self.cp == 4:
            self._spawn(
                "blocker",
                0.0,
                z=S.CROSSING_Z,
                x=S.road_x(S.CROSSING_Z) - 0.4,
            )
        if self.cp == 3:
            self._spawn_heli()

        if self.cp == 0:
            self.say(
                "BODI",
                "They're on us. The tyres, Biribel - shoot the tyres!",
                3.6,
            )

        self._snd("trac_move")

        if self.cp == 3 and self._heli_seen:
            self._spawn_heli()

    def _adopt(self, sim):
        """Begin where the descent pullout ends."""
        self._setup(0, t=sim.t)
        self.z, self.speed, self.odo = sim.z, sim.speed, sim.odo
        self.sec_t, self.spawn_i = sim.sec_t, sim.spawn_i
        self.enemies = copy.deepcopy(sim.enemies)

    def active(self):
        return self._active

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

    def finish(self, result="done"):
        if self.done:
            return False

        self.done = True
        self.result = result
        self._active = False
        STATE.m8_chase_active = False
        self._grab(False)

        if self.audio is not None:
            try:
                self.audio.stop_loops()
            except Exception:
                pass

        from .. import flow as _flow

        return _flow.on_chase_done(result)

    def say(self, who, text, dur=3.0, key=None):
        if key is not None:
            if key in self.said:
                return
            self.said.add(key)

        self.lines.append((self.t, who, text, dur))
        del self.lines[:-3]

    # --- input -------------------------------------------------------------

    def handle_event(self, event):
        if not self._active or self.paused:
            return
        if self.repair_t is not None:
            return

        if (
            event.type == pygame.MOUSEMOTION
            and not self.dying
            and self.end_t is None
        ):
            dx, dy = event.rel
            sens = SENS * (1.0 - ADS_SENS * self.ads)
            self.yaw = (self.yaw + dx * sens) % 360.0
            self.pitch = clamp(
                self.pitch - dy * sens, *PITCH_LIM
            )
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 1
        ):
            self.firing = True
        elif (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 1
        ):
            self.firing = False
        elif (
            event.type == pygame.MOUSEBUTTONDOWN
            and event.button == 3
        ):
            self.aiming = True
        elif (
            event.type == pygame.MOUSEBUTTONUP
            and event.button == 3
        ):
            self.aiming = False
        elif (
            event.type == pygame.KEYDOWN
            and event.key in (pygame.K_SPACE, pygame.K_a, pygame.K_d)
            and not self.dying
            and self.end_t is None
        ):
            self._try_dodge(event.key)
        elif (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_r
        ):
            self._reload()
        elif (
            event.type == pygame.KEYDOWN
            and event.key == pygame.K_e
            and self.repair_t is None
            and not self.dying
            and self.end_t is None
            and self.wreck_t is None
            and not self._cutscene_wait
        ):
            self._try_repair()

    # --- geometry ----------------------------------------------------------

    def tractor_pos(self):
        z = self.z
        y = S.ditch_y(z)
        d = z - S.DITCH_Z

        if -6.0 <= d < 6.0:
            y = max(
                y,
                1.0
                + 0.25 * math.sin(math.pi * (d + 6.0) / 12.0)
                - ((d + 6.0) / 12.0) ** 2,
            )

        return (
            S.road_x(z) + self.lane,
            y,
            z,
        ), S.road_yaw(z) + self.slew

    def tractor_pitch(self):
        d = self.z - S.DITCH_Z
        if -6.0 <= d < 6.0:
            return 4.0 - 10.0 * (d + 6.0) / 12.0
        if 6.0 <= d < 9.0:
            return -6.0 * (1.0 - (d - 6.0) / 3.0)
        return S.ditch_pitch(self.z)

    def trailer_pos(self):
        z = self.z - HITCH
        y = S.ditch_y(z)
        d = z - S.DITCH_Z

        if -6.0 <= d < 6.0:
            y = max(
                y,
                1.0
                + 0.2 * math.sin(math.pi * (d + 6.0) / 12.0)
                - ((d + 6.0) / 12.0) ** 2,
            )

        return (
            S.road_x(z) + self.lane,
            y,
            z,
        ), S.road_yaw(z) - 0.5 * self.slew

    def biribel_pos(self):
        return self._rig()["feet"]

    def reload_el(self):
        return RELOAD_S - self.reloading if self.reloading else None

    def _rig(self):
        """Mount, gun orientation, gunner pose and feet for this frame."""
        key = (
            self.t,
            self.z,
            self.lane,
            self.yaw,
            self.pitch,
            self.reloading,
            self.kick,
        )
        if self._rig_key == key:
            return self._rig_v

        hum = _w.hum(BIRIBEL, flags=(GUN,))
        el = self.reload_el()
        pe = self.pitch

        if el is not None:
            w = R._ease(
                clamp(
                    min(el / 0.3, (RELOAD_S - el) / 0.22),
                    0.0,
                    1.0,
                )
            )
            pe += (RELOAD_PITCH - pe) * w

        base = _hold_at(hum, pe)
        hand, rm = _frame(hum, base)
        (lx, ly, lz), lyaw = self.trailer_pos()

        top = S._xf(
            (S.MOUNT[0], S.POST_TOP, S.MOUNT[1]),
            (lx, ly, lz),
            lyaw,
            S.ditch_pitch(lz),
        )
        piv = _gun_pt(hand, rm, S.LMG_PIVOT)
        c = math.cos(math.radians(self.yaw))
        s = math.sin(math.radians(self.yaw))

        feet = (
            top[0] - (piv[0] * c + piv[2] * s),
            ly + FEET,
            top[2] - (piv[2] * c - piv[0] * s),
        )
        fwd = m_apply(rm, (0.0, 0.0, 1.0))
        pivot = (top[0], feet[1] + piv[1], top[2])

        self._rig_v = {
            "feet": feet,
            "top": top,
            "pivot": pivot,
            "h": pivot[1] - top[1],
            "gyaw": self.yaw + math.degrees(
                math.atan2(fwd[0], fwd[2])
            ),
            "gpitch": math.degrees(
                math.asin(clamp(fwd[1], -1.0, 1.0))
            ) + 0.8 * self.kick,
            "pose": (
                base
                if el is None
                else self._reload_pose(hum, el, base)
            ),
            "el": el,
        }
        self._rig_key = key
        return self._rig_v

    def _reload_pose(self, hum, el, base):
        keys = _reload_keys(hum)
        for (t0, k0), (t1, k1) in zip(
            RELOAD_TRACK, RELOAD_TRACK[1:]
        ):
            if el <= t1:
                break

        if k0 == k1 == "grip":
            return base

        return _mix(
            keys[k0],
            keys[k1],
            R._ease(clamp((el - t0) / (t1 - t0), 0.0, 1.0)),
        )

    def gun_pt(self, q):
        """Transform a gun-space point using the rendered gun's transform."""
        g = self._rig()
        o = S.LMG_PIVOT
        return S._xf(
            (q[0] - o[0], q[1] - o[1], q[2] - o[2]),
            g["pivot"],
            g["gyaw"],
            g["gpitch"],
        )

    def eye_dir(self):
        y = math.radians(self.yaw)
        p = math.radians(self.pitch + 2.2 * self.kick)
        return (
            math.sin(y) * math.cos(p),
            math.sin(p),
            math.cos(y) * math.cos(p),
        )

    def _combat_camera(self):
        if (
            self.wreck_t is not None
            and self.t - self.wreck_t > 0.3
        ):
            el = self.t - self.wreck_t
            (tx, _ty, tz), tyaw = self.tractor_pos()
            (lx, _ly, lz), _ = self.trailer_pos()
            mid = (
                (tx + lx) / 2.0,
                S.ditch_y((tz + lz) / 2.0),
                (tz + lz) / 2.0,
            )
            yaw = tyaw - self.slew

            if el < 5.0:
                e = el - 0.3
                eye = _local(
                    mid,
                    yaw,
                    (
                        -16.0 + 0.6 * e,
                        3.2 - 0.1 * e,
                        -12.0 + 0.5 * e,
                    ),
                )
                return (
                    eye,
                    _local(mid, yaw, (-1.0, 1.0, -5.0)),
                    56.0,
                )

            e = el - 5.0
            b = self._ground(
                self.trailer_pos(), (-1.9, 0.0, -0.2)
            )
            eye = _local(
                b, yaw, (-6.8 + 0.2 * e, 3.6 - 0.1 * e, 1.9)
            )
            return (
                eye,
                _local(b, yaw, (0.4, 0.6, 1.9)),
                48.0,
            )

        if self.end_t is not None:
            el = self.t - self.end_t
            (tx, ty, tz), _ = self.tractor_pos()
            pan = 1.2 * max(0.0, el - 2.0)
            return (
                (tx - 9.0 + 0.4 * el, 2.4, tz - 7.0),
                (tx + 4.0 + pan, 1.6, tz + 1.0),
                52.0,
            )

        bx, by, bz = self.biribel_pos()
        d = self.eye_dir()
        head = (bx, by + 1.62, bz)
        rx = math.cos(math.radians(self.yaw))
        rz = -math.sin(math.radians(self.yaw))
        sh = self.shake * (1.0 - 0.6 * self.ads)
        wob = (
            math.sin(self.t * 37.0) * 0.05 * sh,
            math.sin(self.t * 29.0) * 0.07 * sh,
        )
        eye = (
            head[0] - d[0] * 2.5 + rx * 0.85 + wob[0],
            head[1] + 0.45 - d[1] * 1.2 + wob[1],
            head[2] - d[2] * 2.5 + rz * 0.85,
        )
        tgt = (
            head[0] + d[0] * 20.0 + rx * 0.85,
            head[1] + d[1] * 20.0,
            head[2] + d[2] * 20.0 + rz * 0.85,
        )
        fov = 60.0

        a = self.ads
        if a > 0.0:
            se = self.gun_pt(ADS_EYE)
            sp = self.gun_pt(ADS_POST)
            sd = tuple(sp[i] - se[i] for i in range(3))
            n = math.sqrt(sum(c * c for c in sd)) or 1.0
            sd = tuple(c / n for c in sd)
            st = tuple(
                se[i] + sd[i] * 40.0 for i in range(3)
            )
            eye = tuple(
                eye[i] + (se[i] - eye[i]) * a
                for i in range(3)
            )
            tgt = tuple(
                tgt[i] + (st[i] - tgt[i]) * a
                for i in range(3)
            )
            fov += (ADS_FOV - fov) * a

        return eye, tgt, fov

    def camera(self):
        base = self._combat_camera()
        if self.repair_t is None:
            return base
        el = self.t - self.repair_t
        w = R._ease(clamp(min(el / 0.40, (REPAIR_S - el) / 0.40), 0.0, 1.0))
        (lx, ly, lz), lyaw = self.trailer_pos()
        lp = S.ditch_pitch(lz)
        s_eye = S._xf((2.25, 2.55, -1.45), (lx, ly, lz), lyaw, lp)
        s_tgt = S._xf((0.22, 1.30, 0.16), (lx, ly, lz), lyaw, lp)
        eye = tuple(base[0][i] + (s_eye[i] - base[0][i]) * w for i in range(3))
        tgt = tuple(base[1][i] + (s_tgt[i] - base[1][i]) * w for i in range(3))
        fov = base[2] + (50.0 - base[2]) * w
        return eye, tgt, fov

    def aim_ray(self):
        eye, tgt, _fov = self.camera()
        d = tuple(tgt[i] - eye[i] for i in range(3))
        n = math.sqrt(sum(c * c for c in d)) or 1.0
        return eye, tuple(c / n for c in d)

    # --- enemies -----------------------------------------------------------

    def _spawn(self, kind, lat, z=None, x=None):
        tz = self.z
        e = {
            "kind": kind,
            "lat": lat,
            "alive": True,
            "wrecked": False,
            "t0": self.t,
            "hp": HP[kind],
            "tyre_hp": {},
            "driver_hp": DRIVER_HP.get(kind, 1),
            "gunner_hp": GUNNER_HP,
            "odo": 0.0,
            "cool": 1.6,
            "dead_t": 0.0,
            "spin": 0.0,
            "gunner": kind == "gun_truck",
            "driver": True,
            "v": SPEED,
            "slot": len(self.enemies),
            "_trac": False,
            "wy": 0.0,
            "wvy": 0.0,
            "wp": 0.0,
            "wpr": 0.0,
            "wr": 0.0,
            "wrr": 0.0,
            "wyr": 0.0,
            "w_lat": 0.0,
            "w_fric": WRECK_DECEL,
        }

        if kind in ("jeep", "gun_truck"):
            if z is None:
                eye, _tgt, _fov = self.camera()
                e["z"] = eye[2] - SPAWN_BACK
            else:
                e["z"] = z

            e["gap"] = (
                11.0
                + 4.0 * (e["slot"] % 3)
                + (8.0 if kind == "gun_truck" else 0.0)
            )

            if kind == "gun_truck":
                e["x"] = S.road_x(e["z"]) + 34.0
            else:
                e["x"] = S.road_x(e["z"]) + lat
        else:
            e["z"] = tz if z is None else z
            e["x"] = (
                S.road_x(e["z"]) + lat if x is None else x
            )

        e["yaw"] = (
            90.0 if kind == "blocker" else S.road_yaw(e["z"])
        )
        y, pitch, roll = self._ground_pose(kind, e["x"], e["z"], e["yaw"])
        e["y"] = y
        e["vy"] = 0.0
        e["pitch"] = pitch
        e["roll"] = roll
        e["_gy"] = y
        e["wy"] = y
        e["wp"] = pitch
        e["wr"] = roll
        self.enemies.append(e)
        return e

    def _spawns(self):
        table = SPAWNS[self.cp]

        while (
            self.spawn_i < len(table)
            and self.sec_t >= table[self.spawn_i][0]
        ):
            _t, kind, lat = table[self.spawn_i]
            self.spawn_i += 1
            self._spawn(kind, lat)

            if kind == "gun_truck":
                self.say(
                    "BODI",
                    "Truck with a gun - coming in on the right!",
                    3.2,
                    key="gun_truck",
                )
            elif kind == "jeep":
                self.say(
                    "BODI",
                    "Lights on the road behind us - here they come!",
                    3.0,
                    key="jeeps",
                )

        if self.cp == 2:
            for i, (wx, wz) in enumerate(S.wrecks()):
                if (
                    i not in self.wreck_done
                    and self.z > wz - 22.0
                    and self.z < wz + 10.0
                ):
                    self.wreck_done.add(i)
                    side = (
                        1.0 if wx > S.road_x(wz) else -1.0
                    )
                    for k in range(1 + i % 2):
                        self._spawn(
                            "foot",
                            0.0,
                            z=wz - 1.5 + k * 2.2,
                            x=wx - side * (1.6 + 0.4 * k),
                        )
                    self.say(
                        "BODI",
                        "They're getting out of the cars!",
                        2.8,
                        key="bail",
                    )

    def alive_count(self):
        return sum(
            1 for e in self.enemies
            if e["alive"] and not e["wrecked"]
        ) + (1 if self.heli_active() else 0)

    def _enemy_move(self, dt):
        tz = self.z

        for e in self.enemies:
            if e["kind"] in ("jeep", "gun_truck"):
                if e["wrecked"]:
                    self._wreck_step(e, dt)
                else:
                    target = tz - HITCH - e["gap"]
                    v = self.speed + clamp(
                        (target - e["z"]) * 0.9,
                        -6.0,
                        CLOSE_MAX,
                    )
                    e["v"] = max(
                        min(v, self._follow_cap(e)),
                        e["v"] - BRAKE * dt,
                    )
                    want = (
                        S.road_x(e["z"]) + self._avoid_lat(e)
                    )
                    cur_lat = e["x"] - S.road_x(e["z"])
                    rate = (
                        (
                            0.8
                            if abs(cur_lat) > S.ROAD_W / 2.0 + 1.5
                            else 1.6
                        )
                        if e["kind"] == "gun_truck"
                        else 2.2
                    )
                    step = (
                        (want - e["x"]) * min(1.0, dt * rate)
                    )
                    e["x"] += clamp(
                        step, -LAT_MAX * dt, LAT_MAX * dt
                    )

                e["z"] += e["v"] * dt
                if not e["wrecked"]:
                    e["odo"] += e["v"] * dt
                e["yaw"] = S.road_yaw(e["z"]) + e["spin"]

            elif e["kind"] == "blocker" and e["wrecked"]:
                self._wreck_step(e, dt)
                e["yaw"] = 90.0 + e["spin"]

        self._resolve_contacts(dt)
        for e in self.enemies:
            if e["kind"] == "foot":
                continue
            if e["wrecked"]:
                self._sync_wreck_ground(e)
            else:
                self._step_vehicle_y(e, dt)

    @staticmethod
    def _lift(e, pitch, roll=0.0):
        """Required body height to clear the ground at this tilt."""
        k = 1.3 if e["kind"] == "gun_truck" else 1.0
        p, r = math.radians(pitch), math.radians(roll)
        sp, cp = math.sin(p), math.cos(p)
        sr, cr = math.sin(r), math.cos(r)

        return k * (
            0.95 * abs(sr * cp)
            + 1.6 * abs(sp)
            + 1.5 * max(0.0, -cr * cp)
        )

    @staticmethod
    def _axles(kind):
        return (
            (-2.0, 1.9, 0.85)
            if kind == "gun_truck"
            else (-1.25, 1.25, 0.82)
        )

    def _ground_pose(self, kind, x, z, yaw):
        """Ground-fitted (y, pitch, roll) at the four tyres of ``kind``."""
        if kind == "foot":
            return S.surface_y(x, z), 0.0, 0.0

        lr, lf, hw = self._axles(kind)
        cy = math.cos(math.radians(yaw))
        sy = math.sin(math.radians(yaw))

        def sy_at(xl, zl):
            return S.surface_y(
                x + xl * cy + zl * sy,
                z + zl * cy - xl * sy,
            )

        y_rl, y_rr = sy_at(-hw, lr), sy_at(hw, lr)
        y_fl, y_fr = sy_at(-hw, lf), sy_at(hw, lf)
        if y_rl == 0.0 and y_rr == 0.0 and y_fl == 0.0 and y_fr == 0.0:
            return 0.0, 0.0, 0.0

        y_r = 0.5 * (y_rl + y_rr)
        y_f = 0.5 * (y_fl + y_fr)
        y_l = 0.5 * (y_rl + y_fl)
        y_rt = 0.5 * (y_rr + y_fr)

        y = y_r + (-lr) / (lf - lr) * (y_f - y_r)
        pitch = math.degrees(math.atan2(y_f - y_r, lf - lr))
        roll = math.degrees(math.atan2(y_rt - y_l, 2.0 * hw))
        return y, pitch, roll

    def _air_pitch_limits(self, kind, x, y, z, yaw, roll):
        lr, lf, hw = self._axles(kind)
        cy = math.cos(math.radians(yaw))
        sy = math.sin(math.radians(yaw))
        sr = math.sin(math.radians(roll))

        def sy_at(xl, zl):
            return S.surface_y(
                x + xl * cy + zl * sy,
                z + zl * cy - xl * sy,
            )

        yf_req = max(sy_at(-hw, lf) + hw * sr, sy_at(hw, lf) - hw * sr)
        yr_req = max(sy_at(-hw, lr) + hw * sr, sy_at(hw, lr) - hw * sr)
        p_min = (
            math.degrees(math.asin(clamp((yf_req - y) / lf, -1.0, 1.0)))
            if y - yf_req < lf
            else -90.0
        )
        p_max = (
            math.degrees(math.asin(clamp((y - yr_req) / (-lr), -1.0, 1.0)))
            if y - yr_req < -lr
            else 90.0
        )
        return p_min, p_max

    def _step_vehicle_y(self, e, dt, speed=None):
        gy, gp, gr = self._ground_pose(e["kind"], e["x"], e["z"], e["yaw"])
        prev_gy = e.get("_gy", gy)
        e["_gy"] = gy
        y = e.get("y", gy)
        vy = e.get("vy", 0.0)
        pitch = e.get("pitch", gp)

        if dt <= 1e-6:
            e["y"] = max(y, gy)
            e["vy"] = vy
            e["pitch"] = gp if e["y"] <= gy + 0.005 else pitch
            e["roll"] = gr
            return

        slope_vy = (gy - prev_gy) / dt
        if y <= gy + 0.005 and vy <= slope_vy + 0.25:
            y = gy
            vy = slope_vy
            pitch = gp
        else:
            vy -= 9.8 * dt
            y += vy * dt
            spd = abs(e["v"] if speed is None else speed)
            target_p = clamp(
                math.degrees(math.atan2(vy, max(spd, 1.0))) * 0.6,
                -10.0,
                8.0,
            )
            pitch += (target_p - pitch) * min(1.0, dt * 6.0)
            if y <= gy:
                y = gy
                vy = slope_vy
                pitch = gp
            else:
                p_min, p_max = self._air_pitch_limits(
                    e["kind"], e["x"], y, e["z"], e["yaw"], gr
                )
                if p_min <= p_max:
                    pitch = clamp(pitch, p_min, p_max)
                else:
                    y = gy
                    vy = slope_vy
                    pitch = gp

        e["y"] = y
        e["vy"] = vy
        e["pitch"] = pitch
        e["roll"] = gr

    def _wreck_floor(self, e):
        gy, gp, gr = self._ground_pose(e["kind"], e["x"], e["z"], e["yaw"])
        rel_p = e["wp"] - gp
        sgn_p = 1.0 if math.cos(math.radians(rel_p)) >= 0.0 else -1.0
        rel_r = e["wr"] - sgn_p * gr
        floor = gy + self._lift(e, rel_p, rel_r)
        return gy, gp, gr, rel_p, sgn_p, rel_r, floor

    def _sync_wreck_ground(self, e):
        _, _, _, _, _, _, floor = self._wreck_floor(e)
        if e["wy"] < floor:
            e["wy"] = floor

    def _enemy_pose(self, e):
        if e["kind"] == "foot":
            return S.surface_y(e["x"], e["z"]), 0.0, 0.0
        if e["wrecked"]:
            return e["wy"], e["wp"], e["wr"]
        if "y" in e:
            return e["y"], e["pitch"], e["roll"]
        return self._ground_pose(e["kind"], e["x"], e["z"], e["yaw"])

    def _wreck_step(self, e, dt):
        """Ballistic wreck motion, landing, sliding and settling."""
        gy, gp, gr, rel_p, sgn_p, rel_r, floor = self._wreck_floor(e)
        air = (
            e["wy"] > floor + 0.02
            or e["wvy"] > 0.1
        )

        if air:
            e["wvy"] -= 9.8 * dt
            e["wy"] += e["wvy"] * dt
            e["wp"] += e["wpr"] * dt
            e["wr"] += e["wrr"] * dt
        else:
            if (
                math.cos(math.radians(rel_p))
                * math.cos(math.radians(rel_r))
                > 0.9
            ):
                fric = e["w_fric"] + 10.0 * abs(
                    math.sin(math.radians(e["spin"]))
                )
            else:
                fric = 13.0

            e["v"] = max(0.0, e["v"] - fric * dt)
            e["wyr"] *= math.exp(
                -(4.0 + 6.0 / (1.0 + e["v"])) * dt
            )
            k = min(1.0, dt * 6.0)
            e["wp"] += (
                gp + round(rel_p / 180.0) * 180.0 - e["wp"]
            ) * k
            e["wr"] += (
                sgn_p * gr + round(rel_r / 90.0) * 90.0 - e["wr"]
            ) * k

        e["spin"] += e["wyr"] * dt
        _, _, _, _, _, _, floor = self._wreck_floor(e)

        if e["wy"] < floor or not air:
            e["wy"] = floor

        if e["wy"] <= floor and e["wvy"] <= 0.0:
            if air and e["wvy"] < -2.5:
                hit = -e["wvy"]
                e["wvy"] = hit * 0.35
                e["wpr"] *= 0.45
                e["wrr"] *= 0.55
                e["wyr"] *= 0.8
                self._burst(e, "blast", 3, 1.5, y=0.2)
                e["v"] *= 0.6
                e["w_lat"] *= 0.5

                if self.t - self._crash_t > 0.2:
                    self._crash_t = self.t
                    self._snd(
                        "metal", 0.0, min(0.5, hit / 14.0)
                    )
            else:
                e["wvy"] = 0.0
                e["wpr"] = 0.0
                e["wrr"] = 0.0

        lat = (
            e["x"]
            - S.road_x(e["z"])
            + e["w_lat"] * dt
        )
        e["w_lat"] *= math.exp(
            -(0.6 if air else 4.0) * dt
        )
        lim = S.ROAD_W / 2.0 + 2.5

        if abs(lat) > lim:
            lat = clamp(lat, -lim, lim)
            e["w_lat"] = 0.0

        e["x"] = S.road_x(e["z"]) + lat

    @staticmethod
    def _radius(e):
        return (
            S.TRUCK_R if e["kind"] == "gun_truck" else S.CAR_R
        )

    def _obstacles(self):
        out = [
            (
                e["x"],
                e["z"],
                self._radius(e),
                self.t - e["dead_t"],
            )
            for e in self.enemies
            if e["kind"] in ("jeep", "gun_truck")
            and e["wrecked"]
        ]
        if self.cp == 2:
            out.extend(
                (wx, wz, S.WRECK_R, 999.0)
                for wx, wz in S.wrecks()
            )
        return out

    def _follow_cap(self, e):
        """Safe following speed, allowing reaction delay to fresh wrecks."""
        lat = e["x"] - S.road_x(e["z"])
        r = self._radius(e)
        cap = 1e9

        ahead = [
            (
                o["x"],
                o["z"],
                self._radius(o),
                o["v"] if o["kind"] != "blocker" else 0.0,
            )
            for o in self.enemies
            if o is not e
            and o["kind"] in ("jeep", "gun_truck", "blocker")
            and not (
                o["wrecked"]
                and self.t - o["dead_t"] < REACT_S
            )
        ]

        if self.cp == 2:
            ahead.extend(
                (wx, wz, S.WRECK_R, 0.0)
                for wx, wz in S.wrecks()
            )

        for ox, oz, orad, ov in ahead:
            gap = oz - e["z"]
            # Alongside is not ahead: contacts keep them apart, and braking
            # for a neighbour deadlocks two cars beside a wreck.
            if gap <= r + orad or gap > 70.0:
                continue

            ob = ox - S.road_x(oz)
            if abs(ob - lat) > r + orad + 0.25:
                continue

            room = max(0.0, gap - r - orad - 1.0)
            cap = min(
                cap,
                max(ov, 0.0)
                + math.sqrt(2.0 * BRAKE * 0.8 * room),
            )

        return cap

    def _avoid_lat(self, e):
        """Pick a clear lateral passing offset around wrecks and rubbish."""
        cur_lat = e["x"] - S.road_x(e["z"])
        r = self._radius(e)
        edge = max(0.5, S.ROAD_W / 2.0 - r)
        near_bridge = S.DITCH_Z - 26.0 <= e["z"] <= S.DITCH_Z + 4.0
        shoulder = (
            S.ROAD_W / 2.0 - 0.5
            if near_bridge
            else S.ROAD_W / 2.0 + 1.5
        )
        pref = clamp(e["lat"], -edge, edge)

        speed = max(e["v"], 0.0)
        look_ahead = max(24.0, min(65.0, speed * 3.5 + r * 3.0))
        react = speed * REACT_S
        holding = abs(cur_lat - pref) < 0.3

        relevant = []
        for ox, oz, orad, age in self._obstacles():
            if age < REACT_S:
                continue
            gap = oz - e["z"]
            if -(r + orad + 0.5) <= gap <= look_ahead:
                ob_lat = ox - S.road_x(oz)
                # Inside reaction distance and not yet swerving: too late.
                if (
                    holding
                    and 0.0 < gap < react
                    and abs(cur_lat - ob_lat) < r + orad
                ):
                    continue
                relevant.append((gap, ob_lat, orad))

        if not relevant:
            return pref

        relevant.sort(key=lambda item: item[0])
        min_gap = relevant[0][0]

        clear_pref = all(
            abs(pref - ob_lat) >= r + orad + 0.45
            for _gap, ob_lat, orad in relevant
        )
        if clear_pref:
            blocked_path = False
            for gap, ob_lat, orad in relevant:
                if gap <= r + orad + 4.0:
                    lo = min(cur_lat, pref) - (r + orad + 0.35)
                    hi = max(cur_lat, pref) + (r + orad + 0.35)
                    if lo <= ob_lat <= hi:
                        blocked_path = True
                        break
            if not blocked_path:
                return pref

        cands = [pref, clamp(cur_lat, -shoulder, shoulder)]
        for _gap, ob_lat, orad in relevant[:3]:
            clr = r + orad + 0.65
            for side in (-1.0, 1.0):
                c = ob_lat + side * clr
                cands.append(clamp(c, -edge, edge))
                cands.append(clamp(c, -shoulder, shoulder))
        cands.extend((-edge, 0.0, edge))

        def score(cand):
            near_pen = 0.0
            far_pen = 0.0
            for gap, ob_lat, orad in relevant:
                ov = (r + orad + 0.45) - abs(cand - ob_lat)
                if ov > 0.0:
                    if gap <= min_gap + r + orad + 3.0:
                        near_pen += 1000.0 * ov
                    else:
                        far_pen += (
                            50.0
                            / (1.0 + max(0.0, gap) * 0.1)
                        ) * ov
            off_road = max(0.0, abs(cand) - edge)
            move_cost = (
                abs(cand - cur_lat) * 0.35
                + abs(cand - pref) * 0.15
            )
            return (near_pen, far_pen, off_road, move_cost)

        return min(cands, key=score)

    def _crash_hit(self, a, b):
        live = False

        for e in (a, b):
            # Far back a crash is only a bump: cars must reach the fight.
            if (
                e is not None
                and e["alive"]
                and not e["wrecked"]
                and self.z - e["z"] < CRASH_RANGE
            ):
                self._wreck(e, "crash")
                live = True

        if not live and self.t - self._crash_t > 0.25:
            self._crash_t = self.t
            self._snd("crash")

    def _resolve_contacts(self, dt):
        """Resolve vehicle overlap, speed transfer and tractor damage."""
        cars = [
            e for e in self.enemies
            if e["kind"] in ("jeep", "gun_truck")
        ]
        (tx, _ty, tz), _ = self.tractor_pos()
        (lx, _ly, lz), _ = self.trailer_pos()

        statics = [
            (tx, tz, S.TRACTOR_R, True),
            (lx, lz, S.TRAILER_R, True),
        ]
        for e in self.enemies:
            if e["kind"] == "blocker":
                statics.append(
                    (e["x"], e["z"], S.CAR_R, False)
                )

        if self.cp == 2:
            statics.extend(
                (wx, wz, S.WRECK_R, False)
                for wx, wz in S.wrecks()
                if tz - 160.0 < wz < tz + 40.0
            )

        for i in range(len(cars)):
            a = cars[i]
            ra = self._radius(a)

            for j in range(i + 1, len(cars)):
                b = cars[j]
                dx = b["x"] - a["x"]
                dz = b["z"] - a["z"]
                d = math.hypot(dx, dz)
                rr = ra + self._radius(b)

                if d >= rr or d < 1e-6:
                    continue

                nx, nz = dx / d, dz / d
                pen = (rr - d) * 0.5
                a["x"] -= nx * pen
                a["z"] -= nz * pen
                b["x"] += nx * pen
                b["z"] += nz * pen

                closing = (a["v"] - b["v"]) * nz
                if closing > 0.0:
                    avg = 0.5 * (a["v"] + b["v"])
                    a["v"] += (
                        avg - a["v"]
                    ) * CRASH_TRANSFER
                    b["v"] += (
                        avg - b["v"]
                    ) * CRASH_TRANSFER

                    if closing > CRASH_SPEED:
                        self._crash_hit(a, b)

        for a in cars:
            ra = self._radius(a)
            touch = False

            for sx, sz, sr, is_trac in statics:
                dx = a["x"] - sx
                dz = a["z"] - sz
                d = math.hypot(dx, dz)
                rr = ra + sr

                if d >= rr or d < 1e-6:
                    continue

                nx, nz = dx / d, dz / d
                pen = rr - d
                a["x"] += nx * pen
                a["z"] += nz * pen

                rel = a["v"] - (
                    self.speed if is_trac else 0.0
                )
                closing = -rel * nz

                if closing > 0.0:
                    a["v"] *= 1.0 - 0.5 * CRASH_TRANSFER

                    if is_trac:
                        touch = True

                    if closing > CRASH_SPEED:
                        self._crash_hit(a, None)

            if touch and not a["_trac"]:
                a["_trac"] = True
                self.damage(TRACTOR_HIT)
            elif not touch:
                a["_trac"] = False

    def _enemy_update(self, dt):
        tz = self.z
        (tx, ty, _), _ = self.trailer_pos()
        self._enemy_move(dt)

        for e in self.enemies:
            if not e["alive"] or e["wrecked"]:
                continue

            shooter = (
                e["kind"] != "gun_truck" or e["gunner"]
            )
            if (
                e["kind"] in ("jeep", "blocker")
                and not e["driver"]
            ):
                shooter = False

            dist = math.hypot(
                e["x"] - tx,
                e["z"] - (tz - HITCH),
            )
            e["cool"] -= dt
            reach = 34.0 if e["kind"] == "foot" else 48.0

            if (
                shooter
                and dist < reach
                and e["cool"] <= 0.0
                and not self.dying
                and self.end_t is None
            ):
                heavy = e["kind"] == "gun_truck"
                e["cool"] = (
                    0.18
                    if heavy and e.get("burst", 0) > 0
                    else 2.6
                    if heavy
                    else 1.5 + 0.4 * (e["slot"] % 3)
                )

                if heavy:
                    e["burst"] = (
                        e.get("burst", 0) - 1
                        if e.get("burst", 0) > 0
                        else 5
                    )

                gun = self._enemy_gun(e)
                bx, by, bz = self.biribel_pos()
                gyaw = math.degrees(math.atan2(bx - gun[0], bz - gun[2]))
                gpitch = math.degrees(
                    math.atan2(by + 1.3 - gun[1], math.hypot(bx - gun[0], bz - gun[2]))
                )
                self.flashes.append((self.t, gun, gyaw, gpitch, heavy))

                if self.t - self._snd_t > 0.08:
                    self._snd_t = self.t
                    yr = math.radians(self.yaw)
                    pan = (
                        (gun[0] - bx) * math.cos(yr)
                        - (gun[2] - bz) * math.sin(yr)
                    ) / max(dist, 1.0)
                    self._snd(
                        "guard_shot", 0.8 * pan, dist
                    )

                hit_p = 0.55 if dist > 25.0 else 0.75
                hit = ((e["slot"] * 7 + int(self.t * 10)) % 100) / 100.0 < hit_p
                dmg = 2.2 if heavy else 2.8 if e["kind"] != "foot" else 1.2
                self._spawn_enemy_bullet(
                    gun,
                    hit=hit,
                    dmg=dmg,
                    src=(e["x"], e["z"]),
                    heavy=heavy,
                    from_heli=False,
                )

        # Wrecks go once lost in the fog, so they never block incoming cars.
        self.enemies = [
            e for e in self.enemies
            if e["z"] > tz - (
                S.FOG_END + 20.0 if e["wrecked"] else DESPAWN_BACK
            )
            or e["kind"] == "blocker"
        ]

    def _enemy_gun(self, e):
        y, pitch, roll = self._enemy_pose(e)
        if e["kind"] == "gun_truck":
            return S._xf(
                S.TRUCK_GUN,
                (e["x"], y, e["z"]),
                e["yaw"],
                pitch,
                roll,
            )
        if e["kind"] == "foot":
            return e["x"], y + 1.4, e["z"]
        return S._xf(
            (-0.4, 1.7, 0.4),
            (e["x"], y, e["z"]),
            e["yaw"],
            pitch,
            roll,
        )

    def targets(self, e):
        """Enemy hit spheres as (part, world centre, radius)."""
        yaw = e["yaw"]

        if e["kind"] == "foot":
            fy = S.surface_y(e["x"], e["z"])
            return [
                ("body", (e["x"], fy + 1.15, e["z"]), 0.42),
                ("head", (e["x"], fy + 1.7, e["z"]), 0.24),
            ]

        y, pitch, roll = self._enemy_pose(e)
        p = (e["x"], y, e["z"])

        def at(off):
            return S._xf(off, p, yaw, pitch, roll)

        out = []
        if e["kind"] == "gun_truck":
            if e["gunner"]:
                bx, by, bz = S.TRUCK_BED
                out.append(
                    (
                        "gunner",
                        at((bx, by + 1.2, bz)),
                        0.45,
                    )
                )

            out.append(
                ("driver", at(S.TRUCK_DRIVER), 0.4)
            )
            for i, t in enumerate(S.TRUCK_TYRES):
                out.append(
                    (
                        "tyre%d" % i,
                        at(t),
                        S.TRUCK_TYRE_R,
                    )
                )
            out.append(
                (
                    "body",
                    at((0.0, 1.4, 0.0)),
                    1.4,
                )
            )
            return out

        if e["driver"]:
            out.append(
                ("driver", at(S.CAR_DRIVER), 0.42)
            )

        for i, t in enumerate(S.CAR_TYRES):
            out.append(
                (
                    "tyre%d" % i,
                    at(t),
                    S.CAR_TYRE_R,
                )
            )

        out.append(
            ("body", at((0.0, 0.85, 0.0)), 1.05)
        )
        return out

    def hurt_enemy(self, e, part):
        if not e["alive"] or e["wrecked"]:
            return

        self.hit_mark = self.t
        kind = e["kind"]

        if kind == "foot":
            e["hp"] -= 2 if part == "head" else 1
            self._snd("impact", True)

            if e["hp"] <= 0:
                e["alive"] = False
                e["dead_t"] = self.t
                self._snd("enemy_down", 20.0)
            return

        if part == "gunner":
            e["gunner_hp"] -= 1
            self._snd("impact", True)
            if e["gunner_hp"] <= 0:
                e["gunner"] = False
            return

        if part == "driver":
            e["driver_hp"] -= 1
            if e["driver_hp"] > 0:
                self._snd("metal")
                return

            e["driver"] = False
            self._snd("headshot")
            self._wreck(e, "driver")
            return

        if part.startswith("tyre") and kind != "blocker":
            left = (
                e["tyre_hp"].get(part, TYRE_HP[kind]) - 1
            )
            e["tyre_hp"][part] = left
            self._snd("metal")

            if left <= 0:
                self._wreck(e, "tyre")
            return

        e["hp"] -= 1
        self._snd("metal")
        if e["hp"] <= 0:
            self._wreck(e, "body")

    def _wreck(self, e, cause="body"):
        y, pitch, roll = self._enemy_pose(e)
        base_vy = max(0.0, e.get("vy", 0.0))
        e["wy"] = y
        e["wp"] = pitch
        e["wr"] = roll
        e["wvy"] = e.get("vy", 0.0)
        e["wrecked"] = True
        e["alive"] = False
        e["dead_t"] = self.t
        self._snd("crash")

        rnd = random
        sgn = rnd.choice((-1.0, 1.0))

        if e["kind"] in ("jeep", "gun_truck"):
            side = (
                1.0
                if e["x"] >= S.road_x(e["z"])
                else -1.0
            )
            big = 0.6 if e["kind"] == "gun_truck" else 1.0
            v = e["v"]
            fast = clamp(v / 18.0, 0.0, 1.0)

            e["burn_at"] = 0.2
            e["w_fric"] = rnd.uniform(6.5, 9.0)
            e["w_lat"] = side * rnd.uniform(0.5, 2.5)

            if cause == "tyre":
                if v > 10.0 and rnd.random() < 0.35:
                    e["wvy"] = base_vy + rnd.uniform(2.5, 4.5) * big
                    e["wrr"] = (
                        -side * rnd.uniform(220.0, 420.0) * big
                    )
                    e["wpr"] = sgn * rnd.uniform(0.0, 50.0)
                    e["wyr"] = side * rnd.uniform(60.0, 140.0)
                else:
                    e["wvy"] = base_vy + rnd.uniform(0.6, 1.5)
                    e["wyr"] = (
                        side
                        * rnd.uniform(120.0, 300.0)
                        * (0.3 + 0.7 * fast)
                        * big
                    )
                    e["w_lat"] = side * rnd.uniform(2.0, 5.0)
                    e["w_fric"] = rnd.uniform(3.5, 5.5)
                    e["burn_at"] = 0.6

            elif cause == "driver":
                e["wvy"] = e.get("vy", 0.0)
                e["wyr"] = side * rnd.uniform(8.0, 30.0)
                e["w_lat"] = side * rnd.uniform(1.5, 4.0)
                e["w_fric"] = rnd.uniform(2.0, 3.5)
                e["burn_at"] = 1.0

            elif cause == "crash":
                e["wvy"] = base_vy + (
                    rnd.uniform(1.0, 3.5) * (0.5 + fast) * big
                )
                e["wpr"] = (
                    sgn * rnd.uniform(0.0, 90.0) * fast * big
                )
                e["wrr"] = (
                    -side
                    * rnd.uniform(0.0, 260.0)
                    * fast
                    * big
                )
                e["wyr"] = (
                    side * rnd.uniform(80.0, 220.0) * big
                )

            else:
                roll = -side if rnd.random() < 0.8 else side
                pick = rnd.random()

                if pick < 0.4:
                    e["wvy"] = base_vy + rnd.uniform(3.5, 6.5) * big
                    e["wrr"] = (
                        roll * rnd.uniform(260.0, 560.0) * big
                    )
                    e["wpr"] = (
                        sgn * rnd.uniform(0.0, 60.0) * big
                    )
                    e["wyr"] = rnd.uniform(-90.0, 90.0)

                elif pick < 0.62:
                    e["wvy"] = base_vy + rnd.uniform(2.8, 4.5) * big
                    e["wrr"] = roll * rnd.uniform(110.0, 190.0)
                    e["wpr"] = sgn * rnd.uniform(0.0, 40.0)
                    e["wyr"] = rnd.uniform(-60.0, 60.0)

                elif pick < 0.87:
                    e["wvy"] = base_vy + rnd.uniform(2.0, 3.6) * big
                    e["wpr"] = (
                        sgn * rnd.uniform(30.0, 90.0) * big
                    )
                    e["wrr"] = roll * rnd.uniform(0.0, 50.0)
                    e["wyr"] = (
                        rnd.choice((-1.0, 1.0))
                        * rnd.uniform(160.0, 340.0)
                        * big
                    )
                    e["w_fric"] = rnd.uniform(3.0, 5.0)

                else:
                    e["wvy"] = base_vy + rnd.uniform(5.5, 8.5) * big
                    e["wpr"] = (
                        sgn * rnd.uniform(220.0, 380.0) * big
                    )
                    e["wrr"] = roll * rnd.uniform(0.0, 120.0)
                    e["wyr"] = rnd.uniform(-120.0, 120.0)

                e["w_lat"] = side * rnd.uniform(1.0, 4.0)

            e["v"] *= rnd.uniform(0.6, 1.0)
            self._boom(e)

        if e["kind"] == "blocker":
            e["v"] = 0.0
            e["w_lat"] = 0.0
            e["wvy"] = rnd.uniform(2.0, 4.0)
            e["wpr"] = sgn * rnd.uniform(40.0, 160.0)
            e["wrr"] = (
                rnd.choice((-1.0, 1.0))
                * rnd.uniform(0.0, 150.0)
            )
            e["wyr"] = rnd.uniform(-40.0, 40.0)
            self._boom(e)
            self.say(
                "BODI",
                "Tracks are clear. Hold on!",
                2.6,
                key="clear",
            )

    def _boom(self, e):
        e["boom_t"] = self.t
        e["fx_seed"] = random.randrange(1000)
        self._burst(e, "fire", random.randint(7, 11), 4.0)
        self._burst(e, "blast", random.randint(8, 12), 2.6)

        if abs(e["z"] - self.z) < 35.0:
            self.shake = max(self.shake, 0.5)

    def _burst(self, e, kind, n, speed, y=1.0):
        rise = PUFF[kind][4]

        for _ in range(n):
            if len(self.puffs) >= PUFF_MAX:
                return

            a = random.uniform(0.0, math.tau)
            s = speed * random.uniform(0.3, 1.0)
            self.puffs.append(
                [
                    random.uniform(0.0, 0.15),
                    e["x"] + random.uniform(-0.6, 0.6),
                    e["wy"] + y + random.uniform(-0.3, 0.5),
                    e["z"] + random.uniform(-1.0, 1.0),
                    math.cos(a) * s,
                    rise * random.uniform(0.6, 1.5)
                    + random.uniform(0.0, 0.5 * speed),
                    math.sin(a) * s + e["v"] * 0.4,
                    kind,
                    random.randrange(6),
                ]
            )

    def blocked(self):
        return any(
            e["kind"] == "blocker" and not e["wrecked"]
            for e in self.enemies
        )

    # --- damage and capture ------------------------------------------------

    def _spawn_enemy_bullet(self, muzzle, hit, dmg, src, heavy=False, from_heli=False):
        bx, by, bz = self.biribel_pos()
        (lx, ly, lz), lyaw = self.trailer_pos()
        dist = math.dist(muzzle, (bx, by + 1.3, bz))
        speed = 135.0 if from_heli else 125.0
        dur = clamp(dist / speed, 0.05, 0.30 if from_heli else 0.25)

        ry = math.radians(S.road_yaw(self.z))
        lead_x = math.sin(ry) * self.speed * dur
        lead_z = math.cos(ry) * self.speed * dur

        if hit:
            roll = random.random()
            if roll < 0.45:
                tr_off = (
                    random.uniform(-0.42, 0.42),
                    random.uniform(2.05, 2.55),
                    random.uniform(-1.55, -0.55),
                )
                kind = "metal"
            elif roll < 0.80:
                tr_off = (
                    random.uniform(-1.05, 1.05),
                    random.uniform(1.15, 1.85),
                    -1.85 if random.random() < 0.55 else random.uniform(-1.75, 0.6),
                )
                kind = "metal" if tr_off[2] < -1.75 else "wood"
            else:
                tr_off = (
                    random.uniform(-0.85, 0.85),
                    random.uniform(1.30, 2.05),
                    random.uniform(0.65, 1.40),
                )
                kind = "hay"
            pt_now = S._xf(tr_off, (lx, ly, lz), lyaw, S.ditch_pitch(lz))
            end = (pt_now[0] + lead_x, pt_now[1], pt_now[2] + lead_z)
        else:
            tr_off = None
            if random.random() < 0.58:
                dz_rel = random.uniform(-15.0, -3.2)
                dx_rel = (
                    random.choice((-1.0, 1.0)) * random.uniform(1.5, 4.2)
                    if dz_rel > -5.0
                    else random.uniform(-3.8, 3.8)
                )
                gz = lz + lead_z + dz_rel
                gx = S.road_x(gz) + self.lane + dx_rel
                gy = S.surface_y(gx, gz) + 0.05
                end = (gx, gy, gz)
                kind = "road"
            else:
                side = random.choice((-1.0, 1.0))
                end = (
                    bx + lead_x + side * random.uniform(0.65, 1.45),
                    by + random.uniform(1.15, 2.10),
                    bz + lead_z - random.uniform(1.1, 2.2),
                )
                kind = None

        self.bullets.append(
            {
                "t0": self.t,
                "dur": dur,
                "start": muzzle,
                "end": end,
                "hit": hit,
                "dmg": dmg,
                "src": src,
                "heavy": heavy,
                "kind": kind,
                "tr_off": tr_off,
                "len": 3.4 if heavy else 2.2,
            }
        )
        del self.bullets[:-28]

    def _bullets_update(self, dt):
        self.hurt = max(0.0, self.hurt - dt * 2.2)
        self.dmg_marks = [m for m in self.dmg_marks if self.t - m[0] < 0.9]
        self.impacts = [im for im in self.impacts if self.t - im["t0"] < 0.34]

        if self.wreck_t is not None or self.dying or self.end_t is not None:
            self.bullets.clear()
            return

        keep = []
        for b in self.bullets:
            if self.t < b["t0"] + b["dur"]:
                keep.append(b)
                continue

            if b["hit"]:
                self.damage(b["dmg"], src=b["src"], hit_pos=b["end"], kind=b["kind"])
                if not self.dying and self.end_t is None and b["tr_off"] is not None:
                    (lx, ly, lz), lyaw = self.trailer_pos()
                    pos = S._xf(b["tr_off"], (lx, ly, lz), lyaw, S.ditch_pitch(lz))
                    self.impacts.append(
                        {
                            "t0": self.t,
                            "local": b["tr_off"],
                            "pos": pos,
                            "kind": b["kind"],
                            "heavy": b["heavy"],
                            "seed": random.randrange(1000),
                        }
                    )
                    if b["kind"] in ("wood", "hay") and len(self.puffs) < PUFF_MAX:
                        self.puffs.append(
                            [
                                0.0,
                                pos[0],
                                pos[1],
                                pos[2],
                                random.uniform(-0.8, 0.8),
                                1.2,
                                self.speed * 0.4,
                                "dust",
                                random.randrange(6),
                            ]
                        )
            elif b["kind"] == "road":
                pos = b["end"]
                self.impacts.append(
                    {
                        "t0": self.t,
                        "local": None,
                        "pos": pos,
                        "kind": "road",
                        "heavy": b["heavy"],
                        "seed": random.randrange(1000),
                    }
                )
                if len(self.puffs) < PUFF_MAX:
                    self.puffs.append(
                        [
                            0.0,
                            pos[0],
                            pos[1],
                            pos[2],
                            random.uniform(-0.6, 0.6),
                            1.5,
                            random.uniform(-0.6, 0.6),
                            "dust",
                            random.randrange(6),
                        ]
                    )

        self.bullets = keep
        del self.impacts[:-20]

    def damage(self, n, src=None, hit_pos=None, kind=None):
        if self.dying or self.end_t is not None:
            return
        if self.repair_t is not None:
            n *= 0.35

        self.hull = max(0.0, self.hull - n)
        self._snd("hull_hit")
        self.hurt = min(1.0, self.hurt + clamp(0.32 + n * 0.03, 0.32, 0.85))
        self.shake = max(self.shake, clamp(0.24 + n * 0.018, 0.24, 0.85))

        if self.t - self._hit_snd_t > 0.09:
            self._hit_snd_t = self.t
            self._snd("hurt", n)
            if kind == "metal":
                self._snd("metal", 0.0, 0.35)

        if src is not None:
            bx, _by, bz = self.biribel_pos()
            bearing = _wrap(_yaw_to(src[0] - bx, src[1] - bz) - self.yaw)
            self.dmg_marks.append((self.t, -bearing))
            del self.dmg_marks[:-8]

        if self.hull < 35.0:
            self.say(
                "BODI",
                "Come on, come on!",
                2.4,
                key="low%d" % self.cp,
            )

        if self.hull < 45.0 and self.repairs > 0 and self.repair_t is None:
            self.say("BODI", "Toolbox on the trailer - patch her up!", 2.8, key="tb%d" % self.cp)

        if self.hull <= 0.0:
            self._capture_start()

    # --- toolbox repair ----------------------------------------------------

    def _toolbox_world(self):
        (lx, ly, lz), lyaw = self.trailer_pos()
        x, y, z = S._xf(S.TOOLBOX_AT, (lx, ly, lz), lyaw, S.ditch_pitch(lz))
        return (x, y + 0.14, z)

    def _looking_at_toolbox(self):
        if self.repair_t is not None or self.dying or self.end_t is not None or self.wreck_t is not None:
            return False
        o, d = self.aim_ray()
        return _ray_sphere(o, d, self._toolbox_world(), 0.58) is not None

    def _try_repair(self):
        if self.repairs <= 0 or self.hull >= HULL - 0.5:
            return False
        if not self._looking_at_toolbox():
            return False
        self.repairs -= 1
        self.repair_t = self.t
        self._repair_heal_left = REPAIR_HEAL
        self._repair_spark_i = -1
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.reloading = 0.0
        self._snd("metal", 0.0, 0.35)
        self.say("BODI", "Make it quick!", 2.0)
        return True

    def _repair_update(self, dt):
        if self.repair_t is None:
            return
        el = self.t - self.repair_t
        rate = REPAIR_HEAL / REPAIR_S
        step = min(self._repair_heal_left, rate * dt)
        if step > 0.0 and not self.dying:
            self.hull = min(HULL, self.hull + step)
            self._repair_heal_left -= step

        # Hammer clank + spark ticks synced to the 3 downstrokes on the coupling.
        if 1.04 <= el <= 1.92:
            tick = int((el - 1.04) / 0.40)
            if tick != self._repair_spark_i:
                self._repair_spark_i = tick
                self._snd("metal", 0.1, 0.42)
                self.shake = max(self.shake, 0.18)
                (lx, ly, lz), lyaw = self.trailer_pos()
                spot = S._xf(S.RIG_PUMP_STRIKE, (lx, ly, lz), lyaw, S.ditch_pitch(lz))
                self.sparks.append((self.t, spot))
                del self.sparks[:-6]

        if el >= REPAIR_S:
            if self._repair_heal_left > 0.0 and not self.dying:
                self.hull = min(HULL, self.hull + self._repair_heal_left)
            self._repair_heal_left = 0.0
            self.repair_t = None

    def _capture_start(self):
        self._fail(
            "THE TRACTOR IS WRECKED - AGAIN FROM THE CHECKPOINT"
        )
        self.wreck_t = self.t
        self.shake = 1.0
        self.reloading = 0.0
        self._snd("crash")
        self._snd("trac_stall")
        self.say("BODI", "The engine's gone! Hold on!", 2.2)

        cars = [
            e for e in self.enemies
            if e["kind"] in ("jeep", "gun_truck")
            and not e["wrecked"]
        ]
        for i in range(max(0, 2 - len(cars))):
            self._spawn(
                "jeep",
                (-1.2, -3.6)[i % 2],
                z=self.z - 70.0,
            )

    def _ground(self, frame, off):
        (x, _y, z), yaw = frame
        p = _local(
            (x, 0.0, z), yaw - self.slew, off
        )
        return p[0], S.surface_y(p[0], p[2]), p[2]

    def _capture(self, dt):
        el = self.t - self.wreck_t
        self.speed = max(0.0, self.speed - dt * 7.0)
        self.z += self.speed * dt
        self.odo += self.speed * dt
        self.lane += (
            2.4 - self.lane
        ) * min(1.0, dt * 1.4)

        if self.speed > 0.5:
            self.slew += (
                16.0 - self.slew
            ) * min(1.0, dt * 1.2)

        (_lx, _ly, lz), _ = self.trailer_pos()
        k = 0

        for e in self.enemies:
            if e["kind"] not in ("jeep", "gun_truck"):
                continue

            if e["wrecked"]:
                self._wreck_step(e, dt)
                e["z"] += e["v"] * dt
                e["yaw"] = S.road_yaw(e["z"]) + e["spin"]
                self._sync_wreck_ground(e)
                continue

            gz = lz - 9.0 - 7.0 * k
            gx = S.road_x(gz) + (-1.2, -3.6, -1.0)[k % 3]
            v = clamp(
                (gz - e["z"]) * 1.1,
                -3.0,
                SPEED + 6.0,
            )
            e["z"] += v * dt
            e["odo"] += v * dt
            e["x"] += (
                gx - e["x"]
            ) * min(1.0, dt * 1.5)
            e["yaw"] = S.road_yaw(e["z"]) + clamp(
                (gx - e["x"]) * -8.0, -20.0, 20.0
            )
            self._step_vehicle_y(e, dt, speed=v)

            if k < 3:
                e["stop_k"] = k
            k += 1

        if el > 2.0 and not self.captors:
            self._captors()
        if el > 1.9:
            self.say(
                "GUARD",
                "Out! Out, hands where we can see them!",
                2.6,
                key="cap_out",
            )
        if el > 4.2:
            self.say(
                "BIRIBEL",
                "Bodi. Don't move.",
                2.0,
                key="cap_b",
            )
        if el > 5.6:
            self.say(
                "GUARD",
                "On your knees. Both of you.",
                2.4,
                key="cap_kneel",
            )
        if el >= CAPTURE_S:
            self._setup(self.cp)

    def _captors(self):
        cars = sorted(
            (
                e for e in self.enemies
                if "stop_k" in e and not e["wrecked"]
            ),
            key=lambda e: e["stop_k"],
        ) or [None]

        trac, trl = self.tractor_pos(), self.trailer_pos()
        marks = (
            (
                trl,
                (-1.9, 0.0, -0.2),
                (-4.6, 0.0, -1.4),
            ),
            (
                trl,
                (-1.9, 0.0, -0.2),
                (-4.4, 0.0, 1.6),
            ),
            (
                trac,
                (-1.9, 0.0, -0.9),
                (-4.5, 0.0, -0.2),
            ),
        )

        for i, (frame, who, stand) in enumerate(marks):
            car = cars[min(i, len(cars) - 1)]

            if car is not None:
                cy, cp, cr = self._enemy_pose(car)
                src = S._xf(
                    (-1.3, 0.0, 0.6 - 0.9 * (i // len(cars))),
                    (car["x"], cy, car["z"]),
                    car["yaw"],
                    cp,
                    cr,
                )
            else:
                src = self._ground(
                    trl, (-3.0, 0.0, -14.0 - 2.0 * i)
                )

            self.captors.append(
                {
                    "src": (
                        src[0],
                        S.surface_y(src[0], src[2]),
                        src[2],
                    ),
                    "dst": self._ground(frame, stand),
                    "mark": self._ground(frame, who),
                    "t0": 0.25 * i,
                    "seed": 170 + i,
                }
            )

    # --- the gunship -------------------------------------------------------

    def _start_heli_cutscene(self):
        """Pause the chase and run the gunship arrival through the house player."""
        self._heli_seen = True
        self._cutscene_wait = True
        self.firing = False
        self.aiming = False
        self.ads = 0.0
        self.reloading = 0.0
        self.bullets.clear()
        self.rockets.clear()
        self.heli = None
        self.set_paused(True)
        try:
            E.command_room()
            _w.hum("retardovici")
            _w.hum(("guard", "officer"))
        except Exception:
            pass
        STATE.request_m8_cutscene = "heli"

    def on_heli_cutscene_done(self):
        """The arrival film ended: roll the rig forward and put the gunship on it."""
        self._cutscene_wait = False
        self.z = min(S.SECTIONS[4] - 80.0, self.z + 55.0)
        self.odo += 55.0
        self.cp_toast = self.t
        self.yaw = 180.0
        self.pitch = 6.0
        self._spawn_heli()
        self.heli["state"] = "orbit"
        tx, tz = S.road_x(self.z), self.z - HITCH
        self.heli["x"] = tx + 11.0
        self.heli["y"] = 7.0
        self.heli["z"] = tz - 31.0
        self.heli["yaw"] = _yaw_to(tx - self.heli["x"], tz - self.heli["z"])
        self.say("BODI", "Chopper! Get on that gun!", 3.2)

    def heli_active(self):
        return self.heli is not None and self.heli["state"] not in ("crashed",)

    def _spawn_heli(self):
        S.helicopter_parts()
        z0 = self.z + 110.0
        self.heli = {
            "x": S.road_x(z0) + 28.0,
            "y": 24.0,
            "z": z0,
            "yaw": 180.0,
            "pitch": -6.0,
            "roll": 0.0,
            "hp": HELI_HP,
            "max_hp": HELI_HP,
            "phase2": False,
            "engine_hits": 0,
            "gunner": True,
            "gunner_hp": HELI_GUNNER_HP,
            "main_spin": 0.0,
            "tail_spin": 0.0,
            "state": "fly_in",
            "t0": self.t,
            "cool": 1.3,
            "burst": 0,
            "gun_idx": 0,
            "rocket_stage": 0,
            "salvo_left": 0,
            "salvo_at": 0.0,
            "last_rocket_t": -9.0,
            "lock_t": 0.0,
            "stagger_t": -9.0,
            "vx": 0.0,
            "vy": 0.0,
            "vz": 0.0,
            "crash_t": 0.0,
            "bounces": 0,
            "impact_t": None,
            "cooked_off": False,
            "boom_t": None,
        }
        self.rockets = []

    def _heli_update(self, dt):
        h = self.heli
        if h is None:
            return

        if h["state"] in ("crashing", "skidding", "crashed"):
            self._heli_crash_update(dt)
            return

        h["main_spin"] = (h["main_spin"] + dt * 1450.0) % 360.0
        h["tail_spin"] = (h["tail_spin"] + dt * 2400.0) % 360.0
        el = self.t - h["t0"]

        if not h["phase2"] and h["hp"] <= h["max_hp"] * 0.50:
            h["phase2"] = True
            h["stagger_t"] = self.t
            self._burst({"x": h["x"], "wy": h["y"] + 1.0, "z": h["z"], "v": 0.0}, "fire", 8, 4.0)
            self.say("BODI", "She's smoking - watch out, he's coming in low!", 3.2)

        if (h["phase2"] or h["hp"] < h["max_hp"] * 0.65) and len(self.puffs) < PUFF_MAX:
            if int(self.t * 30.0) != int((self.t - dt) * 30.0):
                self.puffs.append([
                    0.0, h["x"], h["y"] + 2.0, h["z"],
                    random.uniform(-0.8, 0.8), 1.4, self.speed * 0.3, "burn", random.randrange(6),
                ])

        tx, _ty, tz = S.road_x(self.z), 0.0, self.z - HITCH
        if h["state"] == "fly_in":
            if el < 2.2:
                goal_x = S.road_x(self.z + 30.0) + 12.0
                goal_y = 13.0
                goal_z = self.z + 25.0
            else:
                h["state"] = "orbit"
                goal_x = tx + 11.0
                goal_y = 7.0
                goal_z = tz - 31.0
        elif h["state"] == "rocket_lock":
            goal_x = tx + (3.0 * math.sin(el * 1.1) if h["phase2"] else 0.0)
            goal_y = 6.2
            goal_z = tz - 31.0
        else:
            if h["rocket_stage"] == 0 and (h["hp"] <= h["max_hp"] * 0.72 or el > 14.0):
                h["rocket_stage"] = 1
                h["salvo_left"] = 1
                h["state"] = "rocket_lock"
                h["lock_t"] = self.t
                self._snd("horn", 0.35)
                self.say("BODI", "MISSILE LOCK! Get ready to shoot or dodge!", 3.2)
            elif h["rocket_stage"] == 1 and h["hp"] <= h["max_hp"] * 0.32 and self.t - h["last_rocket_t"] > 10.0:
                h["rocket_stage"] = 2
                h["salvo_left"] = 1
                h["state"] = "rocket_lock"
                h["lock_t"] = self.t
                self._snd("horn", 0.45)
                self.say("BODI", "ANOTHER LOCK - WATCH THE PYLON!", 3.2)

            if h["phase2"]:
                goal_x = tx + 16.5 * math.sin(el * 1.15)
                goal_y = 6.2 + 1.8 * math.sin(el * 1.45)
                goal_z = tz - (26.0 + 5.5 * math.cos(el * 0.85))
            else:
                goal_x = tx + 13.5 * math.sin(el * 0.85)
                goal_y = 6.6 + 1.3 * math.sin(el * 1.05)
                goal_z = tz - (28.0 + 5.0 * math.cos(el * 0.65))

        old_x = h["x"]
        rate = 2.8 if h["state"] == "rocket_lock" else (2.4 if h["phase2"] else 2.0)
        h["x"] += (goal_x - h["x"]) * min(1.0, dt * rate)
        h["y"] += (goal_y - h["y"]) * min(1.0, dt * 2.4)
        h["z"] += (goal_z - h["z"]) * min(1.0, dt * 2.6)

        lat_v = (h["x"] - old_x) / max(dt, 1e-4)
        want_yaw = _yaw_to(tx - h["x"], tz - h["z"])
        h["yaw"] = (h["yaw"] + _wrap(want_yaw - h["yaw"]) * min(1.0, dt * 5.5)) % 360.0
        stag = 9.0 * math.sin((self.t - h["stagger_t"]) * 18.0) if self.t - h["stagger_t"] < 0.7 else 0.0
        h["roll"] = clamp(-lat_v * 1.5 + stag, -26.0, 26.0)
        h["pitch"] = clamp(-5.0 + (goal_z - h["z"]) * 0.35, -15.0, 8.0)

        if h["state"] == "rocket_lock":
            if self.t - h["lock_t"] >= HELI_LOCK_S:
                self._launch_rocket(side=-1.0)
                h["salvo_left"] -= 1
                h["last_rocket_t"] = self.t
                if h["salvo_left"] > 0:
                    h["salvo_at"] = self.t + 0.60
                h["state"] = "orbit"
            return

        if h["salvo_left"] > 0 and self.t >= h["salvo_at"]:
            self._launch_rocket(side=1.0)
            h["salvo_left"] -= 1
            h["last_rocket_t"] = self.t

        if h["state"] == "orbit" and not self.dying and self.end_t is None:
            h["cool"] -= dt
            if h["cool"] <= 0.0:
                if h["burst"] <= 0:
                    h["burst"] = (8 if h["gunner"] else 6) if h["phase2"] else (7 if h["gunner"] else 5)
                h["burst"] -= 1
                gap = 1.95 if h["phase2"] else 2.30
                h["cool"] = (0.095 if h["phase2"] else 0.105) if h["burst"] > 0 else gap
                self._heli_shoot()

    def _heli_crash_update(self, dt):
        h = self.heli
        if h["state"] == "crashing":
            h["main_spin"] = (h["main_spin"] + dt * 520.0) % 360.0
            h["tail_spin"] = 0.0
            h["vy"] -= 11.0 * dt
            h["x"] += h["vx"] * dt
            h["y"] += h["vy"] * dt
            h["z"] += h["vz"] * dt
            h["yaw"] = (h["yaw"] + dt * 290.0) % 360.0
            h["pitch"] = clamp(h["pitch"] - dt * 22.0, -38.0, 18.0)
            h["roll"] = clamp(h["roll"] + (42.0 if h["vx"] >= 0 else -42.0) * dt, -75.0, 75.0)

            if len(self.puffs) < PUFF_MAX:
                self.puffs.append([
                    0.0, h["x"] + random.uniform(-0.8, 0.8), h["y"] + 1.4, h["z"] + random.uniform(-0.8, 0.8),
                    random.uniform(-1.5, 1.5), 2.2, h["vz"] * 0.25, "burn", random.randrange(6),
                ])
                if random.random() < 0.55:
                    self.puffs.append([
                        0.0, h["x"], h["y"] + 1.2, h["z"],
                        random.uniform(-1.0, 1.0), 1.6, h["vz"] * 0.2, "fire", random.randrange(6),
                    ])

            ground = S.surface_y(h["x"], h["z"]) + 0.95
            if h["y"] <= ground and h["vy"] < 0.0:
                h["y"] = ground
                self.shake = max(self.shake, 1.0)
                self._snd("crash")
                h["boom_t"] = self.t
                if h["impact_t"] is None:
                    h["impact_t"] = self.t
                self._burst({"x": h["x"], "wy": ground, "z": h["z"], "v": 0.0}, "fire", 20, 6.5)
                self._burst({"x": h["x"], "wy": ground, "z": h["z"], "v": 0.0}, "blast", 18, 4.5)

                if h["bounces"] == 0:
                    h["bounces"] = 1
                    h["vy"] = 3.8
                    h["vx"] *= 0.55
                    h["vz"] = self.speed * 0.30
                else:
                    h["state"] = "skidding"
                    h["vy"] = 0.0
                    h["vx"] *= 0.45
                    h["vz"] *= 0.45
            return

        if h["state"] == "skidding":
            h["x"] += h["vx"] * dt
            h["z"] += h["vz"] * dt
            h["vx"] *= math.exp(-3.8 * dt)
            h["vz"] *= math.exp(-3.8 * dt)
            h["y"] = S.surface_y(h["x"], h["z"]) + 0.95
            want_roll = 84.0 if h["roll"] >= 0.0 else -84.0
            h["roll"] += (want_roll - h["roll"]) * min(1.0, dt * 7.0)
            h["pitch"] += (-16.0 - h["pitch"]) * min(1.0, dt * 6.0)
            if math.hypot(h["vx"], h["vz"]) < 0.6:
                h["state"] = "crashed"
                h["vx"] = h["vz"] = 0.0

        if h["impact_t"] is not None and not h["cooked_off"] and self.t - h["impact_t"] >= 0.75:
            h["cooked_off"] = True
            h["boom_t"] = self.t
            self.shake = max(self.shake, 0.9)
            self._snd("crash")
            self._burst({"x": h["x"], "wy": h["y"] + 0.5, "z": h["z"], "v": 0.0}, "fire", 24, 7.5)
            self._burst({"x": h["x"], "wy": h["y"] + 0.8, "z": h["z"], "v": 0.0}, "blast", 22, 5.2)
            self.say("BODI", "He's down! Border crossing's right ahead!", 3.4)

        if abs(h["z"] - self.z) < 150.0 and len(self.puffs) < PUFF_MAX and random.random() < 0.45:
            self.puffs.append([
                0.0, h["x"] + random.uniform(-1.0, 1.0), h["y"] + 0.8, h["z"] + random.uniform(-1.0, 1.0),
                random.uniform(-0.8, 0.8), 2.6, 0.0, "burn" if random.random() < 0.7 else "fire",
                random.randrange(6),
            ])

    def _heli_shoot(self):
        h = self.heli
        info = S.helicopter_parts()[3]
        pts = [info["chin_gun"], info["pods"][0], info["pods"][1]]
        if h["gunner"]:
            gx, gy, gz = info["gunner_seat"]
            pts.append((gx, gy + 1.35, gz))
        h["gun_idx"] = (h["gun_idx"] + 1) % len(pts)
        off = pts[h["gun_idx"]]
        heavy = h["gun_idx"] < 3

        muzzle = S._xf(off, (h["x"], h["y"], h["z"]), h["yaw"], h["pitch"], h["roll"])
        bx, by, bz = self.biribel_pos()
        dist = math.hypot(h["x"] - bx, h["z"] - bz)
        gyaw = _yaw_to(bx - muzzle[0], bz - muzzle[2])
        gpitch = math.degrees(
            math.atan2(by + 1.35 - muzzle[1], math.hypot(bx - muzzle[0], bz - muzzle[2]))
        )
        self.flashes.append((self.t, muzzle, gyaw, gpitch, heavy))

        if self.t - self._snd_t > 0.08:
            self._snd_t = self.t
            yr = math.radians(self.yaw)
            pan = (
                (muzzle[0] - bx) * math.cos(yr) - (muzzle[2] - bz) * math.sin(yr)
            ) / max(dist, 1.0)
            self._snd("guard_shot", 0.8 * pan, dist)

        self._spawn_enemy_bullet(
            muzzle,
            hit=(random.random() < 0.30),
            dmg=1.6,
            src=(h["x"], h["z"]),
            heavy=heavy,
            from_heli=True,
        )

    def _launch_rocket(self, side=-1.0):
        h = self.heli
        info = S.helicopter_parts()[3]
        pylon = info["pods"][0 if side < 0 else 1] if side > 0 else info["rocket_pylon"]
        pos = S._xf(pylon, (h["x"], h["y"], h["z"]), h["yaw"], h["pitch"], h["roll"])
        tx, ty, tz = self.tractor_pos()[0]
        self._snd("rocket")
        self.rockets.append({
            "pos": pos,
            "start": pos,
            "target_lane": self.lane,
            "arc": side * 1.8,
            "hp": ROCKET_HP,
            "max_hp": ROCKET_HP,
            "yaw": _yaw_to(tx - pos[0], tz - pos[2]),
            "pitch": math.degrees(math.atan2((ty + 1.05) - pos[1], math.hypot(tx - pos[0], tz - pos[2]))),
            "t0": self.t,
            "done": False,
            "dodged": False,
        })

    def _try_dodge(self, key):
        inbound = [rk for rk in self.rockets if not rk["done"] and not rk["dodged"]]
        late_lock = (
            self.heli is not None
            and self.heli["state"] == "rocket_lock"
            and (self.t - self.heli["lock_t"]) >= HELI_LOCK_S - 0.5
        )
        if not (inbound or late_lock):
            return
        if key == pygame.K_a:
            side = -1.0
        elif key == pygame.K_d:
            side = 1.0
        else:
            aim_lane = inbound[0]["target_lane"] if inbound else self.lane
            side = -1.0 if aim_lane >= 0.0 else 1.0
        self.dodge_lane = side * 2.85
        self.dodge_t = self.t
        self.shake = max(self.shake, 0.35)
        self._snd("trac_move")

    def _rocket_update(self, dt):
        tx, ty, tz = self.tractor_pos()[0]
        for rk in self.rockets:
            if rk["done"]:
                continue
            old_x, old_y, old_z = rk["pos"]
            px, py, pz = old_x, old_y, old_z
            pz += (self.speed + 16.0) * dt
            total_z = max(1.0, tz - rk["start"][2])
            frac = clamp((pz - rk["start"][2]) / total_z, 0.0, 1.0)
            aim_x = S.road_x(pz) + rk["target_lane"]
            aim_y = ty + 1.05
            arc_off = rk["arc"] * math.sin(math.pi * frac) * (1.0 - frac)
            px = rk["start"][0] + (aim_x - rk["start"][0]) * frac + arc_off
            py = rk["start"][1] + (aim_y - rk["start"][1]) * frac
            rk["pos"] = (px, py, pz)

            vx, vy, vz = px - old_x, py - old_y, pz - old_z
            if vx * vx + vy * vy + vz * vz > 1e-8:
                rk["yaw"] = _yaw_to(vx, vz)
                rk["pitch"] = math.degrees(math.atan2(vy, math.hypot(vx, vz)))

            if len(self.puffs) < PUFF_MAX:
                tail = S._xf((0.0, 0.0, -S.ROCKET_LEN * 0.5), rk["pos"], rk["yaw"], rk["pitch"])
                self.puffs.append([0.0, tail[0], tail[1], tail[2], random.uniform(-0.3, 0.3), 0.5, 0.0, "fire", 0])

            if pz >= tz - HITCH - 0.5:
                if rk["dodged"]:
                    if pz >= tz + 24.0:
                        self._detonate_rocket(rk, hit_player=False)
                elif abs(self.lane - rk["target_lane"]) >= 1.35:
                    rk["dodged"] = True
                    self.say("BODI", "Close! Too close!", 2.4)
                elif pz >= tz - 1.0:
                    self._detonate_rocket(rk, hit_player=True)

        self.rockets = [rk for rk in self.rockets if not rk["done"]]

    def _detonate_rocket(self, rk, hit_player=False, shot_down=False):
        rk["done"] = True
        pos = rk["pos"]
        self._snd("crash")
        self.shake = max(self.shake, 0.95 if hit_player else 0.45)
        self._burst({"x": pos[0], "wy": pos[1], "z": pos[2], "v": 0.0}, "fire", 12, 4.8, y=0.0)
        self._burst({"x": pos[0], "wy": pos[1], "z": pos[2], "v": 0.0}, "blast", 10, 3.2, y=0.0)
        if hit_player:
            self.damage(ROCKET_DMG, src=(pos[0], pos[2]), kind="metal")
        elif shot_down and self.heli is not None and self.heli["state"] not in ("crashing", "skidding", "crashed"):
            self.heli["stagger_t"] = self.t
            self.hurt_heli("body", dmg=20)
            self.say("BODI", "Shot it right out of the sky!", 2.4)

    def heli_targets(self):
        h = self.heli
        if h is None or h["state"] in ("crashing", "skidding", "crashed"):
            return []
        info = S.helicopter_parts()[3]
        pos = (h["x"], h["y"], h["z"])
        out = []
        if h["gunner"]:
            gx, gy, gz = info["gunner_seat"]
            out.append((
                "gunner",
                S._xf((gx, gy + 1.15, gz), pos, h["yaw"], h["pitch"], h["roll"]),
                0.50,
            ))
        out.append(("cockpit", S._xf(info["pilot_seat"], pos, h["yaw"], h["pitch"], h["roll"]), 0.60))
        out.append(("chin_gun", S._xf(info["chin_gun"], pos, h["yaw"], h["pitch"], h["roll"]), 0.45))
        out.append(("engine", S._xf((0.0, 2.25, 0.1), pos, h["yaw"], h["pitch"], h["roll"]), 0.72))
        out.append(("body", S._xf((0.0, 1.4, 0.0), pos, h["yaw"], h["pitch"], h["roll"]), 1.85))
        out.append(("tail", S._xf((0.0, 1.5, -4.0), pos, h["yaw"], h["pitch"], h["roll"]), 0.85))
        return out

    def hurt_heli(self, part, dmg=None):
        h = self.heli
        if h is None or h["state"] in ("crashing", "skidding", "crashed"):
            return
        self.hit_mark = self.t
        if part == "gunner" and h["gunner"]:
            h["gunner_hp"] -= 1
            self._snd("impact", True)
            if h["gunner_hp"] <= 0:
                h["gunner"] = False
                dmg = 22
                h["stagger_t"] = self.t
                self.say("BODI", "Got the door gunner!", 2.4)
            else:
                dmg = 2
        elif dmg is None:
            if part == "engine":
                h["engine_hits"] += 1
                if h["engine_hits"] % 18 == 0:
                    h["stagger_t"] = self.t
                    h["burst"] = 0
                dmg = 2
            else:
                dmg = 2 if part in ("cockpit", "chin_gun") else 1
        self._snd("headshot" if part in ("cockpit", "gunner", "engine") else "metal")
        h["hp"] = max(0, h["hp"] - dmg)
        if h["hp"] <= 0 and h["state"] not in ("crashing", "skidding", "crashed"):
            h["state"] = "crashing"
            h["crash_t"] = self.t
            side = 1.0 if h["x"] < S.road_x(h["z"]) else -1.0
            h["vx"] = side * 9.5
            h["vy"] = 3.6
            h["vz"] = self.speed * 0.85
            h["boom_t"] = self.t
            self._snd("crash")
            self._burst({"x": h["x"], "wy": h["y"] + 1.6, "z": h["z"] - 3.0, "v": 0.0}, "fire", 14, 5.2)
            self._burst({"x": h["x"], "wy": h["y"] + 1.6, "z": h["z"] - 3.0, "v": 0.0}, "blast", 12, 3.8)

    def _fail(self, msg):
        if self.dying:
            return
        self.dying = True
        self.death_t = 0.0
        self.death_msg = msg
        self.firing = False

    # --- reload and firing -------------------------------------------------

    def _reload(self):
        if (
            self.reloading
            or self.mag >= MAG
            or self.end_t is not None
        ):
            return
        self.reloading = RELOAD_S

    def _toss(self):
        g = self._rig()
        p = self._can_at or self.gun_pt(S.LMG_CAN)
        yr = math.radians(g["gyaw"])
        ry = math.radians(S.road_yaw(self.z))
        v = (
            -math.cos(yr) * 2.6 + math.sin(ry) * self.speed,
            1.8,
            math.sin(yr) * 2.6 + math.cos(ry) * self.speed,
        )
        self.cans.append([p, v, 0.0, g["gyaw"]])
        del self.cans[:-4]

    def _cans_update(self, dt):
        for c in self.cans:
            (x, y, z), (vx, vy, vz) = c[0], c[1]

            if vx or vy or vz:
                ground = S.ditch_y(z) + 0.1
                vy -= 9.8 * dt
                x, y, z = (
                    x + vx * dt,
                    y + vy * dt,
                    z + vz * dt,
                )
                c[2] += dt * 620.0

                if y <= ground and vy < 0.0:
                    y, vx, vy, vz = ground, 0.0, 0.0, 0.0
                    c[2] = 90.0
                    self._snd("metal", 0.0, 0.22)

                c[0], c[1] = (x, y, z), (vx, vy, vz)

        self.cans = [
            c for c in self.cans
            if c[0][2] > self.z - 160.0
        ]

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return

        if self.mag <= 0:
            self._snd("dry")
            self.last_fire = self.t
            self._reload()
            return

        self.mag -= 1
        self.last_fire = self.t

        # Only a real discharged round produces flash and illumination.
        self.last_flash = self.t
        self.flash_seed += 1

        self.kick = min(1.0, self.kick + 0.45)
        self._snd("lmg_shot")
        o, d = self._spread(*self.aim_ray())
        self.heat = min(1.0, self.heat + HEAT_SHOT)
        self.pitch = clamp(
            self.pitch
            + CLIMB * (1.0 - ADS_CLIMB * self.ads),
            *PITCH_LIM,
        )

        for rk in self.rockets:
            if rk["done"]:
                continue
            s = _ray_sphere(o, d, rk["pos"], ROCKET_HIT_R)
            if s is not None and s < 160.0:
                rk["hp"] -= 1
                self.hit_mark = self.t
                self._snd("metal")
                self.sparks.append((self.t, tuple(o[i] + d[i] * s for i in range(3))))
                del self.sparks[:-6]
                if rk["hp"] <= 0:
                    self._detonate_rocket(rk, shot_down=True)
                return

        best = None
        for e in self.enemies:
            if not e["alive"] or e["wrecked"]:
                continue

            for part, c, rad in self.targets(e):
                s = _ray_sphere(o, d, c, rad)
                if (
                    s is not None
                    and s < 140.0
                    and (
                        best is None
                        or s < best[0]
                        or (
                            abs(s - best[0]) < 0.6
                            and part != "body"
                        )
                    )
                ):
                    best = s, e, part

        for part, c, rad in self.heli_targets():
            s = _ray_sphere(o, d, c, rad)
            if (
                s is not None
                and s < 140.0
                and (best is None or s < best[0] or abs(s - best[0]) < 0.6)
            ):
                best = s, None, part

        if best is not None:
            s, e, part = best
            self.sparks.append(
                (
                    self.t,
                    tuple(o[i] + d[i] * s for i in range(3)),
                )
            )
            del self.sparks[:-6]
            if e is None:
                self.hurt_heli(part)
            else:
                self.hurt_enemy(e, part)

        if self.mag <= 0:
            self._reload()

    def _spread(self, o, d):
        cone = math.radians(
            SPREAD[0] + (SPREAD[1] - SPREAD[0]) * self.heat
        )
        cone *= 1.0 - ADS_SPREAD * self.ads

        a = random.uniform(0.0, math.tau)
        r = cone * math.sqrt(random.random())
        n = math.hypot(d[0], d[2]) or 1.0
        ux, uy, uz = d[2] / n, 0.0, -d[0] / n
        vx, vy, vz = (
            d[1] * uz - d[2] * uy,
            d[2] * ux - d[0] * uz,
            d[0] * uy - d[1] * ux,
        )
        k1, k2 = math.cos(a) * r, math.sin(a) * r
        dd = (
            d[0] + ux * k1 + vx * k2,
            d[1] + uy * k1 + vy * k2,
            d[2] + uz * k1 + vz * k2,
        )
        m = math.sqrt(sum(c * c for c in dd)) or 1.0
        return o, tuple(c / m for c in dd)

    # --- update ------------------------------------------------------------

    def update(self, keys=None):
        if not self._active or self.paused:
            return

        dt = clamp(
            float(getattr(STATE, "dt", 1.0 / 60.0)),
            0.0,
            0.05,
        )
        self.t += dt
        if self._cutscene_wait:
            return
        bed = (
            "chase_end"
            if self.end_t is not None
            else "chase_heli"
            if self.heli_active()
            else "chase_x"
            if self.cp == 4
            else "chase"
        )
        self._snd("bed", bed, self.speed / SPEED)
        self._snd("update", dt)
        self.kick = max(0.0, self.kick - dt * 5.0)

        want = (
            1.0
            if (
                self.aiming
                and not self.reloading
                and not self.dying
                and self.end_t is None
                and self.wreck_t is None
            )
            else 0.0
        )
        rate = ADS_UP if want > self.ads else ADS_DOWN
        self.ads = clamp(
            self.ads
            + (want - self.ads) * min(1.0, dt * rate),
            0.0,
            1.0,
        )

        if not self.firing or self.reloading:
            self.heat = max(
                0.0, self.heat - dt * HEAT_COOL
            )

        self.shake = max(0.0, self.shake - dt * 1.5)
        self._puffs_update(dt)
        self._bullets_update(dt)
        self._repair_update(dt)

        if self.dodge_t is not None and self.t - self.dodge_t >= DODGE_S:
            self.dodge_t = None
        self._heli_update(dt)
        self._rocket_update(dt)

        if self.wreck_t is not None:
            self._capture(dt)
            return
        if self.dying:
            self.death_t += dt
            if self.death_t >= 2.4:
                self._setup(self.cp)
            return
        if self.end_t is not None:
            self._ending(dt)
            return

        self.sec_t += dt
        self._cans_update(dt)

        if self.reloading:
            a = RELOAD_S - self.reloading
            self.reloading = max(
                0.0, self.reloading - dt
            )
            b = RELOAD_S - self.reloading

            for t, what in RELOAD_EVENTS:
                if a < t <= b:
                    if what == "toss":
                        self._toss()
                    else:
                        self._snd(what)

            if not self.reloading:
                self.mag = MAG

        if self.firing and not self.reloading:
            self._fire()

        self._drive(dt)
        self._spawns()
        self._enemy_update(dt)

        if self.timer is not None:
            self.timer -= dt
            if self.timer <= 0.0:
                self.timer = 0.0
                self._snd("horn", 0.4)
                self._fail(
                    "THE TRAIN LEFT - AGAIN FROM THE CROSSING"
                )

    def _puffs_update(self, dt):
        drag = max(0.0, 1.0 - dt * 1.8)
        keep = []

        for p in self.puffs:
            p[0] += dt
            if p[0] < PUFF[p[7]][0]:
                p[1] += p[4] * dt
                p[2] += p[5] * dt
                p[3] += p[6] * dt
                p[4] *= drag
                p[6] *= drag
                keep.append(p)

        self.puffs = keep
        if self.dying:
            return

        out = []
        dirt = S.ASPHALT_FROM

        if self.speed > 1.0:
            (tx, ty, tz), tyaw = self.tractor_pos()
            out.append(
                (
                    "exhaust",
                    _local(
                        (tx, ty, tz),
                        tyaw,
                        (-0.37, 2.8, 1.1),
                    ),
                    10.0,
                    "ex",
                    self.speed,
                )
            )

            (lx, ly, lz), lyaw = self.trailer_pos()
            if lz < dirt:
                for side in (-1.0, 1.0):
                    out.append(
                        (
                            "trail",
                            _local(
                                (lx, ly, lz),
                                lyaw,
                                (side * 1.1, 0.15, -1.4),
                            ),
                            3.0 * self.speed / SPEED,
                            ("tr", side),
                            self.speed,
                        )
                    )

        for e in self.enemies:
            if (
                e["kind"] in ("jeep", "gun_truck")
                and not e["wrecked"]
                and e["z"] < dirt
                and e["v"] > 2.0
            ):
                back = (
                    -2.6 if e["kind"] == "gun_truck" else -2.0
                )
                y, pitch, roll = self._enemy_pose(e)
                out.append(
                    (
                        "dust",
                        S._xf(
                            (0.0, 0.2, back),
                            (e["x"], y, e["z"]),
                            e["yaw"],
                            pitch,
                            roll,
                        ),
                        11.0,
                        id(e),
                        e["v"],
                    )
                )

            elif e["wrecked"] and e["kind"] != "foot":
                el = (
                    self.t
                    - e["dead_t"]
                    - e.get("burn_at", 0.2)
                )

                if el > 0.0 and abs(e["z"] - self.z) < 120.0:
                    eng = S._xf(
                        (0.0, 1.3, 1.0),
                        (e["x"], e["wy"], e["z"]),
                        e["yaw"],
                        e["wp"],
                        e["wr"],
                    )
                    out.append(
                        (
                            "burn",
                            eng,
                            5.0 * clamp(
                                1.2 - el / 14.0, 0.25, 1.0
                            ),
                            ("burn", id(e)),
                            0.0,
                        )
                    )
                    if el < 9.0:
                        out.append(
                            (
                                "fire",
                                eng,
                                6.0 * (1.0 - el / 9.0),
                                ("lick", id(e)),
                                0.0,
                            )
                        )

        for kind, pos, rate, key, v in out:
            acc = (
                self._emit.get(key, random.random())
                + rate * dt
            )

            while acc >= 1.0 and len(self.puffs) < PUFF_MAX:
                acc -= 1.0
                rise = PUFF[kind][4]
                lat = (
                    0.5
                    if kind in ("exhaust", "burn", "fire")
                    else 1.4
                )
                self.puffs.append(
                    [
                        0.0,
                        pos[0] + random.uniform(-0.3, 0.3),
                        pos[1],
                        pos[2] + random.uniform(-0.3, 0.3),
                        random.uniform(-lat, lat),
                        rise * random.uniform(0.7, 1.3),
                        v * (
                            0.85 if kind == "exhaust" else 0.3
                        ),
                        kind,
                        random.randrange(6),
                    ]
                )

            self._emit[key] = min(acc, 1.0)

    def _drive(self, dt):
        stop = None
        if self.cp == 3 and self.heli_active():
            stop = S.SECTIONS[4] - 30.0
        elif self.cp == 4 and self.blocked():
            stop = STOP_Z
        elif self.cp == 4:
            stop = S.CROSSING_Z

        want = SPEED
        if stop is not None:
            want = min(
                SPEED, max(0.0, (stop - self.z) * 0.9)
            )

        self.speed += (
            want - self.speed
        ) * min(1.0, dt * 2.0)
        self.z += self.speed * dt
        self.odo += self.speed * dt

        if stop is not None and self.z > stop:
            self.z, self.speed = stop, 0.0

        lane = 0.0
        steer = 1.6
        if self.dodge_t is not None:
            lane = self.dodge_lane
            steer = 11.5
        elif self.cp == 2:
            for wx, wz in S.wrecks():
                if -6.0 < wz - self.z < 26.0:
                    lane = (
                        -1.4 if wx > S.road_x(wz) else 1.4
                    )
                    break

        self.lane += (
            lane - self.lane
        ) * min(1.0, dt * steer)

        if abs(self.z - S.DITCH_Z) < 4.0:
            self.shake = 1.0
        if self.cp == 1 and self.z > S.DITCH_Z - 70.0:
            self.say(
                "BODI", "Hold on!", 2.0, key="ditch"
            )

        nxt = self.cp + 1
        if nxt < len(S.SECTIONS) and self.z >= S.SECTIONS[nxt]:
            self._checkpoint(nxt)

        if (
            self.cp == 4
            and self.barrier_t is None
            and self.z >= S.BARRIER_Z - 3.0
        ):
            self.barrier_t = self.t
            self.shake = 1.0
            self._snd("impact", False)

        if (
            self.cp == 4
            and not self.blocked()
            and self.z >= S.CROSSING_Z - 0.3
        ):
            self.end_t = self.t
            g = self._rig()
            self._jump_start = (g["feet"], self.yaw, dict(g["pose"]))
            self.firing = False
            self.say(
                "BODI",
                "Go! Go, I've got the barrier.",
                3.0,
            )
            self._snd("trac_still")

    def _checkpoint(self, n):
        self.cp = n
        self.sec_t = 0.0
        self.spawn_i = 0
        self.hull = max(self.hull, 65.0)
        self.repairs = max(self.repairs, REPAIRS_MAX)
        STATE.m8_chase_cp = n
        self.cp_toast = self.t

        if n == 2:
            self.say(
                "BODI",
                "Through the old cars. Keep your head down.",
                3.0,
            )

        if n == 3:
            self.heli = None
            self.rockets = []
            if not self._heli_seen:
                self._start_heli_cutscene()
            else:
                self._spawn_heli()

        if n == 4:
            self.timer = CROSSING_TIME
            self._spawn(
                "blocker",
                0.0,
                z=S.CROSSING_Z,
                x=S.road_x(S.CROSSING_Z) - 0.4,
            )
            self._snd("horn", 0.3)
            self.say(
                "BODI",
                "Barrier's down. Jeep on the tracks - clear it!",
                3.4,
            )

    def _ending(self, dt):
        el = self.t - self.end_t
        self.speed = max(0.0, self.speed - dt * 8.0)
        self.odo += self.speed * dt

        if self.train_t is None and el > 1.2:
            self.train_t = self.t
            self._snd("horn", 0.55)

        if el > 6.5:
            self.fade = clamp(
                (el - 6.5) / 1.2, 0.0, 1.0
            )
        if el > 7.8:
            self.finish("train")

    # --- drawing -----------------------------------------------------------

    def train_x(self):
        rx = S.road_x(S.CROSSING_Z)
        if self.train_t is None:
            return rx + S.TRAIN_LAST_X
        el = self.t - self.train_t
        return rx + S.TRAIN_LAST_X + 0.6 * el * el

    def _flash_light_pos(self):
        """Place the shot light ahead of the real barrel opening."""
        tip = self.gun_pt(S.LMG_MUZZLE)
        origin = self.gun_pt((0.0, 0.0, 0.0))
        forward_pt = self.gun_pt((0.0, 0.0, 1.0))
        f = _f_unit(
            tuple(
                forward_pt[i] - origin[i]
                for i in range(3)
            )
        )
        return tuple(
            tip[i] + f[i] * 0.25
            for i in range(3)
        )

    def _flash_lights(self):
        """Brief warm illumination from actual muzzle discharges."""
        now = self.t
        out = []

        for f in self.flashes:
            t0, pos = f[0], f[1]
            age = now - t0
            if 0.0 <= age < 0.08:
                out.append(
                    {
                        "pos": pos,
                        "color": (255, 190, 120),
                        "intensity": (
                            1.8 * (1.0 - age / 0.08)
                        ),
                        "range": 6.0,
                    }
                )

        for im in self.impacts:
            if im["kind"] == "metal":
                age = now - im["t0"]
                if 0.0 <= age < 0.07:
                    (lx, ly, lz), lyaw = self.trailer_pos()
                    pos = (
                        S._xf(im["local"], (lx, ly, lz), lyaw, S.ditch_pitch(lz))
                        if im["local"] is not None
                        else im["pos"]
                    )
                    out.append(
                        {
                            "pos": pos,
                            "color": (255, 205, 120),
                            "intensity": 1.3 * (1.0 - age / 0.07),
                            "range": 3.5,
                        }
                    )

        if self.wreck_t is not None:
            (tx, ty, tz), tyaw = self.tractor_pos()
            el = self.t - self.wreck_t
            out.append(
                {
                    "pos": _local(
                        (tx, ty, tz),
                        tyaw,
                        (0.0, 1.9, 1.0),
                    ),
                    "color": (255, 150, 70),
                    "intensity": (
                        (3.0 if el < 0.3 else 1.3)
                        + 0.25 * math.sin(self.t * 23.0)
                    ),
                    "range": 9.0,
                }
            )

        age = self.t - self.last_flash
        duration = FLASH_MS / 1000.0
        if 0.0 <= age < duration:
            strength = (1.0 - age / duration) ** 1.6
            out.append(
                {
                    "pos": self._flash_light_pos(),
                    "color": (255, 206, 132),
                    "intensity": FLASH_LIGHT * strength,
                    "range": 4.8,
                }
            )

        return out

    def draw(self, surface):
        if not self._active:
            return
        self.render(surface, *self.camera())
        self._hud(surface)

    def render(self, surface, eye, tgt, fov):
        """Render the world without HUD, also used by the pullout film."""
        tm = int(self.t * 1000.0)
        r = S.frame(
            eye, tgt, fov, tm, lights=self._flash_lights()
        )
        del _w.LAST[:]
        self._draw_vehicles(r, tm)
        self._draw_people(r, tm)
        self._draw_fx(r, tm)
        self._draw_smoke(r, tm)
        S.present(r, surface)
        draw_vignette(surface)

    def _draw_vehicles(self, r, tm):
        (tx, ty, tz), tyaw = self.tractor_pos()
        burnt = (
            self.wreck_t is not None
            and self.t - self.wreck_t > 0.12
        )
        S.put_wheeled(
            r,
            "tractor_burnt" if burnt else "tractor",
            (tx, ty, tz),
            tyaw,
            self.tractor_pitch(),
            self.odo,
        )
        r.add_blob_shadow(
            (tx, S.ditch_y(tz) + 0.06, tz),
            1.4,
            2.1,
            0.5,
        )

        (lx, ly, lz), lyaw = self.trailer_pos()
        S.put_wheeled(
            r,
            "trailer",
            (lx, ly, lz),
            lyaw,
            S.ditch_pitch(lz),
            self.odo,
        )
        r.add_blob_shadow(
            (lx, S.ditch_y(lz) + 0.06, lz),
            1.3,
            2.1,
            0.5,
        )
        self._draw_mount(r)
        lp = S.ditch_pitch(lz)
        tb_pos = S._xf(S.TOOLBOX_AT, (lx, ly, lz), lyaw, lp)
        S.put(r, "toolbox_base", S.toolbox_base, tb_pos, lyaw, lp)
        open_k = 0.0
        if self.repair_t is not None:
            el_r = self.t - self.repair_t
            open_k = R._ease(clamp(min((el_r - 0.32) / 0.18, (2.14 - el_r) / 0.16), 0.0, 1.0))
        lid_pos = S._xf(
            tuple(S.TOOLBOX_AT[i] + S.TOOLBOX_HINGE[i] for i in range(3)),
            (lx, ly, lz),
            lyaw,
            lp,
        )
        S.put(r, "toolbox_lid", S.toolbox_lid, lid_pos, lyaw, lp - 95.0 * open_k)
        self._draw_heli(r, tm)

        for e in self.enemies:
            if e["kind"] == "foot":
                continue

            key = (
                "gun_truck"
                if e["kind"] == "gun_truck"
                else "jeep"
            )
            y, pitch, roll = self._enemy_pose(e)

            if e["wrecked"]:
                if (
                    self.t - e["dead_t"]
                    > e.get("burn_at", 0.2)
                ):
                    key += "_burnt"
            elif abs(e["z"] - tz) > LAMP_RANGE:
                key += "_dark"

            S.put_wheeled(
                r,
                key,
                (e["x"], y, e["z"]),
                e["yaw"],
                pitch,
                e["odo"],
                roll,
            )
            big = e["kind"] == "gun_truck"
            gy = S.surface_y(e["x"], e["z"])
            r.add_blob_shadow(
                (e["x"], gy + 0.06, e["z"]),
                1.35 if big else 1.15,
                3.1 if big else 2.4,
                0.5 / (1.0 + max(0.0, y - gy)),
            )

        rx = S.road_x(S.BARRIER_Z)
        up = (
            0.0
            if self.barrier_t is None
            else clamp(
                (self.t - self.barrier_t) / 0.3,
                0.0,
                1.0,
            )
        )
        if up < 0.5:
            S.put(
                r,
                "barrier_arm",
                S.barrier_arm,
                (
                    rx + S.ROAD_W / 2.0 + 0.8,
                    1.0,
                    S.BARRIER_Z,
                ),
                90.0,
            )
        else:
            S.put(
                r,
                "barrier_arm",
                S.barrier_arm,
                (rx - 3.0, 0.05, S.BARRIER_Z + 3.0),
                210.0,
            )

        S.put(
            r,
            "train",
            S.train,
            (self.train_x(), 0.0, S.CROSSING_Z),
            0.0,
        )

    def _draw_heli(self, r, tm):
        h = self.heli
        if h is None:
            return
        burned = h["state"] in ("skidding", "crashed")
        S.put_helicopter(
            r,
            (h["x"], h["y"], h["z"]),
            h["yaw"], h["pitch"], h["roll"],
            h["main_spin"], h["tail_spin"],
            burned=burned,
        )
        gy = S.surface_y(h["x"], h["z"])
        r.add_blob_shadow(
            (h["x"], gy + 0.06, h["z"]),
            3.8, 5.2,
            0.45 / (1.0 + max(0.0, h["y"] - gy)),
        )

    def _draw_heli_crew(self, r, tm):
        h = self.heli
        if h is None or h["state"] in ("crashing", "skidding", "crashed"):
            return
        info = S.helicopter_parts()[3]
        pos = (h["x"], h["y"], h["z"])
        pilot = S._xf(info["pilot_seat"], pos, h["yaw"], h["pitch"], h["roll"])
        _w.actor(
            r, ("guard", "rifle"), dict(_SEATED), pilot, h["yaw"], tm,
            seed=150, amp=0.0, rifle_on=False, flags=("os12",),
        )
        if h["gunner"]:
            seat = S._xf(info["gunner_seat"], pos, h["yaw"], h["pitch"], h["roll"])
            _w.actor(
                r, ("guard", "heavy"), blend(POSES["stand"], "aim", 0.9),
                seat, (h["yaw"] - 55.0) % 360.0, tm,
                seed=151, amp=0.15, rifle_on=True, flags=("os12",),
            )
        else:
            seat = S._xf(info["gunner_seat"], pos, h["yaw"], h["pitch"], h["roll"])
            _w.actor(
                r, ("guard", "heavy"), dict(_SEATED_DEAD), seat, h["yaw"], tm,
                seed=151, amp=0.0, rifle_on=False, flags=("os12",),
            )

    def _draw_heli_fx(self, r, tm):
        h = self.heli
        if h is not None:
            if h["state"] == "rocket_lock":
                info = S.helicopter_parts()[3]
                p = S._xf(
                    info["rocket_pylon"],
                    (h["x"], h["y"], h["z"]),
                    h["yaw"], h["pitch"], h["roll"],
                )
                r.add_sprite(
                    p,
                    _fx.glow(
                        (255, 70, 50), 0.35, tm,
                        flicker=0.6, core=(255, 200, 180), intensity=1.1, max_px=26,
                    ),
                    layer=_fx.FX_LAYER,
                )
            if h["state"] in ("crashing", "crashed"):
                for i in range(3):
                    a = (self.t * 0.7 + i / 3.0) % 1.0
                    c = (
                        h["x"] + 0.5 * math.sin(i * 2.1 + self.t),
                        h["y"] + 0.7 + 1.3 * a,
                        h["z"] + 0.4 * math.cos(i * 1.7 + self.t),
                    )
                    r.add_sprite(
                        c,
                        _fx.glow(
                            (255, 120, 50), 0.35 + 0.4, tm,
                            flicker=0.5, seed=40 + i,
                            core=(255, 220, 150),
                            intensity=1.0 * (1.0 - a), max_px=32,
                        ),
                        layer=_fx.FX_LAYER,
                    )

        if h is not None and h.get("boom_t") is not None and self.t - h["boom_t"] < 0.7:
            age = int((self.t - h["boom_t"]) * 1000.0)
            c = (h["x"], h["y"] + 1.2, h["z"])
            r.add_sprite(c, _fx.flash(age, col=(255, 195, 110), radius_m=5.5, dur_ms=550), layer=_fx.FX_LAYER)
            r.add_sprite(c, _fx.sparks(int(h["boom_t"] * 100), age, col=(255, 210, 140), n=24, speed_m=9.0, dur_ms=700), layer=_fx.FX_LAYER)

        for rk in self.rockets:
            if rk["done"]:
                continue
            px, py, pz = rk["pos"]
            ryaw = rk.get("yaw", 0.0)
            rpitch = rk.get("pitch", -8.0)
            S.put(r, "rocket", S.rocket, (px, py, pz), ryaw, rpitch)
            tail = S._xf((0.0, 0.0, -S.ROCKET_LEN * 0.5), (px, py, pz), ryaw, rpitch)
            r.add_sprite(
                tail,
                _fx.glow(
                    (255, 150, 70), 0.24, tm,
                    flicker=0.45, core=(255, 236, 180), intensity=1.1, max_px=20,
                ),
                layer=_fx.FX_LAYER,
            )

    def _draw_mount(self, r):
        g = self._rig()
        el, yaw = g["el"], g["gyaw"]
        S.put(
            r,
            ("lmg_yoke", round(g["h"], 2)),
            lambda: S.lmg_yoke(g["h"]),
            g["top"],
            yaw,
        )

        tx, ty, tz = S.RACK
        cans = (
            tz[1:]
            if el is not None and el >= CAN_NEW[0]
            else tz
        )
        for cz in cans:
            S.put(
                r,
                "lmg_can",
                S.lmg_can,
                _local(
                    g["top"],
                    yaw,
                    (tx, ty + 0.098, cz),
                ),
                yaw,
            )

        S.put(
            r,
            "lmg_body",
            S.lmg_body,
            g["pivot"],
            yaw,
            g["gpitch"],
        )
        S.put(
            r,
            "lmg_cover",
            S.lmg_cover,
            self.gun_pt(S.LMG_HINGE),
            yaw,
            g["gpitch"] - _cover_lift(el),
        )

        if (
            el is None
            or el < CAN_OLD[0]
            or el >= CAN_NEW[1]
        ):
            S.put(
                r,
                "lmg_can",
                S.lmg_can,
                self.gun_pt(S.LMG_CAN),
                yaw,
                g["gpitch"],
            )

        for p, _v, spin, cyaw in self.cans:
            S.put(
                r, "lmg_can", S.lmg_can, p, cyaw, spin
            )

    def _draw_hand_can(self, r, lhand):
        g = self._rig()
        el = g["el"]

        if el is None or not (
            CAN_OLD[0] <= el < CAN_OLD[1]
            or CAN_NEW[0] <= el < CAN_NEW[1]
        ):
            self._can_at = None
            return

        side = (0.1, 0.0, 0.0)
        top = (-0.04, -0.1, 0.0)
        k = clamp(
            (el - CAN_NEW[0]) / (CAN_NEW[1] - CAN_NEW[0]),
            0.0,
            1.0,
        )
        off = (
            tuple(
                top[i] + (side[i] - top[i]) * k
                for i in range(3)
            )
            if el >= CAN_NEW[0]
            else side
        )
        self._can_at = _local(lhand, g["gyaw"], off)
        S.put(
            r,
            "lmg_can",
            S.lmg_can,
            self._can_at,
            g["gyaw"],
            0.0,
        )

    def _draw_people(self, r, tm):
        (tx, ty, tz), tyaw = self.tractor_pos()
        bodi_wave = (
            self.end_t is not None
            and self.t - self.end_t > 0.4
        )
        bp = dict(_SEATED)

        if bodi_wave:
                    w = math.sin(self.t * 8.0)
                    bp.update(
                        twist=16,
                        head_y=54,
                        head_p=-4,
                        rsh_p=118,
                        rsh_r=-32 - 8 * w,
                        rsh_y=32,
                        rel=40 + 22 * w,
                    )

        if self.repair_t is not None:
            bp.update(twist=42, head_y=38, head_p=6)

        if self.wreck_t is not None:
            self._draw_capture(r, tm)
            return

        self._draw_heli_crew(r, tm)

        _w.actor(
            r,
            ("ally", "bodi"),
            bp,
            _local(
                (tx, ty, tz), tyaw, (0.0, 0.62, -0.75)
            ),
            tyaw,
            tm,
            seed=61,
            amp=0.2,
            rifle_on=False,
            mouth=None,
        )

        if self.end_t is not None:
            self._draw_jump(r, tm, BIRIBEL)
        elif self.repair_t is not None:
            self._draw_repair(r, tm)
        else:
            g = self._rig()
            joints = _w.actor(
                r,
                BIRIBEL,
                g["pose"],
                g["feet"],
                self.yaw,
                tm,
                seed=93,
                amp=0.1,
                rifle_on=False,
                flags=(GUN,),
                expression="angry",
                mouth=0.0,
            )
            if joints:
                self._draw_hand_can(r, joints["lhand"])

            age = self.t - self.last_flash
            if 0.0 <= age < FLASH_MS / 1000.0:
                self._draw_muzzle(
                    r,
                    tm,
                    self.gun_pt(S.LMG_MUZZLE),
                    g["gyaw"],
                    g["gpitch"],
                    int(age * 1000.0),
                    self.flash_seed,
                )

        for e in self.enemies:
            self._draw_crew(r, tm, e)

    @staticmethod
    def _hammer(r, hand, pose, yaw):
        m = Mesh()
        wood = (138, 94, 54)
        grip = (34, 34, 36)
        ferrule = (96, 100, 106)
        head_dark = (64, 68, 74)
        face_steel = (200, 204, 210)
        peen_steel = (118, 122, 128)

        # Hickory shaft + rubber grip + collar along +z in fist space
        m.add(box(0.028, 0.036, 0.34, wood, center=(0.0, 0.0, 0.11)))
        m.add(box(0.034, 0.042, 0.12, grip, center=(0.0, 0.0, 0.0)))
        m.add(box(0.036, 0.044, 0.03, ferrule, center=(0.0, 0.0, 0.255)))

        # Heavy T-head: striking face on -y (hits straight down), tapered peen on +y
        m.add(box(0.056, 0.072, 0.054, head_dark, center=(0.0, -0.005, 0.285)))
        m.add(box(0.052, 0.026, 0.050, (92, 96, 104), center=(0.0, -0.048, 0.285)))
        m.add(box(0.056, 0.014, 0.054, face_steel, center=(0.0, -0.066, 0.285)))
        m.add(box(0.042, 0.028, 0.042, head_dark, center=(0.0, 0.042, 0.285)))
        m.add(box(0.032, 0.020, 0.030, peen_steel, center=(0.0, 0.062, 0.285)))

        F = m_mul(_right_forearm_mat(pose, yaw), rot_x(12.0))
        verts = [tuple(a + b for a, b in zip(m_apply(F, v), hand)) for v in m.verts]
        r.add_dynamic(verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces])

    def _draw_repair(self, r, tm):
        el = self.t - self.repair_t
        (lx, ly, lz), lyaw = self.trailer_pos()
        lp = S.ditch_pitch(lz)
        g = self._rig()
        hum = _w.hum(BIRIBEL, flags=(GUN,))
        keys = _repair_keys(hum)

        p_start = g["feet"]
        p_grab = S._xf(_REPAIR_GRAB_LOCAL, (lx, ly, lz), lyaw, lp)
        p_work = S._xf(_REPAIR_WORK_LOCAL, (lx, ly, lz), lyaw, lp)
        tb = S._xf(S.TOOLBOX_AT, (lx, ly, lz), lyaw, lp)
        pump = S._xf(S.RIG_PUMP_AT, (lx, ly, lz), lyaw, lp)

        grab_yaw = _yaw_to(tb[0] - p_grab[0], tb[2] - p_grab[2])
        work_yaw = _yaw_to(pump[0] - p_work[0], pump[2] - p_work[2])

        def yaw_mix(a, b, k):
            return (a + _wrap(b - a) * clamp(k, 0.0, 1.0)) % 360.0

        show_hammer = False
        if el < 0.40:
            u = clamp(el / 0.40, 0.0, 1.0)
            k = R._ease(u)
            pos = tuple(p_start[i] + (p_grab[i] - p_start[i]) * k for i in range(3))
            yaw = yaw_mix(self.yaw, grab_yaw, k)
            walk = pose_run(u * math.pi * 2.0, lean=7.0)
            pose = blend(blend(g["pose"], keys["reach"], k), walk, 0.65 * math.sin(math.pi * u))
        elif el < 0.60:
            k = R._ease(clamp((el - 0.40) / 0.20, 0.0, 1.0))
            pos, yaw = p_grab, grab_yaw
            pose = blend(keys["reach"], keys["grab"], k)
            show_hammer = el >= 0.56
        elif el < 0.76:
            k = R._ease(clamp((el - 0.60) / 0.16, 0.0, 1.0))
            pos = tuple(p_grab[i] + (p_work[i] - p_grab[i]) * k for i in range(3))
            yaw = yaw_mix(grab_yaw, work_yaw, k)
            pose = blend(keys["grab"], keys["work_up"], k)
            show_hammer = True
        elif el < 1.96:
            frac = ((el - 0.76) / 0.40) % 1.0
            k = _hammer_curve(frac)
            pos, yaw = p_work, work_yaw
            pose = blend(keys["work_down"], keys["work_up"], k)
            show_hammer = True
        elif el < 2.10:
            k = R._ease(clamp((el - 1.96) / 0.14, 0.0, 1.0))
            pos = tuple(p_work[i] + (p_grab[i] - p_work[i]) * k for i in range(3))
            yaw = yaw_mix(work_yaw, grab_yaw, k)
            pose = blend(keys["work_down"], keys["grab"], k)
            show_hammer = el < 2.06
        else:
            u = clamp((el - 2.10) / max(1e-4, REPAIR_S - 2.10), 0.0, 1.0)
            k = R._ease(u)
            pos = tuple(p_grab[i] + (p_start[i] - p_grab[i]) * k for i in range(3))
            yaw = yaw_mix(grab_yaw, self.yaw, k)
            walk = pose_run(u * math.pi * 2.0, lean=7.0)
            pose = blend(blend(keys["grab"], g["pose"], k), walk, 0.65 * math.sin(math.pi * u))

        joints = _w.actor(
            r, BIRIBEL, pose, pos, yaw, tm, seed=93, amp=0.06,
            rifle_on=False, flags=(GUN,), expression="angry", mouth=0.0,
        )
        if show_hammer and joints and "rhand" in joints:
            self._hammer(r, joints["rhand"], pose, yaw)

    def _prisoner(
        self,
        r,
        tm,
        key,
        seat,
        seat_pose,
        mark,
        yaw,
        t_down,
        t_kneel,
        seed,
        rig=False,
        via=None,
    ):
        el = self.t - self.wreck_t

        if (
            via is not None
            and t_down <= el < t_down + 0.45
        ):
            k = R._ease((el - t_down) / 0.45)
            pos = tuple(
                seat[i] + (via[i] - seat[i]) * k
                for i in range(3)
            )
            pos = (
                pos[0],
                pos[1] + 0.12 * math.sin(math.pi * k),
                pos[2],
            )
            _w.actor(
                r,
                key,
                _mix(seat_pose, POSES["stand"], k),
                pos,
                yaw,
                tm,
                seed=seed,
                amp=0.15,
                rifle_on=False,
                mouth=None,
            )
            return

        if via is not None:
            seat, t_down = via, t_down + 0.45

        if el < t_down:
            if rig:
                g = self._rig()
                _w.actor(
                    r,
                    key,
                    g["pose"],
                    g["feet"],
                    self.yaw,
                    tm,
                    seed=seed,
                    amp=0.1,
                    rifle_on=False,
                    flags=(GUN,),
                    expression="angry",
                    mouth=0.0,
                )
            else:
                (_tx, _ty, _tz), tyaw = self.tractor_pos()
                _w.actor(
                    r,
                    key,
                    seat_pose,
                    seat,
                    tyaw,
                    tm,
                    seed=seed,
                    amp=0.2,
                    rifle_on=False,
                    mouth=None,
                )
            return

        k = clamp((el - t_down) / 0.7, 0.0, 1.0)
        pos = tuple(
            seat[i] + (mark[i] - seat[i]) * k
            for i in range(3)
        )
        pos = (
            pos[0],
            pos[1] + 0.5 * math.sin(math.pi * k),
            pos[2],
        )

        if k < 1.0:
            pose = blend(
                POSES["stand"], "crouch", math.sin(math.pi * k)
            )
        elif el < t_kneel:
            pose = _mix(
                POSES["stand"],
                _HANDS_UP,
                clamp(
                    (el - t_down - 0.7) / 0.35,
                    0.0,
                    1.0,
                ),
            )
        else:
            pose = _mix(
                _HANDS_UP,
                _KNEEL_HANDS,
                R._ease(
                    clamp(
                        (el - t_kneel) / 0.6,
                        0.0,
                        1.0,
                    )
                ),
            )

        _w.actor(
            r,
            key,
            pose,
            pos,
            yaw,
            tm,
            seed=seed,
            amp=0.15,
            rifle_on=False,
            expression="angry" if key == BIRIBEL else None,
            mouth=0.0 if key == BIRIBEL else None,
        )

    def _draw_capture(self, r, tm):
        el = self.t - self.wreck_t
        trac, trl = self.tractor_pos(), self.trailer_pos()
        (tx, ty, tz), tyaw = trac
        face = (tyaw - self.slew - 90.0) % 360.0

        self._prisoner(
            r,
            tm,
            BIRIBEL,
            self.biribel_pos(),
            None,
            self._ground(trl, (-1.9, 0.0, -0.2)),
            face,
            2.7,
            5.8,
            93,
            rig=True,
        )

        land = _local(
            (tx, ty, tz), tyaw, (-1.75, 0.0, 0.5)
        )
        self._prisoner(
            r,
            tm,
            ("ally", "bodi"),
            _local(
                (tx, ty, tz), tyaw, (0.0, 0.62, -0.75)
            ),
            dict(_SEATED),
            (land[0], S.ditch_y(land[2]), land[2]),
            face,
            3.1,
            6.1,
            61,
            via=_local(
                (tx, ty, tz), tyaw, (-0.72, 0.72, 0.45)
            ),
        )

        for c in self.captors:
            a = clamp(
                (el - 2.0 - c["t0"]) / 1.9,
                0.0,
                1.0,
            )
            sx, sy, sz = c["src"]
            dx, dy, dz = c["dst"]
            pos = (
                sx + (dx - sx) * a,
                sy + (dy - sy) * a,
                sz + (dz - sz) * a,
            )
            mx, _my, mz = c["mark"]
            yaw = _yaw_to(mx - pos[0], mz - pos[2])

            if a < 1.0:
                sw = math.sin((el - c["t0"]) * 9.0)
                pose = dict(
                    blend(POSES["stand"], "aim", 0.75),
                    lhip_p=26 * sw,
                    rhip_p=-26 * sw,
                    lkn=12 + 22 * max(0.0, -sw),
                    rkn=12 + 22 * max(0.0, sw),
                )
            else:
                pose = blend(POSES["stand"], "aim", 0.92)

            gk = (
                "guard",
                R.GUARD_VIEW[c["seed"] % len(R.GUARD_VIEW)],
            )
            _w.actor(
                r,
                gk,
                pose,
                pos,
                yaw,
                tm,
                seed=c["seed"],
                amp=0.25,
                rifle_on=True,
                flags=("os12",),
            )

        for e in self.enemies:
            self._draw_crew(r, tm, e)

    def _draw_jump(self, r, tm, key):
        el = self.t - self.end_t
        start_pos, start_yaw, start_pose = self._jump_start or (
            self.biribel_pos(),
            self.yaw,
            dict(POSES["stand"]),
        )
        (lx, _ly, lz), lyaw = self.trailer_pos()
        rx = S.road_x(S.CROSSING_Z)

        off_trailer = _local((lx, 0.0, lz), lyaw, (1.8, 0.0, 1.0))
        off_trailer = (off_trailer[0], S.ditch_y(off_trailer[2]), off_trailer[2])

        # Where the train will be at el = 2.35 (train_t begins at el = 1.2)
        launch_train_x = rx + S.TRAIN_LAST_X + 0.6 * (2.35 - 1.2) ** 2
        launch = (launch_train_x - 1.4, 0.0, S.CROSSING_Z - 0.35)
        step = (self.train_x() - 0.3, 1.26, S.CROSSING_Z)

        def yaw_mix(a, b, k):
            return (a + _wrap(b - a) * clamp(k, 0.0, 1.0)) % 360.0

        run_yaw = _yaw_to(launch[0] - off_trailer[0], launch[2] - off_trailer[2])
        hop_yaw = _yaw_to(step[0] - launch[0], step[2] - launch[2])
        land_crouch = blend(POSES["stand"], "crouch", 0.55)

        if el < 0.25:
            u = R._ease(el / 0.25)
            pos = start_pos
            yaw = yaw_mix(start_yaw, run_yaw, u * 0.5)
            pose = _mix(start_pose, POSES["stand"], u)
        elif el < 0.75:
            u = (el - 0.25) / 0.50
            k = R._ease(u)
            pos = (
                start_pos[0] + (off_trailer[0] - start_pos[0]) * k,
                start_pos[1] + (off_trailer[1] - start_pos[1]) * k + 0.25 * math.sin(math.pi * u),
                start_pos[2] + (off_trailer[2] - start_pos[2]) * k,
            )
            yaw = yaw_mix(start_yaw, run_yaw, 0.5 + 0.5 * k)
            pose = blend(POSES["stand"], "crouch", 0.55 * math.sin(math.pi * u))
        elif el < 2.35:
            u = (el - 0.75) / 1.60
            pos = (
                off_trailer[0] + (launch[0] - off_trailer[0]) * u,
                0.0,
                off_trailer[2] + (launch[2] - off_trailer[2]) * u,
            )
            yaw = yaw_mix(run_yaw, hop_yaw, clamp((u - 0.7) / 0.3, 0.0, 1.0))
            sw = math.sin((el - 0.75) * 13.0)
            pose = dict(
                POSES["stand"],
                spine=14,
                head_p=-6,
                lhip_p=38 * sw,
                rhip_p=-38 * sw,
                lkn=16 + 36 * max(0.0, -sw),
                rkn=16 + 36 * max(0.0, sw),
                lsh_p=-34 * sw,
                rsh_p=34 * sw,
                lel=60,
                rel=60,
            )
        elif el < 3.05:
            u = (el - 2.35) / 0.70
            pos = (
                launch[0] + (step[0] - launch[0]) * u,
                launch[1] + (step[1] - launch[1]) * u + 0.45 * math.sin(math.pi * u),
                launch[2] + (step[2] - launch[2]) * u,
            )
            yaw = hop_yaw
            bound = dict(
                POSES["stand"],
                spine=16,
                head_p=-8,
                lhip_p=45,
                lkn=50,
                rhip_p=-20,
                rkn=25,
                lsh_p=110,
                lel=45,
                rsh_p=90,
                rel=55,
            )
            pose = _mix(bound, land_crouch, R._ease(clamp((u - 0.68) / 0.32, 0.0, 1.0)))
        else:
            u = R._ease(clamp((el - 3.05) / 0.65, 0.0, 1.0))
            pos = step
            yaw = yaw_mix(hop_yaw, 270.0, u)
            pose = _mix(land_crouch, POSES["stand"], u)

        _w.actor(
            r,
            key,
            pose,
            pos,
            yaw,
            tm,
            seed=93,
            amp=0.15 if el >= 3.7 else 0.0,
            rifle_on=False,
            mouth=0.0,
        )

    def _draw_crew(self, r, tm, e):
        y, pitch, roll = self._enemy_pose(e)
        p = (e["x"], y, e["z"])

        if e["kind"] == "foot":
            gk = (
                "guard",
                R.GUARD_VIEW[e["slot"] % len(R.GUARD_VIEW)],
            )

            if e["alive"]:
                (tx, _ty, tz), _ = self.trailer_pos()
                yaw = _yaw_to(tx - e["x"], tz - e["z"])
                _w.actor(
                    r,
                    gk,
                    blend(POSES["stand"], "aim", 0.85),
                    p,
                    yaw,
                    tm,
                    seed=100 + e["slot"],
                    amp=0.3,
                    rifle_on=True,
                    flags=("os12",),
                )
            else:
                k = clamp(
                    (self.t - e["dead_t"]) / 0.5,
                    0.0,
                    1.0,
                )
                _w.actor(
                    r,
                    gk,
                    blend("stand", "dead_back", k),
                    p,
                    e["yaw"],
                    tm,
                    seed=100 + e["slot"],
                    amp=0.0,
                    rifle_on=False,
                    flags=("os12",),
                )
            return

        if e["wrecked"]:
            _, _, _, rel_p, _, rel_r, _ = self._wreck_floor(e)
            if (
                math.cos(math.radians(rel_p))
                * math.cos(math.radians(rel_r))
                < 0.94
            ):
                return
            p = (e["x"], e["wy"], e["z"])

        gk = ("guard", "rifle")

        if e["kind"] == "gun_truck":
            _w.actor(
                r,
                gk,
                dict(
                    _SEATED
                    if e["driver"] and not e["wrecked"]
                    else _SEATED_DEAD
                ),
                S._xf(S.TRUCK_SEAT, p, e["yaw"], pitch, roll),
                e["yaw"],
                tm,
                seed=140,
                amp=0.0,
                rifle_on=False,
                flags=("os12",),
            )

            if e["gunner"] and not e["wrecked"]:
                _w.actor(
                    r,
                    ("guard", "heavy"),
                    blend(POSES["stand"], "aim", 0.9),
                    S._xf(S.TRUCK_BED, p, e["yaw"], pitch, roll),
                    e["yaw"],
                    tm,
                    seed=141,
                    amp=0.3,
                    rifle_on=True,
                    flags=("os12",),
                )
            return

        dead = not e["driver"] or e["wrecked"]
        _w.actor(
            r,
            gk,
            dict(_SEATED_DEAD if dead else _SEATED),
            S._xf(S.CAR_SEAT, p, e["yaw"], pitch, roll),
            e["yaw"],
            tm,
            seed=120 + e["slot"],
            amp=0.0,
            rifle_on=False,
            flags=("os12",),
        )

    def _draw_bullets(self, r, tm):
        if not self.bullets:
            return
        ex, ey, ez = self.camera()[0]
        m = Mesh()

        for b in self.bullets:
            u = clamp((self.t - b["t0"]) / max(b["dur"], 1e-4), 0.0, 1.0)
            s_pt, e_pt = b["start"], b["end"]
            dx = e_pt[0] - s_pt[0]
            dy = e_pt[1] - s_pt[1]
            dz = e_pt[2] - s_pt[2]
            total = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
            ux, uy, uz = dx / total, dy / total, dz / total
            tail_len = min(b["len"], total * u)
            head = (s_pt[0] + dx * u, s_pt[1] + dy * u, s_pt[2] + dz * u)

            if tail_len > 0.05:
                tail = (head[0] - ux * tail_len, head[1] - uy * tail_len, head[2] - uz * tail_len)
                mid = (
                    head[0] - ux * (tail_len * 0.45),
                    head[1] - uy * (tail_len * 0.45),
                    head[2] - uz * (tail_len * 0.45),
                )
                ref = (0.0, 1.0, 0.0) if abs(uy) < 0.9 else (1.0, 0.0, 0.0)
                side = _f_unit(_f_cross((ux, uy, uz), ref))
                up = _f_unit(_f_cross(side, (ux, uy, uz)))

                dist_cam = math.dist((ex, ey, ez), head)
                w_h = clamp((0.026 if b["heavy"] else 0.018) + 0.0016 * dist_cam, 0.026, 0.090)
                w_m = w_h * 0.65
                w_t = w_h * 0.22

                for axis in (side, up):
                    p0 = (mid[0] - axis[0] * w_m, mid[1] - axis[1] * w_m, mid[2] - axis[2] * w_m)
                    p1 = (mid[0] + axis[0] * w_m, mid[1] + axis[1] * w_m, mid[2] + axis[2] * w_m)
                    p2 = (head[0] + axis[0] * w_h, head[1] + axis[1] * w_h, head[2] + axis[2] * w_h)
                    p3 = (head[0] - axis[0] * w_h, head[1] - axis[1] * w_h, head[2] - axis[2] * w_h)
                    m.face([p0, p1, p2, p3], (255, 246, 198), 2, True, True)

                    q0 = (tail[0] - axis[0] * w_t, tail[1] - axis[1] * w_t, tail[2] - axis[2] * w_t)
                    q1 = (tail[0] + axis[0] * w_t, tail[1] + axis[1] * w_t, tail[2] + axis[2] * w_t)
                    m.face([q0, q1, p1, p0], (255, 148, 48), 2, True, True)

            r.add_sprite(
                head,
                _fx.glow(
                    (255, 196, 84),
                    0.28 if b["heavy"] else 0.18,
                    tm,
                    core=(255, 250, 224),
                    intensity=1.25 if b["heavy"] else 0.95,
                    max_px=16 if b["heavy"] else 12,
                ),
                layer=_fx.FX_LAYER,
            )

        if m.faces:
            _flash_submit(r, m, bias=-0.04)

    def _draw_impacts(self, r, tm):
        if not self.impacts:
            return
        (lx, ly, lz), lyaw = self.trailer_pos()
        pitch_t = S.ditch_pitch(lz)

        for im in self.impacts:
            age_s = self.t - im["t0"]
            if age_s < 0.0:
                continue
            age_ms = int(age_s * 1000.0)
            pos = (
                S._xf(im["local"], (lx, ly, lz), lyaw, pitch_t)
                if im["local"] is not None
                else im["pos"]
            )
            kind = im["kind"]
            heavy = im["heavy"]

            if kind in ("metal", "road"):
                dur_f = 0.14 if kind == "metal" else 0.12
                if age_s < dur_f:
                    r.add_sprite(
                        pos,
                        _fx.flash(
                            age_ms,
                            col=(255, 224, 150) if kind == "metal" else (255, 200, 120),
                            radius_m=(0.55 if heavy else 0.38) if kind == "metal" else (0.45 if heavy else 0.30),
                            dur_ms=int(dur_f * 1000),
                        ),
                        layer=_fx.FX_LAYER,
                    )
                r.add_sprite(
                    pos,
                    _fx.sparks(
                        im["seed"],
                        age_ms,
                        col=(255, 215, 130),
                        n=(12 if heavy else 8) if kind == "metal" else (9 if heavy else 6),
                        speed_m=4.8 if kind == "metal" else 4.2,
                        dur_ms=300 if kind == "metal" else 240,
                    ),
                    layer=_fx.FX_LAYER,
                )
            elif kind in ("wood", "hay"):
                if age_s < 0.10:
                    r.add_sprite(
                        pos,
                        _fx.glow(
                            (255, 188, 100),
                            0.32,
                            tm,
                            core=(255, 236, 190),
                            intensity=0.95 * (1.0 - age_s / 0.10),
                            max_px=20,
                        ),
                        layer=_fx.FX_LAYER,
                    )
                r.add_sprite(
                    pos,
                    _fx.sparks(
                        im["seed"],
                        age_ms,
                        col=(210, 178, 112) if kind == "hay" else (184, 146, 98),
                        n=10,
                        speed_m=3.6,
                        dur_ms=280,
                    ),
                    layer=_fx.FX_LAYER,
                )

    def _draw_muzzle(
        self, r, tm, pos, yaw, pitch, age_ms, seed, big=True, scale_mul=1.0
    ):
        """Brief, narrow discharge extending from the muzzle.

        The player's basis comes directly from the same transform that
        renders the mounted gun. Enemy fallback uses +z at yaw zero,
        matching the scene's existing yaw convention.
        """
        dur = FLASH_MS if big else ENEMY_FLASH_MS
        if not 0 <= age_ms < dur:
            return

        phase = age_ms / float(dur)
        k = (1.0 - phase) ** 1.35

        flash_scale = getattr(_fx, "flash_scale", None)
        if callable(flash_scale):
            k *= max(0.0, flash_scale())

        if k <= 0.01:
            return

        if big:
            origin = self.gun_pt((0.0, 0.0, 0.0))
            forward_pt = self.gun_pt((0.0, 0.0, 1.0))
            right_pt = self.gun_pt((1.0, 0.0, 0.0))
            up_pt = self.gun_pt((0.0, 1.0, 0.0))

            f = _f_unit(
                tuple(
                    forward_pt[i] - origin[i]
                    for i in range(3)
                )
            )
            rx = _f_unit(
                tuple(
                    right_pt[i] - origin[i]
                    for i in range(3)
                )
            )
            ry = _f_unit(
                tuple(
                    up_pt[i] - origin[i]
                    for i in range(3)
                )
            )
        else:
            yr = math.radians(yaw)
            pr = math.radians(pitch)
            f = (
                math.sin(yr) * math.cos(pr),
                math.sin(pr),
                math.cos(yr) * math.cos(pr),
            )
            rx = (
                math.cos(yr),
                0.0,
                -math.sin(yr),
            )
            ry = _f_unit(_f_cross(f, rx))

        # Stable during a shot; varies between shots without gameplay RNG.
        size = 0.88 + 0.24 * _f_hash(seed, 201)
        size *= (1.0 if big else 0.7) * scale_mul

        _flash_submit(
            r,
            flash_star(pos, f, rx, ry, k, seed, size),
        )

        if not hasattr(_fx, "glow"):
            return

        # Small halo ahead of the opening. No oversized muzzle-centred disc.
        distance = FLASH_LEN * size * FLASH_BIAS
        centre = tuple(
            pos[i] + f[i] * distance
            for i in range(3)
        )
        r.add_sprite(
            centre,
            _fx.glow(
                (255, 174, 76),
                FLASH_BLOOM_R * size,
                tm,
                core=(255, 240, 198),
                intensity=FLASH_BLOOM_I * k,
                max_px=34,
            ),
            layer=_fx.FX_LAYER,
        )

    def _draw_fx(self, r, tm):
        self._draw_heli_fx(r, tm)
        for e in self.enemies:
            if (
                e["kind"] in ("jeep", "gun_truck")
                and not e["wrecked"]
            ):
                y, pitch, roll = self._enemy_pose(e)
                p = (e["x"], y, e["z"])
                lamp_z, lamp_y = (
                    (2.95, 1.05)
                    if e["kind"] == "gun_truck"
                    else (2.2, 0.72)
                )

                for sx in (-1.0, 1.0):
                    q = S._xf(
                        (sx * 0.62, lamp_y, lamp_z),
                        p,
                        e["yaw"],
                        pitch,
                        roll,
                    )
                    r.add_sprite(
                        q,
                        _fx.glow(
                            (255, 226, 170),
                            0.55,
                            tm,
                            core=(255, 248, 228),
                            intensity=0.95,
                        ),
                        layer=_fx.FX_LAYER,
                    )
                    r.add_sprite(
                        q,
                        _far_lamp((255, 244, 214), 1),
                        layer=_fx.FX_LAYER,
                    )

                if e["kind"] == "jeep":
                    blue = (
                        self.t * 2.6 + e["slot"] * 0.37
                    ) % 1.0 < 0.5
                    q = S._xf(
                        (-0.3 if blue else 0.3, 1.66, -0.1),
                        p,
                        e["yaw"],
                        pitch,
                        roll,
                    )
                    r.add_sprite(
                        q,
                        _fx.glow(
                            (70, 110, 255)
                            if blue
                            else (255, 50, 40),
                            0.5,
                            tm,
                            core=(
                                (190, 210, 255)
                                if blue
                                else (255, 170, 150)
                            ),
                            intensity=0.9,
                        ),
                        layer=_fx.FX_LAYER,
                    )
                    r.add_sprite(
                        q,
                        _far_lamp(
                            (60, 100, 255)
                            if blue
                            else (240, 40, 30),
                            2,
                        ),
                        layer=_fx.FX_LAYER,
                    )

            bt = e.get("boom_t")
            if bt is not None and self.t - bt < 0.8:
                age = int((self.t - bt) * 1000.0)
                c = (e["x"], e["wy"] + 1.0, e["z"])
                seed = e.get("fx_seed", e["slot"] + 11)
                r.add_sprite(
                    c,
                    _fx.flash(
                        age,
                        col=(255, 190, 110),
                        radius_m=3.2,
                        dur_ms=450,
                    ),
                    layer=_fx.FX_LAYER,
                )
                r.add_sprite(
                    c,
                    _fx.sparks(
                        seed,
                        age,
                        col=(255, 200, 130),
                        n=18,
                        speed_m=7.0,
                        dur_ms=800,
                    ),
                    layer=_fx.FX_LAYER,
                )

            if (
                e["wrecked"]
                and e["kind"] != "foot"
                and self.t - e["dead_t"]
                > e.get("burn_at", 0.2)
            ):
                f = clamp(
                    1.0 - (self.t - e["dead_t"] - 9.0) / 4.0,
                    0.0,
                    1.0,
                )
                if f > 0.0:
                    c = S._xf(
                        (0.0, 1.0, 1.0),
                        (e["x"], e["wy"], e["z"]),
                        e["yaw"],
                        e["wp"],
                        e["wr"],
                    )
                    r.add_sprite(
                        c,
                        _fx.glow(
                            (255, 132, 48),
                            0.75 * (0.5 + 0.5 * f),
                            tm,
                            flicker=0.8,
                            seed=e.get("fx_seed", e["slot"]),
                            core=(255, 220, 140),
                            intensity=1.1 * f,
                        ),
                        layer=_fx.FX_LAYER,
                    )

        for f in self.flashes:
            t0, pos, gyaw = f[0], f[1], f[2]
            gpitch = f[3] if len(f) > 3 else 0.0
            heavy = f[4] if len(f) > 4 else False
            age = self.t - t0
            if 0.0 <= age < ENEMY_FLASH_MS / 1000.0:
                self._draw_muzzle(
                    r,
                    tm,
                    pos,
                    gyaw,
                    gpitch,
                    int(age * 1000.0),
                    int(t0 * 1000),
                    big=False,
                    scale_mul=1.5 if heavy else 1.0,
                )
                fade_k = 1.0 - age / (ENEMY_FLASH_MS / 1000.0)
                r.add_sprite(
                    pos,
                    _fx.glow(
                        (255, 196, 108),
                        0.72 if heavy else 0.45,
                        tm,
                        core=(255, 248, 220),
                        intensity=(1.35 if heavy else 0.95) * fade_k,
                        max_px=30 if heavy else 20,
                    ),
                    layer=_fx.FX_LAYER,
                )

        self.flashes = [
            f for f in self.flashes
            if self.t - f[0] < 0.2
        ]
        self._draw_bullets(r, tm)
        self._draw_impacts(r, tm)

        for t0, pos in self.sparks:
            if self.t - t0 < 0.1:
                r.add_sprite(
                    pos,
                    _fx.glow(
                        (255, 230, 180),
                        0.22,
                        tm,
                        intensity=1.0,
                        max_px=18,
                    ),
                    layer=_fx.FX_LAYER,
                )

        if self.wreck_t is not None:
            (tx, ty, tz), tyaw = self.tractor_pos()
            el = self.t - self.wreck_t
            eng = _local(
                (tx, ty, tz), tyaw, (0.0, 1.7, 1.0)
            )

            if el < 0.6:
                r.add_sprite(
                    eng,
                    _fx.flash(
                        int(el * 1000.0),
                        col=(255, 190, 110),
                        radius_m=2.6,
                        dur_ms=600,
                    ),
                    layer=_fx.FX_LAYER,
                )
                r.add_sprite(
                    eng,
                    _fx.sparks(
                        7,
                        int(el * 1000.0),
                        col=(255, 200, 130),
                        n=14,
                        speed_m=5.0,
                        dur_ms=600,
                    ),
                    layer=_fx.FX_LAYER,
                )

            for i in range(4):
                c = _local(
                    (tx, ty, tz),
                    tyaw,
                    (
                        0.5 * (i - 1.5),
                        1.55 + 0.1 * (i % 2),
                        0.9 + 0.25 * (i % 2),
                    ),
                )
                r.add_sprite(
                    c,
                    _fx.glow(
                        (255, 132, 48),
                        0.42 + 0.1 * (i % 2),
                        tm,
                        flicker=0.7,
                        seed=30 + i,
                        core=(255, 220, 140),
                        intensity=1.2,
                    ),
                    layer=_fx.FX_LAYER,
                )

        if self.hull < 50.0:
            (tx, ty, tz), tyaw = self.tractor_pos()
            for i in range(3):
                a = (self.t * 0.9 + i / 3.0) % 1.0
                c = _local(
                    (tx, ty, tz),
                    tyaw,
                    (0.3, 2.9 + a * 2.2, 0.9 - a * 3.0),
                )
                r.add_sprite(
                    c,
                    _fx.glow(
                        (52, 50, 50),
                        0.5 + a * 0.9,
                        tm,
                        intensity=0.6 * (1.0 - a),
                    ),
                    layer=_fx.FX_LAYER,
                )

        if self.hull < 65.0 and self.wreck_t is None:
            (lx, ly, lz), lyaw = self.trailer_pos()
            lp = S.ditch_pitch(lz)
            for i in range(2):
                a = (self.t * 1.1 + i * 0.5) % 1.0
                c = S._xf(
                    (
                        S.RIG_PUMP_AT[0],
                        S.RIG_PUMP_AT[1] + 0.22 + a * 0.75,
                        S.RIG_PUMP_AT[2] - a * 1.0,
                    ),
                    (lx, ly, lz),
                    lyaw,
                    lp,
                )
                r.add_sprite(
                    c,
                    _fx.glow((64, 62, 60), 0.24 + a * 0.34, tm, intensity=0.52 * (1.0 - a)),
                    layer=_fx.FX_LAYER,
                )

    def _draw_smoke(self, r, tm):
        ex, ey, ez = self.camera()[0]

        for p in self.puffs:
            life, r0, r1, a0, _rise = PUFF[p[7]]
            k = p[0] / life
            near = clamp(
                (math.dist((ex, ey, ez), p[1:4]) - 2.5) / 4.0,
                0.0,
                1.0,
            )
            alpha = (
                int(
                    a0
                    * near
                    * min(1.0, k * 6.0)
                    * (1.0 - k) ** 1.3
                )
                // 12
                * 12
            )
            if alpha < 12:
                continue

            r.add_sprite(
                (p[1], p[2], p[3]),
                _puff_fn(
                    p[7],
                    r0 + (r1 - r0) * math.sqrt(k),
                    alpha,
                    p[8],
                ),
                layer=2,
            )

        if self.wreck_t is not None:
            (tx, ty, tz), tyaw = self.tractor_pos()
            for i in range(3):
                c = _local(
                    (tx, ty, tz),
                    tyaw,
                    (0.0, 2.2 + 1.3 * i, 0.9 - 0.8 * i),
                )
                r.add_sprite(
                    c,
                    S.W7.smoke(
                        tm,
                        seed=80 + i,
                        size_m=1.4 + 0.6 * i,
                    ),
                    layer=2,
                )

        for i, (wx, wz) in enumerate(S.wrecks()):
            if (
                i % 2 == 0
                and -40.0 < wz - self.z < 160.0
            ) or (
                i % 2
                and abs(wz - self.z) < 60.0
            ):
                r.add_sprite(
                    (wx, 1.2, wz),
                    S.W7.smoke(
                        tm,
                        seed=40 + i,
                        size_m=1.1 + 0.3 * (i % 3),
                    ),
                    layer=2,
                )

    # --- HUD ---------------------------------------------------------------

    def _hud(self, surface):
        cx, cy = WIDTH // 2, HEIGHT // 2

        if self.wreck_t is not None:
            self._capture_hud(surface)
            return

        if self.dying:
            k = clamp(self.death_t / 2.0, 0.0, 1.0)
            veil = pygame.Surface(
                (WIDTH, HEIGHT), pygame.SRCALPHA
            )
            veil.fill((0, 0, 0, int(255 * k)))
            surface.blit(veil, (0, 0))
            img = font_terminal.render(
                self.death_msg, True, (220, 200, 190)
            )
            surface.blit(
                img, img.get_rect(center=(cx, cy))
            )
            return

        if self.hurt > 0.02 and self.end_t is None:
            h_int = int(85 * clamp(self.hurt, 0.0, 1.0))
            if h_int > 2:
                surface.fill((int(h_int * 0.55), 0, 0), special_flags=pygame.BLEND_RGB_ADD)
                for k in range(4):
                    t_b = 14 * (4 - k)
                    v = int(h_int * (0.28 - k * 0.05))
                    if v > 0:
                        surface.fill((v, 0, 0), (0, 0, WIDTH, t_b), special_flags=pygame.BLEND_RGB_ADD)
                        surface.fill((v, 0, 0), (0, HEIGHT - t_b, WIDTH, t_b), special_flags=pygame.BLEND_RGB_ADD)
                        surface.fill((v, 0, 0), (0, 0, t_b, HEIGHT), special_flags=pygame.BLEND_RGB_ADD)
                        surface.fill((v, 0, 0), (WIDTH - t_b, 0, t_b, HEIGHT), special_flags=pygame.BLEND_RGB_ADD)

        if self.end_t is None:
            if self.ads < 0.55:
                U.reticle(
                    surface,
                    int(3 * self.kick * (1.0 - self.ads)),
                )

            H.crosshair(
                surface,
                0,
                lines=False,
                reload_frac=(
                    1.0 - self.reloading / RELOAD_S
                    if self.reloading
                    else 0.0
                ),
                hit_age=self.t - self.hit_mark,
            )
            H.damage_arcs(surface, self.dmg_marks, self.t, life=0.9)
            U.objective(surface, self.objective())
            U.hostiles(surface, self.alive_count())
            self._hull_bar(surface)

            if self.repair_t is not None:
                U.prompt(surface, "Repairing tractor...", None)
            elif self._looking_at_toolbox():
                if self.repairs <= 0:
                    U.prompt(surface, "Toolbox empty", None)
                elif self.hull >= HULL - 0.5:
                    U.prompt(surface, "Tractor hull full", None)
                else:
                    U.prompt(surface, "Repair tractor (%d left)" % self.repairs, "E")

            ammo = font_terminal.render(
                "LMG %d / %d" % (self.mag, MAG)
                if not self.reloading
                else "LMG RELOADING BELT",
                True,
                (220, 214, 196),
            )
            surface.blit(
                ammo,
                (WIDTH - ammo.get_width() - 30, HEIGHT - 50),
            )

            hint = font_terminal_small.render(
                "LMB FIRE   RMB AIM   R BELT",
                True,
                (150, 146, 132),
            )
            surface.blit(
                hint,
                (WIDTH - hint.get_width() - 30, HEIGHT - 30),
            )

            if self.timer is not None:
                col = (
                    (236, 90, 70)
                    if self.timer < 15.0
                    else (230, 220, 190)
                )
                img = font_terminal.render(
                    "TRAIN LEAVES 0:%02d"
                    % int(math.ceil(self.timer)),
                    True,
                    col,
                )
                surface.blit(
                    img,
                    (cx - img.get_width() // 2, 24),
                )

        live = [
            c for c in self.lines
            if self.t - c[0] < c[3]
        ][-2:]
        y = HEIGHT - 150

        for t0, who, text, dur in live:
            a = int(
                255
                * clamp(
                    min(
                        (dur - (self.t - t0)) / 0.4,
                        (self.t - t0) / 0.15 + 0.05,
                    ),
                    0.0,
                    1.0,
                )
            )
            H._text(
                surface,
                font_terminal_small,
                who + ":",
                SPEAKER.get(who, H.TEXT),
                (cx - 6, y),
                "topright",
                a,
            )
            H._text(
                surface,
                font_terminal_small,
                text,
                H.TEXT,
                (cx + 2, y),
                "topleft",
                a,
            )
            y += 20

        if (
            self.cp_toast > 0.0
            and 0.0 <= self.t - self.cp_toast < 2.6
        ):
            H._text(
                surface,
                font_terminal,
                "CHECKPOINT - " + SECTION_NAMES[self.cp],
                H.GOOD,
                (cx, 120),
                "midtop",
                int(
                    255
                    * min(
                        1.0,
                        (2.6 - (self.t - self.cp_toast)) / 0.6,
                    )
                ),
            )

        if self.heli_active():
            h = self.heli
            frac = clamp(h["hp"] / float(h["max_hp"]), 0.0, 1.0)
            bw, bh = 320, 10
            bx = cx - bw // 2
            by = 56
            pygame.draw.rect(surface, (18, 18, 20), (bx - 2, by - 2, bw + 4, bh + 4))
            pygame.draw.rect(surface, (150, 40, 34), (bx, by, int(bw * frac), bh))
            label = font_terminal_small.render("GUARD GUNSHIP", True, (226, 214, 200))
            surface.blit(label, (cx - label.get_width() // 2, by - 20))

        locking = self.heli is not None and self.heli["state"] == "rocket_lock"
        inbound = [rk for rk in self.rockets if not rk["done"] and not rk["dodged"]]
        dodged = any(rk["dodged"] and not rk["done"] for rk in self.rockets)
        if locking or inbound or dodged:
            if dodged and not inbound:
                msg, col = "DODGED!", H.GOOD
            elif inbound:
                msg = "[LMB] SHOOT MISSILE (%d/%d)   OR   [SPACE / A / D] DODGE!" % (inbound[0]["hp"], ROCKET_HP)
                col = (255, 130, 90)
            else:
                msg = "MISSILE LOCKING — READY TO SHOOT OR DODGE"
                col = (240, 170, 90)
            q = font_terminal.render(msg, True, col)
            surface.blit(q, (cx - q.get_width() // 2, cy - 110))
            if locking:
                left = clamp(
                    HELI_LOCK_S - (self.t - self.heli["lock_t"]),
                    0.0, HELI_LOCK_S,
                )
                pygame.draw.rect(
                    surface, (240, 170, 90),
                    (cx - 150, cy - 82, int(300 * left / HELI_LOCK_S), 6),
                )

        if self.fade > 0.0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * self.fade))
            surface.blit(veil, (0, 0))

    def _capture_hud(self, surface):
        el = self.t - self.wreck_t
        bar = int(
            HEIGHT
            * 0.11
            * clamp((el - 0.3) / 0.5, 0.0, 1.0)
        )

        if bar:
            pygame.draw.rect(
                surface,
                (0, 0, 0),
                (0, 0, WIDTH, bar),
            )
            pygame.draw.rect(
                surface,
                (0, 0, 0),
                (0, HEIGHT - bar, WIDTH, bar),
            )

        cx = WIDTH // 2
        y = HEIGHT - bar - 56

        live = [
            c for c in self.lines
            if self.t - c[0] < c[3]
        ][-2:]

        for t0, who, text, dur in live:
            a = int(
                255
                * clamp(
                    min(
                        (dur - (self.t - t0)) / 0.4,
                        (self.t - t0) / 0.15 + 0.05,
                    ),
                    0.0,
                    1.0,
                )
            )
            H._text(
                surface,
                font_terminal_small,
                who + ":",
                SPEAKER.get(who, H.TEXT),
                (cx - 6, y),
                "topright",
                a,
            )
            H._text(
                surface,
                font_terminal_small,
                text,
                H.TEXT,
                (cx + 2, y),
                "topleft",
                a,
            )
            y += 20

        fade = clamp((el - 7.2) / 1.2, 0.0, 1.0)
        if fade > 0.0:
            veil = pygame.Surface((WIDTH, HEIGHT))
            veil.fill((0, 0, 0))
            veil.set_alpha(int(255 * fade))
            surface.blit(veil, (0, 0))

        if el > 6.6:
            a = int(
                255 * clamp((el - 6.6) / 0.5, 0.0, 1.0)
            )
            H._text(
                surface,
                font_terminal,
                "CAPTURED",
                (220, 92, 76),
                (cx, HEIGHT // 2 - 26),
                "midtop",
                a,
            )
            H._text(
                surface,
                font_terminal_small,
                self.death_msg,
                (220, 200, 190),
                (cx, HEIGHT // 2 + 8),
                "midtop",
                a,
            )

    def objective(self):
        if self.cp == 3 and self.heli_active():
            return "Bring down the gunship. Shoot its gunner and guns!"
        if self.cp == 3:
            return "Reach the train."
        if self.cp == 4:
            return (
                "Clear the jeep off the tracks."
                if self.blocked()
                else "Reach the train."
            )
        return "Keep the jeeps off the tractor. Burst the tyres."

    def _hull_bar(self, surface):
        x, y, w, h = 30, HEIGHT - 58, 180, 10
        H._text(
            surface,
            font_terminal_small,
            "TRACTOR",
            H.TEXT,
            (x, y - 20),
            "topleft",
            230,
        )
        pygame.draw.rect(
            surface, (30, 30, 32), (x, y, w, h)
        )

        k = self.hull / HULL
        col = (
            (200, 70, 54)
            if k < 0.35
            else (214, 180, 96)
            if k < 0.6
            else (150, 190, 110)
        )
        pygame.draw.rect(
            surface, col, (x, y, int(w * k), h)
        )
        pygame.draw.rect(
            surface, (110, 118, 132), (x, y, w, h), 1
        )


_PULL = {"sc": None, "n": 0}


def pullout_scene(s):
    """Deterministic pullout simulation shared with the descent film."""
    n = int(round(clamp(s, 0.0, PULL_S) / PULL_DT))

    if _PULL["sc"] is None or n < _PULL["n"]:
        sc = _PULL["sc"] = ChaseScene()
        sc.z, sc.speed, sc.odo = PULL_Z0, 0.0, 0.0
        sc.spawn_i, sc.enemies = 0, []
        _PULL["n"] = 0

    sc = _PULL["sc"]
    while _PULL["n"] < n:
        _PULL["n"] += 1
        sc.t = sc.sec_t = _PULL["n"] * PULL_DT
        sc._drive(PULL_DT)
        sc._spawns()
        sc._enemy_move(PULL_DT)

    return sc


_SCENE = None


def scene():
    global _SCENE
    if _SCENE is None:
        _SCENE = ChaseScene()
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
    """Drop the scene without finishing: restart or quit to menu."""
    if _SCENE is not None and _SCENE.active():
        _SCENE._active = False
        _SCENE.paused = False
        STATE.m8_chase_active = False
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
