"""GPU vs software renderer check on the real M2 ambush film.

    python tools/engine3d_check.py            # parity + speed report
    python tools/engine3d_check.py --shots    # also save side-by-side PNGs to outputs/engine3d/
    python tools/engine3d_check.py --stress   # 60-soldier crowd benchmark

Renders the same frames of missions/m2/sniper3d.py with both engine3d
backends, reports per-frame time and how many pixels differ. Exit code 1 if
the GPU backend is unavailable or a frame differs on more than MAX_DIFF of
its pixels (small differences are expected: per-pixel depth/fog instead of
per-face sorting).
"""
import os
import sys
import time

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

import numpy as np  # noqa: E402
import pygame  # noqa: E402

MAX_DIFF = 0.06          # fraction of pixels allowed to differ by > TOL
TOL = 24                 # per-channel tolerance


def main():
    pygame.init()
    from core.config import WIDTH, HEIGHT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    import engine3d
    info = engine3d.gl_info()
    print("GL:", info)
    if not info["available"]:
        return 1
    from missions.m2.sniper3d import SniperCinematic
    cines = {}
    for mode in ("software", "gl"):
        os.environ["ACARISTAN_RENDERER"] = mode
        cines[mode] = SniperCinematic()
        print(mode, "->", type(cines[mode].r).__name__)
    os.environ.pop("ACARISTAN_RENDERER", None)
    total = cines["software"].shots[-1][1]
    times = [total * k / 24 for k in range(1, 24)]
    shots = "--shots" in sys.argv
    if shots:
        os.makedirs("outputs/engine3d", exist_ok=True)
    worst, ok = 0.0, True
    tsum = {"software": 0.0, "gl": 0.0}
    for i, t in enumerate(times):
        frames = {}
        for mode, c in cines.items():
            c.t = t
            c.draw(screen)                # warm (first-use caches)
            t0 = time.perf_counter()
            for _ in range(3):
                c.draw(screen)
            tsum[mode] += (time.perf_counter() - t0) / 3
            frames[mode] = pygame.surfarray.array3d(c.r.surface).astype(np.int16)
        d = np.abs(frames["software"] - frames["gl"]).max(axis=2)
        frac = float((d > TOL).mean())
        worst = max(worst, frac)
        ok &= frac <= MAX_DIFF
        if shots:
            a = cines["software"].r.surface; b = cines["gl"].r.surface
            out = pygame.Surface((a.get_width() * 2 + 4, a.get_height()))
            out.blit(a, (0, 0)); out.blit(b, (a.get_width() + 4, 0))
            pygame.image.save(out, "outputs/engine3d/frame_%02d.png" % i)
        print("t=%6.2fs  diff=%5.2f%%  tris=%s" % (t, frac * 100, cines["gl"].r.stats.get("tris")))
    n = len(times)
    sw, gl = tsum["software"] / n * 1000, tsum["gl"] / n * 1000
    print("avg frame: software %.1f ms | gl %.1f ms | x%.1f" % (sw, gl, sw / gl))
    print("worst pixel diff: %.2f%%  ->  %s" % (worst * 100, "OK" if ok else "FAIL"))
    return 0 if ok else 1




def stress(n_actors=60, frames=10):
    """Crowd benchmark: n_actors soldiers on the M2 set, both backends."""
    import math
    pygame.init()
    from core.config import WIDTH, HEIGHT
    pygame.display.set_mode((WIDTH, HEIGHT))
    from engine3d import GLRenderer, SoftwareRenderer, Humanoid, pose_run
    from missions.m2 import sniper3d_set as SET
    from missions.m2.sniper3d import SPECS
    specs = list(SPECS.values())
    res = {}
    for cls in (SoftwareRenderer, GLRenderer):
        r = cls(WIDTH // 2, HEIGHT // 2, fog=(88, 90, 98), fog_start=14.0, fog_end=190.0)
        SET.build(r)
        crowd = [Humanoid(specs[i % len(specs)]) for i in range(n_actors)]
        t0 = time.perf_counter()
        for f in range(frames):
            r.set_camera((0, 6, -18), (0, 1, 20), 60)
            r.surface.fill((40, 44, 52))
            r.begin(); r.add_static()
            for i, h in enumerate(crowd):
                x = (i % 10 - 4.5) * 2.2
                z = (i // 10) * 3.0 + f * 0.2
                r.add_humanoid(h, pose_run(f * 0.3 + i), (x, 0, z), 0.0, rifle_on=True)
            r.flush(r.surface)
        res[cls.__name__] = (time.perf_counter() - t0) / frames * 1000
        if cls is GLRenderer:
            pygame.image.save(r.surface, "outputs/engine3d/stress_gl.png")
    print("stress %d actors: software %.1f ms | gl %.1f ms | x%.1f" % (
        n_actors, res["SoftwareRenderer"], res["GLRenderer"],
        res["SoftwareRenderer"] / res["GLRenderer"]))


if __name__ == "__main__" and "--stress" in sys.argv:
    stress()
elif __name__ == "__main__":
    sys.exit(main())
