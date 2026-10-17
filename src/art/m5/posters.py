"""Wall posters of the Lower Quarter (32 x 44 px, 0.64 x 0.88 m in the 3D sets).

variant 0  Guard propaganda: sunburst, helmeted Guard bust, "GUARD"
variant 1  curfew order: "CURFEW", red "22:00", fine print, stamp
variant 2  torn + bleached propaganda (variant 0 after a winter outside)
variant 3  faded KRAP party poster from before the Guard (blue, gear crest)
variant 4  MAG resistance print: woodcut fist, "FREE PRESS"
variant 5  MAG newsletter page: red masthead, columns, photo block
Light from the upper-left; paper curls off the wall bottom-right.
"""
import math

import pygame

from art.m5 import _kit as K

W, H = 32, 44
VARIANTS = 6


def _guard(s):
    s.fill(K.PAPER)
    sky = pygame.Rect(1, 1, W - 2, 31)
    s.fill((168, 36, 32), sky)
    cx, cy = 16, 26
    for k in range(12):                                     # sunburst rays
        if k % 2:
            continue
        a0, a1 = math.pi + k * math.pi / 12, math.pi + (k + 1) * math.pi / 12
        pygame.draw.polygon(s, (128, 22, 22), [(cx, cy), (cx + 40 * math.cos(a0), cy + 40 * math.sin(a0)),
                                               (cx + 40 * math.cos(a1), cy + 40 * math.sin(a1))])
    s.fill(K.PAPER, (0, 0, W, 1)); s.fill(K.PAPER, (0, 0, 1, H)); s.fill(K.PAPER, (W - 1, 0, 1, H))
    # Guard bust in profile, facing left (towards the light)
    pygame.draw.polygon(s, K.INK, [(6, 32), (9, 24), (14, 22), (22, 22), (27, 25), (29, 32)])  # shoulders
    pygame.draw.rect(s, K.INK, (12, 13, 9, 10))                              # head
    pygame.draw.polygon(s, K.INK, [(10, 13), (11, 8), (16, 6), (21, 7), (23, 12), (24, 14), (9, 14)])  # helmet
    pygame.draw.line(s, K.INK, (8, 14), (24, 14))                            # brim
    s.fill((210, 90, 70), (10, 9, 1, 4))                                     # rim light, upper-left
    s.fill((210, 90, 70), (11, 8, 4, 1))
    s.fill(K.GUARD_RED, (22, 26, 4, 2))                                      # armband
    s.fill(K.INK, (1, 32, W - 2, 11))                                        # slogan band
    K.text_c(s, "GUARD", 16, 34, K.PAPER, sp=0)
    K.curl(s, (0, 0, 0))


def _curfew(s):
    s.fill(K.PAPER)
    s.fill(K.INK, (1, 2, W - 2, 11))
    K.text_c(s, "CURFEW", 16, 4, K.PAPER, sp=0)
    K.text_c(s, "22:00", 16, 15, K.RED, sp=0)
    K.lines(s, 4, 25, W - 8, 4, (110, 102, 90), seed=3)
    K.lines(s, 4, 37, 12, 2, (110, 102, 90), seed=8)
    pygame.draw.circle(s, (176, 46, 40), (24, 37), 5, 1)                     # official stamp
    pygame.draw.circle(s, (176, 46, 40), (24, 37), 2)
    pygame.draw.line(s, (40, 40, 70), (5, 41), (14, 39))                     # signature
    s.fill((150, 140, 116), (0, 0, W, 1)); s.fill((150, 140, 116), (0, 0, 1, H))
    K.curl(s, (0, 0, 0))


def _torn(s):
    _guard(s)
    K.fade(s, (196, 182, 150), 0.38)
    for y in range(H):                                     # ripped away bottom-right
        edge = 34 - (y - 18) * 1.1 + ((y * 37) % 7) - 3 + (4 if 26 < y < 30 else 0)
        for x in range(W):
            if y > 18 and x > edge:
                s.set_at((x, y), K.CLEAR)
    for x in range(0, 9):                                  # torn top-left corner
        for y in range(0, 9 - x - (x % 3 == 0)):
            s.set_at((x, y), K.CLEAR)
    pygame.draw.rect(s, (170, 156, 120), (3, 30, 5, 3))    # paste stain


def _krap(s):
    s.fill((206, 196, 160))
    s.fill(K.KRAP_BLUE, (2, 2, W - 4, 27))
    cx, cy = 16, 14
    for k in range(10):                                    # gear teeth
        a = k * math.pi / 5
        s.fill(K.CREAM, (int(cx + 9 * math.cos(a)) - 1, int(cy + 9 * math.sin(a)) - 1, 3, 3))
    pygame.draw.circle(s, K.CREAM, (cx, cy), 8)
    pygame.draw.circle(s, K.KRAP_BLUE, (cx, cy), 5)
    pygame.draw.polygon(s, K.CREAM, [(cx - 2, cy - 4), (cx + 2, cy - 4), (cx + 1, cy + 4), (cx - 1, cy + 4)])
    s.fill((150, 180, 220), (cx - 7, cy - 6, 2, 2))        # highlight, upper-left
    K.text_c(s, "KRAP", 16, 32, K.KRAP_BLUE)
    K.fade(s, (200, 194, 172), 0.42)
    s.fill((178, 170, 146), (19, 0, 1, H))                 # old fold crease
    pygame.draw.ellipse(s, (184, 170, 132), (3, 34, 9, 6), 1)   # water stain ring
    K.curl(s, (0, 0, 0))


def _mag(s):
    s.fill((232, 226, 206))
    # woodcut fist breaking a chain, printed in red ink
    red = (186, 40, 34)
    pygame.draw.rect(s, red, (11, 6, 10, 9))               # fist
    for i in range(4):
        s.fill((232, 226, 206), (12 + i * 2 + (i > 1), 6, 1, 3))   # knuckle gaps
    pygame.draw.rect(s, red, (13, 15, 6, 9))               # wrist/forearm
    for x0 in (4, 22):                                     # broken chain links
        pygame.draw.ellipse(s, red, (x0, 10, 6, 4), 1)
    s.fill((240, 236, 222), (12, 7, 2, 1))                 # highlight, upper-left
    K.text_c(s, "FREE", 16, 27, red)
    K.text_c(s, "PRESS", 16, 35, K.INK)
    K.curl(s, (0, 0, 0))


def _news(s):
    s.fill((226, 220, 200))
    s.fill((186, 40, 34), (2, 2, W - 4, 9))
    K.text_c(s, "MAG", 16, 3, (240, 232, 214))
    s.fill(K.INK, (2, 12, W - 4, 1))
    s.fill((96, 92, 86), (3, 14, 13, 10))                  # photo block
    s.fill((140, 134, 124), (4, 15, 5, 3))
    K.lines(s, 18, 14, 11, 4, (100, 94, 86), seed=5)
    K.lines(s, 3, 27, 12, 5, (100, 94, 86), seed=11)
    K.lines(s, 18, 27, 11, 5, (100, 94, 86), seed=13)
    s.fill((140, 132, 116), (0, 0, W, 1)); s.fill((140, 132, 116), (0, 0, 1, H))
    K.curl(s, (0, 0, 0))


_DRAW = (_guard, _curfew, _torn, _krap, _mag, _news)


def render(variant=0, scale=1):
    s = K.new(W, H)
    _DRAW[variant % VARIANTS](s)
    return K.scaled(s, scale)
