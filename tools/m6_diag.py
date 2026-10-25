"""One-command M6 3D performance diagnostic - run this on the stuttering PC.

    python tools/m6_diag.py                 # train scene, 400 frames
    python tools/m6_diag.py yard            # the yard fight
    python tools/m6_diag.py train 600 --real-window
    python tools/m6_diag.py train 400 --auto   # with the adaptive path on
    python tools/m6_diag.py --report           # one playthrough, writes m6_report.txt

Everything is also written to ``m6_report.txt`` in the repo root; send that
file back instead of a screenshot.

Prints the machine (CPU, GPU backend, GL renderer string), the resolved
render tier, a per-phase frame table for the scene's own draw, the frame
distribution and every hitch over 3x the median (with the phases that were
live).  Copy the whole output back; nothing here touches saves.
"""
import os
import platform
import statistics
import sys
import time

os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "src"))

real_window = "--real-window" in sys.argv
if "--auto" in sys.argv:
    os.environ["ACA_M6_AUTO"] = "1"
if not real_window:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
args = [a for a in sys.argv[1:] if not a.startswith("--")]
which = args[0] if args else "train"
N = int(args[1]) if len(args) > 1 else 400

import pygame  # noqa: E402

_REPORT = []

pygame.init()
surface = pygame.display.set_mode((1000, 700))
from core.config import HEIGHT, WIDTH  # noqa: E402
from core.state import STATE  # noqa: E402
from missions.m6 import perf  # noqa: E402

print("=" * 66)
print("machine   :", platform.platform(), "|", platform.processor() or "?", "|",
      os.cpu_count(), "cpus")
print("python    :", platform.python_version(), "| pygame", pygame.version.ver)
try:
    from engine3d import gl_available, gl_info
    print("GL avail  :", gl_available(), "|", gl_info())
except Exception as exc:
    print("GL avail  : error", exc)
try:
    from core.user_settings import SETTINGS
    print("quality_3d:", SETTINGS.quality_3d)
except Exception:
    pass
print("=" * 66)

PHASES = {}


def _wrap(owner, name, label=None):
    fn = getattr(owner, name, None)
    if fn is None:
        return
    label = label or name

    def timed(*a, **k):
        t0 = time.perf_counter()
        try:
            return fn(*a, **k)
        finally:
            ms = (time.perf_counter() - t0) * 1000.0
            e = PHASES.setdefault(label, [0, 0.0])
            e[0] += 1
            e[1] += ms
            perf.note_phase(label, ms)
    setattr(owner, name, timed)


_real_print = print


def print(*a, **k):          # noqa: A001 - tee to the report file
    _real_print(*a, **k)
    _REPORT.append(" ".join(str(x) for x in a))


if which == "train":
    from missions import m6
    from missions.m6 import train3d as T
    import core.save_system as _save
    _save.select_slot(0)
    m6.start_mission6_train_checkpoint()
    sc = T.scene()
    if STATE.player is not None:
        STATE.player.max_hp = STATE.player.hp = 100000

    def step():
        STATE.dt = 1 / 60
        T.update(None, (WIDTH // 2, HEIGHT // 2))
        STATE.dt = 0.0
        T.draw(surface)

    for n in ("_draw_guards", "_draw_volkov", "_draw_biribel", "_draw_fx",
              "_draw_viewmodel", "_draw_hud", "_draw_static_lights",
              "_draw_station", "_grade_play", "_eye"):
        _wrap(sc, n)
    _wrap(T, "_present")
    _wrap(T, "_sky")
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

    for n in ("_draw_player", "camera"):
        _wrap(ys, n)

from engine3d.gl import GLRenderer  # noqa: E402

for n in ("flush", "flush_overlay", "_composite", "_draw_rigs", "_draw_dyn",
          "_sync_static"):
    _wrap(GLRenderer, n)

if which == "train":
    r = T._renderer()
else:
    r = T._renderer() if False else None
    from missions.m6 import train3d as T  # noqa: E402
    r = T._renderer()

for _ in range(60):
    step()
for k in PHASES:
    PHASES[k][:] = [0, 0.0]

times = []
for _ in range(N):
    t0 = time.perf_counter()
    step()
    times.append((time.perf_counter() - t0) * 1000.0)

med = statistics.median(times)
print("\nrenderer  : %s  buffer=%s  resolved scale=%.2f"
      % (type(r).__name__, r.surface.get_size(), perf.scale()))
print("frames    : %d   median %.1f ms   mean %.1f   p95 %.1f   p99 %.1f   max %.1f"
      % (N, med, statistics.mean(times),
         sorted(times)[int(0.95 * N)], sorted(times)[int(0.99 * N)], max(times)))
print("over 33 ms: %d (%.0f%%)    over 50 ms: %d    over 100 ms: %d"
      % (sum(1 for t in times if t > 33), 100.0 * sum(1 for t in times if t > 33) / N,
         sum(1 for t in times if t > 50), sum(1 for t in times if t > 100)))
print("\nper-frame phases (avg over %d frames):" % N)
for label, (n, s) in sorted(PHASES.items(), key=lambda kv: -kv[1][1])[:14]:
    print("  %-20s %7.2f ms/frame  (%d calls)" % (label, s / N, n))
spikes = [(i, t) for i, t in enumerate(times) if t > med * 3 and t > 40]
if spikes:
    print("\nhitches (> 3x median):")
    for i, t in spikes[:12]:
        print("  frame %4d  %7.1f ms" % (i, t))
print("\nsession hitch log:", os.path.join("build", "m6_hitches.log"))
print("=" * 66)
try:
    with open(os.path.join(ROOT, "m6_report.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(_REPORT) + "\n")
    _real_print("report written to m6_report.txt")
except Exception as exc:
    _real_print("could not write report:", exc)
