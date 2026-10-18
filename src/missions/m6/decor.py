"""Mission 6 - stage decor, ground art and night lighting.

The four M6 spaces are authored as tiles; this module is what makes them
read as places: snow-dusted customs yards, floodlight towers over the
crossing, a freight yard with parked boxcars and a warm signal shack, and
a cold customs office.  Ground and static props are baked once per stage
into cached surfaces; only weather, lamp flicker and light cones are
per-frame.

Prop collision stays in ``world.py`` (every ``B`` tile is solid).  This
module only paints the shapes, so a prop never disagrees with the grid.
"""
import math

import pygame

from engine.core import now_s as _now_s
import engine.lighting as _lighting

from core.config import TILE_SIZE, WIDTH, HEIGHT
from core.state import STATE

from . import maps as _maps
from .meta import (
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
    NOMAN_TOWER_TILES, RAIL_DETECTOR_TILES, VOLKOV_BOXCAR_TILE,
)

T = TILE_SIZE

# Sampled by the minimap's m6 palette.
M6_TILE_BASE = {
    ".": (55, 56, 58), "g": (44, 50, 58), "L": (57, 59, 62),
    "Y": (121, 100, 54), "C": (60, 66, 74), "W": (64, 72, 80),
    "B": (56, 47, 42), "D": (96, 86, 66),
}

_PALETTE = {
    STAGE_CUSTOMS: {
        "floor": {".": (55, 56, 58), "g": (44, 50, 58)},
        "wall": {"C": (62, 68, 76), "W": (68, 75, 82), "B": (58, 52, 46)},
        "door": (98, 88, 68),
    },
    STAGE_NOMAN: {
        "floor": {".": (44, 50, 58), "g": (42, 48, 56), "L": (52, 56, 61)},
        "wall": {"C": (60, 66, 74), "W": (69, 76, 84), "B": (58, 52, 46)},
        "door": (104, 92, 66),
    },
    STAGE_RAIL: {
        "floor": {".": (43, 47, 53), "g": (43, 47, 53),
                  "L": (57, 59, 62), "Y": (121, 100, 54)},
        "wall": {"C": (58, 64, 72), "W": (65, 73, 81), "B": (56, 47, 42)},
        "door": (100, 90, 68),
    },
}
_PALETTE[STAGE_BOXCAR] = _PALETTE[STAGE_RAIL]
_PALETTE[STAGE_TRAIN] = _PALETTE[STAGE_RAIL]

_AMBIENT = {
    STAGE_CUSTOMS: (54, 60, 74),
    STAGE_NOMAN: (40, 48, 64),
    STAGE_RAIL: (44, 50, 64),
}
_AMBIENT[STAGE_BOXCAR] = _AMBIENT[STAGE_RAIL]
_AMBIENT[STAGE_TRAIN] = _AMBIENT[STAGE_RAIL]

# Lamps: (tile_x, tile_y, radius_px, colour, kind).  The kinds flicker a
# little; everything else is a steady practical.
_STAGE_LAMPS = {
    STAGE_CUSTOMS: (
        (10.0, 6.5, 150, (255, 196, 128), "steady"),
        (18.5, 6.5, 150, (255, 196, 128), "steady"),
        (16.0, 12.0, 120, (172, 196, 220), "steady"),
        (20.5, 9.0, 60, (120, 235, 160), "pulse"),
        (13.0, 17.5, 120, (176, 198, 222), "steady"),
    ),
    STAGE_NOMAN: (
        (20.0, 2.0, 130, (255, 186, 116), "steady"),
        (20.0, 15.0, 130, (255, 186, 116), "steady"),
        (8.5, 5.5, 170, (184, 208, 236), "steady"),
        (8.5, 11.5, 170, (184, 208, 236), "steady"),
        (31.5, 5.5, 170, (184, 208, 236), "steady"),
        (31.5, 11.5, 170, (184, 208, 236), "steady"),
    ),
    STAGE_RAIL: (
        (4.0, 6.5, 150, (255, 198, 132), "steady"),
        (12.0, 6.5, 150, (255, 198, 132), "steady"),
        (20.0, 6.5, 150, (255, 198, 132), "steady"),
        (28.0, 6.5, 150, (255, 198, 132), "steady"),
        (36.0, 6.5, 150, (255, 198, 132), "steady"),
        (41.0, 9.0, 110, (255, 96, 70), "bad"),
        (25.0, 10.5, 100, (255, 190, 110), "steady"),
        (2.5, 13.0, 150, (190, 210, 236), "steady"),
    ),
}
_STAGE_LAMPS[STAGE_BOXCAR] = _STAGE_LAMPS[STAGE_RAIL]
_STAGE_LAMPS[STAGE_TRAIN] = _STAGE_LAMPS[STAGE_RAIL]

_GROUND = {}
_PROPS = {}
_STAGE = STAGE_CUSTOMS


def stage():
    return _STAGE


def _h(col, row, k=0):
    return ((col * 73856093) ^ (row * 19349663) ^ (k * 83492791)) & 0xFFFFFFFF


def _shift(col, d):
    return tuple(max(0, min(255, int(v + d))) for v in col)


def reset_run():
    """Fresh campaign run: drop caches so authored art is rebuilt."""
    _GROUND.clear()
    _PROPS.clear()


def build_decor(stage_id):
    """Bind the stage and pre-bake its ground/prop art."""
    global _STAGE
    _STAGE = stage_id
    _ground_surface(stage_id)
    _prop_rows(stage_id)


# ─────────────────────────────────────────────
# Ground bake
# ─────────────────────────────────────────────
def _paint_floor(surf, stage_id, col, row, ch):
    pal = _PALETTE[stage_id]["floor"]
    base = pal.get(ch, pal["."])
    n = (_h(col, row) % 11) - 5
    x, y = col * T, row * T
    colour = _shift(base, n)
    pygame.draw.rect(surf, colour, (x, y, T, T))
    h = _h(col, row, 3)
    # Broad tonal patches first: a uniform 64 px square repeated 500 times is
    # what made the open yards read as flat cardboard.
    if h % 3 == 0:
        pygame.draw.rect(surf, _shift(colour, -5),
                         (x + (h >> 5) % 22, y + (h >> 9) % 22, T // 2, T // 2))
    elif h % 3 == 1:
        pygame.draw.rect(surf, _shift(colour, 4),
                         (x + (h >> 6) % 26, y + (h >> 11) % 26, T // 2, T // 2))
    # Snow settles in patches, never a uniform white blanket: a few
    # deterministic specks and one soft drift per ~5 tiles.
    for i in range(8):
        sx = x + 4 + ((h >> (i * 3)) % (T - 8))
        sy = y + 4 + ((h >> (i * 3 + 5)) % (T - 8))
        pygame.draw.circle(surf, _shift(colour, 8 + (h >> i) % 12),
                           (sx, sy), 1 + (i % 2))
    if h % 4 == 2:
        # Scuffed grit / slush smear.
        gw = 10 + (h >> 7) % 18
        gh = 5 + (h >> 12) % 7
        grit = pygame.Surface((gw, gh), pygame.SRCALPHA)
        pygame.draw.ellipse(grit, (206, 216, 230, 30), (0, 0, gw, gh))
        surf.blit(grit, (x + (h >> 3) % (T - gw), y + (h >> 15) % (T - gh)))
    if h % 9 == 0:
        rw = 16 + (h >> 4) % 22
        drift = pygame.Surface((rw, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(drift, (198, 210, 224, 46), drift.get_rect())
        surf.blit(drift, (x + 4, y + (h >> 8) % (T - 16)))
    if h % 11 == 5:
        # Hairline cracks / frost seams.
        cx0 = x + 8 + (h >> 7) % (T - 24)
        cy0 = y + 8 + (h >> 12) % (T - 24)
        pygame.draw.line(surf, _shift(colour, -12), (cx0, cy0),
                         (cx0 + 12 + (h % 9), cy0 + 6 + (h % 5)), 1)
        pygame.draw.line(surf, _shift(colour, -12), (cx0 + 12, cy0 + 6),
                         (cx0 + 18, cy0 + 3), 1)
    if ch == "L":
        pygame.draw.line(surf, _shift(colour, -9), (x, y), (x, y + T - 1), 1)
        pygame.draw.line(surf, _shift(colour, -9), (x, y), (x + T - 1, y), 1)
        # Paving joints so the platform does not read as one grey slab.
        pygame.draw.line(surf, _shift(colour, -6), (x, y + T // 2),
                         (x + T - 1, y + T // 2), 1)
        pygame.draw.line(surf, _shift(colour, -6), (x + T // 2, y),
                         (x + T // 2, y + T - 1), 1)
    elif ch == "Y":
        pygame.draw.rect(surf, _shift(colour, 18), (x, y + 4, T, T - 8))
        pygame.draw.rect(surf, _shift(colour, -22), (x, y + 4, T, 1))
        pygame.draw.rect(surf, _shift(colour, -22), (x, y + T - 5, T, 1))


def _paint_wall(surf, stage_id, col, row, ch):
    pal = _PALETTE[stage_id]
    base = pal["wall"].get(ch, pal["wall"]["C"])
    x, y = col * T, row * T
    h = _h(col, row, 11)
    pygame.draw.rect(surf, base, (x, y, T, T))
    pygame.draw.line(surf, _shift(base, 16), (x, y), (x + T - 1, y), 3)
    pygame.draw.line(surf, _shift(base, -14), (x, y + T - 3), (x + T - 1, y + T - 3), 3)
    # Snow sits on the crown of every wall: the border is what the player
    # reads first, so a bare concrete band made the map edge look unbuilt.
    cap = 4 + (h % 3)
    pygame.draw.rect(surf, (196, 208, 224), (x, y + 1, T, cap))
    pygame.draw.rect(surf, (168, 182, 202), (x, y + 1 + cap, T, 1))
    if ch == "W":
        for lx in range(x + 4, x + T - 2, 9):
            pygame.draw.line(surf, _shift(base, -8), (lx, y + cap + 4),
                             (lx, y + T - 4), 1)
        # A post at the tile seam, with its cap catching the snow.
        px = x + 2
        pygame.draw.line(surf, (44, 48, 54), (px, y + cap), (px, y + T - 2), 3)
        pygame.draw.circle(surf, (188, 200, 218), (px, y + cap + 2), 3)
        if (col + row) % 3 == 0:
            pygame.draw.line(surf, _shift(base, 12), (x + 2, y + cap + 2),
                             (x + T - 2, y + cap + 2), 1)
        # Sagging wire between the posts.
        wy = y + cap + 9
        pygame.draw.line(surf, (52, 56, 62), (x + 2, wy), (x + T - 2, wy + 3), 1)
    elif ch == "C":
        pygame.draw.line(surf, _shift(base, -9), (x + T - 2, y + cap + 2),
                         (x + T - 2, y + T - 2), 1)
        # Cast-in joints every tile, and the odd rusted rebar nub.
        pygame.draw.line(surf, _shift(base, -11), (x, y + T // 2),
                         (x + T - 1, y + T // 2), 1)
        if h % 5 == 0:
            pygame.draw.line(surf, (96, 70, 52), (x + T // 2 - 4, y + T // 2),
                             (x + T // 2 + 4, y + T // 2), 2)
    elif ch == "B":
        pygame.draw.line(surf, _shift(base, -8), (x + 3, y + 3), (x + T - 4, y + 3), 1)


def _paint_door(surf, stage_id, col, row):
    x, y = col * T, row * T
    pal = _PALETTE[stage_id]
    floor = pal["floor"].get("g", pal["floor"]["."])
    pygame.draw.rect(surf, _shift(floor, -6), (x, y, T, T))
    pygame.draw.rect(surf, pal["door"], (x + 2, y + 2, T - 4, T - 4), 2)
    pygame.draw.line(surf, _shift(pal["door"], 22), (x + 8, y + 8), (x + T - 8, y + 8), 1)
    pygame.draw.circle(surf, _shift(pal["door"], -24), (x + T - 12, y + T // 2), 2)
    # Cold light spilling in from the open doorway.
    pygame.draw.rect(surf, _shift(floor, 9), (x + 4, y + 4, T - 8, 6))


def _customs_detail(surf, grid):
    """Tyre ruts, border paint and the queue's long wait."""
    for row in (13, 15):
        y = row * T + T // 2
        pygame.draw.line(surf, (31, 35, 41), (0, y - 9), (7 * T, y - 9), 3)
        pygame.draw.line(surf, (31, 35, 41), (0, y + 9), (7 * T, y + 9), 3)
    y = 2 * T + T // 2
    for x in range(2 * T, 28 * T, 34):
        pygame.draw.line(surf, (128, 104, 52), (x, y), (x + 18, y), 2)
    y = 18 * T
    for x in range(2 * T, 28 * T, 34):
        pygame.draw.line(surf, (110, 92, 50), (x, y), (x + 18, y), 2)
    # Queue footprints (families stood here a long time).
    for i in range(26):
        fx = (3 * T) + (_h(i, 7) % (3 * T))
        fy = (13 * T) + (_h(i, 9) % (3 * T))
        pygame.draw.line(surf, (54, 60, 68), (fx, fy), (fx + 2, fy + 6), 1)
    # Interior entrance mats.
    pygame.draw.rect(surf, (48, 46, 42), (14 * T + 4, 11 * T + 2, 2 * T - 8, T - 4))
    pygame.draw.rect(surf, (48, 46, 42), (16 * T + 2, 3 * T + 4, T - 4, T - 8))


def _noman_detail(surf, grid):
    """The crossing: lane paint, footprints, gate stripes and snow banks."""
    cx = 20 * T + T // 2
    for y in range(4 * T, 14 * T, 46):
        pygame.draw.line(surf, (122, 106, 60), (cx, y), (cx, y + 22), 2)
    pygame.draw.line(surf, (86, 92, 100), (8 * T, 3 * T), (8 * T, 15 * T), 1)
    pygame.draw.line(surf, (86, 92, 100), (32 * T, 3 * T), (32 * T, 15 * T), 1)
    # A single set of boot prints from the south gate to the first gap.
    for i in range(22):
        y = 16 * T - i * 26
        x = cx + int(math.sin(i * 0.35) * 18) + (6 if i % 2 else -6)
        pygame.draw.ellipse(surf, (33, 38, 45), (x, y, 5, 9))
    for row in (1, 15):
        y = row * T + T // 2
        for x in range(17 * T, 24 * T, 22):
            pygame.draw.line(surf, (146, 126, 66), (x, y - 8), (x + 12, y + 8), 2)
    for x, y in ((2, 3), (2, 14), (37, 3), (37, 14)):
        pygame.draw.ellipse(surf, (132, 144, 160), (x * T - 18, y * T, 2 * T + 36, 20))


def _rail_detail(surf, grid):
    """Rails, sleepers, platform tactiles and yard gravel."""
    for row in (7, 11, 16, 19, 22):
        y = row * T
        pygame.draw.line(surf, (58, 54, 48), (2 * T, y), (43 * T, y), 9)
        pygame.draw.line(surf, (112, 110, 104), (2 * T, y - 2), (43 * T, y - 2), 2)
        pygame.draw.line(surf, (128, 124, 116), (2 * T, y + 3), (43 * T, y + 3), 1)
        for x in range(2 * T, 43 * T, 44):
            pygame.draw.line(surf, (48, 43, 38), (x, y - 8), (x + 20, y + 8), 4)
    for x in range(T, 45 * T, 18):
        pygame.draw.rect(surf, (146, 116, 50), (x, 6 * T + 8, 10, T - 16))
    for i in range(240):
        gx = (_h(i, 3) % (45 * T)) + T
        gy = (_h(i, 8) % (24 * T)) + T
        if grid[gy // T][gx // T] in "g":
            pygame.draw.circle(surf, (54, 58, 64), (gx, gy), 1)
    for x, y in ((1, 8), (1, 20), (44, 8), (44, 20)):
        pygame.draw.ellipse(surf, (128, 140, 156), (x * T - 14, y * T, 2 * T + 26, 22))


# ─────────────────────────────────────────────
# Dressing kit (flat only)
# ─────────────────────────────────────────────
# Everything below paints onto the *ground* surface: no footprint, no
# collision, nothing that reads as a prop you should be able to hide behind.
# That keeps the "what you see is what blocks you" rule intact (collision is
# still only the map's B/W/C tiles) while giving the big open yards
# something to look at.
_SNOW = (198, 210, 226)
_SNOW_DIM = (168, 182, 202)


def _snow_bank(surf, x, y, w, h, seed, a=52):
    """Soft wind-blown drift: three offset ellipses, never a white blob."""
    if w < 6 or h < 4:
        return
    bank = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(bank, (*_SNOW, a), (0, 0, w, h))
    pygame.draw.ellipse(bank, (*_SNOW, a + 18),
                        (w // 6, h // 4, max(4, w // 2), max(3, h // 2)))
    pygame.draw.ellipse(bank, (*_SNOW_DIM, a - 14),
                        (w // 3 + (seed % 5), h // 2, max(3, w // 3), max(2, h // 3)))
    surf.blit(bank, (x, y))


def _wire_coils(surf, x0, y0, x1, y1, seed, col=(74, 78, 84)):
    """Razor wire: overlapping loops along a line, with a shadow under them."""
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy)
    if span < 8:
        return
    ux, uy = dx / span, dy / span
    nx, ny = -uy, ux
    step = 11.0
    n = max(2, int(span / step))
    for i in range(n):
        f = i / float(n)
        cx = x0 + dx * f
        cy = y0 + dy * f
        r = 7 + ((_h(i, seed, 5) >> 3) % 4)
        pygame.draw.ellipse(surf, (24, 26, 30),
                            (cx - r + nx * 2, cy - r * 0.7 + ny * 2 + 3,
                             r * 2, r * 1.5), 1)
        pygame.draw.ellipse(surf, col, (cx - r, cy - r * 0.7, r * 2, r * 1.5), 1)
        if i % 3 == 0:
            pygame.draw.line(surf, (92, 96, 102), (cx - nx * r, cy - ny * r * 0.7),
                             (cx + nx * r, cy + ny * r * 0.7), 1)


def _fence_run(surf, x0, y0, x1, y1, seed, post=(48, 52, 58)):
    """A line of posts with two sagging wires - reads as a perimeter fence."""
    dx, dy = x1 - x0, y1 - y0
    span = math.hypot(dx, dy)
    if span < 16:
        return
    step = 26.0
    n = max(2, int(span / step))
    pts = [(x0 + dx * (i / float(n)), y0 + dy * (i / float(n))) for i in range(n + 1)]
    for i in range(len(pts) - 1):
        ax, ay = pts[i]
        bx, by = pts[i + 1]
        mx, my = (ax + bx) / 2, (ay + by) / 2 + 3
        pygame.draw.line(surf, (58, 62, 68), (ax, ay - 1), (mx, my - 1), 1)
        pygame.draw.line(surf, (58, 62, 68), (mx, my - 1), (bx, by - 1), 1)
        pygame.draw.line(surf, (58, 62, 68), (ax, ay + 3), (mx, my + 3), 1)
        pygame.draw.line(surf, (58, 62, 68), (mx, my + 3), (bx, by + 3), 1)
    for i, (px, py) in enumerate(pts):
        pygame.draw.line(surf, (26, 28, 32), (px + 1, py), (px + 1, py + 6), 2)
        pygame.draw.line(surf, post, (px, py - 2), (px, py + 5), 2)
        pygame.draw.circle(surf, (186, 198, 214), (px, py - 3), 2)


def _sandbags(surf, x, y, w, h, seed):
    """A low sandbag nest: staggered rounded bags with a snow cap."""
    bw, bh = 15, 8
    rows = max(1, h // (bh + 1))
    cols = max(1, w // (bw + 1))
    pygame.draw.ellipse(surf, (10, 12, 16, 110), (x - 2, y + h - 6, w + 6, 12))
    for r in range(rows):
        off = (bw // 2) if r % 2 else 0
        for c in range(cols):
            bx = x + c * (bw + 1) + off
            by = y + r * (bh + 1)
            if bx + bw > x + w:
                continue
            hh = _h(c, r, seed)
            col = (94, 86, 66) if hh % 3 else (86, 80, 62)
            pygame.draw.rect(surf, col, (bx, by, bw, bh), border_radius=3)
            pygame.draw.rect(surf, _shift(col, 16), (bx + 1, by + 1, bw - 2, 3),
                             border_radius=2)
            if hh % 4 == 0:
                pygame.draw.rect(surf, (188, 200, 216), (bx + 2, by, bw - 4, 2),
                                 border_radius=1)


def _ice_sheet(surf, x, y, w, h, seed):
    """Frozen puddle: pale sheet with a bright rim and cracks."""
    ice = pygame.Surface((w, h), pygame.SRCALPHA)
    pygame.draw.ellipse(ice, (156, 178, 202, 58), (0, 0, w, h))
    pygame.draw.ellipse(ice, (196, 214, 232, 34), (w // 8, h // 5, w * 3 // 4, h * 2 // 3))
    pygame.draw.ellipse(ice, (210, 226, 240, 70), (0, 0, w, h), 1)
    for i in range(3):
        hh = _h(i, seed, 7)
        ax = w // 5 + (hh % max(4, w // 2))
        ay = h // 4 + ((hh >> 6) % max(4, h // 2))
        pygame.draw.line(ice, (232, 242, 250, 46), (ax, ay),
                         (ax + 8 + hh % 12, ay + 3 + (hh >> 4) % 8), 1)
    surf.blit(ice, (x, y))


def _tracks(surf, x, y, length, angle, gap=14, col=(28, 32, 38)):
    """Twin ruts (tyre or tracked vehicle) crossing the yard."""
    a = math.radians(angle)
    ux, uy = math.cos(a), math.sin(a)
    nx, ny = -uy, ux
    for side in (-1, 1):
        ox = x + nx * gap * side
        oy = y + ny * gap * side
        pygame.draw.line(surf, col, (ox, oy), (ox + ux * length, oy + uy * length),
                         3 if gap > 12 else 2)


def _crater(surf, x, y, r, seed):
    """Old impact: dark bowl, bright rim, thrown-out spoil."""
    pygame.draw.ellipse(surf, (34, 38, 44), (x - r, y - r * 0.7, r * 2, r * 1.4))
    pygame.draw.ellipse(surf, (26, 30, 36), (x - r * 0.66, y - r * 0.46,
                                             r * 1.32, r * 0.92))
    pygame.draw.ellipse(surf, (66, 72, 80), (x - r, y - r * 0.7, r * 2, r * 1.4), 1)
    for i in range(9):
        hh = _h(i, seed, 3)
        ang = (i / 9.0) * math.tau
        d = r * (1.05 + (hh % 30) / 100.0)
        sx = x + math.cos(ang) * d
        sy = y + math.sin(ang) * d * 0.7
        pygame.draw.circle(surf, (58, 62, 70), (int(sx), int(sy)), 1 + hh % 2)


def _debris(surf, x, y, r, seed, col=(58, 62, 68)):
    """Scattered litter/shell cases inside a radius."""
    n = 6 + (_h(x, y, seed) % 7)
    for i in range(n):
        hh = _h(i, seed, 13)
        ang = (hh % 360) * math.pi / 180.0
        d = (hh >> 9) % max(4, r)
        px = x + math.cos(ang) * d
        py = y + math.sin(ang) * d * 0.75
        if hh % 5 == 0:
            pygame.draw.line(surf, _shift(col, 16), (px, py), (px + 3, py + 1), 1)
        else:
            pygame.draw.circle(surf, col, (int(px), int(py)), 1)


def _papers(surf, x, y, r, seed):
    """Blown paperwork - the customs post was abandoned mid-shift."""
    for i in range(5 + (_h(x, y, seed) % 5)):
        hh = _h(i, seed, 17)
        ang = (hh % 360) * math.pi / 180.0
        d = (hh >> 8) % max(4, r)
        px = int(x + math.cos(ang) * d)
        py = int(y + math.sin(ang) * d * 0.7)
        w = 4 + hh % 4
        h = 3 + (hh >> 5) % 3
        pygame.draw.rect(surf, (176, 172, 158), (px, py, w, h))
        pygame.draw.rect(surf, (198, 194, 180), (px, py, w, 1))


def _oil_stain(surf, x, y, r, seed):
    stain = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
    pygame.draw.ellipse(stain, (12, 12, 14, 96), (0, 0, r * 2, int(r * 1.5)))
    pygame.draw.ellipse(stain, (18, 18, 22, 60), (r // 3, r // 3, r, int(r * 0.8)))
    surf.blit(stain, (x - r, y - int(r * 0.75)))


def _scrub(surf, x, y, seed, col=(56, 54, 44)):
    """A dead bush poking through the snow."""
    hh = _h(x, y, seed)
    for i in range(5):
        ang = -math.pi / 2 + ((i - 2) * 0.42) + ((hh >> (i * 3)) % 12) / 100.0
        ln = 6 + (hh >> (i * 4)) % 9
        ex = x + math.cos(ang) * ln
        ey = y + math.sin(ang) * ln
        pygame.draw.line(surf, col, (x, y), (ex, ey), 1)
        if i % 2 == 0:
            pygame.draw.line(surf, col, (ex, ey), (ex + 3, ey - 2), 1)
    pygame.draw.circle(surf, (150, 162, 178), (x, y + 2), 3)


def _drain(surf, x, y, seed):
    """Grating / manhole: a small dark disc with slots."""
    pygame.draw.ellipse(surf, (30, 32, 36), (x - 11, y - 8, 22, 16))
    pygame.draw.ellipse(surf, (62, 66, 72), (x - 11, y - 8, 22, 16), 1)
    for i in range(4):
        pygame.draw.line(surf, (20, 22, 26), (x - 6 + i * 4, y - 5),
                         (x - 6 + i * 4, y + 5), 1)


def _snow_line(surf, x0, y0, x1, y1, w=4):
    """Thin snow line along the foot of a wall or boxcar."""
    pygame.draw.line(surf, (176, 190, 208), (x0, y0), (x1, y1), w)
    pygame.draw.line(surf, (204, 216, 230), (x0, y0 - 1), (x1, y1 - 1), max(1, w - 2))


def _customs_dress(surf, grid):
    """The post's yard and offices: fences, frozen puddles, abandoned kit."""
    h, w = len(grid), len(grid[0])
    # Inner fence line along the west and east borders of the yard.
    _fence_run(surf, T, 12 * T, T, 19 * T, 21)
    _fence_run(surf, 29 * T - 2, 12 * T, 29 * T - 2, 19 * T, 23)
    _fence_run(surf, 1 * T, 19 * T - 3, 29 * T, 19 * T - 3, 25)
    # Frozen puddles where the queue idled.
    for i, (cx, cy, rw, rh) in enumerate((
            (3.2, 13.4, 74, 34), (6.0, 15.6, 58, 26), (11.5, 14.2, 46, 22),
            (26.5, 16.5, 66, 28), (23.0, 18.0, 52, 24))):
        _ice_sheet(surf, int(cx * T), int(cy * T), rw, rh, i)
    # Snow banked against the frozen cars and the gate posts.
    for (cx, cy) in ((2, 12), (5, 14), (2, 16), (8, 13)):
        _snow_bank(surf, cx * T - 6, cy * T + T - 10, T + 12, 18, cx + cy)
    _snow_bank(surf, 13 * T, 11 * T + 8, 3 * T, 20, 41)
    _snow_bank(surf, 16 * T, 2 * T + 10, 2 * T, 18, 43)
    # Tyre ruts curving out of the queue into the open yard.
    _tracks(surf, 7 * T, 12 * T, 10 * T, 26, gap=17)
    _tracks(surf, 7 * T, 17 * T, 12 * T, -18, gap=17)
    # Dropped paperwork + litter where people waited and where they ran.
    _papers(surf, 4 * T, 14 * T, 46, 51)
    _papers(surf, 12 * T, 12 * T, 38, 53)
    _papers(surf, 19 * T, 9 * T, 40, 55)
    _debris(surf, 11 * T, 17 * T, 60, 57)
    _debris(surf, 25 * T, 13 * T, 54, 59)
    _debris(surf, 9 * T, 5 * T, 44, 61)
    # Sandbag nest watching the south doors.
    _sandbags(surf, 12 * T + 4, 12 * T - 4, 2 * T - 8, 20, 63)
    # Drain in the yard + one inside the processing hall.
    _drain(surf, 17 * T + 10, 16 * T + 8, 65)
    _drain(surf, 21 * T + 12, 9 * T + 20, 67)
    # A dark stain under the file cabinets (years of a leaking radiator).
    _oil_stain(surf, 18 * T + 16, 7 * T + 12, 30, 69)
    # ── inside the post ─────────────────────────────────────────────────
    # The processing hall and file room are the emptiest floor in the
    # mission; give the eye counters, chair marks and abandoned paperwork.
    for i, (cx, cy) in enumerate((
            (9.0, 4.6), (12.0, 4.6), (9.0, 9.4), (13.5, 9.4),
            (19.0, 4.9), (20.5, 4.9), (18.5, 9.4), (21.0, 9.4))):
        # Chair footprints pulled out from the counters.
        _oil_stain(surf, int(cx * T), int(cy * T), 9, 71 + i)
        pygame.draw.circle(surf, (58, 54, 48), (int(cx * T), int(cy * T)), 7, 1)
    for i, (cx, cy) in enumerate(((10.5, 6.0), (15.5, 6.6), (20.0, 6.2),
                                  (12.0, 10.0), (18.0, 8.0), (21.5, 7.4))):
        _papers(surf, int(cx * T), int(cy * T), 34, 81 + i)
    # Water / oil on the hall floor and the drag marks of something heavy.
    _ice_sheet(surf, int(9.5 * T), int(7.2 * T), 74, 30, 91)
    _oil_stain(surf, int(16.5 * T), int(9.8 * T), 34, 93)
    pygame.draw.line(surf, (38, 38, 40), (12 * T, 7 * T + 30), (18 * T, 6 * T + 18), 3)
    pygame.draw.line(surf, (48, 48, 50), (12 * T, 7 * T + 33), (18 * T, 6 * T + 21), 2)
    # Snow blown in through the two doorways.
    _snow_bank(surf, 14 * T - 4, 11 * T + 6, 2 * T + 8, 20, 95)
    _snow_bank(surf, 16 * T - 6, 3 * T + 4, T + 12, 16, 97)
    # Scorch where the queue burned a fire to stay warm.
    _oil_stain(surf, int(4.6 * T), int(17.2 * T), 24, 99)
    _crater(surf, int(4.6 * T), int(17.2 * T), 16, 101)
    _debris(surf, int(4.6 * T), int(17.2 * T), 40, 103, col=(52, 46, 42))


def _noman_dress(surf, grid):
    """The crossing: wire, craters, blown snow and the marks of a watched strip."""
    h, w = len(grid), len(grid[0])
    # Razor wire lashed to both faces of every chicane.
    for (cx, r0, r1) in ((7, 4, 9), (12, 9, 14), (20, 4, 7), (27, 10, 15), (32, 5, 9)):
        _wire_coils(surf, cx * T - 8, r0 * T, cx * T - 8, r1 * T + T, cx)
        _wire_coils(surf, cx * T + T + 8, r0 * T, cx * T + T + 8, r1 * T + T, cx + 100)
    for (rx, c0, c1) in ((4, 13, 18), (12, 23, 29), (8, 29, 34)):
        _wire_coils(surf, c0 * T, rx * T - 8, c1 * T + T, rx * T - 8, rx)
        _wire_coils(surf, c0 * T, rx * T + T + 8, c1 * T + T, rx * T + T + 8, rx + 100)
    # Snow banked against every barrier and tower base.
    for (x, y) in ((15, 7), (24, 7), (9, 11), (35, 14)):
        _snow_bank(surf, x * T - 8, y * T + T - 12, 2 * T + 16, 22, x + y)
    for (x, y) in NOMAN_TOWER_TILES:
        _snow_bank(surf, x * T - 14, y * T + 2 * T - 14, T + 28, 24, x * 3 + y)
    # Craters and the tracked vehicle that came through before dawn.
    _crater(surf, 15 * T, 10 * T, 34, 71)
    _crater(surf, 29 * T, 6 * T, 26, 73)
    _tracks(surf, 2 * T, 8 * T, 16 * T, 4, gap=22)
    _tracks(surf, 22 * T, 12 * T, 17 * T, -7, gap=22)
    # Drifts along the north and south aprons (the wind funnels there).
    for i in range(7):
        _snow_bank(surf, int((3 + i * 5.2) * T), 3 * T - 6 + (i % 3) * 5,
                   T + 26, 20, 80 + i)
        _snow_bank(surf, int((2 + i * 5.4) * T), 13 * T + 20 + (i % 2) * 6,
                   T + 22, 18, 90 + i)
    # Footprints crisscrossing the strip: other people tried this.
    for k in range(3):
        _debris(surf, (8 + k * 11) * T, (7 + (k % 2) * 4) * T, 52, 101 + k,
                col=(38, 44, 52))
    _debris(surf, 18 * T, 6 * T, 60, 111, col=(38, 44, 52))
    _debris(surf, 33 * T, 12 * T, 56, 113, col=(38, 44, 52))
    # Dead scrub pushing through where the ground was never cleared.
    for (cx, cy, sd) in ((5, 12, 121), (36, 9, 123), (10, 6, 125),
                         (30, 14, 127), (25, 4, 129), (16, 12, 131)):
        _scrub(surf, cx * T + 20, cy * T + 24, sd)
    # Hazard line and a drain at the gate thresholds.
    _snow_line(surf, 17 * T, 15 * T + T - 4, 24 * T, 15 * T + T - 4, 3)
    _drain(surf, 20 * T + 30, 16 * T + 14, 133)


def _rail_dress(surf, grid):
    """Freight yard: oil, ice, cable, and the litter of a working platform."""
    h, w = len(grid), len(grid[0])
    # Snow piled along the whole platform edge and every boxcar flank.
    _snow_line(surf, 1 * T, 7 * T + 2, 45 * T, 7 * T + 2, 4)
    _snow_line(surf, 6 * T, 6 * T + 4, 42 * T, 6 * T + 4, 3)
    for (x, y, bw, bh) in ((4, 10, 12, 2), (20, 9, 10, 2), (34, 12, 8, 2),
                           (6, 17, 12, 2), (24, 18, 10, 2), (36, 20, 6, 2),
                           (4, 21, 8, 2)):
        _snow_line(surf, x * T, (y + bh) * T - 2, (x + bw) * T, (y + bh) * T - 2, 4)
        _snow_bank(surf, x * T + 8, (y + bh) * T - 8, bw * T - 16, 16, x + y)
    # Platform furniture marks: benches, a kiosk footprint, ticket litter.
    for i, cx in enumerate((5.0, 13.5, 22.0, 30.5, 38.0)):
        _oil_stain(surf, int(cx * T), int(3.6 * T), 16, 141 + i)
        _debris(surf, int(cx * T), int(4.6 * T), 30, 151 + i, col=(52, 54, 58))
    _papers(surf, 17 * T, 4 * T, 52, 161)
    _papers(surf, 33 * T, 5 * T, 44, 163)
    # Ice between the rails where the yard never drains.
    for i, (cx, cy, rw, rh) in enumerate((
            (12.0, 8.4, 92, 30), (27.0, 13.6, 78, 26), (9.0, 15.2, 66, 24),
            (33.0, 17.4, 84, 28), (18.0, 20.6, 72, 26), (39.0, 9.0, 60, 22))):
        _ice_sheet(surf, int(cx * T), int(cy * T), rw, rh, 171 + i)
    # Oil where engines stood, cable drums left flat, spill mats.
    for i, (cx, cy) in enumerate(((7.0, 13.0), (21.0, 12.0), (37.0, 14.5),
                                  (14.0, 20.0), (28.0, 21.0))):
        _oil_stain(surf, int(cx * T), int(cy * T), 26 + i * 3, 181 + i)
    for i, (cx, cy) in enumerate(((16.5, 13.4), (31.5, 16.8), (11.0, 19.4))):
        pygame.draw.circle(surf, (46, 42, 36), (int(cx * T), int(cy * T)), 20)
        pygame.draw.circle(surf, (30, 28, 24), (int(cx * T), int(cy * T)), 20, 2)
        pygame.draw.circle(surf, (62, 56, 46), (int(cx * T), int(cy * T)), 8)
        pygame.draw.line(surf, (58, 52, 44), (int(cx * T) - 18, int(cy * T)),
                         (int(cx * T) + 18, int(cy * T)), 1)
        _snow_bank(surf, int(cx * T) - 22, int(cy * T) + 14, 44, 12, 191 + i)
    # Litter and shell cases near the crates and the signal office.
    _debris(surf, 18 * T, 15 * T, 62, 201, col=(54, 56, 60))
    _debris(surf, 31 * T, 21 * T, 56, 203, col=(54, 56, 60))
    _debris(surf, 14 * T, 8 * T, 48, 205, col=(54, 56, 60))
    _debris(surf, 40 * T, 12 * T, 60, 207, col=(54, 56, 60))
    # Drain grates along the platform.
    for i, (cx, cy) in enumerate(((9.0, 6.6), (24.0, 6.6), (40.0, 6.6))):
        _drain(surf, int(cx * T), int(cy * T), 211 + i)
    # Perimeter fence inside the border walls, with a gate gap at the yard mouth.
    _fence_run(surf, 1 * T, 8 * T, 1 * T, 14 * T, 221)
    _fence_run(surf, 44 * T, 8 * T, 44 * T, 15 * T, 223)
    _fence_run(surf, 1 * T, 23 * T, 44 * T, 23 * T, 225)


# Contact shadow bands, baked once: a soft dark edge where the floor meets a
# wall or a prop.  Without it every prop looked pasted onto the ground.
_AO_DEPTH = 18
_AO_BANDS = {}


def _ao_band(side, length):
    """Cached shadow band for one side of a tile ('s','n','e','w')."""
    key = (side, length)
    band = _AO_BANDS.get(key)
    if band is not None:
        return band
    if side in ("s", "n"):
        band = pygame.Surface((length, _AO_DEPTH), pygame.SRCALPHA)
        for i in range(_AO_DEPTH):
            a = int(58 * (1.0 - i / float(_AO_DEPTH)) ** 1.7)
            pygame.draw.line(band, (6, 8, 12, a), (0, i), (length - 1, i))
        if side == "n":
            band = pygame.transform.flip(band, False, True)
    else:
        band = pygame.Surface((_AO_DEPTH, length), pygame.SRCALPHA)
        for i in range(_AO_DEPTH):
            a = int(58 * (1.0 - i / float(_AO_DEPTH)) ** 1.7)
            pygame.draw.line(band, (6, 8, 12, a), (i, 0), (i, length - 1))
        if side == "w":
            band = pygame.transform.flip(band, True, False)
    _AO_BANDS[key] = band
    return band


def _ground_ao(surf, grid):
    """Bake contact shadows along every solid edge and under every prop."""
    h, w = len(grid), len(grid[0])

    def solid(cx, cy):
        return grid[cy][cx] in "CWB"

    for row in range(h):
        for col in range(w):
            if not solid(col, row):
                continue
            x, y = col * T, row * T
            if row + 1 < h and not solid(col, row + 1):
                surf.blit(_ao_band("s", T), (x, y + T))
            if row - 1 >= 0 and not solid(col, row - 1):
                surf.blit(_ao_band("n", T), (x, y - _AO_DEPTH))
            if col + 1 < w and not solid(col + 1, row):
                surf.blit(_ao_band("e", T), (x + T, y))
            if col - 1 >= 0 and not solid(col - 1, row):
                surf.blit(_ao_band("w", T), (x - _AO_DEPTH, y))


def _ground_surface(stage_id):
    cached = _GROUND.get(stage_id)
    if cached is not None:
        return cached
    grid = _maps.grid_for(stage_id)
    h, w = len(grid), len(grid[0])
    surf = pygame.Surface((w * T, h * T))
    for row in range(h):
        for col in range(w):
            ch = grid[row][col]
            if ch in "CWB":
                _paint_wall(surf, stage_id, col, row, ch)
            elif ch == "D":
                _paint_door(surf, stage_id, col, row)
            else:
                _paint_floor(surf, stage_id, col, row, ch)
    if stage_id == STAGE_CUSTOMS:
        _customs_detail(surf, grid)
        _customs_dress(surf, grid)
    elif stage_id == STAGE_NOMAN:
        _noman_detail(surf, grid)
        _noman_dress(surf, grid)
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        _rail_detail(surf, grid)
        _rail_dress(surf, grid)
    _ground_ao(surf, grid)
    _GROUND[stage_id] = surf
    return surf


def draw_ground(surface, cam_x, cam_y, stage_id=None):
    stage_id = stage_id or _STAGE
    surf = _ground_surface(stage_id)
    surface.blit(surf, (-int(cam_x), -int(cam_y)))


# ─────────────────────────────────────────────
# Static props (B-tile components)
# ─────────────────────────────────────────────
def _components(stage_id):
    grid = _maps.structure_for(stage_id)
    h, w = len(grid), len(grid[0])
    seen = set()
    out = []
    for row in range(h):
        for col in range(w):
            if grid[row][col] != "B" or (col, row) in seen:
                continue
            stack = [(col, row)]
            seen.add((col, row))
            xs, ys = [col], [row]
            while stack:
                cx, cy = stack.pop()
                for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                    if not (0 <= nx < w and 0 <= ny < h):
                        continue
                    if (nx, ny) in seen or grid[ny][nx] != "B":
                        continue
                    seen.add((nx, ny))
                    xs.append(nx)
                    ys.append(ny)
                    stack.append((nx, ny))
            x0, y0 = min(xs), min(ys)
            out.append((x0, y0, max(xs) - x0 + 1, max(ys) - y0 + 1))
    return sorted(out, key=lambda c: (c[1], c[0]))


def _new_prop(w_px, h_px, over=0, side=0):
    surf = pygame.Surface((w_px + side * 2, h_px + over), pygame.SRCALPHA)
    return surf, side, over


def _draw_car(surf, x, y, w, h, seed):
    colours = ((96, 62, 54), (58, 72, 88), (82, 82, 78), (76, 66, 82))
    body = colours[seed % len(colours)]
    pygame.draw.ellipse(surf, (10, 12, 15, 90), (x + 4, y + h - 10, w - 8, 10))
    pygame.draw.rect(surf, body, (x + 3, y + 10, w - 6, h - 18), border_radius=7)
    pygame.draw.rect(surf, _shift(body, 12), (x + 7, y + 8, w - 14, h - 22), border_radius=6)
    pygame.draw.rect(surf, (30, 40, 48), (x + 10, y + 14, w - 20, 7), border_radius=2)
    pygame.draw.rect(surf, (26, 34, 40), (x + 10, y + h - 20, w - 20, 6), border_radius=2)
    for wx in (x + 14, x + w - 20):
        pygame.draw.rect(surf, (18, 18, 20), (wx, y + 6, 7, 5), border_radius=2)
        pygame.draw.rect(surf, (18, 18, 20), (wx, y + h - 11, 7, 5), border_radius=2)
    pygame.draw.rect(surf, (206, 216, 228), (x + 5, y + 8, w - 10, 4), border_radius=2)
    pygame.draw.circle(surf, (226, 220, 190), (x + w - 12, y + h // 2), 3)


def _draw_barrier(surf, x, y, w, h):
    pygame.draw.ellipse(surf, (10, 12, 15, 100), (x + 3, y + h - 9, w - 6, 9))
    pts = [(x + 4, y + h - 4), (x + 2, y + 8), (x + w - 4, y + 8), (x + w - 6, y + h - 4)]
    pygame.draw.polygon(surf, (116, 112, 104), pts)
    pygame.draw.polygon(surf, (142, 138, 128), pts, 2)
    pygame.draw.rect(surf, (188, 198, 212), (x + 5, y + 6, w - 12, 4), border_radius=2)
    for sx in (x + w // 3, x + 2 * w // 3):
        pygame.draw.line(surf, (86, 82, 76), (sx, y + 12), (sx, y + h - 7), 2)


def _draw_boxcar(surf, x, y, w, h, seed, volkov=False):
    body = (104, 66, 54) if volkov else ((92, 66, 52), (74, 68, 58), (88, 58, 50))[seed % 3]
    pygame.draw.ellipse(surf, (8, 9, 12, 110), (x + 6, y + h - 8, w - 12, 10))
    pygame.draw.rect(surf, (28, 24, 20), (x + 8, y + h - 12, w - 16, 8))
    pygame.draw.rect(surf, body, (x + 4, y + 14, w - 8, h - 26))
    pygame.draw.rect(surf, _shift(body, 10), (x + 8, y + 10, w - 16, 7))
    for rx in range(x + 18, x + w - 14, 26):
        pygame.draw.line(surf, _shift(body, -14), (rx, y + 18), (rx, y + h - 16), 2)
    step = max(2, w // T)
    for i in range(step):
        bx = x + 12 + i * (w - 24) // step
        pygame.draw.rect(surf, (54, 42, 34), (bx, y + h - 12, 12, 6), border_radius=2)
    door_x = x + w // 2 - 18
    pygame.draw.rect(surf, _shift(body, -20), (door_x, y + 18, 36, h - 30))
    pygame.draw.line(surf, _shift(body, -32), (door_x, y + 18), (door_x, y + h - 12), 2)
    pygame.draw.line(surf, _shift(body, -32), (door_x + 36, y + 18), (door_x + 36, y + h - 12), 2)
    pygame.draw.rect(surf, (200, 210, 224), (x + 6, y + 10, w - 12, 6), border_radius=3)
    if volkov:
        pygame.draw.rect(surf, (146, 46, 42), (x + 10, y + 20, w - 20, 6))
        pygame.draw.rect(surf, (232, 198, 96), (door_x + 6, y + 24, 24, h - 40), 2)
        pygame.draw.circle(surf, (255, 196, 110), (door_x + 18, y + h // 2), 5)
    else:
        pygame.draw.rect(surf, (146, 138, 118), (x + 12, y + 22, 18, 12))
        pygame.draw.line(surf, (146, 138, 118), (x + 21, y + 22), (x + 21, y + 34), 1)


def _draw_signal_shack(surf, x, y, w, h):
    pygame.draw.rect(surf, (28, 22, 20), (x + 6, y + h - 14, w - 12, 12))
    pygame.draw.rect(surf, (54, 50, 44), (x + 2, y + h - 56, w - 4, 50))
    pygame.draw.rect(surf, (72, 66, 56), (x + 6, y + h - 62, w - 12, 10))
    for wx in range(x + 10, x + w - 8, 18):
        pygame.draw.rect(surf, (210, 168, 92), (wx, y + h - 50, 10, 12))
        pygame.draw.line(surf, (40, 32, 24), (wx + 5, y + h - 50), (wx + 5, y + h - 38), 1)
    pygame.draw.rect(surf, (44, 40, 36), (x + w // 2 - 4, y + h - 38, 8, 24))
    # Mast and the red signal lamp that marks the tower at night.
    pygame.draw.line(surf, (64, 66, 70), (x + w // 2, y + h - 62), (x + w // 2, y + h - 104), 4)
    pygame.draw.line(surf, (64, 66, 70), (x + 12, y + h - 88), (x + w - 12, y + h - 88), 3)
    pygame.draw.circle(surf, (214, 66, 54), (x + w // 2, y + h - 108), 5)
    pygame.draw.circle(surf, (255, 168, 128), (x + w // 2 - 1, y + h - 109), 2)


def _draw_flood_tower(surf, x, y, w, h):
    cx = x + w // 2
    base = y + h - 6
    pygame.draw.ellipse(surf, (8, 10, 14, 110), (x + 2, base - 8, w - 4, 12))
    pygame.draw.rect(surf, (58, 62, 68), (cx - 9, base - 20, 18, 16))
    pygame.draw.rect(surf, (76, 80, 86), (cx - 13, base - 26, 26, 8))
    pygame.draw.line(surf, (72, 76, 82), (cx, base - 24), (cx, base - 214), 5)
    for i in range(6):
        yy = base - 40 - i * 30
        pygame.draw.line(surf, (56, 60, 66), (cx - 10, yy), (cx + 10, yy - 16), 2)
        pygame.draw.line(surf, (56, 60, 66), (cx + 10, yy), (cx - 10, yy - 16), 2)
    pygame.draw.line(surf, (82, 86, 92), (cx - 26, base - 218), (cx + 26, base - 218), 5)
    for dx in (-22, 22):
        pygame.draw.rect(surf, (44, 46, 50), (cx + dx - 7, base - 230, 14, 12), border_radius=2)
        pygame.draw.rect(surf, (246, 236, 196), (cx + dx - 5, base - 228, 10, 7), border_radius=2)
    pygame.draw.circle(surf, (255, 238, 190), (cx, base - 218), 4)


def _draw_counter(surf, x, y, w, h, warm=False):
    pygame.draw.rect(surf, (36, 30, 26), (x + 2, y + h - 8, w - 4, 8))
    pygame.draw.rect(surf, (86, 72, 56), (x + 2, y + 6, w - 4, h - 10))
    pygame.draw.rect(surf, (128, 116, 96), (x + 2, y + 3, w - 4, 7))
    pygame.draw.line(surf, (152, 140, 118), (x + 4, y + 4), (x + w - 4, y + 4), 1)
    if warm:
        pygame.draw.rect(surf, (44, 86, 66), (x + w // 2 - 10, y - 12, 20, 13), border_radius=2)
        pygame.draw.rect(surf, (110, 210, 150), (x + w // 2 - 8, y - 10, 16, 9), 1)
        pygame.draw.line(surf, (60, 60, 56), (x + w // 2, y + 1), (x + w // 2, y + 4), 2)


def _draw_cabinet(surf, x, y, w, h):
    pygame.draw.rect(surf, (44, 42, 38), (x + 2, y + 2, w - 4, h - 4))
    pygame.draw.rect(surf, (78, 74, 64), (x + 2, y + 2, w - 4, h - 4), 2)
    for dy in range(y + 10, y + h - 6, 14):
        pygame.draw.line(surf, (58, 54, 48), (x + 6, dy), (x + w - 6, dy), 1)
    for dy in (y + 8, y + h - 10):
        pygame.draw.circle(surf, (120, 112, 94), (x + w // 2, dy), 2)


def _draw_crate(surf, x, y, w, h, seed):
    c = (94, 74, 52) if seed % 2 else (72, 70, 64)
    pygame.draw.rect(surf, c, (x + 3, y + 6, w - 6, h - 9))
    pygame.draw.rect(surf, _shift(c, 14), (x + 3, y + 6, w - 6, h - 9), 1)
    pygame.draw.line(surf, _shift(c, -18), (x + 3, y + 6), (x + w - 4, y + h - 4), 2)
    pygame.draw.rect(surf, (196, 206, 220), (x + 4, y + 6, w - 8, 4), border_radius=2)


def _prop_surface(stage_id, comp):
    x0, y0, tw, th = comp
    w, h = tw * T, th * T
    over = 0
    if stage_id == STAGE_NOMAN and (x0, y0) in NOMAN_TOWER_TILES:
        over = 240
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN) and tw >= 6:
        over = 24
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN) and tw >= 4 and th >= 4:
        over = 116
    surf = pygame.Surface((w, h + over), pygame.SRCALPHA)
    ox, oy = 0, over
    seed = _h(x0, y0) % 97
    if stage_id == STAGE_CUSTOMS:
        inside = y0 < 11
        if not inside:
            if th > tw:
                flat = pygame.Surface((h, w), pygame.SRCALPHA)
                _draw_car(flat, 0, 0, h, w, seed)
                surf.blit(pygame.transform.rotate(flat, 90), (0, oy))
            else:
                _draw_car(surf, 0, oy, w, h, seed)
        elif tw >= 3:
            _draw_counter(surf, 0, oy, w, h, warm=(x0, y0) == (19, 8))
        elif th > 2:
            _draw_cabinet(surf, 0, oy, w, h)
        else:
            _draw_counter(surf, 0, oy, w, h)
    elif stage_id == STAGE_NOMAN:
        if (x0, y0) in NOMAN_TOWER_TILES:
            _draw_flood_tower(surf, 0, oy, w, h)
        else:
            _draw_barrier(surf, 0, oy, w, h)
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        if tw >= 6:
            volkov = (x0, y0) == VOLKOV_BOXCAR_TILE
            _draw_boxcar(surf, 0, oy, w, h, seed, volkov)
        elif tw >= 4 and th >= 4:
            _draw_signal_shack(surf, 0, oy, w, h)
        else:
            _draw_crate(surf, 0, oy, w, h, seed)
    else:
        if tw >= 3:
            _draw_counter(surf, 0, oy, w, h,
                          warm=(x0, y0) in ((17, 3), (19, 8), (3, 3)))
        else:
            _draw_cabinet(surf, 0, oy, w, h)
    return surf, oy


def _prop_rows(stage_id):
    cached = _PROPS.get(stage_id)
    if cached is not None:
        return cached
    rows = []
    for comp in _components(stage_id):
        surf, over = _prop_surface(stage_id, comp)
        x0, y0, tw, th = comp
        rows.append({
            "x": x0 * T, "y": y0 * T - over, "w": surf.get_width(),
            "h": surf.get_height(), "surf": surf,
            "bottom": (y0 + th) * T,
        })
    _PROPS[stage_id] = rows
    return rows


def tall_drawables(stage_id, cam_x, cam_y):
    """[(bottom_world_y, draw(surface))] for y-sorting with actors."""
    out = []
    for row in _prop_rows(stage_id):
        sx = row["x"] - cam_x
        sy = row["y"] - cam_y
        if sx > WIDTH or sy > HEIGHT or sx + row["w"] < 0 or sy + row["h"] < 0:
            continue
        surf = row["surf"]
        pos = (int(sx), int(sy))
        out.append((row["bottom"], lambda s, _surf=surf, _p=pos: s.blit(_surf, _p)))
    return out


# ─────────────────────────────────────────────
# Lighting and weather
# ─────────────────────────────────────────────
def _light(radius, colour):
    return _lighting.falloff_sprite(radius, colour)


def _glow(radius, colour):
    return _lighting.bloom_sprite(radius, colour)


def _lamp_on(kind, index):
    t = _now_s()
    if kind == "bad":
        return 0.2 if (int(t * 11) + index) % 13 in (0, 1) else 1.0
    if kind == "pulse":
        return 0.65 + 0.35 * math.sin(t * 2.1 + index)
    return 0.92 + 0.08 * math.sin(t * 1.7 + index * 1.3)


def _torch_colour():
    return (156, 180, 212)


def _light_pass(stage_id, cam_x, cam_y, size):
    sw, sh = size
    lamps, blooms = [], []
    for i, (tx, ty, radius, colour, kind) in enumerate(_STAGE_LAMPS.get(stage_id, ())):
        x, y = tx * T, ty * T
        sx, sy = x - cam_x, y - cam_y
        if not (-radius < sx < sw + radius and -radius < sy < sh + radius):
            continue
        k = _lamp_on(kind, i)
        if k <= 0.2:
            continue
        lamps.append((_light(int(radius * k), colour), (int(sx - radius), int(sy - radius))))
        gr = max(20, radius // 4)
        blooms.append((_glow(gr, colour), (int(sx - gr), int(sy - gr))))
    if STATE.player is not None:
        px = STATE.player.rect.centerx - cam_x
        py = STATE.player.rect.centery - cam_y
        lamps.append((_light(176, _torch_colour()), (int(px - 176), int(py - 176))))
    return _lighting.LightMapDraw(_AMBIENT.get(stage_id, (52, 58, 72)), lamps, blooms)


def _prop_fx(surface, cam_x, cam_y, stage_id):
    t = _now_s()
    if stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        sx, sy = 41.5 * T - cam_x, 7.0 * T - 116 - cam_y
        if (int(t * 2) % 2) == 0 and -30 < sx < WIDTH + 30 and -30 < sy < HEIGHT + 30:
            pygame.draw.circle(surface, (230, 70, 60), (int(sx), int(sy)), 6)
            pygame.draw.circle(surface, (255, 170, 140), (int(sx), int(sy)), 2)
        gx, gy = 25.5 * T - cam_x, 10.1 * T - cam_y
        if -60 < gx < WIDTH + 60 and -60 < gy < HEIGHT + 60:
            glow = pygame.Surface((88, 88), pygame.SRCALPHA)
            pygame.draw.circle(glow, (255, 190, 110, 34), (44, 44), 40)
            pygame.draw.circle(glow, (255, 214, 150, 28), (44, 44), 24)
            surface.blit(glow, (int(gx - 44), int(gy - 44)),
                         special_flags=pygame.BLEND_RGBA_ADD)


def _snow(surface):
    t = _now_s()
    flake = pygame.Surface((3, 3), pygame.SRCALPHA)
    pygame.draw.circle(flake, (224, 232, 244, 150), (1, 1), 1)
    for i in range(118):
        h = _h(i, 29)
        speed = 26 + (h % 46)
        depth = 0.4 + (h % 60) / 100.0
        x = (h % 1300) + math.sin(t * 0.6 + i) * 22 * depth
        y = ((h >> 9) % 900 + t * speed) % 840 - 50
        x = (x + t * 14) % (WIDTH + 40) - 20
        if -10 < x < WIDTH + 10:
            surface.blit(flake, (int(x), int(y)))
            if depth > 0.85:
                pygame.draw.line(surface, (208, 220, 236), (int(x), int(y)),
                                 (int(x - 3), int(y) - 5), 1)


def draw_over(surface, cam_x, cam_y, stage_id=None):
    """Light multiply, warm practicals and snow - after actors, before HUD."""
    stage_id = stage_id or _STAGE
    _light_pass(stage_id, cam_x, cam_y, surface.get_size()).draw(surface, 0, 0)
    _prop_fx(surface, cam_x, cam_y, stage_id)
    tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    tint.fill((38, 54, 82, 20))
    surface.blit(tint, (0, 0))
    _snow(surface)
