"""Diagnostic: render the M5 squadmate handshake at key beats, report draw
count / frame time / wrist gap, and save a contact sheet.
Usage: python previews/handshake_probe.py [tag] [--b64]"""
import os, sys, math, time, base64
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pygame
pygame.init()
from core.config import WIDTH, HEIGHT
pygame.display.set_mode((WIDTH, HEIGHT))
from cutscenes import m5mid3d as M
from engine3d.core import SoftwareRenderer

tag = sys.argv[1] if len(sys.argv) > 1 else "probe"
calls = []
_orig = SoftwareRenderer.add_humanoid
def spy(self, hum, pose, pos, yaw, **kw):
    j = _orig(self, hum, pose, pos, yaw, **kw)
    calls.append(j)
    return j
SoftwareRenderer.add_humanoid = spy

surf = pygame.Surface((WIDTH, HEIGHT))
out = os.path.join(os.path.dirname(__file__), "handshake")
os.makedirs(out, exist_ok=True)
frames = []
for t in (0, 700, 1150, 1450, 1950, 3200):
    calls.clear()
    t0 = time.perf_counter()
    M._squadmate(surf, t)
    dt = (time.perf_counter() - t0) * 1000
    gap = math.dist(calls[0]["rhand"], calls[1]["rhand"]) if len(calls) >= 2 else -1
    print(f"t={t:5d} draws={len(calls)} frame={dt:6.1f}ms gap={gap:.3f}m failed={M._m3d._cache['failed']} {M._m3d._cache.get('err','')}")
    frames.append(surf.copy())
w, h = 640, int(640 * HEIGHT / WIDTH)
sheet = pygame.Surface((w * 2, h * 3))
for i, f in enumerate(frames):
    sheet.blit(pygame.transform.smoothscale(f, (w, h)), ((i % 2) * w, (i // 2) * h))
p = os.path.join(out, f"{tag}_sheet.jpg")
pygame.image.save(sheet, p)
if "--b64" in sys.argv:
    print("B64" + base64.b64encode(open(p, "rb").read()).decode())
