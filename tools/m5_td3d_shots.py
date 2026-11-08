"""Render Mission 5 frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m5_td3d_shots.py [OUT_DIR] [SET ...]

Visual-review tool, not a CI gate. Sets: hq, quarter, print, tunnel.
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
    "hq": ("start_mission5_hq_checkpoint", {"hq_a": (6, 9), "hq_b": (16, 11), "hq_c": (24, 5), "hq_d": (14, 6)}),
    "quarter": ("start_mission5_quarter_checkpoint",
                {"q_a": (6, 6), "q_b": (18, 14), "q_c": (30, 22)}),
    "print": ("start_mission5_printworks_checkpoint", {"p_a": (5, 15), "p_b": (13, 10), "p_c": (20, 5)}),
    "tunnel": ("start_mission5_tunnel_checkpoint", {"t_a": (4, 6), "t_b": (25, 6), "t_w": (31, 5), "t_c": (42, 6)}),
}


def main():
    args = sys.argv[1:]
    out = args.pop(0) if args and args[0] not in SETS else os.path.join(ROOT, "shots", "m5_td3d")
    os.makedirs(out, exist_ok=True)
    from missions import m5
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for key, (start, spots) in SETS.items():
        if args and key not in args:
            continue
        getattr(m5, start)(preserve_timer=True)
        STATE.active_mission = "MISSION5"
        for name, (tx, ty) in spots.items():
            STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
            fx, fy = STATE.player.rect.center
            STATE.camera_x = fx - _cfg.WIDTH // 2
            STATE.camera_y = fy - _cfg.HEIGHT // 2
            m5.game_draw(STATE.camera_x, STATE.camera_y)
            pygame.image.save(_cfg.screen, os.path.join(out, "m5_%s_%s.png" % (name, tag)))
            print("wrote", name, tag)


if __name__ == "__main__":
    main()
