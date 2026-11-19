"""Shared 3D ally-revive choreography for M7 Raid, M8 Trap, and M8 Mansion.

Drives both characters through a four-stage tactical pull-up:
  1. Step-in & drop (0.00..0.24): Biribel closes safely to ~0.92 m, cradles
     the long gun down at the right hip, and drops into a braced lunge while
     the downed ally plants their left hand and reaches up with their right.
  2. Clasp & coil (0.24..0.42): World-space IK locks Biribel's left hand onto
     the ally's right wrist/hand as both compress for the lift.
  3. Haul & rise (0.42..0.84): Biribel drives back through the legs and torso,
     hauling the ally from seated slump onto staggered feet while keeping both
     hands locked together.
  4. Release & follow-through (0.84..1.00 + post-revive settle): Hands unclasp,
     the ally recovers their weapon into ready stance, and Biribel smoothly
     re-shoulders the gun (cancelled immediately by fire, reload, or swap).
"""
import math

from engine3d import POSES, blend, clamp
from engine3d.core import Mesh, m_mul, rot_y, rot_z
from engine3d.hold import POLES, solve_arm_safe as _solve_arm_safe
from engine3d.rig import os12_mesh as _os12_mesh, rifle_mesh as _rifle_mesh

from . import m6world3d as _w

REVIVE_DIST = 0.92
PLAYER_RECOVER_S = 0.40
ALLY_RECOVER_S = 0.55

_L_ARM = ("lsh_p", "lsh_r", "lsh_y", "lel")
_R_ARM = ("rsh_p", "rsh_r", "rsh_y", "rel")
_ARMS_AND_BODY = _L_ARM + _R_ARM + (
    "spine", "spine_r", "twist", "head_p", "head_y",
    "lhip_p", "lhip_r", "lkn", "lank",
    "rhip_p", "rhip_r", "rkn", "rank",
    "rifle_p", "rifle_y", "body_p", "body_r", "lift",
)

_GROUND_GUNS = {}


def _wrap(deg):
    return (deg + 180.0) % 360.0 - 180.0


def _yaw(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def _ease(k):
    u = clamp(k, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def _blend_pose(a, b, k, keys=None):
    u = clamp(k, 0.0, 1.0)
    out = dict(a)
    scan = keys if keys is not None else (set(a) | set(b))
    for kn in scan:
        va = float(a.get(kn, 0.0))
        vb = float(b.get(kn, 0.0))
        if kn in ("rifle_y", "lsh_y", "rsh_y", "head_y", "twist"):
            out[kn] = va + _wrap(vb - va) * u
        else:
            out[kn] = va + (vb - va) * u
    return out


class ReviveState:
    __slots__ = (
        "who", "u", "vis_w", "locking", "hand_world",
        "ally_pos", "ally_yaw", "recover_t0", "recover_sg",
        "kick_done", "last_t", "holds",
    )

    def __init__(self):
        self.clear()

    def clear(self):
        self.who = None
        self.u = 0.0
        self.vis_w = 0.0
        self.locking = False
        self.hand_world = None
        self.ally_pos = None
        self.ally_yaw = 0.0
        self.recover_t0 = -9.0
        self.recover_sg = False
        self.kick_done = False
        self.last_t = 0.0
        # True while the revive is the owner of ``scene.hold`` (the same scalar
        # the scene's own hold actions use, e.g. the M8 trap climb).
        self.holds = False


def ensure(scene):
    st = getattr(scene, "_revive", None)
    if st is None or st.last_t > scene.t + 0.05:
        st = ReviveState()
        scene._revive = st
    st.last_t = scene.t
    return st


def reset(scene):
    st = ReviveState()
    st.last_t = getattr(scene, "t", 0.0)
    scene._revive = st
    return st


def warm():
    if "os12" not in _GROUND_GUNS:
        _GROUND_GUNS["os12"] = _os12_mesh(with_mag=True)
    if "rifle" not in _GROUND_GUNS:
        _GROUND_GUNS["rifle"] = _rifle_mesh(col=(32, 34, 36), accent=(92, 60, 38))


def is_locking(scene):
    if getattr(scene, "dying", False) or getattr(scene, "turn", None) is not None:
        return False
    st = getattr(scene, "_revive", None)
    return bool(st is not None and st.locking)


def is_reviving(scene, name):
    st = getattr(scene, "_revive", None)
    return bool(st is not None and st.who == name and st.vis_w > 0.005)


def _ally_dict(scene, who):
    b = getattr(scene, "brain", None)
    if b is None:
        return None
    return getattr(b, who, None)


def _cancel_player_busy(scene):
    if getattr(scene, "reloading", 0.0) > 0.0:
        scene.reloading = 0.0
        scene._reload_n = 0
        scene._reload_dry = False
        scene._pump_done = False
        ctl = scene._anim_ctl() if hasattr(scene, "_anim_ctl") else None
        if ctl is not None:
            ctl.cancel_reload()
    if getattr(scene, "swapping", 0.0) > 0.0:
        scene.swapping = 0.0
        scene._swap_snd_at = 1e9
        scene._swap_from = getattr(scene, "weapon", "shotgun")
        scene._swap_to = scene._swap_from


def step(scene, dt, who, held, hold_dur, on_complete):
    """Advance active ally-revive timing, step-in positioning, and completion."""
    st = ensure(scene)
    a = _ally_dict(scene, who) if who else None
    active = bool(
        who and held and a is not None
        and a.get("state") == "down"
        and not getattr(scene, "dying", False)
        and getattr(scene, "turn", None) is None
    )
    if active:
        _cancel_player_busy(scene)
        scene.aiming = False
        scene.firing = False
        scene.sprint = False
        if st.who != who:
            st.u = 0.0
            st.kick_done = False
        st.who = who
        st.locking = True
        st.vis_w = min(1.0, st.vis_w + dt * 9.5)
        st.ally_pos = (a["x"], a.get("y", 0.0), a["z"])

        dx, dz = scene.px - a["x"], scene.pz - a["z"]
        d = math.hypot(dx, dz)
        if d > 1e-4:
            ux, uz = dx / d, dz / d
        else:
            yr = math.radians(scene.body_yaw)
            ux, uz = -math.sin(yr), -math.cos(yr)
        tx, tz = a["x"] + ux * REVIVE_DIST, a["z"] + uz * REVIVE_DIST
        pull_k = min(1.0, dt * 8.0)
        nx, nz = scene.world.move(scene.px, scene.pz, (tx - scene.px) * pull_k, (tz - scene.pz) * pull_k)
        scene.px, scene.pz = nx, nz
        if hasattr(scene.world, "surface_y"):
            try:
                scene.py = scene.world.surface_y(scene.px, scene.pz, getattr(scene, "py", 0.0))
            except TypeError:
                # M8 trap's surface_y takes only (x, z); mansion's optional y picks the floor.
                scene.py = scene.world.surface_y(scene.px, scene.pz)
        scene.vel = (0.0, 0.0)
        scene.pmoving = False

        want_yaw = _yaw(a["x"] - scene.px, a["z"] - scene.pz) % 360.0
        scene.body_yaw = _w.yaw_mix(scene.body_yaw, want_yaw, min(1.0, dt * 11.0))
        ally_want = _yaw(scene.px - a["x"], scene.pz - a["z"]) % 360.0
        a["yaw"] = _w.yaw_mix(a["yaw"], ally_want, min(1.0, dt * 10.0))
        st.ally_yaw = a["yaw"]

        scene.hold = getattr(scene, "hold", 0.0) + dt
        st.holds = True
        st.u = clamp(scene.hold / max(0.2, float(hold_dur)), 0.0, 1.0)
        if st.u >= 0.44 and not st.kick_done:
            st.kick_done = True
            scene.cam_kick = min(2.2, getattr(scene, "cam_kick", 0.0) + 0.38)
            impacts = getattr(scene, "impacts", None)
            if impacts is not None:
                impacts.append((scene.t, (a["x"], a.get("y", 0.0) + 0.05, a["z"]), "dust"))
        if scene.hold >= hold_dur:
            scene.hold = 0.0
            st.holds = False
            a["revived_at"] = scene.t
            st.recover_t0 = scene.t
            st.recover_sg = (getattr(scene, "weapon", "shotgun") == "shotgun")
            st.locking = False
            st.vis_w = 0.0
            st.u = 0.0
            st.who = None
            st.hand_world = None
            st.kick_done = False
            impacts = getattr(scene, "impacts", None)
            if impacts is not None:
                impacts.append((scene.t, (a["x"], a.get("y", 0.0) + 0.08, a["z"]), "dust"))
            on_complete(who)
    else:
        st.locking = False
        if st.holds:
            # Hand the shared hold scalar back empty, once, on the way out: a
            # cancel mid-revive must not leave a half-filled bar behind. A hold
            # this frame owned by the scene itself (trap climb) is left alone.
            scene.hold = 0.0
            st.holds = False
        st.vis_w = max(0.0, st.vis_w - dt * 7.5)
        if st.vis_w <= 0.005:
            st.vis_w = 0.0
            st.u = 0.0
            st.who = None
            st.hand_world = None
            st.kick_done = False


def down_pose(t, player_pos, ally_pos, ally_yaw, seed=0):
    """Living injured slump: ragged breathing, head turning to Biribel, reach cue."""
    base = dict(POSES["slump"])
    breath = math.sin(t * 2.5 + seed * 1.3)
    wince = math.sin(t * 1.1 + seed * 2.1)
    base["spine"] = base.get("spine", 0.0) + 3.5 * breath
    base["spine_r"] = base.get("spine_r", 0.0) + 2.5 * wince
    base["head_p"] = base.get("head_p", 0.0) + 3.0 * breath

    dx = player_pos[0] - ally_pos[0]
    dz = player_pos[2] - ally_pos[2]
    dist = math.hypot(dx, dz)
    if dist < 4.5 and dist > 1e-4:
        prox = _ease((4.5 - dist) / 2.3)
        rel_yaw = clamp(_wrap(_yaw(dx, dz) - ally_yaw), -42.0, 42.0)
        base["head_y"] = base.get("head_y", 0.0) + (rel_yaw - base.get("head_y", 0.0)) * prox
        base["head_p"] = base.get("head_p", 0.0) - 12.0 * prox
        if dist < 3.2:
            reach = _ease((3.2 - dist) / 1.4)
            base["rsh_p"] = base.get("rsh_p", 0.0) + (38.0 - base.get("rsh_p", 0.0)) * reach
            base["rsh_r"] = base.get("rsh_r", 0.0) + 12.0 * reach
            base["rel"] = max(14.0, base.get("rel", 0.0) + (28.0 - base.get("rel", 0.0)) * reach)
    return base


def _ally_revive_pose(slump, u):
    """Four-stage downed-ally trajectory from seated slump to upright balance."""
    stand = dict(POSES["stand"])
    extend = dict(
        slump,
        spine=22.0, spine_r=-4.0, twist=-14.0,
        head_p=-16.0, head_y=12.0,
        rsh_p=82.0, rsh_r=10.0, rsh_y=-12.0, rel=16.0,
        lsh_p=-22.0, lsh_r=26.0, lsh_y=0.0, lel=20.0,
    )
    coil = dict(
        stand,
        body_p=-10.0, spine=30.0, spine_r=-6.0, twist=-18.0,
        head_p=-12.0, head_y=14.0,
        lhip_p=68.0, lhip_r=8.0, lkn=92.0, lank=-12.0,
        rhip_p=58.0, rhip_r=8.0, rkn=82.0, rank=-10.0,
        rsh_p=88.0, rsh_r=8.0, rsh_y=-16.0, rel=24.0,
        lsh_p=-26.0, lsh_r=28.0, lsh_y=0.0, lel=26.0,
    )
    mid_rise = dict(
        stand,
        body_p=0.0, spine=30.0, spine_r=2.0, twist=-12.0,
        head_p=6.0, head_y=10.0,
        lhip_p=46.0, lhip_r=6.0, lkn=70.0, lank=-14.0,
        rhip_p=20.0, rhip_r=5.0, rkn=36.0, rank=-8.0,
        rsh_p=76.0, rsh_r=8.0, rsh_y=-14.0, rel=34.0,
        lsh_p=12.0, lsh_r=20.0, lsh_y=0.0, lel=42.0,
    )
    stand_up = dict(
        stand,
        body_p=0.0, spine=12.0, spine_r=0.0, twist=-4.0,
        head_p=4.0, head_y=4.0,
        lhip_p=10.0, lhip_r=3.0, lkn=16.0, lank=-4.0,
        rhip_p=4.0, rhip_r=3.0, rkn=10.0, rank=-2.0,
        rsh_p=58.0, rsh_r=8.0, rsh_y=-8.0, rel=44.0,
        lsh_p=26.0, lsh_r=10.0, lsh_y=0.0, lel=62.0,
    )
    release = dict(
        stand,
        spine=6.0, twist=0.0, head_p=2.0, head_y=0.0,
        lhip_p=4.0, lkn=8.0, rhip_p=2.0, rkn=6.0,
        rsh_p=26.0, rsh_r=6.0, rel=58.0,
        lsh_p=34.0, lsh_r=8.0, lel=68.0,
    )
    if u < 0.24:
        return _blend_pose(slump, extend, _ease(u / 0.24), _ARMS_AND_BODY)
    if u < 0.42:
        return _blend_pose(extend, coil, _ease((u - 0.24) / 0.18), _ARMS_AND_BODY)
    if u < 0.65:
        return _blend_pose(coil, mid_rise, _ease((u - 0.42) / 0.23), _ARMS_AND_BODY)
    if u < 0.84:
        return _blend_pose(mid_rise, stand_up, _ease((u - 0.65) / 0.19), _ARMS_AND_BODY)
    return _blend_pose(stand_up, release, _ease((u - 0.84) / 0.16), _ARMS_AND_BODY)


def ally_pose_and_hand(scene, name, a, ally_hum, fallback_pose, ally_yaw, seed=0):
    """Return ``(pose, rifle_on, expression, hand_world)`` for an ally."""
    st = ensure(scene)
    p_pos = (scene.px, getattr(scene, "py", 0.0), scene.pz)
    a_pos = (a["x"], a.get("y", 0.0), a["z"])
    if st.who == name and st.vis_w > 0.005:
        slump = down_pose(scene.t, p_pos, a_pos, ally_yaw, seed=seed)
        rev_pose = _ally_revive_pose(slump, st.u)
        pose = _blend_pose(slump, rev_pose, _ease(st.vis_w), _ARMS_AND_BODY)
        rifle_on = (st.u >= 0.88)
        _pl, joints, _root = ally_hum.pose_world(pose, a_pos, ally_yaw, rifle_on=False)
        hand_w = joints.get("rhand") if joints else None
        st.hand_world = hand_w
        st.ally_pos = a_pos
        st.ally_yaw = ally_yaw
        expr = "worried" if st.u < 0.72 else "stern"
        return pose, rifle_on, expr, hand_w

    if a.get("state") == "down":
        slump = down_pose(scene.t, p_pos, a_pos, ally_yaw, seed=seed)
        return slump, False, "worried", None

    rev_at = a.get("revived_at", -9.0)
    post_age = scene.t - rev_at
    if 0.0 <= post_age < ALLY_RECOVER_S:
        # Smooth follow-through: steady stance -> re-shouldering fallback_pose
        steady = dict(
            POSES["stand"],
            spine=6.0, twist=0.0, head_p=2.0, head_y=0.0,
            rsh_p=26.0, rsh_r=6.0, rel=58.0,
            lsh_p=34.0, lsh_r=8.0, lel=68.0,
        )
        k = _ease(post_age / ALLY_RECOVER_S)
        return _blend_pose(steady, fallback_pose, k, _ARMS_AND_BODY), True, "stern", None

    return fallback_pose, True, None, None


def draw_ground_rifle(r, a, gun_kind="rifle"):
    """Draw a downed ally's rifle resting flat on the floor beside them."""
    key = "os12" if gun_kind == "os12" else "rifle"
    mesh = _GROUND_GUNS.get(key)
    if mesh is None:
        warm()
        mesh = _GROUND_GUNS[key]
    yaw = a.get("yaw", 0.0)
    rad = math.radians(yaw)
    # Place along the ally's right-side floor beside their hip/thigh
    gx = a["x"] + math.cos(rad) * 0.44 + math.sin(rad) * 0.14
    gz = a["z"] - math.sin(rad) * 0.44 + math.cos(rad) * 0.14
    gy = a.get("y", 0.0) + 0.045
    out = Mesh()
    out.add(mesh, m_mul(rot_y(yaw + 32.0), rot_z(90.0)), (gx, gy, gz))
    _w.add(r, out)


def _player_revive_pose(u, spine_base=0.0):
    """Biribel's athletic lunge, right-hip rifle cradle, and haul-back trajectory."""
    drop = {
        "spine": 36.0, "spine_r": -4.0, "twist": 16.0,
        "head_p": 16.0, "head_y": -14.0,
        "lhip_p": 46.0, "lhip_r": 6.0, "lkn": 68.0, "lank": -12.0,
        "rhip_p": -14.0, "rhip_r": 6.0, "rkn": 48.0, "rank": 16.0,
        "rsh_p": -14.0, "rsh_r": 16.0, "rsh_y": 0.0, "rel": 62.0,
        "lsh_p": 58.0, "lsh_r": 6.0, "lsh_y": 0.0, "lel": 22.0,
        "rifle_p": 70.0, "rifle_y": -28.0,
    }
    clasp = dict(
        drop,
        spine=38.0, twist=20.0, head_p=18.0, head_y=-16.0,
        lhip_p=52.0, lkn=76.0, rhip_p=-16.0, rkn=54.0,
        lsh_p=68.0, lel=18.0,
        rifle_p=72.0,
    )
    haul = dict(
        drop,
        spine=-4.0, spine_r=4.0, twist=-14.0,
        head_p=2.0, head_y=12.0,
        lhip_p=14.0, lkn=20.0, lank=-4.0,
        rhip_p=4.0, rkn=14.0, rank=-2.0,
        lsh_p=48.0, lsh_r=8.0, lel=84.0,
        rifle_p=30.0,
    )
    release = dict(
        POSES["ready"],
        spine=8.0, twist=0.0, head_p=4.0, head_y=0.0,
        rsh_p=-6.0, rsh_r=12.0, rel=62.0,
        lsh_p=36.0, lsh_r=8.0, lel=68.0,
        rifle_p=36.0 + spine_base, rifle_y=-18.0,
    )
    if u < 0.24:
        return _blend_pose(release, drop, _ease(u / 0.24))
    if u < 0.42:
        return _blend_pose(drop, clasp, _ease((u - 0.24) / 0.18))
    if u < 0.84:
        return _blend_pose(clasp, haul, _ease((u - 0.42) / 0.42))
    return _blend_pose(haul, release, _ease((u - 0.84) / 0.16))


def apply_player_revive(scene, hum, base_pose, at, draw_yaw, use_sg):
    """Apply Biribel's revive lunge/cradle + world-space left-arm IK clasp.

    Returns ``(pose, draw_yaw, active_bool)``.
    """
    st = ensure(scene)
    if st.vis_w > 0.005:
        w = _ease(st.vis_w)
        # Un-blade shotgun stance smoothly so Biribel squares up to the ally
        if use_sg:
            draw_yaw = _w.yaw_mix(draw_yaw, scene.body_yaw, w)
        rev_pose = _player_revive_pose(st.u, base_pose.get("spine", 0.0))
        pose = _blend_pose(base_pose, rev_pose, w, _ARMS_AND_BODY)

        # Solve world-space IK onto the ally's outstretched right hand during clasp
        if st.hand_world is not None and 0.14 <= st.u <= 0.90:
            if st.u < 0.26:
                ik_w = _ease((st.u - 0.14) / 0.12) * w
            elif st.u > 0.78:
                ik_w = (1.0 - _ease((st.u - 0.78) / 0.12)) * w
            else:
                ik_w = w
            if ik_w > 0.01:
                poles_l = ((0.45, -1.0, 0.10),) + POLES
                ik_pose = _solve_arm_safe(hum, pose, at, draw_yaw, "l", st.hand_world, poles_l)
                pose = _blend_pose(pose, ik_pose, ik_w, _L_ARM)
        return pose, draw_yaw, True

    # Post-revive weapon re-raise follow-through (cancelled if player acts)
    post_age = scene.t - st.recover_t0
    if 0.0 <= post_age < PLAYER_RECOVER_S:
        cancelled = (
            getattr(scene, "reloading", 0.0) > 0.0
            or getattr(scene, "swapping", 0.0) > 0.0
            or getattr(scene, "firing", False)
            or getattr(scene, "aiming", False)
            or getattr(scene, "crate_act", None) is not None
        )
        if cancelled:
            st.recover_t0 = -9.0
            return base_pose, draw_yaw, False
        k = 1.0 - _ease(post_age / PLAYER_RECOVER_S)
        if use_sg:
            draw_yaw = _w.yaw_mix(draw_yaw, scene.body_yaw, k)
        cradle = dict(
            base_pose,
            spine=base_pose.get("spine", 0.0) + 6.0 * k,
            rsh_p=-8.0, rsh_r=12.0, rsh_y=0.0, rel=60.0,
            lsh_p=34.0, lsh_r=8.0, lsh_y=0.0, lel=66.0,
            rifle_p=base_pose.get("spine", 0.0) + 32.0, rifle_y=-20.0,
        )
        return _blend_pose(base_pose, cradle, k, _ARMS_AND_BODY), draw_yaw, False

    return base_pose, draw_yaw, False


def adjust_camera(scene, eye, tgt, fov):
    """Smoothly drop and frame both Biribel and the ally in 3/4 profile."""
    st = getattr(scene, "_revive", None)
    if st is None or st.vis_w <= 0.005 or st.ally_pos is None:
        return eye, tgt, fov
    if getattr(scene, "dying", False) or getattr(scene, "turn", None) is not None:
        return eye, tgt, fov

    w = _ease(st.vis_w)
    py = getattr(scene, "py", 0.0)
    y_rad = math.radians(scene.yaw)
    p_rad = math.radians(scene.pitch)
    cp = math.cos(p_rad)
    f = (math.sin(y_rad) * cp, math.sin(p_rad), math.cos(y_rad) * cp)
    rg = (math.cos(y_rad), 0.0, -math.sin(y_rad))

    pivot = (scene.px, py + 1.18, scene.pz)
    right = min(1.06, max(0.0, scene.world.ray_hit(pivot, (rg[0], 0.0, rg[2]), 1.36) - 0.30))
    shoulder = (pivot[0] + rg[0] * right, pivot[1], pivot[2] + rg[2] * right)
    back = max(0.55, min(2.60, scene.world.ray_hit(shoulder, (-f[0], -f[1], -f[2]), 2.95) - 0.35))
    rev_eye = (
        shoulder[0] - f[0] * back,
        max(py + 0.38, shoulder[1] - f[1] * back),
        shoulder[2] - f[2] * back,
    )

    ax, ay, az = st.ally_pos
    mid = ((scene.px + ax) * 0.5, (py + 0.90 + ay + 0.72) * 0.5, (scene.pz + az) * 0.5)
    rev_tgt = tuple(tgt[i] + (mid[i] - tgt[i]) * 0.45 for i in range(3))

    out_eye = tuple(eye[i] + (rev_eye[i] - eye[i]) * w for i in range(3))
    out_tgt = tuple(tgt[i] + (rev_tgt[i] - tgt[i]) * w for i in range(3))
    out_fov = fov - 4.0 * w
    return out_eye, out_tgt, out_fov
