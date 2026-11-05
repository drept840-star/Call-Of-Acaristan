"""intro3d.py - engine3d takes for the opening narration (``core.cutscene1``).

Seven shots, one per narrated line, on the same late-PS2 pipeline as the van
take that follows them (``cutscenes.van3d``): 0.64 internal buffer, the film
grade and the crisp upscale into the whole scene band.

    intro_ocean       the Kilemeno at dusk: faceted swell, a trawler and its
                      fisherman, the derrick graveyard, one rig still burning
    intro_city        a pumpjack nodding among the slum roofs, the crane rises
                      to the towers of Acaristan City
    intro_poster      an IPA poster on a wet brick wall, a passer-by, rain
    intro_graffiti    the MAG mask sprayed on a container, a burning barrel
    intro_convoy      the KRAP vans on the steppe road, villagers watching
    intro_checkpoint  a KRAP sentry, FuegoTech crates, the barrier lifts for
                      an oil tanker
    intro_arrival     Biribel in the rain, the van behind him, the city ahead

Contract: ``fn(surface, t_ms)`` draws the scene band only; the narration stays
with the CutscenePlayer. ``cutscenes.engine`` registers these lazily and falls
back to the painted 2D shots when the 3D stack declines.

Axes: x east, y up, z north; the cameras mostly look north (+z).
"""
import math
import random

import pygame

from core.config import SCENE_H, SCENE_TOP, WIDTH
from engine.text import T as _T
from engine3d.core import (Mesh, _orient_outward, box, m_apply, prism, quad_xz,
                           rot_x, rot_y, rot_z, v_cross, v_dot, v_len, v_norm, v_sub)
from engine3d.textures import tex
from cutscenes import m5fx3d as _m5
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7world3d as F
from cutscenes.van3d import _WHEELS, WHEEL_R, _HEAD, _TAIL, _Part, _faces, _van_parts

__all__ = ["SCENES", "prepare"]

RES = 0.64
RW, RH = int(WIDTH * RES), int(SCENE_H * RES)
LAY = _fx.FX_LAYER
_S = {"van": None, "parts": {}, "surf": {}, "dyn": {}}

LOOKS = {
    "dusk_sea": dict(fog=(168, 96, 64), fog_start=60.0, fog_end=470.0,
                     light=dict(direction=(0.25, 0.22, 0.94), ambient=0.46, diffuse=0.58,
                                sky=0.10, tint=(1.0, 0.74, 0.56)),
                     top=(30, 26, 46), bot=(206, 112, 62), sodium=(110, 52, 26),
                     mist=(120, 70, 50), clouds=3, stars=0),
    "city": dict(fog=(52, 36, 42), fog_start=40.0, fog_end=330.0,
                 light=dict(direction=(0.5, 0.3, 0.8), ambient=0.40, diffuse=0.40,
                            sky=0.10, tint=(0.94, 0.74, 0.70)),
                 top=(12, 13, 28), bot=(124, 62, 50), sodium=(96, 46, 26),
                 mist=(60, 40, 44), clouds=3, stars=18),
    "steppe": dict(fog=(160, 118, 86), fog_start=40.0, fog_end=300.0,
                   light=dict(direction=(-0.75, 0.38, -0.3), ambient=0.48, diffuse=0.66,
                              sky=0.10, tint=(1.0, 0.8, 0.6)),
                   top=(66, 66, 92), bot=(222, 150, 96), sodium=(120, 70, 36),
                   mist=(150, 110, 80), clouds=2, stars=0),
    "night": dict(fog=(10, 12, 18), fog_start=18.0, fog_end=140.0,
                  light=dict(direction=(-0.3, 0.8, -0.5), ambient=0.46, diffuse=0.24,
                             sky=0.08, tint=(0.74, 0.84, 1.06)),
                  top=(5, 7, 13), bot=(26, 20, 24), sodium=(36, 22, 16),
                  mist=(20, 22, 30), clouds=2, stars=0),
    "night_city": dict(fog=(14, 14, 22), fog_start=30.0, fog_end=260.0,
                       light=dict(direction=(-0.3, 0.8, -0.5), ambient=0.46, diffuse=0.24,
                                  sky=0.08, tint=(0.74, 0.84, 1.06)),
                       top=(6, 8, 15), bot=(44, 28, 30), sodium=(70, 38, 22),
                       mist=(26, 24, 32), clouds=2, stars=0),
}

# palette (2D cutscene colours, a step brighter for lighting)
STEEL = (76, 78, 84)
STEEL_D = (44, 46, 52)
RUST = (112, 58, 40)
SCORCH = (34, 30, 30)
YEL = (172, 132, 54)
CREAM = (150, 146, 132)
WIN_WARM = (214, 168, 92)
WIN_COLD = (176, 196, 236)
KRAP_BLUE = (52, 92, 150)
SHACKS = ((70, 46, 40), (48, 52, 62), (66, 56, 44), (58, 58, 60), (74, 64, 50))


# ── small builders ──────────────────────────────────────────────────────────
def _k(t, start, length):
    return F.k(t, start, length)


def _mix(a, b, u):
    return F.mix(a, b, u)


def _beam(a, b, w, col, h=None, layer=2, emissive=False):
    """Square-section bar from ``a`` to ``b`` (truss members, booms, masts)."""
    h = h or w
    d = v_sub(b, a)
    if v_len(d) < 1e-6:
        return Mesh()
    f = v_norm(d)
    up = (0.0, 1.0, 0.0) if abs(f[1]) < 0.95 else (1.0, 0.0, 0.0)
    u = v_norm(v_cross(up, f))
    v = v_cross(f, u)
    pts = []
    for p in (a, b):
        for i, j in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            pts.append(tuple(p[k] + u[k] * i * w * 0.5 + v[k] * j * h * 0.5 for k in range(3)))
    m = Mesh()
    m.verts = pts
    quads = ((0, 1, 2, 3), (4, 7, 6, 5), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0))
    m.faces = [(q, col, layer, False, emissive) for q in quads]
    return _orient_outward(m)


def _cyl(cx, cz, r, y0, y1, col, n=8):
    """Upright n-gon column (barrels, buoys, tank legs)."""
    prof = [(math.cos(2 * math.pi * i / n) * r, math.sin(2 * math.pi * i / n) * r)
            for i in range(n)]
    m = prism(prof, y1 - y0, col, z0=0.0)
    return Mesh().add(m, m=rot_x(-90), t=(cx, y0, cz))


def _win(m, x0, x1, y0, y1, z, col, face="-z"):
    """Self-lit window quad just proud of a wall facing ``face``."""
    if face == "-z":
        m.face([(x0, y0, z), (x0, y1, z), (x1, y1, z), (x1, y0, z)], col, 2, False, True)
    else:  # facing -x, x0/x1 are z extents
        m.face([(z, y0, x1), (z, y1, x1), (z, y1, x0), (z, y0, x0)], col, 2, False, True)


def _place(m, pos, yaw=0.0, mat=None):
    out = Mesh()
    out.add(m, m=mat if mat is not None else rot_y(yaw), t=pos)
    return out


def _decal(surf, center, size, q=8):
    """Pixel art -> lit coplanar quads on a wall facing -z (see m5decal)."""
    from cutscenes.m5decal import _rects
    sw, sh = surf.get_size()
    cx, cy, cz = center
    w, h = size
    m = Mesh()

    def p(px, py):
        return (cx + (px / sw - 0.5) * w, cy + (0.5 - py / sh) * h, cz)

    for x0, y0, x1, y1, col in _rects(surf, q=q):
        m.face([p(x0, y1), p(x0, y0), p(x1, y0), p(x1, y1)], col, 2, False, False)
    return m, -0.8


def _surf(key, fn):
    s = _S["surf"].get(key)
    if s is None:
        s = _S["surf"][key] = fn()
    return s


def _pix(name, scale=1):
    from ui.pixfont import font
    return font(name, scale)


# ── stage plumbing ──────────────────────────────────────────────────────────
def _stage(key, look, t, eye, tgt, fov, build, lights=(), hh=0.0, seed=0, roll=0.0, sun=None):
    r, buf = _w.rend(RW, RH)
    r.light_cap = 8
    p = LOOKS[look]
    r.fog, r.fog_start, r.fog_end = p["fog"], p["fog_start"], p["fog_end"]
    from engine3d.core import Light
    r.light = Light(**p["light"])
    r.set_lights(list(lights), cap=8)
    _w.cam(r, t, eye, tgt, fov, hh=hh, seed=seed, roll=roll)
    _m5.night_sky(r, buf, t, p["top"], p["bot"], stars=p["stars"], clouds=p["clouds"],
                  sodium=p["sodium"], mist=p["mist"], seed=seed)
    if sun is not None:
        _sun_disc(r, buf, sun)
    fresh = _w.static_scene(r, "intro:" + key)
    r.begin()
    ok = False
    try:
        if fresh:
            dyn = _S["dyn"][key] = []
            for m in build():
                if isinstance(m, tuple):
                    dyn.append(m)
                else:
                    _w.add(r, m)
        ok = True
    finally:
        _w.static_end(r, ok)
    # decals stay live: the painter only honours a depth bias on dynamic faces
    for m, bias in _S["dyn"].get(key, ()):
        _w.add(r, m, bias=bias)
    return r, buf


def _finish(surface, r, buf, t, seed):
    r.flush(buf)
    _fx.grade_cine(buf)
    _fx.present_crisp(buf, surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)))
    try:
        from cutscenes.post3d import apply_post  # lazy: numpy stack
        apply_post(surface.subsurface((0, SCENE_TOP, WIDTH, SCENE_H)),
                   {"grain": 0.12, "vignette": 0.25}, int(t), "intro_%d" % seed)
    except Exception:
        pass


def _sun_disc(r, buf, sun):
    """Low sun painted into the sky before the geometry, so rigs cut it."""
    d = v_norm(sun)
    c = r.cam
    q = r.project((c[0] + d[0] * 900.0, c[1] + d[1] * 900.0, c[2] + d[2] * 900.0))
    if q is None:
        return
    sx, sy = q[0], q[1]
    _m5._add_at(buf, _m5._halo((150, 66, 28), 120), sx, sy)
    _m5._add_at(buf, _m5._halo((200, 110, 50), 42), sx, sy)
    pygame.draw.circle(buf, (255, 206, 142), (int(sx), int(sy)), 13)
    pygame.draw.circle(buf, (255, 232, 190), (int(sx), int(sy)), 10)


# ── shared sets ─────────────────────────────────────────────────────────────
def _towers(seed, z0, z1, x0, x1, hmin=60.0, hmax=150.0, n=9, crane=True):
    """Glass and panel towers with lit window grids -> (meshes, beacon points)."""
    rng = random.Random(seed)
    out, beacons = [], []
    xs = sorted(rng.uniform(x0, x1) for _ in range(n))
    for i, x in enumerate(xs):
        w = rng.uniform(14.0, 24.0)
        d = rng.uniform(12.0, 18.0)
        h = rng.uniform(hmin, hmax)
        z = rng.uniform(z0, z1)
        col = rng.choice(((42, 48, 60), (50, 54, 64), (36, 42, 54), (58, 56, 60)))
        m = Mesh()
        m.add(box(w, h, d, tex("concrete", like=col), center=(x, h / 2, z), seg=40.0,
                  cols={"top": tuple(c + 8 for c in col)}))
        m.add(box(w * 0.5, 4.0, d * 0.5, STEEL_D, center=(x, h + 2.0, z)))
        zf = z - d / 2 - 0.05
        cold = rng.random() < 0.6
        y = 4.0
        while y < h - 4:
            xx = x - w / 2 + 1.5
            while xx < x + w / 2 - 2.0:
                if rng.random() < 0.34:
                    c = WIN_COLD if cold else WIN_WARM
                    k = rng.uniform(0.55, 1.0)
                    _win(m, xx, xx + 1.4, y, y + 1.8, zf, tuple(int(v * k) for v in c))
                xx += 3.0
            y += 4.0
        out.append(m)
        beacons.append((x, h + 4.4, z))
        if crane and i == n // 2:
            cm = Mesh()
            top = h + 26.0
            cm.add(_beam((x + 2, h, z), (x + 2, top, z), 1.4, YEL))
            cm.add(_beam((x - 30, top, z), (x + 14, top, z), 1.2, YEL, h=1.6))
            cm.add(_beam((x + 2, top + 6, z), (x - 30, top, z), 0.3, YEL))
            cm.add(_beam((x + 2, top + 6, z), (x + 14, top, z), 0.3, YEL))
            cm.add(box(5, 3, 3, STEEL_D, center=(x + 12, top - 2, z)))
            cm.add(_beam((x - 22, top, z), (x - 22, top - 18, z), 0.08, STEEL_D))
            out.append(cm)
            beacons.append((x - 30, top + 0.8, z))
    return out, beacons


def _beacons(r, t, pts, col=(255, 52, 40), period=1600.0):
    for i, p in enumerate(pts):
        r.add_sprite(p, _fx.beacon(col, 2.2, t, period_ms=period, phase=i * 0.37, intensity=0.95),
                     layer=LAY)


def _pumpjack(pos, t, s=1.0, speed=1.0, yaw=0.0):
    """Nodding donkey: walking beam, horse head, crank and counterweights."""
    x, y, z = pos
    ph = t * 0.0013 * speed
    a = 14.0 * math.sin(ph)
    m = Mesh()
    m.add(box(8.2 * s, 0.4 * s, 2.0 * s, STEEL_D, center=(0.3 * s, 0.2 * s, 0)))
    for dz in (-0.75, 0.75):
        m.add(_beam((-1.0 * s, 0.4 * s, dz * s), (0, 4.3 * s, 0), 0.22 * s, YEL))
        m.add(_beam((1.0 * s, 0.4 * s, dz * s), (0, 4.3 * s, 0), 0.22 * s, YEL))
    beam = Mesh().add(box(7.4 * s, 0.5 * s, 0.5 * s, YEL, center=(0.4 * s, 0, 0)))
    head = [(0.0, 0.9), (0.45, 0.75), (0.75, 0.2), (0.65, -0.6), (0.3, -1.15), (0.0, -1.15)]
    beam.add(prism([(hx * s, hy * s) for hx, hy in head], 0.7 * s, YEL, z0=-0.35 * s),
             t=(4.1 * s, 0, 0))
    beam.add(box(1.2 * s, 0.9 * s, 0.9 * s, RUST, center=(-3.4 * s, -0.2 * s, 0)))
    piv = (0, 4.55 * s, 0)
    m.add(beam, m=rot_z(a), t=piv)
    cc = (-3.0 * s, 1.5 * s, 0)
    m.add(box(1.4 * s, 1.6 * s, 1.2 * s, STEEL, center=(-3.0 * s, 0.9 * s, 0)))
    crank = Mesh()
    for dz in (-0.75, 0.75):
        crank.add(box(2.8 * s, 0.5 * s, 0.25 * s, RUST, center=(0, 0, dz * s)))
        crank.add(box(1.0 * s, 1.4 * s, 0.35 * s, STEEL_D, center=(-1.2 * s, 0, dz * s)))
    deg = math.degrees(ph)
    m.add(crank, m=rot_z(deg), t=cc)
    rz = rot_z(a)
    tail = m_apply(rz, (-3.3 * s, -0.2 * s, 0))
    tail = (tail[0] + piv[0], tail[1] + piv[1], 0)
    pin = m_apply(rot_z(deg), (1.25 * s, 0, 0))
    for dz in (-0.75, 0.75):
        m.add(_beam((cc[0] + pin[0], cc[1] + pin[1], dz * s), (tail[0], tail[1], dz * s),
                    0.14 * s, STEEL))
    tip = m_apply(rz, (4.55 * s, -1.1 * s, 0))
    m.add(_beam((tip[0] + piv[0], tip[1] + piv[1], 0), (4.6 * s, 0.9 * s, 0), 0.06 * s, CREAM))
    m.add(box(0.6 * s, 0.9 * s, 0.6 * s, STEEL_D, center=(4.6 * s, 0.45 * s, 0)))
    return _place(m, (x, y, z), yaw)


# ── 1. the Kilemeno Ocean ───────────────────────────────────────────────────
SEA_Z = (-10, -5, 0, 5, 11, 18, 26, 36, 48, 63, 82, 106, 137, 177, 228, 294, 380, 490)
SEA_N = 30
SUN = (0.18, 0.045, 1.0)
GLINT = (255, 192, 124)
GLINT_D = (96, 66, 52)
RIGS = ((-58.0, 150.0, "live", 0.0), (24.0, 112.0, "burn", 0.0), (84.0, 236.0, "live", 0.0),
        (-20.0, 290.0, "live", 0.0), (-30.0, 72.0, "dead", 11.0), (52.0, 64.0, "stump", 0.0))
BOAT = (-7.5, 21.0)


def _wave(x, z, t):
    s = t * 0.001
    return (0.42 * math.sin(x * 0.21 + z * 0.05 + s * 1.1)
            + 0.30 * math.sin(z * 0.17 - x * 0.07 - s * 1.4)
            + 0.13 * math.sin((x + z) * 0.53 + s * 2.3))


def _sea(r, t):
    """Faceted swell, two triangles a cell; facets that mirror the sun into
    the camera turn into the glitter road."""
    cam = r.cam
    sun = v_norm(SUN)
    rows = []
    for z in SEA_Z:
        half = 44.0 + max(0.0, z) * 0.95
        amp = 1.0 / (1.0 + max(0.0, z) / 70.0)
        rows.append([((2.0 * j / SEA_N - 1.0) * half + cam[0] * 0.0,
                      amp * _wave((2.0 * j / SEA_N - 1.0) * half, z, t), float(z))
                     for j in range(SEA_N + 1)])
    verts = [p for row in rows for p in row]
    faces = []
    n1 = SEA_N + 1
    for i in range(len(rows) - 1):
        shade = 1.0 - 0.012 * i
        base = (int(30 * shade), int(42 * shade), int(50 * shade))
        for j in range(SEA_N):
            a, b = i * n1 + j, i * n1 + j + 1
            c, d = b + n1, a + n1
            for tri in ((a, d, c), (a, c, b)):
                p0, p1, p2 = verts[tri[0]], verts[tri[1]], verts[tri[2]]
                n = v_norm(v_cross(v_sub(p1, p0), v_sub(p2, p0)))
                ctr = tuple((p0[k] + p1[k] + p2[k]) / 3.0 for k in range(3))
                vd = v_norm(v_sub(ctr, cam))
                dn = v_dot(vd, n)
                refl = tuple(vd[k] - 2.0 * dn * n[k] for k in range(3))
                sp = v_dot(refl, sun)
                g = max(0.0, min(1.0, (sp - 0.97) / 0.028)) ** 2
                if g > 0.35:
                    col = tuple(int(GLINT[k] * g) for k in range(3))
                    faces.append((tri, col, 0, False, None, True))
                else:
                    col = tuple(int(base[k] + (GLINT_D[k] - base[k]) * g / 0.35) for k in range(3))
                    faces.append((tri, col, 0, False, None, False))
    r.add_dynamic(verts, faces)


def _rig_local(kind, seed):
    rng = random.Random(seed)
    dead = kind in ("dead", "burn", "stump")
    leg = tex("rust", like=(70, 52, 44)) if dead else tex("steel", like=STEEL)
    m = Mesh()
    L = 8.0
    for dx in (-L, L):
        for dz in (-L, L):
            m.add(_beam((dx, -3.0, dz), (dx, 16.0, dz), 1.5, leg))
    for y0, y1 in ((0.0, 8.0), (8.0, 15.5)):
        for (ax, az), (bx, bz) in (((-L, -L), (L, -L)), ((L, -L), (L, L)),
                                   ((L, L), (-L, L)), ((-L, L), (-L, -L))):
            m.add(_beam((ax, y0, az), (bx, y1, bz), 0.4, leg))
            m.add(_beam((bx, y0, bz), (ax, y1, az), 0.4, leg))
            m.add(_beam((ax, y1, az), (bx, y1, bz), 0.5, leg))
    if kind == "stump":
        m.add(box(9.0, 1.6, 7.0, SCORCH, center=(-4.0, 16.6, -3.0)))
        m.add(_beam((-L, 16.0, L), (-2.0, 19.0, 6.0), 0.6, SCORCH))
        return m
    deck = SCORCH if dead else tex("steel", like=(84, 82, 80))
    m.add(box(21.0, 2.2, 21.0, deck, center=(0, 17.1, 0), seg=10.0))
    m.add(box(18.0, 1.6, 16.0, deck, center=(0, 19.9, 1.0), seg=10.0))
    mods = ((-4.0, 3.0, 8.0, 4.0, 6.0, CREAM), (5.0, -3.0, 6.0, 3.0, 5.0, YEL),
            (5.5, 4.5, 5.0, 2.6, 4.0, (96, 98, 104)), (-5.0, -4.5, 6.0, 2.4, 4.0, RUST))
    for mx, mz, w, h, d, col in mods:
        col = SCORCH if dead else col
        m.add(box(w, h, d, col, center=(mx, 20.7 + h / 2, mz)))
        if not dead:
            zf = mz - d / 2 - 0.04
            xx = mx - w / 2 + 0.6
            while xx < mx + w / 2 - 0.8:
                if rng.random() < 0.55:
                    _win(m, xx, xx + 0.6, 21.6, 22.3, zf, WIN_WARM)
                xx += 1.1
    dcol = SCORCH if dead else (122, 116, 104)
    bx, bz = 2.0, -2.0
    for sx in (-1, 1):
        for sz in (-1, 1):
            m.add(_beam((bx + sx * 2.4, 20.7, bz + sz * 2.4), (bx + sx * 0.55, 43.0, bz + sz * 0.55),
                        0.32, dcol))
    for lvl in range(5):
        y = 23.0 + lvl * 4.2
        k = (y - 20.7) / 22.3
        hw = 2.4 + (0.55 - 2.4) * k
        for (ax, az), (cx, cz) in (((-1, -1), (1, -1)), ((1, -1), (1, 1)),
                                   ((1, 1), (-1, 1)), ((-1, 1), (-1, -1))):
            m.add(_beam((bx + ax * hw, y, bz + az * hw), (bx + cx * hw, y, bz + cz * hw), 0.2, dcol))
    m.add(box(1.6, 1.2, 1.6, dcol, center=(bx, 43.6, bz)))
    m.add(_beam((-8.0, 18.0, -8.0), (-8.0, 25.0, -8.0), 0.9, YEL if not dead else SCORCH))
    m.add(_beam((-8.0, 25.0, -8.0), (-21.0, 33.0, -13.0), 0.6, YEL if not dead else SCORCH))
    m.add(box(10.0, 0.5, 10.0, deck, center=(-13.0, 23.6, 7.0)))
    m.add(_beam((-9.0, 18.0, 4.0), (-13.0, 23.3, 7.0), 0.4, leg))
    if kind != "dead":
        m.add(_beam((10.0, 19.0, 0.0), (27.0, 30.0, 2.0), 0.5, dcol))
    return m


def _rig_xform(kind, tilt, x, z):
    sink = {"dead": 7.0, "stump": 4.0}.get(kind, 0.0)
    mat = rot_z(tilt) if tilt else rot_y(0)
    return mat, (x, -sink, z)


def _rig_world(kind, tilt, x, z, p):
    mat, off = _rig_xform(kind, tilt, x, z)
    q = m_apply(mat, p)
    return (q[0] + off[0], q[1] + off[1], q[2] + off[2])


def _ocean_static():
    out = []
    for i, (x, z, kind, tilt) in enumerate(RIGS):
        mat, off = _rig_xform(kind, tilt, x, z)
        out.append(_place(_rig_local(kind, 30 + i), off, mat=mat))
    return out


# hull stations, stern to stem: (z, half-width, sheer height, keel depth)
HULL = ((-4.2, 1.35, 1.25, -0.40), (-2.2, 1.6, 1.15, -0.62), (0.4, 1.62, 1.18, -0.66),
        (2.6, 1.3, 1.35, -0.55), (3.9, 0.7, 1.55, -0.30), (4.7, 0.04, 1.75, 0.25))


def _boat_local():
    """Rusted side trawler, nose +z, deck at y ~0.95: closed hull with a
    cream sheer strake, wheelhouse aft, mast forward, A-frame gantry astern."""
    m = Mesh()
    rust = tex("rust", like=(104, 44, 34))
    band = (150, 140, 118)
    bottom = (40, 30, 28)
    deck_col = tex("m7_plank", like=(96, 84, 66))
    rings = []
    for z, hw, sh, kl in HULL:
        ring = [(-hw, sh, z), (-hw * 0.99, sh - 0.28, z), (-hw * 0.86, 0.3, z), (0.0, kl, z),
                (hw * 0.86, 0.3, z), (hw * 0.99, sh - 0.28, z), (hw, sh, z)]
        rings.append(ring)
    cols = (band, rust, bottom, bottom, rust, band)
    for i in range(len(rings) - 1):
        p, q = rings[i], rings[i + 1]
        for j in range(6):
            m.face([p[j], q[j], q[j + 1], p[j + 1]], cols[j], 2, True, False)
    m.face(rings[0][::-1], rust, 2, True, False)  # transom
    for i in range(len(HULL) - 1):
        (z0, w0, s0, _), (z1, w1, s1, _) = HULL[i], HULL[i + 1]
        y0, y1 = min(s0, 1.15) - 0.2, min(s1, 1.15) - 0.2
        m.face([(-w0 * 0.95, y0, z0), (-w1 * 0.95, y1, z1), (w1 * 0.95, y1, z1), (w0 * 0.95, y0, z0)],
               deck_col, 2, True, False)
    # wheelhouse
    m.add(box(1.7, 1.5, 1.9, CREAM, center=(0, 1.7, -2.3), cols={"top": (120, 116, 104)}))
    m.add(box(2.0, 0.14, 2.2, (70, 66, 60), center=(0, 2.52, -2.3)))
    for x0 in (-0.7, -0.15, 0.4):
        m.face([(x0, 2.0, -1.33), (x0 + 0.38, 2.0, -1.33), (x0 + 0.38, 2.35, -1.33), (x0, 2.35, -1.33)],
               WIN_WARM, 2, True, True)
    for sx in (-0.87, 0.87):
        m.face([(sx, 2.0, -2.8), (sx, 2.35, -2.8), (sx, 2.35, -2.2), (sx, 2.0, -2.2)],
               WIN_WARM, 2, True, True)
    m.add(_beam((0.5, 2.6, -2.7), (0.5, 3.6, -2.7), 0.14, STEEL_D))
    m.add(_beam((-0.4, 2.6, -2.6), (-0.4, 3.0, -2.6), 0.1, STEEL_D))
    # mast, stays and boom
    m.add(_beam((0, 0.95, 1.6), (0, 6.0, 1.6), 0.16, STEEL_D))
    m.add(_beam((-0.6, 4.6, 1.6), (0.6, 4.6, 1.6), 0.1, STEEL_D))
    m.add(_beam((0, 5.8, 1.6), (0, 1.5, 4.4), 0.05, STEEL_D))
    m.add(_beam((0, 5.8, 1.6), (0, 2.6, -2.3), 0.05, STEEL_D))
    m.add(_beam((0, 1.8, 1.6), (1.9, 3.3, -0.2), 0.1, STEEL))
    # stern gantry
    for sx in (-1, 1):
        m.add(_beam((sx * 1.2, 1.0, -4.0), (sx * 0.95, 3.1, -3.75), 0.16, STEEL))
    m.add(_beam((-0.95, 3.1, -3.75), (0.95, 3.1, -3.75), 0.16, STEEL))
    m.add(_beam((0.3, 3.1, -3.75), (0.3, 1.6, -4.3), 0.04, STEEL_D))
    # net pile, floats, winch drum
    for i in range(5):
        m.add(box(0.7, 0.3, 0.6, (64, 72, 60), center=(-0.5 + (i % 3) * 0.45, 1.1, -0.3 + i * 0.3)))
    for i in range(4):
        m.add(box(0.2, 0.2, 0.2, (186, 92, 40), center=(0.7 - i * 0.12, 1.32, 0.2 + i * 0.25)))
    m.add(box(1.0, 0.45, 0.45, (70, 72, 74), center=(0, 1.2, -1.0)))
    return m


def _boat_pose(t):
    x, z = BOAT
    y = _wave(x, z, t) * 0.55
    pitch = (_wave(x, z + 2.0, t) - _wave(x, z - 2.0, t)) * 4.0
    roll = (_wave(x + 1.5, z, t) - _wave(x - 1.5, z, t)) * 5.0 + 1.5 * math.sin(t * 0.0009)
    mat = rot_y(-28)
    from engine3d.core import m_mul
    mat = m_mul(mat, m_mul(rot_x(-pitch), rot_z(roll)))
    return mat, (x, y - 0.15, z)


def _buoy(t, x, z):
    y = _wave(x, z, t) * 0.7
    m = Mesh()
    m.add(_cyl(x, z, 0.55, y - 0.3, y + 0.5, (168, 54, 36)))
    m.add(_beam((x - 0.4, y + 0.5, z), (x, y + 1.9, z), 0.08, STEEL_D))
    m.add(_beam((x + 0.4, y + 0.5, z), (x, y + 1.9, z), 0.08, STEEL_D))
    m.add(_beam((x, y + 0.5, z - 0.4), (x, y + 1.9, z), 0.08, STEEL_D))
    return m, (x, y + 2.0, z)


def _gulls(r, t):
    for i in range(6):
        a = t * 0.00035 * (1.0 + 0.15 * i) + i * 1.1
        cx, cy, cz = BOAT[0] + 2.0, 8.0 + i * 0.6, BOAT[1] + 4.0
        rad = 5.0 + i * 1.3
        p = (cx + math.cos(a) * rad, cy + math.sin(a * 1.7) * 0.6, cz + math.sin(a) * rad)
        flap = math.sin(t * 0.012 + i * 2.0) * 0.35
        sp = 0.55
        col = (34, 28, 30)
        r.add_line3d((p[0] - sp, p[1] + flap, p[2]), p, col, 1, layer=3)
        r.add_line3d(p, (p[0] + sp, p[1] + flap, p[2]), col, 1, layer=3)


def ocean(surface, t):
    u = _k(t, 0, 9500)
    eye = _mix((-3.5, 2.0, -4.0), (2.0, 3.4, 4.0), u)
    tgt = _mix((-5.0, 4.0, 60.0), (10.0, 12.0, 140.0), u)
    roll = 1.1 * math.sin(t * 0.0008)
    lights = [
        {"pos": _rig_world("burn", 0, 24.0, 112.0, (0, 22.0, 0)), "color": (255, 120, 50),
         "intensity": 1.6, "range": 46.0},
        {"pos": (BOAT[0], 2.4, BOAT[1] - 1.0), "color": (255, 190, 110), "intensity": 0.8,
         "range": 5.0},
    ]
    r, buf = _stage("ocean", "dusk_sea", t, eye, tgt, 50, _ocean_static, lights,
                    hh=0.03, seed=3, roll=roll, sun=SUN)
    _sea(r, t)
    mat, off = _boat_pose(t)
    boat = _S["parts"].get("boat")
    if boat is None:
        boat = _S["parts"]["boat"] = _boat_local()
    _w.add(r, _place(boat, off, mat=mat))
    deck = m_apply(mat, (0.6, 0.95, 0.6))
    me = (deck[0] + off[0], deck[1] + off[1], deck[2] + off[2])
    _w.actor(r, "fisherman", F.stand_pose(head_y=-10, head_p=-4), me,
             _w.yaw_to(me, (24.0, 0.0, 112.0)), t, seed=5, amp=0.6)
    bm, bl = _buoy(t, 3.6, 5.0)
    _w.add(r, bm)
    r.add_sprite(bl, _fx.beacon((255, 70, 40), 0.4, t, period_ms=1900.0), layer=LAY)
    for i, (x, z, kind, tilt) in enumerate(RIGS):
        if kind == "live":
            F.fire(r, _rig_world(kind, tilt, x, z, (27.0, 30.4, 2.0)), t, seed=40 + i,
                   size=1.6, smoky=False)
            r.add_sprite(_rig_world(kind, tilt, x, z, (2.0, 44.6, -2.0)),
                         _fx.beacon((255, 52, 40), 2.4, t, period_ms=1700.0, phase=i * 0.3),
                         layer=LAY)
        elif kind == "burn":
            for j, (fx, fz, sz) in enumerate(((0.0, 0.0, 4.5), (-5.0, 4.0, 3.0), (5.0, -3.0, 2.4))):
                F.fire(r, _rig_world(kind, tilt, x, z, (fx, 21.0, fz)), t, seed=60 + j,
                       size=sz, smoky=True)
    _gulls(r, t)
    _finish(surface, r, buf, t, 3)


# ── 2. Acaristan City ───────────────────────────────────────────────────────
PUMP = (2.5, 0.0, 10.0)


def _shacks(seed, x0, x1, z0, z1, keep_out=(), lit=0.3):
    rng = random.Random(seed)
    m = Mesh()
    z = z0
    while z < z1:
        x = x0 + rng.uniform(0, 2)
        while x < x1:
            w, d = rng.uniform(3.2, 5.0), rng.uniform(3.0, 4.6)
            if any(a <= x + w / 2 <= b and c <= z <= e for a, b, c, e in keep_out):
                x += w + 1.0
                continue
            base = 0.0
            for lvl in range(rng.choice((1, 1, 2, 2, 3))):
                h = rng.uniform(2.3, 3.0)
                col = rng.choice(SHACKS)
                ww = w * rng.uniform(0.8, 1.0)
                m.add(box(ww, h, d, tex("metal_rib", like=col), center=(x + w / 2, base + h / 2, z),
                          cols={"top": tuple(max(0, c - 14) for c in col)}))
                if rng.random() < lit:
                    wx = x + w / 2 + rng.uniform(-ww / 3, ww / 3)
                    _win(m, wx - 0.3, wx + 0.3, base + 1.0, base + 1.7, z - d / 2 - 0.04, WIN_WARM)
                base += h
            roof = box(w + 0.4, 0.12, d + 0.4, tex("rust", like=(80, 62, 50)),
                       center=(0, 0, 0))
            m.add(roof, m=rot_x(rng.uniform(-7, 7)), t=(x + w / 2, base + 0.1, z))
            if rng.random() < 0.25:
                m.add(_beam((x + 0.5, base, z), (x + 0.5, base + 2.2, z), 0.06, STEEL_D))
            x += w + rng.uniform(0.6, 1.6)
        z += rng.uniform(4.5, 6.0)
    return m


def _city_static():
    out = [quad_xz(-900, -40, 900, 900, 0.0, tex("m7_dirt", like=(34, 28, 28)), seg=40.0)]
    out.append(_shacks(7, -40, 40, -2, 46, keep_out=((-18.0, 10.0, -6.0, 18.0),)))
    out.append(_shacks(8, -110, 110, 50, 150, lit=0.4))
    mid, _mb = _towers(22, 118, 146, -150, 150, hmin=16.0, hmax=34.0, n=14, crane=False)
    out += mid
    tw, _b = _towers(21, 150, 220, -110, 110)
    out += tw
    out.append(_beam((150, 0, 280), (150, 46, 280), 2.4, STEEL_D))
    out.append(box(2.4, 1.0, 6.0, STEEL_D, center=(8.0, 0.5, 5.0)))
    out.append(_beam((6.5, 0, 6.0), (6.5, 5.5, 6.0), 0.18, STEEL_D))
    out.append(_beam((6.5, 5.4, 6.0), (7.7, 5.4, 6.0), 0.1, STEEL_D))
    out.append(box(0.6, 0.12, 0.3, (255, 214, 150), center=(7.8, 5.3, 6.0), emissive=True))
    for i in range(4):
        x = -14.0 + i * 9.0
        out.append(_beam((x, 0, -1.5), (x, 6.0, -1.5), 0.2, (36, 30, 28)))
    return out


def city(surface, t):
    u = _k(t, 300, 9000)
    eye = _mix((-4.2, 1.6, 1.0), (-11.0, 15.0, -12.0), u)
    tgt = _mix((2.0, 4.0, 10.5), (6.0, 40.0, 180.0), _k(t, 600, 8600))
    fov = 44 + 8 * u
    lights = [{"pos": (7.8, 5.2, 6.0), "color": (255, 180, 100), "intensity": 1.2, "range": 11.0},
              {"pos": (-8.0, 2.0, 8.0), "color": (255, 170, 90), "intensity": 0.7, "range": 6.0},
              {"pos": (9.0, 2.0, 14.0), "color": (255, 170, 90), "intensity": 0.7, "range": 6.0}]
    r, buf = _stage("city", "city", t, eye, tgt, fov, _city_static, lights, hh=0.02, seed=7)
    _w.add(r, _pumpjack(PUMP, t))
    _w.add(r, _pumpjack((-60.0, 0.0, 70.0), t + 900, s=0.9, speed=0.9, yaw=20))
    _w.add(r, _pumpjack((44.0, 0.0, 62.0), t + 400, s=0.9, speed=1.1, yaw=-15))
    r.add_sprite((7.8, 5.3, 6.0), _fx.sodium_lamp(t, seed=2, radius_m=2.0), layer=LAY)
    _tw, beacons = _towers(21, 150, 220, -110, 110)
    _beacons(r, t, beacons)
    F.fire(r, (150.0, 47.0, 280.0), t, seed=9, size=3.0, smoky=True)
    _finish(surface, r, buf, t, 7)


# ── 3. the IPA poster ───────────────────────────────────────────────────────
WALL_Z = 4.0
LAMP = (-2.6, 5.6, WALL_Z - 0.7)


def _poster_surf(defaced=False, seed=0):
    big, small = _pix("R7"), _pix("R5")
    title = _T("engine.stability")
    sub = [s.strip() for s in _T("engine.prosperity_acaristan").split("-") if s.strip()]
    ipa = _T("engine.ipa")
    w = max(big.size(title)[0], max(small.size(s)[0] for s in sub)) + 10
    h = int(w * 1.34)
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((196, 176, 136, 255))
    pygame.draw.rect(s, (150, 32, 30), (0, 0, w, 7))
    small.draw(s, ipa, ((w - small.size(ipa)[0]) // 2, 1), (230, 214, 180))
    cx, cy = w // 2, int(h * 0.33)
    rr = max(5, w // 6)
    pygame.draw.polygon(s, (42, 34, 30), [(cx - rr * 2, int(h * 0.62)), (cx - rr, cy + rr),
                                          (cx + rr, cy + rr), (cx + rr * 2, int(h * 0.62))])
    pygame.draw.polygon(s, (214, 206, 190), [(cx - 3, cy + rr), (cx + 3, cy + rr), (cx, cy + rr + 7)])
    pygame.draw.line(s, (150, 32, 30), (cx, cy + rr + 1), (cx, cy + rr + 8), 2)
    pygame.draw.ellipse(s, (150, 118, 92), (cx - rr + 1, cy - rr, rr * 2 - 2, int(rr * 2.2)))
    pygame.draw.ellipse(s, (122, 94, 74), (cx, cy - rr, rr - 1, int(rr * 2.2)))
    pygame.draw.rect(s, (34, 28, 24), (cx - rr + 1, cy - rr, rr * 2 - 2, rr // 2 + 1))
    pygame.draw.rect(s, (30, 24, 22), (cx - rr // 2, cy - 1, 2, 1))
    pygame.draw.rect(s, (30, 24, 22), (cx + rr // 2 - 2, cy - 1, 2, 1))
    pygame.draw.rect(s, (96, 70, 58), (cx - 2, cy + rr // 2 + 1, 4, 1))
    ty = int(h * 0.66)
    big.draw(s, title, ((w - big.size(title)[0]) // 2, ty), (40, 30, 25))
    for i, line in enumerate(sub):
        small.draw(s, line, ((w - small.size(line)[0]) // 2, ty + 11 + i * 7), (70, 52, 44))
    pygame.draw.rect(s, (60, 50, 40), (0, 0, w, h), 1)
    rng = random.Random(seed)
    for _ in range(w * h // 9):
        x, y = rng.randrange(w), rng.randrange(h)
        c = s.get_at((x, y))
        k = rng.choice((0.82, 0.9, 1.08))
        s.set_at((x, y), (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)), 255))
    for _ in range(3):
        x0 = rng.choice((0, w - 1))
        y0 = rng.randrange(h // 2, h)
        pygame.draw.polygon(s, (0, 0, 0, 0), [(x0, y0), (x0, y0 + rng.randint(5, 12)),
                                              (abs(x0 - rng.randint(3, 8)), y0 + 4)])
    if defaced:
        ink = (16, 15, 15)
        pygame.draw.circle(s, ink, (cx, cy + 2), rr + 3, 2)
        pygame.draw.line(s, ink, (3, 9), (w - 4, h - 6), 2)
        pygame.draw.line(s, ink, (w - 4, 9), (3, h - 6), 2)
        for _ in range(6):
            x = rng.randrange(4, w - 4)
            y = rng.randrange(10, h - 10)
            pygame.draw.line(s, ink, (x, y), (x, y + rng.randint(3, 8)), 1)
    return s


def _poster_static():
    out = []
    out.append(box(44.0, 9.0, 0.8, tex("brick", like=(98, 62, 50)), center=(0, 4.5, WALL_Z + 0.4),
                   seg=6.0))
    out.append(box(44.0, 0.4, 1.0, (52, 48, 46), center=(0, 9.1, WALL_Z + 0.3)))
    out.append(quad_xz(-30, -14, 30, WALL_Z, 0.0, tex("pavement", like=(44, 44, 48)), seg=3.0))
    out.append(box(60.0, 0.16, 0.3, (70, 70, 74), center=(0, 0.08, -2.6)))
    out.append(quad_xz(-30, -14, 30, -2.75, -0.02, (22, 22, 26), seg=6.0))
    out.append(_decal(_surf("poster0", lambda: _poster_surf(False, 1)), (0.0, 2.75, WALL_Z - 0.02),
                      (2.3, 3.1)))
    for i, x in enumerate((-6.5, 6.4, 12.0, -12.8)):
        key = "poster%d" % (i + 1)
        surf = _surf(key, lambda i=i: _poster_surf(i % 2 == 0, 10 + i))
        out.append(_decal(surf, (x, 2.6 + 0.12 * (i % 2), WALL_Z - 0.02), (2.0, 2.7)))
    out.append(_beam((3.8, 0.0, WALL_Z - 0.15), (3.8, 9.0, WALL_Z - 0.15), 0.18, (54, 58, 60)))
    out.append(_beam((LAMP[0], 5.8, WALL_Z), (LAMP[0], 5.8, LAMP[2]), 0.1, STEEL_D))
    out.append(box(0.6, 0.18, 0.4, STEEL_D, center=(LAMP[0], LAMP[1] + 0.1, LAMP[2])))
    out.append(box(0.46, 0.06, 0.3, (255, 214, 150), center=(LAMP[0], LAMP[1] - 0.02, LAMP[2]),
                   emissive=True))
    out.append(box(1.1, 0.8, 0.7, (34, 52, 40), center=(-4.4, 0.4, WALL_Z - 0.5)))
    out.append(box(0.9, 0.5, 0.6, (60, 56, 50), center=(-5.6, 0.25, WALL_Z - 0.4)))
    return out


def poster(surface, t):
    u = _k(t, 0, 9000)
    eye = _mix((-4.0, 1.7, -7.5), (-0.4, 2.6, -2.4), u)
    tgt = _mix((-0.6, 2.3, WALL_Z), (0.0, 2.75, WALL_Z), u)
    fov = 46 - 6 * u
    lights = [{"pos": (LAMP[0], LAMP[1] - 0.1, LAMP[2]), "color": (255, 182, 104),
               "intensity": 1.5, "range": 9.0}]
    r, buf = _stage("poster", "night", t, eye, tgt, fov, _poster_static, lights, hh=0.015, seed=11)
    r.add_sprite((LAMP[0], LAMP[1] - 0.05, LAMP[2]), _fx.sodium_lamp(t, seed=3, radius_m=2.0),
                 layer=LAY)
    r.add_sprite((LAMP[0], LAMP[1] - 2.6, LAMP[2]),
                 _fx.light_shaft(_fx.SODIUM, height_m=5.4, top_m=0.5, bot_m=2.6, t=t, seed=3,
                                 intensity=0.20), layer=LAY)
    for i, x in enumerate((LAMP[0], LAMP[0] + 1.2)):
        r.add_sprite((x, 0.02, LAMP[2] - 1.4 - i),
                     _m5.wet_reflection((255, 178, 100), t, seed=i, length_m=2.6, width_m=0.5,
                                        intensity=0.45), layer=2)
    walk = max(0.0, t - 600) * 0.0013
    x = -9.0 + walk
    if x < 10.0:
        me = (x, 0.0, 1.6)
        _w.actor(r, "civilian", F.walk_pose(t, 1.0, tired=0.5), me, _w.yaw_to(me, (x + 1, 0, 1.6)),
                 t, seed=13, amp=0.3)
    _m5.rain3d(r, t, seed=11, n_near=60, n_far=130, ground=0.0, splashes=8,
               surface=lambda x, z: 0.0 if z < WALL_Z else None)
    _finish(surface, r, buf, t, 11)


# ── 4. the MAG mask ─────────────────────────────────────────────────────────
CONT_Z = 3.0
BARREL = (1.4, -1.8)


def _mag_surf():
    w, h = 64, 84
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    rng = random.Random(23)
    ink = (16, 15, 15, 255)
    cx, cy, k = w // 2, 34, 2.6
    pts = [(0, -8), (-6, -12), (-10, -2), (-8, 8), (0, 12), (8, 8), (10, -2), (6, -12)]
    poly = [(cx + int(px * k), cy + int(py * k)) for px, py in pts]
    for _ in range(260):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(27, 34)
        x, y = int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr * 1.08)
        if 0 <= x < w and 0 <= y < h:
            s.set_at((x, y), ink)
    pygame.draw.polygon(s, ink, poly)
    for ex in (-3, 3):
        pygame.draw.circle(s, (186, 32, 30, 255), (cx + int(ex * k), cy + int(-2 * k)), 3)
    for _ in range(9):
        x = rng.randint(cx - 18, cx + 18)
        y0 = cy + rng.randint(10, 24)
        pygame.draw.line(s, ink, (x, y0), (x, y0 + rng.randint(4, 14)), 1)
    small = _pix("R5")
    tag = _T("engine.maru_sees_you")
    tw = small.size(tag)[0]
    small.draw(s, tag, ((w - tw) // 2, 68), ink)
    for _ in range(5):
        x = rng.randint((w - tw) // 2, (w + tw) // 2)
        pygame.draw.line(s, ink, (x, 74), (x, 74 + rng.randint(2, 8)), 1)
    return s


def _graffiti_static():
    out = []
    out.append(quad_xz(-40, -20, 40, 30, 0.0, tex("m7_dirt", like=(44, 40, 36)), seg=4.0))
    rib = tex("metal_rib", like=(112, 54, 40))
    rib2 = tex("metal_rib", like=(46, 66, 74))
    out.append(box(12.2, 2.6, 2.4, rib, center=(-1.0, 1.3, CONT_Z + 1.2)))
    out.append(box(12.2, 2.6, 2.4, rib2, center=(-7.5, 3.9, CONT_Z + 1.6)))
    out.append(box(12.2, 2.6, 2.4, rib2, center=(11.6, 1.3, CONT_Z + 1.5)))
    out.append(box(12.2, 2.6, 2.4, tex("rust", like=(92, 70, 50)), center=(11.0, 3.9, CONT_Z + 1.9)))
    for x in (-7.1, 5.1):
        out.append(box(0.12, 2.6, 0.1, (50, 30, 24), center=(x, 1.3, CONT_Z - 0.02)))
    out.append(_decal(_surf("mag", _mag_surf), (-0.4, 1.42, CONT_Z - 0.03), (2.2, 2.6)))
    out.append(_cyl(BARREL[0], BARREL[1], 0.32, 0.0, 0.92, tex("rust", like=(80, 44, 32))))
    for i, (x, z) in enumerate(((-3.6, -1.2), (-4.2, -0.6), (-3.9, -0.9))):
        out.append(_place(_cyl(0, 0, 0.42, 0.0, 0.24, (20, 20, 22), n=10), (x, i * 0.24, z)))
    for i in range(6):
        x = 6.0 + i * 2.4
        out.append(_beam((x, 0, -2.4), (x, 2.2, -2.4), 0.08, (60, 62, 66)))
    out.append(box(3.6, 1.2, 1.7, (40, 38, 36), center=(-9.0, 0.6, -0.6)))
    out.append(box(2.0, 0.7, 1.6, (30, 30, 32), center=(-9.4, 1.5, -0.6)))
    return out


def graffiti(surface, t):
    u = _k(t, 0, 9500)
    eye = _mix((-5.6, 1.4, -7.4), (-1.6, 1.55, -3.4), u)
    tgt = _mix((-2.0, 1.5, CONT_Z), (-0.4, 1.55, CONT_Z), u)
    fl = 1.0 + 0.25 * math.sin(t * 0.021) + 0.15 * math.sin(t * 0.047 + 1.3)
    lights = [{"pos": (BARREL[0], 1.5, BARREL[1]), "color": (255, 120, 44),
               "intensity": 1.5 * fl, "range": 8.0}]
    r, buf = _stage("graffiti", "night", t, eye, tgt, 44, _graffiti_static, lights, hh=0.02, seed=23)
    F.fire(r, (BARREL[0], 0.94, BARREL[1]), t, seed=23, size=0.6, smoky=True)
    for i in range(10):
        age = ((t / 1700.0) + i / 10.0) % 1.0
        p = (BARREL[0] + math.sin(i * 2.3 + t * 0.001) * 0.4 * age, 1.2 + age * 3.4,
             BARREL[1] + math.cos(i * 1.7) * 0.3 * age)
        r.add_sprite(p, _fx.glow((255, 140, 50), 0.08, t, intensity=0.9 * (1 - age)), layer=LAY)
    for i in range(5):
        x = 6.0 + i * 2.4
        r.add_line3d((x, 2.1, -2.4), (x + 2.4, 2.1, -2.4), (70, 72, 76), 1, layer=2)
        r.add_line3d((x, 1.2, -2.4), (x + 2.4, 1.2, -2.4), (70, 72, 76), 1, layer=2)
    _finish(surface, r, buf, t, 23)


# ── 5. the convoy ───────────────────────────────────────────────────────────
VAN_SPEED = 11.0
POLE_X = tuple(-150.0 + i * 32.0 for i in range(11))


def _steppe_static():
    out = []
    out.append(quad_xz(-320, -80, 320, 420, 0.0, tex("m7_stubble", like=(118, 96, 62)), seg=26.0))
    out.append(box(640.0, 0.12, 7.0, tex("pavement", like=(52, 50, 50)), center=(0, 0.06, 0), seg=20.0))
    for k in range(-50, 50):
        out.append(quad_xz(k * 6.0, -0.08, k * 6.0 + 2.6, 0.08, 0.125, (176, 160, 104), layer=1))
    rng = random.Random(5)
    for zr, hmax, col in ((210.0, 30.0, (110, 84, 72)), (300.0, 46.0, (124, 96, 88))):
        xs = [-420 + i * 30 for i in range(29)]
        hs = [rng.uniform(hmax * 0.3, hmax) for _ in xs]
        m = Mesh()
        for i in range(len(xs) - 1):
            m.face([(xs[i], 0, zr), (xs[i], hs[i], zr + 8), (xs[i + 1], hs[i + 1], zr + 8),
                    (xs[i + 1], 0, zr)], col, 1, False, False)
        out.append(m)
    for x in POLE_X:
        out.append(_beam((x, 0, -7.0), (x, 7.0, -7.0), 0.22, (60, 48, 40)))
        out.append(_beam((x, 6.6, -7.6), (x, 6.6, -6.4), 0.12, (60, 48, 40)))
    return out


def _van_rig():
    if _S["van"] is None:
        _S["van"] = _van_parts()
    return _S["van"]


def _put_van(r, van, x, t, bob_seed=0.0):
    dist = x
    bob = math.sin(t * 0.011 + bob_seed) * 0.014
    van["body"].put(r, dx=x, dy=bob)
    for g in _WHEELS:
        van[g].put(r, dx=x, spin=-dist / WHEEL_R)


def convoy(surface, t):
    van = _van_rig()
    lead = -12.0 + VAN_SPEED * t * 0.001
    xs = [lead - i * 15.0 for i in range(3)]
    u = _k(t, 0, 9000)
    eye = _mix((-7.5, 1.3, -12.0), (-2.5, 1.55, -13.2), u)
    tx = max(-14.0, min(18.0, lead * 0.55 + 2.0))
    tgt = (tx, 1.6, 0.0)
    lights = []
    for x in xs:
        lights.append({"pos": (x + _HEAD[0] + 0.1, _HEAD[1], 0.0), "color": (255, 236, 190),
                       "intensity": 0.9, "range": 14.0, "kind": "spot", "dir": (1.0, -0.12, 0.0),
                       "cone": 0.86})
    r, buf = _stage("convoy", "steppe", t, eye, tgt, 44, _steppe_static, lights, hh=0.02, seed=31,
                    sun=(-0.75, 0.05, 0.55))
    for i, x in enumerate(xs):
        _put_van(r, van, x, t, bob_seed=i * 1.7)
        r.add_blob_shadow((x, 0.13, 0.0), 3.7, 1.5, 0.6)
        on = (t // 260 + i) % 2 == 0
        for z, col in ((-0.45, (60, 110, 255)), (0.45, (255, 50, 40))):
            if (z < 0) == on:
                r.add_sprite((x + 0.3, 2.62, z), _fx.glow(col, 0.6, t, intensity=0.9), layer=LAY)
        for z in (-0.8, 0.8):
            r.add_sprite((x + _HEAD[0] + 0.06, _HEAD[1], z),
                         _fx.glow((255, 236, 180), 0.7, t, core=(255, 250, 225), intensity=0.7),
                         layer=LAY)
        r.add_sprite((x - 4.0, 0.6, 0.0),
                     _fx.powder(t, seed=i, spread_m=3.4, intensity=0.42, col=(176, 140, 98), puffs=10),
                     layer=LAY)
    watchers = (("civilian", (-1.8, 0.0, -6.4), 21), ("hungry_kid", (-0.9, 0.0, -6.1), 22),
                ("civilian", (3.6, 0.0, -6.9), 23), ("fisherman", (6.2, 0.0, -7.6), 24))
    for key, me, seed in watchers:
        look = max(min(xs[0], me[0] + 18.0), me[0] - 18.0)
        _w.actor(r, key, F.stand_pose(), me, _w.yaw_to(me, (look, 0.0, 0.0)), t, seed=seed, amp=0.5)
    for i in range(len(POLE_X) - 1):
        a, b = POLE_X[i], POLE_X[i + 1]
        for dz in (-0.5, 0.5):
            prev = (a, 6.6, -7.0 + dz)
            for s in range(1, 5):
                f = s / 4.0
                p = (a + (b - a) * f, 6.6 - math.sin(f * math.pi) * 0.7, -7.0 + dz)
                r.add_line3d(prev, p, (40, 32, 30), 1, layer=2)
                prev = p
    _finish(surface, r, buf, t, 31)


# ── 6. the checkpoint ───────────────────────────────────────────────────────
BAR_PIVOT = (-0.6, 1.05, -4.4)
BOOTH = (-4.2, -6.4)
CRATES = (2.6, -6.6)
FLOOD = (7.0, -8.0)


def _stencil(text, col, name="R7"):
    f = _pix(name)
    w, h = f.size(text)
    s = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    f.draw(s, text, (1, 1), (*col, 255))
    return s


def _tanker_local():
    m = Mesh()
    m.add(box(2.4, 2.4, 2.5, (126, 34, 28), center=(5.0, 1.75, 0), cols={"top": (108, 30, 26)}))
    _win(m, -1.0, 1.0, 2.0, 2.7, 6.21, (40, 54, 70), face="-x")
    m.add(box(11.0, 0.5, 2.2, STEEL_D, center=(0.0, 0.8, 0)))
    prof = [(math.cos(2 * math.pi * i / 8 + math.pi / 8) * 1.25,
             math.sin(2 * math.pi * i / 8 + math.pi / 8) * 1.25) for i in range(8)]
    tank = prism(prof, 8.0, tex("steel", like=(150, 152, 150)), z0=-4.0)
    m.add(tank, m=rot_y(90), t=(-1.2, 2.3, 0))
    m.add(_decal(_surf("ft", lambda: _stencil(_T("engine.fuegotech"), (150, 34, 30))),
                 (-1.2, 2.4, -1.27), (4.0, 0.7))[0])
    for x in (4.8, -2.6, -4.2):
        for z in (-1.1, 1.1):
            m.add(box(1.0, 1.0, 0.4, (16, 16, 18), center=(x, 0.5, z)))
    return m


def _checkpoint_static():
    out = []
    out.append(quad_xz(-160, -40, 160, 120, 0.0, tex("m7_dirt", like=(40, 38, 36)), seg=6.0))
    out.append(box(320.0, 0.12, 7.0, tex("pavement", like=(46, 46, 50)), center=(0, 0.06, 0), seg=6.0))
    for k in range(-26, 26):
        out.append(quad_xz(k * 6.0, -0.08, k * 6.0 + 2.6, 0.08, 0.125, (150, 146, 120), layer=1))
    bx, bz = BOOTH
    out.append(box(2.6, 2.6, 2.6, tex("concrete", like=(118, 116, 108)), center=(bx, 1.3, bz)))
    out.append(box(3.0, 0.25, 3.0, (60, 62, 66), center=(bx, 2.72, bz)))
    _win(out[-1], bx - 0.9, bx + 0.9, 1.3, 2.1, bz - 1.33, WIN_WARM)
    krap = _surf("krap", lambda: _stencil(_T("engine.krap"), (236, 236, 236)))
    band = box(2.62, 0.5, 0.02, KRAP_BLUE, center=(bx, 2.35, bz - 1.31))
    out.append(band)
    out.append(_decal(krap, (bx, 2.35, bz - 1.33), (1.2, 0.36)))
    out.append(box(0.4, 1.0, 0.4, (180, 176, 160), center=(BAR_PIVOT[0], 0.5, BAR_PIVOT[2])))
    out.append(box(0.5, 0.9, 0.5, (40, 40, 44), center=(BAR_PIVOT[0], 0.45, 4.6)))
    cx, cz = CRATES
    ct = tex("crate", like=(112, 92, 60))
    ft = _surf("ft2", lambda: _stencil(_T("engine.fuegotech"), (170, 40, 30)))
    ipa = _surf("ipa", lambda: _stencil(_T("engine.property_of_ipa"), (40, 30, 26), "R5"))
    for i in range(3):
        for j in range(2 if i < 2 else 1):
            x, y = cx + i * 1.3, 0.48 + j * 0.96
            out.append(box(1.25, 0.94, 1.0, ct, center=(x, y, cz)))
            out.append(_decal(ft, (x, y + 0.14, cz - 0.52), (1.0, 0.2)))
            out.append(_decal(ipa, (x, y - 0.16, cz - 0.52), (0.9, 0.08)))
    fx_, fz = FLOOD
    out.append(_beam((fx_, 0, fz), (fx_, 7.5, fz), 0.22, STEEL_D))
    out.append(box(1.2, 0.6, 0.4, STEEL_D, center=(fx_, 7.6, fz + 0.1)))
    out.append(box(1.0, 0.4, 0.06, (255, 246, 214), center=(fx_, 7.6, fz + 0.32), emissive=True))
    for i in range(8):
        x = -14.0 + i * 2.6
        out.append(box(1.2, 0.8, 0.6, tex("concrete", like=(96, 94, 88)), center=(x, 0.4, -4.6 - (i % 2) * 0.1)))
    return out


def checkpoint(surface, t):
    if _S["parts"].get("tanker") is None:
        m = _tanker_local()
        _S["parts"]["tanker"] = _Part(m.verts, _faces(m))
    tank = _S["parts"]["tanker"]
    lift = _k(t, 2400, 1700)
    tx = -40.0 + 31.0 * _k(t, 0, 3000) + max(0.0, t - 4300) * 0.006
    u = _k(t, 900, 6200)
    eye = _mix((3.2, 1.7, -10.5), (-2.0, 2.6, -15.0), u)
    tgt = _mix((0.2, 1.4, -4.8), (0.0, 1.6, 0.0), u)
    fov = 34 + 12 * u
    lights = [{"pos": (FLOOD[0], 7.4, FLOOD[1] + 0.4), "color": (255, 240, 210), "intensity": 1.4,
               "range": 18.0, "kind": "spot", "dir": (-0.3, -0.85, 0.42), "cone": 0.75},
              {"pos": (BOOTH[0], 1.7, BOOTH[1] - 1.6), "color": (255, 180, 100), "intensity": 0.8,
               "range": 4.0},
              {"pos": (tx + 6.4, 1.2, 0.0), "color": (255, 236, 190), "intensity": 1.2, "range": 16.0,
               "kind": "spot", "dir": (1.0, -0.1, 0.0), "cone": 0.86}]
    r, buf = _stage("checkpoint", "night", t, eye, tgt, fov, _checkpoint_static, lights,
                    hh=0.012, seed=41)
    tank.put(r, dx=tx)
    r.add_blob_shadow((tx, 0.13, 0.0), 6.0, 1.5, 0.6)
    for z in (-0.85, 0.85):
        r.add_sprite((tx + 6.25, 1.1, z), _fx.glow((255, 236, 180), 0.7, t, core=(255, 250, 225),
                                                    intensity=0.8), layer=LAY)
    arm = Mesh()
    for i in range(8):
        col = (196, 40, 34) if i % 2 == 0 else (220, 220, 214)
        arm.add(box(0.14, 0.14, 1.0, col, center=(0, 0, 0.5 + i)))
    _w.add(r, _place(arm, BAR_PIVOT, mat=rot_x(-82.0 * lift)))
    r.add_sprite((FLOOD[0], 7.55, FLOOD[1] + 0.4), _fx.glow((255, 244, 214), 1.6, t, intensity=0.9),
                 layer=LAY)
    r.add_sprite((FLOOD[0] - 1.5, 3.6, FLOOD[1] + 2.0),
                 _fx.light_shaft((255, 240, 210), height_m=7.0, top_m=0.6, bot_m=4.0, t=t, seed=4,
                                 intensity=0.12), layer=LAY)
    me = (0.35, 0.0, -4.85)
    face = _w.yaw_to(me, (max(-12.0, min(12.0, tx)), 0.0, 0.0))
    _w.actor(r, ("ally", "krap"), F.stand_pose(**dict(_ready())), me, face, t, seed=42, amp=0.4,
             rifle_on=True)
    me2 = (BOOTH[0] + 1.5, 0.0, BOOTH[1] - 1.4)
    _w.actor(r, ("ally", "krap"), F.stand_pose(**dict(_ready())), me2,
             _w.yaw_to(me2, (tx, 0.0, 0.0)), t, seed=43, amp=0.4, rifle_on=True)
    _m5.rain3d(r, t, seed=41, n_near=40, n_far=110, ground=0.0, splashes=6,
               surface=lambda x, z: 0.0)
    _finish(surface, r, buf, t, 41)


def _ready():
    from engine3d.rig import POSES
    return POSES["ready"]


# ── 7. the arrival ──────────────────────────────────────────────────────────
ME = (0.6, 0.0, -1.6)
VAN_X = -7.4
STREET_LAMPS = (-16.0, 10.0, 28.0)


def _arrival_static():
    out = []
    out.append(quad_xz(-800, -800, 800, 800, -0.01, (22, 22, 26), layer=0, seg=40.0))
    out.append(quad_xz(-120, -30, 120, 260, 0.0, tex("pavement", like=(30, 30, 34)), seg=6.0))
    out.append(box(240.0, 0.16, 0.3, (70, 70, 74), center=(0, 0.08, -3.2)))
    out.append(quad_xz(-120, -3.35, 120, 6.0, 0.01, (18, 18, 22), seg=6.0, layer=1))
    for x in STREET_LAMPS:
        out.append(_beam((x, 0, -3.6), (x, 6.0, -3.6), 0.18, STEEL_D))
        out.append(_beam((x, 5.9, -3.6), (x, 5.9, -2.2), 0.1, STEEL_D))
        out.append(box(0.5, 0.1, 0.3, (255, 214, 150), center=(x, 5.82, -2.1), emissive=True))
    out.append(_shacks(13, -70, 70, 26, 70, lit=0.45))
    out.append(_place(_shacks(14, -150, 150, -10, 10, lit=0.4), (-40.0, 0.0, 0.0), -90.0))
    side, _sb = _towers(45, -150, 150, -150, -70, hmin=14.0, hmax=30.0, n=10, crane=False)
    out += side
    tw, _b = _towers(44, 150, 210, -120, 120, n=10)
    out += tw
    out.append(box(0.7, 0.42, 0.34, (40, 46, 40), center=(ME[0] - 0.55, 0.21, ME[2] + 0.2)))
    return out


def arrival(surface, t):
    van = _van_rig()
    u = _k(t, 0, 9500)
    a = _mix((0.0,), (1.0,), u)[0]
    rad = 5.4 - 1.6 * a
    ang = math.radians(172 - 112 * a)
    eye = (ME[0] + math.sin(ang) * rad, 1.15 + 0.4 * a, ME[2] + math.cos(ang) * rad)
    tgt = _mix((ME[0] - 0.3, 1.8, ME[2] + 5.0), (ME[0] - 1.0, 1.5, ME[2]), u)
    lights = [{"pos": (VAN_X + _HEAD[0] + 0.1, _HEAD[1], 0.0), "color": (255, 240, 190),
               "intensity": 1.4, "range": 16.0, "kind": "spot", "dir": (1.0, -0.1, -0.15),
               "cone": 0.86}]
    for x in STREET_LAMPS:
        lights.append({"pos": (x, 5.6, -2.1), "color": (255, 182, 104), "intensity": 1.1,
                       "range": 10.0})
    r, buf = _stage("arrival", "night_city", t, eye, tgt, 44, _arrival_static, lights,
                    hh=0.015, seed=51)
    van["body"].put(r, dx=VAN_X)
    for g in _WHEELS:
        van[g].put(r, dx=VAN_X)
    r.add_blob_shadow((VAN_X, 0.02, 0.0), 3.7, 1.5, 0.7)
    for z in (-0.8, 0.8):
        r.add_sprite((VAN_X + _HEAD[0] + 0.06, _HEAD[1], z),
                     _fx.glow((255, 236, 180), 1.0, t, core=(255, 250, 225), intensity=0.9), layer=LAY)
        r.add_sprite((VAN_X + _TAIL[0] - 0.05, _TAIL[1], z * 1.1),
                     _fx.glow((255, 40, 30), 0.8, t, intensity=0.8), layer=LAY)
    r.add_sprite((VAN_X + 8.0, 0.02, 0.0),
                 _m5.wet_reflection((255, 230, 180), t, seed=5, length_m=4.0, width_m=1.0,
                                    intensity=0.35), layer=2)
    for i, x in enumerate(STREET_LAMPS):
        r.add_sprite((x, 5.82, -2.1), _fx.sodium_lamp(t, seed=i, radius_m=2.4), layer=LAY)
        r.add_sprite((x, 0.02, -2.1), _m5.wet_reflection((255, 178, 100), t, seed=i, length_m=3.2,
                                                          width_m=0.5, intensity=0.4), layer=2)
    _tw, beacons = _towers(44, 150, 210, -120, 120, n=10)
    _beacons(r, t, beacons)
    pose = F.stand_pose(head_p=-6 + 4 * _k(t, 5000, 2500), head_y=0)
    _w.actor(r, ("biribel", "krap"), pose, ME, 0.0, t, seed=52, amp=0.5, expression="neutral")
    _m5.rain3d(r, t, seed=51, n_near=70, n_far=150, ground=0.0, splashes=10,
               surface=lambda x, z: 0.0)
    _finish(surface, r, buf, t, 51)


SCENES = {
    "intro_ocean": ocean,
    "intro_city": city,
    "intro_poster": poster,
    "intro_graffiti": graffiti,
    "intro_convoy": convoy,
    "intro_checkpoint": checkpoint,
    "intro_arrival": arrival,
}


def prepare():
    """Warm the van rig and the pixel decals before the shot clock starts."""
    _van_rig()
    _surf("poster0", lambda: _poster_surf(False, 1))
    _surf("mag", _mag_surf)
    return True
