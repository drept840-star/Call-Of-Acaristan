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
#
# The kit is M6's own (``decor`` paints every kind here): border booms,
# Guard trucks, a snow plough, snow fencing, pallets, a yard fuel tank, an
# APC hulk.  Mission 2's city cars and IPA truck used to dress these yards
# and that is exactly what made the crossing look like a recycled street.
_PROP_LAYOUT = {
    STAGE_CUSTOMS: (
        # north apron - the crossing itself: gate, booms, parked trucks
        ("guard_truck", 4, 1, 3, 1), ("boom", 12, 2, 1, 1), ("boom", 18, 2, 1, 1),
        ("guard_truck", 8, 1, 3, 1),
        ("pallet", 1, 4, 2, 1), ("pallet", 23, 4, 2, 1),
        # the post: processing office (west, enterable) and cold store (east)
        ("counter", 4, 7, 3, 1), ("terminal", 8, 7, 2, 1),
        ("cabinet", 3, 10, 1, 1), ("crate", 9, 10, 1, 1),
        # inspection lane between the post and the store
        ("booth", 12, 6, 1, 2), ("booth", 18, 9, 1, 2),
        # south yard: the queue that froze here, and the fuel farm
        # (the fuel_tank footprint stays: combat draws the live tanker there
        # and TANKER_RECT is checked against it by tools/m6_layout_probe.py)
        ("guard_truck", 2, 13, 3, 1),
        ("plough", 19, 15, 3, 1), ("fuel_tank", 23, 12, 5, 3),
        ("jersey", 10, 12, 2, 1),
        ("snow_fence", 5, 18, 3, 1),
        ("hedgehog", 11, 17, 1, 1),
    ),
    STAGE_NOMAN: (
        # floodlight towers (lights are data in stealth.py)
        ("tower", 8, 4, 1, 2), ("tower", 31, 4, 1, 2),
        ("tower", 8, 10, 1, 2), ("tower", 31, 10, 1, 2),
        # Guard line in front of the north gate
        ("sandbag", 16, 4, 3, 1), ("sandbag", 22, 4, 3, 1),
        ("booth", 12, 1, 2, 2), ("booth", 26, 1, 2, 2),
        ("barrels", 3, 1, 2, 1), ("crates", 35, 1, 2, 2),
        # the strip: a burnt APC, a truck on its side, hedgehogs, wire
        ("apc", 24, 7, 3, 1), ("truck_burnt", 14, 8, 3, 1),
        ("jersey", 11, 6, 2, 1), ("jersey", 28, 9, 3, 1),
        ("snow_fence", 3, 5, 3, 1), ("snow_fence", 34, 5, 3, 1),
        ("snow_fence", 5, 11, 3, 1), ("snow_fence", 30, 11, 3, 1),
        ("hedgehog", 5, 7, 1, 1), ("hedgehog", 14, 10, 1, 1),
        ("hedgehog", 25, 11, 1, 1), ("hedgehog", 35, 7, 1, 1),
        ("hedgehog", 13, 5, 1, 1), ("hedgehog", 26, 5, 1, 1),
        ("hedgehog", 4, 11, 1, 1), ("hedgehog", 36, 11, 1, 1),
        # south trench line: the player's first cover
        ("sandbag", 3, 13, 4, 1), ("sandbag", 11, 13, 3, 1),
        ("sandbag", 17, 13, 2, 1), ("sandbag", 23, 13, 2, 1),
        ("sandbag", 27, 13, 3, 1), ("sandbag", 34, 13, 3, 1),
        ("pallet", 8, 8, 2, 1),
    ),
    STAGE_RAIL: (
        # boxcars ride the three running lines (decor draws the rails under
        # them); Volkov's marked car is the (20,9) one
        ("boxcar", 4, 9, 10, 2), ("boxcar", 20, 9, 10, 2), ("boxcar", 34, 13, 8, 2),
        ("boxcar", 6, 14, 11, 2), ("boxcar", 24, 19, 10, 2),
        ("container", 4, 20, 5, 2), ("container", 36, 20, 5, 2),
        ("shack", 39, 7, 4, 4),
        # yard furniture: water tower, signal gantry, sleeper stacks, plough
        ("water_tower", 2, 12, 2, 2),
        ("sleeper_stack", 17, 12, 2, 1), ("sleeper_stack", 30, 17, 2, 1),
        ("plough", 40, 22, 3, 1), ("snow_fence", 2, 17, 3, 1),
        ("snow_fence", 30, 22, 3, 1),
        ("crates", 17, 16, 2, 2), ("barrels", 13, 7, 2, 1),
        ("barrels", 30, 20, 2, 1), ("jersey", 22, 16, 2, 1),
        ("jersey", 28, 17, 2, 1), ("sandbag", 11, 12, 3, 1),
        ("coil", 33, 16, 1, 1), ("coil", 19, 21, 1, 1),
        ("crates", 11, 22, 2, 2), ("pallet", 34, 8, 2, 1),
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
    """The post: gate apron north, the hall and a cold store, the yard south."""
    b = MapBuilder(30, 20, "g")
    b.border_rect(0, 0, 30, 20, "C", floor="g")
    b.rect(1, 1, 28, 4, "L")          # concrete apron carrying the crossing
    b.set(15, 0, "D")                 # the north gate itself (map exit)
    # The post: the processing office (west, enterable) and the cold store.
    b.border_rect(2, 5, 10, 7, "C", floor=".")
    b.set(11, 8, "D")                 # office door onto the inspection lane
    b.set(6, 11, "D")                 # ... and out to the yard
    b.border_rect(19, 5, 10, 5, "C", floor=".")   # cold store: sealed shell
    b.set(19, 7, "D")                 # cold-store door onto the lane
    b.rect(12, 5, 7, 7, "L")          # the inspection lane between them
    b.rect(13, 4, 4, 10, "L")         # the spine: post frontage to the yard road
    b.rect(19, 10, 10, 2, "L")        # apron under the store's eaves
    # South yard and the road in from the entry gate.
    b.rect(2, 12, 11, 4, ".")         # paved parking / inspection bays
    b.rect(19, 12, 9, 3, ".")         # fuel farm hardstanding
    b.rect(13, 12, 5, 7, "L")         # the approach road (player walks this)
    return _stamp_props(b, STAGE_CUSTOMS)


def _noman():
    """No-man's-land: two aprons, one causeway, everything between is mined."""
    b = MapBuilder(40, 18, "g")
    b.border_rect(0, 0, 40, 18, "C", floor="g")
    b.set(20, 17, "D")       # south gate (entry)
    b.set(20, 0, "D")        # north gate (exit to the rail yard)
    b.rect(1, 1, 38, 2, "L")     # apron under the north gate
    b.rect(1, 15, 38, 2, "L")    # apron under the south gate
    b.rect(19, 3, 3, 12, "L")    # the causeway between the two lines
    b.rect(14, 3, 12, 1, ".")    # swept path across the strip (bodies came this way)
    b.rect(1, 3, 38, 1, ".")     # swept strip along the wire
    b.rect(1, 14, 38, 1, ".")
    return _stamp_props(b, STAGE_NOMAN)


def _rail():
    """The freight yard: platform north, three running lines, yard to the south."""
    b = MapBuilder(46, 26, "g")
    b.border_rect(0, 0, 46, 26, "C", floor="g")
    # Concrete platform + the waiting passenger train along the north edge.
    b.rect(1, 1, 44, 6, "L")
    b.rect(6, 1, 36, 3, "W")
    b.rect(6, 6, 36, 1, "Y")
    # Ballast lanes the boxcars sit on (decor draws the rails over them).
    for row in (9, 14, 19):
        b.rect(1, row, 44, 2, ".")
    # Perimeter fencing with the gaps the Guard comes through.
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
    STAGE_CUSTOMS: [("P", 15, 18), ("E", 14, 13), ("E", 8, 14), ("E", 20, 14),
                    ("E", 10, 15), ("E", 25, 16)],
    STAGE_NOMAN: [("P", 20, 16), ("E", 17, 3), ("E", 23, 3), ("E", 12, 7),
                  ("E", 28, 7), ("E", 17, 7)],
    STAGE_RAIL: [("P", 22, 24), ("V", 25, 11), ("E", 12, 12), ("E", 29, 13),
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
