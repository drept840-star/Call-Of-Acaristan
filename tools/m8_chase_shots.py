"""Render the M8 tractor chase at points along the route, for eyeballing the set.

    python tools/m8_chase_shots.py [--software] [--out=outputs/m8_chase]

Writes one PNG per sampled z (plus a strip of them) so the background can be
compared section by section.
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)

if "--software" in sys.argv:
    os.environ["ACARISTAN_RENDERER"] = "software"

import pygame  # noqa: E402

OUT = "outputs/m8_chase"
for a in sys.argv:
    if a.startswith("--out="):
        OUT = a.split("=", 1)[1]


def main():
    pygame.init()
    from core.config import WIDTH, HEIGHT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    from missions.m8.revenge import chase3d as C
    sc = C.scene()
    sc.begin()
    sc.t = 4.0
    os.makedirs(OUT, exist_ok=True)
    zs = [float(a.split("=", 1)[1]) for a in sys.argv if a.startswith("--z=")] or [
        60.0, 200.0, 340.0, 420.0, 560.0, 680.0, 760.0, 900.0, 1100.0, 1300.0,
        1500.0, 1700.0, 1900.0, 1955.0]
    tiles = []
    for i, z in enumerate(zs):
        sc.z = z
        sc.lane = 0.0
        sc.speed = 0.0
        sc.draw(screen)
        path = os.path.join(OUT, "z_%04d.png" % int(z))
        pygame.image.save(screen, path)
        print("wrote", path)
        tiles.append(pygame.transform.smoothscale(screen, (WIDTH // 3, HEIGHT // 3)))
    if tiles:
        tw, th = tiles[0].get_size()
        sheet = pygame.Surface((tw * 3, th * ((len(tiles) + 2) // 3)))
        sheet.fill((10, 10, 12))
        for i, t in enumerate(tiles):
            sheet.blit(t, ((i % 3) * tw, (i // 3) * th))
        pygame.image.save(sheet, os.path.join(OUT, "strip.png"))
        print("wrote", os.path.join(OUT, "strip.png"))


if __name__ == "__main__":
    main()
