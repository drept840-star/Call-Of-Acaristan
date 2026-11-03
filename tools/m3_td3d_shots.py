"""Render Mission 3 frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m3_td3d_shots.py [OUT_DIR] [SPOT ...]

Visual-review tool, not a CI gate. Starts each stage checkpoint (breakout,
comms, archives, kill order, broadcast), puts Biribel at a few spots on
that stage's map and saves one frame each. SPOT names are prefixed by the
stage (``cell``, ``comms_relay``, ``arch_vault``...); a bare stage name
(``comms``) renders every spot of that stage. ``ACA_M3_FLAGS`` sets
comma-separated STATE flags true after each checkpoint starts.
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

# stage -> (checkpoint function name, {spot: (col, row)})
STAGES = {
    "cell": ("start_mission3_breakout_checkpoint",
             {"cell": (33, 9), "corridor": (20, 14), "kitchen": (4, 22), "guards": (20, 21),
              "armory": (40, 21), "hall": (22, 27), "laundry": (10, 36), "yard": (24, 37),
              "maint": (38, 37), "exit": (40, 15), "outside": (3, 40)}),
    "comms": ("start_mission3_comms_checkpoint",
              {"comms_airlock": (6, 24), "comms_corridor": (20, 24), "comms_relay": (24, 21),
               "comms_server": (39, 22), "comms_battery": (22, 33), "comms_portal": (45, 24)}),
    "arch": ("start_mission3_archives_checkpoint",
             {"arch_lobby": (24, 41), "arch_atrium": (24, 28), "arch_stacks": (12, 25),
              "arch_maru": (11, 14), "arch_cubes": (36, 27), "arch_vestibule": (28, 10),
              "arch_vault": (41, 10), "arch_exit": (24, 5)}),
    "ko": ("start_mission3_kill_order_checkpoint",
           {"ko_stair": (6, 4), "ko_lobby": (19, 17), "ko_west": (5, 18), "ko_east": (32, 18),
            "ko_mezz": (26, 24), "ko_south": (17, 30), "ko_dock": (25, 35), "ko_van": (33, 36)}),
    "bcast": ("start_mission3_broadcast_checkpoint",
              {"bcast_lift": (15, 3), "bcast_hall": (15, 8), "bcast_shaft": (15, 13),
               "bcast_studio": (14, 20), "bcast_suite": (25, 24), "bcast_pc": (25, 27),
               "bcast_west": (6, 25)}),
}


def _frame(m3, out, name, tag):
    fx, fy = STATE.player.rect.center
    STATE.camera_x = fx - _cfg.WIDTH // 2
    STATE.camera_y = fy - _cfg.HEIGHT // 2
    m3.game_draw(STATE.camera_x, STATE.camera_y)
    pygame.image.save(_cfg.screen, os.path.join(out, "m3_%s_%s.png" % (name, tag)))
    print("wrote", name, tag)


def main():
    args = sys.argv[1:]
    names = set(STAGES) | {s for _f, spots in STAGES.values() for s in spots}
    out = args.pop(0) if args and args[0] not in names else os.path.join(ROOT, "shots", "m3_td3d")
    want = set(args)
    os.makedirs(out, exist_ok=True)
    from missions import m3
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for stage, (start, spots) in STAGES.items():
        picked = [s for s in spots if not want or stage in want or s in want]
        if not picked:
            continue
        getattr(m3, start)(preserve_timer=True)
        for flag in filter(None, os.environ.get("ACA_M3_FLAGS", "").split(",")):
            setattr(STATE, flag, True)              # e.g. m3_comms_power_restored
        for name in picked:
            tx, ty = spots[name]
            STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
            _frame(m3, out, name, tag)


if __name__ == "__main__":
    main()
