"""Round-2 M5 cutscene check: renders every m5x_ take (3D, then 2D fallback)."""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("ACARISTAN_RENDERER", "software")
os.environ["ACARISTAN_CUTSCENE3D"] = "1"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from cutscenes import m5mid3d, m5martial3d  # noqa: E402
from missions.m5.meta import M5_MID_CUTSCENES  # noqa: E402

OUT = os.path.join(ROOT, "tools", "m5_r2_shots")
os.makedirs(OUT, exist_ok=True)
for key, shots in M5_MID_CUTSCENES.items():
    for s in shots:
        assert s["scene"] in m5mid3d.M5X_SCENES, s["scene"]
for name, fn in m5mid3d.M5X_SCENES.items():
    for t in (200, 1800):
        fn(screen, t)          # raw 3D call: raises if the take is broken
    pygame.image.save(screen, os.path.join(OUT, "cut3d_" + name + ".png"))
    m5mid3d.draw_m5x_2d(name, screen, 1800)
    pygame.image.save(screen, os.path.join(OUT, "cut2d_" + name + ".png"))
    print("cut", name)
print("3D failed flag:", m5martial3d._cache["failed"], m5martial3d._cache["err"])
print("CUT CHECK OK")
