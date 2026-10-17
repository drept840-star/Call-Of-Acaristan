"""Mission 5 - part module. See __init__.py for the package facade.

Owner module for the Mission 5 runtime map state: MISSION5_MAP (the
currently-bound playable grid), _last_keys, _objective, _radio_marks.
Parts access these as ``_m5_maps.NAME`` - never ``from missions.m5.maps
import MISSION5_MAP`` (that snapshots the binding).

Four procedural maps in the M4 tile grammar (see meta.py):
  MISSION5_HQ_MAP       30x16  Guard HQ (old KRAP depot) - walking sim
  MISSION5_QUARTER_MAP  40x30  Lower Quarter night streets
  MISSION5_PRINT_MAP    26x20  MAG print works (presses, Maru's office)
  MISSION5_TUNNEL_MAP   48x12  basement tunnel to the river gate
Each is validated at import: sealed border, uniform rows, key tiles on
walkable floor, and every walkable cell connected to the start.
"""

from collections import deque

import game.levels as _levels  # RPE6 P7: level data access

from missions.m5.meta import (
    M5_SOLID_CHARS, M5_WALKABLE_TILES,
    QUARTER_W, QUARTER_H, QUARTER_START_TILE, PRINTWORKS_DOOR_TILE,
    QUARTER_TRAM_TILES, QUARTER_CHECKPOINTS, QUARTER_GUARDS,
    PRINT_W, PRINT_H, PRINT_START_TILE, MARU_TILE, BASEMENT_STAIR_TILE,
    RAID_INSERTION_TILES,
    TUNNEL_W, TUNNEL_H, TUNNEL_START_TILE, TUNNEL_MARU_START_TILE,
    RIVER_GATE_TILE, TUNNEL_PURSUIT_TILES,
    HQ_W, HQ_H, HQ_START_TILE, VASILE_TILE, VASILE_DESK_FRONT_TILE, HQ_NPCS,
)


# ─────────────────────────────────────────────
# Grid helpers (M4 procedural idiom, ported - not imported)
# ─────────────────────────────────────────────
def _blank(w, h, fill="C"):
    return [[fill for _ in range(w)] for _ in range(h)]


def _paint(g, x, y, tw, th, tile):
    h = len(g)
    w = len(g[0])
    for row in range(y, y + th):
        for col in range(x, x + tw):
            if 0 <= col < w and 0 <= row < h:
                g[row][col] = tile


def _seal_border(g):
    h = len(g)
    w = len(g[0])
    for x in range(w):
        g[0][x] = "C"
        g[h - 1][x] = "C"
    for y in range(h):
        g[y][0] = "C"
        g[y][w - 1] = "C"


def _validate(g, name, key_tiles, start):
    """Sealed border, uniform rows, walkable keys, full connectivity."""
    h = len(g)
    w = len(g[0])
    assert all(len(row) == w for row in g), name + ": row width mismatch"
    for x in range(w):
        assert g[0][x] in M5_SOLID_CHARS and g[h - 1][x] in M5_SOLID_CHARS, \
            name + ": border not sealed (rows)"
    for y in range(h):
        assert g[y][0] in M5_SOLID_CHARS and g[y][w - 1] in M5_SOLID_CHARS, \
            name + ": border not sealed (cols)"
    for key, (cx, cy) in key_tiles.items():
        assert 0 < cx < w - 1 and 0 < cy < h - 1, \
            "{}: key {} out of bounds".format(name, key)
        assert g[cy][cx] in M5_WALKABLE_TILES, \
            "{}: key {} on solid {!r}".format(name, key, g[cy][cx])
    reached = {start}
    todo = deque([start])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (nx, ny) in reached or not (0 <= nx < w and 0 <= ny < h):
                continue
            if g[ny][nx] in M5_SOLID_CHARS:
                continue
            reached.add((nx, ny))
            todo.append((nx, ny))
    loose = [(x, y) for y in range(h) for x in range(w)
             if g[y][x] not in M5_SOLID_CHARS and (x, y) not in reached]
    if loose:
        raise ValueError("{}: disconnected floor {}".format(name, loose[:8]))


def _stamp(g, marks):
    for (x, y), ch in marks:
        g[y][x] = ch


def _bake(g):
    return ["".join(row) for row in g]


# ─────────────────────────────────────────────
# Guard HQ (30x16) - walking sim, no spawns but P
# ─────────────────────────────────────────────
def _generate_hq_map():
    w, h = HQ_W, HQ_H
    g = _blank(w, h, "C")
    _paint(g, 1, 9, 8, 6, "F")       # locker hall (entry, south-west)
    _paint(g, 9, 10, 15, 3, "L")     # main corridor
    _paint(g, 10, 2, 9, 6, "O")      # briefing room (north)
    _paint(g, 20, 2, 8, 6, "O")      # Commander's office (north-east)
    _paint(g, 24, 10, 4, 4, "O")     # armory (east)
    _paint(g, 13, 8, 2, 2, "D")      # corridor -> briefing
    _paint(g, 22, 8, 2, 2, "D")      # corridor -> office
    for x in (11, 13, 15, 17):       # briefing benches
        g[4][x] = "B"
    _paint(g, 23, 3, 3, 1, "B")      # Vasile's desk (the flag stands on it)
    _paint(g, 26, 13, 1, 1, "B")     # armory rack
    _seal_border(g)
    keys = {"start": HQ_START_TILE, "vasile": VASILE_TILE,
            "desk_front": VASILE_DESK_FRONT_TILE}
    for i, (c, r, _n, _a, _l) in enumerate(HQ_NPCS):
        keys["npc%d" % i] = (c, r)
    _validate(g, "m5 hq", keys, HQ_START_TILE)
    _stamp(g, [(HQ_START_TILE, "P")])
    return _bake(g)


# ─────────────────────────────────────────────
# Lower Quarter (40x30)
# ─────────────────────────────────────────────
# Streets carved out of a solid block field. Main avenue rows 13-17
# (sidewalk 13/17, asphalt 14-16) runs depot (west) -> print works (east).
_Q_V_LANES = ((3, 4), (12, 13), (22, 23), (31, 32))
_Q_H_LANES = ((4, 5), (24, 25))
_Q_AVENUE = (14, 15, 16)


def _generate_quarter_map():
    w, h = QUARTER_W, QUARTER_H
    g = _blank(w, h, "C")
    # Cross streets (asphalt) with sidewalk edges.
    for a, b in _Q_V_LANES:
        _paint(g, a - 1, 2, b - a + 3, h - 4, "d")
        _paint(g, a, 2, b - a + 1, h - 4, ".")
    for a, b in _Q_H_LANES:
        _paint(g, 2, a - 1, 31, b - a + 3, "d")
        _paint(g, 2, a, 31, b - a + 1, ".")
        for va, vb in _Q_V_LANES:          # keep junctions asphalt
            _paint(g, va, a, vb - va + 1, b - a + 1, ".")
    # Main avenue, depot yard to the print-works door.
    _paint(g, 1, 13, 33, 5, "d")
    _paint(g, 1, 14, 33, 3, ".")
    for va, vb in _Q_V_LANES:
        _paint(g, va, 13, vb - va + 1, 5, ".")
    # Depot yard (west, the start) - foyer floor.
    _paint(g, 1, 12, 3, 7, "F")
    # Checkpoints: barricade across the avenue leaving one gap row.
    for cp in QUARTER_CHECKPOINTS:
        for row in _Q_AVENUE:
            if row != cp["gap_row"]:
                g[row][cp["col"]] = "B"
    # Burning tram wreck.
    for x, y in QUARTER_TRAM_TILES:
        g[y][x] = "B"
    # Print-works block (solid) with the door gap in its west face.
    _paint(g, 34, 10, 5, 11, "C")
    dx, dy = PRINTWORKS_DOOR_TILE
    g[dy][dx] = "D"
    _seal_border(g)
    keys = {"start": QUARTER_START_TILE, "door": PRINTWORKS_DOOR_TILE}
    for i, (c, r, _k, _p) in enumerate(QUARTER_GUARDS):
        keys["guard%d" % i] = (c, r)
    _validate(g, "m5 quarter", keys, QUARTER_START_TILE)
    marks = [(QUARTER_START_TILE, "P")]
    marks += [((c, r), "M" if k == "marksman" else "E")
              for c, r, k, _p in QUARTER_GUARDS]
    _stamp(g, marks)
    return _bake(g)


# ─────────────────────────────────────────────
# Print works (26x20)
# ─────────────────────────────────────────────
def _generate_print_map():
    w, h = PRINT_W, PRINT_H
    g = _blank(w, h, "C")
    _paint(g, 1, 15, 8, 4, "F")      # front shop (entry, south-west)
    _paint(g, 1, 7, 15, 7, "O")      # press hall (west/centre)
    _paint(g, 17, 2, 7, 6, "O")      # Maru's back office (north-east)
    _paint(g, 1, 2, 14, 4, "O")      # paper store (north-west)
    _paint(g, 17, 9, 8, 4, "O")      # loading bay (east)
    _paint(g, 10, 15, 14, 4, "L")    # basement corridor (south)
    # Connections (2-wide door gaps).
    _paint(g, 3, 14, 2, 1, "D")      # shop -> press hall
    _paint(g, 6, 6, 2, 1, "D")       # press hall -> paper store
    _paint(g, 15, 3, 2, 1, "D")      # paper store -> office
    _paint(g, 16, 10, 1, 2, "D")     # press hall -> loading bay
    _paint(g, 19, 8, 2, 1, "D")      # loading bay -> office
    _paint(g, 9, 16, 1, 2, "D")      # shop -> corridor
    _paint(g, 20, 13, 2, 2, "D")     # loading bay -> corridor
    _paint(g, 12, 14, 2, 1, "D")     # press hall -> corridor
    # Presses (solid cover islands) and paper stacks.
    for x, y in ((3, 8), (7, 8), (11, 8), (3, 11), (7, 11), (11, 11)):
        _paint(g, x, y, 2, 1, "H")
    for x, y in ((3, 3), (8, 3), (12, 4)):
        _paint(g, x, y, 1, 2, "B")
    _paint(g, 19, 5, 2, 1, "B")      # office desk
    _paint(g, 15, 17, 2, 1, "B")     # crates in the corridor
    # Raid insertion doors punched into the outer wall.
    for x, y in RAID_INSERTION_TILES:
        if x == 0 or x == w - 1 or y == 0 or y == h - 1:
            continue
        g[y][x] = "I"
    sx, sy = BASEMENT_STAIR_TILE
    g[sy][sx] = "S"
    _seal_border(g)
    keys = {"start": PRINT_START_TILE, "maru": MARU_TILE,
            "stair": BASEMENT_STAIR_TILE}
    for i, t in enumerate(RAID_INSERTION_TILES):
        keys["insert%d" % i] = t
    _validate(g, "m5 printworks", keys, PRINT_START_TILE)
    _stamp(g, [(PRINT_START_TILE, "P"), (MARU_TILE, "N")])
    return _bake(g)


# ─────────────────────────────────────────────
# Tunnel (48x12)
# ─────────────────────────────────────────────
def _generate_tunnel_map():
    w, h = TUNNEL_W, TUNNEL_H
    g = _blank(w, h, "C")
    _paint(g, 1, 4, 10, 4, "L")      # basement landing
    _paint(g, 10, 2, 4, 8, "L")      # first bend (wide)
    _paint(g, 13, 2, 12, 3, "L")     # upper run
    _paint(g, 13, 7, 12, 3, "L")     # lower run (parallel - flanking)
    _paint(g, 24, 2, 4, 8, "L")      # junction
    _paint(g, 27, 4, 12, 4, "W")     # flooded section (slow, walkable)
    _paint(g, 38, 3, 9, 6, "L")      # river chamber
    # Pillars / debris (cover, never sealing).
    for x, y in ((6, 4), (17, 3), (20, 8), (31, 5), (35, 6), (41, 4), (41, 7)):
        g[y][x] = "B"
    _seal_border(g)
    keys = {"start": TUNNEL_START_TILE, "maru": TUNNEL_MARU_START_TILE,
            "gate": RIVER_GATE_TILE}
    for i, t in enumerate(TUNNEL_PURSUIT_TILES):
        keys["pursuit%d" % i] = t
    _validate(g, "m5 tunnel", keys, TUNNEL_START_TILE)
    _stamp(g, [(TUNNEL_START_TILE, "P"), (TUNNEL_MARU_START_TILE, "N"),
               (RIVER_GATE_TILE, "G")])
    return _bake(g)


MISSION5_HQ_MAP = _levels.grid("m5.hq", _generate_hq_map())
MISSION5_QUARTER_MAP = _levels.grid("m5.quarter", _generate_quarter_map())
MISSION5_PRINT_MAP = _levels.grid("m5.print", _generate_print_map())
MISSION5_TUNNEL_MAP = _levels.grid("m5.tunnel", _generate_tunnel_map())
MISSION5_MAP = MISSION5_HQ_MAP


def _live_map_dims():
    """(w, h) in tiles of the currently-bound MISSION5_MAP."""
    grid = MISSION5_MAP
    h = len(grid)
    return (len(grid[0]) if h else 0), h


_last_keys = None
_objective = "Report to Vasile."
_radio_marks = set()
