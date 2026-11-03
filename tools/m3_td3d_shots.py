"""Render Mission 3 cell-block frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m3_td3d_shots.py [OUT_DIR] [SPOT ...]

Visual-review tool, not a CI gate. Starts the breakout checkpoint, puts
Biribel at a few spots in the Stabilization Center (his cell, the cell
corridor, the kitchen, the guard hall, the armory, the lower hall, laundry,
yard, maintenance, the exit) and saves one frame each.
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

SPOTS = {"cell": (33, 9), "corridor": (20, 14), "kitchen": (4, 22), "guards": (20, 21),
         "armory": (40, 21), "hall": (22, 27), "laundry": (10, 36), "yard": (24, 37),
         "maint": (38, 37), "exit": (40, 15), "outside": (3, 40)}


def _frame(m3, out, name, tag):
    fx, fy = STATE.player.rect.center
    STATE.camera_x = fx - _cfg.WIDTH // 2
    STATE.camera_y = fy - _cfg.HEIGHT // 2
    m3.game_draw(STATE.camera_x, STATE.camera_y)
    pygame.image.save(_cfg.screen, os.path.join(out, "m3_%s_%s.png" % (name, tag)))
    print("wrote", name, tag)


def main():
    args = sys.argv[1:]
    out = args.pop(0) if args and args[0] not in SPOTS else os.path.join(ROOT, "shots", "m3_td3d")
    want = set(args)
    os.makedirs(out, exist_ok=True)
    from missions import m3
    m3.start_mission3_breakout_checkpoint(preserve_timer=True)
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for name, (tx, ty) in SPOTS.items():
        if want and name not in want:
            continue
        STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
        _frame(m3, out, name, tag)


if __name__ == "__main__":
    main()
