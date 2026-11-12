"""Compare consecutive chase frames: how much does the background actually change?"""
import os
import sys
import numpy as np
import pygame

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

OUT = "outputs/m8_chase"
files = sorted(f for f in os.listdir(OUT) if f.startswith("z_") and f.endswith(".png"))
prev = None
for f in files:
    im = pygame.image.load(os.path.join(OUT, f)).convert()
    a = pygame.surfarray.array3d(im).astype(np.int16)
    if prev is not None:
        d = np.abs(a - prev).max(axis=2)
        frac = float((d > 24).mean())
        # how far did the camera move? sample the top strip (sky) vs the middle
        top = a[0:40, :, :].reshape(-1, 3)
        mid = a[HEIGHT // 2 - 20:HEIGHT // 2 + 20, :, :].reshape(-1, 3) if False else a[200:260, :, :].reshape(-1, 3)
        print("%s  maxdiff_px=%d  frac>24=%.3f" % (f, d.max(), frac))
    prev = a
    HEIGHT = a.shape[0]