"""portrait_refs.py - check the radio portraits against the cutscene cast.

    python tools/sprites/portrait_refs.py [OUT.png] [--b64]

One row per cast member: the 2D cutscene head (cutscenes.figure_kit,
facing right, exactly as the cutscenes draw it), then the spr_portraits
frame at 4x nearest. The 3D rigs derive from the same figure_kit SPECS
(cutscenes.cast3d.spec3d); render them with ``tools/cast_lineup.py face``.
Default OUT: previews/sprites/portrait_refs.png
"""
import base64
import json
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pygame  # noqa: E402

# portrait key -> figure_kit key (faces only; insignia have no cast figure)
PAIRS = (("biribel", "biribel"), ("vasile", "vasile"), ("volkov", "volkov"),
         ("commander", "commander"), ("fisherman", "fisherman"), ("balaceanu", "balaceanu"),
         ("president", "president"), ("maru", "maru"), ("bodi", "bodi"), ("alex", "alex"),
         ("ucilev", "ucilev"), ("krap_command", "krap"), ("ipa_dispatch", "ipa"),
         ("old_squadmate", "krap"), ("gabi", "krap"), ("seby", "civilian"),
         ("darius", "krap"), ("old_woman", "civilian"), ("hungry_kid", "civilian"))
CELL = 112


def head_2d(who):
    from cutscenes.figure_kit import draw_character
    k = 2.0
    s = pygame.Surface((300, 700))
    bg = (40, 44, 50)
    s.fill(bg)
    draw_character(s, who, 150, 690, scale=k, facing_right=True)
    # head box: find the topmost drawn row, take a square under it
    top = next(y for y in range(700) if any(s.get_at((x, y))[:3] != bg for x in range(0, 300, 2)))
    box = pygame.Rect(150 - 64, top - 4, 128, 128)
    return s.subsurface(box.clip(s.get_rect())).copy()


def main(argv):
    pygame.init()
    pygame.display.set_mode((1, 1))
    out = next((a for a in argv if not a.startswith("--")),
               os.path.join(ROOT, "previews", "sprites", "portrait_refs.png"))
    art = os.path.join(ROOT, "assets", "art")
    img = pygame.image.load(os.path.join(art, "spr_portraits.png"))
    frames = json.load(open(os.path.join(art, "spr_portraits.json"), encoding="utf-8"))["frames"]
    font = pygame.font.Font(None, 18)
    cols = 4
    rows = (len(PAIRS) + cols - 1) // cols
    sheet = pygame.Surface((cols * (CELL * 2 + 36), rows * (CELL + 22)))
    sheet.fill((22, 24, 28))
    for i, (pk, fk) in enumerate(PAIRS):
        x0 = (i % cols) * (CELL * 2 + 36) + 8
        y0 = (i // cols) * (CELL + 22) + 4
        h = pygame.transform.scale(head_2d(fk), (CELL, CELL))
        sheet.blit(h, (x0, y0 + 18))
        x, y, w, hh = frames[pk]["rect"]
        p = pygame.transform.scale(img.subsurface((x, y, w, hh)), (w * 4, hh * 4))
        sheet.fill((40, 44, 50), (x0 + CELL + 8, y0 + 18, CELL, CELL))
        sheet.blit(p, (x0 + CELL + 8 + (CELL - w * 4) // 2, y0 + 18 + (CELL - hh * 4)))
        sheet.blit(font.render("%s  (2D: %s)" % (pk, fk), True, (230, 220, 200)), (x0, y0))
    out = os.path.abspath(out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    pygame.image.save(sheet, out)
    print("saved", out)
    if "--b64" in argv:
        print("B64START" + base64.b64encode(open(out, "rb").read()).decode() + "B64END")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
