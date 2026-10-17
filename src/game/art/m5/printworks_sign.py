""""MAG PRINT WORKS" enamel sign over the Print Works (96 x 14 px, 8.4 x 1.3 m).

variant 0  all bulbs lit
variant 1  the R has blown (used on the flicker beat)
"""
from game.art.m5 import _kit as K

W, H = 96, 14
VARIANTS = 2
TEXT = "MAG PRINT WORKS"
LIT = (246, 206, 132)
DEAD = (70, 58, 44)


def render(variant=0, scale=1):
    s = K.new(W, H, (22, 24, 28))
    K.bevel(s, (0, 0, W, H), (64, 66, 74), (8, 8, 10))
    s.fill((30, 32, 38), (2, 2, W - 4, 1))                     # enamel sheen, top
    for x, y in ((2, 2), (W - 3, 2), (2, H - 3), (W - 3, H - 3)):   # rivets
        s.fill(K.GOLD_LO, (x, y, 1, 1))
    # warm halo under each letter so the board itself glows a little
    K.text_c(s, TEXT, W // 2 + 1, 4, (60, 44, 26), skip=(5,) if variant == 1 else ())
    K.text_c(s, TEXT, W // 2, 3, (LIT, DEAD), skip=(5,) if variant == 1 else ())
    return K.scaled(s, scale)
