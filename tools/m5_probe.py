"""m5_probe.py - render M5 cutscene frames headless for visual review.

Usage (repo root, bash):
  SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy tools/../\.venv/Scripts/python.exe \
      tools/m5_probe.py OUT_DIR [scene ...]

With no scene list, dumps the whole M5 ending film at several timestamps in
both the 3D take and the 2D fallback (ACARISTAN_CUTSCENE3D=0).
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()

from core import config  # noqa: E402
from cutscenes import engine as _eng  # noqa: E402
from cutscenes import m5martial3d as _m3d  # noqa: E402

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "_shots", "m5fix")
SCENES = sys.argv[2:] or ["m5_river_gate", "m5_ucilev_scope", "m5_ucilev_reveal",
                          "m5_ucilev_leaves", "m5_radio"]
TIMES = (0, 1500, 3000, 4500, 6000, 7500, 9000)


def dump(scene, t, path):
    _eng.draw_cutscene_scene(config.screen, {"scene": scene, "speaker": "",
                                             "text": "", "lighting": (8, 10, 14),
                                             "min_ms": 0, "quiet_ui": True}, t)
    pygame.image.save(config.screen, path)


def main():
    os.makedirs(OUT, exist_ok=True)
    for mode, env in (("3d", "1"), ("2d", "0")):
        os.environ["ACARISTAN_CUTSCENE3D"] = env
        _m3d._cache["failed"] = False
        for scene in SCENES:
            for t in TIMES:
                name = "%s_%s_%05d.png" % (mode, scene, t)
                dump(scene, t, os.path.join(OUT, name))
                print("wrote", name)


if __name__ == "__main__":
    main()
