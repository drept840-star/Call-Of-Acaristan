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

from core import artpack

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
    STAGE_CUSTOMS: (86, 96, 124),
    STAGE_NOMAN: (80, 92, 124),
    STAGE_RAIL: (82, 92, 120),
}
_AMBIENT[STAGE_BOXCAR] = _AMBIENT[STAGE_RAIL]
_AMBIENT[STAGE_TRAIN] = _AMBIENT[STAGE_RAIL]

# Lamps: (tile_x, tile_y, radius_px, colour, kind).  The kinds flicker a
# little; everything else is a steady practical.
_STAGE_LAMPS = {
    STAGE_CUSTOMS: (
        (15.5, 2.4, 160, (255, 196, 128), "steady"),
        (10.5, 7.5, 150, (255, 196, 128), "steady"),
        (19.0, 7.5, 150, (255, 196, 128), "steady"),
        (19.5, 6.4, 60, (120, 235, 160), "pulse"),
        (10.0, 14.6, 90, (255, 204, 140), "steady"),
        (20.0, 14.6, 90, (255, 204, 140), "bad"),
        (15.0, 16.5, 140, (176, 198, 222), "steady"),
        (5.0, 10.5, 120, (176, 198, 222), "steady"),
        (26.5, 10.5, 120, (176, 198, 222), "steady"),
    ),
    STAGE_NOMAN: (
        (20.0, 2.0, 140, (255, 186, 116), "steady"),
        (20.0, 15.6, 140, (255, 186, 116), "steady"),
        (8.5, 5.5, 170, (184, 208, 236), "tower0"),
        (31.5, 5.5, 170, (184, 208, 236), "tower1"),
        (8.5, 11.5, 170, (184, 208, 236), "tower2"),
        (31.5, 11.5, 170, (184, 208, 236), "tower3"),
        (13.0, 2.4, 90, (255, 204, 140), "steady"),
        (27.0, 2.4, 90, (255, 204, 140), "bad"),
    ),
    STAGE_RAIL: (
        (4.5, 5.4, 160, (255, 198, 132), "tower1"),
        (12.0, 6.5, 150, (255, 198, 132), "steady"),
        (20.0, 6.5, 150, (255, 198, 132), "steady"),
        (28.0, 6.5, 150, (255, 198, 132), "steady"),
        (36.0, 6.5, 150, (255, 198, 132), "steady"),
        (41.0, 9.0, 110, (255, 96, 70), "bad"),
        (25.0, 11.2, 80, (220, 170, 110), "steady"),
        (2.5, 15.5, 150, (190, 210, 236), "steady"),
        (22.0, 22.5, 150, (190, 210, 236), "steady"),
        (40.0, 17.0, 130, (190, 210, 236), "steady"),
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
# House art tiles per floor code (``tools/make_art_pack.py``); M6 only adds
# the frost and the snow that settles against walls.
_ART_FLOOR = {".": ".", "g": "g", "L": "L"}
_FROST = {
    STAGE_CUSTOMS: (196, 208, 226, 34),
    STAGE_NOMAN: (204, 216, 234, 46),
    STAGE_RAIL: (190, 202, 220, 26),
}
_FROST[STAGE_BOXCAR] = _FROST[STAGE_RAIL]
_FROST[STAGE_TRAIN] = _FROST[STAGE_RAIL]


def _paint_floor(surf, stage_id, col, row, ch):
    x, y = col * T, row * T
    art = artpack.tile(_ART_FLOOR[ch], col, row) if ch in _ART_FLOOR else None
    if art is not None:
        surf.blit(art, (x, y))
    else:
        pal = _PALETTE[stage_id]["floor"]
        colour = _shift(pal.get(ch, pal["."]), (_h(col, row) % 5) - 2)
        pygame.draw.rect(surf, colour, (x, y, T, T))
    if ch == "Y":
        colour = _PALETTE[stage_id]["floor"]["Y"]
        pygame.draw.rect(surf, (36, 36, 34), (x, y, T, T))
        pygame.draw.rect(surf, colour, (x, y + 6, T, T - 12))
        for tx in range(x + 4, x + T, 8):
            for ty in range(y + 10, y + T - 8, 8):
                pygame.draw.rect(surf, _shift(colour, -26), (tx, ty, 2, 2))
        pygame.draw.rect(surf, (20, 20, 20), (x, y + 6, T, 1))
        pygame.draw.rect(surf, (20, 20, 20), (x, y + T - 7, T, 1))


def _frost(surf, stage_id):
    """One even frost wash: snow light, not snow noise."""
    layer = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    layer.fill(_FROST.get(stage_id, _FROST[STAGE_CUSTOMS]))
    surf.blit(layer, (0, 0))


def _wall_drifts(surf, grid):
    """Hard-edged snow piled on the windward (north) and lee sides of walls."""
    h, w = len(grid), len(grid[0])
    for row in range(h):
        for col in range(w):
            if grid[row][col] in "CWBD":
                continue
            k = _h(col, row, 17)
            x, y = col * T, row * T
            if row > 0 and grid[row - 1][col] in "CW":
                dh = 6 + k % 7
                pygame.draw.rect(surf, _SNOW_DIM, (x, y, T, dh + 2))
                pygame.draw.rect(surf, _SNOW, (x, y, T, dh))
                if k % 3 == 0:
                    pygame.draw.rect(surf, _SNOW, (x + 8 + k % 20, y + dh, 18 + k % 14, 3))
            if row + 1 < h and grid[row + 1][col] in "CW" and k % 2 == 0:
                pygame.draw.rect(surf, _SNOW_DIM, (x + 6, y + T - 4, T - 12 - k % 18, 4))


def _paint_wall(surf, stage_id, col, row, ch):
    pal = _PALETTE[stage_id]
    base = pal["wall"].get(ch, pal["wall"]["C"])
    x, y = col * T, row * T
    h = _h(col, row, 11)
    art = artpack.wall("C", col, row) if ch == "C" else None
    if art is not None:
        surf.blit(art, (x, y))
    else:
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
    elif ch == "C" and art is None:
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
    """Road paint: gate apron lane, stop line and the plaza lane."""
    y = 2 * T + T // 2
    for x in range(2 * T, 28 * T, 34):
        pygame.draw.line(surf, (128, 104, 52), (x, y), (x + 18, y), 2)
    for x in range(14 * T, 17 * T, 22):
        pygame.draw.line(surf, (146, 126, 66), (x, T - 6), (x + 12, T + 10), 2)
    pygame.draw.line(surf, (176, 172, 150), (7 * T, 12 * T + 10), (23 * T, 12 * T + 10), 3)
    cx = 15 * T + T // 2
    for yy in range(13 * T, 19 * T, 46):
        pygame.draw.line(surf, (128, 104, 52), (cx, yy), (cx, yy + 22), 3)
    pygame.draw.rect(surf, (48, 46, 42), (11 * T + 6, 11 * T + 6, T - 12, T - 12))
    pygame.draw.rect(surf, (48, 46, 42), (18 * T + 6, 11 * T + 6, T - 12, T - 12))


def _noman_detail(surf, grid):
    """The crossing: lane paint, gate stripes and one set of boot prints."""
    cx = 20 * T + T // 2
    for y in range(3 * T, 15 * T, 46):
        pygame.draw.line(surf, (122, 106, 60), (cx, y), (cx, y + 22), 2)
    for i in range(22):
        y = 16 * T - i * 26
        x = cx + int(math.sin(i * 0.35) * 18) + (6 if i % 2 else -6)
        pygame.draw.ellipse(surf, (33, 38, 45), (x, y, 5, 9))
    for row in (1, 15):
        y = row * T + T // 2
        for x in range(17 * T, 24 * T, 22):
            pygame.draw.line(surf, (146, 126, 66), (x, y - 8), (x + 12, y + 8), 2)


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
        _snow_bank(surf, x * T - 14, y * T, 2 * T + 26, 18, x + y)


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
    """Wind-blown drift: a ragged hard-edged crest over a flat base."""
    if w < 6 or h < 4:
        return
    n = max(4, w // 10)
    top = []
    for i in range(n + 1):
        f = i / n
        lift = math.sin(f * math.pi) ** 0.6
        jag = (_h(i, seed, 5) % 5) - 2
        top.append((x + int(f * w), y + h - int(lift * h) + jag))
    base = [(x + w, y + h), (x, y + h)]
    pygame.draw.polygon(surf, (22, 26, 34), [(px + 2, py + 3) for px, py in top + base])
    pygame.draw.polygon(surf, _SNOW_DIM, top + base)
    crest = [(px, py + 2) for px, py in top]
    pygame.draw.polygon(surf, _SNOW, top + crest[::-1])
    pygame.draw.lines(surf, (232, 238, 248), False, top, 1)


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


def _prop_foot_snow(surf, stage_id, skip=("tanker",)):
    """Hard snow drift along the south foot of every outdoor prop."""
    grid = _maps.grid_for(stage_id)
    for kind, x, y, w, h in _maps.props_for(stage_id):
        if kind in skip or kind in ("counter", "terminal", "cabinet", "crate"):
            continue
        if y + h < len(grid) and grid[y + h][x] in "CWB":
            continue
        _snow_bank(surf, x * T + 6, (y + h) * T - 4, w * T - 12, 14, x * 7 + y)


def _customs_dress(surf, grid):
    """The post: frozen queue, ice, paperwork and the marks of a fight."""
    _fence_run(surf, 1 * T, 12 * T, 1 * T, 19 * T, 21)
    _fence_run(surf, 29 * T - 2, 12 * T, 29 * T - 2, 19 * T, 23)
    for i, (cx, cy, rw, rh) in enumerate((
            (8.6, 16.2, 74, 30), (20.4, 17.4, 66, 28), (2.6, 10.2, 58, 24),
            (25.6, 4.4, 60, 24), (12.0, 2.0, 70, 26))):
        _ice_sheet(surf, int(cx * T), int(cy * T), rw, rh, i)
    _tracks(surf, 1 * T, 2 * T + 30, 27 * T, 0, gap=17)
    _tracks(surf, 15 * T + 30, 3 * T, 0.0, 90, gap=17)
    _tracks(surf, 15 * T + 30, 12 * T, 6 * T, 90, gap=17)
    _oil_stain(surf, int(3.5 * T), int(15.2 * T), 40, 31)
    _oil_stain(surf, int(18.5 * T), int(1.9 * T), 34, 33)
    _papers(surf, 4 * T, 16 * T, 46, 51)
    _papers(surf, 12 * T, 13 * T, 38, 53)
    _debris(surf, 4 * T, 18 * T, 52, 57)
    _debris(surf, 25 * T, 15 * T, 54, 59)
    _debris(surf, 14 * T, 14 * T, 44, 61)
    _drain(surf, 17 * T + 10, 17 * T + 8, 65)
    _drain(surf, 21 * T + 12, 9 * T + 20, 67)
    # Inside the post: paperwork, chair marks, a wet patch under the files.
    for i, (cx, cy) in enumerate(((9.5, 5.6), (12.0, 5.6), (17.5, 5.6), (21.0, 5.6),
                                  (8.5, 9.4), (17.0, 9.4))):
        pygame.draw.circle(surf, (58, 54, 48), (int(cx * T), int(cy * T)), 7, 1)
    for i, (cx, cy) in enumerate(((10.5, 7.6), (14.0, 8.6), (19.5, 8.2),
                                  (12.0, 10.0), (21.0, 7.0))):
        _papers(surf, int(cx * T), int(cy * T), 34, 81 + i)
    _oil_stain(surf, int(13.5 * T), int(10.2 * T), 28, 93)
    _ice_sheet(surf, int(8.8 * T), int(7.4 * T), 70, 26, 91)
    for x in (7, 8, 9):
        _snow_bank(surf, x * T, 12 * T + 2, T, 12, 95 + x)
    _snow_bank(surf, 21 * T, 12 * T + 2, 2 * T, 12, 99)
    _prop_foot_snow(surf, STAGE_CUSTOMS)


def _noman_dress(surf, grid):
    """The strip: wire lines, craters, tracks and drifts."""
    for (y, segs) in ((3 * T - 10, ((1, 17), (24, 39))),):
        for c0, c1 in segs:
            _wire_coils(surf, c0 * T, y, c1 * T, y, c0)
    for c0, c1 in ((1, 3), (7, 11), (14, 17), (19, 22), (24, 27), (30, 34), (37, 39)):
        _wire_coils(surf, c0 * T, 14 * T + 12, c1 * T, 14 * T + 12, c0 + 50)
    for (cx, cy, r, sd) in ((10.5, 9.4, 34, 71), (29.5, 6.3, 28, 73), (20.5, 11.5, 30, 75),
                            (5.5, 4.8, 22, 77), (34.5, 9.7, 26, 79), (15.0, 6.4, 20, 81)):
        _crater(surf, int(cx * T), int(cy * T), r, sd)
    _tracks(surf, 1 * T + 10, 6 * T + 20, 9 * T, 0, gap=22)
    _tracks(surf, 30 * T, 12 * T, 9 * T, 0, gap=22)
    for i in range(7):
        _snow_bank(surf, int((2 + i * 5.4) * T), 3 * T - 2 + (i % 3) * 4, T + 26, 16, 80 + i)
    for k, (cx, cy) in enumerate(((9, 7), (19, 10), (30, 8), (18, 5), (33, 12))):
        _debris(surf, cx * T, cy * T, 56, 101 + k, col=(38, 44, 52))
    for (cx, cy, sd) in ((5, 12, 121), (36, 9, 123), (10, 6, 125),
                         (30, 14, 127), (25, 4, 129), (16, 12, 131)):
        _scrub(surf, cx * T + 20, cy * T + 24, sd)
    _snow_line(surf, 17 * T, 15 * T + T - 4, 24 * T, 15 * T + T - 4, 3)
    _drain(surf, 20 * T + 30, 16 * T + 14, 133)
    _prop_foot_snow(surf, STAGE_NOMAN)


def _rail_dress(surf, grid):
    """Freight yard: oil, ice, litter and snow along every car."""
    _snow_line(surf, 1 * T, 7 * T + 2, 45 * T, 7 * T + 2, 4)
    _snow_line(surf, 6 * T, 6 * T + 4, 42 * T, 6 * T + 4, 3)
    for i, cx in enumerate((5.0, 13.5, 22.0, 30.5, 38.0)):
        _debris(surf, int(cx * T), int(4.6 * T), 30, 151 + i, col=(52, 54, 58))
    _papers(surf, 19 * T, 4 * T, 52, 161)
    _papers(surf, 34 * T, 5 * T, 44, 163)
    for i, (cx, cy, rw, rh) in enumerate((
            (8.0, 8.4, 92, 30), (27.0, 13.6, 78, 26), (9.0, 15.2, 66, 24),
            (33.0, 17.4, 84, 28), (18.0, 20.6, 72, 26), (37.0, 9.0, 60, 22))):
        _ice_sheet(surf, int(cx * T), int(cy * T), rw, rh, 171 + i)
    for i, (cx, cy) in enumerate(((7.0, 13.0), (21.0, 12.0), (38.0, 15.0),
                                  (15.0, 23.0), (28.0, 21.0))):
        _oil_stain(surf, int(cx * T), int(cy * T), 26 + i * 3, 181 + i)
    _debris(surf, 18 * T, 16 * T + 40, 62, 201, col=(54, 56, 60))
    _debris(surf, 31 * T, 21 * T, 56, 203, col=(54, 56, 60))
    _debris(surf, 14 * T, 9 * T, 48, 205, col=(54, 56, 60))
    _debris(surf, 40 * T, 12 * T, 60, 207, col=(54, 56, 60))
    for i, (cx, cy) in enumerate(((9.0, 6.6), (24.0, 6.6), (40.0, 6.6))):
        _drain(surf, int(cx * T), int(cy * T), 211 + i)
    _fence_run(surf, 1 * T, 8 * T, 1 * T, 14 * T, 221)
    _fence_run(surf, 44 * T, 8 * T, 44 * T, 15 * T, 223)
    _prop_foot_snow(surf, STAGE_RAIL)


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
        return grid[cy][cx] in "CW"

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


def _floor_under(grid, col, row):
    """Floor code a prop stands on: the nearest open tile's."""
    h, w = len(grid), len(grid[0])
    for r in range(1, 5):
        for dc, dr in ((0, r), (-r, 0), (r, 0), (0, -r)):
            c, rr = col + dc, row + dr
            if 0 <= c < w and 0 <= rr < h and grid[rr][c] in "._gLY":
                return grid[rr][c]
    return "g"


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
            if ch == "B":
                ch = _floor_under(grid, col, row)
            if ch not in "CWD":
                _paint_floor(surf, stage_id, col, row, ch)
    _frost(surf, stage_id)
    for row in range(h):
        for col in range(w):
            ch = grid[row][col]
            if ch in "CW":
                _paint_wall(surf, stage_id, col, row, ch)
            elif ch == "D":
                _paint_door(surf, stage_id, col, row)
    _wall_drifts(surf, grid)
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
    for row in _prop_rows(stage_id):
        surf.blit(row["shadow"], (row["x"] + 7, row["bottom"] - row["fh"] + 9))
    _GROUND[stage_id] = surf
    return surf


def draw_ground(surface, cam_x, cam_y, stage_id=None):
    stage_id = stage_id or _STAGE
    surf = _ground_surface(stage_id)
    surface.blit(surf, (-int(cam_x), -int(cam_y)))


# ─────────────────────────────────────────────
# Static props (authored in maps._PROP_LAYOUT, drawn by kind)
# ─────────────────────────────────────────────
# Art-pack sprites where the house has them (vehicles, drums, crates, cable
# drums); everything else is hard-edged pygame shapes in the same palette.
# The tanker is skipped here: ``combat`` owns it (it can blow up).
_PAINTS = ("faded_red", "sand", "teal", "dusty_white", "faded_blue", "rust_brown")
_DYNAMIC_KINDS = frozenset(("tanker",))
_STEEL = (64, 68, 74)
_STEEL_HI = (96, 100, 108)
_STEEL_LO = (34, 36, 40)
_INK = (10, 12, 16)


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


def _blit_center(surf, img, w, h, oy, lift=0):
    """Blit ``img`` centred in a w x h footprint, bottom-aligned."""
    iw, ih = img.get_size()
    surf.blit(img, ((w - iw) // 2, oy + h - ih - lift if ih <= h else oy + h - ih))


def _art(name):
    return artpack.get(name)


def _vehicle_prop(kind, w, h, seed):
    paint = _PAINTS[seed % len(_PAINTS)]
    key = {
        "car": "car_%s_126x46" % paint, "car_v": "car_%s_126x46" % paint,
        "wreck": "burned_%s_126x46" % paint, "truck": "ipa_truck",
        "truck_burnt": "ipa_truck_charred",
    }[kind]
    img = artpack.vehicle(key)
    if img is not None and kind == "car_v":
        img = pygame.transform.rotate(img, 90 if seed % 2 else -90)
    return img


def _draw_jersey(surf, x, y, w, h, seed):
    """Concrete jersey barrier: sloped face, flat crown, hazard paint."""
    top = y + h - 34
    face = [(x + 2, y + h - 4), (x + 8, top + 10), (x + w - 8, top + 10), (x + w - 2, y + h - 4)]
    pygame.draw.polygon(surf, (104, 102, 96), face)
    pygame.draw.rect(surf, (138, 136, 128), (x + 8, top, w - 16, 11))
    pygame.draw.rect(surf, (190, 202, 216), (x + 9, top, w - 18, 3))
    for i, sx in enumerate(range(x + 12, x + w - 16, 18)):
        col = (196, 64, 48) if i % 2 == 0 else (214, 210, 196)
        pygame.draw.polygon(surf, col, [(sx, y + h - 8), (sx + 8, top + 14),
                                        (sx + 16, top + 14), (sx + 8, y + h - 8)])
    pygame.draw.line(surf, (72, 70, 66), (x + 4, y + h - 6), (x + w - 4, y + h - 6), 2)
    for sx in (x + w // 3, x + 2 * w // 3):
        pygame.draw.line(surf, (76, 74, 70), (sx, top + 1), (sx, y + h - 6), 1)


def _draw_sandbag_wall(surf, x, y, w, h, seed):
    """Three courses of bags, staggered, with a snow crown."""
    bw, bh = 20, 10
    base = y + h - 6
    for r in range(3):
        off = (bw // 2) if r % 2 else 0
        by = base - (r + 1) * (bh - 1)
        bx = x + 2 - off
        c = 0
        while bx < x + w - 4:
            hh = _h(c, r, seed)
            col = (100, 90, 66) if hh % 3 else (88, 80, 60)
            rect = pygame.Rect(max(bx, x + 2), by, min(bw, x + w - 2 - max(bx, x + 2)), bh)
            if rect.w > 6:
                pygame.draw.rect(surf, _INK, rect.inflate(2, 2), border_radius=3)
                pygame.draw.rect(surf, col, rect, border_radius=3)
                pygame.draw.line(surf, _shift(col, 18), (rect.x + 2, rect.y + 2),
                                 (rect.right - 3, rect.y + 2), 1)
            bx += bw
            c += 1
    pygame.draw.rect(surf, _SNOW, (x + 6, base - 3 * (bh - 1) - 2, w - 12, 3))


def _draw_booth(surf, x, y, w, h):
    """Guard booth: block hut, lit window, flat roof under snow."""
    body = pygame.Rect(x + 6, y + h - 70, w - 12, 64)
    pygame.draw.rect(surf, _INK, body.inflate(2, 2))
    pygame.draw.rect(surf, (78, 82, 76), body)
    pygame.draw.rect(surf, (96, 100, 92), (body.x, body.y, body.w, 6))
    win = pygame.Rect(body.x + 12, body.y + 18, body.w - 24, 18)
    pygame.draw.rect(surf, (30, 34, 40), win)
    pygame.draw.rect(surf, (214, 186, 120), win.inflate(-4, -4))
    pygame.draw.line(surf, (60, 52, 40), (win.centerx, win.y), (win.centerx, win.bottom), 2)
    pygame.draw.rect(surf, (44, 46, 44), (body.centerx - 10, body.bottom - 22, 20, 22))
    roof = pygame.Rect(x + 2, y + h - 80, w - 4, 14)
    pygame.draw.rect(surf, _INK, roof.inflate(2, 2))
    pygame.draw.rect(surf, (58, 60, 58), roof)
    pygame.draw.rect(surf, _SNOW, (roof.x, roof.y, roof.w, 6))
    pygame.draw.rect(surf, (196, 64, 48), (body.x, body.bottom - 30, body.w, 4))


def _draw_container(surf, x, y, w, h, seed):
    """Shipping container: ribbed side, end doors, snow on the roof."""
    cols = ((120, 62, 46), (52, 90, 96), (62, 74, 104), (112, 96, 60))
    body = cols[seed % len(cols)]
    roof = pygame.Rect(x + 2, y + 4, w - 4, h - 26)
    side = pygame.Rect(x + 2, roof.bottom, w - 4, 20)
    pygame.draw.rect(surf, _INK, roof.union(side).inflate(2, 2))
    pygame.draw.rect(surf, _shift(body, 14), roof)
    pygame.draw.rect(surf, _shift(body, -20), side)
    for rx in range(side.x + 6, side.right - 4, 9):
        pygame.draw.line(surf, _shift(body, -40), (rx, side.y + 2), (rx, side.bottom - 2), 2)
    if roof.h > roof.w:
        for ry in range(roof.y + 12, roof.bottom - 6, 12):
            pygame.draw.line(surf, _shift(body, -10), (roof.x + 3, ry), (roof.right - 4, ry), 2)
    else:
        for rx in range(roof.x + 12, roof.right - 6, 12):
            pygame.draw.line(surf, _shift(body, -10), (rx, roof.y + 3), (rx, roof.bottom - 4), 2)
    pygame.draw.rect(surf, _SNOW_DIM, (roof.x + 4, roof.y + 3, roof.w - 8, 5))
    for dx in (side.right - 22, side.right - 12):
        pygame.draw.line(surf, (190, 186, 170), (dx, side.y + 3), (dx, side.bottom - 3), 2)


def _draw_hedgehog(surf, x, y, w, h, seed):
    """Czech hedgehog: three welded beams, rusted, snow on the joints."""
    cx, cy = x + w // 2, y + h - 22
    beams = (((-22, 14), (22, -14)), ((-22, -14), (22, 14)), ((0, -26), (0, 20)))
    for (ax, ay), (bx, by) in beams:
        pygame.draw.line(surf, _INK, (cx + ax, cy + ay), (cx + bx, cy + by), 8)
    for i, ((ax, ay), (bx, by)) in enumerate(beams):
        col = (96, 62, 44) if i != 2 else (110, 72, 50)
        pygame.draw.line(surf, col, (cx + ax, cy + ay), (cx + bx, cy + by), 5)
        pygame.draw.line(surf, _shift(col, 26), (cx + ax, cy + ay - 1), (cx + bx, cy + by - 1), 1)
    pygame.draw.rect(surf, _SNOW, (cx - 6, cy - 4, 12, 4))
    pygame.draw.line(surf, _INK, (cx - 18, y + h - 6), (cx + 18, y + h - 6), 3)


def _draw_lamp_mast(surf, x, y, w, h):
    cx, base = x + w // 2, y + h - 6
    pygame.draw.rect(surf, _STEEL_LO, (cx - 7, base - 10, 14, 10))
    pygame.draw.line(surf, _INK, (cx, base - 8), (cx, base - 118), 6)
    pygame.draw.line(surf, _STEEL, (cx, base - 8), (cx, base - 118), 4)
    pygame.draw.rect(surf, _INK, (cx - 12, base - 128, 24, 12))
    pygame.draw.rect(surf, (246, 236, 196), (cx - 9, base - 126, 18, 7))


def _draw_kind(kind, surf, oy, w, h, x0, y0, seed):
    if kind in ("car", "car_v", "wreck", "truck", "truck_burnt"):
        img = _vehicle_prop(kind, w, h, seed)
        if img is not None:
            _blit_center(surf, img, w, h, oy, lift=6)
        else:
            _draw_car(surf, 0, oy, w, h, seed)
    elif kind in ("barrels", "crates", "crate", "coil"):
        name = {"barrels": "prop_barrels", "crates": "prop_crate",
                "crate": "prop_crate", "coil": "prop_coil"}[kind]
        img = _art(name)
        if img is not None and kind == "crate":
            img = pygame.transform.scale(img, (60, 60))
        if img is not None:
            _blit_center(surf, img, w, h, oy, lift=4)
        else:
            _draw_crate(surf, 0, oy, w, h, seed)
    elif kind == "jersey":
        _draw_jersey(surf, 0, oy, w, h, seed)
    elif kind == "sandbag":
        _draw_sandbag_wall(surf, 0, oy, w, h, seed)
    elif kind == "booth":
        _draw_booth(surf, 0, oy, w, h)
    elif kind == "container":
        _draw_container(surf, 0, oy, w, h, seed)
    elif kind == "hedgehog":
        _draw_hedgehog(surf, 0, oy, w, h, seed)
    elif kind == "tower":
        _draw_flood_tower(surf, 0, oy, w, h)
    elif kind == "boxcar":
        _draw_boxcar(surf, 0, oy, w, h, seed, (x0, y0) == VOLKOV_BOXCAR_TILE)
    elif kind == "shack":
        _draw_signal_shack(surf, 0, oy, w, h)
    elif kind == "counter":
        _draw_counter(surf, 0, oy, w, h)
    elif kind == "terminal":
        _draw_counter(surf, 0, oy, w, h, warm=True)
    elif kind == "cabinet":
        _draw_cabinet(surf, 0, oy, w, h)
    elif kind == "mast":
        _draw_lamp_mast(surf, 0, oy, w, h)


_OVER = {"tower": 240, "shack": 116, "booth": 30, "boxcar": 24, "mast": 80,
         "jersey": 6, "sandbag": 4, "hedgehog": 10, "container": 0}


def _stage_props(stage_id):
    props = [p for p in _maps.props_for(stage_id) if p[0] not in _DYNAMIC_KINDS]
    if stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        # Platform lamp the second searchlight hangs from (no footprint).
        c, r = RAIL_DETECTOR_TILES[1]
        props.append(("mast", c, r - 1, 1, 1))
    return props


def _prop_rows(stage_id):
    cached = _PROPS.get(stage_id)
    if cached is not None:
        return cached
    rows = []
    for kind, x0, y0, tw, th in _stage_props(stage_id):
        w, h = tw * T, th * T
        over = _OVER.get(kind, 0)
        surf = pygame.Surface((w, h + over), pygame.SRCALPHA)
        _draw_kind(kind, surf, over, w, h, x0, y0, _h(x0, y0) % 97)
        mask = pygame.mask.from_surface(surf, 40)
        shadow = mask.to_surface(
            setcolor=(4, 6, 10, 120), unsetcolor=(0, 0, 0, 0)).subsurface(
            (0, over, surf.get_width(), h)).copy()
        # A hard dark rim keeps props separate from the snow at night.
        for comp_pts in mask.connected_components(8):
            pts = comp_pts.outline(2)
            if len(pts) > 2:
                pygame.draw.lines(surf, _INK, True, pts, 1)
        rows.append({
            "kind": kind, "x": x0 * T, "y": y0 * T - over, "w": surf.get_width(),
            "h": surf.get_height(), "surf": surf,
            "bottom": (y0 + th) * T, "fh": h, "shadow": shadow,
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


def _light_dead(index):
    from . import stealth as _stealth
    lights = _stealth.all_lights()
    return index < len(lights) and _stealth.dead(lights[index])


def _torch_colour():
    return (204, 214, 228)


def _light_pass(stage_id, cam_x, cam_y, size):
    sw, sh = size
    lamps, blooms = [], []
    for i, (tx, ty, radius, colour, kind) in enumerate(_STAGE_LAMPS.get(stage_id, ())):
        x, y = tx * T, ty * T
        sx, sy = x - cam_x, y - cam_y
        if not (-radius < sx < sw + radius and -radius < sy < sh + radius):
            continue
        if kind.startswith("tower"):
            if _light_dead(int(kind[5:])):
                continue
            kind = "steady"
        k = _lamp_on(kind, i)
        if k <= 0.2:
            continue
        lamps.append((_light(int(radius * k), colour), (int(sx - radius), int(sy - radius))))
        gr = max(20, radius // 4)
        blooms.append((_glow(gr, colour), (int(sx - gr), int(sy - gr))))
    from . import combat as _combat
    for x, y, radius, colour in _combat.extra_lamps():
        sx, sy = x - cam_x, y - cam_y
        if -radius < sx < sw + radius and -radius < sy < sh + radius:
            lamps.append((_light(radius, colour), (int(sx - radius), int(sy - radius))))
    if STATE.player is not None:
        px = STATE.player.rect.centerx - cam_x
        py = STATE.player.rect.centery - cam_y
        lamps.append((_light(224, _torch_colour()), (int(px - 224), int(py - 224))))
    return _lighting.LightMapDraw(_AMBIENT.get(stage_id, (108, 118, 140)), lamps, blooms)


def _dead_lamp(surface, cx, base, t, seed):
    """Shot-out tower head: dark lenses, a dying spark now and then."""
    if not (-60 < cx < WIDTH + 60 and -260 < base < HEIGHT + 260):
        return
    for dx in (-22, 22):
        pygame.draw.rect(surface, (30, 32, 36), (cx + dx - 5, base - 228, 10, 7))
        pygame.draw.line(surface, (70, 74, 80), (cx + dx - 4, base - 227),
                         (cx + dx + 3, base - 223), 1)
    pygame.draw.circle(surface, (40, 42, 46), (int(cx), int(base - 218)), 4)
    if (int(t * 7) + seed * 3) % 11 == 0:
        k = (t * 7) % 1.0
        pygame.draw.circle(surface, (255, 196, 110),
                           (int(cx + 18), int(base - 224 + k * 40)), 2)


def _prop_fx(surface, cam_x, cam_y, stage_id):
    t = _now_s()
    if stage_id == STAGE_NOMAN:
        for i, (c, r) in enumerate(NOMAN_TOWER_TILES):
            if _light_dead(i):
                _dead_lamp(surface, c * T + T // 2 - cam_x, (r + 2) * T - 6 - cam_y, t, i)
    if stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        sx, sy = 41.5 * T - cam_x, 7.0 * T - 116 - cam_y
        if (int(t * 2) % 2) == 0 and not _light_dead(0) \
                and -30 < sx < WIDTH + 30 and -30 < sy < HEIGHT + 30:
            pygame.draw.circle(surface, (230, 70, 60), (int(sx), int(sy)), 6)
            pygame.draw.circle(surface, (255, 170, 140), (int(sx), int(sy)), 2)


_SNOW_FLAKE = pygame.Surface((3, 3), pygame.SRCALPHA)
pygame.draw.circle(_SNOW_FLAKE, (224, 232, 244, 150), (1, 1), 1)


def _snow(surface):
    t = _now_s()
    for i in range(118):
        h = _h(i, 29)
        speed = 26 + (h % 46)
        depth = 0.4 + (h % 60) / 100.0
        x = (h % 1300) + math.sin(t * 0.6 + i) * 22 * depth
        y = ((h >> 9) % 900 + t * speed) % 840 - 50
        x = (x + t * 14) % (WIDTH + 40) - 20
        if -10 < x < WIDTH + 10:
            surface.blit(_SNOW_FLAKE, (int(x), int(y)))
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
