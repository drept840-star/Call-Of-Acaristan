"""Phase-level timing of the M6 train / yard draw (GL path).

Wraps every `_draw_*` / phase helper of the scene with a timer and prints a
per-frame average table, so the Python cost is separated from the FBO
readback (which is timed as its own line).
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
if os.environ.get("ACA_BACKEND"):
    os.environ["ACARISTAN_RENDERER"] = os.environ["ACA_BACKEND"]

import pygame
pygame.init()
surface = pygame.display.set_mode((1000, 700))
from core.config import HEIGHT, WIDTH
from core.state import STATE

which = sys.argv[1] if len(sys.argv) > 1 else "train"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 30

ACC = {}


def wrap(obj, name, label=None):
    fn = getattr(obj, name)
    label = label or name

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            d = (time.perf_counter() - t0) * 1000.0
            e = ACC.setdefault(label, [0, 0.0])
            e[0] += 1
            e[1] += d
    setattr(obj, name, timed)


if which == "train":
    from missions import m6
    from missions.m6 import train3d as T
    import core.save_system as _save
    _save.select_slot(0)
    m6.start_mission6_train_checkpoint()
    sc = T.scene()
    STATE.player.max_hp = STATE.player.hp = 100000
    for n in ("_draw_camera", "_draw_station", "_draw_static_lights",
              "_draw_train_door", "_draw_entrances", "_draw_yard_life",
              "_draw_volkov", "_draw_guards", "_draw_ucilev", "_draw_biribel",
              "_draw_fx", "_draw_death_fx", "_draw_viewmodel", "_draw_yard_wires",
              "_draw_hud", "_flash_lights", "_dynamic_pools", "_eye"):
        wrap(sc, n)
    wrap(T, "_sky", "sky")
    wrap(T, "_light", "light_setup")
    wrap(T, "_grade_play", "grade")
    wrap(T, "_present", "present")
    wrap(T._w, "snow3d", "snow3d")
    wrap(T._w, "static_scene", "static_scene")
    wrap(T._w, "static_end", "static_end")
    wrap(T._w, "rail_platform", "rail_platform")

    def step():
        STATE.dt = 1 / 60
        T.update(None, (WIDTH // 2, HEIGHT // 2))
        STATE.dt = 0.0
        T.draw(surface)
else:
    from missions.m6 import yard3d as Y
    import core.save_system as _save
    _save.select_slot(0)
    ys = Y.YardScene()
    Y.Scene = ys
    sys.modules["missions.m6.yard3d"].Scene = ys
    ys.begin()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000
    for n in ("camera", "_aim_body_yaw", "update"):
        wrap(ys, n)
    wrap(Y.T, "_light", "light_setup")
    wrap(Y.T, "_renderer", "_renderer")

    def step():
        STATE.dt = 1 / 60
        ys.update(None)
        ys.draw(surface)

for _ in range(6):
    step()
for k in ACC:
    ACC[k][:] = [0, 0.0]
t0 = time.perf_counter()
for _ in range(N):
    step()
total = (time.perf_counter() - t0) * 1000.0 / N
print("\n%s: %.2f ms/frame (%.1f fps)" % (which, total, 1000.0 / total))
rows = sorted(ACC.items(), key=lambda kv: -kv[1][1])
for label, (n, s) in rows:
    print("  %-22s %7.2f ms/frame  (%d calls, %.1f%%)"
          % (label, s / N, n, 100.0 * s / (N * total)))
