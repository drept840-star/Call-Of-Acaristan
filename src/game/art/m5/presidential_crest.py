"""State crests (40 x 40 px).

variant 0  presidential seal over the podium (1.6 m): laurel-ringed gold
           medallion, red shield, black eagle, gold star
variant 1  old KRAP party crest in the depot (1.0 m): blue disc, cream gear,
           the party torch - half-painted-over
Gold is lit from the upper-left (bright rim top-left, dark rim bottom-right).
"""
import math

import pygame

from game.art.m5 import _kit as K

W, H = 40, 40
VARIANTS = 2


def _rim(s, cx, cy, r, base, hi, lo):
    pygame.draw.circle(s, base, (cx, cy), r)
    for k in range(72):
        a = k * math.pi / 36
        lit = math.cos(a - math.radians(225))            # 225 deg = upper-left in screen y-down
        col = hi if lit > 0.45 else (lo if lit < -0.45 else base)
        x, y = cx + (r - 1) * math.cos(a), cy + (r - 1) * math.sin(a)
        s.fill(col, (int(round(x)) - 1, int(round(y)) - 1, 2, 2))


def _seal(s):
    cx = cy = 20
    _rim(s, cx, cy, 19, K.BRASS, K.GOLD_HI, K.GOLD_LO)
    for k in range(16):                                  # laurel leaves
        a = k * math.pi / 8 + 0.2
        x, y = cx + 15 * math.cos(a), cy + 15 * math.sin(a)
        s.fill((96, 120, 54) if k % 2 else (124, 146, 70), (int(x) - 1, int(y) - 1, 3, 2))
    shield = [(cx - 9, cy - 10), (cx + 9, cy - 10), (cx + 9, cy + 2), (cx, cy + 11), (cx - 9, cy + 2)]
    pygame.draw.polygon(s, (160, 30, 30), shield)
    pygame.draw.polygon(s, K.GOLD_HI, shield, 1)
    s.fill((196, 60, 54), (cx - 8, cy - 9, 3, 9))         # lit left of shield
    pygame.draw.polygon(s, K.INK, [(cx, cy), (cx - 7, cy - 5), (cx - 5, cy + 1), (cx - 1, cy + 5)])
    pygame.draw.polygon(s, K.INK, [(cx, cy), (cx + 7, cy - 5), (cx + 5, cy + 1), (cx + 1, cy + 5)])
    s.fill(K.INK, (cx - 1, cy - 5, 3, 10))
    s.fill(K.INK, (cx - 2, cy - 7, 3, 2))
    pygame.draw.polygon(s, K.GOLD_HI, [(cx, cy - 16), (cx - 2, cy - 12), (cx + 2, cy - 12)])


def _krap(s):
    cx = cy = 20
    _rim(s, cx, cy, 19, K.KRAP_BLUE, (110, 146, 206), (28, 48, 92))
    for k in range(12):                                  # gear teeth
        a = k * math.pi / 6
        x, y = cx + 12 * math.cos(a), cy + 12 * math.sin(a)
        s.fill(K.CREAM, (int(x) - 2, int(y) - 2, 4, 4))
    pygame.draw.circle(s, K.CREAM, (cx, cy), 11)
    pygame.draw.circle(s, K.KRAP_BLUE, (cx, cy), 7)
    pygame.draw.polygon(s, K.CREAM, [(cx - 2, cy - 1), (cx + 2, cy - 1), (cx + 1, cy + 6), (cx - 1, cy + 6)])  # torch
    pygame.draw.polygon(s, (226, 150, 70), [(cx, cy - 7), (cx - 3, cy - 2), (cx + 3, cy - 2)])   # flame
    s.fill((240, 232, 210), (cx - 10, cy - 7, 3, 2))      # gear highlight, upper-left


def render(variant=0, scale=1):
    s = K.new(W, H)
    (_seal, _krap)[variant % VARIANTS](s)
    return K.scaled(s, scale)
