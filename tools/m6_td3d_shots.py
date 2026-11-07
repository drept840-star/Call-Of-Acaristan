"""Render Mission 6 frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m6_td3d_shots.py [OUT_DIR] [SET ...]

Visual-review tool, not a CI gate. Sets: customs, noman, rail.
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

SETS = {
    "customs": ("start_mission6_customs_checkpoint", {"c_a": (15, 10), "c_b": (6, 6), "c_c": (24, 14)}),
    "noman": ("start_mission6_noman_checkpoint", {"n_a": (20, 8), "n_b": (8, 7), "n_c": (30, 12)}),
    "rail": ("start_mission6_rail_checkpoint", {"r_a": (22, 11), "r_b": (38, 9), "r_c": (8, 12)}),
}


def main():
    args = sys.argv[1:]
    out = args.pop(0) if args and args[0] not in SETS else os.path.join(ROOT, "shots", "m6_td3d")
    os.makedirs(out, exist_ok=True)
    from missions import m6
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for key, (start, spots) in SETS.items():
        if args and key not in args:
            continue
        getattr(m6, start)(preserve_timer=True)
        STATE.active_mission = "MISSION6"
        for name, (tx, ty) in spots.items():
            STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
            fx, fy = STATE.player.rect.center
            STATE.camera_x = fx - _cfg.WIDTH // 2
            STATE.camera_y = fy - _cfg.HEIGHT // 2
            m6.game_draw(STATE.camera_x, STATE.camera_y)
            pygame.image.save(_cfg.screen, os.path.join(out, "m6_%s_%s.png" % (name, tag)))
            print("wrote", name, tag)


if __name__ == "__main__":
    main()
