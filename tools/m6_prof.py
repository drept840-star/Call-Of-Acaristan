import cProfile
import os
import pstats
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

which = "train"
for a in sys.argv[1:]:
    if not a.startswith("-"):
        which = a
N = 24
if which == "train":
    from missions import m6
    from missions.m6 import train3d
    import core.save_system as _save
    _save.select_slot(0)
    m6.start_mission6_train_checkpoint()
    sc = train3d.scene()
    STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1 / 60
        train3d.update(None, (WIDTH // 2, HEIGHT // 2))
        STATE.dt = 0.0
        train3d.draw(surface)
elif which == "yard":
    from missions import m6
    from missions.m6 import yard3d
    import core.save_system as _save
    _save.select_slot(0)
    ys = yard3d.YardScene()
    pygame.key.get_pressed = lambda: [0] * 512
    ys.begin()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1 / 60
        ys.update(None)
        ys.draw(surface)

for _ in range(6):
    step()  # warm
pr = cProfile.Profile()
pr.enable()
for _ in range(N):
    step()
pr.disable()
st = pstats.Stats(pr)
st.sort_stats("cumulative").print_stats(45)
print("\n=== TOTTIME ===")
st.sort_stats("tottime").print_stats(25)
