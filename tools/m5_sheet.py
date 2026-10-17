"""Contact sheet for review: python tools/m5_sheet.py out.jpg name1 name2 ...

Tiles PNGs from tools/m5_r2_shots/ into a 2-column JPEG (each 480x336) and
prints its base64 between markers so a remote reviewer can view it.
"""
import base64
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SHOTS = os.path.join(ROOT, "tools", "m5_r2_shots")
TW = int(os.environ.get("M5_TW", "480"))
TH = TW * 7 // 10


def main():
    pygame.init()
    out, names = sys.argv[1], sys.argv[2:]
    cols = 2 if len(names) > 1 else 1
    rows = (len(names) + cols - 1) // cols
    sheet = pygame.Surface((TW * cols, TH * rows))
    for i, n in enumerate(names):
        crop = None
        if "@" in n:                     # name@x,y,w,h -> zoom a region
            n, c = n.split("@")
            crop = pygame.Rect(*[int(v) for v in c.split(",")])
        img = pygame.image.load(os.path.join(SHOTS, n + ".png"))
        if crop:
            img = img.subsurface(crop).copy()
        sheet.blit(pygame.transform.smoothscale(img, (TW, TH)), ((i % cols) * TW, (i // cols) * TH))
    path = os.path.join(SHOTS, out)
    pygame.image.save(sheet, path)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode()
    print("B64START" + data + "B64END")


if __name__ == "__main__":
    main()
