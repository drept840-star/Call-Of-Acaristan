"""HUD magazine-icon shells (weapon panel). The shell art is static per kind
and state, so it is baked; only the live round count (witness holes / round
stack) is overlaid at runtime by draw._draw_m5_mag_icon.

Variant = kind * 3 + state, kind 0 = stick (K-9 / OS-12), 1 = tapered box
mag; state 0 = empty, 1 = active, 2 = idle.
Stick sprite: 26 x 55, blit at (mx, my - 3). Box sprite: 25 x 47 at (mx, my).
Key light upper-left: lit left flank strip on both kinds."""
import pygame

from game.art.m5 import _kit as K

VARIANTS = 6
C_TERMINAL = (50, 255, 150)
STICK_OFFSET = (0, -3)
BOX_OFFSET = (0, 0)


def _stick(state):
    s = K.new(26, 55)
    bx, by, mw, mh = 5, 3, 14, 52
    if state == 0:
        base, rim, hi = (24, 28, 28), (52, 62, 58), (36, 42, 40)
    elif state == 1:
        base, rim, hi = (36, 48, 44), (120, 230, 180), (70, 92, 84)
    else:
        base, rim, hi = (32, 38, 36), (86, 112, 102), (54, 66, 62)
    right, bottom = bx + mw, by + mh
    poly = [(bx + 1, by), (right - 1, by + 1), (right - 3, bottom), (bx + 3, bottom)]
    pygame.draw.polygon(s, base, poly)
    pygame.draw.polygon(s, rim if state == 1 else (64, 70, 66), poly, 1)
    pygame.draw.line(s, hi, (bx + 4, by + 4), (bx + 5, bottom - 5), 1)
    pygame.draw.rect(s, (80, 86, 78), (bx + 2, by - 3, mw - 2, 4), border_radius=1)
    pygame.draw.rect(s, (18, 20, 20), (bx + 1, bottom - 4, mw - 1, 5), border_radius=1)
    for row_i in range(12):                       # empty witness holes
        wy = bottom - 8 - row_i * 3
        for wx_off in (5, 9):
            pygame.draw.circle(s, (18, 20, 20), (bx + wx_off, wy), 1)
    if state == 1:
        pygame.draw.line(s, (120, 230, 180), (right + 3, by + 4), (right + 3, bottom - 4), 2)
    return s


def _box(state):
    s = K.new(25, 47)
    top_w, bot_w, h = 24, 20, 46
    taper = (top_w - bot_w) // 2
    pts = [(0, 0), (top_w, 0), (taper + bot_w, h), (taper, h)]
    if state == 0:
        base, hl, rim = (45, 42, 38), (55, 52, 48), (55, 50, 45)
    elif state == 1:
        base, hl, rim = (90, 86, 78), (115, 110, 100), (70, 66, 58)
    else:
        base, hl, rim = (72, 68, 62), (92, 88, 80), (60, 56, 50)
    pygame.draw.polygon(s, base, pts)
    pygame.draw.polygon(s, hl, [(1, 2), (5, 2), (taper + 3, h - 3), (taper + 1, h - 3)])
    pygame.draw.polygon(s, C_TERMINAL if state == 1 else rim, pts, 1)
    dark = (40, 38, 35) if state == 0 else (55, 52, 48)
    for bi in range(12):                          # empty round stack
        pygame.draw.circle(s, dark, (top_w // 2, 8 + bi * 3), 2)
    return s


def render(variant=0, scale=1):
    kind, state = divmod(int(variant) % VARIANTS, 3)
    return K.scaled(_stick(state) if kind == 0 else _box(state), scale)
