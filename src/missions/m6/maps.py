"""Authored map layer for Mission 6 - three distinct playable spaces.

Runtime contract is unchanged from the rest of the campaign: ``MISSION6_MAP``
is a ``list[str]`` of tiles.  This module owns the *binding* (like
``missions/m5/maps.py``), so consumers must read it through
``import .maps as _maps`` and never snapshot it with ``from ... import``.

Maps:
  M6_CUSTOMS_MAP   30x20  abandoned customs post + frozen car queue
  M6_NOMAN_MAP     40x18  floodlit no-man's-land between two gates
  M6_RAIL_MAP      46x26  freight yard, platform and waiting train
"""
from collections import deque

from core.mapbuilder import MapBuilder
from .meta import (
    M6_SOLID_CHARS, STAGES, STAGE_ANCHORS, STAGE_SPAWNS,
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
)


# ── layout primitives ────────────────────────────────────────────────────
def _customs():
    b = MapBuilder(30, 20, "g")
    b.border_rect(0, 0, 30, 20, "C", floor="g")
    # Building shell (cols 7..22, rows 3..11), interior floor ".".
    b.rect(7, 3, 16, 9, ".")
    b.border_rect(7, 3, 16, 9, "C", floor=".")
    b.set(14, 11, "D")
    b.set(15, 11, "D")       # south doors into the yard
    b.set(16, 3, "D")        # north door to the crossing
    b.set(16, 0, "D")        # the north gate itself (map exit)
    # Interior offices: west file room / east processing hall.
    b.v_wall(14, 4, 7, "C", doors=(3,))
    b.h_wall(7, 8, 7, "C", doors=(3,))
    b.rect(8, 4, 4, 1, "B")      # stamp counter
    b.rect(8, 10, 3, 1, "B")     # waiting bench
    b.rect(18, 4, 1, 3, "B")     # file cabinets (gap below keeps a path)
    b.rect(19, 8, 3, 1, "B")     # terminal desk
    # Frozen queue of cars in the west yard - families who didn't make it.
    for x, y in ((2, 12), (5, 14), (2, 16), (8, 13)):
        b.rect(x, y, 2, 1, "B")
    # Cover in the yard.
    b.rect(24, 12, 2, 1, "B")
    b.rect(9, 16, 2, 1, "B")
    b.rect(24, 5, 1, 1, "B")
    return b


def _noman():
    b = MapBuilder(40, 18, "g")
    b.border_rect(0, 0, 40, 18, "C", floor="g")
    b.set(20, 17, "D")       # south gate (entry)
    b.set(20, 0, "D")        # north gate (exit to the rail yard)
    # Staging aprons.
    b.rect(1, 15, 38, 2, ".")
    b.rect(1, 1, 38, 2, "L")
    # Razor-wire chicanes: short solid runs with deliberate gaps.
    b.v_wall(7, 4, 5, "W")
    b.v_wall(12, 9, 5, "W")
    b.v_wall(20, 4, 3, "W")
    b.v_wall(27, 10, 5, "W")
    b.v_wall(32, 5, 4, "W")
    b.h_wall(13, 4, 5, "W")
    b.h_wall(23, 12, 6, "W")
    b.h_wall(29, 8, 5, "W")
    # Concrete barriers (cover on the crossing).
    for x, y in ((15, 7), (24, 7), (9, 11), (35, 14)):
        b.rect(x, y, 2, 1, "B")
    # Floodlight tower bases (lights are data in stealth.py, drawn by decor).
    for x, y in ((8, 4), (31, 4), (8, 10), (31, 10)):
        b.rect(x, y, 1, 2, "B")
    return b


def _rail():
    b = MapBuilder(46, 26, "g")
    b.border_rect(0, 0, 46, 26, "C", floor="g")
    # Concrete platform + waiting passenger train along the north edge.
    b.rect(1, 1, 44, 6, "L")
    b.rect(6, 1, 36, 3, "W")
    b.rect(6, 6, 36, 1, "Y")
    # Perimeter fences with gaps.
    b.v_wall(1, 8, 6, "W")
    b.v_wall(1, 18, 5, "W")
    b.v_wall(44, 8, 7, "W")
    b.v_wall(44, 18, 6, "W")
    # Freight boxcars (Volkov's is the (20,9) car).
    for x, y, w, h in ((4, 10, 12, 2), (20, 9, 10, 2), (34, 12, 8, 2),
                       (6, 17, 12, 2), (24, 18, 10, 2), (36, 20, 6, 2),
                       (4, 21, 8, 2)):
        b.rect(x, y, w, h, "B")
    # Signal tower / office block.
    b.rect(39, 7, 4, 4, "B")
    # Yard clutter.
    b.rect(17, 14, 2, 2, "B")
    b.rect(30, 22, 2, 1, "B")
    b.rect(13, 8, 2, 1, "B")
    return b


_BUILDERS = {
    STAGE_CUSTOMS: _customs,
    STAGE_NOMAN: _noman,
    STAGE_RAIL: _rail,
    STAGE_BOXCAR: _rail,
    STAGE_TRAIN: _rail,
}

_SPAWNS = {
    STAGE_CUSTOMS: [("P", 14, 17), ("E", 25, 16), ("E", 20, 5)],
    STAGE_NOMAN: [("P", 20, 16), ("E", 4, 6), ("E", 34, 12), ("E", 20, 2)],
    STAGE_RAIL: [("P", 22, 24), ("V", 25, 11), ("E", 12, 15), ("E", 32, 15),
                 ("E", 38, 6), ("E", 16, 7), ("E", 35, 18)],
    STAGE_BOXCAR: [("P", 22, 24)],
    STAGE_TRAIN: [("P", 22, 24)],
}


def _bake_stage(stage):
    builder = _BUILDERS[stage]()
    structure = builder.to_strings()
    baked = builder.with_spawns(_SPAWNS[stage]).to_strings()
    return structure, baked


# Authored, already-baked maps.  ``bind_stage`` only rebinds the public names.
_CUSTOMS_STRUCTURE, M6_CUSTOMS_MAP = _bake_stage(STAGE_CUSTOMS)
_NOMAN_STRUCTURE, M6_NOMAN_MAP = _bake_stage(STAGE_NOMAN)
_RAIL_STRUCTURE, M6_RAIL_MAP = _bake_stage(STAGE_RAIL)

_STRUCTURES = {
    STAGE_CUSTOMS: _CUSTOMS_STRUCTURE,
    STAGE_NOMAN: _NOMAN_STRUCTURE,
    STAGE_RAIL: _RAIL_STRUCTURE,
    STAGE_BOXCAR: _RAIL_STRUCTURE,
    STAGE_TRAIN: _RAIL_STRUCTURE,
}
_GRIDS = {
    STAGE_CUSTOMS: M6_CUSTOMS_MAP,
    STAGE_NOMAN: M6_NOMAN_MAP,
    STAGE_RAIL: M6_RAIL_MAP,
    STAGE_BOXCAR: M6_RAIL_MAP,
    STAGE_TRAIN: M6_RAIL_MAP,
}

# Bound runtime map (owner state; read through this module only).
MISSION6_MAP = M6_CUSTOMS_MAP
M6_STRUCTURE_MAP = _CUSTOMS_STRUCTURE
_objective = "Search the abandoned crossing, then take the north gate."
_radio_marks = set()
_last_keys = None


def grid_for(stage):
    """Authored baked grid for a stage (spawn markers included)."""
    return _GRIDS.get(stage, M6_CUSTOMS_MAP)


def structure_for(stage):
    """Collision/visual-only grid for a stage (no spawn markers)."""
    return _STRUCTURES.get(stage, _CUSTOMS_STRUCTURE)


def bind_stage(stage):
    """Point ``MISSION6_MAP``/``M6_STRUCTURE_MAP`` at a stage's baked grid."""
    global MISSION6_MAP, M6_STRUCTURE_MAP
    grid = _GRIDS.get(stage, M6_CUSTOMS_MAP)
    MISSION6_MAP = grid
    M6_STRUCTURE_MAP = _STRUCTURES.get(stage, _CUSTOMS_STRUCTURE)
    return grid


def _live_map_dims():
    """(w, h) in tiles of the currently-bound MISSION6_MAP."""
    grid = MISSION6_MAP
    h = len(grid)
    return (len(grid[0]) if h else 0), h


def _reachable(grid, start, blocked=M6_SOLID_CHARS):
    h, w = len(grid), len(grid[0])
    seen = {start}
    todo = deque([start])
    while todo:
        x, y = todo.popleft()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if not (0 <= nx < w and 0 <= ny < h) or (nx, ny) in seen:
                continue
            if grid[ny][nx] in blocked:
                continue
            seen.add((nx, ny))
            todo.append((nx, ny))
    return seen


def _stage_errors(stage):
    errors = []
    builder = _BUILDERS[stage]()
    errors.extend("%s: %s" % (stage, e) for e in builder.validate())
    structure, baked = _bake_stage(stage)
    start = STAGE_SPAWNS[stage]
    if structure[start[1]][start[0]] in M6_SOLID_CHARS:
        errors.append("%s: spawn %r is solid" % (stage, start))
    for label, (cx, cy) in (("anchor", STAGE_ANCHORS[stage]),):
        if not (0 <= cx < len(structure[0]) and 0 <= cy < len(structure)):
            errors.append("%s: %s out of bounds" % (stage, label))
        elif structure[cy][cx] in M6_SOLID_CHARS:
            errors.append("%s: %s %r is solid" % (stage, label, (cx, cy)))
    reached = _reachable(structure, start)
    loose = [(x, y) for y, row in enumerate(structure)
             for x, ch in enumerate(row)
             if ch not in M6_SOLID_CHARS and (x, y) not in reached]
    if loose:
        errors.append("%s: disconnected floor %r" % (stage, loose[:8]))
    for ch, cx, cy in _SPAWNS[stage]:
        if baked[cy][cx] != ch:
            errors.append("%s: spawn %s missing at %r" % (stage, ch, (cx, cy)))
    return errors


def _validate():
    """All-map validation -> [] (sealed, rectangular, connected, spawns)."""
    errors = []
    for stage in STAGES:
        errors.extend(_stage_errors(stage))
    return errors
