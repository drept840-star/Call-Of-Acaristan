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
    "dusk_sea": dict(fog=(168, 98, 66), fog_start=72.0, fog_end=480.0,
                     light=dict(direction=(0.25, 0.24, 0.94), ambient=0.48, diffuse=0.58,
                                sky=0.12, tint=(1.0, 0.76, 0.58)),
                     top=(28, 26, 48), bot=(212, 118, 66), sodium=(118, 56, 28),
                     mist=(126, 74, 52), clouds=3, stars=0),
    "city": dict(fog=(54, 38, 46), fog_start=45.0, fog_end=340.0,
                 light=dict(direction=(0.45, 0.42, 0.78), ambient=0.46, diffuse=0.44,
                            sky=0.12, tint=(0.96, 0.78, 0.72)),
                 top=(12, 14, 30), bot=(132, 66, 52), sodium=(104, 50, 28),
                 mist=(66, 44, 48), clouds=3, stars=18),
    "steppe": dict(fog=(170, 126, 92), fog_start=55.0, fog_end=340.0,
                   light=dict(direction=(-0.45, 0.55, -0.70), ambient=0.58, diffuse=0.64,
                              sky=0.12, tint=(1.0, 0.84, 0.66)),
                   top=(62, 68, 96), bot=(228, 156, 102), sodium=(128, 76, 40),
                   mist=(158, 118, 86), clouds=0, stars=0),
    "night": dict(fog=(11, 13, 20), fog_start=20.0, fog_end=150.0,
                  light=dict(direction=(-0.3, 0.8, -0.5), ambient=0.50, diffuse=0.28,
                             sky=0.08, tint=(0.78, 0.88, 1.08)),
                  top=(5, 7, 14), bot=(28, 22, 26), sodium=(40, 24, 18),
                  mist=(22, 24, 32), clouds=2, stars=0),
    "night_city": dict(fog=(14, 15, 24), fog_start=34.0, fog_end=270.0,
                       light=dict(direction=(-0.3, 0.8, -0.5), ambient=0.50, diffuse=0.28,
                                  sky=0.08, tint=(0.78, 0.88, 1.08)),
                       top=(6, 9, 17), bot=(48, 30, 34), sodium=(76, 42, 24),
                       mist=(28, 26, 36), clouds=2, stars=0),
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
    """Stepped glass/panel towers with clustered lit window bands -> (meshes, beacon points)."""
    rng = random.Random(seed)
    out, beacons = [], []
    xs = sorted(rng.uniform(x0, x1) for _ in range(n))
    for i, x in enumerate(xs):
        w = rng.uniform(14.0, 24.0)
        d = rng.uniform(12.0, 18.0)
        h = rng.uniform(hmin, hmax)
        z = rng.uniform(z0, z1)
        col = rng.choice(((38, 44, 56), (48, 52, 62), (34, 40, 52), (56, 54, 60)))
        m = Mesh()
        # Main shaft + architectural crown setback
        h_main = h * 0.84
        h_top = h - h_main
        m.add(box(w, h_main, d, tex("concrete", like=col), center=(x, h_main / 2, z), seg=36.0,
                  cols={"top": tuple(min(255, c + 8) for c in col)}))
        m.add(box(w * 0.78, h_top, d * 0.82, tuple(min(255, c + 6) for c in col),
                  center=(x, h_main + h_top / 2, z), seg=24.0))
        m.add(box(w * 0.42, 4.2, d * 0.42, STEEL_D, center=(x, h + 2.1, z)))
        # Rooftop spire on tall towers
        if h > 95.0:
            m.add(_beam((x, h + 4.2, z), (x, h + 16.0, z), 0.35, STEEL_D))
        zf = z - d / 2 - 0.06
        cold = rng.random() < 0.55
        # Clustered office strips (horizontal mullions feel real, not noisy dots)
        y = 5.0
        while y < h_main - 4.0:
            floor_lit = rng.random() < 0.48
            band_c = WIN_COLD if (cold ^ (rng.random() < 0.18)) else WIN_WARM
            xx = x - w / 2 + 1.4
            while xx < x + w / 2 - 2.4:
                if floor_lit and rng.random() < 0.62:
                    k = rng.uniform(0.45, 0.92)
                    seg_w = rng.uniform(1.6, 2.5)
                    _win(m, xx, min(x + w / 2 - 1.2, xx + seg_w), y, y + 1.5, zf,
                         tuple(int(v * k) for v in band_c))
                xx += 3.2
            y += 4.2
        out.append(m)
        beacons.append((x, h + (16.4 if h > 95.0 else 4.6), z))
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
SEA_Z = (-10, -7, -4, -1, 2, 5, 8, 12, 16, 21, 27, 34, 43, 54, 68, 86, 108, 136, 175, 225, 290, 380, 490)
SEA_N = 64
SUN = (0.18, 0.055, 1.0)
GLINT = (232, 148, 86)
GLINT_MID = (128, 76, 56)
RIGS = ((-58.0, 150.0, "live", 0.0), (24.0, 112.0, "burn", 0.0), (84.0, 236.0, "live", 0.0),
        (-20.0, 290.0, "live", 0.0), (-30.0, 72.0, "dead", 11.0), (52.0, 64.0, "stump", 0.0))
BOAT = (-7.5, 21.0)


def _wave(x, z, t):
    s = t * 0.001
    return (0.28 * math.sin(x * 0.19 + z * 0.05 + s * 1.1)
            + 0.20 * math.sin(z * 0.15 - x * 0.07 - s * 1.4)
            + 0.08 * math.sin((x + z) * 0.48 + s * 2.2))


def _sea(r, t):
    """Smooth dusk ocean swell with continuous Fresnel/sun glitter path."""
    cam = r.cam
    sun = v_norm(SUN)
    rows = []
    for z in SEA_Z:
        half = 42.0 + max(0.0, z) * 0.95
        amp = 1.0 / (1.0 + max(0.0, z) / 60.0)
        rows.append([((2.0 * j / SEA_N - 1.0) * half,
                      amp * _wave((2.0 * j / SEA_N - 1.0) * half, z, t), float(z))
                     for j in range(SEA_N + 1)])
    verts = [p for row in rows for p in row]
    faces = []
    n1 = SEA_N + 1
    n_rows = len(rows) - 1
    for i in range(n_rows):
        hz = i / float(n_rows)
        # Near water: deep slate-teal; far water: picks up warm dusk horizon tint
        base = (
            int(22 + 56 * hz * hz),
            int(34 + 26 * hz * hz),
            int(46 + 4 * hz),
        )
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
                # Smooth continuous sunset sheen + soft specular core (never harsh binary emissive)
                sheen = max(0.0, min(1.0, (sp - 0.85) / 0.14)) ** 2
                spark = max(0.0, min(1.0, (sp - 0.960) / 0.038)) ** 2.2
                col = tuple(
                    min(255, int(base[k]
                                 + (GLINT_MID[k] - base[k]) * sheen * 0.68
                                 + (GLINT[k] - GLINT_MID[k]) * spark * 0.82))
                    for k in range(3)
                )
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
    out = [quad_xz(-900, -40, 900, 900, 0.0, tex("m7_dirt", like=(36, 30, 30)), seg=40.0)]
    # Keep wide foreground clearing around camera & hero pumpjack so no shack blocks the left third
    out.append(_shacks(7, -44, 44, -2, 48, keep_out=((-22.0, 14.0, -14.0, 22.0),)))
    out.append(_shacks(8, -110, 110, 50, 150, lit=0.42))
    mid, _mb = _towers(22, 118, 146, -150, 150, hmin=18.0, hmax=38.0, n=14, crane=False)
    out += mid
    tw, _b = _towers(21, 150, 220, -110, 110)
    out += tw
    out.append(_beam((150, 0, 280), (150, 46, 280), 2.4, STEEL_D))
    # Industrial oil pipeline & sodium lamp beside the hero pumpjack
    out.append(box(2.4, 1.0, 6.0, STEEL_D, center=(8.0, 0.5, 5.0)))
    out.append(_beam((6.5, 0, 6.0), (6.5, 5.5, 6.0), 0.18, STEEL_D))
    out.append(_beam((6.5, 5.4, 6.0), (7.7, 5.4, 6.0), 0.1, STEEL_D))
    out.append(box(0.6, 0.12, 0.3, (255, 214, 150), center=(7.8, 5.3, 6.0), emissive=True))
    out.append(_beam((-5.4, 0, 7.6), (-5.4, 5.2, 7.6), 0.16, STEEL_D))
    out.append(_beam((-5.4, 5.1, 7.6), (-4.2, 5.1, 7.6), 0.09, STEEL_D))
    out.append(box(0.55, 0.12, 0.28, (255, 206, 138), center=(-4.1, 5.0, 7.6), emissive=True))
    for i in range(4):
        x = -14.0 + i * 9.0
        out.append(_beam((x, 0, -4.5), (x, 6.0, -4.5), 0.18, (38, 32, 30)))
    return out


def city(surface, t):
    u = _k(t, 300, 9000)
    eye = _mix((-6.2, 2.5, -2.8), (-11.0, 16.5, -13.5), u)
    tgt = _mix((2.4, 3.5, 10.5), (6.0, 38.0, 180.0), _k(t, 600, 8600))
    fov = 45 + 7 * u
    lights = [{"pos": (7.8, 5.2, 6.0), "color": (255, 184, 104), "intensity": 1.45, "range": 14.0},
              {"pos": (-4.1, 4.9, 7.6), "color": (255, 174, 96), "intensity": 1.35, "range": 13.0},
              {"pos": (2.5, 3.8, 7.2), "color": (255, 196, 124), "intensity": 0.85, "range": 10.0}]
    r, buf = _stage("city", "city", t, eye, tgt, fov, _city_static, lights, hh=0.02, seed=7)
    _w.add(r, _pumpjack(PUMP, t))
    _w.add(r, _pumpjack((-54.0, 0.0, 68.0), t + 900, s=0.9, speed=0.9, yaw=20))
    _w.add(r, _pumpjack((44.0, 0.0, 62.0), t + 400, s=0.9, speed=1.1, yaw=-15))
    r.add_sprite((7.8, 5.3, 6.0), _fx.sodium_lamp(t, seed=2, radius_m=2.0), layer=LAY)
    r.add_sprite((-4.1, 5.0, 7.6), _fx.sodium_lamp(t, seed=5, radius_m=1.9), layer=LAY)
    _tw, beacons = _towers(21, 150, 220, -110, 110)
    _beacons(r, t, beacons)
    F.fire(r, (150.0, 47.0, 280.0), t, seed=9, size=3.0, smoky=True)
    _finish(surface, r, buf, t, 7)


# ── 3. the IPA poster ───────────────────────────────────────────────────────
WALL_Z = 4.0
LAMP = (-2.6, 5.6, WALL_Z - 0.7)


def _poster_surf(defaced=False, seed=0):
    """High-detail IPA propaganda poster using canonical President portrait."""
    from engine.anim import draw_character as _fk_draw
    w, h = 96, 128
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    s.fill((210, 190, 152, 255))
    # Subtle propaganda sunburst behind portrait
    cx, cy = w // 2, 46
    for i in range(12):
        a0 = i * (math.pi / 6.0)
        a1 = a0 + math.pi / 12.0
        p1 = (cx + int(math.cos(a0) * 60), cy + int(math.sin(a0) * 60))
        p2 = (cx + int(math.cos(a1) * 60), cy + int(math.sin(a1) * 60))
        pygame.draw.polygon(s, (194, 170, 132), [(cx, cy), p1, p2])
    # Top crimson state banner
    pygame.draw.rect(s, (154, 30, 28), (0, 0, w, 15))
    pygame.draw.rect(s, (214, 178, 88), (0, 15, w, 2))
    big, small = _pix("R7"), _pix("R5")
    ipa = _T("engine.ipa")
    small.draw(s, ipa, ((w - small.size(ipa)[0]) // 2, 4), (242, 226, 192))
    # Portrait inset box with canonical Retardovici character art (head + shoulders cleanly framed)
    px, py, pw, ph = 14, 20, w - 28, 58
    port = pygame.Surface((pw, ph))
    port.fill((174, 150, 118))
    for i in range(0, ph, 4):
        pygame.draw.line(port, (162, 138, 108), (0, i), (pw, i), 1)
    # figure_kit draws ~265px tall at scale=1.0 from feet y upward; scale=0.62 -> ~164px tall,
    # so placing feet at y = 172 puts head top around y = 8 and shoulders cleanly filling the frame.
    _fk_draw(port, "president", pw // 2, 174, 0.62, facing_right=True)
    s.blit(port, (px, py))
    pygame.draw.rect(s, (148, 30, 28), (px - 2, py - 2, pw + 4, ph + 4), 2)
    pygame.draw.rect(s, (46, 36, 30), (px, py, pw, ph), 1)
    # Bottom typography band
    pygame.draw.rect(s, (206, 186, 148), (4, 81, w - 8, 43))
    pygame.draw.line(s, (154, 30, 28), (10, 83), (w - 10, 83), 2)
    title = _T("engine.stability")
    sub = [ln.strip() for ln in _T("engine.prosperity_acaristan").split("-") if ln.strip()]
    big.draw(s, title, ((w - big.size(title)[0]) // 2, 89), (34, 24, 20))
    for i, line in enumerate(sub):
        small.draw(s, line, ((w - small.size(line)[0]) // 2, 102 + i * 9), (74, 48, 38))
    pygame.draw.rect(s, (56, 44, 36), (0, 0, w, h), 2)
    # Pasted paper weathering & torn edge
    rng = random.Random(seed)
    for _ in range(w * h // 16):
        x, y = rng.randrange(w), rng.randrange(h)
        c = s.get_at((x, y))
        k = rng.choice((0.86, 0.92, 1.06))
        s.set_at((x, y), (min(255, int(c[0] * k)), min(255, int(c[1] * k)), min(255, int(c[2] * k)), 255))
    for _ in range(3):
        x0 = rng.choice((0, w - 1))
        y0 = rng.randrange(h // 2, h - 10)
        pygame.draw.polygon(s, (0, 0, 0, 0), [(x0, y0), (x0, y0 + rng.randint(6, 14)),
                                              (abs(x0 - rng.randint(4, 10)), y0 + 5)])
    if defaced:
        ink = (18, 16, 16)
        pygame.draw.circle(s, ink, (w // 2, 48), 20, 3)
        pygame.draw.line(s, ink, (8, 18), (w - 8, h - 10), 3)
        pygame.draw.line(s, ink, (w - 8, 18), (8, h - 10), 3)
        for _ in range(8):
            x = rng.randrange(8, w - 8)
            y = rng.randrange(18, h - 14)
            pygame.draw.line(s, ink, (x, y), (x, y + rng.randint(5, 14)), 2)
    return s


def _poster_static():
    out = []
    out.append(box(44.0, 9.0, 0.8, tex("brick", like=(104, 66, 54)), center=(0, 4.5, WALL_Z + 0.4),
                   seg=6.0))
    out.append(box(44.0, 0.4, 1.0, (54, 50, 48), center=(0, 9.1, WALL_Z + 0.3)))
    # Horizontal stone plinth & conduit pipes along the wet brick wall
    out.append(box(44.0, 0.72, 0.14, (58, 56, 54), center=(0, 0.36, WALL_Z - 0.04), seg=8.0))
    out.append(box(44.0, 0.10, 0.16, (72, 68, 64), center=(0, 0.75, WALL_Z - 0.05), seg=8.0))
    out.append(_beam((-20.0, 4.7, WALL_Z - 0.12), (20.0, 4.7, WALL_Z - 0.12), 0.10, (46, 50, 54)))
    out.append(quad_xz(-30, -14, 30, WALL_Z, 0.0, tex("pavement", like=(44, 44, 48)), seg=3.0))
    out.append(box(60.0, 0.16, 0.3, (70, 70, 74), center=(0, 0.08, -2.6)))
    out.append(quad_xz(-30, -14, 30, -2.75, -0.02, (22, 22, 26), seg=6.0))
    out.append(_decal(_surf("poster0", lambda: _poster_surf(False, 1)), (0.0, 2.75, WALL_Z - 0.02),
                      (2.3, 3.1), q=6))
    for i, x in enumerate((-6.5, 6.4, 12.0, -12.8)):
        key = "poster%d" % (i + 1)
        surf = _surf(key, lambda i=i: _poster_surf(i % 2 == 0, 10 + i))
        out.append(_decal(surf, (x, 2.6 + 0.12 * (i % 2), WALL_Z - 0.02), (2.0, 2.7), q=8))
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
BARREL = (1.55, 0.25)


def _mag_surf():
    """High-contrast white-backed stenciled MAG mask + glowing crimson eyes + tag."""
    w, h = 92, 112
    s = pygame.Surface((w, h), pygame.SRCALPHA)
    rng = random.Random(23)
    ink = (5, 5, 7, 255)
    chalk = (224, 218, 206, 255)
    red = (232, 34, 30, 255)
    cx, cy, k = w // 2, 44, 3.2
    pts = [(0, -8), (-6, -12), (-10, -2), (-8, 8), (0, 12), (8, 8), (10, -2), (6, -12)]
    poly_out = [(cx + int(px * (k + 0.35)), cy + int(py * (k + 0.35))) for px, py in pts]
    poly = [(cx + int(px * k), cy + int(py * k)) for px, py in pts]
    # Rough white spray halo behind the black mask so it pops off dark ribbed steel
    for _ in range(320):
        a = rng.uniform(0, 2 * math.pi)
        rr = rng.uniform(28, 42)
        x, y = int(cx + math.cos(a) * rr), int(cy + math.sin(a) * rr * 1.05)
        if 0 <= x < w and 0 <= y < h:
            s.set_at((x, y), chalk)
    pygame.draw.polygon(s, chalk, poly_out)
    pygame.draw.polygon(s, ink, poly)
    # Angular mask brow/jaw slits + bright red MAG eyes
    for ex in (-3.2, 3.2):
        ec = (cx + int(ex * k), cy + int(-1.8 * k))
        pygame.draw.circle(s, red, ec, 5)
        pygame.draw.circle(s, (255, 130, 96, 255), ec, 2)
    # Stenciled teeth/mouth bar
    pygame.draw.rect(s, chalk, (cx - 10, cy + 16, 20, 4))
    for tx in (-6, -1, 4):
        pygame.draw.line(s, ink, (cx + tx, cy + 15), (cx + tx, cy + 21), 2)
    # Paint drips
    for _ in range(11):
        x = rng.randint(cx - 24, cx + 24)
        y0 = cy + rng.randint(14, 30)
        pygame.draw.line(s, ink, (x, y0), (x, y0 + rng.randint(6, 18)), 2)
    # High-contrast "MARU SEES YOU" stencil banner
    small = _pix("R5")
    tag = _T("engine.maru_sees_you")
    tw, th = small.size(tag)
    tx0 = (w - tw) // 2
    pygame.draw.rect(s, (20, 18, 18, 235), (tx0 - 4, 88, tw + 8, th + 6))
    small.draw(s, tag, (tx0, 91), (242, 230, 212))
    for _ in range(6):
        x = rng.randint(tx0, tx0 + tw)
        pygame.draw.line(s, red, (x, 96), (x, 96 + rng.randint(4, 12)), 1)
    return s


def _graffiti_static():
    out = []
    out.append(quad_xz(-40, -20, 40, 30, 0.0, tex("m7_dirt", like=(40, 38, 36)), seg=4.0))
    # Weathered steel-grey hero container so the black/white/red MAG stencil pops cleanly
    rib_hero = tex("metal_rib", like=(112, 118, 124))
    rib_rust = tex("metal_rib", like=(104, 52, 38))
    rib_blue = tex("metal_rib", like=(46, 66, 78))
    out.append(box(12.2, 2.6, 2.4, rib_hero, center=(-1.0, 1.3, CONT_Z + 1.2)))
    out.append(box(12.2, 2.6, 2.4, rib_rust, center=(-7.5, 3.9, CONT_Z + 1.6)))
    out.append(box(12.2, 2.6, 2.4, rib_blue, center=(11.6, 1.3, CONT_Z + 1.5)))
    out.append(box(12.2, 2.6, 2.4, tex("rust", like=(92, 70, 50)), center=(11.0, 3.9, CONT_Z + 1.9)))
    for x in (-7.1, 5.1):
        out.append(box(0.14, 2.6, 0.12, (58, 62, 66), center=(x, 1.3, CONT_Z - 0.02)))
    out.append(_decal(_surf("mag", _mag_surf), (-0.75, 1.44, CONT_Z - 0.04), (2.2, 2.5), q=6))
    # Ribbed burning oil drum clearly visible in right foreground
    bx, bz = BARREL
    out.append(_cyl(bx, bz, 0.34, 0.0, 0.94, tex("rust", like=(96, 52, 36)), n=12))
    for hy in (0.04, 0.34, 0.64, 0.92):
        out.append(_cyl(bx, bz, 0.365, hy - 0.025, hy + 0.025, (64, 38, 28), n=12))
    # Glowing ember holes near the top of the drum
    for a in (-0.9, -0.3, 0.3, 0.9):
        ex = bx + math.sin(a) * 0.345
        ez = bz - math.cos(a) * 0.345
        out.append(box(0.06, 0.06, 0.06, (255, 152, 48), center=(ex, 0.78, ez), emissive=True))
    for i, (x, z) in enumerate(((-3.6, -0.8), (-4.2, -0.2), (-3.9, -0.5))):
        out.append(_place(_cyl(0, 0, 0.42, 0.0, 0.24, (22, 22, 25), n=12), (x, i * 0.24, z)))
    for i in range(6):
        x = 5.4 + i * 2.4
        out.append(_beam((x, 0, -1.8), (x, 2.2, -1.8), 0.08, (60, 62, 66)))
    out.append(box(3.6, 1.2, 1.7, (40, 38, 36), center=(-9.0, 0.6, -0.6)))
    out.append(box(2.0, 0.7, 1.6, (30, 30, 32), center=(-9.4, 1.5, -0.6)))
    return out


def graffiti(surface, t):
    u = _k(t, 0, 9500)
    eye = _mix((-3.4, 1.48, -5.0), (-0.85, 1.50, -2.55), u)
    tgt = _mix((-0.05, 1.38, CONT_Z), (-0.25, 1.44, CONT_Z), u)
    fl = 1.0 + 0.22 * math.sin(t * 0.021) + 0.14 * math.sin(t * 0.047 + 1.3)
    lights = [
        {"pos": (BARREL[0], 1.45, BARREL[1]), "color": (255, 128, 46),
         "intensity": 1.35 * fl, "range": 7.5},
        {"pos": (-1.4, 2.6, CONT_Z - 2.4), "color": (124, 146, 184),
         "intensity": 0.35, "range": 7.0},
    ]
    r, buf = _stage("graffiti", "night", t, eye, tgt, 46, _graffiti_static, lights, hh=0.018, seed=23)
    F.fire(r, (BARREL[0], 0.96, BARREL[1]), t, seed=23, size=0.72, smoky=True)
    r.add_sprite((BARREL[0], 1.15, BARREL[1]),
                 _fx.glow((255, 136, 48), 1.4, t, flicker=0.14, seed=23, intensity=0.65), layer=LAY)
    for i in range(14):
        age = ((t / 1500.0) + i / 14.0) % 1.0
        p = (BARREL[0] + math.sin(i * 2.3 + t * 0.0014) * 0.42 * age, 1.15 + age * 2.8,
             BARREL[1] + math.cos(i * 1.7) * 0.32 * age)
        r.add_sprite(p, _fx.glow((255, 152, 54), 0.09, t, intensity=0.95 * (1 - age)), layer=LAY)
    for i in range(5):
        x = 5.4 + i * 2.4
        r.add_line3d((x, 2.1, -1.8), (x + 2.4, 2.1, -1.8), (70, 72, 76), 1, layer=2)
        r.add_line3d((x, 1.2, -1.8), (x + 2.4, 1.2, -1.8), (70, 72, 76), 1, layer=2)
    _finish(surface, r, buf, t, 23)


# ── 5. the convoy ───────────────────────────────────────────────────────────
VAN_SPEED = 11.0
POLE_X = tuple(-150.0 + i * 32.0 for i in range(11))


def _steppe_static():
    out = []
    out.append(quad_xz(-320, -80, 320, 420, 0.0, tex("m7_stubble", like=(118, 96, 62)), seg=26.0))
    # Gravel roadside verges + paved highway
    out.append(quad_xz(-320, -5.2, 320, 5.2, 0.03, (96, 82, 58), seg=24.0, layer=0))
    out.append(box(640.0, 0.12, 7.0, tex("pavement", like=(54, 52, 54)), center=(0, 0.06, 0), seg=20.0))
    for k in range(-50, 50):
        out.append(quad_xz(k * 6.0, -0.08, k * 6.0 + 2.6, 0.08, 0.125, (186, 170, 112), layer=1))
    # Layered distant mountain/steppe ridges
    rng = random.Random(5)
    for zr, hmax, col in ((185.0, 26.0, (118, 90, 74)), (275.0, 44.0, (132, 102, 90))):
        xs = [-420 + i * 30 for i in range(29)]
        hs = [rng.uniform(hmax * 0.35, hmax) for _ in xs]
        m = Mesh()
        for i in range(len(xs) - 1):
            m.face([(xs[i], 0, zr), (xs[i], hs[i], zr + 8), (xs[i + 1], hs[i + 1], zr + 8),
                    (xs[i + 1], 0, zr)], col, 1, False, False)
        out.append(m)
    # Roadside weathered fence posts & low steppe scrub bushes for depth
    rng2 = random.Random(19)
    for fx in range(-96, 104, 8):
        out.append(_beam((fx, 0.0, 5.4), (fx, 1.05, 5.4), 0.10, (68, 54, 42)))
    for _ in range(38):
        sx = rng2.uniform(-80.0, 90.0)
        sz = rng2.choice((rng2.uniform(-11.0, -5.8), rng2.uniform(5.8, 22.0)))
        sh = rng2.uniform(0.35, 0.72)
        out.append(box(rng2.uniform(0.5, 1.0), sh, rng2.uniform(0.5, 1.0),
                       rng2.choice(((88, 76, 46), (76, 68, 44), (98, 82, 52))),
                       center=(sx, sh * 0.45, sz)))
    for x in POLE_X:
        out.append(_beam((x, 0, -7.8), (x, 7.0, -7.8), 0.22, (60, 48, 40)))
        out.append(_beam((x, 6.6, -8.4), (x, 6.6, -7.2), 0.12, (60, 48, 40)))
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
    lead = -10.0 + VAN_SPEED * t * 0.001
    xs = [lead - i * 14.5 for i in range(3)]
    u = _k(t, 0, 9000)
    eye = _mix((-7.8, 1.42, -11.4), (-2.2, 1.65, -12.8), u)
    tx = max(-12.0, min(18.0, lead * 0.55 + 1.5))
    tgt = (tx, 1.65, 0.0)
    # Warm sun-side fill lights keep the KRAP van armor & insignia readable (never flat black)
    lights = [
        {"pos": (tx - 2.0, 4.2, -9.0), "color": (255, 206, 152), "intensity": 0.95, "range": 28.0},
    ]
    for x in xs:
        lights.append({"pos": (x + _HEAD[0] + 0.1, _HEAD[1], 0.0), "color": (255, 236, 190),
                       "intensity": 1.0, "range": 15.0, "kind": "spot", "dir": (1.0, -0.12, 0.0),
                       "cone": 0.86})
    r, buf = _stage("convoy", "steppe", t, eye, tgt, 44, _steppe_static, lights, hh=0.018, seed=31,
                    sun=(-0.75, 0.06, 0.55))
    for i, x in enumerate(xs):
        _put_van(r, van, x, t, bob_seed=i * 1.7)
        r.add_blob_shadow((x, 0.13, 0.0), 3.7, 1.5, 0.62)
        on = (t // 260 + i) % 2 == 0
        for z, col in ((-0.45, (60, 124, 255)), (0.45, (255, 54, 42))):
            if (z < 0) == on:
                r.add_sprite((x + 0.3, 2.62, z), _fx.glow(col, 0.72, t, intensity=0.95), layer=LAY)
        for z in (-0.8, 0.8):
            r.add_sprite((x + _HEAD[0] + 0.06, _HEAD[1], z),
                         _fx.glow((255, 238, 186), 0.78, t, core=(255, 252, 228), intensity=0.78),
                         layer=LAY)
        r.add_sprite((x - 4.2, 0.65, 0.0),
                     _fx.powder(t, seed=i, spread_m=3.8, intensity=0.46, col=(184, 148, 104), puffs=12),
                     layer=LAY)
    # Staggered roadside villagers with subtle varied postures
    watchers = (
        ("civilian", (-2.2, 0.0, -6.3), 21, {"head_p": -4, "spine": 3}),
        ("hungry_kid", (-1.2, 0.0, -5.8), 22, {"head_p": -8, "rsh_p": 12, "rel": 20}),
        ("civilian", (4.4, 0.0, -7.2), 23, {"head_p": -2, "lsh_p": 14, "lel": 34}),
        ("fisherman", (7.1, 0.0, -8.4), 24, {"head_p": -3, "spine": 5}),
    )
    for key, me, seed, extra in watchers:
        look = max(min(xs[0], me[0] + 18.0), me[0] - 18.0)
        _w.actor(r, key, F.stand_pose(**extra), me, _w.yaw_to(me, (look, 0.0, 0.0)), t, seed=seed, amp=0.5)
    for i in range(len(POLE_X) - 1):
        a, b = POLE_X[i], POLE_X[i + 1]
        for dz in (-0.5, 0.5):
            prev = (a, 6.6, -7.8 + dz)
            for s in range(1, 5):
                f = s / 4.0
                p = (a + (b - a) * f, 6.6 - math.sin(f * math.pi) * 0.7, -7.8 + dz)
                r.add_line3d(prev, p, (40, 32, 30), 1, layer=2)
                prev = p
    _finish(surface, r, buf, t, 31)


# ── 6. the checkpoint ───────────────────────────────────────────────────────
BAR_PIVOT = (-0.8, 1.05, -4.3)
BOOTH = (-5.6, -6.4)
CRATES = (4.2, -6.2)
FLOOD = (7.4, -8.4)
TANKER_WHEEL_R = 0.56
TANKER_WHEELS = (
    ("fl", 5.25, -1.16), ("fr", 5.25, 1.16),
    ("ml", 2.25, -1.16), ("mr", 2.25, 1.16),
    ("rl1", -3.15, -1.16), ("rr1", -3.15, 1.16),
    ("rl2", -4.48, -1.16), ("rr2", -4.48, 1.16),
)


def _stencil(text, col, name="R7"):
    f = _pix(name)
    w, h = f.size(text)
    s = pygame.Surface((w + 2, h + 2), pygame.SRCALPHA)
    f.draw(s, text, (1, 1), (*col, 255))
    return s


def _wheel_mesh(cx, cy, cz, r=TANKER_WHEEL_R, width=0.40, n=14):
    """Rounded multi-segment truck tire with steel rim, lug hub and tread detail."""
    m = Mesh()
    tire_col = (24, 25, 29)
    rim_col = (118, 122, 128)
    hub_col = (56, 60, 66)
    prof_t = [(math.cos(2 * math.pi * i / n) * r,
               math.sin(2 * math.pi * i / n) * r) for i in range(n)]
    prof_r = [(math.cos(2 * math.pi * i / n) * (r * 0.56),
               math.sin(2 * math.pi * i / n) * (r * 0.56)) for i in range(n)]
    prof_h = [(math.cos(2 * math.pi * i / n) * (r * 0.24),
               math.sin(2 * math.pi * i / n) * (r * 0.24)) for i in range(n)]
    m.add(prism(prof_t, width, tire_col, z0=-width * 0.5), t=(cx, cy, cz))
    m.add(prism(prof_r, width + 0.04, rim_col, z0=-(width + 0.04) * 0.5), t=(cx, cy, cz))
    m.add(prism(prof_h, width + 0.09, hub_col, z0=-(width + 0.09) * 0.5), t=(cx, cy, cz))
    # Crossed lug bar on the hub so rotation is visibly crisp in motion
    m.add(box(r * 0.92, 0.07, width + 0.06, (82, 86, 92), center=(cx, cy, cz)))
    m.add(box(0.07, r * 0.92, width + 0.06, (82, 86, 92), center=(cx, cy, cz)))
    return m


def _tanker_parts():
    """Articulated FuegoTech semi-tanker: sculpted nose cab, 16-gon domed steel
    tank, catwalk/hatches/ladder, exhaust stacks, and 8 rolling round wheels."""
    m = Mesh()
    cab_red = (138, 38, 32)
    cab_dark = (96, 26, 22)
    trim = (38, 42, 48)
    chrome = (178, 184, 192)
    glass = (32, 46, 62)

    # Heavy steel chassis rails + fifth-wheel hitch + cross-members
    for z in (-0.62, 0.62):
        m.add(box(12.2, 0.28, 0.18, STEEL_D, center=(0.3, 0.78, z)))
    m.add(box(11.8, 0.14, 1.56, (34, 36, 40), center=(0.2, 0.94, 0.0)))
    m.add(box(1.1, 0.20, 1.35, (52, 54, 60), center=(2.1, 1.06, 0.0)))

    # Sculpted tractor engine hood (x = +4.65 .. +6.42)
    m.add(box(1.85, 1.04, 1.94, cab_red, center=(5.50, 1.48, 0.0),
              cols={"top": (122, 34, 28)}))
    m.add(box(1.78, 0.12, 1.80, cab_dark, center=(5.48, 2.02, 0.0)))
    # Side engine louver vents + front wheel fenders
    for z in (-0.98, 0.98):
        m.add(box(0.95, 0.34, 0.04, trim, center=(5.55, 1.56, z)))
        m.add(box(1.45, 0.18, 0.48, cab_dark, center=(5.25, 1.18, z * 1.08)))
    # Chrome radiator grille + horizontal slats
    m.add(box(0.10, 0.88, 1.24, (24, 26, 30), center=(6.44, 1.48, 0.0)))
    for gy in (1.16, 1.32, 1.48, 1.64, 1.80):
        m.add(box(0.14, 0.045, 1.16, chrome, center=(6.46, gy, 0.0)))
    # Heavy steel front bumper with hazard accents & recessed twin headlights
    m.add(box(0.32, 0.38, 2.48, chrome, center=(6.56, 0.78, 0.0)))
    m.add(box(0.36, 0.12, 2.40, (200, 146, 44), center=(6.58, 0.68, 0.0)))
    for z in (-0.82, 0.82):
        m.add(box(0.12, 0.28, 0.42, trim, center=(6.44, 1.12, z)))
        m.add(box(0.14, 0.18, 0.32, (255, 246, 206), center=(6.48, 1.12, z), emissive=True))
        m.add(box(0.14, 0.10, 0.14, (255, 152, 42), center=(6.48, 1.32, z * 1.12), emissive=True))

    # Tractor cab body (x = +2.90 .. +4.72) + roof visor + clearance lamps
    m.add(box(1.86, 1.98, 2.34, cab_red, center=(3.82, 1.98, 0.0),
              cols={"top": (118, 32, 28)}))
    m.add(box(0.50, 0.14, 2.38, cab_dark, center=(4.86, 2.90, 0.0)))
    for z in (-0.65, 0.0, 0.65):
        m.add(box(0.10, 0.08, 0.14, (255, 168, 48), center=(4.80, 3.01, z), emissive=True))
    # Windshield (front +x) & side cab windows
    m.add(box(0.06, 0.76, 1.96, glass, center=(4.76, 2.42, 0.0)))
    m.add(box(0.09, 0.78, 0.08, trim, center=(4.77, 2.42, 0.0)))
    for z in (-1.18, 1.18):
        m.add(box(1.05, 0.68, 0.05, glass, center=(4.04, 2.40, z)))
        m.add(box(0.28, 0.06, 0.06, chrome, center=(3.78, 1.72, z * 1.01)))
        # Side wing mirrors on brackets
        m.add(box(0.06, 0.05, 0.34, trim, center=(4.56, 2.52, z * 1.12)))
        m.add(box(0.06, 0.05, 0.34, trim, center=(4.56, 2.02, z * 1.12)))
        m.add(box(0.08, 0.56, 0.20, chrome, center=(4.54, 2.27, z * 1.24)))
        # Cab entry step + saddle diesel tank
        m.add(box(0.68, 0.10, 0.24, chrome, center=(3.95, 0.62, z * 0.98)))
        m.add(box(1.32, 0.52, 0.44, (132, 136, 144), center=(2.96, 0.80, z * 0.86)))
        # Vertical chrome exhaust stacks behind cab
        m.add(_cyl(2.74, z * 0.96, 0.09, 1.05, 3.65, chrome, n=10))
        m.add(_cyl(2.74, z * 0.96, 0.13, 1.45, 2.85, (72, 76, 82), n=10))

    # Rear mudguards over drive & tandem trailer axles
    for wx in (2.25, -3.82):
        wlen = 1.45 if wx > 0 else 2.85
        for z in (-1.14, 1.14):
            m.add(box(wlen, 0.12, 0.46, trim, center=(wx, 1.22, z)))

    # 16-sided brushed-steel cylindrical tanker barrel with domed end-caps
    n_seg = 16
    r_main = 1.18
    prof_main = [(math.cos(2 * math.pi * i / n_seg) * r_main,
                  math.sin(2 * math.pi * i / n_seg) * r_main) for i in range(n_seg)]
    prof_cap = [(math.cos(2 * math.pi * i / n_seg) * (r_main * 0.84),
                 math.sin(2 * math.pi * i / n_seg) * (r_main * 0.84)) for i in range(n_seg)]
    tank_steel = tex("steel", like=(164, 168, 174))
    tank_body = prism(prof_main, 7.6, tank_steel, z0=-3.8)
    m.add(tank_body, m=rot_y(90), t=(-1.45, 2.34, 0.0))
    # Domed end-caps (front & rear)
    for ex in (-5.35, 2.45):
        m.add(prism(prof_cap, 0.24, (132, 136, 144), z0=-0.12), m=rot_y(90), t=(ex, 2.34, 0.0))
    # Structural steel reinforcement hoops + lower crimson FuegoTech livery band
    prof_hoop = [(math.cos(2 * math.pi * i / n_seg) * (r_main + 0.035),
                  math.sin(2 * math.pi * i / n_seg) * (r_main + 0.035)) for i in range(n_seg)]
    for hx in (-4.4, -2.4, -0.4, 1.6):
        m.add(prism(prof_hoop, 0.14, (96, 100, 108), z0=-0.07), m=rot_y(90), t=(hx, 2.34, 0.0))
    for z in (-1.20, 1.20):
        m.add(box(7.4, 0.28, 0.04, cab_red, center=(-1.45, 1.88, z)))
        # Side amber marker lights along the lower skirt
        for mx in (-4.8, -2.6, -0.4, 1.8):
            m.add(box(0.14, 0.08, 0.05, (255, 158, 42), center=(mx, 1.12, z * 0.94), emissive=True))
    # Top catwalk, guard rails, and 3 manhole domes
    m.add(box(7.2, 0.08, 0.72, (74, 78, 84), center=(-1.45, 3.55, 0.0)))
    for dz in (-0.36, 0.36):
        m.add(_beam((-5.0, 3.74, dz), (2.1, 3.74, dz), 0.045, chrome))
    for mx in (-3.6, -1.45, 0.7):
        m.add(_cyl(mx, 0.0, 0.28, 3.48, 3.72, (98, 102, 108), n=10))
    # Rear steel access ladder + discharge valve box + taillights
    for dz in (-0.24, 0.24):
        m.add(_beam((-5.54, 1.05, dz), (-5.54, 3.60, dz), 0.05, chrome))
    for ly in (1.35, 1.75, 2.15, 2.55, 2.95, 3.35):
        m.add(_beam((-5.54, ly, -0.24), (-5.54, ly, 0.24), 0.04, chrome))
    m.add(box(1.5, 0.44, 0.56, trim, center=(-1.1, 0.86, -0.96)))
    m.add(box(0.20, 0.28, 2.34, trim, center=(-5.56, 0.86, 0.0)))
    for z in (-0.86, 0.86):
        m.add(box(0.08, 0.16, 0.34, (242, 42, 34), center=(-5.68, 0.88, z), emissive=True))
    # Crisp FUEGOTECH stencil on the camera-facing flank
    m.add(_decal(_surf("ft", lambda: _stencil(_T("engine.fuegotech"), (182, 36, 30))),
                 (-1.45, 2.48, -1.22), (4.4, 0.76))[0])

    parts = {"body": _Part(m.verts, _faces(m))}
    for key, wx, wz in TANKER_WHEELS:
        wm = _wheel_mesh(wx, TANKER_WHEEL_R, wz)
        parts[key] = _Part(wm.verts, _faces(wm), centre=(wx, TANKER_WHEEL_R, wz))
    return parts


def _checkpoint_static():
    out = []
    out.append(quad_xz(-160, -40, 160, 120, 0.0, tex("m7_dirt", like=(38, 36, 34)), seg=6.0))
    out.append(box(320.0, 0.12, 7.6, tex("pavement", like=(44, 45, 50)), center=(0, 0.06, 0), seg=6.0))
    for k in range(-26, 26):
        out.append(quad_xz(k * 6.0, -0.08, k * 6.0 + 2.6, 0.08, 0.125, (160, 154, 126), layer=1))
    bx, bz = BOOTH
    out.append(box(2.7, 2.65, 2.6, tex("concrete", like=(118, 116, 108)), center=(bx, 1.32, bz)))
    out.append(box(3.15, 0.26, 3.05, (58, 60, 66), center=(bx, 2.76, bz)))
    _win(out[-1], bx - 0.9, bx + 0.9, 1.3, 2.1, bz - 1.33, WIN_WARM)
    krap = _surf("krap", lambda: _stencil(_T("engine.krap"), (236, 236, 236)))
    band = box(2.72, 0.52, 0.02, KRAP_BLUE, center=(bx, 2.36, bz - 1.31))
    out.append(band)
    out.append(_decal(krap, (bx, 2.36, bz - 1.33), (1.25, 0.36)))
    # Barrier pedestal + counterweight box + far stanchion
    out.append(box(0.46, 1.05, 0.46, (186, 180, 162), center=(BAR_PIVOT[0], 0.52, BAR_PIVOT[2])))
    out.append(box(0.22, 0.18, 0.22, (255, 164, 42), center=(BAR_PIVOT[0], 1.14, BAR_PIVOT[2]), emissive=True))
    out.append(box(0.5, 0.9, 0.5, (42, 42, 46), center=(BAR_PIVOT[0], 0.45, 4.6)))
    # FuegoTech cargo crates neatly stacked right of checkpoint
    cx, cz = CRATES
    ct = tex("crate", like=(114, 92, 60))
    ft = _surf("ft2", lambda: _stencil(_T("engine.fuegotech"), (178, 40, 30)))
    ipa = _surf("ipa", lambda: _stencil(_T("engine.property_of_ipa"), (40, 30, 26), "R5"))
    for i in range(3):
        for j in range(2 if i < 2 else 1):
            x, y = cx + i * 1.3, 0.48 + j * 0.96
            out.append(box(1.25, 0.94, 1.0, ct, center=(x, y, cz)))
            out.append(_decal(ft, (x, y + 0.14, cz - 0.52), (1.0, 0.2)))
            out.append(_decal(ipa, (x, y - 0.16, cz - 0.52), (0.9, 0.08)))
    fx_, fz = FLOOD
    out.append(_beam((fx_, 0, fz), (fx_, 7.6, fz), 0.22, STEEL_D))
    out.append(box(1.2, 0.6, 0.4, STEEL_D, center=(fx_, 7.7, fz + 0.1)))
    out.append(box(1.0, 0.4, 0.06, (255, 246, 214), center=(fx_, 7.7, fz + 0.32), emissive=True))
    # Second pole across the highway for rim depth
    out.append(_beam((-11.0, 0, 5.2), (-11.0, 7.2, 5.2), 0.20, STEEL_D))
    out.append(box(0.9, 0.32, 0.28, (255, 220, 162), center=(-11.0, 7.2, 5.0), emissive=True))
    # Concrete Jersey barriers lining the checkpoint perimeter
    for i in range(9):
        x = -15.0 + i * 2.7
        if abs(x - BAR_PIVOT[0]) < 1.3:
            continue
        out.append(box(1.3, 0.82, 0.6, tex("concrete", like=(96, 94, 88)), center=(x, 0.41, -4.55)))
    return out


def checkpoint(surface, t):
    if _S["parts"].get("tanker_rig") is None:
        _S["parts"]["tanker_rig"] = _tanker_parts()
    tank = _S["parts"]["tanker_rig"]
    lift = _k(t, 1200, 1500)
    # Tanker rolls into frame right away, eases at the rising barrier, then accelerates past
    tx = -16.5 + 10.5 * _k(t, 0, 2200) + max(0.0, t - 2100) * 0.0036
    u = _k(t, 400, 6600)
    eye = _mix((5.8, 2.25, -13.6), (-4.2, 2.85, -15.4), u)
    tgt = _mix((-1.2, 1.95, -2.2), (0.2, 2.0, 0.0), u)
    fov = 44 + 4 * u
    lights = [
        {"pos": (FLOOD[0], 7.5, FLOOD[1] + 0.5), "color": (255, 242, 212), "intensity": 1.65,
         "range": 24.0, "kind": "spot", "dir": (-0.34, -0.82, 0.46), "cone": 0.72},
        {"pos": (BOOTH[0], 1.8, BOOTH[1] - 1.6), "color": (255, 186, 108), "intensity": 0.9,
         "range": 5.5},
        {"pos": (-11.0, 7.0, 4.8), "color": (255, 206, 146), "intensity": 1.15, "range": 18.0},
        {"pos": (tx + 6.7, 1.15, 0.0), "color": (255, 240, 198), "intensity": 1.55, "range": 18.0,
         "kind": "spot", "dir": (1.0, -0.1, 0.0), "cone": 0.84},
        {"pos": (tx + 2.0, 3.4, -4.8), "color": (210, 220, 240), "intensity": 0.75, "range": 14.0},
    ]
    r, buf = _stage("checkpoint", "night", t, eye, tgt, fov, _checkpoint_static, lights,
                    hh=0.012, seed=41)
    bob = math.sin(t * 0.014) * 0.012
    tank["body"].put(r, dx=tx, dy=bob)
    spin = -tx / TANKER_WHEEL_R
    for key, _wx, _wz in TANKER_WHEELS:
        tank[key].put(r, dx=tx, spin=spin)
    r.add_blob_shadow((tx + 0.3, 0.13, 0.0), 6.5, 1.55, 0.65)
    for z in (-0.82, 0.82):
        r.add_sprite((tx + 6.56, 1.12, z),
                     _fx.glow((255, 238, 188), 0.9, t, core=(255, 252, 228), intensity=0.9), layer=LAY)
        r.add_sprite((tx - 5.74, 0.88, z),
                     _fx.glow((255, 44, 34), 0.7, t, intensity=0.85), layer=LAY)
    # Wet road reflection ahead of the tanker headlights
    r.add_sprite((tx + 10.5, 0.14, 0.0),
                 _m5.wet_reflection((255, 232, 182), t, seed=41, length_m=5.0, width_m=1.1,
                                    intensity=0.38), layer=2)
    # Diesel exhaust wisps rising from the tractor's twin chrome stacks
    for i in range(5):
        age = ((t / 700.0) + i / 5.0) % 1.0
        r.add_sprite((tx + 2.74 - age * 2.2, 3.75 + age * 1.3, -1.10),
                     _fx.haze((110, 114, 124), 0.45 + age * 0.7, t, seed=40 + i,
                              intensity=0.22 * (1.0 - age)), layer=LAY)
    arm = Mesh()
    for i in range(8):
        col = (204, 42, 34) if i % 2 == 0 else (226, 226, 220)
        arm.add(box(0.14, 0.14, 1.0, col, center=(0, 0, 0.5 + i)))
    _w.add(r, _place(arm, BAR_PIVOT, mat=rot_x(-82.0 * lift)))
    # Blinking amber barrier warning beacon
    r.add_sprite((BAR_PIVOT[0], 1.24, BAR_PIVOT[2]),
                 _fx.beacon((255, 168, 42), 0.55, t, period_ms=1100.0, intensity=0.85), layer=LAY)
    r.add_sprite((FLOOD[0], 7.65, FLOOD[1] + 0.4), _fx.glow((255, 244, 214), 1.7, t, intensity=0.95),
                 layer=LAY)
    r.add_sprite((FLOOD[0] - 1.5, 3.6, FLOOD[1] + 2.0),
                 _fx.light_shaft((255, 240, 210), height_m=7.2, top_m=0.6, bot_m=4.2, t=t, seed=4,
                                 intensity=0.14), layer=LAY)
    r.add_sprite((-11.0, 7.2, 5.0), _fx.sodium_lamp(t, seed=9, radius_m=2.2), layer=LAY)
    me = (0.75, 0.0, -5.05)
    face = _w.yaw_to(me, (max(-14.0, min(14.0, tx + 4.0)), 0.0, 0.0))
    _w.actor(r, ("ally", "krap"), F.stand_pose(**dict(_ready())), me, face, t, seed=42, amp=0.4,
             rifle_on=True)
    me2 = (BOOTH[0] + 1.8, 0.0, BOOTH[1] - 1.2)
    _w.actor(r, ("ally", "krap"), F.stand_pose(**dict(_ready())), me2,
             _w.yaw_to(me2, (tx + 4.0, 0.0, 0.0)), t, seed=43, amp=0.4, rifle_on=True)
    _m5.rain3d(r, t, seed=41, n_near=42, n_far=115, ground=0.0, splashes=6,
               surface=lambda x, z: 0.0)
    _finish(surface, r, buf, t, 41)


def _ready():
    from engine3d.rig import POSES
    return POSES["ready"]


# ── 7. the arrival ──────────────────────────────────────────────────────────
ME = (1.6, 0.0, -2.0)
VAN_X = -4.2
STREET_LAMPS = (-15.0, 9.5, 28.0)


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
    out.append(_shacks(13, -70, 70, 30, 74, lit=0.45))
    out.append(_place(_shacks(14, -150, 150, -10, 10, lit=0.4), (-40.0, 0.0, 0.0), -90.0))
    side, _sb = _towers(45, -150, 150, -150, -70, hmin=14.0, hmax=30.0, n=10, crane=False)
    out += side
    tw, _b = _towers(44, 150, 210, -120, 120, n=10)
    out += tw
    # Tactical olive duffel bag with strap beside Biribel's boots
    out.append(box(0.72, 0.38, 0.34, (48, 56, 46), center=(ME[0] - 0.62, 0.19, ME[2] + 0.15)))
    out.append(box(0.14, 0.40, 0.36, (30, 34, 30), center=(ME[0] - 0.62, 0.20, ME[2] + 0.15)))
    return out


def arrival(surface, t):
    van = _van_rig()
    u = _k(t, 0, 9500)
    # Hero wide 3/4 tracking shot: frames BOTH Biribel (right foreground) and the
    # idling KRAP van (left-center) with Acaristan City's glowing towers rising behind.
    eye = _mix((4.6, 1.58, -6.8), (1.0, 1.72, -7.8), u)
    tgt = _mix((-0.9, 1.65, 1.4), (-1.4, 1.75, 2.2), u)
    lights = [
        {"pos": (VAN_X + _HEAD[0] + 0.2, _HEAD[1], 0.0), "color": (255, 240, 192),
         "intensity": 1.65, "range": 18.0, "kind": "spot", "dir": (1.0, -0.1, -0.15),
         "cone": 0.86},
        {"pos": (VAN_X + 1.5, 2.4, -4.4), "color": (160, 184, 224), "intensity": 0.72, "range": 12.0},
    ]
    for x in STREET_LAMPS:
        lights.append({"pos": (x, 5.6, -2.1), "color": (255, 182, 104), "intensity": 1.15,
                       "range": 11.0})
    r, buf = _stage("arrival", "night_city", t, eye, tgt, 46, _arrival_static, lights,
                    hh=0.015, seed=51)
    van["body"].put(r, dx=VAN_X)
    for g in _WHEELS:
        van[g].put(r, dx=VAN_X)
    r.add_blob_shadow((VAN_X, 0.02, 0.0), 3.7, 1.5, 0.7)
    for z in (-0.8, 0.8):
        r.add_sprite((VAN_X + _HEAD[0] + 0.06, _HEAD[1], z),
                     _fx.glow((255, 236, 180), 1.05, t, core=(255, 250, 225), intensity=0.95), layer=LAY)
        r.add_sprite((VAN_X + _TAIL[0] - 0.05, _TAIL[1], z * 1.1),
                     _fx.glow((255, 42, 32), 0.85, t, intensity=0.85), layer=LAY)
    r.add_sprite((VAN_X + 6.5, 0.02, 0.0),
                 _m5.wet_reflection((255, 230, 180), t, seed=5, length_m=4.6, width_m=1.1,
                                    intensity=0.42), layer=2)
    for i in range(4):
        age = ((t / 640.0) + i / 4.0) % 1.0
        r.add_sprite((VAN_X - 3.7 - age * 2.4, 0.52 + age * 0.45, -0.5),
                     _fx.haze((110, 118, 134), 0.35 + age * 0.65, t, seed=55 + i,
                              intensity=0.22 * (1.0 - age)), layer=LAY)
    for i, x in enumerate(STREET_LAMPS):
        r.add_sprite((x, 5.82, -2.1), _fx.sodium_lamp(t, seed=i, radius_m=2.4), layer=LAY)
        r.add_sprite((x, 0.02, -2.1), _m5.wet_reflection((255, 178, 100), t, seed=i, length_m=3.2,
                                                          width_m=0.5, intensity=0.45), layer=2)
    _tw, beacons = _towers(44, 150, 210, -120, 120, n=10)
    _beacons(r, t, beacons)
    # Biribel looking out toward the glowing Acaristan skyline, 3/4 hero silhouette
    pose = F.stand_pose(head_p=-6 + 4 * _k(t, 5000, 2500), head_y=-14)
    _w.actor(r, ("biribel", "krap"), pose, ME, -18.0, t, seed=52, amp=0.5, expression="neutral")
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
