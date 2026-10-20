"""Core of the low-poly renderer: math, meshes, camera, painter renderer.

Conventions: left-handed, x = right, y = up, z = forward (into the screen
for an un-rotated camera). Units are metres. Faces are wound so that the
outward normal is (b - a) x (c - a) in this left-handed space; use the mesh
builders below and you never have to think about it.
"""
import math

import pygame

__all__ = [
    "v_add", "v_sub", "v_mul", "v_dot", "v_cross", "v_len", "v_norm", "v_lerp",
    "m_mul", "m_apply", "rot_x", "rot_y", "rot_z", "M_IDENT",
    "Mesh", "box", "prism", "quad_xz", "disc_xz", "Obj", "Light", "Renderer",
    "SoftwareRenderer",
    "lerp", "clamp", "smooth", "ease_in_out", "ease_out", "ease_in", "mix_col",
]


# ── scalar / colour helpers ─────────────────────────────────────────────
def lerp(a, b, t):
    return a + (b - a) * t


def clamp(v, lo=0.0, hi=1.0):
    return lo if v < lo else hi if v > hi else v


def smooth(t):
    t = clamp(t)
    return t * t * (3 - 2 * t)


def ease_in_out(t):
    t = clamp(t)
    return 4 * t * t * t if t < .5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in(t):
    t = clamp(t)
    return t * t * t


def mix_col(a, b, t):
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t),
            int(a[2] + (b[2] - a[2]) * t))


# ── vectors (plain tuples) ──────────────────────────────────────────────
def v_add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def v_sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def v_mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def v_dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def v_cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def v_len(a):
    return math.sqrt(a[0] * a[0] + a[1] * a[1] + a[2] * a[2])


def v_norm(a):
    l = v_len(a) or 1.0
    return (a[0] / l, a[1] / l, a[2] / l)


def v_lerp(a, b, t):
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t,
            a[2] + (b[2] - a[2]) * t)


# ── 3x3 matrices as 9-tuples, row-major ────────────────────────────────
M_IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def m_mul(a, b):
    return (
        a[0] * b[0] + a[1] * b[3] + a[2] * b[6], a[0] * b[1] + a[1] * b[4] + a[2] * b[7], a[0] * b[2] + a[1] * b[5] + a[2] * b[8],
        a[3] * b[0] + a[4] * b[3] + a[5] * b[6], a[3] * b[1] + a[4] * b[4] + a[5] * b[7], a[3] * b[2] + a[4] * b[5] + a[5] * b[8],
        a[6] * b[0] + a[7] * b[3] + a[8] * b[6], a[6] * b[1] + a[7] * b[4] + a[8] * b[7], a[6] * b[2] + a[7] * b[5] + a[8] * b[8],
    )


def m_apply(m, v):
    return (m[0] * v[0] + m[1] * v[1] + m[2] * v[2],
            m[3] * v[0] + m[4] * v[1] + m[5] * v[2],
            m[6] * v[0] + m[7] * v[1] + m[8] * v[2])


def rot_x(deg):
    """+deg tips +y toward +z (a torso leaning forward)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (1.0, 0.0, 0.0, 0.0, c, -s, 0.0, s, c)


def rot_y(deg):
    """Yaw. +deg turns +z toward +x (clockwise seen from above)."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c, 0.0, s, 0.0, 1.0, 0.0, -s, 0.0, c)


def rot_z(deg):
    """+deg swings a hanging limb (-y) out toward +x."""
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c, -s, 0.0, s, c, 0.0, 0.0, 0.0, 1.0)


# ── meshes ──────────────────────────────────────────────────────────────
class Mesh:
    """verts: [(x,y,z)], faces: [(idx_tuple, colour, layer, double_sided, emissive)]"""
    __slots__ = ("verts", "faces")

    def __init__(self, verts=None, faces=None):
        self.verts = list(verts or [])
        self.faces = list(faces or [])

    def add(self, other, m=M_IDENT, t=(0.0, 0.0, 0.0)):
        base = len(self.verts)
        for v in other.verts:
            p = m_apply(m, v)
            self.verts.append((p[0] + t[0], p[1] + t[1], p[2] + t[2]))
        for idx, col, layer, ds, em in other.faces:
            self.faces.append((tuple(i + base for i in idx), col, layer, ds, em))
        return self

    def face(self, pts, col, layer=2, double=False, emissive=False):
        base = len(self.verts)
        self.verts.extend(pts)
        self.faces.append((tuple(range(base, base + len(pts))), col, layer, double, emissive))
        return self


def _raster_tri(px, grid, pts, uvs, tex, shade, fog, fog_k):
    """Affine nearest texture fill of one screen triangle into a
    surfarray pixels3d view (indexed [x, y]). ``grid`` is the flush's
    shared (XX, YY) float coordinate arrays - allocating them per
    triangle was the rasterizer's main cost. P11 step 9."""
    import numpy as np

    (x0, y0), (x1, y1), (x2, y2) = pts
    W, H = px.shape[0], px.shape[1]
    minx, maxx = max(0, int(min(x0, x1, x2))), min(W - 1, int(max(x0, x1, x2)))
    miny, maxy = max(0, int(min(y0, y1, y2))), min(H - 1, int(max(y0, y1, y2)))
    if maxx < minx or maxy < miny:
        return
    d = (x1 - x0) * (y2 - y0) - (y1 - y0) * (x2 - x0)
    if abs(d) < 1e-9:
        return
    xx = grid[0][minx:maxx + 1, miny:maxy + 1] - x0
    yy = grid[1][minx:maxx + 1, miny:maxy + 1] - y0
    w1 = (xx * (y2 - y0) - yy * (x2 - x0)) / d
    w2 = ((x1 - x0) * yy - (y1 - y0) * xx) / d
    inside = (w1 >= -0.002) & (w2 >= -0.002) & ((w1 + w2) <= 1.002)
    if not inside.any():
        return None
    u = uvs[0][0] + w1 * (uvs[1][0] - uvs[0][0]) + w2 * (uvs[2][0] - uvs[0][0])
    v = uvs[0][1] + w1 * (uvs[1][1] - uvs[0][1]) + w2 * (uvs[2][1] - uvs[0][1])
    th, tw = tex.shape[0], tex.shape[1]
    tu = (u % 1.0 * tw).astype(np.int32)
    np.clip(tu, 0, tw - 1, out=tu)
    tv = (v % 1.0 * th).astype(np.int32)
    np.clip(tv, 0, th - 1, out=tv)
    sampled = tex[tv, tu].astype(np.float32)
    sampled *= shade
    if fog_k > 0.0:
        sampled *= (1.0 - fog_k)
        sampled += np.asarray(fog, np.float32) * fog_k
    np.clip(sampled, 0, 255, out=sampled)
    region = px[minx:maxx + 1, miny:maxy + 1]
    region[inside] = sampled.astype(np.uint8)[inside]
    return (minx, miny, inside)


def _tex_draw(tex, scr, uvs, lit_col, base_col, flat_col, fog, fog_k):
    """Painter item drawing one textured quad, nearest sample, shaded by
    the face's lit colour relative to its base tint. ``flush`` passes a
    shared pixels3d view (attribute ``_tex_px``) so a subdivided floor
    costs one surface lock per run of textured faces, not one per face."""
    import numpy as np

    shade = np.array([min(1.6, lit_col[i] / max(1, base_col[i]))
                      for i in range(3)], dtype=np.float32)
    pts = list(scr)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    bw, bh = max(xs) - min(xs), max(ys) - min(ys)
    stride = 4 if bw * bh > 14400 else 2 if bw * bh > 3600 else 1

    def _tris(tex2, shade2, uvs2, fk):
        return (((pts[0], pts[1], pts[2]), (uvs2[0], uvs2[1], uvs2[2])),
                ((pts[0], pts[2], pts[3]), (uvs2[0], uvs2[2], uvs2[3])))

    if stride == 1:
        def _draw(px_grid):
            px, grid = px_grid
            tex2, shade2, uvs2, fk = tex, shade, uvs, fog_k
            if bw * bh < 16:
                # sub-texel quad: flat fill through the same rasterizer
                # (flat_col is already fogged, so no second fog mix)
                tex2 = np.array([[flat_col]], dtype=np.uint8)
                shade2 = np.ones(3, dtype=np.float32)
                uvs2 = ((0, 0), (0, 0), (0, 0), (0, 0))
                fk = 0.0
            for tri, uv in _tris(tex2, shade2, uvs2, fk):
                _raster_tri(px, grid, tri, uv, tex2, shade2, fog, fk)

        _draw._tex_px = True
        return _draw

    # Big quad: the 16x16 source texels cover many screen pixels, so
    # rasterize at a stride into an alpha-masked tile and let pygame's
    # C scaler/blitter do the expansion (nearest - retro-correct).
    ox, oy = int(min(xs)), int(min(ys))
    tw, th = int(bw // stride) + 2, int(bh // stride) + 2
    spts = tuple(((x - ox) / stride, (y - oy) / stride) for x, y in pts)

    def _draw_surf(surface):
        tmp = np.zeros((tw, th, 3), dtype=np.uint8)
        alpha = np.zeros((tw, th), dtype=np.uint8)
        grid = np.mgrid[0:tw, 0:th].astype(np.float32)
        tris = (((spts[0], spts[1], spts[2]), (uvs[0], uvs[1], uvs[2])),
                ((spts[0], spts[2], spts[3]), (uvs[0], uvs[2], uvs[3])))
        for tri, uv in tris:
            hit = _raster_tri(tmp, grid, tri, uv, tex, shade, fog, fog_k)
            if hit:
                alpha[hit[0]:hit[0] + hit[2].shape[0],
                      hit[1]:hit[1] + hit[2].shape[1]][hit[2]] = 255
        tile = pygame.Surface((tw, th), pygame.SRCALPHA)
        pygame.surfarray.blit_array(tile, tmp)
        pygame.surfarray.pixels_alpha(tile)[:] = alpha
        if stride > 1:
            tile = pygame.transform.scale(tile, (tw * stride, th * stride))
        surface.blit(tile, (ox, oy))

    _draw_surf._tex_surf = True
    return _draw_surf


def _grid_face(mesh, o, u, v, nu, nv, col, layer, emissive=False, colfn=None):
    """Add a subdivided parallelogram o + a*u + b*v (a,b in 0..1)."""
    for i in range(nu):
        for j in range(nv):
            a0, a1 = i / nu, (i + 1) / nu
            b0, b1 = j / nv, (j + 1) / nv
            p = [
                (o[0] + u[0] * a0 + v[0] * b0, o[1] + u[1] * a0 + v[1] * b0, o[2] + u[2] * a0 + v[2] * b0),
                (o[0] + u[0] * a0 + v[0] * b1, o[1] + u[1] * a0 + v[1] * b1, o[2] + u[2] * a0 + v[2] * b1),
                (o[0] + u[0] * a1 + v[0] * b1, o[1] + u[1] * a1 + v[1] * b1, o[2] + u[2] * a1 + v[2] * b1),
                (o[0] + u[0] * a1 + v[0] * b0, o[1] + u[1] * a1 + v[1] * b0, o[2] + u[2] * a1 + v[2] * b0),
            ]
            c = colfn(i, j) if colfn else col
            mesh.face(p, c, layer, False, emissive)


def box(w, h, d, col, center=(0.0, 0.0, 0.0), cols=None, seg=None, layer=2,
        emissive=False, skip=()):
    """Axis-aligned box. ``cols`` may override per side:
    keys top/bottom/left/right/front/back (front = -z side, faces the camera
    of an un-rotated scene). ``seg`` = max face size before subdividing
    (keeps painter sorting sane on big slabs)."""
    cx, cy, cz = center
    x0, x1 = cx - w / 2, cx + w / 2
    y0, y1 = cy - h / 2, cy + h / 2
    z0, z1 = cz - d / 2, cz + d / 2
    cols = cols or {}
    m = Mesh()

    def n(len_):
        return max(1, int(math.ceil(len_ / seg))) if seg else 1

    sides = {
        # name: (origin, u, v) with outward normal = u x v (left-handed => v x u ... checked by test)
        "front": ((x0, y0, z0), (w, 0, 0), (0, h, 0), n(w), n(h)),
        "back": ((x1, y0, z1), (-w, 0, 0), (0, h, 0), n(w), n(h)),
        "left": ((x0, y0, z1), (0, 0, -d), (0, h, 0), n(d), n(h)),
        "right": ((x1, y0, z0), (0, 0, d), (0, h, 0), n(d), n(h)),
        "top": ((x0, y1, z0), (w, 0, 0), (0, 0, d), n(w), n(d)),
        "bottom": ((x0, y0, z1), (w, 0, 0), (0, 0, -d), n(w), n(d)),
    }
    for name, (o, u, v, nu, nv) in sides.items():
        if name in skip:
            continue
        _grid_face(m, o, u, v, nu, nv, cols.get(name, col), layer, emissive)
    return m


def _orient_outward(m):
    """Flip faces of a convex mesh so every normal points away from its centre."""
    if not m.verts:
        return m
    n = len(m.verts)
    c = (sum(v[0] for v in m.verts) / n, sum(v[1] for v in m.verts) / n,
         sum(v[2] for v in m.verts) / n)
    out = []
    for idx, col, layer, ds, em in m.faces:
        a, b, cc = m.verts[idx[0]], m.verts[idx[1]], m.verts[idx[2]]
        nrm = v_cross(v_sub(b, a), v_sub(cc, a))
        fc = (sum(m.verts[i][0] for i in idx) / len(idx), sum(m.verts[i][1] for i in idx) / len(idx),
              sum(m.verts[i][2] for i in idx) / len(idx))
        if v_dot(nrm, v_sub(fc, c)) < 0:
            idx = tuple(reversed(idx))
        out.append((idx, col, layer, ds, em))
    m.faces = out
    return m


def prism(profile, depth, col, z0=0.0, cols=None, layer=2, seg=None):
    """Extrude a convex 2D profile [(x, y)...] along +z from z0 to z0+depth.
    ``cols``: "front" (z0 cap), "back", or profile edge index -> colour."""
    cols = cols or {}
    m = Mesh()
    z1 = z0 + depth
    nseg = max(1, int(math.ceil(depth / seg))) if seg else 1
    m.face([(x, y, z0) for x, y in profile], cols.get("front", col), layer)
    m.face([(x, y, z1) for x, y in profile], cols.get("back", col), layer)
    n = len(profile)
    for i in range(n):
        ax, ay = profile[i]
        bx, by = profile[(i + 1) % n]
        for k in range(nseg):
            za = z0 + depth * k / nseg
            zb = z0 + depth * (k + 1) / nseg
            m.face([(ax, ay, za), (bx, by, za), (bx, by, zb), (ax, ay, zb)],
                   cols.get(i, col), layer)
    return _orient_outward(m)


def quad_xz(x0, z0, x1, z1, y, col, layer=0, seg=None, colfn=None, emissive=False):
    """Upward-facing ground rectangle."""
    m = Mesh()
    nu = max(1, int(math.ceil(abs(x1 - x0) / seg))) if seg else 1
    nv = max(1, int(math.ceil(abs(z1 - z0) / seg))) if seg else 1
    _grid_face(m, (x0, y, z0), (x1 - x0, 0, 0), (0, 0, z1 - z0), nu, nv, col,
               layer, emissive, colfn)
    return m


def disc_xz(cx, cz, r, y, col, n=9, layer=1, wobble=None):
    pts = []
    for i in range(n):
        a = -2 * math.pi * i / n
        rr = r * (wobble[i % len(wobble)] if wobble else 1.0)
        pts.append((cx + math.cos(a) * rr, y, cz + math.sin(a) * rr))
    m = Mesh()
    m.face(pts, col, layer, True)
    return m


# ── world objects ───────────────────────────────────────────────────────
class Obj:
    """A static mesh baked into world space with pre-lit face colours."""
    __slots__ = ("verts", "faces", "center", "radius", "visible", "tag")

    def __init__(self, mesh, light, m=M_IDENT, t=(0.0, 0.0, 0.0), tag=""):
        self.tag = tag
        self.visible = True
        self.verts = [v_add(m_apply(m, v), t) for v in mesh.verts]
        self.faces = []
        for idx, col, layer, ds, em in mesh.faces:
            a, b, c = self.verts[idx[0]], self.verts[idx[1]], self.verts[idx[2]]
            nrm = v_norm(v_cross(v_sub(b, a), v_sub(c, a)))
            lit = col if em else light.shade(col, nrm)
            self.faces.append((idx, lit, layer, ds, nrm, em))
        if self.verts:
            xs = [v[0] for v in self.verts]; ys = [v[1] for v in self.verts]; zs = [v[2] for v in self.verts]
            self.center = ((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2, (min(zs) + max(zs)) / 2)
            self.radius = max(v_len(v_sub(v, self.center)) for v in self.verts)
        else:
            self.center, self.radius = (0.0, 0.0, 0.0), 0.0


class Light:
    def __init__(self, direction=(-0.45, 0.78, -0.42), ambient=0.42, diffuse=0.62,
                 sky=0.10, tint=(1.0, 0.98, 0.95)):
        self.dir = v_norm(direction)
        self.ambient, self.diffuse, self.sky, self.tint = ambient, diffuse, sky, tint

    def shade(self, col, n):
        k = self.ambient + self.diffuse * max(0.0, v_dot(n, self.dir)) + self.sky * n[1]
        return (min(255, int(col[0] * k * self.tint[0])), min(255, int(col[1] * k * self.tint[1])),
                min(255, int(col[2] * k * self.tint[2])))


# ── renderer ────────────────────────────────────────────────────────────
class SoftwareRenderer:
    """Reference CPU renderer: painter's algorithm into a pygame Surface.

    Always available (no GPU needed). engine3d.gl.GLRenderer subclasses this
    for camera maths and scene baking and replaces the rasteriser."""
    NEAR = 0.06
    backend = "software"

    def __init__(self, w, h, fog=(96, 98, 104), fog_start=18.0, fog_end=210.0):
        self.w, self.h = w, h
        self.surface = pygame.Surface((w, h))
        self.fog, self.fog_start, self.fog_end = fog, fog_start, fog_end
        self.light = Light()
        self.lights = []          # local point/spot lights (Phase 11 step 2)
        self.light_cap = 4        # GL uploads this many (max 8); software keeps set_lights' cap
        # Local lights normally ADD their colour to a face, so a warm spot turns
        # a near-black coat tan.  ``light_albedo`` multiplies them by the surface
        # colour instead (``light_gain`` scales it), both backends.  Off by default.
        self.light_albedo = False
        self.light_gain = 1.0
        self.blob_shadows = True  # soft contact shadows (Phase 11 step 3)
        self.textures = {}        # tex_id -> numpy (h, w, 3) (P11 step 9)
        self._blob_cache = {}
        self.objs = []
        self.set_camera((0, 2, -10), (0, 1, 0), 60)
        self._items = []

    # camera -------------------------------------------------------------
    def set_camera(self, pos, target, fov, roll=0.0):
        self.cam = pos
        f = v_norm(v_sub(target, pos))
        up = (0.0, 1.0, 0.0)
        r = v_cross(up, f)
        if v_len(r) < 1e-6:
            r = (1.0, 0.0, 0.0)
        r = v_norm(r)
        u = v_cross(f, r)
        if roll:
            c, s = math.cos(math.radians(roll)), math.sin(math.radians(roll))
            r, u = (v_add(v_mul(r, c), v_mul(u, s)), v_sub(v_mul(u, c), v_mul(r, s)))
        self.right, self.up, self.fwd = r, u, f
        self.fov = fov
        self.focal = (self.w / 2) / math.tan(math.radians(fov) / 2)
        self.tan_h = (self.w / 2) / self.focal
        self.tan_v = (self.h / 2) / self.focal

    def to_cam(self, p):
        dx, dy, dz = p[0] - self.cam[0], p[1] - self.cam[1], p[2] - self.cam[2]
        r, u, f = self.right, self.up, self.fwd
        return (dx * r[0] + dy * r[1] + dz * r[2], dx * u[0] + dy * u[1] + dz * u[2],
                dx * f[0] + dy * f[1] + dz * f[2])

    def project(self, p):
        """World point -> (sx, sy, z) or None when behind the camera."""
        x, y, z = self.to_cam(p)
        if z <= self.NEAR:
            return None
        return (self.w / 2 + x / z * self.focal, self.h / 2 - y / z * self.focal, z)

    def horizon_y(self):
        f = self.fwd
        # screen y of a point infinitely far ahead along the horizontal
        hz = (f[0], 0.0, f[2])
        if v_len(hz) < 1e-6:
            return -9999 if f[1] < 0 else 9999
        x, y, z = (v_dot(hz, self.right), v_dot(hz, self.up), v_dot(hz, self.fwd))
        if z <= 1e-6:
            return -9999
        return self.h / 2 - y / z * self.focal

    def visible_sphere(self, c, r):
        x, y, z = self.to_cam(c)
        if z + r < self.NEAR:
            return False
        if z - r > self.fog_end + 60:
            return False
        # side planes (normalised), cheap and conservative
        kh = math.sqrt(1 + self.tan_h * self.tan_h)
        kv = math.sqrt(1 + self.tan_v * self.tan_v)
        if abs(x) - z * self.tan_h > r * kh:
            return False
        if abs(y) - z * self.tan_v > r * kv:
            return False
        return True

    # scene --------------------------------------------------------------
    def bake(self, mesh, m=M_IDENT, t=(0.0, 0.0, 0.0), tag=""):
        o = Obj(mesh, self.light, m, t, tag)
        self.objs.append(o)
        return o

    def begin(self):
        self._items = []

    def _fog_k(self, z):
        if z <= self.fog_start:
            return 0.0
        k = (z - self.fog_start) / (self.fog_end - self.fog_start)
        return 1.0 if k >= 1 else k

    def _tex_grid(self, size):
        """Shared (XX, YY) float grids for the texture rasterizer,
        cached per surface size (allocating them per flush also hurt)."""
        grid = getattr(self, "_grid_cache", None)
        if grid is None or grid[0] != size:
            import numpy as np

            w, h = size
            xx, yy = np.mgrid[0:w, 0:h].astype(np.float32)
            grid = (size, (xx, yy))
            self._grid_cache = grid
        return grid[1]

    def set_texture(self, tex_id, arr) -> None:
        """Register a texture (numpy (h, w, 3) uint8) for textured faces
        (P11 step 9: palette textures, software nearest sampling)."""
        self.textures[tex_id] = arr

    def set_lights(self, lights, cap=8):
        """Local lights for this frame: dicts with pos/color/intensity/
        range and kind 'point'|'spot' (spot adds dir + cone=cos(half-angle)).
        The strongest ``cap`` win - the per-set light budget (§6.7 step 2)."""
        ls = sorted(lights, key=lambda L: -float(L.get("intensity", 1.0)))
        self.lights = ls[:cap]

    def _local_light(self, col, centre, n, base=None):
        """Add point/spot contributions at a face centre (software path:
        per-face evaluation of the per-vertex model, §6.7 step 2).
        ``base`` = the face albedo, used when ``light_albedo`` is on."""
        r_, g_, b_ = col
        mod = base if (self.light_albedo and base is not None) else None
        gain = self.light_gain
        for L in self.lights:
            lx, ly, lz = L["pos"]
            dx, dy, dz = lx - centre[0], ly - centre[1], lz - centre[2]
            d2 = dx * dx + dy * dy + dz * dz
            rng = float(L.get("range", 6.0))
            if d2 >= rng * rng or d2 < 1e-9:
                continue
            d = d2 ** 0.5
            fall = (1.0 - d / rng) ** 2 * float(L.get("intensity", 1.0))
            if L.get("kind") == "spot":
                ddir = L["dir"]
                cosang = -(dx * ddir[0] + dy * ddir[1] + dz * ddir[2]) / d
                cone = float(L.get("cone", 0.7))
                if cosang <= cone:
                    continue
                fall *= min(1.0, (cosang - cone) / 0.12)
            nd = (n[0] * dx + n[1] * dy + n[2] * dz) / d
            if nd <= 0.0:
                continue
            k = fall * nd
            lc = L["color"]
            if mod is not None:
                k *= gain / 255.0
                r_ += lc[0] * mod[0] * k
                g_ += lc[1] * mod[1] * k
                b_ += lc[2] * mod[2] * k
            else:
                r_ += lc[0] * k
                g_ += lc[1] * k
                b_ += lc[2] * k
        return (min(255, int(r_)), min(255, int(g_)), min(255, int(b_)))

    def _emit(self, wverts, faces, dynamic_light=None, bias=0.0, tint=None):
        """Transform + cull + clip + project faces of one object into items."""
        cam = self.cam
        r, u, f = self.right, self.up, self.fwd
        cx, cy, cz = cam
        r0, r1, r2 = r; u0, u1, u2 = u; f0, f1, f2 = f
        cv = []
        for (px, py, pz) in wverts:
            dx, dy, dz = px - cx, py - cy, pz - cz
            cv.append((dx * r0 + dy * r1 + dz * r2, dx * u0 + dy * u1 + dz * u2,
                       dx * f0 + dy * f1 + dz * f2))
        near = self.NEAR
        foc = self.focal
        hw, hh = self.w / 2, self.h / 2
        W, H = self.w, self.h
        fog = self.fog
        fs, fe = self.fog_start, self.fog_end
        items = self._items
        light = dynamic_light
        for face in faces:
            idx, col, layer, ds, nrm, em = face[:6]
            fb = face[6] if len(face) > 6 else 0.0
            base_col = col
            tex = face[7] if len(face) > 7 else None
            clipped = False
            p0 = wverts[idx[0]]
            if nrm is None:
                a, b, c = p0, wverts[idx[1]], wverts[idx[2]]
                nrm = v_norm(v_cross(v_sub(b, a), v_sub(c, a)))
            facing = (nrm[0] * (cx - p0[0]) + nrm[1] * (cy - p0[1]) + nrm[2] * (cz - p0[2]))
            if facing <= 0 and not ds:
                continue
            if not em and (light is not None or self.lights):
                n2 = nrm if facing > 0 else (-nrm[0], -nrm[1], -nrm[2])
                if light is not None:
                    col = light.shade(col, n2)
                if self.lights:
                    inv = 1.0 / len(idx)
                    centre = (sum(wverts[i][0] for i in idx) * inv,
                              sum(wverts[i][1] for i in idx) * inv,
                              sum(wverts[i][2] for i in idx) * inv)
                    col = self._local_light(col, centre, n2, base_col)
            if tint is not None and not em:
                col = mix_col(col, tint[0], tint[1])
            pts = [cv[i] for i in idx]
            zmin = min(p[2] for p in pts)
            if zmin < near:
                if max(p[2] for p in pts) < near:
                    continue
                pts = _clip_near(pts, near)
                clipped = True
                if len(pts) < 3:
                    continue
            depth = 0.0
            scr = []
            minx = miny = 1e9; maxx = maxy = -1e9
            for (x, y, z) in pts:
                sx = hw + x / z * foc
                sy = hh - y / z * foc
                scr.append((sx, sy))
                depth += z
                if sx < minx: minx = sx
                if sx > maxx: maxx = sx
                if sy < miny: miny = sy
                if sy > maxy: maxy = sy
            if maxx < 0 or minx > W or maxy < 0 or miny > H:
                continue
            depth /= len(pts)
            lit_col = col
            fog_k = 0.0
            if not em and depth > fs:
                fog_k = (depth - fs) / (fe - fs)
                if fog_k > 1: fog_k = 1.0
                col = (int(col[0] + (fog[0] - col[0]) * fog_k), int(col[1] + (fog[1] - col[1]) * fog_k),
                       int(col[2] + (fog[2] - col[2]) * fog_k))
            if (tex is not None and not clipped and len(scr) == 4
                    and tex[0] in self.textures):
                draw = _tex_draw(self.textures[tex[0]], scr, tex[1], lit_col,
                                 base_col, col, fog, fog_k)
                items.append((layer * 1e6 - depth - bias + fb, draw,
                              (0, 0, 1.0, depth)))
            else:
                items.append((layer * 1e6 - depth - bias + fb, col, scr))

    def add_static(self):
        for o in self.objs:
            if not o.visible or not o.faces:
                continue
            if not self.visible_sphere(o.center, o.radius):
                continue
            self._emit(o.verts, o.faces)

    def add_dynamic(self, wverts, faces, bias=0.0, tint=None):
        """faces: (idx, colour, layer, double, None, emissive) - lit per frame."""
        self._emit(wverts, faces, dynamic_light=self.light, bias=bias, tint=tint)

    def _blob_disc(self, w, h, strength):
        key = (w, h, int(strength * 20))
        s = self._blob_cache.get(key)
        if s is None:
            base = self._blob_cache.get("base")
            if base is None:
                import numpy as np
                base = pygame.Surface((128, 128), pygame.SRCALPHA)
                yy, xx = np.mgrid[0:128, 0:128]
                d = ((xx - 63.5) / 62.0) ** 2 + ((yy - 63.5) / 62.0) ** 2
                a = (np.clip(1.0 - d, 0.0, 1.0) ** 1.6 * 255).astype(np.uint8)
                pygame.surfarray.pixels_alpha(base)[:] = a
                self._blob_cache["base"] = base
            s = pygame.transform.smoothscale(base, (max(2, w), max(2, h))).copy()
            s.set_alpha(int(255 * strength))
            self._blob_cache[key] = s
        return s

    def _blob_item(self, pos, rx, rz, strength):
        """Backend-agnostic blob-shadow maths -> (draw_fn, centre) or None.

        ``draw_fn`` has the sprite-callback signature
        ``(surface, sx, sy, scale, z)``; ``centre`` is the projected
        ``(sx, sy, z)`` of ``pos``. Each backend queues the item in its
        own format (software: callable item; GL: ``"sprite"`` item) -
        queueing the software tuple on the GL renderer is what crashed
        GL flushes with humanoids on screen (add_humanoid adds a blob).
        """
        if not self.blob_shadows:
            return None
        c = self.project(pos)
        if c is None:
            return None
        ex = self.project((pos[0] + rx, pos[1], pos[2]))
        ez = self.project((pos[0], pos[1], pos[2] + rz))
        if ex is None or ez is None:
            return None
        wpx = max(4, min(2 * self.w, int(abs(ex[0] - c[0]) * 2)))
        hpx = max(3, min(2 * self.h, int(abs(ez[1] - c[1]) * 2 + wpx * 0.18)))
        if len(self._blob_cache) > 96:  # keep the scaled-disc cache bounded
            base = self._blob_cache.get("base")
            self._blob_cache.clear()
            if base is not None:
                self._blob_cache["base"] = base

        def _draw(surface, sx, sy, scale, z, _c=c, _w=wpx, _h=hpx, _s=strength):
            disc = self._blob_disc(_w, _h, _s)
            surface.blit(disc, (int(_c[0] - _w / 2), int(_c[1] - _h / 2)))

        # Exact pixel box the disc covers: lets the GL compositor depth-test
        # just these pixels instead of the generic 3.5 m sprite reach.
        _draw.bounds = (int(c[0] - wpx / 2), int(c[1] - hpx / 2), wpx, hpx)
        return _draw, c

    def add_blob_shadow(self, pos, rx, rz, strength=0.35, layer=None, bias=0.0):
        """Soft contact shadow: a blurred dark ellipse on the floor under
        an object (Phase 11 step 3). Rides the sprite-item path, so the
        GL backend composites it with depth like any sprite.

        ``layer``/``bias`` are opt-in: a floor drawn on painter layer 2 (the
        M6 platform slab) hides the default layer-0 disc, so a scene can queue
        it on the floor's own layer. Defaults reproduce the historic disc."""
        item = self._blob_item(pos, rx, rz, strength)
        if item is None:
            return
        _draw, c = item
        lay = 0 if layer is None else layer
        self._items.append((lay * 1e6 - c[2] + 0.5 + bias, _draw,
                            (c[0], c[1], self.focal / c[2], c[2])))

    def add_sprite(self, pos, draw_fn, layer=2, bias=0.0):
        """draw_fn(surface, sx, sy, scale_px_per_m, z)."""
        p = self.project(pos)
        if p is None:
            return
        sx, sy, z = p
        self._items.append((layer * 1e6 - z - bias, draw_fn, (sx, sy, self.focal / z, z)))

    def add_humanoid(self, hum, pose, pos, yaw, rifle_on=True, bias=0.0, tint=None,
                     shadow=None):
        """Pose + draw a rig.Humanoid. -> joints (world space). The GL backend
        overrides this with GPU skinning; the result is the same.

        ``shadow`` = ``(layer, bias)`` queues the contact shadow on that painter
        layer (default: the historic floor disc)."""
        v, f, j = hum.build(pose, pos, yaw, rifle_on=rifle_on)
        self.add_dynamic(v, f, bias=bias, tint=tint)
        sl, sb = shadow if shadow else (None, 0.0)
        self.add_blob_shadow((pos[0], pos[1] + 0.02, pos[2]), 0.34, 0.30, 0.40,
                             layer=sl, bias=sb)
        return j

    def add_line3d(self, a, b, col, width=1, layer=3):
        pa, pb = self.to_cam(a), self.to_cam(b)
        if pa[2] < self.NEAR and pb[2] < self.NEAR:
            return
        pts = _clip_near([pa, pb], self.NEAR, closed=False)
        if len(pts) < 2:
            return
        scr = [(self.w / 2 + x / z * self.focal, self.h / 2 - y / z * self.focal) for x, y, z in pts]
        self._items.append((layer * 1e6, ("line", col, width), scr))

    def flush(self, surface=None):
        surface = surface or self.surface
        items = self._items
        items.sort(key=lambda it: it[0])
        draw_poly = pygame.draw.polygon
        pxv = None  # shared pixels3d view across textured runs (step 9)
        try:
            for key, col, data in items:
                if callable(col) and getattr(col, "_tex_px", False):
                    if pxv is None:
                        pxv = pygame.surfarray.pixels3d(surface)
                        grid = self._tex_grid(surface.get_size())
                    col((pxv, grid))
                    continue
                if callable(col) and getattr(col, "_tex_surf", False):
                    if pxv is not None:
                        del pxv
                        pxv = None
                    col(surface)
                    continue
                if pxv is not None:
                    del pxv
                    pxv = None
                if callable(col):
                    sx, sy, scale, z = data
                    col(surface, sx, sy, scale, z)
                elif type(col) is tuple and len(col) == 3 and col[0] == "line":
                    pygame.draw.line(surface, col[1], data[0], data[1], col[2])
                else:
                    draw_poly(surface, col, data)
        finally:
            if pxv is not None:
                del pxv
            self._items = []

    def flush_split(self, surface, split_depth, mid_fn):
        """Draw items farther than split_depth, call mid_fn(surface), then the
        rest (used for depth-of-field: blur the background in between)."""
        items = self._items
        items.sort(key=lambda it: it[0])
        far = []
        near = []
        for it in items:
            layer = int((it[0] + 5e5) // 1e6)
            depth = layer * 1e6 - it[0]
            (far if depth > split_depth or layer == 0 else near).append(it)
        self._items = far
        self.flush(surface)
        mid_fn(surface)
        self._items = near
        self.flush(surface)


    def flush_near_blur(self, surface, split_depth, blur_fn):
        """Sharp background, blurred foreground (rack focus to the distance).
        blur_fn(layer_surface) -> blurred surface blitted over ``surface``."""
        items = self._items
        items.sort(key=lambda it: it[0])
        far, near = [], []
        for it in items:
            layer = int((it[0] + 5e5) // 1e6)
            depth = layer * 1e6 - it[0]
            (far if depth > split_depth or layer == 0 else near).append(it)
        self._items = far
        self.flush(surface)
        if near:
            tmp = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            tmp.fill((0, 0, 0, 0))
            self._items = near
            self.flush(tmp)
            surface.blit(blur_fn(tmp), (0, 0))
        self._items = []


Renderer = SoftwareRenderer


def _clip_near(pts, near, closed=True):
    out = []
    n = len(pts)
    rng = range(n) if closed else range(n - 1)
    if not closed:
        a = pts[0]
        b = pts[1]
        if a[2] >= near and b[2] >= near:
            return [a, b]
        t = (near - a[2]) / (b[2] - a[2])
        c = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near)
        return [c, b] if a[2] < near else [a, c]
    for i in rng:
        a = pts[i]
        b = pts[(i + 1) % n]
        ain = a[2] >= near
        bin_ = b[2] >= near
        if ain:
            out.append(a)
        if ain != bin_:
            t = (near - a[2]) / (b[2] - a[2])
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, near))
    return out
