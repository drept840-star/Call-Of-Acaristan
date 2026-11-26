"""Render the M8 Duty ending films (crash + epilogue, plus liftoff) as contact sheets.

    python tools/m8_duty_film_shots.py [--software] [--out=_shots/m8_duty_films] [--only=crash|epilogue|liftoff]

One PNG per shot at 25/60/95% of its timeline length, plus a per-film contact sheet.
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

OUT = "_shots/m8_duty_films"
ONLY = None
for a in sys.argv:
    if a.startswith("--out="):
        OUT = a.split("=", 1)[1]
    if a.startswith("--only="):
        ONLY = a.split("=", 1)[1]

FILMS = {
    "liftoff": [("liftoff_study", 4000), ("liftoff_window", 4600), ("liftoff_maru", 4600)],
    "crash": [("crash_spin", 3600), ("crash_black", 2200), ("crash_fire", 4600),
              ("crash_promise", 3000), ("crash_better", 2600)],
    "epilogue": [("inauguration", 5400), ("vasile_speech", 5000), ("crowd", 5000),
                 ("eyes", 4200), ("biribel_vo", 5400), ("title_card", 6000)],
}


def main():
    pygame.init()
    from core.config import WIDTH, HEIGHT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    os.makedirs(OUT, exist_ok=True)
    from cutscenes import m8dutyfilms as F

    for film, shots in FILMS.items():
        if ONLY and ONLY != film:
            continue
        panels = []
        for name, dur in shots:
            fn = getattr(F, name)
            for frac in (0.25, 0.60, 0.95):
                t = int(dur * frac)
                screen.fill((0, 0, 0))
                fn(screen, t)
                tag = "%s_%s_t%04d" % (film, name, t)
                pygame.image.save(screen, os.path.join(OUT, tag + ".png"))
                panels.append((tag, screen.copy()))
                print("wrote", tag)
        pw, ph = WIDTH // 3, HEIGHT // 3
        cols = 3
        rows = (len(panels) + cols - 1) // cols
        sheet = pygame.Surface((cols * (pw + 4), rows * (ph + 14)))
        sheet.fill((8, 8, 10))
        font = pygame.font.SysFont("consolas", 11)
        for i, (tag, img) in enumerate(panels):
            x = (i % cols) * (pw + 4)
            y = (i // cols) * (ph + 14)
            sheet.blit(pygame.transform.smoothscale(img, (pw, ph)), (x, y + 12))
            sheet.blit(font.render(tag, True, (200, 200, 200)), (x + 2, y))
        path = os.path.join(OUT, "sheet_%s.png" % film)
        pygame.image.save(sheet, path)
        print("wrote", path)


if __name__ == "__main__":
    main()