"""Customs snow probe (dev only, not a CI gate).

    python tools/m6_snow_probe.py

The post's rooms sit behind doors, so they count as indoor and must carry no
snow: no snow-palette pixel on an indoor floor, on a wall face that looks into
a room, or on an indoor prop.  Prints one line per prop, then OK or FAIL.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

SNOW = {(198, 210, 226), (168, 182, 202), (156, 170, 190), (150, 164, 184),
        (232, 238, 248)}


def _snow_px(surf, x0, y0, x1, y1):
    hits = 0
    for y in range(max(0, y0), min(surf.get_height(), y1)):
        for x in range(max(0, x0), min(surf.get_width(), x1)):
            c = surf.get_at((x, y))
            if c.a and (c.r, c.g, c.b) in SNOW:
                hits += 1
    return hits


def main():
    from core import config as _cfg
    _cfg.screen  # creates the display the art loader needs
    from core.state import STATE
    from missions import m6
    from missions.m6 import decor as _decor
    from missions.m6 import maps as _maps
    from missions.m6 import meta as _meta

    stage = _meta.STAGE_CUSTOMS
    m6.start_m6()
    m6.start_mission6_customs_checkpoint()
    _maps.bind_stage(stage)
    STATE.mission6_stage = stage
    _decor.build_decor(stage)

    T = _decor.T
    grid = _maps.grid_for(stage)
    h, w = len(grid), len(grid[0])
    outdoor = _decor._outdoor_tiles(stage)
    indoor = {(c, r) for r in range(h) for c in range(w)
              if grid[r][c] not in "CWBD" and (c, r) not in outdoor}
    ok = True

    ground = _decor._ground_surface(stage)
    floor_hits = sum(_snow_px(ground, c * T, r * T, c * T + T, r * T + T)
                     for c, r in indoor)
    print("indoor floor tiles: %d, snow pixels on them: %d" % (len(indoor), floor_hits))
    ok &= floor_hits == 0

    face_hits = face_tiles = 0
    for r in range(h):
        for c in range(w):
            if grid[r][c] not in "CW":
                continue
            if (c, r + 1) in indoor:      # room is south: the lip must stay bare
                face_hits += _snow_px(ground, c * T, r * T + T - 4, c * T + T, r * T + T)
                face_tiles += 1
            if (c, r - 1) in indoor:      # room is north: the crown must stay bare
                face_hits += _snow_px(ground, c * T, r * T, c * T + T, r * T + 6)
                face_tiles += 1
    print("room-side wall faces: %d, snow pixels on them: %d" % (face_tiles, face_hits))
    ok &= face_hits == 0

    # Control: exterior faces must show snow, or the palette test proves nothing.
    ext_hits = ext_tiles = 0
    for r in range(h):
        for c in range(w):
            if grid[r][c] not in "CW":
                continue
            if (c, r + 1) in outdoor:
                ext_hits += _snow_px(ground, c * T, r * T + T - 4, c * T + T, r * T + T)
                ext_tiles += 1
            if (c, r - 1) in outdoor:
                ext_hits += _snow_px(ground, c * T, r * T, c * T + T, r * T + 6)
                ext_tiles += 1
    print("outdoor wall faces: %d, snow pixels on them: %d (control, must be > 0)"
          % (ext_tiles, ext_hits))
    ok &= ext_hits > 0

    prop_hits = 0
    for (kind, x, y, pw, ph), row in zip(_decor._stage_props(stage), _decor._prop_rows(stage)):
        ring = [(x, y - 1), (x, y + ph), (x - 1, y), (x + pw, y)]
        inside = not any(t in outdoor for t in ring)
        hits = _snow_px(row["surf"], 0, 0, row["w"], row["h"])
        if inside:
            prop_hits += hits
        print("  %-14s at (%2d,%2d) %s snow px %4d" % (
            kind, x, y, "indoor " if inside else "outdoor", hits))
    print("indoor prop snow pixels: %d" % prop_hits)
    ok &= prop_hits == 0

    print("M6 SNOW PROBE: %s" % ("OK" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
