"""Montage of selected baked M5 sprites for review.

    python tools/m5_sprite_review.py OUT.png name:variant[:zoom] ...

Each tile sits on a mid-grey wall; the lower half has a dark backing so
alpha edges show against both."""
import os
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import pygame  # noqa: E402


def main():
    pygame.init()
    out = sys.argv[1]
    tiles = []
    for spec in sys.argv[2:]:
        parts = spec.split(":")
        name, v = parts[0], int(parts[1])
        z = float(parts[2]) if len(parts) > 2 else 3
        s = pygame.image.load(str(ROOT / "assets" / "baked" / "m5" / ("%s_%d.png" % (name, v))))
        w, h = s.get_size()
        tiles.append(pygame.transform.scale(s, (max(1, int(w * z)), max(1, int(h * z)))))
    pad = 10
    W = sum(t.get_width() + pad for t in tiles) + pad
    H = max(t.get_height() for t in tiles) + 2 * pad
    sheet = pygame.Surface((W, H))
    sheet.fill((70, 66, 62))
    x = pad
    for t in tiles:
        hh = t.get_height() // 2
        sheet.fill((34, 32, 30), (x, pad + hh, t.get_width(), t.get_height() - hh))
        sheet.blit(t, (x, pad))
        x += t.get_width() + pad
    pygame.image.save(sheet, out)
    print("REVIEW", out, W, H)


if __name__ == "__main__":
    main()
