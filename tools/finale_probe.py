"""Render M5 finale frames (optionally from custom cameras) into a JPEG contact sheet.

    python tools/finale_probe.py OUT.jpg COLS THUMB_W spec [spec ...]
    spec = t                      (film camera at t ms)
         | t@ex,ey,ez@tx,ty,tz@fov  (custom camera at t ms)
Prints the sheet path. Frames also saved as outputs/finale_probe/NN.png.
"""
import os, sys
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))
os.chdir(ROOT)
import pygame


def main():
    out, cols, tw = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    specs = sys.argv[4:]
    pygame.init()
    from core.config import WIDTH, HEIGHT
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    from cutscenes import m5shadow3d as m5
    m5.prepare()
    orig = m5._camera
    os.makedirs("outputs/finale_probe", exist_ok=True)
    film_h = m5.BOT - m5.TOP
    th = int(tw * film_h / WIDTH)
    rows = (len(specs) + cols - 1) // cols
    sheet = pygame.Surface((cols * tw, rows * th))
    for i, spec in enumerate(specs):
        parts = spec.split("@")
        t = float(parts[0])
        if len(parts) == 4:
            eye = tuple(float(v) for v in parts[1].split(","))
            tgt = tuple(float(v) for v in parts[2].split(","))
            fov = float(parts[3])
            m5._camera = lambda _t, e=eye, g=tgt, f=fov: (e, g, f, "probe")
        else:
            m5._camera = orig
        screen.fill((0, 0, 0))
        m5.draw(screen, t)
        film = screen.subsurface(pygame.Rect(0, m5.TOP, WIDTH, film_h)).copy()
        pygame.image.save(film, f"outputs/finale_probe/{i:02d}.png")
        sheet.blit(pygame.transform.smoothscale(film, (tw, th)), ((i % cols) * tw, (i // cols) * th))
    m5._camera = orig
    pygame.image.save(sheet, out)
    print("SHEET", out)


if __name__ == "__main__":
    main()
