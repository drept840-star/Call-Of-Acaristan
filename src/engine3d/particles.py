"""Shared vectorized particle & ground-decal pools with GPU instancing support.

Usable by both 3D scenes (M6 yard, M7 raid, M8 trap/mansion) and 2.5D hosts
(via ``topdown3d.dots`` and ``pack_blood_decals``).  All simulation runs in
contiguous NumPy arrays; ``GLRenderer`` draws them via instanced ``ParticlePass``
and ``DecalPass`` while ``SoftwareRenderer`` falls back to lightweight sprites.
"""
import math

import numpy as np

__all__ = [
    "PKIND_SMOKE", "PKIND_SPARK", "PKIND_CASING", "PKIND_DUST",
    "PKIND_EMBER", "PKIND_DEBRIS",
    "DKIND_BLOOD", "DKIND_SCORCH", "DKIND_CRATER", "DKIND_IMPACT",
    "ParticlePool", "DecalPool", "pack_dots", "pack_blood_decals",
]

PKIND_SMOKE = 0
PKIND_SPARK = 1
PKIND_CASING = 2
PKIND_DUST = 3
PKIND_EMBER = 4
PKIND_DEBRIS = 5

DKIND_BLOOD = 0
DKIND_SCORCH = 1
DKIND_CRATER = 2
DKIND_IMPACT = 3


class ParticlePool:
    """Fixed-capacity vectorized 3D particle pool."""

    def __init__(self, capacity=2048, seed=1337):
        self.capacity = int(capacity)
        self.count = 0
        self._cursor = 0
        self._rng = np.random.default_rng(seed)

        n = self.capacity
        self.pos = np.zeros((n, 3), dtype=np.float32)
        self.vel = np.zeros((n, 3), dtype=np.float32)
        self.col = np.zeros((n, 4), dtype=np.float32)
        self.size0 = np.zeros(n, dtype=np.float32)
        self.size1 = np.zeros(n, dtype=np.float32)
        self.age = np.zeros(n, dtype=np.float32)
        self.life = np.ones(n, dtype=np.float32)
        self.grav = np.zeros(n, dtype=np.float32)
        self.drag = np.zeros(n, dtype=np.float32)
        self.bounce = np.zeros(n, dtype=np.float32)
        self.kind = np.zeros(n, dtype=np.float32)
        self.seed = np.zeros(n, dtype=np.float32)
        self._arrays = (
            self.pos, self.vel, self.col, self.size0, self.size1,
            self.age, self.life, self.grav, self.drag, self.bounce,
            self.kind, self.seed,
        )

    def clear(self):
        self.count = 0
        self._cursor = 0

    def _alloc(self):
        if self.count < self.capacity:
            i = self.count
            self.count += 1
            return i
        i = self._cursor % self.capacity
        self._cursor += 1
        return i

    def emit(self, kind, pos, vel=(0.0, 0.0, 0.0), col=(255, 255, 255),
             size0=0.15, size1=None, life=0.8, gravity=0.0, drag=0.0,
             bounce=0.0, alpha=1.0, seed=None):
        i = self._alloc()
        self.pos[i] = pos
        self.vel[i] = vel
        self.col[i] = (col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, float(alpha))
        self.size0[i] = float(size0)
        self.size1[i] = float(size0 if size1 is None else size1)
        self.age[i] = 0.0
        self.life[i] = max(0.02, float(life))
        self.grav[i] = float(gravity)
        self.drag[i] = float(drag)
        self.bounce[i] = float(bounce)
        self.kind[i] = float(kind)
        self.seed[i] = float(self._rng.random() * 100.0 if seed is None else seed)

    def burst_sparks(self, pos, n=12, speed=5.5, col=(255, 204, 122), life=0.52):
        rng = self._rng
        for _ in range(int(n)):
            a = float(rng.uniform(0.0, math.tau))
            el = float(rng.uniform(-0.15, 0.85))
            sp = float(rng.uniform(0.45, 1.15)) * speed
            vx = math.cos(a) * math.cos(el) * sp
            vy = math.sin(el) * sp + 1.2
            vz = math.sin(a) * math.cos(el) * sp
            self.emit(PKIND_SPARK, pos, (vx, vy, vz), col=col,
                      size0=0.08, size1=0.03, life=life * float(rng.uniform(0.6, 1.2)),
                      gravity=9.8, drag=1.8, bounce=0.35, alpha=1.0)

    def burst_smoke(self, pos, n=5, speed=1.1, col=(148, 148, 152),
                    size0=0.16, size1=0.68, life=0.95, alpha=0.45):
        rng = self._rng
        for _ in range(int(n)):
            a = float(rng.uniform(0.0, math.tau))
            sp = float(rng.uniform(0.25, 1.0)) * speed
            vx = math.cos(a) * sp
            vy = float(rng.uniform(0.55, 1.35))
            vz = math.sin(a) * sp
            self.emit(PKIND_SMOKE, pos, (vx, vy, vz), col=col,
                      size0=size0, size1=size1 * float(rng.uniform(0.8, 1.2)),
                      life=life * float(rng.uniform(0.75, 1.25)),
                      gravity=-0.35, drag=2.4, alpha=alpha)

    def burst_muzzle(self, pos, fwd, col=(178, 178, 182), n=4):
        rng = self._rng
        fx, fy, fz = fwd
        for _ in range(int(n)):
            sp = float(rng.uniform(1.4, 3.2))
            vx = fx * sp + float(rng.uniform(-0.45, 0.45))
            vy = fy * sp + float(rng.uniform(0.15, 0.55))
            vz = fz * sp + float(rng.uniform(-0.45, 0.45))
            self.emit(PKIND_SMOKE, pos, (vx, vy, vz), col=col,
                      size0=0.09, size1=0.46, life=float(rng.uniform(0.45, 0.85)),
                      gravity=-0.25, drag=4.2, alpha=0.36)

    def emit_casing(self, pos, vel, col=(214, 174, 72), life=3.6):
        self.emit(PKIND_CASING, pos, vel, col=col,
                  size0=0.036, size1=0.036, life=life,
                  gravity=9.8, drag=0.25, bounce=0.32, alpha=1.0)

    def burst_impact(self, pos, kind="stone", n=8, col=None):
        rng = self._rng
        if kind == "blood":
            c = col or (142, 22, 20)
            for _ in range(int(n)):
                a = float(rng.uniform(0.0, math.tau))
                sp = float(rng.uniform(0.8, 2.6))
                self.emit(PKIND_DUST, pos, (math.cos(a) * sp, float(rng.uniform(0.6, 2.0)), math.sin(a) * sp),
                          col=c, size0=0.08, size1=0.24, life=float(rng.uniform(0.28, 0.52)),
                          gravity=6.5, drag=3.0, alpha=0.72)
        else:
            c = col or (162, 158, 150)
            for _ in range(int(n)):
                a = float(rng.uniform(0.0, math.tau))
                sp = float(rng.uniform(0.7, 2.4))
                self.emit(PKIND_DUST, pos, (math.cos(a) * sp, float(rng.uniform(0.5, 1.8)), math.sin(a) * sp),
                          col=c, size0=0.09, size1=0.34, life=float(rng.uniform(0.35, 0.65)),
                          gravity=1.8, drag=3.5, alpha=0.52)

    def update(self, dt, floor_y=0.0):
        n = self.count
        if n <= 0 or dt <= 0.0:
            return
        dt = min(0.05, float(dt))
        self.age[:n] += dt
        keep = self.age[:n] < self.life[:n]
        m = int(keep.sum())
        if m == 0:
            self.count = 0
            return
        if m < n:
            for arr in self._arrays:
                arr[:m] = arr[:n][keep]
        self.count = m

        d_mul = np.exp(-self.drag[:m] * dt)
        self.vel[:m] *= d_mul[:, None]
        self.vel[:m, 1] -= self.grav[:m] * dt
        self.pos[:m] += self.vel[:m] * dt

        hit = self.pos[:m, 1] < floor_y + 0.015
        if np.any(hit):
            b = self.bounce[:m][hit]
            self.pos[:m, 1][hit] = floor_y + 0.015
            vy = self.vel[:m, 1][hit]
            down = vy < -0.05
            self.vel[:m, 1][hit] = np.where(down, -vy * b, 0.0)
            fric = np.where(down, 0.65, 0.85)
            self.vel[:m, 0][hit] *= fric
            self.vel[:m, 2][hit] *= fric

    def pack(self):
        m = self.count
        if m <= 0:
            return None
        u = np.clip(self.age[:m] / self.life[:m], 0.0, 1.0)
        k = self.kind[:m]
        size = self.size0[:m] + (self.size1[:m] - self.size0[:m]) * np.sqrt(u)

        soft = (k == PKIND_SMOKE) | (k == PKIND_DUST)
        hot = (k == PKIND_SPARK) | (k == PKIND_EMBER)
        alpha = np.where(
            soft,
            np.minimum(1.0, u * 6.0) * np.power(1.0 - u, 1.35),
            np.where(hot, np.power(1.0 - u, 1.45), np.clip((1.0 - u) * 5.0, 0.0, 1.0)),
        ) * self.col[:m, 3]

        out = np.empty((m, 14), dtype=np.float32)
        out[:, 0:3] = self.pos[:m]
        out[:, 3:6] = self.vel[:m]
        out[:, 6:9] = self.col[:m, 0:3]
        out[:, 9] = alpha
        out[:, 10] = size
        out[:, 11] = k
        out[:, 12] = u
        out[:, 13] = self.seed[:m]
        return out

    def submit(self, r):
        arr = self.pack()
        if arr is not None:
            r.add_particles(arr)


class DecalPool:
    """Fixed-capacity vectorized ground-decal ring buffer."""

    def __init__(self, capacity=512):
        self.capacity = int(capacity)
        self.count = 0
        self._cursor = 0
        n = self.capacity
        self.pos = np.zeros((n, 3), dtype=np.float32)
        self.radius = np.zeros(n, dtype=np.float32)
        self.yaw = np.zeros(n, dtype=np.float32)
        self.col = np.zeros((n, 4), dtype=np.float32)
        self.age = np.zeros(n, dtype=np.float32)
        self.life = np.ones(n, dtype=np.float32)
        self.kind = np.zeros(n, dtype=np.float32)
        self.wet = np.zeros(n, dtype=np.float32)
        self._arrays = (
            self.pos, self.radius, self.yaw, self.col,
            self.age, self.life, self.kind, self.wet,
        )

    def clear(self):
        self.count = 0
        self._cursor = 0

    def add(self, kind, pos, radius, col=(82, 14, 16), yaw=0.0,
            life=45.0, alpha=0.92, wet=0.0):
        if self.count < self.capacity:
            i = self.count
            self.count += 1
        else:
            i = self._cursor % self.capacity
            self._cursor += 1
        self.pos[i] = pos
        self.radius[i] = max(0.05, float(radius))
        self.yaw[i] = float(yaw)
        self.col[i] = (col[0] / 255.0, col[1] / 255.0, col[2] / 255.0, float(alpha))
        self.age[i] = 0.0
        self.life[i] = max(0.5, float(life))
        self.kind[i] = float(kind)
        self.wet[i] = float(wet)

    def update(self, dt):
        n = self.count
        if n <= 0 or dt <= 0.0:
            return
        dt = min(0.05, float(dt))
        self.age[:n] += dt
        keep = self.age[:n] < self.life[:n]
        m = int(keep.sum())
        if m == 0:
            self.count = 0
            return
        if m < n:
            for arr in self._arrays:
                arr[:m] = arr[:n][keep]
        self.count = m

    def pack(self):
        m = self.count
        if m <= 0:
            return None
        rem = np.maximum(0.0, self.life[:m] - self.age[:m])
        fade = np.clip(rem / 3.0, 0.0, 1.0)
        out = np.empty((m, 11), dtype=np.float32)
        out[:, 0:3] = self.pos[:m]
        out[:, 3] = self.radius[:m]
        out[:, 4] = self.yaw[:m]
        out[:, 5:8] = self.col[:m, 0:3]
        out[:, 8] = self.col[:m, 3] * fade
        out[:, 9] = self.kind[:m]
        out[:, 10] = self.wet[:m] * fade
        return out

    def submit(self, r):
        arr = self.pack()
        if arr is not None:
            r.add_decals(arr)


def pack_dots(pts):
    """Convert ``[(pos3, col3, size), ...]`` into GPU particle rows."""
    n = len(pts)
    if n <= 0:
        return None
    out = np.zeros((n, 14), dtype=np.float32)
    out[:, 0:3] = np.asarray([p[0] for p in pts], dtype=np.float32)
    out[:, 6:9] = np.asarray([p[1][:3] for p in pts], dtype=np.float32) / 255.0
    out[:, 9] = 1.0
    out[:, 10] = np.asarray([0.045 + 0.018 * p[2] for p in pts], dtype=np.float32)
    out[:, 11] = PKIND_DEBRIS
    return out


def pack_blood_decals(decals, to3_fn, col=(82, 14, 16)):
    """Convert legacy ``STATE.blood_decals`` ``[x, y, alpha, rad_px]`` to GPU decal rows."""
    rows = []
    cr, cg, cb = col[0] / 255.0, col[1] / 255.0, col[2] / 255.0
    for d in decals:
        k = max(0.0, min(1.0, float(d[2]) / 255.0))
        if k <= 0.05:
            continue
        p = to3_fn(d[0], d[1], 0.015)
        rad_m = max(0.16, 0.25 + 0.35 * min(1.0, float(d[3]) / 24.0) * k)
        rows.append((p[0], p[1], p[2], rad_m, (float(d[0]) * 0.13) % math.tau,
                     cr, cg, cb, min(0.92, 0.45 + 0.47 * k), float(DKIND_BLOOD), 0.7 * k))
    if not rows:
        return None
    return np.asarray(rows, dtype=np.float32)
