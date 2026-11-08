"""Capture M3's service bridge: python tools/m3_staging_preview.py [--backend software]."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("gl", "software"), default="gl")
    args = parser.parse_args()
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    os.environ["ACARISTAN_RENDERER"] = args.backend
    os.environ["ACARISTAN_CUTSCENE3D"] = "1"
    os.environ["ACA_FREEZE"] = "1"
    sys.path.insert(0, str(ROOT / "src"))
    import pygame
    from cutscenes import m3staging as film

    out = ROOT / "shots" / "m3_staging" / args.backend
    out.mkdir(parents=True, exist_ok=True)
    surf = pygame.Surface((1000, 700))
    count = 0
    for i, scene in enumerate(film.SCENES):
        times = (0, 280, 440, 620, 800, 980, 1100, 1200, 1600, 3000, 12000)
        for t in times:
            if not film.draw(scene, surf, t):
                raise RuntimeError(f"3D take failed: {scene}: {film._cache['err']}")
            pygame.image.save(surf, str(out / f"{i:02d}_{scene}_{t:05d}.png"))
            count += 1
    r = film._cache["renderer"][0]
    print(f"M3 STAGING: OK ({r.backend}, {count} frames): {out}")


if __name__ == "__main__":
    main()
