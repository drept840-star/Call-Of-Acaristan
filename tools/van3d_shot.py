"""Render the 3D van_exterior take to PNGs: python tools/van3d_shot.py [t_ms ...]"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import HEIGHT, WIDTH  # noqa: E402

pygame.display.set_mode((WIDTH, HEIGHT))
from cutscenes import van3d  # noqa: E402

times = [int(a) for a in sys.argv[1:]] or [0, 1500, 3000]
out = os.path.join(ROOT, "shots", "van3d")
os.makedirs(out, exist_ok=True)
for t in times:
    s = pygame.Surface((WIDTH, HEIGHT))
    s.fill((10, 12, 18))
    van3d.draw_van_exterior_take(s, t)
    pygame.image.save(s, os.path.join(out, "van_%05d.png" % t))
print("failed:", van3d._S["failed"], van3d._S["err"], "backend:", getattr(van3d._S["r"], "backend", None))
