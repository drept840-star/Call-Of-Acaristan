"""Side-by-side probe: M2 ambush film (sniper3d) vs M5 finale (m5shadow3d).

    python tools/finale_compare.py   # PNGs + metrics -> outputs/finale_compare/
"""
import os, sys, time
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
import numpy as np
import pygame

OUT = "outputs/finale_compare"


def metrics(surf, rect):
    a = pygame.surfarray.array3d(surf.subsurface(rect)).astype(np.float32)
    luma = a[..., 0] * .299 + a[..., 1] * .587 + a[..., 2] * .114
    mx, mn = a.max(-1), a.min(-1)
    sat = np.where(mx > 0, (mx - mn) / np.maximum(mx, 1), 0)
    lap = np.abs(4 * luma[1:-1, 1:-1] - luma[:-2, 1:-1] - luma[2:, 1:-1] - luma[1:-1, :-2] - luma[1:-1, 2:])
    return dict(mean=luma.mean(), std=luma.std(), p5=np.percentile(luma, 5),
                p95=np.percentile(luma, 95), sat=sat.mean(), edge=lap.mean())


def main():
    pygame.init()
    from core.config import WIDTH, HEIGHT, SCENE_TOP, SCENE_BOT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    os.makedirs(OUT, exist_ok=True)
    rows = []
    from missions.m2.sniper3d import SniperCinematic, BAR_H
    c = SniperCinematic()
    total = c.shots[-1][1]
    for i in range(1, 9):
        c.t = total * i / 9
        c.draw(screen); t0 = time.perf_counter(); c.draw(screen); dt = time.perf_counter() - t0
        pygame.image.save(screen, f"{OUT}/m2_{i}.png")
        rows.append(("M2", round(c.t, 1), dt, metrics(screen, pygame.Rect(0, BAR_H, WIDTH, HEIGHT - 2 * BAR_H))))
    from cutscenes import m5shadow3d as m5
    from missions.m5.finale_script import CUTS
    m5.prepare()
    for i, cut in enumerate(CUTS):
        t = cut + 900
        screen.fill((0, 0, 0))
        m5.draw(screen, t); t0 = time.perf_counter(); m5.draw(screen, t); dt = time.perf_counter() - t0
        pygame.image.save(screen, f"{OUT}/m5_{i}_{m5._camera(t)[3]}.png")
        rows.append(("M5", t, dt, metrics(screen, pygame.Rect(0, m5.TOP, WIDTH, m5.BOT - m5.TOP))))
    print("film  t       ms   mean   std    p5    p95   sat   edge")
    for film, t, dt, m in rows:
        print(f"{film}  {t:<7} {dt*1000:5.1f} {m['mean']:6.1f} {m['std']:5.1f} {m['p5']:5.1f} {m['p95']:6.1f} {m['sat']:.3f} {m['edge']:5.2f}")
    for film in ("M2", "M5"):
        ms = [m for f, _, _, m in rows if f == film]
        print(film, "AVG", {k: round(float(np.mean([m[k] for m in ms])), 2) for k in ms[0]})


if __name__ == "__main__":
    main()
