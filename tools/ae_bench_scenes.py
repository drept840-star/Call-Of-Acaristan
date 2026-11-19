#!/usr/bin/env python3
"""AE BENCH SCENES - frame bench for the 3D gameplay scenes not covered by
``ae_bench3d`` (office/depot) or ``m6_bench`` (train/yard).

    python tools/ae_bench_scenes.py [all|trap|chase|kill|mansion|flight|ridge|raid|yard|train] \
        [--frames=90] [--backend=auto|gl|software] [--runs=1]

Each scenario boots its scene headless (dummy SDL, fixed 1/60 s dt), runs a
warm-up burst, then times ``update()`` + ``draw()`` onto a 1000x700 surface and
reports avg / p50 / p99 / max in ms and fps. Like the other bench tools this is
a diagnostic, NOT a CI gate; use --runs=3 on a quiet machine and take the best
pass.

Scenes that end during the burst are re-begun so the timer always measures a
live scene rather than an early-out frame.
"""
import collections
import os
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

frames = 90
runs = 1
backend = "auto"
which = "all"
for a in sys.argv[1:]:
    if a.startswith("--frames="):
        frames = int(a.split("=", 1)[1])
    elif a.startswith("--runs="):
        runs = int(a.split("=", 1)[1])
    elif a.startswith("--backend="):
        backend = a.split("=", 1)[1]
    elif not a.startswith("-"):
        which = a
if backend != "auto":
    os.environ["ACARISTAN_RENDERER"] = backend

pygame.init()
surface = pygame.display.set_mode((1000, 700))
from core.state import STATE  # noqa: E402

STATE.dt = 1.0 / 60.0
KEYS = collections.defaultdict(int)


def _trap():
    from missions.m8.revenge import trap3d as M
    STATE.m8_trap_cp = 0
    sc = M.TrapScene()
    sc.begin()

    def step():
        if sc.done:
            sc.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _chase():
    from missions.m8.revenge import chase3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _kill():
    from missions.m8.revenge import kill3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _mansion():
    from missions.m8.duty import mansion3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _flight():
    from missions.m8.duty import flight3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _ridge():
    from missions.m8.duty import ridge3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _train():
    from missions.m6 import train3d as M
    M.begin()

    def step():
        sc = M.scene()
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _raid():
    from missions.m7 import raid3d as M
    STATE.m7_preps = ["tractor", "shed", "loft"]
    STATE.m7_raid_cp = 1
    sc = M.scene()
    M.begin()

    def step():
        if sc.done:
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


def _yard():
    from missions.m6 import yard3d as M
    sc = M.scene()
    M.begin()

    def step():
        if getattr(sc, "done", False):
            M.begin()
        sc.update(KEYS)
        sc.draw(surface)
    return step


SCENES = {
    "trap": _trap,
    "chase": _chase,
    "kill": _kill,
    "mansion": _mansion,
    "flight": _flight,
    "ridge": _ridge,
    "raid": _raid,
    "yard": _yard,
    "train": _train,
}


def _stats(name, samples, backend_name):
    s = sorted(samples)
    avg = statistics.mean(s)
    print("AE BENCH SCENES %-10s avg=%7.2f ms  p50=%7.2f  p99=%7.2f  max=%7.2f  "
          "(%6.1f fps) (%s, %d frames)" % (
              name, avg, s[len(s) // 2], s[min(len(s) - 1, int(0.99 * len(s)))],
              s[-1], 1000.0 / avg, backend_name, len(s)))
    return avg


def main():
    names = list(SCENES) if which == "all" else [which]
    if any(n not in SCENES for n in names):
        print("unknown scene; choose from: all " + " ".join(SCENES), file=sys.stderr)
        return 2
    for name in names:
        try:
            step = SCENES[name]()
        except Exception as exc:
            print("AE BENCH SCENES %-10s SKIP (%s)" % (name, exc))
            continue
        step()  # warm caches / baked set
        best = None
        for run in range(runs):
            samples = []
            for _ in range(frames):
                t0 = time.perf_counter()
                step()
                samples.append((time.perf_counter() - t0) * 1000.0)
            stat = statistics.mean(samples)
            if run:
                print("AE BENCH SCENES %-10s run %d/%d avg=%.2f ms" % (
                    name, run + 1, runs, stat))
            if best is None or stat < best:
                best = stat
        from engine3d import gl_available
        actual = "gl" if gl_available() and backend != "software" else "software"
        _stats(name, samples, actual)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
