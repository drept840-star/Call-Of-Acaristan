"""Vasile's district map (52 x 36 px, 1.3 x 0.9 m): street grid, the river,
the Lower Quarter ringed in red, "SECTOR 4" title strip."""
import pygame

from game.art.m5 import _kit as K

W, H = 52, 36
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H, (196, 182, 142))
    K.bevel(s, (0, 0, W, H), (226, 214, 180), (120, 108, 80))
    s.fill((150, 136, 100), (2, 2, W - 4, 9))
    K.text_c(s, "SECTOR 4", W // 2, 3, K.INK)
    block = (172, 156, 116)
    for gy in range(4):                                         # city blocks
        for gx in range(7):
            x, y = 3 + gx * 7, 13 + gy * 5
            if (gx * 3 + gy) % 5 == 0:
                continue                                        # squares / parks
            s.fill(block, (x, y, 6, 4))
    s.fill((150, 170, 112), (3 + 7 * 0, 13 + 5 * 0, 6, 4))      # the park
    pts = [(2, 30), (12, 27), (22, 29), (32, 24), (42, 26), (50, 20)]
    pygame.draw.lines(s, (92, 110, 124), False, pts, 3)         # the river
    pygame.draw.lines(s, (130, 148, 160), False, [(x, y - 1) for x, y in pts], 1)
    q = pygame.Rect(30, 12, 18, 11)                             # the Lower Quarter
    for x in range(q.left, q.right, 2):
        s.set_at((x, q.top), K.RED); s.set_at((x, q.bottom - 1), K.RED)
    for y in range(q.top, q.bottom, 2):
        s.set_at((q.left, y), K.RED); s.set_at((q.right - 1, y), K.RED)
    s.fill(K.INK, (W - 8, H - 7, 1, 4))                         # north arrow
    s.fill(K.INK, (W - 9, H - 6, 3, 1))
    return K.scaled(s, scale)
