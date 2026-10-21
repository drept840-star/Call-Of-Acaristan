"""Watchtowers and wire fences for the Bloc yards.

Everything here is axis-aligned: the tower narrows by stacking boxes, and the
fence leans its barbs by offsetting boxes, so the whole module keeps the
game's no-rotation rule and the painter's sort stays sane.
"""
from __future__ import annotations

from engine3d.core import box
from missions.m6 import palette3d as P

from .colours import *  # noqa: F401,F403  (WINDOW_DARK, LAMP_WHITE...)

_AXES = {"+z": (0, 1), "-z": (0, -1), "+x": (1, 0), "-x": (-1, 0)}


def _lerp(a, b, t):
    return a + (b - a) * t


def watchtower(add, x, z, h=6.5, facing="+z", col=(44, 40, 34)):
    """A timber spotting tower: four splayed legs, a glazed cabin, a roof
    searchlight. Returns the lens centre so the caller can hang a halo."""
    fx, fz = _AXES[facing]
    # --- legs: stacked segments tapering 2.4 -> 2.0 footprint ---------------
    segs = max(2, int(round(h / 1.0)))
    bottom, top = 2.4, 2.0
    for s in range(segs):
        y0, y1 = h * s / segs, h * (s + 1) / segs
        c = (y0 + y1) / 2
        span = _lerp(bottom, top, c / h)
        leg_h = y1 - y0 + 0.02  # a hair of overlap so the taper never shows a gap
        for sx in (-1, 1):
            for sz in (-1, 1):
                add(box(0.22, leg_h, 0.22, col,
                        center=(x + sx * (span - 0.22) / 2, c, z + sz * (span - 0.22) / 2)))
    # --- cross rings every 2 m ----------------------------------------------
    y = 2.0
    while y < h - 0.5:
        span = _lerp(bottom, top, y / h)
        e = span - 0.11  # centre line of the legs
        for (cx, cz, w, d) in ((x, z - e, span, 0.08), (x, z + e, span, 0.08),
                               (x - e, z, 0.08, span), (x + e, z, 0.08, span)):
            add(box(w, 0.08, d, dim(col, 0.85), center=(cx, y, cz)))
        # a diagonal brace pair on the facing side reads as triangulation
        add(box(span * 1.15, 0.07, 0.07, dim(col, 0.8),
                center=(x, y - 1.0, z + fz * e)))
        y += 2.0
    # --- ladder on the side opposite ``facing`` -----------------------------
    lx, lz = x - fx * (top / 2 + 0.05), z - fz * (top / 2 + 0.05)
    along_x = fz != 0  # a ladder on +-z face spreads along x
    rail_w, rail_d = (0.06, 0.04) if along_x else (0.04, 0.06)
    off = 0.28
    for s in (-1, 1):
        rcx = lx + (s * off if along_x else 0.0)
        rcz = lz + (0.0 if along_x else s * off)
        add(box(rail_w, h + 0.6, rail_d, P.STEEL, center=(rcx, (h + 0.6) / 2, rcz)))
    rung = 0.0
    while rung < h + 0.4:
        y = 0.2 + rung
        add(box(0.05 if along_x else 0.04, 0.05, 0.04 if along_x else 0.05, P.STEEL,
                center=(lx, y, lz)))
        rung += 0.35
    # --- cabin 2.6 x 2.0 x 2.6 ----------------------------------------------
    ch, cw = 2.0, 2.6
    cy = h + ch / 2
    cdim = dim(col, 1.12)
    add(box(cw, ch, cw, cdim, center=(x, cy, z), seg=2))
    band_y = h + 1.15
    for name, (nx, nz) in _AXES.items():
        w, d = (cw + 0.04, 0.04) if nz else (0.04, cw + 0.04)
        add(box(w, 0.7, d, WINDOW_DARK,
                center=(x + nx * cw / 2, band_y, z + nz * cw / 2)))
    # one lit slit, on the face the tower watches
    w, d = (0.9, 0.05) if fz else (0.05, 0.9)
    add(box(w, 0.7, d, (190, 140, 70), emissive=True,
            center=(x + fx * (cw / 2 + 0.02), band_y, z + fz * (cw / 2 + 0.02))))
    # --- roof: two overhanging steps and a snow cap -------------------------
    roof_y = h + ch
    add(box(3.2, 0.14, 3.2, dim(col, 0.7), center=(x, roof_y + 0.07, z)))
    add(box(2.8, 0.14, 2.8, dim(col, 0.8), center=(x, roof_y + 0.21, z)))
    roof_top = roof_y + 0.28
    add(box(2.8, 0.06, 2.8, P.SNOW_DIM, center=(x, roof_top + 0.03, z)))
    # --- searchlight --------------------------------------------------------
    hy = roof_top + 0.3
    hx, hz = x + fx * (1.3 - 0.5), z + fz * (1.3 - 0.5)  # hung over the eave
    add(box(0.5, 0.5, 0.5, P.STEEL, center=(hx, hy, hz)))
    lw, ld = (0.42, 0.04) if fz else (0.04, 0.42)
    lens = (hx + fx * 0.27, hy, hz + fz * 0.27)
    add(box(lw, 0.42, ld, P.LAMP_WHITE, center=lens, emissive=True))
    return lens, facing


def fence_run(add, x0, z0, x1, z1, h=2.6, post_every=3.0, col=(40, 44, 52)):
    """A straight run of barbed wire: posts, four strands, and a Y-top of
    two splayed arms so the wire reads as a stock fence, not a railing."""
    if x0 != x1 and z0 != z1:
        raise ValueError("fence_run is axis-aligned: x0 == x1 or z0 == z1")
    along_x = z0 == z1
    length = abs(x1 - x0) if along_x else abs(z1 - z0)
    a0, a1 = (x0, x1) if along_x else (z0, z1)
    fixed = z0 if along_x else x0
    n = 0  # boxes added; ``at`` counts them

    def at(along, across, y, w_long, w_across, depth, colour):
        nonlocal n
        n += 1
        if along_x:
            add(box(w_long, depth, w_across, colour,
                    center=(along, y, fixed + across)))
        else:
            add(box(w_across, depth, w_long, colour,
                    center=(fixed + across, y, along)))

    count = max(1, int(length / post_every + 0.5))
    posts = [a0 + (a1 - a0) * i / count for i in range(count + 1)]
    for p in posts:
        at(p, 0.0, h / 2, 0.1, 0.1, h, col)
        # Y arms: two short leaning boxes, crossed in offset, never rotated
        arm_h = 0.7
        at(p, 0.0, h + arm_h / 2, 0.07, 0.07, arm_h, dim(col, 0.9))
        for s in (-1, 1):
            for k in range(4):  # stacked bricks = a lean toward +-0.25
                t = k / 3
                at(p, s * 0.25 * t, h + arm_h * (0.15 + 0.8 * t), 0.06, 0.06, 0.16,
                   dim(col, 1.0 - 0.1 * k))
    # four strands, slightly sagging between posts
    for j in range(4):
        y = h * (0.22 + 0.22 * j)
        at((a0 + a1) / 2, 0.0, y, length, 0.03, 0.03, (96, 98, 104))
    # three barbed strands between the Y arms, the barbs as tiny crossed boxes
    for j in range(3):
        y = h + 0.18 + 0.2 * j
        at((a0 + a1) / 2, 0.0, y, length, 0.025, 0.025, (86, 88, 94))
        b = a0 + 0.5
        while b < a1:
            at(b, 0.0, y, 0.06, 0.09, 0.06, (78, 80, 88))
            b += 1.0
    return n
