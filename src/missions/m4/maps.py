"""Split from mission4.py - see __init__.py for the package facade.

Owner module for the Mission 4 runtime map state: MISSION4_MAP (the
currently-bound playable grid), _last_keys, _objective and _radio_marks.
Parts access these as ``_m4_maps.NAME`` (module-attribute style) so a
rebind here is visible everywhere - never ``from missions.m4.maps import
MISSION4_MAP`` (that snapshots the binding).
"""

import math
import time

import pygame

from core.config import (TILE_SIZE)
from core.state import STATE
import game.levels as _levels  # RPE6 P7: level data access

from missions.m4.meta import (
    MAP_W, MAP_H, TILE, M4_SOLID_CHARS, M4_ZONE_DEFS,
    PLAYER_START_TILE, VASILE_START_TILE, STATION_DOOR_TILE,
    STATION_W, STATION_H, STATION_BUILDING,
    STATION_START_TILE, VASILE_ARRIVE_TILE, TRANSMITTER_TILE, LIAISON_TILE, JAMMER_TILE,
)


# ─────────────────────────────────────────────
# Grid authoring helpers (M3 procedural idiom -
# no baked list[str] literals, per repo direction)
# ─────────────────────────────────────────────
def _blank(w, h, fill="g"):
    return [[fill for _ in range(w)] for _ in range(h)]


def _set_tile(g, col, row, tile, w, h):
    if 0 <= col < w and 0 <= row < h:
        g[row][col] = tile


def _paint_tiles(g, x, y, tw, th, tile, w, h):
    for row in range(y, y + th):
        for col in range(x, x + tw):
            _set_tile(g, col, row, tile, w, h)


def _outline_building(g, col, row, bw, bh, interior, w, h, door_tiles=()):
    """Rectangular building perimeter with optional door gaps.

    Mirrors missions.m3.maps._outline_building (values ported, module not
    imported - m3 globals are mission-scoped).
    """
    for yy in range(row, row + bh):
        for xx in range(col, col + bw):
            border = xx in (col, col + bw - 1) or yy in (row, row + bh - 1)
            _set_tile(g, xx, yy, "C" if border else interior, w, h)
    for dx, dy in door_tiles:
        _set_tile(g, col + dx, row + dy, interior, w, h)


# Tile chars the player can stand on. Solid set is M4_SOLID_CHARS;
# everything else in the grammar below is walkable floor or a marker on floor.
# "d" is the sidewalk border of the curfew streets (art-backed t_d_*).
# "F" is an interior ground floor (station foyer) - walkable,
# rendered as a distinct floor tile so interiors read differently from asphalt.
_WALKABLE_TILES = ".adRFDOGJTVENPMXSbwAZ"


def _validate(g, w, h, key_tiles):
    """Import-time map sanity: sealed border, uniform rows, walkable keys.

    MapBuilder.validate() is not used by the M2/M3 procedural style; the
    slice-0 gate instead enforces the three properties those maps actually
    rely on (plan Risks: "Map seams").
    """
    assert all(len(row) == w for row in g), "m4 map row width mismatch"
    for x in range(w):
        assert g[0][x] in M4_SOLID_CHARS and g[h - 1][x] in M4_SOLID_CHARS, \
            "m4 map border not sealed at row 0/{}".format(h - 1)
    for y in range(h):
        assert g[y][0] in M4_SOLID_CHARS and g[y][w - 1] in M4_SOLID_CHARS, \
            "m4 map border not sealed at col 0/{}".format(w - 1)
    for name, (cx, cy) in key_tiles.items():
        assert 0 <= cx < w and 0 <= cy < h, "key tile {} out of bounds".format(name)
        assert g[cy][cx] in _WALKABLE_TILES, \
            "key tile {} lands on solid char {!r}".format(name, g[cy][cx])


# Curfew-street grid (Playtest Polish M3). Rebuilt as a REGULAR, evenly-spaced
# block grid so the map no longer reads as "a ton of unequal black blocks":
# streets are 2 tiles wide, blocks ~4-5, and the old dead top/bottom masses are
# cut through by real cross streets. The boulevard stays the wide E-W artery;
# the station reads as one solid block with a walkable door in its west face.
V_LANES = (3, 4, 9, 10, 15, 16, 21, 22, 27, 28, 33, 34)  # N-S streets (pairs)
H_LANES = (4, 8, 9, 13, 14, 24, 25, 30, 31, 35, 36)       # E-W cross streets
BOULEVARD_ROWS = (18, 19, 20)     # E-W main artery (centre lane = 19)
SIDEWALK_N = 17                   # "d" border above the boulevard
SIDEWALK_S = 21                   # "d" border below the boulevard

# ─────────────────────────────────────────────
# Block registry: every city block is an ACTUAL building footprint - walls,
# roof colour, cornice, lit windows, storefronts on boulevard rows, ground
# entrances onto sidewalks. Facades are derived from this table at draw time
# (see draw._m4_building_blocks); the C field only needs to cover it.
# ─────────────────────────────────────────────
M4_BLOCKS = [
    # id,          x,  y,   w,  h, style,      storeys
    # Registered PER CHUNK: the street grid's building bands are cut by
    # 2-wide walkable alleys, and the old over-wide rects (row_north,
    # deep_s, palace_n, mid_east, blk_r1/s1) stamped facades across those
    # alleys while leaving whole chunks (mid band, row 29) as raw C slabs.
    ("row_n_a",     1,  1,   2,  3, "row",       3),   # rows 1-3 above H_LANE 4
    ("row_n_b",     5,  1,   4,  3, "apartment", 4),
    ("row_n_c",    11,  1,   4,  3, "row",       3),
    ("row_n_d",    17,  1,   4,  3, "apartment", 4),
    ("row_n_e",    23,  1,   4,  3, "row",       3),
    ("row_n_f",    29,  1,   4,  3, "apartment", 4),
    ("row_n_g",    35,  1,   4,  3, "row",       3),
    ("blk_05",      1,  5,   2,  3, "apartment", 4),
    ("blk_07",      5,  5,   4,  3, "row",       3),
    ("blk_11",     11,  5,   4,  3, "apartment", 5),
    ("blk_17",     17,  5,   4,  3, "row",       3),
    ("blk_23",     23,  5,   4,  3, "apartment", 4),
    ("blk_29",     29,  5,   4,  3, "row",       3),
    ("blk_35",     35,  5,   4,  3, "apartment", 4),
    ("blk_05b",     1, 10,   2,  3, "row",       3),
    ("blk_07b",     5, 10,   4,  3, "apartment", 4),
    ("blk_11b",    11, 10,   4,  3, "row",       3),
    ("blk_17b",    17, 10,   4,  3, "apartment", 5),
    ("blk_23b",    23, 10,   4,  3, "row",       3),
    ("blk_29b",    29, 10,   4,  3, "apartment", 4),
    ("blk_35b",    35, 10,   4,  3, "row",       3),
    ("palace_nw",   1, 15,   2,  2, "palace",   4),   # NW civic band, rows 15-16
    ("palace_n",    5, 15,   4,  2, "palace",   4),
    ("mid_11",     11, 15,   4,  2, "apartment", 4),
    ("mid_17",     17, 15,   4,  2, "row",       3),
    ("mid_23",     23, 15,   4,  2, "apartment", 4),
    ("mid_29",     29, 15,   4,  2, "row",       3),   # full band; col 33 alley separates it from the station
    ("blvd_s_1",    1, 22,   2,  2, "row",       3),  # south-of-boulevard row A
    ("blvd_s_2",    5, 22,   4,  2, "apartment", 4),
    ("blvd_s_3",   11, 22,   4,  2, "row",       3),
    ("blvd_s_4",   17, 22,   4,  2, "apartment", 5),
    ("blvd_s_5",   23, 22,   4,  2, "row",       3),
    ("blvd_s_6",   29, 22,   4,  2, "apartment", 4),
    ("blvd_s_7",   35, 22,   4,  2, "row",       3),
    ("blk_r1",      1, 26,   2,  4, "apartment", 4),   # rows 26-29 between H 25/30
    ("blk_r2",      5, 26,   4,  4, "row",       3),
    ("blk_r3",     11, 26,   4,  4, "apartment", 5),
    ("blk_r4",     17, 26,   4,  4, "row",       3),
    ("blk_r5",     23, 26,   4,  4, "apartment", 4),
    ("blk_r6",     29, 26,   4,  4, "row",       3),
    ("blk_r7",     35, 26,   4,  4, "apartment", 4),
    ("blk_s1",      1, 32,   2,  3, "row",       3),   # rows 32-34 between H 31/35
    ("blk_s2",      5, 32,   4,  3, "apartment", 4),
    ("blk_s3",     11, 32,   4,  3, "row",       3),
    ("blk_s4",     17, 32,   4,  3, "apartment", 5),
    ("blk_s5",     23, 32,   4,  3, "row",       3),
    ("blk_s6",     29, 32,   4,  3, "apartment", 4),
    ("blk_s7",     35, 32,   4,  3, "row",       3),
    ("deep_a",      1, 37,   2,  2, "row",       3),   # rows 37-38 below H 36
    ("deep_b",      5, 37,   4,  2, "apartment", 4),
    ("deep_c",     11, 37,   4,  2, "row",       3),
    ("deep_d",     17, 37,   4,  2, "apartment", 4),
    ("deep_e",     23, 37,   4,  2, "row",       3),
    ("deep_f",     29, 37,   4,  2, "apartment", 4),
    ("deep_g",     35, 37,   4,  2, "row",       3),
]

# Radio-station footprint (east): a solid block; door gap on its west face.
# Aligned to the street lattice so it never overlaps a smaller block: the
# col-33 N-S street separates it from the mid_29 band, the row-21 sidewalk
# separates it from the blvd_s row, and H_LANE 14 from blk_35b. It eats the
# col-34 lane pair and the boulevard lanes east of col 33 (the artery visibly
# ends at the west door).
STATION_BLOCK = (34, 14, 5, 7)    # (col,row,w,h) -> cols 34-38, rows 14-20
# Legacy footprint (NW): the player-safehouse shell was removed - the player
# now spawns on the open street between the blocks. Kept so the draw import
# stays valid; nothing is stamped from it anymore.
SAFEHOUSE = (7, 2, 6, 6)
SAFEHOUSE_DOOR = (9, 7)           # legacy, no longer stamped
# Station foyer: carved "F" pocket behind the west door + corridor north into
# the transmitter hall. Keeps the whole station solid-C except this interior.
FOYER = (35, 18, 3, 3)            # cols 35-37, rows 18-20
# Curfew barricades (solid "B") mid-boulevard; sidewalks + cross streets detour.
BOUNCE_COLS = (12, 24)            # barricade columns across the boulevard


def _carve_station_interior(g, w, h):
    """Carve the station's walkable entry pocket out of the solid block.

    A shallow foyer ("F") behind the west door so the door gap opens into a
    real vestibule instead of raw wall. The old north corridor stub is gone:
    it dead-ended into the block face (a door to nowhere on the street map).
    """
    fx, fy, fw, fh = FOYER
    for r in range(fy, fy + fh):
        for c in range(fx, fx + fw):
            _set_tile(g, c, r, "F", w, h)


def _street_grid(w, h):
    """Carve the walkable curfew-street grid into a solid "C" field."""
    g = _blank(w, h, "C")

    # World border (concrete perimeter - keeps the player inside).
    for x in range(w):
        g[0][x] = g[h - 1][x] = "C"
    for y in range(h):
        g[y][0] = g[y][w - 1] = "C"

    # N-S streets (full height) + E-W cross streets (full width): the regular
    # lattice that makes every block a comparable size instead of monoliths.
    for c in V_LANES:
        for r in range(1, h - 1):
            g[r][c] = "."
    for r in H_LANES:
        for c in range(1, w - 1):
            g[r][c] = "."

    # Boulevard (3 lanes) + sidewalks run the full width; the station block
    # is stamped over them below, so the artery visibly ends at the door.
    for c in range(1, w - 1):
        for r in BOULEVARD_ROWS:
            g[r][c] = "."
        g[SIDEWALK_N][c] = "d"
        g[SIDEWALK_S][c] = "d"

    # Painted centre-line on the boulevard (thin procedural overlay, still a
    # walkable asphalt lane - R -> floor t_dot + a procedural dash in draw).
    for c in range(2, w - 2, 3):
        g[19][c] = "R"

    # Curfew cordon: solid barricades across the boulevard. They never sit on
    # a street column, so every block stays reachable by detouring the
    # sidewalks / cross streets (the direct line is blocked, the map is not).
    for bx in BOUNCE_COLS:
        for r in BOULEVARD_ROWS:
            g[r][bx] = "B"

    # Player spawn: directly on the street grid between the blocks (the
    # (9, 4) V+H lane intersection). No safehouse shell is stamped anymore.
    g[PLAYER_START_TILE[1]][PLAYER_START_TILE[0]] = "P"

    # Radio station (east): solid block, carved over the streets it meets, with
    # a walkable door "D" gap in its west face at the boulevard. The adjacent
    # street tile (STATION_DOOR - 1 col, row 19) is < 1 tile away, so the door
    # trigger reads off the end of the boulevard. A shallow foyer vestibule is
    # carved behind the door so the gap opens into a real interior pocket.
    _paint_tiles(g, STATION_BLOCK[0], STATION_BLOCK[1],
                 STATION_BLOCK[2], STATION_BLOCK[3], "C", w, h)
    g[STATION_DOOR_TILE[1]][STATION_DOOR_TILE[0]] = "D"
    _carve_station_interior(g, w, h)

    # Wrecked cars: cover on the boulevard and the lanes south from the
    # safehouse ("H" parks east-west over two tiles, "h" north-south).
    for cx, cy in _STREET_CARS:
        g[cy][cx] = g[cy][cx + 1] = "H"
    for cx, cy in _STREET_CARS_NS:
        g[cy][cx] = g[cy + 1][cx] = "h"

    # IPA patrols (walkable street tiles; world.py spawns them). Guards hold
    # the boulevard checkpoints and the lane down from the safehouse,
    # marksmen cover the long sidewalks into the station cordon.
    for gx, gy in _STREET_GUARDS:
        g[gy][gx] = "E"
    for mx, my in _STREET_MARKSMEN:
        g[my][mx] = "M"
    return g


# Car hulks (left/top tile) and patrol tiles on the curfew street.
_STREET_CARS = ((6, 18), (18, 20), (29, 18), (15, 13), (27, 8))
_STREET_CARS_NS = ((9, 10), (22, 26), (33, 22))
_STREET_GUARDS = ((11, 19), (20, 19), (27, 19), (9, 14), (31, 20))
_STREET_MARKSMEN = ((17, SIDEWALK_N), (22, SIDEWALK_S), (30, SIDEWALK_N))


def _generate_m4_map():
    """Curfew-street map (40x40): NW blocks, boulevard mid, station E.

    Tile grammar: C building block (solid), B barricade (solid), "." asphalt,
    "d" sidewalk, "R" lane paint (overlay on asphalt), "D" door gap (walkable),
    "F" interior floor (station foyer), "L" corridor floor,
    "P" player spawn (open street between the blocks), "H"/"h" car hulk
    (solid), "E" guard spawn, "M" marksman spawn (both on street floor).
    """
    w, h = MAP_W, MAP_H
    g = _street_grid(w, h)

    _validate(g, w, h, {
        "PLAYER_START_TILE": PLAYER_START_TILE,
        "VASILE_START_TILE": VASILE_START_TILE,
        "STATION_DOOR_TILE": STATION_DOOR_TILE,
    })
    return g


# Station barricade sites: door sites "b" take planks or plate, window
# sites "w" take boards. "W" is the weak east wall wave 4 blows open.
STATION_DOOR_SITES = ((17, 21), (18, 21), (6, 16), (29, 17), (12, 4))
STATION_WINDOW_SITES = ((6, 7), (6, 12), (29, 7), (13, 21), (22, 21), (23, 4))
STATION_BREACH_TILES = ((29, 11), (29, 12))
# Loyalist insertion points round the street ring (name -> tile).
STATION_SPAWNS = {"NW": (2, 2), "N": (18, 1), "NE": (33, 2), "W": (2, 14), "E": (33, 14),
                  "SW": (2, 25), "S": (13, 26), "SE": (33, 25)}
# Cover on the forecourt and the ring: car hulks and jersey barriers.
_STATION_CARS = ((8, 24), (25, 24), (31, 2))
_STATION_CARS_NS = ((2, 6), (33, 18), (3, 19))
_STATION_JERSEY = ((13, 24), (14, 24), (22, 24), (23, 24), (31, 10), (4, 10))


def _generate_station_map():
    """36x28 radio station with its forecourt and street ring.

    The building (cols 6-29, rows 4-21) has seven rooms: the transmitter
    hall (north middle) with the rack on its north wall, the entry hall
    (south middle) behind the main door, a cross corridor between them,
    and four wing rooms. Exterior openings are barricade sites ("b" doors,
    "w" windows); the corridor's east end is the weak wall "W". The street
    ring round the building carries the loyalist insertion points "Z" and
    the APC lane "A" on the south forecourt.
    """
    from collections import deque

    w, h = STATION_W, STATION_H
    g = _blank(w, h, ".")
    for x in range(w):
        g[0][x] = g[h - 1][x] = "C"
    for y in range(h):
        g[y][0] = g[y][w - 1] = "C"

    def paint(x, y, width, height, tile):
        _paint_tiles(g, x, y, width, height, tile, w, h)

    bx, by, bw, bh = STATION_BUILDING
    paint(bx - 1, by - 1, bw + 2, bh + 2, "d")    # sidewalk ring hugging the building
    paint(bx, by, bw, bh, "C")
    paint(7, 5, 3, 5, "O")          # NW room (archive)
    paint(11, 5, 14, 5, "O")        # transmitter hall
    paint(26, 5, 3, 5, "O")         # NE room (engineering)
    paint(7, 11, 22, 2, "L")        # cross corridor
    paint(7, 14, 3, 7, "F")         # SW room (offices)
    paint(11, 14, 14, 7, "F")       # entry hall
    paint(26, 14, 3, 7, "F")        # SE room (studio)
    for col in (8, 14, 15, 20, 21, 27):
        g[10][col] = "D"
    for col in (8, 17, 18, 27):
        g[13][col] = "D"
    for col, row in ((13, 16), (22, 16)):
        g[row][col] = "C"           # entry-hall pillars
    for col, row in STATION_DOOR_SITES:
        g[row][col] = "b"
    for col, row in STATION_WINDOW_SITES:
        g[row][col] = "w"
    for col, row in STATION_BREACH_TILES:
        g[row][col] = "W"
    paint(8, 25, 20, 1, "A")        # the APC lane across the forecourt
    for cx, cy in _STATION_CARS:
        g[cy][cx] = g[cy][cx + 1] = "H"
    for cx, cy in _STATION_CARS_NS:
        g[cy][cx] = g[cy + 1][cx] = "h"
    for cx, cy in _STATION_JERSEY:
        g[cy][cx] = "B"

    keys = {
        "STATION_START_TILE": STATION_START_TILE,
        "VASILE_ARRIVE_TILE": VASILE_ARRIVE_TILE,
        "TRANSMITTER_TILE": TRANSMITTER_TILE,
        "JAMMER_TILE": JAMMER_TILE,
        "LIAISON_TILE": LIAISON_TILE,
    }
    keys.update({"Z_" + k: v for k, v in STATION_SPAWNS.items()})
    # Validate before stamping markers: an objective must not silently
    # punch a walkable hole into a misplaced wall.
    _validate(g, w, h, keys)

    for (x, y), tile in ((STATION_START_TILE, "P"), (TRANSMITTER_TILE, "T"),
                         (JAMMER_TILE, "J"), (LIAISON_TILE, "N")):
        g[y][x] = tile
    for x, y in STATION_SPAWNS.values():
        g[y][x] = "Z"

    # Every floor tile is reachable from the forecourt (the weak wall counts
    # as solid: the rooms connect without it).
    start = STATION_START_TILE
    reached = {start}
    pending = deque([start])
    while pending:
        x, y = pending.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in reached:
                continue
            if g[ny][nx] in M4_SOLID_CHARS:
                continue
            reached.add((nx, ny))
            pending.append((nx, ny))
    walkable = {(x, y) for y in range(h) for x in range(w) if g[y][x] not in M4_SOLID_CHARS}
    disconnected = walkable - reached
    if disconnected:
        raise ValueError("m4 station has disconnected floor: {}".format(sorted(disconnected)))
    return ["".join(row) for row in g]


MISSION4_STREET_MAP = _levels.grid("m4.street", _generate_m4_map())
MISSION4_STATION_MAP = _levels.grid("m4.station", _generate_station_map())
MISSION4_MAP = MISSION4_STREET_MAP


def _live_map_dims():
    """(width, height) of the currently-bound MISSION4_MAP, in tiles.

    The street map is 40x40 but the station is 36x28 - render
    loops and camera clamps must derive bounds from this, never from
    MAP_W/MAP_H (m3.maps._live_map_dims lesson).
    """
    grid = MISSION4_MAP
    h = len(grid)
    w = len(grid[0]) if h else 0
    return w, h


# World-space (px) rects for the named curfew-street zones, derived from
# the raw meta.M4_ZONE_DEFS tile tuples (m2.meta.ZONE_WORLD_RECTS idiom).
# Keyed by zone name; used by the ambient/story-beat driver in flow.py.
M4_ZONE_WORLD_RECTS = {
    name: pygame.Rect(l * TILE_SIZE, t * TILE_SIZE, wd * TILE_SIZE, ht * TILE_SIZE)
    for name, (l, t, wd, ht) in (
        (k, v["tile_rect"]) for k, v in M4_ZONE_DEFS.items()
    )
}


def zone_at(world_pos):
    """Return the authored zone name for a world-space point, or None."""
    x, y = world_pos
    for name, rect in M4_ZONE_WORLD_RECTS.items():
        if rect.collidepoint(x, y):
            return name
    return None


def zone_label(name):
    return M4_ZONE_DEFS.get(name, {}).get("label", name)


_last_keys = None
_objective = "Get Vasile and the cache to the radio station."
_radio_marks = set()
