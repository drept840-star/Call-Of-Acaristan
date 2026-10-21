"""Mission 6 yard - the clutter that makes the walled yard look lived in.

Static meshes only (the yard bakes them once with the perimeter).  The solid
props are data (``SOLIDS``) so ``yard3d`` can turn them into blockers: the
camera boom, the Guards' nav grid and the player all respect them.  Kept off
the Guards' routes, the truck road (x 22..27) and the lamp masts.
"""
from __future__ import annotations

import math

from engine3d import tex
from engine3d.core import box, quad_xz

# kind, x, z, w, d, h
SOLIDS = (
    ("container", -20.0, -18.1, 6.1, 2.4, 5.3),     # a stack of two
    ("pallets", -14.4, -18.3, 1.2, 1.2, 1.2),
    ("barrels", -11.2, -18.4, 1.3, 0.9, 0.95),
    ("van", 14.2, -17.9, 5.2, 2.1, 2.0),
    ("crates", 19.2, -18.4, 1.9, 1.3, 1.5),
    ("tyres", 28.3, -17.7, 1.2, 1.2, 1.0),
    ("drums", -27.5, -15.6, 1.2, 1.2, 1.0),
    ("drums", -27.5, -3.6, 1.2, 1.2, 1.0),
    ("pipes", -27.3, 4.2, 1.4, 4.2, 0.95),
    ("pallets", -24.5, 7.6, 1.2, 1.2, 1.2),
    ("sandbags", 27.6, 4.6, 2.4, 0.8, 0.9),
)

_SNOW = (176, 186, 202)
_POST = (34, 36, 42)
_STEEL = (58, 66, 78)


def blockers():
    return [(x - w * 0.5, 0.0, z - d * 0.5, x + w * 0.5, h, z + d * 0.5)
            for _k, x, z, w, d, h in SOLIDS]


def _hash(i, k=1):
    """A repeatable 0..1 from an index (no random module: stable frames)."""
    return (math.sin(i * 12.9898 + k * 78.233) * 43758.5453) % 1.0


def skyline(add):
    """Lit blocks past the walls, so the yard sits in a town, not a void."""
    n = 0
    for i in range(26):
        a = i / 26.0 * math.tau + 0.2
        rad = 62.0 + 26.0 * _hash(i, 2)
        cx, cz = 0.5 + math.cos(a) * rad * 1.35, -5.0 + math.sin(a) * rad
        w, d = 9.0 + 9.0 * _hash(i, 3), 8.0 + 8.0 * _hash(i, 4)
        h = 14.0 + 26.0 * _hash(i, 5)
        add(box(w, h, d, (22 + int(10 * _hash(i, 6)), 26, 36), center=(cx, h * 0.5, cz)))
        fx, fz = -math.cos(a), -math.sin(a)
        face_z = abs(fz) >= abs(fx)            # window wall faces +-z, else +-x
        sgn = (1.0 if fz > 0 else -1.0) if face_z else (1.0 if fx > 0 else -1.0)
        span, rows = (w, d)[0 if face_z else 1], int(h // 3.2)
        cols = int(span // 2.4)
        for r in range(rows):
            for c in range(cols):
                if _hash(i * 97 + r * 7 + c, 8) < 0.62:
                    continue
                off = (c - (cols - 1) * 0.5) * 2.4
                if face_z:
                    pos, size = (cx + off, 2.2 + r * 3.2, cz + sgn * (d * 0.5 + 0.04)), (1.2, 1.5, 0.06)
                else:
                    pos, size = (cx + sgn * (w * 0.5 + 0.04), 2.2 + r * 3.2, cz + off), (0.06, 1.5, 1.2)
                warm = _hash(i * 31 + r * 5 + c, 9)
                col = (255, 203, 109) if warm < 0.7 else (176, 206, 255)
                add(box(*size, col, center=pos, emissive=True))
                n += 1
                if n > 380:
                    return


def _prop(add, kind, x, z, w, d, h):
    if kind == "container":
        for lvl, col in enumerate(((126, 54, 44), (44, 86, 104))):
            cy = 1.3 + lvl * 2.65
            add(box(w, 2.6, d, tex("metal_rib", like=col, tint=True), center=(x, cy, z),
                    seg=3))
            rib = tuple(int(c * 0.78) for c in col)
            for k in range(1, 9):
                add(box(0.06, 2.4, d + 0.05, rib, center=(x - w * 0.5 + w * k / 9.0, cy, z)))
        add(box(w + 0.1, 0.08, d + 0.1, _SNOW, center=(x, h + 0.04, z)))
    elif kind == "pallets":
        for lvl in range(3):
            add(box(w, 0.16, d, tex("crate", like=(112, 86, 56), tint=True),
                    center=(x, 0.1 + lvl * 0.42, z)))
            add(box(w * 0.92, 0.26, d * 0.92, (130, 118, 92) if lvl % 2 else (92, 100, 108),
                    center=(x, 0.3 + lvl * 0.42, z)))
        add(box(w + 0.1, 0.1, d + 0.1, _SNOW, center=(x, 1.2, z)))
    elif kind == "barrels":
        for bx, bz, col in ((-0.35, -0.2, (170, 60, 40)), (0.3, -0.1, (60, 96, 140)),
                            (0.0, 0.25, (178, 150, 54))):
            add(box(0.55, 0.95, 0.55, tex("rust", like=col, tint=True),
                    center=(x + bx, 0.48, z + bz)))
            add(box(0.58, 0.06, 0.58, (30, 32, 38), center=(x + bx, 0.7, z + bz)))
    elif kind == "van":
        add(box(w, 1.25, d, tex("steel", like=(186, 190, 196), tint=True),
                center=(x, 0.95, z), seg=3))
        add(box(w * 0.55, 0.75, d * 0.92, tex("steel", like=(170, 176, 184), tint=True),
                center=(x - 0.6, 1.95, z)))
        add(box(w * 0.28, 0.6, d * 0.94, (28, 36, 48), center=(x + w * 0.34, 1.35, z)))
        for wx in (-1.6, 1.7):
            for wz in (-1.0, 1.0):
                add(box(0.7, 0.7, 0.26, (22, 24, 28), center=(x + wx, 0.38, z + wz)))
        for lz in (-0.7, 0.7):
            add(box(0.04, 0.22, 0.3, (255, 251, 206),
                    center=(x + w * 0.5 + 0.01, 0.9, z + lz), emissive=True))
        add(box(w * 0.55 + 0.1, 0.08, d * 0.92 + 0.1, _SNOW, center=(x - 0.6, 2.34, z)))
    elif kind == "crates":
        add(box(w, 0.75, d, tex("crate", like=(124, 98, 60), tint=True),
                center=(x, 0.38, z)))
        add(box(w * 0.7, 0.75, d * 0.8, tex("crate", like=(108, 84, 52), tint=True),
                center=(x + 0.2, 1.13, z)))
        add(box(w * 0.7 + 0.08, 0.08, d * 0.8 + 0.08, _SNOW, center=(x + 0.2, 1.52, z)))
    elif kind == "tyres":
        for lvl in range(4):
            add(box(0.95, 0.24, 0.95, (22, 24, 28), center=(x, 0.14 + lvl * 0.26, z)))
        add(box(0.8, 0.06, 0.8, _SNOW, center=(x, 1.06, z)))
    elif kind == "drums":
        for dx in (-0.3, 0.3):
            for dz in (-0.3, 0.3):
                add(box(0.5, 0.9, 0.5, tex("rust", like=(70, 96, 70), tint=True),
                        center=(x + dx, 0.45, z + dz)))
                add(box(0.52, 0.05, 0.52, (28, 34, 30), center=(x + dx, 0.6, z + dz)))
    elif kind == "pipes":
        for row in range(3):
            for k in range(3 - row):
                add(box(w - 0.2, 0.28, 0.28, tex("steel", like=_STEEL, tint=True),
                        center=(x, 0.16 + row * 0.27, z - d * 0.5 + 0.35 + k * 0.5 + row * 0.25)))
    elif kind == "sandbags":
        for row in range(2):
            for i in range(int(w / 0.6)):
                add(box(0.58, 0.28, 0.4, (118, 106, 82),
                        center=(x - w * 0.5 + 0.3 + i * 0.6 + row * 0.3, 0.16 + row * 0.27, z)))


def dress(add, wall_w, wall_e, wall_s, road_x):
    """Add every prop, sign, marking and drift to ``add`` (a Mesh.add)."""
    for kind, x, z, w, d, h in SOLIDS:
        _prop(add, kind, x, z, w, d, h)
    # a pipe run and wall lamps along the south wall; warning signs
    add(box(wall_e - wall_w - 2.0, 0.16, 0.16, _STEEL,
            center=((wall_e + wall_w) * 0.5, 2.05, wall_s + 0.5), seg=8))
    for i in range(14):
        add(box(0.1, 0.5, 0.18, _POST, center=(wall_w + 3.0 + i * 4.1, 1.82, wall_s + 0.5)))
    for lx in (-24.0, -6.0, 3.5, 11.0):
        add(box(0.3, 0.14, 0.2, (255, 236, 154), center=(lx, 2.3, wall_s + 0.42), emissive=True))
        add(box(0.1, 0.4, 0.1, _POST, center=(lx, 2.1, wall_s + 0.4)))
    for sx, sz, face in ((-12.0, wall_s + 0.24, 0), (9.0, wall_s + 0.24, 0),
                         (wall_w + 0.24, -5.0, 1), (wall_w + 0.24, 4.5, 1),
                         (wall_e - 0.24, -14.0, 1)):
        w_, d_ = (0.9, 0.04) if face == 0 else (0.04, 0.9)
        add(box(w_ + 0.08, 0.7, d_ + 0.08, (30, 32, 36), center=(sx, 1.5, sz)))
        add(box(w_, 0.62, d_ + 0.02, (232, 186, 46), center=(sx, 1.5, sz), emissive=True))
    # painted ground: the road's centre line, stop line and hazard bars at the
    # south gate, puddles, a manhole and the drifts piled against the walls
    for z0 in range(-19, 8, 3):
        add(quad_xz(road_x - 0.08, z0, road_x + 0.08, z0 + 1.6, 0.052, (150, 154, 150)))
    add(quad_xz(road_x - 2.0, -16.8, road_x + 2.2, -16.55, 0.052, (176, 172, 150)))
    for i in range(10):
        add(quad_xz(road_x - 2.1 + i * 0.44, wall_s + 0.5, road_x - 1.8 + i * 0.44,
                    wall_s + 1.0, 0.054, (200, 160, 40) if i % 2 else (40, 40, 44)))
    for px, pz, pw, pd in ((2.0, -11.0, 3.4, 1.8), (-12.0, -9.6, 4.2, 2.2),
                           (10.4, -4.8, 2.6, 1.6), (-20.0, -4.0, 3.0, 1.6),
                           (6.0, -16.0, 2.4, 1.2), (28.0, -4.0, 1.8, 2.8)):
        add(quad_xz(px - pw * 0.5, pz - pd * 0.5, px + pw * 0.5, pz + pd * 0.5, 0.056,
                    (52, 66, 88)))
        add(quad_xz(px - pw * 0.3, pz - pd * 0.3, px + pw * 0.3, pz + pd * 0.3, 0.058,
                    (70, 86, 112)))
    add(box(0.9, 0.04, 0.9, (30, 32, 38), center=(-4.0, 0.06, -3.4)))
    add(box(0.55, 0.045, 0.55, (46, 50, 58), center=(-4.0, 0.065, -3.4)))
    snow = tex("snow", like=_SNOW)
    for i in range(34):
        add(box(0.8 + 0.7 * _hash(i, 11), 0.10 + 0.10 * _hash(i, 12), 0.45, snow,
                center=(wall_w + 1.2 + i * 1.7, 0.07, wall_s + 0.55 + 0.2 * _hash(i, 13))))
    for i in range(14):
        add(box(0.45, 0.10 + 0.10 * _hash(i, 14), 0.8 + 0.6 * _hash(i, 15), snow,
                center=(wall_w + 0.65, 0.07, wall_s + 1.0 + i * 1.6)))
    for i, (dx, dz) in enumerate(((-24.0, 7.0), (-9.0, -17.0), (-1.0, -15.5), (24.0, -18.0),
                                  (-16.0, -14.5), (12.0, -2.0), (-27.2, -10.0))):
        add(quad_xz(dx - 0.7 - _hash(i, 16) * 0.6, dz - 0.5, dx + 0.7 + _hash(i, 16) * 0.6,
                    dz + 0.5, 0.06, tex("snow_trod", like=(112, 124, 146))))
    skyline(add)
