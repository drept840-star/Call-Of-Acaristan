"""Prefab Soviet panel blocks for the Bloc district.

A panel block is noise, not architecture: the same slab of concrete, a grid of
windows and a few floors where the lights are all out. Every choice comes from
``_hash`` on the block's seed, so a district built from the same seed is the
same district on every load.
"""
from __future__ import annotations

from engine3d import tex
from engine3d.core import box

from missions.m6 import palette3d as P

from .colours import *  # noqa: F401,F403  (WINDOW_*)
from .colours import _hash, dim, only

FLOOR_H = 2.8
COL_W = 1.6
WIN_W, WIN_H = 0.9, 1.1
WIN_OUT = 0.03          # how far a window pane sits proud of the wall

# facing name -> (outward unit in xz, reading/lateral unit in xz)
_FACES = {
    "+z": ((0, 1), (1, 0)),
    "-z": ((0, -1), (1, 0)),
    "+x": ((1, 0), (0, -1)),
    "-x": ((-1, 0), (0, -1)),
}


def _lateral(facing):
    """Return (lateral vector, front offset, front-side name) for ``facing``."""
    out, lat = _FACES[facing]
    side = {"+z": "front", "-z": "back", "+x": "right", "-x": "left"}[facing]
    return lat, out, side


def _span(w, d, facing):
    """Half-extent along the facing's normal and along its lateral axis."""
    if facing in ("+z", "-z"):
        return d / 2, w / 2
    return w / 2, d / 2


def panel_block(add, cx, cz, w, h, d, facing, seed=0, col=(30, 34, 44), lit=0.32,
                balconies=True, budget=None):
    """One panel block: body, seams, windows, a stairwell and a roof.

    ``facing`` names the decorated face; ``w`` is always the x size and ``d``
    the z size, so a block facing +x is decorated on its narrow side. Returns
    the number of boxes added.
    """
    lat, out, _side = _lateral(facing)
    half_out, half_lat = _span(w, d, facing)
    count = 0
    flat = only(facing)                  # panes, seams: the front face only
    slab = only(facing, "top")           # balcony slabs catch the snow too

    # 1. body, a concrete pour with a darker plinth and roof coping
    add(box(w, h, d, tex("concrete", like=col), center=(cx, h / 2, cz), seg=12,
            cols={"top": P.SNOW_DIM}, skip=("bottom",)))
    add(box(w + 0.08, 0.55, d + 0.08, dim(col, 0.66),
            center=(cx, 0.28, cz), skip=("top", "bottom")))
    count += 2

    def on_face(s, y, off):
        """World centre of a box at lateral ``s``, height ``y``, pushed ``off`` out."""
        return (cx + lat[0] * s + out[0] * (half_out + off), y,
                cz + lat[1] * s + out[1] * (half_out + off))

    # Along the lateral axis, emissive panes are thin in the facing axis.
    def pane(s, y, lw, lh, thick, c, em=True, push=0.0, skip=flat):
        sx = abs(lat[0]) * lw + abs(out[0]) * thick
        sz = abs(lat[1]) * lw + abs(out[1]) * thick
        add(box(sx, lh, sz, c, center=on_face(s, y, push + thick / 2), emissive=em,
                skip=skip))

    floors = max(1, int(h // FLOOR_H))
    n_cols = int((2 * half_lat - COL_W * 0.5) // COL_W) + 1
    cols = [(i - (n_cols - 1) / 2) * COL_W for i in range(n_cols)]

    # 2. panel seams: a dark strip at every floor line, a vertical every other column
    seam = dim(col, 0.7)
    span_l = 2 * half_lat
    for f in range(1, floors + 1):
        add(box(span_l if abs(lat[0]) else 0.05, 0.05, span_l if abs(lat[1]) else 0.05,
                seam, center=on_face(0, f * FLOOR_H, 0.025), skip=flat))
        count += 1
    for i in range(0, len(cols), 2):
        add(box(0.05 if abs(lat[0]) else 0.05, h, 0.05 if abs(lat[1]) else 0.05,
                seam, center=on_face(cols[i] + COL_W / 2, h / 2, 0.025), skip=flat))
        count += 1

    # 3. windows, clustered per floor so some floors are mostly dark.  Unlit
    # panes are still glazed dark, which gives the facade its grid at night.
    stair_col = COL_W / 2       # midway between two window columns
    n_win = 0
    for f in range(floors):
        y = f * FLOOR_H + FLOOR_H * 0.55
        fl = lit * (0.3 + 1.4 * _hash(seed * 31 + f, 7))
        for i, s in enumerate(cols):
            k = seed * 97 + f * 13 + i
            r = _hash(k, 3)
            if budget is not None and n_win >= budget:
                if (i + f) % 2 == 0:
                    pane(s, y, WIN_W, WIN_H, WIN_OUT * 0.45, WINDOW_DARK, False)
                    count += 1
                continue
            if r < fl * 0.75:
                c, em = WINDOW_WARM, True
            elif r < fl:
                c, em = WINDOW_COLD, True
            else:
                if (i + f) % 2 == 0:
                    pane(s, y, WIN_W, WIN_H, WIN_OUT * 0.45, WINDOW_DARK, False)
                    count += 1
                continue
            pane(s, y, WIN_W, WIN_H, WIN_OUT, c, em)
            add(box(0.06, WIN_H + 0.16, 0.06, dim(col, 0.62),
                    center=on_face(s - WIN_W * 0.58, y, 0.035), skip=flat))
            add(box(0.06, WIN_H + 0.16, 0.06, dim(col, 0.62),
                    center=on_face(s + WIN_W * 0.58, y, 0.035), skip=flat))
            n_win += 1
            count += 3

    # Pilasters every other bay: a panel block has a vertical rhythm, not a
    # single window-wallpaper pattern.
    for i in range(0, len(cols) + 1, 2):
        s = cols[i] - COL_W / 2 if i < len(cols) else cols[-1] + COL_W / 2
        add(box(0.14, h - 0.55, 0.10, dim(col, 0.82),
                center=on_face(s, (h - 0.55) / 2 + 0.55, 0.035), skip=flat))
        count += 1

    # Ground-floor entrance with a concrete canopy and one warm bulb.
    if floors >= 2 and _hash(seed, 29) < 0.72:
        ent = cols[len(cols) // 2] if cols else 0.0
        pane(ent, 1.05, 1.25, 1.95, 0.05, (32, 34, 38), False, push=0.02)
        add(box(2.25, 0.16, 0.72, dim(col, 0.72),
                center=on_face(ent, 2.16, 0.36), skip=flat))
        add(box(0.26, 0.12, 0.16, (255, 205, 126),
                center=on_face(ent, 2.03, 0.54), emissive=True))
        count += 3

    # 4. stairwell: a thin column of small lit windows on every floor
    stair_s = cols[0] + stair_col if len(cols) > 1 else stair_col
    for f in range(floors):
        y = f * FLOOR_H + FLOOR_H * 0.55
        if _hash(seed + f, 11) < 0.8:
            pane(stair_s, y, 0.5, 0.8, WIN_OUT, (200, 150, 80), True)
            count += 1

    # 5. balconies on every other column, first floor up, ~25% missing
    if balconies:
        par = dim(col, 0.85)
        for f in range(1, floors):
            y = f * FLOOR_H
            for i in range(0, len(cols), 2):
                if _hash(seed * 17 + f * 7 + i, 5) < 0.25:
                    continue
                s = cols[i]
                pane(s, y, 1.2, 0.12, 0.7, par, False, skip=slab)
                pane(s, y + 0.51, 1.2, 0.9, 0.06, par, False, push=0.64)
                count += 2

    # 6. roof: parapet rim, snow cap, lift rooms
    rim = 0.4
    top_y = h + rim / 2
    add(box(w, rim, 0.4, dim(col, 0.9), center=(cx, top_y, cz - d / 2 + 0.2)))
    add(box(w, rim, 0.4, dim(col, 0.9), center=(cx, top_y, cz + d / 2 - 0.2)))
    add(box(0.4, rim, d - 0.8, dim(col, 0.9), center=(cx - w / 2 + 0.2, top_y, cz)))
    add(box(0.4, rim, d - 0.8, dim(col, 0.9), center=(cx + w / 2 - 0.2, top_y, cz)))
    count += 4
    add(box(w - 0.8, 0.12, d - 0.8, P.SNOW_DIM, center=(cx, h + 0.06, cz)))
    count += 1
    rooms = 1 if _hash(seed, 23) < 0.5 else 2
    for r in range(rooms):
        sx = cx + (lat[0] * (2.0 if r else -2.0) if w > 6 else 0.0)
        lw, ld = min(3.0, w * 0.4), min(2.5, d * 0.4)
        add(box(lw, 1.6, ld, dim(col, 0.9), center=(sx, h + 0.8, cz)))
        add(box(lw + 0.2, 0.12, ld + 0.2, P.SNOW_DIM, center=(sx, h + 1.66, cz)))
        count += 2
    if h > 15.0 and _hash(seed, 31) < 0.6:
        ax = cx + lat[0] * (half_lat * 0.45)
        az = cz + lat[1] * (half_lat * 0.45)
        add(box(0.08, 3.0, 0.08, dim(col, 1.05), center=(ax, h + 1.5, az)))
        add(box(1.4, 0.06, 0.06, dim(col, 1.05), center=(ax, h + 2.35, az)))
        add(box(0.06, 0.06, 1.0, dim(col, 1.05), center=(ax, h + 2.05, az)))
        count += 3

    return count


def roof_sign_pos(cx, cz, w, h, d, facing):
    """Where a rooftop slogan stands: on the roof, 0.6 m in from the front edge.

    The y is 2.0 m above the roofline, which puts the letters' centre where a
    letter is first seen against the sky from the street.
    """
    lat, out, _side = _lateral(facing)
    del lat
    half_out, _hl = _span(w, d, facing)
    off = half_out - 0.6
    return ((cx + out[0] * off, h + 2.0, cz + out[1] * off), facing)
