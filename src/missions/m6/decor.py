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

import random

import pygame

from engine.assets import load_image as _load_image
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
    ".": (55, 56, 58), "g": (35, 40, 47), "L": (57, 59, 62),
    "Y": (121, 100, 54), "C": (60, 66, 74), "W": (64, 72, 80),
    "B": (56, 47, 42), "D": (96, 86, 66),
}

_PALETTE = {
    STAGE_CUSTOMS: {
        "floor": {".": (55, 56, 58), "g": (35, 39, 46)},
        "wall": {"C": (45, 51, 61), "W": (50, 57, 67), "B": (44, 38, 34)},
        "door": (98, 88, 68),
    },
    STAGE_NOMAN: {
        "floor": {".": (44, 50, 58), "g": (33, 38, 45), "L": (58, 60, 63)},
        "wall": {"C": (44, 50, 60), "W": (51, 58, 68), "B": (44, 38, 34)},
        "door": (104, 92, 66),
    },
    STAGE_RAIL: {
        "floor": {".": (46, 50, 56), "g": (34, 38, 44),
                  "L": (57, 59, 62), "Y": (121, 100, 54)},
        "wall": {"C": (44, 49, 58), "W": (50, 56, 66), "B": (42, 36, 32)},
        "door": (100, 90, 68),
    },
}
_PALETTE[STAGE_BOXCAR] = _PALETTE[STAGE_RAIL]
_PALETTE[STAGE_TRAIN] = _PALETTE[STAGE_RAIL]

_AMBIENT = {
    STAGE_CUSTOMS: (99, 110, 142),
    STAGE_NOMAN: (92, 105, 140),
    STAGE_RAIL: (95, 106, 136),
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

# ──────────────────────────────────────────────────────────────────────────
# Material surface kit
# ──────────────────────────────────────────────────────────────────────────
# Ground, walls and roofs sample the shared texture set, tinted to the
# authored palette so the source's own hues never leak into the yard.
_MATERIALS = {
    # name        source texture      tint                roughness
    "asphalt":   ("concrete",  (46, 47, 49)),
    "asphalt_d": ("concrete",  (41, 42, 45)),
    "apron":     ("concrete",  (60, 61, 63)),
    "gravel":    ("concrete",  (47, 50, 55)),
    "ballast":   ("ballast",   (44, 46, 50)),
    "snow":      ("snow",      (196, 208, 226)),
    "snow_trod": ("snow_trod", (154, 168, 188)),
    "plank":     ("crate",     (104, 82, 58)),
    "sleeper":   ("sleeper",   (74, 58, 42)),
    "steel":     ("steel",     (86, 92, 100)),
    "rust":      ("rust",      (104, 66, 44)),
    "rib":       ("metal_rib", (96, 100, 108)),
    "coach":     ("boxcar",    (78, 58, 48)),
    "brick":     ("brick",     (78, 62, 52)),
    "wall_c":    ("concrete",  (52, 58, 68)),
    "wall_w":    ("metal_rib", (50, 56, 66)),
    "roof":      ("concrete",  (40, 44, 51)),
}
_TEX_CACHE = {}
_MAT_CACHE = {}
_MAT_VARIANTS = 4


def _load_tex(name):
    """Raw 64 px texture from ``assets/tex3d`` (cached)."""
    tex = _TEX_CACHE.get(name)
    if tex is not None:
        return tex
    path = None
    try:
        from core.config import resource_path
        path = resource_path("assets/tex3d/%s.png" % name)
    except Exception:
        path = None
    try:
        tex = _load_image(path, convert="alpha") if path else None
    except Exception:
        tex = None
    if tex is None:
        # No texture on disk: a soft noise slab keeps the surfaces from
        # collapsing back to flat rectangles.
        tex = pygame.Surface((T, T))
        tex.fill((128, 128, 128))
        for i in range(0, T, 2):
            v = 118 + ((_h(i, 3) % 21))
            pygame.draw.line(tex, (v, v, v), (0, i), (T, i))
    _TEX_CACHE[name] = tex
    return tex


def _tex_mean(tex):
    """Average channel of a texture (one sample per 8th pixel is plenty)."""
    r = g = b = n = 0
    w, h = tex.get_size()
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            c = tex.get_at((x, y))
            r += c.r
            g += c.g
            b += c.b
            n += 1
    n = max(1, n)
    return (r / n, g / n, b / n)


def _tint(tex, colour):
    """Scale a texture onto an authored colour, keeping only its light/dark.

    The texture's *luma* pattern is mapped onto ``colour`` (the same idea as
    the engine's tinted 3D materials): the material lands on the palette entry the
    map authors and keeps its tooth, but the source's own hues - rust spots,
    brick red, moss - never leak into a yard that was never painted that
    colour.  numpy for speed, pure python as the fallback.
    """
    w, h = tex.get_size()
    try:
        import numpy as np
    except Exception:
        np = None
    if np is not None:
        arr = pygame.surfarray.array3d(tex).astype(np.float32)
        luma = arr @ np.array([0.299, 0.587, 0.114], dtype=np.float32)
        luma = np.maximum(luma, 1.0)
        scale = float(sum(colour)) / 3.0 / float(luma.mean() or 1.0)
        out = tex.copy()
        dst = pygame.surfarray.pixels3d(out)
        for c in range(3):
            dst[..., c] = np.clip(luma * scale * (float(colour[c]) * 3.0
                                                 / max(1.0, float(sum(colour)))),
                                  0, 255)
        del dst
        return out
    tot = 0
    n = 0
    for y in range(0, h, 8):
        for x in range(0, w, 8):
            c = tex.get_at((x, y))
            tot += (c.r * 299 + c.g * 587 + c.b * 114) // 1000
            n += 1
    mean = max(1, tot // max(1, n))
    out = tex.copy()
    for y in range(h):
        for x in range(w):
            c = tex.get_at((x, y))
            k = ((c.r * 299 + c.g * 587 + c.b * 114) // 1000) / 255.0
            out.set_at((x, y), (min(255, int(colour[0] * 1.6 * k)),
                                min(255, int(colour[1] * 1.6 * k)),
                                min(255, int(colour[2] * 1.6 * k))))
    return out


_PLATES = {}
_PLATE_PERIOD = {}


def _seamless_plate(name):
    """Mirror-tiled texture with a *known repeat period*.

    The source tiles are 64 px photos: laid side by side they show their
    edges.  Mirroring a 2x2 block makes the values continuous across every
    join, so the assembled block repeats cleanly every ``2 * S`` px.

    The returned surface is stored one tile wider/taller than the period
    (``period + T``), so ``material_at`` can cut a full ``T`` window at any
    offset in ``0 .. period-1``; wrapping that offset at the period is then
    seamless by construction.  Cutting windows out of a plate that is not
    an exact multiple of the tile is what drew the previous faint grid.
    """
    plate = _PLATES.get(name)
    if plate is not None:
        return plate
    tex = _load_tex(name)
    sw, sh = tex.get_size()
    period = (sw * 2, sh * 2)
    # 2x2 mirrored block = one period
    block = pygame.Surface(period)
    for row in range(2):
        for col in range(2):
            block.blit(pygame.transform.flip(tex, bool(col), bool(row)),
                       (col * sw, row * sh))
    # grow it by one tile in each direction so any offset can be sampled
    plate = pygame.Surface((period[0] + T, period[1] + T))
    for row in range(2):
        for col in range(2):
            plate.blit(block, (col * period[0], row * period[1]))
    _PLATES[name] = plate
    _PLATE_PERIOD[name] = period
    return plate


def _plate_period(name):
    return _PLATE_PERIOD.get(name, (T * 2, T * 2))


def material(name, colour=None):
    """``[Surface, ...]`` - the tile-shaped variants of one material.

    ``colour`` overrides the authored tint (props pick their own paint).

    Four variants per material, cut from a doubled (128 px) copy of the
    texture so a wall or a yard does not visibly repeat on a 64 px grid,
    each tinted to the authored colour.
    """
    key = (name,) if colour is None else (name, tuple(colour))
    mats = _MAT_CACHE.get(key)
    if mats is not None:
        return mats
    src_name, default = _MATERIALS.get(name, ("concrete", (60, 60, 60)))
    if colour is None:
        colour = default
    plate = _seamless_plate(src_name)
    pw, ph = _plate_period(src_name)
    out = []
    for i in range(_MAT_VARIANTS):
        # Four hashed windows inside one period of the plate: variants that
        # differ, each of them individually seamless when tiled.
        hh = _h(i, len(name), 43)
        ox = (hh % pw)
        oy = ((hh >> 9) % ph)
        tile = plate.subsurface((ox, oy, T, T)).copy()
        tile = _tint(tile, colour)
        out.append(tile)
    _MAT_CACHE[key] = out
    return out


def material_tile(name, col, row, colour=None):
    """One material tile, picked by the deterministic spatial hash.

    For objects that stand on their own (a crate, a container, a coach
    panel) the four variants are what stops the same 64 px patch repeating.
    """
    variants = material(name, colour)
    return variants[(_h(col, row, 23) >> 3) % len(variants)]


_PLATE_TINT = {}


def material_plate(name, colour=None):
    """The whole seamless plate, tinted once, then cached."""
    key = (name,) if colour is None else (name, tuple(colour))
    plate = _PLATE_TINT.get(key)
    if plate is None:
        src_name, default = _MATERIALS.get(name, ("concrete", (60, 60, 60)))
        if colour is None:
            colour = default
        tex = _tint(_seamless_plate(src_name), colour)
        # A photo has its own big shapes; repeated dozens of times across a
        # yard they become wallpaper.  Pull the plate half-way to its mean
        # so what survives is grain, not motifs.
        mean = _tex_mean(tex)
        half = tex.copy()
        half.fill((128, 128, 128), special_flags=pygame.BLEND_RGB_MULT)
        base = pygame.Surface(tex.get_size())
        base.fill(tuple(int(v * 0.5) for v in mean))
        base.blit(half, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
        plate = base
        _PLATE_TINT[key] = plate
    return plate


def material_at(name, x, y, colour=None):
    """One tile of a material **sampled in world space**.

    Ground, walls and roofs are continuous surfaces: picking a variant per
    tile made every 64 px cell its own little patch, which reads as a floor
    made of disconnected plates.  Sampling the seamless plate at the world
    position instead means the texture flows across tile borders - one
    poured surface, not a grid of stamps.
    """
    plate = material_plate(name, colour)
    pw, ph = _plate_period(name)
    return plate.subsurface((x % pw, y % ph, T, T))

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
    _MAT_CACHE.clear()
    _PLATES.clear()
    _PLATE_TINT.clear()
    _WEAR.clear()


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
    STAGE_CUSTOMS: (196, 208, 226, 15),
    STAGE_NOMAN: (204, 216, 234, 22),
    STAGE_RAIL: (190, 202, 220, 11),
}
_FROST[STAGE_BOXCAR] = _FROST[STAGE_RAIL]
_FROST[STAGE_TRAIN] = _FROST[STAGE_RAIL]


def _floor_material(stage_id, ch):
    """Material name for a floor code (per stage, so the yards differ)."""
    if ch == "L":
        return "apron"
    if ch == "Y":
        return "plank"
    if ch == ".":
        return "asphalt"
    if stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        return "gravel"
    return "asphalt_d"


_WEAR = {}


def _ground_wear(surf, stage_id):
    """One continuous damp/wear pass over the whole yard.

    This is what used to be a per-slab tone (`+-2` steps of a translucent
    plate on every tile), which drew the 64 px grid straight onto the
    floor.  A smooth low-frequency layer does the same job - the ground
    stops being one flat value - without a single tile boundary in it.

    The noise is generated small, blurred twice, then scaled up, so what
    lands on the yard is soft mottling rather than visible cells, and the
    seed is a fixed function of the stage name (``hash()`` is salted per
    process, which made the ground differ between runs).
    """
    size = surf.get_size()
    key = (stage_id, size)
    layer = _WEAR.get(key)
    if layer is None:
        seed = 0x5EED
        for ch in stage_id:
            seed = (seed * 131 + ord(ch)) & 0xFFFFFFFF
        rnd = random.Random(seed)
        sw, sh = max(3, size[0] // 40), max(3, size[1] // 40)
        small = pygame.Surface((sw, sh))
        for yy in range(sh):
            for xx in range(sw):
                v = 232 + rnd.randrange(0, 24)
                small.set_at((xx, yy), (v, v, min(255, int(v * 1.02))))
        for _ in range(2):                   # blur the cells away
            mid = pygame.transform.smoothscale(small, (max(2, sw // 2), max(2, sh // 2)))
            small = pygame.transform.smoothscale(mid, (sw, sh))
        layer = pygame.transform.smoothscale(small, size)
        _WEAR[key] = layer
    surf.blit(layer, (0, 0), special_flags=pygame.BLEND_RGB_MULT)


def _paint_floor(surf, stage_id, col, row, ch):
    """One floor tile: material + slab tone + aggregate grit."""
    x, y = col * T, row * T
    surf.blit(material_at(_floor_material(stage_id, ch), x, y), (x, y))
    for i in range(2):                       # aggregate, so a slab has tooth
        hh = _h(col, row, 31 + i)
        gx = x + 6 + (hh % (T - 12))
        gy = y + 6 + ((hh >> 7) % (T - 12))
        pygame.draw.rect(surf, ((58,) * 3 if hh % 3 else (34,) * 3),
                         (gx, gy, 2, 1))
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


def _solid_tile(grid, col, row):
    """True when (col,row) is outside the map or a solid tile.

    Out of bounds counts as solid: a wall running into the map edge must not
    grow a cap or a side seam there (that is what made every border tile read
    as its own little block).
    """
    h = len(grid)
    w = len(grid[0]) if h else 0
    if not (0 <= col < w and 0 <= row < h):
        return True
    return grid[row][col] in "CWBD"


def _paint_wall(surf, stage_id, col, row, ch, grid):
    """One wall tile, painted as part of the run it belongs to.

    The old painter treated every tile as a standalone block: its own base
    tone, its own top highlight, its own bottom shadow and its own snow cap.
    A 30-tile border then read as a brick wall of 30 separate slabs - the
    "walls look terrible" report.  Edges are now decided by the neighbours:
    a cap only where the wall actually ends, seams only where the run does,
    and one continuous surface in between.
    """
    pal = _PALETTE[stage_id]
    base = pal["wall"].get(ch, pal["wall"]["C"])
    x, y = col * T, row * T

    open_n = not _solid_tile(grid, col, row - 1)
    open_s = not _solid_tile(grid, col, row + 1)
    open_w = not _solid_tile(grid, col - 1, row)
    open_e = not _solid_tile(grid, col + 1, row)

    # Column-keyed noise (never row-keyed): stacked tiles of a vertical run
    # then share one tone and the run stays one surface.
    k = _h(col, 0, 11)
    tone = _shift(base, (k % 5) - 2)
    surf.blit(material_at("wall_w" if ch == "W" else "wall_c", x, y), (x, y))

    # The wall face: a top-down wall reads as a wall by its vertical fall
    # from the lit crown to the shadowed base, not by its outline.  One
    # gradient per tile height, identical on every tile of the run.
    if ch == "C":
        top = y + (5 if open_n else 0)
        for i in range(0, T - (top - y), 4):
            a = i / float(T)
            pygame.draw.rect(surf, _shift(tone, -int(4 + 12 * a)),
                             (x, top + i, T, min(4, T - i - (top - y))))

    # Broad weathering, aligned to a global 2-tile grid so it crosses tiles
    # instead of restarting on each one.
    if ch == "C":
        if (col % 2) == 0:
            pygame.draw.line(surf, _shift(tone, -7), (x, y + 2), (x, y + T - 2), 1)
        if k % 7 == 0:
            pygame.draw.line(surf, _shift(tone, -8), (x + 6, y + 14), (x + T - 5, y + 17), 1)
        if k % 23 == 0:                       # the odd rusted rebar nub
            pygame.draw.line(surf, _shift(tone, 26), (x + T // 2 - 3, y + T // 2),
                             (x + T // 2 + 3, y + T // 2), 2)
        if k % 13 == 0:
            pygame.draw.rect(surf, _shift(tone, 4), (x + 4, y + 20, 9, 5))
        # Poured-panel joint: every fourth tile, barely there, so a long wall
        # still shows structure without turning into brickwork.
        if col % 4 == 0 and not open_w:
            pygame.draw.line(surf, _shift(tone, -6), (x, y + 3), (x, y + T - 4), 1)

    # ── snow along the crown: only where the wall ends and the sky is above
    if open_n:
        cap = 5 + (k % 3)
        pygame.draw.rect(surf, (150, 164, 184), (x, y, T, cap + 2))
        pygame.draw.rect(surf, _SNOW, (x, y, T, cap))
        if k % 3 == 0:                        # wind lip spilling over the edge
            pygame.draw.rect(surf, _SNOW, (x + 3 + k % 12, y + cap, 10 + k % 9, 2))
        pygame.draw.line(surf, _shift(tone, -16), (x, y + cap + 2), (x + T - 1, y + cap + 2), 1)

    # ── the near edge: a bright snow lip and one shadow, not a line per tile
    if open_s:
        pygame.draw.rect(surf, _shift(tone, -20), (x, y + T - 5, T, 2))
        pygame.draw.rect(surf, (156, 170, 190), (x, y + T - 3, T, 3))
        pygame.draw.rect(surf, _SNOW, (x, y + T - 3, T, 1))
        if k % 4 == 0:
            pygame.draw.rect(surf, _SNOW, (x + 4 + k % 16, y + T - 4, 8 + k % 10, 2))

    # ── side seams only where the run stops
    if open_w:
        pygame.draw.rect(surf, _shift(tone, -18), (x, y, 2, T))
        if open_n:
            pygame.draw.rect(surf, (168, 182, 202), (x, y, 2, 3))
    if open_e:
        pygame.draw.rect(surf, _shift(tone, -18), (x + T - 2, y, 2, T))
        if open_n:
            pygame.draw.rect(surf, (168, 182, 202), (x + T - 2, y, 2, 3))

    if ch == "C" and (open_w or open_e):
        # Cast-in joint down the exposed end of a concrete wall.
        ex = x + (T - 3 if open_e else 1)
        pygame.draw.line(surf, _shift(tone, -14), (ex, y + 4), (ex, y + T - 4), 1)

    if ch == "W":
        if not open_n and not open_s:
            _paint_coach_panel(surf, x, y, tone, col, row, grid)
        else:
            _paint_fence_run(surf, x, y, tone, col, row, open_w, open_e)


def _paint_coach_panel(surf, x, y, tone, col, row, grid):
    """A tile inside a thick W band: coach body / platform canopy panel."""
    surf.blit(material_at("coach", x, y), (x, y))
    body = _shift((44, 50, 56), (_h(col, 0, 17) % 5) - 2)
    # Body seam every other tile, a rivet line under the roof edge.
    if col % 2 == 0:
        pygame.draw.line(surf, _shift(body, -10), (x, y + 3), (x, y + T - 3), 1)
    above = grid[row - 1][col] if row > 0 else "W"
    below = grid[row + 1][col] if row + 1 < len(grid) else "W"
    if above in "CW" :
        # top row of the band: roof edge + snow
        pygame.draw.rect(surf, _shift(body, 16), (x, y + 2, T, 4))
        pygame.draw.rect(surf, _SNOW, (x, y, T, 3))
    if below in "CW":
        pygame.draw.rect(surf, _shift(body, -16), (x, y + T - 5, T, 4))
    if above == "W" and below == "W":
        # middle row: the window strip, lit from inside
        win = pygame.Rect(x + 3, y + T // 2 - 7, T - 6, 14)
        pygame.draw.rect(surf, (26, 30, 34), win)
        pygame.draw.rect(surf, (196, 168, 108), win.inflate(-2, -4))
        pygame.draw.line(surf, (120, 96, 54), (win.centerx, win.y + 2),
                         (win.centerx, win.bottom - 2), 1)
        pygame.draw.rect(surf, _shift(body, 10), (x, win.y - 3, T, 2))
        pygame.draw.rect(surf, (66, 62, 52), (x, win.bottom + 2, T, 2))


def _paint_fence_run(surf, x, y, tone, col, row, open_w, open_e):
    """Wire fence: one continuous rail, posts every other tile, sagging wire."""
    rail_y = y + 9
    top, bot = y + 2, y + T - 4
    # Continuous top rail across the run (skips the tile seam entirely).
    pygame.draw.line(surf, _shift(tone, 14), (x, rail_y - 1), (x + T - 1, rail_y - 1), 2)
    pygame.draw.line(surf, _shift(tone, -12), (x, rail_y + 1), (x + T - 1, rail_y + 1), 1)
    # Mesh: diagonal weave, phase-locked to the column so it does not restart.
    for i in range(-1, 3):
        mx = x + i * 11 + (col % 2) * 5
        pygame.draw.line(surf, (58, 62, 68), (mx, top + 3), (mx + 10, bot), 1)
        pygame.draw.line(surf, (58, 62, 68), (mx + 10, top + 3), (mx, bot), 1)
    if open_w or (col % 2) == 0:
        # A post, only where the fence has one: never a picket every 32 px.
        px = x + 1 if open_w else x + T // 2
        pygame.draw.line(surf, (30, 34, 38), (px + 1, top), (px + 1, bot + 2), 3)
        pygame.draw.line(surf, _shift(tone, 8), (px, top), (px, bot + 2), 2)
        pygame.draw.circle(surf, _SNOW, (px, top), 3)
        pygame.draw.circle(surf, (188, 200, 218), (px, top + 1), 2)
    if open_e:
        pygame.draw.line(surf, (30, 34, 38), (x + T - 2, top), (x + T - 2, bot + 2), 3)
    # Sagging wire between the posts.
    wy = y + T - 9
    pygame.draw.line(surf, (52, 56, 62), (x, wy), (x + T - 1, wy + 2), 1)
    pygame.draw.line(surf, (66, 70, 76), (x, wy + 1), (x + T - 1, wy + 3), 1)


def _paint_roofs(surf, grid, stage_id):
    """Buildings read as roofs, not as thick walls.

    A solid block of "C" used to be painted tile-by-tile by the wall painter,
    which gave the post a slab of brickwork where its roof should be.  Any
    concrete tile fully surrounded by concrete is roof: tar-and-gravel with
    snow lying in the seams, and the occasional vent, hatch or skylight.
    """
    h = len(grid)
    w = len(grid[0]) if h else 0

    def solid(c, r):
        return 0 <= c < w and 0 <= r < h and grid[r][c] in "CW"

    for row in range(h):
        for col in range(w):
            if grid[row][col] != "C":
                continue
            if not (solid(col - 1, row) and solid(col + 1, row)
                    and solid(col, row - 1) and solid(col, row + 1)):
                continue
            x, y = col * T, row * T
            k = _h(col // 2, row // 2, 41)          # 2x2 feature clusters
            surf.blit(material_at("roof", x, y), (x, y))
            roof = _shift((38, 42, 49), (k % 6) - 3)
            # Tar seams: one direction per clustering, so roofs stay calm.
            if k % 4 in (0, 1):
                pygame.draw.line(surf, _shift(roof, -7), (x, y + 1), (x + T - 1, y + 1), 1)
                pygame.draw.line(surf, _shift(roof, 5), (x, y + 2), (x + T - 1, y + 2), 1)
            else:
                pygame.draw.line(surf, _shift(roof, -7), (x + 1, y), (x + 1, y + T - 1), 1)
                pygame.draw.line(surf, _shift(roof, 5), (x + 2, y), (x + 2, y + T - 1), 1)
            # Snow lying in the lee of the roof edge and in the seams.
            if k % 5 == 0:
                _snow_bank(surf, x + 2, y + T - 12, T - 4, 10, col * 3 + row, a=40)
            if k % 7 == 0:
                pygame.draw.rect(surf, _SNOW_DIM, (x + 6, y + 6, T - 12, 2))
            # Plant on the roof: a vent stack, a hatch, a skylight.
            f = k % 23
            if f == 0:
                pygame.draw.rect(surf, _INK, (x + 9, y + 9, 14, 14))
                pygame.draw.rect(surf, (72, 76, 82), (x + 10, y + 10, 12, 12))
                pygame.draw.rect(surf, (44, 48, 54), (x + 12, y + 12, 8, 8))
                pygame.draw.rect(surf, _SNOW, (x + 7, y + 7, 18, 3))
            elif f == 3:
                pygame.draw.rect(surf, (66, 70, 76), (x + 8, y + 12, 16, 10), border_radius=2)
                pygame.draw.rect(surf, (30, 34, 40), (x + 10, y + 14, 12, 6))
                pygame.draw.rect(surf, (120, 132, 146), (x + 8, y + 12, 16, 10), 1, border_radius=2)
            elif f == 8 and stage_id in (STAGE_CUSTOMS, STAGE_RAIL):
                # Skylight catching the floodlights.
                pygame.draw.rect(surf, (52, 62, 74), (x + 5, y + 8, T - 10, T - 16))
                pygame.draw.rect(surf, (76, 92, 108), (x + 6, y + 9, T - 14, T - 20))
                pygame.draw.line(surf, (46, 54, 64), (x + T // 2, y + 8),
                                 (x + T // 2, y + T - 8), 1)
                pygame.draw.rect(surf, (128, 146, 164), (x + 5, y + 8, T - 10, T - 16), 1)
            elif f == 15:
                pygame.draw.circle(surf, (30, 33, 38), (x + T // 2, y + T // 2), 5)
                pygame.draw.circle(surf, (78, 82, 88), (x + T // 2, y + T // 2), 5, 1)


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
    """Road paint: the two-lane crossing, its stop lines and bay markings."""
    # Cross-bars across the apron where the boom gates sit.
    y = 3 * T + T // 2
    for x in range(1 * T, 28 * T, 34):
        pygame.draw.line(surf, (128, 104, 52), (x, y), (x + 18, y), 2)
    # Keep-clear box at the crossing gate: an outline, not a picket fence.
    pygame.draw.rect(surf, (128, 104, 52), (12 * T, T + 2, 6 * T, 3 * T - 4), 2)
    for x in range(12 * T + 10, 18 * T - 10, 26):
        pygame.draw.line(surf, (104, 88, 50), (x, T + 6), (x, T + 20), 2)
    # Stop line in front of the booms.
    pygame.draw.line(surf, (176, 172, 150), (12 * T, 3 * T - 4), (19 * T, 3 * T - 4), 3)
    # Centre dashes down the approach road (cols 13..17, rows 12..18).
    cx = 15 * T + T // 2
    for yy in range(12 * T, 19 * T, 46):
        pygame.draw.line(surf, (128, 104, 52), (cx, yy), (cx, yy + 22), 3)
    # Bay markings on the paved inspection yard: stall dividers.
    for bx in range(2 * T + 6, 13 * T, 2 * T):
        pygame.draw.line(surf, (92, 90, 84), (bx, 12 * T + 8), (bx, 15 * T + 22), 2)
    for bx in range(2 * T + 6, 13 * T, 2 * T):
        pygame.draw.line(surf, (120, 118, 110), (bx, 12 * T + 8), (bx, 12 * T + 30), 2)
    # Manhole covers + the drain the yard empties into.
    for cx_, cy_ in ((10, 13), (24, 16), (16, 17)):
        _drain(surf, cx_ * T + T // 2, cy_ * T + T // 2, cx_ * 7)
    # Snow banked against the post's north face and the store eaves.
    for col in range(2, 12):
        _snow_bank(surf, col * T, 5 * T - 5, T, 9, col * 3)
    for col in range(19, 29):
        _snow_bank(surf, col * T, 10 * T - 4, T, 8, col * 5)


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
    for row in (9, 14, 19):
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


# ─────────────────────────────────────────────
# Floor variety, plates and litter (flat, baked)
# ─────────────────────────────────────────────
# Same rule as the kit above: painted into the ground, no footprint.  Shapes
# are hard-edged with a 1 px ink rim; nothing here is blurred or noisy.
_NOT_FLOOR = "CWBDY"
_TAPE = (150, 124, 56)
_HAZARD = (156, 128, 52)


def _floor_at(grid, px, py):
    c, r = int(px // T), int(py // T)
    return 0 <= r < len(grid) and 0 <= c < len(grid[0]) and grid[r][c] not in _NOT_FLOOR


def _open_spot(grid, px, py, m=16):
    """A flat item stays on open floor: its centre and corners at margin ``m``."""
    return _floor_at(grid, px, py) and all(
        _floor_at(grid, px + dx, py + dy) for dx in (-m, m) for dy in (-m, m))


def _floor_variety(surf, stage_id, grid):
    """Repair pours and cracks: the yard stops being one poured slab.

    A patch is a different pour (a step darker or paler, 1 px seam); a crack
    is a 1 px dark walk with a pale lip.  Both are clamped inside their tile.
    """
    h, w = len(grid), len(grid[0])
    for row in range(h):
        for col in range(w):
            if grid[row][col] in _NOT_FLOOR:
                continue
            k = _h(col, row, 211)
            x, y = col * T, row * T
            if k % 9 == 0:
                pw = min(T - 8, 28 + (k >> 3) % 30)
                ph = min(T - 8, 20 + (k >> 8) % 30)
                px = x + 4 + (k >> 14) % (T - 7 - pw)
                py = y + 4 + (k >> 19) % (T - 7 - ph)
                tone = ((4, 6, 10, 42), (190, 200, 216, 16), (4, 6, 10, 24))[(k >> 4) % 3]
                patch = pygame.Surface((pw, ph), pygame.SRCALPHA)
                patch.fill(tone)
                pygame.draw.rect(patch, (8, 10, 14, 90), patch.get_rect(), 1)
                surf.blit(patch, (px, py))
            elif k % 7 == 3:
                rnd = random.Random(k)
                cx = x + 10 + rnd.randrange(T - 20)
                cy = y + 10 + rnd.randrange(T - 20)
                ang = rnd.random() * math.tau
                for _ in range(4 + rnd.randrange(3)):
                    ang += rnd.uniform(-0.7, 0.7)
                    nx = max(x + 3, min(x + T - 3, cx + math.cos(ang) * rnd.randrange(7, 15)))
                    ny = max(y + 3, min(y + T - 3, cy + math.sin(ang) * rnd.randrange(7, 15)))
                    pygame.draw.line(surf, (70, 76, 86), (cx + 1, cy + 1), (nx + 1, ny + 1), 1)
                    pygame.draw.line(surf, (18, 20, 24), (cx, cy), (nx, ny), 1)
                    cx, cy = nx, ny


def _prop_stains(surf, stage_id):
    """Rust bleeding down from the steel: hard streaks under rusting props."""
    for kind, x, y, w, h in _maps.props_for(stage_id):
        if kind not in _RUSTY:
            continue
        for i in range(max(2, w * 2)):
            k = _h(x + i, y, 233)
            sx = x * T + 6 + k % max(1, w * T - 12)
            sy = (y + h) * T - 2
            ln = 8 + (k >> 6) % 14
            pygame.draw.rect(surf, (74, 46, 34), (sx, sy, 3, ln))
            pygame.draw.rect(surf, (104, 64, 44), (sx, sy, 1, ln))


_RUSTY = frozenset(("barrels", "boxcar", "container", "guard_truck", "truck_burnt",
                    "apc", "plough", "coil", "sleeper_stack", "water_tower"))


def _steel_plate(surf, rect):
    """Tile the steel material across ``rect`` in world space, dimmed to the yard."""
    r = pygame.Rect(rect)
    for ty in range(r.y - r.y % T, r.bottom, T):
        for tx in range(r.x - r.x % T, r.right, T):
            clip = pygame.Rect(tx, ty, T, T).clip(r)
            if clip.w > 0 and clip.h > 0:
                surf.blit(material_at("steel", tx, ty), clip.topleft,
                          (clip.x - tx, clip.y - ty, clip.w, clip.h))
    surf.fill((176, 182, 190), r, special_flags=pygame.BLEND_RGB_MULT)
    for bx, by in (r.topleft, r.topright, r.bottomleft, r.bottomright):
        bx += 4 if bx == r.x else -5
        by += 4 if by == r.y else -5
        pygame.draw.circle(surf, (24, 26, 30), (bx + 1, by + 1), 2)
        pygame.draw.circle(surf, (118, 124, 134), (bx, by), 1)
    pygame.draw.rect(surf, _INK, r.inflate(2, 2), 1)


def _hazard(surf, rect):
    """Diagonal hazard stripe, dimmed to the yard's yellow."""
    r = pygame.Rect(rect)
    pygame.draw.rect(surf, (30, 30, 28), r)
    old = surf.get_clip()
    surf.set_clip(r)
    for xx in range(r.x - r.h, r.right, 12):
        pygame.draw.line(surf, _HAZARD, (xx, r.bottom), (xx + r.h, r.y), 5)
    surf.set_clip(old)
    pygame.draw.rect(surf, _INK, r, 1)


def _threshold(surf, col, row, cols=3, dy=0, door_up=True, h=40):
    """Steel plate in front of an exit door, hazard stripe on the door side."""
    r = pygame.Rect(col * T + 6, row * T + dy, cols * T - 12, h)
    _steel_plate(surf, r)
    strip = pygame.Rect(r.x, r.y if door_up else r.bottom - 8, r.w, 8)
    _hazard(surf, strip)


def _crossing(surf, grid, cx, row):
    """Rail crossing plates: two steel slabs flanking the running rail."""
    x = int(cx * T) - T
    top = pygame.Rect(x, row * T - 30, 2 * T, 21)
    low = pygame.Rect(x, row * T + 9, 2 * T, 21)
    if not all(_floor_at(grid, px, py) for r in (top, low)
               for px in (r.x, r.right - 1) for py in (r.y, r.bottom - 1)):
        return False
    _steel_plate(surf, top)
    _steel_plate(surf, low)
    return True


def _tape_box(surf, x, y, w, h, col=_TAPE):
    """A painted storage bay: four taped corners, not a full outline."""
    r = pygame.Rect(x, y, w, h)
    n = 16
    for (cx, cy), sx, sy in ((r.topleft, 1, 1), (r.topright, -1, 1),
                             (r.bottomleft, 1, -1), (r.bottomright, -1, -1)):
        pygame.draw.line(surf, col, (cx, cy), (cx + sx * n, cy), 3)
        pygame.draw.line(surf, col, (cx, cy), (cx, cy + sy * n), 3)


def _road_arrow(surf, x, y, col=(112, 110, 102)):
    """Painted lane arrow, pointing north."""
    pygame.draw.polygon(surf, col, [(x, y - 20), (x + 11, y - 4), (x + 4, y - 4),
                                    (x + 4, y + 16), (x - 4, y + 16), (x - 4, y - 4),
                                    (x - 11, y - 4)])


def _checker(surf, grid, c0, r0, c1, r1, size=32):
    """Lino squares across an interior: alternate cells a step paler."""
    cell = pygame.Surface((size, size), pygame.SRCALPHA)
    cell.fill((190, 200, 216, 12))
    for row in range(r0 * T // size, r1 * T // size):
        for col in range(c0 * T // size, c1 * T // size):
            if (row + col) % 2 and _floor_at(grid, col * size + size // 2,
                                             row * size + size // 2):
                surf.blit(cell, (col * size, row * size))


# Litter: every drawer is (surf, x, y, k) with x, y the centre and k a seed.
# Extents stay under the 16 px clearance ``_open_spot`` checks.
def _it_tin(surf, x, y, k):
    pygame.draw.rect(surf, _INK, (x - 6, y - 4, 12, 9))
    pygame.draw.rect(surf, (76, 82, 64), (x - 5, y - 3, 10, 7))
    pygame.draw.line(surf, (112, 120, 94), (x - 5, y - 3), (x + 4, y - 3), 1)
    pygame.draw.rect(surf, (176, 150, 66), (x - 1, y, 3, 2))


def _it_helmet(surf, x, y, k):
    pygame.draw.ellipse(surf, _INK, (x - 7, y - 6, 15, 12))
    pygame.draw.ellipse(surf, (62, 68, 60), (x - 6, y - 5, 13, 10))
    pygame.draw.arc(surf, (104, 112, 100), (x - 5, y - 4, 9, 7), 0.6, 2.6, 1)
    pygame.draw.line(surf, (30, 32, 30), (x - 5, y + 2), (x + 5, y + 2), 1)


def _it_shells(surf, x, y, k):
    for i in range(6 + k % 4):
        hh = _h(i, k, 29)
        sx, sy = x + hh % 20 - 10, y + (hh >> 5) % 12 - 6
        pygame.draw.rect(surf, (20, 18, 14), (sx + 1, sy + 1, 3, 2))
        pygame.draw.rect(surf, (178, 150, 66), (sx, sy, 3, 2))


def _it_boots(surf, x, y, k):
    a = (k % 628) / 100.0
    ux, uy = math.cos(a), math.sin(a)
    for i in range(3):
        for side in (-1, 1):
            px = x + ux * (i - 1) * 8 - uy * side * 4
            py = y + uy * (i - 1) * 8 + ux * side * 4 + (2 if (i + side) % 2 else 0)
            pygame.draw.ellipse(surf, (28, 32, 38), (px - 2, py - 3, 5, 7))


def _it_grit(surf, x, y, k):
    pts = [(x + math.cos(i * 1.05) * (6 + _h(i, k, 3) % 7),
            y + math.sin(i * 1.05) * (4 + _h(i, k, 5) % 5)) for i in range(6)]
    pygame.draw.polygon(surf, (28, 30, 34), pts)
    pygame.draw.polygon(surf, (64, 68, 76), pts, 1)
    for i in range(4):
        pygame.draw.rect(surf, (74, 78, 86),
                         (x - 10 + _h(i, k, 7) % 20, y - 6 + _h(i, k, 9) % 12, 2, 1))


def _it_scorch(surf, x, y, k):
    r = 9 + k % 6
    pts = [(x + math.cos(i * 0.9) * r * (0.7 + (_h(i, k, 11) % 40) / 100.0),
            y + math.sin(i * 0.9) * r * 0.7 * (0.7 + (_h(i, k, 13) % 40) / 100.0))
           for i in range(7)]
    pygame.draw.polygon(surf, (20, 21, 25), pts)
    pygame.draw.polygon(surf, (44, 46, 52), pts, 1)


def _it_cable(surf, x, y, k):
    pts = [(x - 14, y + 4), (x - 2, y + 4 - k % 3), (x + 4, y - 4), (x + 14, y - 5 + (k >> 2) % 3)]
    pygame.draw.lines(surf, (14, 16, 20), False, [(px, py + 2) for px, py in pts], 3)
    pygame.draw.lines(surf, (34, 38, 44), False, pts, 3)
    pygame.draw.lines(surf, (70, 76, 86), False, [(px, py - 1) for px, py in pts], 1)


def _it_sleeper(surf, x, y, k):
    w, h = (30, 9) if k % 2 else (9, 30)
    r = pygame.Rect(x - w // 2, y - h // 2, w, h)
    pygame.draw.rect(surf, _INK, r.inflate(2, 2))
    pygame.draw.rect(surf, (66, 50, 38), r)
    pygame.draw.line(surf, (98, 78, 58), r.topleft, (r.right - 1, r.top), 1)
    for f in (0.25, 0.75):
        pygame.draw.circle(surf, (28, 24, 22), (int(r.x + r.w * f), r.centery), 1)


def _it_spill(surf, x, y, k):
    pts = [(x + math.cos(i * 0.85) * (6 + _h(i, k, 15) % 7),
            y + math.sin(i * 0.85) * (4 + _h(i, k, 17) % 5)) for i in range(8)]
    pygame.draw.polygon(surf, (22, 22, 24), pts)
    for i in range(5):
        pygame.draw.rect(surf, (62, 62, 66),
                         (x - 7 + _h(i, k, 19) % 14, y - 4 + _h(i, k, 21) % 8, 2, 1))


def _it_tarp(surf, x, y, k):
    """A dropped tarp: flatter and darker than any crate, so it never reads as cover."""
    pts = [(x - 13, y - 4), (x - 4, y - 8), (x + 9, y - 6), (x + 14, y + 1),
           (x + 6, y + 7), (x - 8, y + 6)]
    pygame.draw.polygon(surf, (30, 36, 32), pts)
    pygame.draw.polygon(surf, (50, 58, 50), pts, 1)
    pygame.draw.line(surf, (24, 28, 26), (x - 6, y - 2), (x + 7, y + 2), 1)


def _it_paper(surf, x, y, k):
    _papers(surf, x, y, 11, k)


def _it_rust(surf, x, y, k):
    pts = [(x + math.cos(i * 1.05) * (7 + _h(i, k, 23) % 6),
            y + math.sin(i * 1.05) * (4 + _h(i, k, 25) % 4)) for i in range(6)]
    pygame.draw.polygon(surf, (62, 40, 30), pts)
    pygame.draw.polygon(surf, (96, 60, 42), pts, 1)


_LITTER = {
    "tin": _it_tin, "helmet": _it_helmet, "shells": _it_shells, "boots": _it_boots,
    "grit": _it_grit, "scorch": _it_scorch, "cable": _it_cable, "sleeper": _it_sleeper,
    "spill": _it_spill, "tarp": _it_tarp, "paper": _it_paper, "rust": _it_rust,
}

# (tile rect x0, y0, x1, y1, kinds, count).  Rects are hints: ``_open_spot``
# rejects walls and props, so a rect may overlap them.
_LITTER_PLAN = {
    STAGE_CUSTOMS: (
        ((2, 1, 28, 5), ("tin", "helmet", "shells", "boots", "grit", "cable"), 14),
        ((12, 5, 19, 12), ("shells", "boots", "grit", "tin", "paper"), 9),
        ((2, 12, 13, 19), ("tin", "shells", "grit", "helmet", "cable", "tarp"), 13),
        ((13, 12, 29, 19), ("shells", "grit", "tin", "boots", "helmet"), 13),
        ((3, 6, 11, 11), ("paper", "tin"), 5),
        ((20, 6, 28, 9), ("paper", "tin", "shells", "tarp"), 5),
    ),
    STAGE_NOMAN: (
        ((1, 1, 39, 4), ("shells", "helmet", "cable", "tin", "grit"), 14),
        ((1, 4, 39, 14), ("scorch", "shells", "helmet", "tin", "boots", "grit", "tarp"), 38),
        ((1, 14, 39, 17), ("shells", "tin", "grit", "boots", "cable"), 12),
    ),
    STAGE_RAIL: (
        ((1, 4, 45, 6), ("shells", "tin", "paper", "grit", "cable"), 9),
        ((1, 7, 45, 12), ("sleeper", "spill", "rust", "shells", "grit", "tin", "cable"), 24),
        ((1, 12, 45, 19), ("sleeper", "spill", "rust", "shells", "grit", "tarp", "cable"), 30),
        ((1, 19, 45, 25), ("sleeper", "spill", "rust", "shells", "grit", "tin", "tarp"), 20),
    ),
}
_LITTER_PLAN[STAGE_BOXCAR] = _LITTER_PLAN[STAGE_RAIL]
_LITTER_PLAN[STAGE_TRAIN] = _LITTER_PLAN[STAGE_RAIL]


def _litter(surf, stage_id, grid):
    """Scatter the plan: deterministic, spaced, only where the grid is open."""
    placed = []
    for i, ((x0, y0, x1, y1), kinds, count) in enumerate(_LITTER_PLAN.get(stage_id, ())):
        rnd = random.Random(0x11A5 + i * 977 + len(grid))
        n = tries = 0
        while n < count and tries < count * 40:
            tries += 1
            px = rnd.uniform(x0, x1) * T
            py = rnd.uniform(y0, y1) * T
            if not _open_spot(grid, px, py):
                continue
            if any((px - qx) ** 2 + (py - qy) ** 2 < 46 * 46 for qx, qy in placed):
                continue
            placed.append((px, py))
            _LITTER[kinds[rnd.randrange(len(kinds))]](
                surf, int(px), int(py), rnd.randrange(1 << 16))
            n += 1


# (col, row, dy, h) of each exit's steel plate, see ``_flat_detail``.
_EXIT_PLATES = {STAGE_CUSTOMS: (14, 1, 0, 40), STAGE_NOMAN: (19, 1, 0, 40),
                STAGE_RAIL: (24, 11, 6, 44)}


def exit_lamps(stage_id):
    """World points of the two status lamps at the ends of a stage's exit plate."""
    plate = _EXIT_PLATES.get(stage_id)
    if plate is None:
        return ()
    col, row, dy, h = plate
    y = row * T + dy + h // 2 + 4
    return ((col * T + 16, y), ((col + 3) * T - 16, y))


def _flat_detail(surf, stage_id, grid):
    """Interiors, exit plates and crossings, then the litter."""
    if stage_id == STAGE_CUSTOMS:
        _checker(surf, grid, 3, 6, 11, 11)
        for bx in (20.35, 23.0, 25.65):
            _tape_box(surf, int(bx * T), int(6.3 * T), 2 * T - 10, int(2.3 * T))
        _road_arrow(surf, int(14.5 * T), int(16.2 * T))
        _road_arrow(surf, int(16.5 * T), int(16.2 * T))
        _threshold(surf, 14, 1)
    elif stage_id == STAGE_NOMAN:
        _threshold(surf, 19, 1)
        _threshold(surf, 19, 16, dy=T - 40, door_up=False)   # the way in, no lamps
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        for row in (9, 14, 19):
            n = 0
            for cx in (15.5, 33.5, 18.0, 28.0, 11.0, 37.0, 22.0):
                if n < 2 and _crossing(surf, grid, cx, row):
                    n += 1
        _threshold(surf, 24, 11, dy=6, h=44)
    _litter(surf, stage_id, grid)


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
    _ground_wear(surf, stage_id)
    _frost(surf, stage_id)
    _floor_variety(surf, stage_id, grid)
    for row in range(h):
        for col in range(w):
            ch = grid[row][col]
            if ch in "CW":
                _paint_wall(surf, stage_id, col, row, ch, grid)
            elif ch == "D":
                _paint_door(surf, stage_id, col, row)
    _paint_roofs(surf, grid, stage_id)
    _wall_drifts(surf, grid)
    _prop_stains(surf, stage_id)
    if stage_id == STAGE_CUSTOMS:
        _customs_detail(surf, grid)
        _customs_dress(surf, grid)
    elif stage_id == STAGE_NOMAN:
        _noman_detail(surf, grid)
        _noman_dress(surf, grid)
    elif stage_id in (STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN):
        _rail_detail(surf, grid)
        _rail_dress(surf, grid)
    _flat_detail(surf, stage_id, grid)
    _ground_ao(surf, grid)
    for row in _prop_rows(stage_id):
        surf.blit(row["shadow"], (row["x"] + 7, row["bottom"] - row["fh"] + 9))
    _GROUND[stage_id] = surf
    return surf


_VOID = None


def void_surface():
    """Out-of-map ground: the darkest material, tiled once and cached.

    The frame used to sit on a flat ``C_BG_GAME`` rectangle wherever the map
    ran out, which read as a hole in the screenshots.  Now it is the same
    surface language as the map, just darker and out of play.
    """
    global _VOID
    if _VOID is None or _VOID.get_size() != (WIDTH, HEIGHT):
        _VOID = pygame.Surface((WIDTH, HEIGHT))
        for row in range(0, HEIGHT, T):
            for col in range(0, WIDTH, T):
                _VOID.blit(material_at("asphalt_d", row * T + col, row * T), (col, row))
        shade = pygame.Surface((WIDTH, HEIGHT))
        shade.fill((150, 150, 158))
        _VOID.blit(shade, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
    return _VOID


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
_DYNAMIC_KINDS = frozenset(("fuel_tank",))
_STEEL = (64, 68, 74)
_STEEL_HI = (96, 100, 108)
_STEEL_LO = (34, 36, 40)
_INK = (10, 12, 16)


def _new_prop(w_px, h_px, over=0, side=0):
    surf = pygame.Surface((w_px + side * 2, h_px + over), pygame.SRCALPHA)
    return surf, side, over


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
    _mat_fill(surf, (x + 4, y + 14, w - 8, h - 26), "coach", body, seed, seed)
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
    _mat_fill(surf, (x + 3, y + 6, w - 6, h - 9), "plank", c, seed, seed)
    pygame.draw.rect(surf, c, (x + 3, y + 6, w - 6, h - 9), 0) if False else None
    pygame.draw.rect(surf, _shift(c, 14), (x + 3, y + 6, w - 6, h - 9), 1)
    pygame.draw.line(surf, _shift(c, -18), (x + 3, y + 6), (x + w - 4, y + h - 4), 2)
    pygame.draw.rect(surf, (196, 206, 220), (x + 4, y + 6, w - 8, 4), border_radius=2)


def _mat_fill(surf, rect, name, colour, col=0, row=0):
    """Tile a material across ``rect`` (nearest-scaled when smaller)."""
    r = pygame.Rect(rect)
    if r.w <= 0 or r.h <= 0:
        return
    tile = material_tile(name, col, row, colour)
    if r.w <= T and r.h <= T:
        surf.blit(pygame.transform.scale(tile, (r.w, r.h)), r.topleft)
        return
    for oy in range(0, r.h, T):
        for ox in range(0, r.w, T):
            piece = tile if (ox + T <= r.w and oy + T <= r.h) else \
                pygame.transform.scale(tile, (min(T, r.w - ox), min(T, r.h - oy)))
            surf.blit(piece, (r.x + ox, r.y + oy))


def _blit_center(surf, img, w, h, oy, lift=0):
    """Blit ``img`` centred in a w x h footprint, bottom-aligned."""
    iw, ih = img.get_size()
    surf.blit(img, ((w - iw) // 2, oy + h - ih - lift if ih <= h else oy + h - ih))


def _art(name):
    return artpack.get(name)




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
    _mat_fill(surf, roof, "rib", _shift(body, 10), seed, 1)
    _mat_fill(surf, side, "rib", _shift(body, -14), seed, 2)
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


# ── the border-crossing kit ─────────────────────────────────────────────
# M6 used to dress its yards with the M2 city wrecks (civilian cars, the IPA
# truck) straight out of ``artpack.vehicle``.  Everything below is authored
# for this mission instead: a frozen crossing's own furniture, in the same
# hard-edged night palette as the rest of the map art.
def _draw_boom(surf, x, y, w, h):
    """Border barrier: a striped boom across the lane on its post."""
    base = y + h - 8
    # Post + counterweight.
    pygame.draw.rect(surf, _INK, (x + 3, base - 22, 12, 24))
    pygame.draw.rect(surf, (86, 90, 96), (x + 4, base - 21, 10, 22))
    pygame.draw.rect(surf, _SNOW, (x + 4, base - 21, 10, 3))
    pygame.draw.circle(surf, (48, 52, 58), (x + 9, base - 6), 3)
    # Boom arm, raised at the rest angle the Guards left it.
    arm = [(x + 9, base - 20), (x + w - 4, base - 30), (x + w - 4, base - 25),
           (x + 9, base - 15)]
    pygame.draw.polygon(surf, _INK, [(px, py + 1) for px, py in arm])
    pygame.draw.polygon(surf, (208, 206, 196), arm)
    for i in range(4):
        f = (i + 0.15) / 4.0
        ax = x + 9 + (w - 13) * f
        ay = base - 20 - 10 * f
        pygame.draw.polygon(surf, (188, 62, 48),
                            [(ax, ay), (ax + 7, ay - 1.6), (ax + 7, ay + 3.4), (ax, ay + 5)])
    pygame.draw.circle(surf, (240, 196, 96), (x + w - 6, base - 27), 2)
    # Snow on the post head and a drift at the foot.
    pygame.draw.rect(surf, _SNOW, (x + 2, base + 12, 16, 3))
    pygame.draw.rect(surf, (24, 26, 32), (x + 2, base + 16, 16, 2))


def _draw_guard_truck(surf, x, y, w, h, seed, burnt=False):
    """Guard truck, top-down: cab forward (east), canvas tilt behind."""
    body = (52, 50, 46) if burnt else (72, 76, 64)
    tilt = (44, 42, 40) if burnt else (88, 92, 78)
    top, bot = y + 8, y + h - 6
    mid = (top + bot) // 2
    # Wheels first, so the hull overlaps them.
    for wx in (x + 14, x + w - 26):
        pygame.draw.rect(surf, (18, 18, 20), (wx, top - 3, 12, 6), border_radius=2)
        pygame.draw.rect(surf, (18, 18, 20), (wx, bot - 3, 12, 6), border_radius=2)
    # Canvas tilt over the load bed.
    bed = pygame.Rect(x + 6, top + 2, w - 34, bot - top - 4)
    pygame.draw.rect(surf, _INK, bed.inflate(2, 2))
    _mat_fill(surf, bed, "rib", tilt, seed, 3)
    for rx in range(bed.x + 6, bed.right - 4, 11):
        pygame.draw.line(surf, _shift(tilt, -14), (rx, bed.y + 2), (rx, bed.bottom - 2), 2)
    for ry in (bed.y + 3, bed.centery, bed.bottom - 4):
        pygame.draw.line(surf, _shift(tilt, 10), (bed.x + 2, ry), (bed.right - 2, ry), 1)
    # Cab + windscreen + roof snow.
    cab = pygame.Rect(bed.right + 2, top + 4, 22, bot - top - 8)
    pygame.draw.rect(surf, _INK, cab.inflate(2, 2))
    pygame.draw.rect(surf, body, cab)
    pygame.draw.rect(surf, (34, 44, 52) if not burnt else (26, 24, 22),
                     (cab.x + 4, cab.y + 3, cab.w - 8, 6))
    pygame.draw.rect(surf, _SNOW, (cab.x + 2, cab.y - 1, cab.w - 4, 4))
    # Guard chevron on the tilt, and the snow line along the whole roof.
    pygame.draw.rect(surf, (150, 44, 38) if not burnt else (70, 38, 34),
                     (bed.x + 8, mid - 3, 18, 6))
    pygame.draw.rect(surf, (200, 210, 224) if not burnt else (96, 96, 96),
                     (bed.x + 2, bed.y, bed.w - 4, 3))
    pygame.draw.circle(surf, (236, 226, 186) if not burnt else (60, 56, 52),
                       (cab.right - 3, cab.centery), 2)


def _draw_plough(surf, x, y, w, h, seed):
    """Snow plough: heavy truck with the angled blade out front."""
    _draw_guard_truck(surf, x + 14, y, w - 14, h, seed)
    top, bot = y + 6, y + h - 4
    blade = [(x + 2, bot), (x + 20, top), (x + 28, top + 2), (x + 12, bot)]
    pygame.draw.polygon(surf, _INK, [(px + 1, py + 2) for px, py in blade])
    pygame.draw.polygon(surf, (146, 150, 156), blade)
    pygame.draw.polygon(surf, (176, 180, 186), blade, 2)
    for i in range(3):
        bx = x + 7 + i * 6
        pygame.draw.line(surf, (108, 112, 118), (bx, bot - 3), (bx + 12, top + 4), 2)
    pygame.draw.line(surf, _SNOW, (x + 18, top + 1), (x + 27, top + 3), 2)
    pygame.draw.rect(surf, _SNOW, (x - 2, bot + 1, w, 3))
    pygame.draw.rect(surf, (226, 232, 240), (x - 4, bot + 3, 26, 2))


def _draw_fuel_tank(surf, x, y, w, h, seed, alive=True):
    """Yard fuel tank: sits on saddles, snow on the crown, frost on the seam."""
    top = y + 8
    body = pygame.Rect(x + 4, top, w - 8, h - 16)
    pygame.draw.rect(surf, _INK, body.inflate(3, 3))
    shell = (122, 124, 118) if alive else (58, 52, 48)
    pygame.draw.rect(surf, shell, body, border_radius=9)
    pygame.draw.rect(surf, _shift(shell, 18), (body.x + 3, body.y + 2, body.w - 6, body.h // 3),
                     border_radius=7)
    pygame.draw.line(surf, _shift(shell, -26), (body.x + 4, body.centery),
                     (body.right - 4, body.centery), 1)
    for sx in range(body.x + 22, body.right - 16, 30):
        pygame.draw.line(surf, _shift(shell, -18), (sx, body.y + 3), (sx, body.bottom - 3), 2)
    for hx in (body.x + 16, body.right - 18):
        pygame.draw.circle(surf, _shift(shell, -30), (hx, body.centery), 4)
        pygame.draw.circle(surf, _shift(shell, 20), (hx, body.centery - 1), 2)
    pygame.draw.rect(surf, _SNOW, (body.x + 6, body.y, body.w - 12, 5), border_radius=3)
    if alive:
        pygame.draw.rect(surf, (188, 68, 52), (body.x + 6, body.bottom - 7, 22, 4))
    # Saddles + footing shadow.
    for sx in (body.x + 18, body.right - 26):
        pygame.draw.rect(surf, (34, 34, 38), (sx, body.bottom - 2, 12, 6))
    pygame.draw.rect(surf, (10, 12, 16), (body.x + 2, body.bottom + 3, body.w - 4, 3))


_FUEL_TANK_SURF = {}


def fuel_tank_surface(w, h, alive=True):
    """Cached yard fuel tank for ``combat`` (it owns the damage state)."""
    key = (w, h, bool(alive))
    surf = _FUEL_TANK_SURF.get(key)
    if surf is None:
        surf = pygame.Surface((w, h), pygame.SRCALPHA)
        _draw_fuel_tank(surf, 0, 0, w, h, 0, alive=alive)
        _FUEL_TANK_SURF[key] = surf
    return surf


def _draw_apc(surf, x, y, w, h, seed):
    """Burnt tracked hulk: hull, track runs, open hatch, scorch."""
    top, bot = y + 10, y + h - 4
    for ty in (top, bot - 8):
        pygame.draw.rect(surf, (26, 26, 28), (x + 4, ty, w - 8, 8), border_radius=3)
        for tx in range(x + 8, x + w - 8, 7):
            pygame.draw.line(surf, (54, 52, 50), (tx, ty + 1), (tx, ty + 6), 1)
    hull = [(x + 10, top + 3), (x + w - 22, top + 1), (x + w - 6, top + 9),
            (x + w - 6, bot - 6), (x + w - 24, bot - 2), (x + 10, bot - 4)]
    pygame.draw.polygon(surf, _INK, [(px, py + 1) for px, py in hull])
    pygame.draw.polygon(surf, (62, 56, 48), hull)
    pygame.draw.polygon(surf, (88, 80, 66), hull, 2)
    pygame.draw.rect(surf, (34, 30, 26), (x + 22, (top + bot) // 2 - 6, 22, 12), border_radius=2)
    pygame.draw.circle(surf, (20, 18, 16), (x + w - 22, (top + bot) // 2), 7)
    pygame.draw.circle(surf, (58, 52, 46), (x + w - 22, (top + bot) // 2), 7, 2)
    pygame.draw.line(surf, (30, 26, 22), (x + 34, top + 6), (x + w - 30, bot - 8), 3)
    pygame.draw.rect(surf, (44, 42, 40), (x + 14, top - 2, w - 30, 3))


def _draw_snow_fence(surf, x, y, w, h, seed):
    """Slatted snow fence: the cheapest thing on a border, and the M6st."""
    base = y + h - 8
    pygame.draw.rect(surf, (12, 14, 18), (x + 2, base + 2, w - 4, 4))
    n = max(2, w // 22)
    for i in range(n + 1):
        px = x + 3 + i * (w - 8) // n
        pygame.draw.line(surf, _INK, (px, base - 26), (px, base + 3), 3)
        pygame.draw.line(surf, (78, 74, 64), (px, base - 26), (px, base + 3), 2)
    for ry in range(base - 24, base, 5):
        pygame.draw.line(surf, (96, 92, 80), (x + 3, ry), (x + w - 4, ry + 1), 2)
        pygame.draw.line(surf, (60, 58, 50), (x + 3, ry + 2), (x + w - 4, ry + 3), 1)
    pygame.draw.rect(surf, _SNOW, (x + 3, base - 27, w - 6, 3))
    pygame.draw.rect(surf, (188, 200, 218), (x + 1, base + 5, w - 2, 3))
    # Drift piled on the lee side.
    pygame.draw.rect(surf, _SNOW, (x + 6, base + 4, w - 14, 4), border_radius=2)


def _draw_pallet(surf, x, y, w, h, seed):
    """Tarped cargo on a pallet - the post is full of them."""
    pygame.draw.rect(surf, (12, 14, 18), (x + 4, y + h - 12, w - 8, 4))
    pygame.draw.rect(surf, (74, 58, 40), (x + 4, y + h - 16, w - 8, 5))
    tarps = ((84, 86, 78), (72, 78, 84), (88, 80, 66))
    col = tarps[seed % len(tarps)]
    body = pygame.Rect(x + 8, y + h - 34, w - 16, 20)
    pygame.draw.rect(surf, _INK, body.inflate(2, 2), border_radius=4)
    pygame.draw.rect(surf, col, body, border_radius=4)
    pygame.draw.line(surf, _shift(col, -16), (body.x + 2, body.centery),
                     (body.right - 2, body.centery), 1)
    pygame.draw.rect(surf, _SNOW, (body.x + 2, body.y, body.w - 4, 4), border_radius=2)
    pygame.draw.line(surf, (54, 50, 44), (body.centerx, body.y + 4),
                     (body.centerx, body.bottom - 2), 1)


def _draw_sleeper_stack(surf, x, y, w, h, seed):
    """Stacked railway sleepers, snow in the gaps."""
    base = y + h - 4
    for r in range(4):
        sy = base - (r + 1) * 8
        off = 3 if r % 2 else 0
        for i in range(max(1, w // 26)):
            sx = x + off + i * 26
            pygame.draw.rect(surf, _INK, (sx, sy, 24, 8))
            pygame.draw.rect(surf, (58, 44, 32), (sx + 1, sy + 1, 22, 6))
            pygame.draw.line(surf, (76, 58, 40), (sx + 3, sy + 2), (sx + 20, sy + 2), 1)
            pygame.draw.rect(surf, _SNOW, (sx + 1, sy, 22, 2))
    pygame.draw.rect(surf, (30, 28, 26), (x + 1, base, w - 2, 3))


def _draw_water_tower(surf, x, y, w, h):
    """Rail yard water tower: legs, tank, snow cap, ladder."""
    cx = x + w // 2
    base = y + h - 4
    for dx in (-16, 16):
        pygame.draw.line(surf, _INK, (cx + dx, base), (cx + dx // 2, base - 62), 4)
        pygame.draw.line(surf, (64, 66, 70), (cx + dx, base), (cx + dx // 2, base - 62), 3)
    for i in range(3):
        yy = base - 16 - i * 18
        pygame.draw.line(surf, (56, 58, 62), (cx - 15 + i * 2, yy), (cx + 15 - i * 2, yy), 2)
    tank = pygame.Rect(cx - 30, base - 118, 60, 54)
    pygame.draw.rect(surf, _INK, tank.inflate(3, 3), border_radius=8)
    pygame.draw.rect(surf, (84, 82, 74), tank, border_radius=8)
    for ry in range(tank.y + 10, tank.bottom - 4, 10):
        pygame.draw.line(surf, (62, 60, 54), (tank.x + 3, ry), (tank.right - 3, ry), 1)
    pygame.draw.rect(surf, _SNOW, (tank.x + 4, tank.y, tank.w - 8, 7), border_radius=4)
    pygame.draw.polygon(surf, (66, 64, 58), [(tank.x - 3, tank.y + 2), (cx, tank.y - 14),
                                             (tank.right + 3, tank.y + 2)])
    pygame.draw.line(surf, _SNOW, (tank.x - 3, tank.y + 2), (cx, tank.y - 14), 2)
    pygame.draw.line(surf, (58, 60, 64), (cx + 24, tank.bottom), (cx + 24, base), 2)


def _draw_gantry(surf, x, y, w, h):
    """Signal gantry over the running lines: legs, lattice beam, lamps."""
    base = y + h - 4
    beam = base - 86
    for dx in (4, w - 10):
        pygame.draw.line(surf, _INK, (x + dx, base), (x + dx + 3, beam), 5)
        pygame.draw.line(surf, (58, 60, 64), (x + dx, base), (x + dx + 3, beam), 3)
    pygame.draw.line(surf, _INK, (x + 3, beam - 3), (x + w - 3, beam - 3), 8)
    pygame.draw.line(surf, (66, 68, 72), (x + 3, beam - 3), (x + w - 3, beam - 3), 5)
    for i in range(0, w - 8, 12):
        pygame.draw.line(surf, (52, 54, 58), (x + 6 + i, beam + 1), (x + 14 + i, beam + 9), 2)
        pygame.draw.line(surf, (52, 54, 58), (x + 14 + i, beam + 1), (x + 6 + i, beam + 9), 2)
    for lx in (x + w // 3, x + 2 * w // 3):
        pygame.draw.rect(surf, _INK, (lx - 4, beam, 9, 14))
        pygame.draw.rect(surf, (44, 46, 50), (lx - 3, beam + 1, 7, 12))
        pygame.draw.circle(surf, (86, 200, 120), (lx, beam + 5), 2)
        pygame.draw.circle(surf, (210, 84, 60), (lx, beam + 10), 2)
    pygame.draw.line(surf, _SNOW, (x + 4, beam - 6), (x + w - 4, beam - 6), 2)


def _draw_kind(kind, surf, oy, w, h, x0, y0, seed):
    if kind == "guard_truck":
        _draw_guard_truck(surf, 0, oy, w, h, seed)
    elif kind == "truck_burnt":
        _draw_guard_truck(surf, 0, oy, w, h, seed, burnt=True)
    elif kind == "plough":
        _draw_plough(surf, 0, oy, w, h, seed)
    elif kind == "boom":
        _draw_boom(surf, 0, oy, w, h)
    elif kind == "snow_fence":
        _draw_snow_fence(surf, 0, oy, w, h, seed)
    elif kind == "pallet":
        _draw_pallet(surf, 0, oy, w, h, seed)
    elif kind == "sleeper_stack":
        _draw_sleeper_stack(surf, 0, oy, w, h, seed)
    elif kind == "water_tower":
        _draw_water_tower(surf, 0, oy, w, h)
    elif kind == "gantry":
        _draw_gantry(surf, 0, oy, w, h)
    elif kind == "apc":
        _draw_apc(surf, 0, oy, w, h, seed)
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
         "jersey": 6, "sandbag": 4, "hedgehog": 10, "container": 0,
         "water_tower": 140, "gantry": 104, "snow_fence": 34, "pallet": 26,
         "sleeper_stack": 30, "boom": 40, "guard_truck": 14, "truck_burnt": 14,
         "plough": 14, "apc": 16, "fuel_tank": 12}


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


_LAMP_HEADS = {}


def _lamp_head(colour, lit):
    """Hard-edged lamp housing: ink rim, steel ring, lens, a hard offset shadow."""
    key = (colour, lit)
    img = _LAMP_HEADS.get(key)
    if img is None:
        img = pygame.Surface((20, 20), pygame.SRCALPHA)
        pygame.draw.circle(img, (6, 8, 12, 120), (11, 12), 7)
        pygame.draw.circle(img, _INK, (9, 9), 7)
        pygame.draw.circle(img, (74, 78, 86), (9, 9), 6)
        pygame.draw.circle(img, (34, 36, 40), (9, 9), 4)
        pygame.draw.circle(img, colour if lit else (44, 46, 50), (9, 9), 3)
        if lit:
            pygame.draw.circle(img, (255, 250, 236), (9, 9), 1)
        pygame.draw.line(img, (118, 122, 130), (5, 5), (7, 4), 1)
        _LAMP_HEADS[key] = img
    return img


def _under_prop(stage_id, wx, wy):
    for row in _prop_rows(stage_id):
        if row["x"] <= wx < row["x"] + row["w"] and row["y"] <= wy < row["y"] + row["h"]:
            return True
    return False


def hides(stage_id, wx, wy):
    """True when a tall prop's overhang covers world point (wx, wy).

    The actor sorts behind the prop (its feet are above the footprint's
    bottom edge) and stands inside the prop's drawn rect, so anything painted
    after the light pass must not show through.
    """
    for row in _prop_rows(stage_id):
        if (row["h"] > row["fh"] and row["x"] <= wx < row["x"] + row["w"]
                and row["y"] <= wy < row["y"] + row["h"] and wy + 10 < row["bottom"]):
            return True
    return False


def _lamp_heads(surface, cam_x, cam_y, stage_id):
    """The lamps the light pass lights from: visible housings, not floating glow."""
    for i, (tx, ty, radius, colour, kind) in enumerate(_STAGE_LAMPS.get(stage_id, ())):
        if kind.startswith("tower"):
            continue                              # the tower prop carries its own lamps
        wx, wy = tx * T, ty * T
        sx, sy = int(wx - cam_x), int(wy - cam_y)
        if not (-12 < sx < WIDTH + 12 and -12 < sy < HEIGHT + 12):
            continue
        if _under_prop(stage_id, wx, wy):
            continue
        surface.blit(_lamp_head(colour, _lamp_on(kind, i) > 0.5), (sx - 9, sy - 9))


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
    _lamp_heads(surface, cam_x, cam_y, stage_id)
    tint = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
    tint.fill((38, 54, 82, 20))
    surface.blit(tint, (0, 0))
    _snow(surface)
