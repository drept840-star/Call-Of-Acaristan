"""Top-down wall posters for the gameplay maps (the wall is seen as its front band).

variant 0  "MAG 1991"   cream bill, 60 x 16 (Maru's office)
variant 1  "FREE PRESS" red bill,   60 x 16 (Maru's office)
variant 2  "FREE"       red bill,   54 x 16 (press hall)
variant 3  "MAG"        cream bill, 54 x 16 (press hall)
variant 4  "TRUTH"      navy bill,  54 x 16 (press hall)
variant 5  curfew order strip, 26 x 8 (Lower Quarter facades)
variant 6  Guard propaganda strip, 26 x 8 (Lower Quarter facades)
Lit from the upper-left: bright top/left edge, shade bottom/right.
"""
from art.m5 import _kit as K

VARIANTS = 7
#              text          size      paper            ink
_BILLS = (("MAG 1991", (60, 16), (236, 232, 218), (20, 20, 24)),
          ("FREE PRESS", (60, 16), (210, 60, 50), (236, 232, 218)),
          ("FREE", (54, 16), (210, 60, 50), (236, 232, 218)),
          ("MAG", (54, 16), (236, 232, 218), (186, 40, 34)),
          ("TRUTH", (54, 16), (40, 50, 80), (236, 232, 218)))
TEXTS = {b[0]: i for i, b in enumerate(_BILLS)}


def _edges(s, base):
    w, h = s.get_size()
    K.bevel(s, (0, 0, w, h), K.shade(base, 1.18), K.shade(base, 0.62))


def _bill(i):
    txt, (w, h), paper, ink = _BILLS[i]
    s = K.new(w, h, paper)
    _edges(s, paper)
    K.text_c(s, txt, w // 2, (h - 7) // 2, ink, sp=0 if K.text_w(txt) > w - 4 else 1)
    for x in (2, w - 3):                                  # drawing pins
        s.fill((150, 150, 150), (x, 1, 1, 1))
    return s


def _curfew():
    paper = (200, 190, 160)
    s = K.new(26, 8, paper)
    _edges(s, paper)
    s.fill(K.INK, (2, 2, 14, 2))                          # "CURFEW" header bar
    s.fill((120, 112, 96), (2, 5, 12, 1))                 # fine print
    s.fill((176, 46, 40), (19, 2, 4, 4))                  # stamp
    s.fill(paper, (20, 3, 2, 2))
    return s


def _guard():
    red = (150, 26, 30)
    s = K.new(26, 8, red)
    _edges(s, red)
    s.fill(K.INK, (3, 1, 3, 3))                           # helmeted head
    s.fill(K.INK, (2, 4, 6, 3))                           # shoulders
    s.fill(K.INK, (10, 2, 13, 3))                         # "GUARD" slogan block
    s.fill((206, 70, 60), (10, 2, 13, 1))
    return s


def render(variant=0, scale=1):
    v = variant % VARIANTS
    s = _bill(v) if v < len(_BILLS) else (_curfew() if v == 5 else _guard())
    return K.scaled(s, scale)
