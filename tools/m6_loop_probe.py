"""Whole-game frame-interval probe for a dev-booted M6 scene.

    SDL_VIDEODRIVER=dummy python tools/m6_loop_probe.py --dev-mission6-train 600

Boots the real game loop (`src/app.py`) with the arguments after the script
name, records the wall time of every frame (the same measurement
``clock.tick(60)`` reports), then prints the distribution and the worst
frames with the phases that were live in them.  Quits by posting QUIT.
"""
import os
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

FRAMES = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 600
argv = [a for a in sys.argv[1:] if not a.isdigit()]
sys.argv = ["app.py"] + argv

import pygame  # noqa: E402

TIMES = []
EVENTS = []
_frame_no = [0]
_orig_get = pygame.event.get

PHASES = {}


def _timed(owner, name):
    fn = getattr(owner, name, None)
    if fn is None:
        return

    def wrapped(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            ms = (time.perf_counter() - t0) * 1000.0
            if ms > 2.0:
                EVENTS.append((_frame_no[0], name, ms))
    setattr(owner, name, wrapped)


def _get(*a, **k):
    _frame_clock()
    _frame_no[0] += 1
    evs = _orig_get(*a, **k)
    if _frame_no[0] >= FRAMES and not getattr(_get, "done", False):
        _get.done = True
        evs = list(evs) + [pygame.event.Event(pygame.QUIT)]
    return evs


pygame.event.get = _get
# The frame interval, sampled at the top of the loop (the event pump runs
# first in the frame): this is what the player sees, tick sleep included.
_last = [time.perf_counter()]


def _frame_clock():
    now = time.perf_counter()
    TIMES.append((now - _last[0]) * 1000.0)
    _last[0] = now

import missions.m6.train3d as T  # noqa: E402
import missions.m6.yard3d as Y  # noqa: E402
import engine3d.gl as G  # noqa: E402

_timed(G.GLRenderer, "flush")
_timed(G.GLRenderer, "flush_overlay")
_timed(G.GLRenderer, "_render")
_timed(G.GLRenderer, "_composite")
_timed(G.GLRenderer, "_draw_rigs")
_timed(G.GLRenderer, "_draw_dyn")
_timed(G.GLRenderer, "_sync_static")
_timed(T.TrainScene, "draw")
_timed(T.TrainScene, "update")
for _ph in ("_draw_guards", "_draw_volkov", "_draw_biribel", "_draw_ucilev",
            "_draw_fx", "_draw_death_fx", "_draw_viewmodel", "_draw_hud",
            "_draw_static_lights", "_draw_station", "_draw_entrances",
            "_draw_yard_life", "_draw_train_door", "_grade_play"):
    _timed(T.TrainScene, _ph)
_timed(T, "_present")
from cutscenes import m6fx3d as _FX  # noqa: E402
_timed(_FX, "apply_lut")
_timed(_FX, "present_crisp")

t0 = time.perf_counter()
try:
    import app  # noqa: F401  (runs the game)
except SystemExit:
    pass
wall = time.perf_counter() - t0

if not TIMES:
    print("no frames recorded")
    raise SystemExit(1)
med = statistics.median(TIMES)
spikes = [(i, t) for i, t in enumerate(TIMES) if t > med * 1.8 and t > 25]
print("\nframes=%d  wall=%.1fs  median=%.1f ms  mean=%.1f  p95=%.1f  p99=%.1f  max=%.1f"
      % (len(TIMES), wall, med, statistics.mean(TIMES),
         sorted(TIMES)[int(0.95 * len(TIMES))],
         sorted(TIMES)[int(0.99 * len(TIMES))], max(TIMES)))
print("frames over 33 ms (below 30 fps): %d   over 50 ms: %d"
      % (sum(1 for t in TIMES if t > 33), sum(1 for t in TIMES if t > 50)))
by = {}
for f, name, ms in EVENTS:
    e = by.setdefault(name, [0, 0.0, 0.0])
    e[0] += 1
    e[1] += ms
    e[2] = max(e[2], ms)
for name, (n, s, mx) in sorted(by.items(), key=lambda kv: -kv[1][2])[:10]:
    print("  %-14s n=%4d total=%8.1f ms worst=%7.1f ms" % (name, n, s, mx))
if spikes:
    print("worst frames:")
    for i, t in sorted(spikes, key=lambda kv: -kv[1])[:10]:
        near = [(n, ms) for f, n, ms in EVENTS if f == i]
        print("  frame %4d %7.1f ms <- %s" % (i, t, ", ".join(
            "%s %.1f" % (n, ms) for n, ms in sorted(near, key=lambda kv: -kv[1])[:4])))
