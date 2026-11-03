"""Render Mission 2 top-down frames in 2.5D (and 2D with ACA_TD_2D=1).

    python tools/m2_td3d_shots.py [OUT_DIR] [SPOT ...]

Visual-review tool, not a CI gate. Puts Biribel at a few spots along Route 12
(start, toll plaza, kill zone, IPA truck, tanker, shelter, control room,
garden) and saves one frame each, then the tanker blast and its aftermath.
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

SPOTS = {"start": (8, 72), "approach": (20, 62), "plaza": (30, 38), "killzone": (36, 34),
         "truck": (46, 33), "tanker": (42, 42), "shelter": (28, 49), "control": (58, 20),
         "terminal": (60, 17), "garden": (59, 7), "gantry": (56, 30)}
BLAST = (("blast_0010", 10), ("blast_0060", 60), ("blast_0200", 200))


def _frame(m2, out, name, tag, focus=None):
    fx, fy = focus or STATE.player.rect.center
    STATE.camera_x = fx - _cfg.WIDTH // 2
    STATE.camera_y = fy - _cfg.HEIGHT // 2
    m2.game_draw(STATE.camera_x, STATE.camera_y)
    pygame.image.save(_cfg.screen, os.path.join(out, "m2_%s_%s.png" % (name, tag)))
    print("wrote", name, tag)


def main():
    args = sys.argv[1:]
    out = args.pop(0) if args and not args[0] in SPOTS and args[0] != "blast" else \
        os.path.join(ROOT, "shots", "m2_td3d")
    want = set(args)
    os.makedirs(out, exist_ok=True)
    _cfg.screen
    from missions import m2
    m2.start_mission2_truck(preserve_timer=True)
    STATE.mission2_card = None
    T = _cfg.TILE_SIZE
    tag = "2d" if os.environ.get("ACA_TD_2D") == "1" else "3d"
    for name, (tx, ty) in SPOTS.items():
        if want and name not in want:
            continue
        STATE.player.rect.center = (tx * T + T // 2, ty * T + T // 2)
        _frame(m2, out, name, tag)
    if want and "blast" not in want:
        return
    from missions.m2 import sniper
    sniper._explode_tanker()
    STATE.mission2_card = None
    from missions.m2.meta import STAGE_RUN
    STATE.mission2_stage = STAGE_RUN          # review frames: the world, not the blackout card
    tx, ty = SPOTS["tanker"]
    STATE.player.rect.center = (tx * T + T // 2, (ty + 6) * T + T // 2)
    done = 0
    for name, bt in BLAST:
        while done < bt:
            STATE.mission2_tanker_blast_timer = done
            done += 1
        STATE.mission2_tanker_blast_timer = bt
        STATE.gc_flash_timer = 0
        STATE.mission2_tanker_fireball_radius = int(min(bt, 45) * 15.5)    # update.py drives these
        STATE.mission2_tanker_shockwave_radius = int(min(bt, 50) * 32.0)
        STATE.player_dead = False
        _frame(m2, out, name, tag, focus=STATE.mission2_tanker_rect.center)


if __name__ == "__main__":
    main()
