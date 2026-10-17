"""Safehouse wall calendar (24 x 32 px, 0.6 x 0.8 m): red 1991 header, month
grid, one day ringed in red, nail at the top."""
import pygame

from game.art.m5 import _kit as K

W, H = 24, 32
VARIANTS = 1


def render(variant=0, scale=1):
    s = K.new(W, H, (226, 218, 196))
    s.fill((170, 40, 36), (0, 0, W, 10))
    s.fill((206, 76, 66), (0, 0, W, 1))                         # lit top edge
    K.text_c(s, "1991", W // 2, 2, (240, 232, 214))
    s.fill(K.INK, (11, 0, 2, 1))                                 # nail
    for r in range(5):
        for c in range(6):
            x, y = 2 + c * 4, 12 + r * 4
            s.fill((120, 110, 98) if c < 5 else (170, 60, 50), (x, y, 2, 2))
    pygame.draw.rect(s, (190, 40, 36), (9, 19, 6, 5), 1)         # the circled day
    s.fill((150, 140, 118), (0, H - 2, W, 1))                    # tear-off stubs
    K.curl(s, (0, 0, 0))
    return K.scaled(s, scale)
