"""Presidential Guard banner (36 x 57 px, 1.2 x 1.9 m): brass rod, black
cloth with folds lit from the left, gold eagle, red band "GUARD",
swallowtail hem with gold fringe."""
import math

import pygame

from art.m5 import _kit as K

W, H = 36, 57
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H)
    s.fill(K.BRASS, (0, 0, W, 2))                               # rod
    s.fill(K.GOLD_HI, (0, 0, W, 1))
    s.fill(K.GOLD_HI, (0, 0, 2, 2))                             # finial catch-light
    for x in range(1, W - 1):                                   # cloth with three soft folds
        f = 0.5 + 0.5 * math.cos((x - 2) / (W - 4) * math.pi * 3)
        col = K.mix((18, 16, 18), (40, 37, 40), round(f * 2) / 2)
        s.fill(col, (x, 2, 1, H - 8))
    for x in range(1, W - 1):                                   # swallowtail hem
        d = abs(x - W / 2) / (W / 2)
        bot = int(H - 6 + 4 * d)
        s.fill(s.get_at((x, 10))[:3], (x, H - 6, 1, bot - (H - 6)))
        s.set_at((x, bot), K.BRASS if x % 2 else K.GOLD_LO)     # fringe
    # gold eagle: spread wings, head turned left (to the light)
    cx, cy = 18, 17
    gold = K.BRASS
    pygame.draw.polygon(s, gold, [(cx, cy + 2), (cx - 12, cy - 5), (cx - 9, cy + 1), (cx - 12, cy + 2), (cx - 4, cy + 6)])
    pygame.draw.polygon(s, gold, [(cx, cy + 2), (cx + 12, cy - 5), (cx + 9, cy + 1), (cx + 12, cy + 2), (cx + 4, cy + 6)])
    pygame.draw.rect(s, gold, (cx - 2, cy - 3, 4, 11))          # body
    pygame.draw.rect(s, gold, (cx - 3, cy - 6, 4, 3))           # head
    s.fill(K.GOLD_HI, (cx - 4, cy - 6, 2, 1))                   # beak
    s.fill(K.GOLD_HI, (cx - 11, cy - 5, 5, 1))                  # lit wing edge
    s.fill(K.GOLD_LO, (cx + 1, cy - 2, 1, 9))                   # body shade, right
    s.fill(gold, (cx - 4, cy + 8, 8, 1))                        # talons
    pygame.draw.polygon(s, K.GOLD_HI, [(cx, cy - 13), (cx - 2, cy - 9), (cx + 2, cy - 9)])  # star
    s.fill(K.GUARD_RED, (1, 32, W - 2, 11))                     # red band
    s.fill((206, 70, 60), (1, 32, W - 2, 1))
    s.fill((110, 22, 22), (1, 42, W - 2, 1))
    K.text_c(s, "GUARD", 18, 34, (20, 16, 16))
    return K.scaled(s, scale)
