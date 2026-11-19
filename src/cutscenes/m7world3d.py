"""Mission 7 farm: shared 3D builder for the drop-off, finale and raid.

Axes: x east, y up, z north. Scenes are viewed from -z.
Flat late-PS2 colours, hard edges and blocky forms.

Fire uses animated, low-resolution layered tongues, rising embers, stepped
translucent smoke and restrained light spill. No external fire assets needed.

Background buildings are seated into the faceted hills on stone plinths that
never extend below the visible ground, and the southern road runs through a
single depth-tested corridor mesh (valley, ridge notch and crest) instead of
overlays painted over the background ridge.
"""
from collections import OrderedDict
import io
import json
import math
import os
import struct
from functools import lru_cache

import pygame

from engine3d.core import Light, Mesh, box, prism, quad_xz, rot_x, rot_y, rot_z, v_cross, v_dot, v_sub
from engine3d.rig import POSES
from engine3d.textures import Tex, tex
from cutscenes import m6fx3d as _fx
from cutscenes import m6world3d as _w
from cutscenes import m7palette3d as P


GRASS = P.GRASS
STUBBLE = P.HAY_D
FURROW = P.LOAM
DIRT = P.DIRT
TRACK = P.TRACK
WOOD = P.WOOD_MID
WOOD_D = P.WOOD_D
PLASTER = P.PLASTER
PLASTER_N = (158, 136, 102)
PLASTER_B = (88, 80, 72)
TILE = P.ROOF
TILE_B = (52, 40, 36)
BARN = P.BARN
BARN_B = (78, 46, 42)
TRIM = P.PLASTER
ROOF_METAL = P.GALV_D
STONE = P.STONE
HAY = P.HAY
LEAF = (74, 96, 58)
LEAF2 = P.GRASS_HI
TRUNK = (96, 78, 58)
WIN = (28, 36, 48)
WIN_LIT = P.WINDOW
EMBER = (255, 120, 40)
TRACT = P.TRACTOR
TRACT_D = P.TRACTOR_D
RUB = P.INK
HUB = P.HAY_MID
METAL = P.GALV_D
RUST = P.RUST
HILL_N = (36, 46, 38)
HILL_F = (48, 58, 70)
SKYLINE = (22, 26, 32)
FAR_WALL = (136, 112, 82)

_GROUND_TEX = ("grass", "stubble", "furrow", "dirt", "track")


def _t(name, col, tint=False):
    """M7 texture at ground or prop density."""
    return tex(
        "m7_" + name, like=col, tint=tint,
        density=16.0 if name in _GROUND_TEX else 32.0)


TRACTOR_AT = {False: (-16.0, -3.0), True: (2.0, -3.0)}
TRACTOR_YAW = {False: -90, True: -54}
MOTORCYCLE_AT = (16.75, -6.4, 100.0)
MOTORCYCLE_BOX = (16.25, -7.45, 17.25, -5.35, 1.1)
SEAT_BURN = (1.62, 1.51, -3.53)
SEAT_H = 0.48

LOOKS = {
    "dawn": dict(
        fog=(196, 178, 166), fog_start=9.0, fog_end=96.0,
        light=dict(
            direction=(0.72, 0.30, 0.42), ambient=0.50, diffuse=0.62,
            sky=0.10, tint=(1.0, 0.84, 0.70)),
        sky_top=(92, 116, 152), sky_bot=(234, 186, 150),
        sodium=(96, 62, 38), stars=0),
    "night": dict(
        fog=(10, 13, 20), fog_start=10.0, fog_end=90.0,
        light=dict(
            direction=(-0.3, 0.7, -0.4), ambient=0.30, diffuse=0.34,
            sky=0.10, tint=(0.66, 0.74, 1.0)),
        sky_top=(5, 8, 16), sky_bot=(20, 26, 44),
        sodium=(30, 20, 14), stars=60),
    "raid": dict(
        fog=(22, 29, 46), fog_start=34.0, fog_end=250.0,
        light=dict(
            direction=(-0.42, 0.50, -0.72), ambient=0.36, diffuse=0.72,
            sky=0.12, tint=(0.72, 0.83, 1.0)),
        sky_top=(6, 9, 18), sky_bot=(30, 40, 64),
        sodium=None, stars=90, moon=(-150.0, 15.0)),
    "burn": dict(
        fog=(26, 16, 16), fog_start=8.0, fog_end=96.0,
        light=dict(
            direction=(-0.3, 0.7, -0.4), ambient=0.30, diffuse=0.32,
            sky=0.10, tint=(0.70, 0.70, 0.92)),
        sky_top=(8, 8, 16), sky_bot=(58, 28, 24),
        sodium=(120, 54, 24), stars=34),
}


def _v(col, k):
    out = tuple(max(0, min(255, int(c + k))) for c in col)
    return col.with_rgb(out) if isinstance(col, Tex) else out


def _vary(base, amp):
    def f(i, j):
        h = (i * 73856093 ^ j * 19349663) & 0xFF
        return _v(base, (h % 9 - 4) * amp)
    return f


def _gable_z(w, d, y0, rise, roof, wall, oh=0.3, slopes=("l", "r")):
    """Gable roof with its ridge along z."""
    m = Mesh()
    w2, d2 = w / 2.0, d / 2.0
    ex = w2 + oh
    ey = y0 - oh * rise / w2
    zf, zb = -d2 - oh * 0.6, d2 + oh * 0.6
    if "l" in slopes:
        m.face([
            (-ex, ey, zf), (-ex, ey, zb),
            (0, y0 + rise, zb), (0, y0 + rise, zf)],
            roof, 2, True)
    if "r" in slopes:
        m.face([
            (ex, ey, zf), (0, y0 + rise, zf),
            (0, y0 + rise, zb), (ex, ey, zb)],
            _v(roof, -10), 2, True)
    for z in (-d2, d2):
        m.face([
            (-w2, y0, z), (w2, y0, z), (0, y0 + rise, z)],
            wall, 2, True)
    return m


def _bipyr(cx, cy, cz, r, up, dn, col, col2=None, n=6, moon=False):
    m = Mesh()
    ring = [
        (cx + r * math.cos(math.tau * i / n),
         cy, cz + r * math.sin(math.tau * i / n))
        for i in range(n)]
    top, bot = (cx, cy + up, cz), (cx, cy - dn, cz)
    for i in range(n):
        a, b = ring[i], ring[(i + 1) % n]
        shade = 0
        if moon:
            ang = math.tau * (i + 0.5) / n
            shade = 12 if (
                math.cos(ang) * -0.504 + math.sin(ang) * -0.864 > 0.2
            ) else 0
        m.face([a, b, top], _v(col, shade), 2, True)
        m.face([b, a, bot], _v(col2 or _v(col, -22), shade), 2, True)
    return m


def _fence(x0, z0, x1, z1, h=1.15, every=2.4, col=None, gap=None):
    """Axis-aligned post-and-rail fence; gap uses world coordinates."""
    m = Mesh()
    col = _t("plank", col or WOOD)
    along_x = abs(z1 - z0) < 1e-6
    length = abs(x1 - x0) if along_x else abs(z1 - z0)
    n = max(1, int(round(length / every)))
    pts = [
        (x0 + (x1 - x0) * i / float(n),
         z0 + (z1 - z0) * i / float(n))
        for i in range(n + 1)]

    def in_gap(p):
        if not gap:
            return False
        v = p[0] if along_x else p[1]
        return gap[0] < v < gap[1]

    for p in pts:
        if not in_gap(p):
            m.add(box(0.14, h, 0.14, col, center=(p[0], h / 2, p[1])))
    for a, b in zip(pts[:-1], pts[1:]):
        if in_gap(a) or in_gap(b):
            continue
        cx, cz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        sx = abs(b[0] - a[0]) or 0.06
        sz = abs(b[1] - a[1]) or 0.06
        for yy in (h * 0.42, h * 0.86):
            m.add(box(sx, 0.07, sz, col, center=(cx, yy, cz)))
    return m


def ground():
    return [
        quad_xz(-400, -400, 400, 400, 0.0, _t("grass", GRASS), layer=0, seg=40),
        quad_xz(-46, -12, -26, 34, 0.02, _t("stubble", STUBBLE), layer=1, seg=12),
        quad_xz(-64, -12, -46, 34, 0.02, _t("furrow", P.TRACK_D), layer=1, seg=12),
        quad_xz(-20, -16, 20, 22, 0.02, _t("dirt", DIRT), layer=1, seg=8),
        quad_xz(-3.2, -100, 3.2, -16, 0.04, _t("track", TRACK), layer=1, seg=16),
        quad_xz(-7, -16, 7, -8, 0.04, _t("track", TRACK), layer=1, seg=4),
    ]


HILL_RAD = (84.0, 118.0)


def _hill_h(a, ring=0):
    return (
        (7.0, 14.0)[ring] + 3.5 * math.sin(a * 3 + ring)
        + 2.2 * math.sin(a * 7 + 1.3 * ring))


def hills():
    """Depth-tested faceted hills, open around the southern road."""
    m = Mesh()
    n = 60
    south = 1.5 * math.pi
    cut, shoulder = math.radians(5), math.radians(14)
    for ring, col in enumerate((_t("grass", HILL_N), _t("grass", HILL_F))):
        rad = HILL_RAD[ring]
        angles = [math.tau * i / n for i in range(n + 1)]
        angles.extend((south - cut, south + cut))
        angles.sort()
        rows = []
        for a in angles:
            da = abs((a - south + math.pi) % math.tau - math.pi)
            u = max(0.0, min(1.0, (da - cut) / (shoulder - cut)))
            u = u * u * (3 - 2 * u)
            h = _hill_h(a, ring) * u
            c, s = math.cos(a), math.sin(a)
            rows.append((
                ((rad - 9) * c, -0.5, (rad - 9) * s),
                ((rad - 4) * c, h * 0.43, (rad - 4) * s),
                (rad * c, h, rad * s),
                ((rad + 8) * c, -0.5, (rad + 8) * s)))
        for i in range(len(angles) - 1):
            a = (angles[i] + angles[i + 1]) * 0.5
            da = abs((a - south + math.pi) % math.tau - math.pi)
            if da < cut:
                continue
            lo0, mid0, top0, back0 = rows[i]
            lo1, mid1, top1, back1 = rows[i + 1]
            shade = (((i * 73) ^ (i * 131 + ring * 17)) & 7) - 3
            m.face([lo0, lo1, mid1], _v(col, shade - 3), 2, True)
            m.face([lo0, mid1, mid0], _v(col, shade - 1), 2, True)
            m.face([mid0, mid1, top1], _v(col, shade + 1), 2, True)
            m.face([mid0, top1, top0], _v(col, shade + 3), 2, True)
            m.face([top0, top1, back1, back0], _v(col, shade - 6), 2, True)
    return m


def house(lit=False, burn=False):
    m = Mesh()
    W, D, H = 9.0, 6.0, 3.0
    wall = PLASTER_B if burn else _t("plaster", PLASTER_N if lit else PLASTER)
    plank = _t("plank", WOOD)
    m.add(box(W, H, D, wall, center=(0, H / 2, 0)))
    m.add(box(W + 0.08, 0.42, D + 0.08, _t("stone", P.STONE_D),
              center=(0, 0.21, 0)))
    m.add(_gable_z(
        D, W, H, 1.9, TILE_B if burn else _t("tile", TILE), wall), rot_y(90))
    m.add(box(0.7, 1.8, 0.7, _t("stone", STONE), center=(2.6, H + 1.2, 0.5)))
    m.add(box(0.86, 0.12, 0.86, P.STONE_D, center=(2.6, H + 2.16, 0.5)))
    zf = -D / 2 - 0.04
    shutter = _t("plank", P.TRACTOR_D, tint=True)
    for x in (-3.0, -0.8, 3.6):
        m.add(box(1.25, 1.15, 0.06, TRIM, center=(x, 1.75, zf)))
        m.add(box(0.95, 0.85, 0.06, WIN_LIT if lit else WIN,
                  center=(x, 1.75, zf - 0.06), emissive=lit))
        m.add(box(1.4, 0.08, 0.2, plank, center=(x, 1.13, zf - 0.08)))
        for sx in (-0.76, 0.76):
            m.add(box(0.26, 1.15, 0.05, shutter,
                      center=(x + sx, 1.75, zf - 0.03)))
    m.add(box(1.0, 2.1, 0.08, _t("plank", WOOD_D), center=(1.6, 1.05, zf)))
    for sz in (-1.0, 1.0):
        m.add(box(W + 0.6, 0.12, 0.14, P.GALV_D, center=(0, 2.74, sz * 3.36)))
        m.add(box(0.1, 2.7, 0.1, P.GALV_D, center=(-4.55, 1.37, sz * 3.38)))
    m.add(box(5.0, 0.25, 1.6, plank, center=(1.0, 0.12, -D / 2 - 0.8)))
    for x in (-1.3, 3.3):
        m.add(box(0.14, 2.6, 0.14, plank, center=(x, 1.5, -D / 2 - 1.5)))
    for x0, x1 in ((-1.3, 0.9), (2.3, 3.3)):
        for yy in (0.95, 0.55):
            m.add(box(x1 - x0, 0.07, 0.07, plank,
                      center=((x0 + x1) / 2, yy, -D / 2 - 1.5)))
    m.face([
        (-1.6, 2.7, -D / 2 - 1.7), (3.6, 2.7, -D / 2 - 1.7),
        (3.6, 3.1, -D / 2), (-1.6, 3.1, -D / 2)],
        _t("tin", ROOF_METAL), 2, True)
    m.add(box(1.4, 0.12, 0.5, plank, center=(1.6, 0.04, -D / 2 - 1.85)))
    m.add(box(1.4, 0.42, 0.38, plank, center=(-0.6, 0.45, -D / 2 - 0.35)))
    if not burn:
        # Household first aid on the porch's existing storage chest; never loose
        # bottles on the yard floor, nor a new health interaction.
        from game.scenery3d import medical_supplies
        m.add(medical_supplies(), rot_y(180), t=(-0.6, 0.66, -D / 2 - 0.35))
    m.add(box(0.05, 0.3, 0.05, P.STEEL_D, center=(2, 2.84, -D / 2 - 0.4)))
    if lit:
        m.add(box(0.16, 0.14, 0.16, P.LAMP_WARM,
                  center=(2, 2.63, -D / 2 - 0.4), emissive=True))
    return m


PORCH_LAMP = (-10.0, 2.63, 6.6)
BARN_LAMP = (9.0, 3.94, 6.37)


def barn(burn=False, lamp=False):
    m = Mesh()
    W, D, H = 12.0, 10.0, 4.8
    side = BARN_B if burn else _t("barnboard", BARN)
    door = _t("plank", WOOD_D)
    m.add(box(W, H, D, side, center=(0, H / 2, 0)))
    zf = -D / 2 - 0.03
    if burn:
        # Dark orange interiors keep the animated flames brighter than
        # the openings, rather than making the doors a flat neon panel.
        m.add(box(5.0, 3.6, 0.1, (126, 36, 14),
                  center=(0, 1.8, zf), emissive=True))
        m.add(box(1.6, 1.6, 0.1, (164, 53, 16),
                  center=(0, H + 1.1, zf), emissive=True))
        m.add(_gable_z(W, D, H, 3.0, TILE_B, side, slopes=()))
    else:
        m.add(box(5.0, 3.6, 0.1, door, center=(0, 1.8, zf)))
        for sx in (-1.25, 1.25):
            for ang in (40, -40):
                brace = Mesh()
                brace.add(box(0.14, 4.1, 0.05, _t("plank", P.WOOD_L)),
                          rot_z(ang))
                m.add(brace, t=(sx, 1.8, zf - 0.03))
        for x in (-2.6, 2.6):
            m.add(box(0.2, 3.7, 0.12, _t("plank", P.WOOD_L),
                      center=(x, 1.85, zf - 0.02)))
        m.add(box(5.4, 0.2, 0.12, _t("plank", P.WOOD_L),
                  center=(0, 3.7, zf - 0.02)))
        m.add(box(1.6, 1.6, 0.1, door, center=(0, H + 1.1, zf)))
        m.add(box(1.9, 0.16, 0.12, _t("plank", P.WOOD_L),
                  center=(0, H + 1.95, zf - 0.02)))
        m.add(_gable_z(W, D, H, 3, _t("tin", P.GALV), side))
        if lamp:
            m.add(box(0.08, 0.08, 0.62, P.STEEL_D,
                      center=(-4, 4.12, zf - 0.3)))
            m.add(box(0.52, 0.1, 0.52, P.STEEL_D,
                      center=(-4, 4.06, zf - 0.6)))
            m.add(box(0.2, 0.12, 0.2, P.LAMP_WARM,
                      center=(-4, 3.95, zf - 0.6), emissive=True))
    return m


# ---- M8 ruin: Bodi's farm the morning after the fire (no emissive, M7 burn untouched) ----
RUIN_CHAR = (34, 28, 26)
RUIN_SOOT = (20, 18, 18)
RUIN_ASH = (66, 62, 58)
RUIN_VOID = (8, 8, 10)


def _rbox(m, w, h, d, col, pos, rot=None):
    """Box centred on ``pos``, optionally tilted about its own centre."""
    b = box(w, h, d, col)
    if rot:
        m.add(b, rot, pos)
    else:
        m.add(b, t=pos)


def _scorch(m, rects):
    """Hard-edged scorched ground: stacked dark dirt and ash rectangles."""
    dirt, ash = _t("dirt", (44, 38, 34)), _t("dirt", RUIN_ASH)
    for i, (x0, z0, x1, z1) in enumerate(rects):
        m.add(quad_xz(x0, z0, x1, z1, 0.05 + 0.01 * i, ash if i % 2 else dirt, layer=1, seg=4.0))


def _ruin_wall(m, u0, u1, v, t, h, holes, col, along_x, inn, drops=(0.0,)):
    """Burnt wall of boxes: ragged top, scorched base and cap, black openings
    (hc, hw, y0, y1) with a soot streak above each."""
    def put(ua, ub, ya, yb, c, th, off=0.0):
        if ub - ua < 0.02 or yb - ya < 0.02:
            return
        mu, my = (ua + ub) / 2, (ya + yb) / 2
        if along_x:
            _rbox(m, ub - ua, yb - ya, th, c, (mu, my, v + off))
        else:
            _rbox(m, th, yb - ya, ub - ua, c, (v + off, my, mu))

    def drop(u):
        return drops[int(math.floor(u / 1.5)) % len(drops)]

    char = _t("plank", RUIN_CHAR)
    pieces, cur = [], u0
    for hc, hw, y0, y1 in sorted(holes):
        a, b = hc - hw / 2, hc + hw / 2
        pieces.append((cur, a, 0.0, None))
        if y0 > 0:
            pieces.append((a, b, 0.0, y0))
        pieces.append((a, b, y1, None))
        cur = b
    pieces.append((cur, u1, 0.0, None))
    for ua, ub, ya, yb in pieces:
        if yb is not None:
            put(ua, ub, ya, yb, col, t)
            if ya == 0.0:
                put(ua, ub, 0.0, min(0.55, yb), char, t + 0.04)
            continue
        edges = sorted({ua, ub} | {k * 1.5 for k in range(int(ua // 1.5) + 1, int(ub // 1.5) + 1)
                                   if ua < k * 1.5 < ub})
        for a, b in zip(edges[:-1], edges[1:]):
            top = max(h - drop((a + b) / 2), ya + 0.3)
            put(a, b, ya, top, col, t)
            put(a, b, top - 0.3, top, char, t + 0.04)
            if ya == 0.0:
                put(a, b, 0.0, 0.55, char, t + 0.04)
    for hc, hw, y0, y1 in holes:
        put(hc - hw / 2, hc + hw / 2, y0, y1, RUIN_VOID, t * 0.5, inn * t * 0.25)
        st = max(y1 + 0.4, min(y1 + 1.7, h - drop(hc) - 0.1))
        mid = y1 + (st - y1) * 0.55
        put(hc - hw * 0.35, hc + hw * 0.35, y1, mid, RUIN_SOOT, t + 0.06)
        put(hc - hw * 0.18, hc + hw * 0.18, mid, st, RUIN_SOOT, t + 0.06)


def _ruin_panels(m, spans, v, along_x, hs, col, step=1.1, th=0.12):
    """Barn wall as upright boards; height 0 is a missing board (sky shows)."""
    k = 0
    char = _t("plank", RUIN_CHAR)
    for ua, ub in spans:
        n = max(1, int(round((ub - ua) / step)))
        for i in range(n):
            a, b = ua + (ub - ua) * i / n, ua + (ub - ua) * (i + 1) / n
            h = hs[k % len(hs)]
            k += 1
            if h < 0.2:
                continue
            mu = (a + b) / 2
            for ya, yb, c, tt in ((0.0, h, col, th), (0.0, min(0.4, h), char, th + 0.04),
                                  (max(0.0, h - 0.3), h, char, th + 0.04)):
                if along_x:
                    _rbox(m, b - a - 0.02, yb - ya, tt, c, (mu, (ya + yb) / 2, v))
                else:
                    _rbox(m, tt, yb - ya, b - a - 0.02, c, (v, (ya + yb) / 2, mu))


def house_ruin():
    """Bodi's house after the fire: black openings, rafters against the sky, no glow."""
    m = Mesh()
    W, D, H, t = 9.0, 6.0, 3.0, 0.35
    wall = _t("plaster", (104, 96, 88))
    char = _t("plank", RUIN_CHAR)
    stone = _t("stone", (62, 58, 54))
    _rbox(m, W + 0.08, 0.42, D + 0.08, stone, (0, 0.21, 0))
    _rbox(m, W - 0.7, 0.1, D - 0.7, RUIN_ASH, (0, 0.47, 0))
    win = (1.2, 2.3)
    _ruin_wall(m, -W / 2, W / 2, -D / 2 + t / 2, t, H,
               [(-3.0, 1.0, *win), (-0.8, 1.0, *win), (3.6, 1.0, *win), (1.6, 1.0, 0.0, 2.1)],
               wall, True, 1)
    _ruin_wall(m, -W / 2, W / 2, D / 2 - t / 2, t, H,
               [(-2.4, 1.0, *win), (2.0, 1.0, *win)], wall, True, -1, (0.0, 0.4, 0.0, 1.1, 0.6))
    _ruin_wall(m, -D / 2 + t, D / 2 - t, W / 2 - t / 2, t, H,
               [(0.0, 1.0, *win)], wall, False, -1)
    _ruin_wall(m, -D / 2 + t, D / 2 - t, -W / 2 + t / 2, t, H, [], wall, False, 1, (1.2, 0.0, 0.0, 1.0))
    # gables: the east one stands, the west one is half down
    m.face([(W / 2, H, -D / 2), (W / 2, H, D / 2), (W / 2, H + 1.9, 0)], char, 2, True)
    m.face([(-W / 2, H, -3.0), (-W / 2, H, -1.5), (-W / 2, H + 0.95, -1.5)], char, 2, True)
    m.face([(-W / 2, H, 1.5), (-W / 2, H, 3.0), (-W / 2, H + 0.95, 1.5)], char, 2, True)
    # chimney stands whole, shaft down to the floor
    _rbox(m, 0.7, H - 0.1, 0.7, _t("stone", STONE), (2.6, 1.85, 0.5))
    _rbox(m, 0.7, 1.8, 0.7, _t("stone", STONE), (2.6, H + 1.2, 0.5))
    _rbox(m, 0.86, 0.12, 0.86, P.STONE_D, (2.6, H + 2.16, 0.5))
    # roof frame: standing ridge, a few rafters, a purlin; one end fallen
    ang = math.degrees(math.atan2(1.9, 2.9))
    ln = math.hypot(2.9, 1.9)
    _rbox(m, 7.0, 0.22, 0.22, char, (1.25, H + 1.9, 0))
    _rbox(m, 2.4, 0.2, 0.2, char, (-3.2, H + 1.0, 0.2), rot_z(-26))
    for i, x in enumerate((-1.8, -0.6, 0.6, 1.8, 3.0, 4.2)):
        if i != 1 and i != 4:
            _rbox(m, 0.14, 0.14, ln, char, (x, H + 0.95, -1.45), rot_x(-ang))
        if i in (0, 3, 5):
            _rbox(m, 0.14, 0.14, ln, char, (x, H + 0.95, 1.45), rot_x(ang))
    _rbox(m, 7.0, 0.1, 0.1, char, (1.25, H + 0.95, -1.45))
    # porch: charred deck, one broken post, the tin canopy down on the boards
    _rbox(m, 5.0, 0.25, 1.6, char, (1.0, 0.12, -D / 2 - 0.8))
    _rbox(m, 0.14, 1.3, 0.14, char, (-1.3, 0.9, -D / 2 - 1.5), rot_z(8))
    _rbox(m, 0.14, 2.6, 0.14, char, (3.3, 1.5, -D / 2 - 1.5))
    _rbox(m, 4.6, 0.08, 1.9, _t("tin", (74, 70, 66)), (0.8, 0.62, -D / 2 - 1.5), rot_x(10))
    # debris inside and out
    for w, h, d, p, r in ((1.4, 0.4, 1.0, (-2.0, 0.7, 0.3), None), (0.8, 0.3, 0.6, (-1.8, 1.05, 0.2), rot_y(25)),
                          (1.0, 0.3, 1.2, (0.4, 0.65, -1.0), rot_y(-15)), (0.8, 0.5, 0.8, (3.4, 0.75, 1.4), None),
                          (3.2, 0.16, 0.16, (-1.0, 0.62, 1.5), rot_y(20)), (3.0, 0.16, 0.16, (1.0, 0.62, -0.4), rot_y(-35)),
                          (3.4, 0.2, 0.2, (-6.2, 0.1, 0.5), rot_y(70)), (2.8, 0.2, 0.2, (5.9, 0.1, -2.6), rot_y(-20)),
                          (1.2, 0.35, 0.9, (-5.6, 0.18, -3.0), None), (2.4, 0.18, 0.18, (-4.8, 0.1, 4.4), rot_y(15))):
        _rbox(m, w, h, d, char, p, r)
    _scorch(m, [(-7.0, -7.4, 7.0, 4.6), (-5.4, -5.6, 5.8, 3.8), (-8.2, -2.0, -5.0, 3.0), (-3.0, 4.4, 2.0, 6.6)])
    return m


def barn_ruin():
    """Bodi's barn after the fire: post frame, gaps in the boards, east wall down inside."""
    m = Mesh()
    W, D, H = 12.0, 10.0, 4.8
    char = _t("plank", RUIN_CHAR)
    board = _t("barnboard", (54, 38, 34))
    _rbox(m, W - 0.6, 0.1, D - 0.6, RUIN_ASH, (0, 0.07, 0))
    for x, z, h in ((-5.9, -4.9, H), (5.9, -4.9, 3.4), (-5.9, 4.9, H), (5.9, 4.9, 2.6), (-2.5, -4.9, H),
                    (2.5, -4.9, H - 0.4), (-5.9, -1.6, H), (-5.9, 1.7, 3.1), (5.9, 1.7, 1.2), (-2.0, 4.9, H), (2.0, 4.9, 3.6)):
        _rbox(m, 0.36, h, 0.36, char, (x, h / 2, z))
    _rbox(m, 5.4, 0.22, 0.2, char, (-0.1, H - 0.9, -4.95), rot_z(-3))
    _ruin_panels(m, [(-5.7, -2.7), (2.7, 5.7)], -4.94, True, (4.8, 3.1, 0.0, 2.2, 4.8, 0.0, 3.6), board)
    _ruin_panels(m, [(-5.7, 5.7)], 4.94, True, (4.8, 4.8, 2.4, 0.0, 0.0, 3.9, 4.8, 1.6, 0.0, 4.4, 4.8), board)
    _ruin_panels(m, [(-4.7, 4.7)], -5.94, False, (4.8, 0.0, 2.0, 4.4, 4.8, 0.0, 3.0, 4.8, 2.2), board)
    _ruin_panels(m, [(-4.7, 4.7)], 5.94, False, (0.6, 0.0, 1.1, 0.0, 0.4, 0.9, 0.0, 1.3, 0.5), board)
    # east wall fallen inward: a boarded ramp with charred battens
    m.face([(5.9, 0.35, -4.8), (5.9, 0.35, 4.8), (2.4, 0.95, 4.8), (2.4, 0.95, -4.8)], board, 2, True)
    for z in (-4.0, -1.6, 0.8, 3.2):
        m.face([(5.9, 0.38, z), (5.9, 0.38, z + 0.3), (2.4, 0.98, z + 0.3), (2.4, 0.98, z)], char, 2, True)
    # roof frame: ridge half down, bare rafters, tie beams
    ang = math.degrees(math.atan2(3.0, 5.9))
    ln = math.hypot(5.9, 3.0)
    _rbox(m, 0.22, 0.22, 6.4, char, (0.0, H + 3.0, -2.0))
    _rbox(m, 0.22, 0.22, 3.4, char, (0.6, 2.4, 3.3), rot_x(-35))
    for i, z in enumerate((-4.5, -2.7, -0.9, 0.9, 2.7, 4.5)):
        if i in (0, 1, 3, 5):
            _rbox(m, ln, 0.16, 0.16, char, (-2.95, H + 1.5, z), rot_z(ang))
        if i in (1, 4):
            _rbox(m, ln, 0.16, 0.16, char, (2.95, H + 1.5, z), rot_z(-ang))
    for z in (-4.5, -0.9, 2.7):
        _rbox(m, W - 0.2, 0.22, 0.2, char, (0, H - 0.2, z))
    # gable remnants
    m.face([(-6.0, H, -5.0), (-2.0, H, -5.0), (-6.0, H + 2.0, -5.0)], board, 2, True)
    m.face([(3.0, H, 5.0), (6.0, H, 5.0), (3.0, H + 1.5, 5.0)], board, 2, True)
    # debris
    for w, h, d, p, r in ((2.6, 0.3, 1.6, (-2.4, 0.2, 2.2), rot_y(15)), (1.8, 0.4, 1.2, (-1.2, 0.25, -1.6), rot_y(-30)),
                          (3.8, 0.2, 0.2, (-3.0, 0.15, 0.4), rot_y(80)), (4.0, 0.2, 0.2, (1.0, 0.15, 3.4), rot_y(-12)),
                          (3.4, 0.22, 0.22, (-8.2, 0.12, -2.0), rot_y(40)), (2.2, 0.35, 1.4, (8.0, 0.2, 3.0), rot_y(20)),
                          (4.2, 0.2, 0.2, (-6.8, 0.12, 6.4), rot_y(-70))):
        _rbox(m, w, h, d, char, p, r)
    _scorch(m, [(-8.4, -7.4, 8.4, 7.4), (-7.0, -6.0, 7.2, 6.2), (-10.4, -3.0, -8.0, 4.0), (-4.0, -9.6, 3.0, -7.0)])
    return m


def hay(n=3):
    """Angular straw bales with cut ends, bindings and staggered stacking."""
    m = Mesh()
    n = max(0, int(n))

    # Keep hay free of baked-in straps or coloured texture markings.
    # Facet shading and the existing straw marks provide the detail.
    straw = HAY
    ends = P.HAY_MID
    binding = (72, 65, 43)

    length, height, depth = 1.4, 0.7, 0.9
    hx = length * 0.5
    hy = height * 0.5
    hz = depth * 0.5
    bevel = 0.10

    # Clockwise outline in the bale's yz cross-section.
    profile = (
        (-hy + bevel, -hz),
        (hy - bevel, -hz),
        (hy, -hz + bevel),
        (hy, hz - bevel),
        (hy - bevel, hz),
        (-hy + bevel, hz),
        (-hy, hz - bevel),
        (-hy, -hz + bevel),
    )

    def bale(seed):
        b = Mesh()
        shift = ((seed * 37) % 5 - 2) * 3

        # Straw and bindings share one surface: no overlapping strips.
        shades = (-9, -3, 7, 11, 3, -8, -15, -12)
        strap_width = 0.055
        strap_centres = (-0.39, 0.39)

        cuts = [-hx]
        for centre in strap_centres:
            cuts.extend((
                centre - strap_width / 2,
                centre + strap_width / 2,
            ))
        cuts.append(hx)

        for j, (y0, z0) in enumerate(profile):
            y1, z1 = profile[(j + 1) % len(profile)]

            for left, right in zip(cuts, cuts[1:]):
                middle = (left + right) * 0.5
                is_binding = any(
                    abs(middle - centre) < strap_width / 2
                    for centre in strap_centres
                )

                colour = (
                    binding if is_binding
                    else _v(straw, shift + shades[j])
                )

                b.face([
                    (left, y0, z0),
                    (right, y0, z0),
                    (right, y1, z1),
                    (left, y1, z1),
                ], colour, 2, True)

        # Slightly brighter exposed straw on the two cut ends.
        for side in (-1, 1):
            points = [(side * hx, y, z) for y, z in profile]
            if side < 0:
                points.reverse()
            b.face(points, _v(ends, shift + 5), 2, True)

        # A handful of rectangular straw marks—not a noisy hair effect.
        for side in (-1, 1):
            for j in range(7):
                h = (seed * 31 + j * 17) % 23
                yy = -0.20 + 0.065 * (j % 7)
                zz = -0.23 + 0.075 * (h % 7)
                mark = _v(HAY, -24 if j % 3 == 0 else 15)
                b.add(box(
                    0.008, 0.018, 0.10 + 0.025 * (h % 4),
                    mark,
                    center=(side * (hx + 0.006), yy, zz),
                ))

        for j in range(5):
            xx = -0.55 + j * 0.26
            zz = -0.22 + ((seed * 7 + j * 3) % 5) * 0.10
            b.add(box(
                0.14, 0.008, 0.018, _v(HAY, 12),
                center=(xx, hy + 0.006, zz),
            ))

        return b

    for i in range(n):
        level, slot = divmod(i, 2)
        count = min(2, n - level * 2)

        # Centre a lone top bale; leave a small gap between paired bales.
        x = (slot - (count - 1) * 0.5) * (length + 0.045)
        z = 0.045 if level % 2 else -0.025
        yaw = ((i * 7) % 5 - 2) * 1.2

        m.add(
            bale(i),
            rot_y(yaw),
            t=(x, hy + level * (height + 0.012), z),
        )

    return m


def shed():
    m = Mesh()
    m.add(box(3.4, 2.4, 3.0, _t("plank", WOOD), center=(0, 1.2, 0)))
    m.face([
        (-1.9, 2.3, -1.7), (1.9, 2.3, -1.7),
        (1.9, 2.9, 1.7), (-1.9, 2.9, 1.7)],
        _t("tin", ROOF_METAL), 2, True)
    m.add(box(1.1, 1.9, 0.08, _t("plank", WOOD_D), center=(0.5, 0.95, -1.54)))
    for sx in (-0.4, 0.4):
        for sz in (-0.4, 0.4):
            m.add(box(0.12, 1.1, 0.12, _t("plank", WOOD_D),
                      center=(3.4 + sx, 0.55, sz)))
    rust = tex("rust", like=RUST, tint=True)
    m.add(box(1.3, 0.8, 1.3, rust, center=(3.4, 1.5, 0)))
    for i in range(3):
        m.add(box(0.5, 0.85, 0.5, _v(rust, 14 * i - 14),
                  center=(-2.5, 0.43, -0.6 + 0.65 * i)))
    return m


def well(roof=True):
    m = Mesh()
    st = _t("stone", STONE)
    for sz in (-0.65, 0.65):
        m.add(box(1.7, 0.7, 0.35, st, center=(0, 0.35, sz)))
    for sx in (-0.65, 0.65):
        m.add(box(0.35, 0.7, 1.7, st, center=(sx, 0.35, 0)))
    m.add(box(0.9, 0.02, 0.9, (24, 34, 44), center=(0, 0.52, 0)))
    if roof:
        m.add(well_roof())
    return m


def well_roof():
    """The well's posts, crossbeam, tin roof and bucket, in the well's own frame."""
    m = well_frame()
    tin = _t("tin", ROOF_METAL)
    for quad in WELL_TIN:
        m.face(list(quad), tin, 2, True)
    m.add(box(0.02, 0.9, 0.02, WOOD_D, center=(0, 1.85, 0)))
    m.add(well_bucket(), t=(0, 1.3, 0))
    return m


# the two tin panels, eave to ridge
WELL_TIN = tuple(((-1, 2.3, z), (1, 2.3, z), (1, 2.8, 0), (-1, 2.8, 0)) for z in (-0.7, 0.7))


def well_frame():
    """Posts and crossbeam only."""
    m = Mesh()
    pl = _t("plank", WOOD)
    for sx in (-0.78, 0.78):
        m.add(box(0.12, 2.0, 0.12, pl, center=(sx, 1.35, 0)))
    m.add(box(1.8, 0.12, 0.12, pl, center=(0, 2.3, 0)))
    return m


def well_bucket():
    return box(0.24, 0.22, 0.24, WOOD_D)


def tree(seed=0):
    m = Mesh()
    s = 0.9 + 0.2 * ((seed * 37) % 7) / 7.0
    bark = _t("bark", TRUNK)
    m.add(contact(1.6))
    m.add(box(0.58, 0.14, 0.58, _v(bark, -22), center=(0, 0.07, 0)))
    m.add(box(0.30, 1.8, 0.30, bark, center=(0, 0.9, 0)))
    m.add(_bipyr(0, 2.3 * s, 0, 1.35 * s, s, 0.75 * s, _t("leaf", LEAF)))
    m.add(_bipyr(0.1, 3.1 * s, 0.05, 0.9 * s, 0.8 * s, 0.3 * s,
                 _t("leaf", LEAF2)))
    return m


def contact(size, col=None):
    m = Mesh()
    m.add(quad_xz(
        -size / 2, -size / 2, size / 2, size / 2, 0.046,
        col or _v(LEAF, -26), layer=1, seg=1))
    return m


def orchard():
    m = Mesh()
    bark = _t("bark", TRUNK)
    soil = _t("dirt", FURROW)
    root_soil = _v(soil, -8)
    furrow, leaf = _t("furrow", P.TRACK_D), _t("leaf", LEAF)
    i = 0
    for x in (26, 31, 36, 41):
        m.add(quad_xz(x - 1.35, -10, x + 1.35, 19, 0.028, soil, layer=1, seg=6))
        for dx in (-1, 1):
            m.add(quad_xz(
                x + dx - 0.08, -10, x + dx + 0.08, 19,
                0.033, furrow, layer=1, seg=3))
        for z in (-8, -2, 4, 10, 16):
            # Keep these placements identical to raid_world._orchard().
            tx = x + ((i * 13) % 5) * 0.2 - 0.4
            tz = z + ((i * 7) % 5) * 0.2 - 0.4
            s = 0.90 + 0.04 * ((i * 37) % 7)
            m.add(quad_xz(
                tx - 0.38, tz - 0.38, tx + 0.38, tz + 0.38,
                0.036, root_soil, layer=1, seg=1))
            t = Mesh()
            t.add(contact(1.4))
            t.add(box(0.58, 0.14, 0.58, _v(bark, -22), center=(0, 0.07, 0)))
            t.add(box(0.30, 1.7, 0.30, bark, center=(0, 0.85, 0)))
            for side in (-1, 1):
                t.add(box(0.10, 0.82, 0.10, bark),
                      rot_z(-side * 38), t=(side * 0.25, 1.96, 0))
            crown = _v(leaf, (i % 5 - 2) * 5)
            t.add(_bipyr(0, 2.5, 0, 1.3 * s, 0.95 * s, 1.15,
                         crown, n=6, moon=True))
            t.add(_bipyr(0.5 * s, 2.9, 0.12 * s, 0.82 * s, 0.72 * s, 0.6,
                         _v(crown, 8), n=5, moon=True))
            t.add(_bipyr(-0.47 * s, 2.75, -0.1 * s, 0.75 * s, 0.64 * s, 0.55,
                         _v(crown, -7), n=5, moon=True))
            if i % 3 == 0:
                for side in (-1, 1):
                    for fx in (-0.42, 0.42):
                        fruit = (180, 74, 40) if (i + side) % 2 else (196, 98, 45)
                        t.add(box(0.12, 0.12, 0.12, fruit,
                                  center=(fx * s, 2.5, side * 1.14 * s)))
            m.add(t, rot_y((i * 47) % 360), t=(tx, 0, tz))
            i += 1
    m.add(quad_xz(18, -1.15, 48, 1.15, 0.055, _t("track", TRACK), layer=1, seg=8))
    m.add(quad_xz(43.7, -10, 46.5, 20, 0.038, _t("track", TRACK), layer=1, seg=6))
    return m


@lru_cache(maxsize=1)
def _tractor_asset():
    try:
        from game.render3d_bridge import load_mesh_asset
        return load_mesh_asset("tractor_m7")
    except (OSError, ValueError):
        return None


def tractor(lit=False):
    """Local forward is +x; use the authored asset when available."""
    asset = _tractor_asset()
    if asset is None:
        return _tractor_blocks(lit)
    verts, faces = asset
    m = Mesh()
    m.verts = [tuple(v) for v in verts]
    m.faces = [
        (tuple(f[0]), WIN_LIT if lit and f[2] == 1 else tuple(f[1]),
         2, True, lit and f[2] > 0)
        for f in faces]
    return m


def _tractor_blocks(lit=False):
    m = Mesh()

    def wheel(x, z, rad, wid):
        n = 16
        cy = rad * math.cos(math.pi / n) - 0.025
        angles = [math.tau * k / n + math.pi / n for k in range(n)]

        def ring(radius):
            return [
                (x + radius * math.cos(a), cy + radius * math.sin(a))
                for a in angles]

        outer = ring(rad)
        shoulder = ring(rad * 0.86)
        bead, rim, hub = ring(rad * 0.51), ring(rad * 0.42), ring(rad * 0.18)
        z0, z1 = z - wid / 2, z + wid / 2
        for k in range(n):
            j = (k + 1) % n
            for strip in range(3):
                za, zb = z0 + wid * strip / 3, z0 + wid * (strip + 1) / 3
                shade = 12 if (k + strip) % 2 == 0 else 3
                m.face([
                    (outer[k][0], outer[k][1], za),
                    (outer[j][0], outer[j][1], za),
                    (outer[j][0], outer[j][1], zb),
                    (outer[k][0], outer[k][1], zb)], _v(RUB, shade), 2, True)
        for side in (-1, 1):
            zz = z + side * wid / 2
            for k in range(n):
                j = (k + 1) % n
                for outside, inside, colour in (
                    (outer, shoulder, _v(RUB, 10 if k % 2 else 6)),
                    (shoulder, bead, _v(RUB, 4)),
                    (bead, rim, _v(RUB, -7)),
                    (rim, hub, _v(HUB, 6 if k % 2 else -4)),
                ):
                    m.face([
                        (outside[k][0], outside[k][1], zz),
                        (outside[j][0], outside[j][1], zz),
                        (inside[j][0], inside[j][1], zz),
                        (inside[k][0], inside[k][1], zz)], colour, 2, True)
            m.face([(px, py, zz) for px, py in hub], _v(HUB, -18), 2, True)

    for sz in (-0.78, 0.78):
        wheel(-0.7, sz, 0.75, 0.34)
    for sz in (-0.62, 0.62):
        wheel(1.0, sz, 0.42, 0.2)
    for dims, col, pos in (
        ((2.3, 0.5, 0.75), TRACT_D, (0.1, 0.85, 0)),
        ((1.3, 0.75, 0.7), TRACT, (0.85, 1.3, 0)),
        ((0.06, 0.6, 0.6), METAL, (1.52, 1.3, 0)),
        ((0.5, 0.12, 0.5), RUB, (-0.65, 1.45, 0)),
        ((0.1, 0.5, 0.5), RUB, (-0.92, 1.72, 0)),
        ((0.06, 0.5, 0.06), METAL, (0.15, 1.65, 0)),
    ):
        m.add(box(*dims, col, center=pos))
    for sz in (-0.82, 0.82):
        m.add(box(1.3, 0.1, 0.5, TRACT_D, center=(-0.7, 1.55, sz)))
    steer_r = 0.23
    for k in range(8):
        a, b = math.tau * k / 8, math.tau * (k + 1) / 8
        ax, az = 0.1 + steer_r * math.cos(a), steer_r * math.sin(a)
        bx, bz = 0.1 + steer_r * math.cos(b), steer_r * math.sin(b)
        dx, dz = bx - ax, bz - az
        m.add(box(math.hypot(dx, dz), 0.035, 0.035, RUB),
              rot_y(-math.degrees(math.atan2(dz, dx))),
              t=((ax + bx) / 2, 1.92, (az + bz) / 2))
    m.add(box(0.36, 0.03, 0.035, METAL, center=(0.1, 1.91, 0)))
    m.add(box(0.035, 0.03, 0.36, METAL, center=(0.1, 1.91, 0)))
    m.add(box(0.1, 0.9, 0.1, METAL, center=(1.0, 2.0, 0.22)))
    m.add(box(0.045, 0.48, 0.48, RUB, center=(1.565, 1.3, 0)))
    for yy in (1.12, 1.21, 1.30, 1.39, 1.48):
        m.add(box(0.025, 0.025, 0.44, METAL, center=(1.6, yy, 0)))
    for sz in (-0.28, 0.28):
        m.add(box(0.1, 0.18, 0.22, RUB, center=(1.57, 1.44, sz)))
        m.add(box(0.035, 0.12, 0.16, WIN_LIT if lit else METAL,
                  center=(1.63, 1.44, sz), emissive=lit))
    for sz in (-0.36, 0.36):
        m.add(box(1.05, 0.05, 0.035, _v(TRACT, 16), center=(0.83, 1.69, sz)))
        for xx in (0.55, 0.7, 0.85, 1):
            m.add(box(0.065, 0.26, 0.025, TRACT_D, center=(xx, 1.28, sz)))
        m.add(box(0.48, 0.08, 0.3, METAL, center=(-0.42, 0.72, sz * 1.8)))
    m.add(box(0.17, 0.07, 0.17, RUB, center=(1, 2.48, 0.22)))
    m.add(box(0.22, 0.12, 0.32, METAL, center=(-1.28, 0.55, 0)))
    for side in (-1, 1):
        z = side * 0.82
        m.add(box(1.2, 0.045, 0.06, _v(TRACT, 14),
                  center=(-0.7, 1.615, z + side * 0.22)))
        m.add(box(0.055, 0.13, 0.18, (140, 52, 38), center=(-1.36, 1.47, z)))
        m.add(box(0.08, 0.37, 0.08, TRACT_D), rot_z(-24),
              t=(-0.35, 1.34, z - side * 0.16))
    m.add(box(0.16, 0.06, 0.16, METAL, center=(0.48, 1.705, -0.12)))
    for z in (-0.37, 0.37):
        m.add(box(1.08, 0.08, 0.05, TRACT_D, center=(0.78, 0.98, z)))
    m.add(box(0.43, 0.08, 0.09, METAL, center=(-1.36, 0.51, 0)))
    m.add(box(0.045, 0.45, 0.045, METAL), rot_z(12),
          t=(-0.30, 1.52, -0.25))
    m.add(box(0.09, 0.09, 0.09, RUB, center=(-0.34, 1.76, -0.25)))
    return m


# ---------------------------------------------------------------------------
# Scrambler 125 motorcycle (assets/3D/scrambler125.glb)
# ---------------------------------------------------------------------------

_GLTF_COMP = {
    5120: ("b", 1, 127.0),
    5121: ("B", 1, 255.0),
    5122: ("h", 2, 32767.0),
    5123: ("H", 2, 65535.0),
    5125: ("I", 4, 1.0),
    5126: ("f", 4, 1.0),
}
_GLTF_ARITY = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4, "MAT4": 16}
_M4_IDENT = (
    1.0, 0.0, 0.0, 0.0,
    0.0, 1.0, 0.0, 0.0,
    0.0, 0.0, 1.0, 0.0,
    0.0, 0.0, 0.0, 1.0,
)


def _m4_mul(a, b):
    """Row-major 4x4 matrix product."""
    return tuple(
        a[r * 4 + 0] * b[0 + c]
        + a[r * 4 + 1] * b[4 + c]
        + a[r * 4 + 2] * b[8 + c]
        + a[r * 4 + 3] * b[12 + c]
        for r in range(4) for c in range(4)
    )


def _node_m4(node):
    """glTF node local transform as a row-major 4x4 matrix."""
    if "matrix" in node:
        c = node["matrix"]  # glTF matrices are column-major
        return (
            c[0], c[4], c[8], c[12],
            c[1], c[5], c[9], c[13],
            c[2], c[6], c[10], c[14],
            c[3], c[7], c[11], c[15],
        )
    tx, ty, tz = node.get("translation", (0.0, 0.0, 0.0))
    qx, qy, qz, qw = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    sx, sy, sz = node.get("scale", (1.0, 1.0, 1.0))
    xx, yy, zz = qx * qx, qy * qy, qz * qz
    xy, xz, yz = qx * qy, qx * qz, qy * qz
    wx, wy, wz = qw * qx, qw * qy, qw * qz
    return (
        (1.0 - 2.0 * (yy + zz)) * sx, 2.0 * (xy - wz) * sy, 2.0 * (xz + wy) * sz, tx,
        2.0 * (xy + wz) * sx, (1.0 - 2.0 * (xx + zz)) * sy, 2.0 * (yz - wx) * sz, ty,
        2.0 * (xz - wy) * sx, 2.0 * (yz + wx) * sy, (1.0 - 2.0 * (xx + yy)) * sz, tz,
        0.0, 0.0, 0.0, 1.0,
    )


def _m4_point(m, p):
    x, y, z = p[0], p[1], p[2]
    return (
        m[0] * x + m[1] * y + m[2] * z + m[3],
        m[4] * x + m[5] * y + m[6] * z + m[7],
        m[8] * x + m[9] * y + m[10] * z + m[11],
    )


def _m4_vec(m, v):
    x, y, z = v[0], v[1], v[2]
    return (
        m[0] * x + m[1] * y + m[2] * z,
        m[4] * x + m[5] * y + m[6] * z,
        m[8] * x + m[9] * y + m[10] * z,
    )


def _m4_det3(m):
    return (
        m[0] * (m[5] * m[10] - m[6] * m[9])
        - m[1] * (m[4] * m[10] - m[6] * m[8])
        + m[2] * (m[4] * m[9] - m[5] * m[8])
    )


def _read_accessor(gltf, bin_buf, idx):
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    fmt_ch, size, norm_div = _GLTF_COMP[acc["componentType"]]
    arity = _GLTF_ARITY[acc["type"]]
    count = acc["count"]
    offset = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride") or (size * arity)
    unpack = struct.Struct("<" + fmt_ch * arity).unpack_from
    norm = acc.get("normalized", False) and norm_div > 1.0
    out = []
    for i in range(count):
        vals = unpack(bin_buf, offset + i * stride)
        if norm:
            vals = tuple(max(-1.0, v / norm_div) for v in vals)
        out.append(vals[0] if arity == 1 else vals)
    return out


def _load_glb_surface(gltf, bin_buf, tex_idx):
    try:
        textures = gltf.get("textures") or ()
        images = gltf.get("images") or ()
        src_idx = textures[tex_idx].get("source")
        if src_idx is None:
            return None
        img_info = images[src_idx]
        if "bufferView" not in img_info:
            return None
        bv = gltf["bufferViews"][img_info["bufferView"]]
        start = bv.get("byteOffset", 0)
        raw = bytes(bin_buf[start:start + bv["byteLength"]])
        return pygame.image.load(io.BytesIO(raw))
    except Exception:
        return None


def _sample_surf(surf, u, v):
    w, h = surf.get_size()
    if w <= 0 or h <= 0:
        return (255, 255, 255)
    px = max(0, min(w - 1, int((u % 1.0) * w)))
    py = max(0, min(h - 1, int((v % 1.0) * h)))
    c = surf.get_at((px, py))
    return (c[0], c[1], c[2])


@lru_cache(maxsize=1)
def _scrambler_asset():
    """Load assets/3D/scrambler125.glb -> (verts, faces) in metre world scale.

    Faces are (idx_tuple, rgb_tuple, emit_flag) where emit_flag == 1 marks
    headlight/taillight emissive faces.
    """
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = (
        os.path.join(root, "assets", "3D", "scrambler125.glb"),
        os.path.abspath(os.path.join("assets", "3D", "scrambler125.glb")),
    )
    path = next((p for p in candidates if os.path.isfile(p)), None)
    if path is None:
        return None
    try:
        with open(path, "rb") as fh:
            data = fh.read()
        if len(data) < 20:
            return None
        magic, _version, total_len = struct.unpack_from("<III", data, 0)
        if magic != 0x46546C67:
            return None
        gltf, bin_buf = None, None
        pos = 12
        end = min(len(data), total_len)
        while pos + 8 <= end:
            clen, ctype = struct.unpack_from("<II", data, pos)
            pos += 8
            if ctype == 0x4E4F534A:
                gltf = json.loads(data[pos:pos + clen].decode("utf-8"))
            elif ctype == 0x004E4942:
                bin_buf = memoryview(data)[pos:pos + clen]
            pos += clen
        if not gltf or bin_buf is None:
            return None

        # Material table: (rgb_factor, tex_surface, emit_flag)
        mat_table = []
        for mat in gltf.get("materials") or ():
            pbr = mat.get("pbrMetallicRoughness") or {}
            bf = pbr.get("baseColorFactor", (1.0, 1.0, 1.0, 1.0))
            # Convert linear baseColorFactor to perceptual sRGB
            rgb_f = tuple(max(0.0, min(1.0, float(c))) ** (1.0 / 2.2) for c in bf[:3])
            tex_info = pbr.get("baseColorTexture")
            surf = _load_glb_surface(gltf, bin_buf, tex_info["index"]) if tex_info else None
            ef = mat.get("emissiveFactor") or (0.0, 0.0, 0.0)
            name = (mat.get("name") or "").lower()
            is_emit = (
                max(float(c) for c in ef) > 0.25
                or any(k in name for k in ("headlight", "lamp", "light", "emissive", "bulb"))
            )
            mat_table.append((rgb_f, surf, 1 if is_emit else 0))

        nodes = gltf.get("nodes") or ()
        meshes = gltf.get("meshes") or ()
        scenes = gltf.get("scenes") or ()
        if scenes:
            scene_idx = gltf.get("scene", 0)
            roots = scenes[scene_idx].get("nodes") or ()
        else:
            children = {c for n in nodes for c in (n.get("children") or ())}
            roots = [i for i in range(len(nodes)) if i not in children]

        verts = []
        faces = []

        def walk(node_idx, parent_m4):
            if not (0 <= node_idx < len(nodes)):
                return
            node = nodes[node_idx]
            world_m4 = _m4_mul(parent_m4, _node_m4(node))
            det = _m4_det3(world_m4)
            mesh_idx = node.get("mesh")
            if mesh_idx is not None and 0 <= mesh_idx < len(meshes):
                mesh_def = meshes[mesh_idx]
                for prim in mesh_def.get("primitives") or ():
                    if prim.get("mode", 4) != 4:
                        continue
                    attrs = prim.get("attributes") or {}
                    if "POSITION" not in attrs:
                        continue
                    raw_pos = _read_accessor(gltf, bin_buf, attrs["POSITION"])
                    raw_nrm = (
                        _read_accessor(gltf, bin_buf, attrs["NORMAL"])
                        if "NORMAL" in attrs else None
                    )
                    raw_uv = (
                        _read_accessor(gltf, bin_buf, attrs["TEXCOORD_0"])
                        if "TEXCOORD_0" in attrs else None
                    )
                    raw_col = (
                        _read_accessor(gltf, bin_buf, attrs["COLOR_0"])
                        if "COLOR_0" in attrs else None
                    )
                    indices = (
                        _read_accessor(gltf, bin_buf, prim["indices"])
                        if "indices" in prim else list(range(len(raw_pos)))
                    )
                    mat_idx = prim.get("material")
                    if mat_idx is not None and 0 <= mat_idx < len(mat_table):
                        rgb_f, surf, emit_flag = mat_table[mat_idx]
                    else:
                        rgb_f, surf, emit_flag = (0.78, 0.78, 0.78), None, 0

                    base_v = len(verts)
                    for p in raw_pos:
                        verts.append(_m4_point(world_m4, p))
                    w_nrm = [_m4_vec(world_m4, n) for n in raw_nrm] if raw_nrm else None

                    for t_i in range(0, len(indices) - 2, 3):
                        i0, i1, i2 = int(indices[t_i]), int(indices[t_i + 1]), int(indices[t_i + 2])
                        v0, v1, v2 = verts[base_v + i0], verts[base_v + i1], verts[base_v + i2]
                        gn = v_cross(v_sub(v1, v0), v_sub(v2, v0))
                        if gn[0] * gn[0] + gn[1] * gn[1] + gn[2] * gn[2] < 1e-12:
                            continue
                        if w_nrm is not None:
                            n0, n1, n2 = w_nrm[i0], w_nrm[i1], w_nrm[i2]
                            avg_n = (n0[0] + n1[0] + n2[0], n0[1] + n1[1] + n2[1], n0[2] + n1[2] + n2[2])
                            flip = v_dot(gn, avg_n) < 0.0
                        else:
                            flip = det < 0.0
                        tri = (base_v + i0, base_v + i2, base_v + i1) if flip else (base_v + i0, base_v + i1, base_v + i2)

                        r_c, g_c, b_c = rgb_f[0] * 255.0, rgb_f[1] * 255.0, rgb_f[2] * 255.0
                        if surf is not None and raw_uv is not None:
                            uv0, uv1, uv2 = raw_uv[i0], raw_uv[i1], raw_uv[i2]
                            uc = (uv0[0] + uv1[0] + uv2[0]) / 3.0
                            vc = (uv0[1] + uv1[1] + uv2[1]) / 3.0
                            samples = (
                                _sample_surf(surf, uv0[0], uv0[1]),
                                _sample_surf(surf, uv1[0], uv1[1]),
                                _sample_surf(surf, uv2[0], uv2[1]),
                                _sample_surf(surf, uc, vc),
                            )
                            r_c = sum(s[0] for s in samples) * 0.25 * rgb_f[0]
                            g_c = sum(s[1] for s in samples) * 0.25 * rgb_f[1]
                            b_c = sum(s[2] for s in samples) * 0.25 * rgb_f[2]
                        if raw_col is not None:
                            c0, c1, c2 = raw_col[i0], raw_col[i1], raw_col[i2]
                            r_c *= (c0[0] + c1[0] + c2[0]) / 3.0
                            g_c *= (c0[1] + c1[1] + c2[1]) / 3.0
                            b_c *= (c0[2] + c1[2] + c2[2]) / 3.0
                        col = (
                            max(0, min(255, int(round(r_c)))),
                            max(0, min(255, int(round(g_c)))),
                            max(0, min(255, int(round(b_c)))),
                        )
                        faces.append((tri, col, emit_flag))

            for child_idx in node.get("children") or ():
                walk(child_idx, world_m4)

        for r_idx in roots:
            walk(r_idx, _M4_IDENT)

        if not verts or not faces:
            return None

        # Orient longest horizontal axis along +x (matching tractor convention),
        # ground tires at y = 0, and normalize to ~2.05m length if out of metre range.
        xs = [v[0] for v in verts]
        ys = [v[1] for v in verts]
        zs = [v[2] for v in verts]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        span_z = max(zs) - min(zs)
        cx = (min(xs) + max(xs)) * 0.5
        cy = min(ys)
        cz = (min(zs) + max(zs)) * 0.5
        length = max(span_x, span_z, 1e-4)
        scale = 1.0 if 1.35 <= length <= 2.65 and 0.7 <= span_y <= 1.65 else (2.05 / length)
        swap_xz = span_z > span_x

        norm_verts = []
        for vx, vy, vz in verts:
            lx = (vx - cx) * scale
            ly = (vy - cy) * scale
            lz = (vz - cz) * scale
            if swap_xz:
                # 90-degree rotation around Y: (x, y, z) -> (z, y, -x), det = +1
                norm_verts.append((lz, ly, -lx))
            else:
                norm_verts.append((lx, ly, lz))

        return (tuple(norm_verts), tuple(faces))
    except Exception:
        return None


def motorcycle(lit=False):
    """Scrambler 125 motorcycle (local forward along x); uses assets/3D/scrambler125.glb."""
    asset = _scrambler_asset()
    if asset is None:
        return _motorcycle_blocks(lit)
    verts, faces = asset
    m = Mesh()
    m.verts = list(verts)
    m.faces = [
        (idx, WIN_LIT if lit and em == 1 else col, 2, True, bool(lit and em > 0))
        for idx, col, em in faces
    ]
    return m


scrambler = motorcycle


def _motorcycle_blocks(lit=False):
    """Low-poly scrambler fallback when the GLB asset is absent."""
    m = Mesh()
    tank_col = _v(TRACT, -8)
    frame_col = P.STEEL_D
    seat_col = WOOD_D

    def wheel(cx, rad, wid):
        n = 12
        cy = rad
        z0, z1 = -wid / 2, wid / 2
        ring = [(cx + rad * math.cos(math.tau * k / n), cy + rad * math.sin(math.tau * k / n)) for k in range(n)]
        hub = [(cx + rad * 0.58 * math.cos(math.tau * k / n), cy + rad * 0.58 * math.sin(math.tau * k / n)) for k in range(n)]
        for k in range(n):
            j = (k + 1) % n
            m.face([(ring[k][0], ring[k][1], z0), (ring[j][0], ring[j][1], z0),
                    (ring[j][0], ring[j][1], z1), (ring[k][0], ring[k][1], z1)], RUB, 2, True)
            for zz in (z0, z1):
                m.face([(ring[k][0], ring[k][1], zz), (ring[j][0], ring[j][1], zz),
                        (hub[j][0], hub[j][1], zz), (hub[k][0], hub[k][1], zz)], _v(RUB, -6), 2, True)
        m.add(box(0.14, 0.14, wid + 0.04, METAL, center=(cx, cy, 0)))

    wheel(-0.68, 0.33, 0.12)
    wheel(0.68, 0.34, 0.10)
    # Engine block, cradle frame, fuel tank, bench seat, exhaust, forks & headlamp
    m.add(box(0.38, 0.32, 0.24, METAL, center=(0.0, 0.44, 0.0)))
    m.add(box(0.92, 0.08, 0.14, frame_col, center=(-0.10, 0.62, 0.0)))
    m.add(box(0.46, 0.22, 0.26, tank_col, center=(0.18, 0.76, 0.0)))
    m.add(box(0.56, 0.12, 0.24, seat_col, center=(-0.32, 0.72, 0.0)))
    m.add(box(0.88, 0.06, 0.06, P.GALV, center=(-0.18, 0.42, 0.16)))
    for sz in (-0.09, 0.09):
        m.add(box(0.05, 0.68, 0.05, METAL), rot_z(22), t=(0.56, 0.62, sz))
    m.add(box(0.06, 0.05, 0.68, frame_col, center=(0.42, 0.96, 0.0)))
    m.add(box(0.12, 0.16, 0.16, frame_col, center=(0.60, 0.82, 0.0)))
    m.add(box(0.04, 0.12, 0.12, WIN_LIT if lit else WIN,
              center=(0.66, 0.82, 0.0), emissive=lit))
    m.add(box(0.05, 0.08, 0.10, (160, 42, 34), center=(-0.64, 0.72, 0.0), emissive=lit))
    return m


def pig():
    """Standing version of Bodi's low-poly pig, shared with the raid."""
    from cutscenes.m7pig3d import pig_pose
    return pig_pose()


# Where the pig lives by the stock trough: x, z, yaw (0 = +z, clockwise seen
# from above - the raid's convention).  Baked standing there at dawn; the raid
# stages it alive (raid3d), and by the burn it is long gone.
PIG_HOME = (16.75, -8.55, 190.0)


def _farm_silo():
    m = Mesh()
    n = 10
    ring = [
        (1.55 * math.cos(math.tau * i / n), 1.55 * math.sin(math.tau * i / n))
        for i in range(n)]
    for y0, y1, c0, c1 in (
        (0, 0.35, (95, 105, 106), (130, 137, 132)),
        (0.35, 4.6, (108, 118, 116), (143, 148, 137)),
        (4.6, 4.95, (86, 98, 99), (118, 124, 118)),
    ):
        for i in range(n):
            j = (i + 1) % n
            m.face([
                (ring[i][0], y0, ring[i][1]), (ring[j][0], y0, ring[j][1]),
                (ring[j][0], y1, ring[j][1]), (ring[i][0], y1, ring[i][1])],
                _v(c0 if i % 2 else c1, -8 if i % 2 else 5), 2, True)
    for i in range(n):
        j = (i + 1) % n
        m.face([
            (ring[i][0], 4.95, ring[i][1]),
            (ring[j][0], 4.95, ring[j][1]), (0, 5.75, 0)],
            (112, 66, 46) if i % 2 else (138, 82, 52), 2, True)
    for yy in (0.55, 2.45, 4.45):
        for i in range(n):
            j = (i + 1) % n
            m.face([
                (ring[i][0] * 1.012, yy, ring[i][1] * 1.012),
                (ring[j][0] * 1.012, yy, ring[j][1] * 1.012),
                (ring[j][0] * 1.012, yy + 0.055, ring[j][1] * 1.012),
                (ring[i][0] * 1.012, yy + 0.055, ring[i][1] * 1.012)],
                (72, 83, 84), 2, True)
    m.add(box(0.75, 1.55, 0.08, WOOD_D, center=(0, 0.78, -1.59)))
    m.add(box(1.9, 0.16, 1.9, METAL, center=(0, 0.08, 0)))
    return m


def _farm_windpump():
    m = Mesh()
    metal = (106, 111, 101)
    m.add(box(0.22, 6, 0.22, metal, center=(0, 3, 0)))
    m.add(box(0.13, 3.3, 0.13, WOOD_D), rot_z(-24), t=(-0.72, 1.51, 0))
    m.add(box(0.13, 3.3, 0.13, WOOD_D), rot_z(24), t=(0.72, 1.51, 0))
    m.add(box(2.8, 0.13, 0.12, metal, center=(0, 5.65, -0.15)))
    m.add(box(0.12, 2.8, 0.12, metal, center=(0, 5.65, -0.15)))
    for ang in (45, -45):
        m.add(box(2.2, 0.09, 0.1, (142, 145, 128)),
              rot_z(ang), t=(0, 5.65, -0.22))
    m.add(box(0.42, 0.42, 0.3, RUST, center=(0, 5.65, -0.34)))
    m.add(box(1.5, 0.32, 0.72, WOOD_D, center=(1.2, 0.16, -0.2)))
    m.add(box(1.32, 0.06, 0.54, (42, 68, 70), center=(1.2, 0.33, -0.2)))
    return m


def field_dressing():
    m = Mesh()
    m.add(_farm_silo(), t=(23.5, 0, 29))
    m.add(_farm_windpump(), t=(-23.5, 0, 27))
    for i, (x, z) in enumerate((
        (-62, 29), (-53, 34), (-42, 37), (-32, 32), (-24, 29),
        (-70, 14), (-66, -5), (-52, -13), (-28, 39), (-20, 43),
        (-18, 31), (-12, 35), (-6, 33), (7, 35), (14, 32),
        (20, 39), (28, 43), (48, 26), (51, 15), (50, -13), (31, -23),
    )):
        m.add(tree(70 + i), t=(x, _ground_y(x, z), z))
    for x0, z0, x1, z1, name, col in (
        (-96, 34, -28, 62, "grass", P.GRASS_DRY),
        (-24, 34, 18, 68, "stubble", P.HAY_DD),
        (24, 26, 64, 64, "grass", P.GRASS_D),
        (-78, -48, -24, -20, "furrow", P.TRACK_D),
        (25, -45, 72, -20, "stubble", P.HAY_D),
    ):
        m.add(quad_xz(x0, z0, x1, z1, 0.015, _t(name, col), layer=1, seg=8))
    for run in ((23, -15, 23, -4), (23, 4, 23, 22)):
        m.add(_fence(*run, h=1.05, every=2.5))
    for run in ((-20, 23, -7, 23), (7, 23, 20, 23)):
        m.add(_fence(*run, h=1.05, every=2.6))
    for x in (-8.5, 8.5):
        m.add(_fence(x, -26, x, -18, h=0.95, every=2.5))
    for gx, gz in ((-8, -26), (8, -26), (-7.2, 23), (7.2, 23), (23, -4), (23, 4)):
        m.add(box(0.52, 1.65, 0.52, _t("stone", STONE), center=(gx, 0.82, gz)))
        m.add(box(0.64, 0.16, 0.64, P.STONE_D, center=(gx, 1.72, gz)))
    m.add(_fence(-6.8, -24.5, 6.8, -24.5, h=1.45, every=3,
                 col=P.WOOD_GREY, gap=(-3.4, 3.4)))
    for x, z in ((-4.2, -23.8), (4.2, -23.8), (-5, 21.5),
                 (5, 21.5), (21.4, -1.8), (21.4, 1.8)):
        m.add(box(0.34, 0.42, 0.34, RUST, center=(x, 0.21, z)))
    m.add(_fence(-68, 27, -29, 27, h=0.95, every=3))
    m.add(_fence(-62, -9, -29, -9, h=0.85, every=3, gap=(12, 18)))
    for x, z in ((-57, 23), (-53, 24), (-34, 23), (-30, 20), (-60, -4)):
        m.add(hay(2), t=(x, 0, z))
    m.add(box(2.8, 0.2, 1.5, _t("plank", WOOD_D), center=(-33, 0.65, 29)))
    for z in (28.25, 29.75):
        m.add(box(2.8, 0.45, 0.08, _t("plank", WOOD), center=(-33, 0.95, z)))
        for x in (-34, -32):
            m.add(box(0.5, 0.6, 0.2, RUB, center=(x, 0.32, z)))
    return m


POLES = [(-5.5, -21.0 - 16.0 * i) for i in range(8)][::-1] + [(-18.5, -13.5)]
HOUSE_DROP = (-16.55, 4.2, 10.0)
POLE_H = 7.6


def _pole():
    m = Mesh()
    m.add(box(0.24, POLE_H + 0.2, 0.24, _t("bark", P.WOOD_DARK),
              center=(0, (POLE_H + 0.2) / 2, 0)))
    m.add(box(1.6, 0.12, 0.12, _t("plank", P.WOOD_GREY),
              center=(0, POLE_H - 0.2, 0)))
    for sx in (-0.7, 0.7):
        m.add(box(0.08, 0.16, 0.08, P.GLASS, center=(sx, POLE_H - 0.06, 0)))
    return m


def _pole_y(z):
    """Ground height under the roadside pole line (poles stand at x=-5.5)."""
    if z >= -100:
        return 0.0
    return _south_y(-5.5, z) - 0.05


def poles():
    m, p = Mesh(), _pole()
    for x, z in POLES:
        m.add(p, t=(x, _pole_y(z), z))
    return m


def yard_dressing():
    m = Mesh()
    pl, tin = _t("plank", WOOD), _t("tin", ROOF_METAL)
    ends = _t("stone", P.WOOD_L, tint=True)
    m.add(box(1, 1.15, 3.6, _t("bark", P.WOOD_DUN),
              center=(-17.05, 0.575, 10), cols={"front": ends, "back": ends}))
    m.face([
        (-17.75, 1.45, 7.9), (-17.75, 1.45, 12.1),
        (-16.5, 1.85, 12.1), (-16.5, 1.85, 7.9)], tin, 2, True)
    for z in (8, 12):
        m.add(box(0.1, 1.45, 0.1, pl, center=(-17.7, 0.72, z)))
    m.add(box(1, 1, 1, pl, center=(-18, 0.5, 3.2)))
    m.add(box(0.9, 0.9, 0.9, _v(pl, -12), center=(-18.05, 0.45, 4.25)))
    m.add(box(0.8, 0.8, 0.8, _v(pl, 8), center=(-17.95, 1.4, 3.3)))
    for (x, z), col in zip(
        ((-14.4, -12.6), (-13.75, -12.75), (-14.1, -13.3)),
        (RUST, P.TRACTOR_D, P.GENERATOR),
    ):
        d = tex("rust", like=col, tint=True)
        m.add(box(0.58, 0.9, 0.58, d, center=(x, 0.45, z)))
        for y in (0.3, 0.62):
            m.add(box(0.62, 0.05, 0.62, _v(d, -18), center=(x, y, z)))
    m.add(box(2.2, 0.55, 0.7, _t("plank", WOOD_D), center=(16.5, 0.275, -9.5)))
    m.add(box(2, 0.04, 0.5, P.WATER, center=(16.5, 0.5, -9.5)))
    tarp = (52, 74, 96)
    m.add(box(2.4, 0.7, 1.8, pl, center=(14, 0.35, -12.8)))
    t = Mesh()
    t.add(_gable_z(1.8, 2.4, 0.7, 0.45, tarp, _v(tarp, -12), oh=0.12), rot_y(90))
    m.add(t, t=(14, 0, -12.8))
    for x in (13, 15):
        m.add(box(0.26, 0.18, 0.26, P.STONE_D, center=(x, 0.86, -13.6)))
    return m


_CHURCH_A = math.atan2(96.0, -30.0)
VILLAGE_R = 79.0

# Half extents (x, z) of a village house plinth.
_HOUSE_HALF = (2.2, 1.8)
# Church + tower footprint relative to the church centre: (dx, hw, hd).
_CHURCH_FOOT = (1.5, 6.6, 3.1)
# Farmstead (main house + annex) footprint relative to its centre:
# (dx, dz, hw, hd).
_FARM_FOOT = (0.975, 0.05, 3.15, 1.95)


@lru_cache(maxsize=1)
def _village():
    """Village houses: (x, z, floor_y, lit_sides), seated into the hill."""
    out = []
    for i, (da, dr) in enumerate((
        (-0.34, -1), (-0.26, 0.5), (-0.18, -1.5), (0.11, 0),
        (0.18, -1.5), (0.25, 0.5), (0.32, -1), (0.40, 0),
    )):
        a, rad = _CHURCH_A + da, VILLAGE_R + dr
        x, z = rad * math.cos(a), rad * math.sin(a)
        lo, hi = _footprint_range(x, z, *_HOUSE_HALF)
        out.append((
            x, z, _seat(lo, hi),
            tuple(k for k in range(4) if (i * 5 + k * 3) % 7 < 3)))
    return tuple(out)


def skyline(lit):
    """Distant village and church, seated on stone plinths in the hillside."""
    m = Mesh()
    wall, roof = _t("plaster", FAR_WALL), _t("tile", _v(TILE, -18))
    stone = _t("stone", P.STONE_D)
    win = WIN_LIT if lit else SKYLINE
    for x, z, y, sides in _village():
        lo, _hi = _footprint_range(x, z, *_HOUSE_HALF)
        _plinth(m, x, z, 4.3, 3.5, lo, y + 0.25, stone)
        m.add(box(4.2, 2.8, 3.4, wall, center=(x, y + 1.4, z)))
        g = Mesh()
        g.add(_gable_z(3.4, 4.2, 2.8, 1.6, roof, wall), rot_y(90))
        m.add(g, t=(x, y, z))
        for k in sides:
            ox, oz = ((0, -1.74), (2.14, 0), (0, 1.74), (-2.14, 0))[k]
            w, d = (0.6, 0.06) if k % 2 == 0 else (0.06, 0.6)
            m.add(box(w, 0.6, d, win, center=(x + ox, y + 1.6, z + oz),
                      emissive=lit))

    rad = VILLAGE_R + 3
    cx, cz = rad * math.cos(_CHURCH_A), rad * math.sin(_CHURCH_A)
    tx = cx + 6.4
    dx, hw, hd = _CHURCH_FOOT
    lo, hi = _footprint_range(cx + dx, cz, hw, hd)
    y = _seat(lo, hi)
    _plinth(m, cx + dx, cz, 2 * hw + 0.1, 2 * hd + 0.1, lo, y + 0.3, stone)

    dome = _t("tin", P.GALV_D)
    m.add(box(10, 6, 6, wall, center=(cx, y + 3, cz)))
    g = Mesh()
    g.add(_gable_z(6, 10, 6, 2.6, roof, wall), rot_y(90))
    m.add(g, t=(cx, y, cz))
    m.add(box(3.2, 13, 3.2, wall, center=(tx, y + 6.5, cz)))
    m.add(box(3.6, 0.4, 3.6, dome, center=(tx, y + 13.2, cz)))
    m.add(_bipyr(tx, y + 14.2, cz, 1.9, 2.3, 0.8, dome, _v(dome, -20), n=8))
    m.add(box(0.2, 2.4, 0.2, P.GALV, center=(tx, y + 17.6, cz)))
    m.add(box(1, 0.18, 0.18, P.GALV, center=(tx, y + 18.2, cz)))
    m.add(box(0.5, 1.2, 0.06, win, center=(tx, y + 9.5, cz - 1.63),
              emissive=lit))
    return m


def _shelter_tree(seed=0):
    m = Mesh()
    s = 0.90 + 0.09 * (seed % 5)
    bark = _t("bark", TRUNK)
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 6))
    m.add(contact(1.9))
    m.add(box(0.72, 0.16, 0.72, _v(bark, -20), center=(0, 0.08, 0)))
    m.add(box(0.34, 3.2 * s, 0.34, bark, center=(0, 1.6 * s, 0)))
    if seed % 4 == 0:
        m.add(_bipyr(0, 4.7 * s, 0, 1.05 * s, 3 * s, 4.7 * s, leaf, n=5))
    else:
        m.add(_bipyr(-0.4 * s, 4.1 * s, 0, 2 * s, 1.9 * s, 4.1 * s, leaf, n=6))
        m.add(_bipyr(0.7 * s, 5 * s, 0.25 * s, 1.55 * s, 1.4 * s, 0.9 * s,
                     _v(leaf, 8), n=5))
    return m


def _hedgerow(x0, z0, x1, z1, seed=0):
    m = Mesh()
    dx, dz = x1 - x0, z1 - z0
    length = math.hypot(dx, dz)
    if length < 0.01:
        return m
    nx, nz = -dz / length, dx / length
    width, crest = 1.10, 0.42
    grass = _t("grass", GRASS)
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5))
    a0, a1 = (
        (x0 + nx * width, 0.025, z0 + nz * width),
        (x1 + nx * width, 0.025, z1 + nz * width))
    b0, b1 = (
        (x0 - nx * width, 0.025, z0 - nz * width),
        (x1 - nx * width, 0.025, z1 - nz * width))
    r0, r1 = (x0, crest, z0), (x1, crest, z1)
    m.face([a0, a1, r1, r0], grass, 2, True)
    m.face([r0, r1, b1, b0], _v(grass, -8), 2, True)
    m.face([b0, a0, r0], grass, 2, True)
    m.face([a1, b1, r1], grass, 2, True)
    n = max(2, int(length / 1.7))
    for i in range(n):
        u = (i + 0.5) / n
        h = (i * 37 + seed * 19) % 17
        sideways = (h % 5 - 2) * 0.09
        x, z = x0 + dx * u + nx * sideways, z0 + dz * u + nz * sideways
        cy = 0.98 + 0.05 * (h % 3)
        m.add(_bipyr(
            x, cy, z, 0.85 + 0.08 * (h % 4),
            0.72 + 0.1 * (h % 5), cy - 0.4,
            _v(leaf, (h % 3 - 1) * 5), n=5))
    return m


def _north_lane():
    """Carry the northern farm track up the hill lip to the village."""
    m = Mesh()
    track = _t("track", TRACK)
    rows = []
    for z in (69.6, 71.4, 72.9, 74.1, 75.0, 75.9):
        w = 1.4 - 0.35 * max(0.0, min(1.0, (z - 72.9) / 3.0))
        rows.append([
            (x, _background_height(x, z) + 0.06, z) for x in (-w, 0.0, w)])
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(2):
            m.face([a[i], b[i], b[i + 1]], track, 2, True)
            m.face([a[i], b[i + 1], a[i + 1]], track, 2, True)
    return m


def outer_dressing():
    m = Mesh()
    track, loam = _t("track", TRACK), _t("dirt", FURROW)
    stone, plank = _t("stone", STONE), _t("plank", WOOD)
    m.add(quad_xz(-1.4, 22, 1.4, 70, 0.035, track, layer=1, seg=10))
    m.add(_north_lane())
    for x in (-46, -41, -36, -31, 11, 16, 21):
        m.add(quad_xz(x, 40, x + 2.1, 56, 0.026,
                      _t("furrow", P.TRACK_D), layer=1, seg=4))
    hedge_runs = (
        (-27, 36, -10, 36), (10, 36, 27, 36),
        (-58, 57, -11, 59), (11, 59, 58, 56),
        (48, -17, 48, -5), (48, 5, 48, 25),
        (-9.5, -80, -9.5, -61), (-9.5, -48, -9.5, -29),
        (9, -79, 9, -58))
    for i, run in enumerate(hedge_runs):
        m.add(_hedgerow(*run, seed=20 + i))
    sites = (
        (-27, 39), (-24, 42), (-20, 38), (-16, 43), (-11, 40),
        (11, 41), (15, 38), (20, 43), (25, 40), (31, 44),
        (51, -13), (55, -10), (52, 12), (56, 17), (51, 27), (57, 29),
        (-13, -38), (-16, -43), (-12, -63), (-16, -68),
        (13, -50), (17, -54), (12, -73), (16, -78))
    for i, (x, z) in enumerate(sites):
        m.add(_shelter_tree(i), rot_y((i * 57) % 360),
              t=(x, _ground_y(x, z), z))
    store = Mesh()
    boards = _t("plank", P.WOOD_GREY)
    store.add(box(5, 2.4, 3.6, boards, center=(0, 1.2, 0)))
    store.add(_gable_z(5, 3.6, 2.4, 0.9, _t("tin", ROOF_METAL), boards))
    store.add(box(1.5, 1.9, 0.08, _t("plank", WOOD_D), center=(0, 0.95, -1.84)))
    m.add(store, t=(32, 0, 34))
    m.add(hay(6), t=(-20, 0, 30))
    m.add(hay(4), t=(28, 0, 24.6))
    for i in range(4):
        m.add(box(0.75, 0.55, 0.65, _v(plank, (i % 3 - 1) * 8),
                  center=(45.8 + 0.85 * (i % 2), 0.275, 13 + 0.85 * (i // 2))))
    for x in (-1.1, 1.1):
        m.add(quad_xz(x - 0.25, -92, x + 0.25, -27, 0.052,
                      _t("dirt", P.TRACK_D), layer=1, seg=12))
    for z in range(-87, -31, 9):
        m.add(quad_xz(-0.28, z, 0.28, z + 5, 0.055,
                      _t("grass", GRASS), layer=1, seg=1))
    for x0, x1 in ((-5.5, -4.2), (4.2, 5.5)):
        m.add(quad_xz(x0, -82, x1, -29, 0.025, loam, layer=1, seg=9))
    for x in (-4.7, 4.7):
        m.add(box(1.1, 0.52, 1.9, stone, center=(x, 0.26, -36)))
        m.add(box(1.25, 0.12, 2.1, P.STONE_D, center=(x, 0.58, -36)))
        m.add(box(0.55, 0.24, 0.025, WOOD_D, center=(x, 0.22, -36.965)))
    for z in (-31, -46, -63, -77):
        m.add(box(0.15, 0.65, 0.15, WOOD_D, center=(4, 0.325, z)))
        m.add(box(0.2, 0.12, 0.2, TRIM, center=(4, 0.49, z)))
    return m


def _landscape_water_tower():
    m = Mesh()
    wood, tank = _t("plank", WOOD_D), _t("plank", P.WOOD_GREY)
    tin = _t("tin", ROOF_METAL)
    for x in (-1.2, 1.2):
        for z in (-1.2, 1.2):
            m.add(box(0.18, 6.5, 0.18, wood, center=(x, 3.25, z)))
    m.add(box(3.5, 0.18, 3.5, wood, center=(0, 6.5, 0)))
    braces = Mesh()
    length = math.hypot(2.4, 4.8)
    angle = math.degrees(math.atan2(2.4, 4.8))
    for z in (-1.2, 1.2):
        for a in (-angle, angle):
            braces.add(box(0.11, length, 0.11, wood), rot_z(a), t=(0, 3.55, z))
    m.add(braces)
    m.add(braces, rot_y(90))
    n = 8
    ring = [
        (1.55 * math.cos(math.tau * i / n), 1.55 * math.sin(math.tau * i / n))
        for i in range(n)]
    for i in range(n):
        x0, z0 = ring[i]
        x1, z1 = ring[(i + 1) % n]
        m.face([
            (x0, 6.6, z0), (x1, 6.6, z1), (x1, 9.7, z1), (x0, 9.7, z0)],
            _v(tank, 4 if i % 2 else -3), 2, True)
        m.face([(x0, 9.7, z0), (x1, 9.7, z1), (0, 10.7, 0)],
               _v(tin, 5 if i % 2 else -5), 2, True)
        for y in (6.85, 9.45):
            m.face([
                (x0 * 1.01, y, z0 * 1.01), (x1 * 1.01, y, z1 * 1.01),
                (x1 * 1.01, y + 0.06, z1 * 1.01),
                (x0 * 1.01, y + 0.06, z0 * 1.01)], METAL, 2, True)
    return m


def _landscape_hut(lit):
    m = Mesh()
    w, d, h = 4.4, 3.2, 2.2
    boards, stone = _t("plank", P.WOOD_GREY), _t("stone", P.STONE_D)
    m.add(box(w, h, d, boards, center=(0, h / 2, 0)))
    m.add(box(w + 0.1, 0.22, d + 0.1, stone, center=(0, 0.11, 0)))
    m.add(_gable_z(w, d, h, 0.9, _t("tin", ROOF_METAL), boards))
    m.add(box(0.35, 0.8, 0.35, stone, center=(1.3, 2.85, 0.3)))
    zf = -d / 2 - 0.03
    m.add(box(0.85, 1.8, 0.08, _t("plank", WOOD_D), center=(-0.9, 0.9, zf)))
    m.add(box(0.85, 0.7, 0.06, TRIM, center=(0.9, 1.3, zf)))
    m.add(box(0.65, 0.5, 0.06, WIN_LIT if lit else WIN,
              center=(0.9, 1.3, zf - 0.06), emissive=lit))
    return m


def landscape_dressing(look):
    m = Mesh()
    for x0, z0, x1, z1, name, col in (
        (-70, 35, -49, 56, "stubble", P.HAY_DD),
        (-48, 35, -28, 56, "grass", P.GRASS_DRY),
        (-24, 37, -4, 57, "grass", P.GRASS_DRY),
        (4, 37, 20, 57, "stubble", P.HAY_D),
        (26, 38, 44, 60, "stubble", P.HAY_DD),
        (45, 36, 64, 58, "grass", P.GRASS_DRY),
        (-55, 62, -8, 70, "stubble", P.HAY_DD),
        (8, 62, 54, 70, "grass", P.GRASS_D),
        (-70, -90, -15, -54, "grass", P.GRASS_DRY),
        (15, -90, 70, -54, "stubble", P.HAY_DD),
    ):
        m.add(quad_xz(x0, z0, x1, z1, 0.020, _t(name, col), layer=1, seg=4))
    furrow = _t("furrow", P.TRACK_D)
    for x in (-67, -64, -61, -58, -55, -52):
        m.add(quad_xz(x, 37, x + 0.32, 54, 0.031, furrow, layer=1, seg=2))
    for z in (40, 43, 46, 49, 52, 58):
        m.add(quad_xz(27, z, 43, z + 0.32, 0.031, furrow, layer=1, seg=2))
    m.add(quad_xz(48, -1.15, 72, 1.15, 0.055, _t("track", TRACK), layer=1, seg=4))
    for z in (-0.5, 0.5):
        m.add(quad_xz(21, z - 0.09, 72, z + 0.09, 0.060,
                      _t("dirt", P.TRACK_D), layer=1, seg=6))
    for z0, z1 in ((-96, -86), (-80, -68), (-61, -50), (-43, -29)):
        for x0, x1 in ((-4.1, -3.3), (3.3, 4.1)):
            m.add(quad_xz(x0, z0, x1, z1, 0.020,
                          _t("grass", P.GRASS_DRY), layer=1, seg=3))
    sites = (
        (-66, 44), (-62, 52), (-57, 60), (-47, 62), (-39, 65),
        (-31, 66), (-22, 64), (-13, 65), (12, 65), (21, 66),
        (30, 65), (40, 62), (49, 59), (57, 52), (60, -23),
        (65, -16), (68, -10), (69, 10), (65, 17), (63, 24),
        (59, 33), (57, 40), (-16, -86), (-19, -80), (16, -87), (19, -81))
    for i, (x, z) in enumerate(sites):
        m.add(_shelter_tree(200 + i * 7), rot_y((i * 61) % 360),
              t=(x, _ground_y(x, z), z))
    m.add(_landscape_water_tower(), t=(-32, 0, 53))
    m.add(_landscape_hut(look != "dawn"), t=(-53, 0, 51))
    for i, (x, z) in enumerate((
        (-61, 41), (-52, 45), (-42, 51), (-17, 51),
        (18, 49), (38, 52), (58, 44),
    )):
        m.add(hay(1), rot_y((i * 37) % 180), t=(x, 0, z))
    m.add(_fence(-45, 46, -35, 46, h=0.9, every=3.5, col=P.WOOD_GREY))
    m.add(_fence(30, 46, 42, 46, h=0.9, every=3.5, col=P.WOOD_GREY))
    for z in (-39, -55, -71, -87):
        m.add(box(0.15, 0.85, 0.15, WOOD_D, center=(-4.05, 0.425, z)))
        m.add(box(0.18, 0.13, 0.18, TRIM, center=(-4.05, 0.70, z)))
    sign_z = -49
    m.add(box(0.14, 2.05, 0.14, WOOD_D, center=(-6.1, 1.025, sign_z)))
    m.add(box(1.5, 0.42, 0.1, _t("plank", P.WOOD_GREY),
              center=(-6.1, 1.8, sign_z)))
    for side in (-1, 1):
        z = sign_z + side * 0.061
        m.add(box(0.9, 0.06, 0.012, TRIM, center=(-6.1, 1.85, z)))
        m.add(box(0.58, 0.05, 0.012, TRIM, center=(-6.1, 1.7, z)))
    m.add(_fence(-9.5, -98, -9.5, -84, h=1.05, every=4, col=P.WOOD_GREY))
    m.add(_fence(9, -98, 9, -84, h=1.05, every=4, col=P.WOOD_GREY))
    return m


STALK = (108, 98, 56)
SEEDHEAD = (70, 58, 40)
HIVE = (112, 116, 104)
FAR_RIDGE = (34, 40, 50)
CREST_N = (22, 28, 27)
CREST_F = (34, 41, 47)
_SOUTH = 1.5 * math.pi


def _gap_u(a, cut=5.0, shoulder=14.0):
    da = abs((a - _SOUTH + math.pi) % math.tau - math.pi)
    cut, shoulder = math.radians(cut), math.radians(shoulder)
    u = max(0.0, min(1.0, (da - cut) / (shoulder - cut)))
    return u * u * (3 - 2 * u)


@lru_cache(maxsize=2)
def _hill_surface_triangles(ring):
    rad = HILL_RAD[ring]
    south, cut = 1.5 * math.pi, math.radians(5)
    angles = [math.tau * i / 60 for i in range(61)]
    angles.extend((south - cut, south + cut))
    angles.sort()
    rows = []
    for a in angles:
        h = _hill_h(a, ring) * _gap_u(a)
        c, s = math.cos(a), math.sin(a)
        rows.append(tuple(
            (rr * c, yy, rr * s) for rr, yy in (
                (rad - 9, -0.5), (rad - 4, h * 0.43),
                (rad, h), (rad + 8, -0.5))))
    triangles = []
    for i in range(len(angles) - 1):
        a = (angles[i] + angles[i + 1]) * 0.5
        if abs((a - south + math.pi) % math.tau - math.pi) < cut:
            continue
        lo0, mid0, top0, back0 = rows[i]
        lo1, mid1, top1, back1 = rows[i + 1]
        triangles.extend((
            (lo0, lo1, mid1), (lo0, mid1, mid0),
            (mid0, mid1, top1), (mid0, top1, top0),
            (top0, top1, back1), (top0, back1, back0)))
    return triangles


def _hill_y(a, r, ring=0):
    """Sample the actual triangulated hill surface."""
    x, z = r * math.cos(a), r * math.sin(a)
    height = 0.0
    for p, q, t in _hill_surface_triangles(ring):
        den = (q[2] - t[2]) * (p[0] - t[0]) + (t[0] - q[0]) * (p[2] - t[2])
        if abs(den) < 1e-10:
            continue
        u = ((q[2] - t[2]) * (x - t[0]) + (t[0] - q[0]) * (z - t[2])) / den
        v = ((t[2] - p[2]) * (x - t[0]) + (p[0] - t[0]) * (z - t[2])) / den
        w = 1 - u - v
        if min(u, v, w) >= -1e-8:
            height = max(height, u * p[1] + v * q[1] + w * t[1])
    return height


def _ground_y(x, z):
    a, r = math.atan2(z, x), math.hypot(x, z)
    return max(_hill_y(a, r, ring) for ring in range(len(HILL_RAD))) - 0.08


def _old_tree(seed):
    m = Mesh()
    kind = (seed * 7) % 11
    s = 1.15 + 0.07 * (seed % 5)
    bark = _t("bark", TRUNK)
    if kind == 0:
        m.add(box(0.55, 0.42, 0.55, bark, center=(0, 0.21, 0)))
        m.add(box(0.3, 0.3, 2.1, _t("bark", P.WOOD_GREY)),
              rot_y(30 + seed * 13), t=(0.9, 0.15, 0.4))
        return m
    m.add(box(0.44, 1.5 * s, 0.44, bark, center=(0, 0.75 * s, 0)))
    if kind in (1, 5):
        grey = _t("bark", P.WOOD_GREY)
        for k, (ang, ln) in enumerate(((34, 1.9), (-28, 2.3), (52, 1.4))):
            sn, cs = math.sin(math.radians(ang)), math.cos(math.radians(ang))
            b = Mesh()
            b.add(box(0.16, ln * s, 0.16, grey), rot_z(ang),
                  t=(-sn * ln * s / 2, (1.4 + cs * ln / 2) * s, 0))
            b.add(box(0.09, 0.9 * s, 0.09, grey), rot_z(-ang * 0.4),
                  t=(-sn * ln * s * 0.85, (1.4 + cs * ln * 0.85 + 0.4) * s, 0))
            m.add(b, rot_y(k * 125 + seed * 17))
        return m
    for side in (-1, 1):
        m.add(box(0.18, 1.3 * s, 0.18, bark), rot_z(-side * 32),
              t=(side * 0.34 * s, 1.85 * s, 0))
    crown = _t("leaf", _v(LEAF, (seed % 5 - 2) * 4 - 4))
    m.add(_bipyr(0.15 * s, 2.9 * s, 0, 1.75 * s, s, 0.85 * s, crown, n=6))
    m.add(_bipyr(0.85 * s, 3.25 * s, 0.35 * s, 1.05 * s, 0.85 * s, 0.55 * s,
                 _v(crown, 9), n=5))
    if kind in (2, 8):
        lean = Mesh()
        lean.add(m, rot_z(13 if seed % 2 else -11))
        return lean
    return m


_OLD_SKIP = (
    (51, -13), (55, -10), (52, 12), (56, 17), (51, 27), (57, 29),
    (60, -23), (65, -16), (68, -10), (69, 10), (65, 17), (63, 24),
    (59, 33), (57, 40), (48, 26), (51, 15), (50, -13))


def old_orchard():
    m = Mesh()
    mown, rough, plank = (
        _t("grass", P.GRASS_D), _t("grass", P.GRASS_DRY), _t("plank", WOOD))
    i = 0
    for row, x in enumerate((53, 58.5, 64, 69)):
        m.add(quad_xz(x - 1.4, -27, x + 1.4, 36, 0.03, mown, layer=1, seg=6))
        m.add(quad_xz(x + 2, -27, x + 3.5, 36, 0.032, rough, layer=1, seg=6))
        for k in range(11):
            z = -25 + 5.8 * k + (row % 2) * 2.4
            if abs(z) < 3:
                continue
            h = (i * 37 + row * 11) % 13
            tx, tz = x + (h % 5 - 2) * 0.35, z + (h % 3 - 1) * 0.6
            i += 1
            if any(math.hypot(tx - ox, tz - oz) < 3.4 for ox, oz in _OLD_SKIP) or h == 6:
                continue
            m.add(_old_tree(i), rot_y((i * 53) % 360),
                  t=(tx, _ground_y(tx, tz), tz))
    stone = _t("stone", P.STONE_D)
    for k in range(36):
        z = -30 + 2 * k
        if abs(z + 1) < 2:
            continue
        hh = 0.78 + 0.07 * ((k * 5) % 4)
        y0 = _hill_y(math.atan2(z + 1, 73), math.hypot(73, z + 1)) - 0.2
        m.add(box(0.7, hh, 2.04, _v(stone, ((k * 3) % 5 - 2) * 4),
                  center=(73, y0 + hh / 2, z + 1)))
    for z in (-1.9, 1.9):
        m.add(box(0.8, 1.35, 0.8, _t("stone", STONE), center=(73, 0.67, z)))
    for k, z in enumerate((18.5, 20, 21.6, 23)):
        x = 50.2 + 0.25 * (k % 2)
        m.add(box(0.62, 0.32, 0.52, WOOD_D, center=(x, 0.16, z)))
        m.add(box(0.5, 0.6, 0.44, _v(HIVE, (k % 3 - 1) * 8),
                  center=(x, 0.62, z)))
        m.add(box(0.64, 0.08, 0.58, P.GALV_D, center=(x, 0.96, z)))
    for k, (dx, dy, dz) in enumerate((
        (0, 0, 0), (0.8, 0, 0.1), (0.4, 0.55, 0.05),
        (0, 0, 0.75), (0.1, 0.55, 0.7),
    )):
        m.add(box(0.75, 0.55, 0.65, _v(plank, (k % 3 - 1) * 9),
                  center=(49.6 + dx, 0.275 + dy, -3.6 - dz)))
    lad = Mesh()
    pale = _t("plank", P.WOOD_GREY)
    for sx in (-0.24, 0.24):
        lad.add(box(0.07, 3.2, 0.07, pale, center=(sx, 1.6, 0)))
    for y in (0.5, 1.1, 1.7, 2.3, 2.9):
        lad.add(box(0.5, 0.05, 0.05, pale, center=(0, y, 0)))
    lean = Mesh()
    lean.add(lad, rot_z(-17))
    m.add(lean, rot_y(90), t=(53, 0, -6.4))
    m.add(box(3.2, 1.2, 0.14, _t("plank", P.WOOD_GREY),
              center=(51.6, 0.6, 7.4)))
    m.add(box(0.14, 1.5, 0.14, plank, center=(50.2, 0.75, 5.6)))
    m.add(box(0.14, 0.14, 1.6, plank), rot_y(35), t=(52.8, 0.07, 5.4))
    m.face([
        (50, 1.25, 7.3), (53.2, 1, 7.3),
        (53.4, 0.05, 5.2), (50.1, 0.55, 5.4)],
        _t("tin", ROOF_METAL), 2, True)
    return m


def _poplar(seed, h):
    m = Mesh()
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5 - 6))
    m.add(box(0.36, h * 0.3, 0.36, _t("bark", TRUNK),
              center=(0, h * 0.15, 0)))
    w = 1.25 + 0.12 * (seed % 4)
    m.add(_bipyr(0, h * 0.42, 0, w, h * 0.58, h * 0.24, leaf, n=5, moon=True))
    m.add(_bipyr(0.3, h * 0.66, 0.2, w * 0.7, h * 0.26, h * 0.2,
                 _v(leaf, 8), n=4, moon=True))
    return m


def poplars():
    m = Mesh()
    a, k = math.radians(-38), 0
    while a < math.radians(56):
        h = 11 + 1.2 * ((k * 5) % 7) + (2.5 if k % 9 == 4 else 0)
        r = 77 + 1.6 * ((k * 3) % 3)
        y = _hill_y(a, r) - 0.15
        if k % 11 != 7:
            m.add(_poplar(k, h), rot_y((k * 71) % 360),
                  t=(r * math.cos(a), y, r * math.sin(a)))
        a += math.radians((2.6, 4.2, 3.4, 5, 2.9)[k % 5])
        k += 1
    return m


# Far ridge layout; the southern corridor mesh replaces the ridge faces in
# its sector and reproduces the ridge profile exactly along the seams.
RIDGE_N = 72
RIDGE_R = 140.0
RIDGE_LO_R = RIDGE_R - 13.0
CORRIDOR_DEG = 20.0
_CORRIDOR_SEGS = (
    int(round((270.0 - CORRIDOR_DEG) / (360.0 / RIDGE_N))),
    int(round((270.0 + CORRIDOR_DEG) / (360.0 / RIDGE_N))))


def _ridge_profile(a):
    """(lower edge height, crest height) of the far ridge at angle a."""
    u = _gap_u(a, 7, 22)
    top = 7 + (
        19 + 4 * math.sin(2 * a + 0.7) + 2.5 * math.sin(5 * a + 2.1) - 7) * u
    lo = 2.4 * (1 - u) - u
    return lo, top


def crest_woods():
    m = Mesh()
    church = (_CHURCH_A - 0.36, _CHURCH_A + 0.36)
    for ring, (step, rad, col, keep) in enumerate((
        (2.1, 83.2, CREST_N, 5), (2.4, 117, CREST_F, 8),
    )):
        n = int(360 / step)
        for i in range(n):
            a = math.radians(i * step + ((i * 13) % 5) * 0.3)
            if _gap_u(a, 5, 17) < 1 or (ring == 0 and church[0] < a < church[1]):
                continue
            if (i // 6 * 7) % 11 >= keep or (i * 5) % 7 == 0:
                continue
            if ring and _hill_h(a, 1) / 118 < _hill_h(a, 0) / 84 + 0.012:
                continue
            h = (i * 29 + ring * 5) % 7
            x, z = rad * math.cos(a), rad * math.sin(a)
            y = _hill_y(a, rad, ring) - 0.15
            c = _v(col, (h % 3 - 1) * 2)
            tall = (3.2 if ring == 0 else 5) + 0.45 * h
            trunk_h = tall * 0.38
            m.add(box(0.3, trunk_h, 0.3, _v(c, -4),
                      center=(x, y + trunk_h / 2, z)))
            if h % 3 == 0:
                m.add(_bipyr(
                    x, y + trunk_h + tall * 0.22, z, 1 + 0.1 * h,
                    tall * 0.8, tall * 0.3, c, _v(c, -3), n=4, moon=True))
            else:
                m.add(_bipyr(
                    x, y + trunk_h + tall * 0.3, z, 1.9 + 0.2 * h,
                    tall * 0.5, tall * 0.4, c, _v(c, -3), n=5, moon=True))
    n = RIDGE_N
    rows = []
    for i in range(n + 1):
        a = math.tau * i / n
        lo, top = _ridge_profile(a)
        c, s = math.cos(a), math.sin(a)
        rows.append((
            (RIDGE_LO_R * c, lo, RIDGE_LO_R * s),
            (RIDGE_R * c, top, RIDGE_R * s)))
    for i in range(n):
        if _CORRIDOR_SEGS[0] <= i < _CORRIDOR_SEGS[1]:
            continue  # replaced by the depth-tested southern corridor
        (lo0, top0), (lo1, top1) = rows[i], rows[i + 1]
        shade = ((i * 73) & 3) - 1
        m.face([lo0, lo1, top1], _v(FAR_RIDGE, shade - 1), 0, True)
        m.face([lo0, top1, top0], _v(FAR_RIDGE, shade + 1), 0, True)
    return m


def _valley_y(z):
    u = max(0.0, min(1.0, (-100 - z) / 28))
    return 2.4 * u * u * (3 - 2 * u)


# ---------------------------------------------------------------------------
# Southern corridor: valley floor, the climb through the ridge notch and the
# road beyond the crest, as one depth-tested mesh with the road built in.
# ---------------------------------------------------------------------------

SOUTH_ROAD_HW = 3.2
_CORRIDOR_ROWS = (
    100.0, 104.0, 108.0, 112.0, 116.0, 120.0, 124.0, RIDGE_LO_R,
    130.25, 133.5, 136.75, RIDGE_R, 147.5, 155.0, 170.0, 190.0,
    215.0, 245.0, 280.0, 320.0)


def _road_profile(d):
    """Road height at distance d south of the farm."""
    if d <= RIDGE_LO_R:
        return _valley_y(-d)
    if d <= RIDGE_R:
        y0 = _valley_y(-RIDGE_LO_R)
        return y0 + (7.0 - y0) * (d - RIDGE_LO_R) / (RIDGE_R - RIDGE_LO_R)
    if d <= 155.0:
        s = (d - RIDGE_R) / (155.0 - RIDGE_R)
        return 7.0 + 0.4 * s * s * (3 - 2 * s)
    s = min(1.0, (d - 155.0) / 165.0)
    return 7.4 - 2.2 * s * s * (3 - 2 * s)


def _south_y(x, z):
    """Terrain height inside the southern corridor."""
    r = math.hypot(x, z)
    road = _road_profile(r)
    if abs(x) <= SOUTH_ROAD_HW + 1e-6 or r < RIDGE_LO_R:
        return road
    lo, top = _ridge_profile(math.atan2(z, x))
    if r <= RIDGE_R:
        bank = lo + (top - lo) * (r - RIDGE_LO_R) / (RIDGE_R - RIDGE_LO_R)
    else:
        bank = top + road - 7.0
    return max(road, bank)


def _south_corridor():
    m = Mesh()
    grass, track = _t("grass", GRASS), _t("track", TRACK)
    edge = math.sin(math.radians(CORRIDOR_DEG))
    fracs = (1.0, 0.78, 0.58, 0.40, 0.26, 0.16)
    road_x = (-4.6, -SOUTH_ROAD_HW, 0.0, SOUTH_ROAD_HW, 4.6)

    rows = []
    for r in _CORRIDOR_ROWS:
        e = r * edge
        xs = [-e * f for f in fracs] + list(road_x) + [e * f for f in fracs[::-1]]
        row = []
        for x in xs:
            z = -math.sqrt(max(0.0, r * r - x * x))
            row.append((x, _south_y(x, z), z))
        rows.append(row)

    for k in range(len(rows) - 1):
        a, b = rows[k], rows[k + 1]
        for i in range(len(a) - 1):
            on_road = (
                abs(a[i][0]) <= SOUTH_ROAD_HW + 1e-6
                and abs(a[i + 1][0]) <= SOUTH_ROAD_HW + 1e-6)
            col = track if on_road else _v(grass, ((k * 7 + i * 3) % 5 - 2) * 2)
            m.face([a[i], a[i + 1], b[i + 1]], col, 2, True)
            m.face([a[i], b[i + 1], b[i]], col, 2, True)
    return m


def _walnut(seed):
    m = Mesh()
    leaf = _t("leaf", _v(LEAF, (seed % 3 - 1) * 5 - 2))
    m.add(box(0.4, 2.3, 0.4, _t("bark", TRUNK), center=(0, 1.15, 0)))
    m.add(box(0.16, 1.4, 0.16, _t("bark", TRUNK)),
          rot_z(40), t=(-0.45, 2.4, 0))
    m.add(_bipyr(0.2, 3.5, 0, 2.5, 1.3, 1, leaf, n=6))
    m.add(_bipyr(-0.9, 3.9, 0.5, 1.5, 0.9, 0.5, _v(leaf, 8), n=5))
    return m


SHRINE_AT = (6.5, -44.5)
SHRINE_LAMP = (6.22, 1.74, -44.5)


@lru_cache(maxsize=1)
def _farmsteads():
    """Distant farms: (x, floor_y, z, window_x, window_z)."""
    out = []
    for deg, r in ((-72, 79.5), (250, 79), (151, 80)):
        a = math.radians(deg)
        x, z = r * math.cos(a), r * math.sin(a)
        if abs(x) > abs(z):
            wx, wz = x - math.copysign(2.04, x), z
        else:
            wx, wz = x, z - math.copysign(1.79, z)
        dx, dz, hw, hd = _FARM_FOOT
        lo, hi = _footprint_range(x + dx, z + dz, hw, hd)
        out.append((x, _seat(lo, hi), z, wx, wz))
    return tuple(out)


def road_dressing(lit):
    m = Mesh()
    m.add(_south_corridor())

    stalk = _t("grass", STALK, tint=True)
    disc = [
        (0.25 * math.cos(math.tau * k / 6), 0.25 * math.sin(math.tau * k / 6))
        for k in range(6)]
    for row in range(6):
        x = 7.2 + 1.9 * row
        for k in range(10):
            h = (row * 31 + k * 17) % 13
            if h in (4, 9):
                continue
            z = -46.5 + 1.7 * k + (row % 2) * 0.7
            tall = 1.85 + 0.06 * (h % 7)
            p = Mesh()
            p.face([
                (-0.05, 0, 0), (0.05, 0, 0),
                (0.04, tall, 0), (-0.04, tall, 0)], stalk, 2, True)
            p.face([
                (0, 0, -0.05), (0, 0, 0.05),
                (0, tall, 0.04), (0, tall, -0.04)], stalk, 2, True)
            p.face([
                (0, tall * 0.55, 0), (0.42, tall * 0.42, 0.05),
                (0.36, tall * 0.38, -0.08)], _v(stalk, -10), 2, True)
            head = Mesh()
            head.add(prism(disc, 0.11, _v(SEEDHEAD, (h % 3 - 1) * 5), z0=-0.055),
                     rot_x(34 + 5 * (h % 4)))
            p.add(head, rot_y(90), t=(0.16, tall - 0.12, 0))
            m.add(p, rot_y((h * 41) % 360),
                  t=(x + (h % 3 - 1) * 0.15, 0, z))
    m.add(_hedgerow(18.6, -48.5, 18.6, -28.5, seed=61))
    m.add(_hedgerow(7, -48.6, 18, -48.6, seed=62))

    m.add(quad_xz(-34, -52, -19.5, -26, 0.024,
                  _t("dirt", FURROW), layer=1, seg=6))
    furrow = _t("furrow", P.TRACK_D)
    for k in range(17):
        x = -33.6 + 0.85 * k
        m.add(quad_xz(x, -51.6, x + 0.38, -26.4, 0.034,
                      furrow, layer=1, seg=4))
    m.add(_hedgerow(-18.6, -52.5, -18.6, -26, seed=63))
    for k, z in enumerate((-62, -70.5, -79, -88, -96.5)):
        m.add(_walnut(k), rot_y((k * 83) % 360),
              t=(6.9 + 0.3 * (k % 2), 0, z))

    sx, sz = SHRINE_AT
    grey = _t("plank", P.WOOD_GREY)
    m.add(box(0.16, 1.5, 0.16, WOOD_D, center=(sx, 0.75, sz)))
    m.add(box(0.46, 0.62, 0.62, grey, center=(sx, 1.78, sz)))
    m.add(box(0.03, 0.44, 0.42, P.INK, center=(sx - 0.235, 1.76, sz)))
    roof = Mesh()
    roof.add(_gable_z(
        0.62, 0.82, 0, 0.32, _t("tin", ROOF_METAL), grey, oh=0.12), rot_y(90))
    m.add(roof, t=(sx, 2.09, sz))
    m.add(box(0.06, 0.55, 0.06, WOOD_D, center=(sx, 2.66, sz)))
    m.add(box(0.06, 0.06, 0.32, WOOD_D, center=(sx, 2.76, sz)))
    m.add(box(0.1, 0.14, 0.1, P.LAMP_WARM if lit else P.GLASS,
              center=SHRINE_LAMP, emissive=lit))
    m.add(box(0.7, 0.12, 0.9, _t("stone", P.STONE_D), center=(sx, 0.06, sz)))

    for x0, x1, z in ((4, 5.7, -53), (-5.7, -4, -54.5)):
        cx = (x0 + x1) / 2
        m.add(box(x1 - x0, 0.12, 2.4, _t("plank", P.WOOD_GREY),
                  center=(cx, 0.06, z)))
        for dz in (-1.15, 1.15):
            m.add(box(x1 - x0 + 0.3, 0.16, 0.16, _t("plank", WOOD_D),
                      center=(cx, 0.2, z + dz)))
        out = x1 + 4.2 if x0 > 0 else x0 - 4.2
        m.add(quad_xz(
            min(x1, out), z - 1.1, max(x0, out), z + 1.1, 0.045,
            _t("track", P.TRACK_D), layer=1, seg=2))

    cart = Mesh()
    cart.add(box(2.6, 0.18, 1.4, _t("plank", P.WOOD_GREY)))
    for z in (-0.66, 0.66):
        cart.add(box(2.6, 0.4, 0.07, _t("plank", WOOD_D), center=(0, 0.28, z)))
    cart.add(box(1.6, 0.08, 0.08, WOOD_D, center=(1.9, -0.1, 0.3)))
    tilt = Mesh()
    tilt.add(cart, rot_z(12))
    m.add(tilt, rot_y(74), t=(-7.4, 0.36, -67))
    prof = [
        (0.48 * math.cos(math.pi / 8 + k * math.pi / 4),
         0.48 + 0.48 * math.sin(math.pi / 8 + k * math.pi / 4))
        for k in range(8)]
    wheel = Mesh()
    wheel.add(prism(prof, 0.1, WOOD_D, z0=-0.05))
    m.add(wheel, rot_y(74), t=(-6.95, -0.04, -66))
    flat = Mesh()
    flat.add(prism(prof, 0.1, _v(WOOD_D, -8), z0=-0.05), rot_x(90))
    m.add(flat, rot_y(20), t=(-8.6, 0.05, -69.2))

    roof_c, wall = _t("tile", _v(TILE, -18)), _t("plaster", FAR_WALL)
    stone = _t("stone", P.STONE_D)
    win = WIN_LIT if lit else SKYLINE
    dx, dz, hw, hd = _FARM_FOOT
    for x, y, z, wx, wz in _farmsteads():
        lo, _hi = _footprint_range(x + dx, z + dz, hw, hd)
        _plinth(m, x, z, 4.3, 3.7, lo, y + 0.25, stone)
        _plinth(m, x + 2.9, z + 0.8, 2.5, 2.3, lo, y + 0.12, stone)
        m.add(box(4, 2.6, 3.4, wall, center=(x, y + 1.3, z)))
        g = Mesh()
        g.add(_gable_z(3.4, 4, 2.6, 1.4, roof_c, wall), rot_y(90))
        m.add(g, t=(x, y, z))
        m.add(box(2.4, 1.6, 2.2, _v(wall, -6), center=(x + 2.9, y + 0.8, z + 0.8)))
        sideways = abs(wx - x) > 0.1
        m.add(box(
            0.08 if sideways else 0.62, 0.5, 0.62 if sideways else 0.08,
            win, center=(wx, y + 1.5, wz), emissive=lit))
    return m


def build_static(r, look, park=None, well_roof=True):
    """Bake static scenery; park optionally overrides (x, z, yaw)."""
    add = _w.add
    for q in ground():
        add(r, q)
    add(r, hills())
    add(r, field_dressing())
    add(r, outer_dressing())
    add(r, landscape_dressing(look))
    lit, burn = look != "dawn", look == "burn"
    add(r, old_orchard())
    add(r, poplars())
    add(r, crest_woods())
    add(r, road_dressing(lit))
    add(r, skyline(lit))
    add(r, poles())
    add(r, yard_dressing())
    for mesh, pos in (
        (house(lit=lit, burn=burn), (-12, 0, 10)),
        (barn(burn=burn, lamp=lit and not burn), (13, 0, 12)),
        (shed(), (-11, 0, -9)),
        (well(well_roof), (1, 0, 4)),
    ):
        placed = Mesh()
        placed.add(mesh, t=pos)
        add(r, placed)
    hb = Mesh()
    hb.add(hay(4), t=(5.8, 0, 6))
    hb.add(hay(3), t=(6.4, 0, 3.8))
    add(r, hb)
    add(r, orchard())
    f = Mesh()
    f.add(_fence(-20, -16, 20, -16, gap=(-3.4, 3.4)))
    f.add(_fence(-20, -16, -20, 22))
    f.add(_fence(20, -16, 20, 22, gap=(-3, 3)))
    f.add(_fence(-26, -12, -26, 34))
    add(r, f)
    if look == "dawn":
        pp = Mesh()
        pp.add(pig(), rot_y(PIG_HOME[2] - 90.0), t=(PIG_HOME[0], 0.0, PIG_HOME[1]))
        add(r, pp)
    mx, mz, my = MOTORCYCLE_AT
    mc = Mesh()
    mc.add(motorcycle(lit=lit), rot_y(my), t=(mx, 0.0, mz))
    add(r, mc)
    tx, tz, ty = park or (*TRACTOR_AT[burn], TRACTOR_YAW[burn])
    t = Mesh()
    t.add(tractor(lit=lit), rot_y(ty), t=(tx, 0, tz))
    add(r, t)


def setup(r, look):
    p = LOOKS[look]
    r.fog, r.fog_start, r.fog_end = p["fog"], p["fog_start"], p["fog_end"]
    r.light = Light(**p["light"])


def sky(r, buf, t, look, seed=0):
    p = LOOKS[look]
    if look == "dawn":
        _fx.night_sky(
            r, buf, t, p["sky_top"], p["sky_bot"], stars=0, moon=False,
            clouds=0, sodium=p["sodium"], mist=None, seed=seed, gpu=True)
    elif look == "raid":
        _fx.night_sky(
            r, buf, t, p["sky_top"], p["sky_bot"], stars=p["stars"], moon=False,
            clouds=0, sodium=p["sodium"], mist=None, seed=seed)
        _raid_sky(r, buf, t, p["moon"])
    else:
        _w.night(
            r, buf, t, top=p["sky_top"], bot=p["sky_bot"], stars=p["stars"],
            moon=False, sodium=p["sodium"], seed=seed, gpu=True)


_CLOUDS = (
    (-170, 9, 26, 3), (-128, 17, 18, 2), (-96, 7, 30, 3),
    (-40, 12, 22, 2), (10, 6.5, 34, 3), (64, 15, 20, 2),
    (118, 8, 28, 3), (158, 19, 16, 2), (178, 9.5, 42, 2),
    (-142, 10, 24, 2), (136, 9, 30, 2), (92, 11, 40, 2),
    (52, 9.5, 24, 2))
_CLOUD = (5, 6, 11)
_CLOUD_RIM = (13, 14, 21)
_SKY_CACHE = {}


def _ring_img(rad, col):
    key = ("m7ring", rad, col)
    img = _SKY_CACHE.get(key)
    if img is None:
        img = pygame.Surface((rad * 2 + 2, rad * 2 + 2))
        img.fill((0, 0, 0))
        pygame.draw.circle(img, col, (rad + 1, rad + 1), rad)
        _SKY_CACHE[key] = img
    return img


def _raid_sky(r, buf, t, moon):
    w, h = buf.get_size()
    hy = int(r.horizon_y())
    if hy < 4:
        return
    yaw = math.degrees(math.atan2(r.fwd[0], r.fwd[2]))
    px_deg = w / max(1, r.fov)

    def at(az, el):
        return (
            w / 2 + ((az - yaw + 180) % 360 - 180) * px_deg,
            hy - el * px_deg)

    maz, mel = moon
    mx, my = at(maz, mel)
    rm = int(max(3, px_deg * 0.9))
    if -rm * 8 < mx < w + rm * 8:
        for k, col in ((7, (10, 12, 18)), (4, (16, 19, 28))):
            img = _ring_img(rm * k, col)
            buf.blit(img, (int(mx) - rm * k - 1, int(my) - rm * k - 1),
                     special_flags=pygame.BLEND_ADD)
        pygame.draw.circle(buf, (222, 226, 214), (int(mx), int(my)), rm)
        for dx, dy in ((-0.35, -0.2), (0.15, 0.25), (0.3, -0.35), (-0.1, 0.45)):
            q = max(1, rm // 3)
            pygame.draw.rect(buf, (176, 182, 178),
                             (int(mx + dx * rm), int(my + dy * rm), q, q))
    drift = t * 0.00015
    for i, (az, el, wd, rows) in enumerate(_CLOUDS):
        cx, cy = at(az + drift * (1 + 0.2 * i), el)
        cw = wd * px_deg
        if cx + cw < 0 or cx - cw > w:
            continue
        rh = max(2, int(px_deg * 0.7))
        lit = abs(((az - maz + 180) % 360) - 180) < 60
        for k in range(rows):
            ww = int(cw * (1 - 0.3 * k))
            x0 = int(cx - ww / 2 + (k * 7 % 5 - 2) * px_deg)
            y0 = int(cy - (k + 1) * rh)
            cut = int(ww * (0.35 + 0.1 * ((i + k) % 3)))
            for a, b in ((x0, x0 + cut - rh), (x0 + cut + rh, x0 + ww)):
                if b - a > 1:
                    buf.fill(_CLOUD, (a, y0, b - a, rh), special_flags=pygame.BLEND_ADD)
                    if lit:
                        buf.fill(_CLOUD_RIM, (a + 1, y0, b - a - 2, 1),
                                 special_flags=pygame.BLEND_ADD)


HOUSE_WINDOWS = ((-15, 1.75, 6.88), (-12.8, 1.75, 6.88), (-8.4, 1.75, 6.88))
CHIMNEY_TOP = (-9.4, 5.2, 10.5)
_POOL_CACHE = OrderedDict()


def _pool_img(rx, ry, col, k):
    key = (rx, ry, tuple(col), k)
    img = _POOL_CACHE.get(key)
    if img is not None:
        _POOL_CACHE.move_to_end(key)
        return img
    w, h = rx * 2 + 2, ry * 2 + 2
    try:
        import numpy as np
        import pygame.surfarray as sa
        ax = np.linspace(-1.0, 1.0, w, dtype=np.float32)[:, None]
        ay = np.linspace(-1.0, 1.0, h, dtype=np.float32)[None, :]
        rr = np.hypot(ax, ay)
        f = np.clip(1.0 - rr, 0.0, 1.0)
        b = k * (f ** 2.1)
        img = pygame.Surface((w, h))
        px = sa.pixels3d(img)
        for ch_i in range(3):
            px[..., ch_i] = np.clip(b * col[ch_i], 0, 255).astype(np.uint8)
        del px
    except ImportError:
        img = pygame.Surface((w, h))
        img.fill((0, 0, 0))
        n = 32
        for i in range(n, 0, -1):
            f = i / float(n)
            b = k * (0.06 + 0.94 * (1 - f) ** 2.1)
            c = tuple(min(255, int(ch * b)) for ch in col)
            pygame.draw.ellipse(img, c, (
                rx + 1 - rx * f, ry + 1 - ry * f,
                rx * 2 * f + 1, ry * 2 * f + 1))
    if len(_POOL_CACHE) >= 160:
        _POOL_CACHE.popitem(last=False)
    _POOL_CACHE[key] = img
    return img


def pool(col, radius_m, intensity=0.3, squash=0.5):
    def draw(s, sx, sy, scale, z):
        rx = int(min(240, radius_m * scale))
        if rx < 3:
            return
        ry = max(2, int(min(160, rx * squash)))
        k = int(round(intensity * 24)) / 24
        if k <= 0.02:
            return
        img = _pool_img(rx, ry, col, k)
        s.blit(img, (int(sx) - img.get_width() // 2, int(sy) - img.get_height() // 2),
               special_flags=pygame.BLEND_ADD)
    draw._gl_spec = {
        "kind": "halo", "col": col, "intensity": min(1.0, float(intensity)),
        "radius_m": float(radius_m), "squash": float(squash),
        "max_px": 240.0, "power": 2.1, "peak": 1.0, "hdr": 1.15,
    }
    draw.light = True
    draw.light_soft = True
    draw.bounds_m = (radius_m, radius_m * squash)
    draw.bounds_cap_px = (240, 160)
    return draw


def raid_fx(r, t, lit=True):
    if lit:
        x, y, z = BARN_LAMP
        r.add_sprite((x, y - 0.1, z),
                     _fx.glow(P.LAMP_WARM, 2.4, t, flicker=0.04, seed=3,
                              core=(255, 240, 214), intensity=0.9),
                     layer=_fx.FX_LAYER)
        r.add_sprite((x, y - 0.2, z - 0.1),
                     _fx.light_shaft(P.LAMP_WARM, 3.6, 0.5, 2.6, t,
                                     seed=3, intensity=0.22, tilt=0.03),
                     layer=_fx.FX_LAYER)
        r.add_sprite(PORCH_LAMP,
                     _fx.glow(P.LAMP_WARM, 1.6, t, flicker=0.05, seed=5,
                              core=(255, 240, 214), intensity=0.8),
                     layer=_fx.FX_LAYER)
        for pos, col, rad, intensity, squash in (
            ((PORCH_LAMP[0], PORCH_LAMP[1] - 0.35, PORCH_LAMP[2] + 0.22),
             (255, 168, 92), 2.1, 0.55, 0.8),
            ((BARN_LAMP[0], BARN_LAMP[1] - 0.3, BARN_LAMP[2] + 0.24),
             (255, 170, 96), 1.6, 0.45, 0.8),
            ((PORCH_LAMP[0], 0.05, PORCH_LAMP[2] - 1.3),
             (255, 196, 132), 3.2, 0.34, 0.5),
            ((BARN_LAMP[0] + 1.6, 0.05, BARN_LAMP[2] - 1.2),
             (255, 192, 128), 3.4, 0.28, 0.5),
        ):
            r.add_sprite(pos, pool(col, rad, intensity=intensity, squash=squash),
                         layer=_fx.FX_LAYER)
        for i, pos in enumerate(HOUSE_WINDOWS):
            r.add_sprite((pos[0], pos[1], pos[2] - 0.05),
                         _fx.window_glow(P.WINDOW, 0.9, 0.85, intensity=0.36,
                                         t=t, flicker=0.03, seed=11 + i),
                         layer=_fx.FX_LAYER)
            r.add_sprite((pos[0], 0.05, pos[2] - 0.95),
                         pool((255, 206, 138), 1.5, intensity=0.2, squash=0.55),
                         layer=_fx.FX_LAYER)
        for i, (vx, vz, vy, sides) in enumerate(_village()):
            if sides:
                r.add_sprite((vx, vy + 1.9, vz),
                             _fx.glow(P.WINDOW, 0.9, t, seed=30 + i,
                                      intensity=0.55, max_px=6), layer=_fx.FX_LAYER)
        for i, (_x, y, _z, wx, wz) in enumerate(_farmsteads()):
            r.add_sprite((wx, y + 1.5, wz),
                         _fx.glow(P.WINDOW, 1, t, seed=50 + i,
                                  intensity=0.6, max_px=6), layer=_fx.FX_LAYER)
        r.add_sprite(SHRINE_LAMP,
                     _fx.glow(P.LAMP_WARM, 0.8, t, flicker=0.12, seed=57,
                              core=(255, 232, 196), intensity=0.7, max_px=10),
                     layer=_fx.FX_LAYER)
    cx, cy, cz = CHIMNEY_TOP
    for i in range(3):
        u = (t * 0.00018 + i / 3) % 1
        r.add_sprite((cx + u * 1.6, cy + u * 3.2, cz + u * 0.6),
                     smoke(t, seed=40 + i, size_m=0.8 + u * 1.6),
                     layer=_fx.FX_LAYER)
    wires(r)


def _sag(r, a, b, col, n=3, drop=0.45):
    prev = a
    for i in range(1, n + 1):
        u = i / float(n)
        p = (
            a[0] + (b[0] - a[0]) * u,
            a[1] + (b[1] - a[1]) * u - drop * 4 * u * (1 - u),
            a[2] + (b[2] - a[2]) * u)
        r.add_line3d(prev, p, col, 1, layer=1)
        prev = p


def wires(r):
    col, y = (20, 22, 26), POLE_H - 0.02
    for (x0, z0), (x1, z1) in zip(POLES[:-1], POLES[1:]):
        y0, y1 = y + _pole_y(z0), y + _pole_y(z1)
        for sx in (-0.7, 0.7):
            _sag(r, (x0 + sx, y0, z0), (x1 + sx, y1, z1), col)
    ex, _ey, ez = r.cam
    if ez < 13 or ex < -16.5:
        x, z = POLES[-1]
        _sag(r, (x - 0.7, y, z), HOUSE_DROP, col, drop=0.6)


def raid_pools(extra=()):
    pools = [
        {"pos": BARN_LAMP, "range": 7.5, "color": P.LAMP_WARM,
         "hot": (255, 236, 206), "intensity": 1.6},
        {"pos": PORCH_LAMP, "range": 6, "color": P.LAMP_WARM,
         "hot": (255, 236, 206), "intensity": 1.7},
    ]
    pools += [
        {"pos": (x, y + 0.2, z - 0.9), "range": 2.6, "color": P.WINDOW,
         "hot": (255, 232, 180), "intensity": 1.1}
        for x, y, z in HOUSE_WINDOWS]
    return pools + list(extra)


_GRADE = {}


def raid_curve():
    """1D (3, 256) uint8 grading curve for GPU PostPipeline (without Bayer dither)."""
    curve = _GRADE.get("raid_curve")
    if curve is None:
        import numpy as np
        x = np.arange(256, dtype=np.float32) / 255
        x = np.clip((x - 0.020) / 0.980, 0, 1)
        x = np.clip(0.45 + (x - 0.45) * 1.10, 0, 1)
        x = x ** 1.10
        sh, mid, hi = (1 - x) ** 2, 4 * x * (1 - x), x * x
        chan = [np.clip(v, 0, 1) for v in (
            x - 0.012 * sh + 0.004 * mid + 0.030 * hi,
            x + 0.006 * sh + 0.004 * mid + 0.010 * hi,
            x + 0.022 * sh - 0.006 * mid - 0.034 * hi)]
        rows = [np.clip(np.round(v * 255.0), 0, 255).astype(np.uint8) for v in _fx.ink(chan, np)]
        curve = _GRADE["raid_curve"] = np.stack(rows, axis=0)
    return curve


def grade_raid(surface):
    try:
        import numpy as np
    except ImportError:
        return
    lut = _GRADE.get("raid")
    if lut is None:
        x = np.arange(256, dtype=np.float32) / 255
        x = np.clip((x - 0.020) / 0.980, 0, 1)
        x = np.clip(0.45 + (x - 0.45) * 1.10, 0, 1)
        x = x ** 1.10
        sh, mid, hi = (1 - x) ** 2, 4 * x * (1 - x), x * x
        chan = [np.clip(v, 0, 1) for v in (
            x - 0.012 * sh + 0.004 * mid + 0.030 * hi,
            x + 0.006 * sh + 0.004 * mid + 0.010 * hi,
            x + 0.022 * sh - 0.006 * mid - 0.034 * hi)]
        lut = _GRADE["raid"] = _fx.dither_lut(_fx.ink(chan, np), np)
    _fx.apply_lut(surface, lut, np)


def stage(look, t, eye, tgt, fov, lights=(), hh=0.006, seed=0, size=None, park=None,
          well_roof=True):
    """``well_roof=False`` leaves the well's roof out of the bake for a caller
    that draws (and drops) it itself."""
    r, buf = _w.rend(*size) if size else _w.rend()
    setup(r, look)
    r.set_lights(list(lights))
    _w.cam(r, t, eye, tgt, fov, hh=hh, seed=seed)
    sky(r, r.surface if getattr(r, "backend", "") == "gl" else buf, t, look, seed)
    fresh = _w.static_scene(r, "m7:%s:%s:%d" % (look, park, well_roof))
    r.begin()
    ok = True
    try:
        if fresh:
            build_static(r, look, park, well_roof)
    except Exception:
        ok = False
        raise
    finally:
        _w.static_end(r, ok)
    return r, buf


def finish(surface, r, buf, seed, tag, t):
    if getattr(r, "backend", "") == "gl":
        import zlib
        band = surface.subsurface((0, _w.SAFE_TOP, _w.WIDTH, _w.FILM_H))
        gseed = zlib.crc32(f"m6_film_{seed}:{int(t) // 40}".encode("utf-8"))
        r.flush_to(band, post={
            "bloom": 0.24, "bloom_knee": 0.98, "gamma": 0.82,
            "vignette": 0.40, "vig_mode": 2, "grain": 0.26, "grain_seed": gseed,
        })
        if tag:
            surf = _w.font_terminal_small.render(tag, True, (120, 190, 220))
            plate = pygame.Surface((surf.get_width() + 20, surf.get_height() + 6), pygame.SRCALPHA)
            plate.fill((4, 6, 10, 186))
            pygame.draw.rect(plate, (120, 190, 220, 90), plate.get_rect(), 1)
            surface.blit(plate, (24, _w.SAFE_TOP + 6))
            surface.blit(surf, (34, _w.SAFE_TOP + 9))
        return
    r.flush(buf)
    _w.present(surface, buf)
    _w.finish(surface, seed, tag, t=t)


def mist(r, t, seed=0, n=9, intensity=0.10):
    for i in range(n):
        x, z = -58 + (i * 37 % 61) + 0.0, -6 + (i * 53 % 40)
        r.add_sprite((x, 0.7, z),
                     _fx.haze((214, 196, 182), 8, t, seed=seed + i,
                              intensity=intensity), layer=_fx.FX_LAYER)


def sun(r, t, pos=(96.0, 9.0, -14.0)):
    r.add_sprite(pos,
                 _fx.glow((255, 196, 128), 26, t, intensity=0.85,
                          core=(255, 232, 190), max_px=110),
                 layer=_fx.FX_LAYER)


# ---------------------------------------------------------------------------
# Fire
#
# Flames are camera-facing, layered cel silhouettes built as real geometry:
# a deep red rim, orange body, yellow heart and a white-hot core, each layer
# nudged slightly toward the camera. Depth-tested, so walls still hide them.
# Time is stepped (~15 fps) for the late-PS2 feel and is fully deterministic.
# ---------------------------------------------------------------------------

_FIRE_FRAME_MS = 40.0   # kept for compatibility
_FIRE_FRAMES = 120
_FIRE_STEP_MS = 66.0


def _fire_flicker(t, seed=0):
    """Small, irregular brightness variation; never an on/off strobe."""
    p = seed * 1.731
    return (
        0.90
        + 0.065 * math.sin(t * 0.0083 + p)
        + 0.035 * math.sin(t * 0.0217 + p * 2.3)
        + 0.020 * math.sin(t * 0.0371 + p * 0.7))


# outer -> core: (colour, height scale, width scale)
_FLAME_LAYERS = (
    ((196, 46, 12), 1.00, 1.00),
    ((250, 114, 22), 0.80, 0.76),
    ((255, 188, 60), 0.56, 0.52),
    ((255, 246, 196), 0.30, 0.28),
)
# (offset across, height, half-width), relative to the flame's width/height
_FLAME_TONGUES = (
    (0.00, 1.00, 0.42),
    (-0.34, 0.70, 0.30),
    (0.32, 0.78, 0.32),
    (-0.58, 0.44, 0.22),
    (0.60, 0.50, 0.24),
)
_FLAME_ROWS = (0.0, 0.14, 0.32, 0.52, 0.72, 0.88)


def _flame_profile(s):
    """Teardrop width along a tongue: rounded base, swelling, thin tip."""
    return min(1.0, 0.6 + 2.0 * s) * (1.0 - s) ** 1.15


def _flame_basis(pos, cam):
    """(right, toward-camera) unit vectors in xz for a vertical billboard."""
    if cam is not None:
        dx, dz = cam[0] - pos[0], cam[2] - pos[2]
        d = math.hypot(dx, dz)
        if d > 1e-4:
            fx, fz = dx / d, dz / d
            return (-fz, fx), (fx, fz)
    return (1.0, 0.0), (0.0, -1.0)


def _paint_flame(m, base, right, fwd, t, seed, width, height,
                 licks=True, embers=6):
    if width <= 0.01 or height <= 0.02:
        return
    bx, by, bz = base
    rx, rz = right
    fx, fz = fwd
    step = int(t // _FIRE_STEP_MS)
    ph = step * 0.37 + seed * 1.731
    eps = max(0.01, 0.03 * width)

    def at(u, v, d):
        return (bx + rx * u + fx * d, by + v, bz + rz * u + fz * d)

    def centre(u0, q, lean, v):
        # Sway depends on absolute height, so nested layers stay nested.
        s = v / height
        return (u0 + lean * width * s * s
                + 0.16 * width * s * math.sin(q * 1.9 - s * 6.0)
                + 0.05 * width * s * math.sin(q * 4.3 - s * 13.0))

    tongues = []
    for i, (u0, th, tw) in enumerate(_FLAME_TONGUES):
        q = ph * (1.0 + 0.23 * (i % 3)) + i * 2.17
        grow = 0.80 + 0.14 * math.sin(q * 1.3) + 0.06 * math.sin(q * 3.1 + 1.0)
        lean = 0.22 * math.sin(q * 0.6 + seed)
        tongues.append((u0 * width, th * height * grow, tw * width, q, lean))

    for li, (col, hs, ws) in enumerate(_FLAME_LAYERS):
        d = li * eps
        pull = 0.45 + 0.55 * ws
        for u0, h, w, q, lean in tongues:
            H, W = h * hs, w * ws
            if H < 0.06 * height or W < 0.004:
                continue
            uc = u0 * pull
            rows = []
            for s in _FLAME_ROWS:
                v = s * H
                c = centre(uc, q, lean, v)
                hw = W * _flame_profile(s) * (0.92 + 0.08 * math.sin(q * 2.7 + s * 9.0))
                rows.append((c - hw, c + hw, v))
            for a, b in zip(rows, rows[1:]):
                m.face([at(a[0], a[2], d), at(a[1], a[2], d),
                        at(b[1], b[2], d), at(b[0], b[2], d)], col, 2, True, True)
            top = rows[-1]
            m.face([at(top[0], top[2], d), at(top[1], top[2], d),
                    at(centre(uc, q, lean, H), H, d)], col, 2, True, True)

    if licks:
        # Detached flame blobs breaking off the tips and shrinking away.
        outer, mid = _FLAME_LAYERS[0][0], _FLAME_LAYERS[1][0]
        for i in range(3):
            u0, h, w, q, lean = tongues[i]
            life = (step * 0.06 + i * 0.37 + seed * 0.13) % 1.0
            rr = w * 0.5 * (1.0 - life)
            if rr < 0.01:
                continue
            v = h * (0.9 + 0.6 * life)
            c = centre(u0, q, lean, v)
            col = mid if life < 0.35 else outer
            d = eps * 0.5
            m.face([at(c, v - rr * 1.3, d), at(c + rr, v, d),
                    at(c, v + rr * 1.9, d), at(c - rr, v, d)], col, 2, True, True)

    for k in range(embers):
        life = (step * 0.028 + k / float(embers) + seed * 0.071) % 1.0
        e = width * 0.045 * (1.0 - 0.6 * life)
        if e < 0.008:
            continue
        u = (math.sin(k * 2.4 + seed) * 0.45
             + math.sin(life * 7.0 + k) * 0.18 * (0.3 + life)) * width
        v = height * (0.6 + 1.4 * life)
        col = (255, int(210 - 150 * life), int(110 - 90 * life))
        d = -eps
        m.face([at(u, v - e, d), at(u + e * 0.7, v, d),
                at(u, v + e, d), at(u - e * 0.7, v, d)], col, 2, True, True)


def _coal_bed(m, pos, rad, seed):
    """Glowing fuel bed under ground fires."""
    x, y, z = pos
    n, rot = 7, seed * 0.9
    for rr, col, dy in ((rad, (60, 18, 10), 0.02), (rad * 0.58, (156, 46, 12), 0.03)):
        m.face([
            (x + rr * math.cos(rot + math.tau * i / n), y + dy,
             z + rr * math.sin(rot + math.tau * i / n))
            for i in range(n)], col, 2, True, True)


_FLAME_UNIT = OrderedDict()
_FLAME_PACK = OrderedDict()
_COAL_PACK = []


def _unit_flame(step, seed, licks=True, embers=6, w0=0.9, h0=2.1):
    key = (step, seed, bool(licks), int(embers), w0, h0)
    m = _FLAME_UNIT.get(key)
    if m is None:
        m = Mesh()
        _paint_flame(m, (0.0, 0.0, 0.0), (1.0, 0.0), (0.0, 1.0),
                     step * _FIRE_STEP_MS, seed, w0, h0, licks=licks, embers=embers)
        if len(_FLAME_UNIT) >= 384:
            _FLAME_UNIT.popitem(last=False)
        _FLAME_UNIT[key] = m
    else:
        _FLAME_UNIT.move_to_end(key)
    return m


def _emit_flame_packed(r, pos, right, fwd, step, seed, width, height,
                       licks=True, embers=6, w0=0.9, h0=2.1):
    import numpy as np
    key = (step, seed, bool(licks), int(embers), w0, h0)
    arr = _FLAME_PACK.get(key)
    if arr is None:
        um = _unit_flame(step, seed, licks, embers, w0, h0)
        faces = [(f[0], f[1], f[2], f[3], None, f[4]) for f in um.faces]
        arr = r.pack(um.verts, faces)
        if len(_FLAME_PACK) >= 384:
            _FLAME_PACK.popitem(last=False)
        _FLAME_PACK[key] = arr
    else:
        _FLAME_PACK.move_to_end(key)
    if arr is None:
        return
    out = arr.copy()
    su = width / w0
    sv = height / h0
    sd = max(width, 1.0 / 3.0) / w0
    rx, rz = right
    fx, fz = fwd
    u = arr[:, 0] * su
    d = arr[:, 2] * sd
    out[:, 0] = pos[0] + rx * u + fx * d
    out[:, 1] = pos[1] + arr[:, 1] * sv
    out[:, 2] = pos[2] + rz * u + fz * d
    nx0, nz0 = arr[:, 6], arr[:, 8]
    out[:, 6] = rx * nx0 + fx * nz0
    out[:, 8] = rz * nx0 + fz * nz0
    r.add_packed(out)


def _emit_coal_packed(r, pos, rad, seed):
    if not _COAL_PACK:
        m = Mesh()
        _coal_bed(m, (0.0, 0.0, 0.0), 1.0, 0.0)
        _COAL_PACK.append(r.pack(m.verts, [(f[0], f[1], f[2], f[3], None, f[4]) for f in m.faces]))
    arr = _COAL_PACK[0]
    if arr is None:
        return
    rot = seed * 0.9
    cr, sr = math.cos(rot) * rad, math.sin(rot) * rad
    out = arr.copy()
    x0, z0 = arr[:, 0], arr[:, 2]
    out[:, 0] = pos[0] + cr * x0 - sr * z0
    out[:, 1] = pos[1] + arr[:, 1]
    out[:, 2] = pos[2] + sr * x0 + cr * z0
    r.add_packed(out)


def flame_mesh(pos, t, seed=0, size=1.0, heat=1.0, cam=None):
    """World-space flame cluster anchored at the fuel line, facing ``cam``."""
    m = Mesh()
    size = max(0.0, float(size))
    heat = max(0.0, min(2.0, float(heat)))
    if size <= 0 or heat <= 0:
        return m
    right, fwd = _flame_basis(pos, cam)
    width = size * 0.9
    height = size * 2.1 * (0.8 + 0.2 * min(heat, 1.3))
    if pos[1] < 0.5:
        _coal_bed(m, pos, size * 0.62, seed)
    um = _unit_flame(int(t // _FIRE_STEP_MS), seed, True, 6, 0.9, 2.1)
    bx, by, bz = pos
    rx, rz = right
    fx, fz = fwd
    su = width / 0.9
    sv = height / 2.1
    sd = max(width, 1.0 / 3.0) / 0.9
    base = len(m.verts)
    m.verts.extend(
        (bx + rx * (vx * su) + fx * (vz * sd),
         by + vy * sv,
         bz + rz * (vx * su) + fz * (vz * sd))
        for vx, vy, vz in um.verts
    )
    m.faces.extend(
        (tuple(i + base for i in idx), col, layer, ds, em)
        for idx, col, layer, ds, em in um.faces
    )
    return m


@lru_cache(maxsize=32)
def _smoke_base(warmth, variant):
    """Base 40x40 lumpy smoke puff at full opacity, built once per (warmth, variant)."""
    small = pygame.Surface((40, 40), pygame.SRCALPHA)
    warm = warmth / 3.0
    colour = (
        int(29 + warm * 36),
        int(30 + warm * 15),
        int(34 + warm * 2))
    for i in range(6):
        a = math.tau * i / 6 + variant * 0.47
        cx = 20 + math.cos(a) * 7
        cy = 20 + math.sin(a) * 6
        rad = 9 + ((i * 7 + variant * 3) % 4)
        points = []
        for j in range(8):
            b = math.tau * j / 8
            rr = rad * (0.88 + 0.04 * ((j * 3 + i + variant) % 4))
            points.append((
                int(cx + math.cos(b) * rr),
                int(cy + math.sin(b) * rr)))
        pygame.draw.polygon(small, (*colour, int(255 * 0.58)), points)
    pygame.draw.polygon(small, (*colour, 255), (
        (10, 12), (20, 7), (29, 12), (33, 22),
        (26, 31), (15, 33), (7, 24)))
    inner = (
        max(0, colour[0] - 8),
        max(0, colour[1] - 7),
        max(0, colour[2] - 6),
        255)
    pygame.draw.polygon(small, inner, (
        (16, 14), (25, 13), (29, 21), (23, 28), (13, 25), (12, 19)))
    return small


@lru_cache(maxsize=1024)
def _smoke_img(radius, alpha, warmth, variant):
    """Scaled, faded smoke puff cached across quantised radius/alpha buckets."""
    img = pygame.transform.scale(_smoke_base(warmth, variant), (radius * 2, radius * 2))
    img.set_alpha(alpha)
    return img


def smoke(t, seed=0, size_m=2.0):
    """Buoyant, expanding smoke with warm lower puffs and cool upper soot."""
    from cutscenes import fire3d as _f3d
    return _f3d.emit_smoke(t, seed=seed, size_m=size_m)


def fire(r, pos, t, seed=0, size=1.0, smoky=True, layer=_fx.FX_LAYER):
    """Layered flame cluster, warm halo and smoke that starts above the flames."""
    size = max(0.0, float(size))
    if size <= 0:
        return
    from cutscenes import fire3d as _f3d
    flicker = _fire_flicker(t, seed)
    _f3d.emit_fire(
        r, pos, t, seed=seed, size=size, heat=0.95 * flicker,
        smoky=smoky, embers=True, bed=True, glow=True, layer=layer,
    )


def _wall_flame_mesh(x, y, z, t, seed, size, heat):
    """Flames licking up a wall that faces -z; the wall hides their back."""
    m = Mesh()
    width = size * 0.95
    height = size * 1.55 * (0.8 + 0.2 * min(heat, 1.3))
    um = _unit_flame(int(t // _FIRE_STEP_MS), seed, True, 4, 0.95, 1.55)
    su = width / 0.95
    sv = height / 1.55
    sd = max(width, 1.0 / 3.0) / 0.95
    m.verts = [
        (x + vx * su, y + vy * sv, z - vz * sd)
        for vx, vy, vz in um.verts
    ]
    m.faces = list(um.faces)
    return m


def wall_fire(r, x, y, wall_z, t, seed=0, size=1.0,
              smoky=False, layer=_fx.FX_LAYER):
    """Fire attached to a wall whose visible face points toward -z."""
    size = max(0.0, float(size))
    if size <= 0:
        return
    from cutscenes import fire3d as _f3d
    flicker = _fire_flicker(t, seed)

    # Charred patch on the wall behind the flames.
    z = wall_z - 0.004
    w = size * 0.75
    h = size * 2.2
    m = Mesh()
    m.face([
        (x - w, y, z),
        (x + w, y, z),
        (x + w * 0.8, y + h * 0.55, z),
        (x + w * 0.3, y + h, z),
        (x - w * 0.45, y + h * 0.88, z),
        (x - w * 0.85, y + h * 0.4, z),
    ], (30, 22, 20), 2, True)
    _w.add(r, m)

    _f3d.emit_wall_fire(
        r, x, y, wall_z, t, seed=seed, size=size, heat=0.95 * flicker,
        smoky=smoky, embers=True, glow=True, layer=layer,
    )

BARN_AT = (13.0, 12.0)


def burn_fx(r, t, grow=1.0, layer=_fx.FX_LAYER):
    """Distributed roof, doorway and window fires, with shared smoke columns."""
    grow = max(0.0, min(1.0, float(grow)))
    g = 0.40 + 0.60 * grow

    # Unequal sizes and staggered seeds prevent a row of synchronised
    # identical flames. Only major sources emit full smoke columns.
    barn_sources = (
        (-3.6, 5.0, 10.0, 2.10, True),
        (-1.9, 5.1, 11.0, 1.35, False),
        (-0.5, 5.4, 12.0, 2.65, True),
        (1.2, 5.15, 12.8, 1.55, False),
        (2.8, 5.0, 14.0, 2.30, True),
        (4.2, 5.1, 10.5, 1.85, False),
        (-2.0, 0.25, 6.70, 1.65, False),
        (-0.2, 0.15, 6.66, 1.95, True),
        (1.65, 0.35, 6.68, 1.55, False),
        (0.0, 5.15, 6.72, 1.25, False),
    )
    for i, (dx, y, z, size, smoky) in enumerate(barn_sources):
        # Low sources sit in the doorway and need the scorched wall behind them.
        if y < 1.0:
            wall_fire(r, 13 + dx, y, 6.92, t, seed=3 + i * 7,
                      size=size * g, smoky=smoky, layer=layer)
        else:
            fire(r, (13 + dx, y, z), t, seed=3 + i * 7,
                 size=size * g, smoky=smoky, layer=layer)

    for i, (x, y, z, size, smoky) in enumerate((
        (-14.2, 4.5, 10.0, 1.75, True),
        (-12.0, 4.8, 9.8, 1.15, False),
        (-9.6, 4.3, 10.0, 1.50, True),
        (-13.3, 3.05, 7.0, 0.75, False),
        (-10.6, 3.05, 7.1, 0.90, False),
    )):
        fire(r, (x, y, z), t, seed=91 + i * 11,
             size=size * g, smoky=smoky, layer=layer)

    # Window flames sit just outside the wall. Honour the requested layer
    # for the glow too, so gameplay does not reveal fire through buildings.
    for i, (x, y, z) in enumerate(HOUSE_WINDOWS):
        r.add_sprite(
            (x, y, z - 0.05),
            _fx.window_glow(
                (255, 132, 40), 1.15, 1.05,
                0.52 + 0.18 * grow, t, flicker=0.15, seed=120 + i),
            layer=layer)
        fire(
            r, (x, y - 0.39, z - 0.12), t, seed=131 + i * 13,
            size=(0.55 + 0.15 * (i % 2)) * g, smoky=False, layer=layer,
        )

    # A few broad low-intensity pools connect the fire to the set on the
    # software path as well as GL; do not add one for every tongue.
    for pos, radius, intensity in (
        ((13.0, 0.06, 5.2), 5.6, 0.23),
        ((9.0, 0.06, 7.5), 3.5, 0.13),
        ((-12.0, 0.06, 5.6), 4.3, 0.15),
    ):
        r.add_sprite(
            pos,
            pool(
                (255, 119, 39), radius,
                intensity=intensity * g * _fire_flicker(t, 17),
                squash=0.42),
            layer=layer)


def burn_lights(t=0, boost=0.0):
    """Warm, independently flickering light from the major fire sources."""
    barn_f = max(0.0, _fire_flicker(t, 3) + boost)
    door_f = max(0.0, _fire_flicker(t, 52) + boost)
    house_f = max(0.0, _fire_flicker(t, 91) + boost)
    return [
        {"pos": (13, 5.5, 8), "color": (255, 139, 52),
         "intensity": 1.18 * barn_f, "range": 22},
        {"pos": (13, 2.0, 5.8), "color": (255, 112, 34),
         "intensity": 0.86 * door_f, "range": 14},
        {"pos": (-12, 2.2, 5.8), "color": (255, 146, 61),
         "intensity": 0.65 * house_f, "range": 11},
    ]


def burn_roof(r, fall):
    """Burnt barn roof: one tile slope and exposed rafters, collapsing inward."""
    W, D, H, rise = 12.0, 10.0, 4.8, 3.0
    w2 = W / 2
    ex, ey = w2 + 0.3, H - 0.3 * rise / w2
    zf, zb = -D / 2 - 0.18, D / 2 + 0.18
    ry, rx = H + rise - 4.5 * fall * fall, -0.9 * fall
    m = Mesh()
    m.face([
        (-ex, ey, zf), (-ex, ey, zb), (rx, ry, zb), (rx, ry, zf)],
        TILE_B, 2, True)
    for i in range(6):
        z = zf + (zb - zf) * (i + 0.5) / 6
        m.face([
            (rx, ry, z - 0.1), (rx, ry, z + 0.1),
            (ex, ey, z + 0.1), (ex, ey, z - 0.1)], (34, 24, 22), 2, True)
    h = Mesh()
    h.add(m, t=(BARN_AT[0], 0, BARN_AT[1]))
    _w.add(r, h)


def sparks(t, t0, seed=0, n=46, speed=7.0, life=2.6):
    """Ballistic ember burst with short trails, cooling and staggered fade."""
    life = max(0.001, float(life))

    def _render(s, sx, sy, scale, occ_depth=None, limit=0.0):
        age = (t - t0) / 1000
        if age < 0 or age > life or scale <= 0:
            return
        if occ_depth is not None:
            sh, sw = occ_depth.shape
        for i in range(n):
            h1 = ((i * 7919 + seed * 104729) % 1000) / 1000.0
            h2 = ((i * 6007 + seed * 7 + 311) % 997) / 997.0
            particle_life = life * (0.62 + 0.38 * h1)
            if age >= particle_life:
                continue
            ang = (h1 - 0.5) * 2.2
            sp = speed * (0.45 + 0.8 * h2)
            vx, vy = math.sin(ang) * sp * 0.7, math.cos(ang) * sp
            fade = max(0.0, 1.0 - age / particle_life)
            x = sx + vx * age * scale
            y = sy - (vy * age - 3.2 * age * age) * scale
            ix, iy = int(x), int(y)
            if occ_depth is not None:
                if ix < 0 or ix >= sw or iy < 0 or iy >= sh or occ_depth[iy, ix] < limit:
                    continue
            colour = (
                int(150 + 105 * fade),
                int(48 + 164 * fade),
                int(12 + 100 * fade * fade))
            px = 2 if fade > 0.55 and scale > 4 else 1
            if fade > 0.25 and scale > 2:
                previous = max(0.0, age - 0.025)
                tx = sx + vx * previous * scale
                ty = sy - (vy * previous - 3.2 * previous * previous) * scale
                pygame.draw.line(
                    s, tuple(int(c * 0.55) for c in colour),
                    (int(tx), int(ty)), (ix, iy), 1)
            s.fill(colour, (ix, iy, px, px))

    def draw(s, sx, sy, scale, z):
        _render(s, sx, sy, scale)

    def draw_depth(s, sx, sy, scale, z, occ_depth, limit):
        _render(s, sx, sy, scale, occ_depth, limit)

    # Cover the actual ballistic envelope rather than a fixed 40m box.
    extent = abs(speed) * 1.25 * life + 3.2 * life * life + 1
    draw.bounds_m = (extent, extent)
    draw.bounds_cap_px = (500, 500)
    draw.draw_depth = draw_depth
    return draw


def mix(a, b, u):
    return tuple(x + (y - x) * u for x, y in zip(a, b))


def sit_pose(**kw):
    p = dict(POSES["stand"])
    p.update(
        spine=8, head_p=10, lhip_p=88, rhip_p=88, lkn=90, rkn=90,
        lsh_p=40, lel=64, rsh_p=34, rel=70, rifle_p=84)
    p.update(kw)
    return p


def walk_pose(t, speed=1.0, tired=0.0):
    from engine.anim import locomotion_pose
    ph = t * 0.0072 * speed
    spd = max(0.8, 2.8 * speed * (1.0 - 0.35 * tired))
    p = dict(POSES["stand"])
    p.update(locomotion_pose(spd, 0.0, ph))
    sw = math.sin(ph)
    p["spine"] = p.get("spine", 4.0) + tired * 10.0
    p["head_p"] = p.get("head_p", 0.0) + tired * 12.0
    p["lsh_p"] = 6.0 - 22.0 * sw * (1.0 - 0.35 * tired)
    p["rsh_p"] = 6.0 + 22.0 * sw * (1.0 - 0.35 * tired)
    p["lel"] = 14.0 + 16.0 * max(0.0, -sw)
    p["rel"] = 14.0 + 16.0 * max(0.0, sw)
    return p


def stand_pose(**kw):
    p = dict(POSES["stand"])
    p.update(kw)
    return p


def k(t, start, length):
    """Clamped smoothstep over [start, start + length] milliseconds."""
    x = max(0.0, min(1.0, (t - start) / float(length)))
    return x * x * (3 - 2 * x)


# ---------------------------------------------------------------------------
# Background grounding helpers
#
# The field plane is a background layer without depth, so any building part
# below the visible terrain shows through it as a ghost. Buildings are
# therefore seated part-way into the slope, and their stone plinths stop just
# below the lowest ground point under the footprint.
# ---------------------------------------------------------------------------

def _background_height(x, z):
    """Height of the visible terrain at a world-space position."""
    a = math.atan2(z, x)
    radius = math.hypot(x, z)
    return max(
        0.0,
        *(_hill_y(a, radius, ring) for ring in range(len(HILL_RAD))),
    )


@lru_cache(maxsize=64)
def _footprint_range(cx, cz, half_w, half_d, steps=6):
    """(lowest, highest) terrain height across a rectangular footprint."""
    lo, hi = float("inf"), 0.0
    for ix in range(steps + 1):
        x = cx - half_w + 2.0 * half_w * ix / steps
        for iz in range(steps + 1):
            z = cz - half_d + 2.0 * half_d * iz / steps
            h = _background_height(x, z)
            lo, hi = min(lo, h), max(hi, h)
    return lo, hi


def _seat(lo, hi):
    """Floor height: cut part-way into the slope, as a real hillside house."""
    return lo + 0.45 * (hi - lo) + 0.04


def _plinth(m, cx, cz, w, d, lo, top, col):
    """Stone base from just under the lowest ground point up to the floor."""
    bottom = max(-0.04, lo - 0.35)
    h = top - bottom
    if h > 0.01:
        m.add(box(w, h, d, col, center=(cx, bottom + h / 2, cz)))
