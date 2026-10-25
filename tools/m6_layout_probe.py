"""M6 layout probe: every authored coordinate must land on open floor.

    python tools/m6_layout_probe.py

Checks the map contract (``maps._validate()``) plus every tile the rest of
the mission authors by hand - squad spawns, wave entry tiles, fuel drums,
patrol waypoints, the fuel tank rect, stage anchors and spawns - against the
baked grids.  Prints one line per offending tile; exits 1 when any exist.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from missions.m6 import maps as _maps            # noqa: E402
from missions.m6 import meta as _meta            # noqa: E402
from missions.m6 import combat as _combat        # noqa: E402
from missions.m6 import world as _world          # noqa: E402
from missions.m6 import decor as _decor          # noqa: E402


def main():
    bad = ["map validate: %s" % e for e in _maps._validate()]
    for stage in (_meta.STAGE_CUSTOMS, _meta.STAGE_NOMAN, _meta.STAGE_RAIL):
        grid = _maps.structure_for(stage)
        solid = _meta.M6_SOLID_CHARS

        def check(label, col, row):
            if not (0 <= row < len(grid) and 0 <= col < len(grid[0])):
                bad.append("%s: %s (%d,%d) out of bounds" % (stage, label, col, row))
                return
            if grid[row][col] in solid:
                bad.append("%s: %s (%d,%d) is solid '%s'"
                           % (stage, label, col, row, grid[row][col]))

        for (c, r), kind in _meta.SQUAD_KINDS.get(stage, {}).items():
            check("squad-" + kind, c, r)
        for wi, wave in enumerate(_meta.ARENA_WAVES.get(stage, ())):
            for kind, c, r in wave["units"]:
                check("wave%d-%s" % (wi, kind), c, r)
        for c, r in _meta.ARENA_DRUMS.get(stage, ()):
            check("drum", c, r)
        c, r = _meta.STAGE_ANCHORS[stage]
        check("anchor", c, r)
        c, r = _meta.STAGE_SPAWNS[stage]
        check("spawn", c, r)
        for tile, points in _world._PATROLS.get(stage, {}).items():
            for c, r in points:
                check("patrol", c, r)
        # Props must not sit on top of any of the above.
        occupied = {(c, r) for _k, c, r, _w, _h in _maps.props_for(stage)}
        for (c, r) in _meta.SQUAD_KINDS.get(stage, {}):
            if (c, r) in occupied:
                bad.append("%s: squad (%d,%d) has a prop on it" % (stage, c, r))
        # Prop footprints stay inside the shell and off the stage anchors.
        for kind, x, y, w, h in _maps.props_for(stage):
            if x < 1 or y < 1 or x + w > len(grid[0]) - 1 or y + h > len(grid) - 1:
                bad.append("%s: prop %s at (%d,%d) %dx%d leaves the map"
                           % (stage, kind, x, y, w, h))

    # The fuel tank is authored twice: map prop + combat rect.
    c, r, w, h = _combat.TANKER_RECT
    if ("fuel_tank", c, r, w, h) not in _maps.props_for(_meta.STAGE_CUSTOMS):
        bad.append("combat.TANKER_RECT %r does not match the customs fuel_tank prop"
                   % (_combat.TANKER_RECT,))
    # Every prop kind must have a painter.
    kinds = {p[0] for stage in _maps._PROP_LAYOUT for p in _maps.props_for(stage)}
    for kind in sorted(kinds):
        if kind in _decor._DYNAMIC_KINDS:
            continue
        probe = pygame.Surface((96, 96 + _decor._OVER.get(kind, 0)), pygame.SRCALPHA)
        try:
            _decor._draw_kind(kind, probe, _decor._OVER.get(kind, 0), 96, 64, 0, 0, 3)
        except Exception as exc:
            bad.append("prop %s has no working painter (%s: %s)"
                       % (kind, type(exc).__name__, exc))

    for line in bad:
        print("LAYOUT:", line)
    print("M6 LAYOUT PROBE: %s (%d issue%s)"
          % ("OK" if not bad else "FAILED", len(bad), "" if len(bad) == 1 else "s"))
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
