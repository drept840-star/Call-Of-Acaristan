"""Render one M5 top-down frame (the quarter night) as the house-style target.

    python tools/m5_topdown_frame.py OUT_DIR [stage]

Visual-review tool, not a CI gate.  Used next to the M6 top-down arenas to
judge brightness/contrast/silhouette parity between missions.
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

from core import config as _cfg  # noqa: E402
from core.state import STATE  # noqa: E402


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots", "m5_topdown")
    stage = sys.argv[2] if len(sys.argv) > 2 else "quarter"
    os.makedirs(out, exist_ok=True)
    _cfg.screen
    from missions import m5
    from missions.m5 import flow as _flow

    start = {
        "hq": _flow.start_mission5_hq_checkpoint,
        "quarter": _flow.start_mission5_quarter_checkpoint,
        "printworks": _flow.start_mission5_printworks_checkpoint,
        "tunnel": _flow.start_mission5_tunnel_checkpoint,
    }[stage]
    start()
    if STATE.player is None:
        print("no player after start")
        return
    STATE.camera_x = max(0, STATE.player.rect.centerx - _cfg.WIDTH // 2)
    STATE.camera_y = max(0, STATE.player.rect.centery - _cfg.HEIGHT // 2)
    m5.game_draw(STATE.camera_x, STATE.camera_y)
    surf = pygame.display.get_surface()
    if surf is not None:
        pygame.image.save(surf, os.path.join(out, "m5_%s_frame.png" % stage))
        print("wrote", stage)
    else:
        print("no display surface")


if __name__ == "__main__":
    main()
