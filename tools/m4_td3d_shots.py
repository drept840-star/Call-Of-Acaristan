"""Render Mission 4 frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m4_td3d_shots.py [OUT_DIR] [SPOT ...]

Visual-review tool, not a CI gate. Starts the street (``start_m4``) and the
station checkpoint, puts Biribel at a few spots on each map and saves one
frame each. A bare set name (``street``, ``station``) renders every spot of
that set. ``ACA_M4_FLAGS`` sets comma-separated STATE flags true after
each start (``m4_breached``, ``m4_jammer_installed``...).
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACA_FREEZE", "1")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from core import config as _cfg  # noqa: E402
from core.state import STATE  # noqa: E402

# set -> (start function name, {spot: (col, row)})
SETS = {
    "street": ("start_m4",
               {"st_start": (4, 4), "st_boulevard": (12, 19), "st_mid": (20, 18),
                "st_cross": (16, 13), "st_door": (31, 19), "st_south": (22, 30)}),
    "station": ("start_mission4_station_checkpoint",
                {"sta_forecourt": (17, 23), "sta_entry": (17, 17), "sta_hall": (18, 7),
                 "sta_corridor": (24, 11), "sta_studio": (27, 17), "sta_ring_e": (32, 12),
                 "sta_archive": (8, 7)}),
    "siege": ("start_mission4_tower_checkpoint",
              {"sg_forecourt": (18, 22), "sg_entry": (17, 18), "sg_hall": (18, 9),
               "sg_corridor": (25, 11), "sg_build": (12, 5)}),
}


def _stage_siege(m4):
    """Wave 5 mid-fight: every site built (mixed kinds and damage), the weak
    wall blown, the APC parked at the main door, loyalists on the ring."""
    from missions.m4 import fortify, siege, apc
    import random
    random.seed(7)
    for i, (c, r, kind) in enumerate(STATE.m4_sites):
        k = ("plate" if i % 2 else "planks") if kind == "door" else "boards"
        fortify._place((c, r), k)
        bar = STATE.m4_barricades[(c, r)]
        bar["hp"] = int(bar["max"] * (1.0, 0.55, 0.2, 0.0)[i % 4])
    siege.blow_quiet()
    STATE.m4_siege_t = 24000 + 1800
    STATE.m4_wave = 5
    STATE.m4_supply = 7
    apc.start()
    a = STATE.m4_apc
    a.update(x=apc.TURN_X, y=apc.PARK_Y, yaw=-1.5707963, phase="parked")
    apc._park()
    for door in ("S", "E", "W", "N", "SE"):
        siege._spawn(random.choice(("loyalist", "marksman", "breacher")), door)
    for _ in range(40):
        m4.game_update(_NoKeys())


class _NoKeys:
    def __getitem__(self, k):
        return False


SETUP = {"siege": _stage_siege}


def _frame(m4, out, name, tag):
    fx, fy = STATE.player.rect.center
    STATE.camera_x = fx - _cfg.WIDTH // 2
    STATE.camera_y = fy - _cfg.HEIGHT // 2
    m4.game_draw(STATE.camera_x, STATE.camera_y)
    pygame.image.save(_cfg.screen, os.path.join(out, "m4_%s_%s.png" % (name, tag)))
    print("wrote", name, tag)


def main():
    args = sys.argv[1:]
    names = set(SETS) | {s for _f, spots in SETS.values() for s in spots}
    out = args.pop(0) if args and args[0] not in names else os.path.join(ROOT, "shots", "m4_td3d")
    want = set(args)
    os.makedirs(out, exist_ok=True)
    from missions import m4
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for key, (start, spots) in SETS.items():
        picked = [s for s in spots if not want or key in want or s in want]
        if not picked:
            continue
        getattr(m4, start)(preserve_timer=True)
        STATE.active_mission = "MISSION4"
        for flag in filter(None, os.environ.get("ACA_M4_FLAGS", "").split(",")):
            setattr(STATE, flag, True)
        if key in SETUP:
            SETUP[key](m4)
        for name in picked:
            tx, ty = spots[name]
            STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
            _frame(m4, out, name, tag)


if __name__ == "__main__":
    main()
