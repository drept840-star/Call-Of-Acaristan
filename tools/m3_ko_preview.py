"""Capture Kill Order's four directed 3D shots on either backend."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--backend", choices=("gl", "software"), default="gl")
    args = ap.parse_args()
    os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                      ACARISTAN_RENDERER=args.backend, ACARISTAN_CUTSCENE3D="1", ACA_FREEZE="1")
    sys.path.insert(0, str(ROOT / "src"))
    import pygame
    from cutscenes import m3ko3d as film
    out = ROOT / "shots" / "m3_ko3d" / args.backend
    out.mkdir(parents=True, exist_ok=True)
    surf = pygame.Surface((1000, 700))
    n = 0
    for scene in film.SCENES:
        for t in (0, 700, 1149, 1150, 1300, 2000, 2800, 4200, 5400, 12000):
            if not film.draw(scene, surf, t):
                raise RuntimeError(f"{scene}: {film._cache['err']}")
            pygame.image.save(surf, str(out / f"{scene}_{t:05d}.png"))
            n += 1
    print(f"M3 KO 3D: OK ({n} frames, {args.backend}): {out}")


if __name__ == "__main__":
    main()
