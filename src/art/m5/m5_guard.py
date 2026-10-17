"""Presidential Guard trooper, top-down gameplay sprite (96 x 96, figure
centred at (48, 48), facing +x). Same body grammar as the other enemy
families: flat black tunic, sleeve arms to the weapon, skin hands, skin head
with Guard headgear, red armband. draw._draw_m5_guard rotates it into a
cached angle bucket and adds the walk sway, eyes and hit ring live.

Variant 0: rifleman (beret), 1: marksman (beret, long rifle + scope),
2: raider (steel helmet). Replaces the per-frame polygon drawing."""
import pygame

from art.m5 import _kit as K

VARIANTS = 3
SIZE = 96
C = SIZE // 2
KIT = (58, 58, 68)
SEAM = (76, 76, 88)
BELT = (30, 28, 30)
ARMBAND = (200, 30, 30)
BERET = (18, 18, 22)
HELMET = (40, 42, 46)
SKIN = (190, 160, 130)


def _L(f, sd):
    return (C + f, C + sd)


def _I(p):
    return (int(p[0]), int(p[1]))


def render(variant=0, scale=1):
    kind = ("rifleman", "marksman", "raider")[int(variant) % VARIANTS]
    s = K.new(SIZE, SIZE)
    L = _L
    pygame.draw.polygon(s, KIT, [L(-6.5, -10), L(6.5, -10), L(6.5, 10), L(-6.5, 10)])
    pygame.draw.line(s, SEAM, L(-4, 0), L(4, 0), 2)                        # tunic seam
    pygame.draw.line(s, BELT, L(-1, -10), L(-1, 10), 2)                    # cross belt
    arm_len = 15
    hand = L(arm_len, 0)
    pygame.draw.line(s, KIT, L(0, 11), (hand[0], hand[1] - 3), 5)
    pygame.draw.line(s, KIT, L(0, -11), (hand[0], hand[1] + 3), 5)
    pygame.draw.line(s, ARMBAND, _I(L(0, 9)), _I(L(4, 9)), 3)              # armband, left sleeve
    grip = L(arm_len + 4, 0)
    glen = 26 if kind == "marksman" else 20
    pygame.draw.circle(s, SKIN, _I(grip), 4)
    pygame.draw.line(s, (30, 28, 26), L(arm_len + 6, 0), L(arm_len + 4 + glen, 0), 3)
    pygame.draw.circle(s, (52, 50, 48), _I(L(arm_len + 4 + glen, 0)), 2)
    if kind == "marksman":
        pygame.draw.line(s, (20, 20, 22), L(arm_len + 7, 0), L(arm_len + 13, 0), 5)   # scope
    hr = 8
    pygame.draw.circle(s, SKIN, _I(L(2, 0)), hr)
    if kind == "raider":
        pygame.draw.circle(s, HELMET, _I(L(-1, 0)), hr + 1)
        pygame.draw.circle(s, SKIN, _I(L(4, 0)), hr - 3)
        pygame.draw.line(s, (20, 20, 22), L(3, -hr + 1), L(3, hr - 1), 1)  # chin strap
    else:
        pygame.draw.circle(s, BERET, _I(L(-2, -1)), hr)
        pygame.draw.circle(s, SKIN, _I(L(3, 1)), hr - 3)
        pygame.draw.circle(s, ARMBAND, _I(L(-5, -5)), 2)                   # cockade
    return K.scaled(s, scale)
