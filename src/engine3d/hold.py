"""Weapon holds and arm-vs-body safety for the box rig (engine3d.rig.Humanoid).

One shared path for every cutscene and guard: the gun frame follows the posed
torso, both hands are solved onto the gun by engine3d.ik, and each arm picks
the elbow swivel that stays out of the body. Output is ordinary pose keys.

  body_volumes(hum, pose, pos, yaw)        torso/chest/pelvis/head boxes, world
  arm_clash(hum, pose, pos, yaw, side)     deepest arm point inside the body (m)
  solve_arm_safe(hum, pose, pos, yaw, side, target, poles=None)
  hold_weapon(hum, pose, pos, yaw, weapon, mode, aim=None)  -> pose
  hold_frame(...)                          -> (pose, origin, basis) for guns
                                              drawn apart from the rig rifle
  hold_report(hum, pose, pos, yaw, weapon) support-hand gap, arm/rifle depth

Gun space is (right, up, forward) in metres with the rig rifle's origin on the
right hand; GRIPS lists the points the hands and butt use. Modes: aim (butt in
the shoulder pocket, barrel on ``aim``), ready (low ready), port (across the
chest, muzzle up-left), carry (front-of-body patrol), one_hand (right hand
only, the other arm is left as authored).
"""
import math
from collections import namedtuple

from . import ik
from .core import m_apply
from .ik import (_add, _dot, _full, _hold_frames, _len, _norm, _rifle_axes, _root,
                 _scale, _stock, _strip, _sub, _t, _wrap)

__all__ = ["hold_cached", "Box", "GRIPS", "MODES", "POLES", "POLES_WIDE", "arm_clash", "body_volumes", "hold_frame",
           "hold_report", "hold_weapon", "push_out", "solve_arm_safe"]

Box = namedtuple("Box", "M org c half sc2")

# elbow poles, torso-local with +x OUTWARD from that side (mirrored for the left)
POLES = ((0.8, -1.0, -0.1),      # out-down
         (0.6, -1.0, -0.7),      # out-down-back
         (-0.4, -1.0, 0.15),     # cross-low
         (1.0, -0.2, 0.0))       # out, raised
# tried only when the four above all clash (arm folded across a twisted torso)
POLES_WIDE = ((1.0, 0.0, -1.0), (1.0, 0.0, 0.0), (1.0, 0.6, -0.3), (0.0, -1.0, -1.0),
              (1.0, -1.0, -1.0), (0.3, 0.3, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.8))
POLE_R, POLE_L = (0.8, -1.0, -0.1), (0.4, -1.0, 0.0)

# mirrored from missions.m6.yard3d (the engine never imports game code)
_K9 = dict(grip=(0.012, -0.100, -0.105), fore=(-0.006, 0.035, 0.195),
           guard=(-0.006, 0.020, 0.070), butt=(0.0, 0.0, -0.437))
_RIG = dict(grip=(0.0, 0.0, 0.0), fore=(0.0, -0.035, 0.30), guard=(0.0, -0.035, 0.18),
            butt=None)
# mirrored from game/content/meshes/m7rifle.mesh.json meta (tools/ae_import_m7rifle.py)
# ``pocket`` is added to the mode's shoulder pocket: this stock is deep, so it
# rides out on the shoulder instead of in the chest.
_M7 = dict(grip=(0.0, 0.0, 0.0), fore=(0.0, 0.038, 0.258), guard=(0.0, 0.038, 0.110),
           butt=(0.0, 0.025, -0.243), pocket=(0.11, 0.0, 0.0))
# mirrored from game/content/meshes/akrifle.mesh.json meta (tools/ae_import_akrifle.py)
_AK = dict(grip=(0.0, 0.0, 0.0), fore=(0.0, 0.0235, 0.2835), guard=(0.0, -0.0109, 0.1065),
           butt=(0.0, 0.0038, -0.2857))
# mirrored from game/content/meshes/ak74.mesh.json meta (tools/ae_build_ak74.py)
# The authored AK-74 is a real 0.940 m 6P20, so its stock reaches 24 mm further
# back than the imported asset's; the deeper butt is what puts the length of
# pull at 0.355 m instead of 0.30 m.
_AK74 = dict(grip=(0.0, 0.0, 0.0), fore=(0.0, 0.029, 0.3125), guard=(0.0, 0.01, 0.07),
             butt=(0.0, -0.007, -0.31))
_SG = dict(grip=(0.0, 0.0, 0.0), fore=(0.0, 0.025, 0.33), guard=(0.0, 0.025, 0.20),
           butt=(0.0, 0.045, -0.40))
GRIPS = {"rifle": _RIG, "sniper": dict(_RIG, fore=(0.0, -0.035, 0.34), guard=(0.0, -0.035, 0.20)),
         "os12": _RIG, "k9": _K9, "shotgun": _SG, "m7rifle": _M7, "akrifle": _AK,
         "ak74": _AK74,
         # the support hand cups the shooting hand from the left of the grip
         "pistol": dict(grip=(0.0, 0.0, 0.0), fore=(-0.045, -0.025, 0.0),
                        guard=(-0.045, -0.025, 0.0), butt=None)}

# anchor "butt": butt point sits ``pocket`` from the right shoulder (torso-local);
# anchor "grip": the right hand sits at ``at`` (torso-local, origin at the hip).
# ``aim`` is a torso-local barrel direction used when no world target is given.
MODES = {
    "aim": dict(anchor="butt", pocket=(-0.05, -0.03, 0.05), aim=None, two=True),
    "ready": dict(anchor="butt", pocket=(-0.04, -0.08, 0.08), aim=(-0.14, -0.42, 0.9), two=True),
    "port": dict(anchor="grip", at=(0.10, 0.34, 0.26), aim=(-0.55, 0.65, 0.5), two=True),
    "carry": dict(anchor="grip", at=(0.20, 0.18, 0.24), aim=(-0.10, -0.30, 1.0), two=True),
    "one_hand": dict(anchor="grip", at=(0.24, 0.10, 0.20), aim=(0.0, -0.55, 1.0), two=False),
    # handguns: no stock, so the grip is the anchor. Isosceles stance with both
    # arms out and the hands on the centre line at chin height; low ready
    # points the muzzle at the floor a few metres ahead.
    "pistol_aim": dict(anchor="grip", at=(0.03, 0.50, 0.46), aim=(0.0, 0.0, 1.0), two=True),
    "pistol_ready": dict(anchor="grip", at=(0.04, 0.30, 0.34), aim=(0.0, -0.55, 1.0), two=True),
}
ARM_REACH = 0.58            # shoulder to hand, a touch short of straight
_TORSO = ("torso", "chest", "pelvis")


def _lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t)


def _depth(box, p, margin=0.0):
    """Penetration of world point ``p`` into ``box`` (0 = outside)."""
    q = m_apply(_t(box.M), _sub(p, box.org))
    d = min(box.half[i] + margin - abs(q[i] / box.sc2 - box.c[i]) for i in range(3))
    return max(0.0, d)


def _state(hum, pose, pos, yaw):
    p = _full(pose)
    places, joints, root = hum.pose_world(p, pos, yaw, rifle_on=True)
    return p, places, joints, root, _volumes(hum, places, root)


def _volumes(hum, places, root):
    sc2 = hum._scale * hum._scale
    spec = hum.spec
    nw = float(spec.get("bulk", 0.9 if spec.get("narrow") else 1.0))
    hw = float(spec.get("head_w", 1.0))
    pl = {s: (M, o) for s, _k, M, o, _g, _f in places}

    def box(slot, c, half):
        M, o = pl[slot]
        return Box(M, _add(root, o), c, half, sc2)

    chest = ((0.0, 0.36, 0.0), (0.21 * nw, 0.20, 0.14)) if spec.get("vest") is None \
        else ((0.0, 0.34, 0.0), (0.22 * nw, 0.17, 0.15))
    return {"torso": box(1, (0.0, 0.30, 0.0), (0.20 * nw, 0.26, 0.12)),
            "chest": box(1, *chest),
            "pelvis": box(0, (0.0, 0.0, 0.0), (0.17, 0.09, 0.11)),
            "head": box(2, (0.0, 0.13, 0.01), (0.10 * hw, 0.12, 0.11))}


def body_volumes(hum, pose, pos, yaw):
    """-> {name: Box} in world space for torso, chest (vest/suit), pelvis, head."""
    return _state(hum, pose, pos, yaw)[4]


def push_out(vols, p, margin=0.03):
    """Move world point ``p`` out of the torso volumes along their shallowest axis."""
    for name in _TORSO:
        b = vols[name]
        q = [v / b.sc2 for v in m_apply(_t(b.M), _sub(p, b.org))]
        room = [b.half[i] + margin - abs(q[i] - b.c[i]) for i in range(3)]
        if min(room) <= 0:
            continue
        k = room.index(min(room))
        sign = 1.0 if q[k] - b.c[k] >= 0 else -1.0
        q[k] = b.c[k] + sign * (b.half[k] + margin)
        p = _add(b.org, m_apply(b.M, tuple(q)))
    return p


def _arm_points(places, joints, root, side):
    ua, fa = (4, 6) if side == "l" else (10, 12)
    org = {s: o for s, _k, _M, o, _g, _f in places}
    sh, el = _add(root, org[ua]), _add(root, org[fa])
    hd = joints[side + "hand"]
    return ([_lerp(sh, el, t) for t in (0.4, 0.7)] + [el]
            + [_lerp(el, hd, t) for t in (0.25, 0.5, 0.75, 1.0)])


def _clash(vols, pts, margin):
    return max(_depth(vols[n], q, margin) for n in _TORSO for q in pts)


def arm_clash(hum, pose, pos, yaw, side, margin=0.0):
    """Deepest point (metres) of the ``side`` elbow/forearm/hand inside the body."""
    _p, places, joints, root, vols = _state(hum, pose, pos, yaw)
    return _clash(vols, _arm_points(places, joints, root, side), margin)


_ARM_KEYS = ("sh_p", "sh_r", "sh_y", "el")


def solve_arm_safe(hum, pose, pos, yaw, side, target, poles=None, margin=0.02):
    """-> pose copy with the ``side`` hand on ``target`` (pushed out of the
    torso first) and the elbow swivel that clashes least with the body.

    ``poles`` is tried in order (torso-local, +x outward); the first that does
    not touch the body wins, else the lowest clash plus distance from ``pose``."""
    sx = -1 if side == "l" else 1
    base, _pl, _j, _r, vols = _state(hum, pose, pos, yaw)
    best = None
    # a target the straightened arm can only reach through the chest is moved
    # off the torso in widening steps (the hand falls a few cm short of it)
    for pm in (0.03, 0.06, 0.10):
        goal = push_out(vols, target, pm)
        for i, pl in enumerate(tuple(poles or POLES) + POLES_WIDE):
            q = ik.solve_arm(hum, pose, pos, yaw, side, goal, (pl[0] * sx, pl[1], pl[2]))
            qf = _full(q)
            c = arm_clash(hum, qf, pos, yaw, side, margin)
            if c <= 0.0:
                return q
            dist = sum(abs(_wrap(qf[side + k] - base[side + k])) for k in _ARM_KEYS)
            s = c + 0.0004 * dist + 0.003 * i
            if best is None or s < best[0]:
                best = (s, q, c)
        if best[2] <= 0.012:
            break
    return best[1]


def weapon_of(hum):
    """GRIPS key for the rifle on ``hum`` (``hum._weapon`` overrides the spec)."""
    w = getattr(hum, "_weapon", None) or hum.spec.get("rifle")
    return w if w in GRIPS else "rifle"


def _grips(hum, weapon):
    g = dict(GRIPS[weapon])
    if weapon in ("rifle", "sniper", "os12"):
        g["butt"] = (0.0, 0.0, -_stock(hum))
    return g


def hold_frame(hum, pose, pos, yaw, weapon="rifle", mode="aim", aim=None):
    """-> (pose, origin, basis). ``origin``/``basis`` place the gun in world
    space (basis rows right, up, forward as a rig matrix; origin = gun-space 0).
    ``aim`` is a world point the barrel points at, else the mode's own aim."""
    g, ms = dict(_grips(hum, weapon)), MODES[mode]
    p = _full(pose)
    sc = hum._scale
    O = R = None
    for _ in range(2):
        B0, S, sh, _eye = _hold_frames(hum, p, pos, yaw)
        if ms["anchor"] == "butt":
            anchor = _add(sh, m_apply(S, _scale(_add(ms["pocket"], g.get("pocket", (0.0, 0.0, 0.0))), sc)))
        else:
            anchor = _add(_root(hum, p, pos, yaw), m_apply(S, _scale(ms["at"], sc)))
        if aim is not None:
            ad = _norm(_sub(aim, anchor))
        elif ms["aim"] is not None:
            ad = m_apply(S, _norm(ms["aim"]))
        else:
            ad = m_apply(S, (0.0, 0.0, 1.0))
        R = _rifle_axes(p, B0, ad)
        ref = g["butt"] if ms["anchor"] == "butt" and g["butt"] else g["grip"]
        O = _sub(anchor, m_apply(R, ref))
        two = ms["two"] and g["fore"] is not None
        shl = ik.shoulder_world(hum, p, pos, yaw, "l")
        reach = ARM_REACH * sc
        # move the whole gun into both arms' shared reach (never clamp one hand)
        for _i in range(16):
            for pt, shd in ((g["grip"], sh), (g["guard"] if two else None, shl)):
                if pt is None:
                    continue
                w = _add(O, m_apply(R, pt))
                d = _len(_sub(w, shd))
                if d > reach:
                    O = _add(O, _scale(_sub(shd, w), (d - reach) / d))
        grip = _add(O, m_apply(R, g["grip"]))
        poles_r = (POLE_R,) + POLES
        p = _full(solve_arm_safe(hum, p, pos, yaw, "r", grip, poles_r))
        if two:
            lt = _add(O, m_apply(R, g["fore"]))
            guard = _add(O, m_apply(R, g["guard"]))
            for _i in range(8):
                if _len(_sub(lt, shl)) <= ARM_REACH * sc:
                    break
                lt = _lerp(lt, guard, 0.4)
            p = _full(solve_arm_safe(hum, p, pos, yaw, "l", lt, (POLE_L,) + POLES))
    return _strip(p, pose), O, R


def hold_weapon(hum, pose, pos, yaw, weapon="rifle", mode="aim", aim=None):
    """-> pose copy holding ``weapon`` in ``mode``; rifle_p/rifle_y match the gun."""
    return hold_frame(hum, pose, pos, yaw, weapon, mode, aim)[0]


def _seg_dist(p, a, b):
    ab = _sub(b, a)
    t = max(0.0, min(1.0, _dot(_sub(p, a), ab) / max(_dot(ab, ab), 1e-12)))
    return _len(_sub(p, _add(a, _scale(ab, t))))


def hold_report(hum, pose, pos, yaw, weapon="rifle"):
    """-> dict(support=left hand to the fore-end/handguard segment,
    arm=deepest arm point in the body, rifle=deepest barrel point in the body);
    all metres. support/rifle are None when the rig carries no rifle."""
    p, places, joints, root, vols = _state(hum, pose, pos, yaw)
    arm = max(_clash(vols, _arm_points(places, joints, root, s), 0.0) for s in "lr")
    out = dict(support=None, arm=arm, rifle=None)
    R = joints.get("rifle_m")
    if R is None:
        return out
    g = GRIPS[weapon]
    hand = joints["rhand"]
    if g["fore"] is not None:
        a = _add(hand, m_apply(R, _sub(g["guard"], g["grip"])))
        b = _add(hand, m_apply(R, _sub(g["fore"], g["grip"])))
        out["support"] = _seg_dist(joints["lhand"], a, b)
    pts = [_add(hand, m_apply(R, (0.0, 0.0, z))) for z in (0.0, 0.13, 0.26, 0.39, 0.52, 0.65, 0.78)]
    out["rifle"] = max(_depth(vols[n], q, 0.0) for n in ("torso", "chest", "head") for q in pts)
    return out


_HOLD_KEYS = ("lsh_p", "lsh_r", "lsh_y", "lel", "rsh_p", "rsh_r", "rsh_y", "rel", "rifle_p", "rifle_y")
# Legs never reach the arm solve (it runs at the origin and clashes against
# torso, chest, pelvis and head only), so a running stride must not miss.
_LEG_KEYS = frozenset(("lhip_p", "lhip_r", "rhip_p", "rhip_r", "lkn", "rkn", "lank", "rank",
                       "lift"))
_CACHE = {}


def hold_cached(hum, pose, weapon, mode, aim=None, key=None):
    """hold_weapon for per-frame callers: the arm solve is keyed on the body pose
    rounded to whole degrees, so a held stance costs one solve, not one per frame.

    A generic ``rifle`` request resolves to the rig's own grip set, so an
    imported mesh (the shared AK) is never solved against the box gun's
    fore-end."""
    if weapon == "rifle":
        weapon = weapon_of(hum)
    body = tuple(sorted((k, round(v)) for k, v in pose.items()
                        if k not in _HOLD_KEYS and k not in _LEG_KEYS
                        and isinstance(v, (int, float))))
    ck = (key if key is not None else id(hum), weapon, mode, aim, body)
    arms = _CACHE.get(ck)
    if arms is None:
        if len(_CACHE) > 512:
            _CACHE.clear()
        out = hold_weapon(hum, pose, (0.0, 0.0, 0.0), 0.0, weapon, mode, aim)
        arms = {k: out[k] for k in _HOLD_KEYS if k in out}
        _CACHE[ck] = arms
    return dict(pose, **arms)
