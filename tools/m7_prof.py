"""Profile the Mission 7 raid frame headless.

    python tools/m7_prof.py [w1|w2|w3] [--time] [--play]

Starts the raid, skips to the named wave, lets it play out a little, then
profiles update + draw.  ``--time`` prints ms/frame instead of the profile;
``--play`` runs, sweeps the look, fires and aims.
"""
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
from core.state import STATE
import core.save_system as _save
_save.select_slot(0)
from missions import m7  # noqa: F401  (mission load order)
from missions.m7 import raid3d

args = [a for a in sys.argv[1:] if not a.startswith("-")]
wave = int((args[0] if args else "w2")[-1])
STATE.m7_preps = ["tractor", "shed", "loft"]
STATE.m7_raid_cp = wave - 1
sc = raid3d.scene()
sc.begin()
keys = __import__("collections").defaultdict(int)


PLAY = "--play" in sys.argv
frame = [0]


def step():
    STATE.dt = 1 / 60
    if PLAY:    # run in circles, sweep the look, hold the trigger, aim now and then
        import math
        i = frame[0] = frame[0] + 1
        keys[pygame.K_w] = 1
        keys[pygame.K_LSHIFT] = 1 if (i // 200) % 2 else 0
        sc.yaw = (sc.yaw + 1.2) % 360.0
        sc.pitch = 20.0 * math.sin(i * 0.03) - 5.0
        sc.firing = (i // 90) % 2 == 0
        sc.aiming = (i // 150) % 2 == 1
    if STATE.player is not None:
        STATE.player.hp = 100000
    sc.update(keys)
    sc.draw(surface)


for _ in range(int(60 * 8)):    # into the wave: trucks arrive, men dismount
    step()
    if sc.done:
        break
print("phase", sc.phase, "enemies", sum(1 for e in sc.brain.enemies if e["live"]))
if "--time" in sys.argv:
    ms = []
    for _ in range(600):
        t0 = time.perf_counter()
        step()
        ms.append((time.perf_counter() - t0) * 1000)
    ms.sort()
    print("ms/frame mean %.2f  p50 %.2f  p99 %.2f  max %.2f  (%d frames)" % (
        sum(ms) / len(ms), ms[len(ms) // 2], ms[int(len(ms) * 0.99)], ms[-1], len(ms)))
    sys.exit(0)
pr = cProfile.Profile()
pr.enable()
for _ in range(60):
    step()
pr.disable()
st = pstats.Stats(pr)
st.sort_stats("cumulative").print_stats(50)
print("\n=== TOTTIME ===")
st.sort_stats("tottime").print_stats(30)
if "--callers" in sys.argv:
    st.print_callers("smoothscale|draw.line|transform.scale|Surface. objects|read_into|tobytes")
