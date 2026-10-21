"""Industrial silhouettes on the skyline: chimneys, a radio mast, a water tower.

All three are read from far away and at night, so they are built from a few
big boxes and lit only by their own aviation lamps; the taper is a stack of
short boxes rather than a slanted mesh, because nothing here may rotate.
"""
from __future__ import annotations

import math

from engine3d.core import box
from missions.m6 import palette3d as P

from .colours import BEACON_RED, WINDOW_WARM, dim

STACK_BAND_RED = (96, 30, 28)   # red/white stack stripes, authored dark for night
STACK_BODY = (46, 40, 40)
STACK_BAND = (120, 112, 108)
LIP = (12, 14, 18)


def _lerp(a, b, t):
    return a + (b - a) * t


def _beacons(add, x, z, y, w):
    """Four small emissive boxes, one on each side, at height ``y``."""
    d = w / 2 + 0.02
    for dx, dz in ((d, 0), (-d, 0), (0, d), (0, -d)):
        add(box(0.28, 0.28, 0.28, BEACON_RED, center=(x + dx, y, z + dz),
                emissive=True))


def smokestack(add, x, z, h, base=2.6, top=1.4, body=STACK_BODY,
               band=STACK_BAND) -> list[tuple[float, float, float]]:
    """Red-and-white brick chimney, tapering from ``base`` to ``top``.

    The upper half carries the stripes: that is where a real one is painted,
    because that is the part that shows above the roofline.  Returns one
    axis point per lamp height so the caller can hang halos on it.
    """
    n = 6
    step = h / n
    for i in range(n):
        t0, t1 = i / n, (i + 1) / n
        w = _lerp(base, top, (t0 + t1) / 2)
        y = (i + 0.5) * step
        col = body
        if y >= h / 2:
            # stripes count up from the half-height line: red on even numbers
            col = STACK_BAND_RED if int((y - h / 2) / (0.09 * h)) % 2 == 0 else band
        add(box(w, step, w, col, center=(x, y, z), seg=4))
    # 0.3 m dark lip: the mouth of the flue
    lip_w = top + 0.1
    add(box(lip_w, 0.3, lip_w, LIP, center=(x, h + 0.15, z)))
    ys = [h + 0.3, h * 2 / 3]
    for ly in ys:
        w = _lerp(base, top, ly / h) if ly < h else top
        _beacons(add, x, z, ly, w)
    return [(x, ly, z) for ly in ys]


def radio_mast(add, x, z, h, w=1.4, col=(40, 44, 52)) -> list[tuple[float, float, float]]:
    """A lattice mast: four legs, rings every 5 m, a whip and a dish.

    The legs are stacked segments whose offsets close in linearly, which
    gives the straight taper without a single rotated face.
    """
    seg_h = 5.0          # a far silhouette: longer segments, fewer faces
    n = max(1, int(math.ceil(h / seg_h)))
    seg_h = h / n

    def half_width(y):
        return (w / 2) * (1.0 - 0.6 * min(1.0, y / h))

    for i in range(n):
        y = (i + 0.5) * seg_h
        sw = half_width(i * seg_h) + half_width((i + 1) * seg_h)  # full width
        leg = 0.12
        for sx in (-1, 1):
            for sz in (-1, 1):
                add(box(leg, seg_h, leg, col, skip=("top", "bottom"),
                        center=(x + sx * sw / 2, y, z + sz * sw / 2)))
        # ring bars at the top of each segment
        ry = (i + 1) * seg_h - 0.06
        hw = half_width(ry)
        for side in (-1, 1):
            add(box(hw * 2, 0.08, 0.08, dim(col, 0.8), center=(x, ry, z + side * hw),
                    skip=("left", "right")))
            add(box(0.08, 0.08, hw * 2, dim(col, 0.8), center=(x + side * hw, ry, z),
                    skip=("front", "back")))
    # whip
    add(box(0.08, 3.0, 0.08, dim(col, 1.15), center=(x, h + 1.5, z)))
    # dish, on one side at 70% height
    dw = half_width(h * 0.7)
    add(box(1.2, 1.2, 0.3, P.SLATE_HI, center=(x + dw + 0.5, h * 0.7, z),
            cols={"front": P.STEEL, "back": dim(col, 0.9)}))
    ys = [h + 3.0, h * 2 / 3, h / 3]
    for ly in ys:
        hw = half_width(min(ly, h))
        _beacons(add, x, z, ly, hw * 2)
    return [(x, ly, z) for ly in ys]


def water_tower(add, x, z, h=14.0, col=(38, 42, 50)) -> None:
    """A Rozhnovsky tower: brick shaft, a fat tank, a stepped roof.

    One lit window on the shaft is the only warm point, so the tower reads
    as inhabited from across the yard.
    """
    shaft_w = 3.0
    tank_h = 3.5
    roof_h = 1.2
    shaft_h = h - tank_h - roof_h - 0.4
    add(box(shaft_w, shaft_h + 0.4, shaft_w, col, center=(x, (shaft_h + 0.4) / 2, z),
            seg=5))
    # a plinth where the shaft leaves the ground
    add(box(shaft_w + 0.4, 0.4, shaft_w + 0.4, dim(col, 0.8),
            center=(x, 0.2, z)))
    tank_y = shaft_h + 0.4 + tank_h / 2
    add(box(6.0, tank_h, 6.0, dim(col, 1.1), center=(x, tank_y, z), seg=6))
    rim = 0.4
    for sx, sz in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        add(box(abs(sx) * 6.4 + abs(sz) * 0.3, rim, abs(sz) * 6.4 + abs(sx) * 0.3,
                dim(col, 0.75),
                center=(x + sx * 3.05, tank_y + tank_h / 2 - rim / 2, z + sz * 3.05)))
    # stepped roof: two shrinking slabs then a snow cap
    ry = shaft_h + 0.4 + tank_h
    add(box(5.4, 0.6, 5.4, dim(col, 0.9), center=(x, ry + 0.3, z)))
    add(box(3.6, 0.6, 3.6, dim(col, 0.9), center=(x, ry + 0.9, z)))
    add(box(3.8, 0.12, 3.8, P.SNOW_DIM, center=(x, ry + 1.26, z)))
    # one warm window on the shaft, on the +z face
    add(box(0.7, 0.9, 0.05, WINDOW_WARM,
            center=(x, shaft_h * 0.6, z + shaft_w / 2 + 0.02), emissive=True))
