"""Mission 8 Revenge — GTA IV-style trigger-hijack assassination choreography.

Owns the post-trigger multi-angle cuts, branch timelines (chest, groin,
headshot, Bodi hesitation), Biribel's Fallow 12 pump-rack + walk-up, Vasile's
branch-specific collapse performance, and Bodi's gantry-foot cameo.

All branches end on the shot name ``"witness"`` (wide Route 12 gantry
silhouette) so the scene closes on cold dawn wind and matches the smoke-test
contract without scene switches or renderer reloads.
"""

import math

from core.outfits import OUTFIT_GUARD
from cutscenes import m6world3d as _w
from engine.anim import gait_cycle_m, locomotion_pose, mask_pose
from engine3d import POSES, blend, clamp
from engine3d.hold import hold_cached as _hold_cached
from missions.m7 import raid3d as R

from . import set3d as S3

VX, VY, VZ = S3.VASILE_AT
CY, CZ = S3.CATWALK_Y, S3.CATWALK_Z
BX, BZ, BYAW = 6.2, S3.CATWALK_Z, 270.0
WALK_END_X = 5.05

# Bodi down on the Route 12 apron, aiming straight up between the gantry signs.
BODI_POS = (4.3, 0.0, 46.8)
BODI_YAW = -4.0
BODI_SLOPE = 0.42

# Branch timings (performance seconds after death_t).
KNEE_AT = 0.68
WALK_START = 2.08
WALK_END = 3.22
PUMP_START = 1.92
FINISHER_AT = {"chest": 4.05, "nutshot": 4.25, "headshot": None, "bodi": None}
GROUND_AT = {"chest": 4.82, "nutshot": 5.02, "headshot": 1.15, "bodi": 3.06}
DEATH_S = {"chest": 6.20, "nutshot": 6.45, "headshot": 4.40, "bodi": 5.40}

# Ordered (shot_name, end_age) cuts per branch; last cut is always "witness".
SCHEDULES = {
    "chest": (
        ("impact", 0.58),
        ("grate", 1.85),
        ("walkup", 3.45),
        ("finisher", 4.35),
        ("witness", 99.0),
    ),
    "nutshot": (
        ("impact", 0.58),
        ("grate", 2.15),
        ("walkup", 3.65),
        ("finisher", 4.55),
        ("witness", 99.0),
    ),
    "headshot": (
        ("impact", 0.55),
        ("grate", 1.55),
        ("witness", 99.0),
    ),
    "bodi": (
        ("bodi", 1.25),
        ("grate", 2.75),
        ("witness", 99.0),
    ),
}

_KNEEL = dict(
    POSES["kneel"],
    spine=18.0, head_p=-10.0, head_y=-4.0,
    lsh_p=-24.0, lsh_r=-5.0, lel=76.0,
    rsh_p=-12.0, rsh_r=8.0, rel=28.0,
)
_GROUND = dict(
    POSES["dead_back"],
    body_r=0.0, spine=0.0, twist=0.0,
    head_p=0.0, head_y=-8.0,
    lhip_p=0.0, lhip_r=0.0, lkn=0.0,
    rhip_p=0.0, rhip_r=0.0, rkn=0.0,
    lsh_p=0.0, lsh_r=-6.0, lel=12.0,
    rsh_p=0.0, rsh_r=9.0, rel=5.0,
)

_LIMB_LAG = {
    "head_p": 0.055, "head_y": 0.07,
    "lsh_p": 0.08, "lsh_r": 0.06, "lel": 0.10,
    "rsh_p": 0.12, "rsh_r": 0.08, "rel": 0.14,
}


def _ease(k):
    k = clamp(k, 0.0, 1.0)
    return k * k * (3.0 - 2.0 * k)


def _point(a, b, k):
    return (
        a[0] + (b[0] - a[0]) * k,
        a[1] + (b[1] - a[1]) * k,
        a[2] + (b[2] - a[2]) * k,
    )


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _mix(a, b, k):
    keys = set(a) | set(b)
    return {n: a.get(n, 0.0) + (b.get(n, 0.0) - a.get(n, 0.0)) * k for n in keys}


def _full(p):
    return blend(POSES["stand"], p, 1.0)


def _settle(age, start, duration, strength, frequency=11.0):
    t = age - start
    if t <= 0.0 or t >= duration:
        return 0.0
    env = math.exp(-5.0 * t) * (1.0 - _ease(t / duration))
    return strength * math.sin(frequency * t) * env


def _build_tracks():
    stand = _full({})
    rock = _full(dict(
        spine=-10.0, head_p=-12.0, twist=-10.0,
        lsh_p=8.0, lsh_r=-8.0, lel=24.0,
        rsh_p=-34.0, rsh_r=12.0, rel=42.0,
    ))
    fold = _full(dict(
        spine=16.0, head_p=3.0, twist=-6.0,
        lsh_p=-18.0, lsh_r=-8.0, lel=66.0,
        rsh_p=-28.0, rsh_r=10.0, rel=32.0,
    ))
    knee_hit = _full(dict(_KNEEL, spine=27.0, head_p=6.0, rel=18.0))
    kneel_look = _full(dict(_KNEEL, spine=16.0, head_p=-16.0, head_y=-3.0))
    kneel_wait = _full(dict(_KNEEL, spine=20.0, head_p=-18.0, head_y=-2.0, lel=68.0, rel=22.0))
    fin_snap = _full(dict(
        _KNEEL, spine=-22.0, head_p=-34.0, twist=-10.0,
        lsh_p=-14.0, lsh_r=14.0, lel=34.0,
        rsh_p=-20.0, rsh_r=16.0, rel=24.0,
    ))
    head_snap = _full(dict(
        spine=-20.0, head_p=-36.0, twist=-12.0,
        lsh_p=-10.0, lsh_r=14.0, lel=28.0,
        rsh_p=-22.0, rsh_r=16.0, rel=32.0,
    ))
    ground = _full(_GROUND)

    def _two_stage(fin_t, gnd_t, end_t):
        return (
            (0.00, stand, 0.0, 90.0, 1.80, "ease"),
            (0.10, rock, 0.0, 94.0, 1.80, "ease"),
            (0.24, fold, 0.0, 94.0, 1.72, "ease"),
            (KNEE_AT, knee_hit, -0.03, 92.0, 1.15, "fall"),
            (0.95, kneel_look, -0.03, 92.0, 1.18, "ease"),
            (fin_t, kneel_wait, -0.03, 91.0, 1.16, "ease"),
            (fin_t + 0.16, fin_snap, -0.03, 93.0, 1.05, "ease"),
            (gnd_t, ground, -0.03, 90.0, 0.42, "fall"),
            (end_t, ground, -0.03, 90.0, 0.42, "ease"),
        )

    return {
        "chest": _two_stage(FINISHER_AT["chest"], GROUND_AT["chest"], DEATH_S["chest"]),
        "nutshot": _two_stage(FINISHER_AT["nutshot"], GROUND_AT["nutshot"], DEATH_S["nutshot"]),
        "headshot": (
            (0.00, stand, 0.0, 90.0, 1.80, "ease"),
            (0.12, head_snap, 0.0, 95.0, 1.76, "ease"),
            (0.55, knee_hit, -0.02, 92.0, 1.10, "fall"),
            (GROUND_AT["headshot"], ground, -0.03, 90.0, 0.42, "fall"),
            (DEATH_S["headshot"], ground, -0.03, 90.0, 0.42, "ease"),
        ),
        "bodi": (
            (0.00, stand, 0.0, 90.0, 1.80, "ease"),
            (0.10, rock, 0.0, 96.0, 1.80, "ease"),
            (0.24, fold, 0.0, 94.0, 1.72, "ease"),
            (KNEE_AT, knee_hit, -0.03, 92.0, 1.15, "fall"),
            (0.95, _full(_KNEEL), -0.03, 92.0, 1.18, "ease"),
            (2.50, _full(dict(_KNEEL, spine=23.0, head_p=-3.0, lel=65.0, rel=20.0)),
             -0.03, 92.0, 1.12, "ease"),
            (GROUND_AT["bodi"], ground, -0.03, 90.0, 0.42, "fall"),
            (DEATH_S["bodi"], ground, -0.03, 90.0, 0.42, "ease"),
        ),
    }


TRACKS = _build_tracks()


def _sample_track(track, age):
    if age <= track[0][0]:
        return track[0][1:5]
    for a, b in zip(track, track[1:]):
        if age <= b[0]:
            k = clamp((age - a[0]) / max(1e-6, b[0] - a[0]), 0.0, 1.0)
            k = k * k if b[5] == "fall" else _ease(k)
            return (
                _mix(a[1], b[1], k),
                a[2] + (b[2] - a[2]) * k,
                a[3] + _wrap(b[3] - a[3]) * k,
                a[4] + (b[4] - a[4]) * k,
            )
    return track[-1][1:5]


def warm():
    """Prewarm shotgun nopump holds and Bodi's upward OS-12 aim behind the cut."""
    hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
    for mode in ("ready", "aim"):
        R._sg_holds(hum, mode, ("m7player_sg", mode))
    bhum = _w.hum(("ally", "bodi"), flags=("os12",))
    _bodi_poses(bhum)


def _bodi_poses(bhum):
    ready = _hold_cached(bhum, dict(POSES["ready"]), "os12", "ready",
                         key=("m8_bodi_os12", "ready"))
    aim_st = dict(
        blend(POSES["stand"], "aim", 0.85),
        twist=R.AIM_TWIST, head_y=-0.8 * R.AIM_TWIST,
    )
    aim_base = _hold_cached(
        bhum, aim_st, "os12", "aim",
        aim=(0.0, 1.45 + 10.0 * BODI_SLOPE, 10.0),
        key=("m8_bodi_os12", "up_kill"),
    )
    aim_up = dict(aim_base)
    d_sp = -14.0 - aim_base.get("spine", 0.0)
    aim_up["spine"] = -14.0
    aim_up["head_p"] = -18.0
    aim_up["rifle_p"] = aim_base.get("rifle_p", 0.0) + d_sp
    return ready, aim_up


def shot_at(mode, age):
    """(shot_name, local_age, duration) for ``mode`` at ``age`` seconds."""
    sched = SCHEDULES.get(mode, SCHEDULES["chest"])
    prev = 0.0
    for name, end in sched:
        if age < end:
            return name, max(0.0, age - prev), max(0.01, end - prev)
        prev = end
    name, end = sched[-1]
    return name, max(0.0, age - prev), 1.0


def time_scale(mode, age):
    """Brief micro-slowmo ramp on shot impacts; 1.0 everywhere else."""
    if 0.0 <= age < 0.30:
        return 0.44 + 0.56 * _ease(age / 0.30)
    fin_t = FINISHER_AT.get(mode)
    if fin_t is not None and fin_t <= age < fin_t + 0.30:
        return 0.42 + 0.58 * _ease((age - fin_t) / 0.30)
    return 1.0


def _reduced_motion():
    try:
        from core.user_settings import SETTINGS
        return bool(getattr(SETTINGS, "reduced_motion", False))
    except Exception:
        return False


def _drift(age, seed, amp=0.014):
    if _reduced_motion():
        return (0.0, 0.0, 0.0)
    return (
        math.sin(age * 1.4 + seed) * amp,
        math.cos(age * 1.9 + seed * 1.7) * amp * 0.7,
        math.sin(age * 1.1 + seed * 2.3) * amp * 0.6,
    )


def vasile_performance(mode, age, hits=1, hit_t=0.0, t_now=0.0):
    """Branch-aware Vasile collapse pose, Z offset, yaw, and hit height."""
    track = TRACKS.get(mode, TRACKS["chest"])
    end_s = DEATH_S.get(mode, DEATH_S["chest"])
    if age >= end_s:
        return track[-1][1:5]
    base, dz, yaw, height = _sample_track(track, age)
    pose = dict(base)
    for joint, lag in _LIMB_LAG.items():
        delayed, _, _, _ = _sample_track(track, max(0.0, age - lag))
        pose[joint] = delayed.get(joint, 0.0)
    gnd_t = GROUND_AT.get(mode, GROUND_AT["chest"])
    if mode != "headshot":
        pose["head_p"] += _settle(age, KNEE_AT, 0.50, 12.0)
        pose["spine"] += _settle(age, KNEE_AT, 0.42, 6.0)
    settle_dur = max(0.45, min(1.05, end_s - gnd_t))
    pose["head_p"] += _settle(age, gnd_t + 0.04, settle_dur - 0.04, -8.0)
    pose["lel"] += _settle(age, gnd_t + 0.09, settle_dur - 0.09, 20.0, 12.0)
    pose["rel"] += _settle(age, gnd_t + 0.14, settle_dur - 0.14, 28.0, 10.0)
    if mode == "nutshot":
        fin_t = FINISHER_AT["nutshot"]
        if age < fin_t:
            clutch_k = _ease(age / 0.35) * (1.0 - _ease((age - (fin_t - 0.25)) / 0.25))
            clutch = dict(
                pose,
                spine=pose["spine"] + 16.0,
                head_p=pose["head_p"] + 12.0,
                lsh_p=32.0, lsh_r=2.0, lsh_y=35.0, lel=72.0,
                rsh_p=32.0, rsh_r=2.0, rsh_y=-35.0, rel=72.0,
            )
            pose = _mix(pose, clutch, clutch_k)
    return pose, dz, yaw, height


def vasile_face(mode, age):
    end_s = DEATH_S.get(mode, DEATH_S["chest"])
    if age >= end_s:
        return "neutral"
    if mode == "headshot":
        return "surprised" if age < 0.45 else "neutral"
    if mode == "nutshot":
        if age < 0.70:
            return "surprised"
        if age < FINISHER_AT["nutshot"]:
            return "angry"
        return "neutral" if age >= GROUND_AT["nutshot"] else "worried"
    fin_t = FINISHER_AT.get(mode)
    if age < 0.80:
        return "surprised"
    if fin_t is not None and age < fin_t:
        return "sad" if age > 1.8 else "worried"
    if age >= GROUND_AT.get(mode, 3.06):
        return "neutral"
    return "worried"


def vasile_head_world(pose, dz, yaw, wound=1, flags=("cig_dropped",)):
    """World-space head joint of Vasile so close-ups never crop his face."""
    try:
        hum = _w.hum("vasile", hd=True, wound=wound, bloody=True, flags=flags)
        _, joints, _ = hum.pose_world(pose, (VX, VY, VZ + dz), yaw, rifle_on=False)
        h = joints.get("head")
        if h is not None:
            return h
    except Exception:
        pass
    return (VX, VY + 1.24, VZ + dz)


def biribel_state(mode, age, base_yaw, yaw_off, fire_age):
    """Return ``(pos, yaw, pose, pump_k, use_nopump)`` for Biribel post-trigger."""
    hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
    fin_t = FINISHER_AT.get(mode)
    walk_shift = 0.20 if mode == "nutshot" else 0.0
    w0, w1 = WALK_START + walk_shift, WALK_END + walk_shift
    p0 = PUMP_START + walk_shift

    # Walk-up progress (chest / groin branches only).
    if fin_t is not None:
        walk_u = _ease((age - w0) / max(0.05, w1 - w0))
        bx = BX + (WALK_END_X - BX) * walk_u
        bz = BZ + (VZ + 0.08 - BZ) * walk_u
        moving = w0 < age < w1
        down_k = _ease((age - (w0 + 0.25)) / 0.85) * (1.0 - _ease((age - (fin_t + 0.65)) / 0.80))
        lower_k = _ease((age - (fin_t + 0.85)) / 0.85)
        pump_k = R._pump_k(age - p0)
    else:
        bx, bz = BX, BZ
        moving = False
        down_k = 0.0
        lower_k = _ease((age - (1.85 if mode == "headshot" else 2.80)) / 0.90)
        pump_k = 0.0

    # Aim-down lean via spine keeps the IK left hand locked onto the wooden pump.
    base = dict(POSES["ready"])
    if moving:
        dist = abs(bx - BX)
        spd = abs(WALK_END_X - BX) / max(0.1, w1 - w0)
        phase = dist / gait_cycle_m(spd) * math.tau
        lower = locomotion_pose(spd, 0.0, phase)
        base = mask_pose(lower, base)
        base["spine_r"] = lower.get("spine_r", 0.0) * 0.7
    recoil = max(0.0, 1.0 - fire_age / 0.24) if 0.0 <= fire_age < 0.24 else 0.0
    base["spine"] = base.get("spine", 6.0) + 14.0 * down_k - 7.0 * recoil
    base["head_p"] = base.get("head_p", 0.0) + 10.0 * down_k

    aim_pose = R._shotgun_hold(hum, base, "aim", ("m7player_sg", "aim"), pump_k)
    ready_pose = R._shotgun_hold(hum, base, "ready", ("m7player_sg", "ready"), pump_k)
    if mode == "bodi":
        pose = _mix(aim_pose, ready_pose, lower_k)
    else:
        pose = _mix(aim_pose, ready_pose, lower_k)
    if recoil > 0.0:
        pose["rifle_p"] = pose.get("rifle_p", 0.0) - 9.0 * recoil

    # Aim yaw eases from player's trigger angle straight onto Vasile during walk-up.
    aim_yaw = BYAW + _wrap(base_yaw + yaw_off - BYAW) * (1.0 - lower_k)
    if fin_t is not None:
        aim_yaw = aim_yaw + _wrap(BYAW - aim_yaw) * _ease((age - 0.50) / 0.60)
    return (bx, VY, bz), aim_yaw, pose, pump_k, True


def bodi_state(age):
    """Bodi at the gantry foot: upward OS-12 aim on frame 0, lowering after 0.55 s."""
    bhum = _w.hum(("ally", "bodi"), flags=("os12",))
    ready, aim_up = _bodi_poses(bhum)
    lower_k = _ease((age - 0.55) / 0.65)
    recoil = max(0.0, 1.0 - age / 0.18) if 0.0 <= age < 0.18 else 0.0
    pose = _mix(aim_up, ready, lower_k)
    if recoil > 0.0:
        pose["spine"] = pose.get("spine", 0.0) - 5.0 * recoil
        pose["rifle_p"] = pose.get("rifle_p", 0.0) - 7.0 * recoil
    return BODI_POS, BODI_YAW, pose


def camera(mode, age, head_w=None):
    """Return ``(eye, tgt, fov)`` for the active assassination cut."""
    shot, local, dur = shot_at(mode, age)
    u = _ease(local / dur)

    if shot == "impact":
        # Wide enough side-3/4 south of the catwalk to frame both silhouettes
        # cleanly above the handrail against the lit dusk skyline.
        eye = _point((4.95, CY + 1.54, CZ - 4.35), (4.85, CY + 1.52, CZ - 4.00), u)
        tgt = _point((4.88, CY + 1.24, CZ), (4.78, CY + 1.22, CZ), u)
        fov = 52.0 - 3.0 * u
        dr = _drift(age, 1.1, 0.012)
    elif shot == "bodi":
        # Diagonal low-wide from the apron: Bodi's full upper body and upward
        # OS-12 sit in the lower-left third while Vasile staggers cleanly
        # between the two gantry highway signs in the upper-center.
        eye = _point((6.45, 1.48, 42.4), (6.20, 1.54, 43.0), u)
        tgt = _point((4.10, 3.25, 51.0), (4.05, 3.35, 51.2), u)
        fov = 56.0 - 3.0 * u
        dr = _drift(age, 2.3, 0.014)
    elif shot == "grate":
        # Inside the south rail at deck height, clear of railings and Biribel:
        # tracks Vasile's live head joint so his eyes and headroom stay clear
        # of the top letterbox bar while his knees hit steel below.
        hx, hy, hz = head_w if head_w is not None else (VX, CY + 1.32, VZ - 0.03)
        ty = max(CY + 0.35, hy - 0.14)
        eye = _point((5.72, CY + 0.86, CZ - 0.58), (5.60, CY + 0.88, CZ - 0.55), u)
        tgt = (hx, ty, hz)
        fov = 56.0 - 4.0 * u
        dr = _drift(age, 3.7, 0.010)
    elif shot == "walkup":
        # Clean south-side 3/4 tracking shot above the handrail: opens on
        # Biribel racking the Fallow 12 pump unobstructed, then tracks left
        # with him into a two-shot looming over kneeling Vasile.
        eye = _point((4.45, CY + 1.44, CZ - 3.00), (4.15, CY + 1.46, CZ - 2.75), u)
        tgt = _point((5.45, CY + 1.36, CZ), (4.45, CY + 1.22, CZ), u)
        fov = 48.0 - 2.0 * u
        dr = _drift(age, 5.1, 0.012)
    elif shot == "finisher":
        # Tight high-angle close-up locked to Vasile's live head joint, barrel
        # angling into the right edge right before the point-blank blast.
        hx, hy, hz = head_w if head_w is not None else (VX, CY + 1.24, VZ - 0.03)
        eye = _point((hx + 1.42, hy + 0.24, hz - 0.56), (hx + 1.28, hy + 0.20, hz - 0.50), u)
        tgt = (hx + 0.08, hy - 0.08, hz)
        fov = 46.0 - 3.0 * u
        dr = _drift(age, 6.4, 0.008)
    else:
        # "witness": stark wide gantry silhouette from the Route 12 apron,
        # slowly pulling back as Vasile lies flat and wind takes over.
        wu = _ease(min(1.0, local / 5.2))
        eye = _point((2.40, 2.75, 43.8), (1.60, 2.55, 40.8), wu)
        tgt = _point((4.45, CY + 0.35, CZ), (4.40, CY + 0.28, CZ), wu)
        fov = 46.0 - 2.0 * wu
        dr = _drift(age, 8.2, 0.006)

    return (eye[0] + dr[0], eye[1] + dr[1], eye[2] + dr[2]), tgt, fov
