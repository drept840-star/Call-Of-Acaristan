"""Analytic two-bone IK for the box rig (engine3d.rig.Humanoid).

The rig is posed by angle dicts, so every solver here takes a pose and
returns a *new* pose with the limb keys rewritten; meshes are never touched.
Targets are world points, in the same space ``Humanoid.pose_world`` returns
joints in (pos/yaw applied, ground contact included).

  solve_arm(hum, pose, pos, yaw, side, target, pole=None)
      sets <side>sh_p, <side>sh_r, <side>sh_y, <side>el so the hand joint
      lands on ``target``; ``pole`` (torso-local direction) picks where the
      elbow points.
  solve_leg(hum, pose, pos, yaw, side, target)
      sets <side>hip_p, <side>hip_r, <side>kn so the ankle lands on
      ``target``. The hip has no yaw key, so the knee swivel is implied.
  solve_rifle_hold(hum, pose, pos, yaw, target, ...)
      a shouldered long gun: butt in the right shoulder pocket, barrel on
      ``target``, right hand on the grip, left hand on the fore-end, head
      turned down the barrel. Sets rifle_p/rifle_y plus both arms.

Out-of-reach targets straighten the limb toward them. The hand/ankle can be
the rig's lowest point (prone, kneeling hand on the floor), and ground contact
then lifts the whole body, so each solver re-solves against the new root.
"""
import math

from .core import m_apply, m_mul, rot_x, rot_y, rot_z
from .rig import NEUTRAL, solve_look

__all__ = ["solve_arm", "solve_leg", "solve_rifle_hold", "rifle_hold_gaps", "shoulder_world",
           "UARM", "FARM", "THIGH", "SHIN"]

# bone lengths (unscaled metres), mirrored from Humanoid._placements
UARM, FARM = 0.30, 0.31
THIGH, SHIN = 0.45, 0.45
_EPS = 1e-4
_PASSES = 3


def _full(pose):
    p = dict(NEUTRAL)
    p.update(pose)
    return p


def _body(p, yaw):
    return m_mul(rot_y(yaw), m_mul(rot_x(p["body_p"]), rot_z(p["body_r"])))


def _torso(p, B):
    return m_mul(B, m_mul(rot_y(p["twist"]), m_mul(rot_x(p["spine"]), rot_z(p["spine_r"]))))


def _t(m):
    return (m[0], m[3], m[6], m[1], m[4], m[7], m[2], m[5], m[8])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _scale(v, s):
    return (v[0] * s, v[1] * s, v[2] * s)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(v):
    return math.sqrt(_dot(v, v))


def _norm(v):
    n = _len(v)
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-9 else (0.0, -1.0, 0.0)


def _wrap(a):
    return (a + 180.0) % 360.0 - 180.0


def _root(hum, p, pos, yaw):
    """World offset of the body-local origin (translation + ground contact)."""
    return hum.pose_world(p, pos, yaw, rifle_on=False)[2]


def _aim_zx(w, d, cur_a, cur_p):
    """Angles (A, P) in degrees with Rz(A) . Rx(-P) . w == d.

    ``w`` lies in the yz plane and |w| == |d|. Two solutions exist; the one
    nearer the current pose (cur_a, cur_p) wins so animation stays smooth."""
    r = math.hypot(w[1], w[2])
    alpha = math.atan2(w[2], w[1])
    q = math.asin(max(-1.0, min(1.0, d[2] / r)))
    best = None
    for beta in (q, math.pi - q):
        P = math.degrees(alpha - beta)
        yp = r * math.cos(beta)
        if abs(yp) < 1e-9:
            A = cur_a
        else:
            A = math.degrees(math.atan2(-d[0] / yp, d[1] / yp))
        cost = abs(_wrap(A - cur_a)) + abs(_wrap(P - cur_p))
        if best is None or cost < best[0]:
            best = (cost, A, P)
    return best[1], best[2]


def shoulder_world(hum, pose, pos, yaw, side):
    """World position of the ``side`` ("l"/"r") shoulder joint."""
    p = _full(pose)
    sx = -1 if side == "l" else 1
    S = _torso(p, _body(p, yaw))
    sh = m_apply(S, (hum._sh * sx * hum._scale, 0.5 * hum._scale, 0.0))
    root = _root(hum, p, pos, yaw)
    return (sh[0] + root[0], sh[1] + root[1], sh[2] + root[2])


def _arm_once(hum, p, pos, yaw, side, target, pole):
    sc = hum._scale
    sx = -1 if side == "l" else 1
    Q = _torso(p, _body(p, yaw))          # orthonormal: scale is applied below
    Qt = _t(Q)
    root = _root(hum, p, pos, yaw)
    sh = m_apply(Q, (hum._sh * sx * sc, 0.5 * sc, 0.0))
    # target in torso-local, unscaled metres, shoulder at the origin
    d = _scale(m_apply(Qt, _sub(_sub(target, root), sh)), 1.0 / sc)
    D = max(abs(UARM - FARM) + _EPS, min(UARM + FARM - _EPS, _len(d)))
    dn = _norm(d)
    d = _scale(dn, D)
    ce = (D * D - UARM * UARM - FARM * FARM) / (2.0 * UARM * FARM)
    el = math.degrees(math.acos(max(-1.0, min(1.0, ce))))
    # elbow on the circle round the shoulder->hand axis, toward the pole
    a = (UARM * UARM - FARM * FARM + D * D) / (2.0 * D)
    h = math.sqrt(max(0.0, UARM * UARM - a * a))
    pole = pole or (0.45 * sx, -1.0, -0.35)
    pn = _sub(pole, _scale(dn, _dot(pole, dn)))
    if _len(pn) < 1e-6:                   # pole along the arm: any swivel works
        pn = _sub((0.0, -1.0, 0.0), _scale(dn, -dn[1]))
        if _len(pn) < 1e-6:
            pn = (0.0, 0.0, -1.0)
    elbow = _add(_scale(dn, a), _scale(_norm(pn), h))
    A, P = _aim_zx((0.0, -UARM, 0.0), elbow, p[side + "sh_r"] * sx, p[side + "sh_p"])
    # upper-arm roll: swing the bent forearm round the upper arm onto the hand
    f = _sub(d, elbow)
    Uq = m_mul(rot_z(A), rot_x(-P))
    fu = m_apply(_t(Uq), f)
    if el > 0.5:
        Y = math.degrees(math.atan2(fu[0], fu[2]))
    else:
        Y = p.get(side + "sh_y", 0.0)
    p[side + "sh_r"] = A * sx
    p[side + "sh_p"] = P
    p[side + "sh_y"] = Y
    p[side + "el"] = el


def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def solve_arm(hum, pose, pos, yaw, side, target, pole=None):
    """-> pose copy whose ``side`` hand joint sits on world ``target``.

    ``pole`` is a torso-local direction (+x = the rig's right, +y up,
    +z forward) the elbow bends toward; the default points down, out and
    a little back, like a relaxed arm."""
    p = _full(pose)
    for _ in range(_PASSES):
        _arm_once(hum, p, pos, yaw, side, target, pole)
    return _strip(p, pose)


def _leg_once(hum, p, pos, yaw, side, target):
    sc = hum._scale
    sx = -1 if side == "l" else 1
    B = _body(p, yaw)
    root = _root(hum, p, pos, yaw)
    hip = m_apply(B, (0.1 * sx * sc, -0.04 * sc, 0.0))
    d = _scale(m_apply(_t(B), _sub(_sub(target, root), hip)), 1.0 / sc)
    D = max(abs(THIGH - SHIN) + _EPS, min(THIGH + SHIN - _EPS, _len(d)))
    d = _scale(_norm(d), D)
    ck = (D * D - THIGH * THIGH - SHIN * SHIN) / (2.0 * THIGH * SHIN)
    kn = math.degrees(math.acos(max(-1.0, min(1.0, ck))))
    k = math.radians(kn)
    # hip->ankle in thigh space: the shin folds back (-z) as the knee bends
    w = (0.0, -THIGH - SHIN * math.cos(k), -SHIN * math.sin(k))
    A, P = _aim_zx(w, d, p[side + "hip_r"] * sx, p[side + "hip_p"])
    p[side + "hip_r"] = A * sx
    p[side + "hip_p"] = P
    p[side + "kn"] = kn


def solve_leg(hum, pose, pos, yaw, side, target):
    """-> pose copy whose ``side`` ankle joint sits on world ``target``."""
    p = _full(pose)
    for _ in range(_PASSES):
        _leg_once(hum, p, pos, yaw, side, target)
    return _strip(p, pose)


def _strip(p, pose):
    """Keep the caller's key set plus whatever the solver wrote."""
    return {k: v for k, v in p.items() if k in pose or k not in NEUTRAL
            or v != NEUTRAL[k]}


# right eye in the head frame (Humanoid._face_parts), metres from the neck
EYE_R = (0.048, 0.148, 0.122)


def _hold_frames(hum, p, pos, yaw):
    sc = hum._scale
    B0 = _body(p, yaw)
    S = _torso(p, B0)
    root = _root(hum, p, pos, yaw)
    sh = _add(root, m_apply(S, (hum._sh * sc, 0.5 * sc, 0.0)))
    H = m_mul(S, m_mul(rot_y(p["head_y"]), rot_x(p["head_p"])))
    neck = _add(root, _scale(m_apply(S, (p["head_x"], 0.62, 0.0)), sc))
    eye = _add(neck, _scale(m_apply(H, EYE_R), sc))
    return B0, S, sh, eye


def _rifle_axes(p, B0, aim):
    al = m_apply(_t(B0), aim)
    p["rifle_p"] = math.degrees(math.asin(max(-1.0, min(1.0, -al[1]))))
    p["rifle_y"] = math.degrees(math.atan2(al[0], al[2]))
    return m_mul(B0, m_mul(rot_y(p["rifle_y"]), rot_x(p["rifle_p"])))


def _stock(hum):
    rifle = hum._rifle      # the rifle mesh is not scaled with the body
    return -min(v[2] for v in rifle.verts) if rifle is not None else 0.34


def solve_rifle_hold(hum, pose, pos, yaw, target, fore=0.30, pocket=(-0.05, -0.03, 0.05),
                     weld=None, support_pole=(-0.6, -1.0, 0.1), grip_pole=(1.0, -0.5, -0.4),
                     look=True):
    """-> pose copy holding the rig's rifle shouldered and aimed at ``target``.

    Shoulder mode (``weld=None``): the butt sits in the right shoulder pocket
    (``pocket``: torso-local offset from the shoulder joint, metres) and the
    barrel points at ``target``.
    Cheek-weld mode (``weld=(sight_h, sight_z, relief)``): the sight line
    runs from the right eye to ``target``; the rifle hangs ``sight_h`` under
    it with its eyepiece (``sight_z`` along the gun) ``relief`` metres in
    front of the eye. The butt then lands wherever that puts it, so the torso
    pose decides how close it gets to the shoulder (see ``rifle_hold_gaps``).
    Either way the right hand goes on the grip (the rifle's origin) and the
    left on the fore-end, ``fore`` metres along the barrel. The stock length
    comes from the rifle mesh. ``look`` turns the head toward ``target``
    (solve_look's clamps)."""
    p = _full(pose)
    stock = _stock(hum)
    for _ in range(_PASSES):
        if look:
            joints = hum.pose_world(p, pos, yaw, rifle_on=False)[1]
            hy, hp = solve_look(joints["head"], target, yaw + p["twist"])
            p["head_y"] = hy
            p["head_p"] = hp - p["spine"]
        B0, S, sh, eye = _hold_frames(hum, p, pos, yaw)
        if weld is None:
            butt = _add(sh, m_apply(S, _scale(pocket, hum._scale)))
            aim = _norm(_sub(target, butt))
            R = _rifle_axes(p, B0, aim)
            grip = _add(butt, _scale(aim, stock))
        else:
            sight_h, sight_z, relief = weld
            aim = _norm(_sub(target, eye))
            R = _rifle_axes(p, B0, aim)
            grip = _sub(_add(eye, _scale(aim, relief)), m_apply(R, (0.0, sight_h, sight_z)))
        fore_pt = _add(grip, m_apply(R, (0.0, -0.035, fore)))
        _arm_once(hum, p, pos, yaw, "r", grip, grip_pole)
        _arm_once(hum, p, pos, yaw, "l", fore_pt, support_pole)
    return _strip(p, pose)


def rifle_hold_gaps(hum, pose, pos, yaw, fore=0.30, pocket=(-0.05, -0.03, 0.05),
                    weld=(0.08, 0.01, 0.07)):
    """Contact distances (metres) of a posed rifle hold, for tuning and tests.

    -> dict(butt=butt->shoulder pocket, support=left hand->fore-end,
    eye=right eye->its spot on the sight line, ``relief`` behind the eyepiece)."""
    p = _full(pose)
    _pl, j, _root_ = hum.pose_world(p, pos, yaw, rifle_on=True)
    R = j["rifle_m"]
    hand = j["rhand"]
    B0, S, sh, eye = _hold_frames(hum, p, pos, yaw)
    pk = _add(sh, m_apply(S, _scale(pocket, hum._scale)))
    butt = _add(hand, m_apply(R, (0.0, 0.0, -_stock(hum))))
    fore_pt = _add(hand, m_apply(R, (0.0, -0.035, fore)))
    want_eye = _add(hand, m_apply(R, (0.0, weld[0], weld[1] - weld[2])))
    return dict(butt=_len(_sub(butt, pk)), support=_len(_sub(j["lhand"], fore_pt)),
                eye=_len(_sub(want_eye, eye)))
