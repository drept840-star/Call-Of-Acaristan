"""Headless shots of the 3D "666" scare.

    python tools/egg666_shots.py [OUT_DIR] [--seed=N] [--at=T1,T2,...] [--lit] [--time]

Renders the scare's frames (default out dir shots/egg666) through the real
egg666_3d module, one PNG per time plus a contact sheet ``_sheet.jpg``.
Times are seconds; ``--at`` defaults to the beat sheet 0,1.5,3,5,6.5,8.
``--lit`` uses a denser set that lands on lit frames, ``--time`` renders all
540 frames in order and prints the per-frame cost.  Run from the repo root;
needs the GL renderer (exit 1 otherwise).  ``ui/__init__`` is stubbed so the
whole menu stack is not imported.
"""
import os
import sys
import time
import types

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
if "ui" not in sys.modules:
    _ui = types.ModuleType("ui")
    _ui.__path__ = [os.path.join(ROOT, "src", "ui")]
    sys.modules["ui"] = _ui
from ui import egg666_3d as egg  # noqa: E402

SIZE = (1000, 700)
BEATS = (0.0, 1.5, 3.0, 5.0, 6.5, 8.0)
LIT = (0.7, 1.0, 1.7, 2.3, 2.9, 3.4, 3.75, 4.3, 4.6, 5.0, 5.5, 6.0, 6.4, 6.6, 6.9, 7.2,
       7.35, 7.4, 7.5, 7.7, 8.1, 8.4)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    opt = {a.split("=")[0]: a.split("=")[1] if "=" in a else "" for a in sys.argv[1:] if a.startswith("--")}
    out = args[0] if args else os.path.join(ROOT, "shots", "egg666")
    os.makedirs(out, exist_ok=True)
    seed = int(opt.get("--seed", 4242))
    if not egg.begin(seed, SIZE, sound=False):
        print("egg666: the 3D scare is unavailable here (no GL?)")
        return 1
    screen = pygame.Surface(SIZE)
    if "--time" in opt:
        ms = []
        for f in range(egg.TOTAL):
            t0 = time.perf_counter()
            egg.frame(screen, f)
            ms.append((time.perf_counter() - t0) * 1000.0)
        lit = [m for m in ms if m > 1.0]
        print("frames %d  avg %.1f ms  max %.1f ms (frame %d)  lit avg %.1f ms  over 16.7 ms: %d" % (
            len(ms), sum(ms) / len(ms), max(ms), ms.index(max(ms)), sum(lit) / max(1, len(lit)),
            sum(1 for m in ms if m > 16.7)))
        egg.stop()
        return 0
    times = [float(x) for x in opt["--at"].split(",") if x] if opt.get("--at") else (LIT if "--lit" in opt else BEATS)
    frames = []
    for t in times:
        f = min(egg.TOTAL - 1, int(round(t * 60)))
        if not egg.frame(screen, f):
            print("egg666: frame %d failed" % f)
            return 1
        name = "egg666_%s_f%03d.png" % (opt.get("--seed", "4242"), f)
        pygame.image.save(screen, os.path.join(out, name))
        frames.append((f, screen.copy()))
        print(name)
    cols = 4
    tw, th = SIZE[0] // 3, SIZE[1] // 3
    sheet = pygame.Surface((cols * tw, ((len(frames) + cols - 1) // cols) * th))
    font = pygame.font.Font(None, 22)
    for i, (f, surf) in enumerate(frames):
        x, y = (i % cols) * tw, (i // cols) * th
        sheet.blit(pygame.transform.smoothscale(surf, (tw, th)), (x, y))
        sheet.blit(font.render("f%d  %.2fs" % (f, f / 60.0), True, (255, 255, 0)), (x + 6, y + 4))
    pygame.image.save(sheet, os.path.join(out, "_sheet.jpg"))
    egg.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
