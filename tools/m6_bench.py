"""M6 3D scene frame bench + profile (diagnostic, not a CI gate).

    python tools/m6_bench.py [train|yard|yardc|films|all] [--frames=N]
                             [--profile] [--backend=auto|gl|software]

Times the M6 3D scenes the way they run in the game: a fixed dt step
(1/60 s) of update() followed by one draw() onto a 1000x700 surface, and
reports avg / p50 / p99 / max over N frames, plus an optional cProfile
cumulative table.
"""
import os
import statistics
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

backend = "auto"
frames = 90
do_profile = False
which = "all"
for a in sys.argv[1:]:
    if a.startswith("--frames="):
        frames = int(a.split("=", 1)[1])
    elif a.startswith("--backend="):
        backend = a.split("=", 1)[1]
    elif a == "--profile":
        do_profile = True
    elif not a.startswith("-"):
        which = a
if backend != "auto":
    os.environ["ACARISTAN_RENDERER"] = backend

pygame.init()
surface = pygame.display.set_mode((1000, 700))

from core.config import HEIGHT, WIDTH  # noqa: E402
from core.state import STATE  # noqa: E402


def _stats(name, samples, extra=""):
    samples = sorted(samples)
    n = len(samples)
    avg = statistics.mean(samples)
    p50 = samples[n // 2]
    p99 = samples[min(n - 1, int(0.99 * n))]
    print("M6 BENCH %-14s avg=%6.2f ms  p50=%6.2f  p99=%6.2f  max=%6.2f  "
          "(%.1f fps) %s" % (name, avg, p50, p99, samples[-1], 1000.0 / avg, extra))
    return avg


def _timer(fn, n):
    fn()  # warm
    out = []
    for _ in range(n):
        t0 = time.perf_counter()
        fn()
        out.append((time.perf_counter() - t0) * 1000.0)
    return out


def bench_train():
    from missions import m6
    from missions.m6 import train3d
    import core.save_system as _save
    try:
        _save.select_slot(0)
    except Exception:
        pass
    m6.start_mission6_train_checkpoint()
    sc = train3d.scene()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1.0 / 60.0
        train3d.update(None, (WIDTH // 2, HEIGHT // 2))
        STATE.dt = 0.0
        train3d.draw(surface)

    samples = _timer(step, frames)
    r = train3d._renderer()
    _stats("train", samples, "clock=%.1fs guards=%d buffer=%dx%d"
           % (sc.t, len(sc.guards), r.w, r.h))
    if train3d.active():
        train3d.force_finish("tool")
    return samples


def bench_yard(close=False):
    from missions import m6
    from missions.m6 import yard3d
    import core.save_system as _save
    try:
        _save.select_slot(0)
    except Exception:
        pass
    from missions.m6.yard3d import YardScene
    ys = YardScene()
    ys.begin()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1.0 / 60.0
        ys.update(None)
        ys.draw(surface)

    samples = _timer(step, frames)
    r = train3d_renderer()
    _stats("yard" + ("_close" if close else ""), samples,
           "guards=%d buffer=%s" % (len(getattr(ys, "guards", ())),
                                    "%dx%d" % r.surface.get_size() if r else "?"))
    return samples


def train3d_renderer():
    from missions.m6 import train3d
    try:
        return train3d._renderer()
    except Exception:
        return None


def bench_films():
    """The three M6 engine3d films (insertion / boxcar / ending) per frame."""
    import json
    from core.cutscene_registry import scene_renderer, set_current_shot
    from cutscenes import m6films  # noqa: F401
    from missions.m6 import meta
    groups = {
        "insertion": [s for s in meta.mission6_intro_shots if s["scene"] != "title_card"],
        "boxcar": [s for s in meta.M6_MID_CUTSCENES["boxcar"] if s["scene"] != "title_card"],
        "ending": [s for s in meta.mission6_ending_shots if s["scene"] != "title_card"],
    }
    out = []
    for name, shots in groups.items():
        shot = shots[len(shots) // 2]
        set_current_shot(shot)
        fn = scene_renderer(shot["scene"])
        t = shot.get("dur", 4.0) * 0.5
        samples = _timer(lambda: fn(surface, t * 1000.0), max(20, frames // 3))
        _stats("film_" + name, samples, shot["scene"])
        out += samples
    return out


def main():
    print("renderer:", end=" ")
    from engine3d import Renderer
    r = Renderer(64, 64)
    print(type(r).__name__, "| window %dx%d" % (WIDTH, HEIGHT))
    jobs = []
    if which in ("train", "all"):
        jobs.append(("train", bench_train))
    if which in ("yard", "all"):
        jobs.append(("yard", lambda: bench_yard(False)))
    if which in ("films", "all"):
        jobs.append(("films", bench_films))
    for name, fn in jobs:
        if do_profile:
            import cProfile
            import pstats
            pr = cProfile.Profile()
            pr.enable()
            fn()
            pr.disable()
            st = pstats.Stats(pr)
            st.sort_stats("tottime").print_stats(28)
        else:
            fn()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
