"""Render Mission 1 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m1_td3d_shots.py [OUT_DIR]

Visual-review tool, not a CI gate. Puts Biribel at a few spots (street,
stockroom, hall, yard) and saves one frame each.
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
from core.state import STATE  # noqa: E402

SPOTS = {"street": (9, 6), "truck": (23, 5), "stockroom": (8, 16), "hall": (12, 23),
         "yard": (15, 28), "exfil": (24, 31)}


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots", "m1_td3d")
    os.makedirs(out, exist_ok=True)
    _cfg.screen
    gc.start_mission(preserve_timer=True)
    from missions import m1
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for name, (tx, ty) in SPOTS.items():
        if name == "exfil":              # notebook taken, reinforcement van parked
            from missions.m1.update import debug_jump_to_exfil
            debug_jump_to_exfil()
            STATE.exfil_van_arrived = True
        STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
        STATE.camera_x = STATE.player.rect.centerx - _cfg.WIDTH // 2
        STATE.camera_y = STATE.player.rect.centery - _cfg.HEIGHT // 2
        m1.game_draw(STATE.camera_x, STATE.camera_y)
        pygame.image.save(_cfg.screen, os.path.join(out, "m1_%s_%s.png" % (name, tag)))
        print("wrote", name, tag)
    from core.cutscene_registry import scene_renderer
    for scene, t in (("m1_dropoff", 900), ("m1_dropoff", 1700), ("m1_dropoff", 3600),
                     ("m1_dropoff_follow", 5600), ("m1_dropoff_entry", 8200)):
        scene_renderer(scene)(_cfg.screen, t)
        pygame.image.save(_cfg.screen, os.path.join(out, "%s_%d_%s.png" % (scene, t, tag)))
        print("wrote", scene, t, tag)


if __name__ == "__main__":
    main()
