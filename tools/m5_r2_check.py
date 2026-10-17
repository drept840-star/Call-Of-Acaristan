"""Round-2 M5 headless check: builds stages, draws a few frames, saves PNGs."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from core.state import STATE  # noqa: E402
import missions.m5 as m5  # noqa: E402
from missions.m5 import flow, draw  # noqa: E402

OUT = os.path.join(ROOT, "tools", "m5_r2_shots")
os.makedirs(OUT, exist_ok=True)
m5.start_m5()


def shot(name, wx, wy):
    STATE.player.rect.center = (wx, wy)
    cx, cy = wx - WIDTH // 2, wy - HEIGHT // 2
    for _ in range(3):
        draw.game_draw(cx, cy)
    pygame.image.save(screen, os.path.join(OUT, name + ".png"))
    print("shot", name)


T = TILE_SIZE
flow._enter_hq()
shot("hq_west", 4 * T, 11 * T)
shot("hq_east", 20 * T, 8 * T)
flow._start_vasile_dialogue()
flow._m5_dlg["char_idx"] = 40
shot("dialogue_typing", 24 * T, 5 * T)
flow._m5_dlg["char_idx"] = 9999
shot("dialogue_full", 24 * T, 5 * T)
flow._dlg_reset()
STATE.m5_dialogue_active = False
flow._enter_quarter()
shot("quarter_start", 6 * T, 15 * T)
from missions.m5 import quarter  # noqa: E402
import game.world as _gw  # RPE6 Phase 5 (D4)
from missions.m5.components import M5Guard as _M5Guard


def _m5g(e):
    return _gw.ensure(e, _M5Guard)

faces = [_m5g(e).face for e in STATE.enemies if _m5g(e).passive]
print("old faces", faces, "enemies", len(STATE.enemies))
for i in range(400):
    STATE.player.rect.center = (int((6 + i * 0.06) * T), 15 * T)
    quarter.update()
print("quarter tick ok convoy", quarter._S["convoy"], "civ", quarter._S["civ"])
shot("quarter_mid", 22 * T, 15 * T)
shot("quarter_printworks", 33 * T, 15 * T)
print("R2 CHECK OK walls=%d" % len(STATE.walls))
