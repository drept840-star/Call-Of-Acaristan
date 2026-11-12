"""Render the M8 descent film frames and the first chase frame, and check the handoff.

    python tools/m8_descent_shots.py [--software] [--out=_shots/m8_descent]

Writes one PNG per frame, a side-by-side of the film's last frame and the first
gameplay frame, and prints how many pixels differ between them (the HUD is left
out of the gameplay frame, so a clean handoff reports 0).
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

OUT = "_shots/m8_descent"
for a in sys.argv:
    if a.startswith("--out="):
        OUT = a.split("=", 1)[1]


def _save(surface, name):
    path = os.path.join(OUT, name + ".png")
    pygame.image.save(surface, path)
    print("wrote", path)
    return path


def main():
    pygame.init()
    from core.config import WIDTH, HEIGHT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    os.makedirs(OUT, exist_ok=True)
    from cutscenes import m8films as F
    from missions.m8.revenge import chase3d as C

    film = [("body_t2000", F.descent_body, 2000),
            ("ladder_t2000", F.descent_ladder, 2000),
            ("geton_t1500", F.descent_geton, 1500),
            ("pullout_t2500", F.descent_pullout, 2500),
            ("pullout_t3500", F.descent_pullout, 3500),
            ("pullout_last_t4500", F.descent_pullout, 4500)]
    mid = None
    for name, fn, t in film:
        fn(screen, t)
        _save(screen, name)
        if name == "pullout_t3500":
            mid = screen.copy()
    last = pygame.Surface(screen.get_size())
    last.blit(screen, (0, 0))

    sc = C.scene()
    sc.begin()
    hud = sc._hud
    sc._hud = lambda surface: None          # the 3D picture only, for the handoff diff
    sc.draw(screen)
    first = pygame.Surface(screen.get_size())
    first.blit(screen, (0, 0))
    _save(screen, "chase_first")
    sc._hud = hud
    sc.draw(screen)
    _save(screen, "chase_first_hud")

    w, h = screen.get_size()
    pw, ph = w // 3, h // 3
    strip = pygame.Surface((pw * 3 + 8, ph))
    strip.fill((10, 10, 12))
    for i, panel in enumerate((mid, last, first)):
        strip.blit(pygame.transform.smoothscale(panel, (pw, ph)), (i * (pw + 4), 0))
    _save(strip, "side_by_side_traffic_last_chase")
    pair = pygame.Surface((pw * 2 + 4, ph))
    pair.fill((10, 10, 12))
    pair.blit(pygame.transform.smoothscale(last, (pw, ph)), (0, 0))
    pair.blit(pygame.transform.smoothscale(first, (pw, ph)), (pw + 4, 0))
    _save(pair, "handoff_film_last_vs_chase_first")

    a = pygame.image.tobytes(last, "RGB")
    b = pygame.image.tobytes(first, "RGB")
    differ = sum(1 for i in range(0, len(a), 3) if a[i:i + 3] != b[i:i + 3])
    print("handoff pixels differing (film last vs chase first, no HUD): %d of %d"
          % (differ, w * h))


if __name__ == "__main__":
    main()
