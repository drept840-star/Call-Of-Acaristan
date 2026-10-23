"""Authored map layer for Mission 6 - three distinct playable spaces.

Runtime contract is unchanged from the rest of the campaign: ``MISSION6_MAP``
is a ``list[str]`` of tiles.  This module owns the *binding* (like
``missions/m5/maps.py``), so consumers must read it through
``import .maps as _maps`` and never snapshot it with ``from ... import``.

Maps (combat arenas; props are authored by kind in ``_PROP_LAYOUT``):
  M6_CUSTOMS_MAP   30x20  customs post, inspection yard, fuel tanker
  M6_NOMAN_MAP     40x18  floodlit strip: trench line, wrecks, Guard nests
  M6_RAIL_MAP      46x26  freight yard lanes, platform and waiting train
"""
from collections import deque

from core.mapbuilder import MapBuilder
from .meta import (
    M6_SOLID_CHARS, STAGES, STAGE_ANCHORS, STAGE_SPAWNS,
    STAGE_CUSTOMS, STAGE_NOMAN, STAGE_RAIL, STAGE_BOXCAR, STAGE_TRAIN,
)


# ── prop layout ──────────────────────────────────────────────────────────
# Every prop is authored with its kind: (kind, col, row, w, h).  The builder
# stamps the footprint solid ("B"); ``decor`` paints the kind and ``combat``
# owns the ones that can blow up.
_PROP_LAYOUT = {
    STAGE_CUSTOMS: (
        # north apron: the gate, a parked Guard truck, stores
        ("truck", 17, 1, 3, 1), ("jersey", 11, 2, 2, 1),
        ("barrels", 3, 1, 2, 1), ("crates", 25, 1, 2, 2),
        # side lanes around the post
        ("container", 2, 5, 2, 4), ("car_v", 25, 5, 1, 2),
        ("crates", 26, 8, 2, 2),
        # inside: processing hall (west) and file office (east)
        ("counter", 8, 6, 4, 1), ("cabinet", 13, 9, 1, 2),
        ("terminal", 18, 6, 3, 1), ("cabinet", 22, 8, 1, 2),
        ("crate", 17, 10, 1, 1),
        # inspection yard: booths, the frozen queue, the fuel tanker
        ("booth", 9, 14, 2, 2), ("booth", 19, 14, 2, 2),
        ("tanker", 1, 12, 5, 3), ("car", 24, 13, 2, 1),
        ("car", 26, 16, 2, 1), ("wreck", 3, 17, 2, 1),
        ("jersey", 13, 16, 2, 1), ("jersey", 16, 16, 2, 1),
        ("sandbag", 14, 13, 2, 1),
    ),
    STAGE_NOMAN: (
        # floodlight towers (lights are data in stealth.py)
        ("tower", 8, 4, 1, 2), ("tower", 31, 4, 1, 2),
        ("tower", 8, 10, 1, 2), ("tower", 31, 10, 1, 2),
        # south trench line: the player's first cover
        ("sandbag", 3, 13, 4, 1), ("sandbag", 11, 13, 3, 1),
        ("sandbag", 17, 13, 2, 1), ("sandbag", 22, 13, 2, 1),
        ("sandbag", 27, 13, 3, 1), ("sandbag", 34, 13, 3, 1),
        # the middle of the strip: a burnt truck, wrecks and barriers
        ("truck_burnt", 16, 8, 3, 1), ("wreck", 23, 9, 2, 1),
        ("jersey", 11, 8, 2, 1), ("jersey", 27, 8, 2, 1),
        ("hedgehog", 5, 7, 1, 1), ("hedgehog", 14, 10, 1, 1),
        ("hedgehog", 25, 11, 1, 1), ("hedgehog", 35, 7, 1, 1),
        ("hedgehog", 13, 5, 1, 1), ("hedgehog", 26, 5, 1, 1),
        ("hedgehog", 4, 11, 1, 1), ("hedgehog", 36, 11, 1, 1),
        # Guard line in front of the north gate
        ("sandbag", 16, 4, 3, 1), ("sandbag", 22, 4, 3, 1),
        ("booth", 12, 1, 2, 2), ("booth", 26, 1, 2, 2),
        ("barrels", 3, 1, 2, 1), ("crates", 35, 1, 2, 2),
    ),
    STAGE_RAIL: (
        # freight cars (Volkov's is the (20,9) car) and containers
        ("boxcar", 4, 10, 10, 2), ("boxcar", 20, 9, 10, 2),
        ("boxcar", 34, 12, 8, 2), ("boxcar", 6, 17, 11, 2),
        ("boxcar", 24, 18, 10, 2), ("container", 36, 20, 5, 2),
        ("container", 4, 21, 5, 2),
        ("shack", 39, 7, 4, 4),
        # yard cover
        ("crates", 17, 14, 2, 2), ("barrels", 13, 7, 2, 1),
        ("barrels", 30, 22, 2, 1), ("jersey", 22, 14, 2, 1),
        ("jersey", 28, 15, 2, 1), ("sandbag", 11, 13, 3, 1),
        ("coil", 33, 16, 1, 1), ("coil", 19, 21, 1, 1),
        ("crates", 11, 20, 2, 2),
        # platform stores
        ("barrels", 16, 4, 2, 1), ("crates", 30, 4, 2, 2),
    ),
}
_PROP_LAYOUT[STAGE_BOXCAR] = _PROP_LAYOUT[STAGE_RAIL]
_PROP_LAYOUT[STAGE_TRAIN] = _PROP_LAYOUT[STAGE_RAIL]


def props_for(stage):
    """Authored props of a stage: ((kind, col, row, w, h), ...)."""
    return _PROP_LAYOUT.get(stage, ())


def _stamp_props(b, stage):
    for _kind, x, y, w, h in _PROP_LAYOUT[stage]:
        b.rect(x, y, w, h, "B")
    return b


# ── layout primitives ────────────────────────────────────────────────────
def _customs():
    b = MapBuilder(30, 20, "g")
    b.border_rect(0, 0, 30, 20, "C", floor="g")
    b.rect(1, 1, 28, 3, "L")         # concrete apron at the north gate
    b.set(15, 0, "D")                # the north gate itself (map exit)
    # The post (cols 6..23, rows 4..11): hall west, file office east.
    b.rect(6, 4, 18, 8, ".")
    b.border_rect(6, 4, 18, 8, "C", floor=".")
    for col, row in ((10, 4), (20, 4), (11, 11), (18, 11), (6, 8), (23, 7)):
        b.set(col, row, "D")
    b.v_wall(15, 5, 6, "C", doors=(2,))
    b.rect(7, 12, 16, 7, ".")        # paved inspection plaza
    return _stamp_props(b, STAGE_CUSTOMS)


def _noman():
    b = MapBuilder(40, 18, "g")
    b.border_rect(0, 0, 40, 18, "C", floor="g")
    b.set(20, 17, "D")       # south gate (entry)
    b.set(20, 0, "D")        # north gate (exit to the rail yard)
    b.rect(1, 1, 38, 2, "L")
    b.rect(1, 15, 38, 2, ".")
    return _stamp_props(b, STAGE_NOMAN)


def _rail():
    b = MapBuilder(46, 26, "g")
    b.border_rect(0, 0, 46, 26, "C", floor="g")
    # Concrete platform + waiting passenger train along the north edge.
    b.rect(1, 1, 44, 6, "L")
    b.rect(6, 1, 36, 3, "W")
    b.rect(6, 6, 36, 1, "Y")
    # Perimeter fences with gaps (the flanks the Guard comes through).
    b.v_wall(1, 8, 6, "W")
    b.v_wall(1, 18, 5, "W")
    b.v_wall(44, 8, 7, "W")
    b.v_wall(44, 18, 6, "W")
    return _stamp_props(b, STAGE_RAIL)


_BUILDERS = {
    STAGE_CUSTOMS: _customs,
    STAGE_NOMAN: _noman,
    STAGE_RAIL: _rail,
    STAGE_BOXCAR: _rail,
    STAGE_TRAIN: _rail,
}

# Opening squads: each "E" is a Guard behind cover facing the player's
# approach; ``meta.SQUAD_KINDS`` names the marksmen and raiders.
_SPAWNS = {
    STAGE_CUSTOMS: [("P", 15, 18), ("E", 14, 12), ("E", 9, 13), ("E", 20, 13),
                    ("E", 11, 10), ("E", 25, 12)],
    STAGE_NOMAN: [("P", 20, 16), ("E", 17, 3), ("E", 23, 3), ("E", 12, 7),
                  ("E", 28, 7), ("E", 17, 7)],
    STAGE_RAIL: [("P", 22, 24), ("V", 25, 11), ("E", 12, 12), ("E", 29, 14),
                 ("E", 38, 6), ("E", 16, 7), ("E", 35, 17), ("E", 22, 13)],
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
_objective = "Clear the customs post, then take the north gate."
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
