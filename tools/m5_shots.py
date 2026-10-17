"""M5 3D cutscene stills + timing: python tools/m5_shots.py OUT_DIR [scene_prefix]

Renders every take in m5martial3d.M5_3D_SCENES and m5mid3d.M5X_SCENES at a few
timestamps into OUT_DIR/<scene>_<t>.png, then prints ms/frame per take.
Backend follows ACARISTAN_RENDERER (auto|gl|software). Also writes a contact
sheet OUT_DIR/_sheet.jpg (one row per take).
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

pygame.init()
from core.config import *  # noqa: E402,F401,F403
from cutscenes import m5martial3d as m3d  # noqa: E402
from cutscenes import m5mid3d as mid  # noqa: E402

# take lengths (ms) for the round-1 takes; m5x_* use DEFAULT
DUR = {"m5_tv_bulletin": 6400, "m5_safehouse_tv": 7200, "m5_retardovici_tv": 7400,
       "m5_river_gate": 7200, "m5_ucilev_scope": 9200, "m5_ucilev_reveal": 8400,
       "m5_ucilev_leaves": 6800, "m5_radio": 8800}
DEFAULT = 5200
FRACS = (0.06, 0.4, 0.7, 0.95)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "shots", "m5")
    pref = sys.argv[2] if len(sys.argv) > 2 else ""
    os.makedirs(out, exist_ok=True)
    surf = pygame.Surface((WIDTH, HEIGHT))
    takes = [(k, (lambda f: (lambda s, t: f(s, t)))(v)) for k, v in m3d.M5_3D_SCENES.items()]
    takes += [(k, (lambda f: (lambda s, t: f(s, t)))(v)) for k, v in mid.M5X_SCENES.items()]
    takes = [tk for tk in takes if tk[0].startswith(pref)]
    tw, th = 320, 180
    sheet = pygame.Surface((tw * len(FRACS), th * len(takes)))
    timing = []
    for row, (name, fn) in enumerate(takes):
        dur = DUR.get(name, DEFAULT)
        for col, f in enumerate(FRACS):
            t = int(dur * f)
            fn(surf, t)
            pygame.image.save(surf, os.path.join(out, "%s_%05d.png" % (name, t)))
            sheet.blit(pygame.transform.smoothscale(surf, (tw, th)), (col * tw, row * th))
        n = 12
        t0 = time.perf_counter()
        for i in range(n):
            fn(surf, int(dur * 0.5) + i * 16)
        ms = (time.perf_counter() - t0) * 1000.0 / n
        timing.append((name, ms))
    pygame.image.save(sheet, os.path.join(out, "_sheet.jpg"))
    if m3d._cache.get("failed"):
        print("3D FAILED:", repr(m3d._cache.get("err")))
    r, _buf = m3d._rend()
    print("backend:", getattr(r, "backend", "?"))
    for name, ms in timing:
        print("%-24s %7.1f ms/frame  (%5.1f fps)" % (name, ms, 1000.0 / ms))


if __name__ == "__main__":
    main()
