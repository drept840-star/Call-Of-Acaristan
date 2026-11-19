"""Gameplay death falls for 3D guards (Mission 7 raid, Mission 6 yard).

Active-to-passive ragdoll: hit-context-aware ballistic recoil, protective
reflexes, catch-step balance failure, wall/crate slumping, secondary head/limb
settle, and dropped-weapon continuity over ``RagdollBody`` and direct
``Humanoid`` bone placements.
"""

import math

from engine3d import POSES, blend, clamp
from engine3d.core import (
    m_apply, m_mul, rot_x, rot_y, rot_z, v_add, v_cross, v_norm, v_sub,
)
from engine.collision import RagdollBody

GRAVITY = 9.8
MAX_SUBSTEP = 1.0 / 60.0
TIP_AT = (0.30, 0.22, 0.30, 0.60)   # s: body past its feet, free to drop
LAND_AT = (0.90, 0.75, 0.90, 1.10)  # s: body meets the floor on level ground
SPIN = 75.0                         # deg: side-fall twist

_STAGGER = dict(POSES["aim"], spine=-14, head_p=-12, lsh_p=96, lsh_r=26, lel=18,
                rsh_p=90, rsh_r=40, rel=24, lhip_p=-4, lkn=14, rhip_p=6, rkn=22)
_BUCKLE = dict(POSES["slump"], spine=44, head_p=26, lsh_p=40, lsh_r=18, rsh_p=34,
               rsh_r=16)
_CLUTCH = dict(POSES["slump"], spine=22, head_p=18, lsh_p=52, lsh_r=-12, lel=78,
               rsh_p=28, rsh_r=26, rel=34)
_CLUTCH_R = dict(POSES["slump"], spine=22, head_p=18, rsh_p=52, rsh_r=-12, rel=78,
                 lsh_p=28, lsh_r=26, lel=34)
_GUT_FOLD = dict(POSES["slump"], spine=38, head_p=26, lhip_p=22, rhip_p=18,
                 lsh_p=46, lsh_r=-18, lel=92, rsh_p=24, rsh_r=36, rel=28)
_LEG_BUCKLE = dict(POSES["slump"], spine=18, head_p=14, lsh_p=32, lsh_r=36, lel=24,
                   rsh_p=32, rsh_r=36, rel=24)
_KNEEL = dict(POSES["kneel"], spine=34, head_p=30, lsh_p=14, lsh_r=10, lel=20,
              rsh_p=10, rsh_r=12, rel=24)
_UPPER_NODES = ("chest", "head", "lsh", "rsh", "lel", "rel", "lhand", "rhand")
_LEG_L = ("lhip", "lkn", "lfoot")
_LEG_R = ("rhip", "rkn", "rfoot")
_GUN_BOUNDS_CACHE = {}
_GUN_PACK_CACHE = {}


def _s(a, b, x):
    x = clamp((x - a) / (b - a), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _transpose(M):
    return (M[0], M[3], M[6], M[1], M[4], M[7], M[2], M[5], M[8])


def _ortho(M):
    x = v_norm((M[0], M[3], M[6]))
    z_raw = (M[2], M[5], M[8])
    d = x[0] * z_raw[0] + x[1] * z_raw[1] + x[2] * z_raw[2]
    z = v_norm((z_raw[0] - x[0] * d, z_raw[1] - x[1] * d, z_raw[2] - x[2] * d))
    if x == (0.0, 0.0, 0.0) or z == (0.0, 0.0, 0.0):
        return (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    y = v_cross(z, x)
    return (x[0], y[0], z[0], x[1], y[1], z[1], x[2], y[2], z[2])


def _gun_bounds(mesh):
    key = id(mesh)
    cached = _GUN_BOUNDS_CACHE.get(key)
    if cached is not None and cached[0] is mesh:
        return cached[1:]
    vs = mesh.verts
    if not vs:
        data = ((0.0, 0.0, 0.0), ((0.0, 0.0, 0.0),))
    else:
        xs = [v[0] for v in vs]
        ys = [v[1] for v in vs]
        zs = [v[2] for v in vs]
        x0, x1 = min(xs), max(xs)
        y0, y1 = min(ys), max(ys)
        z0, z1 = min(zs), max(zs)
        com = (0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1))
        corners = (
            (x0, y0, z0), (x0, y0, z1), (x0, y1, z0), (x0, y1, z1),
            (x1, y0, z0), (x1, y0, z1), (x1, y1, z0), (x1, y1, z1),
        )
        data = (com, corners)
    if len(_GUN_BOUNDS_CACHE) > 64:
        _GUN_BOUNDS_CACHE.pop(next(iter(_GUN_BOUNDS_CACHE)))
    _GUN_BOUNDS_CACHE[key] = (mesh,) + data
    return data


def _gun_packed(r, mesh):
    key = id(mesh)
    cached = _GUN_PACK_CACHE.get(key)
    if cached is not None and cached[0] is mesh:
        return cached[1], cached[2]
    faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces]
    rows = r.pack(mesh.verts, faces)
    if len(_GUN_PACK_CACHE) > 64:
        _GUN_PACK_CACHE.pop(next(iter(_GUN_PACK_CACHE)))
    _GUN_PACK_CACHE[key] = (mesh, rows, faces)
    return rows, faces


def track_for(front, slot):
    """Death track from where the shot came: thrown back or spun from the
    front, buckled or dropped to the knees from behind."""
    if front:
        return 2 if slot % 3 == 0 else 1
    return 3 if slot % 2 else 0


def death_pose(track, a, was):
    """Pose ``a`` seconds after the kill, out of the last live pose ``was``."""
    if track == 1:
        if a < 0.18:
            return blend(was, _STAGGER, _s(0.0, 0.18, a))
        return blend(_STAGGER, POSES["dead_back"], _s(0.18, 0.75, a))
    if track == 2:
        half = blend(was, POSES["slump"], 0.5)
        if a < 0.30:
            return blend(was, half, _s(0.0, 0.30, a))
        return blend(half, POSES["dead_side"], _s(0.30, 0.90, a))
    if track == 3:
        if a < 0.55:
            p = blend(was, _KNEEL, _s(0.0, 0.40, a))
            return dict(p, spine=p["spine"] + 8.0 * math.sin(a * 9.0) * _s(0.3, 0.55, a))
        return blend(_KNEEL, POSES["dead_front"], _s(0.55, 1.10, a))
    if a < 0.35:
        return blend(was, _BUCKLE, _s(0.0, 0.35, a))
    return blend(_BUCKLE, POSES["dead_front"], _s(0.35, 0.90, a))


class Fall:
    """One ragdolled body with wall, crate, and ledge collision."""

    def __init__(self, hum, was, track, pos, yaw, push=(0.0, 0.0), slot=0,
                 *, box_world=None, boxes=(), blast=None,
                 is_head=False, hit_zone=None, hit_pos=None, hit_ray=None,
                 weapon=None, dmg=0.0, overkill=0.0, hit_dist=None):
        self.hum, self.was, self.track = hum, dict(was), track
        self.x, self.y, self.z = pos
        self.yaw0 = yaw
        self.slot = int(slot)
        self._var = (self.slot * 37) % 7
        self._side = 1.0 if self.slot % 2 == 0 else -1.0
        self._is_blast = blast is not None or weapon == "blast"
        self.is_head = bool((is_head or hit_zone == "head") and not self._is_blast)
        self.hit_zone = "head" if self.is_head else (hit_zone or "chest")
        self._weapon = weapon or "rifle"
        self._was_down = abs(float(self.was.get("body_p", 0.0))) > 45.0
        self._toppled = False
        self._relaxed = False

        # 3D shot direction + horizontal basis
        px, pz = float(push[0]), float(push[1])
        pm = math.hypot(px, pz)
        if hit_ray is not None:
            rx0, ry0, rz0 = float(hit_ray[0]), float(hit_ray[1]), float(hit_ray[2])
            rm = math.sqrt(rx0 * rx0 + ry0 * ry0 + rz0 * rz0)
            ux, uy, uz = (rx0 / rm, ry0 / rm, rz0 / rm) if rm > 1e-4 else (0.0, 0.0, 1.0)
        else:
            hx0, hz0 = (px / pm, pz / pm) if pm > 1e-4 else (math.sin(math.radians(yaw)), math.cos(math.radians(yaw)))
            ux, uy, uz = hx0, 0.0, hz0
        hm = math.hypot(ux, uz)
        hx, hz = (ux / hm, uz / hm) if hm > 1e-4 else (math.sin(math.radians(yaw)), math.cos(math.radians(yaw)))
        rx, rz = -hz, hx
        lat = ((self._var - 3) * 0.22)
        self._dir = (hx, hz, rx, rz)

        close_k = 0.0
        if self._weapon == "shotgun" and hit_dist is not None:
            close_k = clamp(1.0 - (float(hit_dist) - 1.5) / 7.5, 0.0, 1.0)
        ok_k = clamp(float(overkill) / 60.0, 0.0, 1.0)
        self._power = max(close_k, ok_k * 0.85) if not (self._is_blast or self._weapon == "melee") else 0.0

        nodes = hum.ragdoll_nodes(self.was, pos, yaw)
        self.rag = RagdollBody(nodes, drag=0.962)
        self._box_world = box_world
        self._extra_boxes = tuple(boxes)
        if self._box_world is not None or self._extra_boxes:
            self.rag.step(1e-4, floor_fn=lambda _x, _z, _y=float(pos[1]): _y,
                          box_world=self._box_world, extra_boxes=self._extra_boxes,
                          gravity=0.0, iters=3)
            self.rag.prev = {k: list(v) for k, v in self.rag.pos.items()}
            self.rag._h = MAX_SUBSTEP
            self.rag._still_t = 0.0
            self.rag.asleep = False

        # Lateral hit offset relative to actor right (+1 = right shoulder, -1 = left shoulder)
        yr = math.radians(yaw)
        arx, arz = math.cos(yr), -math.sin(yr)
        ch0 = self.rag.pos["chest"]
        if hit_pos is not None:
            lat_hit = clamp(((float(hit_pos[0]) - ch0[0]) * arx + (float(hit_pos[2]) - ch0[2]) * arz) / 0.24, -1.0, 1.0)
        else:
            lat_hit = 0.0
        if abs(lat_hit) < 0.15:
            lat_hit = self._side * 0.28
        self._lat_hit = lat_hit
        self._twist_dir = 1.0 if lat_hit >= 0.0 else -1.0
        self._hit_leg = "l" if lat_hit < 0.0 else "r"
        self._step_side = ("r" if self._hit_leg == "l" else "l") if self.hit_zone == "leg" else ("l" if self._side > 0 else "r")
        self._plant_side = "r" if self._step_side == "l" else "l"
        self._foot_anchors = {
            "l": list(self.rag.pos["lfoot"]),
            "r": list(self.rag.pos["rfoot"]),
        }
        self._relax_side = "l" if (self.slot % 2 == 0) else "r"
        self._head_yaw = 0.0
        self._head_yaw_tgt = (1.0 if (self.slot % 2 == 0) else -1.0) * (18.0 + ((self.slot * 17) % 5) * 4.5)
        self._wall_slump = False
        self.support_y = float(pos[1])

        has_rifle = getattr(hum, "_rifle", None) is not None
        self._clutch_side = "l" if (has_rifle or lat_hit < 0.15) else "r"
        self._brace_side = "r" if self._clutch_side == "l" else "l"
        self._gut_pose = _GUT_FOLD if self._clutch_side == "l" else dict(
            _GUT_FOLD, rsh_p=46, rsh_r=-18, rel=92, lsh_p=24, lsh_r=36, lel=28,
        )
        self._clutch_pose = _CLUTCH if self._clutch_side == "l" else _CLUTCH_R

        # Weapon continuity setup
        self._rifle_local = None
        self._rifle_mat = None
        self._rifle_pos = tuple(self.rag.pos["rhand"])
        self._prev_rhand = tuple(self.rag.pos["rhand"])
        self._gun = None
        if self._is_blast or self._was_down:
            self._release_at = 0.0
        elif self.is_head or self._weapon == "melee":
            self._release_at = 0.035
        elif self._power > 0.35:
            self._release_at = 0.14
        else:
            self._release_at = 0.18 + 0.04 * (self._var % 4)
        self.rifle_on = bool(has_rifle and self._release_at > 0.0)
        if has_rifle:
            _pl0, j0, _r0 = hum.pose_world(self.was, pos, yaw, rifle_on=True)
            rm0 = j0.get("rifle_m") or rot_y(yaw)
            pl_n, _jn = hum.places_from_nodes(nodes, floor_y=float(pos[1]))
            f_init = next((m for sl, _k, m, _o, _g, _fb in pl_n if sl == 12), None)
            if f_init is not None:
                sc = getattr(hum, "_scale", 1.0) or 1.0
                f0 = tuple(v / sc for v in f_init)
                self._rifle_local = m_mul(_transpose(f0), rm0)
            self._rifle_mat = rm0
            if not self.rifle_on:
                self._release_gun(lambda _x, _z, _y=float(pos[1]): _y, (0.0, 0.0, 0.0), blast=blast)

        # Hit-context-aware ballistic impulses
        if blast is not None:
            ox, oy, oz = blast[0]
            force, radius = float(blast[1]), float(blast[2])
            dx, dy, dz = self.x - ox, (self.y + 0.9) - oy, self.z - oz
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < radius:
                k = (1.0 - d / max(0.1, radius)) * force / max(0.5, d)
                sp = min(4.8, math.hypot(dx * k, dz * k) * 0.55)
                h = math.hypot(dx, dz) or 1.0
                vy = clamp((dy + 0.6) * k * 0.40, 1.4, 3.8)
                self.rag.apply_impulse((dx / h * sp, vy, dz / h * sp), node="pelvis", spread=0.85)
                self.rag.apply_impulse((rx * self._side * 1.4, 0.5, rz * self._side * 1.4), node="chest", spread=0.35)
        elif self._was_down:
            self.rag.apply_impulse((hx * 0.9, -0.4, hz * 0.9), node="chest", spread=0.30)
        elif self.is_head:
            head_sp = 4.2 if (self._weapon == "shotgun" and close_k > 0.3) else (3.4 if self._weapon == "rifle" else 2.6)
            self.rag.apply_impulse((ux * head_sp, max(0.35, uy * head_sp + 0.55), uz * head_sp),
                                   node="head", spread=0.12)
            self.rag.apply_impulse((hx * 0.75, -0.25, hz * 0.75), node="chest", spread=0.18)
            self.rag.apply_impulse((0.0, -1.15, 0.0), node="pelvis", spread=0.22)
            fx_b, fz_b = math.sin(yr), math.cos(yr)
            for kn in ("lkn", "rkn"):
                self.rag.apply_impulse((fx_b * 0.65, -0.35, fz_b * 0.65), node=kn, spread=0.05)
        elif self._weapon == "melee":
            self.rag.apply_impulse((hx * 1.9, 0.25, hz * 1.9), node="chest", spread=0.35)
            self.rag.apply_impulse((hx * 1.2, 0.35, hz * 1.2), node="head", spread=0.20)
        elif self._power > 0.35:
            punch_sp = 2.2 + 2.3 * self._power
            hit_node = "pelvis" if self.hit_zone == "gut" else "chest"
            self.rag.apply_impulse((ux * punch_sp, 0.35 * self._power + uy * 0.6, uz * punch_sp),
                                   node=hit_node, spread=0.22)
            twist_mag = (1.6 + 1.8 * self._power) * (0.4 + 0.6 * abs(lat_hit))
            s_hit = self._twist_dir
            self.rag.apply_impulse((hx * twist_mag, 0.2, hz * twist_mag),
                                   node="rsh" if s_hit > 0 else "lsh", spread=0.18)
            self.rag.apply_impulse((-hx * twist_mag * 0.65, -0.1, -hz * twist_mag * 0.65),
                                   node="lsh" if s_hit > 0 else "rsh", spread=0.18)
        elif self.hit_zone == "gut":
            self.rag.apply_impulse((hx * 1.4, -0.25, hz * 1.4), node="pelvis", spread=0.28)
            self.rag.apply_impulse((-hx * 0.35, -0.55, -hz * 0.35), node="chest", spread=0.25)
        elif self.hit_zone == "leg":
            leg_s = -1.0 if self._hit_leg == "l" else 1.0
            lsx, lsz = arx * leg_s, arz * leg_s
            self.rag.apply_impulse((hx * 1.35 + lsx * 0.45, -0.20, hz * 1.35 + lsz * 0.45),
                                   node=self._hit_leg + "kn", spread=0.32)
            self.rag.apply_impulse((lsx * 0.40, -1.25, lsz * 0.40), node="pelvis", spread=0.35)
            self.rag.apply_impulse((hx * 0.55 + lsx * 0.55, -0.35, hz * 0.55 + lsz * 0.55),
                                   node="chest", spread=0.25)
        else:
            push_sp = clamp(pm * 2.8, 1.1, 2.8) if pm > 1e-4 else 1.5
            twist_sp = 0.75 * abs(lat_hit)
            sh_hit = "rsh" if self._twist_dir > 0 else "lsh"
            if track == 1:
                self.rag.apply_impulse((hx * push_sp + rx * lat, 0.35, hz * push_sp + rz * lat),
                                       node="chest", spread=0.40)
                self.rag.apply_impulse((hx * push_sp * 0.75, 0.35, hz * push_sp * 0.75),
                                       node="head", spread=0.22)
                self.rag.apply_impulse((hx * twist_sp, 0.0, hz * twist_sp), node=sh_hit, spread=0.18)
            elif track == 2:
                self.rag.apply_impulse((hx * push_sp * 0.6 + rx * self._side * 1.6, 0.15,
                                        hz * push_sp * 0.6 + rz * self._side * 1.6),
                                       node="chest", spread=0.35)
                self.rag.apply_impulse((-rx * self._side * 1.4, -0.4, -rz * self._side * 1.4),
                                       node="pelvis", spread=0.25)
            elif track == 3:
                self.rag.apply_impulse((hx * push_sp * 0.45 + rx * lat * 0.5, -0.25,
                                        hz * push_sp * 0.45 + rz * lat * 0.5),
                                       node="chest", spread=0.32)
                self.rag.apply_impulse((hx * 0.4, -1.1, hz * 0.4), node="pelvis", spread=0.28)
            else:
                self.rag.apply_impulse((hx * push_sp * 0.75 + rx * lat, -0.35,
                                        hz * push_sp * 0.75 + rz * lat),
                                       node="chest", spread=0.38)
                self.rag.apply_impulse((-hx * 0.4, -0.9, -hz * 0.4), node="pelvis", spread=0.25)

        self.last = 0.0
        self._acc = 0.0             # unstepped time; the ragdoll runs on a fixed MAX_SUBSTEP clock
        self._sim_t = 0.0
        self._snap = None           # node positions before the last step, for display interpolation
        self.rest = None            # (pose, (x, z), yaw) once settled
        ch = self.rag.pos["chest"]
        self.chest = (ch[0], ch[2])

    def set_world(self, box_world, boxes=()):
        self._box_world = box_world
        self._extra_boxes = tuple(boxes)

    @property
    def expression(self):
        if self.is_head or self._was_down or self.rag.asleep or self.last > 0.28:
            return "closed"
        return "surprised" if self.last < 0.14 else "angry"

    def _active_pose(self, a):
        """Authored reaction pose, yaw, and (upper_tone, left_leg_tone, right_leg_tone)."""
        if self._is_blast or self._was_down:
            return None, self.yaw0, 0.0, 0.0, 0.0
        if self.is_head:
            ut = 1.0 - _s(0.0, 0.045, a)
            lt = 1.0 - _s(0.0, 0.030, a)
            return blend(self.was, POSES["slump"], _s(0.0, 0.04, a)), self.yaw0, ut, lt, lt
        if self.hit_zone == "leg":
            ut = 1.0 - _s(0.06, 0.28, a)
            lt_hit = 1.0 - _s(0.0, 0.03, a)
            lt_ok = 1.0 - _s(0.04, 0.24, a)
            lt_l, lt_r = (lt_hit, lt_ok) if self._hit_leg == "l" else (lt_ok, lt_hit)
            yaw = self.yaw0 + (-20.0 if self._hit_leg == "l" else 20.0) * _s(0.0, 0.22, a)
            return blend(self.was, _LEG_BUCKLE, _s(0.0, 0.18, a)), yaw, ut, lt_l, lt_r
        if self.hit_zone == "gut":
            dur = 0.24 + 0.08 * (self._var % 3)
            ut = 1.0 - _s(0.10, dur, a)
            lt = 1.0 - _s(0.04, dur * 0.72, a)
            yaw = self.yaw0 + self._side * 22.0 * _s(0.0, dur * 0.8, a)
            return blend(self.was, self._gut_pose, _s(0.0, 0.20, a)), yaw, ut, lt, lt
        if self._power > 0.35:
            ut = 1.0 - _s(0.04, 0.16, a)
            lt = 1.0 - _s(0.02, 0.11, a)
            tgt_p = _STAGGER if self.track in (1, 2) else _BUCKLE
            yaw = self.yaw0 + self._twist_dir * 38.0 * self._power * _s(0.0, 0.15, a)
            return blend(self.was, tgt_p, _s(0.0, 0.10, a)), yaw, ut, lt, lt
        if self._weapon == "melee":
            ut = 1.0 - _s(0.03, 0.16, a)
            lt = 1.0 - _s(0.02, 0.13, a)
            tgt_p = _STAGGER if self.track in (1, 2) else _BUCKLE
            return blend(self.was, tgt_p, _s(0.0, 0.12, a)), self.yaw0 + self._side * 18.0 * _s(0.0, 0.14, a), ut, lt, lt
        if self.track == 1:
            ut = 1.0 - _s(0.08, 0.28 + 0.06 * (self._var % 2), a)
            lt = 1.0 - _s(0.03, 0.21, a)
            yaw = self.yaw0 + self._twist_dir * 16.0 * _s(0.0, 0.20, a)
            return blend(self.was, _STAGGER, _s(0.0, 0.14, a)), yaw, ut, lt, lt
        if self.track == 2:
            ut = 1.0 - _s(0.10, 0.36, a)
            lt = 1.0 - _s(0.04, 0.24, a)
            p = blend(self.was, self._clutch_pose, _s(0.0, 0.18, a))
            yaw = self.yaw0 + self._side * 62.0 * _s(0.0, 0.28, a)
            return p, yaw, ut, lt, lt
        if self.track == 3:
            ut = 1.0 - _s(0.28, 0.50, a)
            lt = 1.0 - _s(0.32, 0.52, a)
            p = blend(self.was, _KNEEL, _s(0.0, 0.32, a))
            wob = 7.0 * math.sin(a * 11.0) * _s(0.18, 0.42, a)
            return dict(p, spine=p["spine"] + wob), self.yaw0 + self._side * 12.0 * _s(0.25, 0.50, a), ut, lt, lt
        ut = 1.0 - _s(0.06, 0.26, a)
        lt = 1.0 - _s(0.03, 0.19, a)
        return blend(self.was, _BUCKLE, _s(0.0, 0.20, a)), self.yaw0, ut, lt, lt

    def _apply_muscle_tone(self, h, a, floor):
        p_auth, yaw_tgt, ut, lt_l, lt_r = self._active_pose(a)
        pos, prev = self.rag.pos, self.rag.prev
        pel = pos["pelvis"]
        ch = pos["chest"]
        fl = max(floor(pel[0], pel[2]), self.rag.support_y)

        # Asymmetric landing relaxation & wall-slump chin droop once tone fails
        if not self._relaxed and not self._is_blast and a > 0.24 and ch[1] <= fl + 0.42:
            self._relaxed = True
            if not self._wall_slump:
                kn = self._relax_side + "kn"
                self.rag.apply_impulse((self._dir[2] * self._side * 0.30, -0.15, self._dir[3] * self._side * 0.30),
                                       node=kn, spread=0.25)

        if p_auth is None or (ut <= 0.001 and lt_l <= 0.001 and lt_r <= 0.001):
            return
        if self.track == 3 and not self._toppled and a >= 0.38:
            self._toppled = True
            ux, uz, rx, rz = self._dir
            self.rag.apply_impulse((ux * 1.5 + rx * self._side * 0.9, -0.35, uz * 1.5 + rz * self._side * 0.9),
                                   node="chest", spread=0.35)
        tgt = self.hum.ragdoll_nodes(p_auth, (0.0, 0.0, 0.0), yaw_tgt)
        tpel = tgt["pelvis"]
        h_rag = self.rag._h
        inv_h = 1.0 / h_rag
        cl = 60.0 * h  # tone clamps are m/s per 1/60 s, so they hold at any substep size

        # Impact-surface bracing: compute active bracing arm(s) first so pose-tone doesn't fight them.
        braced_nodes = set()
        if ut > 0.10 and not self.is_head and a > 0.08:
            ch_q = prev["chest"]
            cvx, cvy, cvz = (ch[0] - ch_q[0]) * inv_h, (ch[1] - ch_q[1]) * inv_h, (ch[2] - ch_q[2]) * inv_h
            ch_alt = ch[1] - fl
            wc = self.rag.wall_contact
            if wc is not None or cvy < -0.50 or ch_alt < 0.96:
                sides = ("l", "r") if self.track == 0 else (self._brace_side,)
                if wc is not None:
                    bx = ch[0] - wc[0] * 0.38
                    by_base = max(fl + 0.25, ch[1] - 0.12)
                    bz = ch[2] - wc[1] * 0.38
                else:
                    hm = math.hypot(cvx, cvz)
                    fx_h, fz_h = (cvx / hm, cvz / hm) if hm > 0.15 else (self._dir[0], self._dir[1])
                    bx = ch[0] + fx_h * 0.42
                    by_base = fl + 0.14
                    bz = ch[2] + fz_h * 0.42
                for b_side in sides:
                    sgn_b = -1.0 if b_side == "l" else 1.0
                    h_name, e_name = b_side + "hand", b_side + "el"
                    braced_nodes.add(h_name)
                    braced_nodes.add(e_name)
                    hp_b, hq = pos[h_name], prev[h_name]
                    ep, eq = pos[e_name], prev[e_name]
                    tx_b = bx + self._dir[2] * sgn_b * 0.24
                    tz_b = bz + self._dir[3] * sgn_b * 0.24
                    by = max(by_base, hp_b[1] - 0.32) if wc is None else by_base
                    for i, tv in enumerate((tx_b, by, tz_b)):
                        vel = (hp_b[i] - hq[i]) * inv_h
                        hq[i] -= clamp((95.0 * ut * (tv - hp_b[i]) - 22.0 * ut * vel) * h, -0.22 * cl, 0.22 * cl) * h_rag
                        if i == 1:
                            eq[1] -= clamp((55.0 * ut * (by + 0.18 - ep[1])) * h, -0.15 * cl, 0.15 * cl) * h_rag

        for group, tone, stiff in ((_UPPER_NODES, ut, 250.0), (_LEG_L, lt_l, 220.0), (_LEG_R, lt_r, 220.0)):
            if tone <= 0.001:
                continue
            k = stiff * tone
            d = 28.0 * tone
            for name in group:
                if name in braced_nodes:
                    continue
                if name.endswith("foot") and not self.is_head and a < 0.24:
                    continue
                p, q, tn = pos[name], prev[name], tgt[name]
                for i in range(3):
                    err = (pel[i] + (tn[i] - tpel[i])) - p[i]
                    vel = (p[i] - q[i]) * inv_h
                    dv = clamp((k * err - d * vel) * h, -0.45 * cl, 0.45 * cl)
                    q[i] -= dv * h_rag

        # Dynamic balance (skip on leg hits so the shot leg collapses instead of propping the body up)
        lt_max = max(lt_l, lt_r)
        if lt_max > 0.02 and not self.is_head and self.hit_zone != "leg":
            ux, uz, rx, rz = self._dir
            plant_k = lt_l if self._plant_side == "l" else lt_r
            if plant_k > 0.05:
                pf_name = self._plant_side + "foot"
                anc = self._foot_anchors[self._plant_side]
                pf, pq = pos[pf_name], prev[pf_name]
                if pf[1] <= fl + 0.14:
                    for i in (0, 2):
                        err = anc[i] - pf[i]
                        vel = (pf[i] - pq[i]) * inv_h
                        pq[i] -= clamp((180.0 * plant_k * err - 24.0 * plant_k * vel) * h, -0.35 * cl, 0.35 * cl) * h_rag
            step_k = lt_l if self._step_side == "l" else lt_r
            if step_k > 0.05 and 0.04 <= a <= 0.24:
                sf_name = self._step_side + "foot"
                sf, sq = pos[sf_name], prev[sf_name]
                u_step = _s(0.04, 0.22, a)
                arc = 0.11 * math.sin(math.pi * u_step)
                sgn_s = -1.0 if self._step_side == "l" else 1.0
                tx_s = pel[0] + ux * 0.34 + rx * sgn_s * 0.14
                ty_s = fl + 0.06 + arc
                tz_s = pel[2] + uz * 0.34 + rz * sgn_s * 0.14
                for i, tv in enumerate((tx_s, ty_s, tz_s)):
                    vel = (sf[i] - sq[i]) * inv_h
                    sq[i] -= clamp((210.0 * step_k * (tv - sf[i]) - 22.0 * step_k * vel) * h, -0.45 * cl, 0.45 * cl) * h_rag

            min_low = min(pos["lfoot"][1], pos["rfoot"][1], pos["lkn"][1], pos["rkn"][1])
            if min_low <= fl + 0.18:
                err_y = (fl + tpel[1]) - pel[1]
                vel_y = (pel[1] - prev["pelvis"][1]) * inv_h
                dv_y = clamp((110.0 * lt_max * err_y - 24.0 * lt_max * vel_y) * h, -0.25 * cl, 0.25 * cl)
                prev["pelvis"][1] -= dv_y * h_rag

    def _release_gun(self, floor_fn, vel_est, blast=None):
        mesh = getattr(self.hum, "_rifle", None)
        self.rifle_on = False
        if mesh is None or self._gun is not None:
            return
        ux, uz, rx, rz = self._dir
        if blast is not None:
            ox, _oy, oz = blast[0]
            dx, dz = self._rifle_pos[0] - ox, self._rifle_pos[2] - oz
            dm = math.hypot(dx, dz) or 1.0
            vx = clamp(dx / dm * 2.8 + rx * self._side * 0.6, -4.0, 4.0)
            vz = clamp(dz / dm * 2.8 + rz * self._side * 0.6, -4.0, 4.0)
            vy = 2.1
        else:
            vx = clamp(vel_est[0], -3.0, 3.0) + rx * self._side * 0.55 + ux * 0.30
            vy = clamp(vel_est[1], -2.0, 2.2) + 0.45
            vz = clamp(vel_est[2], -3.0, 3.0) + rz * self._side * 0.55 + uz * 0.30
        self._gun = {
            "pos": list(self._rifle_pos),
            "vel": [vx, vy, vz],
            "mat": self._rifle_mat or rot_y(self.yaw0),
            "ang": [190.0 * self._side, 110.0 * (1.0 if self.slot % 2 else -1.0), 230.0 * self._side],
            "settled": False,
            "settled_rows": None,
            "settled_sw": None,
            "still_t": 0.0,
            "floor_y": float(floor_fn(self._rifle_pos[0], self._rifle_pos[2])),
        }

    def _step_gun(self, h, floor_fn):
        g = self._gun
        if g is None or g["settled"]:
            return
        mesh = self.hum._rifle
        com, corners = _gun_bounds(mesh)
        pos, vel, mat, ang = g["pos"], g["vel"], g["mat"], g["ang"]
        vel[1] -= GRAVITY * h
        pos[0] += vel[0] * h
        pos[1] += vel[1] * h
        pos[2] += vel[2] * h
        dmat = m_mul(rot_y(ang[1] * h), m_mul(rot_x(ang[0] * h), rot_z(ang[2] * h)))
        mat = _ortho(m_mul(mat, dmat))

        com_w = v_add(pos, m_apply(mat, com))
        if self._box_world is not None:
            for nx, nz, pen, idx in self._box_world.capsule_contacts(
                com_w[0], com_w[2], 0.16, com_w[1] - 0.05, com_w[1] + 0.05
            ):
                if com_w[1] < self._box_world.boxes[idx][4] - 0.04:
                    pos[0] += nx * pen
                    pos[2] += nz * pen
                    vn = vel[0] * nx + vel[2] * nz
                    if vn < 0.0:
                        vel[0] -= 1.25 * vn * nx
                        vel[2] -= 1.25 * vn * nz
        for bx0, by0, bz0, bx1, by1, bz1 in self._extra_boxes:
            if by1 - 0.04 > com_w[1] and by0 < com_w[1] + 0.05:
                cx = min(max(com_w[0], bx0), bx1)
                cz = min(max(com_w[2], bz0), bz1)
                dx, dz = com_w[0] - cx, com_w[2] - cz
                d2 = dx * dx + dz * dz
                if 1e-10 < d2 < 0.16 * 0.16:
                    d = math.sqrt(d2)
                    nx, nz, pen = dx / d, dz / d, 0.16 - d
                    pos[0] += nx * pen
                    pos[2] += nz * pen
                    vn = vel[0] * nx + vel[2] * nz
                    if vn < 0.0:
                        vel[0] -= 1.25 * vn * nx
                        vel[2] -= 1.25 * vn * nz

        fl_g = float(floor_fn(com_w[0], com_w[2]))
        if self._box_world is not None:
            for _nx, _nz, _pen, idx in self._box_world.capsule_contacts(
                com_w[0], com_w[2], 0.10, com_w[1] - 0.20, com_w[1] + 0.10
            ):
                top = self._box_world.boxes[idx][4]
                if com_w[1] >= top - 0.05:
                    fl_g = max(fl_g, top)
        for bx0, by0, bz0, bx1, by1, bz1 in self._extra_boxes:
            if bx0 - 0.1 <= com_w[0] <= bx1 + 0.1 and bz0 - 0.1 <= com_w[2] <= bz1 + 0.1:
                if com_w[1] >= by1 - 0.05:
                    fl_g = max(fl_g, by1)

        min_cy = min(m_apply(mat, c)[1] for c in corners)
        if pos[1] + min_cy <= fl_g:
            pos[1] = fl_g - min_cy
            if vel[1] < -0.55:
                vel[1] = -vel[1] * 0.22
            else:
                vel[1] = 0.0
            kf = 0.62 ** (h * 60.0)
            vel[0] *= kf
            vel[2] *= kf
            ang = [a * (0.52 ** (h * 60.0)) for a in ang]
            gx = m_apply(mat, (1.0, 0.0, 0.0))
            gz = m_apply(mat, (0.0, 0.0, 1.0))
            sgn = 1.0 if gx[1] >= 0.0 else -1.0
            gz_h = v_norm((gz[0], 0.0, gz[2]))
            if gz_h == (0.0, 0.0, 0.0):
                gz_h = (self._dir[0], 0.0, self._dir[1])
            x_col = (0.0, sgn, 0.0)
            y_col = v_cross(gz_h, x_col)
            m_flat = (x_col[0], y_col[0], gz_h[0], x_col[1], y_col[1], gz_h[1], x_col[2], y_col[2], gz_h[2])
            k_fl = min(1.0, 14.0 * h)
            mat = _ortho(tuple(mat[i] + (m_flat[i] - mat[i]) * k_fl for i in range(9)))
            sp2 = vel[0] * vel[0] + vel[1] * vel[1] + vel[2] * vel[2]
            if sp2 < 0.004 and abs(gx[1]) > 0.985 and abs(gz[1]) < 0.04:
                g["still_t"] += h
                if g["still_t"] > 0.15:
                    mat = m_flat
                    min_cy = min(m_apply(mat, c)[1] for c in corners)
                    pos[1] = fl_g - min_cy + 0.004
                    g["settled"] = True
                    g["floor_y"] = fl_g
            else:
                g["still_t"] = 0.0
        g["mat"], g["ang"] = mat, ang

    def draw_gun(self, r):
        """Render the dropped rifle once released from the guard's hand."""
        if self.rifle_on or self._gun is None:
            return
        mesh = getattr(self.hum, "_rifle", None)
        if mesh is None:
            return
        g = self._gun
        if hasattr(r, "add_packed") and hasattr(r, "pack"):
            if g["settled"] and g["settled_rows"] is not None:
                r.add_packed(g["settled_rows"])
                return
            rows, _faces = _gun_packed(r, mesh)
            if rows is None:
                return
            import numpy as np
            rt = np.array(g["mat"], dtype=np.float32).reshape(3, 3).T
            out = rows.copy()
            np.matmul(rows[:, 0:3], rt, out=out[:, 0:3])
            out[:, 0] += g["pos"][0]
            out[:, 1] += g["pos"][1]
            out[:, 2] += g["pos"][2]
            np.matmul(rows[:, 6:9], rt, out=out[:, 6:9])
            if g["settled"]:
                g["settled_rows"] = out
            r.add_packed(out)
        else:
            if g["settled"] and g["settled_sw"] is not None:
                wverts, faces = g["settled_sw"]
                r.add_dynamic(wverts, faces)
                return
            mat, pos = g["mat"], g["pos"]
            wverts = [v_add(pos, m_apply(mat, v)) for v in mesh.verts]
            _, faces = _gun_packed(r, mesh) if hasattr(r, "pack") else (None, [(f[0], f[1], f[2], f[3], None, f[4]) for f in mesh.faces])
            if g["settled"]:
                g["settled_sw"] = (wverts, faces)
            r.add_dynamic(wverts, faces)

    def at(self, a, floor):
        """(pose, root, yaw) ``a`` seconds after the kill."""
        floor_fn = floor if callable(floor) else (lambda _x, _z, _y=float(floor): _y)
        dt = min(0.05, max(0.0, a - self.last))
        self.last = a
        if self._gun is not None and not self._gun["settled"]:
            rem_g = dt
            while rem_g > 1e-6 and not self._gun["settled"]:
                hg = MAX_SUBSTEP if rem_g > MAX_SUBSTEP else rem_g
                self._step_gun(hg, floor_fn)
                rem_g -= hg
            if a >= 5.0 and not self._gun["settled"]:
                self._gun["settled"] = True
        if self.rest is not None:
            p, (rx, rz), yaw = self.rest
            return p, (rx, max(floor_fn(*self.chest), self.support_y), rz), yaw
        # Fixed steps: the solver's stiffness and the tone springs then behave the same at
        # 30, 60 or 144 fps; the drawn pose interpolates between the last two steps.
        self._acc += dt
        h = MAX_SUBSTEP
        while self._acc >= h - 1e-9 and not self.rag.asleep:
            self._acc -= h
            self._sim_t += h
            self._snap = {k: tuple(v) for k, v in self.rag.pos.items()}
            self._apply_muscle_tone(h, self._sim_t, floor_fn)
            self.rag.step(
                h, floor_fn=floor_fn, box_world=self._box_world,
                extra_boxes=self._extra_boxes, gravity=GRAVITY, iters=6,
            )
            if self.rag.wall_contact is not None and self.rag.pos["pelvis"][1] <= max(floor_fn(*self.chest), self.rag.support_y) + 0.55:
                self._wall_slump = True
        nodes = self.rag.pos
        if self._snap is not None and not self.rag.asleep:
            k_i = max(0.0, min(1.0, self._acc / h))
            nodes = {n: tuple(s0 + (s1 - s0) * k_i for s0, s1 in zip(self._snap[n], p))
                     for n, p in self.rag.pos.items()}
        ch = self.rag.pos["chest"]
        pel = self.rag.pos["pelvis"]
        self.chest = (ch[0], ch[2])
        fl = floor_fn(*self.chest)
        surf_y = max(fl, self.rag.support_y)
        self.support_y = surf_y
        if not self._wall_slump and ch[1] <= surf_y + 0.44:
            k_hy = _s(0.28, 0.92, a)
            self._head_yaw = self._head_yaw_tgt * k_hy
        elif self._wall_slump:
            self._head_yaw = (8.0 if self._side > 0 else -8.0) * _s(0.30, 0.85, a)

        rifle_m = None
        if self.rifle_on:
            pl_tmp, j_tmp = self.hum.places_from_nodes(nodes, floor_y=surf_y, head_yaw=self._head_yaw)
            f_now = next((m for sl, _k, m, _o, _g, _fb in pl_tmp if sl == 12), None)
            rh_now = j_tmp["rhand"]
            if f_now is not None and self._rifle_local is not None:
                sc = getattr(self.hum, "_scale", 1.0) or 1.0
                f0 = tuple(v / sc for v in f_now)
                droop = rot_x(18.0 * _s(0.05, max(0.08, self._release_at), a))
                rifle_m = m_mul(m_mul(f0, self._rifle_local), droop)
                self._rifle_mat = rifle_m
            self._rifle_pos = rh_now
            if a >= self._release_at or rh_now[1] <= surf_y + 0.24 or self.rag.asleep:
                inv_dt = 1.0 / max(1e-3, dt)
                vel_est = tuple((rh_now[i] - self._prev_rhand[i]) * inv_dt for i in range(3))
                self._release_gun(floor_fn, vel_est)
                rifle_m = None
            else:
                self._prev_rhand = rh_now

        places, joints = self.hum.places_from_nodes(
            nodes, floor_y=surf_y, head_yaw=self._head_yaw,
            rifle_m=rifle_m if self.rifle_on else None,
        )
        pose = {"_places": places, "_joints": joints}
        if self.rag.asleep or a >= 4.0:
            self.rag.asleep = True
            if self.rifle_on:
                self._release_gun(floor_fn, (0.0, 0.0, 0.0))
            self.rest = (pose, (pel[0], pel[2]), self.yaw0)
        return pose, (pel[0], surf_y, pel[2]), self.yaw0
