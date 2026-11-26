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
from cutscenes import revive3d as REV
from cutscenes import m7world3d as F
from engine3d import Mesh, POSES, blend, box, clamp, pose_run
from engine3d.core import m_apply, m_mul, rot_x, rot_y, rot_z
from engine.anim import LayeredAnimState, gait_cycle_m, locomotion_pose, mask_pose
from engine.collision import DebrisPool
from engine3d.hold import (POLES, hold_cached as _hold_cached, hold_frame as _hold_frame,
                           solve_arm_safe as _solve_arm_safe)
from engine3d.ik import solve_leg as _solve_leg
from engine3d.rig import (rifle_mesh as _rifle_mesh,
                          shotgun_mesh as _shotgun_mesh,
                          shotgun_pump_mesh as _shotgun_pump_mesh)

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
SG_RELOAD_PREP = 0.16
SG_RELOAD_SHELL = 0.44
SG_RELOAD_PUMP = 0.46
SG_RELOAD_READY = 0.18
SHELL_AT = (0.35, 1.0, 1.65)
HP_REGEN_DELAY, HP_REGEN = 5.0, 7.0
LOOT_R = 1.5
HOLD_S = {"alex": 1.6, "bodi": 2.4}
WELL_CREAK_S = 0.95                     # warning creak & slip before the post shears
KNOCK_S = 0.26                          # fallback knock blend if beam hits fast
LIFT_LOW = dict(POSES["crouch"], spine=46, head_p=-24, lhip_p=72, lkn=92, lank=12,
                rhip_p=66, rkn=86, rank=10, lsh_p=58, lsh_r=12, lel=24,
                rsh_p=58, rsh_r=12, rel=24)
LIFT_HIGH = dict(POSES["stand"], spine=14, head_p=-16, lhip_p=20, lkn=24, lank=4,
                 rhip_p=14, rkn=18, rank=2, lsh_p=112, lsh_r=12, lel=34,
                 rsh_p=112, rsh_r=12, rel=34)
LIFT_SHOVE = dict(POSES["stand"], spine=6, head_p=-12, lhip_p=12, lkn=14,
                  rhip_p=8, rkn=10, lsh_p=124, lsh_r=16, lel=18,
                  rsh_p=124, rsh_r=16, rel=18)
ALEX_BRACE = dict(POSES["crouch"], spine=44, head_p=-28, head_y=-14,
                  lsh_p=132, lsh_r=28, lel=86, rsh_p=126, rsh_r=26, rel=82)
ALEX_GRAB = dict(POSES["kneel"], spine=26, twist=24, head_y=26, head_p=24,
                 lsh_p=24, lel=34, rsh_p=56, rsh_r=26, rel=22)
LIFT_YAW = 354.0                        # Biribel faces north-slightly-west across the beam
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


_GROUND_SG_MESH = None
_ALEX_GUN_MESH = None


def _motion_prefs():
    try:
        from core.user_settings import SETTINGS
        red = bool(getattr(SETTINGS, "reduced_motion", False))
        shk = float(getattr(SETTINGS, "shake_scale", 100.0)) / 100.0
        return red, clamp(shk, 0.0, 1.5)
    except Exception:
        return False, 1.0


def _alex_gun_mesh():
    global _ALEX_GUN_MESH
    if _ALEX_GUN_MESH is None:
        try:
            from game.render3d_bridge import load_mesh_asset
            verts, faces = load_mesh_asset("m7rifle")
            m = Mesh()
            m.verts = [tuple(v) for v in verts]
            m.faces = [(tuple(f[0]), tuple(f[1]), 2, True, False) for f in faces]
            _ALEX_GUN_MESH = m
        except Exception:
            _ALEX_GUN_MESH = _rifle_mesh()
    return _ALEX_GUN_MESH


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
    out["rifle_y"] = arms.get("rifle_y", 0.0) + pose.get("twist", 0.0) - ref.get("twist", 0.0)
    return out


# Fallow 12 hold: the same engine hold as the OS-12 (hold_cached, square body,
# draw_yaw = body_yaw), then the left hand is re-solved onto the rear of the
# wooden pump.  Square-on the 0.61 m arm reaches ~0.25 m up the gun, so the pump
# rests back at PUMP_REST_Z and racks a short 4.5 cm onto the receiver face.  The
# pump is a separate mesh that slides with the hand (draw_shotgun_pump).
_L_ARM = ("lsh_p", "lsh_r", "lsh_y", "lel")
_SG_HOLD_CACHE = {}
_WALL_HOLD_CACHE = {}
_PUMP_MESH = None
SG_BLADE_YAW, SG_TWIST = 0.0, 0.0
SG_HEAD_Y = -(SG_BLADE_YAW + SG_TWIST)
PUMP_GRIP = -0.075                         # hand target 1.5 cm onto the rear of the wood
PUMP_DELAY, PUMP_DUR = 0.12, 0.32
PUMP_REST_Z, PUMP_BACK_Z = 0.320, 0.275    # 4.5 cm stroke: forward on the wood -> receiver face


def _pump_k(age):
    """0..1 crisp rack stroke after recoil settles (pull back, brief stop,
    slam forward).  Zero outside the stroke window."""
    if age < PUMP_DELAY or age >= PUMP_DELAY + PUMP_DUR:
        return 0.0
    u = (age - PUMP_DELAY) / PUMP_DUR
    if u < 0.42:
        return _ease(u / 0.42)
    if u < 0.56:
        return 1.0
    return 1.0 - _ease((u - 0.56) / 0.44)


def _sg_holds(hum, mode, key):
    """Cached shotgun hold -> (rest pose, racked left arm, ref spine)."""
    ck = (key, mode)
    pair = _SG_HOLD_CACHE.get(ck)
    if pair is None:
        ref = POSES["ready"]
        base = dict(ref, **_hold_cached(hum, ref, "shotgun", mode, key=key))
        _pl, j, _root = hum.pose_world(base, (0.0, 0.0, 0.0), 0.0, rifle_on=True)
        rh, rm = j["rhand"], j["rifle_m"]
        sols = []
        for pz in (PUMP_REST_Z, PUMP_BACK_Z):
            off = m_apply(rm, (0.0, 0.025, pz + PUMP_GRIP))
            tgt = (rh[0] + off[0], rh[1] + off[1], rh[2] + off[2])
            sols.append(_solve_arm_safe(hum, base, (0.0, 0.0, 0.0), 0.0, "l", tgt,
                                        ((0.4, -1.0, 0.0),) + POLES))
        pair = (sols[0], {k: sols[1].get(k, sols[0].get(k, 0.0)) for k in _L_ARM}, ref["spine"])
        _SG_HOLD_CACHE[ck] = pair
    return pair


def _wall_down_hold(hum, weapon, key):
    """Cached compressed downward hold when pressed against walls or props."""
    ck = (weapon, key)
    cached = _WALL_HOLD_CACHE.get(ck)
    if cached is not None:
        return cached
    if weapon == "shotgun":
        ref = dict(
            POSES["ready"], spine=6.0, twist=-8.0,
            head_y=-(SG_BLADE_YAW - 8.0), head_p=6.0,
        )
        grip_local = (0.11, 0.29, 0.22)
        barrel_local = (-0.68, -0.68, 0.18)
        fore_pt = (0.0, 0.025, PUMP_REST_Z + PUMP_GRIP)
        poles_l = ((0.4, -1.0, 0.0),) + POLES
    else:
        ref = dict(
            POSES["ready"], spine=6.0, twist=-10.0,
            head_y=10.0, head_p=6.0,
        )
        grip_local = (0.12, 0.28, 0.22)
        barrel_local = (-0.56, -0.72, 0.38)
        fore_pt = (0.0, -0.025, 0.26)
        poles_l = ((0.5, -1.0, 0.1),) + POLES
    sc = getattr(hum, "_scale", 1.0) or 1.0
    S = m_mul(rot_y(ref["twist"]), rot_x(ref["spine"]))
    root = hum.pose_world(ref, (0.0, 0.0, 0.0), 0.0, rifle_on=False)[2]
    g_off = m_apply(S, tuple(c * sc for c in grip_local))
    grip_tgt = (root[0] + g_off[0], root[1] + g_off[1], root[2] + g_off[2])
    ad = _f_unit(m_apply(S, barrel_local))
    ref["rifle_p"] = math.degrees(math.asin(clamp(-ad[1], -1.0, 1.0)))
    ref["rifle_y"] = math.degrees(math.atan2(ad[0], ad[2]))
    ref = _solve_arm_safe(hum, ref, (0.0, 0.0, 0.0), 0.0, "r", grip_tgt, ((0.8, -1.0, -0.1),) + POLES)
    _pl, joints, _root = hum.pose_world(ref, (0.0, 0.0, 0.0), 0.0, rifle_on=True)
    hand, rm = joints.get("rhand"), joints.get("rifle_m")
    if hand is not None and rm is not None:
        off = m_apply(rm, fore_pt)
        tgt = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
        ref = _solve_arm_safe(hum, ref, (0.0, 0.0, 0.0), 0.0, "l", tgt, poles_l)
    _WALL_HOLD_CACHE[ck] = ref
    return ref


def apply_wall_down(hum, pose, weapon, wall_k, key):
    """Blend the held weapon down across the body as ``wall_k`` approaches 1."""
    k = clamp(float(wall_k), 0.0, 1.0)
    if k <= 1e-3:
        return pose
    wd = _wall_down_hold(hum, weapon, key)
    out = dict(pose)
    for kn in _ARMS:
        va = out.get(kn, 0.0)
        vb = wd.get(kn, va)
        if kn in ("rifle_y", "lsh_y", "rsh_y"):
            out[kn] = va + _wrap(vb - va) * k
        else:
            out[kn] = va + (vb - va) * k
    out["spine"] = out.get("spine", 0.0) + (wd["spine"] - out.get("spine", 0.0)) * k
    d_tw = (wd["twist"] - (SG_TWIST if weapon == "shotgun" else 0.0)) * k
    out["twist"] = out.get("twist", 0.0) + d_tw
    out["head_y"] = out.get("head_y", 0.0) - d_tw
    return out


def _shotgun_hold(hum, pose, mode, key, pump_k=0.0):
    """``pose`` with the shotgun hold and the rack blended in."""
    rest, back, ref_spine = _sg_holds(hum, mode, key)
    out = dict(pose)
    out.update((k, rest[k]) for k in _ARMS if k in rest)
    out["twist"] = out.get("twist", 0.0) + SG_TWIST
    out["head_y"] = out.get("head_y", 0.0) + SG_HEAD_Y
    out["rifle_p"] = rest.get("rifle_p", 0.0) + pose.get("spine", 0.0) - ref_spine
    out["rifle_y"] = rest.get("rifle_y", 0.0) + (out["twist"] - SG_TWIST)
    if pump_k > 0.0:
        for k in _L_ARM:
            cur = out.get(k, 0.0)
            out[k] = cur + _wrap(back[k] - cur) * pump_k
    return out


def draw_shotgun_pump(r, hand, rm, pump_k=0.0):
    """Draw the Fallow 12's sliding wooden fore-end in sync with the left hand."""
    global _PUMP_MESH
    if hand is None or rm is None:
        return
    if _PUMP_MESH is None:
        _PUMP_MESH = _shotgun_pump_mesh()
    pz = PUMP_REST_Z + (PUMP_BACK_Z - PUMP_REST_Z) * pump_k
    verts = [tuple(a + b for a, b in zip(m_apply(rm, (v[0], v[1], v[2] + pz)), hand))
             for v in _PUMP_MESH.verts]
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in _PUMP_MESH.faces]
    r.add_dynamic(verts, faces)


def _f_hash(seed, n):
    """Stable per-shot variation without consuming gameplay RNG."""
    x = math.sin(seed * 127.1 + n * 311.7) * 43758.5453
    return x - math.floor(x)


def _f_unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return tuple(c / n for c in v)


FLASH_S = 0.044
FLASH_S_SUPP = 0.028
# The bore in the gun's own frame (rig.shotgun_mesh's top barrel, the OS-12's
# suppressor can): the flash has to leave the barrel, not the rig's mid-point.
BORE_LOCAL = {
    "shotgun": (0.0, 0.090, 0.702),   # rig.shotgun_mesh top barrel bore
    "rifle": (0.0, 0.005, 0.640),     # rig.os12_mesh suppressor can bore
}


def handheld_flash(r, tm, tip, fvec, rx, ry, age, seed, weapon="shotgun"):
    """Compact, bore-locked flash + depth-occluded halo for handheld guns."""
    suppressed = (weapon != "shotgun")
    dur = FLASH_S_SUPP if suppressed else FLASH_S
    if not (0.0 <= age < dur):
        return
    k = (1.0 - age / dur) ** (1.6 if suppressed else 1.75)
    if k <= 0.02:
        return
    roll = math.radians((seed * 137.5) % 360.0)

    def pt(ahead, right, up):
        return (
            tip[0] + fvec[0] * ahead + rx[0] * right + ry[0] * up,
            tip[1] + fvec[1] * ahead + rx[1] * right + ry[1] * up,
            tip[2] + fvec[2] * ahead + rx[2] * right + ry[2] * up,
        )

    m = Mesh()
    z0 = 0.004

    if suppressed:
        # OS-12 suppressor can: tight bore-narrow axial gas jet (stays inside
        # the 2.5 cm suppressor radius - no wide lateral star petals).
        length = 0.110 * (0.42 + 0.58 * k)
        core_r = 0.010 * (0.75 + 0.25 * k)
        throat_r = 0.013 * (0.70 + 0.30 * k)
        n_sides = 6
        c_root = (255, 246, 214)
        c_mid = (228, 162, 84)
        c_tip = (162, 84, 44)
        r0 = [pt(z0, math.cos(roll + i * math.tau / n_sides) * core_r * 0.65,
                 math.sin(roll + i * math.tau / n_sides) * core_r * 0.65)
              for i in range(n_sides)]
        r1 = [pt(z0 + length * 0.26, math.cos(roll + i * math.tau / n_sides) * throat_r,
                 math.sin(roll + i * math.tau / n_sides) * throat_r)
              for i in range(n_sides)]
        apex = pt(z0 + length, 0.0, 0.0)
        for i in range(n_sides):
            j = (i + 1) % n_sides
            m.face([r0[i], r0[j], r1[j]], c_root, 2, True, True)
            m.face([r0[i], r1[j], r1[i]], c_root, 2, True, True)
            m.face([r1[i], r1[j], apex], c_mid, 2, True, True)

        # 3 slim longitudinal gas wisps hugging the jet (<= 17 mm radius).
        for i in range(3):
            h1 = _f_hash(seed, i * 7 + 1)
            h2 = _f_hash(seed, i * 7 + 2)
            ang = roll + i * (math.tau / 3.0) + (h1 - 0.5) * 0.45
            ca, sa = math.cos(ang), math.sin(ang)
            ca_o, sa_o = -sa, ca
            fin_r = 0.0165 * (0.65 + 0.35 * h2)
            p_a = pt(z0, ca * core_r * 0.4, sa * core_r * 0.4)
            p_b = pt(z0 + length * 0.10, ca_o * 0.004, sa_o * 0.004)
            p_c = pt(z0 + length * 0.10, -ca_o * 0.004, -sa_o * 0.004)
            p_edge = pt(z0 + length * (0.34 + 0.18 * h1), ca * fin_r, sa * fin_r)
            p_end = pt(z0 + length * (0.85 + 0.20 * h2), ca * 0.003, sa * 0.003)
            m.face([p_a, p_b, p_edge], c_mid, 2, True, True)
            m.face([p_a, p_edge, p_c], c_mid, 2, True, True)
            m.face([p_b, p_end, p_edge], c_tip, 2, True, True)
            m.face([p_edge, p_end, p_c], c_tip, 2, True, True)
    else:
        # Fallow 12: crisp, punchy 12-gauge axial discharge + 5-fin muzzle crown.
        length = 0.25 * (0.52 + 0.48 * k)
        core_r = 0.022 * (0.75 + 0.25 * k)
        crown_r = 0.056 * (0.65 + 0.35 * k)
        n_core = 6
        c_root = (255, 252, 234)
        c_mid = (255, 232, 162)
        r0 = [pt(z0, math.cos(roll + i * math.tau / n_core) * core_r * 0.65,
                 math.sin(roll + i * math.tau / n_core) * core_r * 0.65)
              for i in range(n_core)]
        r1 = [pt(z0 + length * 0.22, math.cos(roll + i * math.tau / n_core) * core_r,
                 math.sin(roll + i * math.tau / n_core) * core_r)
              for i in range(n_core)]
        apex = pt(z0 + length * 0.80, 0.0, 0.0)
        for i in range(n_core):
            j = (i + 1) % n_core
            m.face([r0[i], r0[j], r1[j]], c_root, 2, True, True)
            m.face([r0[i], r1[j], r1[i]], c_root, 2, True, True)
            m.face([r1[i], r1[j], apex], c_mid, 2, True, True)

        n_blades = 5
        c_blade = (255, 224, 138)
        c_tip = (252, 152, 54)
        for i in range(n_blades):
            h1 = _f_hash(seed, i * 7 + 1)
            h2 = _f_hash(seed, i * 7 + 2)
            ang = roll + i * (math.tau / n_blades) + (h1 - 0.5) * 0.32
            ca, sa = math.cos(ang), math.sin(ang)
            ca_o, sa_o = -sa, ca
            w0 = core_r * 0.45
            p_in = pt(z0, ca * core_r * 0.3, sa * core_r * 0.3)
            p_l = pt(z0, ca_o * w0, sa_o * w0)
            p_r = pt(z0, -ca_o * w0, -sa_o * w0)
            p_crown = pt(z0 + length * (0.16 + 0.08 * h1), ca * crown_r * (0.85 + 0.3 * h2),
                         sa * crown_r * (0.85 + 0.3 * h2))
            p_jet = pt(z0 + length * (0.82 + 0.25 * h2), ca * core_r * 0.35, sa * core_r * 0.35)
            m.face([p_in, p_l, p_crown], c_blade, 2, True, True)
            m.face([p_in, p_crown, p_r], c_blade, 2, True, True)
            m.face([p_l, p_jet, p_crown], c_tip, 2, True, True)
            m.face([p_crown, p_jet, p_r], c_tip, 2, True, True)

    _w.add(r, m, bias=0.0)
    bloom_pos = pt(z0 + length * (0.36 if suppressed else 0.34), 0.0, 0.0)
    halo = _fx.glow(
        (255, 188, 108) if suppressed else (255, 204, 128),
        0.065 if suppressed else 0.16,
        tm,
        core=(255, 232, 186) if suppressed else (255, 248, 224),
        intensity=(0.34 if suppressed else 0.72) * k,
        max_px=12 if suppressed else 24,
    )
    # Layer 2 + strict_occ: never cheat depth by 0.45 m like streetlamps, so
    # Biribel's shoulder/head/torso and the barrel cleanly occlude the halo.
    halo.light = False
    halo.strict_occ = True
    r.add_sprite(bloom_pos, halo, layer=2)


_SG_RELOAD_KEYS = {}
_SHELL_MESH = None


def _sg_reload_keys(hum):
    """Cached Fallow 12 reload poses (pouch, loading port, pump stroke)."""
    ck = getattr(hum, "_gl_spec_key", None) or id(hum)
    keys = _SG_RELOAD_KEYS.get(ck)
    if keys is None:
        ref = dict(POSES["ready"], twist=SG_TWIST, head_y=SG_HEAD_Y + 32.0, head_p=8.0)
        aim_pt = m_apply(rot_y(25.0 - SG_BLADE_YAW), (-4.8, 3.0, 10.0))
        base, O, R = _hold_frame(hum, ref, (0.0, 0.0, 0.0), 0.0, "shotgun", "ready", aim=aim_pt)
        _pl, joints, _root = hum.pose_world(base, (0.0, 0.0, 0.0), 0.0, rifle_on=True)
        pel = joints["pelvis"]
        poles_l = ((0.4, -1.0, 0.0),) + POLES

        def g_pt(pt):
            off = m_apply(R, pt)
            return (O[0] + off[0], O[1] + off[1], O[2] + off[2])

        pouch_tgt = (pel[0] - 0.23, pel[1] + 0.02, pel[2] + 0.08)
        keys = {
            "_spine": ref["spine"],
            "pouch": _solve_arm_safe(hum, dict(base, head_p=16.0, head_y=SG_HEAD_Y + 26.0),
                                     (0.0, 0.0, 0.0), 0.0, "l", pouch_tgt, poles_l),
            "port_pre": _solve_arm_safe(hum, dict(base, head_p=12.0, head_y=SG_HEAD_Y + 34.0),
                                        (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, -0.09, 0.12)), poles_l),
            "port_in": _solve_arm_safe(hum, dict(base, head_p=12.0, head_y=SG_HEAD_Y + 34.0,
                                                 rifle_p=base.get("rifle_p", 0.0) - 2.5),
                                       (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, 0.015, 0.13)), poles_l),
            "pump_fwd": _solve_arm_safe(hum, dict(base, head_p=6.0, head_y=SG_HEAD_Y + 30.0),
                                        (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, 0.025, PUMP_REST_Z + PUMP_GRIP)), poles_l),
            "pump_back": _solve_arm_safe(hum, dict(base, head_p=6.0, head_y=SG_HEAD_Y + 30.0,
                                                   rifle_p=base.get("rifle_p", 0.0) - 2.0),
                                         (0.0, 0.0, 0.0), 0.0, "l", g_pt((0.0, 0.025, PUMP_BACK_Z + PUMP_GRIP)), poles_l),
        }
        _SG_RELOAD_KEYS[ck] = keys
    return keys


def _blend_pose(a, b, k):
    k = clamp(k, 0.0, 1.0)
    out = dict(a)
    for key in set(a) | set(b):
        va, vb = a.get(key, 0.0), b.get(key, 0.0)
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)):
            out[key] = va + _wrap(vb - va) * k
    return out


def sg_reload_dur(n, dry=True):
    """Exact reload duration (seconds) for ``n`` shotgun shells/slugs."""
    n = max(1, int(n))
    return SG_RELOAD_PREP + n * SG_RELOAD_SHELL + (SG_RELOAD_PUMP if dry else SG_RELOAD_READY)


def sg_shell_times(n):
    """Exact timestamps (seconds) when each of the ``n`` shells seats in the tube."""
    n = max(0, int(n))
    return tuple(SG_RELOAD_PREP + (i + 0.70) * SG_RELOAD_SHELL for i in range(n))


def sg_pump_time(n):
    """Timestamp (seconds) for the dry-chamber pump rack after ``n`` shells."""
    return SG_RELOAD_PREP + max(1, int(n)) * SG_RELOAD_SHELL + 0.148


def sg_shell_slot_prog(elapsed, n):
    """(0..1 progress, active_count) for the single shell currently sliding into the HUD tube."""
    n = max(0, int(n))
    if n <= 0 or elapsed < SG_RELOAD_PREP:
        return 0.0, 0
    rel = elapsed - SG_RELOAD_PREP
    i = int(rel // SG_RELOAD_SHELL)
    if i >= n:
        return 0.0, 0
    local = rel - i * SG_RELOAD_SHELL
    t_in = 0.70 * SG_RELOAD_SHELL
    if local < t_in:
        return clamp(local / t_in, 0.02, 1.0), 1
    return 0.0, 0


def sg_reload_pose(hum, base_pose, elapsed, reload_s=RELOAD_S, shells=None, dry=True):
    """Fallow 12 reload: reach to belt, insert ``shells`` slugs one by one, rack pump if ``dry``.

    Returns (pose, pump_k, shell_in_hand).
    """
    keys = _sg_reload_keys(hum)
    ready = _shotgun_hold(hum, dict(POSES["ready"]), "ready", ("m7player_sg", "ready"), 0.0)
    n = max(1, int(shells)) if shells is not None else 3
    want_dur = sg_reload_dur(n, dry)
    u = clamp(elapsed * (want_dur / max(0.05, float(reload_s))), 0.0, want_dur)
    pump_k = 0.0
    shell = False
    t_last_in = SG_RELOAD_PREP + (n - 1) * SG_RELOAD_SHELL + 0.70 * SG_RELOAD_SHELL
    if u < SG_RELOAD_PREP:
        rel = _blend_pose(ready, keys["pouch"], _ease(u / SG_RELOAD_PREP))
    elif u < t_last_in:
        i = min(n - 1, int((u - SG_RELOAD_PREP) // SG_RELOAD_SHELL))
        local = u - (SG_RELOAD_PREP + i * SG_RELOAD_SHELL)
        t_pre = 0.42 * SG_RELOAD_SHELL
        t_in = 0.70 * SG_RELOAD_SHELL
        if local < t_pre:
            shell = True
            rel = _blend_pose(keys["pouch"], keys["port_pre"], _ease(local / t_pre))
        elif local < t_in:
            shell = True
            rel = _blend_pose(keys["port_pre"], keys["port_in"],
                              _ease((local - t_pre) / (t_in - t_pre)))
        else:
            rel = _blend_pose(keys["port_in"], keys["pouch"],
                              _ease((local - t_in) / (SG_RELOAD_SHELL - t_in)))
    else:
        rem = u - t_last_in
        tail = want_dur - t_last_in
        if dry:
            if rem < 0.18:
                rel = _blend_pose(keys["port_in"], keys["pump_fwd"], _ease(rem / 0.18))
            elif rem < 0.44:
                q = (rem - 0.18) / 0.26
                pump_k = (_ease(q / 0.45) if q < 0.45
                          else (1.0 if q < 0.58 else 1.0 - _ease((q - 0.58) / 0.42)))
                rel = _blend_pose(keys["pump_fwd"], keys["pump_back"], pump_k)
            else:
                rel = _blend_pose(keys["pump_fwd"], ready,
                                  _ease((rem - 0.44) / max(0.05, tail - 0.44)))
        else:
            rel = _blend_pose(keys["port_in"], ready, _ease(rem / max(0.05, tail)))

    out = dict(base_pose)
    for k_name in _ARMS + ("twist", "head_y", "head_p"):
        if k_name in rel:
            out[k_name] = rel[k_name]
    out["rifle_p"] = rel.get("rifle_p", 0.0) + base_pose.get("spine", 0.0) - keys["_spine"]
    return out, pump_k, shell


def draw_sg_shell(r, lhand, rm):
    """Draw a red-and-brass 12-gauge shell in Biribel's left hand."""
    global _SHELL_MESH
    if lhand is None or rm is None:
        return
    if _SHELL_MESH is None:
        m = Mesh()
        m.add(box(0.022, 0.022, 0.046, (186, 38, 32), center=(0.0, 0.0, 0.008)))
        m.add(box(0.024, 0.024, 0.016, (212, 174, 78), center=(0.0, 0.0, -0.022)))
        _SHELL_MESH = m
    verts = [tuple(a + b for a, b in zip(m_apply(rm, v), lhand)) for v in _SHELL_MESH.verts]
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in _SHELL_MESH.faces]
    r.add_dynamic(verts, faces)


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


def _shell_drop_mesh(x, y, z, yaw):
    """Open red-and-brass 12-gauge shell box + two loose shells on the ground."""
    from engine3d import Mesh
    from engine3d.core import rot_y, box
    m = Mesh()
    m.add(box(0.16, 0.06, 0.11, (152, 44, 36), center=(0.0, 0.03, 0.0)))
    m.add(box(0.164, 0.022, 0.07, (220, 210, 182), center=(0.0, 0.042, 0.0)))
    for ox, oz in ((0.12, 0.03), (0.14, -0.04)):
        m.add(box(0.024, 0.024, 0.055, (180, 38, 32), center=(ox, 0.014, oz)))
        m.add(box(0.026, 0.026, 0.020, (212, 174, 78), center=(ox, 0.014, oz - 0.032)))
    out = Mesh()
    out.add(m, rot_y(yaw), (x, y, z))
    return out


_GROUND_SHADOW = (1, -4.0)


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

    def _anim_ctl(self):
        ctl = getattr(self, "_anim", None)
        if ctl is None or getattr(self, "_anim_t0", 0.0) > self.t + 0.05:
            ctl = LayeredAnimState(yaw_deg=getattr(self, "body_yaw", 0.0),
                                   y0=getattr(self, "py", 0.0), stride_gain=1.9)
            self._anim = ctl
        self._anim_t0 = self.t
        return ctl

    def _debris_ctl(self):
        pool = getattr(self, "_debris_pool", None)
        if pool is None or getattr(self, "_debris_t0", 0.0) > self.t + 0.05:
            pool = DebrisPool(capacity=48, seed=707)
            self._debris_pool = pool
        self._debris_t0 = self.t
        return pool

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
        hum = _w.hum(("biribel", OUTFIT_GUARD), flags=("shotgun", "nopump"))
        for mode in ("ready", "aim"):
            _sg_holds(hum, mode, ("m7player_sg", mode))
        _wall_down_hold(hum, "shotgun", ("m7player_sg", "wall"))
        _sg_reload_keys(hum)
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
        REV.warm()
        if self._truck is None:
            self._truck = W.truck()
            self._ledge = W.ledge()
        W._shape("truck_m7")
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
        REV.reset(self)
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
        self.wall_k = 0.0
        self.reloading = 0.0
        self._reload_dur = RELOAD_S
        self._reload_n = 0
        self._reload_dry = False
        self._reload_t_in = ()
        self._reload_pump_at = 1e9
        self._shell_i = 0
        self._pump_done = False
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
        self.last_flash = -9.0
        self.flash_seed = 0
        self._flash_basis = None
        self.lines = []
        self.toast = None
        self.cp_toast = 0.0
        self.kills = 0
        self.dying = False
        self.death_by_bodi = False
        self.death_t = 0.0
        self.death_msg = ""
        self.hold = 0.0
        self.alex_lifting = False
        self.lift_heave = 0.0
        self.lift_heave_cd = 0.0
        self.lift_auto_stage = 0
        self.lift_recover_t = 0.0
        self.lift_cam_k = 0.0
        self.well_shake = 0.0
        self.well_dust = []
        self.alex_gun = None
        self._last_crawl_dust = 0.0
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
        self.alex_lifting = False

    def _load(self, cp):
        self._setup(cp)

    # --- scene contract used by raid_brain -------------------------------------

    def say(self, who, text, dur=3.0):
        try:
            from audio import voice
            ms = voice.play_line(who, text, cut=False)
            if ms:
                dur = max(dur, ms / 1000.0 + 0.3)
        except Exception:
            pass
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
            dx, dz = src[0] - self.px, src[1] - self.pz
            d = math.hypot(dx, dz) or 1.0
            yr = math.radians(getattr(self, "body_yaw", self.yaw))
            lx = (dx * math.cos(yr) - dz * math.sin(yr)) / d
            lz = (dx * math.sin(yr) + dz * math.cos(yr)) / d
            self._anim_ctl().trigger_flinch(lx, lz, clamp(dmg / 18.0, 0.4, 1.5))
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
                if getattr(self, "alex_lifting", False):
                    self._trigger_lift_heave()
                    return
                if (self.reloading > 0.0 and getattr(self, "weapon", "shotgun") == "shotgun"
                        and self.mag > 0 and not getattr(self, "_reload_dry", False)):
                    self.reloading = 0.0
                    self._reload_n = 0
                    self._pump_done = False
                self.firing = True
            elif event.button == 3:
                self.aiming = True
        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button == 1:
                self.firing = False
            elif event.button == 3:
                self.aiming = False
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE and getattr(self, "alex_lifting", False):
                self._trigger_lift_heave()
            elif (event.key == pygame.K_e and hasattr(self, "wreck")
                  and self.hold > 0.05 and self.brain.near_revive() == "alex"):
                self._trigger_lift_heave()
            elif event.key == pygame.K_r:
                if not REV.is_locking(self) and not getattr(self, "alex_lifting", False):
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
        self.lift_heave = max(0.0, self.lift_heave - dt * 3.4)
        self.lift_heave_cd = max(0.0, self.lift_heave_cd - dt)
        self.well_shake *= math.exp(-dt * 7.5)
        if self.lift_recover_t > 0.0:
            self.lift_recover_t = max(0.0, self.lift_recover_t - dt)
        if self.turn is None:
            self._move(k, dt)
        else:
            self._turn_update(dt)   # he has the floor: no walking out of this
        self._update_wall_k(dt)
        if self.reloading and not self.alex_lifting:
            self.reloading = max(0.0, self.reloading - dt)
            elapsed = self._reload_dur - self.reloading
            while self._shell_i < len(self._reload_t_in) and elapsed >= self._reload_t_in[self._shell_i]:
                self._shell_i += 1
                if self.mag < MAG and self.reserve > 0:
                    self.mag += 1
                    self.reserve -= 1
                self._snd("shell_in")
            if self._reload_dry and elapsed >= self._reload_pump_at and not self._pump_done:
                self._pump_done = True
                self._snd("pump")
            if not self.reloading:
                n = max(0, min(self._reload_n - self._shell_i, MAG - self.mag, self.reserve))
                self.mag += n
                self.reserve -= n
                if self._reload_dry and not self._pump_done and self.mag > 0:
                    self._snd("pump")
                self._reload_n = 0
                self._reload_dry = False
                self._pump_done = False
        if self.t >= self.pump_snd_at:
            self.pump_snd_at = 1e9
            self._snd("pump")
        if self.firing and not self.reloading and not REV.is_locking(self) and not self.alex_lifting:
            self._fire()
        self._loot()
        self.recoil = max(0.0, self.recoil - dt * 6.0)
        self.cam_kick *= math.exp(-dt * 11.0)
        self._hold(k, dt)
        want_lcam = 1.0 if self.alex_lifting else 0.0
        self.lift_cam_k += (want_lcam - self.lift_cam_k) * min(1.0, dt * (7.0 if want_lcam else 5.5))
        self._debris_ctl().update(dt, floor_fn=getattr(self, "_floor", None),
                                  box_world=getattr(self.world, "box_world", None))
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
        self.well_dust = [x for x in self.well_dust if now - x[0] < x[5]]

    def _move(self, k, dt):
        def down(*codes):
            try:
                return any(k[c] for c in codes)
            except Exception:
                return False

        if REV.is_locking(self) or getattr(self, "alex_lifting", False):
            self.vel = (0.0, 0.0)
            self.pmoving = False
            self.sprint = False
            self._anim_ctl().update(
                dt, vel_xz=(0.0, 0.0), yaw_deg=self.body_yaw,
                aiming=False, sprint=False, crouch=False,
                floor_fn=getattr(self, "_floor", None),
                pos=(self.px, getattr(self, "py", 0.0), self.pz),
            )
            return
        fwd_in = (1 if down(pygame.K_w, pygame.K_UP) else 0) - (1 if down(pygame.K_s, pygame.K_DOWN) else 0)
        side_in = (1 if down(pygame.K_d, pygame.K_RIGHT) else 0) - (1 if down(pygame.K_a, pygame.K_LEFT) else 0)
        self.sprint = (down(pygame.K_LSHIFT, pygame.K_RSHIFT) and fwd_in > 0
                       and self.ads < 0.3 and not self.firing)
        if self.sprint and getattr(self, "lift_recover_t", 0.0) > 0.0:
            self.lift_recover_t = 0.0
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
        crouch = down(pygame.K_c, pygame.K_LCTRL) and not self.sprint
        self._anim_ctl().update(
            dt, vel_xz=self.vel, yaw_deg=self.body_yaw,
            aiming=(self.ads > 0.3 or self.t - self.last_fire < 0.45),
            sprint=self.sprint, crouch=crouch,
            floor_fn=getattr(self, "_floor", None),
            pos=(self.px, getattr(self, "py", 0.0), self.pz),
        )

    def _wall_probe_dist(self):
        py = getattr(self, "py", 0.0)
        f = _fwd(self.yaw, self.pitch)
        rg = _right(self.yaw)
        o1 = (self.px, py + 1.34, self.pz)
        o2 = (self.px + rg[0] * 0.14, py + 1.34, self.pz + rg[2] * 0.14)
        return min(self.world.ray_hit(o1, f, 1.4), self.world.ray_hit(o2, f, 1.4))

    def _update_wall_k(self, dt):
        if getattr(self, "turn", None) is not None or REV.is_locking(self):
            self.wall_k = 0.0
            return
        use_sg = (getattr(self, "weapon", "shotgun") == "shotgun")
        clear_d = 1.22 if use_sg else 1.12
        full_d = 0.68
        dist = self._wall_probe_dist()
        want = _ease(clamp((clear_d - dist) / (clear_d - full_d), 0.0, 1.0))
        rate = 18.0 if want > self.wall_k else 12.0
        self.wall_k = clamp(self.wall_k + (want - self.wall_k) * min(1.0, dt * rate), 0.0, 1.0)

    # --- camera and aim ----------------------------------------------------------

    def camera(self):
        back, right, up = (BOOM[i] + (BOOM_ADS[i] - BOOM[i]) * self.ads for i in range(3))
        lk = _ease(clamp(getattr(self, "lift_cam_k", 0.0), 0.0, 1.0))
        if lk > 1e-3:
            back += 0.45 * lk
            right += 0.24 * lk
            up -= 0.16 * lk
        pivot = (self.px, EYE_H + up, self.pz)
        f = _fwd(self.yaw, self.pitch)
        rg = _right(self.yaw)
        right = min(right, max(0.0, self.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), right + 0.3) - 0.3))
        shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
        d = (-f[0], -f[1], -f[2])
        dist = max(0.45, min(back, self.world.ray_hit(shoulder, d, back + 0.35) - 0.35))
        eye = (shoulder[0] + d[0] * dist, max(0.35, shoulder[1] + d[1] * dist),
               shoulder[2] + d[2] * dist)
        shk_pitch = 0.0
        wshk = getattr(self, "well_shake", 0.0)
        if wshk > 1e-3 or (self.alex_lifting and self.lift_heave > 0.05):
            red, smul = _motion_prefs()
            if not red and smul > 0.0:
                amp = (wshk + 0.22 * self.lift_heave) * smul
                jx = math.sin(self.t * 47.0) * 0.045 * amp
                jy = math.cos(self.t * 61.0) * 0.075 * amp
                eye = (eye[0] + rg[0] * jx, max(0.32, eye[1] + jy), eye[2] + rg[2] * jx)
                shk_pitch = math.sin(self.t * 53.0) * 1.35 * amp
        fv = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick + shk_pitch)
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
        fov = FOV + (FOV_ADS - FOV) * self.ads - 1.4 * self.cam_kick + 3.5 * lk
        eye, tgt, fov = REV.adjust_camera(self, eye, tgt, fov)
        return eye, tgt, fov, dist

    def _aim_ray(self):
        eye, _tgt, _fov, dist = self.camera()
        f = _fwd(self.yaw, self.pitch + 1.6 * self.cam_kick)   # the crosshair ray, as the camera looks
        return (eye[0] + f[0] * dist, eye[1] + f[1] * dist, eye[2] + f[2] * dist), f

    def _begin_reload(self):
        if self.reloading or self.mag >= MAG or self.reserve <= 0:
            return
        n = min(MAG - self.mag, self.reserve)
        dry = (self.mag == 0)
        self._reload_n = n
        self._reload_dry = dry
        self._reload_dur = sg_reload_dur(n, dry)
        self._reload_t_in = sg_shell_times(n)
        self._reload_pump_at = sg_pump_time(n) if dry else 1e9
        self.reloading = self._reload_dur
        self._shell_i = 0
        self._pump_done = False
        self._snd("reload")
        self._anim_ctl().start_reload(self._reload_dur)

    def reload_total(self):
        return self._reload_dur if self.reloading > 0.0 else self.RELOAD_S

    def reload_shell_info(self):
        if self.reloading <= 0.0 or self._reload_n <= 0:
            return 0.0, 0
        return sg_shell_slot_prog(self._reload_dur - self.reloading, self._reload_n)

    def _fire(self):
        if self.t - self.last_fire < FIRE_GAP:
            return
        if getattr(self, "alex_lifting", False):
            return
        self.lift_recover_t = 0.0
        if self.wall_k > 0.65:
            return
        if self.mag <= 0:
            if self.t - self.last_fire > 0.3:
                self.last_fire = self.t
                self._snd("dry")
                self._begin_reload()
            return
        self.mag -= 1
        self.last_fire = self.t
        self.last_flash = self.t
        self.flash_seed += 1
        self.pump_at = self.t
        self.pump_snd_at = self.t + PUMP_S
        self._pig_scare()
        o, d = self._aim_ray()      # the shot leaves along the sight as it was, before the kick
        look_pitch = self.pitch + 1.6 * self.cam_kick
        self.recoil = min(3.0, self.recoil + 1.4)
        self.cam_kick = min(2.6, self.cam_kick + 2.0)
        self.pitch = clamp(self.pitch + 0.55, *PITCH_LIM)
        self._anim_ctl().trigger_recoil(pitch_deg=8.0, rifle_deg=13.5, cam_pitch=1.8)
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
            hit_e, head, zone, hit_pig, hit_bodi = None, False, "chest", False, False
            for e in self.brain.enemies:
                if not e["alive"] or not e["live"]:
                    continue
                for zi, (c, rad, is_head) in enumerate(self.brain.spheres(e)):
                    h = B._ray_sphere(o, dd, c, rad)
                    if h is not None and h < best:
                        best, hit_e, head = h, e, is_head
                        zone = "head" if is_head else ("chest", "head", "gut", "leg")[min(zi, 3)]
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
                if best < 45.0:
                    self._debris_ctl().spawn_burst(end, n=3, normal=(-dd[0], 0.6, -dd[2]), speed=3.2)
            else:
                any_enemy = True
                any_head = any_head or head
                pdmg = PELLET_HEAD if head else PELLET_BODY
                rec = hits.get(id(hit_e))
                if rec is None:
                    hits[id(hit_e)] = [hit_e, pdmg, head, zone, end, dd, best]
                else:
                    rec[1] += pdmg
                    rec[6] = min(rec[6], best)
                    if head and not rec[2]:
                        rec[2], rec[3], rec[4], rec[5] = True, "head", end, dd
                impact_pts.append((end, "blood"))
        self.world.pig_at = pig_block
        for end in lanes:
            self.tracers.append((self.t, src, end, (255, 226, 160)))
        for end, kind in impact_pts:
            self.impacts.append((self.t, end, kind))
        ld = _fwd(self.yaw, look_pitch)
        self.sparks.append((self.t, (o[0] + ld[0] * farthest, o[1] + ld[1] * farthest,
                                     o[2] + ld[2] * farthest)))
        for e, dmg, is_hd, hz, hp, hray, hdist in hits.values():
            self.brain.hurt_enemy(e, dmg, (o[0], o[2]), hit_ctx=dict(
                is_head=is_hd, hit_zone=hz, hit_pos=hp, hit_ray=hray,
                weapon="shotgun", dmg=dmg, hit_dist=hdist,
            ))
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
                    self.brain.hurt_enemy(e, 150.0 * (1.0 - 0.55 * d / TANK_BLAST_R), (cx, cz),
                                          hit_ctx=dict(weapon="blast", blast=((cx, cy, cz), 15.0, TANK_BLAST_R)))
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

    def _trigger_lift_heave(self):
        """Active heave boost (Space/LMB/tap E while lifting Alex's well beam)."""
        if self.lift_heave_cd > 0.0 or not self.brain.alex.get("pinned"):
            return
        self.lift_heave_cd = 0.26
        self.lift_heave = 1.0
        self.hold += 0.32
        self.wreck.heave_kick(1.0)
        self._snd("beam_heave")
        self.well_shake = max(self.well_shake, 0.34)
        lg, mid, rg = self.wreck.beam_grips()
        self._add_well_dust(mid, 0.75, life=0.85, col=(142, 128, 108), vy=0.55)
        self._add_well_dust(lg, 0.55, life=0.70, col=(134, 120, 100), vy=0.45)
        self._spawn_wood_splinters(rg, n=2, speed=1.8)

    def _hold(self, k, dt):
        if self.turn is not None:
            self.hold = 0.0
            self.alex_lifting = False
            REV.step(self, dt, None, False, 1.0, self.brain.help_done)
            return
        who = self.brain.near_revive()
        try:
            held = bool(k[pygame.K_e])
        except Exception:
            held = False
        if who == "alex":
            # REV.step's idle path only clears scene.hold while it still owns it
            # (ReviveState.holds), so Alex's beam-lift - which shares that field
            # and is advanced right below - is left alone.
            REV.step(self, dt, None, False, 1.0, self.brain.help_done)
            if not held:
                self.alex_lifting = False
                self.lift_auto_stage = 0
                # Gravity-coupled sag instead of instant wipe so brief dodges/taps feel natural.
                self.hold = max(0.0, self.hold - dt * 1.9)
                return
            if not self.alex_lifting:
                self.alex_lifting = True
                self.firing = False
                self.aiming = False
                self.lift_recover_t = 0.0
                self._snd("beam_strain")
            self.hold += dt
            # Slide cleanly into the lifting stance south-east of Alex and face the beam.
            k_step = min(1.0, dt * 11.0)
            self.px, self.pz = self.world.move(
                self.px, self.pz,
                (W.WELL_LIFT_AT[0] - self.px) * k_step,
                (W.WELL_LIFT_AT[1] - self.pz) * k_step,
            )
            self.body_yaw = _w.yaw_mix(self.body_yaw, LIFT_YAW, min(1.0, dt * 14.0))
            u = clamp(self.hold / HOLD_S["alex"], 0.0, 1.0)
            if self.lift_auto_stage == 0 and u >= 0.30:
                self.lift_auto_stage = 1
                if self.lift_heave < 0.2:
                    self.lift_heave = 0.55
                    self.wreck.heave_kick(0.45)
                    self._snd("beam_strain")
                    self._add_well_dust(self.wreck.beam_grips()[1], 0.55, life=0.75)
            elif self.lift_auto_stage == 1 and u >= 0.72:
                self.lift_auto_stage = 2
                if self.lift_heave < 0.2:
                    self.lift_heave = 0.70
                    self.wreck.heave_kick(0.60)
                    self._snd("beam_heave")
                    self._add_well_dust(self.wreck.beam_grips()[1], 0.65, life=0.80)
            if u > 0.18 and self.t - self._last_crawl_dust > 0.22:
                self._last_crawl_dust = self.t
                a = self.brain.alex
                self._add_well_dust((a["x"], 0.10, a["z"] - B.ALEX_CRAWL * u + 0.35),
                                    0.42, life=0.65, col=(126, 112, 92), vy=0.35)
            if self.hold >= HOLD_S[who]:
                self.hold = 0.0
                self.alex_lifting = False
                self.lift_auto_stage = 0
                self.lift_recover_t = 0.32
                self.wreck.shove()
                self._snd("beam_heave")
                self.brain.help_done(who)
            return
        self.alex_lifting = False
        self.lift_auto_stage = 0
        if who == "bodi":
            REV.step(self, dt, "bodi", held, HOLD_S["bodi"], self.brain.help_done)
            if not held:
                self.hold = 0.0
            return
        REV.step(self, dt, None, False, 1.0, self.brain.help_done)
        if not held:
            self.hold = 0.0
            return

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
            self.say("BODI", "That pig was Maru's. He raised it by hand.", 3.4)
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
            return "Dry - take shells off the bodies", None, None
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
        if 0.0 <= now - self.last_flash < max(0.04, FLASH_S):
            out.append({"pos": self._muzzle or (self.px, 1.4, self.pz),
                        "color": (255, 204, 132), "intensity": 1.45, "range": 5.5})

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
        if r.visible_sphere((pm["x"], 0.4, pm["z"]), 1.3):
            if pm["dead"]:
                r.add_sprite(
                    (pm["x"], 0.03, pm["z"]),
                    F.pool((104, 16, 18), 1.05, intensity=0.62, squash=1.0),
                    layer=_fx.FX_LAYER,
                )
                r.add_blob_shadow((pm["x"], 0.02, pm["z"]), 0.55, 0.55, 0.45,
                                  layer=1, bias=-4.0)
                W.put(r, self._dead_pig_mesh(), pm["x"], 0.0, pm["z"], pm["yaw"])
            else:
                moving = pm["mode"] in ("walk", "flee")
                from cutscenes.m7pig3d import walking_frame
                pig_mesh = self._pig_walk[walking_frame(pm["gait"])] if moving else self._pig_mesh
                r.add_blob_shadow((pm["x"], 0.02, pm["z"]), 0.50, 0.50, 0.45,
                                  layer=1, bias=-4.0)
                W.put(r, pig_mesh, pm["x"], 0.0, pm["z"], pm["yaw"])
        self._draw_allies(r, tm)
        self._draw_player(r, tm)
        self._draw_enemies(r, tm)
        self.fire.draw(r, tm, self.t)
        self._draw_tank(r, tm)
        self._draw_fx(r, tm)
        f_age = self.t - self.last_flash
        if 0.0 <= f_age < FLASH_S and self._flash_basis is not None:
            tip, fvec, rx, ry = self._flash_basis
            handheld_flash(r, tm, tip, fvec, rx, ry, f_age, self.flash_seed, "shotgun")
        tx, tz = self.objective_point()
        self.marker_screen = self._project(r, (tx, 1.6, tz)) if tx is not None else None
        if getattr(r, "backend", "") == "gl":
            r.flush_to(surface, post={
                "bloom": 0.28, "bloom_knee": 0.96,
                "lut": F.raid_curve(), "dither_step": _fx.DITHER_STEP,
            })
        else:
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
                    round(2.2 + age * 11.0, 1),
                    tm,
                    core=(255, 250, 220),
                    intensity=3.0 * flash,
                    max_px=150,
                ),
                layer=_fx.FX_LAYER,
            )

        # FIREBALL: several expanding, rising lobes with staggered ignition.
        if age < 2.35:
            for i in range(4):
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
                        smoky=False,
                        layer=2,
                    )

        # PRESSURE FRONT: an expanding, low dust ring.
        if age < 1.15:
            k = age / 1.15
            radius = 0.6 + 10.5 * k
            strength = round(0.30 * (1.0 - k) ** 2, 2)

            for i in range(6):
                ang = i * math.tau / 6.0
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
            for i in range(4):
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
                    smoky=(i == 0),
                    layer=2,
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
            for i in range(6):
                born = 0.3 + i * 0.77
                if age < born:
                    continue

                a = (age - born) % 4.64
                aq = round(a, 1)
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
                        1.1 + aq * 0.55,
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
        anim = self._anim_ctl()
        return anim.compose(
            POSES["ready"], POSES["aim"],
            pitch_deg=self.pitch, time_s=self.t, breath_amp=0.35,
        )

    def _draw_grounded_shotgun(self, r):
        """Biribel's Fallow 12 laid on the dirt beside his right boot during the lift."""
        global _GROUND_SG_MESH
        if _GROUND_SG_MESH is None:
            _GROUND_SG_MESH = _shotgun_mesh(with_pump=True)
        m = m_mul(rot_y(self.body_yaw + 24.0), rot_z(88.0))
        rg = _right(self.body_yaw)
        fw = _fwd(self.body_yaw, 0.0)
        pos = (self.px + rg[0] * 0.42 - fw[0] * 0.08, 0.045,
               self.pz + rg[2] * 0.42 - fw[2] * 0.08)
        w = Mesh()
        w.add(_GROUND_SG_MESH, m, t=pos)
        _w.add(r, w)

    def _lift_pose_ik(self, hum, u):
        """Deadlift-to-press stance with both hands IK-locked onto the live crossbeam."""
        eu = _ease(u)
        heave = self.lift_heave
        red, _ = _motion_prefs()
        trem = (math.sin(self.t * 38.0) * (1.2 if 0.08 < u < 0.96 else 0.0)) if not red else 0.0
        pose = blend(LIFT_LOW, LIFT_HIGH, eu)
        pose["spine"] = pose.get("spine", 24.0) - 6.5 * heave + trem * 0.7
        pose["spine_r"] = trem * 0.65
        pose["head_p"] = pose.get("head_p", -18.0) - 5.0 * heave
        pose["head_y"] = -14.0 * (1.0 - 0.5 * eu)   # glances left at Alex scrambling clear
        pose["lkn"] = max(8.0, pose.get("lkn", 30.0) - 9.0 * heave)
        pose["rkn"] = max(8.0, pose.get("rkn", 26.0) - 9.0 * heave)
        pose["lhip_p"] = max(6.0, pose.get("lhip_p", 26.0) - 7.0 * heave)
        pose["rhip_p"] = max(6.0, pose.get("rhip_p", 22.0) - 7.0 * heave)
        lg, _mid, rg = self.wreck.beam_grips()
        inv = rot_y(-self.body_yaw)
        l_loc = m_apply(inv, (lg[0] - self.px, lg[1], lg[2] - self.pz))
        r_loc = m_apply(inv, (rg[0] - self.px, rg[1], rg[2] - self.pz))
        pose = _solve_arm_safe(hum, pose, (0.0, 0.0, 0.0), 0.0, "l", l_loc,
                               ((-0.65, -1.0, -0.15),) + POLES)
        pose = _solve_arm_safe(hum, pose, (0.0, 0.0, 0.0), 0.0, "r", r_loc,
                               ((0.65, -1.0, -0.15),) + POLES)
        return pose

    def _draw_player(self, r, tm):
        key = ("biribel", OUTFIT_GUARD)
        at = (self.px, 0.0, self.pz)
        if self.dying:
            kk = clamp(self.death_t / 0.6, 0.0, 1.0)
            _w.actor(r, key, blend("kneel", "dead_back", kk), at, self.body_yaw, int(tm), seed=93,
                     amp=0.0, rifle_on=False, flags=("shotgun",), expression="angry",
                     shadow=_GROUND_SHADOW)
            self._muzzle = self._flash_basis = None
            return
        lift = self._help_k()
        if self.alex_lifting and lift > 0.0:
            hum_bare = _w.hum(key, flags=("shotgun",))
            pose = self._lift_pose_ik(hum_bare, lift)
            _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93, amp=0.0,
                     rifle_on=False, flags=("shotgun",), expression="angry",
                     shadow=_GROUND_SHADOW)
            self._draw_grounded_shotgun(r)
            self._muzzle = self._flash_basis = None
            return
        if self.lift_recover_t > 0.0:
            u = 1.0 - clamp(self.lift_recover_t / 0.32, 0.0, 1.0)
            if u < 0.45:
                pose = blend(LIFT_SHOVE, POSES["ready"], _ease(u / 0.45))
                _w.actor(r, key, pose, at, self.body_yaw, int(tm), seed=93, amp=0.0,
                         rifle_on=False, flags=("shotgun",), expression="stern",
                         shadow=_GROUND_SHADOW)
                self._draw_grounded_shotgun(r)
                self._muzzle = self._flash_basis = None
                return
        hum = _w.hum(key, flags=("shotgun", "nopump"))
        pose = self._player_pose()
        shell = False
        draw_yaw = self.body_yaw + SG_BLADE_YAW
        if self.reloading > 0.0:
            pose, pump, shell = sg_reload_pose(
                hum, pose, self._reload_dur - self.reloading, self._reload_dur,
                shells=self._reload_n, dry=self._reload_dry)
            if self.wall_k > 0.005:
                pose["rifle_p"] = pose.get("rifle_p", 0.0) + 38.0 * self.wall_k
                pose["rsh_p"] = pose.get("rsh_p", 0.0) - 12.0 * self.wall_k
                pose["lsh_p"] = pose.get("lsh_p", 0.0) - 10.0 * self.wall_k
        else:
            anim = self._anim_ctl()
            pump = _pump_k(self.t - self.pump_at)
            mode = "aim" if (self.ads > 0.5 or self.t - self.last_fire < 0.50) else "ready"
            pose = _shotgun_hold(hum, pose, mode, ("m7player_sg", mode), pump)
            pose = apply_wall_down(hum, pose, "shotgun", self.wall_k, ("m7player_sg", "wall"))
        pose, draw_yaw, rev_active = REV.apply_player_revive(self, hum, pose, at, draw_yaw, True)
        if rev_active:
            pump = 0.0
            shell = False
        joints = _w.actor(r, key, pose, at, draw_yaw, int(tm), seed=93,
                          amp=0.0 if rev_active else 0.12, rifle_on=True, flags=("shotgun", "nopump"),
                          expression="stern" if rev_active else "angry", shadow=_GROUND_SHADOW)
        if joints:
            draw_shotgun_pump(r, joints.get("rhand"), joints.get("rifle_m"), pump)
            if shell:
                draw_sg_shell(r, joints.get("lhand"), joints.get("rifle_m"))
        rm = joints.get("rifle_m") if joints else None
        hand = joints.get("rhand") if joints else None
        if not rev_active and rm is not None and hand is not None:
            off = m_apply(rm, BORE_LOCAL["shotgun"])
            m = (hand[0] + off[0], hand[1] + off[1], hand[2] + off[2])
            self._flash_basis = (m, _f_unit(m_apply(rm, (0.0, 0.0, 1.0))),
                                 _f_unit(m_apply(rm, (1.0, 0.0, 0.0))),
                                 _f_unit(m_apply(rm, (0.0, 1.0, 0.0))))
        else:
            f, rg = _fwd(self.yaw, 0.0), _right(self.yaw)
            m = (self.px + f[0] * 0.7 + rg[0] * 0.25, 1.38, self.pz + f[2] * 0.7 + rg[2] * 0.25)
            self._flash_basis = None
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
            base = self._cover_pose(key)
            wk = getattr(self, "wreck", None)
            if wk is not None and wk.phase == "creak":
                # First slip hits: Alex whips his head up at the groaning roof.
                u = clamp((wk.creak_t - 0.30) / 0.25, 0.0, 1.0)
                if u > 0.0:
                    eu = _ease(u)
                    p = dict(base)
                    p["head_p"] = base.get("head_p", 0.0) - 36.0 * eu
                    p["head_y"] = base.get("head_y", 0.0) - 18.0 * eu
                    p["spine"] = base.get("spine", 12.0) - 8.0 * eu
                    return p
            elif wk is not None and wk.phase == "fall":
                deg = math.degrees(wk.th)
                if deg < 70.0:
                    return blend(base, ALEX_BRACE, _ease(clamp((deg - 16.0) / 40.0, 0.0, 1.0)))
                # Beam contacts his shoulders and drives him flat cleanly onto impact.
                return blend(ALEX_BRACE, self._pinned_pose(a, key, 0.0),
                             _ease(clamp((deg - 70.0) / (W.WELL_DOWN - 70.0), 0.0, 1.0)))
            return base
        hum = _w.hum(key)
        gun = _ally_gun(key)
        stance = _hold_cached(hum, dict(POSES["ready"]), gun, "ready", key=key)
        rise = (self.t - a.get("freed", -9.0)) / B.ALEX_RISE_S
        if rise < 1.0:
            # out from under the roof: push up onto a knee, take the rifle, stand
            rise = max(0.0, rise)
            if rise < RISE_KNEE:
                return blend(self._pinned_pose(a, key, 1.0), ALEX_GRAB, _ease(rise / RISE_KNEE))
            knee = _hold_cached(hum, dict(POSES["kneel"]), gun, "ready", key=key)
            return blend(knee, stance, _ease((rise - RISE_KNEE) / (1.0 - RISE_KNEE)))
        aiming = self.t - a["aim"] < B.ALLY_HOLD
        if aiming:
            # shouldered at the target, raised over ALLY_RAISE from the ready hold
            aim = _ally_aim(key, a["slope"])
            up = clamp((self.t - a["raised"]) / B.ALLY_RAISE, 0.0, 1.0)
            stance = aim if up >= 1.0 else blend(stance, aim, _ease(up))
        k = a.get("walk_k", 0.0)
        if k <= 0.0:
            return stance
        phase = a.get("gait", 0.0) / gait_cycle_m(3.4) * math.tau
        lower = locomotion_pose(3.4, 0.0, phase)
        run = mask_pose(lower, stance)
        base_tw = AIM_TWIST if aiming else 0.0
        d_tw = lower.get("twist", 0.0) * (0.45 if aiming else 0.65)
        d_sp = lower.get("spine", 0.0) * (0.45 if aiming else 0.60)
        run["body_r"] = lower.get("body_r", 0.0)
        run["spine_r"] = lower.get("spine_r", 0.0) * 0.85
        run["spine"] = stance.get("spine", 0.0) + d_sp
        run["twist"] = stance.get("twist", base_tw) + d_tw
        run["head_y"] = stance.get("head_y", 0.0) - d_tw * 0.8
        run["rifle_p"] = stance.get("rifle_p", 0.0) + d_sp
        run["rifle_y"] = stance.get("rifle_y", 0.0) + d_tw
        return run if k >= 1.0 else blend(stance, run, _ease(k))

    def _help_k(self):
        """How far Biribel is through freeing Alex, 0..1."""
        if self.brain.near_revive() != "alex":
            return 0.0
        return clamp(self.hold / HOLD_S["alex"], 0.0, 1.0)

    def _add_well_dust(self, pos, rad=0.9, life=1.2, col=(132, 118, 98), vy=0.55, vx=0.0, vz=0.0):
        self.well_dust.append((self.t, pos, rad, col, (vx, vy, vz), life))
        del self.well_dust[:-28]

    def _spawn_wood_splinters(self, pos, n=6, normal=(0.0, 0.7, -0.4), speed=3.4):
        pool = self._debris_ctl()
        before = len(pool.items)
        pool.spawn_burst(pos, n=n, normal=normal, speed=speed)
        wood_cols = ((92, 64, 38), (118, 86, 52), (148, 116, 74))
        for i, db in enumerate(pool.items[before:]):
            db.col = wood_cols[i % len(wood_cols)]
            db.half = (0.018, 0.012, 0.09 + 0.04 * (i % 3))

    def _drop_alex_gun(self, a):
        self.alex_gun = {
            "t0": self.t,
            "p0": (a["x"] - 0.22, 0.50, a["z"] - 0.12),
            "p1": (a["x"] - 0.62, 0.045, a["z"] - 0.95),
            "yaw0": 175.0,
            "yaw1": 248.0,
        }

    def _draw_alex_gun(self, r):
        g = self.alex_gun
        if g is None:
            return
        u = clamp((self.t - g["t0"]) / 0.48, 0.0, 1.0)
        eu = 1.0 - (1.0 - u) ** 2
        p0, p1 = g["p0"], g["p1"]
        arc = 0.24 * 4.0 * u * (1.0 - u) if u < 0.72 else 0.06 * math.sin((u - 0.72) / 0.28 * math.pi)
        pos = (
            _lerp(p0[0], p1[0], eu),
            _lerp(p0[1], p1[1], eu) + arc,
            _lerp(p0[2], p1[2], eu),
        )
        yaw = _lerp(g["yaw0"], g["yaw1"], eu)
        roll = 86.0 * _ease(clamp(u / 0.72, 0.0, 1.0))
        w = Mesh()
        w.add(_alex_gun_mesh(), m_mul(rot_y(yaw), rot_z(roll)), t=pos)
        _w.add(r, w)

    def _well_impact_fx(self, pos, power=1.0):
        for i in range(6):
            ang = i * math.tau / 6.0 + 0.35
            self._add_well_dust(
                (pos[0] + math.cos(ang) * 0.55, 0.14, pos[2] + math.sin(ang) * 0.45),
                rad=(0.85 + 0.25 * (i % 2)) * power,
                life=1.15 + 0.25 * (i % 2),
                col=(136, 122, 102),
                vy=0.65 * power,
                vx=math.cos(ang) * 0.95 * power,
                vz=math.sin(ang) * 0.85 * power,
            )
        d = math.hypot(self.px - pos[0], self.pz - pos[2])
        shk = clamp(1.0 - d / 16.0, 0.12, 1.0) * power
        self.well_shake = max(self.well_shake, shk)

    def _well(self, dt):
        """Run the well frame: it goes once Alex has been in cover a moment, the
        first landing pins him, Biribel's hold lifts it, and every hit is heard."""
        a, wk = self.brain.alex, self.wreck
        if a.get("cover_t") is not None:
            if wk.phase == "idle":
                wk.start_creak()
                self._snd("well_creak")
            if self.t - a["cover_t"] >= WELL_CREAK_S and wk.phase == "creak":
                wk.topple()
        lift = self._help_k() if (a.get("pinned") and self.alex_lifting) else 0.0
        wk.update(dt, lift if lift > 0.0 else None)
        for kind, speed in wk.events:
            if kind == "slip":
                self._snd("well_creak")
                for pb in wk.post_bases():
                    self._spawn_wood_splinters(pb, n=3, normal=(0.0, 0.4, -0.8), speed=2.0)
                    self._add_well_dust(pb, 0.45, life=0.75, vy=0.25)
            elif kind == "snap":
                self._snd("well_snap")
                for pb in wk.post_bases():
                    self._spawn_wood_splinters(pb, n=6, normal=(0.0, 0.7, -0.7), speed=4.2)
                    self._add_well_dust(pb, 0.65, life=0.90, vy=0.45)
            elif kind == "tin_tear":
                self._snd("tin_clatter")
            elif kind == "tin":
                self._snd("tin_clatter" if speed > 1.8 else "impact", False)
                self._add_well_dust(wk.tin_center(), 0.55, life=0.75, vy=0.35)
            elif kind == "bucket":
                self._snd("bucket")
            elif kind == "frame":
                mid = wk.beam_grips()[1]
                if a.get("cover_t") is not None:
                    a["cover_t"] = None
                    a["pinned"], a["pinned_t"], a["yaw"] = True, self.t, 180.0
                    self._drop_alex_gun(a)
                    self.say("ALEX", "I'm pinned! Biribel, I'm pinned!", 3.4)
                    self.world.boxes.extend(wk.boxes())
                    self._unstick()
                    self._well_impact_fx(mid, power=1.0)
                    self._spawn_wood_splinters(mid, n=10, normal=(0.0, 0.8, -0.4), speed=3.6)
                    self._snd("well_crash")
                elif speed > 1.2:
                    self._well_impact_fx(mid, power=0.45)
                    self._snd("impact", False)
            elif kind == "drop":
                mid = wk.beam_grips()[1]
                self._well_impact_fx(mid, power=0.80 if speed > 2.0 else 0.40)
                if speed > 1.9:
                    self._snd("well_crash")
                else:
                    self._snd("impact", False)
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
            look = self._help_k() if self.alex_lifting else 0.0
        t, calm = self.t, 1.0 - look
        heave = max(0.0, math.sin(t * 2.4)) ** 3 * calm
        claw = math.sin(t * 5.8) * calm
        crawl = clamp((look - 0.14) / 0.86, 0.0, 1.0)
        pull = math.sin(crawl * math.pi * 3.5) * (1.0 if look > 0.08 else 0.0)
        duck = max(0.0, 1.0 - (t - a.get("flinch", -9.0)) / 0.35) * calm
        kick = max(0.0, math.sin(t * 3.8 + 1.0)) * calm
        # Look up toward Biribel as you walk over to help him.
        d_bir = math.hypot(self.px - a["x"], self.pz - a["z"])
        if calm > 0.3 and d_bir < 8.5:
            to_bir = _wrap(_yaw(self.px - a["x"], self.pz - a["z"]) - 180.0)
            head_turn = clamp(to_bir * 0.55, -34.0, 34.0) * calm
        else:
            head_turn = 14.0 * math.sin(t * 1.1) * calm
        p = dict(POSES["prone"])
        p.update(
            body_r=6.0 * pull,
            twist=10.0 * pull,
            spine=p["spine"] - 16.0 * heave + 10.0 * duck - 8.0 * look,
            head_p=p["head_p"] - 14.0 * heave + 30.0 * duck - 12.0 * look,
            head_y=head_turn,
            lsh_p=p["lsh_p"] - 54.0 * heave + 16.0 * claw + 28.0 * pull,
            rsh_p=p["rsh_p"] - 54.0 * heave - 16.0 * claw - 28.0 * pull,
            lsh_r=p.get("lsh_r", 0.0) + 12.0 * max(0.0, pull),
            rsh_r=p.get("rsh_r", 0.0) + 12.0 * max(0.0, -pull),
            lel=p["lel"] + 42.0 * heave + 32.0 * max(0.0, -pull),
            rel=p["rel"] + 42.0 * heave + 32.0 * max(0.0, pull),
            lkn=p["lkn"] + 28.0 * kick + 14.0 * max(0.0, -pull),
            rkn=p["rkn"] + 28.0 * (calm - kick) + 14.0 * max(0.0, pull),
        )
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
            seed = 61 if name == "bodi" else 62
            pose = self._ally_pose(a, key)
            z, yaw, armed = a["z"], a["yaw"], True
            expr = None
            if name == "alex":
                armed = self._alex_armed(a)
                if a.get("pinned"):
                    u_crawl = _ease(clamp((self._help_k() - 0.12) / 0.88, 0.0, 1.0)) if self.alex_lifting else 0.0
                    z -= B.ALEX_CRAWL * u_crawl
                    expr = "worried" if self.lift_heave < 0.2 else "angry"
                if a.get("cover_t") is not None:
                    # back to the well: turn to face the yard as he drops into cover
                    k = _ease(clamp((self.t - a["cover_t"]) / 0.3, 0.0, 1.0))
                    yaw = a["yaw"] + ((180.0 - a["yaw"] + 180.0) % 360.0 - 180.0) * k
                    if self.wreck.phase in ("creak", "fall") and (
                        self.wreck.phase == "fall" or self.wreck.creak_t > 0.30
                    ):
                        expr = "surprised"
                if armed:
                    self.alex_gun = None
                elif self.alex_gun is not None:
                    self._draw_alex_gun(r)
            if not a.get("pinned") and a.get("cover_t") is None:
                pose, armed, expr, _ = REV.ally_pose_and_hand(
                    self, name, a, _w.hum(key), pose, yaw, seed=seed,
                )
                if not armed:
                    REV.draw_ground_rifle(r, a, "rifle")
            living_down = (a["state"] == "down" or REV.is_reviving(self, name))
            joints = _w.actor(r, key, pose, (a["x"], a["y"], z), yaw, int(tm),
                              seed=seed, amp=0.0 if living_down else 0.3, rifle_on=armed,
                              expression=expr, mouth=0.0, shadow=_GROUND_SHADOW)
            a["muzzle"] = joints.get("muzzle") if joints else None
            if a["state"] == "down" and name == "bodi" and not REV.is_reviving(self, "bodi"):
                r.add_sprite((a["x"], 1.6, a["z"]), _fx.glow((255, 90, 70), 0.3, tm, intensity=0.8,
                                                              core=(255, 160, 140), flicker=0.3),
                             layer=_fx.FX_LAYER)

    def _guard_pose(self, e):
        aiming = e["tele"] > 0.0 or e["left"] > 0 or self.t - e["aim"] < 0.4
        if e["moving"]:
            rush = e.get("kind") in ("rusher", "breacher")
            spd = 4.4 if rush else 3.0
            sp_k = 0.6 if rush else 0.0
            phase = (e.get("gait", self.t * 3.1) / gait_cycle_m(spd, sp_k) * math.tau
                     + e["slot"] * 1.37)
            lower = locomotion_pose(spd, 0.0, phase, sprint=sp_k)
            upper = blend(POSES["stand"], "aim", 0.85) if aiming else POSES["ready"]
            pose = mask_pose(lower, upper)
            pose["body_r"] = lower.get("body_r", 0.0)
            pose["spine"] = upper.get("spine", 6.0) + lower.get("spine", 0.0) * 0.45
            pose["spine_r"] = lower.get("spine_r", 0.0) * 0.8
            pose["twist"] = lower.get("twist", 0.0) * 0.65
            pose["head_y"] = -pose["twist"] * 0.8
            return pose
        if aiming:
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
                if fall is not None and fall.rest is not None:
                    if not r.visible_sphere((x, y + 0.3, z), 1.8):
                        continue
                if fall is None:
                    ux, uz = e.get("fall_dir", (0.0, 0.0))
                    track = D.track_for(e.get("dead_pose") == "dead_back", e["slot"])
                    bw = getattr(self.world, "box_world", None)
                    boxes = self.world.ragdoll_boxes() if hasattr(self.world, "ragdoll_boxes") else ()
                    fall = e["fall"] = D.Fall(_w.hum(gk, True), e.get("pose") or POSES["stand"],
                                              track, (x, y, z), e["yaw"],
                                              (ux * GUARD_PUSH_M, uz * GUARD_PUSH_M), e["slot"],
                                              box_world=bw, boxes=boxes,
                                              **(e.get("death_ctx") or {}))
                pose, root, yaw = fall.at(self.t - e["dead_t"], self._floor)
                _w.actor(r, gk, pose, root, yaw, int(tm), seed=100 + e["slot"], amp=0.0,
                         rifle_on=fall.rifle_on, hd=True, expression=fall.expression,
                         shadow=_GROUND_SHADOW)
                fall.draw_gun(r)
                e["rest"] = fall.chest
                if e["mags"] and fall.rest is not None:
                    a = e["slot"] * 1.9
                    mx = fall.chest[0] + math.cos(a) * 0.42
                    mz = fall.chest[1] + math.sin(a) * 0.42
                    my = self._floor(mx, mz)
                    _w.add(r, _shell_drop_mesh(mx, my, mz, e["yaw"] + 35.0))
                continue
            pose = self._guard_pose(e)
            pose = _held(_w.hum(gk, True), pose, "rifle", "ready", gk)
            stag = max(0.0, 1.0 - (self.t - e["hit_t"]) / 0.3)
            if stag > 0.0:
                # after the hold: rifle_p follows the spine one to one in the
                # solve, so the flinch needs no fresh IK solve per frame
                pose = dict(pose, spine=pose.get("spine", 8) - 12.0 * stag)
                pose["rifle_p"] = pose.get("rifle_p", 0.0) - 12.0 * stag
            e["pose"] = pose
            joints = _w.actor(r, gk, pose, (x, y, z), e["yaw"], int(tm), seed=100 + e["slot"],
                              amp=0.4, rifle_on=True, hd=True, shadow=_GROUND_SHADOW)
            m = joints.get("muzzle") if joints else None
            if m is not None and e["tele"] > 0.0:
                r.add_sprite(m, _fx.glow((255, 70, 50), 0.14, tm, seed=e["slot"], core=(255, 120, 90),
                                         intensity=0.8), layer=_fx.FX_LAYER)

    def _draw_fx(self, r, tm):
        from engine3d.particles import PKIND_DUST, PKIND_SPARK
        r.light_cap = 64
        r.wetness = 0.25
        r.height_fog = (0.026, 0.0, 1.6, (16, 18, 24))
        now = self.t
        use_gpu = getattr(r, "backend", "") == "gl"
        if use_gpu and self._muzzle and now - self.last_fire < 0.03:
            if getattr(self, "_fx_muzzle_t", -1.0) != self.last_fire:
                self._fx_muzzle_t = self.last_fire
                pool = getattr(self, "_fx_pool", None)
                if pool is None:
                    from engine3d.particles import ParticlePool
                    pool = self._fx_pool = ParticlePool(1024, seed=707)
                pool.burst_muzzle(self._muzzle, _fwd(self.yaw, self.pitch), n=5)
        if use_gpu and getattr(self, "_fx_pool", None) is not None:
            dt = max(0.0, min(0.05, now - getattr(self, "_fx_last_t", now)))
            self._fx_last_t = now
            self._fx_pool.update(dt, floor_y=0.0)
            self._fx_pool.submit(r)
        for t0, a, b, col in self.tracers:
            k = (now - t0) / 0.06
            head, tail = min(1.0, k), max(0.0, k - 0.35)
            if tail < 1.0:
                pa = tuple(a[i] + (b[i] - a[i]) * tail for i in range(3))
                pb = tuple(a[i] + (b[i] - a[i]) * head for i in range(3))
                r.add_line3d(pa, pb, col, 2, layer=3)
        if use_gpu:
            rows = []
            for t0, p in self.sparks:
                age = now - t0
                if 0.0 <= age < 0.42:
                    u = age / 0.42
                    for i in range(8):
                        ang = i * 2.39996 + t0 * 11.0
                        vx, vy, vz = math.cos(ang) * 2.4, 1.5 + (i % 3) * 0.7 - 9.8 * age, math.sin(ang) * 2.4
                        rows.append((p[0] + vx * age, max(0.02, p[1] + vy * age), p[2] + vz * age,
                                     vx, vy, vz, 1.0, 0.80, 0.46, 1.0 - u, 0.055, float(PKIND_SPARK), u, float(i)))
            for t0, p, kind in self.impacts:
                age = now - t0
                if 0.0 <= age < 0.36:
                    u = age / 0.36
                    c = (0.68, 0.10, 0.09) if kind == "blood" else (0.86, 0.80, 0.68)
                    for i in range(6):
                        ang = i * 1.047 + t0 * 9.0
                        sp = 1.1 + (i % 2) * 0.5
                        rows.append((p[0] + math.cos(ang) * sp * age, max(0.02, p[1] + 0.5 * age),
                                     p[2] + math.sin(ang) * sp * age, 0.0, 0.2, 0.0,
                                     c[0], c[1], c[2], (1.0 - u) * 0.72, 0.10 + 0.22 * u, float(PKIND_DUST), u, float(i)))
            if rows:
                import numpy as np
                r.add_particles(np.asarray(rows, dtype=np.float32))
        else:
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
        for idx, (t0, pos, rad, col, vel, life) in enumerate(getattr(self, "well_dust", ())):
            age = now - t0
            if 0.0 <= age < life:
                u = age / life
                env = _ease(clamp(u / 0.18, 0.0, 1.0)) * (1.0 - _ease(clamp((u - 0.35) / 0.65, 0.0, 1.0)))
                if env > 0.01:
                    d_pos = (
                        pos[0] + vel[0] * age,
                        max(0.08, pos[1] + vel[1] * age),
                        pos[2] + vel[2] * age,
                    )
                    r.add_sprite(
                        d_pos,
                        _fx.haze(col, rad * (0.65 + 0.95 * u), tm, seed=740 + idx * 7,
                                 intensity=0.44 * env),
                        layer=_fx.FX_LAYER,
                    )
        pool = getattr(self, "_debris_pool", None)
        if pool and pool.items:
            dm = Mesh()
            for db in pool.items:
                hx, hy, hz = db.half
                dm.add(box(hx * 2.0, hy * 2.0, hz * 2.0, db.col),
                       m_mul(rot_y(db.rot[1]), rot_x(db.rot[0])), t=tuple(db.pos))
            _w.add(r, dm)


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