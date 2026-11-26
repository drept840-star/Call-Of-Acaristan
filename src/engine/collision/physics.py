"""Shared capsule sliding, rigid impact debris, and articulated Verlet ragdolls.

Pure Python, no pygame or engine3d imports (RPE6 boundary E1/E3). Callers
supply a ``BoxWorld``, ``Placement`` meshes, or raw ``(x0, y0, z0, x1, y1, z1)``
boxes and an optional ``floor_fn(x, z) -> float``.
"""
from __future__ import annotations

import math
import random
from typing import Callable, Iterable, Sequence

from .boxes import BoxWorld, _box_contact_xz

__all__ = [
    "box_xz_h",
    "box_xz_yy",
    "slide_capsule",
    "DebrisBody",
    "DebrisPool",
    "RagdollBody",
]

Box6 = tuple[float, float, float, float, float, float]


def box_xz_h(b: Sequence[float]) -> Box6:
    """Convert ``(x0, z0, x1, z1, h)`` to ``(x0, 0.0, z0, x1, h, z1)``."""
    return (float(b[0]), 0.0, float(b[1]), float(b[2]), float(b[4]), float(b[3]))


def box_xz_yy(b: Sequence[float]) -> Box6:
    """Convert ``(x0, z0, x1, z1, y0, y1)`` to ``(x0, y0, z0, x1, y1, z1)``."""
    return (float(b[0]), float(b[4]), float(b[1]), float(b[2]), float(b[5]), float(b[3]))


def _collect_contacts(x: float, z: float, r: float, y0: float, y1: float,
                      box_world: BoxWorld | None, meshes: Iterable,
                      extra_boxes: Sequence[Box6]) -> list[tuple[float, float, float, float]]:
    """Collect ``(nx, nz, pen, box_top)`` contacts for capsule ``(x, z, r, y0..y1)``."""
    out: list[tuple[float, float, float, float]] = []
    if box_world is not None:
        for nx, nz, pen, idx in box_world.capsule_contacts(x, z, r, y0, y1):
            out.append((nx, nz, pen, box_world.boxes[idx][4]))
    for bx0, by0, bz0, bx1, by1, bz1 in extra_boxes:
        if by1 <= y0 or by0 >= y1:
            continue
        c = _box_contact_xz(x, z, r, bx0, bz0, bx1, bz1)
        if c is not None:
            out.append((c[0], c[1], c[2], by1))
    for m in meshes:
        if m is None:
            continue
        if hasattr(m, "capsule_contacts"):
            for nx, nz, pen in m.capsule_contacts(x, z, r, y0, y1):
                out.append((nx, nz, pen, 1e9))
        elif m.body_hits(x, z, r, y0, y1):
            wb = m.world_box()
            c = _box_contact_xz(x, z, r, wb[0], wb[2], wb[3], wb[5])
            if c is not None:
                out.append((c[0], c[1], c[2], wb[4]))
    return out


def slide_capsule(x: float, y: float, z: float, dx: float, dz: float,
                  r: float, height: float = 1.8, *,
                  box_world: BoxWorld | None = None,
                  meshes: Iterable = (),
                  extra_boxes: Sequence[Box6] = (),
                  step_h: float = 0.0,
                  floor_fn: Callable[[float, float, float], float] | None = None,
                  bounds: Sequence[float] | None = None,
                  iters: int = 4) -> tuple[float, float, float, bool]:
    """Sub-stepped capsule-vs-world slide with optional stair/curb step-up.

    Returns ``(new_x, new_y, new_z, collided)``.
    """
    disp = math.hypot(dx, dz)
    steps = max(1, math.ceil(disp / max(0.08, r * 0.45))) if disp > 1e-6 else 1
    sdx, sdz = dx / steps, dz / steps
    collided = False
    cx, cy, cz = float(x), float(y), float(z)

    for _ in range(steps):
        rem_x, rem_z = sdx, sdz
        nx, nz = cx + rem_x, cz + rem_z
        if bounds is not None:
            nx = min(max(nx, bounds[0]), bounds[1])
            nz = min(max(nz, bounds[2]), bounds[3])

        if floor_fn is not None:
            fy = float(floor_fn(nx, nz, cy))
            if fy <= cy + step_h and fy > cy - 1.2:
                cy = fy

        # Check step-up over low obstacles if enabled
        contacts = _collect_contacts(nx, nz, r, cy + 0.05, cy + height, box_world, meshes, extra_boxes)
        if contacts and step_h > 0.0:
            max_top = max(c[3] for c in contacts)
            if cy < max_top <= cy + step_h:
                upper = _collect_contacts(nx, nz, r, max_top + 0.05, max_top + height,
                                          box_world, meshes, extra_boxes)
                if not upper:
                    cy = max_top
                    cx, cz = nx, nz
                    continue

        for _it in range(iters):
            if not contacts:
                break
            collided = True
            # Resolve deepest penetration first
            n_x, n_z, pen, _top = max(contacts, key=lambda c: c[2])
            nx += n_x * (pen + 1e-4)
            nz += n_z * (pen + 1e-4)
            # Project remaining velocity onto wall tangent
            vn = rem_x * n_x + rem_z * n_z
            if vn < 0.0:
                rem_x -= vn * n_x
                rem_z -= vn * n_z
            if bounds is not None:
                nx = min(max(nx, bounds[0]), bounds[1])
                nz = min(max(nz, bounds[2]), bounds[3])
            contacts = _collect_contacts(nx, nz, r, cy + 0.05, cy + height, box_world, meshes, extra_boxes)

        cx, cz = nx, nz

    if floor_fn is not None:
        fy = float(floor_fn(cx, cz, cy))
        if fy <= cy + max(step_h, 0.25) and fy > cy - 1.2:
            cy = fy
    return cx, cy, cz, collided


class DebrisBody:
    """One rigid tumbling 3D debris chunk (splinter, crate shard, barrel lid, glass)."""

    __slots__ = ("pos", "vel", "rot", "ang_vel", "half", "col",
                 "bounce", "friction", "age", "life", "settled")

    def __init__(self, pos: Sequence[float], vel: Sequence[float],
                 half: Sequence[float] = (0.12, 0.06, 0.08),
                 col: tuple[int, int, int] = (120, 96, 68),
                 *, ang_vel: Sequence[float] = (0.0, 0.0, 0.0),
                 bounce: float = 0.35, friction: float = 0.65, life: float = 6.0) -> None:
        self.pos = [float(pos[0]), float(pos[1]), float(pos[2])]
        self.vel = [float(vel[0]), float(vel[1]), float(vel[2])]
        self.rot = [0.0, 0.0, 0.0]
        self.ang_vel = [float(ang_vel[0]), float(ang_vel[1]), float(ang_vel[2])]
        self.half = (float(half[0]), float(half[1]), float(half[2]))
        self.col = col
        self.bounce = float(bounce)
        self.friction = float(friction)
        self.age = 0.0
        self.life = float(life)
        self.settled = False


class DebrisPool:
    """Manages rigid-body impact debris colliding with floors and ``BoxWorld`` walls."""

    def __init__(self, capacity: int = 128, seed: int = 404) -> None:
        self.capacity = int(capacity)
        self.items: list[DebrisBody] = []
        self._rng = random.Random(seed)

    def clear(self) -> None:
        self.items.clear()

    def spawn_burst(self, pos: Sequence[float], n: int = 8, *,
                    normal: Sequence[float] = (0.0, 1.0, 0.0),
                    speed: float = 4.5, col: tuple[int, int, int] = (128, 102, 74),
                    half: Sequence[float] = (0.10, 0.04, 0.07),
                    life: float = 6.0, bounce: float = 0.34) -> None:
        rng = self._rng
        nx, ny, nz = float(normal[0]), float(normal[1]), float(normal[2])
        for _ in range(int(n)):
            a = rng.uniform(0.0, math.tau)
            sp = rng.uniform(0.45, 1.25) * speed
            vx = nx * sp * 0.6 + math.cos(a) * sp * 0.65
            vy = max(0.8, ny * sp * 0.5 + rng.uniform(1.2, 3.8))
            vz = nz * sp * 0.6 + math.sin(a) * sp * 0.65
            av = (rng.uniform(-420.0, 420.0), rng.uniform(-420.0, 420.0), rng.uniform(-420.0, 420.0))
            sc = rng.uniform(0.7, 1.25)
            c_var = tuple(max(0, min(255, int(c + rng.randint(-14, 14)))) for c in col)
            body = DebrisBody(pos, (vx, vy, vz),
                              (half[0] * sc, half[1] * sc, half[2] * sc),
                              c_var, ang_vel=av, bounce=bounce, life=life)
            if len(self.items) >= self.capacity:
                self.items.pop(0)
            self.items.append(body)

    def update(self, dt: float, *, floor_fn: Callable[[float, float], float] | None = None,
               box_world: BoxWorld | None = None, gravity: float = 9.8) -> None:
        dt = min(0.05, max(0.0, float(dt)))
        if dt <= 0.0 or not self.items:
            return
        alive: list[DebrisBody] = []
        for b in self.items:
            b.age += dt
            if b.age >= b.life:
                continue
            alive.append(b)
            if b.settled:
                continue
            b.vel[1] -= gravity * dt
            b.pos[0] += b.vel[0] * dt
            b.pos[1] += b.vel[1] * dt
            b.pos[2] += b.vel[2] * dt
            b.rot[0] += b.ang_vel[0] * dt
            b.rot[1] += b.ang_vel[1] * dt
            b.rot[2] += b.ang_vel[2] * dt

            rad = max(b.half)
            if box_world is not None:
                for c_nx, c_nz, pen, _idx in box_world.capsule_contacts(
                    b.pos[0], b.pos[2], rad, b.pos[1] - rad, b.pos[1] + rad
                ):
                    b.pos[0] += c_nx * pen
                    b.pos[2] += c_nz * pen
                    vn = b.vel[0] * c_nx + b.vel[2] * c_nz
                    if vn < 0.0:
                        b.vel[0] -= (1.0 + b.bounce) * vn * c_nx
                        b.vel[2] -= (1.0 + b.bounce) * vn * c_nz
                        b.ang_vel[1] *= -0.7

            fy = (float(floor_fn(b.pos[0], b.pos[2])) if floor_fn is not None else 0.0) + b.half[1]
            if b.pos[1] <= fy:
                b.pos[1] = fy
                if b.vel[1] < -0.6:
                    b.vel[1] = -b.vel[1] * b.bounce
                else:
                    b.vel[1] = 0.0
                b.vel[0] *= b.friction
                b.vel[2] *= b.friction
                b.ang_vel[0] *= 0.65
                b.ang_vel[1] *= 0.72
                b.ang_vel[2] *= 0.65
                if abs(b.vel[1]) < 0.05 and (b.vel[0] ** 2 + b.vel[2] ** 2) < 0.04:
                    b.vel = [0.0, 0.0, 0.0]
                    b.ang_vel = [0.0, 0.0, 0.0]
                    b.settled = True
        self.items = alive


_RAGDOLL_RADII = {
    "pelvis": 0.13, "chest": 0.13, "head": 0.12,
    "lsh": 0.08, "rsh": 0.08, "lel": 0.07, "rel": 0.07, "lhand": 0.06, "rhand": 0.06,
    "lhip": 0.08, "rhip": 0.08, "lkn": 0.07, "rkn": 0.07, "lfoot": 0.06, "rfoot": 0.06,
}
_RAGDOLL_EDGES = (
    ("pelvis", "chest"), ("chest", "head"),
    ("chest", "lsh"), ("lsh", "lel"), ("lel", "lhand"),
    ("chest", "rsh"), ("rsh", "rel"), ("rel", "rhand"),
    ("pelvis", "lhip"), ("lhip", "lkn"), ("lkn", "lfoot"),
    ("pelvis", "rhip"), ("rhip", "rkn"), ("rkn", "rfoot"),
    # Rigid shoulder and pelvic girdles
    ("lsh", "rsh"), ("lhip", "rhip"), ("pelvis", "lsh"), ("pelvis", "rsh"),
)
# Elastic spine and neck range constraints: (node_a, node_b, min_frac, max_frac)
_RAGDOLL_SOFT_LINKS = (
    ("pelvis", "head", 0.72, 1.08),
    ("lsh", "head", 0.72, 1.18), ("rsh", "head", 0.72, 1.18),
    ("lhip", "chest", 0.80, 1.12), ("rhip", "chest", 0.80, 1.12),
    ("lhip", "lsh", 0.76, 1.18), ("rhip", "rsh", 0.76, 1.18),
    ("lhip", "rsh", 0.80, 1.18), ("rhip", "lsh", 0.80, 1.18),
)
_RAGDOLL_MIN_DISTS = (
    ("lsh", "rsh", 0.34), ("lhip", "rhip", 0.18),
    ("pelvis", "head", 0.52),
    ("lsh", "lhand", 0.25), ("rsh", "rhand", 0.25),
    ("lhip", "lfoot", 0.34), ("rhip", "rfoot", 0.34),
    ("lkn", "rkn", 0.14), ("lfoot", "rfoot", 0.12),
    ("rhip", "lkn", 0.40), ("lhip", "rkn", 0.40),
    # hip flexion stops near 110 deg: legs never fold back through the torso
    ("chest", "lkn", 0.44), ("chest", "rkn", 0.44),
    ("chest", "lfoot", 0.50), ("chest", "rfoot", 0.50),
    ("head", "lkn", 0.58), ("head", "rkn", 0.58),
    ("head", "lfoot", 0.66), ("head", "rfoot", 0.66),
)
# limb bones whose midpoints also collide with walls
_RAGDOLL_BONES = (("lsh", "lel"), ("lel", "lhand"), ("rsh", "rel"), ("rel", "rhand"),
                  ("lhip", "lkn"), ("lkn", "lfoot"), ("rhip", "rkn"), ("rkn", "rfoot"),
                  ("pelvis", "chest"))
_MAX_NODE_V = 12.0  # m/s hard cap on carried per-node velocity
_MAX_SOLVER_V = 1.5  # m/s of velocity one step of constraint correction may add per node
_MAX_REST_SOLVER_V = 0.30  # m/s solver rebound cap once grounded and slow
_STICK_V = 0.20  # m/s below which a node touching a surface sticks instead of sliding
_REST_GROUNDED = 6  # nodes touching a surface before rest damping starts
_REST_V = 0.6  # m/s: rest damping only settles a body this slow, never a real topple
_REST_DAMP = 0.72  # velocity kept per 1/60 s while grounded
_SETTLE_V = 0.14  # m/s: a grounded body slower than this is only creeping
_SETTLE_T = 0.22  # s of creeping before a grounded body sleeps
_COM_K = 1.0
_HINGE_DEGEN = 0.95  # |cos| between limb and joint axis past which a hinge limit is skipped
_COM_K_REST = 1.0
_E_SLACK = 1.0  # energy the constraint passes may keep, relative to what came in
_RAGDOLL_MAX_DISTS = (
    ("lkn", "rkn", 0.36), ("lfoot", "rfoot", 0.44),
)
_DEFAULT_LOCAL = {
    "pelvis": (0.0, 0.90, 0.0), "chest": (0.0, 1.32, 0.0), "head": (0.0, 1.66, 0.0),
    "lsh": (-0.21, 1.40, 0.0), "rsh": (0.21, 1.40, 0.0),
    "lel": (-0.26, 1.12, 0.06), "rel": (0.26, 1.12, 0.06),
    "lhand": (-0.24, 0.88, 0.14), "rhand": (0.24, 0.88, 0.14),
    "lhip": (-0.11, 0.84, 0.0), "rhip": (0.11, 0.84, 0.0),
    "lkn": (-0.11, 0.45, 0.02), "rkn": (0.11, 0.45, 0.02),
    "lfoot": (-0.11, 0.06, 0.0), "rfoot": (0.11, 0.06, 0.0),
}


def _dot(a: Sequence[float], b: Sequence[float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Sequence[float] | None, b: Sequence[float] | None) -> tuple[float, float, float]:
    if a is None or b is None:
        return (0.0, 0.0, 0.0)
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _unit(v: Sequence[float]) -> tuple[float, float, float] | None:
    n = math.sqrt(_dot(v, v))
    return (v[0] / n, v[1] / n, v[2] / n) if n > 1e-6 else None


class RagdollBody:
    """15-node constrained Verlet ragdoll with floor, ledge, and wall collision."""

    def __init__(self, nodes: dict[str, Sequence[float]], *, drag: float = 0.992) -> None:
        self.pos: dict[str, list[float]] = {k: [float(v[0]), float(v[1]), float(v[2])] for k, v in nodes.items()}
        self.prev: dict[str, list[float]] = {k: list(v) for k, v in self.pos.items()}
        self.links: list[tuple[str, str, float]] = []
        for a, b in _RAGDOLL_EDGES:
            if a in self.pos and b in self.pos:
                self.links.append((a, b, max(0.08, math.dist(self.pos[a], self.pos[b]))))
        # Body scale from every bone, so soft ranges and distance stops fit this rig's
        # proportions (a pelvis-chest-only scale left real rigs pinned at their limits).
        ratios = [rest / max(1e-6, math.dist(_DEFAULT_LOCAL[a], _DEFAULT_LOCAL[b]))
                  for a, b, rest in self.links if a in _DEFAULT_LOCAL and b in _DEFAULT_LOCAL]
        sc = max(0.75, sum(ratios) / len(ratios)) if ratios else 1.0
        self._min_dists = [(a, b, d * sc) for a, b, d in _RAGDOLL_MIN_DISTS if a in self.pos and b in self.pos]
        self._max_dists = [(a, b, d * sc) for a, b, d in _RAGDOLL_MAX_DISTS if a in self.pos and b in self.pos]
        self._soft_links: list[tuple[str, str, float, float]] = []
        for a, b, f_min, f_max in _RAGDOLL_SOFT_LINKS:
            if a in self.pos and b in self.pos:
                ref = math.dist(_DEFAULT_LOCAL[a], _DEFAULT_LOCAL[b]) * sc
                self._soft_links.append((a, b, max(0.10, ref * f_min), max(0.16, ref * f_max)))
        self.drag = float(drag)
        self.asleep = False
        self._still_t = 0.0
        self._grounded = 0
        self.support_y = min(self.pos.get("lfoot", (0.0, 0.0, 0.0))[1],
                             self.pos.get("rfoot", (0.0, 0.0, 0.0))[1])
        self.wall_contact: tuple[float, float] | None = None
        self._h = 1.0 / 60.0  # last step size: prev offsets encode velocity * _h

    @classmethod
    def from_pose(cls, pos: Sequence[float], yaw_deg: float = 0.0,
                  joints: dict[str, Sequence[float]] | None = None) -> "RagdollBody":
        """Construct from live world joint positions or fallback standing layout."""
        rad = math.radians(yaw_deg)
        c, s = math.cos(rad), math.sin(rad)
        y_shift = 0.0
        if joints and "pelvis" in joints:
            y_shift = float(joints["pelvis"][1]) - (float(pos[1]) + _DEFAULT_LOCAL["pelvis"][1])
        nodes: dict[str, Sequence[float]] = {}
        for name, (lx, ly, lz) in _DEFAULT_LOCAL.items():
            if joints and name in joints:
                nodes[name] = joints[name]
            else:
                nodes[name] = (pos[0] + c * lx + s * lz, pos[1] + ly + y_shift, pos[2] - s * lx + c * lz)
        return cls(nodes)

    def apply_impulse(self, dv: Sequence[float], *, node: str = "chest",
                      spread: float = 0.35) -> None:
        """Inject instantaneous velocity (m/s) into ``node`` and neighbouring joints."""
        self.asleep = False
        self._still_t = 0.0
        vx, vy, vz = float(dv[0]), float(dv[1]), float(dv[2])
        # Verlet velocity is (pos - prev) / h, with h the step size the offsets were last built with
        h = self._h
        paired = {"lkn": "lfoot", "rkn": "rfoot"}.get(node)
        for name, p in self.pos.items():
            if name == node:
                k = 1.0
            elif name == paired:
                k = max(0.75, spread)
            elif name in ("pelvis", "head", "lsh", "rsh"):
                k = spread
            else:
                k = spread * 0.4
            q = self.prev[name]
            q[0] -= vx * k * h
            q[1] -= vy * k * h
            q[2] -= vz * k * h

    def apply_blast(self, origin: Sequence[float], force: float, radius: float) -> None:
        ox, oy, oz = float(origin[0]), float(origin[1]), float(origin[2])
        for name, p in self.pos.items():
            dx, dy, dz = p[0] - ox, p[1] - oy, p[2] - oz
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d >= radius:
                continue
            k = (1.0 - d / max(0.1, radius)) * force / max(0.35, d)
            self.apply_impulse((dx * k, max(2.2, (dy + 0.6) * k), dz * k), node=name, spread=0.15)

    def _limbs_vs_walls(self, box_world: BoxWorld | None, extra_boxes: Sequence[Box6]) -> None:
        """Bone midpoints collide too, so a shin or forearm cannot straddle a
        thin rail or post that both its joints clear."""
        pos = self.pos
        for a, b in _RAGDOLL_BONES:
            if a not in pos or b not in pos:
                continue
            pa, pb = pos[a], pos[b]
            mx, my, mz = (pa[0] + pb[0]) * 0.5, (pa[1] + pb[1]) * 0.5, (pa[2] + pb[2]) * 0.5
            r = 0.07
            push = None
            if box_world is not None:
                for nx, nz, pen, idx in box_world.capsule_contacts(mx, mz, r, my - r, my + r):
                    if my < box_world.boxes[idx][4] - 0.05:
                        push = (nx * pen, nz * pen)
                        break
            if push is None:
                for bx0, by0, bz0, bx1, by1, bz1 in extra_boxes:
                    if by1 - 0.05 > my and by0 < my + r:
                        c = _box_contact_xz(mx, mz, r, bx0, bz0, bx1, bz1)
                        if c is not None:
                            push = (c[0] * c[2], c[1] * c[2])
                            break
            if push is not None:
                for p in (pa, pb):
                    p[0] += push[0]
                    p[2] += push[1]

    def _apply_anatomical_limits(self, strength: float = 1.0) -> None:
        """Enforce 1-DOF knees/elbows, ribcage pushout, shoulder/hip cones,
        and neck angular limits."""
        pos = self.pos
        pel = pos["pelvis"]
        lsh, rsh = pos["lsh"], pos["rsh"]
        lhip, rhip = pos["lhip"], pos["rhip"]
        sh_mid = ((lsh[0] + rsh[0]) * 0.5, (lsh[1] + rsh[1]) * 0.5, (lsh[2] + rsh[2]) * 0.5)
        ty = _unit((sh_mid[0] - pel[0], sh_mid[1] - pel[1], sh_mid[2] - pel[2]))
        if ty is None:
            return
        rx_raw = (rsh[0] - lsh[0], rsh[1] - lsh[1], rsh[2] - lsh[2])
        tx = _unit((rx_raw[0] - ty[0] * _dot(rx_raw, ty),
                    rx_raw[1] - ty[1] * _dot(rx_raw, ty),
                    rx_raw[2] - ty[2] * _dot(rx_raw, ty)))
        hx_raw = (rhip[0] - lhip[0], rhip[1] - lhip[1], rhip[2] - lhip[2])
        px = _unit((hx_raw[0] - ty[0] * _dot(hx_raw, ty),
                    hx_raw[1] - ty[1] * _dot(hx_raw, ty),
                    hx_raw[2] - ty[2] * _dot(hx_raw, ty))) or tx
        tz = _cross(tx, ty) if tx is not None else None
        pz = _cross(px, ty) if px is not None else None
        if px is not None:
            for side, sx in (("l", -1.0), ("r", 1.0)):
                hp, kn, ft = pos[side + "hip"], pos[side + "kn"], pos[side + "foot"]
                tv = (kn[0] - hp[0], kn[1] - hp[1], kn[2] - hp[2])
                tl = math.sqrt(_dot(tv, tv))
                tu = _unit(tv)
                sv = (ft[0] - kn[0], ft[1] - kn[1], ft[2] - kn[2])
                sl = math.sqrt(_dot(sv, sv))
                if tu is None or sl < 0.1:
                    continue
                # Prevent symmetric starfish leg splay and rear hyperextension.
                if pz is not None and tl > 0.1:
                    lat_h = sx * _dot(tv, px)
                    if lat_h > 0.44 * tl:
                        corr = (lat_h - 0.44 * tl) * 0.45 * strength * sx
                        for i in range(3):
                            kn[i] -= px[i] * corr
                            hp[i] += px[i] * corr * 0.35
                    elif lat_h < -0.16 * tl:
                        corr = (-0.16 * tl - lat_h) * 0.45 * strength * sx
                        for i in range(3):
                            kn[i] += px[i] * corr
                            hp[i] -= px[i] * corr * 0.35
                    fwd_h = _dot(tv, pz)
                    if fwd_h < -0.40 * tl:
                        corr = (-0.40 * tl - fwd_h) * 0.45 * strength
                        for i in range(3):
                            kn[i] += pz[i] * corr
                            hp[i] -= pz[i] * corr * 0.35
                tv = (kn[0] - hp[0], kn[1] - hp[1], kn[2] - hp[2])
                tu = _unit(tv)
                if tu is None:
                    continue
                dx = _dot(px, tu)
                if abs(dx) > _HINGE_DEGEN:
                    continue  # thigh along the hip axis: the knee hinge frame is undefined and would flip
                kx = _unit((px[0] - tu[0] * dx, px[1] - tu[1] * dx, px[2] - tu[2] * dx))
                if kx is None:
                    continue
                kz = _cross(kx, (-tu[0], -tu[1], -tu[2]))
                lat = _dot(sv, kx)
                if abs(lat) > 1e-4:
                    c = lat * 0.45 * strength
                    for i in range(3):
                        ft[i] -= kx[i] * c * 0.5
                        kn[i] += kx[i] * c * 0.5
                sv = (ft[0] - kn[0], ft[1] - kn[1], ft[2] - kn[2])
                fwd = _dot(sv, kz)
                if fwd > 0.0:
                    for i in range(3):
                        ft[i] -= kz[i] * fwd * 0.50 * strength
                        kn[i] += kz[i] * fwd * 0.50 * strength
        if tx is not None:
            for side, sx in (("l", -1.0), ("r", 1.0)):
                sh, el, hd = pos[side + "sh"], pos[side + "el"], pos[side + "hand"]
                uv = (el[0] - sh[0], el[1] - sh[1], el[2] - sh[2])
                ul = math.sqrt(_dot(uv, uv))
                if tz is not None and ul > 0.08:
                    uz = _dot(uv, tz)
                    if uz < -0.58 * ul:
                        corr = (-0.58 * ul - uz) * 0.50 * strength
                        for i in range(3):
                            el[i] += tz[i] * corr * 0.5
                            sh[i] -= tz[i] * corr * 0.5
                    ux_s = sx * _dot(uv, tx)
                    if ux_s < -0.18 * ul and uz < 0.20 * ul:
                        corr = (-0.18 * ul - ux_s) * 0.50 * strength * sx
                        for i in range(3):
                            el[i] += tx[i] * corr * 0.5
                            sh[i] -= tx[i] * corr * 0.5
                    uv = (el[0] - sh[0], el[1] - sh[1], el[2] - sh[2])
                uu = _unit(uv)
                fv = (hd[0] - el[0], hd[1] - el[1], hd[2] - el[2])
                fl = math.sqrt(_dot(fv, fv))
                if uu is None or fl < 0.1:
                    continue
                dx = _dot(tx, uu)
                if abs(dx) > _HINGE_DEGEN:
                    continue  # upper arm along the shoulder axis: the elbow frame is undefined and would flip
                ax = _unit((tx[0] - uu[0] * dx, tx[1] - uu[1] * dx, tx[2] - uu[2] * dx))
                if ax is None:
                    continue
                az = _cross(ax, (-uu[0], -uu[1], -uu[2]))
                back = _dot(fv, az)
                if back < -0.04 * fl:
                    corr = -(back + 0.04 * fl) * strength
                    for i in range(3):
                        hd[i] += az[i] * corr * 0.50
                        el[i] -= az[i] * corr * 0.50
                # Prevent elbows and hands clipping inside or behind the ribcage.
                if tz is not None:
                    for limb_p in (el, hd):
                        rp = (limb_p[0] - pel[0], limb_p[1] - pel[1], limb_p[2] - pel[2])
                        ly = _dot(rp, ty)
                        if 0.02 <= ly <= 0.56:
                            lx = _dot(rp, tx)
                            lz = _dot(rp, tz)
                            rx = 0.19 if ly > 0.24 else 0.16
                            rz = 0.135 if ly > 0.24 else 0.12
                            u2 = (lx / rx) ** 2 + (lz / rz) ** 2
                            if u2 < 1.0:
                                if u2 < 1e-4:
                                    nlx, nlz = sx * rx, rz * 0.5
                                else:
                                    u = math.sqrt(u2)
                                    nlx, nlz = lx / u, lz / u
                                    if lz < 0.0:
                                        nlx += sx * rx * 0.25
                                dlx = (nlx - lx) * 0.60 * strength
                                dlz = (nlz - lz) * 0.60 * strength
                                for i in range(3):
                                    limb_p[i] += tx[i] * dlx + tz[i] * dlz
            if tz is not None and "chest" in pos and "head" in pos:
                ch, hd = pos["chest"], pos["head"]
                hv = (hd[0] - ch[0], hd[1] - ch[1], hd[2] - ch[2])
                hl = math.sqrt(_dot(hv, hv))
                if hl > 0.10:
                    hx, hy, hz = _dot(hv, tx), _dot(hv, ty), _dot(hv, tz)
                    dx_c = max(-0.75 * hl, min(0.75 * hl, hx)) - hx
                    dy_c = max(0.18 * hl, hy) - hy
                    dz_c = max(-0.70 * hl, min(0.90 * hl, hz)) - hz
                    if abs(dx_c) + abs(dy_c) + abs(dz_c) > 1e-4:
                        for i in range(3):
                            c = tx[i] * dx_c + ty[i] * dy_c + tz[i] * dz_c
                            hd[i] += c * 0.35 * strength
                            ch[i] -= c * 0.35 * strength

    def step(self, dt: float, *, floor_fn: Callable[[float, float], float] | None = None,
             box_world: BoxWorld | None = None, extra_boxes: Sequence[Box6] = (),
             gravity: float = 9.8, iters: int = 5) -> None:
        if self.asleep or dt <= 0.0:
            return
        # Equal substeps of at most 1/60 s: one long step with the same iteration count
        # leaves the constraints softer, so a body settled differently at 30 and 60 fps.
        dt = min(0.1, float(dt))
        n = max(1, math.ceil(dt * 60.0 - 1e-6))
        for _ in range(n):
            if self.asleep:
                return
            self._substep(dt / n, floor_fn, box_world, extra_boxes, gravity, iters)

    def _substep(self, h: float, floor_fn: Callable[[float, float], float] | None,
                 box_world: BoxWorld | None, extra_boxes: Sequence[Box6],
                 gravity: float, iters: int) -> None:
        g_step = gravity * h * h
        # Time-corrected Verlet: rescale the carried offset to this step's size, and
        # apply drag per 1/60 s so behaviour does not change with the frame rate.
        drag = self.drag ** (h * 60.0) * (h / self._h)
        self._h = h
        max_disp2 = 0.0
        e_in = 0.0  # carried kinetic energy, in offset^2 units
        vy_in: dict[str, float] = {}
        surf_hit: set[str] = set()
        wall_nodes: dict[str, list[float]] = {}
        pel_sup = self.support_y
        ch_sup = self.support_y
        grounded = 0
        start = {k: (p[0], p[1], p[2]) for k, p in self.pos.items()}
        v_max = _MAX_NODE_V * h
        v_max2 = v_max * v_max
        for name, p in self.pos.items():
            q = self.prev[name]
            vx = (p[0] - q[0]) * drag
            vy = (p[1] - q[1]) * drag
            vz = (p[2] - q[2]) * drag
            sp2 = vx * vx + vy * vy + vz * vz
            if sp2 > v_max2:
                sv = v_max / math.sqrt(sp2)
                vx *= sv; vy *= sv; vz *= sv
            q[0], q[1], q[2] = p[0], p[1], p[2]
            p[0] += vx
            p[1] += vy - g_step
            p[2] += vz
            max_disp2 = max(max_disp2, vx * vx + vy * vy + vz * vz)
            e_in += vx * vx + vy * vy + vz * vz
            vy_in[name] = vy
        pred = {k: (p[0], p[1], p[2]) for k, p in self.pos.items()}
        is_resting = self._grounded >= _REST_GROUNDED and max_disp2 < (_REST_V * h) ** 2
        com_k = _COM_K if not is_resting else _COM_K_REST
        lim_k = 0.25 if is_resting else 1.0

        for _it in range(iters):
            for a, b, rest in self.links:
                pa, pb = self.pos[a], self.pos[b]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d < 1e-6:
                    continue
                diff = (d - rest) / d * 0.5
                pa[0] += dx * diff
                pa[1] += dy * diff
                pa[2] += dz * diff
                pb[0] -= dx * diff
                pb[1] -= dy * diff
                pb[2] -= dz * diff
            for a, b, lo_d, hi_d in self._soft_links:
                pa, pb = self.pos[a], self.pos[b]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d < 1e-6:
                    continue
                if d < lo_d:
                    diff = (d - lo_d) / d * 0.42
                elif d > hi_d:
                    diff = (d - hi_d) / d * 0.42
                else:
                    continue
                pa[0] += dx * diff; pa[1] += dy * diff; pa[2] += dz * diff
                pb[0] -= dx * diff; pb[1] -= dy * diff; pb[2] -= dz * diff
            for a, b, max_d in self._max_dists:
                pa, pb = self.pos[a], self.pos[b]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if d > max_d:
                    diff = (d - max_d) / d * 0.5
                    pa[0] += dx * diff
                    pa[1] += dy * diff
                    pa[2] += dz * diff
                    pb[0] -= dx * diff
                    pb[1] -= dy * diff
                    pb[2] -= dz * diff
            for a, b, min_d in self._min_dists:
                pa, pb = self.pos[a], self.pos[b]
                dx, dy, dz = pb[0] - pa[0], pb[1] - pa[1], pb[2] - pa[2]
                d = math.sqrt(dx * dx + dy * dy + dz * dz)
                if 1e-6 < d < min_d:
                    diff = (d - min_d) / d * 0.5
                    pa[0] += dx * diff
                    pa[1] += dy * diff
                    pa[2] += dz * diff
                    pb[0] -= dx * diff
                    pb[1] -= dy * diff
                    pb[2] -= dz * diff
            # Joint limits are internal forces: their one-sided corrections must not move
            # the centre of mass, or every step injects momentum (drift and launches).
            n_inv = 1.0 / len(self.pos)
            c0 = [sum(p[i] for p in self.pos.values()) for i in range(3)]
            self._apply_anatomical_limits(lim_k)
            c1 = [sum(p[i] for p in self.pos.values()) for i in range(3)]
            sx_c, sy_c, sz_c = ((c1[i] - c0[i]) * n_inv for i in range(3))
            for p in self.pos.values():
                p[0] -= sx_c * com_k; p[2] -= sz_c * com_k
            for name, p in self.pos.items():
                rad = _RAGDOLL_RADII.get(name, 0.10)
                surf_y = (float(floor_fn(p[0], p[2])) if floor_fn is not None else 0.0) + rad
                if box_world is not None:
                    for nx, nz, pen, idx in box_world.capsule_contacts(p[0], p[2], rad, p[1] - rad - 0.01, p[1] + rad):
                        box_top = box_world.boxes[idx][4]
                        if p[1] >= box_top - 0.05:
                            surf_y = max(surf_y, box_top + rad)
                            if p[1] < box_top + rad:
                                p[1] = box_top + rad
                                surf_hit.add(name)
                        else:
                            p[0] += nx * pen
                            p[2] += nz * pen
                            wn = wall_nodes.get(name)
                            if wn is None:
                                wall_nodes[name] = [nx, nz]
                            else:
                                wn[0] += nx; wn[1] += nz
                for bx0, by0, bz0, bx1, by1, bz1 in extra_boxes:
                    if by1 > p[1] - rad - 0.01 and by0 < p[1] + rad:
                        c = _box_contact_xz(p[0], p[2], rad, bx0, bz0, bx1, bz1)
                        if c is not None:
                            if p[1] >= by1 - 0.05:
                                surf_y = max(surf_y, by1 + rad)
                                if p[1] < by1 + rad:
                                    p[1] = by1 + rad
                                    surf_hit.add(name)
                            else:
                                p[0] += c[0] * c[2]
                                p[2] += c[1] * c[2]
                                wn = wall_nodes.get(name)
                                if wn is None:
                                    wall_nodes[name] = [c[0], c[1]]
                                else:
                                    wn[0] += c[0]; wn[1] += c[1]
                fl = (float(floor_fn(p[0], p[2])) if floor_fn is not None else 0.0) + rad
                if p[1] < fl:
                    p[1] = fl
                    surf_hit.add(name)
                if _it == iters - 1:
                    if name == "pelvis":
                        pel_sup = surf_y - rad
                    elif name == "chest":
                        ch_sup = surf_y - rad
                    if p[1] <= surf_y + 0.005:
                        surf_hit.add(name)
                    if name in surf_hit or p[1] < fl + 0.06:
                        grounded += 1
            if _it >= iters - 2 and (box_world is not None or extra_boxes):
                self._limbs_vs_walls(box_world, extra_boxes)

        # Solver corrections keep their positions, but only up to _MAX_SOLVER_V of each
        # becomes velocity: conflicting limits/contacts otherwise pump energy (pops, launches).
        v_cap = (_MAX_REST_SOLVER_V if is_resting else _MAX_SOLVER_V) * h
        for name, p in self.pos.items():
            e = pred[name]
            cx, cy, cz = p[0] - e[0], p[1] - e[1], p[2] - e[2]
            c = math.sqrt(cx * cx + cy * cy + cz * cz)
            if c > v_cap:
                k_c = 1.0 - v_cap / c
                q = self.prev[name]
                q[0] += cx * k_c; q[1] += cy * k_c; q[2] += cz * k_c

        # Links, limits and contacts are passive: after projection the body may hold no more
        # kinetic energy than it carried in plus what gravity released this step, minus the
        # impact energy surface contacts absorbed (a landing torso must not flick the legs up).
        e_out = 0.0
        e_cap = e_in - sum(min(0.0, vy_in[n]) ** 2 for n in surf_hit)
        for name, p in self.pos.items():
            q = self.prev[name]
            e_out += (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2
            e_cap += 2.0 * g_step * (q[1] - p[1])
        if e_out > e_cap * _E_SLACK + 1e-12:
            k_e = math.sqrt(max(0.0, e_cap * _E_SLACK) / e_out)
            for name, p in self.pos.items():
                q = self.prev[name]
                q[0] = p[0] - (p[0] - q[0]) * k_e
                q[1] = p[1] - (p[1] - q[1]) * k_e
                q[2] = p[2] - (p[2] - q[2]) * k_e

        # Apply surface friction once per step across all nodes resting on or hitting a surface.
        # Before collapse (grounded < 4), feet/knees scrape freely rather than propping an upright rig up.
        k_f = (0.88 if grounded < 4 else 0.58) ** (h * 60.0)
        for name in surf_hit:
            p = self.pos[name]
            q = self.prev[name]
            s0 = (start[name][0], start[name][2])
            if grounded >= 4 and (p[0] - s0[0]) ** 2 + (p[2] - s0[1]) ** 2 < (_STICK_V * h) ** 2:
                # static friction: once the body has begun to collapse/rest, a slow contact holds its spot
                # (prev may already be shifted by the caps above, so it is not that spot)
                p[0], p[2] = q[0], q[2] = s0
            q[0] = p[0] - (p[0] - q[0]) * k_f
            q[2] = p[2] - (p[2] - q[2]) * k_f
            q[1] = p[1] + max(0.0, (q[1] - p[1]) * 0.04)

        # Wall/crate slump friction: resist rapid vertical drop along a wall once lower body hits ground.
        self.support_y = max(pel_sup, ch_sup)
        wc_x = wc_z = 0.0
        for name in ("chest", "lsh", "rsh", "pelvis"):
            wn = wall_nodes.get(name)
            if wn is not None:
                wc_x += wn[0]; wc_z += wn[1]
        w_mag = math.hypot(wc_x, wc_z)
        self.wall_contact = (wc_x / w_mag, wc_z / w_mag) if w_mag > 1e-6 else None
        if wall_nodes:
            low_grounded = any(k in surf_hit for k in ("pelvis", "lfoot", "rfoot", "lkn", "rkn"))
            k_wy = (0.54 if low_grounded else 0.88) ** (h * 60.0)
            k_wt = (0.62 if low_grounded else 0.90) ** (h * 60.0)
            for name, (wnx, wnz) in wall_nodes.items():
                wl = math.hypot(wnx, wnz)
                if wl < 1e-6:
                    continue
                nx, nz = wnx / wl, wnz / wl
                tx_w, tz_w = -nz, nx
                p = self.pos[name]
                q = self.prev[name]
                vx, vy, vz = p[0] - q[0], p[1] - q[1], p[2] - q[2]
                if vy < 0.0:
                    q[1] = p[1] - vy * k_wy
                vn = max(0.0, vx * nx + vz * nz)
                vt = (vx * tx_w + vz * tz_w) * k_wt
                q[0] = p[0] - (nx * vn + tx_w * vt)
                q[2] = p[2] - (nz * vn + tz_w * vt)

        self._grounded = grounded
        # Rest damping: once most of the body lies slow on a surface, joint-limit corrections
        # would otherwise feed back into carried velocity and keep the corpse twitching.
        actual_disp2 = 0.0
        for name, p in self.pos.items():
            s0 = start[name]
            dx, dy, dz = p[0] - s0[0], p[1] - s0[1], p[2] - s0[2]
            d2 = dx * dx + dy * dy + dz * dz
            if d2 > actual_disp2:
                actual_disp2 = d2
        if grounded >= _REST_GROUNDED and max(max_disp2, actual_disp2) < (_REST_V * h) ** 2:
            k_r = _REST_DAMP ** (h * 60.0)
            for name, p in self.pos.items():
                q = self.prev[name]
                q[0] = p[0] - (p[0] - q[0]) * k_r
                q[2] = p[2] - (p[2] - q[2]) * k_r
                if p[1] > q[1]:  # never slow the drop itself, or the corpse sags in slow motion
                    q[1] = p[1] - (p[1] - q[1]) * k_r
        # Sleep: still in the air for 0.45 s, or a body lying on a surface that only
        # creeps (actual post-solver movement, not pre-solver carry) for _SETTLE_T.
        settled = grounded >= _REST_GROUNDED and actual_disp2 < (_SETTLE_V * h) ** 2
        if settled or actual_disp2 < (0.04 * h) ** 2:
            self._still_t += h
            if self._still_t > (_SETTLE_T if settled else 0.45):
                self.asleep = True
                for name, p in self.pos.items():
                    self.prev[name][:] = p
        else:
            self._still_t = 0.0