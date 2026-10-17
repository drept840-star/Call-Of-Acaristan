"""The black Guard armband pinned to the depot notice board (25 x 8 px, 0.5 x 0.16 m):
black cloth with a red stripe, folded over itself, brass safety pin."""
from game.art.m5 import _kit as K

W, H = 25, 8
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H)
    s.fill((26, 26, 30), (0, 1, W, 6))
    s.fill((44, 44, 50), (0, 1, W, 1))                          # lit top edge
    s.fill((12, 12, 14), (0, 6, W, 1))
    s.fill(K.GUARD_RED, (0, 3, W, 2))
    s.fill((206, 70, 60), (0, 3, W, 1))
    s.fill((14, 14, 16), (16, 0, 2, H))                         # the fold
    s.fill((54, 54, 60), (15, 0, 1, H))
    s.fill(K.GOLD_HI, (3, 2, 6, 1))                             # safety pin
    s.fill(K.BRASS, (3, 5, 6, 1))
    s.fill(K.BRASS, (2, 2, 1, 4))
    return K.scaled(s, scale)
