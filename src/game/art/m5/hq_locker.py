"""Guard HQ steel locker (26 x 44 px, top-down gameplay prop). The dead man's
name strip is taped over in black. Key light from the upper-left: lit left
edge and top lip, shaded right edge. Replaces draw._draw_hq_locker."""
import pygame

from game.art.m5 import _kit as K

W, H = 26, 44
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H)
    s.fill((62, 68, 74), (0, 0, W, H))
    s.fill((84, 90, 98), (0, 0, 4, H))                          # lit left edge
    s.fill((40, 44, 50), (W - 4, 0, 4, H))                      # shaded right edge
    s.fill((92, 98, 106), (1, 1, W - 2, 1))                     # top lip catches light
    cx = W // 2
    pygame.draw.line(s, (34, 36, 40), (cx, 2), (cx, H - 3), 1)  # door split
    for vy in range(6, 16, 3):                                  # vents
        pygame.draw.line(s, (30, 32, 36), (6, vy), (cx - 3, vy), 1)
        pygame.draw.line(s, (30, 32, 36), (cx + 3, vy), (W - 6, vy), 1)
        pygame.draw.line(s, (74, 80, 88), (6, vy + 1), (cx - 3, vy + 1), 1)
    s.fill((12, 12, 14), (5, 20, W - 10, 6))                    # black tape strip
    s.fill((30, 30, 34), (5, 20, W - 10, 1))
    s.fill((150, 150, 140), (cx - 6, 30, 3, 6))                 # handle
    s.fill((190, 190, 178), (cx - 6, 30, 1, 6))
    pygame.draw.rect(s, (24, 26, 30), (0, 0, W, H), 1)
    return K.scaled(s, scale)
