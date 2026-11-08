"""Capture the M3 broadcast bridge, including action endpoints and long holds."""
import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("gl", "software"), default="gl")
    args = parser.parse_args()
    os.environ.update(SDL_VIDEODRIVER="dummy", SDL_AUDIODRIVER="dummy",
                      ACARISTAN_RENDERER=args.backend, ACARISTAN_CUTSCENE3D="1", ACA_FREEZE="1")
    sys.path.insert(0, str(ROOT / "src"))
    import pygame
    from cutscenes import m3broadcast3d as film
    out = ROOT / "shots" / "m3_broadcast3d" / args.backend
    out.mkdir(parents=True, exist_ok=True)
    surface = pygame.Surface((1000, 700))
    sheet = pygame.Surface((1000, 5 * 226))
    for i, scene in enumerate(film.SCENES):
        for t in (0, 450, 900, 1300, 2200, 3400, 6000, 16000):
            if not film.draw(scene, surface, t):
                raise RuntimeError(f"{scene}: {film._cache['err']}")
            pygame.image.save(surface, str(out / f"{scene}_{t:05d}.png"))
            if t in (900, 3400):
                crop = surface.subsurface((0, film.TOP, 1000, film.BOTTOM - film.TOP))
                sheet.blit(pygame.transform.scale(crop, (500, 226)), (0 if t == 900 else 500, i * 226))
    pygame.image.save(sheet, str(out / "contact_sheet.png"))
    print(f"M3 BROADCAST 3D: OK (40 frames, {args.backend}): {out}")


if __name__ == "__main__":
    main()
