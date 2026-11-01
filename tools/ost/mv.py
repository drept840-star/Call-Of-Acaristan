"""OST music videos: one short, loopable 3D scene per album track (engine3d, GL).

Each video loops on whole bars of one section of its track (``LOOPS``), so the
picture, the beat and the audio wrap together. Everything that moves is a
function of the loop: cameras orbit whole turns or cut on bar lines, particles
travel whole periods, props cycle per beat. ``Frame.a`` carries the loop's
audio envelopes (low/mid/high/kick, 0..1) for hit-driven light.

Rendered by tools/build_ost_videos.py. Needs the GL backend and ``src`` on
sys.path.
"""
import math

import numpy as np
import pygame

from engine3d import GLRenderer, Light, Mesh, box, quad_xz
from engine3d import core as C
from engine3d import ik
from engine3d.rig import POSES
from cutscenes.cast3d import humanoid3d
from cutscenes import m5fx3d as fx
from cutscenes.m5ending3d import solve_hand
import missions.m6.bloc3d as B

TAU = math.pi * 2.0
W, H = 640, 360

# track no -> (first bar, bars): the section each video loops
LOOPS = {1: (36, 8), 2: (24, 8), 3: (32, 8), 4: (48, 12), 5: (32, 8), 6: (40, 12), 7: (45, 12), 8: (28, 8)}


class Frame:
    def __init__(self, t, loop_s, spb, a):
        self.t, self.L, self.spb, self.a = t, loop_s, spb, a
        self.k = t / loop_s                 # loop progress 0..1
        self.beat = t / spb
        self.bar = self.beat / 4.0
        self.ms = int(t * 1000)


# ---------------------------------------------------------------- helpers

def smooth(x):
    x = min(1.0, max(0.0, x))
    return x * x * (3 - 2 * x)


def since(beat, hits, period=4.0):
    """Beats since the last hit of a repeating pattern (hits in beats within ``period``)."""
    p = beat % period
    return min((p - h) % period for h in hits)


def until(beat, hits, period=4.0):
    p = beat % period
    return min((h - p) % period for h in hits)


def hit(beat, hits, decay=0.25, period=4.0):
    return math.exp(-since(beat, hits, period) / decay)


def shot(f, bars):
    """(index, progress 0..1) of the current shot when the camera cuts every ``bars``."""
    b = f.bar + 1e-6                    # frame times land a hair short of the bar line
    return int(b // bars), (b % bars) / bars


def norm(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


def rot_y(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def rot_x(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def rot_z(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


class Part:
    """A mesh packed once and drawn per frame with a rigid transform, or as many copies."""

    def __init__(self, mesh):
        faces = [(fc[0], fc[1], fc[2], fc[3], None, fc[4]) for fc in mesh.faces]
        self.arr = GLRenderer.pack(mesh.verts, faces)

    def draw(self, r, t=(0, 0, 0), rot=None):
        a = self.arr.copy()
        if rot is not None:
            a[:, 0:3] = a[:, 0:3] @ rot.T
            a[:, 6:9] = a[:, 6:9] @ rot.T
        a[:, 0:3] += t
        r.add_packed(a)

    def many(self, r, offsets, scales=None):
        offsets = np.asarray(offsets, np.float32).reshape(-1, 3)
        if not len(offsets):
            return
        n = len(self.arr)
        a = np.tile(self.arr, (len(offsets), 1))
        if scales is not None:
            a[:, 0:3] *= np.repeat(np.asarray(scales, np.float32), n)[:, None]
        a[:, 0:3] += np.repeat(offsets, n, axis=0)
        r.add_packed(a)


def mesh_of(*parts):
    m = Mesh()
    for p in parts:
        m.add(p)
    return m


def peak(m, cx, cz, r, h, col, y0=0.0):
    """Four-sided mountain or fir: a pyramid with outward faces."""
    apex = (cx, y0 + h, cz)
    base = [(cx - r, y0, cz - r), (cx + r, y0, cz - r), (cx + r, y0, cz + r), (cx - r, y0, cz + r)]
    for i in range(4):
        a, b = base[i], base[(i + 1) % 4]
        m.face([a, apex, b], col)


def noise2(seed, octaves=4, base=1 / 240.0):
    """Smooth 2D noise in about -1..1: rotated sine products, one per octave."""
    rng = np.random.default_rng(seed)
    waves = []
    for o in range(octaves):
        rot = rng.uniform(0, TAU)
        waves.append((math.cos(rot), math.sin(rot), rng.uniform(0, TAU), rng.uniform(0, TAU),
                      base * 2 ** o * rng.uniform(0.8, 1.25) * TAU, 0.5 ** o))

    def f(x, z):
        v = 0.0
        for c, s, a, b, fr, amp in waves:
            v += amp * math.sin((x * c + z * s) * fr + a) * math.sin((z * c - x * s) * fr + b)
        return v
    return f


def terrain(m, x0, z0, x1, z1, cell, hfn, colfn, layer=2):
    """Heightfield as lit triangles; ``colfn(x, y, z, ny)`` colours each face from its centre and slope."""
    nx, nz = int(round((x1 - x0) / cell)), int(round((z1 - z0) / cell))
    xs, zs = np.linspace(x0, x1, nx + 1), np.linspace(z0, z1, nz + 1)
    hs = [[hfn(x, z) for x in xs] for z in zs]
    for j in range(nz):
        for i in range(nx):
            p = [(xs[i], hs[j][i], zs[j]), (xs[i], hs[j + 1][i], zs[j + 1]),
                 (xs[i + 1], hs[j][i + 1], zs[j]), (xs[i + 1], hs[j + 1][i + 1], zs[j + 1])]
            for tri in ((p[0], p[1], p[2]), (p[2], p[1], p[3])):
                a, b, c = (np.array(v) for v in tri)
                n = norm(np.cross(b - a, c - a))
                cx, cy, cz = (a + b + c) / 3
                m.face(list(tri), colfn(cx, cy, cz, n[1]), layer)


def dome(m, radius, colfn, n_az=48):
    """Emissive sky dome around the origin; ``colfn(direction)`` colours each band cell."""
    elev = [-20, -4, 0, 2, 4, 6, 9, 12, 16, 21, 27, 35, 45, 58, 72, 89.9]
    for e0, e1 in zip(elev[:-1], elev[1:]):
        for k in range(n_az):
            a0, a1 = TAU * k / n_az, TAU * (k + 1) / n_az

            def at(e, a):
                e = math.radians(e)
                return (radius * math.cos(e) * math.sin(a), radius * math.sin(e), radius * math.cos(e) * math.cos(a))
            mid = norm(at((e0 + e1) / 2, (a0 + a1) / 2))
            m.face([at(e0, a0), at(e1, a0), at(e1, a1), at(e0, a1)], colfn(mid), 0, double=True, emissive=True)


def disc(m, direction, dist, rad, col, n=12):
    """Emissive disc facing the origin (a sun or moon on the dome)."""
    d = norm(direction)
    u = norm(np.cross(d, (0, 1, 0)))
    v = np.cross(u, d)
    c = d * dist
    m.face([tuple(c + rad * (u * math.cos(TAU * i / n) + v * math.sin(TAU * i / n))) for i in range(n)],
           col, 0, double=True, emissive=True)


def mix(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def aim(d, up=(0, 1, 0)):
    """Rotation taking +z to ``d`` (and +y as close to ``up`` as it can)."""
    z = norm(d)
    x = np.cross(up, z)
    x = norm(x) if np.linalg.norm(x) > 1e-6 else np.array([1.0, 0, 0])
    return np.column_stack([x, np.cross(z, x), z])


def side_prism(profile, x0, x1, col, cols=None):
    """Convex side profile [(z, y)...] extruded across the car from x0 to x1."""
    m = C.prism([(-z, y) for z, y in profile], x1 - x0, col, z0=x0, cols=cols)
    return Mesh().add(m, C.rot_y(90))


def sedan(body=(172, 164, 136), glass=(24, 30, 40), chrome=(150, 150, 146)):
    """Boxy Soviet saloon, nose at +z, wheels on y = 0."""
    m = Mesh()
    dark, tyre = (12, 12, 14), (7, 7, 8)
    hw = 0.81
    m.add(side_prism([(-2.08, 0.3), (2.08, 0.3), (2.13, 0.5), (2.09, 0.74), (1.0, 0.8), (-1.3, 0.82),
                      (-2.08, 0.79), (-2.13, 0.5)], -hw, hw, body))
    m.add(side_prism([(1.0, 0.8), (0.24, 1.32), (-0.86, 1.34), (-1.36, 0.82)], -0.72, 0.72, glass))
    m.add(box(1.48, 0.05, 1.12, body, center=(0, 1.35, -0.31)))
    for sx in (-1, 1):
        x = sx * 0.72
        m.add(box(0.07, 0.07, 0.92, body), C.rot_x(35.3), (x, 1.065, 0.62))      # A pillar
        m.add(box(0.07, 0.07, 0.73, body), C.rot_x(-46.7), (x, 1.085, -1.1))     # C pillar
        m.add(box(0.07, 0.52, 0.1, body, center=(x, 1.07, -0.3)))                 # B pillar
        xs = sx * (hw + 0.004)
        m.add(box(0.012, 0.03, 4.0, chrome, center=(xs, 0.62, 0)))
        for z in (0.96, -0.3, -1.32):
            m.add(box(0.012, 0.42, 0.015, dark, center=(xs, 0.55, z)))
        for z in (0.5, -0.8):
            m.add(box(0.016, 0.03, 0.12, chrome, center=(xs, 0.7, z)))
        m.add(box(0.08, 0.07, 0.1, body, center=(sx * 0.88, 0.9, 0.92)))
        m.add(box(0.012, 0.06, 0.08, glass, center=(sx * 0.92, 0.9, 0.92)))
        for z in (1.27, -1.22):
            m.add(box(0.012, 0.4, 0.8, dark, center=(xs, 0.45, z)))            # wheel well
            wx0 = sx * 0.79 - 0.1
            m.add(side_prism([(z + 0.3 * math.cos(TAU * k / 8 + math.pi / 8), 0.3 + 0.3 * math.sin(TAU * k / 8 + math.pi / 8))
                              for k in range(8)], wx0, wx0 + 0.22, tyre))
            hx0 = sx * 0.9 - 0.01
            m.add(side_prism([(z + 0.15 * math.cos(TAU * k / 8), 0.3 + 0.15 * math.sin(TAU * k / 8)) for k in range(8)],
                             hx0, hx0 + 0.02, chrome))
    m.add(box(1.12, 0.2, 0.03, dark, center=(0, 0.6, 2.13)))                       # grille
    m.add(box(1.16, 0.02, 0.035, chrome, center=(0, 0.71, 2.13)))
    for x in (-0.62, -0.42, 0.42, 0.62):
        m.add(box(0.15, 0.15, 0.03, (255, 244, 210), center=(x, 0.6, 2.15), emissive=True))
    for z in (2.17, -2.17):
        m.add(box(1.72, 0.1, 0.1, chrome, center=(0, 0.38, z)))
    m.add(box(0.44, 0.1, 0.02, (220, 220, 210), center=(0, 0.27, 2.17)))
    m.add(box(0.44, 0.1, 0.02, (220, 220, 210), center=(0, 0.56, -2.15)))
    for sx in (-1, 1):
        m.add(box(0.36, 0.15, 0.03, (220, 30, 24), center=(sx * 0.58, 0.62, -2.13), emissive=True))
        m.add(box(0.1, 0.15, 0.03, (230, 140, 30), center=(sx * 0.32, 0.62, -2.13)))
    m.add(quad_xz(-0.9, -2.2, 0.9, 2.2, 0.012, (8, 8, 10)))
    return m


def ak_mesh(svd=False):
    """AKM (or SVD with ``svd``) in the rig's rifle frame: origin = right hand on the grip, +z = muzzle."""
    m = Mesh()
    wood, steel, dark = (92, 56, 32), (40, 42, 46), (22, 22, 25)
    n = 0.26 if svd else 0.0

    def ob(w, h, d, col, c, rx=0.0):
        m.add(box(w, h, d, col), C.rot_x(rx), c)
    m.add(side_prism([(-0.1, 0.085), (-0.1, 0.03), (-0.4, -0.04), (-0.42, -0.04), (-0.42, 0.075)],
                     -0.022, 0.022, wood))                                  # stock
    ob(0.034, 0.1, 0.045, wood if svd else dark, (0, -0.03, -0.01), 18)     # pistol grip
    ob(0.05, 0.07, 0.3, steel, (0, 0.05, 0.06))                             # receiver
    ob(0.046, 0.02, 0.28, dark, (0, 0.093, 0.05))                           # dust cover
    ob(0.03, 0.03, 0.04, dark, (0, 0.1, 0.2))                               # rear sight block
    ob(0.012, 0.03, 0.05, steel, (0, 0.005, 0.03))                          # trigger guard
    if not svd:
        ob(0.03, 0.1, 0.065, dark, (0, -0.02, 0.14), -10)                   # curved magazine
        ob(0.03, 0.09, 0.06, dark, (0, -0.1, 0.165), -26)
    else:
        ob(0.03, 0.08, 0.06, dark, (0, -0.01, 0.13))
        ob(0.04, 0.05, 0.24, (14, 14, 16), (0, 0.155, 0.08))               # scope
        ob(0.05, 0.055, 0.03, (14, 14, 16), (0, 0.155, 0.21))
        ob(0.02, 0.04, 0.02, dark, (0, 0.115, 0.08))
    ob(0.054, 0.05, 0.17 + n * 0.3, wood, (0, 0.042, 0.3 + n * 0.15))     # lower handguard
    ob(0.04, 0.026, 0.15 + n * 0.3, wood, (0, 0.085, 0.29 + n * 0.15))    # gas tube cover
    ob(0.022, 0.022, 0.3 + n, dark, (0, 0.055, 0.5 + n * 0.5))             # barrel
    ob(0.03, 0.045, 0.03, steel, (0, 0.07, 0.4 + n))                        # gas block
    ob(0.012, 0.045, 0.014, dark, (0, 0.09, 0.62 + n))                      # front sight
    ob(0.032, 0.032, 0.045, dark, (0, 0.055, 0.66 + n))                     # muzzle brake
    return m


def carry(hum, phase):
    """March at port arms: rifle across the chest, muzzle up-left, both hands on it."""
    p = march(phase, rifle=False)
    p.update(twist=6, rifle_p=-38, rifle_y=-58)
    p = solve_hand(hum, p, "r", (0.12, 0.2, 0.19))
    _, j, R, _ = hum.placements(p)
    guard = np.asarray(j["rhand"]) + C.m_apply(R, (0, 0.02, 0.31))
    return solve_hand(hum, p, "l", tuple(guard))


def to_world(pos, yaw, local):
    """Actor-local (x right, y up, z forward) to world for an actor at ``pos`` turned ``yaw`` degrees."""
    return np.asarray(pos, float) + rot_y(math.radians(yaw)) @ np.asarray(local, float)


def field(n, seed, lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return lo + np.random.default_rng(seed).random((n, 3)) * (hi - lo)


def wrapped(base, lo, hi, cycles, k):
    """Particles moved ``cycles`` (per axis, integer per loop) box lengths by loop progress ``k``."""
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    size = hi - lo
    return lo + np.mod(base - lo + np.asarray(cycles, float) * size * k, size)


def streaks(r, pts, d, col, width=1):
    r.add_lines3d([(tuple(p), tuple(p + d), col, width) for p in pts], layer=5)


def glow(r, pos, col, radius, k=1.0, core=None):
    r.add_sprite(tuple(pos), fx.glow(col, radius, 0, core=core, intensity=k), layer=fx.FX_LAYER)


def gradient(top, bottom, horizon=0.62):
    s = pygame.Surface((W, H))
    for y in range(H):
        u = min(1.0, y / (H * horizon))
        s.fill(tuple(int(top[i] + (bottom[i] - top[i]) * u ** 1.6) for i in range(3)), (0, y, W, 1))
    return s


_VIG = {}


def vignette(surf, strength):
    v = _VIG.get(strength)
    if v is None:
        xx, yy = np.mgrid[0:W, 0:H]
        rr = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        a = (np.clip((rr - 0.55) / 0.75, 0, 1) ** 1.8 * 255 * strength).astype(np.uint8)
        v = pygame.Surface((W, H), pygame.SRCALPHA)
        pygame.surfarray.pixels_alpha(v)[:] = a
        _VIG[strength] = v
    surf.blit(v, (0, 0))


def add_light(surf, col, k):
    if k > 0.01:
        surf.fill(tuple(min(255, int(c * k)) for c in col), special_flags=pygame.BLEND_ADD)


def disc_on_sky(r, surf, direction, rad_px, col, halo_col=None, halo_px=0):
    p = r.project(tuple(np.asarray(r.cam) + norm(direction) * 900.0))
    if p is None:
        return None
    x, y = p[0], p[1]
    if halo_col and halo_px:
        fx._add_at(surf, fx._halo(halo_col, halo_px, 1.8), x, y)
    pygame.draw.circle(surf, col, (int(x), int(y)), rad_px)
    return x, y


def stars(r, surf, seed=3, n=160, col=(150, 156, 180)):
    rng = np.random.default_rng(seed)
    for _ in range(n):
        d = norm((rng.uniform(-1, 1), rng.uniform(0.08, 1.0), rng.uniform(-1, 1)))
        p = r.project(tuple(np.asarray(r.cam) + d * 900.0))
        if p is not None and 0 <= p[0] < W and 0 <= p[1] < H:
            c = tuple(int(v * rng.uniform(0.4, 1.0)) for v in col)
            surf.set_at((int(p[0]), int(p[1])), c)


def soldier(**kw):
    spec = dict(jacket=(52, 58, 44), pants=(46, 50, 40), boots=(20, 20, 20), helmet=(58, 64, 50), rifle="rifle")
    spec.update(kw)
    return humanoid3d("civilian", **spec)


def pose(name=None, **kw):
    p = dict(POSES[name]) if name else {}
    p.update(kw)
    return p


def march(phase, rifle=True):
    s, c = math.sin(phase), math.cos(phase)
    p = dict(spine=4, head_p=-2, lhip_p=26 * s, rhip_p=-26 * s, lkn=8 + 34 * max(0.0, -c),
             rkn=8 + 34 * max(0.0, c), lsh_p=10 - 22 * s, lsh_r=8, lel=24, lift=0.03 * abs(c))
    if rifle:
        p.update(rsh_p=22, rsh_r=14, rel=58, rifle_p=30)
    else:
        p.update(rsh_p=10 + 22 * s, rsh_r=8, rel=24)
    return p


def city(add, seed, n, xr, zr, hr, facing, y0=0.0, lit=0.3, col=(48, 50, 58)):
    rng = np.random.default_rng(seed)
    for i in range(n):
        cx, cz = rng.uniform(*xr), rng.uniform(*zr)
        w, d = (rng.uniform(10, 16), rng.uniform(7, 10)) if facing in ("+z", "-z") else (rng.uniform(7, 10), rng.uniform(10, 16))
        B.panel_block(lambda mm: add(mm, t=(0, y0, 0)), cx, cz, w, rng.uniform(*hr), d, facing,
                      seed=seed * 100 + i, col=col, lit=lit, balconies=False)


# ---------------------------------------------------------------- base scene

class Scene:
    fog, fog_start, fog_end = (0, 0, 0), 20.0, 120.0
    sky = ((0, 0, 0), (0, 0, 0))
    light = dict(direction=(-0.4, 0.7, -0.4), ambient=0.4, diffuse=0.6)
    vig = 0.55

    def __init__(self, title):
        self.title = title
        self.r = GLRenderer(W, H, fog=self.fog, fog_start=self.fog_start, fog_end=self.fog_end)
        self.r.light = Light(**self.light)
        m = Mesh()
        self.build(m)
        if m.faces:
            self.r.bake(m)
        self._sky = gradient(*self.sky)
        self._font = None

    def build(self, m):
        pass

    def camera(self, f):
        raise NotImplementedError

    def backdrop(self, surf, f):
        pass

    def frame(self, r, f):
        pass

    def post(self, surf, f):
        pass

    def draw(self, surf, f):
        r = self.r
        r.begin()
        r.set_lights([])
        r.set_pools([])
        pos, target, fov = self.camera(f)
        r.set_camera(tuple(pos), tuple(target), fov)
        surf.blit(self._sky, (0, 0))
        self.backdrop(surf, f)
        r.add_static()
        self.frame(r, f)
        r.flush(surf)
        self.post(surf, f)
        vignette(surf, self.vig)
        self.caption(surf)

    def caption(self, surf):
        if self._font is None:
            from ui.pixfont import font
            self._font = font("R7", 1)
        y = H - 20
        for dx, dy, col in ((1, 1, (0, 0, 0)), (0, 0, (226, 220, 204))):
            self._font.draw(surf, self.title.upper(), (14 + dx, y + dy), col)

    def release(self):
        self.r.release()


# ---------------------------------------------------------------- 1. Call of Acaristan

class CallOfAcaristan(Scene):
    """Dusk on a ridge above the Bloc. Biribel watches the city; one slow orbit per loop."""
    fog, fog_start, fog_end = (150, 80, 70), 140.0, 1000.0
    sky = ((22, 20, 44), (204, 100, 64))
    light = dict(direction=(0.15, 0.32, 1.0), ambient=0.36, diffuse=0.8, sky=0.12, tint=(1.0, 0.72, 0.56))
    SUN = (0.05, 0.035, 1.0)
    HERO = (0.0, 0.0, 6.0)

    def sky_col(self, d):
        e = math.degrees(math.asin(max(-1.0, min(1.0, d[1]))))
        sun = norm(self.SUN)
        toward = max(0.0, float(np.dot(norm((d[0], 0, d[2])), norm((sun[0], 0, sun[2])))))
        horizon = mix((112, 62, 86), (214, 108, 66), toward ** 1.5)
        if e < 14:
            c = mix(horizon, (120, 64, 84), e / 14)
        elif e < 40:
            c = mix((120, 64, 84), (54, 38, 72), (e - 14) / 26)
        else:
            c = mix((54, 38, 72), (20, 18, 42), (e - 40) / 50)
        near = math.exp(-math.acos(max(-1.0, min(1.0, float(np.dot(d, sun))))) / 0.18)
        return mix(c, (255, 184, 120), near)

    def ground_h(self, x, z):
        d = math.hypot(x, z - 100)
        rise = smooth((d - 430) / 260)
        ridge = 1 - abs(self.n_ridge(x, z))
        off_city = max(smooth((abs(x) - 160) / 40), smooth((abs(z - 150) - 95) / 40))
        hills = self.n_hill(x, z) * 8 * off_city
        return -30 + hills + rise * (20 + 130 * ridge ** 2 + 20 * self.n_hill(z, x))

    def ground_col(self, x, y, z, ny):
        h = y + 30
        c = mix((46, 40, 46), (74, 58, 70), h / 120)
        c = mix(c, (44, 36, 46), (1 - ny) * 1.6)
        if h > 95 and ny > 0.55:
            c = mix(c, (176, 150, 160), (h - 95) / 35)
        v = int(((x * 7 + z * 13) // 1) % 7) - 3
        return tuple(max(0, min(255, q + v)) for q in c)

    def build(self, m):
        self.n_ridge, self.n_hill = noise2(31, 4, 1 / 260.0), noise2(32, 3, 1 / 140.0)
        dome(m, 1250.0, self.sky_col)
        disc(m, self.SUN, 1200.0, 34.0, (255, 226, 170))
        terrain(m, -1000, -850, 1000, 1150, 40, self.ground_h, self.ground_col)
        rock, grass = (66, 58, 52), (58, 56, 40)
        m.add(box(28, 30, 28, rock, center=(0, -15, 0), cols={"top": grass}))
        rng = np.random.default_rng(1)
        for i in range(26):
            a = TAU * i / 26
            rr = rng.uniform(12, 16)
            w, h = rng.uniform(3, 7), rng.uniform(4, 30)
            m.add(box(w, h, w, rock, center=(math.sin(a) * rr, -h / 2 - rng.uniform(0, 2), math.cos(a) * rr),
                      cols={"top": grass}))
        for i in range(9):
            m.add(box(*rng.uniform(0.3, 1.1, 3), (80, 72, 64),
                      center=(rng.uniform(-9, 9), 0.2, rng.uniform(-9, 4))))
        city(m.add, 11, 46, (-150, 150), (70, 230), (14, 44), "-z", y0=-30, lit=0.42, col=(58, 56, 66))
        self.beacons = []
        for x, z, h in ((-40, 120, 52), (25, 150, 60), (80, 95, 46)):
            self.beacons += [(p[0], p[1] - 30, p[2]) for p in B.smokestack(lambda mm: m.add(mm, t=(0, -30, 0)), x, z, h)]
        B.letters(m.add, "АКАРИСТАН", (0, 15, 66), "-z", px=0.7, col=B.NEON_RED)
        m.add(box(26, 45, 6, (52, 50, 58), center=(0, -9.5, 69.1)))
        self.hum = humanoid3d("biribel")
        self.embers = field(140, 5, (-14, -2, -8), (14, 9, 20))
        self.ember = Part(box(0.06, 0.06, 0.06, (255, 150, 70), emissive=True))

    def camera(self, f):
        a = TAU * f.k
        hx, _, hz = self.HERO
        y = 1.1 + 0.7 * math.sin(TAU * f.k * 2)
        sh = 0.04 * f.a["kick"]
        pos = (hx - 6.8 * math.sin(a), y + sh, hz - 6.8 * math.cos(a))
        return pos, (hx, 1.35 + sh * 0.5, hz), 48

    def frame(self, r, f):
        look = 26 * math.sin(TAU * f.beat / 8)
        breath = 2 * math.sin(TAU * f.beat / 4)
        r.add_humanoid(self.hum, pose(None, head_y=look, spine=3 + breath, head_p=-4), self.HERO, 0)
        pts = wrapped(self.embers, (-14, -2, -8), (14, 9, 20), (2, 1, 0), f.k)
        self.ember.many(r, pts)
        for i, b in enumerate(self.beacons[::3]):
            glow(r, b, (255, 60, 40), 3.0, 0.6 + 0.4 * (since(f.beat, [i % 4]) < 1))

    def post(self, surf, f):
        add_light(surf, (70, 30, 12), f.a["kick"] * 0.9)


# ---------------------------------------------------------------- 2. Black Notebook

class BlackNotebook(Scene):
    """Rain on a night street. Volkov writes in the black notebook under a sodium lamp."""
    fog, fog_start, fog_end = (14, 16, 24), 6.0, 60.0
    sky = ((5, 6, 12), (22, 24, 36))
    light = dict(direction=(-0.3, 0.8, -0.4), ambient=0.26, diffuse=0.32, sky=0.08, tint=(0.75, 0.82, 1.0))
    VOLKOV = np.array([4.8, 0.0, 1.2])
    LAMP = (4.5, 4.45, 1.0)

    def build(self, m):
        m.add(quad_xz(-4, -40, 4, 70, 0, (24, 26, 32), seg=8))
        for x in (-5.25, 5.25):
            m.add(box(2.5, 0.15, 110, (48, 48, 54), center=(x, 0.075, 15), seg=8))
        for z in range(-36, 64, 16):
            for side, face in ((-1, "+x"), (1, "-x")):
                h = 12 + (z * 7 % 9)
                B.panel_block(m.add, side * 11, z, 8, h, 14, face, seed=z * 3 + side, col=(40, 40, 46), lit=0.18,
                              balconies=False)
        m.add(box(0.14, 4.6, 0.14, (30, 30, 34), center=(5.7, 2.3, 1.0)))
        m.add(box(1.3, 0.1, 0.1, (30, 30, 34), center=(5.1, 4.55, 1.0)))
        m.add(box(0.5, 0.12, 0.3, (255, 236, 170), center=self.LAMP, emissive=True))
        body, dark = (74, 30, 28), (20, 24, 32)
        m.add(box(1.7, 0.75, 4.2, body, center=(-2.6, 0.55, 6.0)))
        m.add(box(1.5, 0.55, 2.2, dark, center=(-2.6, 1.2, 5.8)))
        m.add(box(1.5, 0.06, 2.2, body, center=(-2.6, 1.5, 5.8)))
        for x, z in ((-1.8, 4.7), (-3.4, 4.7), (-1.8, 7.3), (-3.4, 7.3)):
            m.add(box(0.2, 0.55, 0.55, (14, 14, 16), center=(x, 0.28, z)))
        for x, z, w in ((1.5, 2.0, 2.2), (-1.0, -3.0, 1.6), (2.4, 9.0, 1.8)):
            m.add(quad_xz(x - w, z - w * 0.4, x + w, z + w * 0.4, 0.01, (14, 16, 24)))
        self.hum = humanoid3d("volkov")
        self.book = Part(mesh_of(box(0.28, 0.02, 0.32, (14, 14, 16)),
                                 box(0.26, 0.008, 0.3, (214, 206, 180), center=(0, 0.014, 0)),
                                 box(0.006, 0.01, 0.3, (120, 114, 100), center=(0, 0.02, 0)),
                                 *[box(0.1, 0.003, 0.004, (90, 86, 80), center=(0.075, 0.019, -0.11 + 0.03 * k))
                                   for k in range(6)]))
        self.pen = Part(mesh_of(box(0.012, 0.012, 0.13, (20, 20, 22), center=(0, 0, 0.065)),
                                box(0.006, 0.006, 0.012, (180, 170, 120), center=(0, 0, 0.004))))
        self.rain = field(800, 2, (-8, 0, -8), (9, 10, 16))
        self.fall = np.random.default_rng(3).integers(14, 20, 800)

    def camera(self, f):
        i, u = shot(f, 2)
        V = self.VOLKOV
        push = 0.12 * f.a["kick"]
        if i % 4 == 0:
            a = math.radians(-120 + 30 * u)
            return (V[0] + 7 * math.sin(a), 2.2, V[2] + 7 * math.cos(a)), (V[0], 1.4, V[2]), 50 - push * 10
        if i % 4 == 1:
            return (V[0] - 2.2, 1.65, V[2] - 1.8 + 0.4 * u), (V[0] - 0.3, 1.4, V[2]), 46 - push * 10
        if i % 4 == 2:
            return (-1.5 + 1.2 * u, 0.5, -9.0), (V[0] - 1, 1.7, V[2] + 1), 46 - push * 10
        # over his right shoulder onto the page
        return (V[0] + 0.35, 2.95 - 0.1 * u, V[2] + 0.95), (V[0] - 0.45, 1.3, V[2] - 0.05), 52 - push * 8

    def frame(self, r, f):
        r.set_pools([dict(pos=self.LAMP, range=5.0, color=(255, 186, 104), intensity=1.0, hot=(255, 226, 170))])
        r.set_lights([dict(pos=self.LAMP, color=(255, 196, 120), intensity=1.3, range=7.0, kind="point")])
        phrase = f.beat % 8
        up = smooth((phrase - 6.0) / 0.6) * (1 - smooth((phrase - 7.6) / 0.4))
        pos, yaw = tuple(self.VOLKOV), -90
        p = dict(spine=8, head_p=30 - 32 * up, head_y=-20 * up)
        chest = np.asarray(self.hum.pose_world(p, pos, yaw, rifle_on=False)[1]["chest"])
        # notebook held open in front of the chest, tipped toward his face
        R = rot_y(math.radians(yaw)) @ rot_x(-0.6)
        c = chest + rot_y(math.radians(yaw)) @ np.array([-0.02, -0.12, 0.36])
        right = norm(np.subtract(ik.shoulder_world(self.hum, p, pos, yaw, "r"), ik.shoulder_world(self.hum, p, pos, yaw, "l")))
        along, normal = R[:, 2], R[:, 1]
        p = ik.solve_arm(self.hum, p, pos, yaw, "l", tuple(c - right * 0.15 - normal * 0.04), pole=(-1.0, -0.6, -0.2))
        # pen hand: short strokes across the page, lifted at the end of each line
        stroke = (f.beat * 2) % 1.0
        lift = smooth((stroke - 0.8) / 0.2) * (1 - up)
        tip = c + right * (0.02 + 0.09 * stroke) + along * (0.08 - 0.04 * int(f.beat * 2 % 4)) + normal * (0.012 + 0.03 * lift + 0.08 * up)
        pen_dir = norm(normal * 0.8 + right * 0.45 - along * 0.35)
        p = ik.solve_arm(self.hum, p, pos, yaw, "r", tuple(tip + pen_dir * 0.07 + right * 0.02), pole=(1.0, -0.7, -0.3))
        r.add_humanoid(self.hum, p, pos, yaw)
        self.book.draw(r, c, R)
        self.pen.draw(r, tip, aim(pen_dir))
        glow(r, self.LAMP, (255, 181, 79), 2.4, 0.8 + 0.25 * f.a["kick"], core=(255, 246, 210))
        r.add_sprite((self.LAMP[0], 0.02, self.LAMP[2]), fx.wet_reflection((255, 170, 90), 0, length_m=2.6), layer=1)
        pts = wrapped(self.rain, (-8, 0, -8), (9, 10, 16), np.stack([np.zeros(800), -self.fall, np.zeros(800)], 1), f.k)
        streaks(r, pts, np.array([0.04, -0.4, 0.0]), (110, 118, 146))

    def post(self, surf, f):
        add_light(surf, (30, 34, 50), 0.5 * f.a["mid"] ** 2)


# ---------------------------------------------------------------- 3. Quiet on Route 12

class QuietOnRoute12(Scene):
    """A car on Route 12 at night: a pole a beat, a dash every half beat. Ucilev waits on the verge."""
    fog, fog_start, fog_end = (12, 14, 26), 20.0, 150.0
    sky = ((3, 5, 14), (26, 30, 52))
    light = dict(direction=(0.3, 0.6, 0.5), ambient=0.24, diffuse=0.36, sky=0.1, tint=(0.7, 0.78, 1.0))
    MOON = (-0.35, 0.32, 1.0)
    SPAN = 256.0

    def build(self, m):
        m.add(quad_xz(-500, -500, 500, 500, -0.02, (20, 26, 26)))
        m.add(quad_xz(-3.5, -500, 3.5, 500, 0, (34, 34, 38)))
        rng = np.random.default_rng(4)
        for i in range(40):
            a = TAU * i / 40
            rr = rng.uniform(260, 340)
            peak(m, math.sin(a) * rr, math.cos(a) * rr, rng.uniform(40, 80), rng.uniform(30, 70), (16, 18, 30))
        self.dash = Part(box(0.15, 0.02, 2.0, (196, 186, 150)))
        pole = mesh_of(box(0.22, 7.0, 0.22, (44, 38, 34), center=(0, 3.5, 0)),
                       box(2.2, 0.14, 0.14, (44, 38, 34), center=(0, 6.6, 0)))
        self.pole = Part(pole)
        seg = Mesh()
        for _ in range(60):
            x = rng.choice([-1, 1]) * rng.uniform(9, 70)
            peak(seg, x, rng.uniform(0, 64), rng.uniform(0.8, 1.6), rng.uniform(3, 7), (18, 32, 28))
        for _ in range(14):
            x = rng.choice([-1, 1]) * rng.uniform(14, 80)
            seg.add(box(rng.uniform(10, 24), rng.uniform(1, 4), rng.uniform(10, 20), (22, 28, 28),
                        center=(x, 0.5, rng.uniform(0, 64))))
        self.seg = Part(seg)
        car = sedan()
        self.car = Part(car)
        self.mound = Part(box(5, 1.0, 5, (22, 30, 28), center=(0, 0.5, 0)))
        self.sniper = humanoid3d("ucilev", rifle="sniper")

    def camera(self, f):
        i, u = shot(f, 2)
        sway = 0.3 * math.sin(TAU * u)
        if i == 0:
            return (1.2 + sway, 2.4, -7.5), (0, 1.0, 6), 52
        if i == 1:
            return (-5.5, 0.8, 3.0 - 2 * u), (0, 0.8, 0), 50
        if i == 2:
            return (0.8 + sway, 0.6, 9.0), (0, 0.8, 0), 45
        zs = self.sniper_z(f)
        return (-12.0, 2.2, zs + 2.0), (0, 0.8, 0), 46

    def sniper_z(self, f):
        return (32 - 12 * f.t) % self.SPAN - 64

    def backdrop(self, surf, f):
        stars(self.r, surf)
        disc_on_sky(self.r, surf, self.MOON, 9, (226, 230, 214), (40, 46, 70), 60)

    def frame(self, r, f):
        v = self.SPAN / f.L
        shift = (v * f.t)
        r.set_lights([dict(pos=(0, 0.7, 2.1), dir=tuple(norm((0, -0.12, 1))), cone=math.cos(math.radians(24)),
                           range=42.0, intensity=1.7, color=(255, 240, 200), kind="spot")])
        r.set_pools([dict(pos=(0, 2.0, 11.0), range=8.0, color=(200, 190, 150), intensity=0.7)])
        zs = (np.arange(0, self.SPAN, 4.0) - shift) % self.SPAN - 64
        self.dash.many(r, np.stack([np.zeros_like(zs), np.full_like(zs, 0.01), zs], 1))
        zp = (np.arange(0, self.SPAN, 8.0) + 3 - shift) % self.SPAN - 64
        self.pole.many(r, np.stack([np.full_like(zp, 5.0), np.zeros_like(zp), zp], 1))
        zp.sort()
        wires = []
        for a, b in zip(zp[:-1], zp[1:]):
            for x in (4.1, 5.9):
                wires.append(((x, 6.7, a), (x, 6.7, b), (30, 32, 40), 1))
        r.add_lines3d(wires, layer=4)
        segz = (np.arange(0, self.SPAN, 64.0) - shift) % self.SPAN - 64
        self.seg.many(r, np.stack([np.zeros_like(segz), np.zeros_like(segz), segz], 1))
        bob = 0.025 * f.a["kick"] + 0.01 * math.sin(TAU * f.beat)
        self.car.draw(r, (0, bob, 0))
        cz = r.cam[2]
        for x in (-0.52, 0.52):
            if cz > 0:
                glow(r, (x, 0.6 + bob, 2.18), (255, 236, 190), 0.5, 0.9, core=(255, 255, 240))
            else:
                glow(r, (x * 1.12, 0.62 + bob, -2.16), (220, 40, 30), 0.35, 0.8)
        z = self.sniper_z(f)
        self.mound.draw(r, (-10, 0, z))
        r.add_humanoid(self.sniper, pose("prone"), (-10, 1.0, z), 90)
        near = max(0.0, 1.0 - abs(z) / 18.0)
        if near > 0:
            r.add_sprite((-9.2, 1.25, z), fx.scope_glint(near), layer=fx.FX_LAYER)

    def post(self, surf, f):
        add_light(surf, (16, 18, 30), 0.6 * f.a["kick"])


# ---------------------------------------------------------------- 4. The Vostral

class TheVostral(Scene):
    """The Vostral factory floor: presses slam on the kick, plates ride the belt, the furnace breathes."""
    fog, fog_start, fog_end = (40, 26, 18), 15.0, 70.0
    sky = ((18, 12, 10), (30, 20, 14))
    light = dict(direction=(0.2, 0.8, 0.3), ambient=0.3, diffuse=0.45, sky=0.08, tint=(1.0, 0.8, 0.62))
    PRESSES = ((-8.0, [0, 2]), (0.0, [1, 3]), (8.0, [2.5]))
    LAMPS = [(x, 7.0, z) for x in (-4, 4) for z in (-20, -10, 0, 10, 20)]
    FURNACE = (0.0, 2.2, 29.6)

    def build(self, m):
        m.add(quad_xz(-12, -30, 12, 30, 0, (54, 48, 42), seg=6))
        wall = (46, 40, 36)
        for x in (-12.3, 12.3):
            m.add(box(0.6, 12, 60, wall, center=(x, 6, 0), seg=6))
        m.add(box(24, 12, 0.6, wall, center=(0, 6, 30.3), seg=6))
        m.add(box(24, 12, 0.6, wall, center=(0, 6, -30.3), seg=6))
        m.add(box(24, 0.4, 60, (24, 20, 18), center=(0, 12, 0), seg=8))
        for z in range(-28, 30, 6):
            m.add(box(24, 0.6, 0.4, (36, 32, 30), center=(0, 11.4, z)))
        for z in range(-24, 28, 8):
            for x in (-7, 7):
                m.add(box(0.6, 11, 0.6, (60, 54, 48), center=(x, 5.5, z)))
        for p in self.LAMPS:
            m.add(box(0.05, 4.6, 0.05, (20, 20, 20), center=(p[0], 9.4, p[2])))
            m.add(box(0.8, 0.2, 0.8, (40, 36, 32), center=(p[0], p[1] + 0.2, p[2])))
            m.add(box(0.3, 0.1, 0.3, (255, 210, 140), center=(p[0], p[1], p[2]), emissive=True))
        m.add(box(6, 4, 0.2, (255, 120, 36), center=self.FURNACE, emissive=True))
        m.add(box(7, 0.6, 0.6, (60, 50, 44), center=(0, 4.4, 29.6)))
        B.letters(m.add, "ЗАВОД", (0, 8.6, 29.95), "-z", px=0.35, col=B.NEON_RED)
        m.add(box(1.6, 0.8, 54, (60, 60, 64), center=(0, 0.4, -1), seg=6))
        m.add(box(1.4, 0.05, 54, (26, 26, 28), center=(0, 0.82, -1), seg=6))
        for z, _ in self.PRESSES:
            for x in (-1.3, 1.3):
                m.add(box(0.4, 4.6, 0.6, (110, 92, 40), center=(x, 2.3, z)))
            m.add(box(3.2, 0.6, 0.9, (110, 92, 40), center=(0, 4.6, z)))
        head = mesh_of(box(1.4, 0.9, 1.2, (80, 80, 86), center=(0, 0.45, 0)),
                       box(0.3, 3.0, 0.3, (170, 170, 176), center=(0, 2.4, 0)))
        self.head = Part(head)
        self.plate = Part(box(0.9, 0.08, 1.1, (130, 130, 138)))
        wheel = mesh_of(box(0.3, 5.6, 0.3, (70, 64, 58)), box(0.3, 0.3, 5.6, (70, 64, 58)),
                        box(0.4, 1.0, 1.0, (90, 84, 70)))
        self.wheel = Part(wheel)
        # handle along +z from the fist, head across it (+y = the striking face)
        self.hammer = Part(mesh_of(box(0.035, 0.035, 0.4, (96, 70, 44), center=(0, 0, 0.13)),
                                   box(0.06, 0.17, 0.065, (70, 72, 78), center=(0, 0.0, 0.31)),
                                   box(0.064, 0.02, 0.07, (150, 150, 156), center=(0, 0.085, 0.31))))
        self.workers = [(humanoid3d(n), (s * 1.3, 0, z), -90 * s, ph)
                        for n, s, z, ph in (("civilian", 1, -4.2, 0.0), ("bodi", -1, -3.6, 0.5), ("krap", 1, 4.0, 0.25),
                                            ("civilian", -1, 4.6, 0.75))]

    def camera(self, f):
        i, u = shot(f, 2)
        sh = 0.05 * f.a["kick"]
        if i == 0:
            return (3.5, 3.2 + sh, -26 + 10 * u), (0, 1.5, 10 * u), 55
        if i == 1:
            a = math.radians(-35 + 25 * u)
            return (3.0 * math.sin(a), 1.6 + sh, -3.0 * math.cos(a)), (0, 1.5, 0), 42
        if i == 2:
            return (3.0 + 0.8 * u, 1.3 + sh, 12), (0, 2.2, 28), 50
        if i == 3:
            return (0, 9 + sh, -12 + 8 * u), (0, 0.8, -2 + 8 * u), 50
        if i == 4:
            return (-0.9 - 0.3 * u, 1.75 + sh, -6.2 + 0.4 * u), (0.7, 1.1, -4.1), 46
        return (-6 + 4 * u, 5 + sh, 24), (0, 1.5, 0), 55

    def frame(self, r, f):
        fl = 0.8 + 0.4 * f.a["low"]
        r.set_pools([dict(pos=(0, 3.0, 27.5), range=13.0, color=(255, 120, 40), intensity=fl)] +
                    [dict(pos=p, range=5.0, color=(255, 180, 100), intensity=0.8) for p in self.LAMPS])
        r.set_lights([dict(pos=(0, 3, 26), color=(255, 120, 50), intensity=1.4 * fl, range=24.0, kind="point"),
                      dict(pos=(0, 6.5, 0), color=(255, 190, 120), intensity=0.9, range=14.0, kind="point")])
        rest, bottom = 2.95, 0.9
        for n, (z, hits) in enumerate(self.PRESSES):
            d, nd = since(f.beat, hits), until(f.beat, hits)
            y = bottom + (rest - bottom) * min(1 - math.exp(-d / 0.18), (nd / 0.15) ** 2 if nd < 0.15 else 1.0)
            self.head.draw(r, (0, y, z))
            age = d * f.spb * 1000
            r.add_sprite((0, 0.95, z - 0.6), fx.sparks(n * 7 + int(f.beat) % 4, age, n=22, speed_m=3.0, dur_ms=520),
                         layer=fx.FX_LAYER)
            if age < 120:
                r.add_sprite((0, 0.95, z), fx.flash(age, radius_m=1.6, dur_ms=120), layer=fx.FX_LAYER)
        zs = (np.arange(0, 54, 3.0) + f.t * 54 / f.L * 3) % 54 - 27.5
        self.plate.many(r, np.stack([np.zeros_like(zs), np.full_like(zs, 0.9), zs], 1))
        self.wheel.draw(r, (-11.7, 5.5, 4), rot_x(TAU * f.beat / 4))
        for n, (hum, pos, yaw, ph) in enumerate(self.workers):
            self.hammer_worker(r, f, n, hum, pos, yaw, ph)
        for p in self.LAMPS:
            glow(r, p, (255, 181, 79), 1.6, 0.7)
        glow(r, self.FURNACE, (255, 120, 40), 6.0, 0.6 + 0.4 * f.a["low"])

    STRIKE = np.array([0.1, 0.95, 0.88])      # worker-local: on the plate, belt centre side
    SWING = (-56.0, 150.0)                    # handle angle (deg, up from forward) at strike / top

    def hammer_worker(self, r, f, n, hum, pos, yaw, ph):
        """One hammer blow a beat: fast drop onto the plate on the hit, slower lift after."""
        d, nd = since(f.beat, [ph], 1.0), until(f.beat, [ph], 1.0)
        a = smooth(d / 0.45) * min(1.0, (nd / 0.18) ** 1.5)
        phi = math.radians(self.SWING[0] + (self.SWING[1] - self.SWING[0]) * a)
        hd = np.array([0.0, math.sin(phi), math.cos(phi)])          # handle direction
        face = np.array([0.0, -math.cos(phi), math.sin(phi)])        # striking face
        p0 = math.radians(self.SWING[0])
        h0 = self.STRIKE - np.array([0, math.sin(p0), math.cos(p0)]) * 0.31 - np.array([0, -math.cos(p0), math.sin(p0)]) * 0.085
        h1 = np.array([0.2, 1.88, 0.12])
        # the fist travels an arc about the shoulder between the strike and the top of the lift
        sh = np.array([0.2, 1.42, 0.26])
        v0, v1 = h0 - sh, h1 - sh
        t0, t1 = math.atan2(v0[1], v0[2]), math.atan2(v1[1], v1[2])
        rad = np.hypot(v0[1], v0[2]) * (1 - a) + np.hypot(v1[1], v1[2]) * a
        ang = t0 + (t1 - t0) * a
        hand = sh + np.array([v0[0] + (v1[0] - v0[0]) * a, rad * math.sin(ang), rad * math.cos(ang)])
        p = dict(spine=24 - 6 * a, head_p=22, lhip_p=10, rhip_p=-6, lkn=12, rkn=6)
        p = ik.solve_arm(hum, p, pos, yaw, "r", tuple(to_world(pos, yaw, hand)), pole=(1.0, -0.4, -0.6))
        p = ik.solve_arm(hum, p, pos, yaw, "l", tuple(to_world(pos, yaw, (-0.22, 0.9, 0.62))), pole=(-1.0, -0.6, -0.2))
        j = r.add_humanoid(hum, p, pos, yaw)
        Ry = rot_y(math.radians(yaw))
        self.hammer.draw(r, np.asarray(j["rhand"]), Ry @ np.column_stack([(-1.0, 0, 0), face, hd]))
        age = d * f.spb * 1000
        if age < 360:
            r.add_sprite(tuple(to_world(pos, yaw, self.STRIKE)), fx.sparks(n * 13 + int(f.beat) % 8, age, n=10,
                                                                          speed_m=1.6, dur_ms=360), layer=fx.FX_LAYER)

    def post(self, surf, f):
        add_light(surf, (60, 26, 8), 0.7 * f.a["kick"])


# ---------------------------------------------------------------- 5. Curfew Dawn

class CurfewDawn(Scene):
    """The morning after the curfew: an empty square, birds back on the wing."""
    fog, fog_start, fog_end = (184, 124, 112), 50.0, 420.0
    sky = ((40, 48, 96), (240, 156, 112))
    SUN = (-0.6, 0.12, 1.0)
    light = dict(direction=(-0.6, 0.3, 1.0), ambient=0.44, diffuse=0.7, sky=0.1, tint=(1.0, 0.8, 0.64))
    HERO = (-2.0, 0.0, -5.0)
    INNER = 240.0

    def ground_h(self, x, z):
        """Flat town on a 60 m street grid, low hills rising past 200 m."""
        rise = smooth((math.hypot(x, z) - 200) / 220)
        return -0.03 + rise * (12 + 30 * (0.5 + 0.5 * self.gn(x * 0.4, z * 0.4)))

    def ground_col(self, x, y, z, ny):
        n = self.gn(x * 6, z * 6)
        d = min(abs(x % 60 - 30), abs(z % 60 - 30))
        if y > 1.5:
            return mix((72, 72, 56), (96, 88, 70), y / 30 + 0.2 * n)
        if d < 3.5:
            return mix((48, 46, 52), (58, 54, 58), 0.5 + 0.5 * n)
        if d < 5.5:
            return (90, 84, 82)
        return mix((70, 66, 54), (60, 66, 50), 0.5 + 0.5 * n)

    def tree(self, m, x, z, h):
        m.add(box(0.24, h * 0.45, 0.24, (58, 44, 36), center=(x, h * 0.225, z)))
        m.add(box(1.7, h * 0.4, 1.7, (58, 70, 46), center=(x, h * 0.6, z), cols={"top": (70, 82, 52)}))
        m.add(box(1.1, h * 0.22, 1.1, (64, 76, 50), center=(x, h * 0.89, z), cols={"top": (78, 90, 58)}))

    def lamp(self, m, x, z, ax):
        m.add(box(0.14, 6.0, 0.14, (48, 48, 52), center=(x, 3.0, z)))
        m.add(box(1.2 if ax else 0.1, 0.1, 0.1 if ax else 1.2, (48, 48, 52),
                  center=(x + 0.55 * ax, 5.95, z + 0.55 * (not ax))))
        m.add(box(0.36, 0.14, 0.36, (40, 40, 44), center=(x + 1.1 * ax, 5.85, z + 1.1 * (not ax)),
                  cols={"bottom": (150, 132, 110)}))

    def build(self, m):
        self.gn = noise2(55, 4, 1 / 90.0)
        S = self.INNER
        terrain(m, -S, -S, S, S, 3.0, self.ground_h, self.ground_col, 0)
        terrain(m, -600, -600, 600, 600, 20.0,
                lambda x, z: self.ground_h(x, z) - (1.0 if abs(x) < S and abs(z) < S else 0.0), self.ground_col, 0)
        for c in range(-150, 151, 60):
            for k in range(-36, 36):
                a = k * 8 + 3
                if abs((a + 30) % 60 - 30) < 6:
                    continue
                m.add(quad_xz(c - 0.1, a, c + 0.1, a + 3, 0.01, (150, 146, 134), 1))
                m.add(quad_xz(a, c - 0.1, a + 3, c + 0.1, 0.01, (150, 146, 134), 1))

        def paving(i, j):
            if i in (0, 25) or j in (0, 25):
                return (84, 78, 76)
            return (106, 98, 94) if (i + j) % 2 else (98, 92, 88)
        m.add(quad_xz(-26, -26, 26, 26, 0, None, 1, seg=2, colfn=paving))
        for sx, sz, w, d in ((0, -26, 52.3, 0.3), (0, 26, 52.3, 0.3), (-26, 0, 0.3, 52.3), (26, 0, 0.3, 52.3)):
            m.add(box(w, 0.16, d, (120, 114, 108), center=(sx, 0.08, sz)))
        for t in range(-21, 22, 7):
            for x, z in ((t, 23.5), (t, -23.5), (-23.5, t), (23.5, t)):
                if not (-14 < x < 4 and -14 < z < 0):
                    self.tree(m, x, z, 4.6 + (abs(x * 3 + z * 7) % 5) * 0.3)
        for t in (-18, 0, 18):
            self.lamp(m, t, -25.2, 0)
            self.lamp(m, t, 25.2, 0)
            self.lamp(m, -25.2, t, 1)
            self.lamp(m, 25.2, t, 1)
        for x in (-11, -8, 8, 11):
            m.add(box(1.6, 0.08, 0.5, (90, 66, 46), center=(x, 0.46, 13)))
            m.add(box(1.6, 0.4, 0.08, (90, 66, 46), center=(x, 0.7, 13.24)))
            for dx in (-0.65, 0.65):
                m.add(box(0.08, 0.44, 0.44, (40, 40, 44), center=(x + dx, 0.22, 13)))
        for x in range(-28, 30, 16):
            B.panel_block(m.add, x, -38, 14, 18 + (x * 5 % 7), 8, "+z", seed=x + 40, col=(70, 66, 74), lit=0.12,
                          balconies=False)
        for z in range(-28, 30, 16):
            B.panel_block(m.add, 38, z, 8, 16 + (z * 3 % 9), 14, "-x", seed=z + 90, col=(70, 66, 74), lit=0.12,
                          balconies=False)
        for x in (-6, 10, 26, 42):
            B.panel_block(m.add, x, 46, 14, 16 + (x * 7 % 9), 8, "-z", seed=x + 140, col=(70, 66, 74), lit=0.12,
                          balconies=False)
        for z in (-36, -20, -4):
            B.panel_block(m.add, -46, z, 8, 15 + (z * 5 % 7), 14, "+x", seed=z + 190, col=(70, 66, 74), lit=0.12,
                          balconies=False)
        city(m.add, 5, 16, (-200, 200), (90, 200), (16, 40), "-z", lit=0.08, col=(90, 76, 92))
        city(m.add, 8, 12, (-220, -110), (-200, 60), (14, 30), "+x", lit=0.08, col=(90, 76, 92))
        city(m.add, 9, 12, (110, 220), (-200, 60), (14, 30), "-x", lit=0.08, col=(90, 76, 92))
        city(m.add, 10, 12, (-200, 200), (-220, -110), (14, 30), "+z", lit=0.08, col=(90, 76, 92))
        m.add(box(3.2, 3.0, 3.2, (112, 106, 100), center=(0, 1.5, 6)))
        m.add(box(4.0, 0.4, 4.0, (96, 92, 88), center=(0, 0.2, 6)))
        for i in range(9):
            m.add(box(0.36, 0.1, 0.1, (200, 40, 36) if i % 2 == 0 else (230, 226, 220),
                      center=(-5.6 + i * 0.36, 1.05, -4.0)))
        for x in (-5.9, -2.5):
            m.add(box(0.16, 1.1, 0.16, (60, 60, 60), center=(x, 0.55, -4.0)))
        m.add(box(1.4, 2.4, 1.4, (66, 76, 62), center=(-8, 1.2, -4.5), cols={"top": (54, 60, 50)}))
        for i in range(8):
            a = math.radians(200 + i * 14)
            for lvl in range(2):
                m.add(box(0.7, 0.3, 0.42, (150, 136, 100),
                          center=(-6.2 + 1.6 * math.cos(a), 0.15 + lvl * 0.3, -1.6 + 1.6 * math.sin(a))))
        self.hero = humanoid3d("biribel")
        stone = dict(skin=(118, 114, 110), hair=(100, 96, 92), jacket=(110, 106, 102), vest=None, pants=(104, 100, 96),
                     boots=(96, 92, 88), iris=None, scale=2.2)
        self.statue = humanoid3d("vasile", **stone)
        self.guard = soldier()
        self.guard._rifle = ak_mesh()
        self.birds = [(np.random.default_rng(20 + i).uniform(8, 22), np.random.default_rng(40 + i).uniform(9, 16),
                       (1 if i % 3 else 2) * (1 if i % 2 else -1), i * 0.61) for i in range(14)]

    def camera(self, f):
        i, u = shot(f, 4)
        if i == 0:
            a = -0.9 + 0.5 * smooth(u)
            return (16 * math.sin(a), 1.2 + 6 * smooth(u), 6 - 16 * math.cos(a)), (0, 4, 6), 50
        h = np.array(self.HERO)
        d = norm((self.SUN[0], 0, self.SUN[2]))
        side = np.array([d[2], 0, -d[0]])
        pos = h + side * (2.0 - 0.3 * u) - d * 3.0 + (0, 1.6, 0)
        return pos, h + d * 1.8 + side * 0.5 + (0, 1.8, 0), 62

    def backdrop(self, surf, f):
        p = disc_on_sky(self.r, surf, self.SUN, 22, (255, 226, 170), (180, 90, 50), int(140 + 30 * f.a["low"]))
        if p and f.a["high"] > 0.2:
            k = f.a["high"]
            for j in range(5):
                a = TAU * (j / 5 + f.beat / 8)
                x, y = p[0] + math.cos(a) * 40 * (1 + j % 2), p[1] + math.sin(a) * 26 * (1 + j % 2)
                c = (int(200 * k), int(160 * k), int(110 * k))
                pygame.draw.line(surf, c, (x - 4, y), (x + 4, y))
                pygame.draw.line(surf, c, (x, y - 4), (x, y + 4))

    def frame(self, r, f):
        yaw = math.degrees(math.atan2(self.SUN[0], self.SUN[2]))
        r.add_humanoid(self.hero, pose(None, head_y=10 * math.sin(TAU * f.beat / 16), head_p=-6), self.HERO, yaw)
        r.add_humanoid(self.statue, pose(None, lsh_p=150, lsh_r=10, lel=10, head_p=-8), (0, 3.0, 6), 200)
        r.add_humanoid(self.guard, pose("slump"), (-6.2, 0, -2.6), 160)
        for rad, h, cyc, ph in self.birds:
            a = TAU * (cyc * f.k) + ph * TAU
            c = np.array([4 + rad * math.cos(a), h + math.sin(a * 2) * 0.6, 14 + rad * math.sin(a)])
            fwd = norm((-math.sin(a) * np.sign(cyc), 0, math.cos(a) * np.sign(cyc)))
            side = np.cross(fwd, (0, 1, 0))
            flap = math.radians(38) * math.sin(TAU * (f.beat * 2 + ph))
            up = np.array([0, 1, 0])
            tips = [c + side * s * 0.5 * math.cos(flap) + up * 0.5 * math.sin(flap) for s in (-1, 1)]
            verts = [tuple(c + fwd * 0.18), tuple(c - fwd * 0.12), tuple(tips[0]), tuple(tips[1])]
            r.add_dynamic(verts, [((0, 1, 2), (30, 26, 30), 2, True, None, False),
                                  ((0, 3, 1), (30, 26, 30), 2, True, None, False)])

    def post(self, surf, f):
        add_light(surf, (40, 22, 10), 0.4 * f.a["kick"])


# ---------------------------------------------------------------- 6. Not Tonight

class NotTonight(Scene):
    """Martial law: a column marches through the curfew, a helicopter sweeps the street, Ucilev watches."""
    fog, fog_start, fog_end = (10, 12, 18), 10.0, 34.0
    sky = ((4, 5, 10), (16, 18, 30))
    light = dict(direction=(0.2, 0.9, -0.3), ambient=0.24, diffuse=0.32, sky=0.08, tint=(0.72, 0.8, 1.0))
    HELI = np.array([2.0, 13.0, 3.0])
    UCILEV = (-8.0, 16.0, -8.6)

    def build(self, m):
        m.add(quad_xz(-60, -4, 60, 4, 0, (28, 28, 32), seg=8))
        for z in (-5.25, 5.25):
            m.add(box(120, 0.15, 2.5, (44, 44, 50), center=(0, 0.075, z), seg=8))
        m.add(quad_xz(-60, -30, 60, 30, -0.01, (20, 20, 24)))
        for x in range(-40, 44, 16):
            hb = 16 if x == -8 else 14 + (x * 7 % 11)
            B.panel_block(m.add, x, -12, 14, hb, 8, "+z", seed=x + 7, col=(36, 38, 44), lit=0.1, balconies=False)
            B.panel_block(m.add, x, 12, 14, 14 + (x * 5 % 9), 8, "-z", seed=x + 77, col=(36, 38, 44), lit=0.1,
                          balconies=False)
        B.banner(m.add, "НЕ СЕГОДНЯ", (6, 5.5, 7.9), "-z", px=0.12)
        hull = (48, 56, 42)
        m.add(box(6, 1.6, 2.8, hull, center=(10, 1.3, -6.6)))
        m.add(box(1.6, 0.7, 1.6, hull, center=(10.5, 2.45, -6.6)))
        m.add(box(2.2, 0.15, 0.15, (30, 34, 28), center=(8.6, 2.5, -6.6)))
        for x in (8, 9.4, 10.8, 12.2):
            for z in (-8.0, -5.2):
                m.add(box(0.8, 0.8, 0.3, (16, 16, 16), center=(x, 0.4, z)))
        for x in (-14, -11, 16):
            for zz in (-3.8, 3.8):
                m.add(box(1.4, 0.16, 0.16, (60, 58, 52), center=(x, 0.5, zz)))
                m.add(box(0.16, 0.16, 1.4, (60, 58, 52), center=(x, 0.5, zz)))
        heli = mesh_of(box(1.8, 1.6, 4.0, (36, 40, 40), center=(0, 0, 0)),
                       box(0.4, 0.4, 5.0, (36, 40, 40), center=(0, 0.3, -4.4)),
                       box(0.1, 1.2, 0.8, (36, 40, 40), center=(0, 0.8, -6.6)),
                       box(1.2, 0.8, 0.3, (60, 80, 90), center=(0, 0.1, 2.05)),
                       box(0.1, 0.1, 3.4, (20, 20, 20), center=(-0.8, -1.1, 0)),
                       box(0.1, 0.1, 3.4, (20, 20, 20), center=(0.8, -1.1, 0)),
                       box(0.3, 0.5, 0.3, (20, 20, 20), center=(0, 1.0, 0)))
        self.heli = Part(heli)
        self.rotor = Part(mesh_of(box(9.0, 0.05, 0.3, (24, 24, 24)), box(0.3, 0.05, 9.0, (24, 24, 24))))
        self.troops = [soldier() for _ in range(3)]
        for t in self.troops:
            t._rifle = ak_mesh()
        self.ucilev = humanoid3d("ucilev", rifle="sniper")
        self.ucilev._rifle = ak_mesh(svd=True)
        x, y, z = self.UCILEV
        self.u_yaw = math.degrees(math.atan2(16.0, 12.0))
        self.u_pose = ik.solve_rifle_hold(self.ucilev, pose("kneel", spine=10), self.UCILEV, self.u_yaw,
                                          (x + 16.0, 1.0, z + 12.0))

    def heli_pos(self, f):
        return self.HELI + (0.6 * math.sin(TAU * f.k * 2), 0.3 * math.sin(TAU * f.k * 4), 0)

    def beam_target(self, f):
        return np.array([6 * math.sin(TAU * f.k * 3), 0.0, 2.5 * math.sin(TAU * f.k * 5)])

    def camera(self, f):
        i, u = shot(f, 2)
        v = 36.0 / f.L
        ts = (f.bar - (f.bar % 2)) * 4 * f.spb
        if i == 0:
            return (0, 0.35, -4.5), (0, 0.6, 0), 50
        if i == 1:
            return (-16 + 2 * u, 7, -3.6), (4, 1.5, 0.5), 52
        if i == 2:
            cx = -2 + v * (f.t - ts)
            return (cx, 1.7, -3.6), (cx + 1.5, 1.4, 0), 50
        if i == 3:
            return (-1 + u, 1.2, -2.5), tuple(self.heli_pos(f)), 62
        if i == 4:
            x, y, z = self.UCILEV
            return (x - 1.5 + 0.4 * u, y + 1.3, z + 3.6), (x + 0.3, y + 0.85, z + 0.4), 50
        cx = 8 + v * (f.t - ts)
        return (cx, 1.5, 0), (cx - 6, 1.2, 0), 50

    def backdrop(self, surf, f):
        stars(self.r, surf, seed=6, n=90)

    def frame(self, r, f):
        hp = self.heli_pos(f)
        g = self.beam_target(f)
        d = norm(g - hp)
        r.set_pools([dict(pos=tuple(g + (0, 1.0, 0)), range=3.2, color=(210, 220, 255), intensity=1.3,
                          hot=(240, 244, 255))])
        r.set_lights([dict(pos=tuple(hp), dir=tuple(d), cone=math.cos(math.radians(9)), range=30.0, intensity=2.2,
                           color=(220, 230, 255), kind="spot")])
        self.heli.draw(r, hp, rot_y(0.3 * math.sin(TAU * f.k)))
        self.rotor.draw(r, hp + (0, 1.3, 0), rot_y(TAU * f.beat * 0.75))
        glow(r, hp + (0, -0.6, 1.6), (230, 236, 255), 0.8, 1.0, core=(255, 255, 255))
        glow(r, hp + (0, 0.9, -6.9), (255, 40, 30), 0.4, 1.0 if f.beat % 1 < 0.3 else 0.2)
        self._beam = (hp + (0, -0.6, 1.6), g)
        v = 36.0 / f.L
        n = 18
        walk = carry(self.troops[0], math.pi * f.beat)
        for file, z in enumerate((-1.0, 1.0)):
            for i in range(n):
                x = (i * 36.0 / n + file * 0.5 + v * f.t) % 36.0 - 18
                r.add_humanoid(self.troops[(i + file) % 3], walk, (x, 0, z), 90)
        r.add_humanoid(self.ucilev, self.u_pose, self.UCILEV, self.u_yaw)

    def post(self, surf, f):
        a, g = self._beam
        p0, c = self.r.project(tuple(a)), self.r.project(tuple(g))
        if p0 and c:
            side = norm(np.cross(norm(g - a), (0, 0, 1)))
            q1 = self.r.project(tuple(g + side * 3.0))
            q2 = self.r.project(tuple(g - side * 3.0))
            if q1 and q2:
                tmp = pygame.Surface((W, H))
                pygame.draw.polygon(tmp, (26, 28, 36), [p0[:2], q1[:2], q2[:2]])
                surf.blit(tmp, (0, 0), special_flags=pygame.BLEND_ADD)
        add_light(surf, (24, 26, 40), 0.5 * f.a["kick"])


# ---------------------------------------------------------------- 7. Whiteout

class Whiteout(Scene):
    """The train through the whiteout: poles every two beats, the cars rock on the clacks, Biribel on the roof."""
    fog, fog_start, fog_end = (150, 158, 176), 4.0, 90.0
    sky = ((70, 78, 98), (164, 170, 186))
    light = dict(direction=(-0.2, 0.7, -0.3), ambient=0.5, diffuse=0.35, sky=0.12, tint=(0.85, 0.9, 1.0))
    CARS = (10.0, -6.0, -23.0, -40.0)
    CLACK = [k * 0.5 for k in range(8)]
    HERO = (-4.0, 3.55, 0.0)

    def build(self, m):
        m.add(quad_xz(-400, -400, 400, 400, 0, (196, 202, 216), seg=40))
        m.add(box(800, 0.1, 3.4, (120, 118, 122), center=(0, 0.05, 0), seg=40))
        for z in (-0.72, 0.72):
            m.add(box(800, 0.12, 0.1, (70, 72, 80), center=(0, 0.16, z), seg=40))
        for x in np.arange(-120, 120, 0.75):
            m.add(box(0.25, 0.06, 2.4, (64, 56, 52), center=(x, 0.12, 0)))
        loco = Mesh()
        loco.add(box(14, 3.4, 3.0, (128, 40, 36), center=(0, 2.1, 0), cols={"top": (110, 110, 116)}))
        loco.add(box(2.6, 1.0, 3.04, (230, 210, 150), center=(5.0, 2.9, 0)))
        loco.add(box(0.06, 0.9, 2.2, (255, 214, 150), center=(7.02, 2.9, 0), emissive=True))
        loco.add(box(0.06, 0.4, 0.4, (255, 250, 220), center=(7.02, 1.4, 0), emissive=True))
        loco.add(box(0.3, 0.6, 3.0, (200, 170, 40), center=(7.0, 0.9, 0)))
        self.cars = [Part(loco)]
        for n in range(3):
            w = Mesh()
            w.add(box(16, 3.0, 2.9, (52, 70, 60), center=(0, 2.0, 0), cols={"top": (120, 124, 130)}))
            for k in range(8):
                for zz in (-1.47, 1.47):
                    lit = (k + n) % 3 != 0
                    w.add(box(1.0, 0.7, 0.04, (255, 200, 130) if lit else (30, 36, 40),
                              center=(-6.3 + k * 1.8, 2.4, zz), emissive=lit))
            self.cars.append(Part(w))
        bogie = mesh_of(box(2.6, 0.7, 2.4, (24, 24, 26), center=(0, 0.5, 0)))
        self.bogie = Part(bogie)
        self.pole = Part(mesh_of(box(0.25, 7.0, 0.25, (40, 40, 44), center=(0, 3.5, 0)),
                                 box(0.12, 0.12, 2.5, (40, 40, 44), center=(0, 6.5, 1.2))))
        rng = np.random.default_rng(9)
        seg = Mesh()
        for _ in range(40):
            z = rng.choice([-1, 1]) * rng.uniform(7, 40)
            peak(seg, rng.uniform(0, 96), z, rng.uniform(0.9, 1.8), rng.uniform(4, 9), (40, 58, 54))
        for _ in range(18):
            seg.add(box(rng.uniform(4, 10), rng.uniform(0.4, 1.4), rng.uniform(3, 6), (214, 220, 232),
                        center=(rng.uniform(0, 96), 0.2, rng.choice([-1, 1]) * rng.uniform(5, 30))))
        self.seg = Part(seg)
        far = Mesh()
        for k in range(4):
            B.panel_block(far.add, k * 36 + 10, 52, 16, 18 + k * 4, 8, "-z", seed=k, col=(60, 64, 76), lit=0.3,
                          balconies=False)
        B.letters(far.add, "СЛАВА ТРУДУ", (82, 31, 47.9), "-z", px=0.5, col=B.NEON_RED)
        self.far = Part(far)
        self.hero = humanoid3d("biribel")
        self.snow = field(900, 12, (-24, 0, -12), (24, 10, 12))
        self.snow_cyc = np.random.default_rng(13).integers(15, 19, 900)

    def camera(self, f):
        i, u = shot(f, 2)
        if i == 0:
            return (-6 + 4 * u, 3.0, -14), (-4 + 4 * u, 2.0, 0), 55
        if i == 1:
            return (6, 0.5, -2.8), (-10, 0.9, -1.3), 60
        if i == 2:
            return (32, 2.2, 3), (10, 2.0, 0), 45
        if i == 3:
            return (-8.5, 5.0, -0.8), (4, 3.6, 0), 55
        if i == 4:
            return (-20 + 6 * u, 18, -22), (-8, 1, 0), 50
        x, y, z = self.HERO
        return (x + 3.2, y + 1.2, z - 2.4 + 0.5 * u), (x, y + 0.6, z), 42

    def frame(self, r, f):
        v = 576.0 / f.L
        r.light_cap = 4
        r.set_lights([dict(pos=(17.2, 1.4, 0), dir=tuple(norm((1, -0.08, 0))), cone=math.cos(math.radians(26)),
                           range=50.0, intensity=1.5, color=(255, 246, 220), kind="spot"),
                      dict(pos=(-6, 3, -2.5), color=(255, 200, 130), intensity=0.6, range=6.0, kind="point")])
        for n, (part, x) in enumerate(zip(self.cars, self.CARS)):
            bob = 0.05 * hit(f.beat - n * 0.08, self.CLACK, 0.12)
            part.draw(r, (x, bob, 0))
            half = 5.0 if n == 0 else 6.0
            self.bogie.many(r, [(x - half, 0, 0), (x + half, 0, 0)])
        glow(r, (17.05, 1.4, 0), (255, 246, 220), 1.4, 1.0, core=(255, 255, 255))
        x, y, z = self.HERO
        r.add_humanoid(self.hero, pose("crouch", head_p=-2), (x, y + 0.05 * hit(f.beat - 0.08, self.CLACK, 0.12), z), 90)
        xp = (np.arange(0, 96, 24.0) - v * f.t) % 96 - 48
        offs = [(xx + k * 96, 0, -4.6) for xx in xp for k in (-1, 0, 1)]
        self.pole.many(r, offs)
        sx = (np.arange(0, 576, 96.0) - v * f.t) % 576 - 200
        self.seg.many(r, [(xx, 0, 0) for xx in sx if -200 < xx < 200])
        fx_ = (np.arange(0, 288, 144.0) - 5.0 * f.t) % 288 - 160
        self.far.many(r, [(xx, 0, 0) for xx in fx_])
        pts = wrapped(self.snow, (-24, 0, -12), (24, 10, 12),
                      np.stack([-self.snow_cyc, -np.ones(900) * 2, np.ones(900)], 1), f.k)
        streaks(r, pts, np.array([-0.9, -0.08, 0.04]), (236, 240, 248))

    def post(self, surf, f):
        add_light(surf, (90, 96, 110), 1.2 * f.a["kick"] * smooth(1 - f.beat / 2) + 0.25 * f.a["kick"])


# ---------------------------------------------------------------- 8. I Chose the Many

class IChoseTheMany(Scene):
    """Snow on a square at night. The many hold candles; Biribel faces them. One orbit per loop."""
    fog, fog_start, fog_end = (12, 14, 28), 15.0, 80.0
    sky = ((5, 7, 20), (30, 32, 60))
    light = dict(direction=(0.2, 0.7, -0.5), ambient=0.22, diffuse=0.3, sky=0.1, tint=(0.7, 0.75, 1.0))
    HERO = (0.0, 0.4, -3.2)
    CAST = ("civilian", "bodi", "alex", "ipa", "fisherman", "maru", "krap", "balaceanu")

    def build(self, m):
        m.add(quad_xz(-60, -60, 60, 60, 0, (70, 72, 84), seg=12))
        m.add(box(3.4, 0.4, 2.2, (60, 60, 66), center=(0, 0.2, -3.4)))
        for x in range(-36, 40, 16):
            B.panel_block(m.add, x, -42, 14, 16 + (x * 3 % 8), 8, "+z", seed=x + 3, col=(40, 42, 52), lit=0.22,
                          balconies=False)
            B.panel_block(m.add, x, 46, 14, 16 + (x * 7 % 8), 8, "-z", seed=x + 33, col=(40, 42, 52), lit=0.22,
                          balconies=False)
        for z in range(-28, 36, 16):
            for side, face in ((-1, "+x"), (1, "-x")):
                B.panel_block(m.add, side * 42, z, 8, 18, 14, face, seed=z * 2 + side, col=(40, 42, 52), lit=0.22,
                              balconies=False)
        rng = np.random.default_rng(14)
        self.crowd = []
        for row in range(6):
            for col in range(9):
                x = (col - 4) * 1.15 + rng.uniform(-0.2, 0.2) + (row % 2) * 0.5
                z = 1.0 + row * 1.35 + rng.uniform(-0.2, 0.2)
                self.crowd.append((humanoid3d(self.CAST[int(rng.integers(len(self.CAST)))]), (x, 0, z),
                                   180 + rng.uniform(-12, 12), rng.uniform(0, TAU)))
        self.hero = humanoid3d("biribel")
        self.candle = Part(box(0.05, 0.14, 0.05, (255, 214, 130), emissive=True))
        self.snow = field(600, 21, (-16, 0, -12), (16, 12, 18))
        self.snow_cyc = np.random.default_rng(22).integers(2, 4, 600)

    def camera(self, f):
        a = TAU * f.k
        return (14 * math.sin(a), 3.4 + 1.4 * math.sin(TAU * f.k * 2), 3.0 - 14 * math.cos(a)), (0, 1.2, 3.0), 46

    def backdrop(self, surf, f):
        stars(self.r, surf, seed=8, n=120)

    def frame(self, r, f):
        r.set_lights([dict(pos=(0, 1.6, -2.0), color=(255, 180, 100), intensity=0.8, range=3.0, kind="point")])
        r.set_pools([dict(pos=(0, 1.2, 4.5), range=7.0, color=(255, 170, 90), intensity=0.25 + 0.1 * f.a["high"])])
        r.add_humanoid(self.hero, pose(None, head_y=14 * math.sin(TAU * f.beat / 16), head_p=4), self.HERO, 0)
        lift = f.a["high"]
        hands = []
        for n, (hum, pos, yaw, ph) in enumerate(self.crowd):
            sway = math.sin(TAU * f.beat / 8 + ph)
            p = dict(lsh_p=46, lsh_r=6, lel=96, rsh_p=40, rsh_r=10, rel=100, head_p=-6 + 4 * sway, body_r=2 * sway)
            j = r.add_humanoid(hum, p, pos, yaw + 3 * sway)
            hands.append((np.asarray(j["lhand"]) + np.asarray(j["rhand"])) / 2 + (0, 0.1, 0))
        self.candle.many(r, hands)
        for n, h in enumerate(hands):
            k = 0.65 + 0.15 * math.sin(TAU * f.beat * 2 + n) + 0.3 * lift
            glow(r, h + (0, 0.06, 0), (255, 181, 79), 0.6, k, core=(255, 246, 210))
        pts = wrapped(self.snow, (-16, 0, -12), (16, 12, 18),
                      np.stack([np.ones(600), -self.snow_cyc, np.zeros(600)], 1), f.k)
        streaks(r, pts, np.array([0.02, -0.06, 0.0]), (210, 214, 230))

    def post(self, surf, f):
        add_light(surf, (30, 20, 8), 0.3 * f.a["mid"])


SCENES = {1: CallOfAcaristan, 2: BlackNotebook, 3: QuietOnRoute12, 4: TheVostral, 5: CurfewDawn, 6: NotTonight,
          7: Whiteout, 8: IChoseTheMany}
