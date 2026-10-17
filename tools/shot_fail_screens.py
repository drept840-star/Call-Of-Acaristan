"""Polish pass T9 evidence: render the Mission Failed screen for M1-M5.

Usage: python tools/shot_fail_screens.py  -> shots/polish_pass/09/fail_<key>.png
"""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402
from engine.core import now_ms as _engine_now_ms  # RPE6 B-001
from core import config  # noqa: E402
from core import game_core as gc  # noqa: E402
import ui as menu  # noqa: E402
import ui.system as uisys  # noqa: E402

OUT = ROOT / "shots" / "polish_pass" / "09"
OUT.mkdir(parents=True, exist_ok=True)

for key, start in [("MISSION1", gc.start_mission), ("MISSION2", gc.start_mission2),
                   ("MISSION3", gc.start_mission3), ("MISSION4", gc.start_mission4),
                   ("MISSION5", gc.start_mission5)]:
    start()
    config.screen.fill((0, 0, 0))
    menu.reset_death_animation()
    uisys._death_animation_start = max(1, _engine_now_ms() - 5000)  # RPE6 B-001: game time is the engine clock
    menu.draw_death_screen()
    path = OUT / ("fail_%s.png" % key.lower())
    pygame.image.save(config.screen, str(path))
    print("saved", path)
