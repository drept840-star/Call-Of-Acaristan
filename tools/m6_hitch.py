"""Hitch hunter for the M6 3D scenes.

Runs a scene for N frames, records per-frame wall time, then re-runs it with
phase timers armed around every draw phase and reports, for the frames that
spiked (> 1.6x median), which phases and which side effects (rig template
builds, set bakes, memo re-packs, GC, audio loads) were live in them.
"""
import gc
import os
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

import pygame  # noqa: E402

pygame.init()
surface = pygame.display.set_mode((1000, 700))
from core.config import HEIGHT, WIDTH  # noqa: E402
from core.state import STATE  # noqa: E402

which = sys.argv[1] if len(sys.argv) > 1 else "train"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 600
if os.environ.get("ACA_BACKEND"):
    os.environ["ACARISTAN_RENDERER"] = os.environ["ACA_BACKEND"]

EVENTS = []          # (frame, label, ms)


def note(label, ms):
    EVENTS.append((CUR[0], label, ms))


CUR = [0]

if which == "train":
    from missions import m6
    from missions.m6 import train3d as T
    import core.save_system as _save
    _save.select_slot(0)
    m6.start_mission6_train_checkpoint()
    sc = T.scene()
    STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1 / 60
        T.update(None, (WIDTH // 2, HEIGHT // 2))
        STATE.dt = 0.0
        T.draw(surface)

    obj = sc
    PHASES = ("_draw_camera", "_draw_station", "_draw_static_lights",
              "_draw_train_door", "_draw_entrances", "_draw_yard_life",
              "_draw_volkov", "_draw_guards", "_draw_ucilev", "_draw_biribel",
              "_draw_fx", "_draw_death_fx", "_draw_viewmodel", "_draw_yard_wires",
              "_draw_hud", "_flash_lights", "_dynamic_pools", "_eye")
    mod = T
else:
    from missions.m6 import yard3d as Y
    import core.save_system as _save
    _save.select_slot(0)
    ys = Y.YardScene()
    ys.begin()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1 / 60
        ys.update(None)
        ys.draw(surface)

    obj = ys
    PHASES = ("_draw_player", "_update_guards", "camera", "_update_waves")
    mod = Y


def instrument():
    def wrap(owner, name):
        fn = getattr(owner, name, None)
        if fn is None:
            return
        def timed(*a, **k):
            t0 = time.perf_counter()
            try:
                return fn(*a, **k)
            finally:
                ms = (time.perf_counter() - t0) * 1000.0
                if ms > 1.0:
                    note(name, ms)
        setattr(owner, name, timed)

    for n in PHASES:
        wrap(obj, n)
    wrap(mod, "_sky")
    wrap(mod, "_light")
    for n in ("rail_platform", "static_scene", "static_end", "pack_memo",
              "pack_memo_end", "pack_memo_replay", "snow3d", "_memo_add"):
        wrap(T._w if which == "train" else T._w, n)
    wrap(T, "_grade_play")
    wrap(T, "_present")
    wrap(T, "_hum")
    from engine3d import rig
    wrap(rig.Humanoid, "build")
    from engine3d.gl import GLRenderer
    wrap(GLRenderer, "_sync_static")
    wrap(GLRenderer, "_draw_rigs")
    wrap(GLRenderer, "_draw_dyn")
    wrap(GLRenderer, "flush")
    wrap(GLRenderer, "flush_overlay")


def run(n, collect_events):
    times = []
    del EVENTS[:]
    for i in range(n):
        CUR[0] = i
        gc_was = gc.get_count()[0]
        t0 = time.perf_counter()
        step()
        ms = (time.perf_counter() - t0) * 1000.0
        times.append(ms)
        if collect_events:
            if ms > 30.0:
                note("FRAME", ms)
            if gc.get_count()[0] < gc_was:
                note("GC(GEN0)", 0.0)
    return times


# warm
run(80, False)
import engine3d.gl as G
print("renderer:", type(G.Renderer(64, 64)).__name__,
      "| buffer:", T._renderer().surface.get_size() if which == "train" else "?")
median = statistics.median(run(N, False))
gc.collect()
gc.disable()
instrument()
times = run(N, True)
gc.enable()
spikes = [(i, t) for i, t in enumerate(times) if t > median * 1.6]
print("frames=%d  median=%.2f ms  mean=%.2f  p99=%.2f  max=%.2f  spikes>1.6x: %d"
      % (N, median, statistics.mean(times),
         sorted(times)[int(0.99 * len(times))], max(times), len(spikes)))
by_label = {}
for f, label, ms in EVENTS:
    e = by_label.setdefault(label, [0, 0.0, 0.0])
    e[0] += 1
    e[1] += ms
    e[2] = max(e[2], ms)
print("\nevents during the run (only entries > 1 ms):")
for label, (n, s, mx) in sorted(by_label.items(), key=lambda kv: -kv[1][2])[:18]:
    print("  %-18s n=%4d  total=%8.1f ms  worst=%7.1f ms" % (label, n, s, mx))
print("\nthe 12 worst frames:")
for i, t in sorted(spikes, key=lambda kv: -kv[1])[:12]:
    near = [(lab, ms) for f, lab, ms in EVENTS if f == i]
    print("  frame %4d  %7.1f ms  <- %s" % (i, t, ", ".join(
        "%s %.1f" % (lab, ms) for lab, ms in sorted(near, key=lambda kv: -kv[1])[:6])))
