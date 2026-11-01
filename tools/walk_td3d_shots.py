"""Render walking-sim frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/walk_td3d_shots.py [OUT_DIR]

Visual-review tool, not a CI gate. Puts the player at a few spots along the
alley and the harbour (with the KRAP van parked) and saves one frame each.
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
from core import game_core as gc  # noqa: E402

SPOTS = {"start": (3, 2), "kid": (17, 3), "fish": (27, 5), "oldwoman": (25, 8),
         "overlook": (38, 6), "van": (40, 7)}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots", "walk_td3d")
    os.makedirs(out, exist_ok=True)
    from missions import walking_sim as ws
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    ws.start_walking_sim()
    for name, (tx, ty) in SPOTS.items():
        if name == "van":
            ws.skip_walk_attack()
        ws.walk_player.rect.center = (tx * T + T // 2, ty * T + T // 2)
        ws.walk_camera_x = ws.walk_player.rect.centerx - _cfg.WIDTH // 2
        ws.walk_camera_y = ws.walk_player.rect.centery - _cfg.HEIGHT // 2
        ws._clamp_walk_camera()
        ws.walk_render_x, ws.walk_render_y = ws.walk_camera_x, ws.walk_camera_y
        ws.walk_active_hover = ws._walk_hover_target()
        ws.draw_walking_sim()
        pygame.image.save(_cfg.screen, os.path.join(out, "walk_%s_%s.png" % (name, tag)))
        print("wrote", name, tag)


if __name__ == "__main__":
    main()
