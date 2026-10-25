"""Mission 6 yard - the clutter that makes the walled yard look lived in.

Static meshes only (the yard bakes them once with the perimeter).  The solid
props are data (``SOLIDS``) so ``yard3d`` can turn them into blockers: the
camera boom, the Guards' nav grid and the player all respect them.  Kept off
the Guards' routes, the truck road (x 22..27) and the lamp masts.

Past the walls a Bloc town rings the yard: panel blocks, stacks, a mast, a
water tower and watchtowers.  Their lamps are collected in ``BEACONS``,
``SIGN_LAMPS`` and ``SEARCHLIGHTS`` so ``yard3d`` can hang halo sprites on
them (sprites are not baked with the perimeter mesh).
"""
from __future__ import annotations

import math

from engine3d import tex
from engine3d.core import box, quad_xz
from missions.m6 import bloc3d as B
from missions.m6 import palette3d as P

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

# Lamp points filled by ``skyline``: yard3d reads them every frame for halos.
BEACONS = []        # (x, y, z) aviation lamps on stacks, masts and towers
SIGN_LAMPS = []     # (x, y, z) sodium lamp heads over the lit signs
SEARCHLIGHTS = []   # ((x, y, z), facing) watchtower lenses


def blockers():
    return [(x - w * 0.5, 0.0, z - d * 0.5, x + w * 0.5, h, z + d * 0.5)
            for _k, x, z, w, d, h in SOLIDS]


def _hash(i, k=1):
    """A repeatable 0..1 from an index (no random module: stable frames)."""
    return (math.sin(i * 12.9898 + k * 78.233) * 43758.5453) % 1.0


def _facing_to(cx, cz):
    """The face normal whose axis best points from (cx, cz) at the yard centre."""
    fx, fz = 0.5 - cx, -5.0 - cz
    if abs(fx) >= abs(fz):
        return "+x" if fx > 0 else "-x"
    return "+z" if fz > 0 else "-z"


def _ring_pt(i):
    """Centre of ring block ``i``: an ellipse 62..88 m out around the yard."""
    a = i / 14.0 * math.tau + 0.2
    rad = 62.0 + 26.0 * _hash(i, 2)
    return 0.5 + math.cos(a) * rad * 1.35, -5.0 + math.sin(a) * rad


def _ring_block(i):
    """(cx, cz, facing, w, h, d) of ring block ``i``, as ``skyline`` builds it."""
    cx, cz = _ring_pt(i)
    w, h, d = 18.0 + 18.0 * _hash(i, 3), 14.0 + 28.0 * _hash(i, 5), 10.0 + 4.0 * _hash(i, 4)
    return cx, cz, _facing_to(cx, cz), w, h, d


# Landmarks past the walls, in the ring's gaps: x, z, and how much ring to clear.
_LANDMARKS = ((-44.0, -40.0, 22.0), (46.0, -38.0, 22.0),
              (-62.0, 40.0, 26.0), (66.0, 30.0, 22.0))


def _ring_blocks():
    """The ring blocks ``skyline`` actually builds: (i, cx, cz, facing, w, h, d)."""
    out = []
    for i in range(14):
        cx, cz = _ring_pt(i)
        if any(abs(cx - lx) < clear and abs(cz - lz) < clear
               for lx, lz, clear in _LANDMARKS):
            continue
        out.append((i, *_ring_block(i)))
    return out


def skyline(add):
    """The Bloc town past the walls, so the yard sits in a city, not a void.

    Bodies stay darker than the night fog so they read as silhouettes; only
    windows, neon and the aviation lamps are bright.  The ring has gaps where
    the landmarks stand: stacks south-west and south-east, the mast north-west
    and a water tower north-east.
    """
    del BEACONS[:], SIGN_LAMPS[:], SEARCHLIGHTS[:]
    # 1. ring of panel blocks, each with its lit face turned to the yard
    blocks = _ring_blocks()
    for i, cx, cz, f, w, h, d in blocks:
        col = (26 + int(9 * _hash(i, 6)), 30 + int(7 * _hash(i, 7)),
               40 + int(7 * _hash(i, 6)))
        B.panel_block(add, cx, cz, w, h, d, f, seed=i, col=col, lit=0.30, budget=30, balconies=False)
    # 2. neon slogans on the block most directly south and the most north-west
    south = min(blocks, key=lambda b: (abs(b[1]), abs(b[2] + 40.0)))
    nw = min(blocks, key=lambda b: (b[1] + 45.0) ** 2 + (b[2] - 45.0) ** 2)
    for b, text in ((south, "СЛАВА ТРУДУ"), (nw, "АКАРИСТАН")):
        pos, fac = B.roof_sign_pos(b[1], b[2], b[4], b[5], b[6], b[3])
        B.letters(add, text, pos, fac, px=0.55, col=B.NEON_RED, emissive=True)
    # 3. landmarks past the walls, in the ring's gaps
    BEACONS.extend(B.smokestack(add, -44.0, -40.0, 38.0, base=2.2, top=1.3))
    BEACONS.extend(B.smokestack(add, 46.0, -38.0, 30.0, base=2.0, top=1.2))
    BEACONS.extend(B.radio_mast(add, -62.0, 40.0, 46.0))
    B.water_tower(add, 66.0, 30.0, h=14.0)
    # 4. watchtowers just outside the south corners, lenses turned into the yard
    for tx in (-31.5, 32.5):
        SEARCHLIGHTS.append(B.watchtower(add, tx, -22.5, h=6.5, facing="+z"))
    # 5. a billboard outside the south wall; its lamps get halo sprites
    SIGN_LAMPS.extend(B.billboard(add, ["ВПЕРЁД", "К ПОБЕДЕ!"], (0.0, -25.0), "+z", top=8.0))


def _cable_reel(add, x, z, col=(88, 62, 38)):
    """One timber cable drum: two cheek plates, a hub and a steel axle."""
    add(box(1.05, 1.05, 0.14, col, center=(x, 0.55, z - 0.32)))
    add(box(1.05, 1.05, 0.14, _dim(col), center=(x, 0.55, z + 0.32)))
    add(box(0.48, 0.48, 0.62, (56, 50, 42), center=(x, 0.55, z)))
    add(box(0.80, 0.06, 0.06, _STEEL, center=(x, 0.55, z)))
    add(box(0.12, 0.22, 0.12, (30, 32, 36), center=(x, 0.12, z)))


def _work_cart(add, x, z):
    """A maintenance trolley left where the night shift stopped."""
    add(box(1.65, 0.12, 0.78, (58, 58, 54), center=(x, 0.48, z)))
    add(box(1.55, 0.42, 0.68, (72, 74, 68), center=(x, 0.25, z)))
    for wx, wz in ((-0.68, -0.34), (0.68, -0.34),
                   (-0.68, 0.34), (0.68, 0.34)):
        add(box(0.20, 0.28, 0.16, (24, 25, 28),
                center=(x + wx, 0.16, z + wz)))
    add(box(0.06, 0.84, 0.06, _STEEL, center=(x - 0.82, 0.88, z)))
    add(box(0.54, 0.05, 0.06, _STEEL, center=(x - 0.58, 1.26, z)))
    add(box(0.42, 0.28, 0.36, (66, 48, 34), center=(x + 0.30, 0.68, z)))


def _dead_tree(add, x, z, h=3.8):
    """Wind-broken poplar beyond the wall: a vertical rhythm, no foliage."""
    col = (32, 31, 30)
    add(box(0.22, h, 0.22, col, center=(x, h * 0.5, z)))
    for i, (dx, dz, yy, ln) in enumerate((
            (-0.42, 0.10, 0.62, 1.35), (0.36, -0.14, 0.76, 1.05),
            (-0.20, -0.26, 0.47, 0.85), (0.16, 0.22, 0.34, 0.72))):
        add(box(ln, 0.10, 0.10, col,
                center=(x + dx * ln, h * yy, z + dz * ln)))
    add(box(0.08, 0.72, 0.08, col, center=(x + 0.18, h + 0.32, z - 0.08)))


def _dim(col, k=0.72):
    return tuple(int(c * k) for c in col)


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
    # service clutter: drums, a trolley and a maintenance caddy against the
    # walls, where it frames the lanes without narrowing them
    for x, z in ((-25.9, -12.4), (-24.8, -13.1)):
        _cable_reel(add, x, z)
    _work_cart(add, 25.3, 3.2)
    for i, (x, z, h) in enumerate(((-31.0, 6.0, 4.2), (-30.0, -8.0, 3.4),
                                    (31.5, -11.0, 4.6))):
        _dead_tree(add, x, z, h)
    # smaller wall-side dressing: buckets, a coiled hose, spare sleepers
    for i, (x, z, col) in enumerate(((-20.2, 8.2, (58, 62, 62)),
                                     (-19.4, 8.4, (42, 48, 52)),
                                     (21.8, -15.8, (72, 58, 40)))):
        add(box(0.42, 0.46, 0.42, col, center=(x, 0.24, z)))
        add(box(0.34, 0.06, 0.34, (168, 178, 194), center=(x, 0.50, z)))
    for i in range(3):
        add(box(1.8, 0.10, 0.34, (54, 46, 36),
                center=(-22.8, 0.06 + i * 0.11, -8.4 + i * 0.06)))
    # painted edge lines and an old oil stain around the service bay
    for z0 in (-14.0, -8.0, -2.0, 4.0):
        add(quad_xz(-20.5, z0, -15.2, z0 + 0.08, 0.058, (162, 140, 68)))
    add(quad_xz(-19.6, -11.4, -15.6, -8.2, 0.052, (30, 34, 40)))
    add(quad_xz(-19.0, -10.8, -16.2, -8.8, 0.055, (42, 48, 58)))

    # a pipe run and wall lamps along the south wall; warning signs
    add(box(wall_e - wall_w - 2.0, 0.16, 0.16, _STEEL,
            center=((wall_e + wall_w) * 0.5, 2.05, wall_s + 0.5), seg=8))
    for i in range(14):
        add(box(0.1, 0.5, 0.18, _POST, center=(wall_w + 3.0 + i * 4.1, 1.82, wall_s + 0.5)))
    for lx in (-24.0, -6.0, 3.5, 11.0):
        add(box(0.3, 0.14, 0.2, (255, 236, 154), center=(lx, 2.3, wall_s + 0.42), emissive=True))
        add(box(0.1, 0.4, 0.1, _POST, center=(lx, 2.1, wall_s + 0.4)))
    for sx, sz, face, fac in ((-12.0, wall_s + 0.24, 0, "+z"), (9.0, wall_s + 0.24, 0, "+z"),
                              (wall_w + 0.24, -5.0, 1, "+x"), (wall_w + 0.24, 4.5, 1, "+x"),
                              (wall_e - 0.24, -14.0, 1, "-x")):
        out = 0.02 if fac in ("+z", "+x") else -0.02     # the plate's front side
        dx, dz = (out, 0.0) if face == 0 else (0.0, out)
        B.letters(add, "СТОЙ!", (sx + dx, 1.5, sz + dz), fac, px=0.026,
                  col=(20, 18, 14), emissive=False)
    # two painted banners on the inside of the south wall, facing the yard
    for bx, text in ((-18.0, "МИР"), (18.0, "ТРУД")):
        B.banner(add, text, (bx, 3.6, wall_s + 0.06), "+z", px=0.10)
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
